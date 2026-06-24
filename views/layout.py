"""
Layout global del sistema — CSS, header fijo, barra de usuario, código de acceso.
Llamar render_layout() una sola vez desde app.py después de la autenticación.
"""
import base64
import os
import streamlit as st
import streamlit.components.v1 as _components

from auth.auth_service   import logout_usuario, cambiar_password_propio, login_usuario
from auth.access_code    import generar_codigo_acceso, _get_bloque_horario
import datetime as _dt


# ── CSS global ────────────────────────────────────────────────────────────────

_CSS_GLOBAL = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;1,300;1,400;1,500;1,600;1,700;1,800&family=Montserrat:wght@300;400;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Ocultar elementos nativos de Streamlit ── */
#MainMenu { display: none !important; }
footer    { display: none !important; }
header    { visibility: hidden !important; }
[data-testid="stToolbar"]          { display: none !important; }
[data-testid="stDecoration"]       { display: none !important; }
[data-testid="stStatusWidget"]     { display: none !important; }
[data-testid="stBottomBlockContainer"]   { display: none !important; }
[data-testid="stSidebarCollapsedControl"] { display: none !important; }
[data-testid="stBottom"]                 { display: none !important; }
[data-testid="stHeader"]           { display: none !important; height: 0 !important; min-height: 0 !important; }
[class*="viewerBadge"]             { display: none !important; }
[class*="ViewerBadge"]             { display: none !important; }
.stAppDeployButton                 { display: none !important; }
[data-testid="stAppDeployButton"]  { display: none !important; }
[class*="stAppToolbar"]            { display: none !important; }
a[href*="streamlit.io"]            { display: none !important; }
a[href*="github.com"]              { display: none !important; }
button[title="View fullscreen"]    { display: none !important; }

/* ── Espaciado para el header fijo de 65px + 15px gap = 80px
   SOLUCIÓN PURA CSS (sin JS de gap-enforcement, que era frágil y rompía
   layouts en reruns). Forzamos padding-top:0 en TODOS los wrappers de
   Streamlit y aplicamos el padding-top directamente en .block-container.
   Si Streamlit cambia los testid en el futuro, se agregan acá. */
[data-testid="stMain"],
[data-testid="stMainBlockContainer"],
[data-testid="stAppViewContainer"],
.main,
section.main {
    padding-top: 0 !important;
    margin-top: 0 !important;
}
.stApp > header,
[data-testid="stHeader"] {
    display: none !important; height: 0 !important;
}
[data-testid="stAppViewContainer"] > section:first-child[data-testid="stSidebar"] {
    padding-top: 0 !important;
}
/* Page header margin-top:0 (el padding-top:80px del block-container ya
   da el espacio del header fijo + gap superior). margin-bottom dado
   por _page_headers_css (28px). Aquí solo reset margin-top defensivo. */
.page-hdr, .dash-hdr, .hdr1, .hdr2, .hdr3, .hdr6, .hdr7,
.hdr-admindata, .hdr-contrato, .hdr-notif, .hdr-oper, .hdr-3d,
.hdr-reporte, .hdr-salud, .hdr-usr, .excel-header, .hdr-formulario {
    margin-top: 0 !important;
}

/* ── SACAR DEL FLUJO LOS ELEMENTOS NO-CONTENIDO ──────────────────────────
   CLAVE: el stVerticalBlock principal usa flexbox con `gap`. El gap se
   aplica entre TODOS los items, incluso de altura 0. Por eso varios
   wrappers utilitarios (paneles flotantes, iframes de JS, botones ocultos)
   acumulaban gap y empujaban el page-hdr ~150px hacia abajo.

   Solución: position:absolute los saca del flujo flex → NO contribuyen gap.
   Los hijos position:fixed siguen anclados al viewport (sin transform
   ancestro). Así el page-hdr queda como primer item real y el
   padding-top:80px del block-container da el gap EXACTO sin JS. */

/* 1. Markdown de SOLO <style> (inyecciones de CSS: _CSS_GLOBAL, page-headers,
   preloader, estilos de cada tab). El <style> es el único hijo del
   stMarkdownContainer → no es contenido visible, no debe ocupar flujo.
   El page-hdr NO se ve afectado: render_page_header renderiza un <div>
   (sin <style>), así que no matchea. */
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] [data-testid="stMarkdownContainer"] > style:only-child) {
    position: absolute !important;
    top: 0 !important; left: 0 !important;
    width: 0 !important; height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    overflow: hidden !important;
}
/* 2. Header fijo + barra usuario (markdown con <style>+<div fixed>) */
[data-testid="stElementContainer"]:has(#_usr_header_bar) {
    position: absolute !important;
    top: 0 !important; left: 0 !important;
    width: 0 !important; height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    overflow: visible !important;
}
/* 3. iframes de components.html height=0/1 (JS del layout, preloader, sync,
   paneles). El iframe puede estar anidado, por eso :has descendente. */
[data-testid="stElementContainer"]:has(iframe[height="0"]),
[data-testid="stElementContainer"]:has(iframe[height="1"]) {
    position: absolute !important;
    top: 0 !important; left: 0 !important;
    width: 0 !important; height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    overflow: hidden !important;
}
/* 4. Wrappers de paneles flotantes cuyo CONTENIDO es position:fixed pero
   el wrapper sigue en flujo. NO incluir aquí .st-key-btn_fab_guardar:
   ese wrapper YA es position:fixed (bottom-left) por su propia CSS; si le
   forzamos position:absolute top:0 aquí, el FAB salta al header. */
[data-testid="stElementContainer"]:has(> div[data-testid="stPopover"]),
[data-testid="stElementContainer"]:has(#_prog_panel) {
    position: absolute !important;
    top: 0 !important; left: 0 !important;
    width: 0 !important; height: 0 !important;
    margin: 0 !important; padding: 0 !important;
    overflow: visible !important;
}
/* 5. Fila oculta de botones de sesión + botón cerrar oculto */
[data-testid="stHorizontalBlock"]:has(.st-key-btn_pwd_hdr),
.st-key-btn_cerrar_cotizacion {
    position: absolute !important;
    left: -9999px !important; top: -9999px !important;
    width: 1px !important; height: 1px !important;
    overflow: hidden !important;
    margin: 0 !important; padding: 0 !important;
}

