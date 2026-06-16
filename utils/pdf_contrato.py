"""
Generación de PDF de contrato y preparación de datos de cotización para PDF.
Extraído de app.py para la arquitectura modular.
"""
import io
import os
import re
from datetime import datetime, timedelta

import pandas as pd

from config.supabase import supabase_admin as _supa_admin
from utils.telefono import formatear_telefono
from utils.formato import formato_clp

# Re-export para que los views puedan importar generar_pdf_completo desde aquí
from generators.pdf_cotizacion import generar_pdf_completo  # noqa: F401


# ── CONVERSIÓN A PALABRAS ────────────────────────────────────────────────────

def num_a_palabras(n):
    """Convierte un número entero a su representación en palabras en español."""
    unidades = ['','uno','dos','tres','cuatro','cinco','seis','siete','ocho','nueve',
                'diez','once','doce','trece','catorce','quince','dieciséis','diecisiete',
                'dieciocho','diecinueve','veinte','veintiuno','veintidós','veintitrés',
                'veinticuatro','veinticinco','veintiséis','veintisiete','veintiocho','veintinueve']
    decenas = ['','diez','veinte','treinta','cuarenta','cincuenta','sesenta','setenta','ochenta','noventa']
    centenas = ['','ciento','doscientos','trescientos','cuatrocientos','quinientos',
                'seiscientos','setecientos','ochocientos','novecientos']
    if n == 0: return 'cero'
    if n < 0:  return 'menos ' + num_a_palabras(-n)
    res = ''
    if n >= 1_000_000:
        m = n // 1_000_000
        res += ('un millón' if m == 1 else num_a_palabras(m) + ' millones') + ' '
        n %= 1_000_000
    if n >= 1000:
        m = n // 1000
        res += ('mil' if m == 1 else num_a_palabras(m) + ' mil') + ' '
        n %= 1000
    if n >= 100:
        if n == 100: res += 'cien '
        else: res += centenas[n // 100] + ' '
        n %= 100
    if n >= 30:
        d, u = divmod(n, 10)
        res += decenas[d] + (' y ' + unidades[u] if u else '') + ' '
    elif n > 0:
        res += unidades[n] + ' '
    return res.strip()


def monto_a_palabras(monto):
    """Convierte monto a texto: 'X pesos'."""
    entero = int(round(monto))
    return num_a_palabras(entero) + ' pesos'


# ── CLÁUSULAS DE CONTRATO ────────────────────────────────────────────────────

def _obtener_clausulas_contrato(modelo_predefinido=None, supa_admin=None):
    """Retorna las cláusulas de la plantilla activa con _tipo_plantilla inyectado."""
    sa = supa_admin or _supa_admin

    def _inyectar_tipo(clausulas, tipo):
        if clausulas is None:
            return None
        result = dict(clausulas)
        result['_tipo_plantilla'] = tipo or 'A'
        return result

    try:
        if modelo_predefinido:
            _todas = sa.table("plantillas_contrato").select("*").eq("activa", True).execute()
            for _p in (_todas.data or []):
                _mods = _p.get("modelos") or []
                if isinstance(_mods, str):
                    try:
                        import json as _jm; _mods = _jm.loads(_mods)
                    except Exception: _mods = []
                if modelo_predefinido in _mods:
                    return _inyectar_tipo(_p.get("clausulas"), _p.get("tipo"))
        _res = sa.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).eq("tipo", "A").execute()
        if _res.data and _res.data[0].get("clausulas"):
            return _inyectar_tipo(_res.data[0]["clausulas"], _res.data[0].get("tipo"))
        _res2 = sa.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).execute()
        if _res2.data and _res2.data[0].get("clausulas"):
            return _inyectar_tipo(_res2.data[0]["clausulas"], _res2.data[0].get("tipo"))
    except Exception:
        pass
    return None


