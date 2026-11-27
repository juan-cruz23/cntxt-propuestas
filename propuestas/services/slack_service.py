import hashlib
import hmac
import logging
import os
import time

import requests

from propuestas.models import SolicitudPropuestaIA

logger = logging.getLogger(__name__)


def verificar_firma_slack(request) -> bool:
    """Valida X-Slack-Signature usando SLACK_SIGNING_SECRET."""
    signing_secret = os.getenv('SLACK_SIGNING_SECRET', '').strip()
    if not signing_secret:
        return True  # Permite pruebas locales si aún no está configurado

    timestamp = request.META.get('HTTP_X_SLACK_REQUEST_TIMESTAMP', '')
    signature = request.META.get('HTTP_X_SLACK_SIGNATURE', '')
    if not timestamp or not signature:
        return False

    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            return False
    except ValueError:
        return False

    basestring = f"v0:{timestamp}:{request.body.decode('utf-8')}"
    my_sig = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        basestring.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(my_sig, signature)


def _slack_post(endpoint: str, payload: dict) -> dict:
    token = os.getenv('SLACK_BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Falta configurar SLACK_BOT_TOKEN en variables de entorno.')
    resp = requests.post(
        f'https://slack.com/api/{endpoint}',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json; charset=utf-8',
        },
        json=payload,
        timeout=15,
    )
    data = resp.json()
    if not data.get('ok'):
        logger.error('Error Slack API (%s): %s', endpoint, data)
        raise RuntimeError(f"Slack API error: {data.get('error')}")
    return data


def _formato_cop(valor) -> str:
    try:
        return f"${int(float(valor)):,} COP".replace(',', '.')
    except Exception:
        return '$0 COP'


def notificar_propuesta_lista(solicitud: SolicitudPropuestaIA, base_url: str) -> dict:
    """Envía la tarjeta principal al canal R.E.D. en Slack y guarda thread_ts."""
    channel = solicitud.slack_channel_id or os.getenv('SLACK_RED_CHANNEL_ID', '').strip()
    if not channel:
        raise RuntimeError('Falta configurar SLACK_RED_CHANNEL_ID en variables de entorno.')

    propuesta = solicitud.propuesta
    diag = solicitud.diagnostico_json or {}
    brief = solicitud.brief_json or {}
    faltantes = brief.get('campos_faltantes') or []
    completitud = brief.get('completitud_pct', 0)

    url_editar = f"{base_url.rstrip('/')}/admin-panel/editar/{propuesta.pk}/"
    url_ia = f"{base_url.rstrip('/')}/admin-panel/ia/{solicitud.pk}/"
    url_excel = f"{base_url.rstrip('/')}/admin-panel/ia/{solicitud.pk}/excel/"
    url_publica = f"{base_url.rstrip('/')}/p/{propuesta.slug}/"

    niveles_lines = []
    for idx, pkg in enumerate(propuesta.paquetes_casa_diseno, 1):
        niveles_lines.append(
            f"*{idx}. {pkg.nombre}* — {_formato_cop(pkg.precio_regular)} + IVA · {pkg.dias_entrega} días"
        )
    niveles_txt = '\n'.join(niveles_lines) or '_Sin niveles generados_'

    dolores_txt = '\n'.join(f'• {d}' for d in (diag.get('dolores') or [])[:3]) or '—'
    faltantes_txt = (
        '\n'.join(f"⚠️ *{f.get('campo')}*: {f.get('pregunta_para_red')}" for f in faltantes[:5])
        if faltantes
        else '✅ Brief completo sin vacíos críticos.'
    )

    blocks = [
        {
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': f'Properto · Propuesta #{propuesta.numero}: {propuesta.nombre_proyecto}'[:150],
            },
        },
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': '👔 *Hola equipo R.E.D., soy Properto.* Ya analicé los insumos del proyecto y dejé estructurado el borrador comercial listo para su revisión.',
                }
            ],
        },
        {
            'type': 'section',
            'fields': [
                {'type': 'mrkdwn', 'text': f"*Cliente:*\n{propuesta.dirigido_a}"},
                {'type': 'mrkdwn', 'text': f"*Tipo / Modelo:*\n{diag.get('tipo_proyecto', '—')} ({diag.get('modelo_negocio', 'MADE')})"},
                {'type': 'mrkdwn', 'text': f"*Perfil:*\n{diag.get('segmento', '')} · {diag.get('perfil_cliente', '—')}"},
                {'type': 'mrkdwn', 'text': f"*Brief Completitud:*\n{completitud}%"},
            ],
        },
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f"*Dolores clave detectados:*\n{dolores_txt}"},
        },
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f"*3 Niveles de Acceso (de más a menos):*\n{niveles_txt}"},
        },
        {
            'type': 'section',
            'text': {'type': 'mrkdwn', 'text': f"*Auditoría de Brief (CNTXT Briefs):*\n{faltantes_txt}"},
        },
        {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': '💬 *Respóndeme en este hilo* si deseas ajustar alcances, servicios, tiempos, precios o completar los datos faltantes del Brief. Yo me encargo de actualizar la propuesta al instante. — *Properto*',
                }
            ],
        },
        {
            'type': 'actions',
            'elements': [
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': '🔍 Revisar con Properto'},
                    'url': url_ia,
                },
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': '📊 Excel Accesos'},
                    'url': url_excel,
                },
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': '✏️ Editar Manual'},
                    'url': url_editar,
                },
                {
                    'type': 'button',
                    'style': 'primary',
                    'text': {'type': 'plain_text', 'text': '✅ Aprobar y Archivar en Drive'},
                    'action_id': 'aprobar_propuesta_ia',
                    'value': str(solicitud.pk),
                },
            ],
        },
    ]

    res = _slack_post(
        'chat.postMessage',
        {
            'channel': channel,
            'text': f'Hola equipo R.E.D., soy Properto. Dejé lista la propuesta #{propuesta.numero} ({propuesta.nombre_proyecto}): {url_publica}',
            'blocks': blocks,
        },
    )
    solicitud.slack_channel_id = res.get('channel') or channel
    solicitud.slack_thread_ts = res.get('ts') or ''
    solicitud.estado_ia = 'en_revision_slack'
    solicitud.save(update_fields=['slack_channel_id', 'slack_thread_ts', 'estado_ia', 'updated_at'])
    return res


def responder_en_hilo(channel: str, thread_ts: str, texto: str) -> dict:
    return _slack_post(
        'chat.postMessage',
        {
            'channel': channel,
            'thread_ts': thread_ts,
            'text': texto,
        },
    )