/* ── Base ── */
html, body, [class*="css"] { font-family: 'Plus Jakarta Sans', sans-serif !important; }
.stApp { background-color: #f0f2f8 !important; }

/* ── Inputs ── */
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

/* ── Botones ── */
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

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0 !important; border-bottom: 2px solid #e2e6f3 !important;
    padding: 0 !important; margin-bottom: 0 !important;
    background: transparent !important;
    overflow-x: auto !important; overflow-y: hidden !important;
    scrollbar-width: none !important; -ms-overflow-style: none !important;
    scroll-behavior: smooth !important;
}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar { display: none !important; }
.stTabs [data-baseweb="tab"] {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.88rem !important; font-weight: 900 !important;
    color: #7c85b3 !important; padding: 0.85rem 1.6rem !important;
    background: transparent !important; border: none !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important; letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    -webkit-font-smoothing: antialiased !important;
    transition: all 0.2s ease !important;
}
.stTabs [data-baseweb="tab"] p,
.stTabs [data-baseweb="tab"] span,
.stTabs [data-baseweb="tab"] div {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 700 !important; font-size: 0.88rem !important;
}
.stTabs [data-baseweb="tab"]:hover { color: #5b7cfa !important; background: rgba(91,124,250,0.05) !important; }
.stTabs [aria-selected="true"] {
    color: #5b7cfa !important; border-bottom: 3px solid #5b7cfa !important;
    font-weight: 900 !important; background: rgba(91,124,250,0.06) !important;
}
.stTabs [data-baseweb="tab-panel"] { padding-top: 1.5rem !important; border-top: none !important; background-color: transparent !important; }
.stTabs > div > div:nth-child(2) { border-top: none !important; box-shadow: none !important; }
hr { display: none !important; }

/* ── Toast ── */
div[data-testid="stToast"] {
    background: linear-gradient(135deg, #1d4ed8 0%, #2563eb 100%) !important;
    color: #ffffff !important; border: none !important;
    border-radius: 12px !important; padding: 16px 20px !important;
    min-width: 280px !important;
    box-shadow: 0 8px 24px rgba(37,99,235,0.4) !important;
    font-size: 1rem !important; font-weight: 600 !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
}
div[data-testid="stToast"] p,
div[data-testid="stToast"] span,
div[data-testid="stToast"] div { color: #ffffff !important; font-size: 1rem !important; font-weight: 600 !important; }
div[data-testid="stToast"] button { color: rgba(255,255,255,0.7) !important; filter: brightness(10) !important; }

/* ── Dataframes / editors ── */
div[data-testid="stDataFrame"] > div,
div[data-testid="stDataEditor"] > div {
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(91,124,250,0.08), 0 1px 6px rgba(0,0,0,0.06) !important;
    border: 1px solid rgba(91,124,250,0.15) !important;
    overflow: hidden !important; transition: box-shadow 0.25s ease !important;
    background: #ffffff !important;
}

/* ── Containers con borde ── */
[data-testid="stVerticalBlock"] > [data-testid="stVerticalBlockBorderWrapper"] {
    box-shadow: 0 4px 20px rgba(91,124,250,0.08), 0 1px 6px rgba(0,0,0,0.06) !important;
    border: 1px solid rgba(91,124,250,0.15) !important;
    border-radius: 16px !important; background: #ffffff !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #ffffff; border-radius: 14px; padding: 1rem 1.2rem;
    border: 1.5px solid #e8ebf5; box-shadow: 0 2px 10px rgba(0,0,0,0.04);
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

/* ── H3 / H4 ── */
.stMarkdown h3 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 1.05rem !important; font-weight: 700 !important;
    color: #1e2447 !important; letter-spacing: -0.02em !important;
    padding-left: 0.9rem !important; border-left: 3.5px solid #5b7cfa !important;
    margin: 1.2rem 0 0.8rem 0 !important; line-height: 1.4 !important;
}
.stMarkdown h4 {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 0.95rem !important; font-weight: 700 !important;
    color: #2a3060 !important; letter-spacing: -0.01em !important;
    margin: 1rem 0 0.6rem 0 !important;
}
/* padding-top:80px = 65 (header fijo) + 15 (gap). Estático, sin JS.
   Funciona porque los wrappers no-contenido (paneles flotantes, iframes
   height0, botones ocultos) están position:absolute y NO contribuyen al
   gap flex, así el page-hdr es el primer item real del block-container. */
.block-container { padding-top: 80px !important; padding-bottom: 3rem !important; }

/* ── Header fijo ── */
#_usr_header_bar {
    position: fixed; top: 0; left: 0; right: 0; height: 65px;
    display: flex; align-items: center; padding: 0 1.5rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    box-shadow: 0 4px 24px rgba(0,0,0,0.4), 0 1px 0 rgba(255,255,255,0.05);
    z-index: 99998; gap: 12px; transition: background 0.5s ease;
}
[data-testid="stDialog"] > div > div {
    margin-top: 65px !important; max-height: calc(100vh - 65px) !important;
}
div[role="dialog"] {
    margin-top: 65px !important; max-height: calc(100vh - 65px) !important;
}
#_usr_header_bar .usr-right {
    display: flex; align-items: center; gap: 10px;
    margin-left: auto; flex-shrink: 0;
}

/* ── Heartbeat indicators ── */
@keyframes _hb_pulse{0%,100%{transform:scale(1);opacity:.35}50%{transform:scale(2.4);opacity:0}}
._hb_wrap{display:inline-flex;align-items:center;gap:7px;line-height:1.4;}
._hb_dot{position:relative;display:inline-block;width:20px;height:20px;flex-shrink:0;vertical-align:middle;}
._hb_dot span{position:absolute;border-radius:50%;}
._hb_ring_r{inset:0;background:#E24B4A;opacity:.35;animation:_hb_pulse 1.5s ease-in-out infinite;}
._hb_core_r{inset:3px;background:#E24B4A;}
._hb_ring_a{inset:0;background:#EF9F27;opacity:.35;animation:_hb_pulse 1.5s ease-in-out infinite;}
._hb_core_a{inset:3px;background:#EF9F27;}
._hb_check_wrap{inset:3px;background:#1D9E75;}

/* ── Tabla resultados ── */
.resultados-table {
    width: 100%; border-collapse: separate; border-spacing: 0;
    font-family: 'Plus Jakarta Sans', sans-serif; font-size: 0.875rem;
    background: #ffffff; table-layout: auto;
}
.resultados-table th {
    background: linear-gradient(135deg, #1e2447 0%, #2a3060 100%) !important;
    color: #ffffff !important; font-weight: 900 !important;
    padding: 10px 12px !important; text-align: left !important;
    font-size: 0.72rem !important; letter-spacing: 0.07em !important;
    text-transform: uppercase !important; white-space: nowrap !important;
    position: sticky !important; top: -1px !important; z-index: 2 !important;
}
.resultados-table td {
    padding: 8px 12px !important; border-bottom: 1px solid #f0f2f8 !important;
    color: #3a4070 !important; background-color: #ffffff !important;
    transition: background 0.15s !important; vertical-align: middle !important;
}
.resultados-table tr:hover td { background-color: #f5f7ff !important; }
.resultados-table td.demora-col { color: #dc2626 !important; white-space: nowrap !important; }
.resultados-table tr:last-child td { border-bottom: none !important; }

/* ── Metric cards ── */
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
.metric-card:hover { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(30,36,71,0.3); }
.metric-title { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; color: #7b84b0; margin-bottom: 0.7rem; }
.metric-value { font-size: 2.5rem; font-weight: 800; line-height: 1.05; letter-spacing: -0.04em; color: #e8ecff; }
.metric-change { font-size: 0.75rem; color: #5c6494; margin-top: 0.35rem; }

/* ── Stats cards ── */
.stats-card {
    background: #ffffff; border-radius: 16px; padding: 1.5rem 1.6rem;
    border: 1.5px solid #e8ebf5; box-shadow: 0 2px 12px rgba(0,0,0,0.05);
    transition: all 0.25s cubic-bezier(0.4,0,0.2,1);
    height: 100%; position: relative; overflow: hidden;
}
.stats-card:hover { transform: translateY(-4px); box-shadow: 0 12px 32px rgba(91,124,250,0.12); border-color: #c5ccf0; }
.stats-title { font-size: 0.72rem; font-weight: 700; color: #9099be; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 0.5rem; }
.stats-number {
    font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: 0.5rem 0;
    letter-spacing: -0.04em; padding: 0.5rem 0; text-align: center;
    border-top: 1.5px solid #eaedf5; border-bottom: 1.5px solid #eaedf5;
}
.stats-number.total       { color: #5b7cfa !important; }
.stats-number.autorizadas { color: #10b981 !important; }
.stats-number.borradores  { color: #f59e0b !important; }
.stats-number.incompletas { color: #ef4444 !important; }
.stats-desc { font-size: 0.78rem; color: #a0a8c8; text-align: center; margin-top: 0.25rem; }

/* ── Modulo título ── */
p.modulo-titulo {
    color: #0f172a !important; font-family: 'Montserrat', sans-serif !important;
    font-weight: 900 !important; font-size: 0.95rem !important;
    letter-spacing: 0.05em !important; text-transform: uppercase !important;
    margin: 0 0 6px 0 !important;
}

/* ── Main title / sub title ── */
.main-title {
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-size: 2rem !important; font-weight: 800 !important;
    background: linear-gradient(135deg, #5b7cfa 0%, #8b5cf6 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    letter-spacing: -0.04em; line-height: 1.15;
}
.sub-title { color: #9099be; font-size: 0.82rem; font-weight: 500; margin-top: 0.2rem; letter-spacing: 0.02em; }

/* ── Spinner branded para st.spinner() en tabs ── */
@keyframes _ec_sp_spin { to { transform: rotate(360deg); } }
@keyframes _ec_sp_pulse { 0%,100% { opacity: 0.5; } 50% { opacity: 1; } }
[data-testid="stSpinner"] {
    background: linear-gradient(135deg, rgba(15,23,42,0.97), rgba(30,42,94,0.97)) !important;
    border-radius: 14px !important;
    padding: 22px 28px !important;
    border: 1px solid rgba(91,124,250,0.25) !important;
    box-shadow: 0 8px 32px rgba(15,23,42,0.4) !important;
    color: #cbd5e1 !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em !important;
}
[data-testid="stSpinner"] > div { color: #e2e8f0 !important; font-size: 0.88rem !important; }
[data-testid="stSpinner"] i, [data-testid="stSpinner"] svg, [data-testid="stSpinner"] [role="progressbar"] {
    border-color: rgba(91,124,250,0.25) !important;
    border-top-color: #8b5cf6 !important;
    border-right-color: #5b7cfa !important;
    width: 28px !important; height: 28px !important;
    animation: _ec_sp_spin 1s linear infinite !important;
}

/* (La fila oculta de botones de sesión se maneja arriba, junto a los
   demás elementos sacados del flujo) */
</style>
"""


# ── Logo ─────────────────────────────────────────────────────────────────────

def _logo_html() -> str:
    for path in ["logo.png", "assets/logo.png", "images/logo.png"]:
        if os.path.exists(path):
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            return f'<img src="data:image/png;base64,{b64}" width="280" style="display:block;margin-left:auto;">'
    return '<span style="font-size:1.6rem;font-weight:900;background:linear-gradient(135deg,#5b7cfa,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">Cotizador PRO</span>'


# ── Preloader (fullscreen, página completa) ──────────────────────────────────

def render_preloader() -> None:
    """Preloader fullscreen reutilizable.

    - Carga inicial de la pestaña: se anima 0→100% (~1.8s) + fade-out.
    - Click en sidebar nav o login submit: se re-anima con duración corta.
    - Persiste en el DOM del documento padre (no se re-crea en cada rerun),
      así los reruns de Streamlit no interrumpen la animación.
    """
    _logo_uri = _logo_b64() or ""
    # CSS del overlay — st.markdown lo coloca como <style> en parent <head>,
    # persiste entre reruns sin problema.
    st.markdown("""
<style>
@keyframes _ec_pre_pulse {
  0%, 100% { transform: scale(1); filter: drop-shadow(0 0 20px rgba(91,124,250,0.5)) brightness(1); }
  50%      { transform: scale(1.05); filter: drop-shadow(0 0 40px rgba(139,92,246,0.8)) brightness(1.15); }
}
@keyframes _ec_pre_ring_spin { to { transform: rotate(360deg); } }
@keyframes _ec_pre_shimmer {
  0%   { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
@keyframes _ec_pre_bg {
  0%, 100% { background-position: 0% 50%; }
  50%      { background-position: 100% 50%; }
}
#_ec_preloader {
  position: fixed; inset: 0;
  background: linear-gradient(135deg, #0a0f1f 0%, #0f172a 25%, #1e2a5e 50%, #0f172a 75%, #0a0f1f 100%);
  background-size: 300% 300%;
  animation: _ec_pre_bg 12s ease infinite;
  z-index: 2147483647;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 32px;
  transition: opacity 0.7s ease;
  font-family: 'Montserrat', sans-serif;
}
#_ec_preloader.fade-out { opacity: 0; pointer-events: none; }
#_ec_pre_wrap { position: relative; width: 220px; height: 220px; display:flex; align-items:center; justify-content:center; }
#_ec_pre_ring {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #5b7cfa;
  border-right-color: #8b5cf6;
  animation: _ec_pre_ring_spin 1.6s linear infinite;
}
#_ec_pre_ring2 {
  position: absolute; inset: 12px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-bottom-color: rgba(139,92,246,0.4);
  border-left-color: rgba(91,124,250,0.4);
  animation: _ec_pre_ring_spin 2.4s linear reverse infinite;
}
#_ec_pre_logo {
  max-width: 150px; max-height: 150px;
  animation: _ec_pre_pulse 1.8s ease-in-out infinite;
}
#_ec_pre_bar_wrap {
  width: 320px; max-width: 60vw; height: 4px;
  background: rgba(255,255,255,0.08); border-radius: 2px; overflow: hidden;
  position: relative;
}
#_ec_pre_bar {
  width: 0%; height: 100%;
  background: linear-gradient(90deg, #5b7cfa, #8b5cf6, #5b7cfa);
  background-size: 200% 100%;
  animation: _ec_pre_shimmer 2s linear infinite;
  border-radius: 2px;
  transition: width 0.35s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 0 12px rgba(139,92,246,0.6);
}
#_ec_pre_info {
  display: flex; align-items: center; gap: 18px;
  color: #cbd5e1;
  font-weight: 600; font-size: 0.85rem; letter-spacing: 0.12em; text-transform: uppercase;
  min-height: 20px;
}
#_ec_pre_pct {
  font-weight: 900; font-size: 1rem; color: #fff;
  font-variant-numeric: tabular-nums;
  min-width: 48px; text-align: right;
}
#_ec_pre_msg { opacity: 0.7; }
@media (max-width: 600px) {
  #_ec_pre_wrap { width: 180px; height: 180px; }
  #_ec_pre_logo { max-width: 120px; max-height: 120px; }
}

/* ── Tab-preloader (fondo blanco, logo oscuro) ── */
#_ec_tab_preloader {
  position: fixed;
  top: 65px; right: 0; bottom: 0; left: 0;
  background: #ffffff;
  z-index: 99990;
  display: none;
  flex-direction: column; align-items: center; justify-content: center;
  gap: 28px;
  transition: opacity 0.45s ease;
  font-family: 'Montserrat', sans-serif;
}
#_ec_tab_preloader.fade-out { opacity: 0; pointer-events: none; }
#_ec_tp_wrap { position: relative; width: 200px; height: 200px; display:flex; align-items:center; justify-content:center; }
#_ec_tp_ring {
  position: absolute; inset: 0;
  border-radius: 50%;
  border: 2px solid transparent;
  border-top-color: #5b7cfa;
  border-right-color: #8b5cf6;
  animation: _ec_pre_ring_spin 1.6s linear infinite;
}
#_ec_tp_ring2 {
  position: absolute; inset: 12px;
  border-radius: 50%;
  border: 2px solid transparent;
  border-bottom-color: rgba(139,92,246,0.45);
  border-left-color: rgba(91,124,250,0.45);
  animation: _ec_pre_ring_spin 2.4s linear reverse infinite;
}
#_ec_tp_logo {
  max-width: 130px; max-height: 130px;
  animation: _ec_pre_pulse 1.8s ease-in-out infinite;
  filter: none !important;
}
#_ec_tp_bar_wrap {
  width: 280px; max-width: 55vw; height: 4px;
  background: #eef0f6; border-radius: 2px; overflow: hidden;
}
#_ec_tp_bar {
  width: 0%; height: 100%;
  background: linear-gradient(90deg, #5b7cfa, #8b5cf6, #5b7cfa);
  background-size: 200% 100%;
  animation: _ec_pre_shimmer 2s linear infinite;
  border-radius: 2px;
  transition: width 0.3s cubic-bezier(0.4,0,0.2,1);
  box-shadow: 0 0 10px rgba(139,92,246,0.35);
}
#_ec_tp_info {
  display: flex; align-items: center; gap: 16px;
  color: #475569;
  font-weight: 600; font-size: 0.82rem; letter-spacing: 0.12em; text-transform: uppercase;
  min-height: 20px;
}
#_ec_tp_pct {
  font-weight: 900; font-size: 1rem; color: #0f172a;
  font-variant-numeric: tabular-nums;
  min-width: 48px; text-align: right;
}
#_ec_tp_msg { opacity: 0.8; color: #64748b; }
</style>
""", unsafe_allow_html=True)
    # JS: crea ambos overlays UNA SOLA VEZ en el documento padre (idempotente).
    # Persisten en DOM con display:none entre transiciones para evitar que
    # Streamlit los reemplace en cada rerun.
    _logo_img_tag = (
        f'<img id="_ec_pre_logo" src="{_logo_uri}" alt="" />'
        if _logo_uri else
        '<div id="_ec_pre_logo" style="font-family:Montserrat,sans-serif;font-weight:900;font-size:2.5rem;color:#fff;letter-spacing:0.05em;">COTIZADOR<span style="color:#5b7cfa;"> PRO</span></div>'
    )
    _overlay_html = (
        '<div id="_ec_pre_wrap">'
        '<div id="_ec_pre_ring"></div>'
        '<div id="_ec_pre_ring2"></div>'
        + _logo_img_tag +
        '</div>'
        '<div id="_ec_pre_bar_wrap"><div id="_ec_pre_bar"></div></div>'
        '<div id="_ec_pre_info">'
        '<span id="_ec_pre_msg">Cargando sistema</span>'
        '<span id="_ec_pre_pct">0%</span>'
        '</div>'
    )
    _logo_dark_uri = _logo_dark_b64() or ""
    _logo_dark_tag = (
        f'<img id="_ec_tp_logo" src="{_logo_dark_uri}" alt="" />'
        if _logo_dark_uri else
        '<div id="_ec_tp_logo" style="font-family:Montserrat,sans-serif;font-weight:900;font-size:2rem;color:#0f172a;letter-spacing:0.05em;">COTIZADOR<span style="color:#5b7cfa;"> PRO</span></div>'
    )
    _tab_overlay_html = (
        '<div id="_ec_tp_wrap">'
        '<div id="_ec_tp_ring"></div>'
        '<div id="_ec_tp_ring2"></div>'
        + _logo_dark_tag +
        '</div>'
        '<div id="_ec_tp_bar_wrap"><div id="_ec_tp_bar"></div></div>'
        '<div id="_ec_tp_info">'
        '<span id="_ec_tp_msg">Cargando pestaña</span>'
        '<span id="_ec_tp_pct">0%</span>'
        '</div>'
    )
    # Escapamos backticks por si el base64 los tuviera
    _overlay_html_js     = _overlay_html.replace("\\", "\\\\").replace("`", "\\`")
    _tab_overlay_html_js = _tab_overlay_html.replace("\\", "\\\\").replace("`", "\\`")
    _components.html(f"""
<script>
(function(){{
  var D = window.parent.document;
  var W = window.parent;
  var T_TOTAL = 1800, T_FADE = 600;
  var msgs = ['Cargando sistema', 'Conectando servicios', 'Preparando interfaz', 'Casi listo'];

  // Crear overlays si no existen (idempotentes — sobreviven reruns).
  var ov = D.getElementById('_ec_preloader');
  if (!ov) {{
    ov = D.createElement('div');
    ov.id = '_ec_preloader';
    ov.setAttribute('role', 'status');
    ov.setAttribute('aria-label', 'Cargando');
    ov.style.display = 'none';
    ov.innerHTML = `{_overlay_html_js}`;
    D.body.appendChild(ov);
  }}
  var tp = D.getElementById('_ec_tab_preloader');
  if (!tp) {{
    tp = D.createElement('div');
    tp.id = '_ec_tab_preloader';
    tp.setAttribute('role', 'status');
    tp.setAttribute('aria-label', 'Cargando pestaña');
    tp.style.display = 'none';
    tp.innerHTML = `{_tab_overlay_html_js}`;
    D.body.appendChild(tp);
  }}

  function animate(duration) {{
    var el = D.getElementById('_ec_preloader');
    if (!el) return;
    if (W._ec_pre_iv) {{ clearInterval(W._ec_pre_iv); W._ec_pre_iv = null; }}
    var bar = el.querySelector('#_ec_pre_bar');
    var pctEl = el.querySelector('#_ec_pre_pct');
    var msgEl = el.querySelector('#_ec_pre_msg');
    el.classList.remove('fade-out');
    el.style.display = 'flex';
    el.style.opacity = '1';
    el.style.pointerEvents = 'auto';
    if (bar) bar.style.width = '0%';
    if (pctEl) pctEl.textContent = '0%';
    if (msgEl) msgEl.textContent = msgs[0];
    var t0 = Date.now();
    W._ec_pre_iv = setInterval(function(){{
      var elapsed = Date.now() - t0;
      var pct = Math.min((elapsed / duration) * 100, 100);
      if (bar) bar.style.width = pct + '%';
      if (pctEl) pctEl.textContent = Math.round(pct) + '%';
      var idx = Math.min(Math.floor(pct / 25), msgs.length - 1);
      if (msgEl && msgEl.textContent !== msgs[idx]) msgEl.textContent = msgs[idx];
      if (pct >= 100) {{
        clearInterval(W._ec_pre_iv); W._ec_pre_iv = null;
        setTimeout(function(){{
          var e2 = D.getElementById('_ec_preloader');
          if (!e2) return;
          e2.classList.add('fade-out');
          setTimeout(function(){{
            e2.style.display = 'none';
            e2.style.opacity = '1';
            e2.classList.remove('fade-out');
          }}, T_FADE);
        }}, 200);
      }}
    }}, 60);
  }}
  W._ec_show_preloader = animate;

  // Posiciona el tab-preloader sobre el área de contenido principal
  // (debajo del header fijo, a la derecha del sidebar).
  function positionTab(el) {{
    var sidebar = D.querySelector('section[data-testid="stSidebar"]');
    var sbW = sidebar ? sidebar.offsetWidth : 0;
    el.style.top    = '65px';
    el.style.bottom = '0';
    el.style.left   = sbW + 'px';
    el.style.right  = '0';
  }}

  // Tab-preloader: fondo blanco, logo oscuro. Se queda visible hasta que
  // el DOM de stMain deje de mutar (contenido terminó de cargar) — con un
  // mínimo de tiempo visible para que no parpadee y un fallback duro.
  function animateTab() {{
    var el = D.getElementById('_ec_tab_preloader');
    if (!el) return;
    if (W._ec_tp_iv) {{ clearInterval(W._ec_tp_iv); W._ec_tp_iv = null; }}
    if (W._ec_tp_obs) {{ try {{ W._ec_tp_obs.disconnect(); }} catch(e){{}} W._ec_tp_obs = null; }}
    positionTab(el);
    var bar = el.querySelector('#_ec_tp_bar');
    var pctEl = el.querySelector('#_ec_tp_pct');
    var msgEl = el.querySelector('#_ec_tp_msg');
    var tabMsgs = ['Cargando pestaña', 'Solicitando datos', 'Renderizando', 'Casi listo'];
    el.classList.remove('fade-out');
    el.style.display = 'flex';
    el.style.opacity = '1';
    el.style.pointerEvents = 'auto';
    if (bar) bar.style.width = '0%';
    if (pctEl) pctEl.textContent = '0%';
    if (msgEl) msgEl.textContent = tabMsgs[0];

    var t0 = Date.now();
    var lastMut = Date.now();
    var contentArrived = false;   // ¿llegó YA el contenido nuevo de la pestaña?
    var pctAtArrival = 88;        // valor de la barra al momento de llegar
    var main = D.querySelector('[data-testid="stMain"]') || D.body;
    try {{
      W._ec_tp_obs = new MutationObserver(function(){{
        // Ignoramos los primeros 150ms (ruido del click/popover). Después,
        // cualquier mutación en stMain = Streamlit renderizó el contenido nuevo.
        // CLAVE: durante el fetch lento de la DB, Streamlit bloquea Python y
        // stMain NO muta (el iframe de la tabla es caja negra), así que
        // contentArrived sigue false → el preloader NO termina antes de tiempo.
        if (Date.now() - t0 < 150) return;
        if (!contentArrived) {{
          contentArrived = true;
          pctAtArrival = 88 * (1 - Math.exp(-(Date.now() - t0) / 1400));
        }}
        lastMut = Date.now();
      }});
      W._ec_tp_obs.observe(main, {{ childList: true, subtree: true, attributes: false }});
    }} catch(e) {{}}

    var T_MIN     = 600;    // ms mínimo visible (anti-parpadeo)
    var T_STABLE  = 550;    // ms sin mutaciones (tras llegar el contenido) = listo
    var T_HARD    = 20000;  // hard timeout (pestañas muy lentas)

    W._ec_tp_iv = setInterval(function(){{
      var elapsed = Date.now() - t0;
      // Fallback: si tras 3s no detectamos "llegada" (p.ej. el contenido llegó
      // dentro de la ventana ignorada, o la pestaña no muta stMain), asumimos
      // que ya cargó para no quedarnos esperando el hard timeout.
      if (!contentArrived && elapsed >= 3000) {{
        contentArrived = true;
        pctAtArrival = 88;
      }}
      var sinceMut = Date.now() - lastMut;
      // Barra asintótica hacia 90% mientras espera el contenido; salta a 100%
      // sólo cuando el contenido llegó y se estabilizó.
      var pct;
      if (!contentArrived) {{
        // crece lento hacia 88% (no llega solo: espera el contenido real)
        pct = 88 * (1 - Math.exp(-elapsed / 1400));
      }} else {{
        // contenido llegó: continúa suave desde donde estaba hasta 100%
        // según la estabilidad acumulada (sin saltos).
        pct = pctAtArrival + (100 - pctAtArrival) * Math.min(sinceMut / T_STABLE, 1);
      }}
      if (bar) bar.style.width = pct + '%';
      if (pctEl) pctEl.textContent = Math.round(pct) + '%';
      var idx = Math.min(Math.floor(pct / 25), tabMsgs.length - 1);
      if (msgEl && msgEl.textContent !== tabMsgs[idx]) msgEl.textContent = tabMsgs[idx];

      // Reposiciona si el sidebar cambió de ancho durante la carga
      positionTab(el);

      // Sólo termina cuando: pasó el mínimo Y el contenido nuevo LLEGÓ Y
      // lleva T_STABLE estable. Así queda sincronizado con la carga real.
      var ready = (elapsed >= T_MIN && contentArrived && sinceMut >= T_STABLE);
      if (ready) {{
        clearInterval(W._ec_tp_iv); W._ec_tp_iv = null;
        try {{ W._ec_tp_obs.disconnect(); }} catch(e){{}} W._ec_tp_obs = null;
        if (bar) bar.style.width = '100%';
        if (pctEl) pctEl.textContent = '100%';
        setTimeout(function(){{
          var e2 = D.getElementById('_ec_tab_preloader');
          if (!e2) return;
          e2.classList.add('fade-out');
          setTimeout(function(){{
            e2.style.display = 'none';
            e2.style.opacity = '1';
            e2.classList.remove('fade-out');
          }}, 450);
        }}, 150);
      }} else if (elapsed > T_HARD) {{
        clearInterval(W._ec_tp_iv); W._ec_tp_iv = null;
        try {{ W._ec_tp_obs.disconnect(); }} catch(e){{}} W._ec_tp_obs = null;
        el.classList.add('fade-out');
        setTimeout(function(){{
          el.style.display = 'none'; el.style.opacity = '1'; el.classList.remove('fade-out');
        }}, 450);
      }}
    }}, 60);
  }}
  W._ec_show_tab_preloader = animateTab;

  // Carga inicial de la pestaña del navegador → preloader oscuro fullscreen.
  try {{
    if (W.sessionStorage.getItem('_ec_pre_initial') !== '1') {{
      W.sessionStorage.setItem('_ec_pre_initial', '1');
      animate(T_TOTAL);
    }}
  }} catch(e) {{ animate(T_TOTAL); }}

  // Click handlers: nav del sidebar → tab preloader blanco;
  // submit de form (login) → fullscreen oscuro.
  if (!D._ec_pre_click_bound) {{
    D._ec_pre_click_bound = true;
    D.addEventListener('click', function(e){{
      var t = e.target;
      if (!t || !t.closest) return;
      var clickedBtn = t.closest('button');
      if (!clickedBtn) return;
      var navWrap = t.closest('[class*="st-key-nav_"]');
      if (navWrap) {{ animateTab(); return; }}
      var inForm = t.closest('form, [data-testid="stForm"]');
      if (inForm && clickedBtn.type !== 'button') {{
        // Si #_usr_header_bar existe estamos en la app autenticada → tab preloader.
        // Si no existe estamos en login → fullscreen oscuro.
        var inApp = !!D.getElementById('_usr_header_bar');
        if (inApp) {{ animateTab(); }} else {{ animate(2200); }}
        return;
      }}
    }}, true);
  }}

  // NOTA: ya NO se usa la CSS variable --sb-w ni ResizeObserver para el
  // ancho del sidebar. Todos los elementos que dependen del ancho (brand,
  // footer, header, FAB, popover) usan el `ancho` ESTÁTICO que Python sabe
  // correcto en cada render + transición CSS (los elementos persisten entre
  // reruns, así la transición anima de viejo a nuevo). Es 100% determinista,
  // sin el JS async que dejaba valores viejos y descuadraba el layout.

}})();
</script>
""", height=0)


def _logo_b64() -> str:
    """Devuelve el logo (logo3.png con fallback a logo2.png/logo.png) como data-URI base64."""
    for path in ["logo3.png", "assets/logo3.png", "images/logo3.png",
                 "logo2.png", "assets/logo2.png", "images/logo2.png",
                 "logo.png", "assets/logo.png", "images/logo.png"]:
        if os.path.exists(path):
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            return f"data:image/png;base64,{b64}"
    return ""


def _logo_dark_b64() -> str:
    """Logo en color oscuro (logo.png) — para preloader de fondo blanco."""
    for path in ["logo.png", "assets/logo.png", "images/logo.png"]:
        if os.path.exists(path):
            b64 = base64.b64encode(open(path, "rb").read()).decode()
            return f"data:image/png;base64,{b64}"
    return ""


def render_page_header(icon_key: str, title: str, subtitle: str) -> None:
    """Plantilla universal de page header (basada en .hdr1 — presupuesto).

    Genera un header con:
    - Gradiente del sidebar (#0f172a → #0b1220)
    - Logo a la derecha (logo3.png)
    - 2 círculos decorativos (::before y ::after)
    - Ícono SVG del sidebar a la izquierda (2.8rem)
    - Título Montserrat 900 / 1.6rem / uppercase / white
    - Subtítulo Montserrat 300 / 0.92rem / rgba(255,255,255,0.65)
    """
    from views.sidebar_nav import page_icon_svg
    st.markdown(
        '<div class="page-hdr">'
        + page_icon_svg(icon_key)
        + '<div class="page-hdr-text">'
        + f'<div class="page-hdr-title">{title}</div>'
        + f'<div class="page-hdr-subtitle">{subtitle}</div>'
        + '</div></div>',
        unsafe_allow_html=True,
    )


def _page_headers_css() -> str:
    """CSS de la plantilla universal `.page-hdr` (basada en .hdr1).

    Reemplaza los headers heredados (.dash-hdr, .hdr1..7, .hdr-*, etc.):
    cualquier tab que aún use clases antiguas también recibe la unificación
    via el bloque de overrides.
    """
    _logo_uri = _logo_b64()
    _bg = "linear-gradient(180deg,#0f172a 0%,#0b1220 100%)"
    if _logo_uri:
        _bg = (
            f"url('{_logo_uri}') right 24px center / 240px 60px no-repeat, "
            f"linear-gradient(180deg,#0f172a 0%,#0b1220 100%)"
        )
    # Headers legacy (clases antiguas) — fuerza misma apariencia que .page-hdr
    _legacy = (
        ".dash-hdr, .hdr-contrato, .hdr-admindata, .hdr1, .hdr2, .hdr3, "
        ".hdr-notif, .hdr-oper, .hdr6, .hdr7, .hdr-3d, .hdr-reporte, "
        ".hdr-salud, .hdr-usr, .excel-header, .hdr-formulario"
    )
    _all = ".page-hdr, " + _legacy
    # Selectores hijos para forzar tipografía
    _title_sel = ", ".join(f"{s} > div > div:first-child" for s in _all.split(", ")) + ", .page-hdr-title"
    _subtitle_sel = ", ".join(f"{s} > div > div:nth-child(2)" for s in _all.split(", ")) + ", .page-hdr-subtitle"
    return (
        "<style>"
        # Caja principal
        f"{_all}{{"
        f"background:{_bg}!important;"
        "border-radius:20px!important;padding:34px 280px 34px 36px!important;"
        "margin-top:0!important;margin-bottom:28px!important;"
        "display:flex!important;align-items:center!important;gap:16px!important;"
        "box-shadow:0 8px 32px rgba(15,23,42,0.35)!important;"
        "position:relative!important;overflow:hidden!important;border:none!important;}"
        # Círculo decorativo 1 (arriba-derecha)
        f"{', '.join(s + '::before' for s in _all.split(', '))}{{"
        "content:''!important;position:absolute!important;top:-40px!important;right:-40px!important;"
        "width:180px!important;height:180px!important;border-radius:50%!important;"
        "background:rgba(255,255,255,0.04)!important;pointer-events:none!important;}"
        # Círculo decorativo 2 (abajo-derecha)
        f"{', '.join(s + '::after' for s in _all.split(', '))}{{"
        "content:''!important;position:absolute!important;bottom:-60px!important;right:80px!important;"
        "width:240px!important;height:240px!important;border-radius:50%!important;"
        "background:rgba(255,255,255,0.03)!important;pointer-events:none!important;}"
        # Tipografía del título
        f"{_title_sel}{{"
        "font-family:'Montserrat',sans-serif!important;font-weight:900!important;"
        "font-size:1.6rem!important;letter-spacing:0.05em!important;"
        "text-transform:uppercase!important;color:#fff!important;line-height:1.1!important;}"
        # Tipografía del subtítulo
        f"{_subtitle_sel}{{"
        "font-family:'Montserrat',sans-serif!important;font-weight:300!important;"
        "font-size:0.92rem!important;color:rgba(255,255,255,0.65)!important;"
        "margin-top:2px!important;line-height:1.2!important;letter-spacing:0.01em!important;"
        "text-transform:none!important;}"
        # Wrapper de texto del page-hdr
        ".page-hdr-text{margin-left:0!important;flex:1!important;min-width:0!important;}"
        "</style>"
    )


# ── Dialog cambio de contraseña ───────────────────────────────────────────────

@st.dialog("🔑 Cambiar contraseña")
def _pwd_dialog():
    nombre = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
    st.markdown(f"<div style='text-align:center;padding:0.5rem 0 1rem;'>"
                f"<div style='font-size:2rem;margin-bottom:6px;'>🔑</div>"
                f"<div style='color:#64748b;font-size:0.82rem;'>Usuario: "
                f"<strong style='color:#1e293b;'>{nombre.upper()}</strong></div></div>",
                unsafe_allow_html=True)
    _, mid, _ = st.columns([0.05, 1, 0.05])
    with mid:
        pwd_actual  = st.text_input("Contraseña actual", type="password", key="pwd_actual_dlg")
        pwd_nueva   = st.text_input("Nueva contraseña", type="password", key="pwd_nueva_dlg", placeholder="Mínimo 6 caracteres")
        pwd_repite  = st.text_input("Repetir nueva contraseña", type="password", key="pwd_repite_dlg")
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
        if st.button("🔐 Actualizar contraseña", key="btn_cambiar_pwd_dlg", use_container_width=True, type="primary"):
            if not pwd_actual or not pwd_nueva or not pwd_repite:
                st.error("Completa todos los campos.")
            elif len(pwd_nueva) < 6:
                st.error("Mínimo 6 caracteres.")
            elif pwd_nueva != pwd_repite:
                st.error("Las contraseñas no coinciden.")
            else:
                _u, _ = login_usuario(st.session_state.get("auth_email", ""), pwd_actual)
                if not _u:
                    st.error("❌ Contraseña actual incorrecta.")
                else:
                    ok, err = cambiar_password_propio(pwd_nueva)
                    if ok:
                        st.success("✅ ¡Contraseña actualizada correctamente!")
                    else:
                        st.error(f"❌ {err}")


# ── Render principal ──────────────────────────────────────────────────────────

def render_layout():
    """
    Inyecta CSS global + header fijo + botones de sesión.
    Llamar UNA VEZ desde app.py después de autenticación.
    """
    # 1. CSS global
    st.markdown(_CSS_GLOBAL, unsafe_allow_html=True)
    # 1b. Unificación de page headers (gradiente sidebar + logo a la derecha)
    st.markdown(_page_headers_css(), unsafe_allow_html=True)

    # 3. Header fijo — badge cotización + usuario
    _nombre    = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
    _rol       = st.session_state.get("rol_usuario", "ejecutivo")
    _cot_num   = st.session_state.get("cotizacion_cargada")

    if _rol == "root":
        # SVG inline: key (root), crown (admin), user (resto)
        _svg_root = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>')
        _svg_admin = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/></svg>')
        _svg_user = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>')
        _rol_html = (f'<span style="color:#f59e0b;font-weight:700;font-size:0.8rem;">{_svg_root}ROOT</span>'
                     f' <span style="color:#e2e8f0;font-size:0.82rem;font-weight:600;">{_nombre.upper()}</span>')
    elif _rol == "admin":
        _svg_admin = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L21.183 5.5a.5.5 0 0 1 .798.519l-2.834 10.246a1 1 0 0 1-.956.734H5.81a1 1 0 0 1-.957-.734L2.02 6.02a.5.5 0 0 1 .798-.519l4.276 3.664a1 1 0 0 0 1.516-.294z"/><path d="M5 21h14"/></svg>')
        _rol_html = (f'<span style="color:#a78bfa;font-weight:700;font-size:0.8rem;">{_svg_admin}ADMIN</span>'
                     f' <span style="color:#e2e8f0;font-size:0.82rem;font-weight:600;">{_nombre.upper()}</span>')
    else:
        _svg_user = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>')
        _rol_html = (f'<span style="color:#94a3b8;font-weight:700;font-size:0.8rem;">{_svg_user}</span>'
                     f' <span style="color:#e2e8f0;font-size:0.82rem;font-weight:600;">{_nombre.upper()}</span>')

    if _cot_num:
        _margen   = st.session_state.get("margen", 0)
        _datos    = bool(st.session_state.get("nombre_input") and st.session_state.get("correo_input"))
        _asesor   = st.session_state.get("asesor_seleccionado", "")
        _ok_asesor = bool(_asesor and _asesor != "Seleccionar asesor")
        _plano    = bool(st.session_state.get("plano_adjunto") or st.session_state.get("pdf_url") or st.session_state.get("plano_nombre"))
        _es_adj   = st.session_state.get("_adj_es_adj", False) and st.session_state.get("_adj_check_ep") == _cot_num
        if _es_adj:
            _badge, _bc, _hc = "🔵 ADJUDICADO", "#2563eb", "#1e3a5f"
        elif _margen > 0 and _datos and _ok_asesor:
            _badge, _bc, _hc = f"🟢 AUTORIZADO{' CON PLANO' if _plano else ''}", "#10b981", "#064e3b"
        elif _datos and _ok_asesor and _plano:
            _badge, _bc, _hc = "🟠 BORRADOR CON PLANO", "#f97316", "#7c2d12"
        elif _datos and _ok_asesor:
            _badge, _bc, _hc = "🟡 BORRADOR", "#eab308", "#713f12"
        else:
            _badge, _bc, _hc = f"🔴 INCOMPLETO{' CON PLANO' if _plano else ''}", "#ef4444", "#7f1d1d"
        _left_html = (
            f'<span id="hdr-badge-estado" data-ep="{_cot_num}" title="Click para copiar {_cot_num}" '
            f'style="font-size:0.88rem;font-weight:700;color:#e2e8f0;cursor:pointer;white-space:nowrap;">'
            f'<span>📝 {_cot_num} •</span>'
            f'<span style="color:{_bc};background:rgba(0,0,0,0.3);padding:4px 14px;'
            f'border-radius:20px;border:1px solid {_bc}55;margin-left:8px;">{_badge}</span>'
            f'</span>'
            f'<button id="_btn_cerrar_hdr" data-action="cerrar-cot" '
            f'style="margin-left:12px;background:rgba(239,68,68,0.15);color:#fca5a5;'
            f'border:1px solid rgba(239,68,68,0.3);border-radius:8px;padding:5px 12px;'
            f'font-size:0.85rem;font-weight:700;cursor:pointer;white-space:nowrap;'
            f'font-family:Montserrat,sans-serif;">🗑️ Cerrar</button>'
        )
        _bg = f"linear-gradient(90deg, {_hc} 0%, #0f172a 65%)"
    else:
        _left_html = '<span style="font-size:0.85rem;font-weight:600;color:#ffffff;">Sin cotización activa</span>'
        _bg = "linear-gradient(90deg, #0f172a 0%, #0f172a 100%)"

    st.markdown(
        f'<style>#_usr_header_bar{{background:{_bg};}}</style>'
        f'<div id="_usr_header_bar">'
        f'<div style="display:flex;align-items:center;gap:4px;flex:1;min-width:0;overflow:hidden;">{_left_html}</div>'
        f'<div class="usr-right">{_rol_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 5. Dialog contraseña
    if st.session_state.get("_show_pwd_dialog"):
        st.session_state["_show_pwd_dialog"] = False
        _pwd_dialog()

    # 6. Botones de sesión (ocultos via CSS, clonados al header por JS)
    _c0, _c_pwd, _c_out = st.columns([20, 1, 1])
    with _c_pwd:
        if st.button("🔑 Mi contraseña", key="btn_pwd_hdr", use_container_width=True):
            st.session_state["_show_pwd_dialog"] = True
            st.rerun()
    with _c_out:
        if st.button("🚪 Cerrar sesión", key="btn_cerrar_sesion_header", use_container_width=True):
            logout_usuario()
            st.session_state["modo_admin"] = False
            st.rerun()

    # 7. JS — mover botones al header una sola vez (sin MutationObserver)
    _components.html("""
<script>
(function(){
    var D = window.parent.document;

    // ── Ocultar elementos nativos de Streamlit via <style> inyectado en el parent ──
    if (!D.getElementById('_ec_hide_native')) {
        var s = D.createElement('style');
        s.id = '_ec_hide_native';
        s.textContent = [
            '[data-testid="stSidebarCollapsedControl"]{display:none!important;visibility:hidden!important;width:0!important;height:0!important;overflow:hidden!important;}',
            '[data-testid="stBottom"]{display:none!important;visibility:hidden!important;width:0!important;height:0!important;overflow:hidden!important;}',
            '[data-testid="stBottomBlockContainer"]{display:none!important;}',
            '[data-testid="stToolbar"]{display:none!important;}',
            '[data-testid="stDecoration"]{display:none!important;}',
            '[data-testid="stStatusWidget"]{display:none!important;}',
            '[data-testid="stHeader"]{display:none!important;height:0!important;min-height:0!important;}',
            'header{visibility:hidden!important;}',
            '#MainMenu{display:none!important;}',
            'footer{display:none!important;}',
            '[data-testid="stTooltipIcon"]{display:none!important;}',
            '.stTooltipIcon{display:none!important;}'
        ].join('');
        D.head.appendChild(s);
    }
    // ── Anclar _sb_bottom al sidebar (Streamlit lo renderiza via portal fuera del sidebar) ──
    function fixSbBottom(){
        var sb = D.querySelector('.st-key-_sb_bottom');
        if(!sb) return;
        var sidebar = D.querySelector('section[data-testid="stSidebar"]');
        if (!sidebar) return;
        var w = sidebar.offsetWidth;
        var collapsed = w <= 120;
        // Limpiar cualquier span custom previo (de versiones anteriores del JS)
        var oldIc = sb.querySelector('._ec_toggle_icon');
        if (oldIc) oldIc.remove();
        sb.style.cssText = 'position:fixed!important;bottom:0!important;left:0!important;width:'+w+'px!important;z-index:6!important;box-sizing:border-box!important;background:#0b1220!important;padding:6px 0 10px 0!important;overflow:hidden!important;';
        var wrappers = sb.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stVerticalBlock"]');
        wrappers.forEach(function(el){el.style.background='transparent';el.style.border='none';el.style.boxShadow='none';el.style.padding='0';el.style.margin='0';el.style.width='100%';});
        // Centrar el botón toggle dentro del _sb_bottom. La CSS de _build_css()
        // renderiza el ícono SVG vía ::before, solo necesitamos asegurar que el
        // button llene la columna y use flex centering.
        var tg = sb.querySelector('.st-key-_sb_toggle');
        if (tg) {
            tg.style.cssText = 'width:100%!important;padding:0!important;margin:0!important;display:block!important;';
            var stBtn = tg.querySelector('.stButton');
            if (stBtn) stBtn.style.cssText = 'width:100%!important;padding:0!important;margin:0!important;display:flex!important;align-items:center!important;justify-content:center!important;';
            var btn = tg.querySelector('button');
            if (btn) {
                // Asegurar visibilidad de los hijos originales (puede haber estado oculto por versiones previas)
                btn.querySelectorAll(':scope > *').forEach(function(c){ c.style.display=''; });
                if (collapsed) {
                    btn.style.cssText = 'width:100%!important;height:48px!important;padding:0!important;margin:0!important;background:transparent!important;border:none!important;box-shadow:none!important;outline:none!important;color:transparent!important;display:flex!important;align-items:center!important;justify-content:center!important;';
                } else {
                    btn.style.cssText = '';
                }
            }
        }
    }
    // ── Centrar items de navegación del sidebar colapsado ──
    function fixSbNav(){
        var sidebar = D.querySelector('section[data-testid="stSidebar"]');
        if (!sidebar) return;
        var w = sidebar.offsetWidth;
        // Solo aplica en colapsado (76px). En expandido (256px) dejamos el layout original.
        if (w > 120) return;
        // Forzar contenedores intermedios a width 100% sin padding para que .stButton llene la columna
        var navWrap = D.querySelector('.st-key-_sb_nav');
        if (navWrap) {
            navWrap.style.padding = '0';
            navWrap.style.margin = '0';
            navWrap.style.width = '100%';
            navWrap.querySelectorAll('[data-testid="stVerticalBlockBorderWrapper"],[data-testid="stVerticalBlock"]').forEach(function(el){
                el.style.padding = '0';
                el.style.margin = '0';
                el.style.width = '100%';
            });
            navWrap.querySelectorAll('[data-testid="stElementContainer"]').forEach(function(el){
                el.style.padding = '0';
                el.style.margin = '0';
                el.style.width = '100%';
                el.style.display = 'block';
            });
            navWrap.querySelectorAll('.stButton').forEach(function(el){
                el.style.padding = '0';
                el.style.margin = '0';
                el.style.width = '100%';
                el.style.display = 'block';
                el.style.boxSizing = 'border-box';
            });
        }
    }
    fixSbBottom();
    fixSbNav();
    setTimeout(function(){fixSbBottom();fixSbNav();},200);
    setTimeout(function(){fixSbBottom();fixSbNav();},600);
    setTimeout(function(){fixSbBottom();fixSbNav();},1500);
    setTimeout(function(){fixSbBottom();fixSbNav();},3000);
    // ResizeObserver: re-sincronizar width de _sb_bottom cuando la sidebar transiciona
    if (!D._ecSbResizeObs) {
        var sidebarForObs = D.querySelector('section[data-testid="stSidebar"]');
        if (sidebarForObs && window.ResizeObserver) {
            D._ecSbResizeObs = new ResizeObserver(function(){ fixSbBottom(); fixSbNav(); });
            D._ecSbResizeObs.observe(sidebarForObs);
        }
    }
    // Ocultar elementos nativos de Streamlit que sobran
    function nukeUnwanted(){
        D.querySelectorAll('[data-testid="stSidebarCollapsedControl"]').forEach(function(el){el.remove();});
        fixSbBottom();
        fixSbNav();
    }
    nukeUnwanted();
    if(!D._ecNukeObs){
        D._ecNukeObs=new MutationObserver(function(){setTimeout(nukeUnwanted,50);});
        D._ecNukeObs.observe(D.body,{childList:true,subtree:true});
    }

    function moveButtons() {
        var bar = D.getElementById('_usr_header_bar');
        if (!bar) return false;
        if (bar.querySelector('._hdr_btns')) return true;
        var usrRight = bar.querySelector('.usr-right');
        if (!usrRight) return false;

        // Buscar por clase .st-key-* (robusto): innerText devuelve '' en botones
        // ocultos con visibility:hidden/height:0, por eso fallaba la búsqueda.
        var btnPwd = D.querySelector('.st-key-btn_pwd_hdr button');
        var btnOut = D.querySelector('.st-key-btn_cerrar_sesion_header button');
        if (!btnPwd || !btnOut) return false;

        var S = 'background:rgba(255,255,255,0.08)!important;color:#fff!important;border:1px solid rgba(255,255,255,0.25)!important;border-radius:6px!important;padding:4px 12px!important;font-size:0.82rem!important;font-weight:600!important;cursor:pointer!important;white-space:nowrap!important;font-family:inherit!important;transition:background 0.2s!important;';
        var wrap = D.createElement('div');
        wrap.className = '_hdr_btns';
        wrap.style.cssText = 'display:flex;align-items:center;gap:6px;margin-left:12px;';

        // SVG inline (estilo Lucide) en lugar de emoticones
        var _svgKey = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>';
        var _svgOut = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>';
        var _btnInner = 'display:inline-flex!important;align-items:center!important;gap:6px!important;';

        var cp = D.createElement('button');
        cp.innerHTML = _svgKey + '<span>Mi contraseña</span>';
        cp.style.cssText = S + _btnInner;
        cp.onclick = function(e){ e.preventDefault(); e.stopPropagation(); btnPwd.click(); };

        var co = D.createElement('button');
        co.innerHTML = _svgOut + '<span>Cerrar sesión</span>';
        co.style.cssText = S + _btnInner + 'background:rgba(239,68,68,0.2)!important;border-color:rgba(239,68,68,0.45)!important;';
        co.onclick = function(e){ e.preventDefault(); e.stopPropagation(); btnOut.click(); };

        wrap.appendChild(cp);
        wrap.appendChild(co);
        usrRight.appendChild(wrap);
        return true;
    }

    function tryMove(attempts) {
        if (attempts <= 0) return;
        if (!moveButtons()) {
            setTimeout(function(){ tryMove(attempts - 1); }, 600);
        }
    }
    tryMove(20);

    // ── Badge de estado: copiar EP al click + botón Cerrar -> botón oculto ──
    if (!D._ecHdrActionsBound) {
        D._ecHdrActionsBound = true;
        D.addEventListener('click', function(e){
            var t = e.target;
            // Copiar código de acceso (sidebar) al hacer click
            var codEl = t && t.closest ? t.closest('.ec-copy-code') : null;
            if (codEl) {
                var code = codEl.getAttribute('data-ec-copy') || '';
                if (code) {
                    try {
                        var tc = D.createElement('textarea'); tc.value = code;
                        tc.style.cssText = 'position:fixed;top:-9999px;left:-9999px;';
                        D.body.appendChild(tc); tc.focus(); tc.select();
                        try { D.execCommand('copy'); } catch(_e){}
                        tc.remove();
                    } catch(_e2){}
                    if (window.parent.navigator && window.parent.navigator.clipboard) {
                        window.parent.navigator.clipboard.writeText(code).catch(function(){});
                    }
                    // Feedback: flash de fondo verde + tooltip
                    var prevBg = codEl.style.background;
                    codEl.style.background = 'rgba(34,197,94,0.25)';
                    var oldTitle = codEl.getAttribute('title');
                    codEl.setAttribute('title', '¡Copiado!');
                    setTimeout(function(){
                        codEl.style.background = prevBg;
                        if (oldTitle) codEl.setAttribute('title', oldTitle);
                    }, 900);
                }
                return;
            }
            // Copiar EP
            var badge = t && t.closest ? t.closest('#hdr-badge-estado') : null;
            if (badge) {
                var ep = badge.getAttribute('data-ep') || '';
                if (ep) {
                    try {
                        var ta = D.createElement('textarea'); ta.value = ep;
                        ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px;';
                        D.body.appendChild(ta); ta.focus(); ta.select();
                        try { D.execCommand('copy'); } catch(_e){}
                        ta.remove();
                    } catch(_e2){}
                    if (window.parent.navigator && window.parent.navigator.clipboard) {
                        window.parent.navigator.clipboard.writeText(ep).catch(function(){});
                    }
                    var inner = badge.querySelector('span');
                    if (inner) {
                        var orig = inner.textContent;
                        inner.textContent = '✅ ¡Copiado!';
                        setTimeout(function(){ inner.textContent = orig; }, 1000);
                    }
                }
                return;
            }
            // Cerrar cotización -> click en el botón oculto de Streamlit (por clase)
            var cerrar = t && t.closest ? t.closest('#_btn_cerrar_hdr') : null;
            if (cerrar) {
                if (cerrar._ec_busy) return;   // evita disparos múltiples mientras procesa
                cerrar._ec_busy = true;
                cerrar.textContent = '⏳ Cerrando...';
                cerrar.style.opacity = '0.7';
                cerrar.style.pointerEvents = 'none';
                var hb = D.querySelector('.st-key-btn_cerrar_cotizacion button');
                if (hb) hb.click();
            }
        });
    }

    // ── Flechas de navegación de pestañas (scroll del tab-list) ──
    function initTabArrows() {
        D.querySelectorAll('.tab-nav-arrow').forEach(function(e){ e.remove(); });
        var tablist = D.querySelector('[data-baseweb="tab-list"]');
        if (!tablist) return;
        var wrap = tablist.parentElement;
        if (!wrap) return;
        wrap.style.position = 'relative';
        function makeArrow(dir) {
            var btn = D.createElement('button');
            btn.className = 'tab-nav-arrow';
            btn.innerHTML = dir === 'left' ? '&#8249;' : '&#8250;';
            btn.style.cssText = [
                'position:absolute;top:0;z-index:99;',
                'background:linear-gradient(' + (dir==='left'?'90':'270') + 'deg,rgba(255,255,255,0.97) 55%,rgba(255,255,255,0))',
                ';border:none;cursor:pointer;padding:0 14px;height:100%;',
                'font-size:1.4rem;font-weight:700;color:#5b7cfa;',
                dir==='left' ? 'left:0;' : 'right:0;'
            ].join('');
            btn.addEventListener('click', function(){
                tablist.scrollBy({ left: dir==='left' ? -160 : 160, behavior:'smooth' });
            });
            return btn;
        }
        var btnL = makeArrow('left');
        var btnR = makeArrow('right');
        wrap.appendChild(btnL);
        wrap.appendChild(btnR);
        function updateArrows() {
            var sl = tablist.scrollLeft;
            var maxScroll = tablist.scrollWidth - tablist.clientWidth;
            btnL.style.opacity = sl > 5 ? '1' : '0';
            btnL.style.pointerEvents = sl > 5 ? 'auto' : 'none';
            btnR.style.opacity = sl < maxScroll - 5 ? '1' : '0';
            btnR.style.pointerEvents = sl < maxScroll - 5 ? 'auto' : 'none';
        }
        tablist.addEventListener('scroll', updateArrows);
        updateArrows();
    }
    setTimeout(initTabArrows, 700);
    setTimeout(initTabArrows, 1600);
    if (!D._ecTabArrowsBound) {
        D._ecTabArrowsBound = true;
        D.addEventListener('click', function(e){
            if (e.target && e.target.getAttribute && e.target.getAttribute('data-baseweb') === 'tab') {
                setTimeout(initTabArrows, 300);
                setTimeout(moveButtons, 300);   // restaura pwd/logout si se perdieron
            }
        });
    }
})();
</script>
""", height=0)
