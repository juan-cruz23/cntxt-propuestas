import json
import logging
import os
import threading

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import InsumoPropuestaIA, ServicioCatalogo, SolicitudPropuestaIA
from .services.ai_engine import aplicar_ajuste_conversacional, generar_propuesta_ia
from .services.drive_service import aprobar_y_archivar_en_drive
from .services.slack_service import (
    notificar_propuesta_lista,
    responder_en_hilo,
    verificar_firma_slack,
)

logger = logging.getLogger(__name__)


def _base_url(request) -> str:
    env_url = os.getenv('PUBLIC_BASE_URL', '').strip()
    if env_url:
        return env_url.rstrip('/')
    return f'{request.scheme}://{request.get_host()}'


def _clasificar_tipo_archivo(nombre: str, content_type: str) -> str:
    ct = (content_type or '').lower()
    ext = os.path.splitext((nombre or '').lower())[1]
    if ct.startswith('audio/') or ext in ('.mp3', '.wav', '.m4a', '.ogg', '.opus', '.aac', '.webm'):
        return 'audio'
    if ct.startswith('video/') or ext in ('.mp4', '.mov', '.avi', '.mkv'):
        return 'video'
    if ct.startswith('image/') or ext in ('.jpg', '.jpeg', '.png', '.webp', '.heic', '.gif'):
        return 'imagen'
    return 'documento'


@login_required
def admin_catalogo(request):
    categoria = request.GET.get('categoria', '').strip()
    modelo = request.GET.get('modelo', '').strip()
    q = request.GET.get('q', '').strip()

    servicios = ServicioCatalogo.objects.filter(activo=True)
    if categoria:
        servicios = servicios.filter(categoria=categoria)
    if modelo:
        servicios = servicios.filter(modelo_negocio=modelo)
    if q:
        servicios = servicios.filter(nombre__icontains=q) | servicios.filter(codigo__icontains=q)

    categorias = (
        ServicioCatalogo.objects.filter(activo=True)
        .values_list('categoria', flat=True)
        .distinct()
        .order_by('categoria')
    )
    return render(
        request,
        'admin_panel/catalogo.html',
        {
            'servicios': servicios,
            'categorias': categorias,
            'categoria_filtro': categoria,
            'modelo_filtro': modelo,
            'q': q,
            'total_catalogo': ServicioCatalogo.objects.filter(activo=True).count(),
        },
    )


@login_required
def admin_nueva_ia(request):
    if request.method == 'POST':
        cliente_nombre = request.POST.get('cliente_nombre', '').strip()
        empresa_cliente = request.POST.get('empresa_cliente', '').strip()
        nombre_proyecto = request.POST.get('nombre_proyecto_referencia', '').strip()
        ubicacion = request.POST.get('ubicacion', '').strip()
        transcript = request.POST.get('transcript_o_notas', '').strip()
        notificar_slack = 'notificar_slack' in request.POST

        if not cliente_nombre:
            messages.error(request, 'Ingresa al menos el nombre del cliente.')
            return render(request, 'admin_panel/ia_nueva.html')

        solicitud = SolicitudPropuestaIA.objects.create(
            creado_por=request.user.username,
            cliente_nombre=cliente_nombre,
            empresa_cliente=empresa_cliente,
            nombre_proyecto_referencia=nombre_proyecto,
            ubicacion=ubicacion,
            transcript_o_notas=transcript,
            estado_ia='pendiente',
        )

        # Guardar todos los archivos subidos (audios, fotos, videos)
        for field_name in ('audios', 'multimedia'):
            for f in request.FILES.getlist(field_name):
                tipo = 'audio' if field_name == 'audios' else _clasificar_tipo_archivo(f.name, getattr(f, 'content_type', ''))
                InsumoPropuestaIA.objects.create(
                    solicitud=solicitud,
                    archivo=f,
                    tipo=tipo,
                    nombre_original=f.name[:300],
                    mime_type=(getattr(f, 'content_type', '') or '')[:120],
                    tamano_bytes=getattr(f, 'size', 0) or 0,
                )

        try:
            generar_propuesta_ia(solicitud)
            if notificar_slack and os.getenv('SLACK_BOT_TOKEN') and os.getenv('SLACK_RED_CHANNEL_ID'):
                try:
                    notificar_propuesta_lista(solicitud, _base_url(request))
                    messages.success(request, 'Propuesta IA generada y notificada al canal de R.E.D. en Slack.')
                except Exception as slack_exc:
                    logger.warning('Propuesta creada pero falló Slack: %s', slack_exc)
                    messages.warning(
                        request,
                        f'Propuesta IA generada correctamente, pero no se pudo enviar a Slack: {slack_exc}',
                    )
            else:
                messages.success(request, 'Propuesta IA generada en borrador. Revisa el diagnóstico y los 3 niveles.')
            return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)
        except Exception as exc:
            logger.exception('Error generando propuesta IA')
            messages.error(request, f'Error al procesar con IA: {exc}')
            return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)

    return render(
        request,
        'admin_panel/ia_nueva.html',
        {
            'gemini_configurado': bool(os.getenv('GEMINI_API_KEY', '').strip()),
            'slack_configurado': bool(os.getenv('SLACK_BOT_TOKEN', '').strip() and os.getenv('SLACK_RED_CHANNEL_ID', '').strip()),
            'total_servicios': ServicioCatalogo.objects.filter(activo=True).count(),
        },
    )


