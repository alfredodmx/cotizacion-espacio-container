# v2.1 - titulos tarjetas abajo izquierda
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

# API key de Anthropic para el Visor 3D (leer de secrets o env)
import os as _os_init
ANTHROPIC_API_KEY = (
    _os_init.environ.get("ANTHROPIC_API_KEY", "") or
    (st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else "")
)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def verificar_conexion_supabase():
    # Solo verifica una vez por sesión, no en cada render
    if st.session_state.get('_supabase_ok'):
        return True
    try:
        supabase.table('cotizaciones').select('numero').limit(1).execute()
        st.session_state['_supabase_ok'] = True
        return True
    except Exception as e:
        st.error(f"❌ Error conectando a Supabase: {e}")
        return False

verificar_conexion_supabase()

# =========================================================
# HELPERS: DESCRIPCIONES PDF CLIENTE (JSON en Storage bucket config)
# =========================================================
def cargar_descripciones_por_ep(numero):
    """Carga descripciones de un EP desde Storage bucket config."""
    try:
        import requests as _rq
        _base = SUPABASE_URL.rstrip("/")
        _fname = f"pdf_desc_{numero}.json"
        url = f"{_base}/storage/v1/object/public/config/{_fname}"
        r = _rq.get(url, timeout=3)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return {}

