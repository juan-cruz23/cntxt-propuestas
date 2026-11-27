import io
import re
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from propuestas.models import ServicioCatalogo, SolicitudPropuestaIA


def _safe_sheet_name(title: str, fallback: str) -> str:
    cleaned = re.sub(r'[\[\]\*\?:/\\]', '', title or '').strip()
    return (cleaned or fallback)[:31]


def _lookup_catalogo(codigo: str) -> dict:
    s = ServicioCatalogo.objects.filter(codigo=codigo, activo=True).first()
    if not s:
        return {}
    return {
        'categoria': s.categoria,
        'fase': s.fase,
        'modelo': s.modelo_negocio,
        'horas': float(s.horas_totales),
        'dias': float(s.dias_estimados),
        'valor_cop': int(s.valor_total_cop),
        'entregables': '; '.join(s.entregables or []),
    }


def generar_excel_composicion(solicitud: SolicitudPropuestaIA) -> tuple[bytes, str]:
    """Genera un Excel profesional (.xlsx) con el desglose de servicios por cada Nivel de Acceso."""
    wb = Workbook()

    # Estilos CNTXT (Dark + Gold)
    fill_dark = PatternFill('solid', fgColor='141414')
    fill_gold = PatternFill('solid', fgColor='C8A96E')
    fill_sub = PatternFill('solid', fgColor='F5F0E6')
    fill_total = PatternFill('solid', fgColor='EFE6D5')
    fill_warn = PatternFill('solid', fgColor='FFF3CD')

    font_title = Font(name='Calibri', size=14, bold=True, color='FFFFFF')
    font_header = Font(name='Calibri', size=10, bold=True, color='141414')
    font_bold = Font(name='Calibri', size=10, bold=True, color='141414')
    font_reg = Font(name='Calibri', size=10, color='222222')
    font_muted = Font(name='Calibri', size=9, italic=True, color='555555')

    thin = Side(border_style='thin', color='D6D6D6')
    border_cell = Border(left=thin, right=thin, top=thin, bottom=thin)
    money_fmt = '$#,##0'

    propuesta = solicitud.propuesta
    raw = solicitud.raw_response_json or {}
    p_data = raw.get('propuesta') or {}
    diag = solicitud.diagnostico_json or {}
    brief = solicitud.brief_json or {}
    niveles = sorted(p_data.get('niveles_acceso') or [], key=lambda x: x.get('orden', 99))

    proy_nombre = propuesta.nombre_proyecto if propuesta else (solicitud.nombre_proyecto_referencia or solicitud.cliente_nombre)
    cliente_nombre = propuesta.dirigido_a if propuesta else solicitud.cliente_nombre

    # --- HOJA 1: RESUMEN DE ACCESOS ---
    ws_res = wb.active
    ws_res.title = 'Resumen Accesos'

    ws_res.merge_cells('A1:H1')
    ws_res['A1'] = f'CNTXT · COMPOSICIÓN DE ACCESOS — {proy_nombre.upper()}'
    ws_res['A1'].fill = fill_dark
    ws_res['A1'].font = font_title
    ws_res['A1'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
    ws_res.row_dimensions[1].height = 30

    ws_res['A2'] = f'Cliente: {cliente_nombre} | Empresa: {solicitud.empresa_cliente or "—"} | Generado por Properto'
    ws_res['A2'].font = font_muted

    headers_res = [
        'Orden',
        'Nivel de Acceso',
        'Servicios (#)',
        'Horas Totales',
        'Días Entrega',
        'Valor Base sin IVA (COP)',
        'IVA 19% (COP)',
        'Total con IVA (COP)',
    ]
    for col_idx, h in enumerate(headers_res, 1):
        cell = ws_res.cell(row=4, column=col_idx, value=h)
        cell.fill = fill_gold
        cell.font = font_header
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border_cell
    ws_res.row_dimensions[4].height = 24

    # Crear una pestaña por cada Nivel de Acceso y referenciarla con fórmulas reales en Resumen
    for idx, niv in enumerate(niveles, 1):
        sheet_title = _safe_sheet_name(f'Nivel {idx} - {niv.get("nombre", "")}', f'Nivel {idx}')
        ws_n = wb.create_sheet(title=sheet_title)

        ws_n.merge_cells('A1:K1')
        ws_n['A1'] = f'NIVEL {idx}: {niv.get("nombre", "")} — {proy_nombre}'
        ws_n['A1'].fill = fill_dark
        ws_n['A1'].font = font_title
        ws_n['A1'].alignment = Alignment(horizontal='left', vertical='center', indent=1)
        ws_n.row_dimensions[1].height = 28

        ws_n['A2'] = f'Días calendario estimados: {niv.get("dias_entrega", 0)} | Modifica Cantidad o Valor Unitario para recalcular automáticamente.'
        ws_n['A2'].font = font_muted

        headers_n = [
            'Código',
            'Categoría',
            'Servicio CNTXT',
            'Fase',
            'Modelo',
            'Horas Unit.',
            'Cantidad',
            'Horas Totales',
            'Valor Unitario (COP)',
            'Subtotal (COP)',
            'Nota / Entregables',
        ]
        for c_i, h in enumerate(headers_n, 1):
            c = ws_n.cell(row=4, column=c_i, value=h)
            c.fill = fill_gold
            c.font = font_header
            c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            c.border = border_cell
        ws_n.row_dimensions[4].height = 24

        servicios = niv.get('servicios_catalogo') or []
        start_row = 5
        row_cursor = start_row

        for srv in servicios:
            cod = srv.get('codigo', '')
            cat_info = _lookup_catalogo(cod)
            horas_u = cat_info.get('horas', 0.0)
            cant = float(srv.get('cantidad') or 1)
            val_u = int(srv.get('valor_unitario_cop') or cat_info.get('valor_cop') or 0)
            es_manual = bool(srv.get('requiere_cotizacion_manual') or val_u == 0)
            nota = '⚠️ COTIZACIÓN MANUAL ($0)' if es_manual else cat_info.get('entregables', '')

            valores = [
                cod,
                cat_info.get('categoria', ''),
                srv.get('nombre', ''),
                cat_info.get('fase', ''),
                cat_info.get('modelo', ''),
                horas_u,
                cant,
                f'=F{row_cursor}*G{row_cursor}',
                val_u,
                f'=G{row_cursor}*I{row_cursor}',
                nota,
            ]
            for c_i, val in enumerate(valores, 1):
                c = ws_n.cell(row=row_cursor, column=c_i, value=val)
                c.font = font_reg
                c.border = border_cell
                if es_manual:
                    c.fill = fill_warn
                if c_i in (9, 10):
                    c.number_format = money_fmt
                if c_i in (6, 7, 8):
                    c.number_format = '0.0'
            row_cursor += 1

        if row_cursor == start_row:
            # Si el nivel no trajo servicios_catalogo, dejar fila base con precio del nivel
            ws_n.cell(row=row_cursor, column=1, value='MANUAL').border = border_cell
            ws_n.cell(row=row_cursor, column=3, value=niv.get('nombre', f'Nivel {idx}')).border = border_cell
            ws_n.cell(row=row_cursor, column=7, value=1).border = border_cell
            ws_n.cell(row=row_cursor, column=8, value=0).border = border_cell
            c_u = ws_n.cell(row=row_cursor, column=9, value=int(niv.get('precio_regular') or 0))
            c_u.number_format = money_fmt
            c_u.border = border_cell
            c_s = ws_n.cell(row=row_cursor, column=10, value=f'=G{row_cursor}*I{row_cursor}')
            c_s.number_format = money_fmt
            c_s.border = border_cell
            row_cursor += 1

        end_row = row_cursor - 1
        tot_row = row_cursor

        ws_n.cell(row=tot_row, column=3, value=f'TOTAL SIN IVA — NIVEL {idx}').font = font_bold
        c_h = ws_n.cell(row=tot_row, column=8, value=f'=SUM(H{start_row}:H{end_row})')
        c_h.font = font_bold
        c_h.number_format = '0.0'
        c_t = ws_n.cell(row=tot_row, column=10, value=f'=SUM(J{start_row}:J{end_row})')
        c_t.font = font_bold
        c_t.number_format = money_fmt
        for c_i in range(1, 12):
            ws_n.cell(row=tot_row, column=c_i).fill = fill_total
            ws_n.cell(row=tot_row, column=c_i).border = border_cell

        iva_row = tot_row + 1
        ws_n.cell(row=iva_row, column=3, value='IVA (19%)').font = font_reg
        c_iva = ws_n.cell(row=iva_row, column=10, value=f'=J{tot_row}*0.19')
        c_iva.number_format = money_fmt

        grand_row = tot_row + 2
        ws_n.cell(row=grand_row, column=3, value=f'TOTAL CON IVA — NIVEL {idx}').font = font_bold
        c_g = ws_n.cell(row=grand_row, column=10, value=f'=J{tot_row}+J{iva_row}')
        c_g.font = font_bold
        c_g.number_format = money_fmt
        for c_i in range(1, 12):
            ws_n.cell(row=grand_row, column=c_i).fill = fill_sub
            ws_n.cell(row=grand_row, column=c_i).border = border_cell

        # Anchos cómodos
        widths_n = [12, 22, 42, 12, 10, 11, 10, 13, 18, 18, 40]
        for i, w in enumerate(widths_n, 1):
            ws_n.column_dimensions[get_column_letter(i)].width = w

        # Agregar fila en Resumen referenciando esta hoja con fórmula
        r_res = 4 + idx
        quoted_title = f"'{sheet_title}'"
        res_vals = [
            idx,
            niv.get('nombre', f'Nivel {idx}'),
            len(servicios),
            f'={quoted_title}!H{tot_row}',
            int(niv.get('dias_entrega') or 0),
            f'={quoted_title}!J{tot_row}',
            f'=F{r_res}*0.19',
            f'=F{r_res}+G{r_res}',
        ]
        for c_i, val in enumerate(res_vals, 1):
            c = ws_res.cell(row=r_res, column=c_i, value=val)
            c.font = font_bold if c_i in (2, 6, 8) else font_reg
            c.border = border_cell
            if c_i in (6, 7, 8):
                c.number_format = money_fmt
            if c_i == 4:
                c.number_format = '0.0'

    # Notas de ajuste manual en Resumen
    notas = solicitud.notas_ajuste_manual_json or []
    if notas:
        n_row = 4 + len(niveles) + 2
        ws_res.cell(row=n_row, column=1, value='ALERTAS DE AJUSTE MANUAL (PROPERTO):').font = font_bold
        for i, nota in enumerate(notas, 1):
            ws_res.cell(row=n_row + i, column=1, value=f'• {nota}').font = font_reg

    widths_res = [10, 42, 14, 15, 14, 24, 20, 24]
    for i, w in enumerate(widths_res, 1):
        ws_res.column_dimensions[get_column_letter(i)].width = w

    # --- ÚLTIMA HOJA: DIAGNÓSTICO Y BRIEF ---
    ws_d = wb.create_sheet(title='Diagnóstico y Brief')
    ws_d.merge_cells('A1:B1')
    ws_d['A1'] = f'DIAGNÓSTICO R.E.D. Y AUDITORÍA DE BRIEF — {proy_nombre}'
    ws_d['A1'].fill = fill_dark
    ws_d['A1'].font = font_title
    ws_d.row_dimensions[1].height = 28

    filas_diag = [
        ('Tipo de Proyecto', diag.get('tipo_proyecto', '')),
        ('Modelo de Negocio', diag.get('modelo_negocio', '')),
        ('Segmento / Perfil', f"{diag.get('segmento', '')} · {diag.get('perfil_cliente', '')}"),
        ('Conceptos Maestros', ', '.join(diag.get('conceptos_maestros') or [])),
        ('Dolores Clave', '\n'.join(f'• {x}' for x in (diag.get('dolores') or []))),
        ('Deseos y Motivaciones', '\n'.join(f'• {x}' for x in (diag.get('deseos') or []))),
        ('Retos Principales', '\n'.join(f'• {x}' for x in (diag.get('retos_principales') or []))),
        ('Brief — Categoría', brief.get('project_category', '')),
        ('Brief — m² Estimados', str(brief.get('estimated_area') or 'No especificado')),
        ('Brief — Línea Operativa', brief.get('operative_line', '')),
        ('Brief — Fase Alcance', brief.get('scope_phase', '')),
        ('Brief — Completitud (%)', f"{brief.get('completitud_pct', 0)}%"),
        ('Campos Faltantes', '\n'.join(f"• {f.get('campo')}: {f.get('pregunta_para_red')}" for f in (brief.get('campos_faltantes') or []))),
    ]
    for idx, (k, v) in enumerate(filas_diag, 3):
        c1 = ws_d.cell(row=idx, column=1, value=k)
        c2 = ws_d.cell(row=idx, column=2, value=v)
        c1.font = font_bold
        c1.fill = fill_sub
        c1.border = border_cell
        c2.font = font_reg
        c2.border = border_cell
        c2.alignment = Alignment(wrap_text=True, vertical='top')
    ws_d.column_dimensions['A'].width = 28
    ws_d.column_dimensions['B'].width = 85

    buf = io.BytesIO()
    wb.save(buf)
    safe_proy = re.sub(r'[\\/:*?"<>|]', '', proy_nombre).strip() or 'Propuesta'
    filename = f'ALCANCE_{safe_proy}.xlsx'
    return buf.getvalue(), filename
