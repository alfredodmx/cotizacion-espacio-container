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
from utils.avatars import fetch_foto_map as _fetch_foto_map
from auth.cliente_token import crear_token_cliente, validar_token_cliente

_CSS_CLIENTE = """
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;900&family=Montserrat:wght@700;800;900&display=swap');
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
/* Ancho amplio + sin espacio superior para el formulario del cliente */
[data-testid="stMainBlockContainer"],.block-container{padding-top:0!important;padding-bottom:0!important;padding-left:1.1rem!important;padding-right:1.1rem!important;max-width:100%!important;}
/* Colapsar gaps del vertical block (los st.markdown de CSS no deben dejar aire) */
[data-testid="stVerticalBlock"]{gap:0!important;}
[data-testid="stMain"]{padding-top:0!important;}
/* El botón nativo "Salir" se reemplaza por el botón flotante del formulario */
.st-key-cli_logout{display:none!important;}
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

    /* CARD CENTRAL — GLASS moderado: deja ver el video detrás pero con blur
       sutil para legibilidad. Textos en blanco. */
    @keyframes cli_card_in {{
        from {{ opacity:0; transform:translateY(14px); }}
        to   {{ opacity:1; transform:translateY(0); }}
    }}
    .st-key-cli_login_card,
    .st-key-cli_login_card > div,
    .st-key-cli_login_card > div > div,
    .st-key-cli_login_card div[data-testid="stVerticalBlockBorderWrapper"],
    .st-key-cli_login_card div[data-testid="stVerticalBlock"] {{
        background-color:transparent !important;
        background-image:none !important;
    }}
    .st-key-cli_login_card {{
        background-color:rgba(255,255,255,0.02) !important;
        backdrop-filter:blur(2.5px) saturate(105%) !important;
        -webkit-backdrop-filter:blur(2.5px) saturate(105%) !important;
        border-radius:24px !important;
        padding:38px 34px 30px !important;
        box-shadow:0 24px 60px rgba(5,10,20,0.45),0 8px 24px rgba(5,10,20,0.25) !important;
        border:1px solid rgba(255,255,255,0.20) !important;
        animation:cli_card_in 0.55s cubic-bezier(0.16,1,0.3,1) both !important;
        position:relative !important;
        z-index:50 !important;            /* sobre cli-overlay (z=1) */
        overflow:hidden !important;       /* clip overflow de hijos */
        box-sizing:border-box !important;
    }}
    /* Forzar que los inputs y botón respeten el padding interno del card */
    .st-key-cli_login_card div[data-testid="stTextInput"],
    .st-key-cli_login_card div[data-testid="stButton"],
    .st-key-cli_login_card [data-testid="stElementContainer"] {{
        width:100% !important;
        max-width:100% !important;
        margin-left:0 !important;
        margin-right:0 !important;
        box-sizing:border-box !important;
    }}
    /* La columna que contiene la card también necesita stacking context */
    [data-testid="stColumn"]:has(.st-key-cli_login_card) {{
        position:relative !important;
        z-index:50 !important;
    }}

    /* Bloque título dentro de la card — centrado en flex column */
    .cli-title-block {{
        display:flex !important;
        flex-direction:column !important;
        align-items:center !important;
        text-align:center !important;
        margin:0 auto 22px !important;
        font-family:'Poppins',sans-serif;
        width:100%;
    }}
    /* Badge glass */
    .cli-badge {{
        display:inline-flex;align-items:center;gap:6px;
        background:rgba(255,255,255,0.14) !important;
        backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);
        color:#ffffff !important;border-radius:99px;padding:5px 16px;
        font-size:0.62rem;font-weight:800;letter-spacing:0.14em;
        text-transform:uppercase;margin:0 0 14px 0;
        border:1px solid rgba(255,255,255,0.28);
        box-shadow:0 6px 18px rgba(0,0,0,0.18);
    }}
    /* SVG ícono arriba del título, separado */
    .cli-title-icon {{
        margin:0 0 10px 0;
        filter:drop-shadow(0 2px 10px rgba(0,0,0,0.4));
    }}
    .cli-title-icon svg {{
        width:42px;height:42px;display:block;
    }}
    /* Título en MONTSERRAT 900 UPPERCASE blanco */
    .cli-title {{
        font-family:'Montserrat',sans-serif !important;
        font-size:1.55rem;font-weight:900;color:#ffffff !important;
        line-height:1.18;margin:0 0 10px 0;
        letter-spacing:0.04em;text-transform:uppercase;
        text-shadow:0 2px 14px rgba(0,0,0,0.45);
        text-align:center;
        max-width:100%;
        word-spacing:0.02em;
    }}
    .cli-sub {{
        font-family:'Poppins',sans-serif;
        font-size:0.86rem;color:rgba(255,255,255,0.88) !important;
        line-height:1.55;margin:0 auto;max-width:360px;
        text-align:center;
        text-shadow:0 1px 6px rgba(0,0,0,0.4);
    }}
    @media (max-width:600px) {{
        .cli-title {{ font-size:1.25rem !important; }}
        .cli-title-icon svg {{ width:36px !important; height:36px !important; }}
    }}

    /* Labels de inputs en blanco */
    .st-key-cli_login_card div[data-testid="stTextInput"] label,
    .st-key-cli_login_card div[data-testid="stTextInput"] label p {{
        color:#ffffff !important;
        text-shadow:0 1px 4px rgba(0,0,0,0.35) !important;
        font-weight:700 !important;font-size:0.7rem !important;
        letter-spacing:0.08em !important;text-transform:uppercase !important;
        margin-bottom:4px !important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] > div {{
        background:transparent !important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] div[data-baseweb="input"] {{
        background:transparent !important;border:none !important;box-shadow:none !important;
    }}
    /* Inputs GLASS (más vidriosos que la card) */
    .st-key-cli_login_card div[data-testid="stTextInput"] input {{
        background:rgba(255,255,255,0.12) !important;
        backdrop-filter:blur(6px) !important;
        -webkit-backdrop-filter:blur(6px) !important;
        color:#ffffff !important;opacity:1 !important;
        border:1px solid rgba(255,255,255,0.28) !important;
        border-radius:11px !important;
        padding:12px 14px !important;font-size:0.95rem !important;
        font-family:Poppins,sans-serif !important;font-weight:600 !important;
        transition:border-color 0.18s,box-shadow 0.18s,background 0.18s !important;
        box-shadow:0 4px 12px rgba(0,0,0,0.18) !important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] input:focus {{
        border-color:rgba(255,255,255,0.6) !important;
        background:rgba(255,255,255,0.18) !important;
        box-shadow:0 0 0 3px rgba(255,255,255,0.15),0 4px 12px rgba(0,0,0,0.18) !important;
    }}
    .st-key-cli_login_card div[data-testid="stTextInput"] input::placeholder {{
        color:rgba(255,255,255,0.55) !important;font-weight:500 !important;
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
            # SVG casa estilo Lucide, en blanco
            _svg_house = (
                '<svg viewBox="0 0 24 24" fill="none" stroke="#ffffff" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M3 10.5 12 3l9 7.5V20a1.5 1.5 0 0 1-1.5 1.5h-4.5v-7h-6v7H4.5A1.5 1.5 0 0 1 3 20z"/>'
                '</svg>'
            )
            st.markdown(f"""
            <div class="cli-title-block">
                <div class="cli-badge">&#10022; Portal de Materiales</div>
                <div class="cli-title-icon">{_svg_house}</div>
                <div class="cli-title">Tu casa, tu dise&ntilde;o, tus materiales</div>
                <div class="cli-sub">Ingresa tus datos para acceder a tu formulario personalizado de selecci&oacute;n de materiales.</div>
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
                                # Persistir la sesión en la URL (magic link firmado):
                                # así una recarga NO devuelve al cliente al login.
                                try:
                                    st.query_params["ct"] = crear_token_cliente(ep_clean)
                                except Exception:
                                    pass
                                st.rerun()
                            else:
                                st.error("RUT o código incorrecto. Verifica tus datos.")
                        else:
                            st.error("Código de presupuesto no encontrado.")
                    except Exception as ce:
                        st.error(f"Error de conexión: {ce}")

    # Safety net: force z-index + glass bg + inputs glass vía JS
    # (inline setProperty('important') gana a cualquier CSS de Streamlit/BaseWeb).
    components.html("""
<script>
(function(){
  var D = window.parent.document;
  function paintCard(){
    var el = D.querySelector('.st-key-cli_login_card');
    if (!el) return false;
    // Card wrapper glass
    el.style.setProperty('background-color', 'rgba(255,255,255,0.02)', 'important');
    el.style.setProperty('backdrop-filter', 'blur(2.5px) saturate(105%)', 'important');
    el.style.setProperty('-webkit-backdrop-filter', 'blur(2.5px) saturate(105%)', 'important');
    el.style.setProperty('position', 'relative', 'important');
    el.style.setProperty('z-index', '50', 'important');
    el.style.setProperty('overflow', 'hidden', 'important');
    el.style.setProperty('box-sizing', 'border-box', 'important');
    // Wrappers internos transparentes Y restringidos en width
    el.querySelectorAll('div').forEach(function(d){
      var tid = d.getAttribute && d.getAttribute('data-testid');
      if (tid === 'stVerticalBlockBorderWrapper' || tid === 'stVerticalBlock') {
        d.style.setProperty('background-color', 'transparent', 'important');
        d.style.setProperty('width', '100%', 'important');
        d.style.setProperty('max-width', '100%', 'important');
        d.style.setProperty('box-sizing', 'border-box', 'important');
      }
      if (tid === 'stTextInput' || tid === 'stButton' || tid === 'stElementContainer') {
        d.style.setProperty('width', '100%', 'important');
        d.style.setProperty('max-width', '100%', 'important');
        d.style.setProperty('margin-left', '0', 'important');
        d.style.setProperty('margin-right', '0', 'important');
        d.style.setProperty('box-sizing', 'border-box', 'important');
        if (tid === 'stTextInput') {
          d.querySelectorAll('div').forEach(function(sub){
            sub.style.setProperty('background-color', 'transparent', 'important');
          });
        }
      }
    });
    // Inputs GLASS — forzar bg semi-transparente y color blanco
    el.querySelectorAll('input').forEach(function(inp){
      inp.style.setProperty('background-color', 'rgba(255,255,255,0.12)', 'important');
      inp.style.setProperty('background-image', 'none', 'important');
      inp.style.setProperty('backdrop-filter', 'blur(6px)', 'important');
      inp.style.setProperty('-webkit-backdrop-filter', 'blur(6px)', 'important');
      inp.style.setProperty('color', '#ffffff', 'important');
      inp.style.setProperty('border', '1px solid rgba(255,255,255,0.28)', 'important');
      inp.style.setProperty('border-radius', '11px', 'important');
      inp.style.setProperty('-webkit-text-fill-color', '#ffffff', 'important');
    });
    // Columna padre para contexto de stacking
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
  // Observer para repintar si se hace focus (BaseWeb a veces repinta bg al focus)
  try {
    var obs = new MutationObserver(function(){ paintCard(); });
    obs.observe(D.body, {childList:true, subtree:true, attributes:true, attributeFilter:['style','class']});
    setTimeout(function(){ obs.disconnect(); }, 8000);
  } catch(e) {}
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

    # Asesor del EP (nombre + foto) para el modal de agradecimiento.
    asesor_nombre, asesor_foto = '', ''
    try:
        arow = supabase_admin.table('cotizaciones')\
            .select('asesor_nombre,asesor_email').eq('numero', ep).limit(1).execute().data
        if arow:
            asesor_nombre = (arow[0].get('asesor_nombre') or '').strip()
            ae = (arow[0].get('asesor_email') or '').strip().lower()
            if ae:
                asesor_foto = _fetch_foto_map(supa_url).get(ae, '')
    except Exception:
        pass

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
        _ic_clip = ('<svg viewBox="0 0 24 24" width="46" height="46" fill="none" stroke="#0f3460" '
                    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
                    '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>'
                    '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="m9 14 2 2 4-4"/></svg>')
        st.markdown(f"""
        <div style='max-width:560px;margin:60px auto;text-align:center;font-family:Poppins,sans-serif;'>
          <div style='margin-bottom:16px;'>{_ic_clip}</div>
          <div style='font-size:1.4rem;font-weight:900;color:#0a1628;margin-bottom:8px;'>
            Hola {primer_n}, &#161;ya casi!</div>
          <div style='color:#64748b;font-size:0.95rem;line-height:1.6;'>
            Tu formulario est&#225; siendo preparado. &#161;La espera va a valer la pena!</div>
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
            asesor_nombre=asesor_nombre, asesor_foto=asesor_foto,
        )
        # Alto inicial aproximado; el JS del componente lo ajusta al contenido
        # real vía window.frameElement (fitHeight), evitando el espacio vacío.
        form_height = max(640, len(cfg) * 330)
        components.html(form_html, height=form_height, scrolling=False)

    if st.button("← Salir", key="cli_logout"):
        for k in ['_cliente_ep', '_cliente_ok', '_cliente_nombre', '_cliente_proyecto']:
            st.session_state.pop(k, None)
        # Quitar el token de la URL para que una recarga posterior vaya al login.
        try:
            if "ct" in st.query_params:
                del st.query_params["ct"]
        except Exception:
            pass
        st.rerun()


