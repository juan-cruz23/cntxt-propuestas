import json
import logging
import mimetypes
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from propuestas.models import (
    Entregable,
    FormaPago,
    ObjetivoAlineado,
    Paquete,
    Propuesta,
    Requisito,
    ServicioCatalogo,
    SolicitudPropuestaIA,
)

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(settings.BASE_DIR) / 'propuestas' / 'ai_assets'


def _cargar_contexto_playbook() -> str:
    ruta = ASSETS_DIR / 'playbook_red_context.md'
    if ruta.exists():
        return ruta.read_text(encoding='utf-8')
    return ''


def _obtener_catalogo_compacto() -> list[dict]:
    qs = ServicioCatalogo.objects.filter(activo=True)
    if qs.exists():
        return [
            {
                'codigo': s.codigo,
                'categoria': s.categoria,
                'subcategoria': s.subcategoria,
                'nombre': s.nombre,
                'modelo': s.modelo_negocio,
                'fase': s.fase,
                'entregables': s.entregables,
                'horas': float(s.horas_totales),
                'dias': float(s.dias_estimados),
                'valor_cop': int(s.valor_total_cop),
                'manual': s.requiere_cotizacion_manual,
            }
            for s in qs
        ]
    ruta = ASSETS_DIR / 'catalogo_maestro_cntxt_2026.json'
    if ruta.exists():
        data = json.loads(ruta.read_text(encoding='utf-8'))
        return [
            {
                'codigo': s['codigo'],
                'categoria': s['categoria'],
                'subcategoria': s.get('subcategoria') or '',
                'nombre': s['nombre'],
                'modelo': s.get('modelo_negocio') or 'MADE',
                'fase': s.get('fase') or '',
                'entregables': s.get('entregables') or [],
                'horas': float(s.get('horas_totales') or 0),
                'dias': float(s.get('dias_estimados') or 0),
                'valor_cop': int(s.get('valor_total_cop') or 0),
                'manual': bool(s.get('requiere_cotizacion_manual', False)),
            }
            for s in data.get('servicios', [])
        ]
    return []


def _get_gemini_client():
    api_key = os.getenv('GEMINI_API_KEY', '').strip()
    if not api_key:
        raise RuntimeError(
            'Falta configurar la variable de entorno GEMINI_API_KEY para ejecutar el motor multimodal.'
        )
    from google import genai
    return genai.Client(api_key=api_key)


def _limpiar_json_texto(texto: str) -> dict:
    cleaned = texto.strip()
    if cleaned.startswith('```'):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith('```'):
            lines = lines[1:]
        if lines and lines[-1].strip() == '```':
            lines = lines[:-1]
        cleaned = '\n'.join(lines).strip()
    return json.loads(cleaned)


def _formatear_incluye_html(bloques: list[dict], dias_calendario: int) -> str:
    """Genera HTML limpio compatible con la vista pública de propuestas CNTXT."""
    partes = ['<h2>¿Qué incluye?</h2>']
    for b in bloques or []:
        num = b.get('numero', '')
        tit = b.get('titulo', '')
        heading = f'{num} · {tit}'.strip(' ·')
        partes.append(f'<h3>{heading}</h3>')
        items = b.get('items') or []
        if items:
            lis = ''.join(f'<li>{it}</li>' for it in items)
            partes.append(f'<ul>{lis}</ul>')
    if dias_calendario:
        partes.append(f'<h3>Tiempo de desarrollo</h3><p>{dias_calendario} días calendario estimados.</p>')
    return '\n'.join(partes)


