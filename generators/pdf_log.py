"""
Generador de PDF de audit log (historial de cambios de cotización).

Rediseño 2026: mismo lenguaje visual que el PDF de selección de materiales
(masthead limpio con logo.png a la derecha, paleta cálida neutra + acento
terracota, versalitas con tracking). Se conserva la estructura (KPIs, grupos
por día, tabla antes/después) que ya funcionaba bien.
"""
import io as _io
import os as _os
from datetime import datetime as _dt, timezone, timedelta
from collections import OrderedDict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, KeepTogether, Flowable)
from reportlab.pdfbase.pdfmetrics import stringWidth


def generar_pdf_log(numero, logs):
    """PDF de auditoría — diseño editorial, alineado con el PDF de selección."""
    # ── Paleta (misma que el PDF de selección de materiales) ──
    INK       = colors.HexColor('#1c1b19')
    GRAPHITE  = colors.HexColor('#57534e')
    STONE     = colors.HexColor('#a8a29e')
    LINE      = colors.HexColor('#e7e4de')
    CANVAS    = colors.HexColor('#f6f4f0')
    ACCENT    = colors.HexColor('#8a5a44')   # terracota sobria (modificaciones)
    GREEN     = colors.HexColor('#3f7d55')   # creaciones
    ANTES_BG  = colors.HexColor('#fbeae7')
    ANTES_TX  = colors.HexColor('#b3392b')
    DESP_BG   = colors.HexColor('#e8f3ea')
    DESP_TX   = colors.HexColor('#2f7d4f')

    _tz    = timezone(timedelta(hours=-3))
    _ahora = _dt.now(_tz).strftime("%d/%m/%Y %H:%M")
    _n_mods  = len([l for l in logs if l.get("tipo_cambio") == "modificacion"])
    _n_crea  = len([l for l in logs if l.get("tipo_cambio") == "creacion"])
    _n_total = len(logs)
    _MESES = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
              7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}

    _CAMPOS_TEXTO = {'Teléfono','RUT cliente','RUT empresa','Correo','Nombre cliente',
                     'Asesor','Dirección cliente','Dirección instalación','Descripción del proyecto',
                     'Estado','Empresa','Tipo cliente','Comuna cliente','Región cliente'}

    def _fmt_val(v, campo=None):
        if campo and campo in _CAMPOS_TEXTO:
            return str(v) if v else "—"
        try:
            _s = str(v).strip()
            if _s.startswith("$"):
                return _s
            _n = float(_s)
            if abs(_n) > 999:
                return "$" + "{:,.0f}".format(round(_n)).replace(",", ".")
            return _s
        except Exception:
            return str(v) if v else "—"

    def _hora_chile(fs):
        try:
            return _dt.fromisoformat(fs.replace("Z", "+00:00")).astimezone(_tz).strftime("%H:%M")
        except Exception:
            return fs[11:16]

    def _fecha_chile(fs):
        try:
            return _dt.fromisoformat(fs.replace("Z", "+00:00")).astimezone(_tz).strftime("%Y-%m-%d")
        except Exception:
            return fs[:10]

    def _draw_tracked(c, x, y, text, font, size, color, tracking=0.0, rx=None):
        """Texto con tracking vía text object, aislado con save/restoreState (el Tc
        se filtra si no). rx = alinea a la derecha."""
        text = str(text)
        if rx is not None:
            x = rx - (stringWidth(text, font, size) + tracking * max(0, len(text) - 1))
        c.saveState()
        to = c.beginText(x, y)
        to.setFont(font, size); to.setFillColor(color); to.setCharSpace(tracking)
        to.textOut(text); c.drawText(to)
        c.restoreState()

    # Logo (mismo que el PDF de selección: logo.png).
    _logo_dims = None
    if _os.path.exists("logo.png"):
        try:
            from PIL import Image as _PIL
            _logo_dims = _PIL.open("logo.png").size
        except Exception:
            _logo_dims = None

    buf = _io.BytesIO()
    PW, PH = A4
    ML = MR = 2.0 * cm
    TM = 2.7 * cm
    BM = 1.9 * cm

    def _hf(cv, doc):
        cv.saveState()
        pw, ph = doc.pagesize
        # ── Masthead: título + N° EP a la izquierda, logo a la derecha nivelado ──
        _draw_tracked(cv, ML, ph - 1.02 * cm, 'HISTORIAL DE CAMBIOS',
                      'Helvetica-Bold', 8, STONE, tracking=2.0)
        _draw_tracked(cv, ML, ph - 1.58 * cm, ('N° ' + str(numero)),
                      'Helvetica-Bold', 14, INK, tracking=0.4)
        _draw_tracked(cv, ML, ph - 1.98 * cm, ('Generado el ' + _ahora + '  ·  hora Chile'),
                      'Helvetica', 7.5, STONE, tracking=0.3)
        if _logo_dims:
            _lw, _lh = _logo_dims
            _th = 1.3 * cm
            _tw = _lw * (_th / _lh)
            try:
                cv.drawImage("logo.png", pw - MR - _tw, ph - 1.98 * cm, width=_tw, height=_th,
                             preserveAspectRatio=True, mask="auto")
            except Exception:
                pass
        cv.setStrokeColor(INK); cv.setLineWidth(1.1)
        cv.line(ML, ph - 2.3 * cm, pw - MR, ph - 2.3 * cm)
        # ── Pie ──
        cv.setStrokeColor(LINE); cv.setLineWidth(0.6)
        cv.line(ML, BM - 0.12 * cm, pw - MR, BM - 0.12 * cm)
        _draw_tracked(cv, ML, BM - 0.5 * cm,
                      'Inversiones Container House SpA  ·  RUT 78.268.851-0  ·  Documento interno confidencial',
                      'Helvetica', 6.8, STONE)
        _draw_tracked(cv, 0, BM - 0.5 * cm, ('Pág. ' + str(doc.page)),
                      'Helvetica', 6.8, STONE, rx=pw - MR)
        cv.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=TM, bottomMargin=BM,
                            title=('Historial de cambios ' + str(numero)))

    base = getSampleStyleSheet()
    def _sty(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    s_small = _sty("sm", fontName="Helvetica", fontSize=7.5, textColor=STONE, leading=11)
    s_mono  = _sty("mn", fontName="Courier", fontSize=7.5, textColor=INK, leading=11)
    s_campo = _sty("cp", fontName="Helvetica-Bold", fontSize=6.8, textColor=STONE, leading=10)
    s_antes = _sty("an", fontName="Helvetica", fontSize=7.5, textColor=ANTES_TX, leading=11)
    s_dep   = _sty("dp", fontName="Helvetica", fontSize=7.5, textColor=DESP_TX, leading=11)
    s_num   = _sty("kn", fontName="Helvetica-Bold", fontSize=17, textColor=INK, leading=19)
    s_klab  = _sty("kl", fontName="Helvetica", fontSize=7, textColor=STONE, leading=10)

    story = []

    # ── KPIs (paleta cálida, línea de acento arriba) ──
    def _kpi(num, lab, hexcol):
        return Paragraph(f'<font size="17" color="{hexcol}"><b>{num}</b></font><br/>'
                         f'<font size="7" color="#a8a29e">{lab}</font>', s_num)

    kpi_w = doc.width / 4
    kpi_data = [[
        _kpi(_n_total, 'registros totales', '#1c1b19'),
        _kpi(_n_crea, 'creaciones', '#3f7d55'),
        _kpi(_n_mods, 'modificaciones', '#8a5a44'),
        Paragraph(f'<font size="9" color="#1c1b19"><b>{_ahora}</b></font><br/>'
                  f'<font size="7" color="#a8a29e">generado (hora Chile)</font>', s_num),
    ]]
    kpi_tbl = Table(kpi_data, colWidths=[kpi_w] * 4)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CANVAS),
        ("LINEABOVE",     (0, 0), (0, 0), 2, INK),
        ("LINEABOVE",     (1, 0), (1, 0), 2, GREEN),
        ("LINEABOVE",     (2, 0), (2, 0), 2, ACCENT),
        ("LINEABOVE",     (3, 0), (3, 0), 2, STONE),
        ("LINEAFTER",     (0, 0), (2, 0), 0.5, colors.white),
        ("TOPPADDING",    (0, 0), (-1, -1), 11),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 20))

    class DayHeader(Flowable):
        def __init__(self, titulo, n, width):
            Flowable.__init__(self)
            self.t = (titulo or '').upper(); self.n = n
            self.width = width; self.height = 0.86 * cm

        def wrap(self, *a):
            return self.width, self.height

        def draw(self):
            c = self.canv; Hh = self.height
            _draw_tracked(c, 0, Hh - 0.40 * cm, self.t, 'Helvetica-Bold', 9, INK, tracking=1.4)
            _cnt = str(self.n) + (' eventos' if self.n != 1 else ' evento')
            _draw_tracked(c, 0, Hh - 0.40 * cm, _cnt, 'Helvetica', 7.5, STONE, tracking=0.5, rx=self.width)
            c.setStrokeColor(LINE); c.setLineWidth(0.8)
            c.line(0, Hh - 0.64 * cm, self.width, Hh - 0.64 * cm)

    if not logs:
        story.append(Paragraph("Sin registros de modificaciones.", s_small))
    else:
        grupos = OrderedDict()
        for lg in logs:
            grupos.setdefault(_fecha_chile(lg.get("fecha", "")), []).append(lg)

        for fecha_key, items in grupos.items():
            try:
                _fd = _dt.fromisoformat(fecha_key)
                _titulo_dia = f"{_fd.day} de {_MESES[_fd.month]} de {_fd.year}"
            except Exception:
                _titulo_dia = fecha_key
            story.append(DayHeader(_titulo_dia, len(items), doc.width))
            story.append(Spacer(1, 6))

            for lg in items:
                _hora   = _hora_chile(lg.get("fecha", ""))
                _asesor = lg.get("asesor", "") or "Sistema"
                _tipo   = (lg.get("tipo_cambio", "") or "").upper()
                _det    = lg.get("detalle", {})

                _es_crea = (_tipo == "CREACION")
                _acc     = GREEN if _es_crea else ACCENT
                _bdg_bg  = DESP_BG if _es_crea else colors.HexColor('#f2e9e3')

                hdr_tbl = Table([[
                    Paragraph(f"<b>{_hora}</b>",
                              _sty(f"hr{id(lg)}", fontName="Courier-Bold", fontSize=9, textColor=_acc)),
                    Paragraph(_tipo,
                              _sty(f"bdg{id(lg)}", fontName="Helvetica-Bold", fontSize=6.8,
                                   textColor=_acc, backColor=_bdg_bg, borderPadding=(2, 6, 2, 6))),
                    Paragraph(f"<b>{_asesor}</b>",
                              _sty(f"as{id(lg)}", fontName="Helvetica", fontSize=8, textColor=GRAPHITE)),
                ]], colWidths=[1.9 * cm, 3.2 * cm, doc.width - 5.1 * cm])
                hdr_tbl.setStyle(TableStyle([
                    ("TOPPADDING",    (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING",   (0, 0), (0, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEAFTER",     (0, 0), (0, -1), 1.4, _acc),
                    ("LEFTPADDING",   (1, 0), (-1, -1), 9),
                ]))
                story.append(hdr_tbl)

                if isinstance(_det, dict):
                    if "mensaje" in _det:
                        msg_tbl = Table([[
                            Paragraph("", s_small),
                            Paragraph(str(_det['mensaje']), s_small),
                        ]], colWidths=[1.9 * cm, doc.width - 1.9 * cm])
                        msg_tbl.setStyle(TableStyle([
                            ("TOPPADDING",    (0, 0), (-1, -1), 2),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
                            ("LEFTPADDING",   (0, 0), (0, -1), 0),
                            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                            ("LINEAFTER",     (0, 0), (0, -1), 1.4, _acc),
                            ("LEFTPADDING",   (1, 0), (1, -1), 11),
                            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                        ]))
                        story.append(msg_tbl)
                    else:
                        cam_rows = [[
                            Paragraph("CAMPO", s_campo),
                            Paragraph("ANTES", s_campo),
                            Paragraph("DESPUÉS", s_campo),
                        ]]
                        for _c, _v in _det.items():
                            if isinstance(_v, dict):
                                _a = _fmt_val(str(_v.get("antes", "—")), campo=_c)
                                _d_raw = str(_v.get("despues", "—"))
                                if chr(10) in _d_raw:
                                    _lineas = _d_raw.split(chr(10))[:8]
                                    if len(_d_raw.split(chr(10))) > 8:
                                        _lineas.append('...')
                                    _d_para = Paragraph('<br/>'.join(_lineas), s_dep)
                                else:
                                    _d_para = Paragraph(_fmt_val(_d_raw, campo=_c)[:120], s_dep)
                                _a_para = Paragraph(_a[:70], s_antes)
                            else:
                                _a_para = Paragraph("—", s_antes)
                                _d_para = Paragraph(_fmt_val(str(_v), campo=_c)[:70], s_dep)
                            cam_rows.append([Paragraph(_c, s_mono), _a_para, _d_para])

                        if len(cam_rows) > 1:
                            cam_tbl = Table(cam_rows, colWidths=[4.2 * cm, 5.35 * cm, 5.35 * cm])
                            cam_styles = [
                                ("BACKGROUND",    (0, 0), (-1, 0), CANVAS),
                                ("LINEBELOW",     (0, 0), (-1, 0), 0.6, LINE),
                                ("LINEBELOW",     (0, 1), (-1, -1), 0.4, colors.white),
                                ("BOX",           (0, 0), (-1, -1), 0.4, LINE),
                                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                                ("LEFTPADDING",   (0, 0), (-1, -1), 7),
                                ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
                                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                            ]
                            for _ri in range(1, len(cam_rows)):
                                cam_styles.append(("BACKGROUND", (1, _ri), (1, _ri), ANTES_BG))
                                cam_styles.append(("BACKGROUND", (2, _ri), (2, _ri), DESP_BG))
                            cam_tbl.setStyle(TableStyle(cam_styles))

                            wrap_tbl = Table([["", cam_tbl]], colWidths=[1.9 * cm, doc.width - 1.9 * cm])
                            wrap_tbl.setStyle(TableStyle([
                                ("TOPPADDING",    (0, 0), (-1, -1), 3),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 11),
                                ("LEFTPADDING",   (0, 0), (0, -1), 0),
                                ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                                ("LINEAFTER",     (0, 0), (0, -1), 1.4, _acc),
                                ("LEFTPADDING",   (1, 0), (1, -1), 11),
                                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
                            ]))
                            story.append(KeepTogether(wrap_tbl))

                story.append(Spacer(1, 3))
            story.append(Spacer(1, 10))

    doc.build(story, onFirstPage=_hf, onLaterPages=_hf)
    buf.seek(0)
    return buf.read()
