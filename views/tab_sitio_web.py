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
import uuid as _uuid
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
    "video": '<path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/>',
    "house": '<path d="M3 21h18"/><path d="M5 21V8l7-4.5L19 8v13"/><path d="M9.5 21v-6h5v6"/><path d="M9.5 10.5h1.5M13 10.5h1.5"/>',
    "draft": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h6"/><path d="M8 17h5"/>',
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


# Tipos de metafield que ofrecemos al crear (etiqueta → tipo Shopify).
_MF_TIPOS = {
    "Texto": "single_line_text_field",
    "Texto largo": "multi_line_text_field",
    "Número entero": "number_integer",
    "Número decimal": "number_decimal",
    "Sí / No": "boolean",
}


def _mf_label(mf) -> str:
    """Nombre legible de un metafield a partir de su key (metros_cuadrados → Metros cuadrados)."""
    k = str(mf.get("key", "")).replace("_", " ").replace("-", " ").strip()
    return (k[:1].upper() + k[1:]) if k else "(sin clave)"


def _mf_widget(mf, keyp):
    """Widget de valor adaptado al tipo del metafield (para editar el existente)."""
    t = mf.get("type", "single_line_text_field")
    val = mf.get("value", "")
    if t == "boolean":
        return st.checkbox("v", value=(str(val).strip().lower() == "true"), key=keyp, label_visibility="collapsed")
    if t == "number_integer":
        try:
            _iv = int(float(val or 0))
        except Exception:
            _iv = 0
        return st.number_input("v", value=_iv, step=1, key=keyp, label_visibility="collapsed")
    if t == "number_decimal":
        try:
            _fv = float(val or 0)
        except Exception:
            _fv = 0.0
        return st.number_input("v", value=_fv, step=0.1, format="%.2f", key=keyp, label_visibility="collapsed")
    if t == "multi_line_text_field":
        return st.text_area("v", value=str(val or ""), key=keyp, height=80, label_visibility="collapsed")
    return st.text_input("v", value=str(val or ""), key=keyp, label_visibility="collapsed")


def _mf_serialize(t, w) -> str:
    """Serializa el valor del widget al formato string que espera Shopify según el tipo."""
    if t == "boolean":
        return "true" if w else "false"
    if t == "number_integer":
        try:
            return str(int(w))
        except Exception:
            return "0"
    if t == "number_decimal":
        try:
            s = ("%.4f" % float(w)).rstrip("0").rstrip(".")
            return s or "0"
        except Exception:
            return "0"
    return str(w)


def _mf_is_empty(t, val) -> bool:
    """True si el valor serializado equivale a 'vacío' (para NO crear un metacampo
    definido pero que el usuario dejó en blanco/0/No)."""
    s = str(val or "").strip()
    if t == "boolean":
        return s != "true"
    if t in ("number_integer", "number_decimal"):
        try:
            return float(s or 0) == 0
        except Exception:
            return True
    return s == ""


# Clasificación de metafields para mostrarlos amigables (no técnicos).
def _mf_kind(t) -> str:
    t = t or ""
    if t == "rich_text_field":
        return "rich"
    if t == "boolean":
        return "bool"
    if t == "number_integer":
        return "int"
    if t == "number_decimal":
        return "dec"
    if t == "multi_line_text_field":
        return "multi"
    if t in ("single_line_text_field", "string"):
        return "text"
    return "readonly"   # referencias, json, listas, dimensiones… → solo lectura (Avanzados)


_MF_KIND_LABEL = {"rich": "Texto con formato", "bool": "Sí / No", "int": "Número",
                  "dec": "Número", "multi": "Texto", "text": "Texto", "readonly": "Avanzado"}


def _richtext_to_text(value) -> str:
    """Aplana el rich_text de Shopify (AST JSON {type:root,children:…}) a texto legible:
    párrafos en líneas, ítems de lista con '- '. Si no es JSON, devuelve el texto tal cual."""
    import json
    try:
        node = json.loads(value) if isinstance(value, str) else value
    except Exception:
        return str(value or "")
    if not isinstance(node, dict):
        return str(value or "")

    def _inline(children):
        out = []
        for c in (children or []):
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                out.append(c.get("value", ""))
            else:
                out.append(_inline(c.get("children")))
        return "".join(out)

    lines = []

    def _walk(n):
        _t = n.get("type")
        if _t == "root":
            for ch in n.get("children", []):
                _walk(ch)
        elif _t == "list":
            for li in n.get("children", []):
                lines.append("- " + _inline(li.get("children")))
        elif _t in ("paragraph", "heading", "list-item"):
            _pref = "- " if _t == "list-item" else ""
            lines.append(_pref + _inline(n.get("children")))
        else:
            _txt = _inline(n.get("children"))
            if _txt:
                lines.append(_txt)

    _walk(node)
    return "\n".join(lines).strip()


def _text_to_richtext(text) -> str:
    """Reconstruye un rich_text válido de Shopify desde texto plano: cada línea = párrafo;
    líneas que empiezan con '- ' se agrupan como lista con viñetas."""
    import json
    children, buf = [], []

    def _flush():
        if buf:
            children.append({"type": "list", "listType": "unordered",
                             "children": [{"type": "list-item",
                                           "children": [{"type": "text", "value": x}]} for x in buf]})
            buf.clear()

    for ln in str(text or "").split("\n"):
        s = ln.rstrip()
        if s.strip().startswith("- "):
            buf.append(s.strip()[2:].strip())
        else:
            _flush()
            if s.strip():
                children.append({"type": "paragraph", "children": [{"type": "text", "value": s}]})
    _flush()
    if not children:
        children = [{"type": "paragraph", "children": [{"type": "text", "value": ""}]}]
    return json.dumps({"type": "root", "children": children}, ensure_ascii=False)


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_productos(status, _cb=""):
    return _shop.listar_productos(status=status)


# Estados efectivos = el campo `status` de Shopify (es lo que el admin muestra en la
# columna Estado). Ojo: además de active/draft/archived, existe `unlisted`, que Shopify
# rotula como "No publicado".
_ESTADOS = {
    "active":      ("#dcfce7", "#15803d", "Activo"),
    "unpublished": ("#fef3c7", "#b45309", "No publicado"),
    "draft":       ("#fef9c3", "#854d0e", "Borrador"),
    "archived":    ("#e2e8f0", "#475569", "Archivado"),
}


def _estado_efectivo(p) -> str:
    """Estado que muestra Shopify en la columna Estado = el campo `status`:
    active→Activo, unlisted→No publicado, draft→Borrador, archived→Archivado.
    (La publicación por canal es OTRA cosa y no cambia este estado: un producto
    'active' se ve Activo aunque no esté en ningún canal.)"""
    _s = str(p.get("status") or "").lower()
    if _s == "archived":
        return "archived"
    if _s == "draft":
        return "draft"
    if _s in ("unlisted", "unpublished"):
        return "unpublished"
    return "active"


@st.cache_data(ttl=600, show_spinner=False)
def _plantilla_metafields(_cb=""):
    """Plantilla MAESTRA de características: definiciones de metacampos + la UNIÓN de
    los metacampos que ya existen en los productos de la tienda. Así un producto nuevo
    (o incompleto) muestra TODOS los campos que trae un producto bien completado, aunque
    estén en blanco. Cacheada (algunos metacampos los crean apps sin 'definición', por
    eso no basta con listar_definiciones_metafields). Cada campo: {namespace,key,type,name}."""
    _campos = {}
    _defs, _ = _shop.listar_definiciones_metafields()
    for d in (_defs or []):
        _nk = (d.get("namespace") or "", d.get("key") or "")
        _campos[_nk] = {"namespace": _nk[0], "key": _nk[1],
                        "type": d.get("type") or "single_line_text_field", "name": d.get("name") or ""}
    _prods, _ = _shop.listar_productos(status="")
    for p in (_prods or [])[:20]:
        _mfs, _ = _shop.listar_metafields(p.get("id"))
        for m in (_mfs or []):
            _nk = (m.get("namespace") or "", m.get("key") or "")
            if _nk not in _campos:
                _campos[_nk] = {"namespace": _nk[0], "key": _nk[1],
                                "type": m.get("type") or "single_line_text_field", "name": ""}
    return list(_campos.values())


_CSS = """
<style>
.sw-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #e2e8f0;
  margin:20px 0 14px;display:flex;align-items:center;gap:9px;}
.sw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:16px;}
.sw-card{background:#fff;border:1px solid #e8ebf3;border-radius:15px;overflow:hidden;
  box-shadow:0 2px 12px rgba(15,23,42,.06);display:flex;flex-direction:column;transition:all .18s;}
.sw-card:hover{transform:translateY(-3px);box-shadow:0 10px 26px rgba(15,23,42,.12);border-color:#cdd6ea;}
.sw-thumb{aspect-ratio:1/1;background:#f1f5f9;display:flex;align-items:center;justify-content:center;overflow:hidden;position:relative;cursor:pointer;}
.sw-thumb img{width:100%;height:100%;object-fit:cover;display:block;transition:transform .25s ease;}
.sw-thumb:hover img{transform:scale(1.04);}
.sw-thumb .sw-noimg{color:#cbd5e1;font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}
/* Overlay "Editar" al pasar el mouse sobre la imagen de la card. */
.sw-thumb .sw-edit-ov{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;gap:7px;
  background:rgba(15,23,42,.48);color:#fff;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.72rem;
  letter-spacing:.06em;text-transform:uppercase;opacity:0;transition:opacity .16s ease;pointer-events:none;}
.sw-thumb:hover .sw-edit-ov{opacity:1;}
/* Modo "Ordenar web": cards con manija de arrastre. */
.sw-ord-hint{font-family:Montserrat,sans-serif;font-weight:700;font-size:0.74rem;color:#64748b;margin:2px 0 12px;
  display:flex;align-items:center;gap:6px;}
.sw-ord-hint span{color:#94a3b8;letter-spacing:-3px;}
.sw-ord-card .sw-thumb{cursor:default;}
.sw-ord-card .sw-thumb:hover img{transform:none;}
.sw-ord-grip{position:absolute;top:8px;right:8px;width:30px;height:30px;border-radius:8px;background:rgba(15,23,42,.62);
  color:#fff;display:flex;align-items:center;justify-content:center;cursor:grab;z-index:4;}
.sw-ord-grip:active{cursor:grabbing;background:#5b7cfa;}
.sw-ord-grip svg{width:16px;height:16px;pointer-events:none;}
.sw-card.sw-dragging{opacity:.4;}
.sw-ord-savewrap{display:flex;justify-content:center;margin:18px 0 6px;}
.sw-ord-savebtn{background:#aab2c5;color:#fff;border:none;border-radius:11px;padding:12px 34px;cursor:default;
  font-family:Montserrat,sans-serif;font-weight:800;font-size:0.8rem;letter-spacing:.05em;text-transform:uppercase;
  box-shadow:0 6px 18px rgba(15,23,42,.14);transition:background .15s ease;}
.sw-ord-savebtn.on{background:linear-gradient(135deg,#5b7cfa,#4f46e5);cursor:pointer;}
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
.sw-btn-dup{background:#f0fdf4;color:#15803d!important;border:1px solid #bbf7d0;}
.sw-btn-dup:hover{background:#dcfce7;}
.sw-btn-del{background:#fef2f2;color:#dc2626!important;border:1px solid #fecaca;}
.sw-btn-del:hover{background:#fee2e2;}
.sw-btn-web{background:#eef2ff;color:#2563eb!important;border:1px solid #dbe3ff;}
.sw-btn-web:hover{background:#dbe3ff;}
.sw-btn-adm{background:#f1f5f9;color:#475569!important;border:1px solid #e2e8f0;}
.sw-btn-adm:hover{background:#e2e8f0;}
.sw-note{background:#f8fafc;border:1px solid #e8ebf3;border-left:3px solid #5b7cfa;border-radius:0 12px 12px 0;
  padding:13px 16px;display:flex;gap:11px;align-items:flex-start;margin:2px 0 16px;}
.sw-note p{margin:0;font-size:0.82rem;color:#475569;line-height:1.55;}
.st-key-sw_editcmd,.st-key-sw_savecmd,.st-key-sw_ordcmd{position:absolute!important;left:-9999px!important;top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}
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
  function fire(payload){
    var inp=D.querySelector('.st-key-sw_editcmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, payload+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      // Secuencia COMPLETA (si no, el 2º/3º clic no commitea a Python y "no deja editar").
      inp.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.dispatchEvent(new FocusEvent('blur',{bubbles:true}));
      inp.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  if(W._swEditH){ D.removeEventListener('click', W._swEditH, true); }
  W._swEditH=function(e){
    var t=e.target; if(!t||!t.closest) return;
    var b=t.closest('.sw-edit-btn'); if(!b) return;
    e.preventDefault(); e.stopPropagation();
    var act=b.getAttribute('data-swact')||'edit';
    var id=b.getAttribute('data-swid')||b.getAttribute('data-editid')||'';
    fire(act+':'+id);
  };
  D.addEventListener('click', W._swEditH, true);
})();
</script>"""


# ── Selector de vista (Tarjetas / Tabla), disfrazado de pestañas igual que el CRM ──
_SW_VISTA_CSS = """
<style>
.st-key-sw_vista{border-bottom:2px solid #e2e6f3!important;margin-bottom:16px!important;}
.st-key-sw_vista [role="radiogroup"]{gap:0!important;flex-wrap:wrap!important;margin-bottom:0!important;padding:0!important;}
.st-key-sw_vista [role="radiogroup"] > label{background:transparent!important;border:none!important;position:relative!important;
  border-radius:0!important;padding:0.72rem 1.5rem!important;margin:0!important;cursor:pointer!important;color:#7c85b3!important;
  transition:color .2s!important;}
.st-key-sw_vista [role="radiogroup"] > label:hover{color:#5b7cfa!important;background:rgba(91,124,250,.05)!important;}
.st-key-sw_vista [role="radiogroup"] > label:has(input:checked){color:#5b7cfa!important;background:rgba(91,124,250,.06)!important;}
.st-key-sw_vista [role="radiogroup"] > label:has(input:checked)::after{content:'';position:absolute;left:0;right:0;
  bottom:-2px;height:2px;background:#5b7cfa;z-index:3;}
.st-key-sw_vista [role="radiogroup"] > label > div:first-child{display:none!important;}
.st-key-sw_vista [role="radiogroup"] label [data-testid="stMarkdownContainer"] p{
  font-family:'Plus Jakarta Sans',sans-serif!important;font-size:0.88rem!important;font-weight:700!important;
  text-transform:uppercase!important;letter-spacing:0.05em!important;margin:0!important;}
.st-key-sw_vista [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
.st-key-sw_vista [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p span{color:#7c85b3!important;}
.st-key-sw_vista [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p,
.st-key-sw_vista [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p span,
.st-key-sw_vista [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p,
.st-key-sw_vista [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p span{color:#5b7cfa!important;}
.st-key-sw_vista [role="radiogroup"] label span[role="img"][aria-label$=" icon"]{
  font-family:'Material Symbols Rounded'!important;font-weight:400!important;font-size:0.9rem!important;
  text-transform:none!important;letter-spacing:normal!important;}
</style>
"""


# ── Tabla HTML (iframe autocontenido): mismo diseño que la tabla de COTIZACIONES ──
_SW_TABLE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Montserrat:wght@700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:IFRAMEHPX;overflow:hidden;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;background:transparent;}
#wrap{display:flex;flex-direction:column;height:100%;position:relative;}
#bar2{display:flex;align-items:center;gap:8px;padding:0 0 9px;flex-shrink:0;}
#search{flex:1;min-width:0;height:42px;border:1.5px solid #e2e8f0;border-radius:11px;padding:0 13px;font-size:0.84rem;
  font-family:inherit;outline:none;color:#1e293b;background:#f8fafc;transition:border-color .2s,box-shadow .2s;}
#search:focus{border-color:#5b7cfa;background:#fff;box-shadow:0 0 0 3px rgba(91,124,250,.1);}
#cnt{font-size:0.72rem;color:#94a3b8;white-space:nowrap;font-weight:700;min-width:70px;text-align:right;}
#fsbtn{width:42px;height:42px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;color:#475569;
  cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;padding:0;transition:all .15s;}