def _build_system_prompt(catalogo: list[dict], playbook: str) -> str:
    return f"""Eres el Director Estratégico Comercial y Arquitectónico de CNTXT (Contexto Arquitectura).
Tu misión es analizar insumos multimodales reales de una reunión/visita comercial (audios, fotos, videos y notas/transcript) y generar:
1. La auditoría completa del Project Brief con los 14 campos exactos de `cntxt-briefs` (marcando explícitamente cualquier campo crítico que falte en los insumos, sin inventar datos duros).
2. Un diagnóstico comercial profundo alineado al Playbook R.E.D.
3. Una propuesta comercial estructurada para `cntxt-propuestas` con **SIEMPRE 3 NIVELES DE ACCESO ORDENADOS DE MÁS A MENOS** (Nivel 1 = Integral/Full mayor alcance e inversión, Nivel 2 = Estratégico/Intermedio, Nivel 3 = Esencial/Entrada), correlacionados con servicios REALES del catálogo CNTXT.

--- CONTEXTO PLAYBOOK R.E.D. ---
{playbook}

--- CATÁLOGO MAESTRO DE SERVICIOS CNTXT (JSON) ---
{json.dumps(catalogo, ensure_ascii=False)}

--- REGLAS ESTRICTAS DE SALIDA ---
Responde ÚNICAMENTE con un JSON válido (sin texto adicional fuera del JSON) con esta estructura exacta:
{{
  "brief": {{
    "title": "string (nombre del proyecto)",
    "subtitle": "string (ubicacion exacta o ciudad/sector)",
    "project_category": "string (ej: Vivienda Campestre, Parcelaciones y Condominios, Edificación en Altura, Diseño Interior, Comercial, Hotelería)",
    "estimated_area": null o numero decimal (m2 estimados, NO inventar si no se menciona),
    "operative_line": "DISENO" o "VISUALIZACION" o "",
    "scope_phase": "FASE_1" o "FASE_2" o "FASE_3" o "",
    "status": "PRECONTRACTUAL",
    "description": "string (1. Descripción general del proyecto)",
    "architectural_program": "string (2. Programa arquitectónico detallado)",
    "design_premises": "string (3. Premisas de diseño: técnicas, normativas, bioclimáticas, presupuesto)",
    "conceptual_approach": "string (4. Enfoque conceptual, atmósfera, materialidad, estilo)",
    "essential_deliverables": "string (5. Entregables indispensables solicitados o deducidos)",
    "temporal_conditioning": "string (6. Condicionamiento temporal, fechas o urgencia)",
    "resumen_visual_insumos": "string (síntesis de lo observado en las fotos y videos)",
    "completitud_pct": entero 0..100,
    "campos_faltantes": [
      {{"campo": "string", "criticidad": "alta|media|baja", "pregunta_para_red": "string"}}
    ]
  }},
  "diagnostico": {{
    "tipo_proyecto": "string",
    "modelo_negocio": "MADE" o "SELECT",
    "segmento": "B2B" o "B2C",
    "perfil_cliente": "string (ICP Corporativo o Avatar Victoria/Ana Lucía/Mateo/Luis)",
    "dolores": ["string", "..."],
    "deseos": ["string", "..."],
    "retos_principales": ["string", "..."],
    "conceptos_maestros": ["Well Being|Context|Disruption|Smartness|Customization|Storytelling"]
  }},
  "propuesta": {{
    "nombre_proyecto": "string",
    "nombre_proyecto_subtitulo": "string (ubicación / contexto)",
    "dirigido_a": "string",
    "empresa_cliente": "string",
    "objetivo_texto": "string (HTML con párrafos <p> y <strong> explicando ¿Por qué esta propuesta? en tono CNTXT)",
    "objetivos_alineados": [
      {{"titulo": "string", "descripcion": "string", "icono": "star|target|sparkles|compass|layers"}}
    ],
    "niveles_acceso": [
      {{
        "orden": 1,
        "nombre": "string (Nivel 1 - el más completo, de MÁS a MENOS)",
        "nombre_en": "string",
        "es_destacado": false,
        "que_es": "string (HTML <p>)",
        "para_que": "string (HTML <p>)",
        "bloques_que_incluye": [
          {{"numero": "01", "titulo": "string", "items": ["string", "..."]}}
        ],
        "servicios_catalogo": [
          {{"codigo": "string", "nombre": "string", "cantidad": 1, "valor_unitario_cop": 0, "subtotal_cop": 0, "requiere_cotizacion_manual": false}}
        ],
        "dias_entrega": 45,
        "precio_regular": 0,
        "moneda": "COP",
        "aplica_iva": true
      }}
    ],
    "requisitos_previos": ["string", "..."],
    "consideraciones_texto": "string (HTML <ul><li>...</li></ul> con exclusiones y alcances)",
    "formas_pago": [
      {{"concepto": "Anticipo de inicio de proyecto", "porcentaje": 50, "fecha_pago": "A la firma del contrato"}},
      {{"concepto": "Abono 1", "porcentaje": 20, "fecha_pago": "Entrega 1"}},
      {{"concepto": "Abono 2", "porcentaje": 20, "fecha_pago": "Entrega 2"}},
      {{"concepto": "Abono final", "porcentaje": 10, "fecha_pago": "Entrega Final"}}
    ]
  }},
  "notas_ajuste_manual": [
    "string (alertas claras sobre valores en $0 o factores de escala m2/unidades a validar por R.E.D.)"
  ]
}}

VERIFICA ANTES DE RESPONDER:
- `propuesta.niveles_acceso` DEBE tener EXACTAMENTE 3 elementos ordenados de MAYOR alcance/precio (orden 1) a MENOR alcance/precio (orden 3).
- `propuesta.objetivos_alineados` DEBE tener EXACTAMENTE 3 elementos.
- `propuesta.formas_pago` DEBE sumar 100%.
- Los precios de cada nivel deben sumar los `subtotal_cop` de sus `servicios_catalogo` reales del catálogo (si algún servicio está en $0 / manual, menciónalo en `notas_ajuste_manual`).
"""


