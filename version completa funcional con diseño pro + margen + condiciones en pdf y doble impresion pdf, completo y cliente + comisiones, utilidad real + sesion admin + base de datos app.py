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
import sqlite3
import json

st.set_page_config(layout="wide", page_title="Cotizador PRO", page_icon="📊")

# =========================================================
# INICIALIZAR VARIABLES DE SESIÓN
# =========================================================
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False
    
if 'mostrar_login' not in st.session_state:
    st.session_state.mostrar_login = False

# Variables para datos del cliente
if 'nombre_input' not in st.session_state:
    st.session_state.nombre_input = ""
if 'correo_input' not in st.session_state:
    st.session_state.correo_input = ""
if 'direccion_input' not in st.session_state:
    st.session_state.direccion_input = ""
if 'fecha_inicio' not in st.session_state:
    st.session_state.fecha_inicio = datetime.now().date()
if 'fecha_termino' not in st.session_state:
    st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
if 'observaciones_input' not in st.session_state:
    st.session_state.observaciones_input = ""

# Variable para la cotización seleccionada en la búsqueda
if 'cotizacion_seleccionada' not in st.session_state:
    st.session_state.cotizacion_seleccionada = None

# Variable para la cotización cargada
if 'cotizacion_cargada' not in st.session_state:
    st.session_state.cotizacion_cargada = None

# Variables para el carrito y configuración
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

if 'margen' not in st.session_state:
    st.session_state.margen = 0.0
    
if 'rut_raw' not in st.session_state:
    st.session_state.rut_raw = ""
if 'rut_display' not in st.session_state:
    st.session_state.rut_display = ""
if 'rut_valido' not in st.session_state:
    st.session_state.rut_valido = False
if 'rut_mensaje' not in st.session_state:
    st.session_state.rut_mensaje = ""

if 'telefono_raw' not in st.session_state:
    st.session_state.telefono_raw = ""

if 'asesor_seleccionado' not in st.session_state:
    st.session_state.asesor_seleccionado = "Seleccionar asesor"
if 'correo_asesor' not in st.session_state:
    st.session_state.correo_asesor = ""
if 'telefono_asesor' not in st.session_state:
    st.session_state.telefono_asesor = ""

if 'telefono_asesor_raw' not in st.session_state:
    st.session_state.telefono_asesor_raw = ""

if 'asesor_correo_temp' not in st.session_state:
    st.session_state.asesor_correo_temp = ""

if 'counter' not in st.session_state:
    st.session_state.counter = 0

# Variable para controlar la carga de cotización
if 'cargar_cotizacion_trigger' not in st.session_state:
    st.session_state.cargar_cotizacion_trigger = False
    
if 'cotizacion_a_cargar' not in st.session_state:
    st.session_state.cotizacion_a_cargar = None

# Clave para acceso administrativo
CLAVE_ADMIN = "admin2024"

# =========================================================
# FUNCIONES DE VALIDACIÓN Y FORMATO
# =========================================================

def validar_rut(rut_completo):
    """
    Valida un RUT chileno usando el algoritmo del Módulo 11
    Retorna (bool, str) - (válido, mensaje)
    """
    rut_limpio = re.sub(r'[^0-9kK]', '', rut_completo)
    
    if len(rut_limpio) < 2:
        return False, "RUT incompleto"
    
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1].upper()
    
    if not cuerpo.isdigit():
        return False, "RUT inválido"
    
    suma = 0
    multiplo = 2
    
    for i in range(len(cuerpo) - 1, -1, -1):
        suma += multiplo * int(cuerpo[i])
        multiplo = multiplo + 1 if multiplo < 7 else 2
    
    dv_esperado = 11 - (suma % 11)
    
    if dv_esperado == 10:
        dv_esperado = 'K'
    elif dv_esperado == 11:
        dv_esperado = '0'
    else:
        dv_esperado = str(dv_esperado)
    
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
    
    if len(rut_raw) > 9:
        rut_raw = rut_raw[:9]
    
    if len(rut_raw) >= 2:
        cuerpo = rut_raw[:-1]
        dv = rut_raw[-1].upper()
        
        if cuerpo:
            cuerpo_formateado = ""
            for i, digito in enumerate(reversed(cuerpo)):
                if i > 0 and i % 3 == 0:
                    cuerpo_formateado = "." + cuerpo_formateado
                cuerpo_formateado = digito + cuerpo_formateado
        else:
            cuerpo_formateado = ""
        
        return f"{cuerpo_formateado}-{dv}"
    else:
        return rut_raw

def formatear_telefono(telefono_raw):
    """
    Formatea teléfono chileno
    Ejemplo: 961528954 -> +56 9 6152 8954
    """
    if not telefono_raw:
        return ""
    
    if len(telefono_raw) > 9:
        telefono_raw = telefono_raw[:9]
    
    if len(telefono_raw) == 1:
        return f"+56 {telefono_raw}"
    elif len(telefono_raw) <= 5:
        return f"+56 {telefono_raw[:1]} {telefono_raw[1:]}"
    else:
        return f"+56 {telefono_raw[:1]} {telefono_raw[1:5]} {telefono_raw[5:]}"

def formato_clp(valor):
    return f"${valor:,.0f}".replace(",", ".")

# =========================================================
# FUNCIONES PARA PROCESAR CAMBIOS EN TIEMPO REAL
# =========================================================

