import streamlit as st
import streamlit.components.v1 as components
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
import json
import base64
import uuid
from supabase import create_client
import urllib.parse

st.set_page_config(layout="wide", page_title="Cotizador PRO", page_icon="📊")

# =========================================================
# CONFIGURACIÓN SUPABASE
# =========================================================
SUPABASE_URL = "https://rpjktwxitceqylexcaqw.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJwamt0d3hpdGNlcXlsZXhjYXF3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzI4MzUyMzYsImV4cCI6MjA4ODQxMTIzNn0.LoZN1W7X1pjVgNLFyVRfzQ8iHFp5JN2qw2Egu5yJq0E"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def verificar_conexion_supabase():
    try:
        response = supabase.table('cotizaciones').select('*').limit(1).execute()
        print("✅ Conexión a Supabase exitosa")
        return True
    except Exception as e:
        st.error(f"❌ Error conectando a Supabase: {e}")
        return False

verificar_conexion_supabase()

# =========================================================
# FUNCIONES PARA MANEJO DE PDFs EN STORAGE
# =========================================================
def guardar_plano_en_storage(archivo_pdf_bytes, cotizacion_numero, nombre_original):
    try:
        file_ext = ".pdf"
        carpeta = cotizacion_numero.replace('/', '_').replace('\\', '_')
        file_name = f"cotizacion-{carpeta}/{uuid.uuid4()}{file_ext}"
        response = supabase.storage.from_('planos').upload(
            path=file_name,
            file=archivo_pdf_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = supabase.storage.from_('planos').get_public_url(file_name)
        return public_url, None
    except Exception as e:
        return None, str(e)

def eliminar_plano_de_storage(url_plano):
    try:
        if not url_plano:
            return True, None
        if '/planos/' in url_plano:
            path = url_plano.split('/planos/')[-1]
            supabase.storage.from_('planos').remove([path])
        return True, None
    except Exception as e:
        return False, str(e)

def descargar_plano_desde_url(url_plano):
    try:
        if not url_plano:
            return None, None
        response = requests.get(url_plano)
        if response.status_code == 200:
            return response.content, None
        else:
            return None, f"Error HTTP: {response.status_code}"
    except Exception as e:
        return None, str(e)

# =========================================================
# FUNCIÓN PARA DETECTAR NAVEGADOR
# =========================================================
def detectar_navegador():
    try:
        user_agent = st.context.headers.get('User-Agent', '')
        es_chrome = 'Chrome' in user_agent and 'Edg' not in user_agent
        es_edge = 'Edg' in user_agent
        es_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
        return {
            'es_chrome': es_chrome,
            'es_edge': es_edge,
            'es_safari': es_safari,
            'es_firefox': 'Firefox' in user_agent,
            'needs_google_viewer': es_chrome or es_edge or es_safari
        }
    except:
        return {'needs_google_viewer': True}

# =========================================================
# INICIALIZAR VARIABLES DE SESIÓN
# =========================================================
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False
if 'mostrar_login' not in st.session_state:
    st.session_state.mostrar_login = False
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
if 'plano_adjunto' not in st.session_state:
    st.session_state.plano_adjunto = None
if 'plano_nombre' not in st.session_state:
    st.session_state.plano_nombre = ""
if 'cotizacion_seleccionada' not in st.session_state:
    st.session_state.cotizacion_seleccionada = None
if 'cotizacion_cargada' not in st.session_state:
    st.session_state.cotizacion_cargada = None
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
# ── Leer margen desde FAB via query_params ──────────────
_mgfab = st.query_params.get("mgfab")
if _mgfab is not None:
    try:
        _mgfab_val = max(0.0, min(100.0, float(_mgfab)))
        st.session_state['margen'] = _mgfab_val
    except ValueError:
        pass
    st.query_params.clear()
# ────────────────────────────────────────────────────────

if 'counter' not in st.session_state:
    st.session_state.counter = 0
if 'cargar_cotizacion_trigger' not in st.session_state:
    st.session_state.cargar_cotizacion_trigger = False
if 'cotizacion_a_cargar' not in st.session_state:
    st.session_state.cotizacion_a_cargar = None
if 'mostrar_visor' not in st.session_state:
    st.session_state.mostrar_visor = False
if 'pdf_actual' not in st.session_state:
    st.session_state.pdf_actual = None
    st.session_state.pdf_nombre = ""
if 'numero_en_visor' not in st.session_state:
    st.session_state.numero_en_visor = None
if 'pdf_url' not in st.session_state:
    st.session_state.pdf_url = None

if 'mostrar_toast_exito' not in st.session_state:
    st.session_state.mostrar_toast_exito = False

if 'toast_numero_ep' not in st.session_state:
    st.session_state.toast_numero_ep = ""

if 'recien_guardado' not in st.session_state:
    st.session_state.recien_guardado = False

if 'hash_ultimo_guardado' not in st.session_state:
    st.session_state.hash_ultimo_guardado = None

if 'recien_cargado' not in st.session_state:
    st.session_state.recien_cargado = False

if 'mostrar_advertencia_cerrar' not in st.session_state:
    st.session_state.mostrar_advertencia_cerrar = False

if 'trigger_cerrar_cotizacion' not in st.session_state:
    st.session_state.trigger_cerrar_cotizacion = False

if 'datos_pendientes_cerrar' not in st.session_state:
    st.session_state.datos_pendientes_cerrar = None

if 'numero_a_cargar_pendiente' not in st.session_state:
    st.session_state.numero_a_cargar_pendiente = None

CLAVE_ADMIN = "admin2024"

# =========================================================
# FUNCIONES DE VALIDACIÓN Y FORMATO
# =========================================================
def validar_rut(rut_completo):
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
    telefono_key = f"telefono_input_{st.session_state.counter}"
    if telefono_key in st.session_state:
        valor_actual = st.session_state[telefono_key]
        raw = re.sub(r'[^0-9]', '', valor_actual)
        if len(raw) > 9:
            raw = raw[:9]
        st.session_state.telefono_raw = raw

def leer_datos_actuales():
    mapeo_texto = {
        'nombre_input_':    'nombre_input',
        'correo_input_':    'correo_input',
        'direccion_input_': 'direccion_input',
        'observaciones_input_': 'observaciones_input',
        'asesor_correo_input_': 'correo_asesor',
    }
    for prefijo, campo in mapeo_texto.items():
        mejor_counter = -1
        mejor_valor = None
        for key, valor in st.session_state.items():
            if isinstance(key, str) and key.startswith(prefijo):
                try:
                    c = int(key[len(prefijo):])
                    if c > mejor_counter:
                        mejor_counter = c
                        mejor_valor = valor
                except ValueError:
                    pass
        if mejor_valor is not None:
            st.session_state[campo] = mejor_valor

    mejor_counter = -1
    mejor_rut = None
    for key, valor in st.session_state.items():
        if isinstance(key, str) and key.startswith('rut_input_'):
            try:
                c = int(key[len('rut_input_'):])
                if c > mejor_counter:
                    mejor_counter = c
                    mejor_rut = valor
            except ValueError:
                pass
    if mejor_rut is not None:
        raw = re.sub(r'[^0-9kK]', '', mejor_rut)[:9]
        st.session_state.rut_raw = raw
        st.session_state.rut_display = formatear_rut(raw) if raw else ""
        if len(raw) >= 2:
            valido, mensaje = validar_rut(raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje

    mejor_counter = -1
    mejor_tel = None
    for key, valor in st.session_state.items():
        if isinstance(key, str) and key.startswith('telefono_input_'):
            try:
                c = int(key[len('telefono_input_'):])
                if c > mejor_counter:
                    mejor_counter = c
                    mejor_tel = valor
            except ValueError:
                pass
    if mejor_tel is not None:
        raw = re.sub(r'[^0-9]', '', mejor_tel)[:9]
        st.session_state.telefono_raw = raw

    mejor_counter = -1
    mejor_tel_asesor = None
    for key, valor in st.session_state.items():
        if isinstance(key, str) and key.startswith('asesor_telefono_input_'):
            try:
                c = int(key[len('asesor_telefono_input_'):])
                if c > mejor_counter:
                    mejor_counter = c
                    mejor_tel_asesor = valor
            except ValueError:
                pass
    if mejor_tel_asesor is not None:
        raw = re.sub(r'[^0-9]', '', mejor_tel_asesor)[:9]
        st.session_state.telefono_asesor = raw

    mejor_counter = -1
    mejor_fi = None
    for key, valor in st.session_state.items():
        if isinstance(key, str) and key.startswith('fecha_inicio_'):
            try:
                c = int(key[len('fecha_inicio_'):])
                if c > mejor_counter:
                    mejor_counter = c
                    mejor_fi = valor
            except ValueError:
                pass
    if mejor_fi is not None:
        st.session_state.fecha_inicio = mejor_fi

    mejor_counter = -1
    mejor_ft = None
    for key, valor in st.session_state.items():
        if isinstance(key, str) and key.startswith('fecha_termino_'):
            try:
                c = int(key[len('fecha_termino_'):])
                if c > mejor_counter:
                    mejor_counter = c
                    mejor_ft = valor
            except ValueError:
                pass
    if mejor_ft is not None:
        st.session_state.fecha_termino = mejor_ft

def calcular_hash_estado():
    """Calcula un hash del estado actual para detectar cambios no guardados."""
    import hashlib
    estado = {
        "nombre": st.session_state.get('nombre_input', ''),
        "rut": st.session_state.get('rut_display', ''),
        "correo": st.session_state.get('correo_input', ''),
        "telefono": st.session_state.get('telefono_raw', ''),
        "direccion": st.session_state.get('direccion_input', ''),
        "observaciones": st.session_state.get('observaciones_input', ''),
        "asesor": st.session_state.get('asesor_seleccionado', ''),
        "correo_asesor": st.session_state.get('correo_asesor', ''),
        "telefono_asesor": st.session_state.get('telefono_asesor', ''),
        "fecha_inicio": str(st.session_state.get('fecha_inicio', '')),
        "fecha_termino": str(st.session_state.get('fecha_termino', '')),
        "carrito": json.dumps(st.session_state.get('carrito', []), sort_keys=True),
        "margen": st.session_state.get('margen', 0),
        "plano_nombre": st.session_state.get('plano_nombre', ''),
    }
    estado_str = json.dumps(estado, sort_keys=True)
    return hashlib.md5(estado_str.encode()).hexdigest()

def construir_datos_para_guardar():
    leer_datos_actuales()
    datos_cliente = {
        "Nombre": st.session_state.nombre_input or "",
        "RUT": st.session_state.rut_display or "",
        "Correo": st.session_state.correo_input or "",
        "Teléfono": st.session_state.telefono_raw or "",
        "Dirección": st.session_state.direccion_input or "",
        "Observaciones": st.session_state.observaciones_input or ""
    }
    nombre_asesor = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    datos_asesor = {
        "Nombre Ejecutivo": nombre_asesor,
        "Correo Ejecutivo": st.session_state.correo_asesor or "",
        "Teléfono Ejecutivo": st.session_state.telefono_asesor or ""
    }
    proyecto = {
        'fecha_inicio': str(st.session_state.fecha_inicio),
        'fecha_termino': str(st.session_state.fecha_termino),
        'dias_validez': (st.session_state.fecha_termino - st.session_state.fecha_inicio).days,
        'observaciones': st.session_state.observaciones_input or ""
    }
    config = {
        'margen': st.session_state.margen,
        'modo_admin': st.session_state.modo_admin
    }
    if st.session_state.carrito:
        carrito_df_temp = pd.DataFrame(st.session_state.carrito)
        subtotal_base_temp = carrito_df_temp["Subtotal"].sum()
        if st.session_state.modo_admin or st.session_state.margen > 0:
            subtotal_general_temp = sum(
                item["Cantidad"] * aplicar_margen(item["Precio Unitario"], st.session_state.margen)
                for item in st.session_state.carrito
            )
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
        subtotal_base_temp = subtotal_general_temp = iva_temp = total_temp = 0
        margen_valor_temp = comision_vendedor_temp = comision_supervisor_temp = utilidad_real_temp = 0
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
    plano_nombre = st.session_state.plano_nombre if st.session_state.plano_adjunto else None
    plano_datos = st.session_state.plano_adjunto if st.session_state.plano_adjunto else None
    return datos_cliente, datos_asesor, proyecto, config, totales, plano_nombre, plano_datos

# =========================================================
# FUNCIONES PARA EVALUAR ESTADO DE COTIZACIÓN
# =========================================================
def evaluar_estado_cotizacion(cotizacion):
    datos_completos = all([
        cotizacion.get('cliente_nombre', ''),
        cotizacion.get('cliente_email', '')
    ])
    asesor_completo = any([
        cotizacion.get('asesor_nombre', ''),
        cotizacion.get('asesor_email', ''),
        cotizacion.get('asesor_telefono', '')
    ])
    tiene_plano = cotizacion.get('plano_nombre') not in (None, '')
    if not datos_completos or not asesor_completo:
        return "🔴 INCOMPLETO CON PLANO" if tiene_plano else "🔴 INCOMPLETO"
    tiene_margen = cotizacion.get('config_margen', 0) > 0
    if tiene_margen:
        return "🟢 AUTORIZADO CON PLANO" if tiene_plano else "🟢 AUTORIZADO"
    else:
        return "🟠 BORRADOR CON PLANO" if tiene_plano else "🟡 BORRADOR"

def crear_badge_estado(row):
    config_margen = row[5]
    tiene_plano = row[10] if len(row) > 10 else False
    cliente_nombre = row[1]
    cliente_rut = row[6]
    cliente_email = row[7]
    asesor_nombre = row[2]
    asesor_email = row[8]
    asesor_telefono = row[9]
    datos_completos = all([cliente_nombre, cliente_email])
    asesor_completo = any([asesor_nombre, asesor_email, asesor_telefono])
    if config_margen and config_margen > 0:
        if datos_completos and asesor_completo:
            label = "🟢 AUTORIZADO CON PLANO" if tiene_plano else "🟢 AUTORIZADO"
            color = "#28a745"
            border = "#1e7e34"
        else:
            label = "🔴 INCOMPLETO CON PLANO" if tiene_plano else "🔴 INCOMPLETO"
            color = "#dc3545"
            border = "#bd2130"
    else:
        if datos_completos and asesor_completo:
            if tiene_plano:
                label = "🟠 BORRADOR CON PLANO"
                color = "#f97316"
                border = "#c2410c"
            else:
                label = "🟡 BORRADOR"
                color = "#ffc107"
                border = "#d39e00"
        else:
            label = "🔴 INCOMPLETO CON PLANO" if tiene_plano else "🔴 INCOMPLETO"
            color = "#dc3545"
            border = "#bd2130"
    text_color = "#212529" if label == "🟡 BORRADOR" else "white"
    return f'''<span style="background-color:{color};color:{text_color};padding:4px 12px;
        border-radius:20px;font-size:0.8rem;font-weight:600;display:inline-block;
        border:1px solid {border};box-shadow:0 2px 4px rgba(0,0,0,0.1);">{label}</span>'''

# =========================================================
# FUNCIONES PARA MANEJO DE MARGEN
# =========================================================
def aplicar_margen(precio_original, margen):
    return precio_original * (1 + margen / 100)

def calcular_totales_con_margen(carrito, margen):
    subtotal_con_margen = sum(
        item["Cantidad"] * aplicar_margen(item["Precio Unitario"], margen)
        for item in carrito
    )
    iva_con_margen = subtotal_con_margen * 0.19
    total_con_margen = subtotal_con_margen + iva_con_margen
    return subtotal_con_margen, iva_con_margen, total_con_margen

def calcular_comision_vendedor(subtotal_con_margen):
    return subtotal_con_margen * 0.025

def calcular_comision_supervisor(subtotal_con_margen):
    return subtotal_con_margen * 0.008

def calcular_utilidad_real(margen_valor, comision_vendedor, comision_supervisor):
    return margen_valor - comision_vendedor - comision_supervisor

def buscar_direccion(direccion):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": direccion, "format": "json", "addressdetails": 1, "limit": 1, "countrycodes": "cl"}
    try:
        response = requests.get(url, params=params, headers={"User-Agent": "epcontainer-app"}, timeout=5)
        data = response.json()
        if data:
            address = data[0]["address"]
            comuna = address.get("city") or address.get("town") or address.get("village")
            region = address.get("state")
            return comuna, region
    except:
        pass
    return None, None

def cargar_modelo(nombre_hoja):
    df_modelo = pd.read_excel("cotizador.xlsx", sheet_name=nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[df_modelo["Cantidad"] > 0]
    df_bd = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")[["Item", "P. Unitario real"]]
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    carrito = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        carrito.append({
            "Categoria": row["Categorias"], "Item": row["Item"],
            "Cantidad": row["Cantidad"], "Precio Unitario": row["P. Unitario real"], "Subtotal": subtotal
        })
    return carrito

def cargar_categoria_desde_modelo(nombre_hoja, categoria_objetivo):
    df_modelo = pd.read_excel("cotizador.xlsx", sheet_name=nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[(df_modelo["Cantidad"] > 0) & (df_modelo["Categorias"] == categoria_objetivo)]
    df_bd = pd.read_excel("cotizador.xlsx", sheet_name="BD Total")[["Item", "P. Unitario real"]]
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    categoria_items = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        categoria_items.append({
            "Categoria": row["Categorias"], "Item": row["Item"],
            "Cantidad": row["Cantidad"], "Precio Unitario": row["P. Unitario real"], "Subtotal": subtotal
        })
    return categoria_items

# =========================================================
# FUNCIONES DE SUPABASE PARA COTIZACIONES
# =========================================================
def guardar_cotizacion(numero, cliente, asesor, proyecto, productos, config, totales, plano_nombre=None, plano_datos=None):
    try:
        fecha_actual = datetime.now().isoformat()
        productos_json = json.dumps(productos, ensure_ascii=False)
        tiene_margen = float(config.get('margen', 0) or 0) > 0
        tiene_plano = plano_datos is not None
        datos_completos = all([
            str(cliente.get('Nombre', '')).strip(),
            str(cliente.get('Correo', '')).strip()
        ])
        asesor_completo = any([
            str(asesor.get('Nombre Ejecutivo', '')).strip(),
            str(asesor.get('Correo Ejecutivo', '')).strip(),
            str(asesor.get('Teléfono Ejecutivo', '')).strip()
        ])
        if not datos_completos or not asesor_completo:
            estado = "INCOMPLETO CON PLANO" if tiene_plano else "INCOMPLETO"
        elif tiene_margen:
            estado = "AUTORIZADO CON PLANO" if tiene_plano else "AUTORIZADO"
        else:
            estado = "BORRADOR CON PLANO" if tiene_plano else "BORRADOR"

        response = supabase.table('cotizaciones').select('*').eq('numero', numero).execute()
        existe = len(response.data) > 0

        plano_url = None
        if plano_datos:
            if existe and response.data[0].get('plano_url'):
                eliminar_plano_de_storage(response.data[0]['plano_url'])
            plano_url, error = guardar_plano_en_storage(plano_datos, numero, plano_nombre)
            if error:
                st.error(f"Error al subir plano: {error}")

        data = {
            'numero': numero,
            'fecha_modificacion': fecha_actual,
            'estado': estado,
            'cliente_nombre': str(cliente.get('Nombre', '') or ''),
            'cliente_rut': str(cliente.get('RUT', '') or ''),
            'cliente_email': str(cliente.get('Correo', '') or ''),
            'cliente_telefono': str(cliente.get('Teléfono', '') or ''),
            'cliente_direccion': str(cliente.get('Dirección', '') or ''),
            'asesor_nombre': str(asesor.get('Nombre Ejecutivo', '') or ''),
            'asesor_email': str(asesor.get('Correo Ejecutivo', '') or ''),
            'asesor_telefono': str(asesor.get('Teléfono Ejecutivo', '') or ''),
            'proyecto_fecha_inicio': str(proyecto.get('fecha_inicio', '') or ''),
            'proyecto_fecha_termino': str(proyecto.get('fecha_termino', '') or ''),
            'proyecto_dias_validez': int(proyecto.get('dias_validez', 0) or 0),
            'proyecto_observaciones': str(proyecto.get('observaciones', '') or ''),
            'productos': productos_json,
            'config_margen': float(config.get('margen', 0) or 0),
            'config_modo_admin': 1 if config.get('modo_admin', False) else 0,
            'total_subtotal_sin_margen': float(totales.get('subtotal_sin_margen', 0) or 0),
            'total_subtotal_con_margen': float(totales.get('subtotal_con_margen', 0) or 0),
            'total_iva': float(totales.get('iva', 0) or 0),
            'total_total': float(totales.get('total', 0) or 0),
            'total_margen_valor': float(totales.get('margen_valor', 0) or 0),
            'total_comision_vendedor': float(totales.get('comision_vendedor', 0) or 0),
            'total_comision_supervisor': float(totales.get('comision_supervisor', 0) or 0),
            'total_utilidad_real': float(totales.get('utilidad_real', 0) or 0),
            'plano_nombre': plano_nombre if plano_datos else (response.data[0].get('plano_nombre') if existe else None),
            'plano_url': plano_url if plano_datos else (response.data[0].get('plano_url') if existe else None)
        }

        if existe:
            response = supabase.table('cotizaciones').update(data).eq('numero', numero).execute()
        else:
            data['fecha_creacion'] = fecha_actual
            response = supabase.table('cotizaciones').insert(data).execute()

        return True
    except Exception as e:
        st.error(f"❌ Error al guardar cotización: {e}")
        return False

def buscar_cotizaciones(termino=None, tipo_busqueda='numero'):
    try:
        query = supabase.table('cotizaciones').select(
            'numero', 'cliente_nombre', 'asesor_nombre', 'fecha_creacion',
            'total_total', 'config_margen', 'cliente_rut', 'cliente_email',
            'asesor_email', 'asesor_telefono', 'plano_url'
        )
        if termino and termino.strip():
            campo_map = {
                'numero': 'numero',
                'cliente': 'cliente_nombre',
                'asesor': 'asesor_nombre'
            }
            campo = campo_map.get(tipo_busqueda, 'numero')
            query = query.ilike(campo, f'%{termino}%')
        query = query.order('fecha_creacion', desc=True).limit(50)
        response = query.execute()
        resultados = []
        for row in response.data:
            resultados.append((
                row.get('numero', ''),
                row.get('cliente_nombre', '') or '',
                row.get('asesor_nombre', '') or '',
                row.get('fecha_creacion', '') or '',
                row.get('total_total', 0) or 0,
                row.get('config_margen', 0) or 0,
                row.get('cliente_rut', '') or '',
                row.get('cliente_email', '') or '',
                row.get('asesor_email', '') or '',
                row.get('asesor_telefono', '') or '',
                1 if row.get('plano_url') else 0
            ))
        return resultados
    except Exception as e:
        st.error(f"Error en búsqueda: {e}")
        return []

def cargar_cotizacion(numero):
    try:
        if not numero:
            return None
        response = supabase.table('cotizaciones').select('*').eq('numero', numero).execute()
        if response.data:
            cotizacion = response.data[0]
            # Manejar productos como string JSON o como lista directamente
            productos = cotizacion['productos']
            if isinstance(productos, str):
                cotizacion['productos'] = json.loads(productos)
            elif isinstance(productos, list):
                cotizacion['productos'] = productos
            else:
                cotizacion['productos'] = []
            if cotizacion.get('plano_url'):
                cotizacion['plano_datos'] = None
            return cotizacion
        return None
    except Exception as e:
        st.error(f"Error al cargar cotización: {e}")
        return None

def eliminar_cotizacion(numero):
    try:
        response = supabase.table('cotizaciones').select('plano_url').eq('numero', numero).execute()
        if response.data and response.data[0].get('plano_url'):
            eliminar_plano_de_storage(response.data[0]['plano_url'])
        response = supabase.table('cotizaciones').delete().eq('numero', numero).execute()
        return True
    except Exception as e:
        st.error(f"Error al eliminar: {e}")
        return False

def actualizar_estado_cotizacion(numero, estado):
    try:
        fecha_actual = datetime.now().isoformat()
        response = supabase.table('cotizaciones').update({
            'estado': estado,
            'fecha_modificacion': fecha_actual
        }).eq('numero', numero).execute()
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado: {e}")
        return False

def generar_numero_unico():
    intentos = 0
    while intentos < 20:
        numero = f"EP-{random.randint(10000, 99999)}"
        try:
            response = supabase.table('cotizaciones').select('numero').eq('numero', numero).execute()
            if not response.data:
                return numero
        except:
            pass
        intentos += 1
    return f"EP-{int(datetime.now().timestamp())}"

# =========================================================
# FUNCIÓN PARA CARGAR COTIZACIÓN EN EL SISTEMA
# =========================================================
def preparar_carga_cotizacion(numero_cotizacion):
    cotizacion = cargar_cotizacion(numero_cotizacion)
    if cotizacion:
        tiene_margen = cotizacion.get('config_margen', 0) > 0
        if tiene_margen and not st.session_state.modo_admin:
            return False
        else:
            st.session_state.cotizacion_a_cargar = cotizacion
            st.session_state.cargar_cotizacion_trigger = True
            return True
    return False

def ejecutar_carga_cotizacion():
    if st.session_state.cargar_cotizacion_trigger and st.session_state.cotizacion_a_cargar:
        cotizacion = st.session_state.cotizacion_a_cargar
        st.session_state.carrito = cotizacion['productos']
        st.session_state.nombre_input = cotizacion.get('cliente_nombre', '')
        rut_valor = cotizacion.get('cliente_rut', '')
        st.session_state.rut_display = rut_valor
        st.session_state.rut_raw = re.sub(r'[^0-9kK]', '', rut_valor)
        if st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            valido, mensaje = validar_rut(st.session_state.rut_raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje
        else:
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = "RUT incompleto"
        st.session_state.correo_input = cotizacion.get('cliente_email', '')
        st.session_state.telefono_raw = cotizacion.get('cliente_telefono', '')
        st.session_state.direccion_input = cotizacion.get('cliente_direccion', '')
        nombre_asesor = cotizacion.get('asesor_nombre', '')
        st.session_state.asesor_seleccionado = nombre_asesor if nombre_asesor else "Seleccionar asesor"
        st.session_state.correo_asesor = cotizacion.get('asesor_email', '')
        st.session_state.telefono_asesor = cotizacion.get('asesor_telefono', '')
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
        st.session_state.modo_admin = bool(cotizacion.get('config_modo_admin', False))
        margen_valor = cotizacion.get('config_margen')
        try:
            st.session_state.margen = float(margen_valor) if margen_valor is not None else 0.0
        except (ValueError, TypeError):
            st.session_state.margen = 0.0
        plano_nombre = cotizacion.get('plano_nombre')
        plano_url = cotizacion.get('plano_url')
        if plano_nombre and plano_url:
            st.session_state.plano_nombre = plano_nombre
            st.session_state.pdf_url = plano_url
            st.session_state.plano_adjunto = None
        else:
            st.session_state.plano_nombre = ""
            st.session_state.plano_adjunto = None
            st.session_state.pdf_url = None
        st.session_state.cotizacion_cargada = cotizacion.get('numero', '')
        st.session_state.counter += 100
        st.session_state.mostrar_visor = False
        st.session_state.pdf_actual = None
        st.session_state.pdf_nombre = ""
        st.session_state.numero_en_visor = None
        st.session_state.cargar_cotizacion_trigger = False
        st.session_state.cotizacion_a_cargar = None
        # Resetear hash y marcar como recién cargado para suprimir FAB
        st.session_state.hash_ultimo_guardado = calcular_hash_estado()
        st.session_state.recien_cargado = True
        return True
    return False

# =========================================================
# EJECUTAR CARGA DE COTIZACIÓN SI HAY TRIGGER
# =========================================================
ejecutar_carga_cotizacion()

# =========================================================
# CSS PERSONALIZADO
# =========================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');



    /* ══ FAB margen iframe — sacarlo del flujo ══ */
    /* El último iframe de components antes del final se posiciona fixed */
    [data-testid="stBottom"] ~ div iframe:last-of-type {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        width: 400px !important;
        height: 300px !important;
        border: none !important;
        z-index: 999990 !important;
        pointer-events: auto !important;
        background: transparent !important;
    }

    /* ══ Sombra tabla data_editor / dataframe ══ */
    div[data-testid="stDataFrame"] > div,
    div[data-testid="stDataEditor"] > div {
        border-radius: 16px !important;
        box-shadow: 0 4px 20px rgba(91, 124, 250, 0.08), 0 1px 6px rgba(0,0,0,0.06) !important;
        border: 1px solid rgba(91,124,250,0.15) !important;
        overflow: hidden !important;
        transition: box-shadow 0.25s ease, transform 0.25s ease !important;
        background: #ffffff !important;
    }
    div[data-testid="stDataFrame"] > div:hover,
    div[data-testid="stDataEditor"] > div:hover {
        box-shadow: 0 8px 32px rgba(91, 124, 250, 0.16), 0 2px 10px rgba(0,0,0,0.08) !important;
        transform: translateY(-2px) !important;
    }

    /* ══ Sombra flotante para containers con borde ══ */
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
        box-shadow: 0 4px 20px rgba(91, 124, 250, 0.08), 0 1px 6px rgba(0,0,0,0.06) !important;
        border: 1px solid rgba(91,124,250,0.15) !important;
        border-radius: 16px !important;
        transition: box-shadow 0.25s ease, transform 0.25s ease !important;
        background: #ffffff !important;
    }
    [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 8px 32px rgba(91, 124, 250, 0.16), 0 2px 10px rgba(0,0,0,0.08) !important;
        transform: translateY(-2px) !important;
    }


    #MainMenu { display: none !important; }
    footer { display: none !important; }
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stStatusWidget"] { display: none !important; }
    [data-testid="stBottomBlockContainer"] { display: none !important; }
    [class*="viewerBadge"] { display: none !important; }
    [class*="ViewerBadge"] { display: none !important; }
    [class*="_viewerBadge"] { display: none !important; }
    [class*="profileContainer"] { display: none !important; }
    [class*="_profileContainer"] { display: none !important; }
    [class*="profilePreview"] { display: none !important; }
    [class*="_profilePreview"] { display: none !important; }
    a[href*="streamlit.io"] { display: none !important; }
    a[href*="github.com"] { display: none !important; }
    button[title="View fullscreen"] { display: none !important; }

    /* ══ BASE ══ */
    html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }
    .stApp { background-color: #f0f2f8 !important; }

    /* ══ INPUTS ══ */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        background-color: #ffffff !important; color: #1a1d2e !important;
        border: 1.5px solid #e2e6f3 !important; border-radius: 10px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important; font-size: 0.9rem !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #5b7cfa !important;
        box-shadow: 0 0 0 3px rgba(91,124,250,0.13) !important;
    }
    [data-baseweb="select"] > div {
        background-color: #ffffff !important; border: 1.5px solid #e2e6f3 !important;
        border-radius: 10px !important; color: #1a1d2e !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05) !important;
    }
    [data-baseweb="select"] span,
    .stSelectbox > div > div,
    .stSelectbox > div > div > div { color: #1a1d2e !important; }
    .stTextInput label, .stSelectbox label, .stNumberInput label,
    .stDateInput label, .stTextArea label, .stRadio label,
    .stCheckbox label, .stFileUploader label {
        color: #5a6080 !important; font-weight: 600 !important;
        font-size: 0.8rem !important; letter-spacing: 0.04em !important;
        text-transform: uppercase !important;
    }

    /* ══ BOTONES ══ */
    .stButton > button {
        background-color: #ffffff !important; color: #2a3060 !important;
        border: 1.5px solid #dde1f0 !important; border-radius: 10px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 600 !important; font-size: 0.875rem !important;
        transition: all 0.2s cubic-bezier(0.4,0,0.2,1) !important;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
    }
    .stButton > button:hover {
        background-color: #eef1ff !important; border-color: #5b7cfa !important;
        color: #2a3060 !important; transform: translateY(-1px) !important;
        box-shadow: 0 4px 14px rgba(91,124,250,0.18) !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%) !important;
        color: #ffffff !important; border: none !important;
        box-shadow: 0 4px 16px rgba(91,124,250,0.4) !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 24px rgba(91,124,250,0.5) !important;
    }
    .stDownloadButton > button {
        background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%) !important;
        color: #ffffff !important; border: none !important; border-radius: 10px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 600 !important;
        box-shadow: 0 4px 16px rgba(91,124,250,0.35) !important;
    }
    .stDownloadButton > button:hover { transform: translateY(-1px) !important; }
    .stPopover > button {
        background-color: #ffffff !important; color: #2a3060 !important;
        border: 1.5px solid #dde1f0 !important; border-radius: 10px !important;
    }

    /* ══ TABS ══ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0 !important; border-bottom: 2px solid #e2e6f3 !important;
        padding: 0 !important; margin-bottom: 2rem !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.88rem !important; font-weight: 600 !important;
        color: #9099be !important; padding: 0.75rem 1.4rem !important;
        background: transparent !important; border: none !important;
        border-bottom: 2px solid transparent !important;
        margin-bottom: -2px !important; letter-spacing: 0.02em !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #5b7cfa !important; background: rgba(91,124,250,0.05) !important; }
    .stTabs [aria-selected="true"] {
        color: #5b7cfa !important; border-bottom: 2px solid #5b7cfa !important;
        font-weight: 700 !important; background: rgba(91,124,250,0.06) !important;
    }

    /* ══ TABLA RESULTADOS ══ */
    .resultados-table {
        width: 100%; border-collapse: separate; border-spacing: 0;
        font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.875rem;
        border-radius: 14px; overflow: hidden;
        box-shadow: 0 4px 20px rgba(0,0,0,0.07); background: #ffffff;
    }
    .resultados-table th {
        background: linear-gradient(135deg, #1e2447 0%, #2a3060 100%) !important;
        color: #ffffff !important; font-weight: 700 !important;
        padding: 14px 16px !important; text-align: left !important;
        font-size: 0.75rem !important; letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
    }
    .resultados-table td {
        padding: 12px 16px !important; border-bottom: 1px solid #f0f2f8 !important;
        color: #3a4070 !important; background-color: #ffffff !important;
        transition: background 0.15s !important;
    }
    .resultados-table tr:hover td { background-color: #f5f7ff !important; }
    .resultados-table tr:last-child td { border-bottom: none !important; }

    /* ══ METRIC CARDS ══ */
    .metric-card {
        background: linear-gradient(150deg, #1e2447 0%, #252d5a 100%);
        border-radius: 16px; padding: 1.4rem 1.5rem;
        box-shadow: 0 8px 28px rgba(30,36,71,0.22);
        border: 1px solid rgba(255,255,255,0.07);
        transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
        height: 100%; position: relative; overflow: hidden;
    }
    .metric-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #5b7cfa, #8b5cf6);
    }
    .metric-card::after {
        content: ''; position: absolute; bottom: -30px; right: -30px;
        width: 100px; height: 100px; border-radius: 50%;
        background: rgba(91,124,250,0.08);
    }
    .metric-card:hover { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(30,36,71,0.3); }
    .metric-title {
        font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
        letter-spacing: 0.1em; color: #7b84b0; margin-bottom: 0.7rem;
    }
    .metric-value {
        font-size: 2.5rem; font-weight: 800; line-height: 1.05;
        letter-spacing: -0.04em; color: #e8ecff;
    }
    .metric-change { font-size: 0.75rem; color: #5c6494; margin-top: 0.35rem; }

    /* ══ TARJETAS COLOREADAS ══ */
    .metric-card-special {
        border-radius: 18px; padding: 1.5rem;
        box-shadow: 0 8px 28px rgba(0,0,0,0.14);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        border: 1px solid rgba(255,255,255,0.2);
        height: 100%; display: flex; flex-direction: column;
        position: relative; overflow: hidden;
    }
    .metric-card-special::before {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 120px; height: 120px; border-radius: 50%;
        background: rgba(255,255,255,0.1);
    }
    .metric-card-special::after {
        content: ''; position: absolute; bottom: -20px; left: -20px;
        width: 80px; height: 80px; border-radius: 50%;
        background: rgba(255,255,255,0.06);
    }
    .metric-card-special:hover { transform: translateY(-5px); box-shadow: 0 20px 50px rgba(0,0,0,0.2); }
    .metric-card-total { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
    .metric-card-comisiones { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
    .metric-card-utilidad { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }

    /* ══ STATS CARDS ══ */
    .stats-card {
        background: #ffffff; border-radius: 16px; padding: 1.5rem 1.6rem;
        border: 1.5px solid #e8ebf5;
        box-shadow: 0 2px 12px rgba(0,0,0,0.05);
        transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
        height: 100%; position: relative; overflow: hidden;
    }
    .stats-card::after {
        content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 3px;
        background: linear-gradient(90deg, #5b7cfa, #8b5cf6);
        transform: scaleX(0); transform-origin: left;
        transition: transform 0.3s ease;
    }
    .stats-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(91,124,250,0.12); border-color: #c5ccf0; }
    .stats-card:hover::after { transform: scaleX(1); }
    .stats-title {
        font-size: 0.72rem; font-weight: 700; color: #9099be;
        text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem;
    }
    .stats-number {
        font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: 0.5rem 0;
        letter-spacing: -0.04em; padding: 0.5rem 0; text-align: center;
        border-top: 1.5px solid #eaedf5; border-bottom: 1.5px solid #eaedf5;
    }
    .stats-number.total { color: #5b7cfa !important; }
    .stats-number.autorizadas { color: #10b981 !important; }
    .stats-number.borradores { color: #f59e0b !important; }
    .stats-number.incompletas { color: #ef4444 !important; }
    .stats-desc { font-size: 0.78rem; color: #a0a8c8; text-align: center; margin-top: 0.25rem; }

    /* ══ HEADER ══ */
    .main-title {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 2rem !important; font-weight: 800 !important;
        background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        letter-spacing: -0.04em; line-height: 1.15;
    }
    .sub-title {
        color: #9099be; font-size: 0.82rem; font-weight: 500;
        margin-top: 0.2rem; letter-spacing: 0.02em;
    }

    /* ══ STATUS BADGE ══ */
    .cotizacion-status-container {
        background: #ffffff; border-radius: 50px;
        padding: 0.5rem 1.2rem 0.5rem 1.5rem;
        margin-bottom: 1rem; border: 1.5px solid #e2e6f3;
        box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        display: inline-flex; align-items: center; gap: 1rem;
    }
    .status-badge { font-size: 0.875rem; font-weight: 600; color: #2a3060; }

    /* ══ MODO ADMIN ══ */
    .modo-admin-indicator {
        background: linear-gradient(135deg, #f59e0b, #d97706);
        color: white; padding: 0.3rem 0.9rem; border-radius: 20px;
        font-size: 0.75rem; font-weight: 700; letter-spacing: 0.04em;
        box-shadow: 0 3px 10px rgba(245,158,11,0.35);
    }

    /* ══ SECCIONES ══ */
    div[data-testid="stExpander"] {
        border: 1.5px solid #e2e6f3 !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.04) !important;
        overflow: hidden !important;
        background: #ffffff !important;
    }

    /* ══ ALERTAS ══ */
    .stAlert { border-radius: 12px !important; border: none !important; font-family: 'Plus Jakarta Sans', sans-serif !important; }
    .stSuccess { background: rgba(16,185,129,0.1) !important; color: #065f46 !important; }
    .stError { background: rgba(239,68,68,0.1) !important; color: #991b1b !important; }
    .stWarning { background: rgba(245,158,11,0.1) !important; color: #92400e !important; }
    .stInfo { background: rgba(91,124,250,0.1) !important; color: #1e3a8a !important; }

    /* ══ SEPARADORES ══ */
    hr { border: none !important; border-top: 1.5px solid #e8ebf5 !important; margin: 1.5rem 0 !important; }

    /* ══ SCROLLBAR ══ */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: #f0f2f8; }
    ::-webkit-scrollbar-thumb { background: #c5ccf0; border-radius: 10px; }
    ::-webkit-scrollbar-thumb:hover { background: #5b7cfa; }

    /* ══ TIPOGRAFÍA GENERAL ══ */
    h1, h2, h3, h4 { font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 700 !important; color: #1a1d2e !important; letter-spacing: -0.03em !important; }
    .stMarkdown p { color: #4a5270 !important; line-height: 1.7 !important; font-family: 'Plus Jakarta Sans', sans-serif !important; }

    /* ══ NUMBER INPUT ══ */
    .stNumberInput button { border-radius: 8px !important; }

    /* ══ FILE UPLOADER ══ */
    [data-testid="stFileUploader"] { border-radius: 12px !important; }

    /* ══ RADIO BUTTONS ══ */
    .stRadio > div { gap: 0.5rem !important; }

    /* ══ FAB GUARDAR FLOTANTE ══ */
    .fab-guardar {
        background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%);
        color: white;
        border: none;
        border-radius: 50px;
        padding: 0.9rem 1.6rem;
        font-size: 0.95rem;
        font-weight: 700;
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-family: 'Plus Jakarta Sans', sans-serif;
        letter-spacing: 0.02em;
        animation: pulse-fab 2s infinite;
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
    }
    .fab-guardar:hover {
        transform: translateY(-3px) scale(1.05);
        box-shadow: 0 16px 40px rgba(91,124,250,0.7) !important;
        animation: none;
    }
    .fab-guardar:active {
        transform: scale(0.97);
    }
    @keyframes pulse-fab {
        0%   { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
        50%  { box-shadow: 0 8px 40px rgba(91,124,250,0.9), 0 0 0 12px rgba(91,124,250,0.15); }
        100% { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
    }
    .fab-badge {
        position: absolute;
        top: -5px;
        right: -5px;
        width: 14px;
        height: 14px;
        background: #ef4444;
        border-radius: 50%;
        border: 2px solid white;
        animation: blink-badge 1.5s infinite;
    }
    @keyframes blink-badge {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.2; }
    }
</style>
""", unsafe_allow_html=True)

st.markdown('''
<style>
.stMarkdown h3 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    color: #1e2447 !important;
    letter-spacing: -0.02em !important;
    padding-left: 0.9rem !important;
    border-left: 3.5px solid #5b7cfa !important;
    margin: 1.2rem 0 0.8rem 0 !important;
    line-height: 1.4 !important;
}
.stMarkdown h4 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 700 !important;
    color: #2a3060 !important;
    letter-spacing: -0.01em !important;
    margin: 1rem 0 0.6rem 0 !important;
}
.block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
}
[data-testid="stCheckbox"] span,
[data-testid="stRadio"] span {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 500 !important;
    color: #3a4070 !important;
}
[data-testid="stMetric"] {
    background: #ffffff;
    border-radius: 14px;
    padding: 1rem 1.2rem;
    border: 1.5px solid #e8ebf5;
    box-shadow: 0 2px 10px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.75rem !important; font-weight: 700 !important;
    text-transform: uppercase !important; letter-spacing: 0.07em !important;
    color: #9099be !important;
}
[data-testid="stMetricValue"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 800 !important; color: #1e2447 !important;
    letter-spacing: -0.03em !important;
}
[data-testid="stPopover"] [data-testid="stMarkdown"] h3 {
    border-left: none !important; padding-left: 0 !important;
    font-size: 1rem !important;
}
</style>
''', unsafe_allow_html=True)

_tema = st.get_option("theme.base") or "light"
if _tema == "dark":
    st.markdown('''<style>
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        background-color: #1e293b !important; color: #f1f5f9 !important; border: 1px solid #334155 !important;
    }
    .stSelectbox > div > div, .stSelectbox > div > div > div {
        background-color: #1e293b !important; color: #f1f5f9 !important;
    }
    [data-baseweb="select"] > div { background-color: #1e293b !important; border-color: #334155 !important; color: #f1f5f9 !important; }
    [data-baseweb="select"] span { color: #f1f5f9 !important; }
    .stTextInput label, .stSelectbox label, .stNumberInput label,
    .stDateInput label, .stTextArea label, .stRadio label, .stCheckbox label { color: #94a3b8 !important; }
    .stButton > button { background-color: #1e293b !important; color: #f1f5f9 !important; border: 1px solid #334155 !important; }
    .stButton > button:hover { background-color: #334155 !important; color: #ffffff !important; }
    .stPopover > button { background-color: #1e293b !important; color: #f1f5f9 !important; border: 1px solid #334155 !important; }
    .resultados-table { background: #1e293b !important; border-color: #334155 !important; }
    .resultados-table th { background-color: #0f172a !important; color: #f1f5f9 !important; border-bottom: 2px solid #334155 !important; }
    .resultados-table td { color: #cbd5e1 !important; background-color: #1e293b !important; border-bottom: 1px solid #334155 !important; }
    .resultados-table tr:hover td { background-color: #334155 !important; }
    .stats-card { background: #1e293b !important; border: 1px solid #334155 !important; }
    .stats-title { color: #94a3b8 !important; }
    .stats-desc { color: #64748b !important; }
    .stats-number { border-color: #334155 !important; }
    </style>''', unsafe_allow_html=True)

# =========================================================
# HEADER
# =========================================================
st.markdown('''<div id="header-marker"></div>''', unsafe_allow_html=True)
st.markdown('''
<style>
#header-marker + div [data-testid="stHorizontalBlock"] > div:last-child > div {
    display: flex !important;
    flex-direction: column !important;
    align-items: flex-end !important;
    text-align: right !important;
}
#header-marker + div [data-testid="stHorizontalBlock"] > div:last-child img {
    margin-left: auto !important;
    display: block !important;
}
#header-marker + div [data-testid="stHorizontalBlock"] > div:last-child .stPopover {
    margin-left: auto !important;
}
</style>
''', unsafe_allow_html=True)

import base64 as _b64, os as _os

_logo_html = ""
if _os.path.exists("logo.png"):
    with open("logo.png", "rb") as _f:
        _logo_b64 = _b64.b64encode(_f.read()).decode()
    _logo_html = f'<img src="data:image/png;base64,{_logo_b64}" width="350" style="display:block;margin-left:auto;">'
else:
    _logo_html = '''<svg width="350" height="48" viewBox="0 0 130 48" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;margin-left:auto;">
        <rect width="350" height="48" rx="8" fill="url(#hg)"/>
        <path d="M26 16L32 21L26 26L20 21L26 16Z" fill="white"/>
        <circle cx="65" cy="21" r="5" fill="#FFD966"/>
        <text x="82" y="26" font-family="Inter" font-size="13" font-weight="700" fill="white">PRO</text>
        <defs><linearGradient id="hg" x1="0" y1="0" x2="130" y2="48" gradientUnits="userSpaceOnUse">
            <stop stop-color="#3B82F6"/><stop offset="1" stop-color="#8B5CF6"/>
        </linearGradient></defs>
    </svg>'''

st.markdown(f'''
<div style="
    display:flex; justify-content:space-between; align-items:center;
    padding: 1.2rem 1.8rem;
    background: #ffffff;
    border-radius: 18px;
    border: 1.5px solid #e2e6f3;
    box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    margin-bottom: 1.5rem;
">
    <div style="display:flex; flex-direction:column; gap:0.15rem;">
        <span class="main-title">Cotizador PRO</span>
        <div class="sub-title">Sistema profesional de cotizaciones</div>
    </div>
    <div style="display:flex; flex-direction:column; align-items:flex-end; gap:0.5rem;">
        {_logo_html}
    </div>
</div>
''', unsafe_allow_html=True)

_, col_admin = st.columns([4, 1])
with col_admin:
    if st.session_state.modo_admin:
        st.markdown("**👑 Admin Activo**")
        if st.button("🔓 Cerrar", key="btn_cerrar_sesion_header", use_container_width=True):
            st.session_state.modo_admin = False
            st.rerun()
    else:
        with st.popover("🔐 Admin", use_container_width=True):
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

# =========================================================
# BADGE DE COTIZACIÓN CARGADA
# =========================================================
if st.session_state.cotizacion_cargada:
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

    if st.session_state.margen > 0:
        if datos_completos and asesor_completo:
            rol = "👑 Admin" if st.session_state.modo_admin else "🔒 Solo lectura"
            sufijo = " CON PLANO" if st.session_state.plano_adjunto else ""
            badge_html = f"{rol} • 🟢 AUTORIZADO{sufijo} ({st.session_state.margen}%)"
        else:
            sufijo = " CON PLANO" if st.session_state.plano_adjunto else ""
            badge_html = f"⚠️ {st.session_state.cotizacion_cargada} • 🔴 INCOMPLETO{sufijo}"
    else:
        if datos_completos and asesor_completo:
            if st.session_state.plano_adjunto:
                badge_html = f"📝 {st.session_state.cotizacion_cargada} • 🟠 BORRADOR CON PLANO"
            else:
                badge_html = f"📝 {st.session_state.cotizacion_cargada} • 🟡 BORRADOR"
        else:
            sufijo = " CON PLANO" if st.session_state.plano_adjunto else ""
            badge_html = f"⚠️ {st.session_state.cotizacion_cargada} • 🔴 INCOMPLETO{sufijo}"

    col_badge, col_cerrar = st.columns([3, 1])
    with col_badge:
        st.markdown(f'<div class="cotizacion-status-container"><span class="status-badge">{badge_html}</span></div>', unsafe_allow_html=True)
    with col_cerrar:
        if st.button("🗑️ Cerrar Cotización", key="btn_cerrar_cotizacion", use_container_width=True):
            _hash_actual = calcular_hash_estado()
            _hay_cambios = (
                len(st.session_state.get('carrito', [])) > 0 and
                _hash_actual != st.session_state.get('hash_ultimo_guardado')
            )
            if _hay_cambios:
                # Capturar todos los datos AHORA antes del rerun, mientras los widgets existen
                leer_datos_actuales()
                datos_c, datos_a, proy, cfg, tots, pnom, pdat = construir_datos_para_guardar()
                st.session_state.datos_pendientes_cerrar = {
                    'datos_cliente': datos_c,
                    'datos_asesor': datos_a,
                    'proyecto': proy,
                    'config': cfg,
                    'totales': tots,
                    'plano_nombre': pnom,
                    'plano_datos': pdat,
                    'carrito': list(st.session_state.carrito),
                    'numero': st.session_state.cotizacion_cargada,
                }
                st.session_state.mostrar_advertencia_cerrar = True
            else:
                st.session_state.trigger_cerrar_cotizacion = True
            st.rerun()

    # ── Popup advertencia al cerrar con cambios sin guardar ──
    if st.session_state.get('mostrar_advertencia_cerrar', False):
        @st.dialog("⚠️ Cambios sin guardar")
        def dialogo_advertencia_cerrar():
            st.markdown("""
            <div style="text-align:center;padding:1rem 0;">
                <div style="font-size:3rem;margin-bottom:0.5rem;">⚠️</div>
                <div style="font-size:1rem;font-weight:700;color:#1e2447;margin-bottom:0.5rem;">
                    Se hicieron modificaciones
                </div>
                <div style="font-size:0.88rem;color:#5a6080;line-height:1.6;">
                    Tienes cambios sin guardar en esta cotización.<br/>
                    ¿Qué deseas hacer antes de cerrar?
                </div>
            </div>
            """, unsafe_allow_html=True)

            col_si, col_no, col_cancelar = st.columns(3)
            with col_si:
                if st.button("💾 Guardar y cerrar", use_container_width=True, type="primary", key="dialog_cerrar_si"):
                    # Usar datos capturados antes del rerun
                    d = st.session_state.get('datos_pendientes_cerrar', {})
                    num = d.get('numero') or generar_numero_unico()
                    guardar_cotizacion(
                        num,
                        d.get('datos_cliente', {}),
                        d.get('datos_asesor', {}),
                        d.get('proyecto', {}),
                        d.get('carrito', []),
                        d.get('config', {}),
                        d.get('totales', {}),
                        d.get('plano_nombre', ''),
                        d.get('plano_datos', None)
                    )
                    st.session_state.datos_pendientes_cerrar = None
                    st.session_state.mostrar_advertencia_cerrar = False
                    st.session_state.trigger_cerrar_cotizacion = True
                    st.rerun()
            with col_no:
                if st.button("🗑️ Descartar y cerrar", use_container_width=True, key="dialog_cerrar_no"):
                    st.session_state.datos_pendientes_cerrar = None
                    st.session_state.mostrar_advertencia_cerrar = False
                    st.session_state.trigger_cerrar_cotizacion = True
                    st.rerun()
            with col_cancelar:
                if st.button("✖️ Cancelar", use_container_width=True, key="dialog_cerrar_cancelar"):
                    st.session_state.datos_pendientes_cerrar = None
                    st.session_state.mostrar_advertencia_cerrar = False
                    st.rerun()

        dialogo_advertencia_cerrar()

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3 = st.tabs(["📋 COTIZACIÓN", "👤 DATOS", "📂 COTIZACIONES"])

# =========================================================
# FUNCIÓN PARA GENERAR PDF COMPLETO
# =========================================================
def generar_pdf_completo(carrito_df, subtotal, iva, total, datos_cliente,
                     fecha_inicio, fecha_termino, dias_validez,
                     datos_asesor, margen=0, numero_cotizacion=None):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           leftMargin=20, rightMargin=20,
                           topMargin=30, bottomMargin=30, allowSplitting=1)
    elements = []
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name='SmallFont', parent=styles['Normal'], fontSize=8, leading=12, wordWrap='CJK', leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='HeaderStyle', parent=styles['Normal'], fontSize=9, leading=11, alignment=1, textColor=colors.white, fontName='Helvetica-Bold', leftIndent=0))
    styles.add(ParagraphStyle(name='TituloPresupuesto', parent=styles['Normal'], fontSize=16, leading=20, fontName='Helvetica-Bold', spaceAfter=6, leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='TextoNormal', parent=styles['Normal'], fontSize=10, leading=14, leftIndent=0, alignment=0, spaceAfter=2))
    styles.add(ParagraphStyle(name='TituloSeccion', parent=styles['Normal'], fontSize=12, leading=14, fontName='Helvetica-Bold', spaceAfter=6, leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='NotasEstilo', parent=styles['Normal'], fontSize=8, leading=10, leftIndent=0, alignment=0, textColor=colors.grey, spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalLabel', parent=styles['Normal'], fontSize=10, leading=14, alignment=2, fontName='Helvetica', spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalValue', parent=styles['Normal'], fontSize=10, leading=14, alignment=2, fontName='Helvetica', spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalBold', parent=styles['Normal'], fontSize=12, leading=16, alignment=2, fontName='Helvetica-Bold', spaceAfter=2, textColor=colors.black))

    try:
        logo = Image("logo.png")
        max_width = 2 * inch
        aspect = logo.imageHeight / float(logo.imageWidth)
        logo.drawWidth = max_width
        logo.drawHeight = max_width * aspect
        logo_data = [[logo]]
        logo_table = Table(logo_data, colWidths=[doc.width])
        logo_table.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER'), ('VALIGN', (0,0), (0,0), 'MIDDLE'), ('LEFTPADDING', (0,0), (0,0), 0), ('RIGHTPADDING', (0,0), (0,0), 0)]))
        elements.append(logo_table)
        elements.append(Spacer(1, 15))
    except:
        elements.append(Paragraph("<b># ESPACIO</b>", styles['TituloPresupuesto']))
        elements.append(Spacer(1, 10))

    numero_presupuesto = numero_cotizacion if numero_cotizacion else f"EP-{random.randint(1000,9999)}"
    fecha_emision = datetime.now()

    elements.append(Paragraph(f"<b>PRESUPUESTO Nº {numero_presupuesto}</b>", styles['TituloPresupuesto']))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>Fecha Emisión:</b> {fecha_emision.strftime('%d-%m-%Y')}", styles['TextoNormal']))
    elements.append(Paragraph(f"<b>Validez:</b> {fecha_inicio.strftime('%d-%m-%Y')} hasta {fecha_termino.strftime('%d-%m-%Y')} ({dias_validez} días)", styles['TextoNormal']))
    elements.append(Spacer(1, 20))

    ancho_columna = (doc.width - 20) / 2
    data_ca = [[Paragraph("<b>DATOS DEL CLIENTE</b>", styles['TituloSeccion']), Paragraph("<b>DATOS DEL ASESOR</b>", styles['TituloSeccion'])]]
    cliente_text = "".join(f"<b>{k}:</b> {v}<br/>" for k, v in datos_cliente.items() if v)
    asesor_text = "".join(f"<b>{k}:</b> {v}<br/>" for k, v in datos_asesor.items() if v)
    data_ca.append([Paragraph(cliente_text, styles['TextoNormal']), Paragraph(asesor_text, styles['TextoNormal'])])
    tabla_ca = Table(data_ca, colWidths=[ancho_columna, ancho_columna])
    tabla_ca.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (0,0), (0,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('LEFTPADDING', (0,0), (0,-1), 0), ('RIGHTPADDING', (0,0), (0,-1), 10),
        ('LEFTPADDING', (1,0), (1,-1), 0), ('RIGHTPADDING', (1,0), (1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(tabla_ca)
    elements.append(Spacer(1, 20))

    ancho_total = doc.width
    porcentajes = [15, 50, 8, 13.5, 13.5]
    anchos = [ancho_total * p / 100 for p in porcentajes]
    data = [[
        Paragraph("<b>Categoría</b>", styles['HeaderStyle']),
        Paragraph("<b>Item</b>", styles['HeaderStyle']),
        Paragraph("<b>Cant.</b>", styles['HeaderStyle']),
        Paragraph("<b>P. Unitario</b>", styles['HeaderStyle']),
        Paragraph("<b>Subtotal</b>", styles['HeaderStyle'])
    ]]
    for _, row in carrito_df.iterrows():
        data.append([
            Paragraph(row["Categoria"], styles['SmallFont']),
            Paragraph(row["Item"], styles['SmallFont']),
            Paragraph(str(row["Cantidad"]), styles['SmallFont']),
            Paragraph(formato_clp(row["Precio Unitario"]), styles['SmallFont']),
            Paragraph(formato_clp(row["Subtotal"]), styles['SmallFont'])
        ])

    tabla_productos = Table(data, colWidths=anchos, repeatRows=1, splitByRow=1)
    tabla_productos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.black), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,0), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9), ('BOTTOMPADDING', (0,0), (-1,0), 8), ('TOPPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.white), ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('ALIGN', (2,1), (4,-1), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 2), ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,1), (-1,-1), 4), ('BOTTOMPADDING', (0,1), (-1,-1), 4),
    ]))
    for i in range(1, len(data)):
        if i % 2 == 0:
            tabla_productos.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.Color(0.95, 0.95, 0.95))]))
    elements.append(tabla_productos)
    elements.append(Spacer(1, 20))

    ancho_bloque = (doc.width - 20) / 2
    texto_transporte = "2.- Transporte y bases de apoyo <b>incluidos</b>." if margen > 0 else "2.- Transporte y bases de apoyo <b>no incluidos</b>."
    notas_texto = f"""<b>NOTAS IMPORTANTES:</b><br/>1.- Valores incluyen IVA.<br/>{texto_transporte}<br/>3.- Formas de pago: transferencia - pago contado.<br/>4.- Proceso de pagos: 50% inicial - 25% obra - 25% entrega."""
    bloque_notas = Paragraph(notas_texto, styles['NotasEstilo'])

    totales_data = [
        [Paragraph("Subtotal:", styles['TotalLabel']), Paragraph(formato_clp(subtotal), styles['TotalValue'])],
        [Paragraph("IVA (19%):", styles['TotalLabel']), Paragraph(formato_clp(iva), styles['TotalValue'])],
        [Paragraph("TOTAL:", styles['TotalBold']), Paragraph(formato_clp(total), styles['TotalBold'])]
    ]
    totales_tabla = Table(totales_data, colWidths=[100, 120])
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('LINEABOVE', (1,1), (1,1), 1, colors.grey),
        ('LINEABOVE', (1,2), (1,2), 2, colors.black),
    ]))
    data_bloques = [[bloque_notas, totales_tabla]]
    tabla_bloques = Table(data_bloques, colWidths=[ancho_bloque, ancho_bloque])
    tabla_bloques.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'), ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (1,0), (1,0), 0),
    ]))
    elements.append(tabla_bloques)
    doc.build(elements)
    buffer.seek(0)
    return buffer, numero_presupuesto

# =========================================================
# FUNCIÓN PARA GENERAR PDF CLIENTE
# =========================================================
def generar_pdf_cliente(carrito_df, subtotal, iva, total, datos_cliente,
                     fecha_inicio, fecha_termino, dias_validez,
                     datos_asesor, margen=0, numero_cotizacion=None):

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           leftMargin=20, rightMargin=20,
                           topMargin=30, bottomMargin=30, allowSplitting=1)
    elements = []
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name='SmallFont', parent=styles['Normal'], fontSize=8, leading=12, wordWrap='CJK', leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='HeaderStyle', parent=styles['Normal'], fontSize=9, leading=11, alignment=1, textColor=colors.white, fontName='Helvetica-Bold', leftIndent=0))
    styles.add(ParagraphStyle(name='TituloPresupuesto', parent=styles['Normal'], fontSize=16, leading=20, fontName='Helvetica-Bold', spaceAfter=6, leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='TextoNormal', parent=styles['Normal'], fontSize=10, leading=14, leftIndent=0, alignment=0, spaceAfter=2))
    styles.add(ParagraphStyle(name='TituloSeccion', parent=styles['Normal'], fontSize=12, leading=14, fontName='Helvetica-Bold', spaceAfter=6, leftIndent=0, alignment=0))
    styles.add(ParagraphStyle(name='NotasEstilo', parent=styles['Normal'], fontSize=8, leading=10, leftIndent=0, alignment=0, textColor=colors.grey, spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalLabel', parent=styles['Normal'], fontSize=10, leading=14, alignment=2, fontName='Helvetica', spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalValue', parent=styles['Normal'], fontSize=10, leading=14, alignment=2, fontName='Helvetica', spaceAfter=2))
    styles.add(ParagraphStyle(name='TotalBold', parent=styles['Normal'], fontSize=12, leading=16, alignment=2, fontName='Helvetica-Bold', spaceAfter=2, textColor=colors.black))

    try:
        logo = Image("logo.png")
        max_width = 2 * inch
        aspect = logo.imageHeight / float(logo.imageWidth)
        logo.drawWidth = max_width
        logo.drawHeight = max_width * aspect
        logo_data = [[logo]]
        logo_table = Table(logo_data, colWidths=[doc.width])
        logo_table.setStyle(TableStyle([('ALIGN', (0,0), (0,0), 'CENTER'), ('VALIGN', (0,0), (0,0), 'MIDDLE'), ('LEFTPADDING', (0,0), (0,0), 0), ('RIGHTPADDING', (0,0), (0,0), 0)]))
        elements.append(logo_table)
        elements.append(Spacer(1, 15))
    except:
        elements.append(Paragraph("<b># ESPACIO</b>", styles['TituloPresupuesto']))
        elements.append(Spacer(1, 10))

    numero_presupuesto = numero_cotizacion if numero_cotizacion else f"EP-{random.randint(1000,9999)}"
    fecha_emision = datetime.now()

    elements.append(Paragraph(f"<b>PRESUPUESTO Nº {numero_presupuesto}</b>", styles['TituloPresupuesto']))
    elements.append(Spacer(1, 2))
    elements.append(Paragraph(f"<b>Fecha Emisión:</b> {fecha_emision.strftime('%d-%m-%Y')}", styles['TextoNormal']))
    elements.append(Paragraph(f"<b>Validez:</b> {fecha_inicio.strftime('%d-%m-%Y')} hasta {fecha_termino.strftime('%d-%m-%Y')} ({dias_validez} días)", styles['TextoNormal']))
    elements.append(Spacer(1, 20))

    ancho_columna = (doc.width - 20) / 2
    data_ca = [[Paragraph("<b>DATOS DEL CLIENTE</b>", styles['TituloSeccion']), Paragraph("<b>DATOS DEL ASESOR</b>", styles['TituloSeccion'])]]
    cliente_text = "".join(f"<b>{k}:</b> {v}<br/>" for k, v in datos_cliente.items() if v)
    asesor_text = "".join(f"<b>{k}:</b> {v}<br/>" for k, v in datos_asesor.items() if v)
    data_ca.append([Paragraph(cliente_text, styles['TextoNormal']), Paragraph(asesor_text, styles['TextoNormal'])])
    tabla_ca = Table(data_ca, colWidths=[ancho_columna, ancho_columna])
    tabla_ca.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('ALIGN', (0,0), (0,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'LEFT'),
        ('LEFTPADDING', (0,0), (0,-1), 0), ('RIGHTPADDING', (0,0), (0,-1), 10),
        ('LEFTPADDING', (1,0), (1,-1), 0), ('RIGHTPADDING', (1,0), (1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0), ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(tabla_ca)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>RESUMEN POR CATEGORÍA:</b>", styles['TituloSeccion']))
    elements.append(Spacer(1, 10))

    categorias = carrito_df.groupby('Categoria')
    data_resumen = []
    for categoria, grupo in categorias:
        items_lista = grupo['Item'].tolist()
        descripcion_html = "<br/>".join(f"• {item}" for item in items_lista)
        data_resumen.append([
            Paragraph(categoria, styles['SmallFont']),
            Paragraph(descripcion_html, styles['SmallFont'])
        ])

    ancho_cat = doc.width * 0.25
    ancho_desc = doc.width * 0.75
    headers = [
        Paragraph("<b>Categoría</b>", styles['HeaderStyle']),
        Paragraph("<b>Descripción</b>", styles['HeaderStyle'])
    ]
    tabla_resumen = Table([headers] + data_resumen, colWidths=[ancho_cat, ancho_desc], repeatRows=1)
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.black),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 5),
        ('BOTTOMPADDING', (0,1), (-1,-1), 5),
    ]))
    for i in range(1, len(data_resumen) + 1):
        if i % 2 == 0:
            tabla_resumen.setStyle(TableStyle([('BACKGROUND', (0,i), (-1,i), colors.Color(0.95, 0.95, 0.95))]))
    elements.append(tabla_resumen)
    elements.append(Spacer(1, 20))

    ancho_bloque = (doc.width - 20) / 2
    texto_transporte = "2.- Transporte y bases de apoyo <b>incluidos</b>." if margen > 0 else "2.- Transporte y bases de apoyo <b>no incluidos</b>."
    notas_texto = f"""<b>NOTAS IMPORTANTES:</b><br/>1.- Valores incluyen IVA.<br/>{texto_transporte}<br/>3.- Formas de pago: transferencia - pago contado.<br/>4.- Proceso de pagos: 50% inicial - 25% obra - 25% entrega."""
    bloque_notas = Paragraph(notas_texto, styles['NotasEstilo'])

    totales_data = [
        [Paragraph("Subtotal:", styles['TotalLabel']), Paragraph(formato_clp(subtotal), styles['TotalValue'])],
        [Paragraph("IVA (19%):", styles['TotalLabel']), Paragraph(formato_clp(iva), styles['TotalValue'])],
        [Paragraph("TOTAL:", styles['TotalBold']), Paragraph(formato_clp(total), styles['TotalBold'])]
    ]
    totales_tabla = Table(totales_data, colWidths=[100, 120])
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,-1), 'RIGHT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2), ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2), ('LINEABOVE', (1,1), (1,1), 1, colors.grey),
        ('LINEABOVE', (1,2), (1,2), 2, colors.black),
    ]))
    data_bloques = [[bloque_notas, totales_tabla]]
    tabla_bloques = Table(data_bloques, colWidths=[ancho_bloque, ancho_bloque])
    tabla_bloques.setStyle(TableStyle([
        ('ALIGN', (0,0), (0,0), 'LEFT'), ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'), ('LEFTPADDING', (0,0), (0,0), 0),
        ('RIGHTPADDING', (1,0), (1,0), 0),
    ]))
    elements.append(tabla_bloques)
    doc.build(elements)
    buffer.seek(0)
    return buffer, numero_presupuesto

# =========================================================
# FUNCIÓN LIMPIAR TODO
# =========================================================
def limpiar_todo():
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
    st.session_state.plano_adjunto = None
    st.session_state.plano_nombre = ""
    st.session_state.cotizacion_cargada = None
    st.session_state.cotizacion_seleccionada = None
    st.session_state.margen = 0.0
    st.session_state.mostrar_visor = False
    st.session_state.pdf_actual = None
    st.session_state.pdf_nombre = ""
    st.session_state.numero_en_visor = None
    st.session_state.pdf_url = None
    st.session_state.counter += 100

def _ejecutar_cierre_cotizacion():
    """Limpia todo el estado al cerrar una cotización."""
    limpiar_todo()
    st.session_state.recien_guardado = True
    st.session_state.hash_ultimo_guardado = None

# Procesar triggers de cierre aquí, donde limpiar_todo ya está definida
if st.session_state.get('trigger_cerrar_cotizacion', False):
    st.session_state.trigger_cerrar_cotizacion = False
    _ejecutar_cierre_cotizacion()
    st.session_state.resultados_busqueda = buscar_cotizaciones()
    st.rerun()

# =========================================================
# TAB 2 - DATOS CLIENTE
# =========================================================
with tab2:

    es_solo_lectura = bool(
        st.session_state.cotizacion_cargada and
        st.session_state.margen > 0 and
        not st.session_state.modo_admin
    )

    fecha_inicio = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino
    dias_validez = (fecha_termino - fecha_inicio).days

    if es_solo_lectura:
        st.warning("🔒 Modo solo lectura — cotización con márgenes aplicados.")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            with st.container(border=True):
                st.markdown("**👤 CLIENTE**")
                st.text_input("Nombre", value=st.session_state.nombre_input, disabled=True, key="nombre_readonly")
                st.text_input("RUT", value=st.session_state.rut_display, disabled=True, key="rut_readonly")
                st.text_input("Correo", value=st.session_state.correo_input, disabled=True, key="correo_readonly")
                st.text_input("Teléfono", value=st.session_state.telefono_raw, disabled=True, key="telefono_readonly")
        with col2:
            with st.container(border=True):
                st.markdown("**📍 DIRECCIÓN**")
                st.text_input("Dirección del Proyecto", value=st.session_state.direccion_input, disabled=True, key="direccion_readonly")
        with col3:
            with st.container(border=True):
                st.markdown("**👨‍💼 EJECUTIVO**")
                st.text_input("Asesor", value=st.session_state.asesor_seleccionado, disabled=True, key="asesor_readonly")
                st.text_input("Correo Ejecutivo", value=st.session_state.correo_asesor, disabled=True, key="correo_asesor_readonly")
                st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, disabled=True, key="telefono_asesor_readonly")
        with col4:
            with st.container(border=True):
                st.markdown("**📅 VALIDEZ**")
                st.date_input("Fecha Inicio", value=fecha_inicio, disabled=True, key="fecha_inicio_readonly")
                st.date_input("Fecha Término", value=fecha_termino, disabled=True, key="fecha_termino_readonly")
                st.markdown(f"**⏱️ Duración:** {dias_validez} días")
                if dias_validez > 0:
                    st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días")
        with st.container(border=True):
            st.markdown("**📝 OBSERVACIONES**")
            st.text_area("Observaciones", value=st.session_state.observaciones_input, disabled=True, height=80, key="observaciones_readonly")

    else:
        asesores = {
            "Seleccionar asesor": {"correo": "", "telefono": ""},
            "BERNARD BUSTAMANTE": {"correo": "BALDAY@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56956786366"},
            "ANDREA OSORIO": {"correo": "AOSORIO@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56927619483"},
            "REBECA CALDERON": {"correo": "RCALDERON@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56955286708"},
            "MAURICIO CEVO": {"correo": "MCEVO@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56971406162"},
            "JACQUELINE PÉREZ": {"correo": "JPEREZ@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56992286057"},
            "JAVIER QUEZADA": {"correo": "JQUEZADA@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56966983700"}
        }

        col1, col2, col3, col4 = st.columns(4)

        # ── Columna 1: Cliente ──
        with col1:
            with st.container(border=True):
                st.markdown("**👤 CLIENTE**")

                nombre_key = f"nombre_input_{st.session_state.counter}"
                nombre = st.text_input("Nombre Completo*", placeholder="Ej: Juan Pérez", key=nombre_key, value=st.session_state.nombre_input)
                if nombre != st.session_state.nombre_input:
                    st.session_state.nombre_input = nombre

                correo_key = f"correo_input_{st.session_state.counter}"
                correo = st.text_input("Correo Electrónico*", placeholder="ejemplo@correo.cl", key=correo_key, value=st.session_state.correo_input)
                if correo != st.session_state.correo_input:
                    st.session_state.correo_input = correo
                if correo and "@" not in correo:
                    st.warning("⚠️ El correo debe contener @")

                rut_key = f"rut_input_{st.session_state.counter}"
                st.text_input("RUT (opcional)", value=st.session_state.rut_display, key=rut_key, placeholder="12.345.678-9", on_change=procesar_cambio_rut)
                if st.session_state.rut_raw:
                    if len(st.session_state.rut_raw) >= 2:
                        if st.session_state.rut_valido:
                            st.success("✅ RUT válido")
                        else:
                            st.error(f"❌ {st.session_state.rut_mensaje}")
                    else:
                        st.info("⏳ RUT incompleto")

                telefono_key = f"telefono_input_{st.session_state.counter}"
                st.text_input("Teléfono", value=st.session_state.telefono_raw, key=telefono_key, placeholder="961528954 (9 dígitos)", on_change=procesar_cambio_telefono)

        # ── Columna 2: Dirección ──
        with col2:
            with st.container(border=True):
                st.markdown("**📍 DIRECCIÓN**")
                direccion_key = f"direccion_input_{st.session_state.counter}"
                direccion = st.text_input("Dirección del Proyecto", placeholder="Calle, número, comuna", key=direccion_key, value=st.session_state.direccion_input)
                if direccion != st.session_state.direccion_input:
                    st.session_state.direccion_input = direccion
                if direccion:
                    with st.spinner("Buscando..."):
                        comuna, region = buscar_direccion(direccion)
                        if comuna:
                            st.success(f"🏙️ {comuna}")
                            st.success(f"🗺️ {region}")
                        else:
                            st.info("No se detectó automáticamente.")
                            st.text_input("Comuna", key="comuna_manual")
                            st.text_input("Región", key="region_manual")

        # ── Columna 3: Ejecutivo ──
        with col3:
            with st.container(border=True):
                st.markdown("**👨‍💼 EJECUTIVO**")
                nombres_asesores = list(asesores.keys())
                asesor_key = f"asesor_select_{st.session_state.counter}"
                indice_actual = nombres_asesores.index(st.session_state.asesor_seleccionado) if st.session_state.asesor_seleccionado in nombres_asesores else 0
                asesor_elegido = st.selectbox("Asesor", nombres_asesores, index=indice_actual, key=asesor_key, label_visibility="collapsed")
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

                correo_asesor_key = f"asesor_correo_input_{st.session_state.counter}"
                correo_input = st.text_input("Correo Ejecutivo*", value=st.session_state.correo_asesor, placeholder="ejecutivo@empresa.cl", key=correo_asesor_key)
                if correo_input and "@" not in correo_input:
                    st.warning("⚠️ El correo debe contener @")
                if correo_input != st.session_state.correo_asesor:
                    st.session_state.correo_asesor = correo_input
                    st.session_state.asesor_seleccionado = "Seleccionar asesor"
                    st.session_state.counter += 1
                    st.rerun()

                telefono_asesor_key = f"asesor_telefono_input_{st.session_state.counter}"
                telefono_input = st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, key=telefono_asesor_key, placeholder="912345678 (9 dígitos)")
                if telefono_input != st.session_state.telefono_asesor:
                    raw = re.sub(r'[^0-9]', '', telefono_input)
                    if len(raw) > 9:
                        raw = raw[:9]
                    st.session_state.telefono_asesor = raw
                    st.session_state.asesor_seleccionado = "Seleccionar asesor"
                    st.session_state.counter += 1
                    st.rerun()

        # ── Columna 4: Validez ──
        with col4:
            with st.container(border=True):
                st.markdown("**📅 VALIDEZ**")
                fecha_inicio_key = f"fecha_inicio_{st.session_state.counter}"
                fecha_inicio = st.date_input("Fecha de Inicio", value=st.session_state.fecha_inicio, key=fecha_inicio_key)
                if fecha_inicio != st.session_state.fecha_inicio:
                    st.session_state.fecha_inicio = fecha_inicio

                fecha_termino_key = f"fecha_termino_{st.session_state.counter}"
                fecha_termino = st.date_input("Fecha de Término", value=st.session_state.fecha_termino, key=fecha_termino_key)
                if fecha_termino != st.session_state.fecha_termino:
                    st.session_state.fecha_termino = fecha_termino

                dias_validez = (fecha_termino - fecha_inicio).days
                if dias_validez < 0:
                    st.error("⚠️ Fecha de término anterior a inicio.")
                else:
                    st.markdown(f"**⏱️ Duración:** {dias_validez} días")
                    if dias_validez > 0:
                        st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días de validez")

        # ── Observaciones (ancho completo) ──
        with st.container(border=True):
            st.markdown("**📝 OBSERVACIONES**")
            observaciones_key = f"observaciones_input_{st.session_state.counter}"
            observaciones = st.text_area("Observaciones y notas adicionales", placeholder="Ingresa aquí cualquier información relevante...", height=80, key=observaciones_key, value=st.session_state.observaciones_input)
            if observaciones != st.session_state.observaciones_input:
                st.session_state.observaciones_input = observaciones

    nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    datos_cliente = {
        "Nombre": st.session_state.nombre_input or "",
        "RUT": st.session_state.rut_display or "",
        "Correo": st.session_state.correo_input or "",
        "Teléfono": st.session_state.telefono_raw or "",
        "Dirección": st.session_state.direccion_input or "",
        "Observaciones": st.session_state.observaciones_input or ""
    }
    nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    datos_asesor = {
        "Nombre Ejecutivo": nombre_asesor_final,
        "Correo Ejecutivo": st.session_state.correo_asesor or "",
        "Teléfono Ejecutivo": st.session_state.telefono_asesor or ""
    }

# =========================================================
# TAB 1 - PREPARAR COTIZACIÓN
# =========================================================
with tab1:
    st.markdown("### ☑️ Gestión de Presupuesto")

    fecha_inicio = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino
    dias_validez = (fecha_termino - fecha_inicio).days

    es_solo_lectura = bool(
        st.session_state.cotizacion_cargada and
        st.session_state.margen > 0 and
        not st.session_state.modo_admin
    )

    if es_solo_lectura:
        st.warning("🔒 Esta cotización tiene márgenes aplicados. Modo solo lectura. Solo puedes visualizar y generar PDFs.")

    if not es_solo_lectura:
        col_header, col_plano = st.columns([3, 1])
        with col_header:
            st.markdown("#### Gestión de Productos")
        with col_plano:
            st.markdown('''
            <style>
            [data-testid="stFileUploader"] section {
                border: none !important;
                padding: 0 !important;
                background: transparent !important;
            }
            [data-testid="stFileUploadDropzone"] {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                border: none !important;
                border-radius: 8px !important;
                padding: 8px 16px !important;
                min-height: 0 !important;
            }
            [data-testid="stFileUploadDropzone"]:hover {
                opacity: 0.85 !important;
                cursor: pointer !important;
            }
            [data-testid="stFileUploadDropzone"] > div {
                display: flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 8px !important;
            }
            [data-testid="stFileUploadDropzone"] span {
                display: none !important;
            }
            [data-testid="stFileUploadDropzone"] button {
                display: none !important;
            }
            [data-testid="stFileUploadDropzone"] p {
                color: white !important;
                font-weight: 600 !important;
                font-size: 14px !important;
                margin: 0 !important;
            }
            [data-testid="stFileUploadDropzone"] p::before {
                content: "📎 " !important;
            }
            [data-testid="stFileUploadDropzone"] p[data-testid="stMarkdownContainer"] {
                display: none !important;
            }
            div[data-testid="stFileUploader"] > label {display:none !important;}
            [data-testid="stFileUploader"] small {display:none !important;}
            </style>
            ''', unsafe_allow_html=True)

            uploaded_file = st.file_uploader("Subir Plano PDF", type=["pdf"], key=f"plano_uploader_{st.session_state.counter}", label_visibility="collapsed")

            if uploaded_file is not None:
                if uploaded_file.name != st.session_state.plano_nombre:
                    st.session_state.plano_adjunto = uploaded_file.getvalue()
                    st.session_state.plano_nombre = uploaded_file.name
                st.success(f"✅ {st.session_state.plano_nombre}")
            elif st.session_state.plano_nombre:
                st.info(f"📎 {st.session_state.plano_nombre}")
                if st.button("❌ Quitar plano", key="btn_quitar_plano", use_container_width=True):
                    st.session_state.plano_adjunto = None
                    st.session_state.plano_nombre = ""
                    st.rerun()

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        with col_m1:
            with st.container(border=True):
                st.markdown("**📋 Modelo Predefinido**")
                archivo_excel = pd.ExcelFile("cotizador.xlsx")
                hojas_modelo = [h for h in archivo_excel.sheet_names if h.lower().startswith("modelo")]
                if hojas_modelo:
                    modelo_seleccionado = st.selectbox("Modelo", hojas_modelo, key="modelo_select", label_visibility="collapsed")
                    if st.button("Cargar", key="btn_modelo", use_container_width=True):
                        st.session_state.carrito = cargar_modelo(modelo_seleccionado)
                        st.session_state.modelo_base = modelo_seleccionado
                        st.session_state.margen = 0.0
                        st.success("Modelo cargado correctamente.")
                        st.rerun()

        with col_m2:
            with st.container(border=True):
                st.markdown("**🔍 Ítems**")
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
                            "Categoria": categoria_seleccionada, "Item": item,
                            "Cantidad": cantidad, "Precio Unitario": precio_unitario_original,
                            "Subtotal": precio_unitario_original * cantidad
                        })
                    st.rerun()

        with col_m3:
            with st.container(border=True):
                st.markdown("**🗑️ Eliminar Categoría**")
                if st.session_state.carrito:
                    carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                    categorias_carrito = carrito_df_temp["Categoria"].unique()
                    categoria_eliminar = st.selectbox("Eliminar", ["-- Seleccionar --"] + list(categorias_carrito), key="cat_eliminar", label_visibility="collapsed")
                    if categoria_eliminar != "-- Seleccionar --":
                        if st.button("Eliminar", key="btn_eliminar_categoria", use_container_width=True):
                            st.session_state.carrito = [i for i in st.session_state.carrito if i["Categoria"] != categoria_eliminar]
                            st.success("Categoría eliminada.")
                            st.rerun()
                else:
                    st.info("No hay categorías")

        with col_m4:
            with st.container(border=True):
                st.markdown("**➕ Agregar Categoría**")
                if hojas_modelo:
                    modelo_origen = st.selectbox("Modelo", hojas_modelo, key="modelo_origen", label_visibility="collapsed")
                    df_temp = pd.read_excel("cotizador.xlsx", sheet_name=modelo_origen)
                    categorias_disponibles = df_temp["Categorias"].dropna().unique()
                    categoria_agregar = st.selectbox("Categoría", categorias_disponibles, key="cat_agregar", label_visibility="collapsed")
                    if st.button("Agregar", key="btn_agregar_categoria", use_container_width=True):
                        nuevos_items = cargar_categoria_desde_modelo(modelo_origen, categoria_agregar)
                        st.session_state.carrito = [i for i in st.session_state.carrito if i["Categoria"] != categoria_agregar]
                        st.session_state.carrito.extend(nuevos_items)
                        st.success("Categoría agregada.")
                        st.rerun()
    else:
        st.markdown("#### Gestión de Productos")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        for col, label in zip([col_m1, col_m2, col_m3, col_m4], ["MODELO PREDEFINIDO", "ITEMS", "ELIMINAR CATEGORÍA", "AGREGAR CATEGORÍA"]):
            with col:
                st.markdown(f"**{label}**")
                st.info("Modo lectura")

    st.markdown("---")

    if not st.session_state.modo_admin:
        st.markdown("#### Resumen del Presupuesto")
        if st.session_state.margen > 0:
            st.caption(f"ℹ️ Margen del {st.session_state.margen}% aplicado")

    # Input de margen en modo admin
    if st.session_state.modo_admin:
        col_res_tit, col_res_margen = st.columns([4, 1])
        with col_res_tit:
            st.markdown("#### Resumen del Presupuesto")
        with col_res_margen:
            st.caption("Margen %")
            _nuevo_margen = st.number_input(
                "Margen", min_value=0.0, max_value=100.0,
                value=float(st.session_state.margen),
                step=0.5, format="%.1f",
                key="margen_input_fijo", label_visibility="collapsed"
            )
            if _nuevo_margen != st.session_state.margen:
                st.session_state.margen = _nuevo_margen
                st.rerun()


    # Variables de métricas con valores por defecto
    utilidad_real = 0
    total_comisiones = 0
    comision_vendedor = 0
    comision_supervisor = 0
    margen_valor = 0
    subtotal_base = 0
    subtotal_general = 0
    total = 0
    iva = 0

    if st.session_state.carrito:
        # Fila buscador — solo visible con productos
        col_vacio1, col_search_c, col_fs_c, col_vacio2 = st.columns([1, 3, 0.5, 1])
        with col_search_c:
            buscar_tabla = st.text_input("🔍", placeholder="Filtrar por categoría o ítem...", key="buscar_tabla_presupuesto", label_visibility="collapsed")
        with col_fs_c:
            pantalla_completa = st.toggle("⛶", key="tabla_fullscreen", value=st.session_state.get("tabla_fullscreen_val", False), help="Expandir tabla")
            st.session_state.tabla_fullscreen_val = pantalla_completa
        carrito_df = pd.DataFrame(st.session_state.carrito)
        subtotal_base = carrito_df["Subtotal"].sum()

        if st.session_state.modo_admin or st.session_state.margen > 0:
            carrito_df_con_margen = carrito_df.copy()
            carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(lambda x: aplicar_margen(x, st.session_state.margen))
            carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]
            subtotal_general = carrito_df_con_margen["Subtotal"].sum()
        else:
            carrito_df_con_margen = carrito_df.copy()
            subtotal_general = subtotal_base

        iva = subtotal_general * 0.19
        total = subtotal_general + iva
        margen_valor = subtotal_general - subtotal_base
        comision_vendedor = subtotal_general * 0.025 if st.session_state.modo_admin else 0
        comision_supervisor = subtotal_general * 0.008 if st.session_state.modo_admin else 0
        total_comisiones = comision_vendedor + comision_supervisor
        utilidad_real = margen_valor - total_comisiones if st.session_state.modo_admin else 0
        altura_tabla = 1400 if pantalla_completa else min(38 * len(carrito_df_con_margen) + 80, 420)

        if es_solo_lectura:
            carrito_df_display = carrito_df_con_margen[["Categoria", "Item", "Cantidad", "Precio Unitario", "Subtotal"]].copy()
            carrito_df_display["Precio Unitario"] = carrito_df_display["Precio Unitario"].apply(formato_clp)
            carrito_df_display["Subtotal"] = carrito_df_display["Subtotal"].apply(formato_clp)
            if buscar_tabla:
                mask = (
                    carrito_df_display["Categoria"].str.contains(buscar_tabla, case=False, na=False) |
                    carrito_df_display["Item"].str.contains(buscar_tabla, case=False, na=False)
                )
                carrito_df_display = carrito_df_display[mask]
            st.dataframe(carrito_df_display, use_container_width=True, hide_index=True, height=altura_tabla,
                column_config={"Categoria": st.column_config.TextColumn("Categoría"), "Item": st.column_config.TextColumn("Item"),
                               "Cantidad": st.column_config.NumberColumn("Cant."), "Precio Unitario": st.column_config.TextColumn("P. Unitario"),
                               "Subtotal": st.column_config.TextColumn("Subtotal")})
            st.caption("🔒 Vista de solo lectura")
        else:
            carrito_df_edit = carrito_df_con_margen.copy()
            carrito_df_edit["❌"] = False
            carrito_df_edit["Precio Unitario"] = carrito_df_edit["Precio Unitario"].apply(formato_clp)
            carrito_df_edit["Subtotal"] = carrito_df_edit["Subtotal"].apply(formato_clp)
            if buscar_tabla:
                mask = (
                    carrito_df_edit["Categoria"].str.contains(buscar_tabla, case=False, na=False) |
                    carrito_df_edit["Item"].str.contains(buscar_tabla, case=False, na=False)
                )
                carrito_df_edit_filtrado = carrito_df_edit[mask].copy()
            else:
                carrito_df_edit_filtrado = carrito_df_edit
            edited_df = st.data_editor(carrito_df_edit_filtrado, use_container_width=True, hide_index=True, height=altura_tabla,
                column_config={"❌": st.column_config.CheckboxColumn("❌"), "Categoria": st.column_config.TextColumn("Categoría"),
                               "Item": st.column_config.TextColumn("Item"), "Cantidad": st.column_config.NumberColumn("Cant."),
                               "Precio Unitario": st.column_config.TextColumn("P. Unitario"), "Subtotal": st.column_config.TextColumn("Subtotal")})
            filas_eliminar = edited_df[edited_df["❌"] == True].index.tolist()
            if filas_eliminar:
                indices_reales = carrito_df_edit_filtrado.iloc[filas_eliminar].index.tolist()
                for i in sorted(indices_reales, reverse=True):
                    del st.session_state.carrito[i]
                st.rerun()
        st.markdown("---")
        # Solo botón Limpiar
        col_btn_limpiar, _, _, _ = st.columns(4)
        with col_btn_limpiar:
            if not es_solo_lectura:
                if st.button("🧹 Limpiar", use_container_width=True):
                    limpiar_todo()
                    st.rerun()
            else:
                st.button("🧹 Limpiar", use_container_width=True, disabled=True)

        correo_para_pdf = st.session_state.correo_input
        datos_cliente_pdf = {
            "Nombre": st.session_state.nombre_input,
            "RUT": st.session_state.rut_display or '',
            "Correo": st.session_state.correo_input,
            "Teléfono": st.session_state.telefono_raw or '',
            "Dirección": st.session_state.direccion_input,
            "Observaciones": st.session_state.observaciones_input
        }
        nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
        datos_asesor_pdf = {
            "Nombre Ejecutivo": nombre_asesor_final,
            "Correo Ejecutivo": st.session_state.correo_asesor or "",
            "Teléfono Ejecutivo": st.session_state.telefono_asesor or ""
        }
        carrito_df_pdf = carrito_df_con_margen.copy()
        margen_actual = st.session_state.margen
        numero_para_pdf = st.session_state.cotizacion_cargada if st.session_state.cotizacion_cargada else None

        if st.session_state.modo_admin and st.session_state.margen > 0:
            st.caption(f"*Precios calculados con margen del {st.session_state.margen}%")

        # Asegurar que todas las variables de métricas estén definidas
        if 'utilidad_real' not in dir():
            utilidad_real = margen_valor - total_comisiones if st.session_state.modo_admin else 0

        st.markdown("---")
        st.markdown("#### Métricas")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)

        total_productos = sum(item["Cantidad"] for item in st.session_state.carrito)
        categorias_unicas = len(set(item["Categoria"] for item in st.session_state.carrito))

        with col_m1:
            st.markdown(f'<div class="stats-card"><div class="stats-title">ÍTEMS</div><div class="stats-number" style="color:#3b82f6;border:none;padding:0;">{len(st.session_state.carrito)}</div><div class="stats-desc">En presupuesto</div></div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="stats-card"><div class="stats-title">PRODUCTOS</div><div class="stats-number" style="color:#f59e0b;border:none;padding:0;">{total_productos}</div><div class="stats-desc">Unidades</div></div>', unsafe_allow_html=True)
        with col_m3:
            st.markdown(f'<div class="stats-card"><div class="stats-title">CATEGORÍAS</div><div class="stats-number" style="color:#10b981;border:none;padding:0;">{categorias_unicas}</div><div class="stats-desc">Diferentes</div></div>', unsafe_allow_html=True)
        with col_m4:
            if st.session_state.modo_admin:
                st.markdown(f'''
                <div class="metric-card-special" style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div>
                        <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">📦 TOTAL SIN IVA</div>
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                            <div style="display:flex;justify-content:space-between;"><span>+ Margen {st.session_state.margen}%:</span><span>{formato_clp(margen_valor)}</span></div>
                        </div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                        <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(subtotal_general)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div class="metric-card-special" style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div>
                        <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">📦 TOTAL SIN IVA</div>
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;"><span>Costo base (sin IVA):</span><span>{formato_clp(subtotal_base)}</span></div>
                        </div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                        <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(subtotal_base)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)

        st.markdown("---")

        if st.session_state.modo_admin:
            col_total_card, col_comisiones_card, col_utilidad_card = st.columns(3)
            with col_total_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div>
                            <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">💰 TOTAL CON IVA</div>
                            <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>+ Margen {st.session_state.margen}%:</span><span>{formato_clp(margen_valor)}</span></div>
                                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>= Subtotal c/margen:</span><span>{formato_clp(subtotal_general)}</span></div>
                                <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                            </div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(total)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)
            with col_comisiones_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-comisiones" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div>
                            <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">📊 COMISIONES</div>
                            <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Vendedor 2.5%:</span><span>{formato_clp(comision_vendedor)}</span></div>
                                <div style="display:flex;justify-content:space-between;"><span>Supervisor 0.8%:</span><span>{formato_clp(comision_supervisor)}</span></div>
                            </div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(total_comisiones)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)
            with col_utilidad_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-utilidad" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div>
                            <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">📈 UTILIDAD REAL</div>
                            <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                                <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Margen bruto:</span><span>{formato_clp(margen_valor)}</span></div>
                                <div style="display:flex;justify-content:space-between;"><span>- Comisiones:</span><span>{formato_clp(total_comisiones)}</span></div>
                            </div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(utilidad_real)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)

        else:
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f'''
                <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div>
                        <div class="metric-title" style="color:white;margin-bottom:0.8rem;text-align:center;font-size:1.1rem;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;">💰 TOTAL CON IVA</div>
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                            <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                        </div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:flex-end;">
                        <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(total)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)
            if st.session_state.margen > 0:
                st.info("🔒 Los detalles de comisiones y utilidad solo están disponibles para administradores.")
    else:
        st.info("👈 Agrega productos al presupuesto usando los controles de la izquierda")

# =========================================================
# TAB 3 - GESTIÓN DE COTIZACIONES GUARDADAS
# =========================================================
with tab3:
    st.markdown("### 📂 Gestión de Cotizaciones")

    col_busqueda, col_filtros = st.columns([3, 1])
    with col_busqueda:
        with st.container(border=True):
            tipo_busqueda = st.radio("Buscar por:", ["📋 N° Presupuesto", "👤 Cliente", "👨‍💼 Asesor"], horizontal=True, key="tipo_busqueda")
            tipo_map = {"📋 N° Presupuesto": "numero", "👤 Cliente": "cliente", "👨‍💼 Asesor": "asesor"}
            termino = st.text_input("Buscar...", placeholder="Ingrese término de búsqueda...", key="buscar_cotizacion")

    with col_filtros:
        with st.container(border=True):
            st.markdown("**📅 Filtros rápidos**")
            st.button("📅 Hoy", use_container_width=True)
            st.button("📅 Esta semana", use_container_width=True)
            st.button("📅 Este mes", use_container_width=True)

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
        st.session_state.resultados_busqueda = buscar_cotizaciones(termino if termino else None, tipo_map[tipo_busqueda])
        st.session_state.mostrar_visor = False
        st.session_state.pdf_actual = None
        st.session_state.pdf_nombre = ""
        st.session_state.numero_en_visor = None
        st.session_state.pdf_url = None

    if limpiar_btn:
        st.session_state.resultados_busqueda = []
        st.session_state.ultimo_termino = ""
        st.session_state.mostrar_visor = False
        st.session_state.pdf_actual = None
        st.session_state.pdf_nombre = ""
        st.session_state.numero_en_visor = None
        st.session_state.pdf_url = None
        st.rerun()

    if st.session_state.resultados_busqueda:
        df_resultados = pd.DataFrame(
            st.session_state.resultados_busqueda,
            columns=["N°", "Cliente", "Asesor", "Fecha", "Total", "Margen", "RUT", "Email", "Asesor_Email", "Asesor_Tel", "Tiene_Plano"]
        )
        df_resultados["Total"] = df_resultados["Total"].apply(lambda x: f"${x:,.0f}".replace(",", ".") if x else "$0")
        df_resultados["Fecha"] = df_resultados["Fecha"].apply(lambda x: x[:10] if x else "")
        df_resultados["Estado"] = df_resultados.apply(crear_badge_estado, axis=1)
        df_resultados["Plano"] = df_resultados.apply(lambda row: "📎" if row["Tiene_Plano"] else "❌", axis=1)

        html_table = "<table class='resultados-table'><thead><tr><th>N° Presupuesto</th><th>Cliente</th><th>Asesor</th><th>Fecha</th><th>Total</th><th>Estado</th><th>Plano</th></tr></thead><tbody>"
        for _, row in df_resultados.iterrows():
            html_table += f"<tr><td>{row['N°']}</td><td>{row['Cliente'] or '—'}</td><td>{row['Asesor'] or '—'}</td><td>{row['Fecha']}</td><td>{row['Total']}</td><td style='text-align:center;'>{row['Estado']}</td><td style='text-align:center;font-size:1.2rem;'>{row['Plano']}</td></tr>"
        html_table += "</tbody></table>"
        st.markdown(html_table, unsafe_allow_html=True)

        with st.expander("📋 Leyenda de estados", expanded=False):
            col_l1, col_l2, col_l3, col_l4 = st.columns(4)
            with col_l1:
                st.markdown('<div style="background-color:#d4edda;padding:10px;border-radius:10px;"><span style="font-size:1.2rem;">🟢</span> <strong>AUTORIZADO</strong><br><small>Con margen, datos completos, sin plano</small></div>', unsafe_allow_html=True)
                st.markdown('<div style="background-color:#d4edda;padding:10px;border-radius:10px;margin-top:5px;"><span style="font-size:1.2rem;">🟢</span> <strong>AUTORIZADO CON PLANO</strong><br><small>Con margen, datos completos, con plano</small></div>', unsafe_allow_html=True)
            with col_l2:
                st.markdown('<div style="background-color:#ffedd5;padding:10px;border-radius:10px;"><span style="font-size:1.2rem;">🟠</span> <strong>BORRADOR CON PLANO</strong><br><small>Sin margen, datos completos, con plano</small></div>', unsafe_allow_html=True)
                st.markdown('<div style="background-color:#fff3cd;padding:10px;border-radius:10px;margin-top:5px;"><span style="font-size:1.2rem;">🟡</span> <strong>BORRADOR</strong><br><small>Sin margen, datos completos, sin plano</small></div>', unsafe_allow_html=True)
            with col_l3:
                st.markdown('<div style="background-color:#f8d7da;padding:10px;border-radius:10px;"><span style="font-size:1.2rem;">🔴</span> <strong>INCOMPLETO CON PLANO</strong><br><small>Faltan datos, con plano</small></div>', unsafe_allow_html=True)
            with col_l4:
                st.markdown('<div style="background-color:#f8d7da;padding:10px;border-radius:10px;"><span style="font-size:1.2rem;">🔴</span> <strong>INCOMPLETO</strong><br><small>Faltan datos, sin plano</small></div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### Seleccionar cotización")

        opciones = []
        for idx, row in df_resultados.iterrows():
            datos_completos = all([row[1], row[6], row[7]])
            asesor_completo = any([row[2], row[8], row[9]])
            if row['Margen'] and row['Margen'] > 0:
                estado = ("🟢 AUTORIZADO CON PLANO" if row['Tiene_Plano'] else "🟢 AUTORIZADO") if (datos_completos and asesor_completo) else ("🔴 INCOMPLETO CON PLANO" if row['Tiene_Plano'] else "🔴 INCOMPLETO")
            else:
                if datos_completos and asesor_completo:
                    estado = "🟠 BORRADOR CON PLANO" if row['Tiene_Plano'] else "🟡 BORRADOR"
                else:
                    estado = "🔴 INCOMPLETO CON PLANO" if row['Tiene_Plano'] else "🔴 INCOMPLETO"
            plano_indicador = "📎" if row['Tiene_Plano'] else "❌"
            opciones.append(f"{row['N°']} - {row['Cliente'] or 'S/C'} ({row['Fecha']}) - {row['Total']} - {estado} {plano_indicador}")

        if opciones:
            cotizacion_seleccionada = st.selectbox("Selecciona una cotización:", options=opciones, key="selector_cotizaciones")

            if cotizacion_seleccionada:
                numero_seleccionado = cotizacion_seleccionada.split(" - ")[0]

                tiene_margen_seleccionado = False
                tiene_plano_seleccionado = False
                for row in st.session_state.resultados_busqueda:
                    if row[0] == numero_seleccionado:
                        tiene_margen_seleccionado = bool(row[5] and row[5] > 0)
                        tiene_plano_seleccionado = bool(row[10]) if len(row) > 10 else False
                        break

                if numero_seleccionado != st.session_state.numero_en_visor:
                    if tiene_plano_seleccionado and st.session_state.mostrar_visor:
                        cot_visor = cargar_cotizacion(numero_seleccionado)
                        if cot_visor and cot_visor.get('plano_url'):
                            st.session_state.pdf_url = cot_visor['plano_url']
                            st.session_state.pdf_nombre = cot_visor.get('plano_nombre', 'plano.pdf')
                            st.session_state.numero_en_visor = numero_seleccionado
                            st.rerun()
                        else:
                            st.session_state.mostrar_visor = False
                            st.session_state.pdf_actual = None
                            st.session_state.pdf_nombre = ""
                            st.session_state.numero_en_visor = None
                            st.session_state.pdf_url = None
                            st.rerun()
                    else:
                        if st.session_state.mostrar_visor:
                            st.session_state.mostrar_visor = False
                            st.session_state.pdf_actual = None
                            st.session_state.pdf_nombre = ""
                            st.session_state.numero_en_visor = None
                            st.session_state.pdf_url = None
                            st.rerun()

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
                        # Si hay carrito sin guardar, mostrar advertencia
                        tiene_sin_guardar = (
                            len(st.session_state.carrito) > 0 and
                            st.session_state.cotizacion_cargada != numero_seleccionado
                        )
                        if tiene_sin_guardar:
                            st.session_state.mostrar_advertencia_carga = True
                            st.session_state.numero_a_cargar_pendiente = numero_seleccionado
                            st.rerun()
                        else:
                            if preparar_carga_cotizacion(numero_seleccionado):
                                st.success(f"✅ Cotización {numero_seleccionado} cargada")
                                st.rerun()

            # ── Popup advertencia productos sin guardar ──
            if st.session_state.get('mostrar_advertencia_carga', False):
                @st.dialog("⚠️ Productos sin guardar")
                def dialogo_advertencia():
                    numero_pendiente = st.session_state.get('numero_a_cargar_pendiente', '')
                    st.markdown(f"""
                    <div style="text-align:center;padding:1rem 0;">
                        <div style="font-size:3rem;margin-bottom:0.5rem;">⚠️</div>
                        <div style="font-size:1rem;font-weight:700;color:#1e2447;margin-bottom:0.5rem;">
                            Tienes productos sin guardar
                        </div>
                        <div style="font-size:0.88rem;color:#5a6080;line-height:1.6;">
                            Estás a punto de cargar la cotización <strong>{numero_pendiente}</strong>.<br/>
                            ¿Deseas guardar el presupuesto actual antes de continuar?
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    col_si, col_no, col_cancelar = st.columns(3)
                    with col_si:
                        if st.button("💾 Sí, guardar", use_container_width=True, type="primary", key="dialog_btn_si"):
                            # Guardar primero
                            datos_cliente_g, datos_asesor_g, proyecto_g, config_g, totales_g, plano_n, plano_d = construir_datos_para_guardar()
                            if st.session_state.cotizacion_cargada:
                                num_g = st.session_state.cotizacion_cargada
                            else:
                                num_g = generar_numero_unico()
                            guardar_cotizacion(num_g, datos_cliente_g, datos_asesor_g,
                                               proyecto_g, st.session_state.carrito,
                                               config_g, totales_g, plano_n, plano_d)
                            # Luego cargar
                            st.session_state.mostrar_advertencia_carga = False
                            if preparar_carga_cotizacion(numero_pendiente):
                                st.rerun()
                    with col_no:
                        if st.button("🗑️ No, descartar", use_container_width=True, key="dialog_btn_no"):
                            # Descartar y cargar directamente
                            st.session_state.mostrar_advertencia_carga = False
                            if preparar_carga_cotizacion(numero_pendiente):
                                st.rerun()
                    with col_cancelar:
                        if st.button("✖️ Cancelar", use_container_width=True, key="dialog_btn_cancelar"):
                            st.session_state.mostrar_advertencia_carga = False
                            st.session_state.numero_a_cargar_pendiente = None
                            st.rerun()

                dialogo_advertencia()

            cotizacion_para_pdf = cargar_cotizacion(numero_seleccionado) if cotizacion_seleccionada else None

            def preparar_pdf_data(cotizacion):
                carrito_df_t = pd.DataFrame(cotizacion['productos'])
                margen_c = cotizacion.get('config_margen', 0)
                if margen_c > 0:
                    carrito_df_p = carrito_df_t.copy()
                    carrito_df_p["Precio Unitario"] = carrito_df_p["Precio Unitario"].apply(lambda x: aplicar_margen(x, margen_c))
                    carrito_df_p["Subtotal"] = carrito_df_p["Cantidad"] * carrito_df_p["Precio Unitario"]
                else:
                    carrito_df_p = carrito_df_t.copy()
                subtotal_p = carrito_df_p["Subtotal"].sum()
                iva_p = subtotal_p * 0.19
                total_p = subtotal_p + iva_p
                dc = {"Nombre": cotizacion.get('cliente_nombre',''), "RUT": cotizacion.get('cliente_rut',''),
                      "Correo": cotizacion.get('cliente_email',''), "Teléfono": cotizacion.get('cliente_telefono',''),
                      "Dirección": cotizacion.get('cliente_direccion',''), "Observaciones": cotizacion.get('proyecto_observaciones','')}
                da = {"Nombre Ejecutivo": cotizacion.get('asesor_nombre',''),
                      "Correo Ejecutivo": cotizacion.get('asesor_email',''),
                      "Teléfono Ejecutivo": cotizacion.get('asesor_telefono','')}
                fi = datetime.strptime(cotizacion.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                ft = datetime.strptime(cotizacion.get('proyecto_fecha_termino', (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                dv = cotizacion.get('proyecto_dias_validez', 15)
                return carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c

            with col_acc2:
                if cotizacion_para_pdf:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    pdf_buffer, _ = generar_pdf_completo(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da, margen=margen_c, numero_cotizacion=numero_seleccionado)
                    st.download_button(label="📄 PDF Completo", data=pdf_buffer, file_name=f"Presupuesto_Completo_{numero_seleccionado}.pdf",
                        mime="application/pdf", use_container_width=True, key=f"pdf_completo_{numero_seleccionado}")
                else:
                    st.button("📄 PDF Completo", use_container_width=True, disabled=True)

            with col_acc3:
                if cotizacion_para_pdf:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    pdf_buffer, _ = generar_pdf_cliente(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da, margen=margen_c, numero_cotizacion=numero_seleccionado)
                    st.download_button(label="🔒 PDF Cliente", data=pdf_buffer, file_name=f"Presupuesto_Cliente_{numero_seleccionado}.pdf",
                        mime="application/pdf", use_container_width=True, key=f"pdf_cliente_{numero_seleccionado}")
                else:
                    st.button("🔒 PDF Cliente", use_container_width=True, disabled=True)

            with col_acc4:
                if cotizacion_seleccionada and tiene_plano_seleccionado:
                    label_visor = "🔄 ACTUALIZAR PLANO" if (st.session_state.mostrar_visor and st.session_state.numero_en_visor == numero_seleccionado) else "👁️ VER PLANO"
                    if st.button(label_visor, use_container_width=True, type="primary"):
                        cot_btn = cargar_cotizacion(numero_seleccionado)
                        if cot_btn and cot_btn.get('plano_url'):
                            st.session_state.pdf_url = cot_btn['plano_url']
                            st.session_state.pdf_nombre = cot_btn.get('plano_nombre', 'plano.pdf')
                            st.session_state.mostrar_visor = True
                            st.session_state.numero_en_visor = numero_seleccionado
                            st.rerun()
                else:
                    st.button("👁️ VER PLANO", use_container_width=True, disabled=True)

            # =========================================================
            # VISOR DE PDF
            # =========================================================
            if st.session_state.mostrar_visor and st.session_state.pdf_url:
                with st.expander("📄 Vista Previa del Plano", expanded=True):
                    st.markdown(f"**Archivo:** {st.session_state.pdf_nombre} — cotización `{st.session_state.numero_en_visor}`")
                    navegador = detectar_navegador()
                    if navegador['needs_google_viewer']:
                        pdf_url_encoded = urllib.parse.quote(st.session_state.pdf_url, safe='')
                        google_viewer_url = f"https://docs.google.com/viewer?url={pdf_url_encoded}&embedded=true"
                        st.markdown(f'''
                        <div style="width:100%;height:82vh;border:2px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);margin:0.5rem 0;background:#f0f2f5;">
                            <iframe src="{google_viewer_url}" width="100%" height="100%" style="display:block;border:none;" allow="fullscreen"></iframe>
                        </div>
                        ''', unsafe_allow_html=True)
                    else:
                        st.markdown(f'''
                        <div style="width:100%;height:82vh;border:2px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);margin:0.5rem 0;background:#f0f2f5;">
                            <iframe src="{st.session_state.pdf_url}" width="100%" height="100%" style="display:block;border:none;" allow="fullscreen"></iframe>
                        </div>
                        ''', unsafe_allow_html=True)
                    try:
                        pdf_bytes = requests.get(st.session_state.pdf_url).content
                        st.download_button(
                            label="📥 Descargar Plano",
                            data=pdf_bytes,
                            file_name=st.session_state.pdf_nombre,
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"descargar_plano_{st.session_state.numero_en_visor}"
                        )
                    except Exception as e:
                        st.error(f"Error al descargar el PDF: {e}")

        st.markdown("---")
        st.markdown("### 📊 Estadísticas Rápidas")

        autorizadas = autorizadas_con_plano = borradores_con_plano = borradores = 0
        incompletos_con_plano = incompletos = total_cotizado = 0

        for row in st.session_state.resultados_busqueda:
            datos_completos = all([row[1], row[6], row[7]])
            asesor_completo = any([row[2], row[8], row[9]])
            total_cotizado += row[4] if row[4] else 0
            tiene_plano = bool(row[10]) if len(row) > 10 else False

            if not datos_completos or not asesor_completo:
                if tiene_plano: incompletos_con_plano += 1
                else: incompletos += 1
            elif row[5] and row[5] > 0:
                if tiene_plano: autorizadas_con_plano += 1
                else: autorizadas += 1
            else:
                if tiene_plano: borradores_con_plano += 1
                else: borradores += 1

        autorizadas_total = autorizadas + autorizadas_con_plano

        col_e1, col_e2, col_e3, col_e4, col_e5, col_e6 = st.columns(6)
        stats = [
            (col_e1, "💰 TOTAL COTIZADO", formato_clp(total_cotizado), "total", "Total de cotizaciones"),
            (col_e2, "🟢 AUTORIZADAS", str(autorizadas_total), "autorizadas", f"{autorizadas_con_plano} con plano"),
            (col_e3, "🟠 BORRADOR C/P", str(borradores_con_plano), "color:#f97316;", "Borradores con plano"),
            (col_e4, "🟡 BORRADOR", str(borradores), "borradores", "Borradores sin plano"),
            (col_e5, "🔴 INCOMPLETO C/P", str(incompletos_con_plano), "color:#ef4444;", "Incompletos con plano"),
            (col_e6, "🔴 INCOMPLETO", str(incompletos), "incompletas", "Incompletos sin plano"),
        ]
        for col, title, number, css_class, desc in stats:
            with col:
                if len(number) > 12:
                    font_size = "1.6rem"
                elif len(number) > 8:
                    font_size = "2rem"
                else:
                    font_size = "2.8rem"
                if css_class.startswith("color:"):
                    num_html = f'<div class="stats-number" style="{css_class};font-size:{font_size};">{number}</div>'
                else:
                    num_html = f'<div class="stats-number {css_class}" style="font-size:{font_size};">{number}</div>'
                st.markdown(f'<div class="stats-card"><div class="stats-title">{title}</div>{num_html}<div class="stats-desc">{desc}</div></div>', unsafe_allow_html=True)

    else:
        st.info("💡 No hay resultados. Realice una búsqueda para ver cotizaciones guardadas.")

# =========================================================
# TOAST ÉXITO AL GUARDAR
# =========================================================
if st.session_state.get('mostrar_toast_exito', False):
    ep = st.session_state.get('toast_numero_ep', '')
    components.html(f"""
    <script>
    (function() {{
        const parent = window.parent.document;
        const old = parent.getElementById('toast-exito-ep');
        if (old) old.remove();
        if (!parent.getElementById('toast-exito-style')) {{
            const style = parent.createElement('style');
            style.id = 'toast-exito-style';
            style.innerHTML = `
                @keyframes slideInLeft {{
                    from {{ transform: translateX(-120%); opacity: 0; }}
                    to   {{ transform: translateX(0);    opacity: 1; }}
                }}
                @keyframes fadeOutLeft {{
                    from {{ transform: translateX(0);    opacity: 1; }}
                    to   {{ transform: translateX(-120%); opacity: 0; }}
                }}
                #toast-exito-ep {{
                    position: fixed !important;
                    bottom: 5rem !important;
                    left: 2rem !important;
                    z-index: 999998 !important;
                    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
                    color: white !important;
                    border-radius: 16px !important;
                    padding: 1rem 1.4rem !important;
                    font-family: sans-serif !important;
                    font-size: 0.9rem !important;
                    font-weight: 600 !important;
                    box-shadow: 0 8px 32px rgba(34,197,94,0.4) !important;
                    display: flex !important;
                    align-items: center !important;
                    gap: 0.6rem !important;
                    animation: slideInLeft 0.4s cubic-bezier(0.4,0,0.2,1) forwards !important;
                    min-width: 240px !important;
                }}
                #toast-exito-ep.fadeout {{
                    animation: fadeOutLeft 0.6s cubic-bezier(0.4,0,0.2,1) forwards !important;
                }}
                .toast-titulo {{
                    font-size: 0.8rem !important;
                    opacity: 0.88 !important;
                    font-weight: 500 !important;
                }}
                .toast-ep {{
                    font-size: 1.05rem !important;
                    font-weight: 800 !important;
                    letter-spacing: 0.03em !important;
                }}
            `;
            parent.head.appendChild(style);
        }}
        const toast = parent.createElement('div');
        toast.id = 'toast-exito-ep';
        toast.innerHTML = `
            <span style="font-size:1.4rem">✅</span>
            <div>
                <div class="toast-titulo">Presupuesto guardado con éxito</div>
                <div class="toast-ep">EP {ep}</div>
            </div>
        `;
        parent.body.appendChild(toast);
        setTimeout(() => {{
            toast.classList.add('fadeout');
            setTimeout(() => toast.remove(), 700);
        }}, 3500);
    }})();
    </script>
    """, height=0)
    st.session_state.mostrar_toast_exito = False

# =========================================================
# FAB - OCULTAR ÍCONOS STREAMLIT/GITHUB
# =========================================================
# Inyectar CSS para ocultar íconos de Streamlit Cloud
components.html("""
<script>
(function() {
    const parent = window.parent.document;

    function hideIcons() {
        const selectors = [
            'footer',
            '[data-testid="stToolbar"]',
            '[data-testid="stDecoration"]',
            '[data-testid="stStatusWidget"]',
            '[data-testid="stBottomBlockContainer"]',
            'a[href*="streamlit.io/cloud"]',
            'a[href*="github.com"]',
            '[class*="viewerBadge"]',
            '[class*="ViewerBadge"]',
            '[class*="_viewerBadge"]',
            '[class*="profileContainer"]',
            '[class*="_profileContainer"]',
            '[class*="profilePreview"]',
            '[class*="_profilePreview"]',
        ];
        selectors.forEach(sel => {
            try {
                parent.querySelectorAll(sel).forEach(el => {
                    el.style.setProperty('display', 'none', 'important');
                });
            } catch(e) {}
        });
    }

    if (!parent.getElementById('fab-hide-icons-style')) {
        const style = parent.createElement('style');
        style.id = 'fab-hide-icons-style';
        style.innerHTML = `
            #MainMenu { display: none !important; }
            footer { display: none !important; }
            [data-testid="stToolbar"] { display: none !important; }
            [data-testid="stDecoration"] { display: none !important; }
            [data-testid="stStatusWidget"] { display: none !important; }
            [data-testid="stBottomBlockContainer"] { display: none !important; }
            [class*="viewerBadge"] { display: none !important; }
            [class*="_viewerBadge"] { display: none !important; }
            [class*="profileContainer"] { display: none !important; }
            [class*="_profileContainer"] { display: none !important; }
            [class*="profilePreview"] { display: none !important; }
            a[href*="streamlit.io"] { display: none !important; }
            a[href*="github.com"] { display: none !important; }
        `;
        parent.head.appendChild(style);
    }

    hideIcons();
    setTimeout(hideIcons, 500);
    setTimeout(hideIcons, 1500);
    new MutationObserver(hideIcons).observe(parent.body, {childList: true, subtree: true});
})();
</script>
""", height=0)

# =========================================================
# FAB - BOTÓN GUARDAR FLOTANTE (Streamlit puro)
# =========================================================
_es_solo_lectura = (
    st.session_state.cotizacion_cargada and
    st.session_state.margen > 0 and
    not st.session_state.modo_admin
)

_mostrar_fab = (
    len(st.session_state.get('carrito', [])) > 0 and
    not _es_solo_lectura and
    not st.session_state.get('recien_guardado', False) and
    not st.session_state.get('recien_cargado', False)
)

# Limpiar flags después de evaluar
if st.session_state.get('recien_guardado', False):
    st.session_state.recien_guardado = False
if st.session_state.get('recien_cargado', False):
    st.session_state.recien_cargado = False

if _mostrar_fab:
    # CSS para posicionar el botón de Streamlit como FAB flotante
    st.markdown("""
    <style>
    /* FAB container - lo identificamos por data-testid único */
    div[data-testid="stBottom"] { display: none !important; }

    @keyframes pulse-fab {
        0%   { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
        50%  { box-shadow: 0 8px 40px rgba(91,124,250,0.9), 0 0 0 12px rgba(91,124,250,0.15); }
        100% { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
    }
    @keyframes blink-badge {
        0%, 100% { opacity: 1; }
        50%       { opacity: 0.2; }
    }

    /* Posicionar el contenedor del FAB */
    [data-testid="stVerticalBlock"] div:has(> [data-testid="stVerticalBlock"] > div > button[kind="primary"]#fab_btn_guardar_real) {
        position: fixed !important;
        bottom: 1.5rem !important;
        left: 2rem !important;
        z-index: 999999 !important;
    }

    /* Estilo del botón FAB */
    button[kind="primary"].fab-real-btn,
    div.fab-real-container button {
        background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 50px !important;
        padding: 0.85rem 1.6rem !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
        animation: pulse-fab 2s infinite !important;
        white-space: nowrap !important;
        min-width: 140px !important;
    }
    </style>
    <div class="fab-real-container" style="position:fixed;bottom:1.5rem;left:2rem;z-index:999999;">
    </div>
    """, unsafe_allow_html=True)

    # Botón real de Streamlit que ejecuta la lógica de guardado
    with st.container():
        st.markdown('<div class="fab-real-container" style="position:fixed;bottom:1.5rem;left:2rem;z-index:999999;"></div>', unsafe_allow_html=True)

    # Usar st.session_state para trigger desde el FAB
    if 'fab_trigger_guardar' not in st.session_state:
        st.session_state.fab_trigger_guardar = False

    # El FAB real se implementa como un components.html que inyecta
    # el botón en el documento padre y usa postMessage para comunicarse
    components.html(f"""
    <script>
    (function() {{
        const parent = window.parent.document;

        // Eliminar FAB anterior si existe
        const old = parent.getElementById('fab-guardar-wrapper');
        if (old) old.remove();

        // Crear FAB nuevo
        const style = parent.getElementById('fab-guardar-style') || parent.createElement('style');
        style.id = 'fab-guardar-style';
        style.innerHTML = `
            @keyframes pulse-fab {{
                0%   {{ box-shadow: 0 8px 24px rgba(91,124,250,0.5); }}
                50%  {{ box-shadow: 0 8px 40px rgba(91,124,250,0.9), 0 0 0 12px rgba(91,124,250,0.15); }}
                100% {{ box-shadow: 0 8px 24px rgba(91,124,250,0.5); }}
            }}
            @keyframes blink-badge {{
                0%, 100% {{ opacity: 1; }}
                50%      {{ opacity: 0.2; }}
            }}
            #fab-guardar-wrapper {{
                position: fixed !important;
                bottom: 1.5rem !important;
                left: 2rem !important;
                z-index: 999999 !important;
            }}
            #fab-guardar-btn {{
                background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%) !important;
                color: white !important;
                border: none !important;
                border-radius: 50px !important;
                padding: 0.85rem 1.6rem !important;
                font-size: 0.95rem !important;
                font-weight: 700 !important;
                cursor: pointer !important;
                font-family: sans-serif !important;
                animation: pulse-fab 2s infinite !important;
                white-space: nowrap !important;
            }}
            #fab-guardar-btn:hover {{
                transform: translateY(-3px) scale(1.05) !important;
                animation: none !important;
            }}
            #fab-badge {{
                position: absolute !important;
                top: -5px !important; right: -5px !important;
                width: 14px !important; height: 14px !important;
                background: #ef4444 !important;
                border-radius: 50% !important;
                border: 2px solid white !important;
                animation: blink-badge 1.5s infinite !important;
            }}
        `;
        if (!parent.getElementById('fab-guardar-style')) parent.head.appendChild(style);

        const wrapper = parent.createElement('div');
        wrapper.id = 'fab-guardar-wrapper';
        const btn = parent.createElement('button');
        btn.id = 'fab-guardar-btn';
        btn.innerHTML = '💾 Guardar';
        btn.onclick = function() {{
            // Buscar y clickear el botón guardar real de Streamlit
            const buttons = parent.querySelectorAll('button');
            for (const b of buttons) {{
                const txt = (b.innerText || b.textContent || '').trim();
                if (txt.includes('Guardar') && b.id !== 'fab-guardar-btn' && !b.disabled) {{
                    b.click();
                    return;
                }}
            }}
        }};
        const badge = parent.createElement('span');
        badge.id = 'fab-badge';
        wrapper.appendChild(btn);
        wrapper.appendChild(badge);
        parent.body.appendChild(wrapper);
    }})();
    </script>
    """, height=0)
else:
    # Eliminar FAB del DOM cuando no hay cambios pendientes
    components.html("""
    <script>
    (function() {
        const parent = window.parent.document;
        const w = parent.getElementById('fab-guardar-wrapper');
        if (w) w.remove();
    })();
    </script>
    """, height=0)

# =========================================================
# FAB - MARGEN FLOTANTE (solo visible en modo admin)
# =========================================================
_margen_actual = st.session_state.margen
_mstr = f"{_margen_actual:.1f}"

if st.session_state.modo_admin:
    _color = '#10b981' if _margen_actual > 0 else '#6b7280'
    _anim  = 'animation:pm 2s infinite;' if _margen_actual > 0 else ''

    components.html(f"""
<script>
(function(){{
  var D = window.parent.document;
  ['_fm_s','_fm_b','_fm_p'].forEach(function(id){{
    var e=D.getElementById(id); if(e) e.remove();
  }});

  var s=D.createElement('style'); s.id='_fm_s';
  s.textContent=[
    '@keyframes pm{{0%{{box-shadow:0 6px 20px rgba(16,185,129,.5)}}50%{{box-shadow:0 6px 36px rgba(16,185,129,.9),0 0 0 10px rgba(16,185,129,.15)}}100%{{box-shadow:0 6px 20px rgba(16,185,129,.5)}}}}',
    '#_fm_b{{position:fixed;bottom:1.5rem;left:12rem;z-index:99998;background:linear-gradient(135deg,{_color},{_color}cc);color:#fff;border:none;border-radius:50px;padding:.8rem 1.4rem;font-size:.9rem;font-weight:700;cursor:pointer;white-space:nowrap;{_anim}font-family:sans-serif;box-shadow:0 6px 20px rgba(16,185,129,.4);}}',
    '#_fm_b:hover{{transform:translateY(-2px);animation:none;}}',
    '#_fm_p{{position:fixed;bottom:5rem;left:12rem;z-index:99999;background:#fff;border-radius:16px;box-shadow:0 8px 40px rgba(0,0,0,.28);padding:1rem 1.2rem;min-width:220px;display:none;font-family:sans-serif;}}',
    '#_fm_p.on{{display:block;}}',
    '#_fm_disp{{width:100%;padding:.5rem;border:2px solid #10b981;border-radius:10px;font-size:1.6rem;font-weight:700;text-align:center;margin-bottom:6px;color:#111;background:#f0fdf4;user-select:none;}}',
    '#_fm_pad{{display:grid;grid-template-columns:repeat(3,1fr);gap:5px;margin-bottom:6px;}}',
    '#_fm_pad button{{padding:.5rem;border:1px solid #e5e7eb;border-radius:8px;background:#f9fafb;font-size:1rem;font-weight:600;cursor:pointer;color:#111;font-family:sans-serif;}}',
    '#_fm_pad button:hover{{background:#f0fdf4;border-color:#10b981;}}',
    '#_fm_ok{{width:100%;padding:.55rem;background:linear-gradient(135deg,#10b981,#059669);color:#fff;border:none;border-radius:10px;font-size:.9rem;font-weight:700;cursor:pointer;font-family:sans-serif;}}'
  ].join('');
  D.head.appendChild(s);

  var p=D.createElement('div'); p.id='_fm_p';
  p.innerHTML='<div style="font-size:.85rem;font-weight:700;color:#374151;margin-bottom:.5rem;">Margen %</div>'
    +'<div id="_fm_disp">{_mstr}%</div>'
    +'<div id="_fm_pad">'
    +'<button>1</button><button>2</button><button>3</button>'
    +'<button>4</button><button>5</button><button>6</button>'
    +'<button>7</button><button>8</button><button>9</button>'
    +'<button id="_fm_c" style="color:#ef4444">C</button>'
    +'<button>0</button><button>.</button>'
    +'</div>'
    +'<button id="_fm_ok">&#9989; Aplicar</button>';
  D.body.appendChild(p);

  var cur='{_mstr}';
  var disp=D.getElementById('_fm_disp');

  D.getElementById('_fm_pad').addEventListener('click',function(e){{
    e.stopPropagation();
    var t=e.target; if(!t||t.tagName!=='BUTTON') return;
    var n=t.textContent.trim();
    if(t.id==='_fm_c') cur='0';
    else if(n==='.') {{ if(cur.indexOf('.')<0) cur+='.'; }}
    else cur=(cur==='0')?n:cur+n;
    if(parseFloat(cur)>100) cur='100';
    disp.textContent=cur+'%';
  }});

  D.getElementById('_fm_ok').addEventListener('click',function(e){{
    e.stopPropagation();
    var val = Math.max(0, Math.min(100, parseFloat(cur)||0));
    var current = {_margen_actual};

    // Buscar el number_input de margen por key fijo "margen_input_fijo"
    var niContainer = null;
    var allNI = D.querySelectorAll('[data-testid="stNumberInput"]');
    for(var i=0; i<allNI.length; i++){{
      var inp = allNI[i].querySelector('input');
      if(inp && inp.getAttribute('aria-label') && inp.getAttribute('aria-label').indexOf('margen_input_fijo') >= 0){{
        niContainer = allNI[i]; break;
      }}
      // fallback: step 0.5
      if(inp && (inp.step==='0.5'||inp.getAttribute('step')==='0.5')){{
        niContainer = allNI[i]; break;
      }}
    }}

    if(!niContainer) {{ p.classList.remove('on'); return; }}

    var input = niContainer.querySelector('input');
    var btnMinus = niContainer.querySelector('button:first-of-type');
    var btnPlus  = niContainer.querySelectorAll('button')[1];
    if(!btnPlus) {{ p.classList.remove('on'); return; }}

    // Calcular cuántos clicks de "+" necesitamos
    // step = 0.5, clickear (val - current) / 0.5 veces
    // Si val < current, usar "-"
    var diff = Math.round((val - current) * 10) / 10;
    var clicks = Math.round(Math.abs(diff) / 0.5);
    var btn = diff >= 0 ? btnPlus : btnMinus;

    if(clicks === 0) {{ p.classList.remove('on'); return; }}

    // Hacer los clicks con pequeño delay entre cada uno
    var done = 0;
    function doClick(){{
      if(done >= clicks) return;
      btn.click();
      done++;
      setTimeout(doClick, 30);
    }}
    doClick();
    p.classList.remove('on');
  }});

  var b=D.createElement('button'); b.id='_fm_b';
  b.innerHTML='&#128202; Margen: {_mstr}%';
  b.addEventListener('click',function(e){{
    e.stopPropagation();
    cur='{_mstr}'; disp.textContent=cur+'%';
    p.classList.toggle('on');
  }});
  D.body.appendChild(b);

  D.addEventListener('click',function(e){{
    if(!b.contains(e.target)&&!p.contains(e.target)) p.classList.remove('on');
  }});
}})();
</script>
""", height=0)

else:
    components.html("""<script>
(function(){
  var D=window.parent.document;
  ['_fm_s','_fm_b','_fm_p'].forEach(function(id){
    var e=D.getElementById(id); if(e) e.remove();
  });
})();
</script>""", height=0)