def _rep(texto, d):
    """Reemplaza marcadores {{VAR}} con datos reales del dict d."""
    fmt = lambda v: "${:,.0f}".format(v).replace(",", ".") if v else "$0"
    m = {
        "{{FECHA}}":               d.get("fecha_str", ""),
        "{{TRATAMIENTO}}":         d.get("cli_tratamiento", "Don"),
        "{{CLIENTE}}":             d.get("cli_nombre", ""),
        "{{RUT_CLIENTE}}":         d.get("cli_rut", ""),
        "{{DOMICILIO_CLIENTE}}":   d.get("cli_domicilio", ""),
        "{{COMUNA_CLIENTE}}":      d.get("cli_comuna", ""),
        "{{REGION_CLIENTE}}":      d.get("cli_region", ""),
        "{{DOMICILIO_INST}}":      d.get("inst_domicilio", ""),
        "{{COMUNA_INST}}":         d.get("inst_comuna", ""),
        "{{REGION_INST}}":         d.get("inst_region", ""),
        "{{EP}}":                  d.get("ep_numero", ""),
        "{{EP_NOMBRE}}":           d.get("ep_nombre", ""),
        "{{TOTAL}}":               fmt(d.get("precio_total", 0)),
        "{{TOTAL_PALABRAS}}":      monto_a_palabras(d.get("precio_total", 0)),
        "{{PAGO_50}}":             fmt(d.get("pago_50", 0)),
        "{{PAGO_50_PALABRAS}}":    monto_a_palabras(d.get("pago_50", 0)),
        "{{PAGO_25A}}":            fmt(d.get("pago_25a", 0)),
        "{{PAGO_25A_PALABRAS}}":   monto_a_palabras(d.get("pago_25a", 0)),
        "{{PAGO_25B}}":            fmt(d.get("pago_25b", 0)),
        "{{PAGO_25B_PALABRAS}}":   monto_a_palabras(d.get("pago_25b", 0)),
        "{{PLAZO}}":               str(d.get("plazo_dias", 45)),
    }
    for k, v in m.items():
        texto = texto.replace(k, str(v))
    return texto


# ── GENERADOR DE PDF DE CONTRATO ─────────────────────────────────────────────

