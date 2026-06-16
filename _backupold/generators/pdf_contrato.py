"""
Generador de PDF de contrato de fabricacion y venta.
Incluye carga de clausulas personalizadas desde Supabase (plantillas_contrato).
"""
import io
import os as _os_c
import re as _re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                HRFlowable, Table, TableStyle, PageBreak)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

from generators.word_contrato import monto_a_palabras
from config.supabase import supabase_admin


def _obtener_clausulas_contrato(modelo_predefinido=None):
    """Retorna las clausulas de la plantilla activa. Inyecta _tipo_plantilla."""
    def _inyectar_tipo(clausulas, tipo):
        if clausulas is None:
            return None
        result = dict(clausulas)
        result['_tipo_plantilla'] = tipo or 'A'
        return result
    try:
        if modelo_predefinido:
            todas = supabase_admin.table("plantillas_contrato").select("*").eq("activa", True).execute()
            for p in (todas.data or []):
                mods = p.get("modelos") or []
                if isinstance(mods, str):
                    try:
                        import json as _j; mods = _j.loads(mods)
                    except Exception:
                        mods = []
                if modelo_predefinido in mods:
                    return _inyectar_tipo(p.get("clausulas"), p.get("tipo"))
        res = supabase_admin.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).eq("tipo", "A").execute()
        if res.data and res.data[0].get("clausulas"):
            return _inyectar_tipo(res.data[0]["clausulas"], res.data[0].get("tipo"))
        res2 = supabase_admin.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).execute()
        if res2.data and res2.data[0].get("clausulas"):
            return _inyectar_tipo(res2.data[0]["clausulas"], res2.data[0].get("tipo"))
    except Exception:
        pass
    return None


def _rep(texto: str, d: dict) -> str:
    """Reemplaza marcadores con datos reales."""
    fmt = lambda v: "${:,.0f}".format(v).replace(",", ".") if v else "$0"
    m = {
        "{{FECHA}}":           d.get("fecha_str", ""),
        "{{TRATAMIENTO}}":     d.get("cli_tratamiento", "Don"),
        "{{CLIENTE}}":         d.get("cli_nombre", ""),
        "{{RUT_CLIENTE}}":     d.get("cli_rut", ""),
        "{{DOMICILIO_CLIENTE}}": d.get("cli_domicilio", ""),
        "{{COMUNA_CLIENTE}}":  d.get("cli_comuna", ""),
        "{{REGION_CLIENTE}}":  d.get("cli_region", ""),
        "{{DOMICILIO_INST}}":  d.get("inst_domicilio", ""),
        "{{COMUNA_INST}}":     d.get("inst_comuna", ""),
        "{{REGION_INST}}":     d.get("inst_region", ""),
        "{{EP}}":              d.get("ep_numero", ""),
        "{{EP_NOMBRE}}":       d.get("ep_nombre", ""),
        "{{TOTAL}}":           fmt(d.get("precio_total", 0)),
        "{{TOTAL_PALABRAS}}":  monto_a_palabras(d.get("precio_total", 0)),
        "{{PAGO_50}}":         fmt(d.get("pago_50", 0)),
        "{{PAGO_50_PALABRAS}}": monto_a_palabras(d.get("pago_50", 0)),
        "{{PAGO_25A}}":        fmt(d.get("pago_25a", 0)),
        "{{PAGO_25A_PALABRAS}}": monto_a_palabras(d.get("pago_25a", 0)),
        "{{PAGO_25B}}":        fmt(d.get("pago_25b", 0)),
        "{{PAGO_25B_PALABRAS}}": monto_a_palabras(d.get("pago_25b", 0)),
        "{{PLAZO}}":           str(d.get("plazo_dias", 45)),
    }
    for k, v in m.items():
        texto = texto.replace(k, str(v))
    return texto