@login_required
def admin_ia_detalle(request, pk):
    solicitud = get_object_or_404(SolicitudPropuestaIA, pk=pk)
    propuesta = solicitud.propuesta
    paquetes = propuesta.paquetes_casa_diseno if propuesta else []
    return render(
        request,
        'admin_panel/ia_detalle.html',
        {
            'solicitud': solicitud,
            'propuesta': propuesta,
            'paquetes': paquetes,
            'brief': solicitud.brief_json or {},
            'diagnostico': solicitud.diagnostico_json or {},
            'slack_configurado': bool(os.getenv('SLACK_BOT_TOKEN', '').strip() and os.getenv('SLACK_RED_CHANNEL_ID', '').strip()),
            'drive_configurado': bool(os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip() or os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '').strip()),
        },
    )


@login_required
@require_POST
def admin_ia_ajustar(request, pk):
    solicitud = get_object_or_404(SolicitudPropuestaIA, pk=pk)
    instruccion = request.POST.get('instruccion', '').strip()
    if not instruccion:
        messages.error(request, 'Escribe la instrucción de ajuste que deseas aplicar.')
        return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)
    try:
        resumen = aplicar_ajuste_conversacional(solicitud, instruccion, autor=request.user.username)
        messages.success(request, f'Ajuste aplicado: {resumen}')
        if solicitud.slack_channel_id and solicitud.slack_thread_ts and os.getenv('SLACK_BOT_TOKEN'):
            try:
                responder_en_hilo(
                    solicitud.slack_channel_id,
                    solicitud.slack_thread_ts,
                    f'🔄 *Actualización desde el panel ({request.user.username}):*\n{resumen}',
                )
            except Exception:
                pass
    except Exception as exc:
        messages.error(request, f'Error aplicando ajuste IA: {exc}')
    return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)


@login_required
@require_POST
def admin_ia_enviar_slack(request, pk):
    solicitud = get_object_or_404(SolicitudPropuestaIA, pk=pk)
    try:
        notificar_propuesta_lista(solicitud, _base_url(request))
        messages.success(request, 'Notificación enviada al canal de R.E.D. en Slack.')
    except Exception as exc:
        messages.error(request, f'No se pudo enviar a Slack: {exc}')
    return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)


@login_required
@require_POST
def admin_ia_aprobar_archivar(request, pk):
    solicitud = get_object_or_404(SolicitudPropuestaIA, pk=pk)
    base_url = _base_url(request)
    try:
        res = aprobar_y_archivar_en_drive(solicitud, base_url)
        messages.success(request, f"Propuesta publicada y archivada en Drive: {res['folder_name']}")
        if solicitud.slack_channel_id and solicitud.slack_thread_ts and os.getenv('SLACK_BOT_TOKEN'):
            try:
                responder_en_hilo(
                    solicitud.slack_channel_id,
                    solicitud.slack_thread_ts,
                    (
                        f"✅ *Propuesta aprobada y archivada en Google Drive!*\n"
                        f"📁 *Carpeta:* <{res['folder_url']}|{res['folder_name']}>\n"
                        f"🔗 *Link web listo para enviar por WhatsApp al cliente:*\n{res['public_url']}"
                    ),
                )
            except Exception:
                pass
    except Exception as exc:
        messages.error(request, f'No se pudo archivar en Drive: {exc}')
    return redirect('propuestas:admin_ia_detalle', pk=solicitud.pk)


