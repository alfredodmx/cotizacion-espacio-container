"""
Tab INVENTARIO — maestro de stock propio.

Ingreso de productos en stock: **categoría → ítem** salen de la Excel activa
(hoja 'BD Total', misma fuente que REGISTRO DE COMPRA), + cantidad, unidad, hasta
5 fotos, estado de calidad 1-10, observación y ubicación. Al guardar se registra
automáticamente quién lo hizo y la fecha/hora (Chile). Listado con búsqueda,
edición y baja lógica.

Acceso: root, admin y operacion (operador).
"""
import io
import json
import base64
import html as _html
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

from views.layout import render_page_header
from repositories.inventario_repo import (
    fetch_categorias_items, guardar_inventario, listar_inventario,
    obtener_inventario, actualizar_inventario, eliminar_inventario,
    UNIDADES, MAX_FOTOS,
)

_ROLES_OK = ("root", "admin", "operacion")

_INV_CSS = """
<style>
/* ── Formulario en modal NATIVO st.dialog, estilizado como panel derecho (drawer) ──
   Usamos st.dialog (no un contenedor recolocado por CSS) porque Streamlit mide el
   ancho de los widgets contra el dialog → no se salen; y apila los dropdowns bien. */
div[data-testid="stDialog"] > div{align-items:flex-start!important;justify-content:flex-end!important;}
div[data-testid="stDialog"] div[role="dialog"]{position:fixed!important;top:65px!important;
  right:0!important;left:auto!important;bottom:auto!important;transform:none!important;margin:0!important;
  height:calc(100vh - 65px)!important;max-height:calc(100vh - 65px)!important;background:#fff!important;
  border-radius:0!important;box-shadow:none!important;overflow-y:auto!important;overflow-x:hidden!important;}
/* El CSS global pinta el borderWrapper interno como tarjeta blanca CON SOMBRA (se
   veía un contenedor blanco sombreado que no cubría todo). Lo neutralizamos: el
   único blanco es el propio dialog, sin sombra. */
div[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"]{
  background:transparent!important;border:none!important;box-shadow:none!important;border-radius:0!important;}
/* Título del dialog: tipografía de títulos (Montserrat 700 uppercase) + icono SVG. */
div[data-testid="stDialog"] div[role="dialog"] > div:first-child{
  font-family:'Montserrat',sans-serif!important;font-weight:700!important;font-size:0.92rem!important;
  letter-spacing:0.05em!important;text-transform:uppercase!important;color:#0f172a!important;
  display:flex!important;align-items:center!important;gap:9px!important;}
div[data-testid="stDialog"] div[role="dialog"] > div:first-child::before{
  content:'';flex:0 0 auto;width:18px;height:18px;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%232563eb' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 5H4a1 1 0 0 0-1 1v3a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V6a1 1 0 0 0-1-1Z'/%3E%3Cpath d='M4 10v9a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-9'/%3E%3Cline x1='10' y1='14' x2='14' y2='14'/%3E%3C/svg%3E") no-repeat center/contain;}
/* Widgets internos del formulario (dentro del dialog). */
div[data-testid="stDialog"] [data-testid="stSlider"]{padding:0 4px;}
div[data-testid="stDialog"] [data-testid="stFileUploaderDropzone"]{padding:8px 14px;}
div[data-testid="stDialog"] [data-testid="stFileUploaderFile"]{display:none!important;}
/* Botón "Guardar en inventario": ~320px, centrado y responsivo. */
div[data-testid="stDialog"] [class*="st-key-inv_guardar"]{width:100%!important;}
div[data-testid="stDialog"] [class*="st-key-inv_guardar"] [data-testid="stButton"]{
  display:flex!important;justify-content:center!important;width:100%!important;}
div[data-testid="stDialog"] [class*="st-key-inv_guardar"] button{width:100%!important;max-width:320px!important;}

/* Grilla de miniaturas: flex-wrap (responsivo), papelera flotante en la esquina y
   zoom en hover (lupa). El clic lo maneja el handler del iframe. */
.inv-grid{display:flex;flex-wrap:wrap;gap:12px;margin-top:6px;}
.inv-thumb{position:relative;width:100px;height:100px;border-radius:10px;overflow:hidden;
  border:1.5px solid #e2e8f0;flex:0 0 auto;background:#f1f5f9;}
.inv-thumb img{width:100%;height:100%;object-fit:cover;display:block;}
.inv-zoom{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  color:#fff;background:rgba(15,23,42,0);opacity:0;cursor:zoom-in;z-index:2;
  transition:opacity .18s,background .18s;}
.inv-thumb:hover .inv-zoom{opacity:1;background:rgba(15,23,42,.45);}
.inv-del{position:absolute;top:5px;right:5px;width:24px;height:24px;border-radius:7px;
  display:flex;align-items:center;justify-content:center;background:rgba(220,38,38,.95);
  color:#fff;cursor:pointer;opacity:0;z-index:3;box-shadow:0 2px 6px rgba(0,0,0,.28);
  transition:opacity .18s,transform .18s;}
.inv-thumb:hover .inv-del{opacity:1;}
.inv-del:hover{background:#b91c1c;transform:scale(1.08);}
@media (hover:none){.inv-del{opacity:1!important;}}

/* ── Tabla de resultados (estilo COTIZACIONES vía .resultados-table global) ── */
.inv-tbl-wrap{overflow-x:auto;border-radius:14px;border:1px solid #e6e9f4;
  box-shadow:0 3px 16px rgba(30,36,71,.06);background:#fff;}
.inv-tbl-wrap .resultados-table{margin:0!important;border-radius:0!important;box-shadow:none!important;
  min-width:900px;white-space:nowrap;}
.inv-tbl-wrap .resultados-table td{font-family:Montserrat,sans-serif;}
.inv-act{cursor:pointer;display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;
  border-radius:8px;color:#64748b;transition:background .15s,color .15s;}
.inv-act:hover{background:#eef2ff;color:#2563eb;}
.inv-act-del:hover{background:#fef2f2;color:#dc2626;}
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


def _fid(f):
    """Identidad estable de un archivo subido (para excluirlo sin reordenar)."""
    return f"{getattr(f, 'name', '')}_{getattr(f, 'size', 0)}"


@st.cache_data(ttl=600, show_spinner=False)
def _thumb_b64(data: bytes, mime: str = "image/jpeg") -> str:
    """Miniatura data-URI (~200px, JPEG q70) para previsualizar antes de guardar.
    Cacheada por bytes (los params NO llevan '_' inicial para que sí se hasheen)
    y así no re-procesar en cada rerun. Fallback: bytes crudos."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((200, 200))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=70)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return f"data:{mime};base64," + base64.b64encode(data).decode()


