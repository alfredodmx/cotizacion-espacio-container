import streamlit as st
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import io
from datetime import datetime, timedelta
import random
import re
import requests

st.set_page_config(layout="wide")

# =========================================================
# CSS PERSONALIZADO PARA CONTENEDORES (RESPETANDO TEMAS)
# =========================================================
st.markdown("""
<style>
    /* Estilo para contenedores con borde */
    div[data-testid="stContainer"] {
        border-radius: 15px !important;
        border: 2px solid rgba(128, 128, 128, 0.2) !important;
        background-color: rgba(128, 128, 128, 0.05) !important;
        padding: 20px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05) !important;
    }
    
    /* Estilo para títulos dentro de contenedores - usa el color del tema */
    div[data-testid="stContainer"] h3 {
        margin-top: 0 !important;
        font-size: 1.2rem !important;
        border-bottom: 1px solid rgba(128, 128, 128, 0.2) !important;
        padding-bottom: 10px !important;
        margin-bottom: 15px !important;
        /* Sin color fijo - hereda del tema */
    }
    
    /* Estilo para subtítulos dentro de contenedores */
    div[data-testid="stContainer"] h4, 
    div[data-testid="stContainer"] strong {
        color: inherit !important;
        font-size: 1rem !important;
    }
    
    /* Espaciado entre columnas */
    div[data-testid="stContainer"] div[data-testid="column"] {
        padding: 0 5px !important;
    }
    
    /* Asegurar que los títulos de sección fuera de contenedores usen el color del tema */
    h1, h2, h3, h4, h5, h6 {
        color: inherit !important;
    }
    
    /* Estilo para los separadores */
    hr {
        margin: 1rem 0 !important;
        border-color: rgba(128, 128, 128, 0.2) !important;
    }
    
    /* Mantener el color de los textos de éxito/error/info */
    .stAlert {
        color: inherit !important;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER CON LOGO
# =========================================================
header_col1, header_col2 = st.columns([4, 1])

with header_col1:
    st.title("Cotizador PRO")

with header_col2:
    try:
        st.image("logo2.png", width=300)
    except:
        pass

# =========================================================
# INICIALIZAR TODAS LAS VARIABLES DE SESSION_STATE
# =========================================================

# Inicializar variables del carrito
if 'carrito' not in st.session_state:
    st.session_state.carrito = []
    
# Inicializar variables de RUT
if 'rut_raw' not in st.session_state:
    st.session_state.rut_raw = ""
if 'rut_display' not in st.session_state:
    st.session_state.rut_display = ""
if 'rut_valido' not in st.session_state:
    st.session_state.rut_valido = False
if 'rut_mensaje' not in st.session_state:
    st.session_state.rut_mensaje = ""

# Inicializar variables de teléfono
if 'telefono_raw' not in st.session_state:
    st.session_state.telefono_raw = ""

# Inicializar variables de asesor
if 'asesor_seleccionado' not in st.session_state:
    st.session_state.asesor_seleccionado = "Seleccionar asesor"
if 'correo_asesor' not in st.session_state:
    st.session_state.correo_asesor = ""
if 'telefono_asesor' not in st.session_state:
    st.session_state.telefono_asesor = ""

# Inicializar variables de teléfono asesor (para compatibilidad)
if 'telefono_asesor_raw' not in st.session_state:
    st.session_state.telefono_asesor_raw = ""

# Inicializar variables temporales de asesor (para compatibilidad)
if 'asesor_correo_temp' not in st.session_state:
    st.session_state.asesor_correo_temp = ""

# Variable para forzar actualización de keys
if 'counter' not in st.session_state:
    st.session_state.counter = 0

tab1, tab2 = st.tabs(["🧾 Preparar Cotización", "👤 Datos Cliente / Ejecutivo"])

# =========================================================
# FUNCIONES DE VALIDACIÓN Y FORMATO DE RUT
# =========================================================

def validar_rut(rut_completo):
    """
    Valida un RUT chileno usando el algoritmo del Módulo 11
    Retorna (bool, str) - (válido, mensaje)
    """
    # Limpiar el RUT
    rut_limpio = re.sub(r'[^0-9kK]', '', rut_completo)
    
    if len(rut_limpio) < 2:
        return False, "RUT incompleto"
    
    # Separar cuerpo y dígito verificador
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1].upper()
    
    # Validar que el cuerpo sea numérico
    if not cuerpo.isdigit():
        return False, "RUT inválido"
    
    # Calcular dígito verificador esperado (Módulo 11)
    suma = 0
    multiplo = 2
    
    for i in range(len(cuerpo) - 1, -1, -1):
        suma += multiplo * int(cuerpo[i])
        multiplo = multiplo + 1 if multiplo < 7 else 2
    
    dv_esperado = 11 - (suma % 11)
    
    # Casos especiales
    if dv_esperado == 10:
        dv_esperado = 'K'
    elif dv_esperado == 11:
        dv_esperado = '0'
    else:
        dv_esperado = str(dv_esperado)
    
    # Comparar
    if dv_ingresado == dv_esperado:
        return True, "RUT válido"
    else:
        return False, "RUT inválido"

def formatear_rut(rut_raw):
    """
    Formatea un RUT raw (solo números) a formato con puntos y guión
    Ejemplo: 165571362 -> 16.557.136-2
    """
    if not rut_raw:
        return ""
    
    # Limitar a 9 dígitos
    if len(rut_raw) > 9:
        rut_raw = rut_raw[:9]
    
    # Si tiene al menos 2 caracteres, separar cuerpo y dv
    if len(rut_raw) >= 2:
        cuerpo = rut_raw[:-1]
        dv = rut_raw[-1].upper()
        
        # Formatear cuerpo con puntos (cada 3 dígitos desde la derecha)
        if cuerpo:
            cuerpo_formateado = ""
            for i, digito in enumerate(reversed(cuerpo)):
                if i > 0 and i % 3 == 0:
                    cuerpo_formateado = "." + cuerpo_formateado
                cuerpo_formateado = digito + cuerpo_formateado
        else:
            cuerpo_formateado = ""
        
        # Agregar guión y dígito verificador
        return f"{cuerpo_formateado}-{dv}"
    else:
        return rut_raw

def actualizar_rut():
    """Callback para actualizar el RUT cuando el usuario sale del campo"""
    if 'rut_input' in st.session_state:
        # Obtener el valor actual
        valor_actual = st.session_state.rut_input
        
        # Extraer solo números y K
        raw = re.sub(r'[^0-9kK]', '', valor_actual)
        
        # Limitar a 9 dígitos
        if len(raw) > 9:
            raw = raw[:9]
        
        # Guardar el raw
        st.session_state.rut_raw = raw
        
        # Formatear
        if raw:
            st.session_state.rut_display = formatear_rut(raw)
        else:
            st.session_state.rut_display = ""
        
        # Validar si tiene al menos 2 dígitos
        if len(raw) >= 2:
            valido, mensaje = validar_rut(raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje
        else:
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = "RUT incompleto"

def formatear_telefono(telefono_raw):
    """
    Formatea teléfono chileno
    Ejemplo: 961528954 -> +56 9 6152 8954
    """
    if not telefono_raw:
        return ""
    
    # Limitar a 9 dígitos
    if len(telefono_raw) > 9:
        telefono_raw = telefono_raw[:9]
    
    # Formato: +56 9 XXXX XXXX
    if len(telefono_raw) == 1:
        return f"+56 {telefono_raw}"
    elif len(telefono_raw) <= 5:
        return f"+56 {telefono_raw[:1]} {telefono_raw[1:]}"
    else:
        return f"+56 {telefono_raw[:1]} {telefono_raw[1:5]} {telefono_raw[5:]}"

def actualizar_telefono():
    """Callback para actualizar el teléfono del cliente"""
    if 'telefono_input' in st.session_state:
        valor_actual = st.session_state.telefono_input
        # Extraer solo números
        raw = re.sub(r'[^0-9]', '', valor_actual)
        if len(raw) > 9:
            raw = raw[:9]
        st.session_state.telefono_raw = raw

# ---------------- FUNCIONES ORIGINALES ----------------

def formato_clp(valor):
    return f"${valor:,.0f}".replace(",", ".")

def buscar_direccion(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": direccion,
        "format": "json",
        "addressdetails": 1,
        "limit": 1,
        "countrycodes": "cl"
    }
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": "epcontainer-app"},
            timeout=5
        )
        data = response.json()
        if data:
            address = data[0]["address"]
            comuna = address.get("city") or address.get("town") or address.get("village")
            region = address.get("state")
            return comuna, region
    except:
        pass
    return None, None

# ---------------- MODELOS ----------------

def cargar_modelo(nombre_hoja):
    df_modelo = pd.read_excel("cotizador.xlsx", sheet_name=nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]]
    df_modelo = df_modelo.dropna()
    df_modelo = df_modelo[df_modelo["Cantidad"] > 0]

    df_bd = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")
    df_bd = df_bd[["Item", "P. Unitario real"]]

    df_final = df_modelo.merge(df_bd, on="Item", how="left")

    carrito = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        carrito.append({
            "Categoria": row["Categorias"],
            "Item": row["Item"],
            "Cantidad": row["Cantidad"],
            "Precio Unitario": row["P. Unitario real"],
            "Subtotal": subtotal
        })
    return carrito

def cargar_categoria_desde_modelo(nombre_hoja, categoria_objetivo):
    df_modelo = pd.read_excel("cotizador.xlsx", sheet_name=nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]]
    df_modelo = df_modelo.dropna()

    df_modelo = df_modelo[
        (df_modelo["Cantidad"] > 0) &
        (df_modelo["Categorias"] == categoria_objetivo)
    ]

    df_bd = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")
    df_bd = df_bd[["Item", "P. Unitario real"]]

    df_final = df_modelo.merge(df_bd, on="Item", how="left")

    categoria_items = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        categoria_items.append({
            "Categoria": row["Categorias"],
            "Item": row["Item"],
            "Cantidad": row["Cantidad"],
            "Precio Unitario": row["P. Unitario real"],
            "Subtotal": subtotal
        })
    return categoria_items

# ---------------- PDF ----------------

def generar_pdf(carrito_df, subtotal, iva, total, datos_cliente,
                fecha_inicio, fecha_termino, dias_validez,
                datos_asesor):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=20, rightMargin=20,
                           topMargin=30, bottomMargin=30,
                           allowSplitting=1)
    elements = []
    styles = getSampleStyleSheet()
    
    # Crear estilos personalizados
    styles.add(ParagraphStyle(
        name='SmallFont',
        parent=styles['Normal'],
        fontSize=8,
        leading=12,
        wordWrap='CJK',
        leftIndent=0,
        alignment=0
    ))
    
    styles.add(ParagraphStyle(
        name='HeaderStyle',
        parent=styles['Normal'],
        fontSize=9,
        leading=11,
        alignment=1,
        textColor=colors.white,
        fontName='Helvetica-Bold',
        leftIndent=0
    ))
    
    styles.add(ParagraphStyle(
        name='TituloPresupuesto',
        parent=styles['Normal'],
        fontSize=16,
        leading=20,
        fontName='Helvetica-Bold',
        spaceAfter=6,
        leftIndent=0,
        alignment=0
    ))
    
    styles.add(ParagraphStyle(
        name='TextoNormal',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        leftIndent=0,
        alignment=0,
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TituloSeccion',
        parent=styles['Normal'],
        fontSize=12,
        leading=14,
        fontName='Helvetica-Bold',
        spaceAfter=6,
        leftIndent=0,
        alignment=0
    ))

    # =========================================================
    # LOGO (CENTRADO)
    # =========================================================
    try:
        logo = Image("logo.png")
        max_width = 3 * inch
        aspect = logo.imageHeight / float(logo.imageWidth)
        logo.drawWidth = max_width
        logo.drawHeight = max_width * aspect
        
        logo_data = [[logo]]
        logo_table = Table(logo_data, colWidths=[doc.width])
        logo_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (0, 0), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ]))
        elements.append(logo_table)
        elements.append(Spacer(1, 15))
    except:
        pass

    numero_presupuesto = f"EP-{random.randint(1000,9999)}"
    fecha_emision = datetime.now()

    # =========================================================
    # TÍTULO Y FECHAS
    # =========================================================
    elements.append(Paragraph(f"<b>PRESUPUESTO Nº {numero_presupuesto}</b>", styles['TituloPresupuesto']))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>Fecha Emisión:</b> {fecha_emision.strftime('%d-%m-%Y')}", styles['TextoNormal']))
    elements.append(Paragraph(
        f"<b>Validez:</b> {fecha_inicio.strftime('%d-%m-%Y')} hasta {fecha_termino.strftime('%d-%m-%Y')} ({dias_validez} días)",
        styles['TextoNormal']
    ))
    elements.append(Spacer(1, 20))

    # =========================================================
    # DATOS DEL CLIENTE Y ASESOR
    # =========================================================
    
    ancho_columna = (doc.width - 20) / 2
    
    data_cliente_asesor = []
    
    # Encabezados
    data_cliente_asesor.append([
        Paragraph("<b>DATOS DEL CLIENTE</b>", styles['TituloSeccion']),
        Paragraph("<b>DATOS DEL ASESOR</b>", styles['TituloSeccion'])
    ])
    
    # Preparar datos del cliente
    cliente_text = ""
    for campo, valor in datos_cliente.items():
        if valor:
            cliente_text += f"<b>{campo}:</b> {valor}<br/>"
    
    # Preparar datos del asesor
    asesor_text = ""
    for campo, valor in datos_asesor.items():
        if valor:
            asesor_text += f"<b>{campo}:</b> {valor}<br/>"
    
    data_cliente_asesor.append([
        Paragraph(cliente_text, styles['TextoNormal']),
        Paragraph(asesor_text, styles['TextoNormal'])
    ])
    
    tabla_cliente_asesor = Table(data_cliente_asesor, colWidths=[ancho_columna, ancho_columna])
    tabla_cliente_asesor.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('RIGHTPADDING', (0, 0), (0, -1), 10),
        ('LEFTPADDING', (1, 0), (1, -1), 0),
        ('RIGHTPADDING', (1, 0), (1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    elements.append(tabla_cliente_asesor)
    elements.append(Spacer(1, 20))

    # =========================================================
    # TABLA DE PRODUCTOS - CON ANCHOS CALCULADOS
    # =========================================================
    
    # Calcular anchos basados en el ancho total del documento
    ancho_total = doc.width
    
    # Distribución porcentual de las columnas
    porcentajes = [15, 50, 8, 13.5, 13.5]  # Suma = 100%
    anchos = [ancho_total * p / 100 for p in porcentajes]
    
    data = []
    
    # Encabezados
    headers = [
        Paragraph("<b>Categoría</b>", styles['HeaderStyle']),
        Paragraph("<b>Item</b>", styles['HeaderStyle']),
        Paragraph("<b>Cant.</b>", styles['HeaderStyle']),
        Paragraph("<b>P. Unitario</b>", styles['HeaderStyle']),
        Paragraph("<b>Subtotal</b>", styles['HeaderStyle'])
    ]
    data.append(headers)
    
    # Filas de datos
    for _, row in carrito_df.iterrows():
        data.append([
            Paragraph(row["Categoria"], styles['SmallFont']),
            Paragraph(row["Item"], styles['SmallFont']),
            Paragraph(str(row["Cantidad"]), styles['SmallFont']),
            Paragraph(formato_clp(row["Precio Unitario"]), styles['SmallFont']),
            Paragraph(formato_clp(row["Subtotal"]), styles['SmallFont'])
        ])

    tabla_productos = Table(data, colWidths=anchos, 
                           repeatRows=1,
                           splitByRow=1)
    
    tabla_productos.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    
    # Alternar colores de filas
    for i in range(1, len(data)):
        if i % 2 == 0:
            tabla_productos.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))
            ]))

    elements.append(tabla_productos)
    
    # =========================================================
    # TOTALES (EN KEEP_TOGETHER)
    # =========================================================
    totales_data = [
        ["", "", "", "Subtotal:", formato_clp(subtotal)],
        ["", "", "", "IVA (19%):", formato_clp(iva)],
        ["", "", "", "TOTAL:", formato_clp(total)]
    ]
    
    totales_tabla = Table(totales_data, colWidths=anchos)
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
        ('FONTNAME', (3, 2), (4, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (3, 2), (4, 2), 11),
        ('LINEABOVE', (3, 1), (4, 1), 1, colors.black),
        ('LINEABOVE', (3, 2), (4, 2), 2, colors.black),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
    ]))
    
    from reportlab.platypus import KeepTogether
    elementos_totales = [Spacer(1, 20), totales_tabla]
    elements.append(KeepTogether(elementos_totales))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# =========================================================
# TAB 2 - DATOS CLIENTE / EJECUTIVO (VERSIÓN COMPLETA)
# =========================================================

with tab2:
    # Título de la sección con estilo
    st.markdown("## 📋 Datos para la Cotización")
    st.markdown("---")
    
    # Base de datos de asesores
    asesores = {
        "Seleccionar asesor": {
            "correo": "",
            "telefono": ""
        },
        "María Pérez": {
            "correo": "maria.perez@empresa.cl",
            "telefono": "987654321"
        },
        "Juanito Carmona": {
            "correo": "juan.carmona@empresa.cl",
            "telefono": "912345678"
        },
        "Carlos Rodríguez": {
            "correo": "carlos.rodriguez@empresa.cl",
            "telefono": "955443322"
        },
        "Ana Martínez": {
            "correo": "ana.martinez@empresa.cl",
            "telefono": "966778899"
        },
        "Pedro Soto": {
            "correo": "pedro.soto@empresa.cl",
            "telefono": "944332211"
        }
    }
    
    # Crear dos columnas principales
    col_cliente, col_asesor = st.columns(2)
    
    with col_cliente:
        # Contenedor para Datos del Cliente con título incluido
        with st.container(border=True):
            st.markdown("### 👤 Datos del Cliente")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre Completo*", placeholder="Ej: Juan Pérez", key="nombre_input")
                
                # RUT con un solo campo
                st.text_input(
                    "RUT*", 
                    value=st.session_state.rut_display,
                    key="rut_input",
                    placeholder="12.345.678-9",
                    on_change=actualizar_rut
                )
                
                # Mostrar mensaje de validación
                if st.session_state.rut_raw:
                    if len(st.session_state.rut_raw) >= 2:
                        if st.session_state.rut_valido:
                            st.success("✅ RUT válido")
                        else:
                            st.error(f"❌ {st.session_state.rut_mensaje}")
                    else:
                        st.info("⏳ RUT incompleto")
            
            with col2:
                correo = st.text_input("Correo Electrónico*", placeholder="ejemplo@correo.cl", key="correo_input")
                
                # Validación básica de email
                if correo and "@" not in correo:
                    st.warning("⚠️ El correo debe contener @")
                
                # Teléfono del cliente (sin código, solo números)
                st.text_input(
                    "Teléfono",
                    value=st.session_state.telefono_raw,
                    key="telefono_input",
                    placeholder="961528954 (9 dígitos)",
                    on_change=actualizar_telefono
                )
        
        # Contenedor para Dirección del Proyecto
        with st.container(border=True):
            st.markdown("**📍 Dirección del Proyecto**")
            direccion = st.text_input("Dirección", placeholder="Calle, número, comuna", key="direccion_input")
            
            if direccion:
                with st.spinner("Buscando ubicación..."):
                    comuna, region = buscar_direccion(direccion)
                    if comuna:
                        col_comuna, col_region = st.columns(2)
                        with col_comuna:
                            st.success(f"🏙️ **Comuna:** {comuna}")
                        with col_region:
                            st.success(f"🗺️ **Región:** {region}")
                    else:
                        st.info("No se pudo detectar automáticamente. Puedes escribir la comuna manualmente.")
                        comuna_manual = st.text_input("Comuna", key="comuna_manual")
                        region_manual = st.text_input("Región", key="region_manual")
    
    with col_asesor:
        # Contenedor para Datos del Asesor con título incluido
        with st.container(border=True):
            st.markdown("### 👨‍💼 Datos del Asesor")
            
            # Selector de asesores
            nombres_asesores = list(asesores.keys())
            
            # Crear el selectbox y capturar el valor
            indice_actual = nombres_asesores.index(st.session_state.asesor_seleccionado) if st.session_state.asesor_seleccionado in nombres_asesores else 0
            
            asesor_elegido = st.selectbox(
                "Seleccionar Asesor",
                nombres_asesores,
                index=indice_actual,
                key="asesor_select"
            )
            
            # Actualizar session_state cuando cambia la selección
            if asesor_elegido != st.session_state.asesor_seleccionado:
                st.session_state.asesor_seleccionado = asesor_elegido
                if asesor_elegido != "Seleccionar asesor":
                    st.session_state.correo_asesor = asesores[asesor_elegido]["correo"]
                    st.session_state.telefono_asesor = asesores[asesor_elegido]["telefono"]
                else:
                    st.session_state.correo_asesor = ""
                    st.session_state.telefono_asesor = ""
                st.session_state.counter += 1
                st.rerun()
            
            # Mostrar asesor seleccionado
            if st.session_state.asesor_seleccionado != "Seleccionar asesor":
                st.info(f"👤 Asesor seleccionado: **{st.session_state.asesor_seleccionado}**")
            
            # Crear dos columnas para correo y teléfono
            col_a1, col_a2 = st.columns(2)
            
            with col_a1:
                # Campo de correo con key dinámica
                correo_key = f"asesor_correo_input_{st.session_state.counter}"
                correo_input = st.text_input(
                    "Correo Ejecutivo*", 
                    value=st.session_state.correo_asesor,
                    placeholder="ejecutivo@empresa.cl", 
                    key=correo_key
                )
                
                # Validación básica de email
                if correo_input and "@" not in correo_input:
                    st.warning("⚠️ El correo debe contener @")
                
                # Si el usuario edita manualmente
                if correo_input != st.session_state.correo_asesor:
                    st.session_state.correo_asesor = correo_input
                    st.session_state.asesor_seleccionado = "Seleccionar asesor"
                    st.session_state.counter += 1
                    st.rerun()
            
            with col_a2:
                # Teléfono asesor con key dinámica (sin código de país)
                telefono_key = f"asesor_telefono_input_{st.session_state.counter}"
                telefono_input = st.text_input(
                    "Teléfono Ejecutivo",
                    value=st.session_state.telefono_asesor,
                    key=telefono_key,
                    placeholder="912345678 (9 dígitos)"
                )
                
                # Si el usuario edita manualmente
                if telefono_input != st.session_state.telefono_asesor:
                    # Extraer solo números
                    raw = re.sub(r'[^0-9]', '', telefono_input)
                    if len(raw) > 9:
                        raw = raw[:9]
                    st.session_state.telefono_asesor = raw
                    st.session_state.asesor_seleccionado = "Seleccionar asesor"
                    st.session_state.counter += 1
                    st.rerun()
        
        # Contenedor para Validez del Presupuesto
        with st.container(border=True):
            st.markdown("### 📅 Validez del Presupuesto")
            
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                fecha_inicio = st.date_input("Fecha de Inicio", value=datetime.now(), key="fecha_inicio")
            
            with col_v2:
                fecha_termino = st.date_input("Fecha de Término", 
                                            value=datetime.now() + timedelta(days=15),
                                            key="fecha_termino")
            
            dias_validez = (fecha_termino - fecha_inicio).days
            
            if dias_validez < 0:
                st.error("⚠️ La fecha de término debe ser posterior a la fecha de inicio.")
            else:
                st.markdown(f"**⏱️ Duración:** {dias_validez} días")
                if dias_validez > 0:
                    st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días de validez")
    
    # =========================================================
    # SECCIÓN DE OBSERVACIONES
    # =========================================================
    st.markdown("---")
    st.markdown("### 📝 Observaciones")
    
    with st.container(border=True):
        observaciones = st.text_area("Observaciones y notas adicionales", 
                                    placeholder="Ingresa aquí cualquier información relevante para la cotización...",
                                    height=100,
                                    key="observaciones_input")
    
    # =========================================================
    # RESUMEN DE LOS DATOS INGRESADOS
    # =========================================================
    st.markdown("---")
    with st.expander("📋 Ver resumen de datos ingresados", expanded=False):
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.markdown("**Cliente:**")
            st.write(f"• **Nombre:** {nombre if nombre else 'No ingresado'}")
            st.write(f"• **RUT:** {st.session_state.rut_display if st.session_state.rut_display else 'No ingresado'} {'✅' if st.session_state.rut_valido else '❌' if st.session_state.rut_raw else ''}")
            st.write(f"• **Email:** {correo if correo else 'No ingresado'}")
            st.write(f"• **Teléfono:** {st.session_state.telefono_raw if st.session_state.telefono_raw else 'No ingresado'}")
            st.write(f"• **Dirección:** {direccion if direccion else 'No ingresado'}")
        
        with col_res2:
            st.markdown("**Asesor y Validez:**")
            # Mostrar el nombre del asesor seleccionado
            nombre_asesor_mostrar = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else "No seleccionado"
            st.write(f"• **Ejecutivo:** {nombre_asesor_mostrar}")
            st.write(f"• **Email Ejecutivo:** {st.session_state.correo_asesor if st.session_state.correo_asesor else 'No ingresado'}")
            st.write(f"• **Teléfono Ejecutivo:** {st.session_state.telefono_asesor if st.session_state.telefono_asesor else 'No ingresado'}")
            st.write(f"• **Validez:** {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_termino.strftime('%d/%m/%Y')}")
            st.write(f"• **Días de validez:** {dias_validez if dias_validez > 0 else 'Fechas inválidas'}")
    
    # =========================================================
    # DICCIONARIOS PARA PASAR A LA FUNCIÓN PDF
    # =========================================================
    datos_cliente = {
        "Nombre": nombre if nombre else "",
        "RUT": st.session_state.rut_display if st.session_state.rut_display else "",
        "Correo": correo if correo else "",
        "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else "",
        "Dirección": direccion if direccion else "",
        "Observaciones": observaciones if observaciones else ""
    }
    
    # Para el asesor, usamos el nombre seleccionado del dropdown
    nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    
    datos_asesor = {
        "Nombre Ejecutivo": nombre_asesor_final,
        "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
        "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
    }

# =========================================================
# TAB 1 - PREPARAR COTIZACIÓN (con contenedor único)
# =========================================================
    
with tab1:
    
    # Título de la sección con estilo
    st.markdown("## ☑️ Crea tu Presupuesto")
    st.markdown("---")
    
    # Contenedor único con borde redondeado para los 4 módulos
    with st.container(border=True):
        st.markdown("### 📦 Gestión de Productos")
        
        # Crear 4 columnas dentro del contenedor
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        # ---------- 1️⃣ MODELOS PREDEFINIDOS ----------
        with col_m1:
            st.markdown("**Modelos Predefinidos**")
            
            archivo_excel = pd.ExcelFile("cotizador.xlsx")
            hojas_modelo = [h for h in archivo_excel.sheet_names if h.lower().startswith("modelo")]

            if hojas_modelo:
                modelo_seleccionado = st.selectbox("Seleccionar Modelo", hojas_modelo, key="modelo_select", label_visibility="collapsed")

                if st.button("Cargar Modelo", key="btn_modelo", use_container_width=True):
                    st.session_state.carrito = cargar_modelo(modelo_seleccionado)
                    st.session_state.modelo_base = modelo_seleccionado
                    st.success(f"Modelo {modelo_seleccionado} cargado correctamente.")
                    st.rerun()

        # ---------- 2️⃣ SELECCIONAR ÍTEMS ----------
        with col_m2:
            st.markdown("**Agregar Ítems**")
            
            df = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")

            categorias = df["Categorias"].dropna().unique()
            categoria_seleccionada = st.selectbox("Categoría", categorias, key="cat_manual", label_visibility="collapsed")

            items_filtrados = df[df["Categorias"] == categoria_seleccionada]
            item = st.selectbox("Ítem", items_filtrados["Item"], key="item_manual", label_visibility="collapsed")

            cantidad = st.number_input("Cantidad", min_value=1, value=1, key="cantidad_manual", label_visibility="collapsed")

            precio_unitario = items_filtrados[
                items_filtrados["Item"] == item
            ]["P. Unitario real"].values[0]

            subtotal_item = precio_unitario * cantidad

            st.caption(f"P. Unitario: {formato_clp(precio_unitario)}")
            st.caption(f"Subtotal: {formato_clp(subtotal_item)}")

            if st.button("Agregar", key="btn_agregar_manual", use_container_width=True):
                existe = False

                for producto in st.session_state.carrito:
                    if producto["Item"] == item:
                        producto["Cantidad"] += cantidad
                        producto["Subtotal"] = producto["Cantidad"] * producto["Precio Unitario"]
                        existe = True
                        break

                if not existe:
                    st.session_state.carrito.append({
                        "Categoria": categoria_seleccionada,
                        "Item": item,
                        "Cantidad": cantidad,
                        "Precio Unitario": precio_unitario,
                        "Subtotal": subtotal_item
                    })

                st.rerun()

        # ---------- 3️⃣ GESTIÓN POR CATEGORÍA ----------
        with col_m3:
            st.markdown("**Eliminar Categoría**")
            
            if st.session_state.carrito:
                carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                categorias_carrito = carrito_df_temp["Categoria"].unique()

                categoria_eliminar = st.selectbox(
                    "Categoría a eliminar",
                    ["-- Seleccionar --"] + list(categorias_carrito),
                    key="cat_eliminar",
                    label_visibility="collapsed"
                )

                if categoria_eliminar != "-- Seleccionar --":
                    if st.button("Eliminar Categoría", key="btn_eliminar_categoria", use_container_width=True):
                        st.session_state.carrito = [
                            item for item in st.session_state.carrito
                            if item["Categoria"] != categoria_eliminar
                        ]
                        st.success(f"Categoría '{categoria_eliminar}' eliminada.")
                        st.rerun()
            else:
                st.info("No hay categorías para eliminar")

        # ---------- 4️⃣ RECUPERAR / AGREGAR CATEGORÍA ----------
        with col_m4:
            st.markdown("**Agregar Categoría**")
            
            if hojas_modelo:
                modelo_origen = st.selectbox(
                    "Modelo origen",
                    hojas_modelo,
                    key="modelo_origen",
                    label_visibility="collapsed"
                )

                df_temp = pd.read_excel("cotizador.xlsx", sheet_name=modelo_origen)
                categorias_disponibles = df_temp["Categorias"].dropna().unique()

                categoria_agregar = st.selectbox(
                    "Categoría a agregar",
                    categorias_disponibles,
                    key="cat_agregar",
                    label_visibility="collapsed"
                )

                if st.button("Agregar Categoría", key="btn_agregar_categoria", use_container_width=True):
                    nuevos_items = cargar_categoria_desde_modelo(
                        modelo_origen,
                        categoria_agregar
                    )

                    st.session_state.carrito = [
                        item for item in st.session_state.carrito
                        if item["Categoria"] != categoria_agregar
                    ]

                    st.session_state.carrito.extend(nuevos_items)
                    st.success(f"Categoría '{categoria_agregar}' agregada.")
                    st.rerun()

    # ---------------- RESUMEN ----------------
    st.markdown("---")
    st.subheader("Resumen del Presupuesto")

    if st.session_state.carrito:
        carrito_df = pd.DataFrame(st.session_state.carrito)

        # ---------------- TABLA CON ELIMINACIÓN DIRECTA ----------------
        carrito_df_edit = carrito_df.copy()
        carrito_df_edit["❌"] = False

        edited_df = st.data_editor(
            carrito_df_edit,
            use_container_width=True,
            hide_index=True,
            column_config={
                "❌": st.column_config.CheckboxColumn(
                    "❌",
                    help="Marcar para eliminar ítem"
                )
            }
        )

        filas_eliminar = edited_df[edited_df["❌"] == True].index.tolist()

        if filas_eliminar:
            for i in sorted(filas_eliminar, reverse=True):
                del st.session_state.carrito[i]
            st.rerun()

        # ---------------- TOTALES ----------------
        carrito_df = pd.DataFrame(st.session_state.carrito)

        subtotal_general = carrito_df["Subtotal"].sum()
        iva = subtotal_general * 0.19
        total = subtotal_general + iva

        st.markdown("### Totales")
        st.write("Subtotal:", formato_clp(subtotal_general))
        st.write("IVA (19%):", formato_clp(iva))
        st.write("TOTAL:", formato_clp(total))

        # Obtener los valores directamente de session_state para el PDF
        correo_para_pdf = st.session_state.get('correo_input', '')
        if not correo_para_pdf and 'correo_input' in locals():
            correo_para_pdf = correo
        
        # Validar que el RUT sea válido antes de generar PDF
        rut_valido_para_pdf = True
        if st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            rut_valido_para_pdf = st.session_state.rut_valido
        
        # Verificar que las variables necesarias existen
        if 'fecha_inicio' not in locals():
            fecha_inicio = st.session_state.get('fecha_inicio', datetime.now())
        if 'fecha_termino' not in locals():
            fecha_termino = st.session_state.get('fecha_termino', datetime.now() + timedelta(days=15))
        if 'dias_validez' not in locals():
            dias_validez = (fecha_termino - fecha_inicio).days
        
        # Construir datos para el PDF directamente desde session_state
        datos_cliente_pdf = {
            "Nombre": st.session_state.get('nombre_input', ''),
            "RUT": st.session_state.rut_display if st.session_state.rut_display else '',
            "Correo": st.session_state.get('correo_input', ''),
            "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else '',
            "Dirección": st.session_state.get('direccion_input', ''),
            "Observaciones": st.session_state.get('observaciones_input', '')
        }
        
        # Datos del asesor desde session_state
        nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
        
        datos_asesor_pdf = {
            "Nombre Ejecutivo": nombre_asesor_final,
            "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
            "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
        }
        
        if "@" not in correo_para_pdf:
            st.error("El correo debe contener '@' para generar el PDF.")
        elif dias_validez < 0:
            st.error("Fechas incorrectas.")
        elif not rut_valido_para_pdf and st.session_state.rut_raw:
            st.error("El RUT no es válido. Corrígelo antes de generar el PDF.")
        else:
            pdf_buffer = generar_pdf(
                carrito_df,
                subtotal_general,
                iva,
                total,
                datos_cliente_pdf,
                fecha_inicio,
                fecha_termino,
                dias_validez,
                datos_asesor_pdf
            )

            st.download_button(
                label="Descargar Presupuesto en PDF",
                data=pdf_buffer,
                file_name="Presupuesto_Epcontainer.pdf",
                mime="application/pdf"
            )

        if st.button("Limpiar Presupuesto"):
            st.session_state.carrito = []
            st.rerun()