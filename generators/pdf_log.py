"""
Generador de PDF de audit log (historial de cambios de cotizacion).
"""
import io as _io
import os as _os
from datetime import datetime as _dt, timezone, timedelta
from collections import OrderedDict
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                Table, TableStyle, KeepTogether)


def generar_pdf_log(numero, logs):
    """PDF de auditoria — diseno limpio tipo registro de cambios."""
    C_BG       = colors.HexColor('#0d1117')
    C_AZUL     = colors.HexColor('#58a6ff')
    C_VERDE    = colors.HexColor('#3fb950')
    C_AMARILLO = colors.HexColor('#d29922')
    C_GRIS     = colors.HexColor('#8b949e')
    C_LINE     = colors.HexColor('#e2e8f0')
    C_HDR_BG   = colors.HexColor('#f6f8fa')
    C_ANTES    = colors.HexColor('#ffdcd7')
    C_DESPUES  = colors.HexColor('#ccffd8')
    C_ANT_TXT  = colors.HexColor('#cf222e')
    C_DEP_TXT  = colors.HexColor('#1a7f37')

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
                return "$" + "{:,.0f}".format(round(_n)).replace(",",".")
            return _s
        except Exception:
            return str(v) if v else "—"

    def _hora_chile(fs):
        try:
            return _dt.fromisoformat(fs.replace("Z","+00:00")).astimezone(_tz).strftime("%H:%M")
        except Exception:
            return fs[11:16]

    def _fecha_chile(fs):
        try:
            return _dt.fromisoformat(fs.replace("Z","+00:00")).astimezone(_tz).strftime("%Y-%m-%d")
        except Exception:
            return fs[:10]

    buf = _io.BytesIO()
    PW, PH = A4
    ML = MR = 2.2*cm
    TM = 2.8*cm
    BM = 2.0*cm

    def _hf(cv, doc):
        cv.saveState()
        pw, ph = doc.pagesize
        banda_h = 1.4*cm
        cv.setFillColor(C_BG)
        cv.rect(0, ph - banda_h, pw, banda_h, fill=1, stroke=0)
        if _os.path.exists("logo.png"):
            from reportlab.lib.utils import ImageReader
            _img = ImageReader("logo.png")
            _iw, _ih = _img.getSize()
            _lw = 2.6*cm
            _lh = _lw * (_ih / float(_iw))
            _ly = ph - banda_h + (banda_h - _lh) / 2
            cv.drawImage(_img, x=(pw - _lw)/2, y=_ly,
                         width=_lw, height=_lh,
                         preserveAspectRatio=True, mask="auto")
        cv.setFont("Helvetica-Bold", 6.5)
        cv.setFillColor(C_GRIS)
        cv.drawString(ML, ph - banda_h/2 - 2.5, "AUDIT LOG")
        cv.setFont("Helvetica", 6.5)
        cv.drawRightString(pw - MR, ph - banda_h/2 - 2.5, numero)
        cv.setStrokeColor(C_AZUL)
        cv.setLineWidth(1.2)
        cv.line(ML, ph - banda_h - 1, pw - MR, ph - banda_h - 1)
        cv.setStrokeColor(C_LINE)
        cv.setLineWidth(0.4)
        cv.line(ML, BM - 0.1*cm, pw - MR, BM - 0.1*cm)
        cv.setFont("Helvetica", 6.5)
        cv.setFillColor(C_GRIS)
        cv.drawString(ML, BM - 0.45*cm,
            "Inversiones Container House SpA  ·  RUT 78.268.851-0  ·  Documento interno confidencial")
        cv.drawRightString(pw - MR, BM - 0.45*cm, f"Pág. {doc.page}  ·  {_ahora}")
        cv.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=ML, rightMargin=MR,
                            topMargin=TM, bottomMargin=BM)

    base = getSampleStyleSheet()
    def _sty(name, **kw):
        return ParagraphStyle(name, parent=base["Normal"], **kw)

    s_ep     = _sty("ep",  fontName="Helvetica-Bold", fontSize=20, textColor=C_BG, spaceAfter=2)
    s_sub    = _sty("sub", fontName="Helvetica", fontSize=9, textColor=C_GRIS, spaceAfter=14)
    s_dia    = _sty("dia", fontName="Helvetica-Bold", fontSize=7.5, textColor=C_AZUL, spaceBefore=12, spaceAfter=3)
    s_normal = _sty("nor", fontName="Helvetica", fontSize=8.5, leading=13)
    s_small  = _sty("sm",  fontName="Helvetica", fontSize=7.5, textColor=C_GRIS, leading=11)
    s_mono   = _sty("mn",  fontName="Courier", fontSize=7.5, leading=11)
    s_campo  = _sty("cp",  fontName="Helvetica-Bold", fontSize=7.5, leading=11)
    s_antes  = _sty("an",  fontName="Helvetica", fontSize=7.5, textColor=C_ANT_TXT, leading=11)
    s_dep    = _sty("dp",  fontName="Helvetica", fontSize=7.5, textColor=C_DEP_TXT, leading=11)

    story = []

    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph("Historial de cambios", s_sub))
    story.append(Paragraph(numero, s_ep))
    story.append(Spacer(1, 6))
    story.append(Table([[""]], colWidths=[doc.width],
                        style=[("LINEBELOW",(0,0),(0,0),0.8,C_BG),
                               ("TOPPADDING",(0,0),(0,0),0),
                               ("BOTTOMPADDING",(0,0),(0,0),0)]))
    story.append(Spacer(1, 10))

    kpi_w = doc.width / 4
    kpi_data = [[
        Paragraph(f'<font size="17"><b>{_n_total}</b></font><br/>'
                  f'<font color="#8b949e" size="7">registros totales</font>', s_normal),
        Paragraph(f'<font size="17" color="#3fb950"><b>{_n_crea}</b></font><br/>'
                  f'<font color="#8b949e" size="7">creaciones</font>', s_normal),
        Paragraph(f'<font size="17" color="#58a6ff"><b>{_n_mods}</b></font><br/>'
                  f'<font color="#8b949e" size="7">modificaciones</font>', s_normal),
        Paragraph(f'<font size="8.5"><b>{_ahora}</b></font><br/>'
                  f'<font color="#8b949e" size="7">generado (hora Chile)</font>', s_normal),
    ]]
    kpi_tbl = Table(kpi_data, colWidths=[kpi_w]*4)
    kpi_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,-1), C_HDR_BG),
        ("LINEABOVE",     (0,0), (0,0),   2, C_BG),
        ("LINEABOVE",     (1,0), (1,0),   2, C_VERDE),
        ("LINEABOVE",     (2,0), (2,0),   2, C_AZUL),
        ("LINEABOVE",     (3,0), (3,0),   2, C_AMARILLO),
        ("LINEAFTER",     (0,0), (2,0),   0.4, C_LINE),
        ("TOPPADDING",    (0,0), (-1,-1), 10),
        ("BOTTOMPADDING", (0,0), (-1,-1), 10),
        ("LEFTPADDING",   (0,0), (-1,-1), 10),
        ("RIGHTPADDING",  (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
    ]))
    story.append(kpi_tbl)
    story.append(Spacer(1, 18))

    if not logs:
        story.append(Paragraph("Sin registros.", s_small))
    else:
        grupos = OrderedDict()
        for lg in logs:
            _f = _fecha_chile(lg.get("fecha", ""))
            grupos.setdefault(_f, []).append(lg)

        for fecha_key, items in grupos.items():
            try:
                _fd = _dt.fromisoformat(fecha_key)
                _titulo_dia = f"{_fd.day} de {_MESES[_fd.month]} de {_fd.year}".upper()
            except Exception:
                _titulo_dia = fecha_key

            dia_tbl = Table(
                [[Paragraph(f"── {_titulo_dia}", s_dia),
                  Paragraph(f"{len(items)} evento{'s' if len(items)!=1 else ''}",
                            _sty(f"cnt{fecha_key}", fontName="Helvetica", fontSize=7.5,
                                 textColor=C_GRIS, alignment=TA_RIGHT))]],
                colWidths=[doc.width*0.75, doc.width*0.25])
            dia_tbl.setStyle(TableStyle([
                ("LINEBELOW",     (0,0), (-1,0), 0.4, C_LINE),
                ("TOPPADDING",    (0,0), (-1,-1), 0),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("VALIGN",        (0,0), (-1,-1), "BOTTOM"),
                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
            ]))
            story.append(dia_tbl)

            for lg in items:
                _hora   = _hora_chile(lg.get("fecha", ""))
                _asesor = lg.get("asesor", "") or "Sistema"
                _tipo   = lg.get("tipo_cambio", "").upper()
                _det    = lg.get("detalle", {})

                _dot_color = C_VERDE if _tipo == "CREACION" else C_AZUL
                _bdg_bg    = colors.HexColor("#d1f5db") if _tipo == "CREACION" else colors.HexColor("#dbeafe")
                _bdg_txt   = colors.HexColor("#1a7f37") if _tipo == "CREACION" else colors.HexColor("#1d4ed8")

                hdr_tbl = Table([[
                    Paragraph(f"<b>{_hora}</b>",
                               _sty(f"hr{_hora}{id(lg)}", fontName="Courier-Bold",
                                    fontSize=9, textColor=_dot_color)),
                    Paragraph(_tipo,
                               _sty(f"bdg{_hora}{id(lg)}", fontName="Helvetica-Bold",
                                    fontSize=7, textColor=_bdg_txt, backColor=_bdg_bg,
                                    borderPadding=(2,5,2,5))),
                    Paragraph(f"<b>{_asesor}</b>",
                               _sty(f"as{_hora}{id(lg)}", fontName="Helvetica",
                                    fontSize=8, textColor=C_GRIS)),
                ]], colWidths=[2.0*cm, 3.2*cm, doc.width - 5.2*cm])
                hdr_tbl.setStyle(TableStyle([
                    ("TOPPADDING",    (0,0), (-1,-1), 7),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                    ("LEFTPADDING",   (0,0), (-1,-1), 0),
                    ("RIGHTPADDING",  (0,0), (-1,-1), 4),
                    ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                    ("LINEAFTER",     (0,0), (0,-1),  1.2, _dot_color),
                    ("LEFTPADDING",   (1,0), (-1,-1), 8),
                ]))
                story.append(hdr_tbl)

                if isinstance(_det, dict):
                    if "mensaje" in _det:
                        msg_tbl = Table([[
                            Paragraph("", s_small),
                            Paragraph(f"-> {_det['mensaje']}", s_small),
                        ]], colWidths=[2.0*cm, doc.width - 2.0*cm])
                        msg_tbl.setStyle(TableStyle([
                            ("TOPPADDING",    (0,0), (-1,-1), 2),
                            ("BOTTOMPADDING", (0,0), (-1,-1), 8),
                            ("LEFTPADDING",   (0,0), (-1,-1), 0),
                            ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                            ("LINEAFTER",     (0,0), (0,-1),  1.2, _dot_color),
                            ("LEFTPADDING",   (1,0), (1,-1),  10),
                            ("VALIGN",        (0,0), (-1,-1), "TOP"),
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
                                    _d = '<br/>'.join(_lineas)
                                    _d_para = Paragraph(_d, s_dep)
                                else:
                                    _d = _fmt_val(_d_raw, campo=_c)
                                    _d_para = Paragraph(_d[:120], s_dep)
                                _a_para = Paragraph(_a[:70], s_antes)
                            else:
                                _a_para = Paragraph("—", s_antes)
                                _d_para = Paragraph(_fmt_val(str(_v), campo=_c)[:70], s_dep)
                            cam_rows.append([
                                Paragraph(_c, s_mono),
                                _a_para,
                                _d_para,
                            ])

                        if len(cam_rows) > 1:
                            _cw1, _cw2, _cw3 = 4.2*cm, 5.4*cm, 5.4*cm
                            cam_tbl = Table(cam_rows, colWidths=[_cw1, _cw2, _cw3])
                            cam_styles = [
                                ("BACKGROUND",    (0,0), (-1,0),  C_HDR_BG),
                                ("LINEBELOW",     (0,0), (-1,0),  0.5, C_LINE),
                                ("GRID",          (0,0), (-1,-1), 0.3, C_LINE),
                                ("TOPPADDING",    (0,0), (-1,-1), 4),
                                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
                                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                            ]
                            for _ri in range(1, len(cam_rows)):
                                cam_styles.append(("BACKGROUND", (1,_ri), (1,_ri), C_ANTES))
                                cam_styles.append(("BACKGROUND", (2,_ri), (2,_ri), C_DESPUES))
                            cam_tbl.setStyle(TableStyle(cam_styles))

                            wrap_tbl = Table(
                                [["", cam_tbl]],
                                colWidths=[2.0*cm, doc.width - 2.0*cm])
                            wrap_tbl.setStyle(TableStyle([
                                ("TOPPADDING",    (0,0), (-1,-1), 3),
                                ("BOTTOMPADDING", (0,0), (-1,-1), 10),
                                ("LEFTPADDING",   (0,0), (-1,-1), 0),
                                ("RIGHTPADDING",  (0,0), (-1,-1), 0),
                                ("LINEAFTER",     (0,0), (0,-1),  1.2, _dot_color),
                                ("LEFTPADDING",   (1,0), (1,-1),  10),
                                ("VALIGN",        (0,0), (-1,-1), "TOP"),
                            ]))
                            story.append(KeepTogether(wrap_tbl))

                story.append(Spacer(1, 2))

    doc.build(story, onFirstPage=_hf, onLaterPages=_hf)
    buf.seek(0)
    return buf.read()