def procesar_cambio_rut():
    """Procesa el cambio en el campo RUT"""
    rut_key = f"rut_input_{st.session_state.counter}"
    if rut_key in st.session_state:
        valor_actual = st.session_state[rut_key]
        raw = re.sub(r'[^0-9kK]', '', valor_actual)
        if len(raw) > 9:
            raw = raw[:9]
        
        st.session_state.rut_raw = raw
        
        if raw:
            st.session_state.rut_display = formatear_rut(raw)
        else:
            st.session_state.rut_display = ""
        
        if len(raw) >= 2:
            valido, mensaje = validar_rut(raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje
        else:
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = "RUT incompleto"

def procesar_cambio_telefono():
    """Procesa el cambio en el campo teléfono"""
    telefono_key = f"telefono_input_{st.session_state.counter}"
    if telefono_key in st.session_state:
        valor_actual = st.session_state[telefono_key]
        raw = re.sub(r'[^0-9]', '', valor_actual)
        if len(raw) > 9:
            raw = raw[:9]
        st.session_state.telefono_raw = raw

# =========================================================
# FUNCIONES PARA EVALUAR ESTADO DE COTIZACIÓN
# =========================================================

def evaluar_estado_cotizacion(cotizacion):
    """
    Evalúa el estado de una cotización:
    - 🟢 AUTORIZADO: tiene margen > 0 Y datos completos
    - 🟡 BORRADOR: sin margen, datos completos
    - 🔴 INCOMPLETO: faltan datos del cliente o asesor (con o sin margen)
    """
    # Verificar datos del cliente
    datos_completos = True
    campos_requeridos = [
        cotizacion.get('cliente_nombre', ''),
        cotizacion.get('cliente_rut', ''),
        cotizacion.get('cliente_email', '')
    ]
    
    if not all(campos_requeridos):
        datos_completos = False
    
    # Verificar datos del asesor (al menos uno de los dos)
    asesor_completo = (
        cotizacion.get('asesor_nombre', '') or 
        cotizacion.get('asesor_email', '') or 
        cotizacion.get('asesor_telefono', '')
    )
    
    if not asesor_completo:
        datos_completos = False
    
    # SI FALTAN DATOS → INCOMPLETO (sin importar el margen)
    if not datos_completos:
        return "🔴 INCOMPLETO"
    
    # SI DATOS COMPLETOS, verificar margen
    tiene_margen = cotizacion.get('config_margen', 0) > 0
    
    if tiene_margen:
        return "🟢 AUTORIZADO"
    else:
        return "🟡 BORRADOR"

def crear_badge_estado(row):
    """
    Crea un badge HTML según el estado de la cotización
    row: tupla con todos los datos de la cotización
    """
    # Extraer datos
    config_margen = row[5]  # índice del margen
    cliente_nombre = row[1]
    cliente_rut = row[6]
    cliente_email = row[7]
    asesor_nombre = row[2]
    asesor_email = row[8]
    asesor_telefono = row[9]
    
    # Verificar datos completos
    datos_completos = all([cliente_nombre, cliente_rut, cliente_email])
    asesor_completo = any([asesor_nombre, asesor_email, asesor_telefono])
    
    # Determinar estado y crear badge
    if config_margen and config_margen > 0:
        if datos_completos and asesor_completo:
            # 🟢 AUTORIZADO (con margen Y datos completos)
            return '''
            <span style="
                background-color: #28a745; 
                color: white; 
                padding: 4px 12px; 
                border-radius: 20px; 
                font-size: 0.8rem;
                font-weight: 600;
                display: inline-block;
                border: 1px solid #1e7e34;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                🟢 AUTORIZADO
            </span>
            '''
        else:
            # 🔴 INCOMPLETO (tiene margen pero faltan datos)
            return '''
            <span style="
                background-color: #dc3545; 
                color: white; 
                padding: 4px 12px; 
                border-radius: 20px; 
                font-size: 0.8rem;
                font-weight: 600;
                display: inline-block;
                border: 1px solid #bd2130;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            ">
                🔴 INCOMPLETO
            </span>
            '''
    
    # Sin margen
    if datos_completos and asesor_completo:
        # 🟡 BORRADOR (listo para revisión)
        return '''
        <span style="
            background-color: #ffc107; 
            color: #212529; 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 0.8rem;
            font-weight: 600;
            display: inline-block;
            border: 1px solid #d39e00;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            🟡 BORRADOR
        </span>
        '''
    else:
        # 🔴 INCOMPLETO (faltan datos)
        return '''
        <span style="
            background-color: #dc3545; 
            color: white; 
            padding: 4px 12px; 
            border-radius: 20px; 
            font-size: 0.8rem;
            font-weight: 600;
            display: inline-block;
            border: 1px solid #bd2130;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        ">
            🔴 INCOMPLETO
        </span>
        '''

# =========================================================
# FUNCIONES PARA MANEJO DE MARGEN
# =========================================================

def aplicar_margen(precio_original, margen):
    """
    Aplica un margen porcentual al precio original
    """
    return precio_original * (1 + margen / 100)

def formatear_precio_con_margen(precio_original, margen):
    """
    Formatea el precio con margen aplicado
    """
    precio_con_margen = aplicar_margen(precio_original, margen)
    return formato_clp(precio_con_margen)

def calcular_totales_con_margen(carrito, margen):
    """
    Calcula todos los totales aplicando el margen
    """
    subtotal_con_margen = 0
    for item in carrito:
        precio_con_margen = aplicar_margen(item["Precio Unitario"], margen)
        subtotal_con_margen += item["Cantidad"] * precio_con_margen
    
    iva_con_margen = subtotal_con_margen * 0.19
    total_con_margen = subtotal_con_margen + iva_con_margen
    
    return subtotal_con_margen, iva_con_margen, total_con_margen

# =========================================================
# FUNCIONES PARA CÁLCULO DE COMISIONES Y UTILIDAD REAL
# =========================================================

def calcular_comision_vendedor(subtotal_con_margen):
    """
    Calcula la comisión del vendedor (2.5% sobre subtotal con margen)
    """
    return subtotal_con_margen * 0.025

def calcular_comision_supervisor(subtotal_con_margen):
    """
    Calcula la comisión del supervisor (0.8% sobre subtotal con margen)
    """
    return subtotal_con_margen * 0.008

def calcular_utilidad_real(margen_valor, comision_vendedor, comision_supervisor):
    """
    Calcula la utilidad real restando las comisiones del margen bruto
    Utilidad Real = Margen - Comisión Vendedor - Comisión Supervisor
    """
    return margen_valor - comision_vendedor - comision_supervisor

# =========================================================
# FUNCIÓN PARA OFUSCAR TEXTOS CON X (YA NO SE USA)
# =========================================================

def ofuscar_texto(texto):
    """
    Reemplaza la mitad del texto con 'X'
    Ejemplo: "Canal Cielo 20X 25" -> "Canal Cielo 20X XXXXX"
    """
    if not texto or len(texto) <= 3:
        return texto
    
    largo = len(texto)
    chars_visibles = largo // 2
    
    texto_visible = texto[:chars_visibles]
    texto_ofuscado = texto_visible + " " + "X" * (largo - chars_visibles)
    
    return texto_ofuscado

def ofuscar_numero(numero):
    """
    Reemplaza un número con 'X'
    Ejemplo: 1000 -> XXXX
    """
    if not numero:
        return ""
    
    num_str = str(numero)
    return "X" * len(num_str)

def ofuscar_precio(precio):
    """
    Ofusca un precio formateado
    Ejemplo: $1.000 -> $XXXX
    """
    if not precio:
        return ""
    
    if precio.startswith('$'):
        numeros = re.sub(r'[^0-9]', '', precio)
        return "$" + "X" * len(numeros)
    else:
        return "X" * len(str(precio))

# ---------------- FUNCIONES ORIGINALES ----------------

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

# =========================================================
# CONFIGURACIÓN DE BASE DE DATOS SQLITE
# =========================================================
def init_database():
    """Inicializa la base de datos SQLite"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    
    # Tabla de cotizaciones
    c.execute('''
        CREATE TABLE IF NOT EXISTS cotizaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero TEXT UNIQUE,
            fecha_creacion TEXT,
            fecha_modificacion TEXT,
            estado TEXT,
            cliente_nombre TEXT,
            cliente_rut TEXT,
            cliente_email TEXT,
            cliente_telefono TEXT,
            cliente_direccion TEXT,
            asesor_nombre TEXT,
            asesor_email TEXT,
            asesor_telefono TEXT,
            proyecto_fecha_inicio TEXT,
            proyecto_fecha_termino TEXT,
            proyecto_dias_validez INTEGER,
            proyecto_observaciones TEXT,
            productos TEXT,
            config_margen REAL,
            config_modo_admin BOOLEAN,
            total_subtotal_sin_margen REAL,
            total_subtotal_con_margen REAL,
            total_iva REAL,
            total_total REAL,
            total_margen_valor REAL,
            total_comision_vendedor REAL,
            total_comision_supervisor REAL,
            total_utilidad_real REAL
        )
    ''')
    
    conn.commit()
    conn.close()

# Llamar a init_database al inicio del programa
init_database()

# =========================================================
# FUNCIONES DE BASE DE DATOS
# =========================================================

def guardar_cotizacion(
    numero, cliente, asesor, proyecto, productos,
    config, totales
):
    """Guarda una cotización en la base de datos"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Convertir productos a JSON para almacenar
    productos_json = json.dumps(productos, ensure_ascii=False)
    
    # DEBUG: Imprimir para verificar
    print("=== GUARDANDO COTIZACIÓN ===")
    print(f"Número: {numero}")
    print(f"Margen recibido: {config.get('margen', 0)}")
    print(f"Modo Admin: {config.get('modo_admin', False)}")
    
    try:
        # La consulta tiene 27 signos de interrogación (?)
        c.execute('''
            INSERT OR REPLACE INTO cotizaciones (
                numero, fecha_creacion, fecha_modificacion, estado,
                cliente_nombre, cliente_rut, cliente_email, cliente_telefono, cliente_direccion,
                asesor_nombre, asesor_email, asesor_telefono,
                proyecto_fecha_inicio, proyecto_fecha_termino, proyecto_dias_validez, proyecto_observaciones,
                productos, config_margen, config_modo_admin,
                total_subtotal_sin_margen, total_subtotal_con_margen, total_iva, total_total,
                total_margen_valor, total_comision_vendedor, total_comision_supervisor, total_utilidad_real
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            numero,                                      # 1. numero
            fecha_actual,                                # 2. fecha_creacion
            fecha_actual,                                # 3. fecha_modificacion
            'borrador',                                  # 4. estado
            cliente.get('Nombre', ''),                   # 5. cliente_nombre
            cliente.get('RUT', ''),                      # 6. cliente_rut
            cliente.get('Correo', ''),                   # 7. cliente_email
            cliente.get('Teléfono', ''),                 # 8. cliente_telefono
            cliente.get('Dirección', ''),                # 9. cliente_direccion
            asesor.get('Nombre Ejecutivo', ''),          # 10. asesor_nombre
            asesor.get('Correo Ejecutivo', ''),          # 11. asesor_email
            asesor.get('Teléfono Ejecutivo', ''),        # 12. asesor_telefono
            proyecto.get('fecha_inicio', ''),            # 13. proyecto_fecha_inicio
            proyecto.get('fecha_termino', ''),           # 14. proyecto_fecha_termino
            proyecto.get('dias_validez', 0),             # 15. proyecto_dias_validez
            proyecto.get('observaciones', ''),           # 16. proyecto_observaciones
            productos_json,                              # 17. productos
            float(config.get('margen', 0)),              # 18. config_margen
            1 if config.get('modo_admin', False) else 0, # 19. config_modo_admin
            float(totales.get('subtotal_sin_margen', 0)), # 20. total_subtotal_sin_margen
            float(totales.get('subtotal_con_margen', 0)), # 21. total_subtotal_con_margen
            float(totales.get('iva', 0)),                 # 22. total_iva
            float(totales.get('total', 0)),               # 23. total_total
            float(totales.get('margen_valor', 0)),        # 24. total_margen_valor
            float(totales.get('comision_vendedor', 0)),   # 25. total_comision_vendedor
            float(totales.get('comision_supervisor', 0)), # 26. total_comision_supervisor
            float(totales.get('utilidad_real', 0))        # 27. total_utilidad_real
        ))
        
        conn.commit()
        print(f"✅ Cotización {numero} guardada con margen: {config.get('margen', 0)}")
        return True
    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        st.error(f"Error al guardar: {e}")
        return False
    finally:
        conn.close()

def buscar_cotizaciones(termino=None, tipo_busqueda='numero'):
    """Busca cotizaciones por número, cliente o asesor"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    
    # Ahora traemos más campos para evaluar el estado
    if termino and termino.strip():
        if tipo_busqueda == 'numero':
            c.execute('''
                SELECT numero, cliente_nombre, asesor_nombre, fecha_creacion, total_total, 
                       config_margen, cliente_rut, cliente_email, asesor_email, asesor_telefono
                FROM cotizaciones 
                WHERE numero LIKE ? 
                ORDER BY fecha_creacion DESC
            ''', (f'%{termino}%',))
        elif tipo_busqueda == 'cliente':
            c.execute('''
                SELECT numero, cliente_nombre, asesor_nombre, fecha_creacion, total_total,
                       config_margen, cliente_rut, cliente_email, asesor_email, asesor_telefono
                FROM cotizaciones 
                WHERE cliente_nombre LIKE ? 
                ORDER BY fecha_creacion DESC
            ''', (f'%{termino}%',))
        elif tipo_busqueda == 'asesor':
            c.execute('''
                SELECT numero, cliente_nombre, asesor_nombre, fecha_creacion, total_total,
                       config_margen, cliente_rut, cliente_email, asesor_email, asesor_telefono
                FROM cotizaciones 
                WHERE asesor_nombre LIKE ? 
                ORDER BY fecha_creacion DESC
            ''', (f'%{termino}%',))
    else:
        c.execute('''
            SELECT numero, cliente_nombre, asesor_nombre, fecha_creacion, total_total,
                   config_margen, cliente_rut, cliente_email, asesor_email, asesor_telefono
            FROM cotizaciones 
            ORDER BY fecha_creacion DESC 
            LIMIT 50
        ''')
    
    resultados = c.fetchall()
    conn.close()
    return resultados

def cargar_cotizacion(numero):
    """Carga una cotización completa por su número"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    
    c.execute('SELECT * FROM cotizaciones WHERE numero = ?', (numero,))
    row = c.fetchone()
    
    if row:
        # Obtener nombres de columnas
        c.execute('PRAGMA table_info(cotizaciones)')
        columnas = [col[1] for col in c.fetchall()]
        
        # Crear diccionario con los datos
        cotizacion = dict(zip(columnas, row))
        
        # Parsear productos de JSON
        cotizacion['productos'] = json.loads(cotizacion['productos'])
        
        conn.close()
        return cotizacion
    
    conn.close()
    return None

def eliminar_cotizacion(numero):
    """Elimina una cotización de la base de datos"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    c.execute('DELETE FROM cotizaciones WHERE numero = ?', (numero,))
    conn.commit()
    conn.close()

def actualizar_estado_cotizacion(numero, estado):
    """Actualiza el estado de una cotización"""
    conn = sqlite3.connect('cotizaciones.db')
    c = conn.cursor()
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        UPDATE cotizaciones 
        SET estado = ?, fecha_modificacion = ? 
        WHERE numero = ?
    ''', (estado, fecha_actual, numero))
    conn.commit()
    conn.close()

# =========================================================
# FUNCIÓN PARA CARGAR COTIZACIÓN EN EL SISTEMA
# =========================================================
def preparar_carga_cotizacion(numero_cotizacion):
    """Prepara la carga de una cotización verificando permisos"""
    cotizacion = cargar_cotizacion(numero_cotizacion)
    if cotizacion:
        # Verificar si tiene margen y el usuario NO es admin
        tiene_margen = cotizacion.get('config_margen', 0) > 0
        if tiene_margen and not st.session_state.modo_admin:
            # ❌ Ejecutivo intentando cargar cotización con margen - DENEGADO
            return False
        else:
            # ✅ Admin o cotización sin margen - PERMITIDO
            st.session_state.cotizacion_a_cargar = cotizacion
            st.session_state.cargar_cotizacion_trigger = True
            return True
    return False

def ejecutar_carga_cotizacion():
    """Ejecuta la carga de la cotización (se llama AL INICIO del script)"""
    if st.session_state.cargar_cotizacion_trigger and st.session_state.cotizacion_a_cargar:
        cotizacion = st.session_state.cotizacion_a_cargar
        
        # Mostrar qué cotización se está cargando
        print(f"\n{'='*50}")
        print(f"🔄 CARGANDO COTIZACIÓN: {cotizacion.get('numero', '')}")
        print(f"{'='*50}")
        
        # ===== CARGAR PRODUCTOS EN EL CARRITO =====
        st.session_state.carrito = cotizacion['productos']
        print(f"✓ Productos cargados: {len(st.session_state.carrito)} items")
        
        # ===== CARGAR DATOS DEL CLIENTE =====
        st.session_state.nombre_input = cotizacion.get('cliente_nombre', '')
        print(f"✓ Nombre cliente: {st.session_state.nombre_input}")
        
        # RUT
        rut_valor = cotizacion.get('cliente_rut', '')
        st.session_state.rut_display = rut_valor
        st.session_state.rut_raw = re.sub(r'[^0-9kK]', '', rut_valor)
        print(f"✓ RUT: {st.session_state.rut_display}")
        
        # Validar RUT si tiene datos
        if st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            valido, mensaje = validar_rut(st.session_state.rut_raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje
        else:
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = "RUT incompleto"
        
        # CORREO y TELÉFONO del cliente
        st.session_state.correo_input = cotizacion.get('cliente_email', '')
        st.session_state.telefono_raw = cotizacion.get('cliente_telefono', '')
        st.session_state.direccion_input = cotizacion.get('cliente_direccion', '')
        print(f"✓ Email: {st.session_state.correo_input}")
        print(f"✓ Teléfono: {st.session_state.telefono_raw}")
        
        # ===== CARGAR DATOS DEL ASESOR =====
        nombre_asesor = cotizacion.get('asesor_nombre', '')
        
        # Guardar el nombre del asesor
        st.session_state.asesor_seleccionado = nombre_asesor if nombre_asesor else "Seleccionar asesor"
        st.session_state.correo_asesor = cotizacion.get('asesor_email', '')
        st.session_state.telefono_asesor = cotizacion.get('asesor_telefono', '')
        print(f"✓ Asesor: {st.session_state.asesor_seleccionado}")
        
        # ===== CARGAR FECHAS DEL PROYECTO =====
        if cotizacion.get('proyecto_fecha_inicio'):
            try:
                st.session_state.fecha_inicio = datetime.strptime(cotizacion['proyecto_fecha_inicio'], '%Y-%m-%d').date()
            except:
                st.session_state.fecha_inicio = datetime.now().date()
        else:
            st.session_state.fecha_inicio = datetime.now().date()
        
        if cotizacion.get('proyecto_fecha_termino'):
            try:
                st.session_state.fecha_termino = datetime.strptime(cotizacion['proyecto_fecha_termino'], '%Y-%m-%d').date()
            except:
                st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
        else:
            st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
        
        st.session_state.observaciones_input = cotizacion.get('proyecto_observaciones', '')
        
        # ===== CARGAR CONFIGURACIÓN =====
        st.session_state.modo_admin = bool(cotizacion.get('config_modo_admin', False))
        
        # ===== CARGAR MARGEN - CON VERSIÓN FORZADA =====
        margen_valor = cotizacion.get('config_margen')
        print(f"🔍 Valor de margen desde BD: {margen_valor} (tipo: {type(margen_valor)})")
        
        if margen_valor is not None:
            try:
                # Convertir a float y asegurar que sea un número válido
                nuevo_margen = float(margen_valor)
                st.session_state.margen = nuevo_margen
                print(f"✅ MARGEN CARGADO: {nuevo_margen}%")
            except (ValueError, TypeError) as e:
                print(f"❌ Error al convertir margen: {e}")
                st.session_state.margen = 0.0
        else:
            print(f"⚠️ Margen no encontrado, estableciendo a 0")
            st.session_state.margen = 0.0
        
        # Verificar los totales calculados en la BD
        print(f"\n📊 Totales desde BD:")
        print(f"   - Subtotal sin margen: {cotizacion.get('total_subtotal_sin_margen', 0)}")
        print(f"   - Subtotal con margen: {cotizacion.get('total_subtotal_con_margen', 0)}")
        print(f"   - Margen valor: {cotizacion.get('total_margen_valor', 0)}")
        
        # Guardar el número de la cotización cargada
        st.session_state.cotizacion_cargada = cotizacion.get('numero', '')
        print(f"✓ Cotización cargada: {st.session_state.cotizacion_cargada}")
        
        # ===== INCREMENTAR COUNTER PARA FORZAR RECREACIÓN DE WIDGETS =====
        st.session_state.counter += 100  # Incremento grande para asegurar cambio
        print(f"✅ COUNTER NUEVO: {st.session_state.counter}")
        print(f"{'='*50}\n")
        
        # Resetear el trigger
        st.session_state.cargar_cotizacion_trigger = False
        st.session_state.cotizacion_a_cargar = None
        
        return True
    return False

# =========================================================
# EJECUTAR CARGA DE COTIZACIÓN SI HAY TRIGGER
# =========================================================
ejecutar_carga_cotizacion()

# =========================================================
# CSS PERSONALIZADO - CON CORRECCIONES DE MODO CLARO
# =========================================================
st.markdown("""
<style>
    /* =========================================================
       IMPORTAR FUENTES PROFESIONALES
    ========================================================= */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* =========================================================
       RESET Y VARIABLES GLOBALES
    ========================================================= */
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* =========================================================
       VARIABLES MODO CLARO (TONOS PASTEL SUAVES)
    ========================================================= */
    :root, .stApp {
        --bg-primary: #f8fafc;
        --bg-secondary: #ffffff;
        --bg-card: #ffffff;
        --text-primary: #0f172a;
        --text-secondary: #334155;
        --text-tertiary: #475569;
        --accent-primary: #3b82f6;
        --accent-secondary: #8b5cf6;
        --accent-success: #10b981;
        --accent-warning: #f59e0b;
        --accent-danger: #ef4444;
        --accent-glow: rgba(59, 130, 246, 0.1);
        --border-light: #e2e8f0;
        --border-medium: #cbd5e1;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.05);
        --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.05);
        --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.05);
        --input-bg: #ffffff;
        --input-border: #cbd5e1;
        --input-text: #0f172a;
        --button-bg: #ffffff;
        --button-border: #cbd5e1;
        --button-text: #0f172a;
        --button-hover-bg: #f1f5f9;
        --metric-bg: linear-gradient(135deg, #ffffff, #f8fafc);
        --tab-text: #334155;
        --tab-hover: #0f172a;
        --tab-active: #3b82f6;
    }
    
    /* =========================================================
       VARIABLES MODO OSCURO (SE MANTIENEN IGUAL)
    ========================================================= */
    @media (prefers-color-scheme: dark) {
        :root, .stApp {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-tertiary: #94a3b8;
            --accent-primary: #60a5fa;
            --accent-secondary: #c084fc;
            --accent-success: #34d399;
            --accent-warning: #fbbf24;
            --accent-danger: #f87171;
            --accent-glow: rgba(96, 165, 250, 0.15);
            --border-light: #334155;
            --border-medium: #475569;
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.3);
            --shadow-lg: 0 10px 15px -3px rgba(0,0,0,0.3);
            --input-bg: #1e293b;
            --input-border: #334155;
            --input-text: #f8fafc;
            --button-bg: #1e293b;
            --button-border: #334155;
            --button-text: #f8fafc;
            --button-hover-bg: #334155;
            --metric-bg: linear-gradient(135deg, #1e293b, #0f172a);
            --tab-text: #cbd5e1;
            --tab-hover: #f8fafc;
            --tab-active: #60a5fa;
        }
    }
    
    /* =========================================================
       CORRECCIONES ESPECÍFICAS PARA MODO CLARO
    ========================================================= */
    @media (prefers-color-scheme: light) {
        /* Textos de pestañas */
        .stTabs [data-baseweb="tab"] {
            color: #334155 !important;
            font-weight: 500 !important;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            color: #0f172a !important;
        }
        
        .stTabs [aria-selected="true"] {
            color: #3b82f6 !important;
            font-weight: 600 !important;
        }
        
        /* Subtítulo */
        .sub-title {
            color: #475569 !important;
        }
        
        /* Inputs y selects */
        .stTextInput input, 
        .stSelectbox select, 
        .stDateInput input {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
        }
        
        .stTextInput input:focus, 
        .stSelectbox select:focus, 
        .stDateInput input:focus {
            border-color: #3b82f6 !important;
            box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
        }
        
        /* Botones normales */
        .stButton button {
            background-color: #ffffff !important;
            color: #0f172a !important;
            border: 1px solid #cbd5e1 !important;
        }
        
        .stButton button:hover {
            background-color: #f1f5f9 !important;
            border-color: #3b82f6 !important;
            color: #3b82f6 !important;
        }
        
        /* Botón Guardar (primary) */
        .stButton button[kind="primary"] {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
            color: white !important;
            border: none !important;
        }
        
        .stButton button[kind="primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3) !important;
        }
        
        /* Botones de descarga */
        .stDownloadButton button {
            background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
            color: white !important;
            border: none !important;
        }
        
        .stDownloadButton button:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(59, 130, 246, 0.3) !important;
        }
        
        /* Tarjetas de métricas */
        .metric-card {
            background: linear-gradient(135deg, #ffffff, #f8fafc) !important;
            border: 1px solid #e2e8f0 !important;
        }
        
        .metric-title {
            color: #475569 !important;
        }
        
        .metric-value {
            color: #0f172a !important;
        }
        
        /* Estadísticas rápidas */
        .stats-card {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
        }
        
        .stats-title {
            color: #475569 !important;
        }
        
        .stats-number.total { color: #3b82f6 !important; }
        .stats-number.autorizadas { color: #10b981 !important; }
        .stats-number.borradores { color: #f59e0b !important; }
        .stats-number.incompletas { color: #ef4444 !important; }
        
        .stats-desc {
            color: #64748b !important;
        }
        
        /* Labels de inputs */
        .stTextInput label, 
        .stSelectbox label, 
        .stDateInput label {
            color: #475569 !important;
            font-weight: 500 !important;
        }
    }
    
    /* =========================================================
       HEADER - LOGO DERECHA, ADMIN DEBAJO
    ========================================================= */
    .header-container {
        background: var(--bg-secondary);
        border-radius: 16px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        border: 1px solid var(--border-light);
        box-shadow: var(--shadow-md);
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    
    .header-left {
        flex: 1;
    }
    
    .header-right {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0.5rem;
    }
    
    .main-title {
        font-size: 2rem !important;
        font-weight: 700;
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }
    
    .sub-title {
        color: var(--text-secondary);
        font-size: 0.9rem;
        font-weight: 400;
        margin-top: 0.2rem;
    }
    
    .logo-glossy {
        max-width: 120px;
        max-height: 45px;
        object-fit: contain;
        filter: drop-shadow(0 2px 4px rgba(0,0,0,0.1));
    }
    
    /* =========================================================
       BADGE DE COTIZACIÓN CARGADA CON BOTÓN CERRAR
    ========================================================= */
    .cotizacion-status-container {
        background: var(--bg-card);
        border-radius: 40px;
        padding: 0.5rem 1rem 0.5rem 1.5rem;
        margin-bottom: 1rem;
        border: 1px solid var(--border-light);
        box-shadow: var(--shadow-sm);
        display: inline-flex;
        align-items: center;
        gap: 1rem;
    }
    
    .status-badge {
        font-size: 0.9rem;
        font-weight: 500;
        color: var(--text-primary);
    }
    
    .btn-cerrar {
        background: var(--button-bg);
        border: 1px solid var(--border-medium);
        color: var(--text-secondary);
        border-radius: 30px;
        padding: 0.4rem 1.2rem;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s ease;
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
    }
    
    .btn-cerrar:hover {
        background: var(--accent-danger);
        border-color: var(--accent-danger);
        color: white;
    }
    
    /* =========================================================
       TABS MEJORADAS
    ========================================================= */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem !important;
        border-bottom: 1px solid var(--border-light) !important;
        padding: 0 0.5rem !important;
        margin-bottom: 1.5rem !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        padding: 0.6rem 0 !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.2s ease !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text-primary) !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: var(--accent-primary) !important;
        border-bottom-color: var(--accent-primary) !important;
        font-weight: 600 !important;
    }
    
    /* =========================================================
       TABLA DE RESULTADOS
    ========================================================= */
    .resultados-table {
        width: 100%;
        border-collapse: collapse;
        font-family: 'Inter', sans-serif;
        font-size: 0.9rem;
        border: 1px solid var(--border-light);
        border-radius: 12px;
        overflow: hidden;
        box-shadow: var(--shadow-sm);
        background: var(--bg-card);
    }
    
    .resultados-table th {
        background-color: var(--bg-secondary);
        color: var(--text-primary);
        font-weight: 600;
        padding: 12px;
        text-align: left;
        border-bottom: 2px solid var(--border-light);
    }
    
    .resultados-table td {
        padding: 10px 12px;
        border-bottom: 1px solid var(--border-light);
        color: var(--text-secondary);
    }
    
    .resultados-table tr:hover {
        background-color: var(--bg-primary);
    }
    
    /* =========================================================
       TARJETAS DE MÉTRICAS
    ========================================================= */
    .metric-card {
        background: var(--metric-bg);
        border-radius: 16px;
        padding: 1.25rem;
        box-shadow: var(--shadow-sm);
        border: 1px solid var(--border-light);
        transition: all 0.2s ease;
        height: 100%;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-md);
        border-color: var(--border-medium);
    }
    
    .metric-title {
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--text-tertiary);
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
        color: var(--text-primary);
    }
    
    .metric-change {
        font-size: 0.8rem;
        color: var(--text-tertiary);
    }
    
    .metric-card-special {
        border-radius: 20px;
        padding: 1.5rem;
        box-shadow: var(--shadow-md);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .metric-card-special:hover {
        transform: translateY(-3px);
        box-shadow: var(--shadow-lg);
    }
    
    .metric-card-total {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    }
    
    .metric-card-comisiones {
        background: linear-gradient(135deg, #f59e0b, #d97706);
    }
    
    .metric-card-utilidad {
        background: linear-gradient(135deg, #10b981, #059669);
    }
    
    /* =========================================================
       ESTADÍSTICAS RÁPIDAS
    ========================================================= */
    .stats-card {
        background: var(--metric-bg);
        border-radius: 20px;
        padding: 1.5rem;
        border: 1px solid var(--border-light);
        box-shadow: var(--shadow-md);
        transition: transform 0.2s ease;
        height: 100%;
    }
    
    .stats-card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-lg);
    }
    
    .stats-title {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-secondary);
        margin-bottom: 0.5rem;
        letter-spacing: 0.5px;
    }
    
    .stats-number {
        font-size: 2.8rem;
        font-weight: 700;
        line-height: 1.2;
        margin: 0.5rem 0;
        letter-spacing: -0.02em;
        border-top: 2px solid var(--border-medium);
        border-bottom: 2px solid var(--border-medium);
        padding: 0.5rem 0;
        text-align: center;
    }
    
    .stats-desc {
        font-size: 0.85rem;
        color: var(--text-tertiary);
        margin-top: 0.5rem;
        text-align: center;
        line-height: 1.4;
    }
    
    /* =========================================================
       BOTONES
    ========================================================= */
    .stButton button {
        font-family: 'Inter', sans-serif !important;
        background: var(--button-bg) !important;
        color: var(--button-text) !important;
        border: 1px solid var(--button-border) !important;
        border-radius: 40px !important;
        padding: 0.6rem 1.2rem !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    .stButton button:hover {
        background: var(--button-hover-bg) !important;
        border-color: var(--accent-primary) !important;
        color: var(--accent-primary) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-md) !important;
    }
    
    .stDownloadButton button {
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 40px !important;
        padding: 0.6rem 1.5rem !important;
        font-size: 0.9rem !important;
        box-shadow: 0 4px 10px -4px var(--accent-glow) !important;
        transition: all 0.2s ease !important;
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 16px -6px var(--accent-glow) !important;
    }
    
    /* =========================================================
       INPUTS
    ========================================================= */
    .stTextInput input, 
    .stSelectbox select, 
    .stDateInput input {
        font-family: 'Inter', sans-serif !important;
        background: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 12px !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
    }
    
    .stTextInput input:focus, 
    .stSelectbox select:focus, 
    .stDateInput input:focus {
        border-color: var(--accent-primary) !important;
        box-shadow: 0 0 0 3px var(--accent-glow) !important;
        outline: none !important;
    }
    
    .stTextInput label, 
    .stSelectbox label, 
    .stDateInput label {
        font-size: 0.8rem !important;
        font-weight: 500 !important;
        color: var(--text-tertiary) !important;
        margin-bottom: 0.2rem !important;
    }
    
    /* =========================================================
       EXPANDER
    ========================================================= */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
        background: var(--bg-secondary) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border-light) !important;
        padding: 0.7rem 1rem !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    /* =========================================================
       PROGRESS BAR
    ========================================================= */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)) !important;
        border-radius: 20px !important;
        height: 6px !important;
    }
    
    /* =========================================================
       DIVISORES
    ========================================================= */
    hr {
        margin: 1.5rem 0 !important;
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--border-medium), transparent) !important;
    }
    
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER REDISEÑADO - LOGO DERECHA, ADMIN DEBAJO
# =========================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)

col_left, col_right = st.columns([3, 1])

with col_left:
    st.markdown('<div class="header-left">', unsafe_allow_html=True)
    st.markdown('<span class="main-title">Cotizador PRO</span>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Sistema profesional de cotizaciones</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with col_right:
    st.markdown('<div class="header-right">', unsafe_allow_html=True)
    try:
        st.image("logo.png", width=120)
    except:
        st.markdown("""
        <svg class="logo-glossy" width="120" height="45" viewBox="0 0 120 45" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="120" height="45" rx="8" fill="url(#gradient)" />
            <path d="M24 15L30 20L24 25L18 20L24 15Z" fill="white" />
            <circle cx="60" cy="20" r="5" fill="#FFD966" />
            <text x="80" y="24" font-family="Inter" font-size="12" font-weight="600" fill="white">PRO</text>
            <defs>
                <linearGradient id="gradient" x1="0" y1="0" x2="120" y2="45" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#3B82F6"/>
                    <stop offset="1" stop-color="#8B5CF6"/>
                </linearGradient>
            </defs>
        </svg>
        """, unsafe_allow_html=True)
    
    if st.session_state.modo_admin:
        st.markdown('<div style="display: flex; align-items: center; gap: 0.5rem; margin-top: 0.5rem;">', unsafe_allow_html=True)
        st.markdown('<span class="modo-admin-indicator">👑 Admin Activo</span>', unsafe_allow_html=True)
        if st.button("🔓 Cerrar", key="btn_cerrar_sesion_header", use_container_width=False):
            st.session_state.modo_admin = False
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        with st.popover("🔐 Admin", use_container_width=False):
            st.markdown("### Acceso Administrativo")
            st.markdown("Ingrese su clave de autorización:")
            clave_input = st.text_input("Clave", type="password", key="clave_admin_header", label_visibility="collapsed")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Cancelar", use_container_width=True):
                    st.rerun()
            with col2:
                if st.button("Acceder", use_container_width=True, type="primary"):
                    if clave_input == CLAVE_ADMIN:
                        st.session_state.modo_admin = True
                        st.success("✅ Acceso concedido")
                        st.rerun()
                    else:
                        st.error("❌ Clave incorrecta")
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# BADGE DE COTIZACIÓN CARGADA (CON BOTÓN CERRAR)
# =========================================================
if st.session_state.cotizacion_cargada:
    badge_html = ""
    if st.session_state.margen > 0:
        datos_completos = all([
            st.session_state.nombre_input,
            st.session_state.rut_display,
            st.session_state.correo_input
        ])
        asesor_completo = any([
            st.session_state.asesor_seleccionado != "Seleccionar asesor",
            st.session_state.correo_asesor,
            st.session_state.telefono_asesor
        ])
        
        if datos_completos and asesor_completo:
            if st.session_state.modo_admin:
                badge_html = f"👑 Admin • 🟢 AUTORIZADO ({st.session_state.margen}%)"
            else:
                badge_html = f"🔒 Solo lectura • 🟢 AUTORIZADO ({st.session_state.margen}%)"
        else:
            badge_html = f"⚠️ {st.session_state.cotizacion_cargada} • 🔴 INCOMPLETO"
    else:
        datos_completos = all([
            st.session_state.nombre_input,
            st.session_state.rut_display,
            st.session_state.correo_input
        ])
        asesor_completo = any([
            st.session_state.asesor_seleccionado != "Seleccionar asesor",
            st.session_state.correo_asesor,
            st.session_state.telefono_asesor
        ])
        
        if datos_completos and asesor_completo:
            badge_html = f"📝 {st.session_state.cotizacion_cargada} • 🟡 BORRADOR"
        else:
            badge_html = f"⚠️ {st.session_state.cotizacion_cargada} • 🔴 INCOMPLETO"
    
    col_badge, col_cerrar = st.columns([3, 1])
    with col_badge:
        st.markdown(f'<div class="cotizacion-status-container"><span class="status-badge">{badge_html}</span></div>', unsafe_allow_html=True)
    with col_cerrar:
        if st.button("🗑️ Cerrar Cotización", key="btn_cerrar_cotizacion", use_container_width=True):
            procesar_cambio_rut()
            procesar_cambio_telefono()
            
            numero_guardar = st.session_state.cotizacion_cargada
            if numero_guardar:
                datos_cliente_guardar = {
                    "Nombre": st.session_state.nombre_input or "",
                    "RUT": st.session_state.rut_display or "",
                    "Correo": st.session_state.correo_input or "",
                    "Teléfono": st.session_state.telefono_raw or "",
                    "Dirección": st.session_state.direccion_input or "",
                    "Observaciones": st.session_state.observaciones_input or ""
                }
                
                nombre_asesor_guardar = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
                
                datos_asesor_guardar = {
                    "Nombre Ejecutivo": nombre_asesor_guardar,
                    "Correo Ejecutivo": st.session_state.correo_asesor or "",
                    "Teléfono Ejecutivo": st.session_state.telefono_asesor or ""
                }
                
                proyecto = {
                    'fecha_inicio': str(st.session_state.fecha_inicio),
                    'fecha_termino': str(st.session_state.fecha_termino),
                    'dias_validez': (st.session_state.fecha_termino - st.session_state.fecha_inicio).days,
                    'observaciones': st.session_state.observaciones_input
                }
                
                config = {
                    'margen': st.session_state.margen,
                    'modo_admin': st.session_state.modo_admin
                }
                
                if st.session_state.carrito:
                    carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                    subtotal_base_temp = carrito_df_temp["Subtotal"].sum()
                    
                    if st.session_state.modo_admin:
                        subtotal_general_temp = 0
                        for item in st.session_state.carrito:
                            precio_con_margen = aplicar_margen(item["Precio Unitario"], st.session_state.margen)
                            subtotal_general_temp += item["Cantidad"] * precio_con_margen
                        iva_temp = subtotal_general_temp * 0.19
                        total_temp = subtotal_general_temp + iva_temp
                        margen_valor_temp = subtotal_general_temp - subtotal_base_temp
                        comision_vendedor_temp = subtotal_general_temp * 0.025
                        comision_supervisor_temp = subtotal_general_temp * 0.008
                        utilidad_real_temp = margen_valor_temp - comision_vendedor_temp - comision_supervisor_temp
                    else:
                        subtotal_general_temp = subtotal_base_temp
                        iva_temp = subtotal_general_temp * 0.19
                        total_temp = subtotal_general_temp + iva_temp
                        margen_valor_temp = 0
                        comision_vendedor_temp = 0
                        comision_supervisor_temp = 0
                        utilidad_real_temp = 0
                else:
                    subtotal_base_temp = 0
                    subtotal_general_temp = 0
                    iva_temp = 0
                    total_temp = 0
                    margen_valor_temp = 0
                    comision_vendedor_temp = 0
                    comision_supervisor_temp = 0
                    utilidad_real_temp = 0
                
                totales = {
                    'subtotal_sin_margen': subtotal_base_temp,
                    'subtotal_con_margen': subtotal_general_temp,
                    'iva': iva_temp,
                    'total': total_temp,
                    'margen_valor': margen_valor_temp,
                    'comision_vendedor': comision_vendedor_temp,
                    'comision_supervisor': comision_supervisor_temp,
                    'utilidad_real': utilidad_real_temp
                }
                
                guardar_cotizacion(
                    numero_guardar,
                    datos_cliente_guardar,
                    datos_asesor_guardar,
                    proyecto,
                    st.session_state.carrito,
                    config,
                    totales
                )
            
            st.session_state.carrito = []
            st.session_state.nombre_input = ""
            st.session_state.rut_raw = ""
            st.session_state.rut_display = ""
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = ""
            st.session_state.correo_input = ""
            st.session_state.telefono_raw = ""
            st.session_state.direccion_input = ""
            st.session_state.asesor_seleccionado = "Seleccionar asesor"
            st.session_state.correo_asesor = ""
            st.session_state.telefono_asesor = ""
            st.session_state.fecha_inicio = datetime.now().date()
            st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
            st.session_state.observaciones_input = ""
            st.session_state.cotizacion_cargada = None
            st.session_state.cotizacion_seleccionada = None
            st.session_state.margen = 0.0
            st.session_state.counter += 100
            
            st.success("✅ Cotización guardada y cerrada. Listo para nueva cotización.")
            st.rerun()

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3 = st.tabs(["📋 COTIZACIÓN", "👤 DATOS", "📂 COTIZACIONES"])

# =========================================================
# FUNCIÓN PARA GENERAR PDF COMPLETO (CON LOGO Y TABLA DETALLADA)
# =========================================================

def generar_pdf_completo(carrito_df, subtotal, iva, total, datos_cliente,
                     fecha_inicio, fecha_termino, dias_validez,
                     datos_asesor, margen=0, numero_cotizacion=None):

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
    
    styles.add(ParagraphStyle(
        name='NotasEstilo',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        leftIndent=0,
        alignment=0,
        textColor=colors.grey,
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalLabel',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalValue',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalBold',
        parent=styles['Normal'],
        fontSize=12,
        leading=16,
        alignment=2,
        fontName='Helvetica-Bold',
        spaceAfter=2,
        textColor=colors.black
    ))

    # =========================================================
    # LOGO
    # =========================================================
    try:
        logo = Image("logo.png")
        max_width = 2 * inch
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
        elements.append(Paragraph("<b># ESPACIO</b>", styles['TituloPresupuesto']))
        elements.append(Spacer(1, 10))

    # USAR EL NÚMERO PROPORCIONADO O GENERAR UNO NUEVO
    if numero_cotizacion:
        numero_presupuesto = numero_cotizacion
    else:
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
    # TABLA DE PRODUCTOS (DETALLADA)
    # =========================================================
    
    ancho_total = doc.width
    porcentajes = [15, 50, 8, 13.5, 13.5]
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
    
    # Filas de datos (todos los items)
    for _, row in carrito_df.iterrows():
        categoria = row["Categoria"]
        item = row["Item"]
        cantidad = str(row["Cantidad"])
        precio_unitario = formato_clp(row["Precio Unitario"])
        subtotal_item = formato_clp(row["Subtotal"])
        
        data.append([
            Paragraph(categoria, styles['SmallFont']),
            Paragraph(item, styles['SmallFont']),
            Paragraph(cantidad, styles['SmallFont']),
            Paragraph(precio_unitario, styles['SmallFont']),
            Paragraph(subtotal_item, styles['SmallFont'])
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
    
    for i in range(1, len(data)):
        if i % 2 == 0:
            tabla_productos.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))
            ]))

    elements.append(tabla_productos)
    elements.append(Spacer(1, 20))
    
    # =========================================================
    # BLOQUES: NOTAS Y TOTALES
    # =========================================================
    
    ancho_bloque = (doc.width - 20) / 2
    
    if margen > 0:
        texto_transporte = "2.- Transporte y bases de apoyo <b>incluidos</b>."
    else:
        texto_transporte = "2.- Transporte y bases de apoyo <b>no incluidos</b>."
    
    notas_texto = f"""
    <b>NOTAS IMPORTANTES:</b><br/>
    1.- Valores incluyen IVA.<br/>
    {texto_transporte}<br/>
    3.- Formas de pago: transferencia - pago contado.<br/>
    4.- Proceso de pagos: 50% inicial - 25% obra - 25% entrega.
    """
    
    bloque_notas = Paragraph(notas_texto, styles['NotasEstilo'])
    
    totales_data = [
        [Paragraph("Subtotal:", styles['TotalLabel']), Paragraph(formato_clp(subtotal), styles['TotalValue'])],
        [Paragraph("IVA (19%):", styles['TotalLabel']), Paragraph(formato_clp(iva), styles['TotalValue'])],
        [Paragraph("TOTAL:", styles['TotalBold']), Paragraph(formato_clp(total), styles['TotalBold'])]
    ]
    
    totales_tabla = Table(totales_data, colWidths=[100, 120])
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (1, 1), (1, 1), 1, colors.grey),
        ('LINEABOVE', (1, 2), (1, 2), 2, colors.black),
    ]))
    
    data_bloques = [[bloque_notas, totales_tabla]]
    tabla_bloques = Table(data_bloques, colWidths=[ancho_bloque, ancho_bloque])
    tabla_bloques.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    
    elements.append(tabla_bloques)

    doc.build(elements)
    buffer.seek(0)
    return buffer, numero_presupuesto

# =========================================================
# FUNCIÓN PARA GENERAR PDF CLIENTE (RESUMIDO)
# =========================================================

def generar_pdf_cliente(carrito_df, subtotal, iva, total, datos_cliente,
                     fecha_inicio, fecha_termino, dias_validez,
                     datos_asesor, margen=0, numero_cotizacion=None):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=20, rightMargin=20,
                           topMargin=30, bottomMargin=30,
                           allowSplitting=1)
    elements = []
    styles = getSampleStyleSheet()
    
    # Crear estilos personalizados (MISMOS QUE PDF COMPLETO)
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
    
    styles.add(ParagraphStyle(
        name='NotasEstilo',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        leftIndent=0,
        alignment=0,
        textColor=colors.grey,
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalLabel',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalValue',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalBold',
        parent=styles['Normal'],
        fontSize=12,
        leading=16,
        alignment=2,
        fontName='Helvetica-Bold',
        spaceAfter=2,
        textColor=colors.black
    ))

    # =========================================================
    # LOGO
    # =========================================================
    try:
        logo = Image("logo.png")
        max_width = 2 * inch
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
        elements.append(Paragraph("<b># ESPACIO</b>", styles['TituloPresupuesto']))
        elements.append(Spacer(1, 10))

    # USAR EL NÚMERO PROPORCIONADO O GENERAR UNO NUEVO
    if numero_cotizacion:
        numero_presupuesto = numero_cotizacion
    else:
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
    # DATOS DEL CLIENTE Y ASESOR (COMPLETOS, IGUAL QUE PDF COMPLETO)
    # =========================================================
    
    ancho_columna = (doc.width - 20) / 2
    
    data_cliente_asesor = []
    
    # Encabezados
    data_cliente_asesor.append([
        Paragraph("<b>DATOS DEL CLIENTE</b>", styles['TituloSeccion']),
        Paragraph("<b>DATOS DEL ASESOR</b>", styles['TituloSeccion'])
    ])
    
    # Preparar datos del cliente (TODOS los campos)
    cliente_text = ""
    for campo, valor in datos_cliente.items():
        if valor:
            cliente_text += f"<b>{campo}:</b> {valor}<br/>"
    
    # Preparar datos del asesor (TODOS los campos)
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
    # RESUMEN POR CATEGORÍA (CON AJUSTE DE TEXTO)
    # =========================================================
    elements.append(Paragraph("<b>RESUMEN POR CATEGORÍA:</b>", styles['TituloSeccion']))
    elements.append(Spacer(1, 10))
    
    # Agrupar items por categoría
    categorias = carrito_df.groupby('Categoria')
    
    # Preparar datos para la tabla de resumen
    data_resumen = []
    
    for categoria, grupo in categorias:
        total_categoria = grupo['Subtotal'].sum()
        items_lista = grupo['Item'].tolist()
        
        # Crear descripción con los items (limitada para que no se desborde)
        if len(items_lista) > 2:
            descripcion = f"Incluye: {', '.join(items_lista[:2])} y {len(items_lista)-2} más"
        else:
            descripcion = f"Incluye: {', '.join(items_lista)}"
        
        # Limitar longitud de la descripción para evitar desbordamiento
        if len(descripcion) > 60:
            descripcion = descripcion[:57] + "..."
        
        data_resumen.append([categoria, descripcion, formato_clp(total_categoria)])
    
    # Crear tabla de resumen con el mismo estilo que la tabla de productos
    ancho_categoria = doc.width * 0.20  # 20% para categoría
    ancho_descripcion = doc.width * 0.55  # 55% para descripción (más espacio)
    ancho_total = doc.width * 0.25  # 25% para total
    
    # Encabezados
    headers = [
        Paragraph("<b>Categoría</b>", styles['HeaderStyle']),
        Paragraph("<b>Descripción</b>", styles['HeaderStyle']),
        Paragraph("<b>Total</b>", styles['HeaderStyle'])
    ]
    
    tabla_resumen = Table([headers] + data_resumen, 
                          colWidths=[ancho_categoria, ancho_descripcion, ancho_total],
                          repeatRows=1)
    
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.black),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ('WORDWRAP', (1, 1), (1, -1), 'CJK'),  # Forzar word wrap en columna de descripción
    ]))
    
    # Colorear filas alternadas
    for i in range(1, len(data_resumen) + 1):
        if i % 2 == 0:
            tabla_resumen.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))
            ]))
    
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 20))
    
    # =========================================================
    # BLOQUES: NOTAS Y TOTALES (IGUAL QUE PDF COMPLETO)
    # =========================================================
    
    ancho_bloque = (doc.width - 20) / 2
    
    if margen > 0:
        texto_transporte = "2.- Transporte y bases de apoyo <b>incluidos</b>."
    else:
        texto_transporte = "2.- Transporte y bases de apoyo <b>no incluidos</b>."
    
    notas_texto = f"""
    <b>NOTAS IMPORTANTES:</b><br/>
    1.- Valores incluyen IVA.<br/>
    {texto_transporte}<br/>
    3.- Formas de pago: transferencia - pago contado.<br/>
    4.- Proceso de pagos: 50% inicial - 25% obra - 25% entrega.
    """
    
    bloque_notas = Paragraph(notas_texto, styles['NotasEstilo'])
    
    totales_data = [
        [Paragraph("Subtotal:", styles['TotalLabel']), Paragraph(formato_clp(subtotal), styles['TotalValue'])],
        [Paragraph("IVA (19%):", styles['TotalLabel']), Paragraph(formato_clp(iva), styles['TotalValue'])],
        [Paragraph("TOTAL:", styles['TotalBold']), Paragraph(formato_clp(total), styles['TotalBold'])]
    ]
    
    totales_tabla = Table(totales_data, colWidths=[100, 120])
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (1, 1), (1, 1), 1, colors.grey),
        ('LINEABOVE', (1, 2), (1, 2), 2, colors.black),
    ]))
    
    data_bloques = [[bloque_notas, totales_tabla]]
    tabla_bloques = Table(data_bloques, colWidths=[ancho_bloque, ancho_bloque])
    tabla_bloques.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (1, 0), (1, 0), 0),
    ]))
    
    elements.append(tabla_bloques)

    doc.build(elements)
    buffer.seek(0)
    return buffer, numero_presupuesto

# =========================================================
# FUNCIÓN PARA LIMPIAR TODO (NUEVA COTIZACIÓN)
# =========================================================
def limpiar_todo():
    """Limpia todos los campos para una nueva cotización"""
    st.session_state.carrito = []
    st.session_state.nombre_input = ""
    st.session_state.rut_raw = ""
    st.session_state.rut_display = ""
    st.session_state.rut_valido = False
    st.session_state.rut_mensaje = ""
    st.session_state.correo_input = ""
    st.session_state.telefono_raw = ""
    st.session_state.direccion_input = ""
    st.session_state.asesor_seleccionado = "Seleccionar asesor"
    st.session_state.correo_asesor = ""
    st.session_state.telefono_asesor = ""
    st.session_state.fecha_inicio = datetime.now().date()
    st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
    st.session_state.observaciones_input = ""
    st.session_state.cotizacion_cargada = None
    st.session_state.cotizacion_seleccionada = None
    st.session_state.margen = 0.0
    st.session_state.counter += 100

# =========================================================
# TAB 2 - DATOS CLIENTE (CON RUT OPCIONAL)
# =========================================================
with tab2:
    st.markdown("### 📋 Datos de la Cotización")
    
    # Verificar si la cotización cargada tiene margen y el usuario NO es admin
    es_solo_lectura = False
    if st.session_state.cotizacion_cargada and st.session_state.margen > 0 and not st.session_state.modo_admin:
        es_solo_lectura = True
    
    # Definir variables de fecha para usar en todo el bloque
    fecha_inicio = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino
    dias_validez = (fecha_termino - fecha_inicio).days
    
    if es_solo_lectura:
        st.warning("🔒 Esta cotización tiene márgenes aplicados. Modo solo lectura.")
        st.info("Los datos se muestran solo para referencia. No se pueden realizar modificaciones.")
        
        # Mostrar datos en modo solo lectura
        with st.container(border=True):
            st.markdown("### 👤 Datos del Cliente")
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("Nombre Completo", value=st.session_state.nombre_input, disabled=True, key="nombre_readonly")
                st.text_input("RUT", value=st.session_state.rut_display, disabled=True, key="rut_readonly")
            with col2:
                st.text_input("Correo Electrónico", value=st.session_state.correo_input, disabled=True, key="correo_readonly")
                st.text_input("Teléfono", value=st.session_state.telefono_raw, disabled=True, key="telefono_readonly")
        
        with st.container(border=True):
            st.markdown("### 📍 Dirección del Proyecto")
            st.text_input("Dirección", value=st.session_state.direccion_input, disabled=True, key="direccion_readonly")
        
        with st.container(border=True):
            st.markdown("### 👨‍💼 Asesor")
            st.text_input("Ejecutivo", value=st.session_state.asesor_seleccionado, disabled=True, key="asesor_readonly")
            st.text_input("Correo Ejecutivo", value=st.session_state.correo_asesor, disabled=True, key="correo_asesor_readonly")
            st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, disabled=True, key="telefono_asesor_readonly")
        
        with st.container(border=True):
            st.markdown("### 📅 Validez")
            col1, col2 = st.columns(2)
            with col1:
                st.date_input("Fecha de Inicio", value=fecha_inicio, disabled=True, key="fecha_inicio_readonly")
            with col2:
                st.date_input("Fecha de Término", value=fecha_termino, disabled=True, key="fecha_termino_readonly")
            st.markdown(f"**⏱️ Duración:** {dias_validez} días")
        
        st.markdown("### 📝 Observaciones")
        st.text_area("Observaciones", value=st.session_state.observaciones_input, disabled=True, height=100, key="observaciones_readonly")
        
    else:
        # Modo normal (editable)
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
            with st.container(border=True):
                st.markdown("👤 CLIENTE")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    nombre_key = f"nombre_input_{st.session_state.counter}"
                    nombre = st.text_input(
                        "Nombre Completo*", 
                        placeholder="Ej: Juan Pérez", 
                        key=nombre_key,
                        value=st.session_state.nombre_input
                    )
                    if nombre != st.session_state.nombre_input:
                        st.session_state.nombre_input = nombre
                    
                    rut_key = f"rut_input_{st.session_state.counter}"
                    st.text_input(
                        "RUT (opcional)",
                        value=st.session_state.rut_display,
                        key=rut_key,
                        placeholder="12.345.678-9",
                        on_change=procesar_cambio_rut
                    )
                    
                    if st.session_state.rut_raw:
                        if len(st.session_state.rut_raw) >= 2:
                            if st.session_state.rut_valido:
                                st.success("✅ RUT válido")
                            else:
                                st.error(f"❌ {st.session_state.rut_mensaje}")
                        else:
                            st.info("⏳ RUT incompleto")
                
                with col2:
                    correo_key = f"correo_input_{st.session_state.counter}"
                    correo = st.text_input(
                        "Correo Electrónico*", 
                        placeholder="ejemplo@correo.cl", 
                        key=correo_key,
                        value=st.session_state.correo_input
                    )
                    if correo != st.session_state.correo_input:
                        st.session_state.correo_input = correo
                    
                    if correo and "@" not in correo:
                        st.warning("⚠️ El correo debe contener @")
                    
                    telefono_key = f"telefono_input_{st.session_state.counter}"
                    st.text_input(
                        "Teléfono",
                        value=st.session_state.telefono_raw,
                        key=telefono_key,
                        placeholder="961528954 (9 dígitos)",
                        on_change=procesar_cambio_telefono
                    )
        
        with col_asesor:
            with st.container(border=True):
                st.markdown("👨‍💼 ASESOR")
                
                nombres_asesores = list(asesores.keys())
                asesor_key = f"asesor_select_{st.session_state.counter}"
                indice_actual = nombres_asesores.index(st.session_state.asesor_seleccionado) if st.session_state.asesor_seleccionado in nombres_asesores else 0
                
                asesor_elegido = st.selectbox(
                    "Seleccionar Asesor",
                    nombres_asesores,
                    index=indice_actual,
                    key=asesor_key,
                    label_visibility="collapsed"
                )
                
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
                
                if st.session_state.asesor_seleccionado != "Seleccionar asesor":
                    st.info(f"👤 Asesor seleccionado: **{st.session_state.asesor_seleccionado}**")
                
                col_a1, col_a2 = st.columns(2)
                
                with col_a1:
                    correo_key = f"asesor_correo_input_{st.session_state.counter}"
                    correo_input = st.text_input(
                        "Correo Ejecutivo*", 
                        value=st.session_state.correo_asesor,
                        placeholder="ejecutivo@empresa.cl", 
                        key=correo_key
                    )
                    
                    if correo_input and "@" not in correo_input:
                        st.warning("⚠️ El correo debe contener @")
                    
                    if correo_input != st.session_state.correo_asesor:
                        st.session_state.correo_asesor = correo_input
                        st.session_state.asesor_seleccionado = "Seleccionar asesor"
                        st.session_state.counter += 1
                        st.rerun()
                
                with col_a2:
                    telefono_key = f"asesor_telefono_input_{st.session_state.counter}"
                    telefono_input = st.text_input(
                        "Teléfono Ejecutivo",
                        value=st.session_state.telefono_asesor,
                        key=telefono_key,
                        placeholder="912345678 (9 dígitos)"
                    )
                    
                    if telefono_input != st.session_state.telefono_asesor:
                        raw = re.sub(r'[^0-9]', '', telefono_input)
                        if len(raw) > 9:
                            raw = raw[:9]
                        st.session_state.telefono_asesor = raw
                        st.session_state.asesor_seleccionado = "Seleccionar asesor"
                        st.session_state.counter += 1
                        st.rerun()
        
        # Dirección del Proyecto
        with st.container(border=True):
            st.markdown("📍 PROYECTO")
            st.markdown("**📍 Dirección del Proyecto**")
            
            direccion_key = f"direccion_input_{st.session_state.counter}"
            direccion = st.text_input(
                "Dirección", 
                placeholder="Calle, número, comuna", 
                key=direccion_key,
                value=st.session_state.direccion_input
            )
            if direccion != st.session_state.direccion_input:
                st.session_state.direccion_input = direccion
            
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
        
        # Validez del Presupuesto
        with st.container(border=True):
            st.markdown("📅 VALIDEZ")
            st.markdown("### 📅 Validez del Presupuesto")
            
            col_v1, col_v2 = st.columns(2)
            
            with col_v1:
                fecha_inicio_key = f"fecha_inicio_{st.session_state.counter}"
                fecha_inicio = st.date_input(
                    "Fecha de Inicio", 
                    value=st.session_state.fecha_inicio, 
                    key=fecha_inicio_key
                )
                if fecha_inicio != st.session_state.fecha_inicio:
                    st.session_state.fecha_inicio = fecha_inicio
            
            with col_v2:
                fecha_termino_key = f"fecha_termino_{st.session_state.counter}"
                fecha_termino = st.date_input(
                    "Fecha de Término", 
                    value=st.session_state.fecha_termino,
                    key=fecha_termino_key
                )
                if fecha_termino != st.session_state.fecha_termino:
                    st.session_state.fecha_termino = fecha_termino
            
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
        # Definir si está deshabilitado
        observaciones_disabled = False
        if st.session_state.cotizacion_cargada and st.session_state.margen > 0 and not st.session_state.modo_admin:
            observaciones_disabled = True
        
        observaciones_key = f"observaciones_input_{st.session_state.counter}"
        observaciones = st.text_area(
            "Observaciones y notas adicionales", 
            placeholder="Ingresa aquí cualquier información relevante para la cotización...",
            height=100,
            key=observaciones_key,
            value=st.session_state.observaciones_input,
            disabled=observaciones_disabled
        )
        if not observaciones_disabled and observaciones != st.session_state.observaciones_input:
            st.session_state.observaciones_input = observaciones
    
    # =========================================================
    # RESUMEN DE LOS DATOS INGRESADOS
    # =========================================================
    st.markdown("---")
    with st.expander("📋 Ver resumen de datos ingresados", expanded=False):
        col_res1, col_res2 = st.columns(2)
        
        with col_res1:
            st.markdown("**Cliente:**")
            st.write(f"• **Nombre:** {st.session_state.nombre_input if st.session_state.nombre_input else 'No ingresado'}")
            st.write(f"• **RUT:** {st.session_state.rut_display if st.session_state.rut_display else 'No ingresado'} {'✅' if st.session_state.rut_valido else '❌' if st.session_state.rut_raw else ''}")
            st.write(f"• **Email:** {st.session_state.correo_input if st.session_state.correo_input else 'No ingresado'}")
            st.write(f"• **Teléfono:** {st.session_state.telefono_raw if st.session_state.telefono_raw else 'No ingresado'}")
            st.write(f"• **Dirección:** {st.session_state.direccion_input if st.session_state.direccion_input else 'No ingresado'}")
        
        with col_res2:
            st.markdown("**Asesor y Validez:**")
            nombre_asesor_mostrar = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else "No seleccionado"
            st.write(f"• **Ejecutivo:** {nombre_asesor_mostrar}")
            st.write(f"• **Email Ejecutivo:** {st.session_state.correo_asesor if st.session_state.correo_asesor else 'No ingresado'}")
            st.write(f"• **Teléfono Ejecutivo:** {st.session_state.telefono_asesor if st.session_state.telefono_asesor else 'No ingresado'}")
            st.write(f"• **Validez:** {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_termino.strftime('%d/%m/%Y')}")
            st.write(f"• **Días de validez:** {dias_validez if dias_validez > 0 else 'Fechas inválidas'}")
    
    # =========================================================
    # DICCIONARIOS PARA PDF
    # =========================================================
    datos_cliente = {
        "Nombre": st.session_state.nombre_input if st.session_state.nombre_input else "",
        "RUT": st.session_state.rut_display if st.session_state.rut_display else "",
        "Correo": st.session_state.correo_input if st.session_state.correo_input else "",
        "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else "",
        "Dirección": st.session_state.direccion_input if st.session_state.direccion_input else "",
        "Observaciones": st.session_state.observaciones_input if st.session_state.observaciones_input else ""
    }
    
    nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    
    datos_asesor = {
        "Nombre Ejecutivo": nombre_asesor_final,
        "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
        "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
    }

# =========================================================
# TAB 1 - PREPARAR COTIZACIÓN (CON GESTIÓN SIMPLIFICADA)
# =========================================================
    
with tab1:
    st.markdown("### ☑️ Gestión de Presupuesto")
    
    # Obtener fechas desde session_state
    fecha_inicio = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino
    dias_validez = (fecha_termino - fecha_inicio).days
    
    # Verificar si la cotización cargada tiene margen y el usuario NO es admin
    es_solo_lectura = False
    if st.session_state.cotizacion_cargada and st.session_state.margen > 0 and not st.session_state.modo_admin:
        es_solo_lectura = True
    
    if es_solo_lectura:
        st.warning("🔒 Esta cotización tiene márgenes aplicados. Modo solo lectura. Solo puedes visualizar y generar PDFs.")
    
    # GESTIÓN DE PRODUCTOS - SIMPLIFICADA (SIN BOXES EXTRA)
    if not es_solo_lectura:
        st.markdown("#### Gestión de Productos")
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        # ---------- 1️⃣ MODELOS PREDEFINIDOS ----------
        with col_m1:
            with st.container():
                archivo_excel = pd.ExcelFile("cotizador.xlsx")
                hojas_modelo = [h for h in archivo_excel.sheet_names if h.lower().startswith("modelo")]

                if hojas_modelo:
                    modelo_seleccionado = st.selectbox("Modelo", hojas_modelo, key="modelo_select", label_visibility="collapsed")

                    if st.button("Cargar", key="btn_modelo", use_container_width=True):
                        st.session_state.carrito = cargar_modelo(modelo_seleccionado)
                        st.session_state.modelo_base = modelo_seleccionado
                        st.session_state.margen = 0.0
                        st.success(f"Modelo cargado correctamente.")
                        st.rerun()

        # ---------- 2️⃣ SELECCIONAR ÍTEMS ----------
        with col_m2:
            with st.container():
                df = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")
                categorias = df["Categorias"].dropna().unique()
                categoria_seleccionada = st.selectbox("Categoría", categorias, key="cat_manual", label_visibility="collapsed")
                items_filtrados = df[df["Categorias"] == categoria_seleccionada]
                item = st.selectbox("Ítem", items_filtrados["Item"], key="item_manual", label_visibility="collapsed")
                cantidad = st.number_input("Cantidad", min_value=1, value=1, key="cantidad_manual", label_visibility="collapsed")

                if st.button("Agregar", key="btn_agregar_manual", use_container_width=True):
                    existe = False
                    for producto in st.session_state.carrito:
                        if producto["Item"] == item:
                            producto["Cantidad"] += cantidad
                            producto["Subtotal"] = producto["Cantidad"] * producto["Precio Unitario"]
                            existe = True
                            break
                    if not existe:
                        precio_unitario_original = items_filtrados[items_filtrados["Item"] == item]["P. Unitario real"].values[0]
                        st.session_state.carrito.append({
                            "Categoria": categoria_seleccionada,
                            "Item": item,
                            "Cantidad": cantidad,
                            "Precio Unitario": precio_unitario_original,
                            "Subtotal": precio_unitario_original * cantidad
                        })
                    st.rerun()

        # ---------- 3️⃣ ELIMINAR CATEGORÍA ----------
        with col_m3:
            with st.container():
                if st.session_state.carrito:
                    carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                    categorias_carrito = carrito_df_temp["Categoria"].unique()
                    categoria_eliminar = st.selectbox(
                        "Eliminar",
                        ["-- Seleccionar --"] + list(categorias_carrito),
                        key="cat_eliminar",
                        label_visibility="collapsed"
                    )
                    if categoria_eliminar != "-- Seleccionar --":
                        if st.button("Eliminar", key="btn_eliminar_categoria", use_container_width=True):
                            st.session_state.carrito = [
                                item for item in st.session_state.carrito
                                if item["Categoria"] != categoria_eliminar
                            ]
                            st.success(f"Categoría eliminada.")
                            st.rerun()
                else:
                    st.info("No hay categorías")

        # ---------- 4️⃣ AGREGAR CATEGORÍA ----------
        with col_m4:
            with st.container():
                if hojas_modelo:
                    modelo_origen = st.selectbox(
                        "Modelo",
                        hojas_modelo,
                        key="modelo_origen",
                        label_visibility="collapsed"
                    )
                    df_temp = pd.read_excel("cotizador.xlsx", sheet_name=modelo_origen)
                    categorias_disponibles = df_temp["Categorias"].dropna().unique()
                    categoria_agregar = st.selectbox(
                        "Categoría",
                        categorias_disponibles,
                        key="cat_agregar",
                        label_visibility="collapsed"
                    )
                    if st.button("Agregar", key="btn_agregar_categoria", use_container_width=True):
                        nuevos_items = cargar_categoria_desde_modelo(modelo_origen, categoria_agregar)
                        st.session_state.carrito = [
                            item for item in st.session_state.carrito
                            if item["Categoria"] != categoria_agregar
                        ]
                        st.session_state.carrito.extend(nuevos_items)
                        st.success(f"Categoría agregada.")
                        st.rerun()

    # ---------------- RESUMEN ----------------
    st.markdown("---")

    # CONTROL DE MARGEN - Solo visible para admin
    if st.session_state.modo_admin:
        col_titulo, col_margen_etq, col_margen_input = st.columns([4, 0.5, 0.8])
        with col_titulo:
            st.markdown("#### Resumen del Presupuesto")
        with col_margen_etq:
            st.markdown("**Margen (%)**")
        with col_margen_input:
            margen_key = f"margen_input_{st.session_state.counter}"
            margen_input = st.number_input(
                "Margen", 
                min_value=0.0, 
                max_value=100.0, 
                value=float(st.session_state.margen),
                step=0.5,
                format="%.1f",
                key=margen_key,
                label_visibility="collapsed"
            )
            if margen_input != st.session_state.margen:
                st.session_state.margen = margen_input
                st.rerun()
    else:
        st.markdown("#### Resumen del Presupuesto")
        if st.session_state.margen > 0:
            st.caption(f"ℹ️ Esta cotización tiene un margen del {st.session_state.margen}% aplicado")

    if st.session_state.carrito:
        carrito_df = pd.DataFrame(st.session_state.carrito)
        
        # Calcular totales base
        subtotal_base = carrito_df["Subtotal"].sum()
        
        if st.session_state.modo_admin:
            carrito_df_con_margen = carrito_df.copy()
            carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(
                lambda x: aplicar_margen(x, st.session_state.margen)
            )
            carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]
            subtotal_general = carrito_df_con_margen["Subtotal"].sum()
            iva = subtotal_general * 0.19
            total = subtotal_general + iva
            margen_valor = subtotal_general - subtotal_base
            comision_vendedor = subtotal_general * 0.025
            comision_supervisor = subtotal_general * 0.008
            total_comisiones = comision_vendedor + comision_supervisor
            utilidad_real = margen_valor - comision_vendedor - comision_supervisor
        else:
            if st.session_state.margen > 0:
                carrito_df_con_margen = carrito_df.copy()
                carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(
                    lambda x: aplicar_margen(x, st.session_state.margen)
                )
                carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]
                subtotal_general = carrito_df_con_margen["Subtotal"].sum()
            else:
                subtotal_general = subtotal_base
            iva = subtotal_general * 0.19
            total = subtotal_general + iva
            margen_valor = 0
            comision_vendedor = 0
            comision_supervisor = 0
            total_comisiones = 0
            utilidad_real = 0

        # ---------------- TABLA DE PRODUCTOS ----------------
        if es_solo_lectura:
            if st.session_state.modo_admin:
                carrito_df_display = carrito_df_con_margen.copy()
            else:
                if st.session_state.margen > 0:
                    carrito_df_display = carrito_df_con_margen.copy()
                else:
                    carrito_df_display = carrito_df.copy()
            
            carrito_df_display = carrito_df_display[["Categoria", "Item", "Cantidad", "Precio Unitario", "Subtotal"]].copy()
            carrito_df_display["Precio Unitario"] = carrito_df_display["Precio Unitario"].apply(lambda x: formato_clp(x))
            carrito_df_display["Subtotal"] = carrito_df_display["Subtotal"].apply(lambda x: formato_clp(x))
            
            st.dataframe(
                carrito_df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Categoria": st.column_config.TextColumn("Categoría"),
                    "Item": st.column_config.TextColumn("Item"),
                    "Cantidad": st.column_config.NumberColumn("Cant."),
                    "Precio Unitario": st.column_config.TextColumn("P. Unitario"),
                    "Subtotal": st.column_config.TextColumn("Subtotal"),
                }
            )
            st.caption("🔒 Vista de solo lectura")
            
        else:
            if st.session_state.modo_admin:
                carrito_df_edit = carrito_df_con_margen.copy()
            else:
                carrito_df_edit = carrito_df.copy()
            
            carrito_df_edit["❌"] = False
            carrito_df_edit["Precio Unitario"] = carrito_df_edit["Precio Unitario"].apply(lambda x: formato_clp(x))
            carrito_df_edit["Subtotal"] = carrito_df_edit["Subtotal"].apply(lambda x: formato_clp(x))

            edited_df = st.data_editor(
                carrito_df_edit,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "❌": st.column_config.CheckboxColumn("❌"),
                    "Categoria": st.column_config.TextColumn("Categoría"),
                    "Item": st.column_config.TextColumn("Item"),
                    "Cantidad": st.column_config.NumberColumn("Cant."),
                    "Precio Unitario": st.column_config.TextColumn("P. Unitario"),
                    "Subtotal": st.column_config.TextColumn("Subtotal"),
                }
            )

            filas_eliminar = edited_df[edited_df["❌"] == True].index.tolist()
            if filas_eliminar:
                for i in sorted(filas_eliminar, reverse=True):
                    del st.session_state.carrito[i]
                st.rerun()

        # =========================================================
        # 4 BOTONES DEBAJO DE LA TABLA
        # =========================================================
        st.markdown("---")
        
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            if not es_solo_lectura:
                if st.button("💾 Guardar", use_container_width=True, type="primary"):
                    procesar_cambio_rut()
                    procesar_cambio_telefono()
                    
                    if st.session_state.cotizacion_cargada:
                        numero_guardar = st.session_state.cotizacion_cargada
                        es_actualizacion = True
                    else:
                        numero_guardar = f"EP-{random.randint(1000,9999)}"
                        es_actualizacion = False
                    
                    datos_cliente_guardar = {
                        "Nombre": st.session_state.nombre_input if st.session_state.nombre_input else "",
                        "RUT": st.session_state.rut_display if st.session_state.rut_display else "",
                        "Correo": st.session_state.correo_input if st.session_state.correo_input else "",
                        "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else "",
                        "Dirección": st.session_state.direccion_input if st.session_state.direccion_input else "",
                        "Observaciones": st.session_state.observaciones_input if st.session_state.observaciones_input else ""
                    }
                    
                    nombre_asesor_guardar = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
                    
                    datos_asesor_guardar = {
                        "Nombre Ejecutivo": nombre_asesor_guardar,
                        "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
                        "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
                    }
                    
                    proyecto = {
                        'fecha_inicio': str(st.session_state.fecha_inicio),
                        'fecha_termino': str(st.session_state.fecha_termino),
                        'dias_validez': (st.session_state.fecha_termino - st.session_state.fecha_inicio).days,
                        'observaciones': st.session_state.observaciones_input
                    }
                    
                    config = {
                        'margen': st.session_state.margen,
                        'modo_admin': st.session_state.modo_admin
                    }
                    
                    if st.session_state.carrito:
                        carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                        subtotal_base_temp = carrito_df_temp["Subtotal"].sum()
                        
                        if st.session_state.modo_admin:
                            subtotal_general_temp = 0
                            for item in st.session_state.carrito:
                                precio_con_margen = aplicar_margen(item["Precio Unitario"], st.session_state.margen)
                                subtotal_general_temp += item["Cantidad"] * precio_con_margen
                            iva_temp = subtotal_general_temp * 0.19
                            total_temp = subtotal_general_temp + iva_temp
                            margen_valor_temp = subtotal_general_temp - subtotal_base_temp
                            comision_vendedor_temp = subtotal_general_temp * 0.025
                            comision_supervisor_temp = subtotal_general_temp * 0.008
                            utilidad_real_temp = margen_valor_temp - comision_vendedor_temp - comision_supervisor_temp
                        else:
                            subtotal_general_temp = subtotal_base_temp
                            iva_temp = subtotal_general_temp * 0.19
                            total_temp = subtotal_general_temp + iva_temp
                            margen_valor_temp = 0
                            comision_vendedor_temp = 0
                            comision_supervisor_temp = 0
                            utilidad_real_temp = 0
                    else:
                        subtotal_base_temp = 0
                        subtotal_general_temp = 0
                        iva_temp = 0
                        total_temp = 0
                        margen_valor_temp = 0
                        comision_vendedor_temp = 0
                        comision_supervisor_temp = 0
                        utilidad_real_temp = 0
                    
                    totales = {
                        'subtotal_sin_margen': subtotal_base_temp,
                        'subtotal_con_margen': subtotal_general_temp,
                        'iva': iva_temp,
                        'total': total_temp,
                        'margen_valor': margen_valor_temp,
                        'comision_vendedor': comision_vendedor_temp,
                        'comision_supervisor': comision_supervisor_temp,
                        'utilidad_real': utilidad_real_temp
                    }
                    
                    if guardar_cotizacion(
                        numero_guardar,
                        datos_cliente_guardar,
                        datos_asesor_guardar,
                        proyecto,
                        st.session_state.carrito,
                        config,
                        totales
                    ):
                        if es_actualizacion:
                            st.success(f"✅ Cotización {numero_guardar} actualizada")
                        else:
                            st.session_state.cotizacion_cargada = numero_guardar
                            st.success(f"✅ Cotización {numero_guardar} guardada")
                        
                        st.session_state.resultados_busqueda = buscar_cotizaciones()
                        st.rerun()
            else:
                st.button("💾 Guardar", use_container_width=True, disabled=True)

        # Preparar datos para PDF
        correo_para_pdf = st.session_state.correo_input
        rut_valido_para_pdf = True
        if st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            rut_valido_para_pdf = st.session_state.rut_valido

        datos_cliente_pdf = {
            "Nombre": st.session_state.nombre_input,
            "RUT": st.session_state.rut_display if st.session_state.rut_display else '',
            "Correo": st.session_state.correo_input,
            "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else '',
            "Dirección": st.session_state.direccion_input,
            "Observaciones": st.session_state.observaciones_input
        }

        nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
        datos_asesor_pdf = {
            "Nombre Ejecutivo": nombre_asesor_final,
            "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
            "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
        }

        carrito_df_original = pd.DataFrame(st.session_state.carrito)

        if st.session_state.modo_admin or st.session_state.margen > 0:
            carrito_df_pdf = carrito_df_original.copy()
            carrito_df_pdf["Precio Unitario"] = carrito_df_pdf["Precio Unitario"].apply(
                lambda x: aplicar_margen(x, st.session_state.margen)
            )
            carrito_df_pdf["Subtotal"] = carrito_df_pdf["Cantidad"] * carrito_df_pdf["Precio Unitario"]
            margen_actual = st.session_state.margen
        else:
            carrito_df_pdf = carrito_df_original.copy()
            margen_actual = 0

        # Validaciones
        errores = []
        if "@" not in correo_para_pdf:
            errores.append("❌ El correo debe contener '@'")
        if dias_validez < 0:
            errores.append("❌ La fecha de término debe ser posterior a la fecha de inicio")
        if not rut_valido_para_pdf and st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            errores.append("❌ El RUT no es válido")
        
        if errores:
            for error in errores:
                st.error(error)
            if not es_solo_lectura:
                st.info("Corrige los errores para poder generar los PDFs")
            with col_btn2:
                st.button("📥 PDF Completo", use_container_width=True, disabled=True)
            with col_btn3:
                st.button("🔒 PDF Cliente", use_container_width=True, disabled=True)
        else:
            with col_btn2:
                numero_para_pdf = st.session_state.cotizacion_cargada if st.session_state.cotizacion_cargada else None
                pdf_buffer_completo, numero_cotizacion = generar_pdf_completo(
                    carrito_df_pdf, subtotal_general, iva, total,
                    datos_cliente_pdf, fecha_inicio, fecha_termino, dias_validez,
                    datos_asesor_pdf, margen=margen_actual, numero_cotizacion=numero_para_pdf
                )
                st.download_button(
                    label="📥 PDF Completo",
                    data=pdf_buffer_completo,
                    file_name=f"Presupuesto_Completo_{numero_cotizacion}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_completo"
                )

            with col_btn3:
                pdf_buffer_cliente, numero_cotizacion = generar_pdf_cliente(
                    carrito_df_pdf, subtotal_general, iva, total,
                    datos_cliente_pdf, fecha_inicio, fecha_termino, dias_validez,
                    datos_asesor_pdf, margen=margen_actual, numero_cotizacion=numero_para_pdf
                )
                st.download_button(
                    label="🔒 PDF Cliente",
                    data=pdf_buffer_cliente,
                    file_name=f"Presupuesto_Cliente_{numero_cotizacion}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_cliente"
                )

        with col_btn4:
            if not es_solo_lectura:
                if st.button("🧹 Limpiar", use_container_width=True):
                    st.session_state.carrito = []
                    if st.session_state.modo_admin:
                        st.session_state.margen = 0.0
                    st.session_state.cotizacion_cargada = None
                    st.rerun()
            else:
                st.button("🧹 Limpiar", use_container_width=True, disabled=True)

        # =========================================================
        # TOTALES
        # =========================================================
        st.markdown("### Totales")
        col_total1, col_total2, col_total3 = st.columns(3)
        with col_total1:
            st.metric("Subtotal", formato_clp(subtotal_general))
        with col_total2:
            st.metric("IVA (19%)", formato_clp(iva))
        with col_total3:
            st.metric("TOTAL", formato_clp(total))
        
        if st.session_state.modo_admin and st.session_state.margen > 0:
            st.caption(f"*Precios calculados con margen del {st.session_state.margen}%")

        # =========================================================
        # TARJETAS DE MÉTRICAS
        # =========================================================
        st.markdown("---")
        st.markdown("#### Métricas")

        # PRIMERA FILA
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        with col_m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">ÍTEMS</div>
                <div class="metric-value" style="color: #3b82f6;">{len(st.session_state.carrito)}</div>
                <div class="metric-change">En presupuesto</div>
            </div>
            """, unsafe_allow_html=True)

        with col_m2:
            total_productos = sum(item["Cantidad"] for item in st.session_state.carrito)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">PRODUCTOS</div>
                <div class="metric-value" style="color: #f59e0b;">{total_productos}</div>
                <div class="metric-change">Unidades</div>
            </div>
            """, unsafe_allow_html=True)

        with col_m3:
            categorias_unicas = len(set(item["Categoria"] for item in st.session_state.carrito))
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">CATEGORÍAS</div>
                <div class="metric-value" style="color: #10b981;">{categorias_unicas}</div>
                <div class="metric-change">Diferentes</div>
            </div>
            """, unsafe_allow_html=True)

        with col_m4:
            if st.session_state.modo_admin:
                st.markdown(f"""
                <div class="metric-card-special" style="background: linear-gradient(135deg, #ef4444, #dc2626); padding: 1.5rem;">
                    <div class="metric-title" style="color: white;">📦 SUBTOTAL</div>
                    <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                        {formato_clp(subtotal_general)}
                    </div>
                    <div style="margin-top: 1rem;">
                        <div style="display: flex; justify-content: space-between; color: white;">
                            <span>Costo base:</span>
                            <span>{formato_clp(subtotal_base)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between; color: white;">
                            <span>+ Margen {st.session_state.margen}%:</span>
                            <span>{formato_clp(margen_valor)}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="metric-card-special" style="background: linear-gradient(135deg, #ef4444, #dc2626); padding: 1.5rem;">
                    <div class="metric-title" style="color: white;">📦 SUBTOTAL</div>
                    <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                        {formato_clp(subtotal_base)}
                    </div>
                    <div style="margin-top: 1rem; color: white;">
                        Costo base (sin IVA)
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")

        # SEGUNDA FILA - Solo visible para admin
        if st.session_state.modo_admin:
            if st.session_state.margen > 0:
                col_total, col_comisiones, col_utilidad = st.columns(3)

                with col_total:
                    st.markdown(f"""
                    <div class="metric-card-special metric-card-total" style="padding: 1.5rem;">
                        <div class="metric-title" style="color: white;">💰 TOTAL CON IVA</div>
                        <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                            {formato_clp(total)}
                        </div>
                        <div style="margin-top: 1rem; color: white;">
                            <div style="display: flex; justify-content: space-between;">
                                <span>Costo base:</span>
                                <span>{formato_clp(subtotal_base)}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>+ Margen {st.session_state.margen}%:</span>
                                <span>{formato_clp(margen_valor)}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>= Subtotal c/margen:</span>
                                <span>{formato_clp(subtotal_general)}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>+ IVA 19%:</span>
                                <span>{formato_clp(iva)}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_comisiones:
                    st.markdown(f"""
                    <div class="metric-card-special metric-card-comisiones" style="padding: 1.5rem;">
                        <div class="metric-title" style="color: white;">📊 COMISIONES</div>
                        <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                            {formato_clp(total_comisiones)}
                        </div>
                        <div style="margin-top: 1rem; color: white;">
                            <div style="display: flex; justify-content: space-between;">
                                <span>Vendedor 2.5%:</span>
                                <span>{formato_clp(comision_vendedor)}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>Supervisor 0.8%:</span>
                                <span>{formato_clp(comision_supervisor)}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                with col_utilidad:
                    st.markdown(f"""
                    <div class="metric-card-special metric-card-utilidad" style="padding: 1.5rem;">
                        <div class="metric-title" style="color: white;">📈 UTILIDAD REAL</div>
                        <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                            {formato_clp(utilidad_real)}
                        </div>
                        <div style="margin-top: 1rem; color: white;">
                            <div style="display: flex; justify-content: space-between;">
                                <span>Margen bruto:</span>
                                <span>{formato_clp(margen_valor)}</span>
                            </div>
                            <div style="display: flex; justify-content: space-between;">
                                <span>- Comisiones:</span>
                                <span>{formato_clp(total_comisiones)}</span>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                col_total, col_comisiones, col_utilidad = st.columns(3)
                with col_total:
                    st.markdown(f"""
                    <div class="metric-card-special metric-card-total" style="opacity: 0.7;">
                        <div class="metric-title">TOTAL CON IVA</div>
                        <div class="metric-value">{formato_clp(total)}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_comisiones:
                    st.markdown("""
                    <div class="metric-card-special metric-card-comisiones" style="opacity: 0.7;">
                        <div class="metric-title">COMISIONES</div>
                        <div class="metric-value">$0</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_utilidad:
                    st.markdown("""
                    <div class="metric-card-special metric-card-utilidad" style="opacity: 0.7;">
                        <div class="metric-title">UTILIDAD REAL</div>
                        <div class="metric-value">$0</div>
                    </div>
                    """, unsafe_allow_html=True)

        else:
            # MODO EJECUTIVO
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f"""
                <div class="metric-card-special metric-card-total" style="padding: 1.5rem;">
                    <div class="metric-title" style="color: white;">💰 TOTAL CON IVA</div>
                    <div style="text-align: center; font-size: 2.5rem; font-weight: 700; color: white;">
                        {formato_clp(total)}
                    </div>
                    <div style="margin-top: 1rem; color: white;">
                        <div style="display: flex; justify-content: space-between;">
                            <span>Costo base:</span>
                            <span>{formato_clp(subtotal_base)}</span>
                        </div>
                        <div style="display: flex; justify-content: space-between;">
                            <span>+ IVA 19%:</span>
                            <span>{formato_clp(iva)}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            if st.session_state.margen > 0:
                st.info("🔒 Los detalles de comisiones y utilidad solo están disponibles para administradores.")
    else:
        st.info("👈 Agrega productos al presupuesto usando los controles de la izquierda")

# =========================================================
# TAB 3 - GESTIÓN DE COTIZACIONES GUARDADAS (VERSIÓN FINAL CORREGIDA)
# =========================================================
with tab3:
    st.markdown("### 📂 Gestión de Cotizaciones")
    
    # Layout de búsqueda
    col_busqueda, col_filtros = st.columns([3, 1])
    
    with col_busqueda:
        tipo_busqueda = st.radio(
            "Buscar por:",
            ["📋 N° Presupuesto", "👤 Cliente", "👨‍💼 Asesor"],
            horizontal=True,
            key="tipo_busqueda"
        )
        
        tipo_map = {
            "📋 N° Presupuesto": "numero",
            "👤 Cliente": "cliente",
            "👨‍💼 Asesor": "asesor"
        }
        
        termino = st.text_input(
            "Buscar...",
            placeholder="Ingrese término de búsqueda...",
            key="buscar_cotizacion"
        )
    
    with col_filtros:
        st.markdown("### Filtros rápidos")
        if st.button("📅 Hoy", use_container_width=True):
            pass
        if st.button("📅 Esta semana", use_container_width=True):
            pass
        if st.button("📅 Este mes", use_container_width=True):
            pass
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 4])
    with col_btn1:
        buscar_btn = st.button("🔍 Buscar", type="primary", use_container_width=True)
    with col_btn2:
        limpiar_btn = st.button("🗑️ Limpiar", use_container_width=True)
    
    st.markdown("---")
    st.markdown("### Resultados")
    
    if 'resultados_busqueda' not in st.session_state:
        st.session_state.resultados_busqueda = []
    
    if buscar_btn or (termino and termino != st.session_state.get('ultimo_termino', '')):
        st.session_state.ultimo_termino = termino
        st.session_state.resultados_busqueda = buscar_cotizaciones(
            termino if termino else None,
            tipo_map[tipo_busqueda]
        )
    
    if limpiar_btn:
        st.session_state.resultados_busqueda = []
        st.session_state.ultimo_termino = ""
        st.rerun()
    
    if st.session_state.resultados_busqueda:
        # Crear DataFrame
        df_resultados = pd.DataFrame(
            st.session_state.resultados_busqueda,
            columns=["N°", "Cliente", "Asesor", "Fecha", "Total", "Margen", 
                     "RUT", "Email", "Asesor_Email", "Asesor_Tel"]
        )
        
        # Formatear total
        df_resultados["Total"] = df_resultados["Total"].apply(
            lambda x: f"${x:,.0f}".replace(",", ".") if x else "$0"
        )
        
        # Formatear fecha (solo la fecha, sin hora)
        df_resultados["Fecha"] = df_resultados["Fecha"].apply(
            lambda x: x[:10] if x else ""
        )
        
        # Crear columna de estado con badges HTML (SIN SALTOS DE LÍNEA)
        df_resultados["Estado"] = df_resultados.apply(crear_badge_estado, axis=1)
        
        # CONSTRUIR TABLA HTML COMPLETA
        html_table = "<table class='resultados-table'><thead><tr>"
        html_table += "<th>N° Presupuesto</th><th>Cliente</th><th>Asesor</th><th>Fecha</th><th>Total</th><th>Estado</th>"
        html_table += "</tr></thead><tbody>"
        
        # Filas de datos
        for _, row in df_resultados.iterrows():
            cliente = row['Cliente'] if row['Cliente'] else '—'
            asesor = row['Asesor'] if row['Asesor'] else '—'
            
            html_table += "<tr>"
            html_table += f"<td>{row['N°']}</td>"
            html_table += f"<td>{cliente}</td>"
            html_table += f"<td>{asesor}</td>"
            html_table += f"<td>{row['Fecha']}</td>"
            html_table += f"<td>{row['Total']}</td>"
            html_table += f"<td style='text-align:center;'>{row['Estado']}</td>"
            html_table += "</tr>"
        
        html_table += "</tbody></table>"
        
        # Mostrar la tabla
        st.markdown(html_table, unsafe_allow_html=True)
        
        # Leyenda de estados
        with st.expander("📋 Leyenda de estados", expanded=False):
            col_leyenda1, col_leyenda2, col_leyenda3 = st.columns(3)
            with col_leyenda1:
                st.markdown("""
                <div style="background-color: #d4edda; padding: 10px; border-radius: 10px;">
                    <span style="font-size:1.2rem;">🟢</span> <strong>AUTORIZADO</strong><br>
                    <small>Con margen aplicado y datos completos</small>
                </div>
                """, unsafe_allow_html=True)
            with col_leyenda2:
                st.markdown("""
                <div style="background-color: #fff3cd; padding: 10px; border-radius: 10px;">
                    <span style="font-size:1.2rem;">🟡</span> <strong>BORRADOR</strong><br>
                    <small>Sin margen, datos completos</small>
                </div>
                """, unsafe_allow_html=True)
            with col_leyenda3:
                st.markdown("""
                <div style="background-color: #f8d7da; padding: 10px; border-radius: 10px;">
                    <span style="font-size:1.2rem;">🔴</span> <strong>INCOMPLETO</strong><br>
                    <small>Faltan datos del cliente o asesor</small>
                </div>
                """, unsafe_allow_html=True)
        
        # Selector de cotización
        st.markdown("---")
        st.markdown("### Seleccionar cotización")
        
        opciones = []
        for idx, row in df_resultados.iterrows():
            datos_completos = all([row[1], row[6], row[7]])
            asesor_completo = any([row[2], row[8], row[9]])
            
            if row['Margen'] and row['Margen'] > 0:
                if datos_completos and asesor_completo:
                    estado = "🟢 AUTORIZADO"
                else:
                    estado = "🔴 INCOMPLETO"
            else:
                if datos_completos and asesor_completo:
                    estado = "🟡 BORRADOR"
                else:
                    estado = "🔴 INCOMPLETO"
            
            opcion = f"{row['N°']} - {row['Cliente'] or 'S/C'} ({row['Fecha']}) - {row['Total']} - {estado}"
            opciones.append(opcion)
        
        if opciones:
            cotizacion_seleccionada = st.selectbox(
                "Selecciona una cotización:",
                options=opciones,
                key="selector_cotizaciones"
            )
            
            if cotizacion_seleccionada:
                numero_seleccionado = cotizacion_seleccionada.split(" - ")[0]
                
                tiene_margen_seleccionado = False
                for row in st.session_state.resultados_busqueda:
                    if row[0] == numero_seleccionado:
                        tiene_margen_seleccionado = row[5] and row[5] > 0
                        break
                
                if tiene_margen_seleccionado and not st.session_state.modo_admin:
                    st.warning("🔒 Cotización autorizada - Solo puedes generar PDFs")
            
            st.markdown("---")
            st.markdown("### Acciones")
            
            col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
            
            with col_acc1:
                if tiene_margen_seleccionado and not st.session_state.modo_admin:
                    st.button("📂 Cargar", use_container_width=True, disabled=True)
                else:
                    if st.button("📂 Cargar", use_container_width=True):
                        if cotizacion_seleccionada:
                            if preparar_carga_cotizacion(numero_seleccionado):
                                st.success(f"✅ Cotización {numero_seleccionado} cargada")
                                st.rerun()

            with col_acc2:
                if cotizacion_seleccionada:
                    cotizacion = cargar_cotizacion(numero_seleccionado)
                    if cotizacion:
                        carrito_df_temp = pd.DataFrame(cotizacion['productos'])
                        margen_cotizacion = cotizacion.get('config_margen', 0)
                        
                        if margen_cotizacion > 0:
                            carrito_df_pdf = carrito_df_temp.copy()
                            carrito_df_pdf["Precio Unitario"] = carrito_df_pdf["Precio Unitario"].apply(
                                lambda x: aplicar_margen(x, margen_cotizacion)
                            )
                            carrito_df_pdf["Subtotal"] = carrito_df_pdf["Cantidad"] * carrito_df_pdf["Precio Unitario"]
                            subtotal_pdf = carrito_df_pdf["Subtotal"].sum()
                        else:
                            carrito_df_pdf = carrito_df_temp.copy()
                            subtotal_pdf = carrito_df_temp["Subtotal"].sum()
                        
                        iva_pdf = subtotal_pdf * 0.19
                        total_pdf = subtotal_pdf + iva_pdf
                        
                        datos_cliente_pdf = {
                            "Nombre": cotizacion.get('cliente_nombre', ''),
                            "RUT": cotizacion.get('cliente_rut', ''),
                            "Correo": cotizacion.get('cliente_email', ''),
                            "Teléfono": cotizacion.get('cliente_telefono', ''),
                            "Dirección": cotizacion.get('cliente_direccion', ''),
                            "Observaciones": cotizacion.get('proyecto_observaciones', '')
                        }
                        
                        datos_asesor_pdf = {
                            "Nombre Ejecutivo": cotizacion.get('asesor_nombre', ''),
                            "Correo Ejecutivo": cotizacion.get('asesor_email', ''),
                            "Teléfono Ejecutivo": cotizacion.get('asesor_telefono', '')
                        }
                        
                        fecha_inicio_pdf = datetime.strptime(
                            cotizacion.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), 
                            '%Y-%m-%d'
                        ).date()
                        fecha_termino_pdf = datetime.strptime(
                            cotizacion.get('proyecto_fecha_termino', (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')), 
                            '%Y-%m-%d'
                        ).date()
                        dias_validez_pdf = cotizacion.get('proyecto_dias_validez', 15)
                        
                        pdf_buffer, _ = generar_pdf_completo(
                            carrito_df_pdf, subtotal_pdf, iva_pdf, total_pdf,
                            datos_cliente_pdf, fecha_inicio_pdf, fecha_termino_pdf, dias_validez_pdf,
                            datos_asesor_pdf, margen=margen_cotizacion, numero_cotizacion=numero_seleccionado
                        )
                        
                        st.download_button(
                            label="📄 PDF Completo",
                            data=pdf_buffer,
                            file_name=f"Presupuesto_Completo_{numero_seleccionado}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"pdf_completo_{numero_seleccionado}"
                        )
                else:
                    st.button("📄 PDF Completo", use_container_width=True, disabled=True)

            with col_acc3:
                if cotizacion_seleccionada:
                    cotizacion = cargar_cotizacion(numero_seleccionado)
                    if cotizacion:
                        carrito_df_temp = pd.DataFrame(cotizacion['productos'])
                        margen_cotizacion = cotizacion.get('config_margen', 0)
                        
                        if margen_cotizacion > 0:
                            carrito_df_pdf = carrito_df_temp.copy()
                            carrito_df_pdf["Precio Unitario"] = carrito_df_pdf["Precio Unitario"].apply(
                                lambda x: aplicar_margen(x, margen_cotizacion)
                            )
                            carrito_df_pdf["Subtotal"] = carrito_df_pdf["Cantidad"] * carrito_df_pdf["Precio Unitario"]
                            subtotal_pdf = carrito_df_pdf["Subtotal"].sum()
                        else:
                            carrito_df_pdf = carrito_df_temp.copy()
                            subtotal_pdf = carrito_df_temp["Subtotal"].sum()
                        
                        iva_pdf = subtotal_pdf * 0.19
                        total_pdf = subtotal_pdf + iva_pdf
                        
                        datos_cliente_pdf = {
                            "Nombre": cotizacion.get('cliente_nombre', ''),
                            "RUT": cotizacion.get('cliente_rut', ''),
                            "Correo": cotizacion.get('cliente_email', ''),
                            "Teléfono": cotizacion.get('cliente_telefono', ''),
                            "Dirección": cotizacion.get('cliente_direccion', ''),
                            "Observaciones": cotizacion.get('proyecto_observaciones', '')
                        }
                        
                        datos_asesor_pdf = {
                            "Nombre Ejecutivo": cotizacion.get('asesor_nombre', ''),
                            "Correo Ejecutivo": cotizacion.get('asesor_email', ''),
                            "Teléfono Ejecutivo": cotizacion.get('asesor_telefono', '')
                        }
                        
                        fecha_inicio_pdf = datetime.strptime(
                            cotizacion.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), 
                            '%Y-%m-%d'
                        ).date()
                        fecha_termino_pdf = datetime.strptime(
                            cotizacion.get('proyecto_fecha_termino', (datetime.now() + timedelta(days=15)).strftime('%Y-%m-%d')), 
                            '%Y-%m-%d'
                        ).date()
                        dias_validez_pdf = cotizacion.get('proyecto_dias_validez', 15)
                        
                        pdf_buffer, _ = generar_pdf_cliente(
                            carrito_df_pdf, subtotal_pdf, iva_pdf, total_pdf,
                            datos_cliente_pdf, fecha_inicio_pdf, fecha_termino_pdf, dias_validez_pdf,
                            datos_asesor_pdf, margen=margen_cotizacion, numero_cotizacion=numero_seleccionado
                        )
                        
                        st.download_button(
                            label="🔒 PDF Cliente",
                            data=pdf_buffer,
                            file_name=f"Presupuesto_Cliente_{numero_seleccionado}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"pdf_cliente_{numero_seleccionado}"
                        )
                else:
                    st.button("🔒 PDF Cliente", use_container_width=True, disabled=True)

            with col_acc4:
                if st.button("🗑️ Eliminar", use_container_width=True):
                    if cotizacion_seleccionada:
                        if st.checkbox(f"¿Confirmar eliminación de {numero_seleccionado}?"):
                            eliminar_cotizacion(numero_seleccionado)
                            st.success(f"✅ Cotización {numero_seleccionado} eliminada")
                            st.session_state.resultados_busqueda = buscar_cotizaciones()
                            st.rerun()
        
        # =========================================================
        # ESTADÍSTICAS RÁPIDAS (PODEROSAS)
        # =========================================================
        st.markdown("---")
        st.markdown("### 📊 Estadísticas Rápidas")
        
        # Calcular estadísticas
        autorizadas = 0
        borradores = 0
        incompletos = 0
        total_cotizado = 0
        
        for row in st.session_state.resultados_busqueda:
            datos_completos = all([row[1], row[6], row[7]])
            asesor_completo = any([row[2], row[8], row[9]])
            total_valor = row[4] if row[4] else 0
            total_cotizado += total_valor
            
            if datos_completos and asesor_completo:
                if row[5] and row[5] > 0:
                    autorizadas += 1
                else:
                    borradores += 1
            else:
                incompletos += 1
        
        # Mostrar tarjetas de estadísticas con diseño PODEROSO
        col_est1, col_est2, col_est3, col_est4 = st.columns(4)
        
        with col_est1:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-title">💰 TOTAL COTIZADO</div>
                <div class="stats-number total">{formato_clp(total_cotizado)}</div>
                <div class="stats-desc">Total de cotizaciones en el sistema</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_est2:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-title">🟢 AUTORIZADAS</div>
                <div class="stats-number autorizadas">{autorizadas}</div>
                <div class="stats-desc">Cotizaciones aprobadas por supervisor con margen aplicado</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_est3:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-title">🟡 BORRADORES</div>
                <div class="stats-number borradores">{borradores}</div>
                <div class="stats-desc">Cotizaciones en edición, sin margen, datos completos</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_est4:
            st.markdown(f"""
            <div class="stats-card">
                <div class="stats-title">🔴 INCOMPLETAS</div>
                <div class="stats-number incompletas">{incompletos}</div>
                <div class="stats-desc">Cotizaciones incompletas, faltan datos del cliente o asesor</div>
            </div>
            """, unsafe_allow_html=True)
    
    else:
        st.info("💡 No hay resultados. Realice una búsqueda para ver cotizaciones guardadas.")