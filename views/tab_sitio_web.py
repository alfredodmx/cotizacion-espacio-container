"""
Tab SITIO WEB — Productos de la tienda Shopify (solo root/admin).

Fase 1 (esta): CONEXIÓN + listado de productos (activos/borradores/archivados) con
foto, precio, estado y accesos directos a la web y al admin de Shopify. Read-only.
Fases siguientes (edición desde acá, sin entrar a Shopify): descripción/título/tags/
estado → fotos (agregar/reordenar/eliminar) → características (metafields) → videos.

Todo DEFENSIVO: si faltan credenciales o el token no tiene `read_products`, se
muestra un aviso claro y no se rompe nada.
"""
import streamlit as st
from views.layout import render_page_header
from utils import shopify as _shop

_IC = {
    "globe": '<circle cx="12" cy="12" r="10"/><line x1="2" x2="22" y1="12" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
    "box": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "img": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
}


def _ic(name, color="#64748b", size=16, mr=8, valign=-3):
    _mr = f"margin-right:{mr}px;" if mr else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:{valign}px;{_mr}flex-shrink:0;">{_IC.get(name, "")}</svg>')


def _fmt_clp(v) -> str:
    try:
        return "$" + "{:,.0f}".format(float(v)).replace(",", ".")
    except Exception:
        return "—"


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_productos(status, _cb=""):
    return _shop.listar_productos(status=status)


_CSS = """
<style>
.sw-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #e2e8f0;
  margin:20px 0 14px;display:flex;align-items:center;gap:9px;}
.sw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:16px;}
.sw-card{background:#fff;border:1px solid #e8ebf3;border-radius:15px;overflow:hidden;
  box-shadow:0 2px 12px rgba(15,23,42,.06);display:flex;flex-direction:column;transition:all .18s;}
.sw-card:hover{transform:translateY(-3px);box-shadow:0 10px 26px rgba(15,23,42,.12);border-color:#cdd6ea;}
.sw-thumb{aspect-ratio:1/1;background:#f1f5f9;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;}
.sw-thumb img{width:100%;height:100%;object-fit:cover;display:block;}
.sw-thumb .sw-noimg{color:#cbd5e1;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}
.sw-badge{position:absolute;top:9px;left:9px;font-family:Montserrat,sans-serif;font-size:9.5px;font-weight:800;
  text-transform:uppercase;letter-spacing:.04em;padding:3px 9px;border-radius:99px;}
.sw-body{padding:12px 13px 13px;display:flex;flex-direction:column;flex:1;}
.sw-title{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:0.86rem;color:#0f172a;line-height:1.25;
  margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;min-height:2.1em;}
.sw-price{font-family:Montserrat,sans-serif;font-weight:900;font-size:1.02rem;color:#0f172a;}
.sw-meta{font-size:0.68rem;color:#94a3b8;font-weight:600;margin-top:5px;display:flex;flex-wrap:wrap;gap:4px 10px;}
.sw-type{font-size:0.66rem;color:#64748b;background:#f1f5f9;border-radius:6px;padding:2px 7px;margin-top:8px;
  display:inline-block;font-weight:700;width:fit-content;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sw-actions{display:flex;gap:7px;margin-top:11px;}
.sw-btn{flex:1;text-align:center;font-family:Montserrat,sans-serif;font-size:0.68rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.03em;padding:7px 6px;border-radius:9px;text-decoration:none;transition:all .15s;}
.sw-btn-web{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff!important;}
.sw-btn-web:hover{filter:brightness(1.07);}
.sw-btn-adm{background:#f1f5f9;color:#475569!important;border:1px solid #e2e8f0;}
.sw-btn-adm:hover{background:#e2e8f0;}
.sw-note{background:#f8fafc;border:1px solid #e8ebf3;border-left:3px solid #5b7cfa;border-radius:0 12px 12px 0;
  padding:13px 16px;display:flex;gap:11px;align-items:flex-start;margin:2px 0 16px;}
.sw-note p{margin:0;font-size:0.82rem;color:#475569;line-height:1.55;}
</style>
"""