def generar_pdf_contrato(datos, clausulas_externas=None):
    """
    Genera PDF del contrato a partir del dict `datos`.
    Campos esperados: fecha_str, tipo_cliente (natural/juridica),
    cli_nombre, cli_rut, cli_empresa, cli_rut_empresa, cli_domicilio,
    cli_comuna, cli_region, inst_domicilio, inst_comuna, inst_region,
    ep_numero, ep_nombre, precio_total, plazo_dias, pago_50, pago_25a, pago_25b.
    Retorna bytes del PDF.
    """
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    HRFlowable, Table, TableStyle, PageBreak)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

    buf = io.BytesIO()

    AZUL       = colors.HexColor('#0f3460')
    AZUL_LIGHT = colors.HexColor('#e8eef7')
    GRIS       = colors.HexColor('#64748b')
    NEGRO      = colors.HexColor('#0f172a')

    def _build_header_footer(canvas, doc):
        canvas.saveState()
        pw = doc.pagesize[0]
        if os.path.exists("logo.png"):
            from reportlab.lib.utils import ImageReader
            _img = ImageReader("logo.png")
            _iw, _ih = _img.getSize()
            _aspect = _ih / float(_iw)
            _lw = 4.5 * cm
            _lh = _lw * _aspect
            canvas.drawImage(_img,
                             x=(pw - _lw) / 2,
                             y=doc.pagesize[1] - doc.topMargin + 0.3*cm,
                             width=_lw, height=_lh,
                             preserveAspectRatio=True, mask='auto')
        canvas.setStrokeColor(AZUL)
        canvas.setLineWidth(1.2)
        _ly = doc.pagesize[1] - doc.topMargin + 0.1*cm
        canvas.line(doc.leftMargin, _ly, pw - doc.rightMargin, _ly)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(GRIS)
        _fy = doc.bottomMargin - 0.5*cm
        canvas.drawCentredString(pw/2, _fy,
            f"Inversiones Container House SpA  ·  RUT 78.268.851-0  ·  Página {doc.page}")
        canvas.setStrokeColor(GRIS)
        canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, _fy + 0.35*cm, pw - doc.rightMargin, _fy + 0.35*cm)
        canvas.restoreState()

    doc_pdf = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=3*cm, rightMargin=3*cm,
        topMargin=3.8*cm, bottomMargin=2.2*cm,
        title=f"Contrato {datos.get('ep_numero','')}"
    )

    base = getSampleStyleSheet()
    normal = ParagraphStyle('cNormal', parent=base['Normal'],
                            fontName='Times-Roman', fontSize=12.5,
                            leading=19, spaceAfter=6,
                            alignment=TA_JUSTIFY, firstLineIndent=0)
    bold   = ParagraphStyle('cBold', parent=normal, fontName='Times-Bold')
    titulo = ParagraphStyle('cTitulo', parent=base['Normal'],
                            fontName='Times-Bold', fontSize=15,
                            leading=20, spaceAfter=2, spaceBefore=6,
                            alignment=TA_CENTER, textColor=AZUL)
    subtit = ParagraphStyle('cSubtit', parent=base['Normal'],
                            fontName='Times-Bold', fontSize=11,
                            leading=16, spaceAfter=8,
                            alignment=TA_CENTER, textColor=AZUL)
    seccion = ParagraphStyle('cSeccion', parent=base['Normal'],
                             fontName='Helvetica-Bold', fontSize=9.5,
                             leading=13, spaceBefore=14, spaceAfter=5,
                             textColor=colors.white, backColor=AZUL,
                             leftIndent=-0.3*cm, rightIndent=-0.3*cm,
                             borderPadding=(4, 8, 4, 8))
    firma      = ParagraphStyle('cFirma', parent=normal,
                                fontName='Times-Roman', fontSize=12.5,
                                leading=19, alignment=TA_CENTER)
    firma_bold = ParagraphStyle('cFirmaBold', parent=firma, fontName='Times-Bold')

    def HR():
        return HRFlowable(width="100%", thickness=0.6,
                          color=AZUL_LIGHT, spaceAfter=6, spaceBefore=2)
    def SP(h=6): return Spacer(1, h)

    d = datos
    precio  = d['precio_total']
    p50     = d['pago_50']
    p25a    = d['pago_25a']
    p25b    = d['pago_25b']
    precio_p = monto_a_palabras(precio)
    p50_p    = monto_a_palabras(p50)
    p25a_p   = monto_a_palabras(p25a)
    p25b_p   = monto_a_palabras(p25b)
    fmt      = lambda v: "${:,.0f}".format(v).replace(",", ".")

    if d['tipo_cliente'] == 'natural':
        tratamento = d.get('cli_tratamiento', 'Don')
        cli_bloque = (
            f"{tratamento} <b>{d['cli_nombre']}</b>, cédula nacional de identidad "
            f"<b>N° {d['cli_rut']}</b>, con domicilio en <b>{d['cli_domicilio']}</b>, "
            f"comuna de <b>{d['cli_comuna']}</b>, Región {d['cli_region']}, "
            f"quien en adelante se denominará \"el Cliente\"."
        )
    else:
        tratamento = d.get('cli_tratamiento', 'Don')
        cli_bloque = (
            f"{tratamento} <b>{d['cli_nombre']}</b>, cédula nacional de identidad "
            f"<b>N° {d['cli_rut']}</b>, en representación de "
            f"<b>{d['cli_empresa']}</b>, Rol Único Tributario "
            f"<b>N° {d['cli_rut_empresa']}</b>, con domicilio en "
            f"<b>{d['cli_domicilio']}</b>, comuna de <b>{d['cli_comuna']}</b>, "
            f"Región {d['cli_region']}, quien en adelante se denominará \"el Cliente\"."
        )

    _plt_cls = clausulas_externas if clausulas_externas else _obtener_clausulas_contrato()

    _ORIG = {
        "intro":        "En Santiago de Chile, a <b>{{FECHA}}</b>, comparecen:",
        "comparecencia_cliente": "{{TRATAMIENTO}} <b>{{CLIENTE}}</b>, cédula nacional de identidad N° <b>{{RUT_CLIENTE}}</b>, con domicilio en <b>{{DOMICILIO_CLIENTE}}</b>, comuna de <b>{{COMUNA_CLIENTE}}</b>, Región {{REGION_CLIENTE}}, quien en adelante se denominará \"el Cliente\".\n\nSe deja expresa constancia que la dirección de instalación del proyecto será <b>{{DOMICILIO_INST}}</b>, comuna de <b>{{COMUNA_INST}}</b>, Región <b>{{REGION_INST}}</b>.\n\nLas partes declaran ser mayores de edad, con plena capacidad legal para contratar, y acuerdan celebrar el presente <b>Contrato de Fabricación y Venta de Vivienda Tipo Container</b>, el cual se regirá por las cláusulas que se indican a continuación.",
        "instalacion":  f"Se deja expresa constancia que la dirección de instalación del proyecto será <b>{d['inst_domicilio']}</b>, comuna de <b>{d['inst_comuna']}</b>, Región {d['inst_region']}.",
        "objeto":       "El Cliente encarga al Proveedor la <b>fabricación y venta</b> del Proyecto individualizado precedentemente, conforme a los <b>planos entregados por el Cliente</b>, a las <b>especificaciones técnicas</b>, y al <b>presupuesto detallado contenido en el Anexo N°2</b>, documentos que el Cliente declara conocer, aceptar y que forman parte integrante e inseparable del presente contrato.",
        "alcance":      f"El Proveedor declara contar con la experiencia, conocimientos técnicos, personal calificado, herramientas e infraestructura necesarias para la correcta ejecución del Proyecto, comprometiéndose a:\na) Fabricar el módulo conforme a la normativa vigente aplicable.\nb) Respetar las especificaciones técnicas y alcances definidos en los Anexos.\nc) Ejecutar los trabajos con estándares de calidad y seguridad.\nCualquier trabajo, modificación o prestación no contemplada expresamente en los Anexos será considerada <b>obra adicional</b>, debiendo ser cotizada y aprobada por escrito por ambas partes.",
        "visitas":      "El Cliente podrá realizar visitas de seguimiento a las instalaciones del Proveedor ubicadas en <b>Portezuelo, parcela 3, Colina, Región Metropolitana</b>, previa coordinación con al menos <b>48 horas hábiles de anticipación</b>, con el único objeto de verificar el avance del Proyecto, quedando expresamente prohibida cualquier interferencia en los procesos productivos o instrucciones al personal del Proveedor.",
        "precio":       f"El precio total del Proyecto asciende a la suma de <b>{fmt(precio)}</b> ({precio_p}), IVA incluido.",
        "forma_pago":   f"El precio será pagado por el Cliente al Proveedor en las siguientes etapas:\na) <b>50% inicial</b>: <b>{fmt(d.get('pago_50',0))}</b> ({monto_a_palabras(d.get('pago_50',0))}), correspondiente a la asignación del contenedor y ejecución de obra gruesa.\nb) <b>25% intermedio</b>: <b>{fmt(d.get('pago_25a',0))}</b> ({monto_a_palabras(d.get('pago_25a',0))}), una vez finalizada la obra gruesa.\nc) <b>25% final</b>: <b>{fmt(d.get('pago_25b',0))}</b> ({monto_a_palabras(d.get('pago_25b',0))}), luego de la preentrega del Proyecto y el mismo día del despacho del módulo.\nEl Proveedor emitirá la factura correspondiente al día hábil siguiente de recibido cada pago, bajo modalidad de <b>pago al contado</b>.",
        "plazo":        f"El plazo máximo de fabricación y entrega será de <b>{d.get('plazo_dias',45)} días hábiles administrativos</b>, contados desde el día hábil siguiente a aquel en que los fondos del anticipo se encuentren efectivamente liberados.\nEl Cliente se obliga a contar con <b>radier y/o apoyos estructurales ejecutados, nivelados y aptos</b> para la instalación dentro de un plazo máximo de <b>30 días hábiles</b> desde la firma del contrato. Cualquier atraso en estas condiciones suspenderá automáticamente los plazos de entrega.",
        "inicio":       "La fabricación del Proyecto se iniciará <b>única y exclusivamente</b> una vez recibido y efectivamente abonado el pago inicial del <b>50% del valor total del contrato</b>.",
        "penalidad":    "En caso de atraso imputable exclusivamente al Proveedor en los plazos establecidos para la fabricación o entrega del Proyecto, éste pagará al Cliente, a título de indemnización única y total, una suma equivalente al <b>1% del valor neto correspondiente al último 25% del Proyecto por cada 7 días hábiles de atraso</b>, con un <b>tope máximo del 10% del valor neto de dicho monto</b>.\nNo se considerarán atrasos imputables al Proveedor aquellos derivados de caso fortuito, fuerza mayor, condiciones climáticas adversas, retrasos de proveedores externos, o cualquier situación no atribuible directamente al Proveedor.\nAsimismo, en caso de que el atraso sea imputable al Cliente, ya sea por retraso en los pagos comprometidos, falta de entrega de antecedentes necesarios, impedimentos de acceso al lugar de instalación, o cualquier otra circunstancia bajo su responsabilidad, los plazos del Proyecto se extenderán automáticamente por el mismo período de tiempo que dure dicho atraso, sin que ello genere responsabilidad ni penalidad alguna para el Proveedor.",
        "bodegaje":     "Una vez notificada la finalización del Proyecto, el Cliente dispondrá de un plazo máximo de <b>10 días hábiles</b> para coordinar el retiro o despacho del módulo. Vencido dicho plazo, el Proveedor quedará facultado para cobrar un <b>cargo por bodegaje equivalente al 1% del valor neto del Proyecto por cada 7 días corridos</b>, hasta el retiro efectivo.",
        "garantia":     "El Proveedor otorga una garantía de <b>6 meses</b> contados desde la entrega del módulo, limitada exclusivamente a <b>defectos de fabricación o construcción imputables al proceso productivo</b>.\nQuedan expresamente excluidos de garantía los daños derivados de:\n• Mal uso o uso distinto al previsto\n• Modificaciones no autorizadas\n• Transporte realizado por terceros\n• Vandalismo\n• Fenómenos naturales\n• Falta de mantención adecuada",
        "terminacion":  "El presente contrato podrá terminarse anticipadamente por:\na) Incumplimiento grave de cualquiera de las partes.\nb) Mutuo acuerdo por escrito.\nc) No pago oportuno de cualquiera de las etapas de pago.\nEn caso de término imputable al Cliente, los montos pagados <b>no serán reembolsables</b>, salvo acuerdo distinto por escrito.",
        "jurisdiccion": "Para todos los efectos legales derivados del presente contrato, las partes fijan su domicilio en la <b>ciudad de Santiago</b>, y se someten a la competencia de sus <b>Tribunales Ordinarios de Justicia</b>.",
        "firma":        "El presente contrato se firma en <b>dos ejemplares de igual tenor y fecha</b>, quedando uno en poder de cada parte.",
    }

    def _p(clave, fallback=None):
        def _strip(t): return re.sub(r'<[^>]+>', '', t).strip()
        if _plt_cls and clave in _plt_cls and _plt_cls[clave]:
            _txt_sup = _plt_cls[clave]
            _txt_orig_plain = _strip(_ORIG.get(clave, ""))
            if _txt_sup.strip() == _txt_orig_plain:
                return _rep(_ORIG.get(clave, fallback or ""), d)
            return _rep(_txt_sup, d)
        return _rep(_ORIG.get(clave, fallback or ""), d)

    story = []
    story += [
        Paragraph("CONTRATO DE FABRICACIÓN Y VENTA", titulo),
        Paragraph("VIVIENDA TIPO CONTAINER", subtit),
        SP(4),
        HRFlowable(width="100%", thickness=1.5, color=AZUL, spaceAfter=10, spaceBefore=0),
        Paragraph(_p("intro", f"En Santiago de Chile, a <b>{d['fecha_str']}</b>, comparecen:"), normal),
        SP(4),
    ]

    story += [
        Paragraph("I. COMPARECENCIA", seccion),
        Paragraph("1. EL PROVEEDOR", bold),
        Paragraph(
            "Don <b>Alan Mauricio Gatica Concha</b>, cédula nacional de identidad "
            "N° <b>13.668.157-5</b>, en representación de "
            "<b>Inversiones Container House SpA</b>, Rol Único Tributario "
            "N° <b>78.268.851-0</b>, ambos con domicilio para estos efectos en "
            "Villasana N° 2039, Departamento 51, Torre D, comuna de Quinta Normal, "
            "Región Metropolitana, quien en adelante se denominará "
            "indistintamente \"el Proveedor\".", normal),
        SP(6),
        Paragraph("2. EL CLIENTE", bold),
        Paragraph(_p("comparecencia_cliente", cli_bloque), normal),
        HR(),
    ]

    story += [
        Paragraph("II. DEFINICIONES", seccion),
        Paragraph("Para efectos del presente contrato, se entenderá por:", normal),
        Paragraph(
            f"a) <b>Proyecto</b>: La vivienda tipo container identificada como "
            f"<b>Proyecto N° {d['ep_numero']} – \"{d['ep_nombre']}\"</b>.", normal),
        Paragraph(
            "b) <b>Anexos</b>: Los documentos técnicos y comerciales que forman parte "
            "integrante del presente contrato, en especial Anexo N°1 (Especificaciones "
            "Técnicas) y Anexo N°2 (Presupuesto Detallado).", normal),
        Paragraph(
            "c) <b>Preentrega</b>: Instancia de revisión visual del módulo previo a su "
            "despacho desde las instalaciones del Proveedor.", normal),
        HR(),
    ]

    story += [
        Paragraph("III. OBJETO DEL CONTRATO", seccion),
        Paragraph(_p("objeto", "El Cliente encarga al Proveedor la fabricación y venta del Proyecto individualizado precedentemente."), normal),
        HR(),
    ]

    story += [Paragraph("IV. ALCANCE TÉCNICO Y EJECUCIÓN", seccion)]
    for _l in _p("alcance", None).split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    story += [
        Paragraph("V. VISITAS Y SEGUIMIENTO DEL PROYECTO", seccion),
        Paragraph(_p("visitas", None), normal),
        HR(),
    ]

    story += [
        Paragraph("VI. PRECIO", seccion),
        Paragraph(_p("precio", f"El precio total del Proyecto asciende a la suma de <b>{fmt(precio)}</b> ({precio_p}), IVA incluido."), normal),
        HR(),
    ]

    story += [Paragraph("VII. FORMA Y ETAPAS DE PAGO", seccion)]
    for _l in _p("forma_pago", None).split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    story += [
        Paragraph("VIII. INICIO DE FABRICACIÓN", seccion),
        Paragraph(_p("inicio", None), normal),
        HR(),
    ]

    story += [
        Paragraph("IX. MEDIOS DE PAGO", seccion),
        Paragraph(
            "Los pagos deberán efectuarse mediante <b>transferencia electrónica, "
            "cheque o vale vista</b>, a la siguiente cuenta bancaria:", normal),
    ]
    datos_banco = [
        ["Razón Social:", "Inversiones Container House SpA"],
        ["RUT:",          "78.268.851-0"],
        ["Banco:",        "Banco Itaú"],
        ["Cuenta Corriente:", "N° 230771767"],
        ["Correo de confirmación:", "jperez@espaciocontainerhouse.cl"],
    ]
    tbl = Table(datos_banco, colWidths=[4.5*cm, 11*cm])
    tbl.setStyle(TableStyle([
        ('FONTNAME',  (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME',  (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE',  (0,0), (-1,-1), 10),
        ('LEADING',   (0,0), (-1,-1), 14),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#f8fafc'), colors.white]),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
    ]))
    story += [tbl, SP(6),
        Paragraph(
            "Cada pago deberá ser informado por el Cliente mediante correo electrónico, "
            "adjuntando el comprobante respectivo.", normal),
        HR(),
    ]

    story += [Paragraph("X. PLAZO DE FABRICACIÓN Y ENTREGA", seccion)]
    for _l in _p("plazo", None).split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    story += [Paragraph("XI. PENALIDAD POR ATRASO", seccion)]
    for _l in _p("penalidad", None).split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    _tipo_plt_pdf = (_plt_cls.get("_tipo_plantilla") if _plt_cls else None) or 'A'

    def _romano(n):
        _vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
                 (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
        r = ''
        for v, s in _vals:
            while n >= v:
                r += s; n -= v
        return r

    _clausulas_vars = [
        ('bodegaje',          'RETIRO, DESPACHO Y BODEGAJE',                                   False, 'hr',       ('A', 'B')),
        ('garantia',          'GARANTÍA',                                                        True,  'hr',       ('A', 'B', 'E')),
        ('terminacion',       'TERMINACIÓN ANTICIPADA',                                          True,  'hr',       ('A', 'B', 'E')),
        ('jurisdiccion',      'DOMICILIO Y JURISDICCIÓN',                                        False, 'pagebreak',('A', 'B', 'E')),
        ('suministro_energia','SUMINISTRO DE ENERGÍA ELÉCTRICA Y USO DE HERRAMIENTAS',          True,  'sp',       ('B', 'E')),
        ('firma',             'FIRMA',                                                           False, 'sp60',     ('A', 'B', 'E')),
    ]

    _num_clausula = 11
    for _clave, _titulo, _multi, _sep, _tipos in _clausulas_vars:
        if _tipo_plt_pdf not in _tipos:
            continue
        _num_clausula += 1
        _num_str = _romano(_num_clausula)

        if _clave == 'suministro_energia':
            _txt_sum = (_plt_cls or {}).get("suministro_energia", "")
            if not _txt_sum:
                continue
            _txt_sum = re.sub(
                r'^X{0,3}(?:IX|IV|V?I{0,3})\..*?Y USO DE HERRAMIENTAS\s*',
                '', _txt_sum.strip(), flags=re.IGNORECASE | re.DOTALL
            ).strip()
            story += [
                Paragraph(f"{_num_str}. {_titulo}", seccion),
                Paragraph(_rep(_txt_sum, d), normal),
                SP(6),
            ]
        elif _clave == 'firma':
            story += [
                Paragraph(f"{_num_str}. {_titulo}", seccion),
                Paragraph(_p("firma", None), normal),
                SP(60),
            ]
        elif _multi:
            story += [Paragraph(f"{_num_str}. {_titulo}", seccion)]
            for _l in _p(_clave, None).split("\n"):
                if _l.strip(): story.append(Paragraph(_l.strip(), normal))
            if _sep == 'hr': story += [HR()]
        else:
            story += [
                Paragraph(f"{_num_str}. {_titulo}", seccion),
                Paragraph(_p(_clave, None), normal),
            ]
            if _sep == 'hr': story += [HR()]
            elif _sep == 'pagebreak': story += [PageBreak()]

    if d['tipo_cliente'] == 'natural':
        cli_firma_nombre = d['cli_nombre']
    else:
        cli_firma_nombre = d['cli_nombre']

    firma_data = [[
        Paragraph("EL PROVEEDOR", firma_bold),
        Paragraph("EL CLIENTE", firma_bold),
    ],[
        Paragraph("_" * 34, firma),
        Paragraph("_" * 34, firma),
    ],[
        Paragraph("Alan Mauricio Gatica Concha", firma_bold),
        Paragraph(cli_firma_nombre, firma_bold),
    ],[
        Paragraph("RUT: 13.668.157-5", firma),
        Paragraph(f"RUT: {d['cli_rut']}", firma),
    ],[
        Paragraph("Inversiones Container House SpA", firma),
        Paragraph(d.get('cli_empresa', '') or '', firma),
    ]]
    firma_tbl = Table(firma_data, colWidths=[8*cm, 8*cm])
    firma_tbl.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(firma_tbl)

    doc_pdf.build(story,
                  onFirstPage=_build_header_footer,
                  onLaterPages=_build_header_footer)
    buf.seek(0)
    return buf.read()


# ── PREPARACIÓN DE DATOS PARA PDF DE PRESUPUESTO ─────────────────────────────

def preparar_pdf_data(cotizacion):
    """
    Prepara datos de una cotización para generar PDF de presupuesto.
    Retorna: (carrito_df, subtotal, iva, total, datos_cliente, datos_asesor,
              fecha_inicio, fecha_termino, dias_validez, margen)
    """
    carrito_df_t = pd.DataFrame(cotizacion['productos'])
    if not carrito_df_t.empty and 'Categoria' in carrito_df_t.columns:
        carrito_df_t = carrito_df_t.sort_values(['Categoria', 'Item'], ignore_index=True)

    margen_c = cotizacion.get('config_margen', 0)
    if margen_c > 0:
        carrito_df_p = carrito_df_t.copy()
        carrito_df_p["Precio Unitario"] = carrito_df_p["Precio Unitario"].apply(
            lambda x: x * (1 + margen_c / 100)
        )
        carrito_df_p["Subtotal"] = carrito_df_p["Cantidad"] * carrito_df_p["Precio Unitario"]
    else:
        carrito_df_p = carrito_df_t.copy()

    subtotal_p = carrito_df_p["Subtotal"].sum()
    iva_p      = subtotal_p * 0.19
    total_p    = subtotal_p + iva_p

    dc = {
        "Nombre":            cotizacion.get('cliente_nombre', ''),
        "RUT":               cotizacion.get('cliente_rut', ''),
        "Correo":            cotizacion.get('cliente_email', ''),
        "Teléfono":          formatear_telefono(cotizacion.get('cliente_telefono', '')),
        "Dirección":         cotizacion.get('cliente_direccion', ''),
        "ComunaCliente":     cotizacion.get('cliente_comuna', ''),
        "RegionCliente":     cotizacion.get('cliente_region', ''),
        "DireccionProyecto": cotizacion.get('proyecto_direccion', ''),
        "ComunaProyecto":    cotizacion.get('proyecto_comuna', ''),
        "RegionProyecto":    cotizacion.get('proyecto_region', ''),
        "TipoCliente":       cotizacion.get('cliente_tipo', 'natural'),
        "EmpresaCliente":    cotizacion.get('cliente_empresa', ''),
        "RutEmpresa":        cotizacion.get('cliente_rut_empresa', ''),
        "Observaciones":     cotizacion.get('proyecto_observaciones', ''),
    }
    da = {
        "Nombre Ejecutivo":   cotizacion.get('asesor_nombre', ''),
        "Correo Ejecutivo":   cotizacion.get('asesor_email', ''),
        "Teléfono Ejecutivo": formatear_telefono(cotizacion.get('asesor_telefono', '')),
    }

    _fmt = '%Y-%m-%d'
    fi = datetime.strptime(
        cotizacion.get('proyecto_fecha_inicio', datetime.now().strftime(_fmt)), _fmt
    ).date()
    ft = datetime.strptime(
        cotizacion.get('proyecto_fecha_termino',
                       (datetime.now() + timedelta(days=15)).strftime(_fmt)), _fmt
    ).date()
    dv = cotizacion.get('proyecto_dias_validez', 15)

    return carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c
