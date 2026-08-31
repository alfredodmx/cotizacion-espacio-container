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
    "video": '<path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/>',
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
def _cargar_productos(status, _cb="", published_status=""):
    return _shop.listar_productos(status=status, published_status=published_status)


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_publicados(_cb=""):
    """Set de IDs publicados en la tienda online (fuente de verdad para 'Activo' vs
    'No publicado'). Usa la API de publicaciones (GraphQL, AUTORITATIVA); si falta el
    scope read_publications cae al filtro REST published_status (menos fiable) y, en
    último caso, el llamador usa published_at. None si todo falla."""
    ids, _ = _shop.ids_publicados_online_store()
    if ids is not None:
        return ids
    ids2, _ = _shop.listar_ids_publicados()
    return ids2


# Estados efectivos (status de Shopify + publicación en la tienda online).
_ESTADOS = {
    "active":      ("#dcfce7", "#15803d", "Activo"),
    "unpublished": ("#fef3c7", "#b45309", "No publicado"),
    "draft":       ("#fef9c3", "#854d0e", "Borrador"),
    "archived":    ("#e2e8f0", "#475569", "Archivado"),
}


def _estado_efectivo(p, pubset=None) -> str:
    """Estado REAL que muestra Shopify: archivado / borrador / activo (publicado) o
    'unpublished' = activo pero SIN publicar en la tienda online. La publicación se
    decide por el SET de ids publicados (published_status), NO por published_at (que
    es legacy y no coincide). Si no hay set, cae a published_at."""
    _s = str(p.get("status") or "").lower()
    if _s == "archived":
        return "archived"
    if _s == "draft":
        return "draft"
    if pubset is None:
        pubset = st.session_state.get("sw_pubset")
    if pubset is not None:
        return "active" if str(p.get("id")) in pubset else "unpublished"
    return "active" if p.get("published_at") else "unpublished"


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

    # Set de productos publicados en la tienda online (fuente de verdad del estado).
    # Se carga temprano (cacheado) para que card, tabla, editor y diálogo coincidan.
    st.session_state["sw_pubset"] = _cargar_publicados()

    # ── Puente para abrir el editor / duplicar ──
    _ec = st.text_input("editcmd", key="sw_editcmd", label_visibility="collapsed")
    if _ec and "|" in _ec:
        _head, _ets = _ec.rsplit("|", 1)
        if _ets != st.session_state.get("sw_editcmd_ts"):
            st.session_state["sw_editcmd_ts"] = _ets
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

    # ── Selector de vista: Tarjetas (por defecto) / Tabla ──
    st.markdown(_SW_VISTA_CSS, unsafe_allow_html=True)
    _vistas = ["Tarjetas", "Tabla"]
    _vicons = {"Tarjetas": ":material/grid_view:", "Tabla": ":material/table_rows:"}
    _vista = st.radio("Vista", _vistas, index=0, key="sw_vista", horizontal=True,
                      label_visibility="collapsed", format_func=lambda v: f"{_vicons.get(v, '')} {v}")

    # Cada opción → (status, published_status). "No publicados" = activo pero sin
    # publicar en la tienda online (lo que Shopify muestra en gris como "No publicado").
    _opts = {
        "Activos":       ("active", "published"),
        "No publicados": ("active", "unpublished"),
        "Borradores":    ("draft", ""),
        "Archivados":    ("archived", ""),
        "Todos":         ("", ""),
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
            _cargar_publicados.clear()
            st.session_state.pop("sw_mf_defs", None)
            st.session_state.pop("sw_cols", None)
            st.session_state.pop("sw_pubs", None)
            st.session_state.pop("sw_pubs_err", None)
            st.rerun()
    with _c3:
        if st.button("Nuevo producto", key="sw_new_open", use_container_width=True, type="primary",
                     icon=":material/add_box:"):
            _clear_editor_state()
            for _k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_new_")]:
                st.session_state.pop(_k, None)
            st.session_state["sw_new"] = True
            st.rerun()
    _status, _pubstatus = _opts[_lbl]

    with st.spinner("Conectando con Shopify y trayendo los productos…"):
        _prods, _err = _cargar_productos(_status, published_status=_pubstatus)

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

    _bcol = _ESTADOS

    # ── Diagnóstico temporal de estados (para hallar la señal correcta) ──
    with st.expander("🔧 Diagnóstico de estados (debug)"):
        if st.button("Analizar señales de publicación", key="sw_diag_btn"):
            _pubs_d, _pe = _shop.listar_publicaciones()
            _pubname = {p.get("id"): p.get("name") for p in (_pubs_d or [])}
            _os_d = _shop._online_store_pub_id()
            _pubset_d = st.session_state.get("sw_pubset")
            st.write(f"**Publicaciones (canales) detectadas:** {[p.get('name') for p in (_pubs_d or [])]}"
                     + (f" · error: {_pe}" if _pe else ""))
            st.write(f"**Online Store pub id detectada:** `{_os_d}`")
            st.write(f"**sw_pubset (set usado para el badge)** — {len(_pubset_d) if _pubset_d else 0} ids: "
                     f"`{list(_pubset_d)[:20] if _pubset_d else _pubset_d}`")
            _rows = []
            with st.spinner("Consultando cada producto…"):
                for p in _prods:
                    _pid = p.get("id")
                    _pp, _ = _shop.publicaciones_de_producto(_pid)
                    _pp = _pp or set()
                    _rows.append({
                        "Producto": p.get("title"),
                        "id": str(_pid),
                        "status": p.get("status"),
                        "published_at": str(p.get("published_at"))[:19] if p.get("published_at") else None,
                        "published_scope": p.get("published_scope"),
                        "En canales (isPublished)": ", ".join(
                            sorted(_pubname.get(g, str(g).rsplit('/', 1)[-1]) for g in _pp)) or "—",
                        "¿en Online Store?": (_os_d in _pp) if _os_d else None,
                        "badge del sistema": _estado_efectivo(p),
                    })
            st.dataframe(_rows, use_container_width=True, hide_index=True)
            st.caption("Compara la columna «badge del sistema» y «¿en Online Store?» con lo que Shopify "
                       "muestra como Estado (Activo / No publicado) y dime cuál columna coincide.")

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
    """Formulario para CREAR un producto nuevo. Al crearlo, abre su editor para que se
    le agreguen fotos, videos y características. Se crea como BORRADOR por defecto (no
    queda público hasta que se active)."""
    if st.button("← Volver al catálogo", key="sw_new_back"):
        st.session_state.pop("sw_new", None)
        for _k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_new_")]:
            st.session_state.pop(_k, None)
        st.rerun()

    st.markdown(f'<div class="sw-sec">{_ic("box", "#0f172a", 17, 0)}Nuevo producto</div>',
                unsafe_allow_html=True)
    st.caption("Crea un modelo nuevo para la web. Se guarda como BORRADOR (no visible) hasta que lo "
               "actives; primero podrás agregarle fotos, videos y características.")

    _title = st.text_input("Nombre del producto *", key="sw_new_title",
                           placeholder="Ej: Cabaña Aurora 36m²")
    _dc1, _dc2 = st.columns([3, 1.2])
    with _dc1:
        _desc = st.text_area("Descripción · acepta HTML", key="sw_new_desc", height=150,
                             placeholder="Describe el modelo, materiales, terminaciones…")
    with _dc2:
        _price = st.number_input("Precio", min_value=0.0, step=1000.0, format="%.0f", key="sw_new_price")
        _est_lbl = st.selectbox("Estado inicial", ["Borrador", "Activo"], key="sw_new_status")
    _tc1, _tc2 = st.columns(2)
    with _tc1:
        _ptype = st.text_input("Tipo de producto", value="Casa Container", key="sw_new_type")
    with _tc2:
        _tags = st.text_input("Etiquetas (separadas por coma)", key="sw_new_tags")
    _imgurl = st.text_input("Foto principal por URL (opcional)", key="sw_new_img",
                            placeholder="https://…/foto.jpg", help="Luego podrás agregar/subir más fotos.")

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    _conf = st.checkbox("Confirmo crear este producto en la web (como borrador).", key="sw_new_conf")
    if st.button("Crear producto", type="primary", key="sw_new_create",
                 disabled=(not (_title or "").strip() or not _conf), icon=":material/add_box:"):
        _campos = {
            "title": _title.strip(),
            "body_html": _desc,
            "status": "active" if _est_lbl == "Activo" else "draft",
            "product_type": _ptype.strip(),
            "tags": _tags.strip(),
            "variants": [{"price": f"{_price:.0f}"}],
        }
        if (_imgurl or "").strip():
            _campos["images"] = [{"src": _imgurl.strip()}]
        with st.spinner("Creando producto en Shopify…"):
            _prod, _err = _shop.crear_producto(_campos)
        if _err or not _prod:
            st.error(_err or "No se pudo crear el producto.", icon=":material/error:")
        else:
            st.session_state.pop("sw_new", None)
            for _k in [k for k in list(st.session_state.keys()) if str(k).startswith("sw_new_")]:
                st.session_state.pop(_k, None)
            _clear_editor_state()
            _cargar_productos.clear()
            st.session_state["sw_edit_id"] = str(_prod.get("id"))
            st.toast("Producto creado. Ahora agrégale fotos, videos y características.")
            st.rerun()


def _render_editor(pid):
    """Editor de UN producto: datos + precios + fotos. Escribe a Shopify con confirmación."""
    st.markdown("<style>.st-key-sw_ed_del button{background:#fef2f2!important;border:1px solid #fecaca!important;"
                "color:#dc2626!important;}.st-key-sw_ed_del button:hover{background:#fee2e2!important;"
                "border-color:#fca5a5!important;}.st-key-sw_ed_del button p{color:#dc2626!important;}</style>",
                unsafe_allow_html=True)
    _bc1, _bc2, _bc3 = st.columns([1.1, 1.05, 1.05], vertical_alignment="center")
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
        # Estado + publicación en la tienda online. "No publicado" = activo pero oculto
        # en la web (published=false). Se refleja el estado REAL (no solo el status).
        _est_map = {"Activo": ("active", True), "No publicado": ("active", False),
                    "Borrador": ("draft", None), "Archivado": ("archived", None)}
        _est_lbls = list(_est_map.keys())
        _cur_lbl = {"active": "Activo", "unpublished": "No publicado",
                    "draft": "Borrador", "archived": "Archivado"}.get(_estado_efectivo(_p), "Activo")
        _status_lbl = st.selectbox("Estado (visibilidad en la web)", _est_lbls,
                                   index=_est_lbls.index(_cur_lbl), key="sw_ed_status")
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
            _st_val, _pub_val = _est_map[_status_lbl]
            _campos_prod = {
                "title": _title.strip(), "body_html": _desc,
                "status": _st_val,
                "product_type": _ptype.strip(), "tags": _tags.strip()}
            if _pub_val is not None:   # publicar / despublicar de la tienda online
                _campos_prod["published"] = _pub_val
            _ok, _e = _shop.actualizar_producto(pid, _campos_prod)
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
            _cargar_publicados.clear()                    # cambió la publicación
            st.toast("Cambios publicados en la web.")
            st.rerun()

    # ── Organización (proveedor + colecciones) ──
    st.markdown(f'<div class="sw-sec">{_ic("box", "#0f172a", 16, 0)}Organización del producto</div>',
                unsafe_allow_html=True)
    st.caption("Proveedor y colecciones (agrupaciones de la web). Las colecciones «automáticas» "
               "no aparecen aquí porque su contenido lo define una regla en Shopify.")
    _vendor = st.text_input("Proveedor", value=_p.get("vendor", "") or "", key="sw_ed_vendor",
                            placeholder="Ej: Container Houses")

    _cols = st.session_state.get("sw_cols")
    if _cols is None:
        with st.spinner("Cargando colecciones…"):
            _cols, _ = _shop.listar_colecciones()
        _cols = _cols or []
        st.session_state["sw_cols"] = _cols
    _col_title = {str(c.get("id")): (c.get("title") or "(sin título)") for c in _cols}

    _collects = st.session_state.get("sw_edit_collects")
    if _collects is None or st.session_state.get("sw_edit_collects_pid") != str(pid):
        _collects, _ = _shop.colecciones_de_producto(pid)
        _collects = _collects or []
        st.session_state["sw_edit_collects"] = _collects
        st.session_state["sw_edit_collects_pid"] = str(pid)
    _collect_by_col = {str(cl.get("collection_id")): cl.get("id") for cl in _collects}
    _cur_cols = [cid for cid in _collect_by_col if cid in _col_title]

    if _col_title:
        _sel_cols = st.multiselect(
            "Colecciones", options=list(_col_title.keys()), default=_cur_cols,
            format_func=lambda cid: _col_title.get(cid, cid), key="sw_ed_cols",
            help="Marca las colecciones a las que pertenece este producto.")
    else:
        _sel_cols = _cur_cols
        st.caption("No hay colecciones manuales en la tienda (o el token no tiene permiso para leerlas).")

    if st.button("Guardar organización", key="sw_ed_orgsave", type="primary", icon=":material/save:"):
        _errs = []
        with st.spinner("Guardando organización…"):
            if (_vendor or "").strip() != (_p.get("vendor", "") or "").strip():
                _ok, _e = _shop.actualizar_producto(pid, {"vendor": _vendor.strip()})
                if not _ok:
                    _errs.append(_e)
            _selset, _curset = set(_sel_cols), set(_cur_cols)
            for _cid in _selset - _curset:      # agregar a colección
                _ok, _e = _shop.agregar_a_coleccion(pid, _cid)
                if not _ok:
                    _errs.append(_e)
            for _cid in _curset - _selset:      # quitar de colección
                _collectid = _collect_by_col.get(_cid)
                if _collectid:
                    _ok, _e = _shop.quitar_de_coleccion(_collectid)
                    if not _ok:
                        _errs.append(_e)
        if _errs:
            st.error("No se pudo guardar todo: " + " · ".join(str(x) for x in _errs))
        else:
            st.session_state.pop("sw_edit_prod", None)
            st.session_state.pop("sw_edit_collects", None)
            _cargar_productos.clear()
            st.toast("Organización guardada.")
            st.rerun()

    # ── Canales de venta (publicaciones) ──
    st.markdown(f'<div class="sw-sec">{_ic("box", "#0f172a", 16, 0)}Canales de venta</div>',
                unsafe_allow_html=True)
    st.caption("Dónde se muestra el producto (Tienda online, Point of Sale, etc.), igual que "
               "«Gestionar publicación» en Shopify. «Tienda online» es lo mismo que el estado "
               "Activo/No publicado de arriba.")
    _pubs = st.session_state.get("sw_pubs")
    if _pubs is None:
        with st.spinner("Cargando canales…"):
            _pubs, _puberr = _shop.listar_publicaciones()
        st.session_state["sw_pubs"] = _pubs or []
        st.session_state["sw_pubs_err"] = _puberr
        _pubs = _pubs or []
    _puberr = st.session_state.get("sw_pubs_err")
    if _puberr:
        st.info("Para gestionar los canales de venta desde aquí, el token de Shopify necesita los "
                "permisos **read_publications** y **write_publications**. Agrégalos en tu app custom "
                "(Configuración de API → scopes), Guarda y REINSTALA la app. Luego pulsa Actualizar. "
                f"\n\nDetalle técnico: {_puberr}", icon=":material/info:")
    elif _pubs:
        _ppubs = st.session_state.get("sw_edit_prodpubs")
        if _ppubs is None or st.session_state.get("sw_edit_prodpubs_pid") != str(pid):
            _pp, _ = _shop.publicaciones_de_producto(pid)
            _ppubs = list(_pp) if _pp is not None else []
            st.session_state["sw_edit_prodpubs"] = _ppubs
            st.session_state["sw_edit_prodpubs_pid"] = str(pid)
        _cur_pub = set(_ppubs)
        _ch_state = {}
        for _pub in _pubs:
            _gid = _pub.get("id")
            _num = str(_gid).rsplit("/", 1)[-1]
            _cc1, _cc2 = st.columns([4, 1.2], vertical_alignment="center")
            with _cc1:
                st.markdown(f'<div style="font-weight:700;color:#0f172a;font-size:0.9rem;padding-top:6px;">'
                            f'{_he(_pub.get("name", "Canal"))}</div>', unsafe_allow_html=True)
            with _cc2:
                _ch_state[_gid] = st.toggle("Publicado", value=(_gid in _cur_pub),
                                            key=f"sw_ed_ch_{_num}", label_visibility="collapsed")
        if st.button("Guardar canales", key="sw_ed_chsave", type="primary", icon=":material/save:"):
            _to_pub = [p for p, on in _ch_state.items() if on and p not in _cur_pub]
            _to_unpub = [p for p, on in _ch_state.items() if not on and p in _cur_pub]
            _errs = []
            with st.spinner("Actualizando canales…"):
                if _to_pub:
                    _ok, _e = _shop.publicar_en_canales(pid, _to_pub)
                    if not _ok:
                        _errs.append(_e)
                if _to_unpub:
                    _ok, _e = _shop.despublicar_de_canales(pid, _to_unpub)
                    if not _ok:
                        _errs.append(_e)
            if _errs:
                st.error("No se pudo actualizar todo: " + " · ".join(str(x) for x in _errs))
            else:
                st.session_state.pop("sw_edit_prodpubs", None)
                st.session_state.pop("sw_edit_prod", None)
                _cargar_productos.clear()
                _cargar_publicados.clear()
                st.toast("Canales de venta actualizados.")
                st.rerun()

    # ── Fotos ──
    st.markdown(f'<div class="sw-sec">{_ic("img", "#0f172a", 16, 0)}Fotos '
                f'<span style="color:#94a3b8;font-weight:800;">· {len(_imgs)}</span></div>',
                unsafe_allow_html=True)
    if _imgs:
        st.caption("La 1ª foto es la principal en la web. Usa ◀ ▶ para reordenar y la papelera para eliminar.")
        _all_ids = [im.get("id") for im in _imgs]

        def _reorder(new_ids):
            with st.spinner("Reordenando…"):
                _ok, _e = _shop.reordenar_imagenes(pid, new_ids)
            if _ok:
                st.session_state.pop("sw_edit_prod", None)
                _cargar_productos.clear()
                st.rerun()
            else:
                st.error(_e)

        _n = 4
        for _base in range(0, len(_imgs), _n):
            _row = _imgs[_base:_base + _n]
            _cols = st.columns(_n)
            for _j, im in enumerate(_row):
                _gidx = _base + _j
                with _cols[_j]:
                    _src = im.get("src", "")
                    if _src:
                        st.markdown(f'<div class="sw-ph"><img src="{_he(_src)}" alt=""></div>',
                                    unsafe_allow_html=True)
                    _b1, _b2, _b3 = st.columns(3)
                    with _b1:
                        if st.button("", icon=":material/chevron_left:", key=f"sw_ed_mvl_{im.get('id')}",
                                     use_container_width=True, help="Mover antes", disabled=(_gidx == 0)):
                            _no = list(_all_ids)
                            _no[_gidx - 1], _no[_gidx] = _no[_gidx], _no[_gidx - 1]
                            _reorder(_no)
                    with _b2:
                        if st.button("", icon=":material/chevron_right:", key=f"sw_ed_mvr_{im.get('id')}",
                                     use_container_width=True, help="Mover después",
                                     disabled=(_gidx == len(_imgs) - 1)):
                            _no = list(_all_ids)
                            _no[_gidx + 1], _no[_gidx] = _no[_gidx], _no[_gidx + 1]
                            _reorder(_no)
                    with _b3:
                        if st.button("", icon=":material/delete:", key=f"sw_ed_delimg_{im.get('id')}",
                                     use_container_width=True, help="Eliminar"):
                            with st.spinner("Eliminando foto…"):
                                _ok, _e = _shop.eliminar_imagen(pid, im.get("id"))
                            if _ok:
                                st.session_state.pop("sw_edit_prod", None)
                                _cargar_productos.clear()
                                st.toast("Foto eliminada.")
                                st.rerun()
                            else:
                                st.error(_e)
                    st.markdown(f'<div style="text-align:center;font-size:0.66rem;color:#94a3b8;'
                                f'font-weight:700;">Foto #{_gidx + 1}'
                                + ('  · principal' if _gidx == 0 else '') + '</div>', unsafe_allow_html=True)
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

    # ── Videos ──
    _vid = st.session_state.get("sw_edit_vid")
    if _vid is None or st.session_state.get("sw_edit_vid_pid") != str(pid):
        with st.spinner("Cargando videos…"):
            _vid, _viderr = _shop.listar_videos(pid)
        if _viderr:
            st.warning(_viderr)
            _vid = []
        st.session_state["sw_edit_vid"] = _vid
        st.session_state["sw_edit_vid_pid"] = str(pid)

    st.markdown(f'<div class="sw-sec">{_ic("video", "#0f172a", 16, 0)}Videos '
                f'<span style="color:#94a3b8;font-weight:800;">· {len(_vid)}</span></div>',
                unsafe_allow_html=True)
    st.caption("Agrega videos de YouTube o Vimeo pegando el enlace. Aparecen en la galería del producto "
               "(si tu tema muestra videos).")

    if _vid:
        _vn = 4
        for _vbase in range(0, len(_vid), _vn):
            _vrow = _vid[_vbase:_vbase + _vn]
            _vcols = st.columns(_vn)
            for _vj, vd in enumerate(_vrow):
                with _vcols[_vj]:
                    _pv = vd.get("preview_url", "")
                    if _pv:
                        st.markdown(
                            f'<div class="sw-ph" style="position:relative;"><img src="{_he(_pv)}" alt="">'
                            '<div style="position:absolute;inset:0;display:flex;align-items:center;'
                            'justify-content:center;"><div style="width:38px;height:38px;border-radius:50%;'
                            'background:rgba(15,23,42,.6);display:flex;align-items:center;justify-content:center;">'
                            '<svg width="16" height="16" viewBox="0 0 24 24" fill="#fff"><polygon points="6 3 20 12 6 21 6 3"/></svg>'
                            '</div></div></div>', unsafe_allow_html=True)
                    else:
                        st.markdown('<div class="sw-ph" style="display:flex;align-items:center;'
                                    'justify-content:center;aspect-ratio:1/1;color:#94a3b8;font-size:0.72rem;'
                                    'font-weight:700;">VIDEO</div>', unsafe_allow_html=True)
                    _label = (vd.get("host") or ("Externo" if vd.get("type") == "EXTERNAL_VIDEO" else "Subido")).title()
                    _st = vd.get("status")
                    _ourl = vd.get("origin_url", "")
                    st.markdown(
                        f'<div style="text-align:center;font-size:0.68rem;color:#64748b;font-weight:700;">{_he(_label)}'
                        + (f' · {_he(_st)}' if _st and _st != "READY" else "")
                        + (f'<br><a href="{_he(_ourl)}" target="_blank" style="color:#5b7cfa;">ver</a>' if _ourl else "")
                        + '</div>', unsafe_allow_html=True)
                    if st.button("Eliminar", key=f"sw_ed_vdel_{vd.get('id')}", use_container_width=True,
                                 icon=":material/delete:"):
                        with st.spinner("Eliminando video…"):
                            _ok, _e = _shop.eliminar_media(pid, vd.get("id"))
                        if _ok:
                            st.session_state.pop("sw_edit_vid", None)
                            st.toast("Video eliminado.")
                            st.rerun()
                        else:
                            st.error(_e)
    else:
        st.caption("Este producto no tiene videos todavía.")

    st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
    _vurl = st.text_input("Agregar video (enlace de YouTube o Vimeo)", key="sw_ed_newvid_url",
                          placeholder="https://www.youtube.com/watch?v=…")
    if st.button("Agregar video", key="sw_ed_addvid", icon=":material/video_call:",
                 disabled=not (_vurl or "").strip()):
        with st.spinner("Agregando video…"):
            _ok, _e = _shop.agregar_video_externo(pid, _vurl.strip())
        if _ok:
            st.session_state.pop("sw_edit_vid", None)
            st.session_state.pop("sw_ed_newvid_url", None)
            _cargar_productos.clear()
            st.toast("Video agregado.")
            st.rerun()
        else:
            st.error(_e)

    # ── Características (metafields) ──
    # Se muestran TODOS los campos DEFINIDOS en la tienda (m², baños, dormitorios,
    # clima, características…) aunque el producto todavía no tenga valor, más los
    # metacampos propios que ya tenga. Así se pueden completar aunque estén vacíos.
    _mf = st.session_state.get("sw_edit_mf")
    if _mf is None or st.session_state.get("sw_edit_mf_pid") != str(pid):
        with st.spinner("Cargando características…"):
            _mf, _mferr = _shop.listar_metafields(pid)
        if _mferr:
            st.warning(_mferr)
            _mf = []
        st.session_state["sw_edit_mf"] = _mf
        st.session_state["sw_edit_mf_pid"] = str(pid)

    _defs = st.session_state.get("sw_mf_defs")
    if _defs is None:
        _defs, _ = _shop.listar_definiciones_metafields()
        _defs = _defs or []
        st.session_state["sw_mf_defs"] = _defs

    # Fusiona definiciones + valores. Cada campo editable = def (con su nombre bonito)
    # + el valor del producto si existe (id) o vacío (id=None → se crea al guardar).
    _mf_by_nk = {(m.get("namespace") or "", m.get("key") or ""): m for m in _mf}
    _editable, _seen = [], set()
    for d in _defs:
        _nk = (d.get("namespace") or "", d.get("key") or "")
        if _mf_kind(d.get("type")) == "readonly":
            continue   # referencias/imágenes/listas → abajo, solo si ya tienen valor
        _ex = _mf_by_nk.get(_nk)
        if _ex:
            _editable.append({**_ex, "name": d.get("name") or _mf_label(_ex)})
        else:
            _editable.append({"id": None, "namespace": _nk[0], "key": _nk[1],
                              "type": d.get("type"), "value": "", "name": d.get("name") or _mf_label(d)})
        _seen.add(_nk)
    for m in _mf:   # metacampos editables propios que no tengan definición
        _nk = (m.get("namespace") or "", m.get("key") or "")
        if _nk in _seen or _mf_kind(m.get("type")) == "readonly":
            continue
        _editable.append({**m, "name": _mf_label(m)})

    # Avanzados = definiciones de tipo referencia/lista/imagen (Image, video reels…),
    # incluso vacías, + los que ya tengan valor. Así no "faltan" campos.
    _advanced, _adv_seen = [], set()
    for d in _defs:
        if _mf_kind(d.get("type")) != "readonly":
            continue
        _nk = (d.get("namespace") or "", d.get("key") or "")
        _ex = _mf_by_nk.get(_nk)
        if _ex:
            _advanced.append({**_ex, "name": d.get("name") or _mf_label(_ex)})
        else:
            _advanced.append({"id": None, "namespace": _nk[0], "key": _nk[1],
                              "type": d.get("type"), "value": "", "name": d.get("name") or _mf_label(d)})
        _adv_seen.add(_nk)
    for m in _mf:
        _nk = (m.get("namespace") or "", m.get("key") or "")
        if _nk in _adv_seen or _mf_kind(m.get("type")) != "readonly":
            continue
        _advanced.append({**m, "name": _mf_label(m)})

    st.markdown(f'<div class="sw-sec">{_ic("text", "#0f172a", 16, 0)}Características / detalles '
                f'<span style="color:#94a3b8;font-weight:800;">· {len(_editable)}</span></div>',
                unsafe_allow_html=True)
    st.caption("Los detalles del producto (m², dormitorios, baños, clima, características, etc.). Se muestran "
               "todos los campos definidos aunque estén vacíos: complétalos y pulsa Guardar. Un campo que "
               "dejes vacío no se publica.")

    if _editable:
        _mf_ws = {}
        for m in _editable:
            _ns = m.get("namespace") or "custom"
            _key = m.get("key") or ""
            _nk = f"{_ns}__{_key}"
            _mid = m.get("id")
            _kind = _mf_kind(m.get("type"))
            _mc1, _mc2, _mc3 = st.columns([2.4, 3.2, 0.7], vertical_alignment="center")
            with _mc1:
                st.markdown(
                    f'<div style="font-weight:700;color:#0f172a;font-size:0.85rem;line-height:1.2;">'
                    f'{_he(m.get("name") or _mf_label(m))}</div>'
                    f'<div style="font-size:0.64rem;color:#94a3b8;font-weight:600;">'
                    f'{_he(_MF_KIND_LABEL.get(_kind, "Texto"))}' + ("" if _mid else " · sin completar")
                    + '</div>', unsafe_allow_html=True)
            with _mc2:
                if _kind == "rich":
                    _orig = _richtext_to_text(m.get("value"))
                    _w = st.text_area("v", value=_orig, key=f"sw_ed_mf_{_nk}", height=130,
                                      label_visibility="collapsed",
                                      help="Escribe normal. Para una lista con viñetas, empieza la línea con «- ».")
                    _mf_ws[_nk] = ("rich", _w, _orig, m)
                else:
                    _mf_ws[_nk] = (m.get("type"), _mf_widget(m, f"sw_ed_mf_{_nk}"), None, m)
            with _mc3:
                if _mid and st.button("", icon=":material/delete:", key=f"sw_ed_mfdel_{_nk}",
                                      use_container_width=True, help="Vaciar este detalle"):
                    with st.spinner("Eliminando…"):
                        _ok, _e = _shop.eliminar_metafield(pid, _mid)
                    if _ok:
                        st.session_state.pop("sw_edit_mf", None)
                        st.toast("Detalle eliminado.")
                        st.rerun()
                    else:
                        st.error(_e)
        if st.button("Guardar características", key="sw_ed_mfsave", type="primary",
                     icon=":material/save:"):
            _errs = []
            with st.spinner("Guardando características…"):
                for _nk, (_t, _w, _orig, m) in _mf_ws.items():
                    _mid = m.get("id")
                    _ns = m.get("namespace") or "custom"
                    _key = m.get("key") or ""
                    if _t == "rich":
                        _newtxt = str(_w or "")
                        if _mid:
                            if _newtxt != str(_orig or ""):
                                _ok, _e = _shop.actualizar_metafield(pid, _mid, "rich_text_field",
                                                                     _text_to_richtext(_w))
                                if not _ok:
                                    _errs.append(_e)
                        elif _newtxt.strip():
                            _ok, _e = _shop.crear_metafield(pid, _ns, _key, "rich_text_field",
                                                            _text_to_richtext(_w))
                            if not _ok:
                                _errs.append(_e)
                    else:
                        _nv = _mf_serialize(_t, _w)
                        if _mid:
                            if str(_nv) != str(m.get("value", "")):
                                _ok, _e = _shop.actualizar_metafield(pid, _mid, _t, _nv)
                                if not _ok:
                                    _errs.append(_e)
                        elif not _mf_is_empty(_t, _nv):
                            _ok, _e = _shop.crear_metafield(pid, _ns, _key, _t, _nv)
                            if not _ok:
                                _errs.append(_e)
            if _errs:
                st.error("No se pudieron guardar algunas: " + " · ".join(str(x) for x in _errs))
            else:
                st.session_state.pop("sw_edit_mf", None)
                st.toast("Características guardadas.")
                st.rerun()
    elif not _advanced:
        st.caption("Este producto no tiene características ni definiciones de metacampos en la tienda.")

    # Avanzados (referencias / imágenes / listas / JSON): Image, video reels, etc.
    # Se muestran (incluso vacíos) para que no "falten"; su contenido son referencias
    # internas de Shopify, así que acá van en solo lectura (edítalos en Shopify).
    if _advanced:
        with st.expander(f"Campos avanzados · {len(_advanced)} (imágenes / videos / referencias)"):
            st.caption("Campos como Image o video reels guardan referencias internas de Shopify "
                       "(archivos/medios). Se muestran para consultarlos; para cambiar su contenido, "
                       "edítalos en Shopify (así no se rompen).")
            for m in _advanced:
                _mid = m.get("id")
                _ns = m.get("namespace") or ""
                _key = m.get("key") or ""
                _nk = f"{_ns}__{_key}"
                _val = str(m.get("value", "") or "")
                _ac1, _ac2 = st.columns([5, 0.7], vertical_alignment="center")
                with _ac1:
                    st.markdown(
                        f'<div style="font-weight:700;color:#334155;font-size:0.82rem;">'
                        f'{_he(m.get("name") or _mf_label(m))}'
                        f'<span style="font-size:0.62rem;color:#94a3b8;font-weight:600;"> · '
                        f'{_he(_ns)}.{_he(_key)}</span></div>', unsafe_allow_html=True)
                    st.text_input("v", value=(_val[:300] if _val else "— sin completar —"),
                                  disabled=True, key=f"sw_ed_mfro_{_nk}", label_visibility="collapsed")
                with _ac2:
                    if _mid and st.button("", icon=":material/delete:", key=f"sw_ed_mfrodel_{_nk}",
                                          use_container_width=True, help="Vaciar este campo"):
                        with st.spinner("Eliminando…"):
                            _ok, _e = _shop.eliminar_metafield(pid, _mid)
                        if _ok:
                            st.session_state.pop("sw_edit_mf", None)
                            st.toast("Campo eliminado.")
                            st.rerun()
                        else:
                            st.error(_e)

    with st.expander("➕ Agregar característica"):
        _nc1, _nc2, _nc3 = st.columns([1.2, 1.6, 1.4])
        with _nc1:
            _ns = st.text_input("Namespace", value="custom", key="sw_ed_mfns",
                                help="Agrupador. 'custom' es el habitual.")
        with _nc2:
            _key = st.text_input("Clave (key)", key="sw_ed_mfkey", placeholder="metros_cuadrados")
        with _nc3:
            _tlbl = st.selectbox("Tipo", list(_MF_TIPOS.keys()), key="sw_ed_mftipo")
        _tval = _MF_TIPOS[_tlbl]
        if _tval == "boolean":
            _newv = st.checkbox("Valor (marcado = Sí)", key="sw_ed_mfval_b")
        elif _tval == "number_integer":
            _newv = st.number_input("Valor", step=1, value=0, key="sw_ed_mfval_i")
        elif _tval == "number_decimal":
            _newv = st.number_input("Valor", step=0.1, value=0.0, format="%.2f", key="sw_ed_mfval_d")
        elif _tval == "multi_line_text_field":
            _newv = st.text_area("Valor", key="sw_ed_mfval_t", height=80)
        else:
            _newv = st.text_input("Valor", key="sw_ed_mfval_s")
        if st.button("Agregar característica", key="sw_ed_mfadd", type="primary",
                     disabled=not (_key or "").strip(), icon=":material/add:"):
            with st.spinner("Agregando…"):
                _ok, _e = _shop.crear_metafield(pid, (_ns or "custom").strip(), _key.strip(),
                                                _tval, _mf_serialize(_tval, _newv))
            if _ok:
                st.session_state.pop("sw_edit_mf", None)
                for _k in ("sw_ed_mfkey", "sw_ed_mfval_s", "sw_ed_mfval_t", "sw_ed_mfval_i",
                           "sw_ed_mfval_d", "sw_ed_mfval_b"):
                    st.session_state.pop(_k, None)
                st.toast("Característica agregada.")
                st.rerun()
            else:
                st.error(_e)