def render_tab_sitio_web(**kwargs):
    if st.session_state.get("rol_usuario", "ejecutivo") not in ("root", "admin"):
        st.info("Esta sección es solo para administradores (admin y root).", icon=":material/lock:")
        return

    st.markdown(_CSS, unsafe_allow_html=True)
    render_page_header(
        "sitio_web",
        "Sitio web",
        "Productos de la tienda Shopify &middot; edítalos desde aquí sin entrar a Shopify &middot; solo admin y root.",
    )

    if not _shop.configurado():
        st.warning("Aún no está configurada la conexión con Shopify. Agrega **SHOPIFY_STORE** "
                   "(`tu-tienda.myshopify.com`) y **SHOPIFY_TOKEN** en los secrets de Streamlit. "
                   "El token (app custom) necesita los permisos **read_products** y **write_products**.",
                   icon=":material/warning:")
        return

    # Nota de alcance de la fase.
    st.markdown(
        f'<div class="sw-note">{_ic("info", "#5b7cfa", 18, 0, 0)}'
        '<p><b>Fase 1 — conexión y catálogo.</b> Acá se ven los productos que están en la web. '
        'La edición desde el sistema (fotos, descripción, características, videos) se habilita en '
        'las siguientes fases, con confirmación antes de publicar en la web real.</p></div>',
        unsafe_allow_html=True)

    _opts = {"Activos": "active", "Borradores": "draft", "Archivados": "archived", "Todos": ""}
    _c1, _c2 = st.columns([4, 1], vertical_alignment="bottom")
    with _c1:
        st.markdown(
            "<style>.st-key-sw_estado label,.st-key-sw_estado label *{font-family:Montserrat,sans-serif!important;"
            "font-weight:700!important;font-size:0.84rem!important;letter-spacing:0.04em!important;"
            "text-transform:uppercase!important;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;}</style>",
            unsafe_allow_html=True)
        _lbl = st.radio("Estado", list(_opts.keys()), horizontal=True, index=0,
                        key="sw_estado", label_visibility="collapsed")
    with _c2:
        if st.button("Actualizar", key="sw_refresh", use_container_width=True, icon=":material/refresh:"):
            _cargar_productos.clear()
            st.rerun()
    _status = _opts[_lbl]

    with st.spinner("Conectando con Shopify y trayendo los productos…"):
        _prods, _err = _cargar_productos(_status)

    if _err:
        st.error(_err, icon=":material/error:")
        return
    if not _prods:
        st.info("No hay productos con ese estado en la tienda.")
        return

    _adm = _shop.store_admin_url()
    st.markdown(
        f'<div class="sw-sec">{_ic("box", "#0f172a", 17, 0)}Productos en la web '
        f'<span style="color:#94a3b8;font-weight:800;">· {len(_prods)}</span>'
        + (f'<a href="{_adm}/products" target="_blank" style="margin-left:auto;font-family:Montserrat;'
           f'font-size:0.7rem;font-weight:800;text-transform:uppercase;letter-spacing:.03em;color:#5b7cfa;'
           f'text-decoration:none;">Abrir en Shopify ↗</a>' if _adm else "")
        + '</div>', unsafe_allow_html=True)

    _bcol = {"active": ("#dcfce7", "#15803d", "Activo"),
             "draft": ("#fef9c3", "#854d0e", "Borrador"),
             "archived": ("#e2e8f0", "#475569", "Archivado")}

    def _he(s):
        return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    _cards = ""
    for p in _prods:
        _title = _he(p.get("title") or "(sin título)")
        _imgs = p.get("images") or []
        _img0 = (_imgs[0].get("src") if _imgs else "") or (p.get("image") or {}).get("src", "")
        _thumb = (f'<img src="{_he(_img0)}" alt="" loading="lazy">' if _img0
                  else '<span class="sw-noimg">Sin foto</span>')
        _vars = p.get("variants") or []
        _prices = []
        for v in _vars:
            try:
                _prices.append(float(v.get("price") or 0))
            except Exception:
                pass
        if _prices:
            _pmin, _pmax = min(_prices), max(_prices)
            _price = _fmt_clp(_pmin) if _pmin == _pmax else f"{_fmt_clp(_pmin)} – {_fmt_clp(_pmax)}"
        else:
            _price = "—"
        _bg, _fg, _blbl = _bcol.get(p.get("status", "active"), _bcol["active"])
        _ptype = _he(p.get("product_type") or (p.get("tags") or "").split(",")[0].strip() or "Producto")
        _web = _shop.producto_web_url(p.get("handle"))
        _admp = _shop.producto_admin_url(p.get("id"))
        _cards += (
            '<div class="sw-card">'
            f'<div class="sw-thumb">{_thumb}'
            f'<span class="sw-badge" style="background:{_bg};color:{_fg};">{_blbl}</span></div>'
            '<div class="sw-body">'
            f'<div class="sw-title">{_title}</div>'
            f'<div class="sw-price">{_price}</div>'
            f'<div class="sw-meta"><span>{_ic("img", "#94a3b8", 12, 4)}{len(_imgs)} foto(s)</span>'
            f'<span>{len(_vars)} variante(s)</span></div>'
            f'<div class="sw-type">{_ptype}</div>'
            '<div class="sw-actions">'
            + (f'<a class="sw-btn sw-btn-web" href="{_he(_web)}" target="_blank">Ver en la web</a>' if _web else "")
            + (f'<a class="sw-btn sw-btn-adm" href="{_he(_admp)}" target="_blank">Shopify</a>' if _admp else "")
            + '</div></div></div>')

    st.markdown(f'<div class="sw-grid">{_cards}</div>', unsafe_allow_html=True)