def _adjuntar_insumos_gemini(client, solicitud: SolicitudPropuestaIA) -> list:
    partes = []
    uploaded_refs = []
    for insumo in solicitud.insumos.all():
        try:
            ruta = insumo.archivo.path
        except Exception:
            continue
        if not os.path.exists(ruta):
            continue
        mime = insumo.mime_type or mimetypes.guess_type(ruta)[0] or 'application/octet-stream'
        try:
            # Usar Files API de Gemini para soportar audio, video e imágenes grandes limpiamente
            f_ref = client.files.upload(file=ruta, config={'mime_type': mime})
            uploaded_refs.append(f_ref)
            partes.append(f_ref)
        except Exception as exc:
            logger.warning('No se pudo subir insumo %s a Gemini: %s', insumo.nombre_original, exc)
    return partes, uploaded_refs


def generar_propuesta_ia(solicitud: SolicitudPropuestaIA) -> Propuesta:
    """Ejecuta el Skill Multimodal de CNTXT y crea/actualiza la Propuesta real en BD."""
    solicitud.estado_ia = 'procesando'
    solicitud.error_mensaje = ''
    solicitud.save(update_fields=['estado_ia', 'error_mensaje', 'updated_at'])

    client = _get_gemini_client()
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    catalogo = _obtener_catalogo_compacto()
    playbook = _cargar_contexto_playbook()

    system_prompt = _build_system_prompt(catalogo, playbook)

    user_context = (
        f"DATOS INICIALES CAPTURADOS POR R.E.D.:\n"
        f"- Cliente: {solicitud.cliente_nombre}\n"
        f"- Empresa: {solicitud.empresa_cliente or 'No especificada'}\n"
        f"- Proyecto (referencia): {solicitud.nombre_proyecto_referencia or 'Por definir según insumos'}\n"
        f"- Ubicación: {solicitud.ubicacion or 'Por extraer de insumos'}\n"
        f"- Transcript / Notas adicionales:\n{solicitud.transcript_o_notas or '(Sin notas escritas; analizar audios, fotos y videos adjuntos)'}\n\n"
        f"Analiza todos los archivos multimedia adjuntos y genera el JSON completo."
    )

    media_parts, uploaded_refs = _adjuntar_insumos_gemini(client, solicitud)
    contents = [*media_parts, user_context]

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
            config={
                'system_instruction': system_prompt,
                'response_mime_type': 'application/json',
                'temperature': 0.35,
            },
        )
        data = _limpiar_json_texto(response.text)
    except Exception as exc:
        solicitud.estado_ia = 'error'
        solicitud.error_mensaje = str(exc)
        solicitud.save(update_fields=['estado_ia', 'error_mensaje', 'updated_at'])
        raise
    finally:
        for ref in uploaded_refs:
            try:
                client.files.delete(name=ref.name)
            except Exception:
                pass

    propuesta = sincronizar_propuesta_desde_json(solicitud, data)
    return propuesta


