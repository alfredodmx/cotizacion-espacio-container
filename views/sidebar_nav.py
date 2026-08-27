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
    "inventario": '<path d="M20 5H4a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1Z"/><path d="M4 10v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9"/><line x1="10" y1="14" x2="14" y2="14"/>',
    "clientes": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/><path d="M22 11h-4"/><path d="M20 9v4"/>',
    "admindata": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "sitio_web": '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "formulario": '<rect x="4" y="4" width="16" height="18" rx="2"/><path d="M9 4V2h6v2"/><line x1="8" y1="10" x2="16" y2="10"/><line x1="8" y1="14" x2="16" y2="14"/><line x1="8" y1="18" x2="13" y2="18"/>',
    "seguridad": '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/>',
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
    _cod = str(_cod)
    if colapsado:
        return (
            "<div class='ec-copy-code' data-ec-copy='" + _cod + "' "
            "title='Click para copiar' "
            "style='margin:0 auto 6px;text-align:center;cursor:pointer;user-select:none;'>"
            "<div style='font-size:0.95rem;font-weight:800;color:#2dd4bf;letter-spacing:0.08em;'>"
            + _cod + "</div></div>"
        )
    return (
        "<div class='ec-copy-code' data-ec-copy='" + _cod + "' "
        "title='Click para copiar' "
        "style='background:rgba(45,212,191,0.08);border:1px solid rgba(45,212,191,0.25);"
        "border-radius:10px;padding:8px 12px;margin-bottom:10px;display:flex;align-items:center;"
        "justify-content:space-between;gap:10px;cursor:pointer;user-select:none;"
        "transition:background .15s;'>"
        "<div style='font-size:0.62rem;color:#94a3b8;font-weight:700;text-transform:uppercase;"
        "letter-spacing:0.05em;line-height:1.25;'>Código<br>" + _bloque_disp + "</div>"
        "<div style='font-size:1.1rem;font-weight:800;color:#2dd4bf;letter-spacing:0.12em;'>"
        + _cod + "</div></div>"
    )