def generar_pdf_contrato(datos: dict, clausulas_externas=None) -> bytes:
    """Genera PDF del contrato a partir del dict datos."""
    buf = io.BytesIO()

    AZUL       = colors.HexColor('#0f3460')
    AZUL_LIGHT = colors.HexColor('#e8eef7')
    GRIS       = colors.HexColor('#64748b')

    def _build_header_footer(canvas, doc):
        canvas.saveState()
        pw = doc.pagesize[0]
        if _os_c.path.exists("logo.png"):
            from reportlab.lib.utils import ImageReader
            img = ImageReader("logo.png")
            iw, ih = img.getSize()
            lw = 4.5*cm; lh = lw * (ih / float(iw))
            canvas.drawImage(img, x=(pw-lw)/2,
                             y=doc.pagesize[1]-doc.topMargin+0.3*cm,
                             width=lw, height=lh,
                             preserveAspectRatio=True, mask='auto')
        canvas.setStrokeColor(AZUL); canvas.setLineWidth(1.2)
        canvas.line(doc.leftMargin, doc.pagesize[1]-doc.topMargin+0.1*cm,
                    pw-doc.rightMargin, doc.pagesize[1]-doc.topMargin+0.1*cm)
        canvas.setFont('Helvetica', 8); canvas.setFillColor(GRIS)
        canvas.drawCentredString(pw/2, doc.bottomMargin-0.5*cm,
            f"Inversiones Container House SpA  ·  RUT 78.268.851-0  ·  Página {doc.page}")
        canvas.setStrokeColor(GRIS); canvas.setLineWidth(0.4)
        canvas.line(doc.leftMargin, doc.bottomMargin-0.15*cm,
                    pw-doc.rightMargin, doc.bottomMargin-0.15*cm)
        canvas.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=3*cm, rightMargin=3*cm,
                            topMargin=3.8*cm, bottomMargin=2.2*cm,
                            title=f"Contrato {datos.get('ep_numero','')}")

    base = getSampleStyleSheet()
    normal  = ParagraphStyle('cNormal', parent=base['Normal'], fontName='Times-Roman',
                              fontSize=12.5, leading=19, spaceAfter=6, alignment=TA_JUSTIFY)
    bold    = ParagraphStyle('cBold', parent=normal, fontName='Times-Bold')
    titulo  = ParagraphStyle('cTitulo', parent=base['Normal'], fontName='Times-Bold',
                              fontSize=15, leading=20, spaceAfter=2, spaceBefore=6,
                              alignment=TA_CENTER, textColor=AZUL)
    subtit  = ParagraphStyle('cSubtit', parent=base['Normal'], fontName='Times-Bold',
                              fontSize=11, leading=16, spaceAfter=8,
                              alignment=TA_CENTER, textColor=AZUL)
    seccion = ParagraphStyle('cSeccion', parent=base['Normal'], fontName='Helvetica-Bold',
                              fontSize=9.5, leading=13, spaceBefore=14, spaceAfter=5,
                              textColor=colors.white, backColor=AZUL,
                              leftIndent=-0.3*cm, rightIndent=-0.3*cm,
                              borderPadding=(4, 8, 4, 8))
    firma_s  = ParagraphStyle('cFirma', parent=normal, fontName='Times-Roman',
                               fontSize=12.5, leading=19, alignment=TA_CENTER)
    firma_b  = ParagraphStyle('cFirmaBold', parent=firma_s, fontName='Times-Bold')

    def HR(): return HRFlowable(width="100%", thickness=0.6, color=AZUL_LIGHT, spaceAfter=6, spaceBefore=2)
    def SP(h=6): return Spacer(1, h)

    d = datos
    precio = d['precio_total']
    fmt = lambda v: "${:,.0f}".format(v).replace(",", ".")

    if d['tipo_cliente'] == 'natural':
        tratamiento = d.get('cli_tratamiento', 'Don')
        cli_bloque = (
            f"{tratamiento} <b>{d['cli_nombre']}</b>, cédula nacional de identidad "
            f"<b>N° {d['cli_rut']}</b>, con domicilio en <b>{d['cli_domicilio']}</b>, "
            f"comuna de <b>{d['cli_comuna']}</b>, Región {d['cli_region']}, "
            f"quien en adelante se denominará \"el Cliente\"."
        )
    else:
        tratamiento = d.get('cli_tratamiento', 'Don')
        cli_bloque = (
            f"{tratamiento} <b>{d['cli_nombre']}</b>, cédula nacional de identidad "
            f"<b>N° {d['cli_rut']}</b>, en representación de "
            f"<b>{d.get('cli_empresa','')}</b>, Rol Único Tributario "
            f"<b>N° {d.get('cli_rut_empresa','')}</b>, con domicilio en "
            f"<b>{d['cli_domicilio']}</b>, comuna de <b>{d['cli_comuna']}</b>, "
            f"Región {d['cli_region']}, quien en adelante se denominará \"el Cliente\"."
        )

    plt_cls = clausulas_externas if clausulas_externas else _obtener_clausulas_contrato()

    _ORIG = {
        "intro": "En Santiago de Chile, a <b>{{FECHA}}</b>, comparecen:",
        "comparecencia_cliente": "{{TRATAMIENTO}} <b>{{CLIENTE}}</b>, cédula nacional de identidad N° <b>{{RUT_CLIENTE}}</b>, con domicilio en <b>{{DOMICILIO_CLIENTE}}</b>, comuna de <b>{{COMUNA_CLIENTE}}</b>, Región {{REGION_CLIENTE}}, quien en adelante se denominará \"el Cliente\".\n\nSe deja expresa constancia que la dirección de instalación del proyecto será <b>{{DOMICILIO_INST}}</b>, comuna de <b>{{COMUNA_INST}}</b>, Región <b>{{REGION_INST}}</b>.\n\nLas partes declaran ser mayores de edad, con plena capacidad legal para contratar, y acuerdan celebrar el presente <b>Contrato de Fabricación y Venta de Vivienda Tipo Container</b>, el cual se regirá por las cláusulas que se indican a continuación.",
        "objeto": "El Cliente encarga al Proveedor la <b>fabricación y venta</b> del Proyecto individualizado precedentemente, conforme a los <b>planos entregados por el Cliente</b>, a las <b>especificaciones técnicas</b>, y al <b>presupuesto detallado contenido en el Anexo N°2</b>, documentos que el Cliente declara conocer, aceptar y que forman parte integrante e inseparable del presente contrato.",
        "alcance": "El Proveedor declara contar con la experiencia, conocimientos técnicos, personal calificado, herramientas e infraestructura necesarias para la correcta ejecución del Proyecto, comprometiéndose a:\na) Fabricar el módulo conforme a la normativa vigente aplicable.\nb) Respetar las especificaciones técnicas y alcances definidos en los Anexos.\nc) Ejecutar los trabajos con estándares de calidad y seguridad.\nCualquier trabajo, modificación o prestación no contemplada expresamente en los Anexos será considerada <b>obra adicional</b>, debiendo ser cotizada y aprobada por escrito por ambas partes.",
        "visitas": "El Cliente podrá realizar visitas de seguimiento a las instalaciones del Proveedor ubicadas en <b>Portezuelo, parcela 3, Colina, Región Metropolitana</b>, previa coordinación con al menos <b>48 horas hábiles de anticipación</b>, con el único objeto de verificar el avance del Proyecto, quedando expresamente prohibida cualquier interferencia en los procesos productivos o instrucciones al personal del Proveedor.",
        "precio": f"El precio total del Proyecto asciende a la suma de <b>{fmt(precio)}</b> ({monto_a_palabras(precio)}), IVA incluido.",
        "forma_pago": f"El precio será pagado por el Cliente al Proveedor en las siguientes etapas:\na) <b>50% inicial</b>: <b>{fmt(d.get('pago_50',0))}</b> ({monto_a_palabras(d.get('pago_50',0))}), correspondiente a la asignación del contenedor y ejecución de obra gruesa.\nb) <b>25% intermedio</b>: <b>{fmt(d.get('pago_25a',0))}</b> ({monto_a_palabras(d.get('pago_25a',0))}), una vez finalizada la obra gruesa.\nc) <b>25% final</b>: <b>{fmt(d.get('pago_25b',0))}</b> ({monto_a_palabras(d.get('pago_25b',0))}), luego de la preentrega del Proyecto y el mismo día del despacho del módulo.\nEl Proveedor emitirá la factura correspondiente al día hábil siguiente de recibido cada pago, bajo modalidad de <b>pago al contado</b>.",
        "plazo": f"El plazo máximo de fabricación y entrega será de <b>{d.get('plazo_dias',45)} días hábiles administrativos</b>, contados desde el día hábil siguiente a aquel en que los fondos del anticipo se encuentren efectivamente liberados.\nEl Cliente se obliga a contar con <b>radier y/o apoyos estructurales ejecutados, nivelados y aptos</b> para la instalación dentro de un plazo máximo de <b>30 días hábiles</b> desde la firma del contrato. Cualquier atraso en estas condiciones suspenderá automáticamente los plazos de entrega.",
        "inicio": "La fabricación del Proyecto se iniciará <b>única y exclusivamente</b> una vez recibido y efectivamente abonado el pago inicial del <b>50% del valor total del contrato</b>.",
        "penalidad": "En caso de atraso imputable exclusivamente al Proveedor en los plazos establecidos para la fabricación o entrega del Proyecto, éste pagará al Cliente, a título de indemnización única y total, una suma equivalente al <b>1% del valor neto correspondiente al último 25% del Proyecto por cada 7 días hábiles de atraso</b>, con un <b>tope máximo del 10% del valor neto de dicho monto</b>.\nNo se considerarán atrasos imputables al Proveedor aquellos derivados de caso fortuito, fuerza mayor, condiciones climáticas adversas, retrasos de proveedores externos, o cualquier situación no atribuible directamente al Proveedor.\nAsimismo, en caso de que el atraso sea imputable al Cliente, los plazos del Proyecto se extenderán automáticamente por el mismo período de tiempo que dure dicho atraso, sin que ello genere responsabilidad ni penalidad alguna para el Proveedor.",
        "bodegaje": "Una vez notificada la finalización del Proyecto, el Cliente dispondrá de un plazo máximo de <b>10 días hábiles</b> para coordinar el retiro o despacho del módulo. Vencido dicho plazo, el Proveedor quedará facultado para cobrar un <b>cargo por bodegaje equivalente al 1% del valor neto del Proyecto por cada 7 días corridos</b>, hasta el retiro efectivo.",
        "garantia": "El Proveedor otorga una garantía de <b>6 meses</b> contados desde la entrega del módulo, limitada exclusivamente a <b>defectos de fabricación o construcción imputables al proceso productivo</b>.\nQuedan expresamente excluidos de garantía los daños derivados de:\n• Mal uso o uso distinto al previsto\n• Modificaciones no autorizadas\n• Transporte realizado por terceros\n• Vandalismo\n• Fenómenos naturales\n• Falta de mantención adecuada",
        "terminacion": "El presente contrato podrá terminarse anticipadamente por:\na) Incumplimiento grave de cualquiera de las partes.\nb) Mutuo acuerdo por escrito.\nc) No pago oportuno de cualquiera de las etapas de pago.\nEn caso de término imputable al Cliente, los montos pagados <b>no serán reembolsables</b>, salvo acuerdo distinto por escrito.",
        "jurisdiccion": "Para todos los efectos legales derivados del presente contrato, las partes fijan su domicilio en la <b>ciudad de Santiago</b>, y se someten a la competencia de sus <b>Tribunales Ordinarios de Justicia</b>.",
        "firma": "El presente contrato se firma en <b>dos ejemplares de igual tenor y fecha</b>, quedando uno en poder de cada parte.",
    }

    def _p(clave, fallback=None):
        def _strip(t): return _re.sub(r'<[^>]+>', '', t).strip()
        if plt_cls and clave in plt_cls and plt_cls[clave]:
            txt_sup = plt_cls[clave]
            if txt_sup.strip() == _strip(_ORIG.get(clave, "")):
                return _rep(_ORIG.get(clave, fallback or ""), d)
            return _rep(txt_sup, d)
        return _rep(_ORIG.get(clave, fallback or ""), d)

    story = [
        Paragraph("CONTRATO DE FABRICACIÓN Y VENTA", titulo),
        Paragraph("VIVIENDA TIPO CONTAINER", subtit),
        SP(4),
        HRFlowable(width="100%", thickness=1.5, color=AZUL, spaceAfter=10, spaceBefore=0),
        Paragraph(_p("intro", f"En Santiago de Chile, a <b>{d['fecha_str']}</b>, comparecen:"), normal),
        SP(4),
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
        Paragraph("III. OBJETO DEL CONTRATO", seccion),
        Paragraph(_p("objeto"), normal),
        HR(),
    ]

    story.append(Paragraph("IV. ALCANCE TÉCNICO Y EJECUCIÓN", seccion))
    for _l in _p("alcance").split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR(), Paragraph("V. VISITAS Y SEGUIMIENTO DEL PROYECTO", seccion),
              Paragraph(_p("visitas"), normal), HR(),
              Paragraph("VI. PRECIO", seccion),
              Paragraph(_p("precio"), normal), HR()]

    story.append(Paragraph("VII. FORMA Y ETAPAS DE PAGO", seccion))
    for _l in _p("forma_pago").split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR(), Paragraph("VIII. INICIO DE FABRICACIÓN", seccion),
              Paragraph(_p("inicio"), normal), HR()]

    story += [Paragraph("IX. MEDIOS DE PAGO", seccion),
              Paragraph("Los pagos deberán efectuarse mediante <b>transferencia electrónica, "
                        "cheque o vale vista</b>, a la siguiente cuenta bancaria:", normal)]
    datos_banco = [
        ["Razón Social:", "Inversiones Container House SpA"],
        ["RUT:", "78.268.851-0"],
        ["Banco:", "Banco Itaú"],
        ["Cuenta Corriente:", "N° 230771767"],
        ["Correo de confirmación:", "jperez@espaciocontainerhouse.cl"],
    ]
    tbl_banco = Table(datos_banco, colWidths=[4.5*cm, 11*cm])
    tbl_banco.setStyle(TableStyle([
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.HexColor('#f8fafc'), colors.white]),
        ('TOPPADDING',    (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING',   (0,0), (-1,-1), 6),
    ]))
    story += [tbl_banco, SP(6),
              Paragraph("Cada pago deberá ser informado por el Cliente mediante correo electrónico, adjuntando el comprobante respectivo.", normal),
              HR()]

    story.append(Paragraph("X. PLAZO DE FABRICACIÓN Y ENTREGA", seccion))
    for _l in _p("plazo").split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    story.append(Paragraph("XI. PENALIDAD POR ATRASO", seccion))
    for _l in _p("penalidad").split("\n"):
        if _l.strip(): story.append(Paragraph(_l.strip(), normal))
    story += [HR()]

    tipo_plt = (plt_cls.get("_tipo_plantilla") if plt_cls else None) or 'A'

    def _romano(n):
        vals = [(1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),
                (50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
        r = ''
        for v, s in vals:
            while n >= v: r += s; n -= v
        return r

    clausulas_vars = [
        ('bodegaje',        'RETIRO, DESPACHO Y BODEGAJE',          False, 'hr',        ('A','B')),
        ('garantia',        'GARANTÍA',                              True,  'hr',        ('A','B','E')),
        ('terminacion',     'TERMINACIÓN ANTICIPADA',                True,  'hr',        ('A','B','E')),
        ('jurisdiccion',    'DOMICILIO Y JURISDICCIÓN',              False, 'pagebreak', ('A','B','E')),
        ('suministro_energia', 'SUMINISTRO DE ENERGÍA ELÉCTRICA Y USO DE HERRAMIENTAS',
                                                                     True,  'sp',        ('B','E')),
        ('firma',           'FIRMA',                                 False, 'sp60',      ('A','B','E')),
    ]

    num_clausula = 11
    for clave, titulo_c, multi, sep, tipos in clausulas_vars:
        if tipo_plt not in tipos:
            continue
        num_clausula += 1
        num_str = _romano(num_clausula)

        if clave == 'suministro_energia':
            txt = (plt_cls or {}).get("suministro_energia", "")
            if not txt:
                continue
            txt = _re.sub(
                r'^X{0,3}(?:IX|IV|V?I{0,3})\..*?Y USO DE HERRAMIENTAS\s*',
                '', txt.strip(), flags=_re.IGNORECASE | _re.DOTALL
            ).strip()
            story += [Paragraph(f"{num_str}. {titulo_c}", seccion),
                      Paragraph(_rep(txt, d), normal), SP(6)]
        elif clave == 'firma':
            story += [Paragraph(f"{num_str}. {titulo_c}", seccion),
                      Paragraph(_p("firma"), normal), SP(60)]
        elif multi:
            story.append(Paragraph(f"{num_str}. {titulo_c}", seccion))
            for _l in _p(clave).split("\n"):
                if _l.strip(): story.append(Paragraph(_l.strip(), normal))
            if sep == 'hr': story.append(HR())
        else:
            story += [Paragraph(f"{num_str}. {titulo_c}", seccion),
                      Paragraph(_p(clave), normal)]
            if sep == 'hr': story.append(HR())
            elif sep == 'pagebreak': story.append(PageBreak())

    if d['tipo_cliente'] == 'natural':
        cli_firma_sub = f"RUT: {d['cli_rut']}"
    else:
        cli_firma_sub = f"RUT: {d['cli_rut']}\n{d.get('cli_empresa','')}"

    firma_data = [
        [Paragraph("EL PROVEEDOR", firma_b), Paragraph("EL CLIENTE", firma_b)],
        [Paragraph("_"*34, firma_s), Paragraph("_"*34, firma_s)],
        [Paragraph("Alan Mauricio Gatica Concha", firma_b), Paragraph(d['cli_nombre'], firma_b)],
        [Paragraph("RUT: 13.668.157-5", firma_s), Paragraph(f"RUT: {d['cli_rut']}", firma_s)],
        [Paragraph("Inversiones Container House SpA", firma_s), Paragraph(d.get('cli_empresa','') or '', firma_s)],
    ]
    firma_tbl = Table(firma_data, colWidths=[8*cm, 8*cm])
    firma_tbl.setStyle(TableStyle([
        ('ALIGN',         (0,0), (-1,-1), 'CENTER'),
        ('VALIGN',        (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING',    (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(firma_tbl)

    doc.build(story, onFirstPage=_build_header_footer, onLaterPages=_build_header_footer)
    buf.seek(0)
    return buf.read()