#fsbtn:hover{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(37,99,235,.3);}
#fsbtn svg{width:17px;height:17px;display:block;}
html.fs,html.fs body,html.fs #wrap{height:100vh!important;}
html.fs body{padding:12px 16px!important;}
#tbl-w{flex:1;overflow:auto;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);border:1px solid #e2e8f0;}
#tbl-w::-webkit-scrollbar{width:7px;height:7px;}
#tbl-w::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px;}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:0.86rem;table-layout:auto;background:#fff;}
thead th{background:linear-gradient(135deg,#1e2447 0%,#2a3060 100%);color:#fff;font-weight:900;
  font-size:0.7rem;letter-spacing:0.07em;text-transform:uppercase;padding:11px 12px;white-space:nowrap;
  position:sticky;top:0;z-index:2;text-align:left;}
thead th.r{text-align:right;}
thead th.c{text-align:center;}
tbody td{padding:9px 12px;border-bottom:1px solid #f0f2f8;color:#3a4070;vertical-align:middle;}
tbody tr:hover td{background:#f5f7ff;}
tbody tr:last-child td{border-bottom:none;}
td.r{text-align:right;}
td.c{text-align:center;}
td.name{font-weight:700;color:#1e293b;max-width:250px;white-space:normal;line-height:1.3;}
td.price{font-weight:900;color:#0f172a;font-variant-numeric:tabular-nums;white-space:nowrap;}
td.antes{color:#94a3b8;font-variant-numeric:tabular-nums;white-space:nowrap;}
td.antes s{color:#94a3b8;}
.sw-tb-main{width:54px;height:54px;border-radius:9px;object-fit:cover;display:block;background:#f1f5f9;}
.sw-tb-noimg{width:54px;height:54px;border-radius:9px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;
  color:#cbd5e1;font-size:8px;font-weight:800;text-transform:uppercase;text-align:center;line-height:1.1;}
.sw-tb-others{display:flex;gap:4px;align-items:center;flex-wrap:nowrap;}
.sw-tb-oth{width:32px;height:32px;border-radius:6px;object-fit:cover;display:block;background:#f1f5f9;border:1px solid #e8ebf3;}
.sw-tb-more{font-size:11px;font-weight:800;color:#64748b;background:#f1f5f9;border-radius:6px;padding:0 6px;height:32px;display:flex;align-items:center;}
.sw-tb-dash{color:#cbd5e1;font-weight:700;}
.sw-tb-badge{display:inline-block;font-family:Montserrat,sans-serif;font-weight:800;font-size:10px;letter-spacing:0.03em;
  text-transform:uppercase;border-radius:99px;padding:4px 10px;white-space:nowrap;}
.sw-tb-type{font-size:11px;color:#64748b;background:#f1f5f9;border-radius:6px;padding:3px 8px;font-weight:700;white-space:nowrap;}
.sw-tb-cnt{display:inline-flex;align-items:center;justify-content:center;min-width:26px;height:24px;border-radius:7px;
  background:#eef2ff;color:#4256c7;font-weight:800;font-size:12px;padding:0 6px;}
.sw-tb-acts{display:flex;gap:5px;align-items:center;justify-content:center;}
.sw-tb-edit{font-family:Montserrat,sans-serif;font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.03em;
  background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;border:none;border-radius:8px;padding:7px 13px;cursor:pointer;
  white-space:nowrap;transition:filter .15s;}
.sw-tb-edit:hover{filter:brightness(1.08);}
.sw-tb-del{width:32px;height:30px;border:1px solid #fecaca;border-radius:8px;background:#fef2f2;color:#dc2626;cursor:pointer;
  display:inline-flex;align-items:center;justify-content:center;padding:0;transition:all .15s;}
.sw-tb-del:hover{background:#fee2e2;border-color:#fca5a5;}
.sw-tb-del svg{width:15px;height:15px;display:block;}
#empty{display:none;padding:26px;text-align:center;color:#94a3b8;font-size:0.85rem;}
</style></head>
<body>
<div id="wrap">
  <div id="bar2">
    <input id="search" type="text" placeholder="Buscar por nombre, tipo o estado..." autocomplete="off">
    <span id="cnt"></span>
    <button id="fsbtn" type="button" title="Pantalla completa"></button>
  </div>
  <div id="tbl-w">
    <table>
      <thead><tr>
        <th>Imagen</th><th>Otras imágenes</th><th>Producto</th><th class="c">Estado</th><th>Tipo</th>
        <th class="r">Precio antes</th><th class="r">Precio</th><th class="c">Variantes</th><th class="c">Fotos</th><th class="c">Acciones</th>
      </tr></thead>
      <tbody>ROWSPLACEHOLDER</tbody>
    </table>
    <div id="empty">Sin resultados para la búsqueda.</div>
  </div>
</div>
<script>
(function(){
var NRES=__NRES__;
var doc=document;
function applyFilters(){
  var term=(doc.getElementById('search').value||'').trim().toLowerCase();
  var rows=doc.querySelectorAll('tbody tr[data-blob]');var vis=0;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var show=(!term||(r.getAttribute('data-blob')||'').indexOf(term)>=0);
    r.style.display=show?'':'none'; if(show)vis++;
  }
  var el=doc.getElementById('cnt'); if(el)el.textContent=vis+' de '+NRES;
  doc.getElementById('empty').style.display=vis?'none':'block';
}
doc.getElementById('search').addEventListener('input',applyFilters);

/* Editar/Eliminar → escribe al input oculto sw_editcmd del padre (secuencia COMPLETA) */
function fireCmd(payload){
  try{
    var W=window.parent, D=W.document;
    var inp=D.querySelector('.st-key-sw_editcmd input'); if(!inp) return;
    var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
    inp.focus({preventScroll:true});
    setter.call(inp,payload+'|'+Date.now());
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new FocusEvent('blur',{bubbles:true}));
    inp.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));
    inp.blur();
  }catch(e){}
}
doc.addEventListener('click',function(e){
  var ed=e.target.closest?e.target.closest('.sw-tb-edit'):null;
  if(ed){ fireCmd('edit:'+(ed.getAttribute('data-swid')||'')); return; }
  var dl=e.target.closest?e.target.closest('.sw-tb-del'):null;
  if(dl){ fireCmd('del:'+(dl.getAttribute('data-swid')||'')); return; }
});

/* Fullscreen (mismo mecanismo/z-index que COTIZACIONES) */
(function(){
  var P=window.parent, IFR=null;
  try{ IFR=window.frameElement; }catch(e){}
  if(!IFR){ try{ var ifs=P.document.querySelectorAll('iframe'); for(var i=0;i<ifs.length;i++){ if(ifs[i].contentWindow===window){ IFR=ifs[i]; break; } } }catch(e){} }
  var EXP='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>';
  var SHR='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M3 21l7-7"/></svg>';
  var btn=doc.getElementById('fsbtn');
  var PROPS=[['position','fixed'],['top','0'],['left','0'],['width','100vw'],['height','100vh'],['z-index','999999'],['border','none'],['border-radius','0'],['margin','0'],['background','#fff']];
  function isFS(){ return P._swFsActive===true; }
  function apply(){ if(!IFR)return; for(var i=0;i<PROPS.length;i++) IFR.style.setProperty(PROPS[i][0],PROPS[i][1],'important'); doc.documentElement.classList.add('fs'); P._swFsActive=true; if(btn){btn.innerHTML=SHR;btn.title='Salir de pantalla completa';} }
  function remove(){ if(IFR){for(var i=0;i<PROPS.length;i++) IFR.style.removeProperty(PROPS[i][0]);} doc.documentElement.classList.remove('fs'); P._swFsActive=false; if(btn){btn.innerHTML=EXP;btn.title='Pantalla completa';} }
  function toggle(){ if(isFS())remove(); else apply(); }
  if(btn){ btn.onclick=toggle; btn.innerHTML=isFS()?SHR:EXP; }
  if(isFS()) apply();
  doc.addEventListener('keydown',function(e){ if(e.key==='Escape'&&isFS()) remove(); });
  try{ if(P._swFsEsc) P.document.removeEventListener('keydown',P._swFsEsc,true); P._swFsEsc=function(e){ if(e.key==='Escape'&&isFS()) remove(); }; P.document.addEventListener('keydown',P._swFsEsc,true); }catch(e){}
})();

applyFilters();
})();
</script>
</body></html>"""


def _build_sw_table(prods, bcol):
    """Arma la tabla HTML (estilo COTIZACIONES) con una fila por producto. Devuelve
    (html, alto_iframe)."""
    _rows = ""
    for p in prods:
        _imgs = p.get("images") or []
        _img0 = (_imgs[0].get("src") if _imgs else "") or (p.get("image") or {}).get("src", "")
        _main = (f'<img class="sw-tb-main" src="{_he(_img0)}" alt="" loading="lazy">' if _img0
                 else '<span class="sw-tb-noimg">Sin<br>foto</span>')
        _others = _imgs[1:]
        _oth = ""
        for im in _others[:6]:
            _s = im.get("src") or ""
            if _s:
                _oth += f'<img class="sw-tb-oth" src="{_he(_s)}" alt="" loading="lazy">'
        _extra = len(_others) - 6
        if _extra > 0:
            _oth += f'<span class="sw-tb-more">+{_extra}</span>'
        if not _oth:
            _oth = '<span class="sw-tb-dash">—</span>'
        _title = _he(p.get("title") or "(sin título)")
        _bg, _fg, _blbl = bcol.get(_estado_efectivo(p), bcol["active"])
        _type = _he(p.get("product_type") or (p.get("tags") or "").split(",")[0].strip() or "—")
        _vars = p.get("variants") or []
        _prices, _cmps = [], []
        for v in _vars:
            try:
                _prices.append(float(v.get("price") or 0))
            except Exception:
                pass
            try:
                _cv = float(v.get("compare_at_price") or 0)
                if _cv > 0:
                    _cmps.append(_cv)
            except Exception:
                pass
        if _prices:
            _pmin, _pmax = min(_prices), max(_prices)
            _price = _fmt_clp(_pmin) if _pmin == _pmax else f"{_fmt_clp(_pmin)} – {_fmt_clp(_pmax)}"
        else:
            _price = "—"
        _antes = (f"<s>{_fmt_clp(max(_cmps))}</s>" if _cmps else '<span class="sw-tb-dash">—</span>')
        _blob = _he((str(p.get("title") or "") + " " + str(p.get("product_type") or "")
                     + " " + str(p.get("tags") or "") + " " + _blbl).lower())
        _rows += (
            f'<tr data-blob="{_blob}">'
            f'<td>{_main}</td>'
            f'<td><div class="sw-tb-others">{_oth}</div></td>'
            f'<td class="name">{_title}</td>'
            f'<td class="c"><span class="sw-tb-badge" style="background:{_bg};color:{_fg};">{_blbl}</span></td>'
            f'<td><span class="sw-tb-type">{_type}</span></td>'
            f'<td class="r antes">{_antes}</td>'
            f'<td class="r price">{_price}</td>'
            f'<td class="c"><span class="sw-tb-cnt">{len(_vars)}</span></td>'
            f'<td class="c"><span class="sw-tb-cnt">{len(_imgs)}</span></td>'
            f'<td class="c"><div class="sw-tb-acts">'
            f'<button type="button" class="sw-tb-edit" data-swid="{_he(p.get("id"))}">Editar</button>'
            f'<button type="button" class="sw-tb-del" data-swid="{_he(p.get("id"))}" title="Eliminar de la web">'
            '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>'
            '</button></div></td>'
            f'</tr>')
    _n = len(prods)
    _tbl_h = max(320, min(_n * 74 + 56, 620))
    _iframe_h = 66 + _tbl_h
    _html = (_SW_TABLE_TEMPLATE.replace("IFRAMEHPX", str(_iframe_h) + "px")
             .replace("__NRES__", str(_n)).replace("ROWSPLACEHOLDER", _rows))
    return _html, _iframe_h


def _clp_plain(v) -> str:
    """Número con separador de miles (18490000 → '18.490.000'), sin símbolo, para los
    inputs de precio con formato moneda."""
    try:
        n = int(round(float(v or 0)))
    except Exception:
        n = 0
    return "" if n == 0 else "{:,.0f}".format(n).replace(",", ".")


# ── Editor de producto: formulario HTML limpio (iframe) con guardado único ─────
_SW_FORM_TEMPLATE = r"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Montserrat:wght@700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body{font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;background:transparent;color:#0f172a;}
#ed-root{padding-bottom:78px;}   /* aire para que el botón flotante Guardar y publicar no tape la última tarjeta */
.ed-head{display:flex;align-items:center;gap:14px;justify-content:space-between;margin:0 0 14px;flex-wrap:wrap;}
.ed-title-mini{font-family:'Plus Jakarta Sans';font-weight:800;font-size:1.05rem;color:#0f172a;min-width:0;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;}
.ed-save{display:inline-flex;align-items:center;gap:8px;background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;
  border:none;border-radius:11px;padding:11px 20px;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.78rem;
  text-transform:uppercase;letter-spacing:.04em;cursor:pointer;box-shadow:0 6px 18px rgba(37,99,235,.32);white-space:nowrap;
  transition:filter .15s,transform .1s;}
.ed-save:hover{filter:brightness(1.07);transform:translateY(-1px);}
.ed-save:disabled{opacity:.6;cursor:default;transform:none;filter:none;}
.ed-save svg{width:16px;height:16px;}
.ed-grid{display:grid;grid-template-columns:1.55fr 1fr;gap:16px;align-items:start;}
@media(max-width:820px){.ed-grid{grid-template-columns:1fr;}}
.ed-card{background:#fff;border:1px solid #e8ebf3;border-radius:14px;padding:16px 17px;box-shadow:0 2px 10px rgba(15,23,42,.05);margin-bottom:16px;}
.ed-card:last-child{margin-bottom:0;}
.ed-lbl{font-family:Montserrat,sans-serif;font-weight:800;font-size:0.72rem;text-transform:uppercase;letter-spacing:.05em;
  color:#0f172a;margin-bottom:11px;display:flex;align-items:center;gap:7px;}
.ed-lbl small{font-family:'Plus Jakarta Sans';font-weight:600;font-size:0.68rem;text-transform:none;letter-spacing:0;color:#94a3b8;}
label.ed-flbl{display:block;font-size:0.72rem;font-weight:700;color:#475569;margin:12px 0 5px;text-transform:uppercase;letter-spacing:.03em;}
label.ed-flbl:first-child{margin-top:0;}
input.ed-in,select.ed-in,textarea.ed-in{width:100%;border:1.5px solid #e2e8f0;border-radius:10px;padding:10px 12px;
  font-size:0.9rem;font-family:inherit;color:#0f172a;background:#f8fafc;outline:none;transition:border-color .15s,box-shadow .15s;}
input.ed-in:focus,select.ed-in:focus,textarea.ed-in:focus{border-color:#5b7cfa;background:#fff;box-shadow:0 0 0 3px rgba(91,124,250,.12);}
textarea.ed-in{min-height:150px;resize:vertical;line-height:1.5;}
select.ed-in{cursor:pointer;appearance:none;background-image:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%2364748b' stroke-width='2.2' stroke-linecap='round'><path d='M4 6l4 4 4-4'/></svg>");background-repeat:no-repeat;background-position:right 12px center;padding-right:34px;}
.ed-money-wrap{position:relative;}
.ed-money-wrap::before{content:'$';position:absolute;left:12px;top:50%;transform:translateY(-50%);color:#94a3b8;font-weight:800;font-size:0.9rem;}
input.ed-money{padding-left:24px;font-variant-numeric:tabular-nums;font-weight:700;}
.ed-two{display:grid;grid-template-columns:1fr 1fr;gap:12px;}
.ed-vrow{margin-bottom:12px;}
.ed-vrow:last-child{margin-bottom:0;}
.ed-vtitle{font-weight:700;color:#475569;font-size:0.8rem;margin-bottom:6px;}
/* Imágenes */
.ed-imgs{display:grid;grid-template-columns:repeat(auto-fill,minmax(104px,1fr));gap:10px;}
.ed-img{position:relative;aspect-ratio:1/1;border-radius:11px;overflow:hidden;background:#f1f5f9;border:1px solid #e8ebf3;
  cursor:pointer;user-select:none;}                 /* centro → clic para ampliar (dedito) */
.ed-img.dragging{opacity:.4;cursor:grabbing;}
.ed-img img{width:100%;height:100%;object-fit:cover;display:block;pointer-events:none;}
/* X de eliminar: arriba a la IZQUIERDA (fotos y videos). */
.ed-img .ed-del{position:absolute;top:5px;left:5px;width:26px;height:26px;border-radius:50%;border:none;
  background:rgba(15,23,42,.62);color:#fff;cursor:pointer;display:none;align-items:center;justify-content:center;padding:0;z-index:3;}
.ed-img:hover .ed-del{display:flex;}
.ed-img .ed-del svg{width:14px;height:14px;}
.ed-img .ed-del:hover{background:#dc2626;}
/* Manija de arrastre (grip): arriba a la DERECHA (fotos y videos); cursor de "manito". */
.ed-img .ed-drag{position:absolute;top:5px;right:5px;width:26px;height:26px;border-radius:7px;
  background:rgba(15,23,42,.62);color:#fff;cursor:grab;display:none;align-items:center;justify-content:center;padding:0;z-index:3;}
.ed-img:hover .ed-drag{display:flex;}
.ed-img .ed-drag:active{cursor:grabbing;background:#5b7cfa;}
.ed-img .ed-drag svg{width:15px;height:15px;pointer-events:none;}
.ed-img .ed-princ{position:absolute;bottom:5px;left:5px;font-family:Montserrat,sans-serif;font-weight:800;font-size:8.5px;
  text-transform:uppercase;letter-spacing:.04em;background:#5b7cfa;color:#fff;border-radius:5px;padding:2px 6px;display:none;}
.ed-img.is-princ .ed-princ{display:block;}
.ed-img.ed-deleted{opacity:.32;filter:grayscale(1);}
.ed-img.ed-deleted .ed-del{display:flex;background:#dc2626;}
.ed-img.ed-new::after{content:'NUEVA';position:absolute;bottom:5px;right:5px;font-family:Montserrat;font-weight:800;font-size:8px;
  background:#16a34a;color:#fff;border-radius:5px;padding:2px 5px;letter-spacing:.03em;}
/* Videos en la galería: mismo tile, con badge de reproducción; clic para ampliar,
   pero NO se arrastran (sin manija). */
.ed-img.ed-video{cursor:pointer;}
.ed-img.ed-video .ed-vph{width:100%;height:100%;display:flex;align-items:center;justify-content:center;
  background:#0f172a;color:#cbd5e1;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.72rem;letter-spacing:.06em;}
.ed-img.ed-video .ed-vplay{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:36px;height:36px;
  border-radius:50%;background:rgba(15,23,42,.6);display:flex;align-items:center;justify-content:center;pointer-events:none;}
.ed-img.ed-video .ed-vplay svg{width:16px;height:16px;}
.ed-img.ed-video .ed-vbadge{position:absolute;bottom:5px;left:5px;font-family:Montserrat,sans-serif;font-weight:800;font-size:8.5px;
  text-transform:uppercase;letter-spacing:.04em;background:rgba(15,23,42,.72);color:#fff;border-radius:5px;padding:2px 6px;}
.ed-drag-hint{font-size:0.7rem;color:#94a3b8;margin-top:9px;}
.ed-addimg{display:flex;gap:8px;margin-top:11px;}
.ed-addimg input{flex:1;border:1.5px solid #e2e8f0;border-radius:9px;padding:8px 11px;font-size:0.82rem;font-family:inherit;background:#f8fafc;outline:none;}
.ed-addimg input:focus{border-color:#5b7cfa;background:#fff;}
.ed-addimg button{border:1px solid #dbe3ff;background:#eef2ff;color:#2563eb;border-radius:9px;padding:0 14px;font-weight:800;font-size:0.75rem;cursor:pointer;font-family:Montserrat;text-transform:uppercase;letter-spacing:.03em;transition:opacity .15s;}
.ed-addimg button:disabled{opacity:.42;cursor:default;filter:grayscale(.4);}
.ed-addimg button:not(:disabled):hover{background:#dbe3ff;}
.ed-noimg{color:#94a3b8;font-size:0.82rem;padding:8px 0;}
/* Agregar desde el PC (todo HTML) */
.ed-pcbtn{margin-top:9px;width:100%;display:flex;align-items:center;justify-content:center;gap:8px;background:#0f172a;
  color:#fff;border:none;border-radius:10px;padding:11px;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.74rem;
  text-transform:uppercase;letter-spacing:.03em;cursor:pointer;transition:filter .15s;}
.ed-pcbtn:hover{filter:brightness(1.18);}
.ed-pcbtn svg{width:16px;height:16px;}
.ed-pcwrap{display:none;margin-top:11px;border-top:1px dashed #e2e8f0;padding-top:12px;}
.ed-pcwrap.on{display:block;}
.ed-pchead{display:flex;align-items:center;justify-content:space-between;margin-bottom:9px;}
.ed-pchead span{font-weight:800;font-size:0.76rem;color:#0f172a;font-family:Montserrat,sans-serif;}
.ed-pcclear{background:none;border:none;color:#dc2626;font-weight:800;font-size:0.7rem;cursor:pointer;text-transform:uppercase;letter-spacing:.03em;font-family:Montserrat,sans-serif;}
.ed-pcclear:hover{text-decoration:underline;}
.ed-pcthumbs{display:flex;flex-wrap:wrap;gap:8px;max-height:186px;overflow-y:auto;padding:2px;}
.ed-pcthumb{position:relative;width:80px;height:80px;border-radius:9px;overflow:hidden;border:1px solid #e8ebf3;background:#f1f5f9;flex:0 0 auto;}
.ed-pcthumb img,.ed-pcthumb video{width:100%;height:100%;object-fit:cover;display:block;background:#0f172a;}
.ed-pcadd{width:80px;height:80px;border-radius:9px;border:2px dashed #cbd5e1;background:#f8fafc;color:#94a3b8;
  display:flex;align-items:center;justify-content:center;font-size:30px;font-weight:300;line-height:1;cursor:pointer;
  flex:0 0 auto;transition:all .15s;}
.ed-pcadd:hover{border-color:#5b7cfa;color:#5b7cfa;background:#fff;}
.ed-pcplay{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;pointer-events:none;}
.ed-pcplay span{width:26px;height:26px;border-radius:50%;background:rgba(15,23,42,.6);display:flex;align-items:center;justify-content:center;}
.ed-pcvtag{position:absolute;bottom:3px;left:3px;font-family:Montserrat,sans-serif;font-weight:800;font-size:7.5px;
  background:#0f172a;color:#fff;border-radius:4px;padding:1px 4px;letter-spacing:.03em;}
.ed-pcmsg{display:none;background:#fff1f2;border:1px solid #fca5a5;color:#b91c1c;border-radius:9px;padding:8px 11px;
  font-size:0.76rem;line-height:1.4;margin-top:10px;}
.ed-pchint{font-size:0.72rem;color:#94a3b8;font-weight:600;margin-top:9px;}
/* Características / detalles (metacampos) */
.ed-mf-hint{font-size:0.75rem;color:#94a3b8;line-height:1.45;margin:2px 0 12px;}
.ed-mf-list{display:flex;flex-direction:column;}
.ed-mf-row{display:grid;grid-template-columns:1.25fr 2fr;gap:14px;align-items:start;padding:11px 0;border-bottom:1px solid #f1f5f9;}
.ed-mf-row:last-child{border-bottom:none;}
@media(max-width:700px){.ed-mf-row{grid-template-columns:1fr;gap:5px;}}
.ed-mf-name{font-weight:700;color:#0f172a;font-size:0.85rem;line-height:1.25;padding-top:9px;}
.ed-mf-name small{display:block;font-weight:600;font-size:0.63rem;color:#94a3b8;margin-top:2px;}
.ed-mf-ctl{display:flex;gap:8px;align-items:flex-start;}
.ed-mf-ctl .ed-in{flex:1;min-width:0;}
.ed-mf-ctl textarea.ed-in{min-height:92px;}
.ed-mf-del{flex:0 0 auto;width:40px;height:40px;border:1px solid #fecaca;border-radius:9px;background:#fef2f2;color:#dc2626;
  cursor:pointer;display:flex;align-items:center;justify-content:center;padding:0;transition:all .15s;}
.ed-mf-del:hover{background:#fee2e2;border-color:#fca5a5;}
.ed-mf-del svg{width:16px;height:16px;}
.ed-mf-row.ed-mf-deleted{opacity:.5;}
.ed-mf-row.ed-mf-deleted .ed-in{background:#f1f5f9;pointer-events:none;}
.ed-mf-bool{display:flex;align-items:center;gap:9px;padding-top:9px;font-weight:600;color:#334155;font-size:0.9rem;cursor:pointer;}
.ed-mf-bool input{width:18px;height:18px;accent-color:#2563eb;cursor:pointer;}
/* Especificaciones (sidebar) */
.ed-especs-hint{font-size:0.72rem;color:#94a3b8;margin:0 0 8px;}
.ed-especs-input{min-height:140px;line-height:1.5;}
/* Imágenes de planta y render (metacampos de imagen) */
.ed-imgmeta-card{grid-column:1 / -1;}
.ed-ims-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;}
@media(max-width:820px){.ed-ims-grid{grid-template-columns:1fr;}}
.ed-ims-lbl{font-size:0.72rem;font-weight:700;color:#475569;margin-bottom:7px;text-transform:uppercase;letter-spacing:.03em;}
.ed-ims-box{position:relative;width:100%;height:210px;border:1.5px solid #e2e8f0;border-radius:12px;background:#f1f5f9;
  display:flex;align-items:center;justify-content:center;overflow:hidden;}
.ed-ims-box img{max-width:100%;max-height:100%;width:auto;height:auto;object-fit:contain;display:block;}
.ed-ims-empty{color:#94a3b8;font-size:0.82rem;font-weight:600;}
.ed-ims-badge{position:absolute;top:8px;left:8px;background:#4f46e5;color:#fff;font-family:Montserrat,sans-serif;
  font-weight:800;font-size:8px;letter-spacing:.05em;text-transform:uppercase;padding:3px 7px;border-radius:6px;z-index:2;}
/* Botones sobre la imagen (arriba-derecha): ampliar + quitar */
.ed-ims-ov{position:absolute;top:8px;right:8px;display:flex;gap:6px;z-index:3;}
.ed-ims-ov button{width:31px;height:31px;border-radius:9px;border:none;cursor:pointer;display:flex;align-items:center;
  justify-content:center;background:rgba(15,23,42,.60);color:#fff;transition:background .15s;padding:0;}
.ed-ims-ov button svg{width:16px;height:16px;}
.ed-ims-zoom:hover{background:rgba(15,23,42,.85);}
.ed-ims-clear:hover{background:#dc2626;}
.ed-ims-hint{font-size:0.72rem;color:#94a3b8;margin:7px 0 8px;}
.ed-ims-acts{display:flex;gap:8px;}
.ed-ims-pick{border-radius:9px;padding:10px 12px;font-family:'Plus Jakarta Sans',sans-serif;font-weight:700;
  font-size:0.8rem;cursor:pointer;border:1.5px solid #0f172a;background:#0f172a;color:#fff;transition:all .15s;
  flex:1;display:flex;align-items:center;justify-content:center;gap:6px;}
.ed-ims-pick:hover{background:#1e293b;}
.ed-ims-pick svg{width:15px;height:15px;}
.ed-pcx{position:absolute;top:3px;right:3px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(15,23,42,.66);
  color:#fff;cursor:pointer;font-size:13px;line-height:1;display:flex;align-items:center;justify-content:center;padding:0;}
.ed-pcx:hover{background:#dc2626;}
.ed-pcprog{display:none;height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin:12px 0 2px;}
.ed-pcprog.on{display:block;}
.ed-pcbar{height:100%;width:0;background:linear-gradient(90deg,#5b7cfa,#2563eb);transition:width .12s;}
.ed-pcup{margin-top:11px;width:100%;background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;border:none;border-radius:10px;
  padding:11px;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.76rem;text-transform:uppercase;letter-spacing:.03em;
  cursor:pointer;transition:filter .15s;box-shadow:0 5px 14px rgba(22,163,74,.26);}
.ed-pcup:hover{filter:brightness(1.08);}
.ed-pcup:disabled{opacity:.6;cursor:default;box-shadow:none;}
.ed-addvid{display:flex;gap:8px;margin-top:8px;}
.ed-addvid input{flex:1;border:1.5px solid #e2e8f0;border-radius:9px;padding:8px 11px;font-size:0.82rem;font-family:inherit;background:#f8fafc;outline:none;}
.ed-addvid input:focus{border-color:#5b7cfa;background:#fff;}
.ed-addvid button{border:1px solid #dbe3ff;background:#eef2ff;color:#2563eb;border-radius:9px;padding:0 14px;font-weight:800;font-size:0.75rem;cursor:pointer;font-family:Montserrat,sans-serif;text-transform:uppercase;letter-spacing:.03em;white-space:nowrap;transition:opacity .15s;}
.ed-addvid button:disabled{opacity:.42;cursor:default;filter:grayscale(.4);}
.ed-addvid button:not(:disabled):hover{background:#dbe3ff;}
/* toggles + checks */
.ed-toggle{display:flex;align-items:center;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;}
.ed-toggle:last-child{border-bottom:none;}
.ed-toggle span{font-weight:700;font-size:0.86rem;color:#0f172a;}
.ed-sw{position:relative;width:42px;height:23px;flex:0 0 auto;}
.ed-sw input{opacity:0;width:0;height:0;position:absolute;}
.ed-sw i{position:absolute;inset:0;background:#cbd5e1;border-radius:99px;transition:.18s;cursor:pointer;}
.ed-sw i::after{content:'';position:absolute;top:2px;left:2px;width:19px;height:19px;border-radius:50%;background:#fff;transition:.18s;box-shadow:0 1px 3px rgba(0,0,0,.2);}
.ed-sw input:checked + i{background:#2563eb;}
.ed-sw input:checked + i::after{left:21px;}
.ed-check{display:flex;align-items:center;gap:9px;padding:7px 0;cursor:pointer;font-size:0.86rem;font-weight:600;color:#334155;}
.ed-check input{width:17px;height:17px;accent-color:#2563eb;cursor:pointer;flex:0 0 auto;}
.ed-info{font-size:0.74rem;color:#64748b;background:#f8fafc;border:1px solid #e8ebf3;border-radius:9px;padding:9px 11px;line-height:1.4;}
</style></head>
<body>
<div id="ed-root">
<div class="ed-head">
  <div class="ed-title-mini" id="ttl">__TITLE__</div>
</div>
<div class="ed-grid">
  <div class="ed-main">
    <div class="ed-card">
      <div class="ed-lbl">Fotos y videos <small>· clic para ampliar · arrastra desde la manija para ordenar · la 1ª foto es la principal</small></div>
      <div class="ed-imgs" id="imgs">__IMAGES__</div>
      <div class="ed-addimg">
        <input id="addurl" type="text" placeholder="Pega la URL de una foto y presiona Enter o Agregar">
        <button type="button" id="addbtn" disabled>Agregar</button>
      </div>
      <div class="ed-addvid">
        <input id="addvidurl" type="text" placeholder="Enlace de video de YouTube o Vimeo y presiona Enter o Agregar">
        <button type="button" id="addvidbtn" disabled>Agregar video</button>
      </div>
      <button type="button" id="pcbtn" class="ed-pcbtn">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
        Agregar fotos/videos desde PC
      </button>
      <input type="file" id="pcfile" accept="image/*,video/*" multiple style="display:none">
      <div id="pcwrap" class="ed-pcwrap">
        <div class="ed-pchead"><span id="pccount">0 archivos</span>
          <button type="button" id="pcclear" class="ed-pcclear">Quitar todos</button></div>
        <div id="pcthumbs" class="ed-pcthumbs"></div>
        <div id="pcmsg" class="ed-pcmsg"></div>
        <div class="ed-pchint">Se suben al pulsar «Guardar y publicar».</div>
      </div>
    </div>
    <div class="ed-card">
      <label class="ed-flbl">Título</label>
      <input class="ed-in" id="f_title" type="text" value="__TITLE_ATTR__" placeholder="Nombre del modelo">
      <label class="ed-flbl">Descripción · acepta HTML básico</label>
      <textarea class="ed-in" id="f_desc">__DESC__</textarea>
    </div>
    <div class="ed-card">
      <div class="ed-lbl">Precios</div>
      __PRICES__
    </div>
  </div>
  <div class="ed-side">
    <div class="ed-card">
      <label class="ed-flbl">Estado</label>
      <select class="ed-in" id="f_status">__STATUS__</select>
    </div>
    <div class="ed-card">
      <div class="ed-lbl">Canales de venta</div>
      __CHANNELS__
    </div>
    <div class="ed-card">
      <label class="ed-flbl">Tipo de producto</label>
      <input class="ed-in" id="f_type" type="text" value="__TYPE__" placeholder="Ej: Casa Container">
      <label class="ed-flbl">Proveedor</label>
      <input class="ed-in" id="f_vendor" type="text" value="__VENDOR__" placeholder="Ej: Container Houses">
      <div class="ed-lbl" style="margin-top:15px;">Colecciones</div>
      __COLLECTIONS__
    </div>
  </div>
  <div class="ed-card ed-mf-card" style="margin-top:16px;">
    <div class="ed-lbl">Características / detalles</div>
    <div class="ed-mf-hint">Los detalles del producto (m², dormitorios, baños, clima, características, etc.). Complétalos; un campo que dejes vacío no se publica. La papelera vacía/elimina ese campo. Se guardan con «Guardar y publicar».</div>
    <div class="ed-mf-list">__METAFIELDS__</div>
  </div>
  __ESPECS__
  <div class="ed-card ed-imgmeta-card" style="margin-top:16px;">
    <div class="ed-lbl">Imágenes de planta y render</div>
    <div class="ed-mf-hint">Imágenes adicionales del producto (planta y render). Se suben al pulsar «Guardar y publicar».</div>
    <div class="ed-ims-grid">__IMGMETAS__</div>
  </div>
</div>
<script>
(function(){
var doc=document, grid=doc.getElementById('imgs');

/* ── Formato moneda en los inputs de precio ── */
function fmtMoney(v){ v=(''+v).replace(/\D/g,''); if(!v) return ''; return parseInt(v,10).toLocaleString('es-CL'); }
[].slice.call(doc.querySelectorAll('.ed-money')).forEach(function(inp){
  inp.value=fmtMoney(inp.value);
  inp.addEventListener('input',function(){ var p=this.selectionStart; this.value=fmtMoney(this.value); });
});

/* ── Imágenes: principal + arrastrar + eliminar (marcar) ── */
function refreshPrincipal(){
  var first=null;
  [].slice.call(grid.querySelectorAll('.ed-img')).forEach(function(t){
    t.classList.remove('is-princ');
    if(!first && !t.classList.contains('ed-deleted') && t.getAttribute('data-video')!=='1') first=t;
  });
  if(first) first.classList.add('is-princ');
}
grid.addEventListener('click',function(e){
  var d=e.target.closest?e.target.closest('.ed-del'):null;
  if(d){                                                    // botón X → eliminar / descartar
    var tile=d.closest('.ed-img'); if(!tile) return;
    if(tile.getAttribute('data-new')==='1'){ tile.remove(); }   // nueva → se descarta
    else { tile.classList.toggle('ed-deleted'); }
    refreshPrincipal(); setDirty(); return;
  }
  if(e.target.closest && e.target.closest('.ed-drag')) return;   // manija → no abrir visor
  var t=e.target.closest?e.target.closest('.ed-img'):null;  // click en el medio → previsualizar
  if(t && !t.classList.contains('ed-deleted')) openFs(t);
});
/* Arrastrar SOLO desde la manija (grip): se habilita draggable al presionarla y se
   restaura al soltar. Así el centro queda como "clic para ampliar" (dedito). */
grid.addEventListener('mousedown',function(e){
  var h=e.target.closest?e.target.closest('.ed-drag'):null; if(!h) return;
  var tile=h.closest('.ed-img'); if(tile) tile.setAttribute('draggable','true');
});
function _swResetDrag(){ [].slice.call(grid.querySelectorAll('.ed-img[draggable="true"]')).forEach(function(t){ t.setAttribute('draggable','false'); }); }
doc.addEventListener('mouseup', _swResetDrag);
var dragEl=null;
grid.addEventListener('dragstart',function(e){
  var t=e.target.closest('.ed-img'); if(!t) return; dragEl=t;
  e.dataTransfer.effectAllowed='move'; setTimeout(function(){t.classList.add('dragging');},0);
});
grid.addEventListener('dragend',function(){ if(dragEl)dragEl.classList.remove('dragging'); dragEl=null; _swResetDrag(); refreshPrincipal(); setDirty(); });
grid.addEventListener('dragover',function(e){
  e.preventDefault(); if(!dragEl) return;
  var t=e.target.closest('.ed-img'); if(!t||t===dragEl) return;
  var r=t.getBoundingClientRect(); var before=(e.clientY < r.top + r.height/2) || (Math.abs(e.clientY-(r.top+r.height/2))<r.height/2 && e.clientX < r.left + r.width/2);
  grid.insertBefore(dragEl, before ? t : t.nextSibling);
});

/* ── Previsualización FULLSCREEN (fotos + videos): slide loop + navegación + eliminar.
   Se monta en el documento PADRE para cubrir toda la ventana (el iframe es de poca altura). */
function _swPD(){ try{ return window.parent.document; }catch(e){ return doc; } }
try{ var _stale=_swPD().getElementById('sw-fs'); if(_stale){ _stale.remove(); _swPD().body.style.overflow=''; } }catch(e){}
function _swMedia(){
  var out=[];
  [].slice.call(grid.querySelectorAll('.ed-img')).forEach(function(t){
    if(t.classList.contains('ed-deleted')) return;
    if(t.getAttribute('data-video')==='1'){
      out.push({tile:t, kind:'video', src:t.getAttribute('data-vsrc')||'', pv:t.getAttribute('data-vpv')||'', origin:t.getAttribute('data-vorigin')||''});
    }else{
      var im=t.querySelector('img'); out.push({tile:t, kind:'image', src:(im?im.getAttribute('src'):'')});
    }
  });
  return out;
}
function openFs(startTile){
  var PD=_swPD(); var items=_swMedia(); if(!items.length) return;
  var idx=0, i; for(i=0;i<items.length;i++){ if(items[i].tile===startTile){ idx=i; break; } }
  var old=PD.getElementById('sw-fs'); if(old) old.remove();
  if(!PD.getElementById('sw-fs-css')){
    var s=PD.createElement('style'); s.id='sw-fs-css';
    s.textContent='@keyframes swFsBd{from{opacity:0}to{opacity:1}}@keyframes swFsInR{from{opacity:0;transform:translateX(30px)}to{opacity:1;transform:translateX(0)}}@keyframes swFsInL{from{opacity:0;transform:translateX(-30px)}to{opacity:1;transform:translateX(0)}}#sw-fs ._st::-webkit-scrollbar{height:7px}#sw-fs ._st::-webkit-scrollbar-thumb{background:rgba(255,255,255,.25);border-radius:9px}';
    (PD.head||PD.body).appendChild(s);
  }
  var prevOv=PD.body.style.overflow; PD.body.style.overflow='hidden';
  var chevL='<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>';
  var chevR='<svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18l6-6-6-6"/></svg>';
  var xIco='<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>';
  var trIco='<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
  var playB='<svg viewBox="0 0 24 24" width="26" height="26" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
  var arrowCss='background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:#fff;cursor:pointer;border-radius:50%;width:46px;height:46px;display:flex;align-items:center;justify-content:center;flex-shrink:0;';
  var closeCss='background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:#fff;cursor:pointer;border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;';
  function esc(u){ return (u||'').replace(/"/g,'&quot;'); }
  function bigHtml(it){
    if(it.kind==='video'){
      if(it.src){ return '<video src="'+esc(it.src)+'"'+(it.pv?' poster="'+esc(it.pv)+'"':'')+' controls playsinline style="max-width:88vw;max-height:70vh;border-radius:12px;background:#000;"></video>'; }
      return '<div style="position:relative;display:inline-block;">'
        + (it.pv? '<img src="'+esc(it.pv)+'" style="max-width:88vw;max-height:70vh;border-radius:12px;">'
                : '<div style="width:min(70vw,520px);height:min(48vh,320px);background:#0f172a;border-radius:12px;display:flex;align-items:center;justify-content:center;color:#cbd5e1;font-weight:800;letter-spacing:.06em;">VIDEO</div>')
        + (it.origin? '<a href="'+esc(it.origin)+'" target="_blank" style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-decoration:none;"><span style="width:66px;height:66px;border-radius:50%;background:rgba(15,23,42,.62);display:flex;align-items:center;justify-content:center;">'+playB+'</span></a>':'')
        + '</div>';
    }
    return '<img src="'+esc(it.src)+'" style="max-width:88vw;max-height:70vh;object-fit:contain;border-radius:12px;">';
  }
  function thumbHtml(it,i){
    var inner = it.kind==='video'
      ? (it.pv? '<img src="'+esc(it.pv)+'" style="width:100%;height:100%;object-fit:cover;">' : '<div style="width:100%;height:100%;background:#0f172a;"></div>')
      : '<img src="'+esc(it.src)+'" style="width:100%;height:100%;object-fit:cover;">';
    var badge = it.kind==='video' ? '<span style="position:absolute;bottom:2px;right:3px;width:14px;height:14px;border-radius:50%;background:rgba(15,23,42,.72);display:flex;align-items:center;justify-content:center;"><svg viewBox="0 0 24 24" width="8" height="8" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg></span>' : '';
    return '<div class="_th" data-i="'+i+'" style="position:relative;width:62px;height:62px;border-radius:9px;overflow:hidden;flex-shrink:0;cursor:pointer;border:2px solid transparent;">'+inner+badge+'</div>';
  }
  var multi=items.length>1;
  var ov=PD.createElement('div'); ov.id='sw-fs';
  ov.style.cssText='position:fixed;inset:0;background:rgba(6,11,22,.94);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:16px;box-sizing:border-box;font-family:-apple-system,Segoe UI,Roboto,sans-serif;animation:swFsBd .22s ease both;';
  ov.innerHTML=
    '<button class="_cl" style="position:absolute;top:16px;right:18px;'+closeCss+'">'+xIco+'</button>'
    +'<div class="_ct" style="position:absolute;top:22px;left:22px;color:#cbd5e1;font-size:.82rem;font-weight:700;letter-spacing:.03em;"></div>'
    +'<div style="display:flex;align-items:center;gap:16px;max-width:96vw;">'
    + (multi? '<button class="_pv" style="'+arrowCss+'">'+chevL+'</button>':'')
    +'<div class="_stg" style="display:flex;align-items:center;justify-content:center;min-width:min(60vw,420px);min-height:150px;overflow:hidden;">'+bigHtml(items[idx])+'</div>'
    + (multi? '<button class="_nx" style="'+arrowCss+'">'+chevR+'</button>':'')
    +'</div>'
    +'<button class="_del" style="margin-top:18px;background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;border:none;border-radius:11px;padding:12px 30px;font-size:13.5px;font-weight:800;cursor:pointer;display:inline-flex;align-items:center;gap:9px;box-shadow:0 8px 22px rgba(220,38,38,.4);">'+trIco+'Eliminar</button>'
    + (multi? '<div class="_st" style="display:flex;gap:9px;margin-top:16px;max-width:92vw;overflow-x:auto;padding:6px 2px 8px;">'+items.map(thumbHtml).join('')+'</div>':'');
  PD.body.appendChild(ov);
  var stg=ov.querySelector('._stg'), ct=ov.querySelector('._ct'), strip=ov.querySelector('._st');
  var pvb=ov.querySelector('._pv'), nxb=ov.querySelector('._nx');
  function paint(){
    ct.textContent=(idx+1)+' / '+items.length;
    if(strip){ var ts=strip.querySelectorAll('._th'); for(var i=0;i<ts.length;i++){ var on=(i===idx); ts[i].style.borderColor=on?'#5b7cfa':'transparent'; ts[i].style.transform=on?'scale(1.06)':'scale(1)'; }
      var cur=strip.querySelector('._th[data-i="'+idx+'"]'); if(cur&&cur.scrollIntoView){ try{cur.scrollIntoView({inline:'center',block:'nearest'});}catch(e){} } }
  }
  function render(dir){ stg.innerHTML=bigHtml(items[idx]); var inn=stg.firstElementChild; if(inn&&dir) inn.style.animation=(dir<0?'swFsInL':'swFsInR')+' .28s ease both'; paint(); }
  function go(d){ var n=items.length; if(n<2) return; idx=(idx+d+n)%n; render(d); }
  function onKey(e){ if(e.key==='Escape') close(); else if(e.key==='ArrowRight') go(1); else if(e.key==='ArrowLeft') go(-1); }
  function close(){ if(ov.parentNode) ov.parentNode.removeChild(ov); PD.body.style.overflow=prevOv||''; PD.removeEventListener('keydown',onKey); }
  function delCur(){
    var t=items[idx].tile;
    if(t.getAttribute('data-new')==='1'){ t.remove(); } else { t.classList.add('ed-deleted'); }
    refreshPrincipal(); setDirty();
    items.splice(idx,1);
    if(!items.length){ close(); return; }
    if(idx>=items.length) idx=items.length-1;
    if(strip) strip.innerHTML=items.map(thumbHtml).join('');
    if(pvb) pvb.style.display=(items.length>1)?'':'none';
    if(nxb) nxb.style.display=(items.length>1)?'':'none';
    render(0);
  }
  ov.querySelector('._cl').addEventListener('click', close);
  ov.querySelector('._del').addEventListener('click', delCur);
  if(pvb) pvb.addEventListener('click', function(){go(-1);});
  if(nxb) nxb.addEventListener('click', function(){go(1);});
  if(strip){ strip.addEventListener('click', function(e){ var th=e.target.closest?e.target.closest('._th'):null; if(!th) return; idx=parseInt(th.getAttribute('data-i'),10)||0; render(0); }); }
  ov.addEventListener('click', function(e){ if(e.target===ov) close(); });
  PD.addEventListener('keydown', onKey);
  paint();
}

/* ── Agregar foto por URL ── */
function addUrl(){
  var inp=doc.getElementById('addurl'); var u=(inp.value||'').trim(); if(!u) return;
  var d=doc.createElement('div'); d.className='ed-img ed-new'; d.setAttribute('draggable','false');
  d.setAttribute('data-new','1'); d.setAttribute('data-src',u);
  var grip='<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/><circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>';
  d.innerHTML='<img src="'+u.replace(/"/g,'&quot;')+'" alt=""><span class="ed-drag" title="Arrastra para reordenar">'+grip+'</span><button type="button" class="ed-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg></button><span class="ed-princ">Principal</span>';
  grid.appendChild(d); inp.value=''; syncAdd(); refreshPrincipal(); setDirty();
}
var _addbtn=doc.getElementById('addbtn'), _addurl=doc.getElementById('addurl');
function syncAdd(){ _addbtn.disabled=!(_addurl.value||'').trim(); }
_addurl.addEventListener('input',syncAdd);
_addbtn.addEventListener('click',function(){ if(!this.disabled) addUrl(); });
_addurl.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); addUrl(); }});
syncAdd(); refreshPrincipal();

/* ── Características / detalles (metacampos) ── */
function collectMetafields(){
  var out=[];
  [].slice.call(doc.querySelectorAll('.ed-mf-row')).forEach(function(row){
    var kind=row.getAttribute('data-kind'), el=row.querySelector('.ed-mf-input');
    var val=(kind==='bool')?(el.checked?'true':'false'):(el.value||'');
    out.push({ns:row.getAttribute('data-ns'), key:row.getAttribute('data-key'),
      type:row.getAttribute('data-type'), id:row.getAttribute('data-id')||'', kind:kind,
      value:val, orig:row.getAttribute('data-orig')||'', deleted:row.classList.contains('ed-mf-deleted')});
  });
  return out;
}
doc.addEventListener('click',function(e){
  var d=e.target.closest?e.target.closest('.ed-mf-del'):null; if(!d) return;
  var row=d.closest('.ed-mf-row'); if(row){ row.classList.toggle('ed-mf-deleted'); setDirty(); }
});

/* ── Guardar todo (un solo payload al puente sw_savecmd) ── */
function collect(){
  var variants=[];
  [].slice.call(doc.querySelectorAll('.ed-vrow')).forEach(function(row){
    var id=row.getAttribute('data-vid');
    var pr=row.querySelector('.ed-price'), cm=row.querySelector('.ed-cmp');
    variants.push({id:id, price:parseInt((pr.value||'0').replace(/\D/g,'')||'0',10),
                   compare_at:parseInt((cm.value||'0').replace(/\D/g,'')||'0',10)});
  });
  var channels_on=[];
  [].slice.call(doc.querySelectorAll('.ed-chan')).forEach(function(c){ if(c.checked) channels_on.push(c.getAttribute('data-gid')); });
  var collections_on=[];
  [].slice.call(doc.querySelectorAll('.ed-col')).forEach(function(c){ if(c.checked) collections_on.push(c.getAttribute('data-cid')); });
  var image_order=[], image_delete=[], image_add_urls=[], video_delete=[], media_order=[], new_ext_videos=[];
  [].slice.call(grid.querySelectorAll('.ed-img')).forEach(function(t){
    var mgid=t.getAttribute('data-mediaid');   // gid del media (foto o video) para reordenar TODO junto
    if(t.getAttribute('data-video')==='1'){    // tile de video
      var nvu=t.getAttribute('data-newvidurl');
      if(nvu){ new_ext_videos.push(nvu); return; }   // video externo nuevo (por URL) → se agrega al guardar
      if(t.classList.contains('ed-deleted')){ var mid=t.getAttribute('data-mid'); if(mid) video_delete.push(mid); }
      else if(mgid){ media_order.push(mgid); }
      return;
    }
    var id=t.getAttribute('data-id');
    if(t.classList.contains('ed-deleted')){ if(id) image_delete.push(parseInt(id,10)); return; }
    if(t.getAttribute('data-new')==='1'){ image_add_urls.push(t.getAttribute('data-src')); return; }
    if(id) image_order.push(parseInt(id,10));
    if(mgid) media_order.push(mgid);
  });
  return {
    title:doc.getElementById('f_title').value,
    body_html:doc.getElementById('f_desc').value,
    status:doc.getElementById('f_status').value,
    product_type:doc.getElementById('f_type').value,
    vendor:doc.getElementById('f_vendor').value,
    variants:variants, channels_on:channels_on, collections_on:collections_on,
    channels_present:doc.querySelectorAll('.ed-chan').length>0,
    collections_present:doc.querySelectorAll('.ed-col').length>0,
    image_order:image_order, image_delete:image_delete, image_add_urls:image_add_urls,
    video_delete:video_delete, media_order:media_order, new_ext_videos:new_ext_videos,
    metafields:collectMetafields(),
    especs_sidebar:(function(){ var e=doc.getElementById('f_especs'); return e?{value:e.value,
      type:e.getAttribute('data-type')||'', id:e.getAttribute('data-id')||'',
      orig:e.getAttribute('data-orig')||''}:null; })()
  };
}
function fire(payload){
  try{
    var W=window.parent, D=W.document;
    var inp=D.querySelector('.st-key-sw_savecmd input'); if(!inp) return;
    var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
    inp.focus({preventScroll:true});
    setter.call(inp, payload+'|'+Date.now());
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.dispatchEvent(new FocusEvent('blur',{bubbles:true}));
    inp.dispatchEvent(new FocusEvent('focusout',{bubbles:true}));
    inp.blur();
  }catch(e){}
}
/* ── Estado "hay cambios" (dirty) + exponer el guardado al botón flotante del padre ──
   dirty = el formulario ACTUAL difiere del estado INICIAL. Así, si agregas algo y luego
   lo quitas (o editas y vuelves atrás), el botón se DESACTIVA de nuevo. */
var _initial=null;
function collectStr(){ try{ return JSON.stringify(collect()); }catch(e){ return ''; } }
function imgMetaDirty(){ try{ return (imgMetaFiles&&Object.keys(imgMetaFiles).length>0)||(imgMetaRemove&&Object.keys(imgMetaRemove).length>0); }catch(e){ return false; } }
function setDirty(){ try{ window.parent._swDirty=((_initial!==null && collectStr()!==_initial) || (typeof pcFiles!=='undefined' && pcFiles.length>0) || imgMetaDirty()); }catch(e){} }
try{
  var _P=window.parent;
  _P._swDirty=false;                         // al cargar, sin cambios → botón deshabilitado
  _P._swSave=async function(){               // guarda el formulario Y sube las fotos/videos del PC pendientes
    try{
      var payload=collect();
      if(typeof pcFiles!=='undefined' && pcFiles.length){
        var totV=pcFiles.filter(function(f){return f.isVideo;}).reduce(function(a,f){return a+f.file.size;},0);
        if(totV>100*1024*1024){
          if(pcmsg){ pcmsg.textContent='Los videos suman '+(totV/1048576).toFixed(0)+' MB. Máximo 100 MB — quita alguno o comprímelo (para videos muy pesados, súbelo directo en Shopify).'; pcmsg.style.display='block'; }
          var fb0=window.parent.document.getElementById('sw-float-save'); if(fb0){ fb0.textContent='Guardar y publicar'; fb0.disabled=false; }
          return;
        }
        var photos=[], videos=[], fb=window.parent.document.getElementById('sw-float-save');
        for(var i=0;i<pcFiles.length;i++){
          var it=pcFiles[i];
          if(it.isVideo){ var vb=await fileB64(it.file); if(vb) videos.push({name:it.name, mime:(it.file.type||'video/mp4'), b64:vb}); }
          else { var b=await resizeB64(it.file); if(b) photos.push({name:it.name, b64:b}); }
          if(fb) fb.textContent='Subiendo '+(i+1)+'/'+pcFiles.length+'…';
        }
        payload.pc_files=photos; payload.pc_videos=videos;
      }
      /* Metacampos de imagen (planta/render): subir los nuevos (base64) + marcar quitados. */
      try{
        var ims=[], imsRm=[];
        if(typeof imgMetaFiles!=='undefined'){
          for(var mk in imgMetaFiles){ var it2=imgMetaFiles[mk]; var mb=await fileB64(it2.file);
            if(mb) ims.push({namespace:it2.ns, key:mk, name:it2.file.name, mime:(it2.file.type||'image/jpeg'), b64:mb}); }
        }
        if(typeof imgMetaRemove!=='undefined'){
          for(var rk in imgMetaRemove){ imsRm.push({namespace:imgMetaRemove[rk].ns, key:rk}); }
        }
        payload.image_metas=ims; payload.image_metas_remove=imsRm;
      }catch(e){}
      fire(JSON.stringify(payload));
    }catch(e){}
  };
}catch(e){}
_initial=collectStr();                        // foto del estado inicial (sin cambios)
doc.addEventListener('input', function(e){ var id=e.target&&e.target.id; if(id==='addurl'||id==='addvidurl') return; setDirty(); });
doc.addEventListener('change', function(e){ var id=e.target&&e.target.id; if(id==='addurl'||id==='addvidurl') return; setDirty(); });

/* ── Agregar fotos/videos desde el PC (miniaturas 80x80 + resize/lectura + progreso) ── */
var pcFiles=[];
var pcbtn=doc.getElementById('pcbtn'), pcfile=doc.getElementById('pcfile'),
    pcwrap=doc.getElementById('pcwrap'), pcthumbs=doc.getElementById('pcthumbs'),
    pccount=doc.getElementById('pccount'), pcmsg=doc.getElementById('pcmsg');
function pcRender(){
  pcthumbs.innerHTML='';
  pcFiles.forEach(function(it,idx){
    var d=doc.createElement('div'); d.className='ed-pcthumb';
    if(it.isVideo){
      d.innerHTML='<video src="'+it.url+'" muted preload="metadata"></video>'
        +'<div class="ed-pcplay"><span><svg width="12" height="12" viewBox="0 0 24 24" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg></span></div>'
        +'<span class="ed-pcvtag">VIDEO</span>'
        +'<button type="button" class="ed-pcx" data-i="'+idx+'">×</button>';
    }else{
      d.innerHTML='<img src="'+it.url+'" alt=""><button type="button" class="ed-pcx" data-i="'+idx+'">×</button>';
    }
    pcthumbs.appendChild(d);
  });
  if(pcFiles.length){   // tile "+" al final para seguir agregando (estilo Shopify)
    var add=doc.createElement('div'); add.className='ed-pcadd'; add.setAttribute('title','Agregar más'); add.textContent='+';
    pcthumbs.appendChild(add);
  }
  var nv=pcFiles.filter(function(f){return f.isVideo;}).length, ni=pcFiles.length-nv, parts=[];
  if(ni) parts.push(ni+(ni===1?' foto':' fotos')); if(nv) parts.push(nv+(nv===1?' video':' videos'));
  pccount.textContent=parts.join(' · ')||'0 archivos';
  pcwrap.classList.toggle('on', pcFiles.length>0);
  pcbtn.style.display = pcFiles.length ? 'none' : '';   // con archivos: se usa el tile "+"
  setDirty();
}
pcbtn.addEventListener('click',function(){ pcfile.click(); });
pcfile.addEventListener('change',function(){
  var fs=this.files||[];
  for(var i=0;i<fs.length;i++){ var f=fs[i]; pcFiles.push({file:f, url:URL.createObjectURL(f), name:f.name, isVideo:((f.type||'').indexOf('video')===0)}); }
  this.value=''; if(pcmsg) pcmsg.style.display='none'; pcRender();
});
pcthumbs.addEventListener('click',function(e){
  if(e.target.closest && e.target.closest('.ed-pcadd')){ pcfile.click(); return; }
  var x=e.target.closest?e.target.closest('.ed-pcx'):null; if(!x) return;
  var i=parseInt(x.getAttribute('data-i'),10); if(!isNaN(i)){ pcFiles.splice(i,1); pcRender(); }
});
doc.getElementById('pcclear').addEventListener('click',function(){ pcFiles=[]; if(pcmsg) pcmsg.style.display='none'; pcRender(); });
function resizeB64(file){
  return new Promise(function(res){
    var img=new Image();
    img.onload=function(){
      var mx=1500, w=img.width, h=img.height, s=Math.min(1, mx/Math.max(w,h));
      var cw=Math.max(1,Math.round(w*s)), ch=Math.max(1,Math.round(h*s));
      var cv=doc.createElement('canvas'); cv.width=cw; cv.height=ch;
      try{ cv.getContext('2d').drawImage(img,0,0,cw,ch); res((cv.toDataURL('image/jpeg',0.8).split(',')[1])||''); }
      catch(e){ res(''); }
    };
    img.onerror=function(){ res(''); };
    img.src=URL.createObjectURL(file);
  });
}
function fileB64(file){
  return new Promise(function(res){ var r=new FileReader();
    r.onload=function(){ try{ res((''+r.result).split(',')[1]||''); }catch(e){ res(''); } };
    r.onerror=function(){ res(''); }; r.readAsDataURL(file); });
}
/* ── Agregar video por enlace (YouTube/Vimeo): agrega un tile a la galería y se
   sube al presionar "Guardar y publicar" (igual que las fotos por URL / desde PC). ── */
var addvidbtn=doc.getElementById('addvidbtn'), addvidurl=doc.getElementById('addvidurl');
function syncVid(){ addvidbtn.disabled=!(addvidurl.value||'').trim(); }
function addVid(){
  var u=(addvidurl.value||'').trim(); if(!u) return;
  var grip='<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/><circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/><circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>';
  var xico='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>';
  var play='<svg viewBox="0 0 24 24" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg>';
  var d=doc.createElement('div'); d.className='ed-img ed-video ed-new'; d.setAttribute('draggable','false');
  d.setAttribute('data-video','1'); d.setAttribute('data-new','1');
  d.setAttribute('data-newvidurl',u); d.setAttribute('data-vorigin',u);
  d.innerHTML='<div class="ed-vph">VIDEO</div><div class="ed-vplay">'+play+'</div><span class="ed-drag" title="Arrastra para reordenar">'+grip+'</span><button type="button" class="ed-del">'+xico+'</button><span class="ed-vbadge">Video</span>';
  grid.appendChild(d); addvidurl.value=''; syncVid(); setDirty();
}
addvidurl.addEventListener('input',syncVid);
addvidbtn.addEventListener('click',function(){ if(!this.disabled) addVid(); });
addvidurl.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); addVid(); }});
syncVid();

/* ── Metacampos de imagen (planta / render): elegir / ampliar / quitar ──
   Los archivos se leen a base64 y se suben al pulsar «Guardar y publicar» (via _swSave). */
var imgMetaFiles={}, imgMetaRemove={};
function openImgFs(url){    // visor fullscreen de UNA imagen, montado en el doc padre
  if(!url) return; var PD=_swPD();
  var old=PD.getElementById('sw-imgfs'); if(old) old.remove();
  var prevOv=PD.body.style.overflow; PD.body.style.overflow='hidden';
  var ov=PD.createElement('div'); ov.id='sw-imgfs';
  ov.style.cssText='position:fixed;inset:0;background:rgba(6,11,22,.94);z-index:2147483647;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;';
  ov.innerHTML='<button class="_cl" title="Cerrar" style="position:absolute;top:16px;right:18px;width:40px;height:40px;border-radius:50%;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:#fff;cursor:pointer;font-size:22px;line-height:1;display:flex;align-items:center;justify-content:center;">×</button>'
    +'<img src="'+(url+'').replace(/"/g,'&quot;')+'" style="max-width:94vw;max-height:90vh;object-fit:contain;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.5);">';
  PD.body.appendChild(ov);
  function close(){ if(ov.parentNode) ov.parentNode.removeChild(ov); PD.body.style.overflow=prevOv||''; PD.removeEventListener('keydown',onKey); }
  function onKey(e){ if(e.key==='Escape') close(); }
  ov.addEventListener('click', function(e){ if(e.target===ov) close(); });
  ov.querySelector('._cl').addEventListener('click', close);
  PD.addEventListener('keydown', onKey);
}
[].slice.call(doc.querySelectorAll('.ed-ims')).forEach(function(slot){
  var key=slot.getAttribute('data-key'), ns=slot.getAttribute('data-ns');
  var hadImg=slot.getAttribute('data-hasimg')==='1';
  var fileIn=slot.querySelector('.ed-ims-file'), img=slot.querySelector('.ed-ims-img'),
      empty=slot.querySelector('.ed-ims-empty'), badge=slot.querySelector('.ed-ims-badge'),
      ov=slot.querySelector('.ed-ims-ov'), zoom=slot.querySelector('.ed-ims-zoom'),
      clr=slot.querySelector('.ed-ims-clear'), pick=slot.querySelector('.ed-ims-pick'),
      picktxt=slot.querySelector('.ed-ims-picktxt');
  function curUrl(){ return img && img.getAttribute('src'); }
  function hasShown(){ return curUrl() || imgMetaFiles[key]; }
  function refresh(){ if(ov) ov.style.display=hasShown()?'':'none'; if(picktxt) picktxt.textContent=hasShown()?'Cambiar imagen':'Subir imagen'; }
  pick.addEventListener('click', function(){ fileIn.click(); });
  if(zoom) zoom.addEventListener('click', function(){ openImgFs(curUrl()); });
  fileIn.addEventListener('change', function(){
    var f=this.files&&this.files[0]; if(!f) return;
    imgMetaFiles[key]={file:f, ns:ns}; delete imgMetaRemove[key];
    var url=URL.createObjectURL(f);
    if(img){ img.setAttribute('src',url); img.style.display=''; }
    if(empty) empty.style.display='none';
    if(badge) badge.style.display='';
    this.value=''; refresh(); setDirty();
  });
  if(clr) clr.addEventListener('click', function(){
    delete imgMetaFiles[key];
    if(hadImg) imgMetaRemove[key]={ns:ns};   // quitar el metacampo existente al guardar
    if(img){ img.removeAttribute('src'); img.style.display='none'; }
    if(empty) empty.style.display='';
    if(badge) badge.style.display='none';
    refresh(); setDirty();
  });
  refresh();
});

/* ── Auto-ajuste de la altura del iframe a su contenido (sin barra de scroll) ──
   Se mide el ALTO del wrapper #ed-root (offsetHeight = alto del contenido, NO depende
   del alto exterior del iframe) → así NO hay bucle de realimentación (que hacía crecer
   el iframe al infinito y tiritar la pantalla). */
function swResize(){
  try{
    var el=doc.getElementById('ed-root'); if(!el) return;
    var h=Math.ceil(el.offsetHeight)+6;
    var fe=window.frameElement; if(!fe) return;
    if(Math.abs((parseInt(fe.style.height,10)||0)-h)>3){ fe.style.setProperty('height', h+'px', 'important'); }
  }catch(e){}
}
setInterval(swResize, 200);
[0,150,400].forEach(function(t){ setTimeout(swResize, t); });
})();
</script>
</body></html>"""


def _mf_rows_html(editable):
    """Filas HTML de los metacampos editables (Características/detalles) para el iframe.
    Cada fila guarda ns/key/type/id/kind/orig en data-attrs para armar el payload."""
    _trash = ('<button type="button" class="ed-mf-del" title="Vaciar/eliminar">'
              '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/>'
              '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>')
    _rows = ""
    for m in editable or []:
        _ns = m.get("namespace") or "custom"
        _key = m.get("key") or ""
        _mid = m.get("id") or ""
        _kind = _mf_kind(m.get("type"))
        _name = _he(m.get("name") or _mf_label(m))
        _kindlbl = _he(_MF_KIND_LABEL.get(_kind, "Texto")) + ("" if _mid else " · sin completar")
        if _kind in ("rich", "multi"):
            _val = _richtext_to_text(m.get("value")) if _kind == "rich" else str(m.get("value") or "")
            _ctl = f'<textarea class="ed-in ed-mf-input">{_he(_val)}</textarea>'
            _orig = _val
        elif _kind == "bool":
            _chk = " checked" if str(m.get("value")).strip().lower() == "true" else ""
            _ctl = f'<label class="ed-mf-bool"><input type="checkbox" class="ed-mf-input"{_chk}><span>Sí</span></label>'
            _orig = "true" if _chk else "false"
        else:
            _val = str(m.get("value") or "")
            _im = ' inputmode="numeric"' if _kind in ("int", "dec") else ''
            _ctl = f'<input class="ed-in ed-mf-input" type="text"{_im} value="{_he(_val)}">'
            _orig = _val
        _rows += (
            f'<div class="ed-mf-row" data-ns="{_he(_ns)}" data-key="{_he(_key)}" '
            f'data-type="{_he(m.get("type") or "")}" data-id="{_he(_mid)}" data-kind="{_kind}" '
            f'data-orig="{_he(_orig)}">'
            f'<div class="ed-mf-name">{_name}<small>{_kindlbl}</small></div>'
            f'<div class="ed-mf-ctl">{_ctl}{_trash}</div></div>')
    return _rows or '<div class="ed-info">No hay características definidas en la tienda.</div>'


def _especs_to_text(_type, _value):
    """Valor del metacampo → texto para el textarea (lista = una línea por ítem)."""
    import json as _json
    _t = str(_type or "")
    if _t.startswith("list."):
        try:
            _arr = _json.loads(_value) if _value else []
            if isinstance(_arr, list):
                return "\n".join(str(x) for x in _arr)
        except Exception:
            pass
        return str(_value or "")
    if _t == "rich_text_field":
        return _richtext_to_text(_value)
    return str(_value or "")


def _especs_serialize(_type, _text):
    """Texto del textarea → valor para Shopify según el tipo. Devuelve (serializado, vacío?)."""
    import json as _json
    _t = str(_type or "")
    if _t.startswith("list."):
        _lines = [ln.strip() for ln in str(_text or "").splitlines() if ln.strip()]
        return _json.dumps(_lines, ensure_ascii=False), (len(_lines) == 0)
    if _t == "rich_text_field":
        return _text_to_richtext(_text or ""), (not str(_text or "").strip())
    _s = str(_text or "")
    return _s, (not _s.strip())


def _especs_html(especs):
    """Tarjeta HTML del metacampo ESPECIFICACIONES (SIDEBAR) — textarea, ancho completo."""
    if not especs:
        return ""
    _t = str(especs.get("type") or "")
    _islist = _t.startswith("list.")
    _hint = ("Una especificación por línea (aparecen como lista en la barra lateral)."
             if _islist else "Texto de las especificaciones que se muestra en la barra lateral.")
    _ph = "Ej: 2 dormitorios&#10;45 m²&#10;Baño completo&#10;Cocina equipada"
    return (
        '<div class="ed-card ed-especs-card" style="grid-column:1 / -1;margin-top:16px;">'
        '<div class="ed-lbl">Especificaciones (sidebar)</div>'
        '<div class="ed-mf-hint">Las especificaciones que se muestran en la barra lateral del '
        'producto en la web (metacampo <code>custom.especificaciones_sidebar</code>). Se guardan '
        'con «Guardar y publicar».</div>'
        f'<div class="ed-especs-hint">{_hint}</div>'
        f'<textarea class="ed-in ed-especs-input" id="f_especs" data-type="{_he(_t)}" '
        f'data-id="{_he(especs.get("id") or "")}" data-orig="{_he(especs.get("text") or "")}" '
        f'placeholder="{_ph}">{_he(especs.get("text") or "")}</textarea></div>')


def _imgmeta_html(img_metas):
    """Slots HTML de los metacampos de imagen (planta/render) para el formulario. Cada slot:
    caja con la imagen actual (uniforme), botón para elegir/cambiar y botón para quitar."""
    _cam = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 '
            '2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3z"/><circle cx="12" cy="13" r="3"/></svg>')
    _zoom = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h6v6"/><path d="M9 21H3v-6"/>'
             '<path d="M21 3l-7 7"/><path d="M3 21l7-7"/></svg>')
    _x = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" '
          'stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>')
    _out = ""
    for m in (img_metas or []):
        _url = _he(m.get("url") or "")
        _has = "1" if _url else "0"
        _imgstyle = "" if _url else "display:none;"
        _emptystyle = "display:none;" if _url else ""
        _ovstyle = "" if _url else "display:none;"
        _out += (
            f'<div class="ed-ims" data-ns="{_he(m.get("ns") or "custom")}" '
            f'data-key="{_he(m.get("key"))}" data-hasimg="{_has}">'
            f'<div class="ed-ims-lbl">{_he(m.get("label"))}</div>'
            f'<div class="ed-ims-box"><img class="ed-ims-img" src="{_url}" alt="" style="{_imgstyle}">'
            f'<div class="ed-ims-empty" style="{_emptystyle}">Sin imagen</div>'
            '<span class="ed-ims-badge" style="display:none">Nueva</span>'
            f'<div class="ed-ims-ov" style="{_ovstyle}">'
            f'<button type="button" class="ed-ims-zoom" title="Ampliar">{_zoom}</button>'
            f'<button type="button" class="ed-ims-clear" title="Quitar imagen">{_x}</button>'
            '</div></div>'
            f'<div class="ed-ims-hint">{_he(m.get("hint") or "")}</div>'
            f'<div class="ed-ims-acts"><button type="button" class="ed-ims-pick">{_cam}'
            f'<span class="ed-ims-picktxt">{"Cambiar imagen" if _url else "Subir imagen"}</span></button>'
            '<input type="file" class="ed-ims-file" accept="image/png,image/jpeg,image/webp" style="display:none">'
            '</div></div>')
    return _out or '<div class="ed-info">No hay metacampos de imagen configurados.</div>'


def _build_editor_form(p, pubs, prod_pubs, cols, cur_cols, metafields=None, videos=None,
                       img_metas=None, especs=None):
    """Arma el formulario HTML del editor. `pubs`=canales [{id,name}], `prod_pubs`=set
    GIDs publicados, `cols`=colecciones [{id,title}], `cur_cols`=ids seleccionadas,
    `videos`=medios de video del producto (se muestran junto a las fotos).
    Devuelve (html, alto_iframe)."""
    _imgs = p.get("images") or []
    _vids = videos or []
    _x = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>'
    _play = '<svg viewBox="0 0 24 24" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg>'
    _grip = ('<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/>'
             '<circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/>'
             '<circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>')
    _img_html = ""
    for im in _imgs:
        _src = _he(im.get("src", ""))
        _mgid = _he(im.get("admin_graphql_api_id") or "")   # gid del MediaImage (para reordenar)
        _img_html += (f'<div class="ed-img" draggable="false" data-id="{_he(im.get("id"))}" data-mediaid="{_mgid}">'
                      f'<img src="{_src}" alt="">'
                      f'<span class="ed-drag" title="Arrastra para reordenar">{_grip}</span>'
                      f'<button type="button" class="ed-del">{_x}</button>'
                      '<span class="ed-princ">Principal</span></div>')
    # Videos (subidos desde el PC o por enlace): mismos tiles que las fotos, con badge de
    # reproducción y su propia manija de arrastre (se reordenan junto con las fotos vía
    # media gid). NO son "principal". Se pueden eliminar. Van después de las fotos.
    for vd in _vids:
        _mid = _he(vd.get("id") or "")
        _pv = _he(vd.get("preview_url") or "")
        _vsrc = _he(vd.get("src") or "")
        _vorig = _he(vd.get("origin_url") or "")
        _thumb = (f'<img src="{_pv}" alt="">' if _pv
                  else '<div class="ed-vph">VIDEO</div>')
        _img_html += (f'<div class="ed-img ed-video" draggable="false" data-video="1" data-mid="{_mid}" '
                      f'data-mediaid="{_mid}" data-vsrc="{_vsrc}" data-vpv="{_pv}" data-vorigin="{_vorig}">'
                      f'{_thumb}<div class="ed-vplay">{_play}</div>'
                      f'<span class="ed-drag" title="Arrastra para reordenar">{_grip}</span>'
                      f'<button type="button" class="ed-del">{_x}</button>'
                      '<span class="ed-vbadge">Video</span></div>')
    if not _img_html:
        _img_html = ('<div class="ed-noimg">Este producto no tiene fotos ni videos. '
                     'Agrega una foto por URL o sube fotos/videos desde el PC abajo.</div>')

    # Precios por variante
    _vars = p.get("variants") or []
    _prices = ""
    for v in _vars:
        _vt = v.get("title") or ""
        _vt_html = (f'<div class="ed-vtitle">{_he(_vt)}</div>'
                    if _vt and _vt.lower() != "default title" else "")
        _prices += (
            f'<div class="ed-vrow" data-vid="{_he(v.get("id"))}">{_vt_html}'
            '<div class="ed-two">'
            '<div><label class="ed-flbl">Precio (ahora)</label>'
            '<div class="ed-money-wrap"><input class="ed-in ed-money ed-price" inputmode="numeric" '
            f'value="{_clp_plain(v.get("price"))}"></div></div>'
            '<div><label class="ed-flbl">Precio antes (tachado)</label>'
            '<div class="ed-money-wrap"><input class="ed-in ed-money ed-cmp" inputmode="numeric" '
            f'value="{_clp_plain(v.get("compare_at_price"))}"></div></div>'
            '</div></div>')
    if not _prices:
        _prices = '<div class="ed-noimg">Sin variantes.</div>'

    # Estado
    _cur_est = _estado_efectivo(p)
    _status = ""
    for _val, _lbl in (("active", "Activo"), ("unlisted", "No publicado"),
                       ("draft", "Borrador"), ("archived", "Archivado")):
        _st_key = {"active": "active", "unlisted": "unpublished", "draft": "draft", "archived": "archived"}[_val]
        _sel = " selected" if _st_key == _cur_est else ""
        _status += f'<option value="{_val}"{_sel}>{_lbl}</option>'

    # Canales
    _channels = ""
    for pub in (pubs or []):
        _gid = pub.get("id")
        _chk = " checked" if _gid in (prod_pubs or set()) else ""
        _channels += (f'<label class="ed-toggle"><span>{_he(pub.get("name", "Canal"))}</span>'
                      f'<span class="ed-sw"><input type="checkbox" class="ed-chan" data-gid="{_he(_gid)}"{_chk}>'
                      '<i></i></span></label>')
    if not _channels:
        _channels = ('<div class="ed-info">Para gestionar canales, el token necesita '
                     '<b>read_publications</b> y <b>write_publications</b>. Agrégalos y reinstala la app.</div>')

    # Colecciones
    _collections = ""
    _curset = set(str(c) for c in (cur_cols or []))
    for c in (cols or []):
        _cid = str(c.get("id"))
        _chk = " checked" if _cid in _curset else ""
        _collections += (f'<label class="ed-check"><input type="checkbox" class="ed-col" '
                         f'data-cid="{_he(_cid)}"{_chk}><span>{_he(c.get("title", "(sin título)"))}</span></label>')
    if not _collections:
        _collections = '<div class="ed-info">No hay colecciones manuales en la tienda.</div>'

    _title_attr = _he(p.get("title") or "")               # valor del input (vacío = en blanco)
    _title_disp = _he(p.get("title") or "(sin título)")    # encabezado mini
    _html = (_SW_FORM_TEMPLATE
             .replace("__TITLE_ATTR__", _title_attr).replace("__TITLE__", _title_disp)
             .replace("__IMAGES__", _img_html)
             .replace("__DESC__", _he(p.get("body_html") or ""))
             .replace("__PRICES__", _prices)
             .replace("__STATUS__", _status)
             .replace("__CHANNELS__", _channels)
             .replace("__TYPE__", _he(p.get("product_type") or ""))
             .replace("__VENDOR__", _he(p.get("vendor") or ""))
             .replace("__COLLECTIONS__", _collections)
             .replace("__METAFIELDS__", _mf_rows_html(metafields))
             .replace("__ESPECS__", _especs_html(especs))
             .replace("__IMGMETAS__", _imgmeta_html(img_metas)))
    # Altura estimada (izquierda vs derecha) + características (el iframe se auto-ajusta luego).
    _nmedia = len(_imgs) + len(_vids)
    _img_rows = (_nmedia + 3) // 4 if _nmedia else 1
    _left = 70 + (_img_rows * 118 + 90) + 300 + (max(1, len(_vars)) * 110 + 60)
    _right = 130 + (max(1, len(pubs or [])) * 44 + 60) + (200 + len(cols or []) * 34)
    _mf_h = 90 + len(metafields or []) * 78
    _imgmeta_h = 360 if (img_metas is not None) else 0   # tarjeta de imágenes planta/render
    _especs_h = 250 if especs else 0                      # tarjeta especificaciones sidebar
    _h = 70 + max(_left, _right) + _mf_h + _imgmeta_h + _especs_h
    return _html, _h


def _clear_editor_state():
    for k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_ed_")]:
        st.session_state.pop(k, None)
    st.session_state.pop("sw_edit_prod", None)
    st.session_state.pop("sw_edit_mf", None)
    st.session_state.pop("sw_edit_mf_pid", None)
    st.session_state.pop("sw_edit_vid", None)
    st.session_state.pop("sw_edit_vid_pid", None)
    st.session_state.pop("sw_edit_collects", None)
    st.session_state.pop("sw_edit_collects_pid", None)
    st.session_state.pop("sw_edit_prodpubs", None)
    st.session_state.pop("sw_edit_prodpubs_pid", None)
    st.session_state.pop("sw_up_excluded", None)


def _duplicar_flow(pid):
    """Duplica un producto como BORRADOR (copia fotos/variantes/desc + las características
    editables) y abre el editor del NUEVO para renombrarlo y ajustarlo. Hace rerun."""
    _p, _ = _shop.get_producto(pid)
    _orig = (_p or {}).get("title", "Producto") if _p else "Producto"
    with st.spinner("Duplicando producto…"):
        _newid, _err = _shop.duplicar_producto(pid, f"Copia de {_orig}",
                                                include_images=True, new_status="DRAFT")
    if _err or not _newid:
        st.error(_err or "No se pudo duplicar el producto.", icon=":material/error:")
        return
    # Copiar las características (metafields) EDITABLES (Shopify no las duplica). Las
    # referencias/listas/json se omiten (apuntarían a media del original).
    try:
        _mfs, _ = _shop.listar_metafields(pid)
        for m in (_mfs or []):
            if _mf_kind(m.get("type")) == "readonly":
                continue
            _shop.crear_metafield(_newid, m.get("namespace") or "custom", m.get("key"),
                                  m.get("type"), m.get("value"))
    except Exception:
        pass
    _clear_editor_state()
    st.session_state.pop("sw_new", None)
    _cargar_productos.clear()
    st.session_state["sw_edit_id"] = str(_newid)
    st.session_state["sw_toast"] = "Producto duplicado (borrador). Renómbralo y ajústalo antes de activarlo."
    st.rerun()


def _guardar_todo(pid, data: dict):
    """Persiste TODO el formulario del editor en Shopify de una sola vez: datos del
    producto, precios, estado, canales, colecciones y fotos (borrar/reordenar/agregar).
    Devuelve lista de errores (vacía = todo OK)."""
    _errs = []
    # 1) Datos del producto (título/desc/estado/tipo/proveedor).
    _campos = {
        "title": (data.get("title") or "").strip(),
        "body_html": data.get("body_html") or "",
        "status": (data.get("status") or "active"),
        "product_type": (data.get("product_type") or "").strip(),
        "vendor": (data.get("vendor") or "").strip(),
    }
    _ok, _e = _shop.actualizar_producto(pid, _campos)
    if not _ok:
        _errs.append(_e)
    # 2) Precios por variante.
    for v in data.get("variants") or []:
        try:
            _price = int(v.get("price") or 0)
        except Exception:
            _price = 0
        try:
            _cmp = int(v.get("compare_at") or 0)
        except Exception:
            _cmp = 0
        _vc = {"price": str(_price), "compare_at_price": (str(_cmp) if _cmp > 0 else None)}
        _ok, _e = _shop.actualizar_variante(v.get("id"), _vc)
        if not _ok:
            _errs.append(_e)
    # 3) Canales (diff contra lo publicado actualmente). Solo si el formulario mostró
    # los toggles (evita des-publicar por accidente cuando no cargaron / falta scope).
    _cur_pub, _ = _shop.publicaciones_de_producto(pid) if data.get("channels_present") else (None, None)
    if _cur_pub is not None:
        _desired = set(data.get("channels_on") or [])
        _to_pub = [g for g in _desired if g not in _cur_pub]
        _to_unpub = [g for g in _cur_pub if g not in _desired]
        if _to_pub:
            _ok, _e = _shop.publicar_en_canales(pid, _to_pub)
            if not _ok:
                _errs.append(_e)
        if _to_unpub:
            _ok, _e = _shop.despublicar_de_canales(pid, _to_unpub)
            if not _ok:
                _errs.append(_e)
    # 4) Colecciones (diff). Solo si el formulario mostró las colecciones.
    _collects, _ = _shop.colecciones_de_producto(pid) if data.get("collections_present") else ([], None)
    _collect_by_col = {str(cl.get("collection_id")): cl.get("id") for cl in (_collects or [])}
    _cur_c = set(_collect_by_col.keys()) if data.get("collections_present") else set()
    _desired_c = set(str(c) for c in (data.get("collections_on") or []))
    for _cid in _desired_c - _cur_c:
        _ok, _e = _shop.agregar_a_coleccion(pid, _cid)
        if not _ok:
            _errs.append(_e)
    for _cid in _cur_c - _desired_c:
        _collectid = _collect_by_col.get(_cid)
        if _collectid:
            _ok, _e = _shop.quitar_de_coleccion(_collectid)
            if not _ok:
                _errs.append(_e)
    # 5) Medios (fotos + videos): eliminar marcados → agregar fotos nuevas → reordenar TODO.
    for _iid in data.get("image_delete") or []:
        _ok, _e = _shop.eliminar_imagen(pid, _iid)
        if not _ok:
            _errs.append(_e)
    for _vmid in data.get("video_delete") or []:      # videos marcados (por media id)
        if _vmid:
            _ok, _e = _shop.eliminar_media(pid, _vmid)
            if not _ok:
                _errs.append(_e)
    for _url in data.get("image_add_urls") or []:
        if _url:
            _ok, _e = _shop.agregar_imagen(pid, src=_url)
            if not _ok:
                _errs.append(_e)
    for _vu in data.get("new_ext_videos") or []:      # videos por enlace (YouTube/Vimeo)
        if _vu:
            _ok, _e = _shop.agregar_video_externo(pid, _vu)
            if not _ok:
                _errs.append(_e)
    # Reordenar TODO el media (fotos + videos) en el orden visual de la galería. Los
    # medios recién agregados no traen gid → quedan al final (Shopify los deja después).
    _mo = [g for g in (data.get("media_order") or []) if g]
    if len(_mo) >= 2:
        _ok, _e = _shop.reordenar_media(pid, _mo)
        if not _ok:
            _errs.append(_e)
    elif data.get("image_order"):                     # fallback si no hubo gids de media
        _ok, _e = _shop.reordenar_imagenes(pid, list(data.get("image_order")))
        if not _ok:
            _errs.append(_e)
    # 6) Características / detalles (metacampos): crear / actualizar / eliminar.
    for m in data.get("metafields") or []:
        _kind = m.get("kind")
        _mid = (m.get("id") or "").strip()
        _mns = m.get("ns") or "custom"
        _mkey = m.get("key") or ""
        _mtype = m.get("type") or "single_line_text_field"
        _mval = m.get("value")
        if m.get("deleted"):
            if _mid:
                _ok, _e = _shop.eliminar_metafield(pid, _mid)
                if not _ok:
                    _errs.append(_e)
            continue
        if str(_mval) == str(m.get("orig")):
            continue                     # sin cambios → no tocar
        if _kind == "rich":
            _ser = _text_to_richtext(_mval or "")
            _mtype = "rich_text_field"
            _empty = not str(_mval or "").strip()
        elif _kind == "bool":
            _ser = "true" if str(_mval).strip().lower() == "true" else "false"
            _mtype = "boolean"
            _empty = (_ser == "false")
        elif _kind == "int":
            try:
                _ser = str(int(float(_mval or 0)))
            except Exception:
                _ser = "0"
            _empty = (_ser in ("0", ""))
        elif _kind == "dec":
            try:
                _ser = ("%.4f" % float(_mval or 0)).rstrip("0").rstrip(".") or "0"
            except Exception:
                _ser = "0"
            _empty = (_ser in ("0", ""))
        else:
            _ser = str(_mval or "")
            _empty = not _ser.strip()
        if _mid:
            _ok, _e = _shop.actualizar_metafield(pid, _mid, _mtype, _ser)
            if not _ok:
                _errs.append(_e)
        elif not _empty:                 # nuevo y con contenido → crear
            _ok, _e = _shop.crear_metafield(pid, _mns, _mkey, _mtype, _ser)
            if not _ok:
                _errs.append(_e)
    # 6b) Especificaciones (sidebar): editor dedicado; serializa según el tipo (lista → JSON).
    _esp = data.get("especs_sidebar")
    if _esp is not None and str(_esp.get("value")) != str(_esp.get("orig")):
        _etype = _esp.get("type") or "list.single_line_text_field"
        _eid = (_esp.get("id") or "").strip()
        _eser, _eempty = _especs_serialize(_etype, _esp.get("value"))
        if _eempty:
            if _eid:
                _ok, _e = _shop.eliminar_metafield(pid, _eid)
                if not _ok:
                    _errs.append(_e)
        elif _eid:
            _ok, _e = _shop.actualizar_metafield(pid, _eid, _etype, _eser)
            if not _ok:
                _errs.append(_e)
        else:
            _ok, _e = _shop.crear_metafield(pid, "custom", "especificaciones_sidebar", _etype, _eser)
            if not _ok:
                _errs.append(_e)
    # 7) Fotos/videos elegidos desde el PC (van en el mismo guardado).
    _errs += _subir_fotos(pid, data.get("pc_files") or [])
    for _v in data.get("pc_videos") or []:
        _b64v = _v.get("b64") or ""
        if not _b64v:
            continue
        try:
            _vb = base64.b64decode(_b64v)
        except Exception:
            _vb = b""
        if _vb:
            _ok, _e = _shop.subir_video(pid, _v.get("name") or "video.mp4",
                                        _v.get("mime") or "video/mp4", _vb)
            if not _ok:
                _errs.append(_e)
    # 8) Metacampos de imagen (planta/render): subir la imagen a Files y apuntar el metacampo;
    #    o quitar el metacampo si se marcó para eliminar.
    for _im in data.get("image_metas") or []:
        _b64i = _im.get("b64") or ""
        if not _b64i:
            continue
        try:
            _ib = base64.b64decode(_b64i)
        except Exception:
            _ib = b""
        if not _ib:
            continue
        _gid, _pv, _e = _shop.subir_imagen_archivo(_im.get("name") or "imagen.jpg",
                                                   _im.get("mime") or "image/jpeg", _ib)
        if _e or not _gid:
            _errs.append(_e or "No se pudo subir la imagen.")
            continue
        _ok, _e2 = _shop.set_metafield_referencia(pid, _im.get("namespace") or "custom",
                                                  _im.get("key"), _gid)
        if not _ok:
            _errs.append(_e2)
    for _rm in data.get("image_metas_remove") or []:
        _ok, _e = _shop.borrar_metafield_por_clave(pid, _rm.get("namespace") or "custom",
                                                   _rm.get("key"))
        if not _ok:
            _errs.append(_e)
    return _errs


def _subir_fotos(pid, files):
    """Sube al producto las fotos elegidas desde el PC (ya redimensionadas en el
    navegador, cada una en base64). Una request por foto. Devuelve lista de errores."""
    _errs = []
    for f in files or []:
        _b64 = f.get("b64") or ""
        if not _b64:
            continue
        _ok, _e = _shop.agregar_imagen(pid, attachment=_b64, filename=(f.get("name") or "foto.jpg"))
        if not _ok:
            _errs.append(_e)
    return _errs


@st.dialog("Eliminar producto")
def _dialog_eliminar(pid):
    """Confirmación (doble: casilla + botón) para borrar un producto de Shopify."""
    _p = st.session_state.get("sw_edit_prod")
    if not _p or str(_p.get("id")) != str(pid):
        _p, _ = _shop.get_producto(pid)
    _p = _p or {}
    _title = _p.get("title") or f"Producto {pid}"
    _imgs = _p.get("images") or []
    _img0 = (_imgs[0].get("src") if _imgs else "") or (_p.get("image") or {}).get("src", "")
    _bg, _fg, _blbl = _ESTADOS.get(_estado_efectivo(_p), _ESTADOS["active"])
    _thumb = (f'<img src="{_he(_img0)}" style="width:56px;height:56px;border-radius:10px;object-fit:cover;flex:0 0 auto;">'
              if _img0 else '<div style="width:56px;height:56px;border-radius:10px;background:#f1f5f9;flex:0 0 auto;"></div>')
    st.markdown(
        '<div style="display:flex;gap:12px;align-items:center;background:#fff;border:1px solid #e8ebf3;'
        'border-radius:12px;padding:12px 14px;margin-bottom:12px;">'
        f'{_thumb}<div><div style="font-family:\'Plus Jakarta Sans\',sans-serif;font-weight:800;color:#0f172a;'
        f'font-size:0.95rem;line-height:1.25;">{_he(_title)}</div>'
        '<span style="display:inline-block;margin-top:5px;font-family:Montserrat,sans-serif;font-weight:800;'
        'font-size:10px;text-transform:uppercase;letter-spacing:.03em;border-radius:99px;padding:3px 9px;'
        f'background:{_bg};color:{_fg};">{_blbl}</span></div></div>', unsafe_allow_html=True)
    st.markdown(
        '<div style="background:#fff1f2;border:1.5px solid #fca5a5;border-radius:12px;padding:13px 15px;">'
        '<div style="font-family:Montserrat,sans-serif;font-weight:800;font-size:0.82rem;color:#b91c1c;'
        'text-transform:uppercase;letter-spacing:.03em;display:flex;align-items:center;gap:8px;">'
        f'{_ic("alert", "#dc2626", 17, 0, 0)}Acción permanente</div>'
        '<p style="margin:7px 0 0;font-size:0.83rem;color:#7f1d1d;line-height:1.5;">Este producto se eliminará '
        'de la tienda Shopify y <b>dejará de aparecer en la web</b>, junto con sus fotos, variantes y '
        'características. <b>No se puede deshacer.</b></p></div>', unsafe_allow_html=True)
    _ok = st.checkbox("Entiendo que se elimina de la web de forma permanente.", key="sw_del_ck")
    _c1, _c2 = st.columns(2)
    with _c1:
        if st.button("Cancelar", key="sw_del_cancel", use_container_width=True, icon=":material/close:"):
            st.session_state.pop("sw_del_pending", None)
            st.session_state.pop("sw_del_ck", None)
            st.rerun()
    with _c2:
        if st.button("Sí, eliminar", key="sw_del_go", type="primary", use_container_width=True,
                     icon=":material/delete_forever:", disabled=not _ok):
            with st.spinner("Eliminando producto…"):
                _ok2, _err = _shop.eliminar_producto(pid)
            if _err or not _ok2:
                st.error(_err or "No se pudo eliminar el producto.", icon=":material/error:")
                return
            st.session_state.pop("sw_del_pending", None)
            st.session_state.pop("sw_del_ck", None)
            st.session_state.pop("sw_edit_id", None)
            _clear_editor_state()
            _cargar_productos.clear()
            st.session_state["sw_toast"] = f"Producto eliminado: {_title}"
            st.rerun()


def render_tab_sitio_web(**kwargs):
    if st.session_state.get("rol_usuario", "ejecutivo") not in ("root", "admin", "sitio_web"):
        st.info("Esta sección es solo para administradores (admin y root) y el rol Sitio web.",
                icon=":material/lock:")
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

    # ── Puente para abrir el editor / duplicar ──
    # Tras procesar un comando dejamos el input VACÍO: así el siguiente clic es una
    # transición vacío→valor, que Streamlit commitea de forma fiable (cambiar de un
    # valor no-vacío a otro a veces NO commitea en Streamlit Cloud → "no deja editar").
    if st.session_state.pop("_sw_reset_editcmd", False):
        st.session_state["sw_editcmd"] = ""
    _ec = st.text_input("editcmd", key="sw_editcmd", label_visibility="collapsed")
    if _ec and "|" in _ec:
        _head, _ets = _ec.rsplit("|", 1)
        if _ets != st.session_state.get("sw_editcmd_ts"):
            st.session_state["sw_editcmd_ts"] = _ets
            st.session_state["_sw_reset_editcmd"] = True   # limpiar el input en el próximo run
            _act, _, _eid = _head.partition(":")
            _eid = (_eid or _act).strip()   # compat: sin ":" el payload es solo el id (editar)
            if _act == "dup":
                _duplicar_flow(_eid)        # duplica y hace rerun al editor del nuevo
            elif _act == "del":
                st.session_state["sw_del_pending"] = _eid
                st.session_state.pop("sw_del_ck", None)
                st.rerun()
            elif _eid:
                _clear_editor_state()
                st.session_state["sw_edit_id"] = _eid
                st.rerun()

    _tmsg = st.session_state.pop("sw_toast", None)
    if _tmsg:
        st.toast(_tmsg, icon=":material/check_circle:")

    # ── Confirmación de borrado (sobre cualquier modo) ──
    if st.session_state.get("sw_del_pending"):
        _dialog_eliminar(st.session_state["sw_del_pending"])

    # ── Modo NUEVO PRODUCTO ──
    if st.session_state.get("sw_new"):
        _render_nuevo()
        return

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

    # ── Vista previa del tema borrador (los productos son compartidos entre temas) ──
    _render_preview_borrador_bar()

    # ── Selector de vista: Tarjetas (por defecto) / Tabla / Ordenar web ──
    st.markdown(_SW_VISTA_CSS, unsafe_allow_html=True)
    _vistas = ["Tarjetas", "Tabla", "Ordenar web", "Reels"]
    _vicons = {"Tarjetas": ":material/grid_view:", "Tabla": ":material/table_rows:",
               "Ordenar web": ":material/swap_vert:", "Reels": ":material/movie:"}
    _vista = st.radio("Vista", _vistas, index=0, key="sw_vista", horizontal=True,
                      label_visibility="collapsed", format_func=lambda v: f"{_vicons.get(v, '')} {v}")

    # Modo "Ordenar web": arrastrar las tarjetas de una colección → fija su orden en la web.
    if _vista == "Ordenar web":
        _render_reordenar()
        return

    # Modo "Reels": ver/editar los videos reels de la sección de Shopify (bloques del tema).
    if _vista == "Reels":
        _render_reels()
        return

    # Cada opción → (status a pedir a Shopify, filtro extra client-side por estado
    # efectivo). "No publicados" (status unlisted) no tiene filtro REST propio, así que
    # se piden todos y se filtran en el cliente.
    _opts = {
        "Activos":       ("active", None),
        "No publicados": ("", "unpublished"),
        "Borradores":    ("draft", None),
        "Archivados":    ("archived", None),
        "Todos":         ("", None),
    }
    _c1, _c2, _c3 = st.columns([3.6, 1, 1.4], vertical_alignment="bottom")
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
            _plantilla_metafields.clear()
            st.session_state.pop("sw_cols", None)
            st.session_state.pop("sw_pubs", None)
            st.session_state.pop("sw_pubs_err", None)
            st.rerun()
    with _c3:
        if st.button("Nuevo modelo", key="sw_new_open", use_container_width=True, type="primary",
                     icon=":material/villa:"):
            _clear_editor_state()
            for _k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_new_")]:
                st.session_state.pop(_k, None)
            st.session_state["sw_new"] = True
            st.rerun()
    _status, _filtro_estado = _opts[_lbl]

    with st.spinner("Conectando con Shopify y trayendo los productos…"):
        _prods, _err = _cargar_productos(_status)

    if _err:
        st.error(_err, icon=":material/error:")
        components.html(_SW_JS, height=0)
        return
    if _filtro_estado:   # p.ej. "No publicados" (unlisted): filtro por estado efectivo
        _prods = [p for p in (_prods or []) if _estado_efectivo(p) == _filtro_estado]
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

    _bcol = _ESTADOS

    # ── Modo TABLA (mismo diseño que la tabla de COTIZACIONES) ──
    if _vista == "Tabla":
        _tbl_html, _tbl_h = _build_sw_table(_prods, _bcol)
        components.html(_tbl_html, height=_tbl_h + 4, scrolling=False)
        return

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
        _bg, _fg, _blbl = _bcol.get(_estado_efectivo(p), _bcol["active"])
        _ptype = _he(p.get("product_type") or (p.get("tags") or "").split(",")[0].strip() or "Producto")
        _web = _shop.producto_web_url(p.get("handle"))
        _admp = _shop.producto_admin_url(p.get("id"))
        _edit_ov = (f'<div class="sw-edit-ov">{_ic("edit", "#fff", 15, 0)}Editar</div>')
        _cards += (
            '<div class="sw-card">'
            f'<div class="sw-thumb sw-edit-btn" data-swact="edit" data-swid="{_he(p.get("id"))}" '
            f'title="Editar este modelo">{_thumb}{_edit_ov}'
            f'<span class="sw-badge" style="background:{_bg};color:{_fg};">{_blbl}</span></div>'
            '<div class="sw-body">'
            f'<div class="sw-title">{_title}</div>'
            f'<div class="sw-price">{_price}</div>{_cmp_html}'
            f'<div class="sw-meta"><span>{_ic("img", "#94a3b8", 12, 4)}{len(_imgs)} foto(s)</span>'
            f'<span>{len(_vars)} variante(s)</span></div>'
            f'<div class="sw-type">{_ptype}</div>'
            '<div class="sw-actions">'
            f'<button type="button" class="sw-btn sw-btn-edit sw-edit-btn" '
            f'data-swact="edit" data-swid="{_he(p.get("id"))}">Editar</button>'
            f'<button type="button" class="sw-btn sw-btn-dup sw-edit-btn" '
            f'data-swact="dup" data-swid="{_he(p.get("id"))}" '
            'title="Crear una copia (borrador) para un modelo nuevo">Duplicar</button></div>'
            '<div class="sw-actions" style="margin-top:6px;">'
            + (f'<a class="sw-btn sw-btn-web" href="{_he(_web)}" target="_blank">Ver</a>' if _web else "")
            + (f'<a class="sw-btn sw-btn-adm" href="{_he(_admp)}" target="_blank">Shopify</a>' if _admp else "")
            + '</div>'
            '<div class="sw-actions" style="margin-top:6px;">'
            f'<button type="button" class="sw-btn sw-btn-del sw-edit-btn" '
            f'data-swact="del" data-swid="{_he(p.get("id"))}" '
            'title="Eliminar este producto de la web">Eliminar</button></div>'
            '</div></div>')

    st.markdown(f'<div class="sw-grid">{_cards}</div>', unsafe_allow_html=True)
    components.html(_SW_JS, height=0)


def _render_nuevo():
    """Nuevo modelo: MISMA plantilla del editor, en blanco, con defaults (No publicado,
    Online Store ON, proveedor Container Houses, colección LÍNEA HOME). Al «Guardar y
    publicar» se crea el producto y se abre su editor."""
    if st.button("← Volver al catálogo", key="sw_new_back"):
        st.session_state.pop("sw_new", None)
        _clear_editor_state()
        st.rerun()

    st.markdown(f'<div class="sw-sec">{_ic("house", "#0f172a", 18, 0)}Nuevo modelo</div>',
                unsafe_allow_html=True)
    st.caption("Completa la plantilla y presiona «Guardar y publicar». Por defecto queda "
               "No publicado, en el canal Online Store, proveedor Container Houses y colección LÍNEA HOME.")

    # Canales y colecciones (cacheados en sesión, igual que el editor).
    _pubs = st.session_state.get("sw_pubs")
    if _pubs is None:
        _pubs, _puberr = _shop.listar_publicaciones()
        st.session_state["sw_pubs"] = _pubs or []
        st.session_state["sw_pubs_err"] = _puberr
        _pubs = _pubs or []
    _cols = st.session_state.get("sw_cols")
    if _cols is None:
        _cols, _ = _shop.listar_colecciones()
        _cols = _cols or []
        st.session_state["sw_cols"] = _cols

    # Defaults: Online Store ON + colección LÍNEA HOME.
    _os_gid = next((p.get("id") for p in _pubs
                    if "online store" in str(p.get("name") or "").lower()), None)
    _prod_pubs_set = {_os_gid} if _os_gid else set()

    def _norm(s):
        return " ".join(str(s or "").upper().replace("Í", "I").split())
    _lh_id = next((str(c.get("id")) for c in _cols if "LINEA HOME" in _norm(c.get("title"))), None)
    _cur_cols = [_lh_id] if _lh_id else []

    # Características (metacampos): plantilla completa en BLANCO.
    _mf_editable = []
    for d in _plantilla_metafields():
        if _mf_kind(d.get("type")) == "readonly":
            continue
        _mf_editable.append({"id": None, "namespace": d.get("namespace"), "key": d.get("key"),
                             "type": d.get("type"), "value": "", "name": d.get("name") or _mf_label(d)})

    # Producto VACÍO con los defaults (No publicado + proveedor Container Houses).
    _p = {"id": None, "title": "", "body_html": "", "status": "unlisted",
          "product_type": "", "vendor": "Container Houses", "images": [],
          "variants": [{"id": None, "title": "Default Title", "price": "", "compare_at_price": ""}]}

    # Puente de guardado (mismo input oculto sw_savecmd). El "guardado completo" CREA.
    if st.session_state.pop("_sw_reset_savecmd", False):
        st.session_state["sw_savecmd"] = ""
    _sc = st.text_input("savecmd", key="sw_savecmd", label_visibility="collapsed")
    if _sc and "|" in _sc:
        _sbody, _sts = _sc.rsplit("|", 1)
        if _sts != st.session_state.get("sw_savecmd_ts"):
            st.session_state["sw_savecmd_ts"] = _sts
            st.session_state["_sw_reset_savecmd"] = True
            import json as _json
            try:
                _data = _json.loads(_sbody)
            except Exception:
                _data = None
            # Las URLs de video ya se agregan como tile (van en el payload), así que aquí
            # solo procesamos el guardado completo → crear el modelo.
            if _data is not None and _data.get("op") not in ("upload", "video_url"):
                _crear_modelo(_data)

    _form_html, _form_h = _build_editor_form(_p, _pubs, _prod_pubs_set, _cols, _cur_cols,
                                             metafields=_mf_editable, videos=[])
    components.html(_form_html, height=int(_form_h), scrolling=False)
    components.html(_SW_FLOAT_JS + f"<!--{_uuid.uuid4().hex}-->", height=0)


def _crear_modelo(data: dict):
    """Crea un modelo NUEVO desde la plantilla del editor: crea el producto base y luego
    aplica TODO (estado real, canales, colecciones, características, fotos/videos) reusando
    _guardar_todo. Deja «No publicado» aplicando el estado al final. Abre el nuevo editor."""
    _title = (data.get("title") or "").strip()
    if not _title:
        st.session_state["sw_toast"] = "Ponle un nombre al modelo antes de crearlo."
        st.rerun()
        return
    # Precio de la única variante (si lo pusieron).
    _vs = data.get("variants") or []
    try:
        _price = int((_vs[0] or {}).get("price") or 0) if _vs else 0
    except Exception:
        _price = 0
    try:
        _cmp = int((_vs[0] or {}).get("compare_at") or 0) if _vs else 0
    except Exception:
        _cmp = 0
    _want_status = (data.get("status") or "unlisted")
    # "unlisted" no es un estado válido al CREAR (solo active/draft/archived); se crea
    # activo (para poder publicarlo en el canal) y se pasa a No publicado al final.
    _create_status = "active" if _want_status == "unlisted" else _want_status
    _campos = {
        "title": _title,
        "body_html": data.get("body_html") or "",
        "status": _create_status,
        "product_type": (data.get("product_type") or "").strip(),
        "vendor": (data.get("vendor") or "").strip(),
        "variants": [{"price": str(_price), "compare_at_price": (str(_cmp) if _cmp > 0 else None)}],
    }
    with st.spinner("Creando el modelo en Shopify…"):
        _prod, _err = _shop.crear_producto(_campos)
    if _err or not _prod:
        st.session_state["sw_toast"] = _err or "No se pudo crear el modelo."
        st.rerun()
        return
    _newid = _prod.get("id")
    # Aplicar el resto con _guardar_todo (canales, colecciones, metacampos, fotos/videos).
    # Se quitan las variantes (el precio ya se fijó al crear) y se deja el estado de
    # creación; el estado final (No publicado) se aplica DESPUÉS de publicar el canal.
    _data2 = dict(data)
    _data2["variants"] = []
    _data2["status"] = _create_status
    with st.spinner("Publicando y aplicando la configuración…"):
        _errs = _guardar_todo(_newid, _data2)
        if _want_status != _create_status:
            _ok, _e = _shop.actualizar_producto(_newid, {"status": _want_status})
            if not _ok:
                _errs.append(_e)
    # Abrir el editor del nuevo modelo.
    st.session_state.pop("sw_new", None)
    _clear_editor_state()
    _cargar_productos.clear()
    st.session_state["sw_edit_id"] = str(_newid)
    if _errs:
        st.session_state["sw_toast"] = "Modelo creado con avisos: " + " · ".join(str(x) for x in _errs[:3])
    else:
        st.session_state["sw_toast"] = "Modelo creado y publicado."
        st.session_state["sw_saved_ok"] = True
    st.rerun()


# JS del modo "Ordenar web": arrastrar las cards (desde la manija) reordena la grilla en
# el doc PADRE; el botón "Guardar orden" (#sw-ord-save) manda el orden por el puente
# sw_ordcmd. draggable solo se habilita desde la manija (como en la galería del editor).
_SW_REORDER_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var grid=D.getElementById('sw-reord-grid'); if(!grid) return;
  var saveBtn=D.getElementById('sw-ord-save');
  function order(){ return [].slice.call(grid.querySelectorAll('[data-pid]')).map(function(c){return c.getAttribute('data-pid');}); }
  var initial=order().join(',');
  function dirty(){ return order().join(',')!==initial; }
  function refreshBtn(){ if(saveBtn){ var dd=dirty(); saveBtn.disabled=!dd; saveBtn.classList.toggle('on', dd); } }
  grid.addEventListener('mousedown',function(e){ var h=e.target.closest?e.target.closest('.sw-ord-grip'):null; if(!h) return; var c=h.closest('[data-pid]'); if(c) c.setAttribute('draggable','true'); });
  D.addEventListener('mouseup',function(){ [].slice.call(grid.querySelectorAll('[data-pid][draggable="true"]')).forEach(function(c){c.setAttribute('draggable','false');}); });
  var dragEl=null;
  grid.addEventListener('dragstart',function(e){ var c=e.target.closest('[data-pid]'); if(!c) return; dragEl=c; e.dataTransfer.effectAllowed='move'; setTimeout(function(){c.classList.add('sw-dragging');},0); });
  grid.addEventListener('dragend',function(){ if(dragEl)dragEl.classList.remove('sw-dragging'); dragEl=null; refreshBtn(); });
  grid.addEventListener('dragover',function(e){ e.preventDefault(); if(!dragEl) return; var c=e.target.closest('[data-pid]'); if(!c||c===dragEl) return; var r=c.getBoundingClientRect(); var before=(e.clientY<r.top+r.height/2)||(Math.abs(e.clientY-(r.top+r.height/2))<r.height/2 && e.clientX<r.left+r.width/2); grid.insertBefore(dragEl, before?c:c.nextSibling); });
  function fire(payload){ var inp=D.querySelector('.st-key-sw_ordcmd input'); if(!inp) return; try{ var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set; inp.focus({preventScroll:true}); setter.call(inp, payload+'|'+Date.now()); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true})); inp.dispatchEvent(new KeyboardEvent('keypress',{key:'Enter',keyCode:13,which:13,bubbles:true})); inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true})); inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true})); inp.dispatchEvent(new FocusEvent('blur',{bubbles:true})); inp.dispatchEvent(new FocusEvent('focusout',{bubbles:true})); inp.blur(); }catch(e){} }
  if(saveBtn){ saveBtn.textContent='Guardar orden'; }   // en cada montaje/rerun vuelve al estado normal
  if(saveBtn && W._swOrdSaveH){ saveBtn.removeEventListener('click', W._swOrdSaveH); }
  if(saveBtn){ W._swOrdSaveH=function(){ if(saveBtn.disabled) return; saveBtn.textContent='Guardando…'; saveBtn.disabled=true; saveBtn.classList.remove('on'); fire(order().join(',')); }; saveBtn.addEventListener('click', W._swOrdSaveH); }
  refreshBtn();
})();
</script>"""


def _render_reordenar():
    """Modo 'Ordenar web': elige una colección MANUAL y arrastra sus productos (desde la
    manija) para fijar el orden en que se ven en su página web (collectionReorderProducts)."""
    st.markdown(f'<div class="sw-sec">{_ic("box", "#0f172a", 17, 0)}Ordenar productos en la web</div>',
                unsafe_allow_html=True)
    st.caption("Elige una colección y arrastra las tarjetas desde la manija para definir el orden en que "
               "se ven en su página web. Al guardar, la colección queda en orden Manual y el nuevo orden "
               "se aplica en Shopify (puede tardar unos segundos en reflejarse).")

    _cols = st.session_state.get("sw_cols")
    if _cols is None:
        _cols, _ = _shop.listar_colecciones()
        _cols = _cols or []
        st.session_state["sw_cols"] = _cols
    if not _cols:
        st.info("No hay colecciones manuales en la tienda para ordenar.")
        return
    _opts = {(c.get("title") or "(sin título)"): str(c.get("id")) for c in _cols}
    _sel = st.selectbox("Colección", list(_opts.keys()), key="sw_reord_col")
    _cid = _opts.get(_sel)
    if not _cid:
        return

    with st.spinner("Cargando productos de la colección…"):
        _prods, _so, _err = _shop.productos_de_coleccion(_cid)
    if _err:
        st.warning(_err)
        return

    # Resultado del último guardado (persistente, se muestra una vez para poder ver el
    # error real de Shopify si algo falla).
    _res = st.session_state.pop("sw_ord_result", None)
    if _res:
        if _res[0] == "ok":
            st.success("Orden guardado en Shopify. Puede tardar unos segundos en reflejarse en la web.",
                       icon=":material/check_circle:")
        else:
            st.error(f"Shopify no aceptó el nuevo orden: {_res[1]}", icon=":material/error:")

    # Puente de guardado del orden (input oculto sw_ordcmd; se auto-limpia tras procesar).
    if st.session_state.pop("_sw_reset_ordcmd", False):
        st.session_state["sw_ordcmd"] = ""
    _oc = st.text_input("ordcmd", key="sw_ordcmd", label_visibility="collapsed")
    if _oc and "|" in _oc:
        _obody, _ots = _oc.rsplit("|", 1)
        if _ots != st.session_state.get("sw_ordcmd_ts"):
            st.session_state["sw_ordcmd_ts"] = _ots
            st.session_state["_sw_reset_ordcmd"] = True
            _gids = [g for g in _obody.split(",") if g]
            if len(_gids) >= 2:
                _errs = []
                with st.spinner("Guardando el orden en Shopify…"):
                    # La colección DEBE estar en orden Manual para poder fijar el orden. Lo
                    # forzamos SIEMPRE (es idempotente): si ya está Manual, Shopify no cambia
                    # nada; si estaba en automático (más vendidos, etc.), pasa a Manual. Sin
                    # esto, collectionReorderProducts falla con "can only be reordered if
                    # the collection sort order is 'Manually'".
                    _okm, _em = _shop.set_coleccion_manual(_cid)
                    if not _okm:
                        _errs.append(_em)
                    _ok, _e = _shop.reordenar_productos_coleccion(_cid, _gids)
                    if not _ok:
                        _errs.append(_e)
                if not _errs:
                    # Orden optimista: reflejarlo ya (el job async puede tardar al refetch).
                    st.session_state["sw_ord_saved"] = {"cid": _cid, "gids": _gids}
                    st.session_state["sw_ord_result"] = ("ok", None)
                else:
                    st.session_state["sw_ord_result"] = ("err", " · ".join(str(x) for x in _errs if x))
                st.rerun()

    if not _prods:
        st.info("Esta colección no tiene productos.")
        return

    # Reflejar el último orden guardado (optimista) mientras Shopify procesa el job.
    _saved = st.session_state.get("sw_ord_saved")
    if _saved and _saved.get("cid") == _cid:
        _pos = {g: i for i, g in enumerate(_saved.get("gids") or [])}
        _prods = sorted(_prods, key=lambda pr: _pos.get(pr.get("gid"), 10 ** 6))

    st.markdown(f'<div class="sw-ord-hint">{len(_prods)} producto(s) en «{_he(_sel)}» · '
                'arrastra desde la manija <span>&#8942;&#8942;</span> para reordenar</div>',
                unsafe_allow_html=True)
    _grip = ('<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/>'
             '<circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/>'
             '<circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>')
    _cards = ""
    for pr in _prods:
        _img = _he(pr.get("image") or "")
        _thumb = (f'<img src="{_img}" alt="" loading="lazy">' if _img
                  else '<span class="sw-noimg">Sin foto</span>')
        _bg, _fg, _blbl = _ESTADOS.get(_estado_efectivo({"status": pr.get("status")}), _ESTADOS["active"])
        _cards += (
            f'<div class="sw-card sw-ord-card" data-pid="{_he(pr.get("gid"))}">'
            f'<div class="sw-thumb">{_thumb}'
            f'<span class="sw-badge" style="background:{_bg};color:{_fg};">{_blbl}</span>'
            f'<span class="sw-ord-grip" title="Arrastra para ordenar">{_grip}</span></div>'
            f'<div class="sw-body"><div class="sw-title">{_he(pr.get("title"))}</div></div></div>')
    st.markdown(f'<div id="sw-reord-grid" class="sw-grid">{_cards}</div>', unsafe_allow_html=True)
    st.markdown('<div class="sw-ord-savewrap"><button id="sw-ord-save" class="sw-ord-savebtn" disabled>'
                'Guardar orden</button></div>', unsafe_allow_html=True)
    # Nonce (colección + ts del último guardado): cambia el contenido del componente para
    # forzar que el JS se re-ejecute tras guardar y resetee el botón (si no, queda pegado).
    _nonce = f"{_cid}-{st.session_state.get('sw_ordcmd_ts', '')}"
    components.html(_SW_REORDER_JS + f"<!--n:{_he(_nonce)}-->", height=0)


# Botón FLOTANTE "Guardar y publicar": se inyecta en el <body> del padre (fijo, centrado
# abajo, con sombra). Deshabilitado sin cambios; se habilita cuando el formulario marca
# window.parent._swDirty=true. Al click llama window.parent._swSave() (que arma y envía el
# formulario por el puente). Un intervalo en el contexto del PADRE lo sincroniza y lo quita
# al salir del editor (cuando ya no existe el input oculto sw_savecmd). Solo vive en esta
# pestaña/editor.
_SW_FLOAT_JS = r"""<script>
(function(){
  var P=window.parent, PD=P&&P.document; if(!PD) return;
  var old=PD.getElementById('sw-float-save'); if(old) old.remove();
  var b=PD.createElement('button'); b.id='sw-float-save'; b.type='button';
  b.textContent='Guardar y publicar';
  b.setAttribute('style','position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:99998;'
    +'font-family:Montserrat,Segoe UI,sans-serif;font-weight:800;font-size:0.8rem;text-transform:uppercase;'
    +'letter-spacing:.05em;padding:14px 34px;border:none;border-radius:13px;color:#fff;cursor:default;'
    +'background:#aab2c5;box-shadow:0 6px 16px rgba(15,23,42,.18);transition:background .18s,box-shadow .18s,transform .1s;');
  PD.body.appendChild(b);
  b.onmousedown=function(){ if(!b.disabled) b.style.transform='translateX(-50%) translateY(1px)'; };
  b.onmouseup=function(){ b.style.transform='translateX(-50%)'; };
  b.onclick=function(){ if(b.disabled) return; try{ P._swSave(); }catch(e){} b.textContent='Guardando…'; b.disabled=true;
    b.style.setProperty('background','#334155','important'); };
  var s=PD.createElement('script');
  s.textContent="(function(){var W=window;if(W._swFloatInt)clearInterval(W._swFloatInt);W._swFloatMiss=0;"
    +"var GRAD='linear-gradient(135deg,#5b7cfa,#2563eb)';"
    +"W._swFloatInt=setInterval(function(){try{var b=document.getElementById('sw-float-save');if(!b)return;"
    // Sólo quitar el botón tras VARIAS ausencias seguidas del input (así un rerun que tarda en
    // remontar sw_savecmd no lo borra). Si el input reaparece, se resetea el contador.
    +"if(!document.querySelector('.st-key-sw_savecmd')){ if(++W._swFloatMiss>=5){b.remove();clearInterval(W._swFloatInt);} return;} W._swFloatMiss=0;"
    +"if(b.textContent.indexOf('Guardando')===0)return;var d=!!W._swDirty;b.disabled=!d;"
    +"b.style.setProperty('background',d?GRAD:'#aab2c5','important');"
    +"b.style.boxShadow=d?'0 12px 30px rgba(37,99,235,.42)':'0 6px 16px rgba(15,23,42,.18)';"
    +"b.style.cursor=d?'pointer':'default';"
    +"}catch(e){}},300);})();";
  PD.body.appendChild(s); s.remove();
})();
</script>"""


_SW_REELS_CSS = """<style>
.sw-reels-meta{font-size:0.76rem;color:#64748b;margin:2px 0 14px;}
.sw-reels-meta code{background:#eef2ff;color:#4f46e5;padding:1px 6px;border-radius:5px;font-size:0.72rem;}
.sw-reels-badge{display:inline-block;padding:1px 8px;border-radius:999px;font-size:0.66rem;
  font-weight:700;text-transform:uppercase;letter-spacing:0.04em;vertical-align:middle;}
.sw-reels-badge.is-live{background:#dcfce7;color:#15803d;}
.sw-reels-badge.is-draft{background:#fef3c7;color:#b45309;}
.sw-reels-h{font-family:Montserrat,sans-serif;font-weight:800;font-size:0.82rem;letter-spacing:.04em;
  text-transform:uppercase;color:#0f172a;margin:16px 0 10px;display:flex;align-items:center;gap:8px;}
.sw-reels-h::before{content:'';width:4px;height:14px;border-radius:3px;background:linear-gradient(180deg,#5b7cfa,#4f46e5);}
.sw-reel-av{width:74px;height:74px;border-radius:50%;background:#0f172a;background-size:cover;background-position:center;margin:0 auto;border:2px solid #e2e8f0;}
.sw-reel-av--empty{display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:0.6rem;font-weight:700;}
.sw-reel-avn{text-align:center;font-size:0.76rem;font-weight:700;color:#0f172a;margin-top:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sw-reel-avr{text-align:center;font-size:0.66rem;color:#94a3b8;}
.sw-reel-card{position:relative;aspect-ratio:9/16;border-radius:12px;overflow:hidden;background:#0f172a;border:1px solid #e8ebf3;}
.sw-reel-card img{width:100%;height:100%;object-fit:cover;display:block;}
.sw-reel-ph{width:100%;height:100%;display:flex;align-items:center;justify-content:center;color:#cbd5e1;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.72rem;letter-spacing:.06em;}
.sw-reel-play{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:40px;height:40px;border-radius:50%;background:rgba(10,14,20,.5);border:1.5px solid rgba(255,255,255,.85);display:flex;align-items:center;justify-content:center;}
.sw-reel-play svg{width:15px;height:15px;margin-left:2px;}
.sw-reel-tag{position:absolute;left:6px;bottom:6px;z-index:2;background:rgba(8,10,14,.85);color:#fff;font-family:Montserrat,sans-serif;font-weight:700;font-size:0.62rem;letter-spacing:.03em;padding:3px 8px;border-radius:6px;max-width:calc(100% - 12px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.sw-reel-cap{font-size:0.7rem;color:#64748b;margin:5px 2px 0;line-height:1.3;}
</style>"""


def _reels_clear_state():
    for _k in ("sw_reels", "sw_reels_err", "sw_reels_vids", "sw_reels_work",
               "sw_reels_workkey", "sw_reels_base", "sw_reels_files", "sw_reels_prods",
               "sw_reel_edit_k"):
        st.session_state.pop(_k, None)


def _reels_norm(_work):
    """Firma comparable (para detectar cambios) de la lista de reels."""
    return [(str(r.get("video") or ""), str(r.get("caption") or ""),
             str(r.get("linked_product") or ""), str(r.get("advisor_name") or "")) for r in _work]


def _reel_video_filename(_v):
    """Nombre de archivo legible de un valor de campo 'video'."""
    _s = str(_v or "")
    if "/videos/" in _s:
        _s = _s.split("/videos/", 1)[-1]
    elif "/" in _s:
        _s = _s.rsplit("/", 1)[-1]
    try:
        from urllib.parse import unquote
        return unquote(_s)
    except Exception:
        return _s


def _reel_prod_select_html(prod_opts, selected=""):
    _sel = str(selected or "")
    _out = ""
    for _val, _label in prod_opts:
        _s = " selected" if str(_val) == _sel else ""
        _out += f'<option value="{_he(_val)}"{_s}>{_he(_label)}</option>'
    return _out


def _reel_media_html(r):
    _src, _pv = _he(r.get("_src") or ""), _he(r.get("_pv") or "")
    if _src:
        _pt = (f'poster="{_pv}"' if _pv else "")
        return f'<video class="rlc-vid" preload="none" playsinline controls {_pt} src="{_src}"></video>'
    if _pv:
        return f'<div class="rlc-ph" style="background:url(\'{_pv}\') center/cover;"></div>'
    return '<div class="rlc-ph">SIN VIDEO<small>súbelo abajo</small></div>'


def _reel_card_html(r, prod_opts):
    """Una tarjeta de reel del editor HTML (subida de video como en el editor de productos)."""
    _x = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
          'stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>')
    _grip = ('<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.7"/>'
             '<circle cx="15" cy="6" r="1.7"/><circle cx="9" cy="12" r="1.7"/><circle cx="15" cy="12" r="1.7"/>'
             '<circle cx="9" cy="18" r="1.7"/><circle cx="15" cy="18" r="1.7"/></svg>')
    _cam = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="m23 7-7 5 7 5V7z"/>'
            '<rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>')
    return (
        f'<div class="rlc" draggable="false" data-id="{_he(r.get("id") or "")}" '
        f'data-video="{_he(r.get("video") or "")}" data-newkey="">'
        f'<div class="rlc-media"><div class="rlc-vidwrap">{_reel_media_html(r)}</div>'
        f'<button type="button" class="rlc-del" title="Eliminar reel">{_x}</button>'
        f'<span class="rlc-grip" title="Arrastrar para ordenar">{_grip}</span></div>'
        '<div class="rlc-body">'
        f'<button type="button" class="rlc-change">{_cam}Cambiar video</button>'
        '<label class="rlc-lbl">Producto vinculado</label>'
        f'<select class="rlc-prod ed-in">{_reel_prod_select_html(prod_opts, r.get("linked_product"))}</select>'
        '<label class="rlc-lbl">Descripción</label>'
        f'<input class="rlc-cap ed-in" type="text" value="{_he(r.get("caption") or "")}" placeholder="Descripción del reel">'
        '<label class="rlc-lbl">Ejecutivo (asesor)</label>'
        f'<input class="rlc-adv ed-in" type="text" list="rl-advs" value="{_he(r.get("advisor_name") or "")}" placeholder="Ej: Andrea Osorio">'
        '</div></div>')


def _build_reels_form(work, prod_opts, adv_names):
    """Editor HTML de los reels (diseño como el editor de productos): tarjetas con video
    reproducible, eliminar, arrastrar para ordenar, subir/cambiar video DESDE EL PC (igual que
    las fotos/videos de productos) y producto vinculado. El guardado va por el puente
    sw_reelscmd; los videos nuevos van en base64 (como en productos). Devuelve (html, alto)."""
    _add = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
            'stroke-linecap="round"><path d="M12 5v14"/><path d="M5 12h14"/></svg>')
    _cards = "".join(_reel_card_html(r, prod_opts) for r in work)
    if not _cards:
        _cards = ('<div class="rl-empty">Aún no hay reels. Pulsa «Agregar reel» para subir el primero '
                  '(video vertical 9:16).</div>')
    _tpl = _reel_card_html({"id": None, "video": "", "caption": "", "advisor_name": "",
                            "linked_product": "", "_pv": "", "_src": ""}, prod_opts)
    _advs = "".join(f'<option value="{_he(n)}">' for n in sorted({a for a in adv_names if a}))
    _html = r"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800&family=Plus+Jakarta+Sans:wght@500;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box;} html,body{margin:0;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;background:transparent;color:#0f172a;}
#rl-root{padding-bottom:82px;}
.rl-top{display:flex;justify-content:flex-start;align-items:center;gap:12px;margin:0 0 16px;}
.rl-add{display:inline-flex;align-items:center;gap:8px;background:#0f172a;color:#fff;border:none;border-radius:12px;
  padding:12px 22px;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.76rem;text-transform:uppercase;
  letter-spacing:.04em;cursor:pointer;transition:background .15s;}
.rl-add:hover{background:#1e293b;} .rl-add svg{width:16px;height:16px;}
.rl-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));gap:16px;align-items:start;}
.rlc{background:#fff;border:1px solid #e8ebf3;border-radius:14px;overflow:hidden;box-shadow:0 2px 10px rgba(15,23,42,.05);
  display:flex;flex-direction:column;}
.rlc.rl-dragging{opacity:.45;}
.rlc-media{position:relative;aspect-ratio:9/16;background:#0f172a;overflow:hidden;}
.rlc-vidwrap{width:100%;height:100%;}
.rlc-vidwrap video{width:100%;height:100%;object-fit:cover;display:block;background:#0f172a;}
.rlc-ph{width:100%;height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#64748b;
  font-family:Montserrat,sans-serif;font-weight:800;font-size:.72rem;letter-spacing:.06em;gap:5px;}
.rlc-ph small{font-family:'Plus Jakarta Sans';font-weight:600;font-size:.62rem;letter-spacing:0;color:#94a3b8;text-transform:none;}
.rlc-del,.rlc-grip{position:absolute;top:8px;width:31px;height:31px;border-radius:9px;display:flex;align-items:center;
  justify-content:center;background:rgba(15,23,42,.60);color:#fff;cursor:pointer;border:none;z-index:3;padding:0;}
.rlc-del{left:8px;} .rlc-grip{right:8px;cursor:grab;}
.rlc-del:hover{background:#dc2626;} .rlc-del svg,.rlc-grip svg{width:16px;height:16px;}
.rlc-body{padding:12px 13px 15px;display:flex;flex-direction:column;}
.rlc-change{margin-bottom:6px;background:#eef2ff;color:#2563eb;border:1px solid #dbe3ff;border-radius:9px;padding:8px;
  font-family:'Plus Jakarta Sans';font-weight:700;font-size:.76rem;cursor:pointer;display:flex;align-items:center;
  justify-content:center;gap:6px;transition:background .15s;}
.rlc-change:hover{background:#dbe3ff;} .rlc-change svg{width:15px;height:15px;}
.rlc-lbl{font-size:.66rem;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:.03em;margin:9px 0 4px;}
.ed-in{width:100%;border:1.5px solid #e2e8f0;border-radius:9px;padding:9px 10px;font-size:.84rem;font-family:inherit;
  background:#f8fafc;outline:none;color:#0f172a;}
.ed-in:focus{border-color:#5b7cfa;background:#fff;} select.ed-in{cursor:pointer;}
.rl-empty{grid-column:1/-1;color:#94a3b8;font-size:.88rem;padding:34px;text-align:center;border:1.5px dashed #cbd5e1;border-radius:14px;}
.rl-msg{display:none;background:#fff1f2;border:1px solid #fca5a5;color:#b91c1c;border-radius:10px;padding:10px 13px;
  font-size:.8rem;line-height:1.4;margin-bottom:12px;}
</style></head><body><div id="rl-root">
<div class="rl-top"><button type="button" id="rl-addbtn" class="rl-add">__ADD__ Agregar reel</button></div>
<div id="rl-msg" class="rl-msg"></div>
<div class="rl-grid" id="rl-grid">__CARDS__</div>
<datalist id="rl-advs">__ADVS__</datalist>
<template id="rl-tpl">__TPL__</template>
<input type="file" id="rl-file" accept="video/*" style="display:none">
</div>
<script>
(function(){
var doc=document, P=window.parent;
var grid=doc.getElementById('rl-grid'), fileIn=doc.getElementById('rl-file'),
    addbtn=doc.getElementById('rl-addbtn'), tpl=doc.getElementById('rl-tpl'), msg=doc.getElementById('rl-msg');
var newFiles={}, upMode={op:'',card:null};
function uid(){ return 'n'+Math.random().toString(36).slice(2,10); }
function fileB64(f){ return new Promise(function(res){ var r=new FileReader();
  r.onload=function(){ try{ res((''+r.result).split(',')[1]||''); }catch(e){ res(''); } };
  r.onerror=function(){ res(''); }; r.readAsDataURL(f); }); }
function ensureEmpty(){ var e=grid.querySelector('.rl-empty'); if(e && grid.querySelectorAll('.rlc').length) e.remove();
  if(!grid.querySelectorAll('.rlc').length && !grid.querySelector('.rl-empty')){ var d=doc.createElement('div'); d.className='rl-empty'; d.textContent='Aún no hay reels. Pulsa «Agregar reel» para subir el primero.'; grid.appendChild(d); } }
function setCardVideo(card, url){ var w=card.querySelector('.rlc-vidwrap');
  w.innerHTML='<video preload="metadata" playsinline controls src="'+(url+'').replace(/"/g,'&quot;')+'"></video>'; }
function collect(){ var out=[]; [].slice.call(grid.querySelectorAll('.rlc')).forEach(function(c){
  out.push({id:c.getAttribute('data-id')||'', video:c.getAttribute('data-video')||'', newkey:c.getAttribute('data-newkey')||'',
    product:(c.querySelector('.rlc-prod')||{}).value||'', caption:(c.querySelector('.rlc-cap')||{}).value||'',
    advisor:(c.querySelector('.rlc-adv')||{}).value||''}); }); return out; }
var _initial=JSON.stringify(collect());
function dirty(){ return JSON.stringify(collect())!==_initial || Object.keys(newFiles).length>0; }
function setDirty(){ try{ P._swReelsDirty=dirty(); }catch(e){} }
function showMsg(t){ if(msg){ msg.textContent=t; msg.style.display='block'; } }
function hideMsg(){ if(msg) msg.style.display='none'; }
/* Subir/cambiar video (archivo local, como en productos) */
addbtn.addEventListener('click', function(){ upMode={op:'add',card:null}; fileIn.value=''; fileIn.click(); });
grid.addEventListener('click', function(e){
  var ch=e.target.closest?e.target.closest('.rlc-change'):null;
  if(ch){ upMode={op:'change',card:ch.closest('.rlc')}; fileIn.value=''; fileIn.click(); return; }
  var dl=e.target.closest?e.target.closest('.rlc-del'):null;
  if(dl){ var c=dl.closest('.rlc'); var nk=c.getAttribute('data-newkey'); if(nk&&newFiles[nk])delete newFiles[nk]; c.remove(); ensureEmpty(); setDirty(); }
});
fileIn.addEventListener('change', function(){
  var f=this.files&&this.files[0]; if(!f) return;
  if((f.type||'').indexOf('video')!==0){ showMsg('El archivo debe ser un video.'); return; }
  var key=uid(); newFiles[key]=f; var url=URL.createObjectURL(f);
  if(upMode.op==='change' && upMode.card){ var c=upMode.card; var old=c.getAttribute('data-newkey'); if(old&&newFiles[old]&&old!==key)delete newFiles[old];
    c.setAttribute('data-newkey',key); setCardVideo(c,url); }
  else { var e=grid.querySelector('.rl-empty'); if(e)e.remove();
    var node=tpl.content.firstElementChild.cloneNode(true); node.setAttribute('data-id',''); node.setAttribute('data-video','');
    node.setAttribute('data-newkey',key); grid.appendChild(node); setCardVideo(node,url); node.scrollIntoView({block:'nearest'}); }
  this.value=''; hideMsg(); setDirty();
});
/* Reordenar por arrastre desde la manija (grip) */
var dragEl=null;
grid.addEventListener('mousedown', function(e){ var g=e.target.closest?e.target.closest('.rlc-grip'):null; if(!g)return; var c=g.closest('.rlc'); if(c)c.setAttribute('draggable','true'); });
grid.addEventListener('mouseup', function(){ [].slice.call(grid.querySelectorAll('.rlc')).forEach(function(c){ c.setAttribute('draggable','false'); }); });
grid.addEventListener('dragstart', function(e){ var c=e.target.closest?e.target.closest('.rlc'):null; if(!c){return;} dragEl=c; e.dataTransfer.effectAllowed='move'; setTimeout(function(){ c.classList.add('rl-dragging'); },0); });
grid.addEventListener('dragend', function(){ if(dragEl){ dragEl.classList.remove('rl-dragging'); dragEl.setAttribute('draggable','false'); } dragEl=null; setDirty(); });
grid.addEventListener('dragover', function(e){ e.preventDefault(); if(!dragEl)return; var t=e.target.closest?e.target.closest('.rlc'):null; if(!t||t===dragEl)return;
  var r=t.getBoundingClientRect(); var before=(e.clientY < r.top + r.height/2); grid.insertBefore(dragEl, before?t:t.nextSibling); });
grid.addEventListener('input', setDirty);
grid.addEventListener('change', setDirty);
/* Guardado: expone _swReelsSave al padre (lo llama el botón flotante) */
function fire(payload){ try{ var W=P, D=W.document; var inp=D.querySelector('.st-key-sw_reelscmd input'); if(!inp)return;
  var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set; inp.focus({preventScroll:true});
  setter.call(inp, payload+'|'+Date.now()); inp.dispatchEvent(new Event('input',{bubbles:true})); inp.dispatchEvent(new Event('change',{bubbles:true}));
  inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true})); inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true}));
  inp.dispatchEvent(new FocusEvent('blur',{bubbles:true})); inp.dispatchEvent(new FocusEvent('focusout',{bubbles:true})); inp.blur(); }catch(e){} }
function resetBtn(){ var b=P.document.getElementById('sw-reels-float'); if(b){ b.textContent='Guardar reels'; b.disabled=false; } }
try{ P._swReelsDirty=false;
  P._swReelsSave=async function(){ try{
    var cards=collect(); var missing=cards.filter(function(c){ return !c.video && !c.newkey; }).length;
    if(missing){ showMsg('Hay '+missing+' reel(s) sin video. Súbeles un video o elimínalos.'); resetBtn(); return; }
    var keys=Object.keys(newFiles), tot=0, i;
    for(i=0;i<keys.length;i++){ tot+=newFiles[keys[i]].size; }
    if(tot>100*1024*1024){ showMsg('Los videos nuevos suman '+(tot/1048576).toFixed(0)+' MB. Máximo 100 MB por guardado — sube menos a la vez o comprímelos.'); resetBtn(); return; }
    var nv=[], fb=P.document.getElementById('sw-reels-float');
    for(i=0;i<keys.length;i++){ var k=keys[i]; if(fb) fb.textContent='Subiendo '+(i+1)+'/'+keys.length+'…';
      var bb=await fileB64(newFiles[k]); if(bb) nv.push({key:k, name:newFiles[k].name, mime:(newFiles[k].type||'video/mp4'), b64:bb}); }
    if(fb) fb.textContent='Guardando…';
    fire(JSON.stringify({reels:cards, new_videos:nv}));
  }catch(e){ resetBtn(); } };
}catch(e){}
/* Auto-ajuste del alto del iframe */
function swResize(){ try{ var el=doc.getElementById('rl-root'); if(!el)return; var h=Math.ceil(el.offsetHeight)+6; var fe=window.frameElement; if(!fe)return;
  if(Math.abs((parseInt(fe.style.height,10)||0)-h)>3){ fe.style.setProperty('height', h+'px','important'); } }catch(e){} }
setInterval(swResize,250); [0,200,500].forEach(function(t){ setTimeout(swResize,t); });
})();
</script></body></html>"""
    _html = (_html.replace("__ADD__", _add).replace("__CARDS__", _cards)
             .replace("__TPL__", _tpl).replace("__ADVS__", _advs))
    _n = max(1, len(work))
    _rows = (_n + 2) // 3
    return _html, 120 + _rows * 620


_SW_REELS_FLOAT_JS = r"""<script>
(function(){
  var P=window.parent, PD=P&&P.document; if(!PD) return;
  var old=PD.getElementById('sw-reels-float'); if(old) old.remove();
  var b=PD.createElement('button'); b.id='sw-reels-float'; b.type='button'; b.textContent='Guardar reels';
  b.setAttribute('style','position:fixed;left:50%;transform:translateX(-50%);bottom:26px;z-index:99998;'
    +'font-family:Montserrat,Segoe UI,sans-serif;font-weight:800;font-size:0.8rem;text-transform:uppercase;'
    +'letter-spacing:.05em;padding:14px 34px;border:none;border-radius:13px;color:#fff;cursor:default;'
    +'background:#aab2c5;box-shadow:0 6px 16px rgba(15,23,42,.18);transition:background .18s,box-shadow .18s,transform .1s;');
  PD.body.appendChild(b);
  b.onmousedown=function(){ if(!b.disabled) b.style.transform='translateX(-50%) translateY(1px)'; };
  b.onmouseup=function(){ b.style.transform='translateX(-50%)'; };
  b.onclick=function(){ if(b.disabled) return; try{ P._swReelsSave(); }catch(e){} b.textContent='Guardando…'; b.disabled=true;
    b.style.setProperty('background','#334155','important'); };
  var s=PD.createElement('script');
  s.textContent="(function(){var W=window;if(W._swReelsInt)clearInterval(W._swReelsInt);W._swReelsMiss=0;"
    +"var GRAD='linear-gradient(135deg,#5b7cfa,#2563eb)';"
    +"W._swReelsInt=setInterval(function(){try{var b=document.getElementById('sw-reels-float');if(!b)return;"
    +"if(!document.querySelector('.st-key-sw_reelscmd')){ if(++W._swReelsMiss>=5){b.remove();clearInterval(W._swReelsInt);} return;} W._swReelsMiss=0;"
    +"if(b.textContent.indexOf('Guardando')===0)return;var d=!!W._swReelsDirty;b.disabled=!d;"
    +"b.style.setProperty('background',d?GRAD:'#aab2c5','important');"
    +"b.style.boxShadow=d?'0 12px 30px rgba(37,99,235,.42)':'0 6px 16px rgba(15,23,42,.18)';"
    +"b.style.cursor=d?'pointer':'default';"
    +"}catch(e){}},300);})();";
  PD.body.appendChild(s); s.remove();
})();
</script>"""


def _render_reels():
    """FASE 2: muestra y EDITA los reels de la sección de Shopify (bloques del tema) — video,
    ejecutivo (asesor), descripción y producto vinculado — más agregar, eliminar y reordenar.
    Escribe el asset del tema con respaldo automático y confirmación."""
    st.markdown(_SW_REELS_CSS, unsafe_allow_html=True)
    _h1, _h2 = st.columns([5, 1.3], vertical_alignment="bottom")
    with _h1:
        st.markdown(f'<div class="sw-sec">{_ic("video", "#0f172a", 17, 0)}Reels por asesor</div>',
                    unsafe_allow_html=True)
    with _h2:
        if st.button("Actualizar", icon=":material/refresh:", key="sw_reels_refresh",
                     use_container_width=True):
            _reels_clear_state()
            st.rerun()
    st.caption("Videos verticales de la sección «Reels por asesor» de tu web. Edita cada reel: "
               "qué ejecutivo, descripción, producto y video; o agrégalos, reordénalos y elimínalos.")

    if st.session_state.pop("sw_reels_saved", False):
        st.success("Reels guardados en el tema. Cuando publiques ese tema, pasan a producción.",
                   icon=":material/check_circle:")
    _rerrs = st.session_state.pop("sw_reels_errs", None)
    if _rerrs:
        st.warning("No se pudo guardar (tus cambios NO se aplicaron):\n\n"
                   + "\n\n".join(f"- {e}" for e in _rerrs), icon=":material/error:")

    _info = st.session_state.get("sw_reels")
    if _info is None:
        with st.spinner("Buscando los reels en tu tema de Shopify…"):
            _info, _rerr = _shop.leer_reels()
        st.session_state["sw_reels"] = _info or {}
        st.session_state["sw_reels_err"] = _rerr
    if not _info:
        st.warning(st.session_state.get("sw_reels_err")
                   or "No se encontró la sección de reels en el tema publicado.")
        return

    _advisors = _info.get("advisors", [])
    # Copia de trabajo (editable) — se reconstruye si cambió la sección/tema.
    _sig = f"{_info.get('theme_id')}|{_info.get('asset_key')}|{_info.get('section_id')}"
    if st.session_state.get("sw_reels_workkey") != _sig:
        _ids = ([r.get("video") for r in _info.get("reels", [])]
                + [a.get("video") for a in _advisors])
        with st.spinner("Cargando miniaturas de los videos…"):
            _vids, _ = _shop.resolver_videos(_ids)
        _vids = _vids or {}
        _work = []
        for _r in _info.get("reels", []):
            _rv = _vids.get(str(_r.get("video"))) or {}
            _work.append({"_k": _uuid.uuid4().hex[:8], "id": _r.get("id"),
                          "video": _r.get("video"), "caption": _r.get("caption") or "",
                          "linked_product": str(_r.get("linked_product") or ""),
                          "advisor_name": _r.get("advisor_name") or "",
                          "_pv": _rv.get("preview_url") or "", "_src": _rv.get("src") or ""})
        st.session_state["sw_reels_work"] = _work
        st.session_state["sw_reels_base"] = _reels_norm(_work)
        st.session_state["sw_reels_vids"] = _vids
        st.session_state["sw_reels_workkey"] = _sig
    _work = st.session_state["sw_reels_work"]
    _vids = st.session_state.get("sw_reels_vids") or {}

    _es_borrador = str(_info.get("theme_role") or "") != "main"
    if _es_borrador:
        st.info(f"Estos reels están en una **versión BORRADOR** de tu tema: "
                f"**{_info.get('theme_name') or '—'}** (no es la publicada). No se encontró la "
                f"sección en el tema publicado, así que se muestra y edita la del borrador. "
                f"Cuando publiques ese tema, estos cambios pasan a producción.",
                icon=":material/draft:")
    _rol_txt = "publicado" if not _es_borrador else "borrador"
    st.markdown(f'<div class="sw-reels-meta">Tema: <b>{_he(_info.get("theme_name"))}</b> '
                f'<span class="sw-reels-badge {"is-draft" if _es_borrador else "is-live"}">'
                f'{_rol_txt}</span> · sección <code>{_he(_info.get("section_type"))}</code> · '
                f'{len(_work)} reel(s) · {len(_advisors)} asesor(es)'
                + (f' · {_info.get("n_secciones")} secciones con reels' if (_info.get("n_secciones") or 0) > 1 else "")
                + '</div>', unsafe_allow_html=True)

    with st.expander("Diagnóstico técnico (claves de los bloques del tema)"):
        st.caption(f"Sección elegida: {_info.get('section_id')} · tipo bloque asesor: "
                   f"{_info.get('advisor_type')} · {_info.get('n_secciones')} sección(es) con reels en el tema. "
                   "Esto muestra las CLAVES reales de los bloques (para ajustar guardado si difieren).")
        st.json(_info.get("raw_blocks") or [])

    if _advisors:
        st.markdown('<div class="sw-reels-h">Asesores</div>', unsafe_allow_html=True)
        _nc = min(6, max(1, len(_advisors)))
        _acols = st.columns(_nc)
        for _i, _a in enumerate(_advisors):
            with _acols[_i % _nc]:
                _pv = (_vids.get(str(_a.get("video"))) or {}).get("preview_url", "")
                _av = (f'<div class="sw-reel-av" style="background-image:url(\'{_he(_pv)}\')"></div>'
                       if _pv else '<div class="sw-reel-av sw-reel-av--empty">Sin video</div>')
                st.markdown(_av + f'<div class="sw-reel-avn">{_he(_a.get("name") or "—")}</div>'
                            + (f'<div class="sw-reel-avr">{_he(_a.get("role"))}</div>'
                               if _a.get("role") else ""), unsafe_allow_html=True)

    # ── Editor HTML de reels (subir/cambiar video, eliminar, reordenar, asociar producto) ──
    _prods = st.session_state.get("sw_reels_prods")
    if _prods is None:
        _pl, _ = _shop.listar_productos(status="")
        _prods = _pl or []
        st.session_state["sw_reels_prods"] = _prods
    _prod_opts = [("", "(sin producto)")] + [(str(p.get("id")), (p.get("title") or f"#{p.get('id')}"))
                                             for p in _prods]
    _adv_names = ([a.get("name") for a in _advisors if a.get("name")]
                  + [r.get("advisor_name") for r in _work if r.get("advisor_name")])

    # Puente de guardado (input oculto sw_reelscmd; se auto-limpia tras procesar). Los videos
    # nuevos van en base64 dentro del payload, igual que las fotos/videos del editor de productos.
    st.markdown("<style>.st-key-sw_reelscmd{position:fixed!important;left:-9999px!important;"
                "width:1px!important;height:1px!important;opacity:0!important;}</style>",
                unsafe_allow_html=True)
    if st.session_state.pop("_sw_reset_reelscmd", False):
        st.session_state["sw_reelscmd"] = ""
    _rc = st.text_input("reelscmd", key="sw_reelscmd", label_visibility="collapsed")
    if _rc and "|" in _rc:
        _rbody, _rts = _rc.rsplit("|", 1)
        if _rts != st.session_state.get("sw_reelscmd_ts"):
            st.session_state["sw_reelscmd_ts"] = _rts
            st.session_state["_sw_reset_reelscmd"] = True
            import json as _json
            try:
                _data = _json.loads(_rbody)
            except Exception:
                _data = None
            if _data is not None:
                _errs, _refmap = [], {}
                _nv = _data.get("new_videos") or []
                _spin = (f"Subiendo {len(_nv)} video(s) y guardando los reels…" if _nv
                         else "Guardando los reels…")
                with st.spinner(_spin):
                    for _v in _nv:
                        try:
                            _vb = base64.b64decode(_v.get("b64") or "")
                        except Exception:
                            _vb = b""
                        if not _vb:
                            continue
                        _ref, _pv3, _src3, _e = _shop.subir_video_archivo(
                            _v.get("name") or "video.mp4", _v.get("mime") or "video/mp4", _vb)
                        if _e or not _ref:
                            _errs.append(_e or "No se pudo subir un video.")
                        else:
                            _refmap[_v.get("key")] = _ref
                    _reels = []
                    for _c in (_data.get("reels") or []):
                        _vid = _refmap.get(_c.get("newkey")) if _c.get("newkey") else _c.get("video")
                        if not _vid and not _c.get("id"):
                            continue   # reel nuevo sin video → se ignora
                        _reels.append({"id": _c.get("id") or None, "video": _vid,
                                       "caption": _c.get("caption") or "",
                                       "linked_product": _c.get("product") or "",
                                       "advisor_name": _c.get("advisor") or ""})
                    _ok, _serr, _bk = _shop.guardar_reels(
                        _info.get("theme_id"), _info.get("asset_key"),
                        _info.get("section_id"), _reels)
                    if not _ok:
                        _errs.append(_serr or "No se pudo guardar la sección de reels.")
                if _errs:
                    st.session_state["sw_reels_errs"] = _errs
                else:
                    st.session_state["sw_reels_saved"] = True
                    _reels_clear_state()
                st.rerun()

    _form_html, _form_h = _build_reels_form(_work, _prod_opts, _adv_names)
    components.html(_form_html, height=int(_form_h), scrolling=False)
    # Nonce: re-monta el botón flotante «Guardar reels» en cada render.
    components.html(_SW_REELS_FLOAT_JS + f"<!--{_uuid.uuid4().hex}-->", height=0)


# Metacampos de IMAGEN del producto (file_reference) que se editan aparte del formulario
# HTML, con subida nativa. (namespace, key, etiqueta, ayuda)
_IMG_MFS = [
    ("custom", "imagen_render", "Imagen de render", "El render 3D del modelo."),
    ("custom", "imagen_planta", "Imagen de planta", "El plano / planta del modelo."),
]


def _preview_theme():
    """(id, nombre) del tema borrador elegido para previsualizar (por defecto el que contiene
    «NUEVA»). Devuelve (None, None) si no hay temas borrador. Cachea la lista en sesión."""
    _tid = st.session_state.get("sw_prev_theme_id")
    if _tid:
        return _tid, st.session_state.get("sw_prev_theme_name")
    _temas = st.session_state.get("sw_temas")
    if _temas is None:
        _temas, _terr = _shop.listar_temas()
        st.session_state["sw_temas"] = _temas or []
        st.session_state["sw_temas_err"] = _terr
    _drafts = [t for t in (_temas or [])
               if str(t.get("role")) not in ("main", "demo", "archived")]
    if not _drafts:
        return None, None
    _t = next((t for t in _drafts if "nueva" in str(t.get("name") or "").lower()), _drafts[0])
    return _t.get("id"), _t.get("name")


def _render_preview_borrador_bar():
    """Barra para PREVISUALIZAR la tienda en un tema BORRADOR (p.ej. «Versión NUEVA») sin
    publicarlo. Los productos son de la tienda (compartidos entre todos los temas), así que lo
    que editas aquí YA aplica al borrador; esto solo te deja VERLO renderizado en ese tema."""
    _temas = st.session_state.get("sw_temas")
    if _temas is None:
        _temas, _terr = _shop.listar_temas()
        st.session_state["sw_temas"] = _temas or []
        st.session_state["sw_temas_err"] = _terr
    _drafts = [t for t in (_temas or [])
               if str(t.get("role")) not in ("main", "demo", "archived")]
    if not _drafts:
        return
    st.markdown(
        '<div style="display:flex;gap:8px;align-items:flex-start;background:#fffbeb;'
        'border:1px solid #fde68a;border-radius:10px;padding:10px 14px;margin:2px 0 12px;">'
        f'{_ic("draft", "#b45309", 18, 0, 0)}'
        '<p style="margin:0;font-size:0.82rem;color:#78350f;line-height:1.4;">'
        '<b>Vista previa del tema borrador.</b> Tus productos son los mismos en todos los temas, '
        'así que lo que subes/editas/eliminas aquí <b>ya aplica al borrador</b>. Usa este botón '
        'para <b>verlos renderizados</b> en el tema borrador antes de publicarlo.</p></div>',
        unsafe_allow_html=True)
    _c1, _c2 = st.columns([3, 1.5], vertical_alignment="bottom")
    with _c1:
        _di = next((i for i, t in enumerate(_drafts)
                    if "nueva" in str(t.get("name") or "").lower()), 0)
        _sel = st.selectbox("Tema borrador", options=range(len(_drafts)), index=_di,
                            format_func=lambda i: (_drafts[i].get("name") or f"Tema {_drafts[i].get('id')}"),
                            key="sw_prev_sel", label_visibility="collapsed")
    _t = _drafts[_sel]
    st.session_state["sw_prev_theme_id"] = _t.get("id")
    st.session_state["sw_prev_theme_name"] = _t.get("name")
    with _c2:
        _url = _shop.url_preview_tema(_t.get("id"))
        st.link_button("Ver la tienda ↗", _url or "#", use_container_width=True,
                       disabled=not _url, help="Abre la tienda con el tema borrador (requiere tu sesión de Shopify).")


def _render_editor(pid):
    """Editor de UN producto: datos + precios + fotos. Escribe a Shopify con confirmación."""
    st.markdown("<style>.st-key-sw_ed_del button{background:#fef2f2!important;border:1px solid #fecaca!important;"
                "color:#dc2626!important;}.st-key-sw_ed_del button:hover{background:#fee2e2!important;"
                "border-color:#fca5a5!important;}.st-key-sw_ed_del button p{color:#dc2626!important;}</style>",
                unsafe_allow_html=True)
    # Volver a la IZQUIERDA; Duplicar/Eliminar a la DERECHA (espacio al medio).
    _bc1, _bcsp, _bc2, _bc3 = st.columns([1.8, 4, 1.6, 1.6], vertical_alignment="center")
    with _bc1:
        if st.button("← Volver al catálogo", key="sw_ed_back"):
            st.session_state.pop("sw_edit_id", None)
            _clear_editor_state()
            _cargar_productos.clear()
            st.rerun()
    with _bc2:
        with st.popover("Duplicar producto", icon=":material/content_copy:", use_container_width=True):
            st.markdown("**Duplicar este producto**")
            st.caption("Crea una copia como **borrador** (invisible en la web) con las fotos, "
                       "variantes, descripción y características. Luego la renombras y ajustas.")
            if st.button("Sí, duplicar", key="sw_ed_dup_go", type="primary",
                         icon=":material/content_copy:", use_container_width=True):
                _duplicar_flow(pid)
    with _bc3:
        if st.button("Eliminar producto", key="sw_ed_del", icon=":material/delete:",
                     use_container_width=True):
            st.session_state["sw_del_pending"] = str(pid)
            st.session_state.pop("sw_del_ck", None)
            st.rerun()

    if st.session_state.pop("sw_saved_ok", False):
        st.success("Cambios guardados y publicados en el sitio web.", icon=":material/check_circle:")
    _serrs = st.session_state.pop("sw_save_errs", None)
    if _serrs:
        st.warning("Se guardó, pero algunos pasos tuvieron avisos:\n\n"
                   + "\n\n".join(f"- {e}" for e in _serrs), icon=":material/warning:")

    _p = st.session_state.get("sw_edit_prod")
    if not _p or str(_p.get("id")) != str(pid):
        with st.spinner("Cargando producto…"):
            _p, _err = _shop.get_producto(pid)
        if _err or not _p:
            st.error(_err or "No se pudo cargar el producto.", icon=":material/error:")
            return
        st.session_state["sw_edit_prod"] = _p

    # Enlace para VER este producto en el tema borrador (los productos son compartidos entre
    # temas, así que estos cambios ya aplican al borrador; esto es solo para revisarlo).
    _ptid, _ptname = _preview_theme()
    if _ptid and _p.get("handle"):
        _purl = _shop.url_preview_tema(_ptid, f"/products/{_p.get('handle')}")
        if _purl:
            st.link_button(f"Ver este producto en el borrador «{_ptname or ''}» ↗", _purl,
                           help="Abre el producto renderizado con el tema borrador (requiere tu sesión de Shopify).")

    # ── Formulario del producto (HTML limpio, un solo guardado) ──
    # Canales (publicaciones)
    _pubs = st.session_state.get("sw_pubs")
    if _pubs is None:
        _pubs, _puberr = _shop.listar_publicaciones()
        st.session_state["sw_pubs"] = _pubs or []
        st.session_state["sw_pubs_err"] = _puberr
        _pubs = _pubs or []
    _prod_pubs = st.session_state.get("sw_edit_prodpubs")
    if _prod_pubs is None or st.session_state.get("sw_edit_prodpubs_pid") != str(pid):
        _pp, _ = _shop.publicaciones_de_producto(pid)
        _prod_pubs = list(_pp) if _pp is not None else []
        st.session_state["sw_edit_prodpubs"] = _prod_pubs
        st.session_state["sw_edit_prodpubs_pid"] = str(pid)
    _prod_pubs_set = set(_prod_pubs)
    # Colecciones
    _cols = st.session_state.get("sw_cols")
    if _cols is None:
        _cols, _ = _shop.listar_colecciones()
        _cols = _cols or []
        st.session_state["sw_cols"] = _cols
    _col_ids = {str(c.get("id")) for c in _cols}
    _collects = st.session_state.get("sw_edit_collects")
    if _collects is None or st.session_state.get("sw_edit_collects_pid") != str(pid):
        _collects, _ = _shop.colecciones_de_producto(pid)
        _collects = _collects or []
        st.session_state["sw_edit_collects"] = _collects
        st.session_state["sw_edit_collects_pid"] = str(pid)
    _cur_cols = [str(cl.get("collection_id")) for cl in _collects
                 if str(cl.get("collection_id")) in _col_ids]
    # Características (metacampos): TODOS los definidos (aunque vacíos) + los propios.
    _mf = st.session_state.get("sw_edit_mf")
    if _mf is None or st.session_state.get("sw_edit_mf_pid") != str(pid):
        _mf, _ = _shop.listar_metafields(pid)
        _mf = _mf or []
        st.session_state["sw_edit_mf"] = _mf
        st.session_state["sw_edit_mf_pid"] = str(pid)
    _defs = _plantilla_metafields()
    _mf_by_nk = {(m.get("namespace") or "", m.get("key") or ""): m for m in _mf}
    # Metacampos con editor DEDICADO (no van en la lista genérica de Características).
    _MF_DEDICADOS = {("custom", "especificaciones_sidebar")} | {(ns, k) for ns, k, *_ in _IMG_MFS}
    _mf_editable, _mf_seen = [], set()
    for d in _defs:
        _nk = (d.get("namespace") or "", d.get("key") or "")
        if _nk in _MF_DEDICADOS or _mf_kind(d.get("type")) == "readonly":
            continue
        _ex = _mf_by_nk.get(_nk)
        if _ex:
            _mf_editable.append({**_ex, "name": d.get("name") or _mf_label(_ex)})
        else:
            _mf_editable.append({"id": None, "namespace": _nk[0], "key": _nk[1],
                                 "type": d.get("type"), "value": "", "name": d.get("name") or _mf_label(d)})
        _mf_seen.add(_nk)
    for m in _mf:
        _nk = (m.get("namespace") or "", m.get("key") or "")
        if _nk in _mf_seen or _nk in _MF_DEDICADOS or _mf_kind(m.get("type")) == "readonly":
            continue
        _mf_editable.append({**m, "name": _mf_label(m)})

    # Metacampos de IMAGEN (planta/render): valores actuales (gid) + su URL para mostrarlos
    # dentro del formulario. La resolución (GraphQL) se cachea por producto.
    _img_gids = [(_mf_by_nk.get((_ns, _key)) or {}).get("value") for _ns, _key, *_ in _IMG_MFS]
    _img_gids = [g for g in _img_gids if g and str(g).startswith("gid://")]
    _iuk = f"sw_imgmf_urls_{pid}"
    _iurls = st.session_state.get(_iuk)
    if _iurls is None:
        _iurls, _ = _shop.resolver_imagenes(_img_gids)
        _iurls = _iurls or {}
        st.session_state[_iuk] = _iurls
    _img_metas = []
    for _ns, _key, _label, _hint in _IMG_MFS:
        _v = (_mf_by_nk.get((_ns, _key)) or {}).get("value") or ""
        _img_metas.append({"ns": _ns, "key": _key, "label": _label, "hint": _hint,
                           "gid": _v, "url": (_iurls.get(_v) if _v else "") or ""})

    # ESPECIFICACIONES (SIDEBAR): tipo detectado (del propio producto o de la definición) +
    # valor actual → texto para el textarea. Editor dedicado (list = una línea por ítem).
    _esp_mf = _mf_by_nk.get(("custom", "especificaciones_sidebar"))
    if _esp_mf and _esp_mf.get("type"):
        _esp_type, _esp_id, _esp_val = _esp_mf.get("type"), (_esp_mf.get("id") or ""), (_esp_mf.get("value") or "")
    else:
        _esp_def = next((d for d in _defs if (d.get("namespace"), d.get("key"))
                         == ("custom", "especificaciones_sidebar")), None)
        _esp_type = (_esp_def.get("type") if _esp_def else "") or "list.single_line_text_field"
        _esp_id, _esp_val = "", ""
    _especs = {"type": _esp_type, "id": _esp_id,
               "text": _especs_to_text(_esp_type, _esp_val)}

    # Puente de guardado (input oculto sw_savecmd; se auto-limpia tras procesar).
    if st.session_state.pop("_sw_reset_savecmd", False):
        st.session_state["sw_savecmd"] = ""
    _sc = st.text_input("savecmd", key="sw_savecmd", label_visibility="collapsed")
    if _sc and "|" in _sc:
        _sbody, _sts = _sc.rsplit("|", 1)
        if _sts != st.session_state.get("sw_savecmd_ts"):
            st.session_state["sw_savecmd_ts"] = _sts
            st.session_state["_sw_reset_savecmd"] = True
            import json as _json
            try:
                _data = _json.loads(_sbody)
            except Exception:
                _data = None
            if _data is not None:
                if _data.get("op") == "upload":     # subir fotos/videos del PC (op aparte)
                    _files = _data.get("files") or []
                    _vids = _data.get("videos") or []
                    _spin = f"Subiendo {len(_files)} foto(s)" + (f" y {len(_vids)} video(s)" if _vids else "") + " a la tienda…"
                    with st.spinner(_spin):
                        _errs = _subir_fotos(pid, _files)
                        for _v in _vids:
                            try:
                                _vb = base64.b64decode(_v.get("b64") or "")
                            except Exception:
                                _vb = b""
                            if _vb:
                                _ok, _e = _shop.subir_video(pid, _v.get("name") or "video.mp4",
                                                            _v.get("mime") or "video/mp4", _vb)
                                if not _ok:
                                    _errs.append(_e)
                    if _vids:
                        st.session_state.pop("sw_edit_vid", None)   # refrescar la galería de videos
                    _msg = f"{len(_files)} foto(s)" + (f" y {len(_vids)} video(s)" if _vids else "")
                    st.session_state["sw_toast"] = _msg + " subido(s)." + (" (con avisos)" if _errs else "")
                elif _data.get("op") == "video_url":   # agregar video por enlace (YouTube/Vimeo)
                    _u = (_data.get("url") or "").strip()
                    if _u:
                        with st.spinner("Agregando video…"):
                            _okv, _ev = _shop.agregar_video_externo(pid, _u)
                        st.session_state.pop("sw_edit_vid", None)
                        st.session_state["sw_toast"] = ("Video agregado." if _okv
                                                        else f"No se pudo agregar el video: {_ev}")
                else:                               # guardado completo del formulario (+ fotos/videos PC)
                    with st.spinner("Guardando en Shopify…"):
                        _errs = _guardar_todo(pid, _data)
                    if _data.get("pc_videos") or _data.get("video_delete") or _data.get("new_ext_videos"):
                        st.session_state.pop("sw_edit_vid", None)   # refrescar galería de videos
                    if _errs:
                        st.session_state["sw_toast"] = "Guardado con avisos (revisa el detalle arriba)."
                        st.session_state["sw_save_errs"] = [str(x) for x in _errs]   # detalle completo
                    else:
                        st.session_state["sw_toast"] = "✅ Cambios guardados y publicados en el sitio web."
                        st.session_state["sw_saved_ok"] = True
                st.session_state.pop("sw_edit_prod", None)
                st.session_state.pop("sw_edit_collects", None)
                st.session_state.pop("sw_edit_prodpubs", None)
                st.session_state.pop("sw_edit_mf", None)   # refrescar características
                st.session_state.pop(f"sw_imgmf_urls_{pid}", None)  # refrescar imágenes planta/render
                _cargar_productos.clear()
                st.rerun()

    # Videos del producto (subidos + externos): se muestran DENTRO de la galería de
    # medios, junto a las fotos (como en Shopify). Se cargan antes de armar el formulario.
    _vid = st.session_state.get("sw_edit_vid")
    if _vid is None or st.session_state.get("sw_edit_vid_pid") != str(pid):
        with st.spinner("Cargando videos…"):
            _vid, _viderr = _shop.listar_videos(pid)
        if _viderr:
            st.warning(_viderr)
            _vid = []
        st.session_state["sw_edit_vid"] = _vid
        st.session_state["sw_edit_vid_pid"] = str(pid)

    _form_html, _form_h = _build_editor_form(_p, _pubs, _prod_pubs_set, _cols, _cur_cols,
                                             metafields=_mf_editable, videos=_vid,
                                             img_metas=_img_metas, especs=_especs)
    components.html(_form_html, height=int(_form_h), scrolling=False)   # el propio iframe se auto-ajusta
    # Nonce: fuerza re-ejecución del iframe en cada render → el botón flotante se RE-MONTA
    # siempre (tras publicar, cambiar de producto, etc.), en vez de reusar un iframe estático.
    components.html(_SW_FLOAT_JS + f"<!--{_uuid.uuid4().hex}-->", height=0)   # botón flotante "Guardar y publicar"
