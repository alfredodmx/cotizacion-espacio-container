"""
Generador de PDF catalogo de seleccion de materiales del cliente.
"""
# La funcion generar_pdf_seleccion_cliente es extraida tal cual de app.py (lineas 3463-3953).
# Dependencias: reportlab, Pillow, requests.

def generar_pdf_seleccion_cliente(ep, nombre_cliente, config_data, resps_map, mat_items_sel=None, fecha_formulario=''):
    """PDF catalogo de seleccion — diseno con hero.jpeg."""
    import io as _io_s
    import datetime as _dt_s
    import requests as _rq_s
    import os as _os_s
    from collections import defaultdict
    from PIL import Image as _PIL
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, KeepTogether, Image as _RLImage)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import Flowable

    if mat_items_sel is None:
        mat_items_sel = {}

    W, H = A4
    buffer = _io_s.BytesIO()

    C_ACCENT  = colors.HexColor('#3b82f6')
    C_ACCENT2 = colors.HexColor('#1e40af')
    C_SOFT    = colors.HexColor('#eff6ff')
    C_WHITE   = colors.white
    C_DARK    = colors.HexColor('#1e3a5f')
    C_BORDER  = colors.HexColor('#bfdbfe')
    C_MUTED   = colors.HexColor('#6b7280')
    C_OK      = colors.HexColor('#059669')
    C_PEND    = colors.HexColor('#f97316')
    C_CARD    = colors.HexColor('#f8fafc')
    C_TEXT    = colors.HexColor('#1e293b')

    _now  = _dt_s.datetime.now()
    _nstr = _now.strftime('%d/%m/%Y')
    _tot  = len(config_data)
    _don  = sum(1 for c in config_data
                if any(resps_map.get(str(i)) for i in (c.get('item_ids') or [])))
    _pct  = int(_don / _tot * 100) if _tot > 0 else 0

    styles = getSampleStyleSheet()
    def PS(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)
    def _block(color, w, h):
        t = Table([['']], colWidths=[w], rowHeights=[h])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),color),
            ('LEFTPADDING',(0,0),(0,0),0),('RIGHTPADDING',(0,0),(0,0),0),
            ('TOPPADDING',(0,0),(0,0),0),('BOTTOMPADDING',(0,0),(0,0),0)]))
        return t
    def _img_from_url(url, max_w, max_h):
        try:
            r = _rq_s.get(url, timeout=5)
            if r.status_code == 200:
                buf = _io_s.BytesIO(r.content)
                pil = _PIL.open(buf)
                iw, ih = pil.size
                ratio = min(max_w/iw, max_h/ih)
                buf.seek(0)
                return _RLImage(buf, width=iw*ratio, height=ih*ratio)
        except Exception:
            pass
        return None
    def _swatch(hex_val, w, h):
        try:
            c = colors.HexColor(hex_val if hex_val.startswith('#') else f'#{hex_val}')
        except Exception:
            c = C_BORDER
        t = Table([['']], colWidths=[w], rowHeights=[h])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(0,0),c),
            ('LEFTPADDING',(0,0),(0,0),0),('RIGHTPADDING',(0,0),(0,0),0),
            ('TOPPADDING',(0,0),(0,0),0),('BOTTOMPADDING',(0,0),(0,0),0)]))
        return t

    LPAD = 1.5*cm
    RPAD = 1.5*cm
    CW   = W - LPAD - RPAD

    story = []

    logo_cell = Paragraph('ESPACIO CONTAINER HOUSE',
                           PS('_lc', fontName='Helvetica-Bold', fontSize=13, textColor=C_DARK))
    try:
        _logo_file = 'logo3.png' if _os_s.path.exists('logo3.png') else 'logo.png'
        pil_l = _PIL.open(_logo_file)
        lw, lh = pil_l.size
        target_h = 1.73*cm
        ratio = target_h / lh
        logo_cell = _RLImage(_logo_file, width=lw*ratio, height=lh*ratio)
    except Exception:
        pass

    MARGIN_SIDE = 20
    HEADER_W    = W - (MARGIN_SIDE * 2)
    HEADER_H    = 7.6*cm
    HEADER_R    = 20

    _hero_path = None
    for _fn in ['hero.jpeg', 'hero.jpg']:
        if _os_s.path.exists(_fn):
            _hero_path = _fn
            break

    class HeaderFlowable(Flowable):
        def __init__(self):
            Flowable.__init__(self)
            self.width  = W
            self.height = HEADER_H + MARGIN_SIDE
        def wrap(self, *args):
            return self.width, self.height
        def draw(self):
            c = self.canv
            x = MARGIN_SIDE; y = 0
            hw = HEADER_W; hh = HEADER_H
            c.saveState()
            p = c.beginPath()
            p.roundRect(x, y, hw, hh, HEADER_R)
            c.clipPath(p, stroke=0, fill=0)
            try:
                from reportlab.lib.utils import ImageReader as _IR
                from PIL import ImageDraw as _ID, Image as _PILImg
                _hp = _PILImg.open(_hero_path).convert('RGBA')
                _iw, _ih = _hp.size
                _pw, _ph = int(hw), int(hh)
                _scale = max(_pw/_iw, _ph/_ih)
                _sw = int(_iw * _scale); _sh = int(_ih * _scale)
                _hp = _hp.resize((_sw, _sh), _PILImg.LANCZOS)
                _ox = (_sw - _pw) // 2; _oy = (_sh - _ph) // 2
                _hp = _hp.crop((_ox, _oy, _ox+_pw, _oy+_ph))
                _hp_rgba = _hp.convert('RGBA')
                _overlay = _PILImg.new('RGBA', _hp_rgba.size, (5, 10, 20, int(0.30 * 255)))
                _hp = _PILImg.alpha_composite(_hp_rgba, _overlay).convert('RGB')
                _buf = _io_s.BytesIO()
                _hp.save(_buf, format='PNG')
                _buf.seek(0)
                c.drawImage(_IR(_buf), x, y, width=hw, height=hh, preserveAspectRatio=False)
            except Exception:
                c.setFillColor(colors.HexColor('#0a1628'))
                c.roundRect(x, y, hw, hh, HEADER_R, fill=1, stroke=0)
            c.restoreState()
            for _si in range(12, 0, -1):
                _sa = 0.028 * _si / 12 * 0.8
                c.saveState()
                c.setFillColorRGB(10/255, 22/255, 40/255, _sa)
                c.roundRect(x-_si*0.5, y-_si*1.2, hw+_si, hh+_si*0.3, HEADER_R+_si*0.5, fill=1, stroke=0)
                c.restoreState()
            PAD = 24; cx = x + PAD
            try:
                _lf2 = 'logo3.png' if _os_s.path.exists('logo3.png') else 'logo.png'
                pil_l = _PIL.open(_lf2)
                lw2, lh2 = pil_l.size
                target_h2 = 1.73*cm; ratio2 = target_h2 / lh2
                logo_w2 = lw2 * ratio2
                logo_x = x + hw - PAD - logo_w2
                logo_y = y + hh - PAD - target_h2
                c.drawImage(_lf2, logo_x, logo_y, width=logo_w2, height=target_h2,
                            preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
            _font_bold = 'Helvetica-Bold'
            badge_y = y + hh - PAD - 1.73*cm - 0.5*cm
            c.saveState()
            c.setFillColorRGB(1,1,1,0.15); c.setStrokeColorRGB(1,1,1,0.3); c.setLineWidth(0.5)
            c.roundRect(cx, badge_y-2, 5.5*cm, 0.45*cm, 8, fill=1, stroke=1)
            c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 6.5)
            c.drawString(cx+8, badge_y+3, '✶ TU SELECCIÓN DE MATERIALES ✶')
            c.restoreState()
            title_y = badge_y - 1.4*cm
            c.setFillColor(colors.white); c.setFont(_font_bold, 22)
            _primer = (nombre_cliente or 'Cliente').split()[0]
            c.drawString(cx, title_y + 0.5*cm, f'Bienvenida/o, {_primer}')
            c.setFont('Helvetica', 8); c.setFillColorRGB(1,1,1,0.7)
            c.drawString(cx, title_y-0.1*cm, 'Selecciones de materiales para tu proyecto container')
            c.saveState()
            c.setFillColorRGB(1,1,1,0.1); c.setStrokeColorRGB(1,1,1,0.15)
            c.roundRect(cx, y+PAD, 3.5*cm, 0.45*cm, 8, fill=1, stroke=1)
            c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 7.5)
            c.drawString(cx+8, y+PAD+5, f'\U0001f4cb {ep}')
            c.restoreState()
            bar_y = y + PAD + 0.55*cm; bar_w = hw - PAD*2; bar_h = 5
            c.saveState()
            c.setFillColorRGB(1,1,1,0.12)
            c.roundRect(cx, bar_y, bar_w, bar_h, 2, fill=1, stroke=0)
            fill_w = max(4.0, (_pct/100.0) * bar_w)
            c.setFillColor(colors.HexColor('#3b82f6'))
            c.roundRect(cx, bar_y, fill_w, bar_h, 2, fill=1, stroke=0)
            c.restoreState()
            c.setFont('Helvetica', 6); c.setFillColorRGB(1,1,1,0.6)
            c.drawString(cx, bar_y+bar_h+3, f'{_don} de {_tot} secciones completadas — {_pct}%')

    story.append(Spacer(1, 6))
    story.append(HeaderFlowable())
    story.append(Spacer(1, 0.5*cm))

    sub = Table([[
        Paragraph('Tu detalle de selecciones',
                   PS('_ds', fontName='Helvetica-Bold', fontSize=13, textColor=C_DARK, leading=16)),
        Paragraph(f'{_pct}% completado  ·  {_don}/{_tot} secciones',
                   PS('_ds2', fontName='Helvetica', fontSize=9, textColor=C_MUTED, alignment=2)),
    ]], colWidths=[CW*0.6, CW*0.4])
    sub.setStyle(TableStyle([
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(0,0),LPAD),('RIGHTPADDING',(-1,0),(-1,0),RPAD),
        ('TOPPADDING',(0,0),(-1,-1),14),('BOTTOMPADDING',(0,0),(-1,-1),6),
    ]))
    story.append(sub)
    story.append(Table([[_block(C_ACCENT,CW,2)]], colWidths=[W],
                        style=[('LEFTPADDING',(0,0),(0,0),LPAD),
                                ('RIGHTPADDING',(0,0),(0,0),RPAD),
                                ('TOPPADDING',(0,0),(0,0),0),
                                ('BOTTOMPADDING',(0,0),(0,0),12)]))

    cats = defaultdict(list)
    seen = []
    for cfg in sorted(config_data, key=lambda x: (x.get('categoria',''), x.get('orden',0))):
        cat = cfg.get('categoria', 'Sin categoría')
        if cat not in seen:
            seen.append(cat)
        cats[cat].append(cfg)

    CARD_W = CW / 3
    IMG_H  = 2.8*cm

    for cat_name in seen:
        cfgs = cats[cat_name]
        cat_h = Table([[
            Paragraph(cat_name.upper(),
                       PS('_ch', fontName='Helvetica-Bold', fontSize=10,
                          textColor=C_ACCENT2, leading=13, alignment=1)),
        ]], colWidths=[W])
        cat_h.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(0,0), C_SOFT),
            ('LEFTPADDING',(0,0),(0,0),0),('RIGHTPADDING',(0,0),(0,0),0),
            ('TOPPADDING',(0,0),(0,0),7),('BOTTOMPADDING',(0,0),(0,0),6),
            ('LINEBELOW',(0,0),(0,0), 1.5, C_ACCENT),
            ('ALIGN',(0,0),(0,0),'CENTER'),
        ]))

        grid_rows = []
        row_cells = []

        for cfg in cfgs:
            tg  = cfg.get('titulo_grupo', '')
            ids = [str(x) for x in (cfg.get('item_ids') or [])]
            sel_id = sel_val = None
            for iid in ids:
                v = resps_map.get(str(iid))
                if v:
                    sel_id = iid; sel_val = v; break

            if sel_id:
                idata   = mat_items_sel.get(sel_id, {})
                tipo    = idata.get('tipo', '')
                img_url = idata.get('imagen_url', '')
                hex_val = idata.get('hex', '')
                nom_sel = sel_val
                if tipo in ('color', 'imagen') and idata.get('nombre', ''):
                    nom_sel = idata.get('nombre', sel_val)
                visual = None
                if tipo == 'color' and hex_val:
                    visual = _swatch(hex_val, CARD_W-0.4*cm, IMG_H)
                elif img_url:
                    visual = _img_from_url(img_url, CARD_W-0.4*cm, IMG_H)
                if not visual:
                    visual = Table([[Paragraph(nom_sel[:14],
                                    PS('_fb', fontName='Helvetica-Bold', fontSize=9,
                                       textColor=C_ACCENT2, alignment=1))]],
                                   colWidths=[CARD_W-0.4*cm], rowHeights=[IMG_H],
                                   style=[('BACKGROUND',(0,0),(0,0),C_SOFT),
                                          ('VALIGN',(0,0),(0,0),'MIDDLE')])
                card = Table([
                    [Paragraph(tg, PS('_ct', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_MUTED, leading=10))],
                    [visual],
                    [Paragraph(nom_sel[:28], PS('_cv', fontName='Helvetica-Bold', fontSize=8, textColor=C_TEXT, leading=10, spaceBefore=3))],
                    [Paragraph('Seleccionado', PS('_ck', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_OK, spaceBefore=1, spaceAfter=4))],
                ], colWidths=[CARD_W-0.2*cm])
                card.setStyle(TableStyle([
                    ('BOX',(0,0),(0,-1), 0.5, C_BORDER),
                    ('BACKGROUND',(0,0),(0,-1), C_WHITE),
                    ('LEFTPADDING',(0,0),(0,-1),6),('RIGHTPADDING',(0,0),(0,-1),6),
                    ('TOPPADDING',(0,0),(0,0),5),('BOTTOMPADDING',(0,0),(0,0),4),
                    ('LEFTPADDING',(0,1),(0,1),0),('RIGHTPADDING',(0,1),(0,1),0),
                    ('TOPPADDING',(0,1),(0,1),0),('BOTTOMPADDING',(0,1),(0,1),0),
                    ('LINEBELOW',(0,1),(0,1), 1.5, C_ACCENT),
                ]))
            else:
                card = Table([
                    [Paragraph(tg, PS('_pt', fontName='Helvetica-Bold', fontSize=7.5, textColor=C_MUTED, leading=10))],
                    [Table([[Paragraph('—', PS('_qm', fontName='Helvetica', fontSize=18,
                                               textColor=C_BORDER, alignment=1))]],
                            colWidths=[CARD_W-0.4*cm], rowHeights=[IMG_H],
                            style=[('BACKGROUND',(0,0),(0,0),C_CARD),
                                   ('VALIGN',(0,0),(0,0),'MIDDLE')])],
                    [Paragraph('Pendiente de selección',
                                PS('_pp', fontName='Helvetica-Oblique', fontSize=7.5, textColor=C_PEND, spaceAfter=4))],
                ], colWidths=[CARD_W-0.2*cm])
                card.setStyle(TableStyle([
                    ('BOX',(0,0),(0,-1), 0.5, C_BORDER),
                    ('BACKGROUND',(0,0),(0,-1), C_WHITE),
                    ('LEFTPADDING',(0,0),(0,-1),6),('RIGHTPADDING',(0,0),(0,-1),6),
                    ('TOPPADDING',(0,0),(0,0),5),('BOTTOMPADDING',(0,0),(0,0),4),
                    ('LEFTPADDING',(0,1),(0,1),0),('RIGHTPADDING',(0,1),(0,1),0),
                    ('TOPPADDING',(0,1),(0,1),0),('BOTTOMPADDING',(0,1),(0,1),0),
                    ('LINEBELOW',(0,1),(0,1), 1.5, C_PEND),
                ]))

            row_cells.append(card)
            if len(row_cells) == 3:
                grid_rows.append(row_cells[:])
                row_cells = []

        while 0 < len(row_cells) < 3:
            row_cells.append(Paragraph('', styles['Normal']))
        if row_cells:
            grid_rows.append(row_cells)

        if grid_rows:
            grid = Table(grid_rows, colWidths=[CARD_W, CARD_W, CARD_W])
            grid.setStyle(TableStyle([
                ('VALIGN',(0,0),(-1,-1),'TOP'),
                ('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
                ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),
            ]))
            wrap = Table([[grid]], colWidths=[W])
            wrap.setStyle(TableStyle([
                ('LEFTPADDING',(0,0),(0,0),LPAD),('RIGHTPADDING',(0,0),(0,0),RPAD),
                ('TOPPADDING',(0,0),(0,0),4),('BOTTOMPADDING',(0,0),(0,0),4),
            ]))
            story.append(KeepTogether([cat_h, wrap]))
        story.append(Spacer(1, 0.2*cm))

    _total_pages = [0]

    def _count_pages(canvas, document):
        _total_pages[0] = document.page

    def _draw_last(canvas, document):
        if document.page < _total_pages[0]:
            return
        canvas.saveState()
        _nw = W - LPAD - RPAD
        _ny = 1.5*cm
        from reportlab.lib.utils import simpleSplit
        _max_w = _nw - 16
        _font_sz = 7.5
        _line_h = 0.36*cm
        _ntxt = (
            'Estimado cliente, después de la elaboración de este formulario de selección de materiales '
            'de su proyecto, usted cuenta con 3 días para realizar modificaciones. '
            'Transcurrido este tiempo puede realizar cambios pero puede incurrir en costos adicionales '
            'y alteraciones en los tiempos de entrega de su proyecto. '
            'Dichos cambios deberán verse reflejados en un anexo a este formulario.'
        )
        _lines = simpleSplit(_ntxt, 'Helvetica', _font_sz, _max_w)
        _nh = (len(_lines) + 1) * _line_h + 0.25*cm
        canvas.setFillColor(colors.HexColor('#eff6ff'))
        canvas.setStrokeColor(colors.HexColor('#3b82f6'))
        canvas.setLineWidth(1.5)
        canvas.roundRect(LPAD, _ny, _nw, _nh, 6, fill=1, stroke=1)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        canvas.roundRect(LPAD, _ny, 0.28*cm, _nh, 6, fill=1, stroke=0)
        canvas.rect(LPAD+0.14*cm, _ny, 0.14*cm, _nh, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor('#1e40af'))
        canvas.setFont('Helvetica-Bold', 8.5)
        canvas.drawString(LPAD+0.42*cm, _ny+_nh-0.34*cm, '!  Nota importante')
        canvas.setFillColor(colors.HexColor('#1e293b'))
        canvas.setFont('Helvetica', _font_sz)
        for _li, _lt in enumerate(_lines):
            canvas.drawString(LPAD+0.42*cm, _ny+_nh-0.34*cm-(_li+1)*_line_h, _lt)
        _ly = _ny + _nh + 0.12*cm
        canvas.setStrokeColor(C_ACCENT); canvas.setLineWidth(1)
        canvas.line(LPAD, _ly, W-RPAD, _ly)
        canvas.setFont('Helvetica', 7); canvas.setFillColor(C_MUTED)
        _fy = _ly + 0.15*cm
        canvas.drawString(LPAD, _fy, f'Generado el {_nstr}  ·  Espacio Container House SpA')
        canvas.drawRightString(W-RPAD, _fy, f'{nombre_cliente or "Cliente"}  ·  Proyecto {ep}')
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=0, rightMargin=0,
                            topMargin=0, bottomMargin=3.5*cm)
    doc.build(story, onFirstPage=_count_pages, onLaterPages=_draw_last)
    buffer.seek(0)
    return buffer.read()
