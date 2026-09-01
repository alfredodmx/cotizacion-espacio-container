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
.st-key-sw_editcmd,.st-key-sw_savecmd{position:absolute!important;left:-9999px!important;top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}
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
  cursor:grab;user-select:none;}
.ed-img.dragging{opacity:.4;cursor:grabbing;}
.ed-img img{width:100%;height:100%;object-fit:cover;display:block;pointer-events:none;}
.ed-img .ed-del{position:absolute;top:5px;right:5px;width:26px;height:26px;border-radius:50%;border:none;
  background:rgba(15,23,42,.62);color:#fff;cursor:pointer;display:none;align-items:center;justify-content:center;padding:0;}
.ed-img:hover .ed-del{display:flex;}
.ed-img .ed-del svg{width:14px;height:14px;}
.ed-img .ed-del:hover{background:#dc2626;}
.ed-img .ed-princ{position:absolute;bottom:5px;left:5px;font-family:Montserrat,sans-serif;font-weight:800;font-size:8.5px;
  text-transform:uppercase;letter-spacing:.04em;background:#5b7cfa;color:#fff;border-radius:5px;padding:2px 6px;display:none;}
.ed-img.is-princ .ed-princ{display:block;}
.ed-img.ed-deleted{opacity:.32;filter:grayscale(1);}
.ed-img.ed-deleted .ed-del{display:flex;background:#dc2626;}
.ed-img.ed-new::after{content:'NUEVA';position:absolute;top:5px;left:5px;font-family:Montserrat;font-weight:800;font-size:8px;
  background:#16a34a;color:#fff;border-radius:5px;padding:2px 5px;letter-spacing:.03em;}
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
<div class="ed-head">
  <div class="ed-title-mini" id="ttl">__TITLE__</div>
  <button class="ed-save" id="save" type="button">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/></svg>
    <span id="savelbl">Guardar y publicar</span>
  </button>
</div>
<div class="ed-grid">
  <div class="ed-main">
    <div class="ed-card">
      <div class="ed-lbl">Fotos <small>· arrastra para ordenar · la 1ª es la principal · pasa el mouse para eliminar</small></div>
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
        <div id="pcprog" class="ed-pcprog"><div id="pcbar" class="ed-pcbar"></div></div>
        <button type="button" id="pcup" class="ed-pcup">Subir</button>
      </div>
    </div>
    <div class="ed-card">
      <label class="ed-flbl">Título</label>
      <input class="ed-in" id="f_title" type="text" value="__TITLE_ATTR__">
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
    if(!first && !t.classList.contains('ed-deleted')) first=t;
  });
  if(first) first.classList.add('is-princ');
}
grid.addEventListener('click',function(e){
  var d=e.target.closest?e.target.closest('.ed-del'):null; if(!d) return;
  var tile=d.closest('.ed-img'); if(!tile) return;
  if(tile.getAttribute('data-new')==='1'){ tile.remove(); }   // nueva → se descarta
  else { tile.classList.toggle('ed-deleted'); }
  refreshPrincipal();
});
var dragEl=null;
grid.addEventListener('dragstart',function(e){
  var t=e.target.closest('.ed-img'); if(!t) return; dragEl=t;
  e.dataTransfer.effectAllowed='move'; setTimeout(function(){t.classList.add('dragging');},0);
});
grid.addEventListener('dragend',function(){ if(dragEl)dragEl.classList.remove('dragging'); dragEl=null; refreshPrincipal(); });
grid.addEventListener('dragover',function(e){
  e.preventDefault(); if(!dragEl) return;
  var t=e.target.closest('.ed-img'); if(!t||t===dragEl) return;
  var r=t.getBoundingClientRect(); var before=(e.clientY < r.top + r.height/2) || (Math.abs(e.clientY-(r.top+r.height/2))<r.height/2 && e.clientX < r.left + r.width/2);
  grid.insertBefore(dragEl, before ? t : t.nextSibling);
});

/* ── Agregar foto por URL ── */
function addUrl(){
  var inp=doc.getElementById('addurl'); var u=(inp.value||'').trim(); if(!u) return;
  var d=doc.createElement('div'); d.className='ed-img ed-new'; d.setAttribute('draggable','true');
  d.setAttribute('data-new','1'); d.setAttribute('data-src',u);
  d.innerHTML='<img src="'+u.replace(/"/g,'&quot;')+'" alt=""><button type="button" class="ed-del"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg></button><span class="ed-princ">Principal</span>';
  grid.appendChild(d); inp.value=''; syncAdd(); refreshPrincipal();
}
var _addbtn=doc.getElementById('addbtn'), _addurl=doc.getElementById('addurl');
function syncAdd(){ _addbtn.disabled=!(_addurl.value||'').trim(); }
_addurl.addEventListener('input',syncAdd);
_addbtn.addEventListener('click',function(){ if(!this.disabled) addUrl(); });
_addurl.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); addUrl(); }});
syncAdd(); refreshPrincipal();

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
  var image_order=[], image_delete=[], image_add_urls=[];
  [].slice.call(grid.querySelectorAll('.ed-img')).forEach(function(t){
    var id=t.getAttribute('data-id');
    if(t.classList.contains('ed-deleted')){ if(id) image_delete.push(parseInt(id,10)); return; }
    if(t.getAttribute('data-new')==='1'){ image_add_urls.push(t.getAttribute('data-src')); }
    else if(id){ image_order.push(parseInt(id,10)); }
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
    image_order:image_order, image_delete:image_delete, image_add_urls:image_add_urls
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
doc.getElementById('save').addEventListener('click',function(){
  var b=this; b.disabled=true; doc.getElementById('savelbl').textContent='Guardando…';
  fire(JSON.stringify(collect()));
});

/* ── Agregar fotos/videos desde el PC (miniaturas 80x80 + resize/lectura + progreso) ── */
var pcFiles=[];
var pcbtn=doc.getElementById('pcbtn'), pcfile=doc.getElementById('pcfile'),
    pcwrap=doc.getElementById('pcwrap'), pcthumbs=doc.getElementById('pcthumbs'),
    pccount=doc.getElementById('pccount'), pcup=doc.getElementById('pcup'),
    pcprog=doc.getElementById('pcprog'), pcbar=doc.getElementById('pcbar'),
    pcmsg=doc.getElementById('pcmsg');
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
  pcup.textContent='Subir '+pcFiles.length+(pcFiles.length===1?' archivo':' archivos');
  pcwrap.classList.toggle('on', pcFiles.length>0);
  pcbtn.style.display = pcFiles.length ? 'none' : '';   // con archivos: se usa el tile "+"
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
pcup.addEventListener('click',function(){
  if(!pcFiles.length) return;
  var vids=pcFiles.filter(function(f){return f.isVideo;});
  var totV=vids.reduce(function(a,f){return a+f.file.size;},0), CAP=100*1024*1024;
  if(totV>CAP){ pcmsg.textContent='Los videos suman '+(totV/1048576).toFixed(0)+' MB. El máximo es 100 MB por subida — quita alguno o comprímelo (para videos muy pesados, súbelo directo en Shopify).'; pcmsg.style.display='block'; return; }
  var self=this; self.disabled=true; pcprog.classList.add('on'); pcbar.style.width='0%'; if(pcmsg) pcmsg.style.display='none';
  var photos=[], videos=[], done=0, total=pcFiles.length;
  function step(idx){
    if(idx>=pcFiles.length){ self.textContent='Subiendo a la tienda…'; fire(JSON.stringify({op:'upload', files:photos, videos:videos})); return; }
    var it=pcFiles[idx];
    var p = it.isVideo
      ? fileB64(it.file).then(function(b){ if(b) videos.push({name:it.name, mime:(it.file.type||'video/mp4'), b64:b}); })
      : resizeB64(it.file).then(function(b){ if(b) photos.push({name:it.name, b64:b}); });
    p.then(function(){ done++; pcbar.style.width=Math.round(done/total*100)+'%'; step(idx+1); });
  }
  step(0);
});

/* ── Agregar video por enlace (YouTube/Vimeo), estilo igual al de URL de imagen ── */
var addvidbtn=doc.getElementById('addvidbtn'), addvidurl=doc.getElementById('addvidurl');
function syncVid(){ addvidbtn.disabled=!(addvidurl.value||'').trim(); }
function addVid(){
  var u=(addvidurl.value||'').trim(); if(!u) return;
  addvidbtn.disabled=true; addvidbtn.textContent='Agregando…';
  fire(JSON.stringify({op:'video_url', url:u}));
}
addvidurl.addEventListener('input',syncVid);
addvidbtn.addEventListener('click',function(){ if(!this.disabled) addVid(); });
addvidurl.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); addVid(); }});
syncVid();
})();
</script>
</body></html>"""


def _build_editor_form(p, pubs, prod_pubs, cols, cur_cols):
    """Arma el formulario HTML del editor. `pubs`=canales [{id,name}], `prod_pubs`=set
    GIDs publicados, `cols`=colecciones [{id,title}], `cur_cols`=ids seleccionadas.
    Devuelve (html, alto_iframe)."""
    _imgs = p.get("images") or []
    _x = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg>'
    _img_html = ""
    for im in _imgs:
        _src = _he(im.get("src", ""))
        _img_html += (f'<div class="ed-img" draggable="true" data-id="{_he(im.get("id"))}">'
                      f'<img src="{_src}" alt="">'
                      f'<button type="button" class="ed-del">{_x}</button>'
                      '<span class="ed-princ">Principal</span></div>')
    if not _img_html:
        _img_html = '<div class="ed-noimg">Este producto no tiene fotos. Agrega una por URL abajo.</div>'

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

    _title = _he(p.get("title") or "(sin título)")
    _html = (_SW_FORM_TEMPLATE
             .replace("__TITLE_ATTR__", _title).replace("__TITLE__", _title)
             .replace("__IMAGES__", _img_html)
             .replace("__DESC__", _he(p.get("body_html") or ""))
             .replace("__PRICES__", _prices)
             .replace("__STATUS__", _status)
             .replace("__CHANNELS__", _channels)
             .replace("__TYPE__", _he(p.get("product_type") or ""))
             .replace("__VENDOR__", _he(p.get("vendor") or ""))
             .replace("__COLLECTIONS__", _collections))
    # Altura estimada (izquierda vs derecha).
    _img_rows = (len(_imgs) + 3) // 4 if _imgs else 1
    _left = 70 + (_img_rows * 118 + 90) + 300 + (max(1, len(_vars)) * 110 + 60)
    _right = 130 + (max(1, len(pubs or [])) * 44 + 60) + (200 + len(cols or []) * 34)
    _h = 70 + max(_left, _right)
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
    # 5) Fotos: eliminar marcadas → reordenar restantes → agregar nuevas (al final).
    for _iid in data.get("image_delete") or []:
        _ok, _e = _shop.eliminar_imagen(pid, _iid)
        if not _ok:
            _errs.append(_e)
    _order = [i for i in (data.get("image_order") or [])]
    if _order:
        _ok, _e = _shop.reordenar_imagenes(pid, _order)
        if not _ok:
            _errs.append(_e)
    for _url in data.get("image_add_urls") or []:
        if _url:
            _ok, _e = _shop.agregar_imagen(pid, src=_url)
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

    # ── Selector de vista: Tarjetas (por defecto) / Tabla ──
    st.markdown(_SW_VISTA_CSS, unsafe_allow_html=True)
    _vistas = ["Tarjetas", "Tabla"]
    _vicons = {"Tarjetas": ":material/grid_view:", "Tabla": ":material/table_rows:"}
    _vista = st.radio("Vista", _vistas, index=0, key="sw_vista", horizontal=True,
                      label_visibility="collapsed", format_func=lambda v: f"{_vicons.get(v, '')} {v}")

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
                else:                               # guardado completo del formulario
                    with st.spinner("Guardando en Shopify…"):
                        _errs = _guardar_todo(pid, _data)
                    st.session_state["sw_toast"] = (
                        ("Guardado con avisos: " + " · ".join(str(x) for x in _errs[:3]))
                        if _errs else "Cambios publicados en la web.")
                st.session_state.pop("sw_edit_prod", None)
                st.session_state.pop("sw_edit_collects", None)
                st.session_state.pop("sw_edit_prodpubs", None)
                _cargar_productos.clear()
                st.rerun()

    _form_html, _form_h = _build_editor_form(_p, _pubs, _prod_pubs_set, _cols, _cur_cols)
    components.html(_form_html, height=int(_form_h), scrolling=True)

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

    # La sección Videos solo se muestra si el producto YA tiene videos (para verlos y
    # eliminarlos). Para AGREGAR se usa el formulario de arriba (enlace o desde PC).
    if _vid:
        st.markdown(f'<div class="sw-sec">{_ic("video", "#0f172a", 16, 0)}Videos '
                    f'<span style="color:#94a3b8;font-weight:800;">· {len(_vid)}</span></div>',
                    unsafe_allow_html=True)
        st.caption("Videos del producto (agregados por enlace o desde el PC en el formulario de arriba). "
                   "Elimínalos con el botón de cada uno.")
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
