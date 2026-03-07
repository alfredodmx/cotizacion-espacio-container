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
# INICIALIZAR VARIABLES DE SESIÓN
# =========================================================
if 'modo_admin' not in st.session_state:
    st.session_state.modo_admin = False
    
if 'mostrar_login' not in st.session_state:
    st.session_state.mostrar_login = False

# Clave para acceso administrativo
CLAVE_ADMIN = "admin2024"

# =========================================================
# CSS PERSONALIZADO - DISEÑO PREMIUM
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
       VARIABLES MODO CLARO (PASTEL SUAVE) - POR DEFECTO
    ========================================================= */
    :root, .stApp {
        --bg-primary: #f8fafc;
        --bg-secondary: #ffffff;
        --bg-card: #ffffff;
        --bg-card-gradient: linear-gradient(135deg, #ffffff, #f8fafc);
        --text-primary: #1e293b;
        --text-secondary: #475569;
        --text-tertiary: #64748b;
        --accent-primary: #3b82f6;
        --accent-secondary: #8b5cf6;
        --accent-glow: rgba(59, 130, 246, 0.1);
        --border-light: #e2e8f0;
        --border-medium: #cbd5e1;
        --shadow-sm: 0 2px 4px rgba(0, 0, 0, 0.02), 0 1px 2px rgba(0, 0, 0, 0.01);
        --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.03), 0 2px 4px -1px rgba(0, 0, 0, 0.02);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.03), 0 4px 6px -2px rgba(0, 0, 0, 0.01);
        --shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.03), 0 10px 10px -5px rgba(0, 0, 0, 0.01);
        --glass-bg: rgba(255, 255, 255, 0.8);
        --glass-border: rgba(255, 255, 255, 0.9);
        --input-bg: #ffffff;
        --input-border: #e2e8f0;
        --input-text: #1e293b;
        --button-bg: #ffffff;
        --button-border: #e2e8f0;
        --button-text: #1e293b;
        --button-hover-bg: #f8fafc;
        --button-hover-border: #3b82f6;
        --metric-card-bg: linear-gradient(135deg, #ffffff, #f8fafc);
        --metric-value-1: #fbbf24;
        --metric-value-2: #f97316;
        --metric-value-3: #10b981;
        --metric-value-4: #f43f5e;
    }
    
    /* =========================================================
       VARIABLES MODO OSCURO (PROFESIONAL)
    ========================================================= */
    @media (prefers-color-scheme: dark) {
        :root, .stApp {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #1e293b;
            --bg-card-gradient: linear-gradient(135deg, #1e293b, #0f172a);
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-tertiary: #94a3b8;
            --accent-primary: #60a5fa;
            --accent-secondary: #c084fc;
            --accent-glow: rgba(96, 165, 250, 0.2);
            --border-light: #334155;
            --border-medium: #475569;
            --shadow-sm: 0 4px 6px -1px rgba(0, 0, 0, 0.2), 0 2px 4px -1px rgba(0, 0, 0, 0.1);
            --shadow-md: 0 10px 15px -3px rgba(0, 0, 0, 0.3), 0 4px 6px -2px rgba(0, 0, 0, 0.2);
            --shadow-lg: 0 20px 25px -5px rgba(0, 0, 0, 0.3), 0 10px 10px -5px rgba(0, 0, 0, 0.2);
            --shadow-xl: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            --glass-bg: rgba(30, 41, 59, 0.7);
            --glass-border: rgba(255, 255, 255, 0.05);
            --input-bg: #1e293b;
            --input-border: #334155;
            --input-text: #f8fafc;
            --button-bg: #1e293b;
            --button-border: #334155;
            --button-text: #f8fafc;
            --button-hover-bg: #334155;
            --button-hover-border: #60a5fa;
            --metric-card-bg: linear-gradient(135deg, #1e293b, #0f172a);
            --metric-value-1: #fbbf24;
            --metric-value-2: #f97316;
            --metric-value-3: #10b981;
            --metric-value-4: #f43f5e;
        }
    }
    
    /* =========================================================
       HEADER GLASSMORPHISM - SIN LÍNEA SUPERIOR
    ========================================================= */
    .header-container {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 28px;
        padding: 1.25rem 2rem;
        margin-bottom: 1.5rem;
        border: 1px solid var(--glass-border);
        box-shadow: var(--shadow-lg);
        position: relative;
        overflow: hidden;
        transition: all 0.3s ease;
    }
    
    /* ELIMINADA LA LÍNEA SUPERIOR GRIS */
    .header-container::before {
        display: none !important;
        content: none !important;
    }
    
    .header-container::after {
        content: '';
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, var(--accent-glow) 0%, transparent 70%);
        opacity: 0.2;
        z-index: -1;
    }
    
    .title-container {
        position: relative;
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
        display: inline-block;
    }
    
    .sub-title {
        color: var(--text-secondary);
        font-size: 0.85rem;
        font-weight: 400;
        margin-top: 0.1rem;
        letter-spacing: 0.3px;
    }
    
    /* =========================================================
       LOGO CON EFECTO GLOSSY
    ========================================================= */
    .logo-container {
        display: flex;
        justify-content: flex-end;
        align-items: center;
        height: 100%;
    }
    
    .logo-glossy {
        max-width: 140px;
        max-height: 50px;
        object-fit: contain;
        filter: drop-shadow(0 4px 6px rgba(0, 0, 0, 0.05));
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }
    
    .logo-glossy:hover {
        transform: scale(1.03) translateY(-2px);
        filter: drop-shadow(0 8px 12px var(--accent-glow));
    }
    
    /* =========================================================
       BOTÓN ADMINISTRATIVO GLOSSY
    ========================================================= */
    .access-container {
        display: flex;
        justify-content: flex-start;
        align-items: center;
        margin-top: 0.3rem;
    }
    
    /* Eliminar recuadro del popover */
    div[data-testid="stPopover"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        min-width: auto !important;
    }
    
    /* Botón administrativo - PASTEL EN MODO CLARO */
    .stPopover button {
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        border-radius: 40px !important;
        padding: 0.5rem 1.4rem !important;
        font-size: 0.9rem !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 10px -4px var(--accent-glow) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        backdrop-filter: blur(5px);
        letter-spacing: 0.3px;
        cursor: pointer;
        margin: 0 !important;
        position: relative;
        overflow: hidden;
    }
    
    .stPopover button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
        transition: left 0.5s ease;
    }
    
    .stPopover button:hover::before {
        left: 100%;
    }
    
    .stPopover button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 16px -6px var(--accent-glow) !important;
    }
    
    /* Indicador modo administrativo */
    .modo-admin-indicator {
        background: linear-gradient(135deg, #10b981, #059669);
        color: white;
        padding: 0.5rem 1.4rem;
        border-radius: 40px;
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: 0 4px 10px -4px rgba(16, 185, 129, 0.3);
        border: 1px solid rgba(255, 255, 255, 0.2);
        backdrop-filter: blur(5px);
        letter-spacing: 0.3px;
    }
    
    /* Botón cerrar sesión */
    .cerrar-sesion-button {
        background: rgba(239, 68, 68, 0.1) !important;
        color: #ef4444 !important;
        border: 1px solid rgba(239, 68, 68, 0.2) !important;
        font-weight: 500 !important;
        border-radius: 40px !important;
        padding: 0.5rem 1.4rem !important;
        font-size: 0.9rem !important;
        transition: all 0.3s ease !important;
        margin-left: 0.8rem !important;
    }
    
    .cerrar-sesion-button:hover {
        background: rgba(239, 68, 68, 0.15) !important;
        border-color: #ef4444 !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 10px -4px rgba(239, 68, 68, 0.3);
    }
    
    /* =========================================================
       MODAL DE LOGIN PREMIUM
    ========================================================= */
    div[data-testid="stPopoverContent"] {
        background: var(--bg-secondary) !important;
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-radius: 24px !important;
        padding: 1.5rem !important;
        box-shadow: var(--shadow-xl) !important;
        border: 1px solid var(--border-light) !important;
        min-width: 320px !important;
        margin-top: 0.6rem !important;
    }
    
    /* =========================================================
       TABS PROFESIONALES
    ========================================================= */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem !important;
        border-bottom: 1px solid var(--border-light) !important;
        padding: 0 0.5rem !important;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.9rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        padding: 0.6rem 0 !important;
        background: transparent !important;
        border-bottom: 2px solid transparent !important;
        transition: all 0.2s ease !important;
        letter-spacing: 0.3px;
        text-transform: uppercase;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--text-primary) !important;
        border-bottom-color: var(--accent-glow) !important;
    }
    
    .stTabs [aria-selected="true"] {
        color: var(--accent-primary) !important;
        border-bottom-color: var(--accent-primary) !important;
        font-weight: 600 !important;
    }
    
    /* =========================================================
       TARJETAS ULTRA PREMIUM - PASTEL EN MODO CLARO
    ========================================================= */
    .premium-card {
        background: var(--bg-secondary);
        border-radius: 20px;
        padding: 1.25rem;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-light);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .premium-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .premium-card:hover {
        transform: translateY(-2px);
        box-shadow: var(--shadow-lg);
        border-color: var(--border-medium);
    }
    
    .premium-card:hover::before {
        opacity: 0.5;
    }
    
    .premium-card-title {
        color: var(--text-tertiary);
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.8rem;
    }
    
    /* Contenedores de Streamlit - FORZADOS A USAR VARIABLES */
    div[data-testid="stContainer"] {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-light) !important;
        border-radius: 20px !important;
        padding: 1.25rem !important;
        margin-bottom: 1.25rem !important;
        box-shadow: var(--shadow-md) !important;
        transition: all 0.3s ease !important;
    }
    
    div[data-testid="stContainer"]:hover {
        border-color: var(--accent-glow) !important;
        box-shadow: var(--shadow-lg) !important;
    }
    
    /* =========================================================
       INPUTS Y SELECTORES - FORZADOS A USAR VARIABLES
    ========================================================= */
    .stTextInput input, 
    .stSelectbox select, 
    .stDateInput input,
    .stTextInput input:focus,
    .stSelectbox select:focus,
    .stDateInput input:focus {
        font-family: 'Inter', sans-serif !important;
        background: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 14px !important;
        padding: 0.6rem 1rem !important;
        font-size: 0.9rem !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
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
        font-size: 0.7rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.3px !important;
        color: var(--text-tertiary) !important;
        margin-bottom: 0.2rem !important;
    }
    
    /* =========================================================
       BOTONES - FORZADOS A USAR VARIABLES
    ========================================================= */
    .stButton button {
        font-family: 'Inter', sans-serif !important;
        background: var(--button-bg) !important;
        color: var(--button-text) !important;
        border: 1px solid var(--button-border) !important;
        border-radius: 12px !important;
        padding: 0.5rem 1.2rem !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    .stButton button:hover {
        background: var(--button-hover-bg) !important;
        border-color: var(--button-hover-border) !important;
        color: var(--accent-primary) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-md) !important;
    }
    
    /* Botón de descarga */
    .stDownloadButton button {
        background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.6rem 1.5rem !important;
        border-radius: 14px !important;
        box-shadow: 0 6px 12px -6px var(--accent-glow) !important;
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
        transform: translateY(-2px);
        box-shadow: 0 10px 18px -8px var(--accent-glow);
    }
    
    /* =========================================================
       TARJETAS DE MÉTRICAS PRINCIPALES
    ========================================================= */
    .metric-card {
        background: var(--metric-card-bg);
        border-radius: 20px;
        padding: 1.25rem;
        box-shadow: var(--shadow-md);
        border: 1px solid var(--border-light);
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
        height: 100%;
    }
    
    .metric-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
        opacity: 0.3;
        transition: opacity 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: var(--shadow-lg);
        border-color: var(--border-medium);
    }
    
    .metric-card:hover::before {
        opacity: 0.8;
    }
    
    .metric-title {
        color: var(--text-tertiary);
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.3rem;
    }
    
    .metric-value {
        font-size: 2.2rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.2rem;
        letter-spacing: -0.02em;
    }
    
    .metric-change {
        font-weight: 500;
        font-size: 0.75rem;
    }
    
    /* =========================================================
       TARJETAS ESPECIALES - MISMA PROPORCIÓN
    ========================================================= */
    .metric-card-special {
        border-radius: 24px;
        padding: 1.75rem;
        box-shadow: 0 12px 20px -10px rgba(0, 0, 0, 0.15);
        transition: all 0.3s ease;
        border: 1px solid rgba(255, 255, 255, 0.1);
        height: 100%;
        display: flex;
        flex-direction: column;
    }
    
    .metric-card-special:hover {
        transform: translateY(-4px);
        box-shadow: 0 16px 24px -12px rgba(0, 0, 0, 0.2);
    }
    
    .metric-card-special .metric-title {
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    
    .metric-card-special .metric-value {
        color: white;
        font-size: 2.5rem;
        font-weight: 700;
        text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }
    
    .metric-card-special .metric-change {
        color: rgba(255, 255, 255, 0.8);
        font-weight: 500;
        font-size: 0.85rem;
        margin-top: auto;
    }
    
    /* Tarjeta TOTAL CON IVA */
    .metric-card-total {
        background: linear-gradient(135deg, #3b82f6, #8b5cf6);
    }
    
    /* Tarjeta COMISIONES */
    .metric-card-comisiones {
        background: linear-gradient(135deg, #f59e0b, #d97706);
    }
    
    .comision-detalle {
        color: rgba(255, 255, 255, 0.9);
        font-size: 0.9rem;
        font-weight: 500;
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.3rem;
        padding: 0.2rem 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    }
    
    .comision-detalle:last-child {
        border-bottom: none;
    }
    
    .comision-detalle span:first-child {
        opacity: 0.9;
    }
    
    .comision-detalle span:last-child {
        font-weight: 600;
    }
    
    /* Tarjeta UTILIDAD REAL */
    .metric-card-utilidad {
        background: linear-gradient(135deg, #10b981, #059669);
    }
    
    /* =========================================================
       TABLA DE DATOS - CON FUNCIONALIDADES COMPLETAS
    ========================================================= */
    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border-light) !important;
        border-radius: 16px !important;
        overflow: hidden !important;
        box-shadow: var(--shadow-md) !important;
    }
    
    /* RESTAURAR FUNCIONALIDADES DE LA TABLA */
    div[data-testid="stDataFrame"] button,
    div[data-testid="stDataFrame"] [data-testid="stColumnHeader"],
    div[data-testid="stDataFrame"] svg {
        display: inline-flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
    }
    
    /* Asegurar que los iconos sean visibles */
    div[data-testid="stDataFrame"] svg {
        fill: currentColor !important;
        width: 1.25rem !important;
        height: 1.25rem !important;
    }
    
    /* Estilo para el botón de expandir */
    button[title="Expand"] {
        display: inline-flex !important;
    }
    
    /* Estilo para el buscador */
    input[type="search"] {
        background: var(--input-bg) !important;
        color: var(--input-text) !important;
        border: 1px solid var(--input-border) !important;
        border-radius: 8px !important;
        padding: 0.4rem 0.8rem !important;
    }
    
    /* =========================================================
       EXPANDER
    ========================================================= */
    .streamlit-expanderHeader {
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: var(--text-primary) !important;
        background: var(--bg-secondary) !important;
        border-radius: 14px !important;
        border: 1px solid var(--border-light) !important;
        padding: 0.7rem 1rem !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    .streamlit-expanderHeader:hover {
        border-color: var(--accent-primary) !important;
        box-shadow: var(--shadow-md) !important;
    }
    
    /* =========================================================
       PROGRESS BAR
    ========================================================= */
    .stProgress > div > div {
        background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary)) !important;
        border-radius: 20px !important;
        height: 5px !important;
    }
    
    /* =========================================================
       SEPARADORES
    ========================================================= */
    hr {
        margin: 1.2rem 0 !important;
        border: none !important;
        height: 1px !important;
        background: linear-gradient(90deg, transparent, var(--border-medium), transparent) !important;
    }
    
    /* =========================================================
       TÍTULOS DE SECCIÓN
    ========================================================= */
    .section-title {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: var(--text-primary) !important;
        margin-bottom: 0.8rem !important;
        letter-spacing: -0.01em;
    }
    
    .section-subtitle {
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        margin-bottom: 0.6rem !important;
    }
    
</style>
""", unsafe_allow_html=True)

# =========================================================
# HEADER REDISEÑADO - SIN LÍNEA GRIS
# =========================================================
st.markdown('<div class="header-container">', unsafe_allow_html=True)

col_titulo, col_logo = st.columns([3, 1])

with col_titulo:
    st.markdown('<div class="title-container">', unsafe_allow_html=True)
    st.markdown('<span class="main-title">Cotizador PRO</span>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Sistema profesional de cotizaciones</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Acceso Administrativo
    st.markdown('<div class="access-container">', unsafe_allow_html=True)
    
    if st.session_state.modo_admin:
        st.markdown('<div style="display: flex; align-items: center; gap: 0.8rem;">', unsafe_allow_html=True)
        st.markdown('<span class="modo-admin-indicator">👑 Admin Activo</span>', unsafe_allow_html=True)
        if st.button("🔓 Cerrar", key="btn_cerrar_sesion_header"):
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

with col_logo:
    st.markdown('<div class="logo-container">', unsafe_allow_html=True)
    try:
        st.image("logo.png", use_container_width=False, width=140)
    except:
        st.markdown("""
        <svg class="logo-glossy" width="140" height="50" viewBox="0 0 140 50" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="140" height="50" rx="10" fill="url(#gradient)" />
            <path d="M28 18L36 25L28 32L20 25L28 18Z" fill="white" />
            <circle cx="70" cy="25" r="6" fill="#FFD966" />
            <text x="95" y="30" font-family="Inter" font-size="14" font-weight="600" fill="white">PRO</text>
            <defs>
                <linearGradient id="gradient" x1="0" y1="0" x2="140" y2="50" gradientUnits="userSpaceOnUse">
                    <stop stop-color="#3B82F6"/>
                    <stop offset="1" stop-color="#8B5CF6"/>
                </linearGradient>
            </defs>
        </svg>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# INICIALIZAR VARIABLES DE SESIÓN
# =========================================================
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

# =========================================================
# TABS
# =========================================================
tab1, tab2 = st.tabs(["📋 COTIZACIÓN", "👤 DATOS"])

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

def actualizar_rut():
    """Callback para actualizar el RUT cuando el usuario sale del campo"""
    if 'rut_input' in st.session_state:
        valor_actual = st.session_state.rut_input
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

def actualizar_telefono():
    """Callback para actualizar el teléfono del cliente"""
    if 'telefono_input' in st.session_state:
        valor_actual = st.session_state.telefono_input
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
# FUNCIÓN PARA OFUSCAR TEXTOS CON X (MITAD DEL TEXTO)
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
# TAB 2 - DATOS CLIENTE (REDISEÑADO)
# =========================================================

with tab2:
    st.markdown('<div class="section-title">📋 Datos de la Cotización</div>', unsafe_allow_html=True)
    
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
            st.markdown('<div class="premium-card-title">👤 CLIENTE</div>', unsafe_allow_html=True)
            
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
            st.markdown('<div class="premium-card-title">📍 PROYECTO</div>', unsafe_allow_html=True)
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
            st.markdown('<div class="premium-card-title">👨‍💼 ASESOR</div>', unsafe_allow_html=True)
            
            # Selector de asesores
            nombres_asesores = list(asesores.keys())
            
            # Crear el selectbox y capturar el valor
            indice_actual = nombres_asesores.index(st.session_state.asesor_seleccionado) if st.session_state.asesor_seleccionado in nombres_asesores else 0
            
            asesor_elegido = st.selectbox(
                "Seleccionar Asesor",
                nombres_asesores,
                index=indice_actual,
                key="asesor_select",
                label_visibility="collapsed"
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
            st.markdown('<div class="premium-card-title">📅 VALIDEZ</div>', unsafe_allow_html=True)
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
# TAB 1 - PREPARAR COTIZACIÓN (REDISEÑADO)
# =========================================================
    
with tab1:
    st.markdown('<div class="section-title">☑️ Gestión de Presupuesto</div>', unsafe_allow_html=True)
    
    # Contenedor único con borde redondeado para los 4 módulos
    with st.container(border=True):
        st.markdown('<div class="premium-card-title">📦 PRODUCTOS</div>', unsafe_allow_html=True)
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
                    st.session_state.margen = 0.0
                    st.success(f"Modelo cargado correctamente.")
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

            # Mostrar precios con margen aplicado (solo si está en modo administrativo)
            if st.session_state.modo_admin:
                precio_con_margen = aplicar_margen(precio_unitario_original, st.session_state.margen)
                subtotal_con_margen = precio_con_margen * cantidad
                st.caption(f"P. Unitario original: {formato_clp(precio_unitario_original)}")
                if st.session_state.margen > 0:
                    st.caption(f"P. con margen ({st.session_state.margen}%): {formato_clp(precio_con_margen)}")
                st.caption(f"Subtotal con margen: {formato_clp(subtotal_con_margen)}")
            else:
                st.caption(f"P. Unitario: {formato_clp(precio_unitario_original)}")
                st.caption(f"Subtotal: {formato_clp(precio_unitario_original * cantidad)}")

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
                        "Precio Unitario": precio_unitario_original,
                        "Subtotal": precio_unitario_original * cantidad
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
                        st.success(f"Categoría eliminada.")
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
                    st.success(f"Categoría agregada.")
                    st.rerun()

    # ---------------- RESUMEN ----------------
    st.markdown("---")

    # Título y control de margen en la MISMA LÍNEA (solo visible en modo administrativo)
    if st.session_state.modo_admin:
        col_titulo, col_margen_etq, col_margen_input = st.columns([4, 0.5, 0.8])

        with col_titulo:
            st.markdown('<div class="section-subtitle">Resumen del Presupuesto</div>', unsafe_allow_html=True)

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
    else:
        st.markdown('<div class="section-subtitle">Resumen del Presupuesto</div>', unsafe_allow_html=True)

    if st.session_state.carrito:
        # Crear DataFrame para mostrar
        carrito_df = pd.DataFrame(st.session_state.carrito)
        
        # Calcular totales base (sin margen)
        subtotal_base = carrito_df["Subtotal"].sum()
        iva_base = subtotal_base * 0.19
        total_base = subtotal_base + iva_base
        
        # Calcular totales con margen (solo si está en modo administrativo)
        if st.session_state.modo_admin:
            # Aplicar margen a los precios para la visualización
            carrito_df_con_margen = carrito_df.copy()
            carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(
                lambda x: aplicar_margen(x, st.session_state.margen)
            )
            carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]
            subtotal_general = carrito_df_con_margen["Subtotal"].sum()
            iva = subtotal_general * 0.19
            total = subtotal_general + iva
            
            # CALCULAR MARGEN BRUTO (diferencia entre subtotal con margen y subtotal sin margen)
            margen_valor = subtotal_general - subtotal_base
            
            # Calcular comisiones (2.5% y 0.8% sobre subtotal con margen)
            comision_vendedor = subtotal_general * 0.025
            comision_supervisor = subtotal_general * 0.008
            total_comisiones = comision_vendedor + comision_supervisor
            
            # Calcular utilidad real (margen bruto menos comisiones)
            utilidad_real = margen_valor - comision_vendedor - comision_supervisor
        else:
            # Modo ejecutivo: mostrar precios sin margen
            subtotal_general = subtotal_base
            iva = iva_base
            total = total_base
            margen_valor = 0
            comision_vendedor = 0
            comision_supervisor = 0
            total_comisiones = 0
            utilidad_real = 0

        # ---------------- TABLA CON ELIMINACIÓN DIRECTA ----------------
        if st.session_state.modo_admin:
            # Mostrar tabla con precios con margen
            carrito_df_edit = carrito_df_con_margen.copy()
        else:
            # Mostrar tabla con precios sin margen
            carrito_df_edit = carrito_df.copy()
            
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

        # ---------------- TOTALES ----------------
        st.markdown("### Totales")
        st.write("Subtotal:", formato_clp(subtotal_general))
        st.write("IVA (19%):", formato_clp(iva))
        st.write("TOTAL:", formato_clp(total))
        if st.session_state.modo_admin and st.session_state.margen > 0:
            st.caption(f"*Precios calculados con margen del {st.session_state.margen}%")

        # BOTONES DEBAJO DE LA TABLA - LIMPIAR A LA IZQUIERDA, PDFs A LA DERECHA
        col_btn_left, col_btn_center, col_btn_right = st.columns([1, 1, 1])

        with col_btn_left:
            if st.button("🧹 Limpiar Presupuesto", use_container_width=True):
                st.session_state.carrito = []
                if st.session_state.modo_admin:
                    st.session_state.margen = 0.0
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

        # Aplicar margen a los precios para el PDF (solo si está en modo administrativo)
        if st.session_state.modo_admin:
            carrito_df_pdf = carrito_df_original.copy()
            carrito_df_pdf["Precio Unitario"] = carrito_df_pdf["Precio Unitario"].apply(
                lambda x: aplicar_margen(x, st.session_state.margen)
            )
            carrito_df_pdf["Subtotal"] = carrito_df_pdf["Cantidad"] * carrito_df_pdf["Precio Unitario"]
            margen_actual = st.session_state.margen
        else:
            carrito_df_pdf = carrito_df_original.copy()
            margen_actual = 0

        # Verificar validaciones antes de mostrar los botones
        if "@" not in correo_para_pdf:
            st.error("El correo debe contener '@' para generar el PDF.")
        elif dias_validez < 0:
            st.error("Fechas incorrectas.")
        elif not rut_valido_para_pdf and st.session_state.rut_raw:
            st.error("El RUT no es válido. Corrígelo antes de generar el PDF.")
        else:
            with col_btn_center:
                # PDF COMPLETO
                pdf_buffer_completo = generar_pdf_base(
                    carrito_df_pdf,
                    subtotal_general,
                    iva,
                    total,
                    datos_cliente_pdf,
                    fecha_inicio,
                    fecha_termino,
                    dias_validez,
                    datos_asesor_pdf,
                    ofuscar=False,
                    margen=margen_actual
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
                # PDF PARA CLIENTE
                pdf_buffer_cliente = generar_pdf_base(
                    carrito_df_pdf,
                    subtotal_general,
                    iva,
                    total,
                    datos_cliente_pdf,
                    fecha_inicio,
                    fecha_termino,
                    dias_validez,
                    datos_asesor_pdf,
                    ofuscar=True,
                    margen=margen_actual
                )

                st.download_button(
                    label="🔒 PDF para Cliente",
                    data=pdf_buffer_cliente,
                    file_name="Presupuesto_Cliente.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key="pdf_cliente"
                )

        # =========================================================
        # TARJETAS DE MÉTRICAS - 3 TARJETAS EN LA MISMA FILA
        # =========================================================
        st.markdown("---")
        st.markdown('<div class="section-subtitle">Métricas</div>', unsafe_allow_html=True)
        
        # Primera fila con 4 tarjetas básicas
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        
        with col_m1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">ÍTEMS</div>
                <div class="metric-value" style="color: #fbbf24;">{len(st.session_state.carrito)}</div>
                <div class="metric-change" style="color: #fbbf24;">En presupuesto</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_m2:
            total_productos = sum(item["Cantidad"] for item in st.session_state.carrito)
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">PRODUCTOS</div>
                <div class="metric-value" style="color: #f97316;">{total_productos}</div>
                <div class="metric-change" style="color: #f97316;">Unidades</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_m3:
            categorias_unicas = len(set(item["Categoria"] for item in st.session_state.carrito))
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">CATEGORÍAS</div>
                <div class="metric-value" style="color: #10b981;">{categorias_unicas}</div>
                <div class="metric-change" style="color: #10b981;">Diferentes</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_m4:
            # Determinar el texto del subtotal según el modo y margen
            if st.session_state.modo_admin and st.session_state.margen > 0:
                subtotal_texto = f"Sin IVA • Margen {st.session_state.margen}%"
            else:
                subtotal_texto = "Sin IVA"
                
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">SUBTOTAL</div>
                <div class="metric-value" style="color: #f43f5e;">{formato_clp(subtotal_general)}</div>
                <div class="metric-change" style="color: #f43f5e;">{subtotal_texto}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Segunda fila - COMPORTAMIENTO DINÁMICO SEGÚN MODO
        st.markdown("---")
        
        if st.session_state.modo_admin and st.session_state.margen > 0:
            # MODO ADMINISTRATIVO: 3 tarjetas en la misma fila
            col_total, col_comisiones, col_utilidad = st.columns(3)
            
            with col_total:
                st.markdown(f"""
                <div class="metric-card-special metric-card-total">
                    <div class="metric-title">TOTAL CON IVA</div>
                    <div class="metric-value">{formato_clp(total)}</div>
                    <div class="metric-change">IVA incluido (19%) • Margen {st.session_state.margen}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_comisiones:
                st.markdown(f"""
                <div class="metric-card-special metric-card-comisiones">
                    <div class="metric-title">COMISIONES</div>
                    <div class="metric-value">{formato_clp(total_comisiones)}</div>
                    <div class="comision-detalle">
                        <span>Vendedor (2.5%)</span>
                        <span>{formato_clp(comision_vendedor)}</span>
                    </div>
                    <div class="comision-detalle">
                        <span>Supervisor (0.8%)</span>
                        <span>{formato_clp(comision_supervisor)}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_utilidad:
                st.markdown(f"""
                <div class="metric-card-special metric-card-utilidad">
                    <div class="metric-title">UTILIDAD REAL</div>
                    <div class="metric-value">{formato_clp(utilidad_real)}</div>
                    <div class="metric-change">Margen {st.session_state.margen}% - Comisiones</div>
                </div>
                """, unsafe_allow_html=True)
        
        elif st.session_state.modo_admin and st.session_state.margen == 0:
            # MODO ADMINISTRATIVO SIN MARGEN: 3 tarjetas atenuadas
            col_total, col_comisiones, col_utilidad = st.columns(3)
            
            with col_total:
                st.markdown(f"""
                <div class="metric-card-special metric-card-total" style="opacity: 0.7;">
                    <div class="metric-title">TOTAL CON IVA</div>
                    <div class="metric-value">{formato_clp(total)}</div>
                    <div class="metric-change">IVA incluido (19%)</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_comisiones:
                st.markdown("""
                <div class="metric-card-special metric-card-comisiones" style="opacity: 0.7;">
                    <div class="metric-title">COMISIONES</div>
                    <div class="metric-value">$0</div>
                    <div class="comision-detalle">
                        <span>Vendedor (2.5%)</span>
                        <span>$0</span>
                    </div>
                    <div class="comision-detalle">
                        <span>Supervisor (0.8%)</span>
                        <span>$0</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_utilidad:
                st.markdown("""
                <div class="metric-card-special metric-card-utilidad" style="opacity: 0.7;">
                    <div class="metric-title">UTILIDAD REAL</div>
                    <div class="metric-value">$0</div>
                    <div class="metric-change">Sin margen aplicado</div>
                </div>
                """, unsafe_allow_html=True)
        
        else:
            # MODO EJECUTIVO: Total con IVA centrado
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f"""
                <div class="metric-card-special metric-card-total">
                    <div class="metric-title">TOTAL CON IVA</div>
                    <div class="metric-value">{formato_clp(total)}</div>
                    <div class="metric-change">IVA incluido (19%)</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("👈 Agrega productos al presupuesto usando los controles de la izquierda")