"""
Sidebar de navegación lateral — reemplaza las pestañas superiores.
Botones nativos (clic confiable) + iconos SVG vía CSS + colapsar/expandir.
El código de acceso (root/admin) va anclado abajo, sobre el botón de colapso.
"""
import urllib.parse as _url
import streamlit as st

from auth.access_code import generar_codigo_acceso, _get_bloque_horario
import datetime as _dt


# ── Iconos SVG (línea, estilo Lucide) ────────────────────────────────────────
# Solo el contenido interno del <svg>; el color y el wrapper se generan al vuelo.
_ICON_PATHS = {
    "dashboard": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "presupuesto": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "datos": '<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "cotizaciones": '<path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>',
    "edicion_pdf": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "ranking": '<circle cx="12" cy="8" r="6"/><polyline points="8.21 13.89 7 23 12 20 17 23 15.79 13.88"/>',
    "contrato": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M9 15l2 2 4-4"/>',
    "3d": '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/>',
    "proyecto_excel": '<rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/>',
    "sistema": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
    "usuarios": '<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "notificaciones": '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    "reporte": '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>',
    "operaciones": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "admindata": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "formulario": '<rect x="4" y="4" width="16" height="18" rx="2"/><path d="M9 4V2h6v2"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="16" y2="14"/><line x1="8" y1="18" x2="13" y2="18"/>',
    "_collapse": '<polyline points="15 18 9 12 15 6"/>',
    "_expand": '<polyline points="9 18 15 12 9 6"/>',
}


def _svg_uri(key: str, color: str) -> str:
    """Devuelve un data-URI de un icono SVG con el color de stroke dado."""
    inner = _ICON_PATHS.get(key, "")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='22' height='22' "
        "viewBox='0 0 24 24' fill='none' stroke='" + color + "' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round'>" + inner + "</svg>"
    )
    return "data:image/svg+xml," + _url.quote(svg)


def page_icon_svg(key: str, size_rem: float = 2.8, color: str = "white") -> str:
    """HTML de un SVG inline con el mismo ícono que el sidebar, para usar
    como reemplazo de emoticons en los page headers. size_rem = tamaño en rem
    (2.8rem por defecto, igual al emoticon original)."""
    inner = _ICON_PATHS.get(key, "")
    return (
        f'<span style="display:inline-flex;align-items:center;justify-content:center;'
        f'width:{size_rem}rem;height:{size_rem}rem;flex-shrink:0;line-height:1;">'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="100%" height="100%" '
        f'viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{inner}</svg></span>'
    )


_COL_IDLE = "#94a3b8"     # icono normal
_COL_ACTIVE = "#ffffff"   # icono del activo
_ACCENT = "#5b7cfa"


def _codigo_acceso_html(colapsado: bool) -> str:
    """HTML del código de acceso (root/admin). Compacto si está colapsado."""
    try:
        _mo = _dt.datetime.utcnow().month
        _off = -3 if _mo in (10, 11, 12, 1, 2, 3) else -4
        _now_cl = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=_off)))
        _bloque = _get_bloque_horario(_now_cl)
        _parts = _bloque.rsplit("-", 2)
        _bloque_disp = f"{_parts[-2][:2]}:{_parts[-2][2:]} → {_parts[-1][:2]}:{_parts[-1][2:]}"
        _cod = generar_codigo_acceso()
    except Exception:
        return ""
    if colapsado:
        return (
            "<div title='Código de acceso' style='margin:0 auto 6px;text-align:center;'>"
            "<div style='font-size:0.95rem;font-weight:800;color:#2dd4bf;letter-spacing:0.08em;'>"
            + str(_cod) + "</div></div>"
        )
    return (
        "<div style='background:rgba(45,212,191,0.08);border:1px solid rgba(45,212,191,0.25);"
        "border-radius:10px;padding:8px 12px;margin-bottom:10px;display:flex;align-items:center;"
        "justify-content:space-between;gap:10px;'>"
        "<div style='font-size:0.62rem;color:#94a3b8;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.05em;line-height:1.25;'>Código<br>" + _bloque_disp + "</div>"
        "<div style='font-size:1.1rem;font-weight:800;color:#2dd4bf;letter-spacing:0.12em;'>"
        + str(_cod) + "</div></div>"
    )


