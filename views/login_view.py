"""
Pantalla de login del sistema interno (ejecutivos, admin, root).
Rate limiting: 5 intentos → bloqueo 5 min.
"""
import base64
import os
import time

import streamlit as st

from auth.roles import get_rol
from auth.access_code import validar_codigo_acceso
from repositories.logs_repo import registrar_log
from utils.security import (
    login_rate_limit, registrar_login_fallido, registrar_login_bloqueado,
    analizar_inputs,
)


_CSS_LOGIN = """
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;700;900&display=swap');

/* Fondo: VIDEO en vez de negro (mismo hero_video.mp4 de la página del cliente).
   El video va detrás de TODO con z-index negativo; el body oscuro queda de
   respaldo por si el video no carga. Solo se cambia el fondo — el resto del
   login (inputs, botón, logo) queda idéntico. */
html, body { background: #0a0a0a !important; }
[data-testid="stApp"], [data-testid="stAppViewContainer"],
[data-testid="stMain"], .block-container { background: transparent !important; }
.login-video {
    position:fixed; inset:0; width:100%; height:100%;
    object-fit:cover; z-index:-2;
}
.login-overlay {
    position:fixed; inset:0; z-index:-1; pointer-events:none;
    background:linear-gradient(135deg, rgba(6,10,18,0.66) 0%, rgba(8,14,28,0.78) 100%);
}
[data-testid="stHeader"]     { display:none !important; }
[data-testid="stToolbar"]    { display:none !important; }
[data-testid="stDecoration"] { display:none !important; }
.stDeployButton              { display:none !important; }
#MainMenu                    { display:none !important; }
footer                       { display:none !important; }
[data-testid="stNotificationActionButton"] { display:none !important; }
div[class*='ErrorBoundary']  { display:none !important; }
section[data-testid='stException'] { display:none !important; }

[data-testid="stAppViewContainer"]::before {
    content:''; position:fixed; top:0; left:0; right:0; height:1px;
    background: rgba(255,255,255,0.15); z-index:9999;
}

.login-divider { height:1px; margin:20px 0; background: rgba(255,255,255,0.08); }

div[data-testid="stTextInput"] label,
div[data-testid="stTextInput"] label p {
    color: rgba(255,255,255,0.4) !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.14em !important;
    text-transform: uppercase !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 400 !important;
}
/* INPUTS estilo GLASS (igual que la página del cliente): el campo completo
   —incluido el ícono de ver contraseña— flota sobre vidrio translúcido. */
div[data-testid="stTextInput"] > div,
div[data-testid="stTextInput"] > div > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
div[data-testid="stTextInput"] > div > div {
    background: rgba(255,255,255,0.12) !important;
    -webkit-backdrop-filter: blur(6px) !important;
    backdrop-filter: blur(6px) !important;
    border: 1px solid rgba(255,255,255,0.28) !important;
    border-radius: 11px !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.18) !important;
    transition: border-color .18s, box-shadow .18s, background .18s !important;
}
div[data-testid="stTextInput"] > div > div:focus-within {
    border-color: rgba(255,255,255,0.60) !important;
    background: rgba(255,255,255,0.18) !important;
    box-shadow: 0 0 0 3px rgba(255,255,255,0.15), 0 4px 12px rgba(0,0,0,0.18) !important;
}
div[data-testid="stTextInput"] input {
    background: transparent !important;
    color: #ffffff !important;
    font-size: 0.93rem !important;
    font-family: 'Montserrat', sans-serif !important;
    font-weight: 500 !important;
    caret-color: #ffffff !important;
}
div[data-testid="stTextInput"] input::placeholder { color: rgba(255,255,255,0.55) !important; }
/* Ícono ver/ocultar contraseña en claro, visible sobre el glass */
div[data-testid="stTextInput"] [data-baseweb="input"] button { background: transparent !important; }
div[data-testid="stTextInput"] [data-baseweb="input"] button svg {
    fill: rgba(255,255,255,0.75) !important; color: rgba(255,255,255,0.75) !important;
}

/* BOTÓN estilo GLASS (mismo lenguaje vidrioso que los inputs) */
div[data-testid="stButton"] > button,
div[data-testid="stButton"] > button[kind="primary"] {
    background: rgba(255,255,255,0.12) !important;
    -webkit-backdrop-filter: blur(8px) !important;
    backdrop-filter: blur(8px) !important;
    color: #ffffff !important;
    border: 1px solid rgba(255,255,255,0.30) !important;
    border-radius: 12px !important;
    font-weight: 700 !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.22em !important;
    text-transform: uppercase !important;
    font-family: 'Montserrat', sans-serif !important;
    padding: 0.85rem !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.28) !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] > button:hover,
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: rgba(255,255,255,0.20) !important;
    border-color: rgba(255,255,255,0.50) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 12px 30px rgba(0,0,0,0.35) !important;
    color: #ffffff !important;
}
div[data-testid="stButton"] > button:active,
div[data-testid="stButton"] > button[kind="primary"]:active {
    transform: translateY(0) !important;
    box-shadow: 0 4px 14px rgba(0,0,0,0.30) !important;
}
"""


