import streamlit as st
import pandas as pd
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # CORREGIDO: agregado ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
import io
from datetime import datetime, timedelta
import random
import re
import requests

st.set_page_config(layout="wide")

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

#st.markdown("---")

# Inicializar session_state
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

tab1, tab2 = st.tabs(["🧾 Preparar Cotización", "👤 Datos Cliente / Ejecutivo"])

# ---------------- FUNCIONES ----------------

def formato_clp(valor):
    return f"${valor:,.0f}".replace(",", ".")

def formatear_rut(rut):
    rut = re.sub(r"[^0-9kK]", "", rut)
    if len(rut) < 2:
        return rut
    cuerpo = rut[:-1]
    dv = rut[-1]
    try:
        cuerpo = f"{int(cuerpo):,}".replace(",", ".")
    except:
        return rut
    return f"{cuerpo}-{dv}"

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
# TAB 2 - DATOS CLIENTE / EJECUTIVO (VERSIÓN CORREGIDA)
# =========================================================

with tab2:
    # Título de la sección con estilo
    st.markdown("## 📋 Datos para la Cotización")
    st.markdown("---")
    
    # Crear dos columnas principales para organizar mejor la información
    col_cliente, col_asesor = st.columns(2)
    
    with col_cliente:
        st.markdown("### 👤 Datos del Cliente")
        
        with st.container(border=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nombre = st.text_input("Nombre Completo*", placeholder="Ej: Juan Pérez")
                rut_input = st.text_input("RUT*", placeholder="12.345.678-9")
                rut = formatear_rut(rut_input)
                if rut_input and len(rut_input) > 1:
                    st.caption(f"RUT formateado: {rut}")
            
            with col2:
                correo = st.text_input("Correo Electrónico*", placeholder="ejemplo@correo.cl")
                codigo_pais = st.selectbox("Código", ["+56"], help="Código de país")
                telefono_num = st.text_input("Teléfono", placeholder="9 1234 5678")
                telefono = f"{codigo_pais}{telefono_num}" if telefono_num else ""
        
        with st.container(border=True):
            st.markdown("**📍 Dirección del Proyecto**")
            direccion = st.text_input("Dirección", placeholder="Calle, número, comuna")
            
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
        st.markdown("### 👨‍💼 Datos del Asesor")
        
        with st.container(border=True):
            col_a1, col_a2 = st.columns(2)
            
            with col_a1:
                asesor_nombre = st.text_input("Nombre Ejecutivo*", placeholder="Ej: María González")
                asesor_correo = st.text_input("Correo Ejecutivo*", placeholder="ejecutivo@empresa.cl")
            
            with col_a2:
                asesor_telefono = st.text_input("Teléfono Ejecutivo", placeholder="+56 9 8765 4321")
                # Espacio para mantener la alineación
                st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("### 📅 Validez del Presupuesto")
        
        with st.container(border=True):
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                fecha_inicio = st.date_input("Fecha de Inicio", value=datetime.now())
            
            with col_v2:
                # CORRECCIÓN: Usar timedelta en lugar de sumar días manualmente
                fecha_termino = st.date_input("Fecha de Término", 
                                            value=datetime.now() + timedelta(days=15))
            
            dias_validez = (fecha_termino - fecha_inicio).days
            
            if dias_validez < 0:
                st.error("⚠️ La fecha de término debe ser posterior a la fecha de inicio.")
            else:
                # Barra de progreso visual para los días de validez
                st.markdown(f"**⏱️ Duración:** {dias_validez} días")
                if dias_validez > 0:
                    st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días de validez")
    
    # Sección de observaciones (ocupa todo el ancho)
    st.markdown("---")
    st.markdown("### 📝 Observaciones")
    
    with st.container(border=True):
        observaciones = st.text_area("Observaciones y notas adicionales", 
                                    placeholder="Ingresa aquí cualquier información relevante para la cotización...",
                                    height=100)
    
    # Resumen de los datos ingresados
    st.markdown("---")
    with st.expander("📋 Ver resumen de datos ingresados", expanded=False):
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.markdown("**Cliente:**")
            st.write(f"• **Nombre:** {nombre if nombre else 'No ingresado'}")
            st.write(f"• **RUT:** {rut if rut else 'No ingresado'}")
            st.write(f"• **Email:** {correo if correo else 'No ingresado'}")
            st.write(f"• **Teléfono:** {telefono if telefono else 'No ingresado'}")
            st.write(f"• **Dirección:** {direccion if direccion else 'No ingresado'}")
        
        with col_res2:
            st.markdown("**Asesor y Validez:**")
            st.write(f"• **Ejecutivo:** {asesor_nombre if asesor_nombre else 'No ingresado'}")
            st.write(f"• **Email Ejecutivo:** {asesor_correo if asesor_correo else 'No ingresado'}")
            st.write(f"• **Validez:** {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_termino.strftime('%d/%m/%Y')}")
            st.write(f"• **Días de validez:** {dias_validez if dias_validez > 0 else 'Fechas inválidas'}")
    
    # Diccionarios para pasar a la función PDF
    datos_cliente = {
        "Nombre": nombre if nombre else "",
        "RUT": rut if rut else "",
        "Correo": correo if correo else "",
        "Teléfono": telefono if telefono else "",
        "Dirección": direccion if direccion else "",
        "Observaciones": observaciones if observaciones else ""
    }
    
    datos_asesor = {
        "Nombre Ejecutivo": asesor_nombre if asesor_nombre else "",
        "Correo Ejecutivo": asesor_correo if asesor_correo else "",
        "Teléfono Ejecutivo": asesor_telefono if asesor_telefono else ""
    }

# =========================================================
# TAB 1 - PREPARAR COTIZACIÓN (sin cambios)
# =========================================================
    
with tab1:
    
    # Título de la sección con estilo
    st.markdown("## ☑️ Crea tu Presupuesto")
    st.markdown("---")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    # ---------- 1️⃣ MODELOS PREDEFINIDOS ----------
    with col_m1:
        st.subheader("Modelos Predefinidos")

        archivo_excel = pd.ExcelFile("cotizador.xlsx")
        hojas_modelo = [h for h in archivo_excel.sheet_names if h.lower().startswith("modelo")]

        if hojas_modelo:
            modelo_seleccionado = st.selectbox("Seleccionar Modelo", hojas_modelo, key="modelo_select")

            if st.button("Cargar Modelo (Reemplaza el actual)", key="btn_modelo"):
                st.session_state.carrito = cargar_modelo(modelo_seleccionado)
                st.session_state.modelo_base = modelo_seleccionado
                st.success(f"Modelo {modelo_seleccionado} cargado correctamente.")
                st.rerun()

    # ---------- 2️⃣ SELECCIONAR ÍTEMS ----------
    with col_m2:
        st.subheader("Agregar Ítems")

        df = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")

        categorias = df["Categorias"].dropna().unique()
        categoria_seleccionada = st.selectbox("Selecciona Categoría", categorias, key="cat_manual")

        items_filtrados = df[df["Categorias"] == categoria_seleccionada]
        item = st.selectbox("Selecciona Ítem", items_filtrados["Item"], key="item_manual")

        cantidad = st.number_input("Cantidad", min_value=1, value=1, key="cantidad_manual")

        precio_unitario = items_filtrados[
            items_filtrados["Item"] == item
        ]["P. Unitario real"].values[0]

        subtotal_item = precio_unitario * cantidad

        st.write("Precio Unitario:", formato_clp(precio_unitario))
        st.write("Subtotal Ítem:", formato_clp(subtotal_item))

        if st.button("Agregar al Presupuesto", key="btn_agregar_manual"):
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
        st.subheader("Eliminar Categoría")

        if st.session_state.carrito:
            carrito_df_temp = pd.DataFrame(st.session_state.carrito)
            categorias_carrito = carrito_df_temp["Categoria"].unique()

            categoria_eliminar = st.selectbox(
                "Eliminar categoría completa",
                ["-- Seleccionar --"] + list(categorias_carrito),
                key="cat_eliminar"
            )

            if categoria_eliminar != "-- Seleccionar --":
                if st.button("Eliminar Categoría Seleccionada", key="btn_eliminar_categoria"):
                    st.session_state.carrito = [
                        item for item in st.session_state.carrito
                        if item["Categoria"] != categoria_eliminar
                    ]
                    st.success(f"Categoría '{categoria_eliminar}' eliminada.")
                    st.rerun()

    # ---------- 4️⃣ RECUPERAR / AGREGAR CATEGORÍA ----------
    with col_m4:
        st.subheader("Agregar Categoría")

        if hojas_modelo:
            modelo_origen = st.selectbox(
                "Seleccionar modelo origen",
                hojas_modelo,
                key="modelo_origen"
            )

            df_temp = pd.read_excel("cotizador.xlsx", sheet_name=modelo_origen)
            categorias_disponibles = df_temp["Categorias"].dropna().unique()

            categoria_agregar = st.selectbox(
                "Seleccionar categoría a agregar",
                categorias_disponibles,
                key="cat_agregar"
            )

            if st.button("Agregar Categoría al Presupuesto", key="btn_agregar_categoria"):
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

        # Verificar que las variables necesarias existen
        if 'correo' not in locals():
            correo = ""
        if 'dias_validez' not in locals():
            dias_validez = 0
        if 'datos_cliente' not in locals():
            datos_cliente = {}
        if 'datos_asesor' not in locals():
            datos_asesor = {}
        if 'fecha_inicio' not in locals():
            fecha_inicio = datetime.now()
        if 'fecha_termino' not in locals():
            fecha_termino = datetime.now()

        if "@" not in correo:
            st.error("El correo debe contener '@' para generar el PDF.")
        elif dias_validez < 0:
            st.error("Fechas incorrectas.")
        else:
            pdf_buffer = generar_pdf(
                carrito_df,
                subtotal_general,
                iva,
                total,
                datos_cliente,
                fecha_inicio,
                fecha_termino,
                dias_validez,
                datos_asesor
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