def _build_css(items, activo: str) -> str:
    """CSS del sidebar: dark azul, iconos SVG, activo, colapso.

    El colapso es 100% CSS: el estado EXPANDIDO es el default y el COLAPSADO se
    aplica con la clase `html.ec-sbc` (que un JS añade/quita y persiste en
    localStorage). Así NO hace falta rerun de Python para colapsar/expandir.
    Brand y footer fijos vía position:fixed (no dependen del DOM de Streamlit)."""
    ancho = "256px"      # expandido (default); el colapsado lo da html.ec-sbc
    _foot_h = "112px"
    css = ["<style>"]
    # Contenedor del sidebar: fondo AZUL OSCURO, SIN borde.
    # IMPORTANTE: el cambio de ANCHO es INSTANTÁNEO (0s). Una transición de width
    # hace que el observer del "sidebar redimensionable" de Streamlit pelee el
    # cambio (re-aplica el ancho cada frame), dejando la transición atascada en
    # 256px → el sidebar NO colapsaba. Con cambio instantáneo, Streamlit no
    # alcanza a revertirlo. (Las posiciones del header/FAB también van instantáneas
    # para que todo cambie a la vez, sin desfases.)
    _t = "0s"
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
    # El área de navegación DEBE scrollear (altura limitada al viewport): con
    # muchos items (root=16) la lista supera la pantalla y, si no scrollea, el
    # footer fijo (position:fixed; bottom:0) tapa los últimos items. El padding
    # reserva espacio para el brand (arriba) y el footer (abajo), ambos fijos.
    css.append(
        f'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]'
        f'{{padding:54px 0.55rem calc({_foot_h} + 6px)!important;'
        f'box-sizing:border-box!important;height:100vh!important;max-height:100vh!important;'
        f'overflow-y:auto!important;overflow-x:hidden!important;}}'
    )
    # BRAND fijo arriba — width estática `ancho` (Python la sabe correcta en
    # CADA render) + transición. NO usar --sb-w (el JS del iframe es async y
    # a veces dejaba un valor viejo, descuadrando el brand). El elemento
    # persiste entre reruns, así la transición anima de viejo a nuevo ancho.
    css.append(
        f'.st-key-_sb_brand_full,.st-key-_sb_brand_mini'
        f'{{position:fixed!important;top:0!important;left:0!important;width:{ancho}!important;'
        f'z-index:7!important;background:#0f172a!important;box-sizing:border-box!important;'
        f'padding:10px 12px 8px!important;transition:width {_t}!important;'
        f'overflow:hidden!important;}}'
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
        f'z-index:7!important;box-sizing:border-box!important;'
        f'padding:8px 0.3rem 10px!important;box-shadow:0 -8px 16px rgba(11,18,32,0.9)!important;'
        f'overflow:hidden!important;transition:width {_t}!important;}}'
    )
    # Ocultar el header nativo del sidebar (la barra superior de Streamlit con el
    # botón de colapso) — es lo que metía el gran espacio arriba. Usamos el nuestro.
    css.append(
        'section[data-testid="stSidebar"] [data-testid="stSidebarHeader"]{display:none!important;height:0!important;min-height:0!important;padding:0!important;}'
        'section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"]{display:none!important;}'
    )
    # El header fijo arranca después del sidebar. left estático `ancho` +
    # transición (el header bar persiste entre reruns → anima suave).
    css.append(f'#_usr_header_bar{{left:{ancho}!important;transition:left {_t}!important;}}')
    # FAB Guardar: se corre a la derecha del sidebar con el `ancho` estático
    # (correcto en cada render) + transición. El elemento .st-key-btn_fab_guardar
    # persiste entre reruns, así anima de la posición vieja a la nueva.
    css.append(f'.st-key-btn_fab_guardar{{left:calc({ancho} + 1.2rem)!important;transition:left {_t}!important;}}')
    # Scrollbar fino para el area de navegacion (el contenido scrollea)
    css.append(
        'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar{width:6px;}'
        'section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar-thumb'
        '{background:rgba(148,163,184,0.25);border-radius:3px;}'
    )
    # Botones de navegacion (generico) — tipografía de los títulos de PRESUPUESTO
    # (Montserrat 700, 0.88rem, letter-spacing 0.05em, UPPERCASE). El color se
    # mantiene CLARO (#cbd5e1) porque el sidebar es oscuro (#0f172a sería invisible).
    css.append(
        'section[data-testid="stSidebar"] .stButton button{width:100%!important;'
        'justify-content:flex-start!important;gap:12px!important;background:transparent!important;'
        'border:1px solid transparent!important;color:#cbd5e1!important;font-family:Montserrat,sans-serif!important;'
        'font-weight:700!important;font-size:0.8rem!important;letter-spacing:0.05em!important;'
        'text-transform:uppercase!important;border-radius:10px!important;'
        'padding:9px 12px!important;margin:1px 0!important;min-height:0!important;'
        'box-shadow:none!important;transition:background .12s,color .12s;}'
    )
    # El texto del botón vive en un stMarkdownContainer hijo con su PROPIA
    # font-family (Source Sans Pro) y font-size (16px) que pisan la del <button>.
    # Hay que forzar la tipografía AHÍ para que sea idéntica a los títulos de
    # PRESUPUESTO (Montserrat 0.88rem). El line-height 1.6 da la misma altura.
    css.append(
        'section[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"],'
        'section[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"] p,'
        'section[data-testid="stSidebar"] .stButton button p{'
        'font-family:Montserrat,sans-serif!important;font-weight:700!important;font-size:0.8rem!important;'
        'letter-spacing:0.05em!important;line-height:1.6!important;text-transform:uppercase!important;}'
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
    # Expandido: el ícono tiene margin-right para separarse del texto. Cursor
    # pointer en todo el toggle (lo intercepta el JS para colapsar sin rerun).
    css.append(
        '.st-key-_sb_toggle button{width:100%!important;cursor:pointer!important;'
        'justify-content:center!important;background:transparent!important;border:none!important;'
        'box-shadow:none!important;color:#94a3b8!important;border-radius:10px!important;'
        'padding:9px 0!important;min-height:0!important;overflow:visible!important;}'
        '.st-key-_sb_toggle button:hover'
        '{background:transparent!important;border:none!important;border-color:transparent!important;color:#cbd5e1!important;}'
        '.st-key-_sb_toggle button:focus,'
        '.st-key-_sb_toggle button:active'
        '{background:transparent!important;border:none!important;box-shadow:none!important;color:#94a3b8!important;}'
        f'.st-key-_sb_toggle button::before{{content:"";flex-shrink:0;'
        f'width:20px;height:20px;margin:0 8px 0 0;'
        f'background:url("{_svg_uri("_collapse", _COL_IDLE)}") no-repeat center/contain;}}'
        # Mini-logo "C": oculto en expandido (se muestra sólo colapsado).
        '.ec-brand-mini{display:none!important;}'
    )
    # ══ Estado COLAPSADO — se activa con la clase html.ec-sbc (la añade/quita el
    #    JS y la persiste en localStorage). Sin rerun de Python. Mismas reglas que
    #    antes, prefijadas con la clase para que sólo apliquen colapsado. ════════
    _C = "html.ec-sbc "
    # Anchos / posiciones (animan por las transiciones del estado expandido).
    css.append(
        f'{_C}section[data-testid="stSidebar"]{{width:76px!important;min-width:76px!important;}}'
        f'{_C}.st-key-_sb_brand_full{{width:76px!important;}}'
        f'{_C}.ec-brand-full{{display:none!important;}}'
        f'{_C}.ec-brand-mini{{display:flex!important;}}'
        f'{_C}.ec-sb-code{{display:none!important;}}'
        f'{_C}.st-key-_sb_bottom{{width:76px!important;}}'
        f'{_C}#_usr_header_bar{{left:76px!important;}}'
        f'{_C}.st-key-btn_fab_guardar{{left:calc(76px + 1.2rem)!important;}}'
    )
    # Base colapsada (padding/scroll del área de nav y footer)
    css.append(
        f'{_C}section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{{padding:0!important;margin:0!important;}}'
        f'{_C}section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]{{padding:54px 0 60px!important;scrollbar-width:none!important;}}'
        f'{_C}section[data-testid="stSidebar"] [data-testid="stSidebarUserContent"]::-webkit-scrollbar{{width:0!important;display:none!important;}}'
        f'{_C}section[data-testid="stSidebar"] .st-key-_sb_nav{{padding-left:0!important;padding-right:0!important;width:100%!important;}}'
        f'{_C}.st-key-_sb_bottom{{padding:6px 0 8px!important;box-shadow:none!important;overflow:hidden!important;}}'
        f'{_C}section[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"],'
        f'{_C}section[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{{width:100%!important;margin:0!important;padding:0!important;}}'
        f'{_C}section[data-testid="stSidebar"] [data-testid="stElementContainer"],'
        f'{_C}section[data-testid="stSidebar"] .stButton{{width:100%!important;padding:0!important;margin:0!important;}}'
    )
    # Nav: .stButton posiciona, button transparente, icono centrado vía .stButton::before
    css.append(
        f'{_C}section[data-testid="stSidebar"] .st-key-_sb_nav .stButton{{position:relative!important;height:44px!important;}}'
        f'{_C}section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button{{'
        f'position:absolute!important;inset:0!important;background:transparent!important;border:none!important;'
        f'color:transparent!important;box-shadow:none!important;outline:none!important;'
        f'width:100%!important;height:100%!important;z-index:1!important;}}'
        f'{_C}section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button>*{{visibility:hidden!important;}}'
        f'{_C}section[data-testid="stSidebar"] .st-key-_sb_nav .stButton button::before{{display:none!important;}}'
    )
    for it in items:
        k = it["key"]; ic = it.get("icon", "")
        _color = _COL_ACTIVE if k == activo else _COL_IDLE
        _icon_uri = _svg_uri(ic, _color)
        css.append(
            f'{_C}section[data-testid="stSidebar"] .st-key-nav_{k} .stButton::before{{'
            f'content:""!important;display:block!important;position:absolute!important;'
            f'left:50%!important;top:50%!important;transform:translate(-50%,-50%)!important;'
            f'width:22px!important;height:22px!important;'
            f'background:url("{_icon_uri}") no-repeat center/contain!important;'
            f'pointer-events:none!important;z-index:2!important;}}'
        )
        if k == activo:
            css.append(
                f'{_C}section[data-testid="stSidebar"] .st-key-nav_{k} .stButton{{'
                f'background:linear-gradient(135deg,{_ACCENT},#7c5cfa)!important;border-radius:10px!important;}}'
            )
    # Toggle colapsado: icono "expandir" centrado, texto oculto
    css.append(
        f'{_C}.st-key-_sb_toggle{{width:76px!important;padding:0!important;margin:0!important;display:block!important;}}'
        f'{_C}.st-key-_sb_toggle .stButton{{position:relative!important;height:48px!important;width:76px!important;padding:0!important;margin:0!important;display:block!important;}}'
        f'{_C}.st-key-_sb_toggle .stButton button{{position:absolute!important;left:0!important;top:0!important;'
        f'width:76px!important;height:48px!important;background:transparent!important;border:none!important;'
        f'color:transparent!important;box-shadow:none!important;outline:none!important;padding:0!important;margin:0!important;}}'
        f'{_C}.st-key-_sb_toggle .stButton button>*{{visibility:hidden!important;width:0!important;height:0!important;overflow:hidden!important;}}'
        f'{_C}.st-key-_sb_toggle .stButton button::before{{content:""!important;display:block!important;'
        f'position:absolute!important;left:50%!important;top:50%!important;transform:translate(-50%,-50%)!important;'
        f'margin:0!important;padding:0!important;width:22px!important;height:22px!important;flex:none!important;'
        f'background:url("{_svg_uri("_expand", _COL_IDLE)}") no-repeat center/contain!important;pointer-events:none!important;}}'
    )
    # Tooltip visible al hover
    css.append(
        f'{_C}section[data-testid="stSidebar"]{{overflow:visible!important;}}'
        '[data-baseweb="tooltip"],[role="tooltip"]{z-index:99999!important;}'
    )
    # En fullscreen de la tabla de PRESUPUESTO (html.pp-fs) el iframe cubre el
    # sidebar → correr Guardar y el tab de Margen a la izquierda del viewport
    # (sin el offset del ancho del sidebar). Al salir del fullscreen se quita
    # la clase y vuelven a su posición normal.
    # `body` extra en el selector del margen: sube la especificidad por encima
    # de la regla de sidebar colapsado (html.ec-sbc ...) que vive en
    # tab_cotizacion y se renderiza DESPUÉS → así pp-fs gana igual.
    css.append(
        'html.pp-fs .st-key-btn_fab_guardar{left:1.2rem!important;}'
        'html.pp-fs body section[data-testid="stMain"] div[data-testid="stPopover"]{left:0!important;}'
        'html.pp-fs body div[data-baseweb="popover"]:has(.ec-mg-marker){left:0!important;}'
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
    # El contenido se renderiza SIEMPRE completo (expandido). El colapso es puro
    # CSS (clase html.ec-sbc, gestionada por el JS de layout vía localStorage) →
    # no hay rerun al togglear, así que NO se re-renderiza este footer (evita el
    # botón duplicado) ni se ralentiza el sistema.
    st.markdown(_build_css(items, _actual), unsafe_allow_html=True)

    with st.sidebar:
        # Marca: mini-logo "C" (visible colapsado) + texto completo (expandido).
        # El CSS muestra uno u otro según html.ec-sbc.
        st.markdown(
            '<div class="st-key-_sb_brand_full" style="padding:6px 8px 12px;">'
            '<div class="ec-brand-mini" style="width:36px;height:36px;margin:2px auto 0;'
            'border-radius:10px;background:linear-gradient(135deg,#5b7cfa,#7c5cfa);'
            'align-items:center;justify-content:center;color:#fff;font-weight:900;'
            'font-family:Montserrat;">C</div>'
            '<div class="ec-brand-full">'
            '<div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.1rem;'
            'color:#fff;letter-spacing:0.04em;">COTIZADOR<span style="color:#5b7cfa;"> PRO</span></div>'
            '<div style="font-size:0.62rem;color:#64748b;font-weight:600;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-top:1px;">Panel de gestión</div></div></div>',
            unsafe_allow_html=True,
        )

        # Navegación (cada botón cambia la página → ese sí necesita rerun)
        with st.container(key="_sb_nav"):
            for it in items:
                if st.button(it["label"], key=f"nav_{it['key']}", use_container_width=True):
                    st.session_state["nav_page"] = it["key"]
                    st.rerun()

        # Sección inferior anclada: código de acceso + toggle
        with st.container(key="_sb_bottom"):
            # El código de acceso solo se muestra con el sidebar expandido
            if rol in ("root", "admin"):
                _cod_html = _codigo_acceso_html(False)
                if _cod_html:
                    st.markdown(f'<div class="ec-sb-code">{_cod_html}</div>', unsafe_allow_html=True)
            if st.button("Ocultar menú", key="_sb_toggle", use_container_width=True):
                pass

    return st.session_state["nav_page"]