def render_cliente_view(supabase_admin, supa_url: str, supa_key: str) -> None:
    """
    Punto de entrada de la vista pública del cliente.
    Llama st.stop() al terminar (siempre es una vista completa).
    """
    _init_cliente_state()

    # ── Restaurar sesión desde el token de la URL (magic link firmado) ────────
    # Aditivo + fallback: si el token es válido, entra directo al formulario sin
    # re-pedir RUT+código (así una recarga no lo desloguea). Si es inválido/
    # expirado/ausente, no pasa nada y cae al login normal de abajo.
    if not st.session_state._cliente_ok:
        _tok = st.query_params.get("ct")
        _ep_tok = validar_token_cliente(_tok) if _tok else None
        if _ep_tok:
            try:
                _row = (supabase_admin.table('cotizaciones')
                        .select('cliente_nombre,proyecto_observaciones,cliente_rut')
                        .eq('numero', _ep_tok).limit(1).execute().data)
                if _row:
                    st.session_state._cliente_ep       = _ep_tok
                    st.session_state._cliente_ok        = True
                    st.session_state._cliente_nombre    = _row[0].get('cliente_nombre', '')
                    st.session_state._cliente_proyecto  = _row[0].get('proyecto_observaciones', '')
            except Exception:
                pass  # cualquier fallo → se muestra el login (nada roto)

    st.markdown(f"<style>{_CSS_CLIENTE}</style>", unsafe_allow_html=True)
    logo_b64 = _cargar_logo_b64()

    if not st.session_state._cliente_ok:
        _render_login_cliente(logo_b64, supabase_admin)
    else:
        _render_formulario_cliente(supabase_admin, supa_url, supa_key)

    st.stop()