def _cargar_logo_b64() -> str:
    for path in ["logo3.png", "assets/logo3.png", "images/logo3.png"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""


@st.cache_data(show_spinner=False)
def _cargar_video_b64() -> str:
    """Video de fondo (mismo `hero_video.mp4` que usa la página del cliente).
    Cacheado para no releer/reencodear los ~2 MB en cada rerun del login."""
    for path in ["hero_video.mp4", "assets/hero_video.mp4"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""


def render_login(login_usuario_fn) -> None:
    """
    Renderiza la pantalla de login.
    login_usuario_fn(email, password) -> (user | None, error_str | None)
    Llama st.stop() si el usuario no está autenticado.
    """
    logo_b64 = _cargar_logo_b64()

    st.markdown(f"<style>{_CSS_LOGIN}</style>", unsafe_allow_html=True)

    # Video de fondo (detrás de todo, z-index negativo). Si no hay video, el body
    # oscuro de respaldo deja el login igual que antes.
    video_b64 = _cargar_video_b64()
    if video_b64:
        st.markdown(
            f'<video class="login-video" autoplay muted loop playsinline '
            f'src="data:video/mp4;base64,{video_b64}"></video>'
            '<div class="login-overlay"></div>',
            unsafe_allow_html=True,
        )

    # Aviso de sesión expirada por inactividad (viene de check_session_timeout,
    # que recarga a ?expired=1 para montar el login limpio).
    if st.query_params.get("expired") == "1":
        st.warning("⏱️ Tu sesión expiró por inactividad. Por favor inicia sesión nuevamente.")

    if logo_b64:
        st.markdown(
            f'<style>.login-logo-wrap img{{width:750px!important;max-width:100%!important;'
            f'display:block!important;margin:0 auto!important;}}</style>'
            f'<div class="login-logo-wrap">'
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="width:750px;max-width:100%;display:block;margin:0 auto 8px;'
            f'filter:drop-shadow(0 2px 16px rgba(255,255,255,0.08));"></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="text-align:center;margin-bottom:20px;color:white;font-size:3rem;">🧊</div>',
                    unsafe_allow_html=True)

    st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
    st.markdown('<div class="login-divider"></div>', unsafe_allow_html=True)
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

    _, _mc, _ = st.columns([1.5, 1, 1.5])
    with _mc:
        email_in = st.text_input("Correo electrónico", key="login_email", placeholder="usuario@empresa.cl")
        pass_in  = st.text_input("Contraseña", type="password", key="login_pass", placeholder="••••••••")
        code_in  = st.text_input("Código de acceso", key="login_code",
                                  placeholder="Solicítalo al administrador", max_chars=6)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        now = time.time()
        attempts      = st.session_state.get('_login_attempts', 0)
        blocked_until = st.session_state.get('_login_blocked_until', 0)
        is_blocked    = now < blocked_until

        if is_blocked:
            wait = int(blocked_until - now)
            st.error(f"🔒 Demasiados intentos fallidos. Espera {wait} segundos.")

        if st.button("⚡ Ingresar al sistema", use_container_width=True,
                     type="primary", key="btn_login", disabled=is_blocked):
            _email_norm = (email_in or "").strip().lower()
            # Escaneo del input: un email/código con XSS o SQLi es intento de ataque.
            _peligro, _ = analizar_inputs(
                {'email': email_in, 'codigo': code_in}, email=_email_norm, contexto='login')
            # Rate limiting SERVER-SIDE (no evadible por nueva pestaña): cuenta los
            # fallos recientes de este email en la base, no solo en la sesión.
            _srv_blocked, _srv_intentos = login_rate_limit(_email_norm)
            if _peligro:
                st.error("🚫 Entrada no válida. El intento fue registrado.")
            elif _srv_blocked:
                registrar_login_bloqueado(_email_norm, _srv_intentos)
                st.error("🔒 Demasiados intentos fallidos para esta cuenta. Espera unos minutos.")
            elif not email_in or not pass_in:
                st.error("Completa correo y contraseña.")
            else:
                with st.spinner("Verificando..."):
                    user, err = login_usuario_fn(email_in.strip(), pass_in)

                if user:
                    _meta  = user.user_metadata or {}
                    rol    = get_rol(user.email, _meta)
                    requiere_codigo = rol in ("ejecutivo", "operacion")
                    if requiere_codigo and not validar_codigo_acceso(code_in):
                        st.error("🔐 Código de acceso incorrecto. Solicítalo al administrador.")
                    else:
                        st.session_state.auth_user    = str(user.id)
                        st.session_state.auth_email   = user.email or email_in.strip()
                        st.session_state.auth_nombre  = _meta.get("nombre", user.email or "")
                        st.session_state.rol_usuario  = rol
                        st.session_state.es_supervisor = rol in ("root", "admin")
                        st.session_state.es_root       = rol == "root"
                        st.session_state.es_operacion  = rol == "operacion"
                        if st.session_state.es_supervisor:
                            st.session_state.modo_admin = True
                        st.session_state.pop('resultados_busqueda', None)
                        st.session_state['_login_attempts']      = 0
                        st.session_state['_login_blocked_until'] = 0
                        st.session_state.pop('_usuarios_cache', None)
                        st.rerun()
                else:
                    attempts += 1
                    st.session_state['_login_attempts'] = attempts
                    # Log server-side (para auditoría + rate limiting por email).
                    registrar_login_fallido(_email_norm, attempts)
                    if attempts >= 5:
                        st.session_state['_login_blocked_until'] = now + 300
                        st.session_state['_login_attempts']      = 0
                        st.error("🔒 Demasiados intentos. Bloqueado por 5 minutos.")
                    elif "Invalid login" in str(err) or "invalid_credentials" in str(err):
                        remaining = 5 - attempts
                        st.error(f"❌ Correo o contraseña incorrectos. {remaining} intento(s) restante(s).")
                    elif "Email not confirmed" in str(err):
                        st.error("❌ Cuenta no confirmada. Contacta al administrador.")
                    else:
                        st.error(f"❌ {err}")

        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;color:rgba(255,255,255,0.15);font-size:0.65rem;'
            'letter-spacing:0.2em;text-transform:uppercase;font-family:\'Montserrat\',sans-serif;'
            'font-weight:300;margin-top:8px;">Sistema de gestión · Uso interno</div>',
            unsafe_allow_html=True,
        )

    st.stop()