def _build_css(items, activo: str, colapsado: bool) -> str:
    """CSS del sidebar: dark azul, iconos SVG, activo, colapso. Brand y footer
    fijos vía position:fixed (no depende del DOM interno de Streamlit)."""
    ancho = "76px" if colapsado else "256px"
    _foot_h = "70px" if colapsado else "112px"
    css = ["<style>"]
    # Contenedor del sidebar: fondo AZUL OSCURO, SIN borde
    # Transición elegante (cubic-bezier "ease-out-cubic") para colapsar/expandir.
    _ease = "cubic-bezier(0.22,1,0.36,1)"
    _t = f"0.32s {_ease}"
    css.append(
        f'section[data-testid="stSidebar"]{{width:{ancho}!important;min-width:{ancho}!important;'
        f'background:linear-gradient(180deg,#0f172a 0%,#0b1220 100%)!important;'
        f'border-right:none!important;'
        f'transition:width {_t},min-width {_t}!important;will-change:width;}}'
    )
    # Todos los contenedores internos transparentes y SIN borde (se ve el azul)
    css.append(
        'section[data-testid="stSidebar"] [data-testid="stSidebarContent"],'
        'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"],'
        'section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],'
        'section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],'
        'section[data-testid="stSidebar"] [data-testid="stElementContainer"],'
        'section[data-testid="stSidebar"] .stButton'
        '{background:transparent!important;border:none!important;box-shadow:none!important;}'
    )
    # Padding del area de contenido + espacio para brand fijo (arriba) y footer (abajo)
    css.append(
        f'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]'
        f'{{padding:54px 0.55rem calc({_foot_h} + 6px)!important;}}'
    )
    # BRAND fijo arriba
    css.append(
        f'.st-key-_sb_brand_full,.st-key-_sb_brand_mini'
        f'{{position:fixed!important;top:0!important;left:0!important;width:{ancho}!important;'
        f'z-index:6!important;background:#0f172a!important;box-sizing:border-box!important;'
        f'padding:10px 12px 8px!important;transition:width {_t}!important;}}'
    )
    # FOOTER fijo abajo (codigo + toggle) — fondo MACIZO (más específico que la
    # regla de transparencia, e incluye los wrappers internos, para que no se
    # transparente y no se vea el contenido que scrollea detrás).
    css.append(
        f'.st-key-_sb_bottom,'
        f'.st-key-_sb_bottom [data-testid="stVerticalBlockBorderWrapper"],'
        f'.st-key-_sb_bottom [data-testid="stVerticalBlock"]'
        f'{{background:#0b1220!important;border:none!important;box-shadow:none!important;}}'
        f'.st-key-_sb_bottom'
        f'{{position:fixed!important;bottom:0!important;left:0!important;width:{ancho}!important;'
        f'z-index:6!important;box-sizing:border-box!important;'
        f'padding:8px 0.3rem 10px!important;box-shadow:0 -8px 16px rgba(11,18,32,0.9)!important;'
        f'overflow:hidden!important;transition:width {_t}!important;}}'
    )
    # Ocultar el header nativo del sidebar (la barra superior de Streamlit con el
    # botón de colapso) — es lo que metía el gran espacio arriba. Usamos el nuestro.
    css.append(
        'section[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{display:none!important;height:0!important;min-height:0!important;padding:0!important;}'
        'section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]{display:none!important;}'
    )
    # El header fijo arranca despues del sidebar (no lo tapa)
    css.append(f'#_usr_header_bar{{left:{ancho}!important;transition:left {_t}!important;}}')
    # El FAB flotante de guardar se corre para no quedar sobre el sidebar.
    # (También se mantiene via --sb-w en tab_cotizacion; acá la transición.)
    css.append(f'.st-key-btn_fab_guardar{{left:calc({ancho} + 1.2rem)!important;transition:left {_t}!important;}}')
    # Scrollbar fino para el area de navegacion (el contenido scrollea)
    css.append(
        'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar{width:6px;}'
        'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar-thumb'
        '{background:rgba(148,163,184,0.25);border-radius:3px;}'
    )
    # Botones de navegacion (generico)
    css.append(
        'section[data-testid="stSidebar"] .stButton button{width:100%!important;'
        'justify-content:flex-start!important;gap:12px!important;background:transparent!important;'
        'border:1px solid transparent!important;color:#cbd5e1!important;font-family:Montserrat,sans-serif!important;'
        'font-weight:600!important;font-size:0.82rem!important;border-radius:10px!important;'
        'padding:9px 12px!important;margin:1px 0!important;min-height:0!important;'
        'box-shadow:none!important;transition:background .12s,color .12s;}'
    )
    css.append(
        'section[data-testid="stSidebar"] .stButton button:hover{background:rgba(91,124,250,0.12)!important;'
        'color:#ffffff!important;border-color:rgba(91,124,250,0.25)!important;}'
    )
    # Icono ::before por cada item (color normal)
    for it in items:
        k = it["key"]; ic = it.get("icon", "")
        css.append(
            f'.st-key-nav_{k} button::before{{content:"";flex-shrink:0;width:22px;height:22px;'
            f'background:url("{_svg_uri(ic, _COL_IDLE)}") no-repeat center/contain;}}'
        )
    # Item activo
    css.append(
        f'.st-key-nav_{activo} button{{background:linear-gradient(135deg,{_ACCENT},#7c5cfa)!important;'
        f'color:#fff!important;border-color:transparent!important;font-weight:700!important;'
        f'box-shadow:0 4px 14px rgba(91,124,250,0.35)!important;}}'
    )
    _act_icon = items_icon(items, activo)
    if _act_icon:
        css.append(
            f'.st-key-nav_{activo} button::before{{background:url("{_svg_uri(_act_icon, _COL_ACTIVE)}") no-repeat center/contain!important;}}'
        )
    # Toggle colapsar — con prefijo del section para GANAR a la regla genérica de
    # los botones (misma especificidad + va después). Fondo transparente (azul),
    # sin borde, SIN cambio al hover/focus.
    # Cuando NO está colapsado: el ícono tiene margin-right para separarse del texto
    _toggle_margin = '0 8px 0 0' if not colapsado else '0'
    css.append(
        '.st-key-_sb_toggle button{width:100%!important;'
        'justify-content:center!important;background:transparent!important;border:none!important;'
        'box-shadow:none!important;color:#94a3b8!important;border-radius:10px!important;'
        'padding:9px 0!important;min-height:0!important;overflow:visible!important;}'
        '.st-key-_sb_toggle button:hover'
        '{background:transparent!important;border:none!important;border-color:transparent!important;color:#cbd5e1!important;}'
        '.st-key-_sb_toggle button:focus,'
        '.st-key-_sb_toggle button:active'
        '{background:transparent!important;border:none!important;box-shadow:none!important;color:#94a3b8!important;}'
        f'.st-key-_sb_toggle button::before{{content:"";flex-shrink:0;'
        f'width:20px;height:20px;margin:{_toggle_margin};'
        f'background:url("{_svg_uri("_expand" if colapsado else "_collapse", _COL_IDLE)}") no-repeat center/contain;}}'
    )
    if colapsado:
        # ── Base del sidebar colapsado ────────────────────────────────────────
        css.append(
            'section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:0!important;margin:0!important;}'
            'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{padding:54px 0 60px!important;scrollbar-width:none!important;}'
            'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar{width:0!important;display:none!important;}'
            'section[data-testid="stSidebar"] .st-key-_sb_nav{padding-left:0!important;padding-right:0!important;width:100%!important;}'
            '.st-key-_sb_bottom{'
            'padding:6px 0 8px!important;width:76px!important;box-shadow:none!important;overflow:hidden!important;}'
            'section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],'
            'section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{width:100%!important;margin:0!important;padding:0!important;}'
            'section[data-testid="stSidebar"] [data-testid="stElementContainer"],'
            'section[data-testid="stSidebar"] .stButton{width:100%!important;padding:0!important;margin:0!important;}'
        )
        # ── Icono vía ::before del div .stButton (no el <button>) ────────────
        # El <div class="stButton"> sí rellena el 100% del sidebar (76px).
        # Ponemos el ícono como ::before absolutamente centrado en ese div.
        # El <button> se hace transparente / invisible para no mostrar texto.
        # ── Botones de nav: .stButton como posicionamiento, button transparente ─
        css.append(
            'section[data-testid="stSidebar"] .st-key-_sb_nav .stButton{'
            'position:relative!important;height:44px!important;}'
            'section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button{'
            'position:absolute!important;inset:0!important;'
            'background:transparent!important;border:none!important;'
            'color:transparent!important;box-shadow:none!important;outline:none!important;'
            'width:100%!important;height:100%!important;z-index:1!important;}'
            'section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button>*{visibility:hidden!important;}'
            # Solo ocultamos ::before en los botones de nav (el toggle conserva el suyo)
            'section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button::before{display:none!important;}'
        )
        # ── Ícono centrado de cada ítem de nav via .stButton::before ─────────
        for it in items:
            k = it["key"]; ic = it.get("icon", "")
            _color = _COL_ACTIVE if k == activo else _COL_IDLE
            _icon_uri = _svg_uri(ic, _color)
            css.append(
                f'section[data-testid="stSidebar"] .st-key-nav_{k} .stButton::before{{'
                f'content:""!important;display:block!important;'
                f'position:absolute!important;left:50%!important;top:50%!important;'
                f'transform:translate(-50%,-50%)!important;'
                f'width:22px!important;height:22px!important;'
                f'background:url("{_icon_uri}") no-repeat center/contain!important;'
                f'pointer-events:none!important;z-index:2!important;}}'
            )
            if k == activo:
                css.append(
                    f'section[data-testid="stSidebar"] .st-key-nav_{k} .stButton{{'
                    f'background:linear-gradient(135deg,{_ACCENT},#7c5cfa)!important;'
                    f'border-radius:10px!important;}}'
                )
        # ── Toggle (expandir): conserva su button::before original ───────────
        # La CSS general ya inyectó .st-key-_sb_toggle button::before con el ícono.
        # Solo ajustamos height del .stButton y escondemos el texto del button.
        css.append(
            '.st-key-_sb_toggle{width:76px!important;padding:0!important;margin:0!important;'
            'display:block!important;}'
            '.st-key-_sb_toggle .stButton{'
            'position:relative!important;height:48px!important;width:76px!important;'
            'padding:0!important;margin:0!important;display:block!important;}'
            '.st-key-_sb_toggle .stButton button{'
            'position:absolute!important;left:0!important;top:0!important;'
            'width:76px!important;height:48px!important;'
            'background:transparent!important;border:none!important;'
            'color:transparent!important;box-shadow:none!important;outline:none!important;'
            'padding:0!important;margin:0!important;}'
            '.st-key-_sb_toggle .stButton button>*{'
            'visibility:hidden!important;width:0!important;height:0!important;overflow:hidden!important;}'
            f'.st-key-_sb_toggle .stButton button::before{{'
            f'content:""!important;display:block!important;'
            f'position:absolute!important;left:50%!important;top:50%!important;'
            f'transform:translate(-50%,-50%)!important;margin:0!important;padding:0!important;'
            f'width:22px!important;height:22px!important;flex:none!important;'
            f'background:url("{_svg_uri("_expand", _COL_IDLE)}") no-repeat center/contain!important;'
            f'pointer-events:none!important;}}'
        )
        # Tooltip visible al hover
        css.append(
            'section[data-testid="stSidebar"]{overflow:visible!important;}'
            '[data-baseweb="tooltip"],[role="tooltip"]{z-index:99999!important;}'
        )
    css.append("</style>")
    return "".join(css)