@transaction.atomic
def sincronizar_propuesta_desde_json(
    solicitud: SolicitudPropuestaIA,
    data: dict,
    nota_cambio: str | None = None,
) -> Propuesta:
    """Crea o actualiza la Propuesta y sus modelos hijos desde el JSON del Skill."""
    p_data = data.get('propuesta') or {}
    brief_data = data.get('brief') or {}
    diag_data = data.get('diagnostico') or {}
    notas_manuales = data.get('notas_ajuste_manual') or []

    propuesta = solicitud.propuesta
    if propuesta is None:
        propuesta = Propuesta(
            fecha_presentacion=date.today(),
            estado='borrador',
            de='CNTXT',
            incluye_casa_diseno=True,
            incluye_partners=False,
        )

    propuesta.nombre_proyecto = (
        p_data.get('nombre_proyecto')
        or solicitud.nombre_proyecto_referencia
        or brief_data.get('title')
        or f'Proyecto {solicitud.cliente_nombre}'
    )[:300]
    propuesta.nombre_proyecto_subtitulo = (
        p_data.get('nombre_proyecto_subtitulo') or solicitud.ubicacion or brief_data.get('subtitle') or ''
    )[:300]
    propuesta.dirigido_a = (p_data.get('dirigido_a') or solicitud.cliente_nombre)[:300]
    propuesta.empresa_cliente = (p_data.get('empresa_cliente') or solicitud.empresa_cliente or '')[:300]
    propuesta.objetivo_texto = p_data.get('objetivo_texto') or ''
    propuesta.consideraciones_texto = p_data.get('consideraciones_texto') or ''

    reqs_list = p_data.get('requisitos_previos') or []
    if reqs_list:
        propuesta.requisitos_texto = '<ul>' + ''.join(f'<li>{r}</li>' for r in reqs_list) + '</ul>'
    propuesta.save()

    # Objetivos alineados
    propuesta.objetivos.all().delete()
    for idx, obj in enumerate(p_data.get('objetivos_alineados') or []):
        ObjetivoAlineado.objects.create(
            propuesta=propuesta,
            titulo=(obj.get('titulo') or '')[:200],
            descripcion=obj.get('descripcion') or '',
            icono=(obj.get('icono') or 'star')[:50],
            orden=idx,
        )

    # 3 Niveles de acceso (ordenados de más a menos)
    propuesta.paquetes.filter(tipo='casa_diseno').delete()
    niveles = sorted(p_data.get('niveles_acceso') or [], key=lambda x: x.get('orden', 99))
    for idx, niv in enumerate(niveles):
        bloques = niv.get('bloques_que_incluye') or []
        dias = int(niv.get('dias_entrega') or 15)
        incluye_html = niv.get('incluye_texto') or _formatear_incluye_html(bloques, dias)
        precio = Decimal(str(niv.get('precio_regular') or 0))
        paquete = Paquete.objects.create(
            propuesta=propuesta,
            tipo='casa_diseno',
            nombre=(niv.get('nombre') or f'Nivel {idx + 1}')[:200],
            nombre_en=(niv.get('nombre_en') or '')[:200],
            que_es=niv.get('que_es') or '',
            para_que=niv.get('para_que') or '',
            incluye_texto=incluye_html,
            dias_entrega=dias,
            precio_regular=precio,
            moneda=(niv.get('moneda') or 'COP')[:10],
            aplica_iva=bool(niv.get('aplica_iva', True)),
            es_destacado=bool(niv.get('es_destacado', idx == 1)),
            orden=idx,
        )
        for b_idx, b in enumerate(bloques):
            cat_label = f"{b.get('numero', '')} · {b.get('titulo', '')}".strip(' ·')[:200]
            desc = '\n'.join(f'• {it}' for it in (b.get('items') or []))
            if cat_label:
                Entregable.objects.create(
                    paquete=paquete,
                    categoria=cat_label,
                    descripcion=desc,
                    orden=b_idx,
                )

    # Requisitos individuales
    propuesta.requisitos.all().delete()
    for idx, req in enumerate(reqs_list):
        Requisito.objects.create(propuesta=propuesta, texto=str(req)[:500], orden=idx)

    # Formas de pago
    propuesta.formas_pago.all().delete()
    for idx, fp in enumerate(p_data.get('formas_pago') or []):
        FormaPago.objects.create(
            propuesta=propuesta,
            concepto=(fp.get('concepto') or '')[:300],
            porcentaje=int(fp.get('porcentaje') or 0),
            fecha_pago=(fp.get('fecha_pago') or '')[:300],
            orden=idx,
        )

    # Actualizar solicitud IA
    solicitud.propuesta = propuesta
    solicitud.brief_json = brief_data
    solicitud.diagnostico_json = diag_data
    solicitud.notas_ajuste_manual_json = notas_manuales
    solicitud.raw_response_json = data
    if solicitud.estado_ia in ('pendiente', 'procesando', 'error'):
        solicitud.estado_ia = 'borrador_generado'
    if nota_cambio:
        hist = list(solicitud.historial_cambios_json or [])
        hist.append({
            'fecha': timezone.now().isoformat(),
            'resumen': nota_cambio,
        })
        solicitud.historial_cambios_json = hist
    solicitud.save()

    # Sincronizar opcionalmente a tabla compartida briefs_projectbrief si existe en Postgres
    _sincronizar_brief_compartido(solicitud, brief_data)

    return propuesta