def guardar_descripciones_por_ep(numero, descripciones: dict):
    """Guarda descripciones de un EP como JSON en Storage bucket config."""
    try:
        _fname = f"pdf_desc_{numero}.json"
        data = json.dumps(descripciones, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            supabase.storage.from_("config").remove([_fname])
        except:
            pass
        supabase.storage.from_("config").upload(
            path=_fname,
            file=data,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar descripciones: {e}")
        return False


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

# ── Leer acción guardar desde FAB via query_params ───────
if st.query_params.get("_fabg") == "1":
    st.query_params.clear()
    st.session_state['_trigger_guardar_fab'] = True
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

@st.cache_data(ttl=3600)
def buscar_direccion(direccion):
    # Cache 1 hora — evita HTTP en cada render mientras el usuario escribe
    if not direccion or len(direccion.strip()) < 5:
        return None, None
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


# =========================================================
# HELPER: OBTENER EXCEL ACTIVO DESDE SUPABASE
# =========================================================
import io as _io_excel

@st.cache_data(ttl=60)
def _get_excel_bytes_activo():
    """Descarga el Excel activo desde Supabase Storage. Cache 60s."""
    try:
        _resp = supabase.table('excel_versiones').select('archivo_url').eq('activa', True).limit(1).execute()
        if _resp.data:
            _url = _resp.data[0]['archivo_url']
            import requests as _rq
            _r = _rq.get(_url, timeout=15)
            _r.raise_for_status()
            return _io_excel.BytesIO(_r.content)
    except:
        pass
    return "cotizador.xlsx"  # fallback local

def _excel_src():
    """Retorna la fuente del Excel (BytesIO desde Supabase o path local)."""
    if 'excel_bytes_cache' not in st.session_state:
        st.session_state.excel_bytes_cache = _get_excel_bytes_activo()
    return st.session_state.excel_bytes_cache

@st.cache_data(ttl=300)
def _leer_hoja_excel(nombre_hoja):
    """Lee y cachea una hoja del Excel — evita re-parsear en cada render."""
    return pd.read_excel(_excel_src(), sheet_name=nombre_hoja)

@st.cache_data(ttl=300)
def _leer_bd_total():
    """Lee y cachea la hoja BD Total."""
    return pd.read_excel(_excel_src(), sheet_name="BD Total")[["Item", "P. Unitario real"]]

@st.cache_data(ttl=300)
def _leer_hojas_disponibles():
    """Lista de hojas del Excel cacheada."""
    return pd.ExcelFile(_excel_src()).sheet_names

def cargar_modelo(nombre_hoja):
    df_modelo = _leer_hoja_excel(nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[df_modelo["Cantidad"] > 0]
    df_bd = _leer_bd_total()
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
    df_modelo = _leer_hoja_excel(nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[(df_modelo["Cantidad"] > 0) & (df_modelo["Categorias"] == categoria_objetivo)]
    df_bd = _leer_bd_total()
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

def exportar_csv_completo():
    """Exporta todas las cotizaciones de Supabase a CSV."""
    try:
        response = supabase.table('cotizaciones').select(
            'numero', 'fecha_creacion', 'fecha_modificacion',
            'cliente_nombre', 'cliente_rut', 'cliente_email', 'cliente_telefono', 'cliente_direccion',
            'asesor_nombre', 'asesor_email', 'asesor_telefono',
            'config_margen',
            'total_subtotal_sin_margen', 'total_subtotal_con_margen',
            'total_iva', 'total_total', 'total_margen_valor',
            'total_comision_vendedor', 'total_comision_supervisor', 'total_utilidad_real',
            'estado', 'plano_nombre', 'plano_url'
        ).order('fecha_creacion', desc=True).execute()
        if not response.data:
            return None
        df = pd.DataFrame(response.data)
        df.columns = [
            'N° Presupuesto', 'Fecha Creación', 'Fecha Modificación',
            'Cliente', 'RUT', 'Email Cliente', 'Teléfono Cliente', 'Dirección',
            'Asesor', 'Email Asesor', 'Teléfono Asesor',
            'Margen %',
            'Subtotal sin Margen', 'Subtotal con Margen',
            'IVA', 'Total con IVA', 'Valor Margen',
            'Comisión Vendedor', 'Comisión Supervisor', 'Utilidad Real',
            'Estado', 'Nombre Plano', 'URL Plano'
        ]
        return df.to_csv(index=False).encode('utf-8-sig')
    except Exception as e:
        st.error(f"Error al exportar: {e}")
        return None

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
        padding: 0 !important; margin-bottom: 0 !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1.5rem !important;
        border-top: none !important;
    }
    .stTabs > div > div:nth-child(2) {
        border-top: none !important;
        box-shadow: none !important;
    }
    hr { display: none !important; }
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
        width: 100%; border-collapse: collapse; border-spacing: 0;
        font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.875rem;
        background: #ffffff;
    }
    .resultados-table th {
        background: linear-gradient(135deg, #1e2447 0%, #2a3060 100%) !important;
        color: #ffffff !important; font-weight: 700 !important;
        padding: 14px 16px !important; text-align: left !important;
        font-size: 0.75rem !important; letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
        position: sticky !important; top: 0 !important; z-index: 2 !important;
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
    /* ── Headers de tabs — texto siempre blanco ── */
    .tab-header h2, .tab-header p,
    .tab-header h2 *, .tab-header p *,
    .tab-header span[style*="display:block"] { color: #ffffff !important; }
    .tab-header h2 { color: #ffffff !important; font-size:1.5rem !important; font-weight:700 !important; margin:0 !important; }
    .tab-header p  { color: rgba(255,255,255,0.75) !important; font-size:0.88rem !important; margin:6px 0 0 !important; }
    </style>''', unsafe_allow_html=True)

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
    margin-bottom: 0.8rem;
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

# Barra admin — alineada a la derecha debajo del header
_col_esp, _col_admin_btn = st.columns([3, 1])
with _col_admin_btn:
    if not st.session_state.modo_admin:
        with st.popover("🔐 Admin ▾", use_container_width=True):
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
    else:
        st.markdown('<div style="padding-top:0.3rem;font-weight:700;color:#5b7cfa;text-align:right;">👑 Admin Activo</div>', unsafe_allow_html=True)

# Herramientas admin — solo cuando está activo
if st.session_state.modo_admin:
    _col_esp2, _col_csv, _col_cerrar = st.columns([3, 1, 1])
    with _col_csv:
        if st.button("📦 Exportar CSV", key="btn_generar_csv", use_container_width=True):
            st.session_state._csv_listo = exportar_csv_completo()
        if st.session_state.get('_csv_listo'):
            from datetime import datetime as _dt
            _fname = f"cotizaciones_backup_{_dt.now().strftime('%Y%m%d_%H%M')}.csv"
            st.download_button(
                label="⬇️ Descargar CSV",
                data=st.session_state._csv_listo,
                file_name=_fname,
                mime="text/csv",
                use_container_width=True,
                key="btn_export_csv"
            )
    with _col_cerrar:
        if st.button("🔓 Cerrar sesión", key="btn_cerrar_sesion_header", use_container_width=True):
            st.session_state.modo_admin = False
            st.session_state._csv_listo = None
            st.rerun()

# =========================================================
# BADGE DE COTIZACIÓN CARGADA
# =========================================================
if st.session_state.cotizacion_cargada:
    datos_completos = all([
        st.session_state.nombre_input,
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
# FUNCIÓN: RANKING DE EJECUTIVOS
# =========================================================
def cargar_ranking_ejecutivos(periodo='mes'):
    """Carga métricas de ejecutivos desde Supabase."""
    try:
        from datetime import datetime as _dt, timedelta as _td
        query = supabase.table('cotizaciones').select(
            'asesor_nombre, total_total, config_margen, cliente_nombre,'
            'cliente_email, cliente_rut, asesor_email, asesor_telefono, fecha_creacion'
        )
        if periodo == 'mes':
            _inicio = _dt.now().replace(day=1).strftime('%Y-%m-%d')
            query = query.gte('fecha_creacion', _inicio)
        resp = query.execute()
        if not resp.data:
            return []
        # Agrupar por asesor
        asesores = {}
        for row in resp.data:
            nombre = row.get('asesor_nombre') or 'Sin asignar'
            if nombre not in asesores:
                asesores[nombre] = {
                    'nombre': nombre,
                    'total_presupuestos': 0,
                    'total_generado': 0.0,
                    'autorizados': 0,
                    'borradores': 0,
                    'incompletos': 0,
                }
            a = asesores[nombre]
            a['total_presupuestos'] += 1
            a['total_generado'] += float(row.get('total_total') or 0)
            # Clasificar estado
            margen = float(row.get('config_margen') or 0)
            datos_ok = all([row.get('cliente_nombre'), row.get('cliente_email')])
            asesor_ok = any([row.get('asesor_nombre'), row.get('asesor_email'), row.get('asesor_telefono')])
            if margen > 0 and datos_ok and asesor_ok:
                a['autorizados'] += 1
            elif datos_ok and asesor_ok:
                a['borradores'] += 1
            else:
                a['incompletos'] += 1
        # Calcular métricas derivadas
        ranking = []
        for nombre, a in asesores.items():
            n = a['total_presupuestos']
            a['promedio'] = a['total_generado'] / n if n > 0 else 0
            a['pct_autorizado'] = round((a['autorizados'] / n) * 100) if n > 0 else 0
            # Score: pondera total generado (60%) + % autorizado (25%) + cantidad (15%)
            max_total = max((x['total_generado'] for x in asesores.values()), default=1) or 1
            max_n     = max((x['total_presupuestos'] for x in asesores.values()), default=1) or 1
            a['score'] = round(
                (a['total_generado'] / max_total) * 60 +
                (a['pct_autorizado'] / 100) * 25 +
                (a['total_presupuestos'] / max_n) * 15
            )
            ranking.append(a)
        # Ordenar por score desc
        ranking.sort(key=lambda x: x['score'], reverse=True)
        return ranking
    except Exception as e:
        return []


# =========================================================
# TABS
# =========================================================
if st.session_state.modo_admin:
    tab1, tab2, tab3, tab6, tab7, tab4, tab5 = st.tabs(["📋 COTIZACIÓN", "👤 DATOS", "📂 COTIZACIONES", "✏️ EDICIÓN PDF", "🏆 RANKING", "🧊 3D BETA", "📊 PROYECTO EXCEL"])
else:
    tab1, tab2, tab3, tab6, tab7, tab4 = st.tabs(["📋 COTIZACIÓN", "👤 DATOS", "📂 COTIZACIONES", "✏️ EDICIÓN PDF", "🏆 RANKING", "🧊 3D BETA"])
    tab5 = None

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
                     datos_asesor, margen=0, numero_cotizacion=None, descripciones_ep=None):
    _descripciones_ep = descripciones_ep or {}

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
        desc_custom = (_descripciones_ep or {}).get(categoria, '').strip()
        if desc_custom:
            descripcion_html = desc_custom.replace('\n', '<br/>')
        else:
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
    st.markdown("""
        <style>
        .hdr2 {
            background: linear-gradient(135deg, #2d0d66 0%, #5b0d7a 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr2 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr2 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        </style>
        <div class="hdr2">
          <span style="font-size:2.4rem">👤</span>
          <div>
            <h2>Datos del Cliente</h2>
            <p>Completa la información del cliente y del proyecto antes de guardar.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

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
                st.markdown("**👤 Cliente**")
                st.text_input("Nombre", value=st.session_state.nombre_input, disabled=True, key="nombre_readonly")
                st.text_input("RUT", value=st.session_state.rut_display, disabled=True, key="rut_readonly")
                st.text_input("Correo", value=st.session_state.correo_input, disabled=True, key="correo_readonly")
                st.text_input("Teléfono", value=st.session_state.telefono_raw, disabled=True, key="telefono_readonly")
        with col2:
            with st.container(border=True):
                st.markdown("**📍 Dirección**")
                st.text_input("Dirección del Proyecto", value=st.session_state.direccion_input, disabled=True, key="direccion_readonly")
        with col3:
            with st.container(border=True):
                st.markdown("**👨‍💼 Ejecutivo**")
                st.text_input("Asesor", value=st.session_state.asesor_seleccionado, disabled=True, key="asesor_readonly")
                st.text_input("Correo Ejecutivo", value=st.session_state.correo_asesor, disabled=True, key="correo_asesor_readonly")
                st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, disabled=True, key="telefono_asesor_readonly")
        with col4:
            with st.container(border=True):
                st.markdown("**📅 Validez**")
                st.date_input("Fecha Inicio", value=fecha_inicio, disabled=True, key="fecha_inicio_readonly")
                st.date_input("Fecha Término", value=fecha_termino, disabled=True, key="fecha_termino_readonly")
                st.markdown(f"**⏱️ Duración:** {dias_validez} días")
                if dias_validez > 0:
                    st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días")
        with st.container(border=True):
            st.markdown("**📝 Observaciones**")
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
                st.markdown("**👤 Cliente**")

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
                st.markdown("**📍 Dirección**")
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
                st.markdown("**👨‍💼 Ejecutivo**")
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
                st.markdown("**📅 Validez**")
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
            st.markdown("**📝 Observaciones**")
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
    st.markdown("""
        <style>
        .hdr1 {
            background: linear-gradient(135deg, #0d2266 0%, #0d47a1 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr1 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr1 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        </style>
        <div class="hdr1">
          <span style="font-size:2.4rem">☑️</span>
          <div>
            <h2>Gestión de Presupuesto</h2>
            <p>Agrega productos, aplica márgenes y genera tu cotización en PDF.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

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
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([1,1,1,1,0.7])

        with col_m1:
            with st.container(border=True):
                st.markdown("**📋 Modelo Predefinido**")
                hojas_modelo = [h for h in _leer_hojas_disponibles() if h.lower().startswith("modelo")]
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
                df = _leer_hoja_excel("BD Total")
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
                    df_temp = _leer_hoja_excel(modelo_origen)
                    categorias_disponibles = df_temp["Categorias"].dropna().unique()
                    categoria_agregar = st.selectbox("Categoría", categorias_disponibles, key="cat_agregar", label_visibility="collapsed")
                    if st.button("Agregar", key="btn_agregar_categoria", use_container_width=True):
                        nuevos_items = cargar_categoria_desde_modelo(modelo_origen, categoria_agregar)
                        st.session_state.carrito = [i for i in st.session_state.carrito if i["Categoria"] != categoria_agregar]
                        st.session_state.carrito.extend(nuevos_items)
                        st.success("Categoría agregada.")
                        st.rerun()

        with col_m5:
            with st.container(border=True):
                st.markdown("**📎 Plano PDF**")
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
                [data-testid="stFileUploadDropzone"] span { display: none !important; }
                [data-testid="stFileUploadDropzone"] button { display: none !important; }
                [data-testid="stFileUploadDropzone"] p {
                    color: white !important;
                    font-weight: 600 !important;
                    font-size: 14px !important;
                    margin: 0 !important;
                }
                [data-testid="stFileUploadDropzone"] p::before { content: "📎 " !important; }
                div[data-testid="stFileUploader"] > label { display:none !important; }
                [data-testid="stFileUploader"] small { display:none !important; }
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

    else:
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
        tiene_margen = st.session_state.margen > 0
        comision_vendedor = subtotal_general * 0.025 if (st.session_state.modo_admin and tiene_margen) else 0
        comision_supervisor = subtotal_general * 0.008 if (st.session_state.modo_admin and tiene_margen) else 0
        total_comisiones = comision_vendedor + comision_supervisor
        utilidad_real = margen_valor - total_comisiones if (st.session_state.modo_admin and tiene_margen) else 0
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
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>+ Margen {st.session_state.margen}%:</span><span>{formato_clp(margen_valor)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.4rem;font-weight:700;color:white;">📦 Total sin iva</span>
                        <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(subtotal_general)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)
            else:
                st.markdown(f'''
                <div class="metric-card-special" style="background:linear-gradient(135deg,#ef4444,#dc2626);padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                        <div style="display:flex;justify-content:space-between;"><span>Costo base (sin IVA):</span><span>{formato_clp(subtotal_base)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.4rem;font-weight:700;color:white;">📦 Total sin iva</span>
                        <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(subtotal_base)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)

        st.markdown("---")

        if st.session_state.modo_admin:
            col_total_card, col_comisiones_card, col_utilidad_card = st.columns(3)
            with col_total_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>+ Margen {st.session_state.margen}%:</span><span>{formato_clp(margen_valor)}</span></div>
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>= Subtotal c/margen:</span><span>{formato_clp(subtotal_general)}</span></div>
                            <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:1.4rem;font-weight:700;color:white;">💰 Total con iva</span>
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(total)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)
            with col_comisiones_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-comisiones" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Vendedor 2.5%:</span><span>{formato_clp(comision_vendedor)}</span></div>
                            <div style="display:flex;justify-content:space-between;"><span>Supervisor 0.8%:</span><span>{formato_clp(comision_supervisor)}</span></div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:1.4rem;font-weight:700;color:white;">📊 Comisiones</span>
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(total_comisiones)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)
            with col_utilidad_card:
                    st.markdown(f'''
                    <div class="metric-card-special metric-card-utilidad" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                        <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                            <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Margen bruto:</span><span>{formato_clp(margen_valor)}</span></div>
                            <div style="display:flex;justify-content:space-between;"><span>- Comisiones:</span><span>{formato_clp(total_comisiones)}</span></div>
                        </div>
                        <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                            <span style="font-size:1.4rem;font-weight:700;color:white;">📈 Utilidad real</span>
                            <span style="font-size:2.2rem;font-weight:700;color:white;">{formato_clp(utilidad_real)}</span>
                        </div>
                    </div>''', unsafe_allow_html=True)

        else:
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f'''
                <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.4rem;font-weight:700;color:white;">💰 Total con iva</span>
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
    st.markdown("""
        <style>
        .hdr3 {
            background: linear-gradient(135deg, #6b4e00 0%, #e65100 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr3 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr3 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        </style>
        <div class="hdr3">
          <span style="font-size:2.4rem">📂</span>
          <div>
            <h2>Gestión de Cotizaciones</h2>
            <p>Busca, carga y administra todas las cotizaciones del sistema.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

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

    # Forzar refresco si se acaba de guardar una cotización
    if st.session_state.get('_tab3_necesita_refresh', False):
        st.session_state.resultados_busqueda = None
        st.session_state['_tab3_necesita_refresh'] = False

    if 'resultados_busqueda' not in st.session_state or st.session_state.resultados_busqueda is None:
        st.session_state.resultados_busqueda = buscar_cotizaciones()

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

        n_resultados = len(df_resultados)
        altura_tabla = min(n_resultados * 48 + 50, 530)  # ~10 filas = 530px máx

        rows_html = ""
        for _, row in df_resultados.iterrows():
            rows_html += f"<tr><td>{row['N°']}</td><td>{row['Cliente'] or '—'}</td><td>{row['Asesor'] or '—'}</td><td>{row['Fecha']}</td><td>{row['Total']}</td><td style='text-align:center;'>{row['Estado']}</td><td style='text-align:center;font-size:1.2rem;'>{row['Plano']}</td></tr>"

        html_table = f"""
        <div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid #e2e8f0;">
            <div style="overflow-y:auto;max-height:{altura_tabla}px;">
                <table class='resultados-table' style='margin:0;border-radius:0;box-shadow:none;'>
                    <thead style='position:sticky;top:0;z-index:2;'>
                        <tr><th>N° Presupuesto</th><th>Cliente</th><th>Asesor</th><th>Fecha</th><th>Total</th><th>Estado</th><th>Plano</th></tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>
        <p style="font-size:0.8rem;color:#888;margin-top:6px;">Mostrando {n_resultados} resultado{'s' if n_resultados != 1 else ''}</p>
        """
        st.markdown(html_table, unsafe_allow_html=True)

        st.markdown("### Seleccionar cotización")

        opciones = []
        for idx, row in df_resultados.iterrows():
            # Usar nombres de columna correctos (no índices numéricos)
            datos_completos = all([row['Cliente'], row['Email']])
            asesor_completo = any([row['Asesor'], row['Asesor_Email'], row['Asesor_Tel']])
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
                    _desc_ep = cargar_descripciones_por_ep(numero_seleccionado)
                    pdf_buffer, _ = generar_pdf_cliente(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da, margen=margen_c, numero_cotizacion=numero_seleccionado, descripciones_ep=_desc_ep)
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
                    pdf_url_visor = st.session_state.pdf_url
                    pdf_url_encoded = urllib.parse.quote(pdf_url_visor, safe='')
                    google_viewer_url = f"https://docs.google.com/viewer?url={pdf_url_encoded}&embedded=true"
                    usar_google = navegador['needs_google_viewer']
                    src_inicial = google_viewer_url if usar_google else pdf_url_visor

                    components.html(f"""
<style>
@keyframes spin {{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
body,html{{margin:0;padding:0;overflow:hidden;}}
#pdf-wrap {{width:100%;height:680px;border:2px solid #e2e8f0;border-radius:12px;
            overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);background:#f0f2f5;position:relative;}}
#pdf-loading {{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
               justify-content:center;background:#f0f2f5;z-index:2;gap:12px;
               transition:opacity 0.4s ease;}}
#pdf-spinner {{width:40px;height:40px;border:4px solid #cbd5e1;border-top-color:#5b7cfa;
               border-radius:50%;animation:spin 0.8s linear infinite;}}
#pdf-loading span {{color:#64748b;font-size:0.9rem;font-family:sans-serif;}}
#pdf-iframe {{position:absolute;inset:0;width:100%;height:100%;border:none;display:block;}}
</style>
<div id="pdf-wrap">
  <div id="pdf-loading">
    <div id="pdf-spinner"></div>
    <span id="pdf-status">Cargando PDF...</span>
  </div>
  <iframe id="pdf-iframe" src="" allow="fullscreen"></iframe>
</div>
<script>
(function() {{
  var iframe  = document.getElementById('pdf-iframe');
  var loading = document.getElementById('pdf-loading');
  var status  = document.getElementById('pdf-status');
  var googleUrl  = "{google_viewer_url}";
  var directUrl  = "{pdf_url_visor}";
  var usingGoogle = {"true" if usar_google else "false"};

  function hideLoading() {{
    loading.style.opacity = '0';
    setTimeout(function(){{ loading.style.display = 'none'; }}, 400);
  }}

  function loadDirect() {{
    usingGoogle = false;
    status.textContent = 'Cargando PDF...';
    iframe.src = directUrl;
    // Para iframe directo, ocultar spinner tras tiempo prudente según conexión
    setTimeout(hideLoading, 4000);
  }}

  // Arrancar con Google Viewer o directo según navegador
  if (usingGoogle) {{
    iframe.src = googleUrl;
    // Google Viewer: ocultar spinner a los 3s (ya renderizó o sigue cargando de fondo)
    // Si a los 12s aún no hubo contenido, caer a directo
    setTimeout(function() {{
      if (loading.style.display !== 'none') hideLoading();
    }}, 3000);
    setTimeout(function() {{
      // Intentar detectar pantalla en blanco de Google Viewer vía postMessage no es posible
      // por CORS — simplemente ofrecer fallback visual con botón
      if (usingGoogle) {{
        try {{
          var doc = iframe.contentDocument || iframe.contentWindow.document;
          if (!doc || !doc.body || doc.body.children.length === 0) loadDirect();
        }} catch(e) {{
          // CORS — no podemos leer, asumir que cargó bien
        }}
      }}
    }}, 8000);
  }} else {{
    iframe.src = directUrl;
    setTimeout(hideLoading, 4000);
  }}
}})();
</script>
""", height=710, scrolling=False)

                    try:
                        pdf_bytes = requests.get(st.session_state.pdf_url, timeout=15).content
                        st.download_button(
                            label="📥 Descargar Plano",
                            data=pdf_bytes,
                            file_name=st.session_state.pdf_nombre,
                            mime="application/pdf",
                            use_container_width=True,
                            key=f"descargar_plano_{st.session_state.numero_en_visor}"
                        )
                    except Exception as e:
                        st.warning("⚠️ No se pudo preparar la descarga. Intenta de nuevo.")

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
# TOAST ÉXITO AL GUARDAR — st.toast() nativo
# CSS solo se inyecta cuando el toast está activo, evita contenedor
# vacío pegado en pantalla entre reruns
# =========================================================
if st.session_state.get('mostrar_toast_exito', False):
    ep = st.session_state.get('toast_numero_ep', '')
    st.markdown("""
<style>
div[data-testid="stToastContainer"] {
    position: fixed !important;
    bottom: 5.5rem !important;
    left: 2rem !important;
    right: auto !important;
    top: auto !important;
    width: auto !important;
    max-width: none !important;
    overflow: visible !important;
    z-index: 999999 !important;
    height: auto !important;
    min-height: 0 !important;
}
div[data-testid="stToast"] {
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
    color: white !important;
    border-radius: 18px !important;
    padding: 1.1rem 1.6rem !important;
    box-shadow: 0 10px 36px rgba(34,197,94,0.5) !important;
    border: none !important;
    width: 320px !important;
    min-width: 320px !important;
    max-width: 320px !important;
    height: auto !important;
    min-height: 80px !important;
    max-height: none !important;
    overflow: visible !important;
    box-sizing: border-box !important;
}
div[data-testid="stToast"] > div,
div[data-testid="stToast"] > div > div,
div[data-testid="stToast"] > div > div > div {
    overflow: visible !important;
    height: auto !important;
    max-height: none !important;
    width: 100% !important;
    max-width: none !important;
}
div[data-testid="stToast"] > div {
    display: flex !important;
    align-items: center !important;
    gap: 0.8rem !important;
}
div[data-testid="stToast"] [data-testid="stToastIcon"] {
    font-size: 2rem !important;
    flex-shrink: 0 !important;
}
div[data-testid="stToast"] p,
div[data-testid="stToast"] span,
div[data-testid="stToast"] div,
div[data-testid="stToast"] li {
    color: white !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
div[data-testid="stToast"] p {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    opacity: 0.92 !important;
    margin: 0 0 3px 0 !important;
    line-height: 1.4 !important;
}
div[data-testid="stToast"] strong {
    font-size: 1.25rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.04em !important;
    color: white !important;
    display: block !important;
    line-height: 1.3 !important;
}
</style>
""", unsafe_allow_html=True)
    st.toast(f"Presupuesto guardado  ·  **{ep}**", icon="✅")
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
# FAB - BOTÓN GUARDAR FLOTANTE
# =========================================================
_es_solo_lectura = (
    st.session_state.cotizacion_cargada and
    st.session_state.margen > 0 and
    not st.session_state.modo_admin
)

_hash_actual = calcular_hash_estado()
_hay_cambios = _hash_actual != st.session_state.get('hash_ultimo_guardado')

_mostrar_fab = (
    len(st.session_state.get('carrito', [])) > 0 and
    not _es_solo_lectura and
    not st.session_state.get('recien_guardado', False) and
    not st.session_state.get('recien_cargado', False) and
    _hay_cambios
)

if st.session_state.get('recien_guardado', False):
    st.session_state.recien_guardado = False
if st.session_state.get('recien_cargado', False):
    st.session_state.recien_cargado = False

if _mostrar_fab:
    st.markdown('<style>#btn_fab_guardar_container{display:none!important}</style>', unsafe_allow_html=True)
    if st.button("💾 Guardar", key="btn_fab_guardar"):
        datos_c, datos_a, proy, cfg, tots, pl_n, pl_d = construir_datos_para_guardar()
        num_g = st.session_state.cotizacion_cargada or generar_numero_unico()
        guardar_cotizacion(num_g, datos_c, datos_a, proy,
                           st.session_state.carrito, cfg, tots, pl_n, pl_d)
        st.session_state.cotizacion_cargada = num_g
        st.session_state.hash_ultimo_guardado = _hash_actual  # reusar hash ya calculado
        st.session_state.recien_guardado = True
        st.session_state.mostrar_toast_exito = True
        st.session_state.toast_numero_ep = num_g
        st.session_state.resultados_busqueda = None
        st.session_state['_tab3_necesita_refresh'] = True
        st.rerun()

    # FAB JS: botón flotante en DOM padre que clickea el botón real
    components.html("""
    <script>
    (function() {
        const parent = window.parent.document;

        const old = parent.getElementById('fab-guardar-wrapper');
        if (old) old.remove();

        const style = parent.getElementById('fab-guardar-style') || parent.createElement('style');
        style.id = 'fab-guardar-style';
        style.innerHTML = `
            @keyframes pulse-fab {
                0%   { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
                50%  { box-shadow: 0 8px 40px rgba(91,124,250,0.9), 0 0 0 12px rgba(91,124,250,0.15); }
                100% { box-shadow: 0 8px 24px rgba(91,124,250,0.5); }
            }
            #fab-guardar-wrapper {
                position: fixed !important;
                bottom: 1.5rem !important;
                left: 2rem !important;
                z-index: 999999 !important;
            }
            #fab-guardar-btn {
                background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%);
                color: white; border: none; border-radius: 50px;
                padding: 0.85rem 1.6rem; font-size: 0.95rem; font-weight: 700;
                cursor: pointer; font-family: sans-serif;
                animation: pulse-fab 2s infinite; white-space: nowrap;
            }
            #fab-guardar-btn:hover { transform: translateY(-3px); animation: none; }
        `;
        if (!parent.getElementById('fab-guardar-style')) parent.head.appendChild(style);

        const wrapper = parent.createElement('div');
        wrapper.id = 'fab-guardar-wrapper';
        const btn = parent.createElement('button');
        btn.id = 'fab-guardar-btn';
        btn.innerHTML = '&#128190; Guardar';
        // Ocultar el botón fijo guardar del layout
        setTimeout(function(){
            const buttons = parent.querySelectorAll('button');
            for (const b of buttons) {
                const txt = (b.innerText || b.textContent || '').trim();
                if ((txt === '💾 Guardar' || txt === 'Guardar') && b.id !== 'fab-guardar-btn') {
                    b.parentElement.style.display = 'none';
                }
            }
        }, 300);

        btn.onclick = function() {
            const buttons = parent.querySelectorAll('button');
            for (const b of buttons) {
                const txt = (b.innerText || b.textContent || '').trim();
                if ((txt === '💾 Guardar' || txt === 'Guardar') && b.id !== 'fab-guardar-btn' && !b.disabled) {
                    b.click();
                    return;
                }
            }
        };
        wrapper.appendChild(btn);
        parent.body.appendChild(wrapper);
    })();
    </script>
    """, height=0)

else:
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
# TAB 4 - 3D BETA
# =========================================================

def _analizar_plano_con_claude(pdf_bytes):
    """Descarga PDF, renderiza imagen, llama Claude Vision, retorna layout JSON."""
    import fitz  # PyMuPDF
    import base64, anthropic, json

    # Renderizar primera página del PDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    mat = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()

    # Convertir a base64
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")

    # Llamar a Claude Vision
    client = anthropic.Anthropic(api_key=SUPABASE_KEY.replace(SUPABASE_KEY, __import__("os").environ.get("ANTHROPIC_API_KEY", "")))
    # Usar la clave de Anthropic directamente
    import httpx
    resp = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": __import__("os").environ.get("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        },
        json={
            "model": "claude-opus-4-5",
            "max_tokens": 1024,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": img_b64}
                    },
                    {
                        "type": "text",
                        "text": """Analiza esta planta arquitectónica de un container house.
Responde SOLO con JSON válido, sin texto extra ni markdown:
{"width":<ancho total metros>,"depth":<profundidad total metros>,"wallHeight":2.8,"walls":[{"side":"front","openings":[{"type":"door","x":<pos x desde centro>,"y":<centro y desde suelo>,"w":<ancho>,"h":<alto>},{"type":"window","x":...,"y":...,"w":...,"h":...}]},{"side":"back","openings":[...]},{"side":"left","openings":[...]},{"side":"right","openings":[...]}]}
Reglas: puertas ~0.9x2.1m (y=1.05), ventanas ~1.2x1.0m (y=1.2). x relativo al centro de la pared (negativo=izquierda). Detecta TODAS las aberturas visibles."""
                    }
                ]
            }]
        },
        timeout=30
    )
    data = resp.json()
    txt = "".join(b.get("text","") for b in data.get("content",[])).strip()
    txt = txt.replace("```json","").replace("```","").strip()
    return json.loads(txt), img_b64

with tab4:
    st.markdown("""
        <style>
        .hdr4 {
            background: linear-gradient(135deg, #003d52 0%, #006978 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr4 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr4 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        </style>
        <div class="hdr4">
          <span style="font-size:2.4rem">🧊</span>
          <div>
            <h2>Visor 3D Beta</h2>
            <p>Selecciona un presupuesto con plano adjunto para generar su prototipo 3D interactivo.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

    # Obtener presupuestos con plano
    try:
        _resp_3d = supabase.table('cotizaciones').select(
            'numero', 'cliente_nombre', 'plano_url', 'plano_nombre'
        ).not_.is_('plano_url', 'null').order('fecha_creacion', desc=True).execute()
        _opciones_3d = _resp_3d.data or []
    except:
        _opciones_3d = []

    if not _opciones_3d:
        st.info("No hay presupuestos con plano adjunto disponibles.")
    else:
        _labels_3d = [
            f"{r['numero']} — {r['cliente_nombre'] or 'S/C'} — {r['plano_nombre'] or 'plano.pdf'}"
            for r in _opciones_3d
        ]
        _sel_3d = st.selectbox("Selecciona presupuesto con plano:", _labels_3d, key="sel_3d_presupuesto")
        _idx_3d = _labels_3d.index(_sel_3d)
        _plano_url_3d = _opciones_3d[_idx_3d]['plano_url']

        st.markdown(f"📎 **Plano:** `{_opciones_3d[_idx_3d]['plano_nombre'] or 'plano.pdf'}`")

        # Cache por URL — procesa automáticamente al seleccionar
        _cache_key = f"layout_3d_{_plano_url_3d}"
        _layout_3d = st.session_state.get(_cache_key)
        _img_b64_3d = st.session_state.get(f"img_3d_{_plano_url_3d}", "")

        # Si no hay layout en cache, procesar automáticamente
        if not _layout_3d:
            with st.spinner("⏳ Procesando plano con IA, un momento..."):
                _pdf_bytes = None
                try:
                    import requests as _req
                    _r = _req.get(_plano_url_3d, timeout=20)
                    _r.raise_for_status()
                    _pdf_bytes = _r.content
                except Exception as _e:
                    st.error(f"❌ No se pudo descargar el plano: {_e}")

            if _pdf_bytes:
                with st.spinner("🖼️ Renderizando página del plano..."):
                    try:
                        import fitz as _fitz
                        _doc = _fitz.open(stream=_pdf_bytes, filetype="pdf")
                        _page = _doc[0]
                        _pix = _page.get_pixmap(matrix=_fitz.Matrix(2.0, 2.0))
                        _img_bytes = _pix.tobytes("png")
                        _doc.close()
                        import base64 as _b64
                        _img_b64_3d = _b64.b64encode(_img_bytes).decode("utf-8")
                        st.session_state[f"img_3d_{_plano_url_3d}"] = _img_b64_3d
                    except Exception as _e:
                        st.error(f"❌ Error al renderizar PDF: {_e}. Asegúrate de instalar PyMuPDF: pip install pymupdf")
                        _img_b64_3d = ""

                if _img_b64_3d:
                    with st.spinner("🤖 Analizando plano con IA..."):
                        try:
                            import httpx as _httpx, json as _json
                            _api_key = ANTHROPIC_API_KEY
                            if not _api_key:
                                raise ValueError("ANTHROPIC_API_KEY no configurada")
                            _cv_resp = _httpx.post(
                                "https://api.anthropic.com/v1/messages",
                                headers={
                                    "x-api-key": _api_key,
                                    "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"
                                },
                                json={
                                    "model": "claude-sonnet-4-20250514",
                                    "max_tokens": 2048,
                                    "messages": [
                                        {
                                            "role": "user",
                                            "content": [
                                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _img_b64_3d}},
                                                {"type": "text", "text": """Analiza este plano arquitectónico de un container house.

PASO 1 — Describe brevemente lo que ves:
- Dimensiones totales del container (largo x ancho en metros)
- Cuántas PUERTAS reales hay (deben tener arco de 90°) y en qué pared
- Cuántas VENTANAS reales hay (rectángulo con doble línea o líneas internas) y en qué pared
- IGNORA completamente: costillas estructurales, líneas de división interna, muebles, cotas

PASO 2 — Genera el JSON final con SOLO las aberturas reales que describiste:
{"width":<largo>,"depth":<ancho>,"wallHeight":2.8,"walls":[{"side":"front","openings":[{"type":"door","x":<x desde centro pared>,"y":1.05,"w":<ancho m>,"h":2.1},{"type":"window","x":<x>,"y":1.2,"w":<ancho m>,"h":<alto m>}]},{"side":"back","openings":[...]},{"side":"left","openings":[...]},{"side":"right","openings":[...]}]}

LÍMITES ESTRICTOS: máximo 3 puertas y 6 ventanas en total. Una pared sin aberturas usa "openings":[]
El JSON debe ir al final de tu respuesta, solo como bloque de código con ```json```"""}
                                            ]
                                        }
                                    ]
                                },
                                timeout=40
                            )
                            _cv_data = _cv_resp.json()
                            _cv_txt = "".join(b.get("text","") for b in _cv_data.get("content",[])).strip()

                            # Extraer JSON del bloque ```json``` si existe, sino buscar { directo
                            import re as _re
                            _json_match = _re.search(r'```json\s*(\{.*?\})\s*```', _cv_txt, _re.DOTALL)
                            if _json_match:
                                _cv_json_str = _json_match.group(1)
                            else:
                                # Fallback: encontrar el primer { hasta el último }
                                _js = _cv_txt.find('{')
                                _je = _cv_txt.rfind('}')
                                _cv_json_str = _cv_txt[_js:_je+1] if _js >= 0 else _cv_txt

                            _layout_raw = _json.loads(_cv_json_str)

                            # ── Post-procesador estricto ──────────────────────────
                            _W = float(_layout_raw.get("width", 9))
                            _D = float(_layout_raw.get("depth", 3))

                            # Límites máximos de aberturas por pared
                            _max_openings = {"front": 3, "back": 2, "left": 2, "right": 2}

                            for _wall in _layout_raw.get("walls", []):
                                _side  = _wall["side"]
                                _wlen  = _W if _side in ("front","back") else _D
                                _valid = []

                                for _op in _wall.get("openings", []):
                                    _ow  = float(_op.get("w", 0.9))
                                    _oh  = float(_op.get("h", 2.1))
                                    _ox  = float(_op.get("x", 0))
                                    _oy  = float(_op.get("y", 1.05))

                                    # Filtro 1: x dentro del rango de la pared
                                    if abs(_ox) + _ow/2 >= _wlen/2 - 0.05:
                                        continue

                                    # Filtro 2: dimensiones razonables
                                    if _op.get("type") == "door":
                                        if not (0.7 <= _ow <= 1.2 and 1.8 <= _oh <= 2.4):
                                            continue
                                    else:  # window
                                        if not (0.4 <= _ow <= 2.0 and 0.4 <= _oh <= 1.8):
                                            continue

                                    # Filtro 3: y dentro de la pared
                                    if _oy - _oh/2 < 0 or _oy + _oh/2 > 2.8:
                                        continue

                                    # Filtro 4: no solapada con otra abertura ya aceptada
                                    _overlap = False
                                    for _v in _valid:
                                        if abs(_ox - float(_v["x"])) < (_ow + float(_v["w"]))/2 + 0.05:
                                            _overlap = True; break
                                    if _overlap:
                                        continue

                                    _valid.append({**_op, "x": _ox, "y": _oy, "w": _ow, "h": _oh})

                                # Limitar cantidad máxima por pared
                                _wall["openings"] = _valid[:_max_openings.get(_side, 3)]

                            _layout_3d = _layout_raw
                            st.session_state[_cache_key] = _layout_3d
                            st.rerun()
                        except ValueError as _ve:
                            # Sin API key: análisis geométrico local
                            st.warning(f"⚠️ {_ve} — usando análisis geométrico local")
                            try:
                                import base64 as _b64c, io, json as _json
                                from PIL import Image as _PIL_Image
                                import numpy as _np

                                _img_data = _b64c.b64decode(_img_b64_3d)
                                _pil_img = _PIL_Image.open(io.BytesIO(_img_data)).convert("L")
                                _arr = _np.array(_pil_img)
                                ih, iw = _arr.shape

                                # Bounding box del contenido oscuro (paredes)
                                _dark = _arr < 100
                                _rows = _np.any(_dark, axis=1)
                                _cols = _np.any(_dark, axis=0)
                                _r0,_r1 = _np.where(_rows)[0][[0,-1]]
                                _c0,_c1 = _np.where(_cols)[0][[0,-1]]

                                # Escala: asumir que el plano representa un container HC
                                # Maitencillo HC: 6.0 x 3.0 m típico, o 9.0 x 3.0 m
                                _ratio = (_c1-_c0) / max(_r1-_r0, 1)
                                if _ratio > 2.5:
                                    _W, _D = 9.0, 3.0
                                elif _ratio > 1.8:
                                    _W, _D = 6.0, 3.0
                                else:
                                    _W, _D = 6.0, 3.0

                                # Detectar aberturas por proyección de píxeles claros en bordes
                                def _find_openings(edge_strip, wall_len, side):
                                    """Detecta zonas claras (aberturas) en un strip del borde"""
                                    bright = edge_strip > 200
                                    openings = []
                                    in_gap = False
                                    gap_start = 0
                                    min_gap = int(iw * 0.05)  # mínimo 5% del ancho
                                    for i, b in enumerate(bright):
                                        if b and not in_gap:
                                            in_gap = True; gap_start = i
                                        elif not b and in_gap:
                                            in_gap = False
                                            gap_w = i - gap_start
                                            if gap_w >= min_gap:
                                                cx = (gap_start + i/2) / len(bright) * wall_len - wall_len/2
                                                w_m = gap_w / len(bright) * wall_len
                                                if w_m < 1.5:  # puerta
                                                    openings.append({"type":"door","x":round(cx,2),"y":1.05,"w":round(min(w_m,1.0),2),"h":2.1})
                                                else:  # ventana
                                                    openings.append({"type":"window","x":round(cx,2),"y":1.2,"w":round(min(w_m,1.5),2),"h":1.0})
                                    return openings

                                _strip_h = max(5, int(ih*0.05))
                                _strip_w = max(5, int(iw*0.05))
                                _front_strip = _arr[_r1-_strip_h:_r1, _c0:_c1].mean(axis=0)
                                _back_strip  = _arr[_r0:_r0+_strip_h, _c0:_c1].mean(axis=0)
                                _left_strip  = _arr[_r0:_r1, _c0:_c0+_strip_w].mean(axis=1)
                                _right_strip = _arr[_r0:_r1, _c1-_strip_w:_c1].mean(axis=1)

                                _layout_3d = {
                                    "width": _W, "depth": _D, "wallHeight": 2.8,
                                    "walls": [
                                        {"side":"front",  "openings": _find_openings(_front_strip, _W, "front")},
                                        {"side":"back",   "openings": _find_openings(_back_strip,  _W, "back")},
                                        {"side":"left",   "openings": _find_openings(_left_strip,  _D, "left")},
                                        {"side":"right",  "openings": _find_openings(_right_strip, _D, "right")},
                                    ]
                                }
                                st.session_state[_cache_key] = _layout_3d
                                st.rerun()
                            except Exception as _e2:
                                st.error(f"❌ Error en análisis local: {_e2}")
                        except Exception as _e_api:
                            st.error(f"❌ Error API Claude: {_e_api}")
                            st.info("💡 Configura ANTHROPIC_API_KEY en los secrets de Streamlit para usar Claude Vision.")


        if _layout_3d and _img_b64_3d:
            import json as _json
            _layout_json = _json.dumps(_layout_3d)

            _visor_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:#0f1117;overflow:hidden;font-family:'Segoe UI',sans-serif;}}
#wrap{{width:100%;height:600px;position:relative;}}
#c3d{{width:100%;height:100%;display:block;}}
#ctrl{{position:absolute;top:10px;left:10px;z-index:10;display:flex;gap:6px;flex-wrap:wrap;}}
.btn{{background:rgba(15,17,34,0.82);color:#cdd6f4;border:1px solid rgba(255,255,255,0.15);padding:5px 12px;border-radius:18px;cursor:pointer;font-size:11px;font-weight:600;transition:all .15s;}}
.btn:hover,.btn.on{{background:rgba(91,124,250,0.72);border-color:#5b7cfa;color:#fff;}}
#hud{{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);color:rgba(255,255,255,0.35);font-size:10px;background:rgba(0,0,0,0.5);padding:5px 14px;border-radius:18px;white-space:nowrap;}}
</style></head>
<body><div id="wrap">
<canvas id="c3d"></canvas>
<div id="ctrl">
<button class="btn on" id="bRoof" onclick="tog('roof')">🏠 Techo</button>
<button class="btn on" id="bPlan" onclick="tog('plan')">📐 Plano</button>
<button class="btn on" id="bWire" onclick="tog('wire')">🔲 Wire</button>
<button class="btn" onclick="resetCam()">🎯 Reset</button>
<button class="btn" onclick="setV('top')">⬆ Top</button>
<button class="btn" onclick="setV('iso')">🔷 Iso</button>
</div>
<div id="hud">🖱 Arrastrar: rotar │ Scroll: zoom │ Derecho: mover</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const LAYOUT={_layout_json};
const IMG_B64="{_img_b64_3d}";

const cv=document.getElementById('c3d');
const W0=cv.parentElement.offsetWidth,H0=600;
const renderer=new THREE.WebGLRenderer({{canvas:cv,antialias:true}});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setSize(W0,H0);
renderer.shadowMap.enabled=true;
const scene=new THREE.Scene();
scene.background=new THREE.Color(0x0f1117);
const camera=new THREE.PerspectiveCamera(42,W0/H0,0.1,300);
let S={{th:0.6,ph:1.0,r:32}},T=new THREE.Vector3(0,1.5,0);
function applyC(){{
  camera.position.set(T.x+S.r*Math.sin(S.ph)*Math.sin(S.th),T.y+S.r*Math.cos(S.ph),T.z+S.r*Math.sin(S.ph)*Math.cos(S.th));
  camera.lookAt(T);
}}
applyC();
scene.add(new THREE.AmbientLight(0xffffff,0.5));
const sun=new THREE.DirectionalLight(0xfff8e7,1.0);
sun.position.set(15,25,12);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);
scene.add(sun);
scene.add(new THREE.HemisphereLight(0x7788cc,0x223344,0.35));
scene.add(new THREE.GridHelper(80,80,0x1e2140,0x1a1d36));
const gRoof=new THREE.Group(),gPlan=new THREE.Group(),gWire=new THREE.Group(),gBody=new THREE.Group();
scene.add(gBody,gRoof,gPlan,gWire);
const vis={{roof:true,plan:true,wire:true}};
function tog(k){{
  vis[k]=!vis[k];
  if(k==='roof')gRoof.visible=vis[k];
  if(k==='plan')gPlan.visible=vis[k];
  if(k==='wire')gWire.visible=vis[k];
  document.getElementById('b'+k[0].toUpperCase()+k.slice(1)).classList.toggle('on',vis[k]);
}}
let drag=false,rDrag=false,lx=0,ly=0;
cv.addEventListener('mousedown',e=>{{drag=true;rDrag=e.button===2;lx=e.clientX;ly=e.clientY;}});
cv.addEventListener('contextmenu',e=>e.preventDefault());
window.addEventListener('mouseup',()=>drag=false);
window.addEventListener('mousemove',e=>{{
  if(!drag)return;
  const dx=e.clientX-lx,dy=e.clientY-ly;lx=e.clientX;ly=e.clientY;
  if(rDrag){{const r=new THREE.Vector3().crossVectors(new THREE.Vector3().subVectors(camera.position,T).normalize(),camera.up).normalize();T.addScaledVector(r,-dx*0.022);T.y+=dy*0.022;}}
  else{{S.th-=dx*0.007;S.ph=Math.max(0.05,Math.min(Math.PI/2.05,S.ph+dy*0.007));}}
  applyC();
}});
cv.addEventListener('wheel',e=>{{S.r=Math.max(3,Math.min(80,S.r+e.deltaY*0.04));applyC();}},{{passive:true}});
function resetCam(){{S={{th:0.6,ph:1.0,r:32}};T.set(0,1.5,0);applyC();}}
function setV(v){{if(v==='top'){{S.ph=0.04;applyC();}}else{{S={{th:0.8,ph:0.85,r:30}};applyC();}}}}
(function loop(){{requestAnimationFrame(loop);renderer.render(scene,camera);}})();

// Materiales
const mWall=new THREE.MeshStandardMaterial({{color:0xd4dde3,roughness:0.45,metalness:0.2}});
const mRoof=new THREE.MeshStandardMaterial({{color:0x546e7a,roughness:0.4,metalness:0.55}});
const mGlass=new THREE.MeshStandardMaterial({{color:0x89cff0,transparent:true,opacity:0.4,roughness:0.05,metalness:0.1}});
const mDoor=new THREE.MeshStandardMaterial({{color:0x37474f,roughness:0.4,metalness:0.6}});
const mWire=new THREE.MeshBasicMaterial({{color:0x5b7cfa,wireframe:true}});
const mRib=new THREE.MeshStandardMaterial({{color:0x8fa4ae,roughness:0.45,metalness:0.5}});

const W=LAYOUT.width, D=LAYOUT.depth, H=LAYOUT.wallHeight||2.8, th=0.14;

// Plano PDF como textura en el suelo
const img=new Image();
img.onload=()=>{{
  const tex=new THREE.Texture(img);tex.needsUpdate=true;
  const fm=new THREE.Mesh(new THREE.PlaneGeometry(W,D),new THREE.MeshStandardMaterial({{map:tex,roughness:0.85}}));
  fm.rotation.x=-Math.PI/2;fm.position.y=0.01;fm.receiveShadow=true;gPlan.add(fm);
}};
img.src='data:image/png;base64,'+IMG_B64;

// Suelo sólido
const flM=new THREE.Mesh(new THREE.BoxGeometry(W+th*2,0.1,D+th*2),
  new THREE.MeshStandardMaterial({{color:0xc8cdd4,roughness:0.95}}));
flM.position.y=-0.05;flM.receiveShadow=true;gBody.add(flM);

// ── makeWall: construye una pared con huecos correctos ──────────
// wallW = largo de la pared, openings = array de {{type,x,y,w,h}}
// x = posición desde el centro de la pared (-wallW/2 .. +wallW/2)
// y = centro vertical desde el suelo (0..H)
function makeWall(px, pz, rotY, wallW, openings) {{

  // 1. Clonar y sanear openings — clamp para que no salgan del borde
  const ops = openings
    .map(op => {{
      const hw = op.w / 2;
      const x  = Math.max(-wallW/2 + hw + 0.01, Math.min(wallW/2 - hw - 0.01, op.x));
      const yb = op.y - op.h/2;  // base
      const yt = op.y + op.h/2;  // tope
      const y  = Math.max(op.h/2 + 0.01, Math.min(H - op.h/2 - 0.01, op.y));
      return {{ ...op, x, y }};
    }})
    .sort((a,b) => a.x - b.x);

  const grp = new THREE.Group();
  grp.position.set(px, 0, pz);
  grp.rotation.y = rotY;

  // 2. Por cada abertura construir: panel-izq, dintel, antepecho, relleno
  let curX = -wallW / 2;

  ops.forEach(op => {{
    const opL = op.x - op.w/2;   // borde izquierdo del hueco
    const opR = op.x + op.w/2;   // borde derecho
    const opB = op.y - op.h/2;   // base del hueco
    const opT = op.y + op.h/2;   // tope del hueco

    // Panel izquierdo (lleno, de suelo a techo)
    const segW = opL - curX;
    if (segW > 0.02) {{
      const m = new THREE.Mesh(new THREE.BoxGeometry(segW, H, th), mWall);
      m.position.set(curX + segW/2, H/2, 0);
      m.castShadow = true; m.receiveShadow = true;
      grp.add(m);
    }}
    curX = opR;

    // Dintel (sobre el hueco)
    const dintelH = H - opT;
    if (dintelH > 0.02) {{
      const m = new THREE.Mesh(new THREE.BoxGeometry(op.w, dintelH, th), mWall);
      m.position.set(op.x, opT + dintelH/2, 0);
      m.castShadow = true;
      grp.add(m);
    }}

    // Antepecho (bajo el hueco — solo ventanas)
    if (op.type === 'window' && opB > 0.02) {{
      const m = new THREE.Mesh(new THREE.BoxGeometry(op.w, opB, th), mWall);
      m.position.set(op.x, opB/2, 0);
      m.castShadow = true;
      grp.add(m);
    }}

    // Relleno del hueco (vidrio o puerta)
    const mat  = op.type === 'door' ? mDoor : mGlass;
    const fill = new THREE.Mesh(new THREE.BoxGeometry(op.w, op.h, th * 0.3), mat);
    fill.position.set(op.x, op.y, 0);
    fill.castShadow = true;
    grp.add(fill);

    // Marco del hueco
    const mrkMat = mRib;
    const mkT = 0.05;
    // Jambas laterales
    [opL - mkT/2, opR + mkT/2].forEach(mx => {{
      const mk = new THREE.Mesh(new THREE.BoxGeometry(mkT, op.h, th+0.02), mrkMat);
      mk.position.set(mx, op.y, 0); grp.add(mk);
    }});
    // Dintel marco
    const mk2 = new THREE.Mesh(new THREE.BoxGeometry(op.w + mkT*2, mkT, th+0.02), mrkMat);
    mk2.position.set(op.x, opT + mkT/2, 0); grp.add(mk2);
    // Umbral (solo ventana)
    if (op.type === 'window') {{
      const mk3 = new THREE.Mesh(new THREE.BoxGeometry(op.w + mkT*2, mkT, th+0.02), mrkMat);
      mk3.position.set(op.x, opB - mkT/2, 0); grp.add(mk3);
    }}
  }});

  // Panel derecho final
  const remW = wallW/2 - curX;
  if (remW > 0.02) {{
    const m = new THREE.Mesh(new THREE.BoxGeometry(remW, H, th), mWall);
    m.position.set(curX + remW/2, H/2, 0);
    m.castShadow = true; m.receiveShadow = true;
    grp.add(m);
  }}

  gBody.add(grp);

  // Wire outline (pared completa, en grupo separado)
  const wg = new THREE.Group();
  wg.position.set(px, H/2, pz);
  wg.rotation.y = rotY;
  wg.add(new THREE.Mesh(new THREE.BoxGeometry(wallW, H, th), mWire));
  gWire.add(wg);
}}

// ── Construir las 4 paredes ─────────────────────────────────────
LAYOUT.walls.forEach(w => {{
  let px, pz, rotY, ww;
  if      (w.side==='front') {{ px=0;    pz= D/2; rotY=0;          ww=W; }}
  else if (w.side==='back')  {{ px=0;    pz=-D/2; rotY=0;          ww=W; }}
  else if (w.side==='left')  {{ px=-W/2; pz=0;    rotY=Math.PI/2;  ww=D; }}
  else                       {{ px= W/2; pz=0;    rotY=Math.PI/2;  ww=D; }}
  makeWall(px, pz, rotY, ww, w.openings||[]);
}});

// ── Techo ───────────────────────────────────────────────────────
// Losa principal
const roofM = new THREE.Mesh(new THREE.BoxGeometry(W+th*2, 0.18, D+th*2), mRoof);
roofM.position.y = H + 0.09;
roofM.castShadow = true;
gRoof.add(roofM);
// Alero frontal
const aleroM = new THREE.Mesh(new THREE.BoxGeometry(W+th*2, 0.08, 0.4), mRoof);
aleroM.position.set(0, H+0.04, D/2+th+0.2);
gRoof.add(aleroM);
// Perfil metálico perimetral del techo
[[W+th*2, 0.12, th, 0, D/2+th/2, 0],
 [W+th*2, 0.12, th, 0,-D/2-th/2, 0],
 [th, 0.12, D+th*2,-W/2-th/2, 0, 0],
 [th, 0.12, D+th*2, W/2+th/2, 0, 0]].forEach(r => {{
  const m = new THREE.Mesh(new THREE.BoxGeometry(r[0],r[1],r[2]), mRib);
  m.position.set(r[3], H, r[4]);
  gRoof.add(m);
}});

// ── Costillas estructurales (rasgos de container) ───────────────
const ribHeights = [0.0, 0.55, 1.1, 1.65, 2.2, H];
ribHeights.forEach(h => {{
  // frente y atrás
  [D/2+th*0.6, -D/2-th*0.6].forEach(pz2 => {{
    const m = new THREE.Mesh(new THREE.BoxGeometry(W+th*2, 0.05, 0.05), mRib);
    m.position.set(0, h, pz2); gBody.add(m);
  }});
  // laterales
  [-W/2-th*0.6, W/2+th*0.6].forEach(px2 => {{
    const m = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.05, D+th*2), mRib);
    m.position.set(px2, h, 0); gBody.add(m);
  }});
}});

// ── Columnas en las 4 esquinas ──────────────────────────────────
[[-W/2, -D/2],[W/2, -D/2],[-W/2, D/2],[W/2, D/2]].forEach(([cx,cz]) => {{
  const col = new THREE.Mesh(new THREE.BoxGeometry(th+0.04, H+0.2, th+0.04), mRib);
  col.position.set(cx, H/2, cz);
  col.castShadow = true;
  gBody.add(col);
}});

// ── Ajustar cámara ──────────────────────────────────────────────
T.set(0, H * 0.35, 0);
S.r  = Math.max(W, D) * 2.6;
S.th = 0.55;   // ángulo horizontal — muestra fachada frontal
S.ph = 0.85;   // ángulo vertical — ni muy alto ni muy bajo
applyC();
</script></body></html>"""

            import streamlit.components.v1 as _components
            _components.html(_visor_html, height=620, scrolling=False)
            st.caption(f"⚠️ Beta — Dimensiones detectadas: {_layout_3d.get('width',0):.1f}m × {_layout_3d.get('depth',0):.1f}m × {_layout_3d.get('wallHeight',2.8):.1f}m altura")

            # Debug: mostrar JSON detectado + botón para regenerar
            import json as _json_dbg
            _col_dbg1, _col_dbg2 = st.columns([3,1])
            with _col_dbg2:
                if st.button("🔄 Regenerar", key="btn_regen_3d", help="Forzar nuevo análisis del plano"):
                    st.session_state.pop(_cache_key, None)
                    st.session_state.pop(f"img_3d_{_plano_url_3d}", None)
                    st.rerun()
            with _col_dbg1:
                with st.expander("🔍 Ver JSON detectado por Claude Vision"):
                    st.json(_layout_3d)

# =========================================================
# TAB 5 - PROYECTO EXCEL (solo admin)
# =========================================================
if st.session_state.modo_admin and tab5 is not None:
    with tab5:

        # CSS del tab5
        st.markdown("""
        <style>
        .excel-header {
            background: linear-gradient(135deg, #0f2240 0%, #1a4d33 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px; margin-top: -1rem;
            display: flex; align-items: center; gap: 16px;
        }
        .excel-header h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .excel-header p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }

        /* Padding para todos los widgets del tab5 */
        [data-testid="stVerticalBlock"] [data-testid="stFileUploader"],
        [data-testid="stVerticalBlock"] [data-testid="stTextInput"] > div,
        [data-testid="stVerticalBlock"] [data-testid="stTextInput"] input {
            padding-left: 4px;
        }
        /* Contenedor de subida con bordes y padding */
        .upload-box {
            background: white;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            padding: 20px 28px 16px 28px;
            margin-bottom: 16px;
        }
        .upload-box .stFileUploader {
            padding: 0 !important;
        }
        .version-row { margin-bottom: 4px; }
        .status-bar-green {
            background: linear-gradient(90deg,rgba(16,185,129,0.12),rgba(16,185,129,0.03));
            border: 1px solid #10b981; border-radius: 10px;
            padding: 14px 20px; margin-top: 16px;
        }
        .status-bar-warn {
            background: rgba(245,158,11,0.08); border: 1px solid #f59e0b;
            border-radius: 10px; padding: 14px 20px; margin-top: 16px;
        }
        </style>
        """, unsafe_allow_html=True)

        # Header
        st.markdown("""
        <div class="excel-header">
          <span style="font-size:2.4rem">📊</span>
          <div>
            <h2>Proyecto Excel — Control de Versiones</h2>
            <p>Sube nuevas versiones del cotizador.xlsx y activa la que necesites. El sistema se actualiza al instante.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Subir nueva versión ──────────────────────────────
        # Usar key dinámica para resetear el uploader tras subir
        if "excel_upload_key" not in st.session_state:
            st.session_state.excel_upload_key = 0


        with st.container():
            st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
            _mg_l, _titulo_col, _mg_r = st.columns([0.4, 9, 0.4])
            with _titulo_col:
                st.markdown("##### ⬆️ Subir nueva versión")
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

            # Columnas con margen lateral para simular padding
            _mg, _col_up1, _col_up2, _mg2 = st.columns([0.4, 3, 2, 0.4])
            with _col_up1:
                _excel_file = st.file_uploader(
                    "Archivo cotizador.xlsx",
                    type=["xlsx"],
                    key=f"uploader_excel_{st.session_state.excel_upload_key}",
                    label_visibility="collapsed"
                )
            with _col_up2:
                st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
                _version_nombre = st.text_input(
                    "Nombre de versión",
                    placeholder="Ej: v2.1 — Abril 2025",
                    key=f"input_vnom_{st.session_state.excel_upload_key}",
                    label_visibility="collapsed"
                )
                st.caption("📝 Nombre de la versión")

            if _excel_file and _version_nombre:
                st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                _mg3, _col_sb, _col_info, _mg4 = st.columns([0.4, 1, 3, 0.4])
                with _col_sb:
                    _btn_subir = st.button("📤 Subir versión", key="btn_subir_excel",
                                           use_container_width=True, type="primary")
                with _col_info:
                    st.info(f"📁 **{_excel_file.name}** — versión: **{_version_nombre}**")

                if _btn_subir:
                    with st.spinner("⏳ Subiendo archivo a Supabase..."):
                        try:
                            import datetime as _dt
                            _ts = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                            _nombre_archivo = f"cotizador_{_ts}.xlsx"
                            _excel_bytes = _excel_file.read()

                            supabase.storage.from_("config").upload(
                                path=_nombre_archivo,
                                file=_excel_bytes,
                                file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                            )
                            _url_publica = supabase.storage.from_("config").get_public_url(_nombre_archivo)
                            supabase.table("excel_versiones").insert({
                                "version_nombre": _version_nombre,
                                "archivo_url": _url_publica,
                                "archivo_nombre": _nombre_archivo,
                                "activa": False,
                                "subida_por": "admin"
                            }).execute()

                            st.session_state.excel_upload_key += 1
                            st.success(f"✅ Versión **{_version_nombre}** subida correctamente.")
                            st.rerun()
                        except Exception as _e:
                            st.error(f"❌ Error al subir: {_e}")
            elif _excel_file and not _version_nombre:
                _mg5, _col_w, _mg6 = st.columns([0.4, 5, 0.4])
                with _col_w:
                    st.warning("⚠️ Escribe un nombre para identificar esta versión.")

            st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

        st.markdown("---")

        # ── Lista de versiones ───────────────────────────────
        st.markdown("##### 📋 Versiones disponibles")
        st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
        try:
            _versiones = supabase.table("excel_versiones").select("*").order("fecha_subida", desc=True).execute().data or []
        except:
            _versiones = []

        if not _versiones:
            st.info("📭 No hay versiones subidas aún. Sube el cotizador.xlsx para comenzar.")
        else:
            for _v in _versiones:
                _es_activa = _v.get("activa", False)
                _fecha = str(_v.get("fecha_subida",""))[:16].replace("T"," ")

                _cv1, _cv2, _cv3, _cv4 = st.columns([3, 2.5, 1.5, 0.6])

                with _cv1:
                    if _es_activa:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">'
                            f'<span style="font-size:1.5rem">🟢</span>'
                            f'<div><div style="font-size:1.05rem;font-weight:700;color:#065f46;">{_v["version_nombre"]}</div>'
                            f'<div style="font-size:0.75rem;color:#10b981;font-weight:600;">✅ VERSIÓN ACTIVA</div></div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:10px;padding:4px 0;">'
                            f'<span style="font-size:1.2rem;opacity:.35;">⚪</span>'
                            f'<div><div style="font-size:1rem;font-weight:600;color:#374151;">{_v["version_nombre"]}</div>'
                            f'<div style="font-size:0.75rem;color:#9ca3af;">🗓 {_fecha}</div></div>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                with _cv2:
                    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
                    st.caption(f"📁 `{_v.get('archivo_nombre','')}`")
                    st.caption(f"🗓 {_fecha} &nbsp;·&nbsp; 👤 {_v.get('subida_por','admin')}")

                with _cv3:
                    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                    if not _es_activa:
                        if st.button("⚡ Activar", key=f"btn_act_{_v['id']}",
                                     use_container_width=True, type="primary"):
                            with st.spinner("Activando..."):
                                try:
                                    supabase.table("excel_versiones").update({"activa": False}).neq("id","00000000-0000-0000-0000-000000000000").execute()
                                    supabase.table("excel_versiones").update({"activa": True}).eq("id", _v["id"]).execute()
                                    _get_excel_bytes_activo.clear()
                                    st.session_state.pop("excel_bytes_cache", None)
                                    st.rerun()
                                except Exception as _e:
                                    st.error(f"❌ {_e}")
                    else:
                        st.markdown(
                            '<div style="background:#10b981;color:white;padding:8px 0;'
                            'border-radius:8px;text-align:center;font-size:12px;font-weight:700;">'
                            '🟢 ACTIVA</div>',
                            unsafe_allow_html=True
                        )

                with _cv4:
                    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                    if not _es_activa:
                        if st.button("🗑️", key=f"btn_del_{_v['id']}", help="Eliminar esta versión"):
                            try:
                                supabase.storage.from_("config").remove([_v.get("archivo_nombre","")])
                                supabase.table("excel_versiones").delete().eq("id", _v["id"]).execute()
                                st.rerun()
                            except Exception as _e:
                                st.error(f"❌ {_e}")

                st.markdown('<hr style="border:none;border-top:1px solid #f0f0f0;margin:8px 0 12px;">', unsafe_allow_html=True)

        # ── Barra de estado ──────────────────────────────────
        _activa_info = next((_v for _v in _versiones if _v.get("activa")), None)
        if _activa_info:
            _fa = str(_activa_info.get("fecha_subida",""))[:16].replace("T"," ")
            st.markdown(
                f'<div style="background:linear-gradient(90deg,rgba(16,185,129,0.12),rgba(16,185,129,0.03));'
                f'border:1px solid #10b981;border-radius:10px;padding:14px 20px;margin-top:12px;'
                f'display:flex;align-items:center;gap:12px;">'
                f'<span style="font-size:1.4rem">🟢</span>'
                f'<div><span style="color:#065f46;font-weight:700;">Sistema usando versión activa:</span> '
                f'<strong style="color:#059669;">{_activa_info["version_nombre"]}</strong>'
                f'<span style="color:#6b7280;font-size:0.8rem;margin-left:10px;">subida el {_fa}</span></div>'
                f'</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div style="background:rgba(245,158,11,0.08);border:1px solid #f59e0b;'
                'border-radius:10px;padding:14px 20px;margin-top:12px;">'
                '⚠️ <strong>Sin versión activa</strong> — el sistema usa el archivo local '
                '<code>cotizador.xlsx</code> de GitHub.</div>',
                unsafe_allow_html=True
            )



# =========================================================
# FAB - MARGEN FLOTANTE (st.popover nativo — 100% confiable)
# =========================================================
_margen_actual = st.session_state.margen
_mstr = f"{_margen_actual:.1f}"

if st.session_state.modo_admin:
    _color_fab = '#10b981' if _margen_actual > 0 else '#6b7280'
    st.markdown(f"""
<style>
/* Identificar el popover de margen por ser el ÚNICO popover fuera del header */
section[data-testid="stMain"] div[data-testid="stPopover"] {{
    position: fixed !important;
    bottom: 1.5rem !important;
    left: 12rem !important;
    z-index: 99998 !important;
}}
section[data-testid="stMain"] div[data-testid="stPopover"] > div > button {{
    background: linear-gradient(135deg, {_color_fab}, {_color_fab}dd) !important;
    color: white !important;
    border: none !important;
    border-radius: 50px !important;
    padding: 0.8rem 1.4rem !important;
    font-size: 0.9rem !important;
    font-weight: 700 !important;
    white-space: nowrap !important;
    box-shadow: 0 6px 20px rgba(16,185,129,.4) !important;
    min-height: unset !important;
    height: auto !important;
}}
</style>
""", unsafe_allow_html=True)

    with st.popover(f"📊 Margen: {_mstr}%"):
        st.markdown("**Aplicar margen**")
        _mg_pop = st.number_input(
            "Margen %", min_value=0.0, max_value=100.0,
            value=float(_margen_actual),
            step=0.5, format="%.1f",
            key="margen_popover"
        )
        if st.button("✅ Aplicar", key="btn_aplicar_margen", use_container_width=True):
            st.session_state.margen = _mg_pop
            st.rerun()

else:
    components.html("""<script>
(function(){
  var D=window.parent.document;
  ['_fm_s','_fm_b','_fm_p'].forEach(function(id){
    var e=D.getElementById(id); if(e) e.remove();
  });
})();
</script>""", height=0)

# =========================================================
# TAB 6 - EDICIÓN PDF (visible para todos)
# =========================================================
if tab6 is not None:
    with tab6:
        st.markdown("""
        <style>
        .hdr6 {
            background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr6 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr6 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        </style>
        <div class="hdr6">
          <span style="font-size:2.4rem">✏️</span>
          <div>
            <h2>Edición PDF Cliente</h2>
            <p>Busca tu cotización por número EP y personaliza la descripción de cada categoría para el cliente.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Buscar cotización por EP
        with st.container(border=True):
            st.markdown("#### 🔍 Buscar cotización")
            col_ep, col_btn = st.columns([3, 1])
            with col_ep:
                _ep_buscar = st.text_input("Número EP", placeholder="Ej: EP-22286",
                                           key="pdf_edit_ep_input",
                                           label_visibility="collapsed")
            with col_btn:
                _btn_buscar_ep = st.button("🔍 Buscar", use_container_width=True,
                                           key="pdf_edit_btn_buscar", type="primary")

        # Estado de cotización cargada para edición
        if 'pdf_edit_cotizacion' not in st.session_state:
            st.session_state.pdf_edit_cotizacion = None
        if 'pdf_edit_numero' not in st.session_state:
            st.session_state.pdf_edit_numero = None

        if _btn_buscar_ep and _ep_buscar.strip():
            _cot_found = cargar_cotizacion(_ep_buscar.strip().upper())
            if _cot_found:
                st.session_state.pdf_edit_cotizacion = _cot_found
                st.session_state.pdf_edit_numero = _ep_buscar.strip().upper()
                st.success(f"✅ Cotización {st.session_state.pdf_edit_numero} encontrada — {_cot_found.get('cliente_nombre','S/C')}")
            else:
                st.error("❌ No se encontró la cotización. Verifica el número EP.")
                st.session_state.pdf_edit_cotizacion = None
                st.session_state.pdf_edit_numero = None

        # Si hay cotización cargada, mostrar editor
        if st.session_state.pdf_edit_cotizacion and st.session_state.pdf_edit_numero:
            _cot_edit = st.session_state.pdf_edit_cotizacion
            _num_edit = st.session_state.pdf_edit_numero

            # Info de la cotización
            st.markdown(f"""
            <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;
                        padding:12px 16px;margin:12px 0;">
                <b>📋 {_num_edit}</b> — {_cot_edit.get('cliente_nombre','S/C')} &nbsp;|&nbsp;
                Asesor: {_cot_edit.get('asesor_nombre','—')} &nbsp;|&nbsp;
                Fecha: {(_cot_edit.get('fecha_creacion','')[:10])}
            </div>
            """, unsafe_allow_html=True)

            # Cargar descripciones — preferir session_state para evitar CDN cache
            _cache_key_desc = f"_desc_cache_{_num_edit}"
            if _cache_key_desc in st.session_state:
                _desc_actuales = st.session_state[_cache_key_desc]
            else:
                _desc_actuales = cargar_descripciones_por_ep(_num_edit)
                st.session_state[_cache_key_desc] = _desc_actuales

            # Obtener categorías de los productos de esta cotización
            _productos = _cot_edit.get('productos', [])
            if _productos:
                _cats_ep = sorted(list({p.get('Categoria','') for p in _productos if p.get('Categoria','')}))
            else:
                _cats_ep = []

            if not _cats_ep:
                st.warning("Esta cotización no tiene productos con categorías definidas.")
            else:
                st.markdown(f"#### 📝 Editar descripciones ({len(_cats_ep)} categorías)")
                st.caption("Escribe la descripción que verá el cliente en el PDF. Si la dejas vacía, se mostrarán los ítems del carrito.")

                _desc_editadas = {}
                for _cat in _cats_ep:
                    with st.container(border=True):
                        col_cat, col_estado, col_limpiar_uno = st.columns([3, 1, 1])
                        with col_cat:
                            st.markdown(f"**{_cat}**")
                        with col_estado:
                            if _cat in _desc_actuales and _desc_actuales[_cat].strip():
                                st.markdown("🟣 Personalizada")
                            else:
                                st.markdown("⬜ Por defecto")
                        with col_limpiar_uno:
                            if _cat in _desc_actuales and _desc_actuales[_cat].strip():
                                if st.button("🗑️ Limpiar", key=f"pdf_limpiar_{_num_edit}_{_cat}",
                                             use_container_width=True):
                                    _dict_actualizado = {k: v for k, v in _desc_actuales.items() if k != _cat}
                                    guardar_descripciones_por_ep(_num_edit, _dict_actualizado)
                                    # Actualizar directo en session_state — evita CDN cache de Storage
                                    st.session_state[f"_desc_cache_{_num_edit}"] = _dict_actualizado
                                    # Limpiar el widget del text_area
                                    _key_widget = f"pdf_edit_desc_{_num_edit}_{_cat}"
                                    if _key_widget in st.session_state:
                                        del st.session_state[_key_widget]
                                    st.rerun()

                        _val_actual = _desc_actuales.get(_cat, '')
                        _nueva = st.text_area(
                            f"Descripción para {_cat}",
                            value=_val_actual,
                            height=80,
                            placeholder=f"Ej: Incluye todos los elementos de {_cat.lower()}...",
                            key=f"pdf_edit_desc_{_num_edit}_{_cat}",
                            label_visibility="collapsed"
                        )
                        _desc_editadas[_cat] = _nueva

                st.markdown("")
                col_guardar, col_limpiar = st.columns([2, 1])
                with col_guardar:
                    if st.button("💾 Guardar todas las descripciones", type="primary",
                                 use_container_width=True, key="pdf_edit_guardar_todo"):
                        # Solo guardar categorías con descripción no vacía
                        _dict_final = {k: v.strip() for k, v in _desc_editadas.items() if v.strip()}
                        if guardar_descripciones_por_ep(_num_edit, _dict_final):
                            st.session_state[f"_desc_cache_{_num_edit}"] = _dict_final
                            st.success("✅ Descripciones guardadas. Se usarán al generar el PDF cliente.")
                            st.session_state.pdf_edit_cotizacion = None
                            st.session_state.pdf_edit_numero = None
                            st.rerun()

                with col_limpiar:
                    if st.button("🗑️ Limpiar todas", use_container_width=True,
                                 key="pdf_edit_limpiar_todo"):
                        if guardar_descripciones_por_ep(_num_edit, {}):
                            st.session_state[f"_desc_cache_{_num_edit}"] = {}
                            # Limpiar todos los widgets de text_area
                            for _c in _cats_ep:
                                _kw = f"pdf_edit_desc_{_num_edit}_{_c}"
                                if _kw in st.session_state:
                                    del st.session_state[_kw]
                            st.success("✅ Descripciones eliminadas.")
                            st.session_state.pdf_edit_cotizacion = None
                            st.session_state.pdf_edit_numero = None
                            st.rerun()
        else:
            st.info("🔍 Ingresa el número EP y presiona Buscar para editar las descripciones de una cotización.")

# =========================================================
# TAB 7 - RANKING EJECUTIVOS (visible para todos)
# =========================================================
if tab7 is not None:
    with tab7:
        st.markdown("""
        <style>
        .hdr7 {
            background: linear-gradient(135deg, #78350f 0%, #d97706 100%);
            border-radius: 14px; padding: 24px 28px; margin-bottom: 24px;
            display: flex; align-items: center; gap: 16px;
        }
        .hdr7 h2 { color: #ffffff !important; margin: 0; font-size: 1.5rem; font-weight: 700; }
        .hdr7 p  { color: rgba(255,255,255,0.75) !important; margin: 6px 0 0; font-size: 0.88rem; }
        .rank-card {
            background: white; border-radius: 14px; padding: 20px 24px;
            border: 1px solid #e2e8f0; margin-bottom: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        }
        .rank-1 { border-left: 5px solid #f59e0b; }
        .rank-2 { border-left: 5px solid #94a3b8; }
        .rank-3 { border-left: 5px solid #cd7c3a; }
        .rank-other { border-left: 5px solid #e2e8f0; }
        .rank-medal { font-size: 2rem; min-width: 2.5rem; }
        .rank-score-bar {
            height: 8px; border-radius: 4px;
            background: linear-gradient(90deg, #f59e0b, #d97706);
            margin-top: 6px;
        }
        </style>
        <div class="hdr7">
          <span style="font-size:2.4rem">🏆</span>
          <div>
            <h2>Ranking de Ejecutivos</h2>
            <p>Desempeño del equipo de ventas — este mes.</p>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Cargar datos
        with st.spinner("Cargando ranking..."):
            _ranking = cargar_ranking_ejecutivos(periodo='mes')

        if not _ranking:
            st.info("No hay cotizaciones registradas este mes.")
        else:
            from datetime import datetime as _dt
            _mes_actual = _dt.now().strftime("%B %Y").capitalize()
            st.markdown(f"#### 📅 {_mes_actual} — {len(_ranking)} ejecutivo{'s' if len(_ranking) != 1 else ''}")

            # Métricas globales del mes
            _total_mes     = sum(a['total_generado'] for a in _ranking)
            _total_presup  = sum(a['total_presupuestos'] for a in _ranking)
            _total_autori  = sum(a['autorizados'] for a in _ranking)

            col_g1, col_g2, col_g3 = st.columns(3)
            with col_g1:
                st.metric("💰 Total mes", f"${_total_mes:,.0f}".replace(",","."))
            with col_g2:
                st.metric("📋 Presupuestos", _total_presup)
            with col_g3:
                pct_g = round((_total_autori / _total_presup) * 100) if _total_presup else 0
                st.metric("🟢 % Autorizados", f"{pct_g}%")

            st.markdown("---")

            # Cards por ejecutivo
            _medallas = {1: "🥇", 2: "🥈", 3: "🥉"}
            _clases   = {1: "rank-1", 2: "rank-2", 3: "rank-3"}

            for i, ej in enumerate(_ranking, 1):
                medalla   = _medallas.get(i, f"#{i}")
                cls       = _clases.get(i, "rank-other")
                score      = ej["score"]
                total_fmt  = "${:,.0f}".format(ej['total_generado']).replace(",", ".")
                prom_fmt   = "${:,.0f}".format(ej['promedio']).replace(",", ".")
                color_pct  = "#16a34a" if ej['pct_autorizado'] >= 50 else "#dc2626"
                bar_width  = score  # score ya es sobre 100

                st.markdown(f"""
                <div class="rank-card {cls}">
                  <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
                    <span class="rank-medal">{medalla}</span>
                    <div style="flex:1;min-width:200px;">
                      <div style="font-size:1.1rem;font-weight:700;color:#1e293b;">{ej['nombre']}</div>
                      <div class="rank-score-bar" style="width:{bar_width}%"></div>
                      <div style="font-size:0.75rem;color:#64748b;margin-top:2px;">Score {score}/100</div>
                    </div>
                    <div style="display:flex;gap:24px;flex-wrap:wrap;">
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{ej['total_presupuestos']}</div>
                        <div style="font-size:0.72rem;color:#64748b;">Presupuestos</div>
                      </div>
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{total_fmt}</div>
                        <div style="font-size:0.72rem;color:#64748b;">Total generado</div>
                      </div>
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{prom_fmt}</div>
                        <div style="font-size:0.72rem;color:#64748b;">Promedio / cot.</div>
                      </div>
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:{color_pct};">{ej['pct_autorizado']}%</div>
                        <div style="font-size:0.72rem;color:#64748b;">Autorizados</div>
                      </div>
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{ej['autorizados']}</div>
                        <div style="font-size:0.72rem;color:#64748b;">🟢 Autor.</div>
                      </div>
                      <div style="text-align:center;">
                        <div style="font-size:1.3rem;font-weight:800;color:#0f172a;">{ej['borradores']}</div>
                        <div style="font-size:0.72rem;color:#64748b;">🟡 Borrad.</div>
                      </div>
                    </div>
                  </div>
                </div>
                """, unsafe_allow_html=True)

            st.caption("Score = 60% total generado + 25% % autorizados + 15% cantidad de presupuestos")

