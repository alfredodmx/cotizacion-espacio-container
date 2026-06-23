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
    """Pantalla de acceso: video background + glass card central con título y form."""
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
        f'<img src="data:image/png;base64,{logo_b64}" style="height:54px;width:auto;display:block;">'
        f'</a>'
        if logo_b64 else ''
    )

    st.markdown(f"""
    {vtag}
    <div class="cli-overlay"></div>
    <div class="cli-logo-wrap">{logo_link}</div>

    <style>
    /* Reset de fondos de Streamlit para que se vea el video */
    html,body,.stApp{{background:transparent!important;}}
    .stMainBlockContainer{{background:transparent!important;padding-top:0!important;}}
    .block-container{{background:transparent!important;padding-top:0!important;}}
    section[data-testid="stMain"]{{background:transparent!important;}}
    section[data-testid="stMain"] > div{{position:relative;z-index:10;}}
    div[data-testid="stVerticalBlock"]{{background:transparent!important;}}
    [data-testid="stApp"],[data-testid="stAppViewContainer"]{{background:transparent!important;}}

    /* Overlay sutil sobre el video para mejor contraste */
    .cli-overlay {{
        position:fixed;inset:0;
        background:linear-gradient(135deg,rgba(5,10,20,0.45) 0%,rgba(10,22,50,0.55) 100%);
        z-index:1;pointer-events:none;
    }}

    /* Logo arriba a la derecha, con sombra fuerte para que flote sobre el video */
    .cli-logo-wrap {{
        position:fixed;top:18px;right:22px;z-index:100;
        filter:drop-shadow(0 6px 22px rgba(0,0,0,0.55)) drop-shadow(0 2px 6px rgba(0,0,0,0.35));
    }}

    /* CARD CENTRAL — sólida blanca con sombra fuerte para que "flote" sobre el video.
       st.container(key=) crea un wrapper st-key-X que contiene
       stVerticalBlockBorderWrapper > stVerticalBlock. Aplicamos el bg al
       wrapper Y al stVerticalBlock interno porque la regla global de
       arriba lo pone transparente. */
    @keyframes cli_card_in {{
        from {{ opacity:0; transform:translateY(14px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}
    .st-key-cli_login_card,
    .st-key-cli_login_card > div,
    .st-key-cli_login_card > div > div,
    .st-key-cli_login_card div[data-testid="stVerticalBlockBorderWrapper"],
    .st-key-cli_login_card div[data-testid="stVerticalBlock"] {{
        background-color:#ffffff !important;
        background-image:none !important;
    }}
    .st-key-cli_login_card {{
        border-radius:24px !important;
        padding:38px 34px 30px !important;
        box-shadow:0 30px 80px rgba(5,10,20,0.55),0 12px 32px rgba(5,10,20,0.30) !important;
        border:1px solid rgba(255,255,255,0.6) !important;
        animation:cli_card_in 0.55s cubic-bezier(0.16,1,0.3,1) both !important;
        overflow:hidden !important;
        position:relative !important;
        z-index:50 !important;  /* sobre cli-overlay (z=1) */
    }}
    /* La columna que contiene la card también necesita stacking context */
    [data-testid="stColumn"]:has(.st-key-cli_login_card) {{
        position:relative !important;
        z-index:50 !important;
    }}

    /* Bloque título dentro de la card */
    .cli-title-block {{
        text-align:center;margin-bottom:22px;font-family:Poppins,sans-serif;
    }}
    .cli-badge {{
        display:inline-block;
        background:linear-gradient(135deg,#0f3460,#1a5276);
        color:white !important;border-radius:99px;padding:5px 16px;
        font-size:0.62rem;font-weight:800;letter-spacing:0.14em;
        text-transform:uppercase;margin-bottom:14px;
        box-shadow:0 8px 22px rgba(15,52,96,0.40);
    }}
    .cli-title {{
        font-size:1.75rem;font-weight:900;color:#0a1628 !important;
        line-height:1.15;margin:0 0 8px;letter-spacing:-0.01em;
    }}
    .cli-sub {{
        font-size:0.86rem;color:#64748b !important;line-height:1.55;
        margin:0 auto;max-width:340px;
    }}

    /* Inputs sólidos */
    .st-key-cli_login_card div[data-testid="stTextInput"] label,
    .st-key-cli_login_card div[data-testid="stTextInput"] label p {{
        color:#0a1628!important;text-shadow:none!important;
        font-weight:700!important;font-size:0.7rem!important;
        letter-spacing:0.08em!important;text-transform:uppercase!important;
        margin-bottom:4px!important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] > div {{
        background:transparent!important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] div[data-baseweb="input"] {{
        background:transparent!important;border:none!important;box-shadow:none!important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] input {{
        background:#f8fafc!important;color:#0a1628!important;opacity:1!important;
        border:1.5px solid #e2e8f0!important;border-radius:11px!important;
        padding:12px 14px!important;font-size:0.95rem!important;
        font-family:Poppins,sans-serif!important;font-weight:600!important;
        transition:border-color 0.18s,box-shadow 0.18s,background 0.18s!important;
        box-shadow:inset 0 1px 2px rgba(15,23,42,0.04)!important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] input:focus {{
        border-color:#0f3460!important;background:white!important;
        box-shadow:0 0 0 3px rgba(15,52,96,0.13),inset 0 1px 2px rgba(15,23,42,0.04)!important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] input::placeholder {{
        color:#94a3b8!important;font-weight:500!important;
    }}

    /* Botón solid con sombra fuerte */
    .st-key-cli_login_card div[data-testid="stButton"] > button {{
        background:linear-gradient(135deg,#0f3460 0%,#1a5276 100%)!important;
        color:white!important;border:none!important;
        border-radius:12px!important;padding:14px 22px!important;
        font-size:0.95rem!important;font-weight:700!important;
        font-family:Poppins,sans-serif!important;letter-spacing:0.015em!important;
        box-shadow:0 16px 38px rgba(15,52,96,0.42),0 6px 16px rgba(15,52,96,0.28)!important;
        margin-top:8px!important;
        transition:transform 0.18s cubic-bezier(0.4,0,0.2,1),box-shadow 0.18s!important;
    }}
    .st-key-cli_login_card div[data-testid="stButton"] > button:hover {{
        transform:translateY(-2px)!important;
        box-shadow:0 22px 50px rgba(15,52,96,0.5),0 8px 20px rgba(15,52,96,0.32)!important;
    }}
    .st-key-cli_login_card div[data-testid="stButton"] > button:active {{
        transform:translateY(0)!important;
    }}

    /* Mensajes de error dentro de la card */
    .st-key-cli_login_card div[data-testid="stAlert"] {{
        background:#fef2f2!important;border:1px solid #fecaca!important;
        border-radius:10px!important;
    }}

    @media (max-width:600px) {{
        .st-key-cli_login_card {{ padding:28px 22px!important; }}
        .cli-title {{ font-size:1.45rem!important; }}
    }}
    </style>
    """, unsafe_allow_html=True)

    # Espacio superior para centrado vertical aproximado
    st.markdown("<div style='height:12vh;'></div>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2.2, 1])
    with col:
        with st.container(key="cli_login_card"):
            st.markdown("""
            <div class="cli-title-block">
                <div class="cli-badge">✦ Portal de Materiales</div>
                <div class="cli-title">Tu casa, tus materiales 🏡</div>
                <div class="cli-sub">Ingresa tus datos para acceder a tu formulario personalizado de selección de materiales.</div>
            </div>
            """, unsafe_allow_html=True)

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

    # Safety net: force z-index + bg vía JS por si la CSS no llega.
    # Fallback de :has() para navegadores antiguos.
    components.html("""
<script>
(function(){
  var D = window.parent.document;
  function paintCard(){
    var el = D.querySelector('.st-key-cli_login_card');
    if (!el) return false;
    el.style.setProperty('background-color', '#ffffff', 'important');
    el.style.setProperty('position', 'relative', 'important');
    el.style.setProperty('z-index', '50', 'important');
    // Columna padre para crear contexto de stacking si :has no funciona
    var col = el.closest('[data-testid="stColumn"]');
    if (col) {
      col.style.setProperty('position', 'relative', 'important');
      col.style.setProperty('z-index', '50', 'important');
    }
    return true;
  }
  paintCard();
  setTimeout(paintCard, 300);
  setTimeout(paintCard, 1200);
})();
</script>
""", height=0)


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