@st.cache_data(ttl=600, show_spinner=False)
def _preview_b64(data: bytes, mime: str = "image/jpeg") -> str:
    """Imagen ~1000px (JPEG q82) para el lightbox 'ver en grande'. Cacheada."""
    try:
        from PIL import Image, ImageOps
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((1000, 1000))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return f"data:{mime};base64," + base64.b64encode(data).decode()


# SVG inline para la grilla de fotos (papelera flotante + lupa de zoom).
_SVG_TRASH = ('<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/>'
              '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
              '<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>')
_SVG_ZOOM = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/>'
             '<path d="m21 21-4.3-4.3"/><line x1="11" y1="8" x2="11" y2="14"/>'
             '<line x1="8" y1="11" x2="14" y2="11"/></svg>')

# Handler (iframe height=0): delegación de clicks en el doc PADRE para zoom
# (lightbox client-side) y quitar foto (bridge _inv_fcmd → Python). Se re-bindea
# en cada run (el iframe se recrea → el listener viejo muere).
_INV_FOTOS_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var PREV=__PREV__;
  function fire(action, fid){
    var inp=D.querySelector('.st-key-_inv_fcmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, action+'|'+fid+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  function lightbox(uri){
    var old=D.getElementById('inv-lightbox'); if(old) old.remove();
    var ov=D.createElement('div'); ov.id='inv-lightbox';
    ov.style.cssText='position:fixed;inset:0;z-index:2147483000;background:rgba(5,12,28,.86);'+
      'display:flex;align-items:center;justify-content:center;padding:30px;cursor:zoom-out;'+
      'animation:invLbIn .18s ease;';
    var im=D.createElement('img'); im.src=uri;
    im.style.cssText='max-width:92vw;max-height:92vh;border-radius:12px;box-shadow:0 24px 70px rgba(0,0,0,.55);';
    ov.appendChild(im);
    function close(){ ov.remove(); if(W._invEsc){D.removeEventListener('keydown',W._invEsc);W._invEsc=null;} }
    ov.addEventListener('click', close);
    if(W._invEsc){D.removeEventListener('keydown',W._invEsc);}
    W._invEsc=function(e){ if(e.key==='Escape') close(); };
    D.addEventListener('keydown', W._invEsc);
    D.body.appendChild(ov);
    if(!D.getElementById('inv-lb-kf')){var s=D.createElement('style');s.id='inv-lb-kf';
      s.textContent='@keyframes invLbIn{from{opacity:0}to{opacity:1}}';D.head.appendChild(s);}
  }
  if(W._invClickH){ D.removeEventListener('click', W._invClickH, true); }
  W._invClickH=function(ev){
    var t=ev.target; if(!t||!t.closest) return;
    var d=t.closest('[data-inv-del]');
    if(d){ ev.preventDefault(); ev.stopPropagation(); fire('remove', d.getAttribute('data-inv-del')); return; }
    var z=t.closest('[data-inv-zoom]');
    if(z){ ev.preventDefault(); ev.stopPropagation(); var f=z.getAttribute('data-inv-zoom'); if(PREV[f]) lightbox(PREV[f]); return; }
  };
  D.addEventListener('click', W._invClickH, true);
})();
</script>"""

_SVG_EDIT = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/>'
             '<path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>')
_SVG_TRASH16 = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/>'
                '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
                '<line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/></svg>')

# Handler de la tabla (iframe height=0): menú contextual (click derecho) con
# Ver fotos / Editar / Eliminar + galería + clicks de la columna Acciones. Todo
# vía bridge _inv_tcmd → Python. Re-bindea cada run. FOTOS = {id: [urls]}.
_INV_TABLE_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var FOTOS=__FOTOS__;
  var EYE='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>';
  var PENCIL='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/></svg>';
  var TRASH='<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>';
  function fire(action, id){
    var inp=D.querySelector('.st-key-_inv_tcmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, action+'|'+id+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  function closeMenu(){ var m=D.getElementById('inv-ctxmenu'); if(m) m.remove(); }
  function gallery(urls){
    var old=D.getElementById('inv-gallery'); if(old) old.remove();
    var ov=D.createElement('div'); ov.id='inv-gallery';
    ov.style.cssText='position:fixed;inset:0;z-index:2147483200;background:rgba(5,12,28,.92);display:flex;align-items:center;justify-content:center;padding:26px;cursor:zoom-out;';
    var grid=D.createElement('div');
    grid.style.cssText='display:flex;flex-wrap:wrap;gap:14px;align-items:center;justify-content:center;max-width:94vw;max-height:88vh;overflow:auto;';
    urls.forEach(function(u){
      var im=D.createElement('img'); im.src=u;
      im.style.cssText='max-width:'+(urls.length>1?'44vw':'88vw')+';max-height:84vh;border-radius:12px;box-shadow:0 18px 50px rgba(0,0,0,.5);object-fit:contain;background:#0b1020;';
      grid.appendChild(im);
    });
    ov.appendChild(grid);
    function close(){ ov.remove(); if(W._invGalEsc){D.removeEventListener('keydown',W._invGalEsc);W._invGalEsc=null;} }
    ov.addEventListener('click', close);
    if(W._invGalEsc){D.removeEventListener('keydown',W._invGalEsc);}
    W._invGalEsc=function(e){ if(e.key==='Escape') close(); };
    D.addEventListener('keydown', W._invGalEsc);
    D.body.appendChild(ov);
  }
  function menuItem(m,label,icon,color,disabled,cb){
    var b=D.createElement('button');
    b.style.cssText='display:flex;align-items:center;gap:10px;width:100%;background:transparent;border:none;border-radius:8px;padding:9px 11px;cursor:'+(disabled?'default':'pointer')+';text-align:left;font-family:Montserrat,sans-serif;font-size:.8rem;font-weight:600;color:'+(disabled?'#cbd5e1':color)+';';
    b.innerHTML='<span style="display:inline-flex;flex:0 0 auto;">'+icon+'</span><span>'+label+'</span>';
    if(!disabled){
      b.addEventListener('mouseenter',function(){b.style.background='#f1f5f9';});
      b.addEventListener('mouseleave',function(){b.style.background='transparent';});
      b.addEventListener('click',function(ev){ev.stopPropagation();closeMenu();cb();});
    }
    m.appendChild(b);
  }
  function buildMenu(x,y,id){
    closeMenu();
    var urls=FOTOS[id]||[];
    var m=D.createElement('div'); m.id='inv-ctxmenu';
    m.style.cssText='position:fixed;z-index:2147483400;background:#fff;border:1px solid #e5e9f2;border-radius:12px;box-shadow:0 14px 40px rgba(15,23,42,.24);padding:6px;min-width:198px;';
    menuItem(m,'Ver fotos ('+urls.length+')',EYE,'#2563eb',urls.length===0,function(){gallery(urls);});
    menuItem(m,'Editar',PENCIL,'#334155',false,function(){fire('edit',id);});
    var sep=D.createElement('div'); sep.style.cssText='height:1px;background:#eef1f6;margin:5px 4px;'; m.appendChild(sep);
    menuItem(m,'Eliminar',TRASH,'#dc2626',false,function(){fire('del',id);});
    D.body.appendChild(m);
    var r=m.getBoundingClientRect(), px=x, py=y;
    if(px+r.width>W.innerWidth) px=W.innerWidth-r.width-8;
    if(py+r.height>W.innerHeight) py=W.innerHeight-r.height-8;
    m.style.left=px+'px'; m.style.top=py+'px';
  }
  if(W._invTblH){ D.removeEventListener('click', W._invTblH, true); }
  W._invTblH=function(ev){
    var t=ev.target; if(!t||!t.closest) return;
    if(!t.closest('#inv-ctxmenu')) closeMenu();
    var e=t.closest('[data-inv-edit]');
    if(e){ ev.preventDefault(); ev.stopPropagation(); fire('edit', e.getAttribute('data-inv-edit')); return; }
    var d=t.closest('[data-inv-delrow]');
    if(d){ ev.preventDefault(); ev.stopPropagation(); fire('del', d.getAttribute('data-inv-delrow')); return; }
  };
  D.addEventListener('click', W._invTblH, true);
  if(W._invCtxH){ D.removeEventListener('contextmenu', W._invCtxH, true); }
  W._invCtxH=function(ev){
    var tr=ev.target&&ev.target.closest?ev.target.closest('.inv-tbl-wrap tbody tr[data-inv-id]'):null;
    if(!tr) return;
    ev.preventDefault();
    buildMenu(ev.clientX, ev.clientY, tr.getAttribute('data-inv-id'));
  };
  D.addEventListener('contextmenu', W._invCtxH, true);
  if(W._invScrollH){ W.removeEventListener('scroll', W._invScrollH, true); }
  W._invScrollH=function(){ closeMenu(); };
  W.addEventListener('scroll', W._invScrollH, true);
})();
</script>"""

