"""
Generador de PDF de balance de compras (Rendicion de Cuentas).
"""
import io
import json
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from datetime import datetime, timezone, timedelta

from services.cotizacion_service import calcular_totales_rc


def generar_pdf_balance(cotizacion_numero, datos_cliente, datos_asesor, registros, productos_presupuesto, incluir_varios=False):
    """Genera PDF de balance de compras consolidando todos los registros."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5*cm, rightMargin=1.5*cm,
                            topMargin=2*cm, bottomMargin=2*cm)
    elements = []
    styles = getSampleStyleSheet()
    tz_cl = timezone(timedelta(hours=-3))

    def _sty(name, **kw):
        try:
            styles.add(ParagraphStyle(name=name, parent=styles['Normal'], **kw))
        except Exception:
            pass
        return styles[name]

    _sty('BTitle',     fontSize=18, fontName='Helvetica-Bold', spaceAfter=4,  textColor=colors.HexColor('#1e2447'))
    _sty('BSubtitle',  fontSize=10, textColor=colors.HexColor('#64748b'),     spaceAfter=2)
    _sty('BSection',   fontSize=11, fontName='Helvetica-Bold', spaceAfter=4,  textColor=colors.HexColor('#1e2447'), spaceBefore=10)
    _sty('BLabel',     fontSize=9,  textColor=colors.HexColor('#64748b'))
    _sty('BValue',     fontSize=9,  fontName='Helvetica-Bold')
    _sty('BSmall',     fontSize=8,  textColor=colors.HexColor('#64748b'))
    _sty('BRegHeader', fontSize=9,  fontName='Helvetica-Bold', textColor=colors.HexColor('#1e2447'), spaceBefore=8, spaceAfter=2)

    now_str = datetime.now(tz_cl).strftime('%d/%m/%Y %H:%M')

    # ── HEADER ──
    _logo_cell = ""
    try:
        from reportlab.platypus import Image as _RLImage
        _logo = _RLImage("logo.png")
        _logo_w = 4*cm
        _logo_aspect = _logo.imageHeight / float(_logo.imageWidth)
        _logo.drawWidth  = _logo_w
        _logo.drawHeight = _logo_w * _logo_aspect
        _logo_cell = _logo
    except Exception:
        pass

    header_data = [[
        _logo_cell,
        Paragraph("<b>BALANCE DE COMPRAS" + (" (CON VARIOS)" if incluir_varios else "") + "</b>", styles['BTitle']),
        Paragraph(f"Generado: {now_str}", styles['BSmall'])
    ]]
    header_tbl = Table(header_data, colWidths=[4.5*cm, 9*cm, 4*cm])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',  (2, 0), (2, 0),  'RIGHT'),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1e2447'), spaceBefore=4, spaceAfter=8))

    # ── DATOS DEL PROYECTO ──
    _nombre = datos_cliente.get('Nombre', '')
    _rut    = datos_cliente.get('RUT', '')
    _asesor = datos_asesor.get('Nombre Ejecutivo', '')
    info_data = [
        [Paragraph('<b>N° Presupuesto</b>', styles['BLabel']), Paragraph(cotizacion_numero, styles['BValue']),
         Paragraph('<b>Cliente</b>', styles['BLabel']), Paragraph(_nombre, styles['BValue'])],
        [Paragraph('<b>RUT</b>', styles['BLabel']), Paragraph(_rut, styles['BValue']),
         Paragraph('<b>Ejecutivo</b>', styles['BLabel']), Paragraph(_asesor, styles['BValue'])],
    ]
    info_tbl = Table(info_data, colWidths=[3*cm, 6*cm, 3*cm, 5.5*cm])
    info_tbl.setStyle(TableStyle([
        ('VALIGN',         (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 3),
        ('TOPPADDING',     (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_tbl)
    elements.append(Spacer(1, 0.3*cm))

    # ── PROGRESO GLOBAL ──
    if incluir_varios:
        prods_valid = list(productos_presupuesto or [])
    else:
        prods_valid = [p for p in (productos_presupuesto or [])
                       if str(p.get('Categoria', '')).strip().lower() != 'varios']
    total_items = len(prods_valid)
    items_en_registros = set()
    for reg in registros:
        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = json.loads(items_r)
            except Exception:
                items_r = []
        for it in items_r:
            if float(it.get('precio_real', 0) or 0) > 0:
                items_en_registros.add(str(it.get('item', '')))
    comprados = sum(1 for p in prods_valid if str(p.get('Item', '')) in items_en_registros)
    pct = round(comprados / total_items * 1000) / 10 if total_items > 0 else 0
    pct_col = (colors.HexColor('#3b82f6') if pct >= 100 else
               colors.HexColor('#16a34a') if pct >= 66.6 else
               colors.HexColor('#eab308') if pct >= 33.3 else colors.HexColor('#dc2626'))
    pct_lbl = 'Compra finalizada' if pct >= 100 else f'{pct}% comprado'

    prog_data = [[
        Paragraph('<b>Progreso de compra</b>', styles['BLabel']),
        Paragraph(f'<b>{pct_lbl}</b>', ParagraphStyle('_pc', parent=styles['Normal'],
            fontSize=11, fontName='Helvetica-Bold', textColor=pct_col)),
        Paragraph(f'{comprados} de {total_items} ítems', styles['BSmall']),
    ]]
    prog_tbl = Table(prog_data, colWidths=[3.5*cm, 6*cm, 3*cm])
    prog_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX',           (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING',   (0, 0), (0, -1),  8),
    ]))
    elements.append(prog_tbl)
    elements.append(Spacer(1, 0.4*cm))

    # ── REGISTROS DE COMPRA ──
    elements.append(Paragraph('Detalle de Registros de Compra', styles['BSection']))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=6))

    _tipo_labels   = {'online': 'Compra Online', 'presencial': 'Compra Presencial'}
    _subtipo_labels = {'retiro': 'Retiro', 'despacho': 'Despacho',
                       'completo': 'Retiro Completo', 'parcial': 'Retiro Parcial'}
    col_azul  = colors.HexColor('#1e2447')
    col_gris  = colors.HexColor('#64748b')
    col_verde = colors.HexColor('#16a34a')
    col_rojo  = colors.HexColor('#dc2626')

    tbl_header = ['Categoría', 'Ítem', 'Cant.', 'Presup.', 'Real', 'Adic.', 'Diferencia']
    col_ws = [2.5*cm, 5.5*cm, 1.2*cm, 2.2*cm, 2.2*cm, 1.2*cm, 2.7*cm]

    for idx_r, reg in enumerate(registros):
        try:
            fecha_reg = datetime.fromisoformat(
                reg['fecha_registro'].replace('Z', '+00:00')
            ).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M')
        except Exception:
            fecha_reg = '—'
        lugar    = reg.get('lugar_compra', '') or '—'
        tipo     = _tipo_labels.get(reg.get('tipo_compra', ''), reg.get('tipo_compra', '') or '—')
        subtipo  = _subtipo_labels.get(reg.get('subtipo_compra', ''), reg.get('subtipo_compra', '') or '')
        tipo_full = f"{tipo} — {subtipo}" if subtipo else tipo
        fecha_ent = reg.get('fecha_entrega_compra', '') or ''
        falto    = reg.get('falto_retirar', '') or ''
        obs      = reg.get('observaciones', '') or 'Sin observaciones'
        factura  = reg.get('factura_nombre', '') or '—'

        reg_info = f"Registro #{idx_r+1} — {fecha_reg} | {lugar} | {tipo_full}"
        if fecha_ent:
            reg_info += f" | Para: {fecha_ent}"
        elements.append(Paragraph(reg_info, styles['BRegHeader']))
        if falto:
            elements.append(Paragraph(f"Faltó retirar: {falto}", styles['BSmall']))
        elements.append(Paragraph(f"Observación: {obs}", styles['BSmall']))
        _factura_url = reg.get('factura_url', '') or ''
        if _factura_url:
            elements.append(Paragraph(
                f'Factura: <link href="{_factura_url}"><u><font color="#3b82f6">{factura}</font></u></link>',
                styles['BSmall']
            ))
        else:
            elements.append(Paragraph(f"Factura: {factura}", styles['BSmall']))
        elements.append(Spacer(1, 0.2*cm))

        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = json.loads(items_r)
            except Exception:
                items_r = []

        if items_r:
            rows = [tbl_header]
            row_types = ['header']
            sub_p = sub_r = sub_a = sub_s = 0.0
            pn_pdf  = {str(p.get('Item', '')) for p in (productos_presupuesto or [])}
            pp_map  = {str(p.get('Item', '')): round(float(p.get('Precio Unitario', 0) or 0)) for p in (productos_presupuesto or [])}
            for it in items_r:
                pp   = float(it.get('precio_presupuestado', 0) or 0)
                pr   = float(it.get('precio_real', 0) or 0)
                cant = float(it.get('cantidad', 1) or 1)
                adic = int(it.get('adicional', 0) or 0)
                dif  = (pp - pr) * cant - (adic * pr)
                is_sin = it.get('sin_registro', False)
                is_con = (it.get('es_adicional', False) or str(it.get('item', '')) not in pn_pdf) and not is_sin
                pp_real = pp_map.get(str(it.get('item', '')), pp) if not is_con and not is_sin else pp
                if is_sin:   sub_s += pr * cant
                elif is_con: sub_a += pr * cant
                else:        sub_p += pp_real * cant; sub_r += pr * cant + adic * pr
                dif_str = f"${abs(dif):,.0f} {'v' if dif >= 0 else '^'}".replace(',', '.')
                rows.append([it.get('categoria', ''), it.get('item', ''), str(int(cant)),
                    f"${pp_real:,.0f}".replace(',', '.'), f"${pr:,.0f}".replace(',', '.'),
                    str(adic), dif_str])
                row_types.append('sin' if is_sin else ('con' if is_con else 'normal'))
            bal_r = sub_p - sub_r
            rows.append(['', 'SUBTOTAL PRESUPUESTO', '',
                f"${sub_p:,.0f}".replace(',', '.'), f"${sub_r:,.0f}".replace(',', '.'),
                '', f"${abs(bal_r):,.0f} {'v' if bal_r >= 0 else '^'}".replace(',', '.')])
            row_types.append('subtotal')
            if sub_a > 0:
                rows.append(['', 'ADICIONALES CON REGISTRO', '', '—', f"${sub_a:,.0f}".replace(',', '.'), '', ''])
                row_types.append('subtotal_con')
            if sub_s > 0:
                rows.append(['', 'ADICIONALES SIN REGISTRO', '', '—', f"${sub_s:,.0f}".replace(',', '.'), '', ''])
                row_types.append('subtotal_sin')

            tbl = Table(rows, colWidths=col_ws, repeatRows=1)
            tbl_style = [
                ('BACKGROUND', (0, 0), (-1, 0), col_azul),
                ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
                ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE',   (0, 0), (-1, -1), 7),
                ('ALIGN',      (2, 0), (-1, -1), 'RIGHT'),
                ('ALIGN',      (0, 0), (1, -1),  'LEFT'),
                ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
                ('TOPPADDING',    (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
            for ri, rtype in enumerate(row_types):
                if rtype == 'con':
                    tbl_style += [('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fff7ed')),
                                  ('TEXTCOLOR',  (0, ri), (1, ri),  colors.HexColor('#c2410c'))]
                elif rtype == 'sin':
                    tbl_style += [('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fdf2f8')),
                                  ('TEXTCOLOR',  (0, ri), (1, ri),  colors.HexColor('#9d174d'))]
                elif rtype == 'subtotal':
                    tbl_style += [('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#f1f5f9')),
                                  ('FONTNAME',   (0, ri), (-1, ri), 'Helvetica-Bold')]
                elif rtype == 'subtotal_con':
                    tbl_style += [('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fff3e0')),
                                  ('FONTNAME',   (0, ri), (-1, ri), 'Helvetica-Bold'),
                                  ('TEXTCOLOR',  (0, ri), (-1, ri), colors.HexColor('#c2410c'))]
                elif rtype == 'subtotal_sin':
                    tbl_style += [('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fdf2f8')),
                                  ('FONTNAME',   (0, ri), (-1, ri), 'Helvetica-Bold'),
                                  ('TEXTCOLOR',  (0, ri), (-1, ri), colors.HexColor('#9d174d'))]
                if ri > 0 and row_types[ri] not in ('subtotal', 'subtotal_con', 'subtotal_sin') \
                        and len(rows[ri]) > 6 and rows[ri][6]:
                    is_ahorro = 'v' in rows[ri][6]
                    tbl_style.append(('TEXTCOLOR', (6, ri), (6, ri), col_verde if is_ahorro else col_rojo))
            tbl.setStyle(TableStyle(tbl_style))
            elements.append(tbl)

        elements.append(Spacer(1, 0.4*cm))
        if idx_r < len(registros) - 1:
            elements.append(HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#e2e8f0'), spaceAfter=4))

    # ── RESUMEN FINAL ──
    elements.append(Paragraph('Resumen Final Consolidado', styles['BSection']))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=8))

    tots     = calcular_totales_rc(productos_presupuesto, registros, incluir_varios=incluir_varios)
    total_p  = tots['tP']; total_r = tots['tR']
    total_a  = tots['tA']; total_s = tots['tS']
    iva_p    = total_p * 0.19; iva_r = total_r * 0.19
    bal      = total_p - total_r; iva_bal = iva_p - iva_r
    bal_col  = col_verde if bal >= 0 else col_rojo
    bal_lbl  = 'AHORRO' if bal >= 0 else 'SOBRECOSTO'

    def _fmt(v): return f"${abs(v):,.0f}".replace(',', '.')

    iva_a = total_a * 0.19; iva_s = total_s * 0.19

    resumen_rows = [
        ['', 'PRESUPUESTADO', 'REAL', 'BALANCE', 'ADIC. C/REG.', 'ADIC. S/REG.'],
        ['Subtotal neto',  _fmt(total_p), _fmt(total_r), _fmt(bal), _fmt(total_a),  _fmt(total_s)],
        ['IVA (19%)',      _fmt(iva_p),   _fmt(iva_r),   _fmt(iva_bal), _fmt(iva_a),  _fmt(iva_s)],
        ['Total con IVA',  _fmt(total_p+iva_p), _fmt(total_r+iva_r), _fmt(bal+iva_bal), _fmt(total_a+iva_a), _fmt(total_s+iva_s)],
    ]
    res_tbl = Table(resumen_rows, colWidths=[3*cm, 2.8*cm, 2.8*cm, 2.8*cm, 2.5*cm, 2.5*cm])
    res_style = [
        ('BACKGROUND', (0, 0), (-1, 0),  col_azul),
        ('TEXTCOLOR',  (0, 0), (-1, 0),  colors.white),
        ('FONTNAME',   (0, 0), (-1, 0),  'Helvetica-Bold'),
        ('FONTNAME',   (0, 3), (-1, 3),  'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, -1), 9),
        ('ALIGN',      (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN',      (0, 0), (0, -1),  'LEFT'),
        ('GRID',       (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TEXTCOLOR',  (3, 1), (3, -1),  bal_col),
        ('TEXTCOLOR',  (4, 1), (4, -1),  colors.HexColor('#c2410c')),
        ('BACKGROUND', (4, 0), (4, 0),   colors.HexColor('#ea580c')),
        ('BACKGROUND', (4, 1), (4, -1),  colors.HexColor('#fff7ed')),
        ('TEXTCOLOR',  (4, 0), (4, 0),   colors.white),
        ('TEXTCOLOR',  (5, 1), (5, -1),  colors.HexColor('#9d174d')),
        ('BACKGROUND', (5, 0), (5, 0),   colors.HexColor('#db2777')),
        ('BACKGROUND', (5, 1), (5, -1),  colors.HexColor('#fdf2f8')),
        ('TEXTCOLOR',  (5, 0), (5, 0),   colors.white),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    res_tbl.setStyle(TableStyle(res_style))
    elements.append(res_tbl)
    elements.append(Spacer(1, 0.3*cm))

    badge_data = [[Paragraph(
        f"<b>{bal_lbl}: {_fmt(bal+iva_bal)} (con IVA)</b>",
        ParagraphStyle('_badge', parent=styles['Normal'], fontSize=12,
            fontName='Helvetica-Bold', textColor=bal_col, alignment=1)
    )]]
    badge_tbl = Table(badge_data, colWidths=[16*cm])
    badge_tbl.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), colors.HexColor('#f0fdf4') if bal >= 0 else colors.HexColor('#fef2f2')),
        ('BOX',           (0, 0), (-1, -1), 1, bal_col),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(badge_tbl)

    doc.build(elements)
    buf.seek(0)
    return buf.read()
