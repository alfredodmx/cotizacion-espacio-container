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

st.set_page_config(layout="wide", page_title="Cotizador PRO", page_icon="📊")

# =========================================================
# CSS PERSONALIZADO - DISEÑO PREMIUM
# =========================================================
st.markdown("""
<style>
    /* IMPORTAR FUENTES PREMIUM */
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');
    
    /* ESTILOS GLOBALES */
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    /* =========================================================
       HEADER CON EFECTO GLASSMORPHISM
    ========================================================= */
    .header-container {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 1rem 2rem;
        margin-bottom: 2rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }
    
    .gradient-title {
        font-size: 2.8rem !important;
        font-weight: 800;
        background: linear-gradient(135deg, #3b82f6, #8b5cf6, #ec4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.2;
        letter-spacing: -0.02em;
    }
    
    /* =========================================================
       TARJETAS DE MÉTRICAS CON EFECTO 3D
    ========================================================= */
    .metric-card {
        background: linear-gradient(135deg, #ffffff, #f8fafc);
        border-radius: 24px;
        padding: 1.5rem;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 
                    0 8px 10px -6px rgba(0, 0, 0, 0.02),
                    inset 0 1px 0 rgba(255, 255, 255, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1rem;
        height: 100%;
        display: flex;
        flex-direction: column;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, #8b5cf6);
        border-radius: 24px 24px 0 0;
    }
    
    .metric-card:hover {
        transform: translateY(-4px) scale(1.02);
        box-shadow: 0 20px 30px -10px rgba(59, 130, 246, 0.2),
                    0 8px 10px -6px rgba(0, 0, 0, 0.1);
    }
    
    .metric-title {
        color: #64748b;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        color: #0f172a;
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    
    .metric-change {
        color: #10b981;
        font-size: 0.85rem;
        font-weight: 500;
        margin-top: auto;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }
    
    /* TARJETA ESPECIAL PARA TOTAL CON IVA */
    .metric-card-total {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border-radius: 24px;
        padding: 1.5rem;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2), 
                    0 8px 10px -6px rgba(0, 0, 0, 0.1),
                    inset 0 1px 0 rgba(255, 255, 255, 0.1);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1rem;
        width: 100%;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card-total::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #60a5fa, #c084fc);
    }
    
    .metric-card-total:hover {
        transform: translateY(-4px);
        box-shadow: 0 25px 30px -10px rgba(59, 130, 246, 0.3);
    }
    
    .metric-card-total .metric-title {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-card-total .metric-value {
        color: white;
        font-size: 2.4rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    
    .metric-card-total .metric-change {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* TARJETA ESPECIAL PARA UTILIDAD */
    .metric-card-utilidad {
        background: linear-gradient(135deg, #10b981, #059669);
        border-radius: 24px;
        padding: 1.5rem;
        box-shadow: 0 20px 25px -5px rgba(16, 185, 129, 0.2), 
                    0 8px 10px -6px rgba(0, 0, 0, 0.1),
                    inset 0 1px 0 rgba(255, 255, 255, 0.2);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        margin-bottom: 1rem;
        width: 100%;
        position: relative;
        overflow: hidden;
    }
    
    .metric-card-utilidad::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 4px;
        background: linear-gradient(90deg, #34d399, #fbbf24);
    }
    
    .metric-card-utilidad:hover {
        transform: translateY(-4px);
        box-shadow: 0 25px 30px -10px rgba(16, 185, 129, 0.4);
    }
    
    .metric-card-utilidad .metric-title {
        color: rgba(255, 255, 255, 0.8);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
    }
    
    .metric-card-utilidad .metric-value {
        color: white;
        font-size: 2.4rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }
    
    .metric-card-utilidad .metric-change {
        color: rgba(255, 255, 255, 0.8);
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* =========================================================
       CONTENEDORES CON EFECTO GLASS
    ========================================================= */
    div[data-testid="stContainer"] {
        background: rgba(255, 255, 255, 0.7) !important;
        backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 24px !important;
        padding: 1.5rem !important;
        margin-bottom: 1.5rem !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.05) !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="stContainer"]:hover {
        box-shadow: 0 12px 40px rgba(59, 130, 246, 0.1) !important;
        border-color: rgba(59, 130, 246, 0.3) !important;
    }
    
    /* =========================================================
       INPUTS Y SELECTORES PREMIUM
    ========================================================= */
    .stTextInput input, .stSelectbox select, .stDateInput input {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background: rgba(255, 255, 255, 0.9) !important;
        border: 1px solid rgba(203, 213, 225, 0.5) !important;
        border-radius: 16px !important;
        padding: 0.75rem 1rem !important;
        font-size: 0.95rem !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02) !important;
    }
    
    .stTextInput input:focus, .stSelectbox select:focus, .stDateInput input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.1) !important;
        outline: none !important;
    }
    
    /* ETIQUETAS DE INPUT */
    .stTextInput label, .stSelectbox label, .stDateInput label {
        font-size: 0.8rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.03em !important;
        color: #64748b !important;
        margin-bottom: 0.25rem !important;
    }
    
    /* =========================================================
       BOTONES CON EFECTO 3D
    ========================================================= */
    .stButton button {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        background: white !important;
        color: #0f172a !important;
        border: 1px solid rgba(203, 213, 225, 0.5) !important;
        border-radius: 16px !important;
        padding: 0.6rem 1.2rem !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05) !important;
    }
    
    .stButton button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(59, 130, 246, 0.2) !important;
    }
    
    /* BOTÓN PRIMARIO (DOWNLOAD) */
    .stDownloadButton button {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6) !important;
        color: white !important;
        border: none !important;
        font-weight: 700 !important;
        padding: 0.75rem 1.5rem !important;
        border-radius: 16px !important;
        box-shadow: 0 10px 20px -5px rgba(59, 130, 246, 0.4) !important;
        position: relative;
        overflow: hidden;
    }
    
    .stDownloadButton button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        transition: left 0.5s ease;
    }
    
    .stDownloadButton button:hover::before {
        left: 100%;
    }
    
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 15px 25px -5px rgba(59, 130, 246, 0.5) !important;
    }
    
    /* =========================================================
       TABS MODERNOS
    ========================================================= */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem !important;
        border-bottom: 1px solid rgba(203, 213, 225, 0.3) !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        color: #64748b !important;
        padding: 0.75rem 0 !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.02em;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #0f172a !important;
        border-bottom-color: rgba(59, 130, 246, 0.3) !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: #3b82f6 !important;
        border-bottom-color: #3b82f6 !important;
        font-weight: 700 !important;
    }
    
    /* =========================================================
       EXPANDER PREMIUM
    ========================================================= */
    .streamlit-expanderHeader {
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
        color: #0f172a !important;
        background: rgba(255, 255, 255, 0.5) !important;
        backdrop-filter: blur(5px) !important;
        border-radius: 16px !important;
        border: 1px solid rgba(203, 213, 225, 0.3) !important;
        padding: 0.75rem 1rem !important;
        transition: all 0.2s ease !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: rgba(255, 255, 255, 0.8) !important;
        border-color: rgba(59, 130, 246, 0.3) !important;
    }
    
    /* =========================================================
       PROGRESS BAR
    ========================================================= */
    .stProgress > div > div {
        background: linear-gradient(90deg, #3b82f6, #8b5cf6) !important;
        border-radius: 8px !important;
        height: 8px !important;
    }
    
    /* =========================================================
       SEPARADORES
    ========================================================= */
    hr {
        margin: 2rem 0 !important;
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, rgba(59, 130, 246, 0.2), transparent) !important;
    }
    
    /* =========================================================
       MODO OSCURO PREMIUM
    ========================================================= */
    @media (prefers-color-scheme: dark) {
        .metric-card {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            border-color: rgba(255, 255, 255, 0.05);
        }
        
        .metric-title {
            color: #94a3b8;
        }
        
        .metric-value {
            color: #f1f5f9;
        }
        
        div[data-testid="stContainer"] {
            background: rgba(15, 23, 42, 0.7) !important;
            border-color: rgba(255, 255, 255, 0.05) !important;
        }
        
        .stTextInput input, .stSelectbox select, .stDateInput input {
            background: rgba(15, 23, 42, 0.9) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
            color: #f1f5f9 !important;
        }
        
        .stTextInput label, .stSelectbox label, .stDateInput label {
            color: #94a3b8 !important;
        }
        
        .stButton button {
            background: #1e293b !important;
            color: #f1f5f9 !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
        }
        
        .stButton button:hover {
            border-color: #3b82f6 !important;
            color: #60a5fa !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            color: #94a3b8;
        }
        
        .stTabs [data-baseweb="tab"]:hover {
            color: #f1f5f9;
        }
        
        .streamlit-expanderHeader {
            color: #f1f5f9 !important;
            background: rgba(15, 23, 42, 0.5) !important;
            border-color: rgba(255, 255, 255, 0.05) !important;
        }
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER CON DISEÑO PREMIUM
# =========================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)
col1, col2 = st.columns([4, 1])

with col1:
    st.markdown('<p class="gradient-title">Cotizador PRO</p>', unsafe_allow_html=True)
    st.markdown('<p style="color: #64748b; margin-top: -0.5rem;">Sistema profesional de cotizaciones</p>', unsafe_allow_html=True)

with col2:
    try:
        st.image("logo2.png", width=200)
    except:
        st.markdown('<div style="background: linear-gradient(135deg, #3b82f6, #8b5cf6); width: 120px; height: 120px; border-radius: 60px; display: flex; align-items: center; justify-content: center; margin-left: auto;"><span style="color: white; font-size: 2rem; font-weight: bold;">CP</span></div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# INICIALIZAR TODAS LAS VARIABLES DE SESSION_STATE
# =========================================================

# Inicializar variables del carrito
if 'carrito' not in st.session_state:
    st.session_state.carrito = []

# Inicializar variable de margen
if 'margen' not in st.session_state:
    st.session_state.margen = 0.0  # Margen por defecto 0%
    
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

def actualizar_telefono_asesor():
    """Callback para actualizar el teléfono del asesor"""
    if 'telefono_asesor_input' in st.session_state:
        valor_actual = st.session_state.telefono_asesor_input
        raw = re.sub(r'[^0-9]', '', valor_actual)
        if len(raw) > 9:
            raw = raw[:9]
        st.session_state.telefono_asesor_raw = raw

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
# FUNCIÓN PARA CALCULAR UTILIDAD
# =========================================================

def calcular_utilidad(carrito, margen):
    """
    Calcula la utilidad generada por el margen
    Utilidad = Total con margen - Total sin margen
    """
    if margen <= 0:
        return 0
    
    # Calcular total sin margen
    total_sin_margen = sum(item["Cantidad"] * item["Precio Unitario"] for item in carrito)
    total_sin_margen_iva = total_sin_margen * 1.19
    
    # Calcular total con margen
    subtotal_con_margen, _, total_con_margen = calcular_totales_con_margen(carrito, margen)
    
    # Utilidad es la diferencia
    utilidad = total_con_margen - total_sin_margen_iva
    
    return utilidad

# =========================================================
# FUNCIÓN PARA OFUSCAR TEXTOS CON X (MITAD DEL TEXTO)
# =========================================================

def ofuscar_texto(texto):
    """
    Reemplaza la mitad del texto con 'X'
    Ejemplo: "Canal Cielo 20X 25" -> "Canal Cielo 20X XXXXX"
    """
    if not texto or len(texto) <= 3:
        return texto
    
    # Calcular cuántos caracteres dejar visibles (la mitad)
    largo = len(texto)
    chars_visibles = largo // 2
    
    # Dejar la primera mitad visible, el resto con X
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
    
    # Convertir a string y reemplazar cada dígito con X
    num_str = str(numero)
    return "X" * len(num_str)

def ofuscar_precio(precio):
    """
    Ofusca un precio formateado
    Ejemplo: $1.000 -> $XXXX
    """
    if not precio:
        return ""
    
    # Extraer el símbolo $ y los puntos, ofuscar los números
    if precio.startswith('$'):
        # Mantener el signo $, ofuscar el resto
        numeros = re.sub(r'[^0-9]', '', precio)
        return "$" + "X" * len(numeros)
    else:
        return "X" * len(str(precio))

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

# =========================================================
# FUNCIÓN BASE PARA GENERAR PDF (CON NOTAS DINÁMICAS)
# =========================================================

def generar_pdf_base(carrito_df, subtotal, iva, total, datos_cliente,
                     fecha_inicio, fecha_termino, dias_validez,
                     datos_asesor, ofuscar=False, margen=0):

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
    
    # Estilo para las notas (más pequeño)
    styles.add(ParagraphStyle(
        name='NotasEstilo',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        leftIndent=0,
        alignment=0,  # 0 = izquierda
        textColor=colors.grey,
        spaceAfter=2
    ))
    
    # Estilo para los totales
    styles.add(ParagraphStyle(
        name='TotalLabel',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,  # 2 = derecha
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalValue',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        alignment=2,  # 2 = derecha
        fontName='Helvetica',
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='TotalBold',
        parent=styles['Normal'],
        fontSize=12,
        leading=16,
        alignment=2,  # 2 = derecha
        fontName='Helvetica-Bold',
        spaceAfter=2,
        textColor=colors.black
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
        # Determinar valores según si ofuscamos o no
        if ofuscar:
            # Para cliente: ofuscar textos y números
            categoria = ofuscar_texto(row["Categoria"])
            item = ofuscar_texto(row["Item"])
            cantidad = ofuscar_numero(row["Cantidad"])
            precio_unitario = ofuscar_precio(formato_clp(row["Precio Unitario"]))
            subtotal_item = ofuscar_precio(formato_clp(row["Subtotal"]))
        else:
            # Normal: mostrar todo
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
    
    # Alternar colores de filas
    for i in range(1, len(data)):
        if i % 2 == 0:
            tabla_productos.setStyle(TableStyle([
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))
            ]))

    elements.append(tabla_productos)
    elements.append(Spacer(1, 20))
    
    # =========================================================
    # BLOQUES: NOTAS A LA IZQUIERDA, TOTALES A LA DERECHA
    # =========================================================
    
    # Crear tabla de dos columnas para los bloques
    ancho_bloque = (doc.width - 20) / 2
    
    # Determinar el texto del punto 2 según el margen
    if margen > 0:
        texto_transporte = "2.- Transporte y bases de apoyo <b>incluidos</b>."
    else:
        texto_transporte = "2.- Transporte y bases de apoyo <b>no incluidos</b>."
    
    # Preparar bloque de notas con texto dinámico
    notas_texto = f"""
    <b>NOTAS IMPORTANTES:</b><br/>
    1.- Valores incluyen IVA.<br/>
    {texto_transporte}<br/>
    3.- Formas de pago: transferencia - pago contado.<br/>
    4.- Proceso de pagos: 50% inicial - 25% obra - 25% entrega.
    """
    
    bloque_notas = Paragraph(notas_texto, styles['NotasEstilo'])
    
    # Preparar bloque de totales - SIN SEPARADOR SUPERIOR
    totales_data = [
        [Paragraph("Subtotal:", styles['TotalLabel']), Paragraph(formato_clp(subtotal), styles['TotalValue'])],
        [Paragraph("IVA (19%):", styles['TotalLabel']), Paragraph(formato_clp(iva), styles['TotalValue'])],
        [Paragraph("TOTAL:", styles['TotalBold']), Paragraph(formato_clp(total), styles['TotalBold'])]
    ]
    
    # Tabla de totales con separadores - SIN línea superior en la primera fila
    totales_tabla = Table(totales_data, colWidths=[100, 120])
    totales_tabla.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        # Línea después de Subtotal (fila 1)
        ('LINEABOVE', (1, 1), (1, 1), 1, colors.grey),
        # Línea después de IVA (fila 2)
        ('LINEABOVE', (1, 2), (1, 2), 2, colors.black),
    ]))
    
    # Crear la tabla de dos columnas
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
    return buffer

# =========================================================
# TAB 2 - DATOS CLIENTE / EJECUTIVO
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
                    st.session_state.margen = 0.0  # Resetear margen al cargar modelo
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

            precio_unitario_original = items_filtrados[
                items_filtrados["Item"] == item
            ]["P. Unitario real"].values[0]

            # Mostrar precios con margen aplicado
            precio_con_margen = aplicar_margen(precio_unitario_original, st.session_state.margen)
            subtotal_con_margen = precio_con_margen * cantidad

            st.caption(f"P. Unitario original: {formato_clp(precio_unitario_original)}")
            if st.session_state.margen > 0:
                st.caption(f"P. con margen ({st.session_state.margen}%): {formato_clp(precio_con_margen)}")
            st.caption(f"Subtotal con margen: {formato_clp(subtotal_con_margen)}")

            if st.button("Agregar", key="btn_agregar_manual", use_container_width=True):
                existe = False

                for producto in st.session_state.carrito:
                    if producto["Item"] == item:
                        producto["Cantidad"] += cantidad
                        # Mantenemos el precio original en el carrito
                        producto["Subtotal"] = producto["Cantidad"] * producto["Precio Unitario"]
                        existe = True
                        break

                if not existe:
                    st.session_state.carrito.append({
                        "Categoria": categoria_seleccionada,
                        "Item": item,
                        "Cantidad": cantidad,
                        "Precio Unitario": precio_unitario_original,  # Guardamos el precio original
                        "Subtotal": precio_unitario_original * cantidad  # Subtotal original
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

    # Título y control de margen en la MISMA LÍNEA
    col_titulo, col_margen_etq, col_margen_input = st.columns([4, 0.5, 0.8])

    with col_titulo:
        st.subheader("Resumen del Presupuesto")

    with col_margen_etq:
        st.markdown("**Margen (%)**")

    with col_margen_input:
        margen_input = st.number_input(
            "Margen", 
            min_value=0.0, 
            max_value=100.0, 
            value=st.session_state.margen,
            step=0.5,
            format="%.1f",
            key="margen_input_resumen",
            label_visibility="collapsed",
            help="Porcentaje de margen a aplicar sobre los precios"
        )
        
        # Actualizar el margen en session_state
        if margen_input != st.session_state.margen:
            st.session_state.margen = margen_input
            st.rerun()

    if st.session_state.carrito:
        # Crear DataFrame para mostrar
        carrito_df = pd.DataFrame(st.session_state.carrito)
        
        # Calcular totales con margen
        subtotal_con_margen, iva_con_margen, total_con_margen = calcular_totales_con_margen(
            st.session_state.carrito, st.session_state.margen
        )
        
        # Calcular utilidad
        utilidad = calcular_utilidad(st.session_state.carrito, st.session_state.margen)
        
        # Aplicar margen a los precios para la visualización
        carrito_df_con_margen = carrito_df.copy()
        carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(
            lambda x: aplicar_margen(x, st.session_state.margen)
        )
        carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]

        # ---------------- TABLA CON ELIMINACIÓN DIRECTA ----------------
        carrito_df_edit = carrito_df_con_margen.copy()
        carrito_df_edit["❌"] = False
        carrito_df_edit["Precio Unitario"] = carrito_df_edit["Precio Unitario"].apply(lambda x: formato_clp(x))
        carrito_df_edit["Subtotal"] = carrito_df_edit["Subtotal"].apply(lambda x: formato_clp(x))

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

        # ---------------- TOTALES CON MARGEN ----------------
        subtotal_general = carrito_df_con_margen["Subtotal"].sum()
        iva = subtotal_general * 0.19
        total = subtotal_general + iva

        # BOTONES DEBAJO DE LA TABLA - LIMPIAR A LA IZQUIERDA, PDFs A LA DERECHA
        col_btn_left, col_btn_center, col_btn_right = st.columns([1, 1, 1])

        with col_btn_left:
            if st.button("🧹 Limpiar Presupuesto", use_container_width=True):
                st.session_state.carrito = []
                st.session_state.margen = 0.0  # Resetear margen
                st.rerun()

        # =========================================================
        # PREPARAR DATOS COMUNES PARA AMBOS PDFs
        # =========================================================
        correo_para_pdf = st.session_state.get('correo_input', '')
        if not correo_para_pdf and 'correo_input' in locals():
            correo_para_pdf = correo

        rut_valido_para_pdf = True
        if st.session_state.rut_raw and len(st.session_state.rut_raw) >= 2:
            rut_valido_para_pdf = st.session_state.rut_valido

        if 'fecha_inicio' not in locals():
            fecha_inicio = st.session_state.get('fecha_inicio', datetime.now())
        if 'fecha_termino' not in locals():
            fecha_termino = st.session_state.get('fecha_termino', datetime.now() + timedelta(days=15))
        if 'dias_validez' not in locals():
            dias_validez = (fecha_termino - fecha_inicio).days

        # Construir datos para el PDF
        datos_cliente_pdf = {
            "Nombre": st.session_state.get('nombre_input', ''),
            "RUT": st.session_state.rut_display if st.session_state.rut_display else '',
            "Correo": st.session_state.get('correo_input', ''),
            "Teléfono": st.session_state.telefono_raw if st.session_state.telefono_raw else '',
            "Dirección": st.session_state.get('direccion_input', ''),
            "Observaciones": st.session_state.get('observaciones_input', '')
        }

        nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""

        datos_asesor_pdf = {
            "Nombre Ejecutivo": nombre_asesor_final,
            "Correo Ejecutivo": st.session_state.correo_asesor if st.session_state.correo_asesor else "",
            "Teléfono Ejecutivo": st.session_state.telefono_asesor if st.session_state.telefono_asesor else ""
        }

        # Crear DataFrame base con precios originales
        carrito_df_original = pd.DataFrame(st.session_state.carrito)

        # Aplicar margen a los precios (para ambos PDFs)
        carrito_df_con_margen_pdf = carrito_df_original.copy()
        carrito_df_con_margen_pdf["Precio Unitario"] = carrito_df_con_margen_pdf["Precio Unitario"].apply(
            lambda x: aplicar_margen(x, st.session_state.margen)
        )
        carrito_df_con_margen_pdf["Subtotal"] = carrito_df_con_margen_pdf["Cantidad"] * carrito_df_con_margen_pdf["Precio Unitario"]

        # Verificar validaciones antes de mostrar los botones
        if "@" not in correo_para_pdf:
            st.error("El correo debe contener '@' para generar el PDF.")
        elif dias_validez < 0:
            st.error("Fechas incorrectas.")
        elif not rut_valido_para_pdf and st.session_state.rut_raw:
            st.error("El RUT no es válido. Corrígelo antes de generar el PDF.")
        else:
            with col_btn_center:
                # PDF COMPLETO - CON MARGEN APLICADO PERO SIN OFUSCAR
                pdf_buffer_completo = generar_pdf_base(
                    carrito_df_con_margen_pdf,  # Usar el DataFrame con margen aplicado
                    subtotal_general,
                    iva,
                    total,
                    datos_cliente_pdf,
                    fecha_inicio,
                    fecha_termino,
                    dias_validez,
                    datos_asesor_pdf,
                    ofuscar=False,
                    margen=st.session_state.margen  # Pasar el margen para las notas
                )

                st.download_button(
                    label="📥 PDF Completo",
                    data=pdf_buffer_completo,
                    file_name="Presupuesto_Completo.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_completo"
                )

            with col_btn_right:
                # PDF PARA CLIENTE - CON MARGEN APLICADO Y OFUSCADO
                pdf_buffer_cliente = generar_pdf_base(
                    carrito_df_con_margen_pdf,  # Usar el mismo DataFrame con margen aplicado
                    subtotal_general,
                    iva,
                    total,
                    datos_cliente_pdf,
                    fecha_inicio,
                    fecha_termino,
                    dias_validez,
                    datos_asesor_pdf,
                    ofuscar=True,
                    margen=st.session_state.margen  # Pasar el margen para las notas
                )

                st.download_button(
                    label="🔒 PDF para Cliente",
                    data=pdf_buffer_cliente,
                    file_name="Presupuesto_Cliente.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_cliente"
                )

        st.markdown("### Totales")
        st.write("Subtotal:", formato_clp(subtotal_general))
        st.write("IVA (19%):", formato_clp(iva))
        st.write("TOTAL:", formato_clp(total))
        if st.session_state.margen > 0:
            st.caption(f"*Precios calculados con margen del {st.session_state.margen}%")

        # =========================================================
        # TARJETAS DE MÉTRICAS (DESPUÉS DE LOS TOTALES)
        # =========================================================
        st.markdown("### Resumen Final")
        
        # Calcular totales para las métricas
        with st.container():
            # Primera fila con 4 tarjetas
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            
            with col_m1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">TOTAL ITEMS</div>
                    <div class="metric-value">{len(st.session_state.carrito)}</div>
                    <div class="metric-change">En presupuesto</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_m2:
                total_productos = sum(item["Cantidad"] for item in st.session_state.carrito)
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">PRODUCTOS</div>
                    <div class="metric-value">{total_productos}</div>
                    <div class="metric-change">Unidades</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_m3:
                categorias_unicas = len(set(item["Categoria"] for item in st.session_state.carrito))
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">CATEGORÍAS</div>
                    <div class="metric-value">{categorias_unicas}</div>
                    <div class="metric-change">Diferentes</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_m4:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-title">SIN IVA</div>
                    <div class="metric-value">{formato_clp(subtotal_general)}</div>
                    <div class="metric-change">Subtotal {f'({st.session_state.margen}% margen)' if st.session_state.margen > 0 else ''}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Segunda fila con tarjetas de TOTAL CON IVA y UTILIDAD
            st.markdown("---")
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f"""
                <div class="metric-card-total">
                    <div class="metric-title">TOTAL CON IVA</div>
                    <div class="metric-value">{formato_clp(total)}</div>
                    <div class="metric-change">IVA incluido (19%) {f'• Margen {st.session_state.margen}%' if st.session_state.margen > 0 else ''}</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Tercera fila con tarjeta de UTILIDAD (solo si hay margen)
            if st.session_state.margen > 0:
                col_u1, col_u2, col_u3 = st.columns([1, 2, 1])
                with col_u2:
                    st.markdown(f"""
                    <div class="metric-card-utilidad">
                        <div class="metric-title">UTILIDAD</div>
                        <div class="metric-value">{formato_clp(utilidad)}</div>
                        <div class="metric-change">Ganancia por margen del {st.session_state.margen}%</div>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.info("👈 Agrega productos al presupuesto usando los controles de la izquierda")