@st.cache_data(ttl=60, show_spinner=False)
def _inv_all():
    """Lista completa de inventario activo (cacheada; se limpia al mutar)."""
    return listar_inventario("")


# ── Formulario (ingreso / edición) ───────────────────────────────────────────

def _render_form_body(cat_items, rec, rol):
    """Cuerpo del formulario (dentro del st.dialog-drawer). El título y la X los
    aporta el propio dialog."""
    editing = rec is not None
    sfx = f"e{rec['id']}" if editing else f"n{st.session_state.get('_inv_nonce', 0)}"

    if True:
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
                                  value=rec.get("ubicacion", "") if editing else "oficina colina",
                                  placeholder="oficina colina",
                                  key=f"inv_ubic_{sfx}")

        _cal0 = int(rec["calidad"]) if editing and rec.get("calidad") else 7
        _cal_cur = int(st.session_state.get(f"inv_cal_{sfx}", _cal0))
        _bg, _fg = _cal_colors(_cal_cur)
        st.markdown(
            '<div style="display:flex;align-items:center;justify-content:space-between;'
            'margin:2px 0 2px;"><span style="font-size:0.8rem;font-weight:600;color:#5a6080;'
            'text-transform:uppercase;letter-spacing:.04em;">Estado de calidad '
            '<span style="color:#a7aec9;text-transform:none;font-weight:500;">· 1 peor → 10 mejor</span>'
            f'</span><span style="background:{_bg};color:{_fg};font-family:Montserrat,sans-serif;'
            'font-weight:800;font-size:0.72rem;padding:3px 13px;border-radius:20px;'
            f'letter-spacing:.03em;">{_cal_cur}/10 · {_cal_label(_cal_cur)}</span></div>',
            unsafe_allow_html=True)
        calidad = st.slider("Estado de calidad", 1, 10, value=_cal0,
                            key=f"inv_cal_{sfx}", label_visibility="collapsed")

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

        # ── Fotos: uploader + previsualización 100x100 con zoom y quitar ──
        _cap = MAX_FOTOS - (len(fotos_conservar) if editing else 0)
        _fnonce = st.session_state.get(f"inv_fnonce_{sfx}", 0)
        _excl = st.session_state.setdefault(f"inv_fexcl_{sfx}", set())
        # Bridge oculto: la grilla HTML escribe "remove|<fid>|ts" para quitar 1 foto.
        st.markdown('<style>.st-key-_inv_fcmd{position:absolute!important;left:-9999px!important;'
                    'top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}</style>',
                    unsafe_allow_html=True)
        st.text_input('fcmd', key='_inv_fcmd', label_visibility='collapsed')
        _fcmd = str(st.session_state.get('_inv_fcmd', '') or '')
        if _fcmd and '|' in _fcmd:
            _fp = _fcmd.split('|')
            if _fp[-1] != st.session_state.get('_inv_fcmd_ts') and _fp[0] == 'remove' and len(_fp) >= 3:
                st.session_state['_inv_fcmd_ts'] = _fp[-1]
                _excl.add('|'.join(_fp[1:-1]))
                st.session_state[f"inv_fexcl_{sfx}"] = _excl
        _lbl = (f"Agregar fotos (quedan {max(0, _cap)} de {MAX_FOTOS})" if editing
                else f"Fotos del producto (hasta {MAX_FOTOS})")
        _raw = st.file_uploader(_lbl, type=["png", "jpg", "jpeg", "webp"],
                                accept_multiple_files=True,
                                key=f"inv_fotos_{sfx}_{_fnonce}")
        # Poda exclusiones obsoletas y filtra las que el usuario quitó.
        _raw_ids = {_fid(f) for f in (_raw or [])}
        _excl &= _raw_ids
        st.session_state[f"inv_fexcl_{sfx}"] = _excl
        fotos = [f for f in (_raw or []) if _fid(f) not in _excl]
        if len(fotos) > _cap:
            st.warning(f"Solo se guardarán las primeras {max(0, _cap)} fotos "
                       f"(máximo {MAX_FOTOS}).")
            fotos = fotos[:max(0, _cap)]

        if fotos:
            hc1, hc2 = st.columns([3, 1])
            with hc1:
                st.markdown('<div style="font-size:0.72rem;color:#94a3b8;font-weight:700;'
                            'text-transform:uppercase;letter-spacing:.05em;padding-top:8px;">'
                            f'{len(fotos)} foto(s) seleccionada(s)</div>',
                            unsafe_allow_html=True)
            with hc2:
                if st.button("Eliminar todas", use_container_width=True,
                             key=f"inv_delall_{sfx}"):
                    st.session_state[f"inv_fnonce_{sfx}"] = _fnonce + 1
                    st.session_state[f"inv_fexcl_{sfx}"] = set()
                    st.rerun()
            # Grilla HTML: cada miniatura con papelera flotante (esquina) + zoom en
            # hover (lightbox client-side). Papelera → bridge _inv_fcmd → Python.
            _prev_map, _cells = {}, ""
            for f in fotos:
                _b = f.getvalue()
                _mime = getattr(f, "type", "image/jpeg")
                _fidv = _fid(f)
                _prev_map[_fidv] = _preview_b64(_b, _mime)
                _fa = _html.escape(_fidv, quote=True)
                _cells += (
                    '<div class="inv-thumb">'
                    f'<img src="{_thumb_b64(_b, _mime)}" alt="">'
                    f'<div class="inv-zoom" data-inv-zoom="{_fa}" title="Ver en grande">{_SVG_ZOOM}</div>'
                    f'<div class="inv-del" data-inv-del="{_fa}" title="Quitar foto">{_SVG_TRASH}</div>'
                    '</div>')
            st.markdown(f'<div class="inv-grid">{_cells}</div>', unsafe_allow_html=True)
            components.html(_INV_FOTOS_JS.replace('__PREV__', json.dumps(_prev_map)),
                            height=0)

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
                                key=f"inv_guardar_{sfx}")
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