def items_icon(items, key):
    for it in items:
        if it["key"] == key:
            return it.get("icon", "")
    return ""


def render_sidebar(items, rol: str, nombre: str) -> str:
    """Renderiza el sidebar de navegación y devuelve la página seleccionada.

    items: lista de dicts {key, label, icon}. La página activa se guarda en
    st.session_state['nav_page'].
    """
    _keys = [it["key"] for it in items]
    _actual = st.session_state.get("nav_page")
    if _actual not in _keys:
        _actual = _keys[0] if _keys else None
        st.session_state["nav_page"] = _actual
    _colapsado = st.session_state.get("_sb_collapsed", False)

    st.markdown(_build_css(items, _actual, _colapsado), unsafe_allow_html=True)

    with st.sidebar:
        # Marca / logo
        if _colapsado:
            st.markdown(
                '<div class="st-key-_sb_brand_mini" style="text-align:center;padding:6px 0 10px;">'
                '<div style="width:36px;height:36px;margin:0 auto;border-radius:10px;'
                'background:linear-gradient(135deg,#5b7cfa,#7c5cfa);display:flex;align-items:center;'
                'justify-content:center;color:#fff;font-weight:900;font-family:Montserrat;">C</div></div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="st-key-_sb_brand_full" style="padding:6px 8px 12px;">'
                '<div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.1rem;'
                'color:#fff;letter-spacing:0.04em;">COTIZADOR<span style="color:#5b7cfa;"> PRO</span></div>'
                '<div style="font-size:0.62rem;color:#64748b;font-weight:600;text-transform:uppercase;'
                'letter-spacing:0.08em;margin-top:1px;">Panel de gestión</div></div>',
                unsafe_allow_html=True,
            )

        # Navegación (cada botón cambia la página)
        with st.container(key="_sb_nav"):
            for it in items:
                _lbl = it["label"] if not _colapsado else "\u200b"
                if st.button(_lbl, key=f"nav_{it['key']}", use_container_width=True):
                    st.session_state["nav_page"] = it["key"]
                    st.rerun()

        # Sección inferior anclada: código de acceso + toggle
        with st.container(key="_sb_bottom"):
            # El código de acceso solo se muestra con el sidebar expandido
            if rol in ("root", "admin") and not _colapsado:
                _cod_html = _codigo_acceso_html(_colapsado)
                if _cod_html:
                    st.markdown(_cod_html, unsafe_allow_html=True)
            _tlabel = "\u200b" if _colapsado else "Ocultar menú"
            if st.button(_tlabel, key="_sb_toggle", use_container_width=True):
                st.session_state["_sb_collapsed"] = not _colapsado
                st.rerun()

    return st.session_state["nav_page"]
