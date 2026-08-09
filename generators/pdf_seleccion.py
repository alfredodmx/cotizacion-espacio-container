"""
Generador de PDF catalogo de seleccion de materiales del cliente.

Rediseno editorial/arquitectonico (2026): tipografia Helvetica (modernista),
paleta calida neutra (hueso/piedra/tinta), hairlines, mucho aire, tiles de
imagen uniformes y marcadores sutiles seleccionado/pendiente. Misma firma y
mismos datos de entrada que la version anterior.
"""


def generar_pdf_seleccion_cliente(ep, nombre_cliente, config_data, resps_map, mat_items_sel=None, fecha_formulario=''):
    """PDF catalogo de seleccion de materiales del cliente (diseno limpio)."""
    import io as _io_s
    import datetime as _dt_s
    import requests as _rq_s
    import os as _os_s
    from collections import defaultdict
    from PIL import Image as _PIL
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                     TableStyle, KeepTogether, Image as _RLImage, Flowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfbase.pdfmetrics import stringWidth

    if mat_items_sel is None:
        mat_items_sel = {}

    W, H = A4
    buffer = _io_s.BytesIO()

    # ── Paleta arquitectonica: tinta calida + neutros piedra + un acento sobrio ──
    INK      = colors.HexColor('#1c1b19')   # texto principal (negro calido)
    GRAPHITE = colors.HexColor('#57534e')   # texto secundario
    STONE    = colors.HexColor('#a8a29e')   # etiquetas / terciario
    LINE     = colors.HexColor('#e7e4de')   # hairlines
    CANVAS   = colors.HexColor('#f6f4f0')   # tiles suaves (pendiente / fondo imagen)
    WHITE    = colors.white
    ACCENT   = colors.HexColor('#8a5a44')   # terracota sobria (barra progreso / detalle)

    _now   = _dt_s.datetime.now()
    _fecha = (fecha_formulario or '').strip() or _now.strftime('%d/%m/%Y')
    _nstr  = _now.strftime('%d/%m/%Y')
    _tot   = len(config_data)
    _don   = sum(1 for c in config_data
                 if any(resps_map.get(str(i)) for i in (c.get('item_ids') or [])))
    _pct   = int(_don / _tot * 100) if _tot > 0 else 0

    styles = getSampleStyleSheet()

    def PS(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    LPAD = 1.7 * cm
    RPAD = 1.7 * cm
    CW   = W - LPAD - RPAD

    def _draw_tracked(c, x, y, text, font, size, color, tracking=0.0, rx=None):
        """Dibuja texto con tracking (letter-spacing) vía text object. Si rx, alinea
        a la derecha (calcula el ancho incluyendo el tracking)."""
        text = str(text)
        if rx is not None:
            _w = stringWidth(text, font, size) + tracking * max(0, len(text) - 1)
            x = rx - _w
        # save/restoreState aísla el charSpace (Tc): si no, el tracking se "filtra"
        # al texto que se dibuje después en la misma página (p.ej. la nota del pie).
        c.saveState()
        to = c.beginText(x, y)
        to.setFont(font, size)
        to.setFillColor(color)
        to.setCharSpace(tracking)
        to.textOut(text)
        c.drawText(to)
        c.restoreState()

    def _img_from_url(url, max_w, max_h):
        try:
            r = _rq_s.get(url, timeout=5)
            if r.status_code == 200:
                buf = _io_s.BytesIO(r.content)
                pil = _PIL.open(buf)
                iw, ih = pil.size
                ratio = min(max_w / iw, max_h / ih)
                buf.seek(0)
                return _RLImage(buf, width=iw * ratio, height=ih * ratio)
        except Exception:
            pass
        return None

    def _tile(idata, w, h, pendiente=False):
        """Tile visual uniforme: swatch de color, imagen centrada o placeholder suave.
        Marco hairline fino; fondo blanco (seleccionado) o piedra suave (pendiente)."""
        tipo = (idata or {}).get('tipo', '')
        hexv = (idata or {}).get('hex', '')
        url  = (idata or {}).get('imagen_url', '')
        if (not pendiente) and tipo == 'color' and hexv:
            try:
                col = colors.HexColor(hexv if str(hexv).startswith('#') else '#' + str(hexv))
            except Exception:
                col = CANVAS
            t = Table([['']], colWidths=[w], rowHeights=[h])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, 0), col),
                ('BOX', (0, 0), (0, 0), 0.5, LINE),
                ('LEFTPADDING', (0, 0), (0, 0), 0), ('RIGHTPADDING', (0, 0), (0, 0), 0),
                ('TOPPADDING', (0, 0), (0, 0), 0), ('BOTTOMPADDING', (0, 0), (0, 0), 0),
            ]))
            return t
        inner = None
        if (not pendiente) and url:
            inner = _img_from_url(url, w - 0.5 * cm, h - 0.5 * cm)
        if inner is None:
            inner = Paragraph('', styles['Normal'])
        t = Table([[inner]], colWidths=[w], rowHeights=[h])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), CANVAS if pendiente or inner is None else WHITE),
            ('BOX', (0, 0), (0, 0), 0.5, LINE),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'), ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (0, 0), 6), ('RIGHTPADDING', (0, 0), (0, 0), 6),
            ('TOPPADDING', (0, 0), (0, 0), 6), ('BOTTOMPADDING', (0, 0), (0, 0), 6),
        ]))
        return t

    # ── Estilos de texto ──
    _lab   = PS('_lab', fontName='Helvetica-Bold', fontSize=6.3, textColor=STONE,
                leading=8.5, spaceAfter=4)                       # etiqueta del grupo (caps)
    _name  = PS('_name', fontName='Helvetica-Bold', fontSize=9, textColor=INK,
                leading=11.5, spaceBefore=6, spaceAfter=1)       # nombre del material
    _oks   = PS('_oks', fontName='Helvetica', fontSize=6.8, textColor=GRAPHITE,
                leading=9, spaceBefore=1, spaceAfter=2)          # 'Seleccionado'
    _pends = PS('_pends', fontName='Helvetica-Oblique', fontSize=6.8, textColor=STONE,
                leading=9, spaceBefore=6, spaceAfter=2)          # 'Pendiente'

    story = []

    # ── Masthead (portada tipografica limpia) ──
    _logo_file = 'logo3.png' if _os_s.path.exists('logo3.png') else (
        'logo.png' if _os_s.path.exists('logo.png') else None)
    _logo_dims = None
    if _logo_file:
        try:
            _lw, _lh = _PIL.open(_logo_file).size
            _logo_dims = (_lw, _lh)
        except Exception:
            _logo_dims = None

    _nombre_full = (nombre_cliente or 'Cliente').strip()
    _nl = len(_nombre_full)
    _name_sz = 24 if _nl <= 20 else (20 if _nl <= 30 else 16)

    class Masthead(Flowable):
        def __init__(self):
            Flowable.__init__(self)
            self.width = CW
            self.height = 3.9 * cm

        def wrap(self, *a):
            return self.width, self.height

        def draw(self):
            c = self.canv
            Ht = self.height
            # Logo arriba a la izquierda
            if _logo_file and _logo_dims:
                _lw, _lh = _logo_dims
                _th = 1.15 * cm
                _tw = _lw * (_th / _lh)
                try:
                    c.drawImage(_logo_file, 0, Ht - _th, width=_tw, height=_th,
                                preserveAspectRatio=True, mask='auto')
                except Exception:
                    pass
            # Metadatos arriba a la derecha
            _draw_tracked(c, 0, Ht - 0.30 * cm, ('N° ' + str(ep)),
                          'Helvetica-Bold', 10, INK, tracking=0.4, rx=CW)
            _draw_tracked(c, 0, Ht - 0.72 * cm, _fecha,
                          'Helvetica', 8, STONE, tracking=0.3, rx=CW)
            # Titulo del documento (caps con tracking) + nombre grande
            _draw_tracked(c, 0, Ht - 1.95 * cm, 'SELECCIÓN DE MATERIALES',
                          'Helvetica-Bold', 8, STONE, tracking=2.2)
            c.setFont('Helvetica', _name_sz)
            c.setFillColor(INK)
            c.drawString(0, Ht - 2.95 * cm, _nombre_full)
            # Barra de progreso fina
            _by = 0.62 * cm
            c.setStrokeColor(LINE)
            c.setLineWidth(2.2)
            c.setLineCap(1)
            c.line(0, _by, CW, _by)
            _fillw = max(0.0, (_pct / 100.0) * CW)
            if _fillw > 0:
                c.setStrokeColor(ACCENT)
                c.line(0, _by, _fillw, _by)
            _draw_tracked(c, 0, 0.12 * cm,
                          (str(_don) + ' de ' + str(_tot) + ' secciones seleccionadas'),
                          'Helvetica', 7.2, STONE, tracking=0.5)
            _draw_tracked(c, 0, 0.12 * cm, (str(_pct) + '%'),
                          'Helvetica-Bold', 7.2, GRAPHITE, tracking=0.5, rx=CW)

    story.append(Masthead())
    story.append(Spacer(1, 0.55 * cm))

    # ── Secciones por categoria ──
    cats = defaultdict(list)
    seen = []
    for cfg in sorted(config_data, key=lambda x: (x.get('categoria', ''), x.get('orden', 0))):
        cat = cfg.get('categoria', 'Sin categoría')
        if cat not in seen:
            seen.append(cat)
        cats[cat].append(cfg)

    CARD_W = CW / 3.0
    IMG_H  = 2.95 * cm

    class SectionHeader(Flowable):
        def __init__(self, titulo, n):
            Flowable.__init__(self)
            self.width = CW
            self.height = 0.98 * cm
            self.titulo = (titulo or '').upper()
            self.n = n

        def wrap(self, *a):
            return self.width, self.height

        def draw(self):
            c = self.canv
            Ht = self.height
            _draw_tracked(c, 0, Ht - 0.42 * cm, self.titulo,
                          'Helvetica-Bold', 10.5, INK, tracking=1.6)
            _cnt = str(self.n) + (' elemento' if self.n == 1 else ' elementos')
            _draw_tracked(c, 0, Ht - 0.42 * cm, _cnt,
                          'Helvetica', 7.5, STONE, tracking=0.6, rx=CW)
            c.setStrokeColor(INK)
            c.setLineWidth(1.1)
            c.line(0, Ht - 0.72 * cm, CW, Ht - 0.72 * cm)

    for cat_name in seen:
        cfgs = cats[cat_name]
        grid_rows = []
        row_cells = []

        for cfg in cfgs:
            tg  = cfg.get('titulo_grupo', '') or ''
            ids = [str(x) for x in (cfg.get('item_ids') or [])]
            sel_id = sel_val = None
            for iid in ids:
                v = resps_map.get(str(iid))
                if v:
                    sel_id = iid
                    sel_val = v
                    break

            if sel_id:
                idata = mat_items_sel.get(sel_id, {}) or {}
                nom_sel = sel_val
                if idata.get('tipo', '') in ('color', 'imagen') and idata.get('nombre', ''):
                    nom_sel = idata.get('nombre', sel_val)
                card = Table([
                    [Paragraph(tg.upper(), _lab)],
                    [_tile(idata, CARD_W - 0.55 * cm, IMG_H, pendiente=False)],
                    [Paragraph(str(nom_sel)[:40], _name)],
                    [Paragraph('Seleccionado', _oks)],
                ], colWidths=[CARD_W - 0.4 * cm])
            else:
                card = Table([
                    [Paragraph(tg.upper(), _lab)],
                    [_tile({}, CARD_W - 0.55 * cm, IMG_H, pendiente=True)],
                    [Paragraph('', _name)],
                    [Paragraph('Pendiente de selección', _pends)],
                ], colWidths=[CARD_W - 0.4 * cm])

            card.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), WHITE),
                ('LEFTPADDING', (0, 0), (0, -1), 0), ('RIGHTPADDING', (0, 0), (0, -1), 0),
                ('TOPPADDING', (0, 0), (0, 0), 0), ('BOTTOMPADDING', (0, 0), (0, 0), 3),
                ('TOPPADDING', (0, 2), (0, -1), 0), ('BOTTOMPADDING', (0, 1), (0, 1), 0),
                ('VALIGN', (0, 0), (0, -1), 'TOP'),
            ]))
            row_cells.append(card)
            if len(row_cells) == 3:
                grid_rows.append(row_cells[:])
                row_cells = []

        while 0 < len(row_cells) < 3:
            row_cells.append(Paragraph('', styles['Normal']))
        if row_cells:
            grid_rows.append(row_cells)

        def _row_table(cells):
            _rt = Table([cells], colWidths=[CARD_W, CARD_W, CARD_W])
            _rt.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (0, -1), 0), ('RIGHTPADDING', (-1, 0), (-1, -1), 0),
                ('LEFTPADDING', (1, 0), (-1, -1), 0.3 * cm),
                ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ]))
            return _rt

        _blocks = [SectionHeader(cat_name, len(cfgs)), Spacer(1, 0.18 * cm)]
        if grid_rows:
            # El titulo viaja junto a la primera fila (evita titulo huerfano); las
            # filas siguientes fluyen sueltas para poder partir de pagina si hace falta.
            story.append(KeepTogether(_blocks + [_row_table(grid_rows[0])]))
            for _r in grid_rows[1:]:
                story.append(_row_table(_r))
        else:
            story.append(KeepTogether(_blocks))
        story.append(Spacer(1, 0.35 * cm))

    # ── Pie: nota + credito (solo en la ultima pagina) ──
    _total_pages = [0]

    def _count_pages(canvas, document):
        _total_pages[0] = document.page

    def _draw_footer(canvas, document):
        if document.page < _total_pages[0]:
            return
        canvas.saveState()
        _ntxt = (
            'Estimado cliente, luego de elaborar este formulario de selección de materiales '
            'usted cuenta con 3 días para realizar modificaciones. Transcurrido ese plazo los '
            'cambios pueden implicar costos adicionales y ajustes en los tiempos de entrega, y '
            'deberán reflejarse en un anexo a este documento.'
        )
        _fs = 7.3
        _lh = 0.37 * cm
        _lines = simpleSplit(_ntxt, 'Helvetica', _fs, CW - 0.5 * cm)
        _block_h = 0.55 * cm + len(_lines) * _lh
        _base = 1.35 * cm
        _top = _base + _block_h
        # Hairline superior de la nota
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.8)
        canvas.line(LPAD, _top + 0.35 * cm, W - RPAD, _top + 0.35 * cm)
        # Marca de acento a la izquierda + titulo
        canvas.setFillColor(ACCENT)
        canvas.rect(LPAD, _top - 0.30 * cm, 0.5 * cm, 0.09 * cm, fill=1, stroke=0)
        _draw_tracked(canvas, LPAD, _top - 0.18 * cm, 'NOTA IMPORTANTE',
                      'Helvetica-Bold', 8, INK, tracking=1.4)
        canvas.setFillColor(GRAPHITE)
        canvas.setFont('Helvetica', _fs)
        for _i, _lt in enumerate(_lines):
            canvas.drawString(LPAD, _top - 0.62 * cm - _i * _lh, _lt)
        # Credito al pie
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.8)
        canvas.line(LPAD, _base - 0.28 * cm, W - RPAD, _base - 0.28 * cm)
        canvas.setFont('Helvetica', 6.8)
        canvas.setFillColor(STONE)
        canvas.drawString(LPAD, _base - 0.62 * cm,
                          'Espacio Container House SpA  ·  Generado el ' + _nstr)
        canvas.drawRightString(W - RPAD, _base - 0.62 * cm,
                               (nombre_cliente or 'Cliente') + '  ·  Proyecto ' + str(ep))
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=LPAD, rightMargin=RPAD,
                            topMargin=1.35 * cm, bottomMargin=3.4 * cm,
                            title=('Selección de materiales ' + str(ep)))
    doc.build(story, onFirstPage=_count_pages, onLaterPages=_draw_footer)
    buffer.seek(0)
    return buffer.read()