def _tabla_html(data):
    """HTML de la tabla de stock (clase global .resultados-table = estilo COTIZACIONES)."""
    rows = ""
    for d in data:
        fotos = d.get("fotos") or []
        thumb = (f'<img src="{_esc(fotos[0])}" style="width:44px;height:44px;object-fit:cover;'
                 'border-radius:8px;border:1px solid #e2e8f0;display:block;">'
                 if fotos else f'<span style="color:#cbd5e1;">{_IC_IMG}</span>')
        cal = d.get("calidad")
        _bg, _fg = _cal_colors(cal)
        cal_badge = (f'<span style="background:{_bg};color:{_fg};font-weight:800;font-size:0.72rem;'
                     f'padding:2px 9px;border-radius:20px;">{cal}/10</span>') if cal else "—"
        obs = d.get("observacion", "")
        obs_html = (f'<div style="font-size:0.68rem;color:#94a3b8;font-weight:500;white-space:normal;'
                    f'max-width:230px;margin-top:2px;">{_esc(obs)}</div>') if obs else ""
        rows += (
            f'<tr data-inv-id="{_esc(d["id"])}" style="cursor:context-menu;">'
            f'<td>{thumb}</td>'
            f'<td style="font-weight:700;color:#0f172a;text-transform:uppercase;letter-spacing:.02em;">'
            f'{_esc(d.get("item",""))}{obs_html}</td>'
            f'<td><span style="background:#e0e7ff;color:#4338ca;font-weight:700;font-size:0.68rem;'
            f'padding:2px 9px;border-radius:20px;text-transform:uppercase;">{_esc(d.get("categoria",""))}</span></td>'
            f'<td style="font-weight:700;">{_fmt_cant(d.get("cantidad"))} '
            f'<span style="color:#94a3b8;font-weight:600;">{_esc(d.get("unidad",""))}</span></td>'
            f'<td>{cal_badge}</td>'
            f'<td>{_esc(d.get("ubicacion","")) or "—"}</td>'
            f'<td>{_esc(d.get("creado_por_nombre") or d.get("creado_por_email") or "—")}</td>'
            f'<td style="color:#64748b;">{_fmt_fecha(d.get("fecha_modificacion") or d.get("fecha_creacion"))}</td>'
            '<td style="white-space:nowrap;">'
            f'<span class="inv-act inv-act-edit" data-inv-edit="{_esc(d["id"])}" title="Editar">{_SVG_EDIT}</span>'
            f'<span class="inv-act inv-act-del" data-inv-delrow="{_esc(d["id"])}" title="Eliminar">{_SVG_TRASH16}</span>'
            '</td></tr>')
    return (
        '<div class="inv-tbl-wrap"><table class="resultados-table"><thead><tr>'
        '<th>Foto</th><th>Producto</th><th>Categoría</th><th>Stock</th><th>Calidad</th>'
        '<th>Ubicación</th><th>Registró</th><th>Fecha</th><th>Acciones</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>')


