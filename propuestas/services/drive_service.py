import io
import json
import logging
import mimetypes
import os
import re

from django.template.loader import render_to_string

from propuestas.models import SolicitudPropuestaIA

logger = logging.getLogger(__name__)

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']


def _get_drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON', '').strip()
    json_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_FILE', '').strip()

    if raw_json:
        info = json.loads(raw_json)
        creds = service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
    elif json_path and os.path.exists(json_path):
        creds = service_account.Credentials.from_service_account_file(json_path, scopes=DRIVE_SCOPES)
    else:
        raise RuntimeError(
            'Falta configurar GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_SERVICE_ACCOUNT_FILE para Google Drive.'
        )
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def _siguiente_consecutivo(service, parent_folder_id: str) -> int:
    """Lee las subcarpetas existentes en 03. Propuestas/2026 y calcula el siguiente número NN."""
    query = (
        f"'{parent_folder_id}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    max_num = 0
    page_token = None
    while True:
        res = service.files().list(
            q=query,
            fields='nextPageToken, files(id, name)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageSize=200,
            pageToken=page_token,
        ).execute()
        for f in res.get('files', []):
            m = re.match(r'^(\d{1,3})\.\s+', f.get('name', ''))
            if m:
                n = int(m.group(1))
                # Ignorar carpetas especiales como "1000. Select"
                if n < 900 and n > max_num:
                    max_num = n
        page_token = res.get('nextPageToken')
        if not page_token:
            break
    return max_num + 1


def _crear_carpeta(service, nombre: str, parent_id: str) -> dict:
    meta = {
        'name': nombre,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    return service.files().create(
        body=meta,
        fields='id, webViewLink',
        supportsAllDrives=True,
    ).execute()


def _subir_bytes(service, nombre: str, data: bytes, mime_type: str, parent_id: str) -> dict:
    from googleapiclient.http import MediaIoBaseUpload

    media = MediaIoBaseUpload(io.BytesIO(data), mimetype=mime_type, resumable=True)
    meta = {'name': nombre, 'parents': [parent_id]}
    return service.files().create(
        body=meta,
        media_body=media,
        fields='id, webViewLink',
        supportsAllDrives=True,
    ).execute()


def generar_resumen_pdf_o_html(solicitud: SolicitudPropuestaIA, base_url: str) -> tuple[bytes, str, str]:
    """Renderiza el documento oficial de la propuesta (PDF vía WeasyPrint si está disponible, si no HTML)."""
    propuesta = solicitud.propuesta
    html = render_to_string(
        'admin_panel/ia_propuesta_print.html',
        {
            'propuesta': propuesta,
            'solicitud': solicitud,
            'paquetes': propuesta.paquetes_casa_diseno,
            'public_url': f"{base_url.rstrip('/')}/p/{propuesta.slug}/",
        },
    )
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=base_url).write_pdf()
        return pdf_bytes, 'application/pdf', 'pdf'
    except Exception as exc:
        logger.warning('WeasyPrint no disponible, exportando versión HTML imprimible: %s', exc)
        return html.encode('utf-8'), 'text/html', 'html'


def aprobar_y_archivar_en_drive(solicitud: SolicitudPropuestaIA, base_url: str) -> dict:
    """Publica la propuesta, crea {NN}. Proyecto - Cliente + Insumos/ en Drive y sube el PDF."""
    propuesta = solicitud.propuesta
    if not propuesta:
        raise RuntimeError('La solicitud no tiene una propuesta asociada.')

    # 1. Publicar la propuesta para que el link público funcione de inmediato
    if propuesta.estado != 'publicada':
        propuesta.estado = 'publicada'
        propuesta.save(update_fields=['estado', 'updated_at'])

    parent_id = os.getenv(
        'GOOGLE_DRIVE_PROPUESTAS_FOLDER_ID',
        '1KAQ-YZsBHvVUHcpBgCHM-SVRD9SyiO5x',
    ).strip()

    service = _get_drive_service()
    siguiente = _siguiente_consecutivo(service, parent_id)
    consec_str = f'{siguiente:02d}'

    nombre_proy = re.sub(r'[\\/:*?"<>|]', '', propuesta.nombre_proyecto).strip()
    nombre_cli = re.sub(r'[\\/:*?"<>|]', '', propuesta.empresa_cliente or propuesta.dirigido_a).strip()
    carpeta_nombre = f'{consec_str}. {nombre_proy} - {nombre_cli}' if nombre_cli else f'{consec_str}. {nombre_proy}'

    carpeta = _crear_carpeta(service, carpeta_nombre, parent_id)
    carpeta_id = carpeta['id']
    carpeta_url = carpeta.get('webViewLink', f'https://drive.google.com/drive/folders/{carpeta_id}')

    # Subcarpeta Insumos
    insumos_folder = _crear_carpeta(service, 'Insumos', carpeta_id)
    for insumo in solicitud.insumos.all():
        try:
            ruta = insumo.archivo.path
            if os.path.exists(ruta):
                mime = insumo.mime_type or mimetypes.guess_type(ruta)[0] or 'application/octet-stream'
                with open(ruta, 'rb') as f:
                    _subir_bytes(service, insumo.nombre_original or os.path.basename(ruta), f.read(), mime, insumos_folder['id'])
        except Exception as exc:
            logger.warning('No se pudo subir insumo %s a Drive: %s', insumo.nombre_original, exc)

    # Generar y subir PDF/HTML de la propuesta
    doc_bytes, doc_mime, ext = generar_resumen_pdf_o_html(solicitud, base_url)
    doc_name = f'Propuesta_{consec_str}_{nombre_proy}.{ext}'
    doc_file = _subir_bytes(service, doc_name, doc_bytes, doc_mime, carpeta_id)
    doc_url = doc_file.get('webViewLink', '')

    solicitud.drive_folder_id = carpeta_id
    solicitud.drive_folder_url = carpeta_url
    solicitud.drive_pdf_url = doc_url
    solicitud.estado_ia = 'aprobada_archivada'
    solicitud.save(update_fields=['drive_folder_id', 'drive_folder_url', 'drive_pdf_url', 'estado_ia', 'updated_at'])

    return {
        'folder_name': carpeta_nombre,
        'folder_url': carpeta_url,
        'pdf_url': doc_url,
        'public_url': f"{base_url.rstrip('/')}/p/{propuesta.slug}/",
    }
