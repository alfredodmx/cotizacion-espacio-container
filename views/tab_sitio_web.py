"""
Tab SITIO WEB — Productos de la tienda Shopify (solo root/admin).

Fase 1: conexión + catálogo (grilla read-only).
Fase 2/3 (esta): EDITAR un producto desde el sistema (sin entrar a Shopify) —
título, descripción, estado, tipo, etiquetas, precios y FOTOS (agregar por URL o
subida + eliminar). Cada guardado publica en la web REAL → pide confirmación.
Requiere que el token de Shopify tenga `write_products` (además de `read_products`).

Todo DEFENSIVO: si faltan credenciales o el token no tiene permisos, avisa claro.
"""
import base64
import streamlit as st
import streamlit.components.v1 as components
from views.layout import render_page_header
from utils import shopify as _shop

_IC = {
    "box": '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "img": '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "text": '<path d="M17 6.1H3"/><path d="M21 12.1H3"/><path d="M15.1 18H3"/>',
    "tag": '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
    "money": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
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


def _he(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


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
.sw-compare{font-size:0.72rem;color:#94a3b8;font-weight:600;margin-top:1px;}
.sw-compare s{color:#94a3b8;}
.sw-meta{font-size:0.68rem;color:#94a3b8;font-weight:600;margin-top:5px;display:flex;flex-wrap:wrap;gap:4px 10px;}
.sw-type{font-size:0.66rem;color:#64748b;background:#f1f5f9;border-radius:6px;padding:2px 7px;margin-top:8px;
  display:inline-block;font-weight:700;width:fit-content;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.sw-actions{display:flex;gap:7px;margin-top:11px;}
.sw-btn{flex:1;text-align:center;font-family:Montserrat,sans-serif;font-size:0.68rem;font-weight:800;
  text-transform:uppercase;letter-spacing:.03em;padding:7px 6px;border-radius:9px;text-decoration:none;transition:all .15s;
  border:none;cursor:pointer;line-height:1.5;}
.sw-btn-edit{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff!important;}
.sw-btn-edit:hover{filter:brightness(1.07);}
.sw-btn-web{background:#eef2ff;color:#2563eb!important;border:1px solid #dbe3ff;}
.sw-btn-web:hover{background:#dbe3ff;}
.sw-btn-adm{background:#f1f5f9;color:#475569!important;border:1px solid #e2e8f0;}
.sw-btn-adm:hover{background:#e2e8f0;}
.sw-note{background:#f8fafc;border:1px solid #e8ebf3;border-left:3px solid #5b7cfa;border-radius:0 12px 12px 0;
  padding:13px 16px;display:flex;gap:11px;align-items:flex-start;margin:2px 0 16px;}
.sw-note p{margin:0;font-size:0.82rem;color:#475569;line-height:1.55;}
.st-key-sw_editcmd{position:absolute!important;left:-9999px!important;top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}
.sw-ed-head{display:flex;gap:16px;align-items:center;background:#fff;border:1px solid #e8ebf3;border-radius:16px;
  padding:14px 18px;box-shadow:0 2px 12px rgba(15,23,42,.06);margin-bottom:6px;}
.sw-ed-thumb{width:74px;height:74px;border-radius:12px;overflow:hidden;flex-shrink:0;background:#f1f5f9;}
.sw-ed-thumb img{width:100%;height:100%;object-fit:cover;display:block;}
.sw-ed-name{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:1.05rem;color:#0f172a;line-height:1.2;}
.sw-ph-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}
.sw-ph{border:1px solid #e8ebf3;border-radius:12px;overflow:hidden;background:#fff;}
.sw-ph img{width:100%;aspect-ratio:1/1;object-fit:cover;display:block;}
</style>
"""

# Puente: click en "Editar" de una card → abre el editor (input oculto sw_editcmd).
_SW_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function fire(id){
    var inp=D.querySelector('.st-key-sw_editcmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, id+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  if(W._swEditH){ D.removeEventListener('click', W._swEditH, true); }
  W._swEditH=function(e){
    var t=e.target; if(!t||!t.closest) return;
    var b=t.closest('.sw-edit-btn'); if(!b) return;
    e.preventDefault(); e.stopPropagation();
    fire(b.getAttribute('data-editid')||'');
  };
  D.addEventListener('click', W._swEditH, true);
})();
</script>"""


def _clear_editor_state():
    for k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_ed_")]:
        st.session_state.pop(k, None)
    st.session_state.pop("sw_edit_prod", None)


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
                   "(`tu-tienda.myshopify.com`) y **SHOPIFY_TOKEN** en los secrets. El token (app custom) "
                   "necesita **read_products** y **write_products**.", icon=":material/warning:")
        return

    # ── Puente para abrir el editor ──
    _ec = st.text_input("editcmd", key="sw_editcmd", label_visibility="collapsed")
    if _ec and "|" in _ec:
        _eid, _ets = _ec.rsplit("|", 1)
        if _ets != st.session_state.get("sw_editcmd_ts"):
            st.session_state["sw_editcmd_ts"] = _ets
            _clear_editor_state()
            st.session_state["sw_edit_id"] = _eid.strip()
            st.rerun()

    # ── Modo EDITOR ──
    if st.session_state.get("sw_edit_id"):
        _render_editor(st.session_state["sw_edit_id"])
        components.html(_SW_JS, height=0)
        return

    # ── Modo CATÁLOGO ──
    st.markdown(
        f'<div class="sw-note">{_ic("info", "#5b7cfa", 18, 0, 0)}'
        '<p><b>Edita tus productos sin entrar a Shopify.</b> Pulsa <b>Editar</b> en cualquier producto '
        'para cambiar título, descripción, precio, estado, etiquetas y <b>fotos</b>. Cada cambio se '
        'publica en la web real, con confirmación previa.</p></div>',
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
        components.html(_SW_JS, height=0)
        return
    if not _prods:
        st.info("No hay productos con ese estado en la tienda.")
        components.html(_SW_JS, height=0)
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
        # Precio antes (compare_at_price, tachado) si alguna variante lo tiene.
        _cmps = []
        for v in _vars:
            try:
                _cv = float(v.get("compare_at_price") or 0)
                if _cv > 0:
                    _cmps.append(_cv)
            except Exception:
                pass
        _cmp_html = (f'<div class="sw-compare">Antes: <s>{_fmt_clp(max(_cmps))}</s></div>' if _cmps else "")
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
            f'<div class="sw-price">{_price}</div>{_cmp_html}'
            f'<div class="sw-meta"><span>{_ic("img", "#94a3b8", 12, 4)}{len(_imgs)} foto(s)</span>'
            f'<span>{len(_vars)} variante(s)</span></div>'
            f'<div class="sw-type">{_ptype}</div>'
            f'<div class="sw-actions"><button type="button" class="sw-btn sw-btn-edit sw-edit-btn" '
            f'data-editid="{_he(p.get("id"))}">Editar</button></div>'
            '<div class="sw-actions" style="margin-top:6px;">'
            + (f'<a class="sw-btn sw-btn-web" href="{_he(_web)}" target="_blank">Ver</a>' if _web else "")
            + (f'<a class="sw-btn sw-btn-adm" href="{_he(_admp)}" target="_blank">Shopify</a>' if _admp else "")
            + '</div></div></div>')

    st.markdown(f'<div class="sw-grid">{_cards}</div>', unsafe_allow_html=True)
    components.html(_SW_JS, height=0)


def _render_editor(pid):
    """Editor de UN producto: datos + precios + fotos. Escribe a Shopify con confirmación."""
    if st.button("← Volver al catálogo", key="sw_ed_back"):
        st.session_state.pop("sw_edit_id", None)
        _clear_editor_state()
        _cargar_productos.clear()
        st.rerun()

    _p = st.session_state.get("sw_edit_prod")
    if not _p or str(_p.get("id")) != str(pid):
        with st.spinner("Cargando producto…"):
            _p, _err = _shop.get_producto(pid)
        if _err or not _p:
            st.error(_err or "No se pudo cargar el producto.", icon=":material/error:")
            return
        st.session_state["sw_edit_prod"] = _p

    _imgs = _p.get("images") or []
    _img0 = (_imgs[0].get("src") if _imgs else "")
    _thumb = (f'<img src="{_he(_img0)}" alt="">' if _img0 else "")
    st.markdown(
        '<div class="sw-ed-head">'
        f'<div class="sw-ed-thumb">{_thumb}</div>'
        f'<div><div class="sw-ed-name">{_he(_p.get("title") or "—")}</div>'
        f'<div style="font-size:0.76rem;color:#94a3b8;font-weight:600;margin-top:3px;">'
        f'{len(_imgs)} foto(s) · {len(_p.get("variants") or [])} variante(s) · ID {_he(_p.get("id"))}</div></div></div>',
        unsafe_allow_html=True)

    # ── Datos del producto ──
    st.markdown(f'<div class="sw-sec">{_ic("edit", "#0f172a", 16, 0)}Datos del producto</div>',
                unsafe_allow_html=True)
    _dc1, _dc2 = st.columns([3, 1])
    with _dc1:
        _title = st.text_input("Título", value=_p.get("title", "") or "", key="sw_ed_title")
    with _dc2:
        _status_opts = {"Activo": "active", "Borrador": "draft", "Archivado": "archived"}
        _cur = _p.get("status", "active")
        _sidx = list(_status_opts.values()).index(_cur) if _cur in _status_opts.values() else 0
        _status_lbl = st.selectbox("Estado (visibilidad en la web)", list(_status_opts.keys()),
                                   index=_sidx, key="sw_ed_status")
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        _ptype = st.text_input("Tipo de producto", value=_p.get("product_type", "") or "", key="sw_ed_type")
    with _tc2:
        _tags = st.text_input("Etiquetas (separadas por coma)", value=_p.get("tags", "") or "", key="sw_ed_tags")
    _desc = st.text_area("Descripción · acepta HTML", value=_p.get("body_html", "") or "",
                         height=220, key="sw_ed_desc",
                         help="Es la descripción que se ve en la ficha del producto en la web. Puedes usar HTML básico (<p>, <b>, <ul><li>…).")

    # ── Precios ──
    st.markdown(f'<div class="sw-sec">{_ic("money", "#0f172a", 16, 0)}Precios</div>', unsafe_allow_html=True)
    st.caption("«Precio antes» es el valor tachado que se muestra como precio anterior (para que se vea el "
               "descuento debe ser MAYOR que el precio actual). Déjalo en 0 para quitarlo.")
    _vars = _p.get("variants") or []
    _price_widgets = {}
    _cmp_widgets = {}
    for v in _vars:
        _vid = v.get("id")
        _vtitle = v.get("title") or ""
        if _vtitle and _vtitle.lower() != "default title":
            st.markdown(f'<div style="font-weight:700;color:#475569;font-size:0.82rem;margin:8px 0 2px;">'
                        f'{_he(_vtitle)}</div>', unsafe_allow_html=True)
        _cp1, _cp2 = st.columns(2)
        with _cp1:
            _price_widgets[_vid] = st.number_input(
                "Precio (ahora)", min_value=0.0, step=1000.0, format="%.0f",
                value=float(v.get("price") or 0), key=f"sw_ed_price_{_vid}")
        with _cp2:
            _cmp_widgets[_vid] = st.number_input(
                "Precio antes (tachado)", min_value=0.0, step=1000.0, format="%.0f",
                value=float(v.get("compare_at_price") or 0), key=f"sw_ed_cmp_{_vid}")

    # ── Guardar (con confirmación) ──
    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    _conf = st.checkbox("Entiendo que estos cambios se **publican en la web real**.", key="sw_ed_confirm")
    if st.button("Guardar y publicar", type="primary", disabled=not _conf,
                 key="sw_ed_save", icon=":material/cloud_upload:"):
        _errs = []
        with st.spinner("Guardando en Shopify…"):
            _ok, _e = _shop.actualizar_producto(pid, {
                "title": _title.strip(), "body_html": _desc,
                "status": _status_opts[_status_lbl],
                "product_type": _ptype.strip(), "tags": _tags.strip()})
            if not _ok:
                _errs.append(_e)
            for v in _vars:
                _vid = v.get("id")
                _vc = {}
                _np = _price_widgets.get(_vid)
                if _np is not None and abs(float(v.get("price") or 0) - float(_np)) > 0.5:
                    _vc["price"] = f"{_np:.0f}"
                _nc = _cmp_widgets.get(_vid)
                _curc = float(v.get("compare_at_price") or 0)
                if _nc is not None and abs(_curc - float(_nc)) > 0.5:
                    # 0 → null limpia el precio antes; >0 → lo fija.
                    _vc["compare_at_price"] = (f"{_nc:.0f}" if float(_nc) > 0 else None)
                if _vc:
                    _ov, _oe = _shop.actualizar_variante(_vid, _vc)
                    if not _ov:
                        _errs.append(_oe)
        if _errs:
            st.error("No se pudieron publicar algunos cambios: " + " · ".join(str(x) for x in _errs))
        else:
            st.session_state.pop("sw_edit_prod", None)   # refetch fresco
            _cargar_productos.clear()
            st.toast("Cambios publicados en la web.")
            st.rerun()

    # ── Fotos ──
    st.markdown(f'<div class="sw-sec">{_ic("img", "#0f172a", 16, 0)}Fotos '
                f'<span style="color:#94a3b8;font-weight:800;">· {len(_imgs)}</span></div>',
                unsafe_allow_html=True)
    if _imgs:
        _n = 4
        _rows = [_imgs[i:i + _n] for i in range(0, len(_imgs), _n)]
        for _row in _rows:
            _cols = st.columns(_n)
            for _j, im in enumerate(_row):
                with _cols[_j]:
                    _src = im.get("src", "")
                    if _src:
                        st.markdown(f'<div class="sw-ph"><img src="{_he(_src)}" alt=""></div>',
                                    unsafe_allow_html=True)
                    if st.button("Eliminar", key=f"sw_ed_delimg_{im.get('id')}", use_container_width=True,
                                 icon=":material/delete:"):
                        with st.spinner("Eliminando foto…"):
                            _ok, _e = _shop.eliminar_imagen(pid, im.get("id"))
                        if _ok:
                            st.session_state.pop("sw_edit_prod", None)
                            _cargar_productos.clear()
                            st.toast("Foto eliminada.")
                            st.rerun()
                        else:
                            st.error(_e)
    else:
        st.caption("Este producto no tiene fotos todavía.")

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    _ac1, _ac2 = st.columns(2)
    with _ac1:
        _newurl = st.text_input("Agregar foto por URL", key="sw_ed_newimg_url",
                                placeholder="https://…/foto.jpg")
        if st.button("Agregar por URL", key="sw_ed_addurl", use_container_width=True,
                     icon=":material/add_link:", disabled=not (_newurl or "").strip()):
            with st.spinner("Subiendo foto…"):
                _ok, _e = _shop.agregar_imagen(pid, src=_newurl.strip())
            if _ok:
                st.session_state.pop("sw_edit_prod", None)
                st.session_state.pop("sw_ed_newimg_url", None)
                _cargar_productos.clear()
                st.toast("Foto agregada.")
                st.rerun()
            else:
                st.error(_e)
    with _ac2:
        _up = st.file_uploader("O súbela desde tu equipo", type=["jpg", "jpeg", "png", "webp"],
                               key="sw_ed_upimg")
        if _up is not None and st.button("Subir esta foto", key="sw_ed_addup",
                                         use_container_width=True, icon=":material/upload:"):
            try:
                _b64 = base64.b64encode(_up.getvalue()).decode()
            except Exception:
                _b64 = ""
            if not _b64:
                st.error("No se pudo leer el archivo.")
            else:
                with st.spinner("Subiendo foto…"):
                    _ok, _e = _shop.agregar_imagen(pid, attachment=_b64, filename=_up.name)
                if _ok:
                    st.session_state.pop("sw_edit_prod", None)
                    _cargar_productos.clear()
                    st.toast("Foto subida.")
                    st.rerun()
                else:
                    st.error(_e)