def _sincronizar_brief_compartido(solicitud: SolicitudPropuestaIA, brief_data: dict):
    """Si la BD compartida Postgres tiene la tabla `briefs_projectbrief` de cntxt-briefs, crea/actualiza el Brief."""
    if not brief_data:
        return
    try:
        tables = connection.introspection.table_names()
        if 'briefs_projectbrief' not in tables:
            return
        now = timezone.now()
        title = (brief_data.get('title') or solicitud.nombre_proyecto_referencia or solicitud.cliente_nombre)[:300]
        subtitle = (brief_data.get('subtitle') or solicitud.ubicacion or '')[:300]
        category = (brief_data.get('project_category') or '')[:200]
        est_area = brief_data.get('estimated_area')
        op_line = brief_data.get('operative_line') if brief_data.get('operative_line') in ('VISUALIZACION', 'DISENO') else ''
        scope_phase = brief_data.get('scope_phase') if brief_data.get('scope_phase') in ('FASE_1', 'FASE_2', 'FASE_3') else ''
        ref_url = (solicitud.drive_folder_url or '')[:500]

        with connection.cursor() as cursor:
            if solicitud.brief_externo_id:
                cursor.execute(
                    """
                    UPDATE briefs_projectbrief
                    SET title=%s, subtitle=%s, project_category=%s, estimated_area=%s,
                        operative_line=%s, scope_phase=%s, description=%s,
                        architectural_program=%s, design_premises=%s, conceptual_approach=%s,
                        essential_deliverables=%s, temporal_conditioning=%s,
                        reference_images_url=%s, updated_at=%s
                    WHERE id=%s
                    """,
                    [
                        title, subtitle, category, est_area, op_line, scope_phase,
                        brief_data.get('description') or '',
                        brief_data.get('architectural_program') or '',
                        brief_data.get('design_premises') or '',
                        brief_data.get('conceptual_approach') or '',
                        brief_data.get('essential_deliverables') or '',
                        brief_data.get('temporal_conditioning') or '',
                        ref_url, now, solicitud.brief_externo_id,
                    ],
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO briefs_projectbrief (
                        title, subtitle, project_category, estimated_area, operative_line,
                        scope_phase, description, architectural_program, design_premises,
                        conceptual_approach, essential_deliverables, temporal_conditioning,
                        reference_images_url, status, created_by_id, created_at, updated_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'PRECONTRACTUAL',NULL,%s,%s)
                    RETURNING id
                    """,
                    [
                        title, subtitle, category, est_area, op_line, scope_phase,
                        brief_data.get('description') or '',
                        brief_data.get('architectural_program') or '',
                        brief_data.get('design_premises') or '',
                        brief_data.get('conceptual_approach') or '',
                        brief_data.get('essential_deliverables') or '',
                        brief_data.get('temporal_conditioning') or '',
                        ref_url, now, now,
                    ],
                )
                row = cursor.fetchone()
                if row:
                    solicitud.brief_externo_id = row[0]
                    solicitud.save(update_fields=['brief_externo_id'])
    except Exception as exc:
        logger.warning('No se pudo sincronizar con briefs_projectbrief (opcional): %s', exc)


def aplicar_ajuste_conversacional(solicitud: SolicitudPropuestaIA, instruccion: str, autor: str = 'R.E.D.') -> str:
    """Aplica cambios pedidos desde Slack (en hilo) o desde el panel sobre la propuesta actual."""
    client = _get_gemini_client()
    model_name = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    catalogo = _obtener_catalogo_compacto()
    playbook = _cargar_contexto_playbook()

    estado_actual = solicitud.raw_response_json or {}

    prompt_edicion = f"""Eres el motor de propuestas IA de CNTXT.
A continuación tienes el JSON ACTUAL de una propuesta y su Brief, junto con una instrucción de cambio solicitada por {autor}.
Aplica ÚNICAMENTE los cambios pedidos respetando el catálogo real de servicios y manteniendo SIEMPRE los 3 niveles de acceso ordenados de MÁS a MENOS.
Si el usuario completó datos faltantes del Brief, actualiza `brief` y retira esos campos de `brief.campos_faltantes` recalculando `completitud_pct`.

Devuelve un JSON con exactamente dos claves:
{{
  "resumen_cambios": "string corto en español explicando qué se actualizó",
  "data_actualizada": {{ ... el mismo esquema completo de brief, diagnostico, propuesta y notas_ajuste_manual ... }}
}}

--- JSON ACTUAL ---
{json.dumps(estado_actual, ensure_ascii=False)}

--- INSTRUCCIÓN DE CAMBIO DE {autor} ---
{instruccion}
"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt_edicion,
        config={
            'system_instruction': _build_system_prompt(catalogo, playbook),
            'response_mime_type': 'application/json',
            'temperature': 0.25,
        },
    )
    parsed = _limpiar_json_texto(response.text)
    resumen = parsed.get('resumen_cambios') or 'Propuesta actualizada según tu instrucción.'
    nueva_data = parsed.get('data_actualizada') or parsed

    sincronizar_propuesta_desde_json(solicitud, nueva_data, nota_cambio=f'{autor}: {resumen}')
    return resumen
