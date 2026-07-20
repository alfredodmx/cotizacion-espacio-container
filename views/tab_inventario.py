"""
Tab INVENTARIO — maestro de stock propio.

Ingreso de productos en stock: **categoría → ítem** salen de la Excel activa
(hoja 'BD Total', misma fuente que REGISTRO DE COMPRA), + cantidad, unidad, hasta
5 fotos, estado de calidad 1-10, observación y ubicación. Al guardar se registra
automáticamente quién lo hizo y la fecha/hora (Chile). Listado con búsqueda,
edición y baja lógica.

Acceso: root, admin y operacion (operador).
"""
import html as _html
from datetime import datetime

import streamlit as st

from views.layout import render_page_header
from repositories.inventario_repo import (
    fetch_categorias_items, guardar_inventario, listar_inventario,
    obtener_inventario, actualizar_inventario, eliminar_inventario,
    UNIDADES, MAX_FOTOS,
)

_ROLES_OK = ("root", "admin", "operacion")

_INV_CSS = """
<style>
div[class*="st-key-inv_form_card"]{background:#fff;border:1.5px solid #e8ebf5;
  border-radius:16px;padding:16px 20px 8px;box-shadow:0 2px 12px rgba(0,0,0,.05);
  margin-bottom:8px;}
div[class*="st-key-inv_card_"]{background:#fff;border:1.5px solid #e8ebf5;
  border-radius:14px;padding:13px 16px;box-shadow:0 2px 10px rgba(0,0,0,.04);
  margin-bottom:11px;transition:box-shadow .2s,border-color .2s;}
div[class*="st-key-inv_card_"]:hover{box-shadow:0 6px 20px rgba(91,124,250,.12);
  border-color:#c5ccf0;}
</style>
"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _svg(path, size=16, color="#2563eb"):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" style="flex-shrink:0;vertical-align:-2px;">'
            f'{path}</svg>')


def _titulo(texto, icon=""):
    st.markdown(
        '<div style="display:flex;align-items:center;gap:9px;margin:4px 0 12px;">'
        f'{icon}<span style="font-family:\'Montserrat\',sans-serif;font-weight:700;'
        'font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;'
        f'color:#0f172a;">{texto}</span></div>',
        unsafe_allow_html=True)


def _esc(s):
    return _html.escape(str(s if s is not None else ""))


def _cal_colors(v):
    if not v:
        return ("#f1f5f9", "#64748b")
    if v <= 3:
        return ("#fee2e2", "#dc2626")
    if v <= 6:
        return ("#fef3c7", "#d97706")
    return ("#dcfce7", "#16a34a")


def _cal_label(v):
    if not v:
        return ""
    if v <= 3:
        return "Malo"
    if v <= 6:
        return "Regular"
    if v <= 8:
        return "Bueno"
    return "Excelente"


def _fmt_fecha(s):
    if not s:
        return ""
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(s)[:16].replace("T", " ")


def _fmt_cant(c):
    try:
        f = float(c)
        return str(int(f)) if f == int(f) else f"{f:g}"
    except (TypeError, ValueError):
        return str(c)


@st.cache_data(ttl=60, show_spinner=False)
def _inv_all():
    """Lista completa de inventario activo (cacheada; se limpia al mutar)."""
    return listar_inventario("")


# ── Formulario (ingreso / edición) ───────────────────────────────────────────

def _render_form(cat_items, rec, rol):
    editing = rec is not None
    sfx = f"e{rec['id']}" if editing else f"n{st.session_state.get('_inv_nonce', 0)}"

    with st.container(key="inv_form_card"):
        _ic = ('<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>'
               if editing else '<path d="M12 5v14"/><path d="M5 12h14"/>')
        _titulo("Editar producto" if editing else "Ingresar producto",
                _svg(_ic, 17, "#2563eb"))

        cats = list(cat_items.keys())
        if not cats and not editing:
            st.info("No hay una Excel activa con categorías. Sube una en "
                    "PROYECTO EXCEL para poder ingresar stock.")
            return
        if editing and rec.get("categoria") and rec["categoria"] not in cats:
            cats = [rec["categoria"]] + cats
        cat_idx = cats.index(rec["categoria"]) if editing and rec.get("categoria") in cats else 0

        c1, c2 = st.columns(2)
        with c1:
            categoria = st.selectbox("Categoría", cats,
                                     index=cat_idx if cats else 0,
                                     key=f"inv_cat_{sfx}") if cats else ""
        items = [x["item"] for x in cat_items.get(categoria, [])]
        if editing and rec.get("item") and rec["item"] not in items:
            items = [rec["item"]] + items
        item_idx = items.index(rec["item"]) if editing and rec.get("item") in items else 0
        with c2:
            item = st.selectbox("Producto", items,
                                index=item_idx if items else 0,
                                key=f"inv_item_{sfx}") if items else ""

        c3, c4 = st.columns(2)
        with c3:
            _cant0 = float(rec["cantidad"]) if editing and rec.get("cantidad") is not None else 0.0
            cantidad = st.number_input("Cantidad en stock", min_value=0.0, step=1.0,
                                       value=_cant0, key=f"inv_cant_{sfx}")
        with c4:
            uni_idx = UNIDADES.index(rec["unidad"]) if editing and rec.get("unidad") in UNIDADES else 0
            unidad = st.selectbox("Unidad", UNIDADES, index=uni_idx, key=f"inv_uni_{sfx}")

        ubicacion = st.text_input("Ubicación / bodega",
                                  value=rec.get("ubicacion", "") if editing else "",
                                  placeholder="Bodega A · Rack 3",
                                  key=f"inv_ubic_{sfx}")

        _cal0 = int(rec["calidad"]) if editing and rec.get("calidad") else 7
        calidad = st.slider("Estado de calidad (1 peor → 10 mejor)", 1, 10,
                            value=_cal0, key=f"inv_cal_{sfx}")
        _bg, _fg = _cal_colors(calidad)
        st.markdown(
            f'<div style="margin:-4px 0 10px;"><span style="background:{_bg};color:{_fg};'
            'font-family:Montserrat,sans-serif;font-weight:800;font-size:0.72rem;'
            'padding:3px 12px;border-radius:20px;letter-spacing:.03em;">'
            f'Calidad {calidad}/10 · {_cal_label(calidad)}</span></div>',
            unsafe_allow_html=True)

        # Fotos existentes (solo en edición): desmarcar para quitar.
        fotos_conservar = []
        if editing and rec.get("fotos"):
            st.markdown('<div style="font-size:0.72rem;color:#94a3b8;font-weight:700;'
                        'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px;">'
                        'Fotos actuales — desmarca para quitar</div>',
                        unsafe_allow_html=True)
            _cols = st.columns(MAX_FOTOS)
            for i, url in enumerate(rec["fotos"][:MAX_FOTOS]):
                with _cols[i]:
                    st.markdown(
                        f'<img src="{_esc(url)}" style="width:100%;height:66px;'
                        'object-fit:cover;border-radius:8px;border:1.5px solid #e2e8f0;">',
                        unsafe_allow_html=True)
                    if st.checkbox("Mantener", value=True, key=f"inv_keep_{sfx}_{i}"):
                        fotos_conservar.append(url)

        _restantes = MAX_FOTOS - len(fotos_conservar) if editing else MAX_FOTOS
        _lbl = (f"Agregar fotos (quedan {max(0, _restantes)} espacios)" if editing
                else f"Fotos del producto (hasta {MAX_FOTOS})")
        fotos = st.file_uploader(_lbl, type=["png", "jpg", "jpeg", "webp"],
                                 accept_multiple_files=True, key=f"inv_fotos_{sfx}")

        observacion = st.text_area("Observación",
                                   value=rec.get("observacion", "") if editing else "",
                                   placeholder="Detalle del producto, defectos, procedencia…",
                                   key=f"inv_obs_{sfx}")

        if editing:
            b1, b2 = st.columns(2)
            with b1:
                guardar = st.button("Guardar cambios", type="primary",
                                    use_container_width=True, key=f"inv_save_{sfx}")
            with b2:
                if st.button("Cancelar", use_container_width=True, key=f"inv_cancel_{sfx}"):
                    st.session_state.pop("_inv_edit", None)
                    st.rerun()
        else:
            guardar = st.button("Guardar en inventario", type="primary",
                                use_container_width=True, key=f"inv_save_{sfx}")
            st.markdown('<div style="text-align:center;color:#94a3b8;font-size:0.72rem;'
                        'margin-top:6px;">Se registra automáticamente quién guarda '
                        'y la fecha/hora</div>', unsafe_allow_html=True)

        if guardar:
            if not categoria or not item:
                st.warning("Selecciona categoría y producto.")
                return
            _tot_fotos = (len(fotos_conservar) if editing else 0) + len(fotos or [])
            if _tot_fotos > MAX_FOTOS:
                st.warning(f"Máximo {MAX_FOTOS} fotos en total.")
                return
            _nombre = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
            _email = st.session_state.get("auth_email", "")

            if editing:
                campos = {
                    "categoria": categoria, "item": item, "cantidad": float(cantidad),
                    "unidad": unidad, "calidad": int(calidad),
                    "observacion": observacion, "ubicacion": ubicacion,
                }
                ok, err = actualizar_inventario(
                    rec["id"], campos, files_nuevas=fotos,
                    fotos_conservar=fotos_conservar, actor=_nombre or _email)
                if ok:
                    _inv_all.clear()
                    st.session_state.pop("_inv_edit", None)
                    st.session_state["_inv_toast"] = "Producto actualizado."
                    if err:
                        st.session_state["_inv_error"] = f"Guardado, pero algunas fotos fallaron: {err}"
                    st.rerun()
                else:
                    st.error(f"No se pudo actualizar: {err}")
            else:
                new_id, err = guardar_inventario(
                    categoria, item, cantidad, unidad, calidad, observacion,
                    fotos, ubicacion, _email, _nombre)
                if new_id:
                    _inv_all.clear()
                    st.session_state["_inv_nonce"] = st.session_state.get("_inv_nonce", 0) + 1
                    st.session_state["_inv_toast"] = f"“{item}” agregado al inventario."
                    if err:
                        st.session_state["_inv_error"] = f"Guardado, pero algunas fotos fallaron: {err}"
                    st.rerun()
                else:
                    st.error(f"No se pudo guardar: {err}")


# ── Listado ──────────────────────────────────────────────────────────────────

_IC_BOX = _svg('<path d="M12 2 2 7l10 5 10-5-10-5Z"/><path d="m2 17 10 5 10-5"/>'
               '<path d="m2 12 10 5 10-5"/>', 13, "#64748b")
_IC_PIN = _svg('<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>'
               '<circle cx="12" cy="10" r="3"/>', 13, "#64748b")
_IC_CLOCK = _svg('<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
                 12, "#94a3b8")
_IC_IMG = _svg('<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/>'
               '<circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
               22, "#94a3b8")


def _render_card(d, rol, confirming):
    _id = d["id"]
    fotos = d.get("fotos") or []
    cal = d.get("calidad")
    _bg, _fg = _cal_colors(cal)

    if fotos:
        thumbs = "".join(
            f'<img src="{_esc(u)}" style="width:52px;height:52px;object-fit:cover;'
            'border-radius:8px;border:1.5px solid #e2e8f0;">' for u in fotos[:MAX_FOTOS])
        thumb_html = (f'<div style="display:flex;gap:5px;flex-wrap:wrap;max-width:174px;">'
                      f'{thumbs}</div>')
    else:
        thumb_html = ('<div style="width:60px;height:60px;border-radius:8px;background:#eef2ff;'
                      'display:flex;align-items:center;justify-content:center;">'
                      f'{_IC_IMG}</div>')

    cal_badge = (f'<span style="background:{_bg};color:{_fg};font-family:Montserrat,sans-serif;'
                 f'font-weight:800;font-size:0.66rem;padding:2px 9px;border-radius:20px;">'
                 f'Calidad {cal}/10</span>') if cal else ""
    ubic = d.get("ubicacion", "")
    ubic_html = f'<span>{_IC_PIN} {_esc(ubic)}</span>' if ubic else ""
    obs = d.get("observacion", "")
    obs_html = (f'<div style="margin-top:5px;font-size:0.75rem;color:#64748b;'
                f'font-family:Montserrat,sans-serif;">{_esc(obs)}</div>') if obs else ""
    quien = d.get("creado_por_nombre") or d.get("creado_por_email") or "—"
    fecha = _fmt_fecha(d.get("fecha_modificacion") or d.get("fecha_creacion"))

    card = (
        '<div style="display:flex;gap:14px;align-items:flex-start;">'
        f'{thumb_html}'
        '<div style="flex:1;min-width:0;">'
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
        f'<span style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.86rem;'
        f'letter-spacing:.03em;text-transform:uppercase;color:#0f172a;">{_esc(d.get("item",""))}</span>'
        f'<span style="background:#e0e7ff;color:#4338ca;font-family:Montserrat,sans-serif;'
        'font-weight:700;font-size:0.64rem;padding:2px 9px;border-radius:20px;'
        f'text-transform:uppercase;letter-spacing:.03em;">{_esc(d.get("categoria",""))}</span>'
        f'{cal_badge}</div>'
        '<div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:6px;'
        'font-family:Montserrat,sans-serif;font-size:0.77rem;color:#475569;font-weight:600;">'
        f'<span>{_IC_BOX} {_fmt_cant(d.get("cantidad"))} {_esc(d.get("unidad",""))}</span>'
        f'{ubic_html}</div>'
        f'{obs_html}'
        '<div style="margin-top:7px;font-size:0.69rem;color:#94a3b8;'
        f'font-family:Montserrat,sans-serif;">{_IC_CLOCK} {_esc(quien)} · {fecha}</div>'
        '</div></div>'
    )

    with st.container(key=f"inv_card_{_id}"):
        st.markdown(card, unsafe_allow_html=True)
        if confirming:
            cc1, cc2, _sp = st.columns([1.3, 1, 3])
            with cc1:
                if st.button("Sí, eliminar", type="primary",
                             use_container_width=True, key=f"inv_delyes_{_id}"):
                    ok, err = eliminar_inventario(_id)
                    st.session_state.pop("_inv_del_confirm", None)
                    if ok:
                        _inv_all.clear()
                        st.session_state["_inv_toast"] = "Producto eliminado del stock."
                    else:
                        st.session_state["_inv_error"] = f"No se pudo eliminar: {err}"
                    st.rerun()
            with cc2:
                if st.button("Cancelar", use_container_width=True, key=f"inv_delno_{_id}"):
                    st.session_state.pop("_inv_del_confirm", None)
                    st.rerun()
        else:
            cc1, cc2, _sp = st.columns([1, 1, 4])
            with cc1:
                if st.button("Editar", use_container_width=True, key=f"inv_ed_{_id}"):
                    st.session_state["_inv_edit"] = _id
                    st.session_state.pop("_inv_del_confirm", None)
                    st.rerun()
            with cc2:
                if st.button("Eliminar", use_container_width=True, key=f"inv_dl_{_id}"):
                    st.session_state["_inv_del_confirm"] = _id
                    st.rerun()


def _render_listado(rol):
    busqueda = st.text_input("Buscar en el stock",
                             placeholder="Producto, categoría, bodega…",
                             key="_inv_busca", label_visibility="collapsed")
    data = _inv_all()
    if busqueda:
        b = busqueda.strip().lower()
        data = [d for d in data if b in
                f"{d.get('item','')} {d.get('categoria','')} "
                f"{d.get('ubicacion','')} {d.get('observacion','')}".lower()]

    _titulo(f"En stock · {len(data)} producto(s)",
            _svg('<path d="M20 5H4a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1Z"/>'
                 '<path d="M4 10v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9"/>', 16, "#0f172a"))

    if not data:
        st.markdown('<div style="text-align:center;color:#94a3b8;padding:26px;'
                    'font-family:Montserrat,sans-serif;font-weight:600;">'
                    'Sin productos que coincidan.</div>', unsafe_allow_html=True)
        return
    _confirm = st.session_state.get("_inv_del_confirm")
    for d in data:
        _render_card(d, rol, _confirm == d["id"])


# ── Entrada del tab ──────────────────────────────────────────────────────────

def render_tab_inventario(**kwargs):
    _rol = st.session_state.get("rol_usuario", "ejecutivo")
    if _rol not in _ROLES_OK:
        render_page_header("inventario", "Inventario", "Stock propio")
        st.warning("No tienes acceso a esta sección.")
        return

    render_page_header("inventario", "Inventario",
                       "Stock propio · maestro de productos disponibles")
    st.markdown(_INV_CSS, unsafe_allow_html=True)

    _t = st.session_state.pop("_inv_toast", None)
    if _t:
        st.toast(_t)
    _e = st.session_state.pop("_inv_error", None)
    if _e:
        st.toast(_e)

    cat_items = fetch_categorias_items()

    _edit_id = st.session_state.get("_inv_edit")
    _rec = obtener_inventario(_edit_id) if _edit_id else None
    if _edit_id and not _rec:
        st.session_state.pop("_inv_edit", None)

    _render_form(cat_items, _rec, _rol)
    st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)
    _render_listado(_rol)
