"""
Vista pública del formulario de materiales para clientes.
Acceso: ?cliente=1, autenticado con RUT + código EP.
"""
import base64
import os
import re

import streamlit as st
import streamlit.components.v1 as components

from components.html_formulario_cliente import build_formulario_cliente_html

_CSS_CLIENTE = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;900&display=swap');
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{display:none!important;}
.stAppHeader,.st-emotion-cache-xi6p3a,[data-testid="stAppHeader"]{display:none!important;height:0!important;}
.stMainBlockContainer,.block-container,.st-emotion-cache-1ibsh2c{padding-top:0!important;margin-top:0!important;}
/* Fondo opaco en TODOS los wrappers para que nunca se transparente el formulario.
   Usamos background-color (no shorthand background) para no romper otras props. */
html,body{background-color:#f0f4f8 !important;}
.stApp,[data-testid="stApp"]{background-color:#f0f4f8 !important;}
[data-testid="stAppViewContainer"]{background-color:#f0f4f8 !important;}
[data-testid="stMain"],[data-testid="stMainBlockContainer"]{background-color:#f0f4f8 !important;}
.block-container,div[data-testid="stVerticalBlock"]{background-color:transparent !important;}
iframe{border:none !important;background-color:#f0f4f8 !important;}
[data-testid="stCustomComponentV1"],[data-testid="stIFrame"],[data-testid="element-container"]{background-color:#f0f4f8 !important;border-radius:0 !important;box-shadow:none !important;}
"""

_RESIZE_JS = (
    '<script>window.onload=function(){'
    'var h=document.body.scrollHeight;'
    'window.parent.postMessage({type:"streamlit:setFrameHeight",height:h},"*");'
    'setTimeout(function(){'
    'var h2=document.body.scrollHeight;'
    'window.parent.postMessage({type:"streamlit:setFrameHeight",height:h2},"*");'
    '},600);};</script>'
)


def _cargar_logo_b64() -> str:
    for path in ["logo3.png", "assets/logo3.png", "images/logo3.png"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""


def _cargar_hero_b64() -> str:
    for path in ["hero.jpeg", "hero.jpg", "assets/hero.jpeg", "assets/hero.jpg"]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    return ""


def _init_cliente_state() -> None:
    for key, val in {
        '_cliente_ok':       False,
        '_cliente_ep':       '',
        '_cliente_nombre':   '',
        '_cliente_proyecto': '',
    }.items():
        if key not in st.session_state:
            st.session_state[key] = val


def _render_login_cliente(logo_b64: str, supabase_admin) -> None:
    """Pantalla de acceso con video background."""
    video_b64 = ""
    for vp in ["hero_video.mp4", "assets/hero_video.mp4"]:
        if os.path.exists(vp):
            with open(vp, "rb") as vf:
                video_b64 = base64.b64encode(vf.read()).decode()
            break

    vtag = (
        f'<video autoplay muted loop playsinline src="data:video/mp4;base64,{video_b64}" '
        'style="position:fixed;top:0;left:0;width:100%;height:100%;object-fit:cover;z-index:0;"></video>'
        if video_b64 else ''
    )
    logo_link = (
        f'<a href="https://espaciocontainerhouse.cl/" target="_blank">'
        f'<img src="data:image/png;base64,{logo_b64}" style="height:58px;width:auto;"></a>'
        if logo_b64 else ''
    )

    st.markdown(f"""
    {vtag}
    <div style="position:fixed;top:0;left:0;width:100%;height:100%;
        background:linear-gradient(135deg,rgba(5,10,20,0.55),rgba(10,22,50,0.40));
        z-index:1;pointer-events:none;"></div>
    <div style="position:fixed;top:16px;right:20px;z-index:100;">{logo_link}</div>
    <div style="position:fixed;top:25%;left:50%;transform:translate(-50%,-50%);
        z-index:5;text-align:center;width:100%;padding:0 20px;pointer-events:none;">
        <div style="display:inline-block;background:rgba(255,255,255,0.15);
            border:1px solid rgba(255,255,255,0.3);color:white;border-radius:99px;
            padding:5px 18px;font-size:0.68rem;font-weight:700;letter-spacing:0.12em;
            text-transform:uppercase;margin-bottom:14px;font-family:Poppins,sans-serif;">
            ✦ Portal de Materiales
        </div>
        <div style="font-size:2.8rem;font-weight:900;color:white;line-height:1.15;
            margin-bottom:12px;text-shadow:0 2px 24px rgba(0,0,0,0.4);font-family:Poppins,sans-serif;">
            Tu casa,<br>tus materiales 🏡</div>
        <div style="font-size:0.95rem;color:rgba(255,255,255,0.8);max-width:380px;
            margin:0 auto;line-height:1.6;font-family:Poppins,sans-serif;">
            Ingresa tus datos para acceder a tu formulario personalizado de selección de materiales.
        </div>
    </div>
    <style>
    html,body,.stApp{{background:transparent!important;}}
    .stMainBlockContainer{{background:transparent!important;padding-top:0!important;}}
    .block-container{{background:transparent!important;}}
    section[data-testid="stMain"]{{background:transparent!important;}}
    section[data-testid="stMain"] > div{{position:relative;z-index:10;}}
    div[data-testid="stVerticalBlock"]{{background:transparent!important;}}
    div[data-testid="stTextInput"] label,
    div[data-testid="stTextInput"] label p{{color:white!important;text-shadow:0 1px 4px rgba(0,0,0,0.5)!important;}}
    div[data-testid="stTextInput"] > div{{background:transparent!important;}}
    div[data-testid="stTextInput"] input{{background:white!important;opacity:1!important;color:#1e293b!important;}}
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div style='height:36vh;'></div>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 2, 1])
    with col:
        rut_inp = st.text_input("RUT", placeholder="12.345.678-9", key="cli_rut")
        ep_inp  = st.text_input("Código de presupuesto", placeholder="EP-12345", key="cli_ep")
        if st.button("Ingresar a mi formulario →", type="primary",
                     use_container_width=True, key="cli_login"):
            rut_clean = re.sub(r'[^0-9kK]', '', rut_inp.strip()).upper()
            ep_clean  = ep_inp.strip().upper()
            if not rut_clean or not ep_clean:
                st.error("Ingresa tu RUT y código de presupuesto.")
            else:
                try:
                    check = supabase_admin.table('cotizaciones').select(
                        'numero,cliente_nombre,cliente_rut,proyecto_observaciones'
                    ).eq('numero', ep_clean).execute()
                    if check.data:
                        row = check.data[0]
                        rut_db = re.sub(r'[^0-9kK]', '', (row.get('cliente_rut') or '')).upper()
                        if rut_db == rut_clean:
                            st.session_state._cliente_ep       = ep_clean
                            st.session_state._cliente_ok       = True
                            st.session_state._cliente_nombre   = row.get('cliente_nombre', '')
                            st.session_state._cliente_proyecto = row.get('proyecto_observaciones', '')
                            st.rerun()
                        else:
                            st.error("RUT o código incorrecto. Verifica tus datos.")
                    else:
                        st.error("Código de presupuesto no encontrado.")
                except Exception as ce:
                    st.error(f"Error de conexión: {ce}")


def _render_formulario_cliente(supabase_admin, supa_url: str, supa_key: str) -> None:
    # Re-asegurar fondos opacos por si quedaron estilos transparent del login.
    st.markdown("""
    <style>
    html,body,.stApp,[data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],[data-testid="stMainBlockContainer"]{
        background-color:#f0f4f8 !important;
        background-image:none !important;
    }
    [data-testid="stCustomComponentV1"],[data-testid="stIFrame"]{
        background-color:#f0f4f8 !important;
    }
    iframe{background-color:#f0f4f8 !important;}
    </style>
    """, unsafe_allow_html=True)

    ep       = st.session_state._cliente_ep
    nombre   = st.session_state._cliente_nombre
    primer_n = nombre.split()[0].capitalize() if nombre else "Cliente"

    try:
        cat = supabase_admin.table('catalogo_materiales').select('*').eq('activo', True)\
            .order('categoria').order('orden_grupo').order('titulo_grupo').order('nombre')\
            .execute().data or []
    except Exception:
        cat = []

    try:
        cfg = supabase_admin.table('formulario_config').select('*')\
            .eq('cotizacion_numero', ep).order('orden').execute().data or []
    except Exception:
        cfg = []

    if not cfg:
        st.markdown(f"""
        <div style='max-width:560px;margin:60px auto;text-align:center;font-family:Poppins,sans-serif;'>
          <div style='font-size:3rem;margin-bottom:16px;'>📋</div>
          <div style='font-size:1.4rem;font-weight:900;color:#0a1628;margin-bottom:8px;'>
            Hola {primer_n}, ¡ya casi!</div>
          <div style='color:#64748b;font-size:0.95rem;line-height:1.6;'>
            Tu formulario está siendo preparado. ¡La espera va a valer la pena! 🏡</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        try:
            resps_db  = supabase_admin.table('formulario_respuestas').select('*')\
                .eq('cotizacion_numero', ep).execute().data or []
            resps_map = {r.get('item_id') or r.get('pregunta_id', ''): r['respuesta'] for r in resps_db}
        except Exception:
            resps_map = {}

        logo_b64 = _cargar_logo_b64()
        hero_b64 = _cargar_hero_b64()
        form_html = build_formulario_cliente_html(
            cat, cfg, resps_map, supa_url, supa_key,
            ep, nombre, logo_b64, hero_b64=hero_b64,
        )
        form_html = form_html.replace('</body>', _RESIZE_JS + '</body>')
        form_height = max(1200, len(cfg) * 450)
        components.html(form_html, height=form_height, scrolling=False)

    if st.button("← Salir", key="cli_logout"):
        for k in ['_cliente_ep', '_cliente_ok', '_cliente_nombre', '_cliente_proyecto']:
            st.session_state.pop(k, None)
        st.rerun()


def render_cliente_view(supabase_admin, supa_url: str, supa_key: str) -> None:
    """
    Punto de entrada de la vista pública del cliente.
    Llama st.stop() al terminar (siempre es una vista completa).
    """
    _init_cliente_state()

    st.markdown(f"<style>{_CSS_CLIENTE}</style>", unsafe_allow_html=True)
    logo_b64 = _cargar_logo_b64()

    if not st.session_state._cliente_ok:
        _render_login_cliente(logo_b64, supabase_admin)
    else:
        _render_formulario_cliente(supabase_admin, supa_url, supa_key)

    st.stop()