@login_required
def admin_ia_print(request, pk):
    solicitud = get_object_or_404(SolicitudPropuestaIA, pk=pk)
    propuesta = solicitud.propuesta
    return render(
        request,
        'admin_panel/ia_propuesta_print.html',
        {
            'solicitud': solicitud,
            'propuesta': propuesta,
            'paquetes': propuesta.paquetes_casa_diseno if propuesta else [],
            'public_url': f"{_base_url(request)}/p/{propuesta.slug}/" if propuesta else '',
        },
    )


@csrf_exempt
@require_POST
def slack_events_webhook(request):
    """Recibe eventos de Slack (url_verification y respuestas en hilo para editar propuestas)."""
    if not verificar_firma_slack(request):
        return HttpResponse(status=403)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return HttpResponse(status=400)

    if payload.get('type') == 'url_verification':
        return JsonResponse({'challenge': payload.get('challenge', '')})

    if payload.get('type') == 'event_callback':
        event = payload.get('event') or {}
        # Ignorar mensajes de bots para evitar bucles infinitos
        if event.get('bot_id') or event.get('subtype'):
            return JsonResponse({'ok': True})

        thread_ts = event.get('thread_ts')
        text = (event.get('text') or '').strip()
        channel = event.get('channel') or ''

        if thread_ts and text:
            solicitud = SolicitudPropuestaIA.objects.filter(slack_thread_ts=thread_ts).first()
            if solicitud:
                base_url = _base_url(request)

                def _worker():
                    try:
                        responder_en_hilo(channel, thread_ts, '⏳ Procesando tu ajuste en la propuesta...')
                        resumen = aplicar_ajuste_conversacional(solicitud, text, autor='Slack R.E.D.')
                        url_editar = f"{base_url}/admin-panel/editar/{solicitud.propuesta.pk}/"
                        url_ia = f"{base_url}/admin-panel/ia/{solicitud.pk}/"
                        responder_en_hilo(
                            channel,
                            thread_ts,
                            f"✅ *Cambio aplicado:* {resumen}\n🔍 <{url_ia}|Ver Diagnóstico IA> · ✏️ <{url_editar}|Editar Manual>",
                        )
                    except Exception as exc:
                        logger.exception('Error procesando ajuste desde hilo Slack')
                        try:
                            responder_en_hilo(channel, thread_ts, f'❌ Error aplicando ajuste: {exc}')
                        except Exception:
                            pass

                threading.Thread(target=_worker, daemon=True).start()

    return JsonResponse({'ok': True})


@csrf_exempt
@require_POST
def slack_interactions_webhook(request):
    """Maneja el clic en el botón 'Aprobar y Archivar en Drive' desde Slack."""
    if not verificar_firma_slack(request):
        return HttpResponse(status=403)

    raw_payload = request.POST.get('payload', '')
    if not raw_payload:
        return HttpResponse(status=400)

    try:
        payload = json.loads(raw_payload)
    except Exception:
        return HttpResponse(status=400)

    actions = payload.get('actions') or []
    base_url = _base_url(request)

    for action in actions:
        if action.get('action_id') == 'aprobar_propuesta_ia':
            sol_id = action.get('value')
            solicitud = SolicitudPropuestaIA.objects.filter(pk=sol_id).first()
            if solicitud:
                channel = solicitud.slack_channel_id or (payload.get('channel') or {}).get('id', '')
                thread_ts = solicitud.slack_thread_ts or (payload.get('message') or {}).get('ts', '')

                def _approve_worker():
                    try:
                        responder_en_hilo(channel, thread_ts, '⏳ Publicando propuesta, generando PDF y archivando en Google Drive...')
                        res = aprobar_y_archivar_en_drive(solicitud, base_url)
                        responder_en_hilo(
                            channel,
                            thread_ts,
                            (
                                f"✅ *¡Propuesta aprobada y archivada en Google Drive!*\n"
                                f"📁 *Carpeta:* <{res['folder_url']}|{res['folder_name']}>\n"
                                f"📄 *Documento:* <{res['pdf_url']}|Ver archivo en Drive>\n"
                                f"🔗 *Link web listo para copiar y enviar por WhatsApp al cliente:*\n{res['public_url']}"
                            ),
                        )
                    except Exception as exc:
                        logger.exception('Error archivando propuesta desde Slack')
                        try:
                            responder_en_hilo(channel, thread_ts, f'❌ Error al archivar en Drive: {exc}')
                        except Exception:
                            pass

                threading.Thread(target=_approve_worker, daemon=True).start()

    return JsonResponse({'ok': True})