def _render_tabla(rol):
    """Barra superior (buscar + Ingresar producto) + tabla de stock + handler de fila."""
    tb1, tb2 = st.columns([3, 1])
    with tb1:
        busqueda = st.text_input("Buscar en el stock", key="_inv_busca",
                                 placeholder="Producto, categoría, bodega…",
                                 label_visibility="collapsed")
    with tb2:
        if st.button("Ingresar producto", type="primary", use_container_width=True,
                     icon=":material/add:", key="inv_open_form"):
            st.session_state.pop("_inv_edit", None)
            st.session_state["_inv_open"] = True
            st.rerun()

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
        st.markdown('<div style="text-align:center;color:#94a3b8;padding:34px;'
                    'font-family:Montserrat,sans-serif;font-weight:600;border:1px dashed #d7ddf0;'
                    'border-radius:14px;">Sin productos en stock. Pulsa '
                    '<b>Ingresar producto</b> para agregar el primero.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(_tabla_html(data), unsafe_allow_html=True)

    # Bridge oculto + handler (menú contextual: ver fotos/editar/eliminar + acciones).
    st.markdown('<style>.st-key-_inv_tcmd{position:absolute!important;left:-9999px!important;'
                'top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}</style>',
                unsafe_allow_html=True)
    st.text_input("tcmd", key="_inv_tcmd", label_visibility="collapsed")
    _fotos_map = {d["id"]: (d.get("fotos") or [])[:MAX_FOTOS] for d in data}
    components.html(_INV_TABLE_JS.replace("__FOTOS__", json.dumps(_fotos_map, ensure_ascii=False)),
                    height=0)


def _render_del_confirm():
    """Doble confirmación de borrado (dos preguntas). Disparada por el menú
    contextual o el icono eliminar de la fila (ambos setean _inv_del_confirm)."""
    _cid2 = st.session_state.get("_inv_del_confirm2")
    _cid1 = st.session_state.get("_inv_del_confirm")

    if _cid2:   # ── 2ª pregunta ──
        _rec = obtener_inventario(_cid2)
        _nombre = (_rec.get("item") if _rec else None) or "este producto"

        @st.dialog("Confirmación final")
        def _dlg2():
            st.markdown(f"Vas a **eliminar definitivamente** «{_esc(_nombre)}» del inventario. "
                        "Se dará de baja y dejará de aparecer en el stock. ¿Continuar?")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Sí, eliminar", type="primary", use_container_width=True,
                             key="_inv_del2_yes"):
                    ok, err = eliminar_inventario(_cid2)
                    st.session_state.pop("_inv_del_confirm2", None)
                    if ok:
                        _inv_all.clear()
                        st.session_state["_inv_toast"] = "Producto eliminado del stock."
                    else:
                        st.session_state["_inv_error"] = f"No se pudo eliminar: {err}"
                    st.rerun()
            with d2:
                if st.button("Cancelar", use_container_width=True, key="_inv_del2_no"):
                    st.session_state.pop("_inv_del_confirm2", None)
                    st.rerun()
        _dlg2()
        return

    if _cid1:   # ── 1ª pregunta ──
        _rec = obtener_inventario(_cid1)
        _nombre = (_rec.get("item") if _rec else None) or "este producto"

        @st.dialog("Eliminar del inventario")
        def _dlg1():
            st.markdown(f"¿Seguro que quieres eliminar **{_esc(_nombre)}** del stock?")
            d1, d2 = st.columns(2)
            with d1:
                if st.button("Sí, continuar", type="primary", use_container_width=True,
                             key="_inv_del1_yes"):
                    st.session_state["_inv_del_confirm2"] = _cid1
                    st.session_state.pop("_inv_del_confirm", None)
                    st.rerun()
            with d2:
                if st.button("Cancelar", use_container_width=True, key="_inv_del1_no"):
                    st.session_state.pop("_inv_del_confirm", None)
                    st.rerun()
        _dlg1()


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

    # Acciones de la tabla (editar / eliminar) escritas por el handler de fila.
    _tcmd = str(st.session_state.get("_inv_tcmd", "") or "")
    if _tcmd and "|" in _tcmd:
        _tp = _tcmd.split("|")
        if _tp[-1] != st.session_state.get("_inv_tcmd_ts"):
            st.session_state["_inv_tcmd_ts"] = _tp[-1]
            _act, _tid = _tp[0], "|".join(_tp[1:-1])
            if _act == "edit":
                st.session_state["_inv_edit"] = _tid
                st.session_state["_inv_open"] = True   # one-shot: abre el dialog
            elif _act == "del":
                st.session_state["_inv_del_confirm"] = _tid

    # Vista principal: barra + tabla de stock (estilo COTIZACIONES).
    _render_tabla(_rol)
    _render_del_confirm()

    # Formulario en modal-drawer (st.dialog). One-shot: se abre UNA vez cuando
    # _inv_open está set (botón Ingresar o editar de fila); Streamlit lo mantiene
    # abierto en los reruns internos hasta que el usuario cierre o guarde.
    # Guard: no abrir a la vez que un dialog de confirmación (un solo dialog/run).
    _del_active = bool(st.session_state.get("_inv_del_confirm")
                       or st.session_state.get("_inv_del_confirm2"))
    if st.session_state.get("_inv_open") and not _del_active:
        st.session_state.pop("_inv_open", None)
        _eid = st.session_state.get("_inv_edit")
        _rec = obtener_inventario(_eid) if _eid else None
        if _eid and not _rec:
            st.session_state.pop("_inv_edit", None)
            _rec = None
        _title = "Editar producto" if _rec else "Ingresar producto"

        @st.dialog(_title, width="large")
        def _form_dialog():
            _render_form_body(cat_items, _rec, _rol)

        _form_dialog()
