"""
Pestaña CLIENTES (CRM) — maestro de clientes.

FASE 2: SOLO-ROOT. Vistas Pipeline (kanban) / Bandeja (leads) / Maestro (tabla).
- Pipeline y estado se DERIVAN de las cotizaciones (fuente de verdad); solo las
  etapas tempranas (lead_nuevo/contactado) viven en clientes.etapa_manual.
- Click en un cliente (fila del maestro o tarjeta del kanban) → ficha 360 (datos
  + línea de tiempo + presupuestos), vía puente JS→Python.

Condiciones duras: pestaña visible SOLO para root (doble llave: fuera de la
navegación de otros roles en app.py + guard acá). ADITIVA: solo lee lo existente
y escribe en tablas nuevas. No toca el flujo actual.
"""
import html as _html
from datetime import date as _date, datetime as _dt, timedelta as _td

import streamlit as st
import streamlit.components.v1 as components

from views.layout import render_page_header
from repositories.clientes_repo import (
    listar_clientes, crear_cliente, registrar_actividad, listar_actividad,
    backfill_desde_cotizaciones, dedup_key, enriquecer_con_pipeline,
    identidades_compartidas,
    crear_tarea, listar_tareas_cliente, completar_tarea, listar_tareas_pendientes,
    tareas_vencidas_no_notificadas, marcar_notificadas,
    STAGE_LEAD, STAGE_CONTACTADO, STAGE_PRESUPUESTO, STAGE_PROPUESTA,
    STAGE_GANADO, STAGE_PERDIDO,
)
try:
    from utils.notificaciones import notificar_recordatorio
except Exception:   # notificaciones es opcional; si falla, los recordatorios igual se guardan
    def notificar_recordatorio(*a, **k):
        return 0

_ROL_OK = "root"

# Metadatos de cada etapa: (label, color del punto/acento).
_STAGE_ORDER = [STAGE_LEAD, STAGE_CONTACTADO, STAGE_PRESUPUESTO,
                STAGE_PROPUESTA, STAGE_GANADO, STAGE_PERDIDO]
_STAGE_META = {
    STAGE_LEAD:        ("Lead nuevo",        "#888780", "#f1f5f9", "#475569"),
    STAGE_CONTACTADO:  ("Contactado",        "#378ADD", "#e0f2fe", "#0369a1"),
    STAGE_PRESUPUESTO: ("En presupuesto",    "#7F77DD", "#ede9fe", "#6d28d9"),
    STAGE_PROPUESTA:   ("Propuesta enviada", "#EF9F27", "#fef3c7", "#b45309"),
    STAGE_GANADO:      ("Ganado",            "#1D9E75", "#dcfce7", "#15803d"),
    STAGE_PERDIDO:     ("Perdido",           "#94a3b8", "#f1f5f9", "#64748b"),
}


# ── Estilo del selector de vista (igual que las sub-pestañas de OPERACIONES) ───
_CLI_SELECTOR_CSS = """
<style>
.st-key-_cli_view [role="radiogroup"]{gap:0!important;flex-wrap:wrap!important;
  border-bottom:2px solid #e2e6f3!important;margin-bottom:2px!important;padding:0!important;}
.st-key-_cli_view [role="radiogroup"] > label{background:transparent!important;border:none!important;
  border-bottom:3px solid transparent!important;border-radius:0!important;padding:0.85rem 1.6rem!important;
  margin:0 0 -2px 0!important;cursor:pointer!important;color:#7c85b3!important;
  transition:color .2s,border-color .2s!important;}
.st-key-_cli_view [role="radiogroup"] > label:hover{color:#5b7cfa!important;background:rgba(91,124,250,.05)!important;}
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked){color:#5b7cfa!important;
  border-bottom-color:#5b7cfa!important;background:rgba(91,124,250,.06)!important;}
.st-key-_cli_view [role="radiogroup"] > label > div:first-child{display:none!important;}
.st-key-_cli_view [role="radiogroup"] label [data-testid="stMarkdownContainer"] p{
  font-family:'Plus Jakarta Sans',sans-serif!important;font-size:0.88rem!important;font-weight:700!important;
  text-transform:uppercase!important;letter-spacing:0.05em!important;margin:0!important;}
.st-key-_cli_view [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p span{color:#7c85b3!important;}
.st-key-_cli_view [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p span,
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p span{color:#5b7cfa!important;}
.st-key-_cli_view [role="radiogroup"] label span[role="img"][aria-label$=" icon"]{
  font-family:'Material Symbols Rounded'!important;font-weight:400!important;font-size:0.88rem!important;
  text-transform:none!important;letter-spacing:normal!important;}
</style>
"""

_CLI_CSS = """
<style>
.cli-tbl-wrap{overflow-x:auto;border-radius:14px;border:1px solid #e6e9f4;
  box-shadow:0 3px 16px rgba(30,36,71,.06);background:#fff;margin-top:10px;}
.cli-tbl-wrap table{width:100%;border-collapse:collapse;min-width:820px;white-space:nowrap;}
.cli-tbl-wrap thead th{background:linear-gradient(135deg,#1e2447 0%,#2a3060 100%);color:#fff;
  font-family:'Plus Jakarta Sans',sans-serif;font-weight:900;font-size:0.72rem;letter-spacing:.07em;
  text-transform:uppercase;padding:11px 14px;text-align:left;position:sticky;top:0;}
.cli-tbl-wrap tbody td{font-family:Montserrat,sans-serif;font-size:0.82rem;color:#0f172a;
  padding:9px 14px;border-bottom:1px solid #f0f2f8;}
.cli-tbl-wrap tbody tr{cursor:pointer;transition:background .12s;}
.cli-tbl-wrap tbody tr:nth-child(even){background:#f8fafc;}
.cli-tbl-wrap tbody tr:hover{background:#eef4ff!important;}
.cli-pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:0.68rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.03em;}
.cli-sbar{display:flex;align-items:center;gap:9px;background:#fff;border:1px solid #e6e9f4;
  border-radius:12px;padding:9px 13px;box-shadow:0 3px 16px rgba(30,36,71,.06);}
.cli-sbar input{flex:1 1 auto;border:none;outline:none;background:transparent;min-width:0;
  font-family:Montserrat,sans-serif;font-size:.86rem;font-weight:600;color:#0f172a;}
.cli-sbar input::placeholder{color:#94a3b8;font-weight:500;}
.cli-sbar .cli-sico{display:inline-flex;flex:0 0 auto;color:#94a3b8;}
.cli-empty-ph{text-align:center;color:#94a3b8;padding:40px;font-family:Montserrat,sans-serif;
  font-weight:600;border:1px dashed #d7ddf0;border-radius:14px;margin-top:10px;}

/* ── Kanban ── */
.cli-kb-wrap{overflow-x:auto;padding-bottom:8px;margin-top:12px;}
.cli-kb{display:flex;gap:12px;min-width:920px;}
.cli-kb-col{flex:1;min-width:150px;background:#f8fafc;border-radius:12px;padding:10px;}
.cli-kb-hd{display:flex;align-items:center;gap:7px;margin-bottom:10px;}
.cli-kb-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.cli-kb-nm{font-family:'Plus Jakarta Sans',sans-serif;font-size:12px;font-weight:800;color:#0f172a;
  text-transform:uppercase;letter-spacing:.03em;}
.cli-kb-ct{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:700;}
.cli-card{background:#fff;border:1px solid #e6e9f4;border-radius:10px;padding:10px;margin-bottom:8px;
  cursor:pointer;transition:box-shadow .12s,transform .12s;}
.cli-card:hover{box-shadow:0 6px 18px rgba(30,36,71,.12);transform:translateY(-1px);}
.cli-card-nm{font-family:Montserrat,sans-serif;font-size:12.5px;font-weight:800;color:#0f172a;line-height:1.3;}
.cli-card-mt{font-size:12px;color:#0f172a;font-weight:700;margin:4px 0;}
.cli-card-sub{font-size:10.5px;color:#94a3b8;font-weight:600;display:flex;align-items:center;gap:5px;}
.cli-kb-empty{font-size:11px;color:#cbd5e1;text-align:center;padding:14px 4px;font-family:Montserrat,sans-serif;}

/* ── Ficha 360 (dentro del st.dialog) ── */
.cli-fh{display:flex;align-items:center;gap:12px;margin-bottom:12px;}
.cli-fh-av{width:46px;height:46px;border-radius:50%;background:#e0e7ff;color:#4338ca;display:flex;
  align-items:center;justify-content:center;font-family:Montserrat,sans-serif;font-weight:800;font-size:16px;flex-shrink:0;}
.cli-fh-nm{font-family:Montserrat,sans-serif;font-weight:800;font-size:1.05rem;color:#0f172a;line-height:1.2;}
.cli-fh-sub{font-size:0.8rem;color:#64748b;margin-top:2px;}
.cli-data{display:grid;grid-template-columns:1fr 1fr;gap:8px 16px;margin:6px 0 4px;}
.cli-data div{font-size:0.82rem;color:#0f172a;}
.cli-data .k{font-size:0.66rem;color:#94a3b8;font-weight:700;text-transform:uppercase;letter-spacing:.05em;}
.cli-sec-t{font-family:Montserrat,sans-serif;font-weight:700;font-size:0.82rem;letter-spacing:0.05em;
  text-transform:uppercase;color:#0f172a;margin:16px 0 9px;}
.cli-tl{border-left:1.5px solid #e2e8f0;padding-left:14px;display:flex;flex-direction:column;gap:11px;}
.cli-tl-it{position:relative;}
.cli-tl-dot{position:absolute;left:-20px;top:3px;width:10px;height:10px;border-radius:50%;
  border:2px solid #fff;}
.cli-tl-t{font-size:0.82rem;color:#0f172a;}
.cli-tl-d{font-size:0.7rem;color:#94a3b8;}
.cli-ep-row{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 12px;
  border-bottom:1px solid #f1f5f9;}
.cli-ep-n{font-family:Montserrat,sans-serif;font-weight:700;font-size:0.84rem;color:#0f172a;}
.cli-ep-m{font-family:Montserrat,sans-serif;font-weight:800;font-size:0.84rem;color:#0f172a;white-space:nowrap;}
</style>
"""


# ── Ficha 360 como DRAWER derecho (mismo patrón que INVENTARIO/COMPRAS) ───────
# El @st.dialog se recoloca por CSS: cubre TODA la altura, pegado a la derecha.
# OJO: la regla base NO puede llevar `transform:none!important` (le ganaría a la
# animación de entrada). El reposo lo fija _CLI_DRAWER_STILL_CSS.
_CLI_DRAWER_CSS = """
<style>
div[data-testid="stDialog"]{overflow:hidden!important;}
div[data-testid="stDialog"] > div{align-items:flex-start!important;justify-content:flex-end!important;
  overflow:hidden!important;}
div[data-testid="stDialog"] div[role="dialog"]{position:fixed!important;top:0!important;right:0!important;
  left:auto!important;bottom:0!important;margin:0!important;width:min(560px,96vw)!important;
  max-width:none!important;height:100vh!important;max-height:100vh!important;background:#fff!important;
  border-radius:0!important;box-shadow:-16px 0 48px rgba(15,23,42,0.20)!important;
  overflow-y:auto!important;overflow-x:hidden!important;animation:none!important;}
@keyframes cliDrawerIn{from{transform:translateX(100%);}to{transform:translateX(0);}}
@keyframes cliBackdropIn{from{opacity:0;}to{opacity:1;}}
div[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"]{
  background:transparent!important;border:none!important;box-shadow:none!important;border-radius:0!important;}
div[data-testid="stDialog"] div[role="dialog"] > div:first-child{
  font-family:'Montserrat',sans-serif!important;font-weight:700!important;font-size:0.92rem!important;
  letter-spacing:0.05em!important;text-transform:uppercase!important;color:#0f172a!important;}
</style>
"""

# Entrada (deslizar desde la derecha): SOLO cuando el drawer se abre desde cerrado.
_CLI_DRAWER_ANIM_CSS = """
<style>
div[data-testid="stDialog"] div[role="dialog"]{
  animation:cliDrawerIn .34s cubic-bezier(.22,.61,.36,1) both!important;}
div[data-testid="stDialog"]::before,div[data-testid="stDialog"] > div[data-testid="stDialogBackdrop"]{
  animation:cliBackdropIn .34s ease both!important;}
</style>
"""

# Reposo (reruns con el drawer abierto): sin animación, anclado en translateX(0) —
# neutraliza el translateY(20) por defecto de Streamlit.
_CLI_DRAWER_STILL_CSS = """
<style>div[data-testid="stDialog"] div[role="dialog"]{transform:translateX(0)!important;}</style>
"""

# Animación de SALIDA: Streamlit quita el dialog de golpe, así que interceptamos
# los cierres NATIVOS (X, clic fuera, Escape) en el documento padre y en fase de
# captura, animamos la salida y recién dejamos pasar el cierre real. Guards
# _cliClosing (un gesto = un cierre) y _cliSkipClose (deja pasar el click
# programático); se resetean al inicio de cada run porque el iframe que tenía el
# timeout muere en el rerun. Re-bindea cada run.
_CLI_DRAWER_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  W._cliSkipClose=false; W._cliClosing=false;
  function dlg(){ return D.querySelector('div[data-testid="stDialog"] div[role="dialog"]'); }
  var CANCELA='[class*="st-key-_cli_add_cancel"] button';
  function closeTarget(t){
    if(!t||!t.closest) return null;
    var b=t.closest(CANCELA); if(b) return b;
    if(t.closest('button[aria-label="Close"]')) return 'x';
    if(t.closest('div[data-testid="stDialog"]') && !t.closest('div[role="dialog"]')) return 'x';
    return null;
  }
  function realClose(target){
    W._cliSkipClose=true;
    var el=(target==='x'||!target)
      ? D.querySelector('div[data-testid="stDialog"] button[aria-label="Close"]') : target;
    if(el){ try{ el.click(); }catch(e){} }
    W.setTimeout(function(){ W._cliSkipClose=false; W._cliClosing=false; }, 600);
  }
  function closeWithAnim(target){
    if(W._cliClosing) return; W._cliClosing=true;
    var d=dlg(); if(!d){ realClose(target); return; }
    var done=false;
    function fin(){ if(done) return; done=true; realClose(target); }
    try{
      d.getAnimations().forEach(function(a){ try{a.cancel();}catch(e){} });
      var a=d.animate([{transform:'translateX(0)'},{transform:'translateX(100%)'}],
                      {duration:260, easing:'cubic-bezier(.5,0,.75,0)', fill:'forwards'});
      a.onfinish=fin; a.oncancel=fin;
      W.setTimeout(fin, 330);
    }catch(e){ fin(); }
  }
  ['pointerdown','mousedown','click'].forEach(function(evt){
    var k='_cliCl_'+evt;
    if(W[k]){ try{ D.removeEventListener(evt, W[k], true); }catch(e){} }
    W[k]=function(ev){
      if(W._cliSkipClose || !dlg()) return;
      var tg=closeTarget(ev.target); if(!tg) return;
      ev.preventDefault(); ev.stopImmediatePropagation(); closeWithAnim(tg);
    };
    D.addEventListener(evt, W[k], true);
  });
  if(W._cliEscCap){ try{ D.removeEventListener('keydown', W._cliEscCap, true); }catch(e){} }
  W._cliEscCap=function(ev){
    if(ev.key!=='Escape' && ev.keyCode!==27) return;
    if(W._cliSkipClose || !dlg()) return;
    ev.preventDefault(); ev.stopImmediatePropagation(); closeWithAnim('x');
  };
  D.addEventListener('keydown', W._cliEscCap, true);
})();
</script>"""


def _svg(path, size=16, color="#0f172a", sw=2):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="flex-shrink:0;vertical-align:-2px;">{path}</svg>')


def _titulo(texto, icon=""):
    st.markdown(
        '<div style="display:flex;align-items:center;gap:9px;margin:6px 0 10px;">'
        f'{icon}<span style="font-family:\'Montserrat\',sans-serif;font-weight:700;'
        'font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;'
        f'color:#0f172a;">{texto}</span></div>',
        unsafe_allow_html=True)


def _esc(s):
    return _html.escape(str(s if s is not None else ""))


_ICON_USER_PATH = ('<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/>'
                   '<circle cx="12" cy="7" r="4"/>')


def _initials(nombre: str) -> str:
    parts = [p for p in str(nombre or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def _fmt_money(v) -> str:
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        v = 0
    return f"${v:,.0f}".replace(",", ".") if v else "$0"


@st.cache_data(ttl=60, show_spinner=False)
def _cli_data() -> list:
    """Maestro enriquecido con el pipeline DERIVADO (_stage/_cotizaciones/_monto).
    Cacheado; se limpia al mutar/sincronizar."""
    return enriquecer_con_pipeline(listar_clientes(solo_activos=True))


@st.cache_data(ttl=60, show_spinner=False)
def _cli_polluted() -> set:
    """Identidades compartidas (placeholders) para la dedup del alta manual."""
    return identidades_compartidas()


def _kpi(label, valor, color="#0f172a"):
    return (
        '<div style="background:#f8fafc;border-radius:12px;padding:12px 14px;">'
        f'<div style="font-size:0.74rem;color:#64748b;font-weight:600;">{label}</div>'
        f'<div style="font-family:Montserrat,sans-serif;font-size:1.5rem;font-weight:800;'
        f'color:{color};line-height:1.2;">{valor}</div></div>')


_ORIGEN_COLORS = {
    "shopify": ("#ede9fe", "#6d28d9"),
    "web":     ("#e0f2fe", "#0369a1"),
    "manual":  ("#f1f5f9", "#475569"),
}


def _origen_pill(origen: str) -> str:
    _bg, _fg = _ORIGEN_COLORS.get(str(origen or "").split(" ")[0].lower(), _ORIGEN_COLORS["manual"])
    return f'<span class="cli-pill" style="background:{_bg};color:{_fg};">{_esc(origen)}</span>'


# ── Puente JS→Python: click en fila/tarjeta abre la ficha ─────────────────────
_CLI_CLICK_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function fire(cid){
    var inp=D.querySelector('.st-key-_cli_cmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, 'open|'+cid+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  if(W._cliClickH){ D.removeEventListener('click', W._cliClickH, true); }
  W._cliClickH=function(ev){
    var t=ev.target; if(!t||!t.closest) return;
    var el=t.closest('[data-cid]'); if(!el) return;
    ev.preventDefault(); ev.stopPropagation(); fire(el.getAttribute('data-cid'));
  };
  D.addEventListener('click', W._cliClickH, true);
})();
</script>"""

def _iniciar_presupuesto(cli: dict):
    """Arranca un PRESUPUESTO NUEVO para este cliente con los datos ya cargados.
    Reusa el mismo mecanismo que "Cargar presupuesto" de COTIZACIONES
    (ejecutar_carga_cotizacion, en tab_cotizacion.py): un dict con forma de
    cotización + trigger; con numero='' el sistema genera un EP nuevo al guardar
    (tab_cotizacion.py: `cotizacion_cargada or generar_numero_unico()`). Carrito
    VACÍO, sin margen, sin plano → presupuesto en blanco con el cliente prellenado.
    NO modifica el flujo existente: solo setea el estado que ese flujo ya consume."""
    st.session_state["cotizacion_a_cargar"] = {
        "numero": "",                      # '' → presupuesto NUEVO (no edita uno existente)
        "productos": [],                   # carrito vacío
        "cliente_nombre": cli.get("nombre", ""),
        "cliente_rut": cli.get("rut", ""),
        "cliente_email": cli.get("email", ""),
        "cliente_telefono": cli.get("telefono", ""),
        "cliente_direccion": cli.get("direccion", ""),
        "cliente_comuna": cli.get("comuna", ""),
        "cliente_region": cli.get("region", ""),
        "cliente_tipo": cli.get("tipo", "natural") or "natural",
        "cliente_empresa": cli.get("empresa", ""),
        "cliente_rut_empresa": cli.get("rut_empresa", ""),
        "asesor_nombre": cli.get("asignado_nombre", ""),
        "asesor_email": cli.get("asignado_email", ""),
        "asesor_telefono": "",
        "config_margen": 0,
        "proyecto_direccion": "", "proyecto_comuna": "", "proyecto_region": "",
        "proyecto_observaciones": "",
    }
    st.session_state["cargar_cotizacion_trigger"] = True
    st.session_state["nav_page"] = "presupuesto"       # navegar al editor
    _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
    registrar_actividad(cli.get("id"), "presupuesto",
                        "Presupuesto nuevo iniciado desde el CRM", actor=_actor)


# Menú contextual (click DERECHO) en tarjetas del pipeline / filas del maestro:
# "Crear presupuesto" + "Ver ficha 360". Escribe en el puente _cli_cmd. El
# click IZQUIERDO sigue abriendo la ficha (ver _CLI_CLICK_JS); son eventos
# distintos (contextmenu vs click) → no chocan.
_CLI_CTXMENU_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var MENU='_cli_ctxmenu';
  function fire(action, cid){
    var inp=D.querySelector('.st-key-_cli_cmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, action+'|'+cid+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  function ic(p){return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'+p+'</svg>';}
  function closeMenu(){var m=D.getElementById(MENU); if(m) m.remove();}
  function build(cid, cname, x, y){
    closeMenu();
    var m=D.createElement('div'); m.id=MENU;
    m.style.cssText='position:absolute;z-index:2147483000;min-width:224px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 12px 34px rgba(15,23,42,.18);padding:6px;font-family:-apple-system,Segoe UI,Roboto,sans-serif;';
    if(cname){
      var hd=D.createElement('div');
      hd.style.cssText='padding:8px 10px 9px;border-bottom:1px solid #f1f5f9;margin-bottom:4px;font-size:12.5px;font-weight:800;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:224px;';
      hd.textContent=cname; m.appendChild(hd);
    }
    function row(label, svg, color, action){
      var r=D.createElement('div');
      r.style.cssText='display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;color:'+color+';';
      r.innerHTML=ic(svg)+'<span>'+label+'</span>';
      r.addEventListener('mouseenter',function(){r.style.background='#eef2ff';});
      r.addEventListener('mouseleave',function(){r.style.background='transparent';});
      r.addEventListener('click',function(ev){ev.stopPropagation();closeMenu();fire(action,cid);});
      m.appendChild(r);
    }
    row('Crear presupuesto','<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" x2="12" y1="12" y2="18"/><line x1="9" x2="15" y1="15" y2="15"/>','#2563eb','nuevo');
    row('Ver ficha 360','<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>','#0f172a','open');
    D.body.appendChild(m);
    var vw=W.innerWidth, vh=W.innerHeight, sx=W.pageXOffset||0, sy=W.pageYOffset||0;
    var rw=m.offsetWidth, rh=m.offsetHeight, px=x, py=y;
    if(px-sx+rw>vw) px=sx+vw-rw-8;
    if(py-sy+rh>vh) py=sy+vh-rh-8;
    m.style.left=Math.max(sx+4,px)+'px'; m.style.top=Math.max(sy+4,py)+'px';
  }
  if(W._cliCtxH){ D.removeEventListener('contextmenu', W._cliCtxH, true); }
  W._cliCtxH=function(e){
    var el=e.target&&e.target.closest?e.target.closest('[data-cid]'):null; if(!el) return;
    e.preventDefault();
    build(el.getAttribute('data-cid'), el.getAttribute('data-cname')||'', e.pageX, e.pageY);
  };
  D.addEventListener('contextmenu', W._cliCtxH, true);
  if(W._cliCtxDown){ D.removeEventListener('mousedown', W._cliCtxDown, true); }
  W._cliCtxDown=function(e){var m=D.getElementById(MENU); if(m && !m.contains(e.target)) closeMenu();};
  D.addEventListener('mousedown', W._cliCtxDown, true);
  if(W._cliCtxKey){ D.removeEventListener('keydown', W._cliCtxKey, true); }
  W._cliCtxKey=function(e){if(e.key==='Escape') closeMenu();};
  D.addEventListener('keydown', W._cliCtxKey, true);
})();
</script>"""

# Buscador client-side del maestro (input HTML + data-s por fila): sin reruns.
_CLI_SEARCH_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var q=D.getElementById('_cli_q');
  if(!q) return;
  if(W._cliQH){ try{ q.removeEventListener('input', W._cliQH); }catch(e){} }
  W._cliQH=function(){
    var v=(q.value||'').toLowerCase().trim();
    var trs=D.querySelectorAll('.cli-tbl-wrap tbody tr[data-s]'), n=0;
    for(var i=0;i<trs.length;i++){
      var ok=(!v)||(trs[i].getAttribute('data-s').indexOf(v)>=0);
      trs[i].style.display=ok?'':'none'; if(ok) n++;
    }
    var c=D.getElementById('_cli_count'); if(c) c.textContent=n;
    var em=D.getElementById('_cli_noresult'); if(em) em.style.display=(n||!trs.length)?'none':'block';
    W._cliQ=v;
  };
  q.addEventListener('input', W._cliQH);
  if(W._cliQ){ q.value=W._cliQ; W._cliQH(); }
})();
</script>"""


# ── Renders de cada vista ─────────────────────────────────────────────────────

def _render_maestro(data: list):
    _titulo(f'Maestro · <span id="_cli_count">{len(data)}</span> cliente(s)',
            _svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                 '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', 16))
    st.markdown(
        '<div class="cli-sbar"><span class="cli-sico">'
        + _svg('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', 16, "currentColor")
        + '</span><input id="_cli_q" type="text" autocomplete="off" '
        'placeholder="Buscar por nombre, RUT, correo, teléfono o ejecutivo…"></div>',
        unsafe_allow_html=True)
    if not data:
        st.markdown('<div class="cli-empty-ph">Aún no hay clientes. Pulsa '
                    '<b>Sincronizar</b> para importar desde tus cotizaciones, o '
                    '<b>Agregar cliente</b>.</div>', unsafe_allow_html=True)
        return
    rows = ""
    for d in data:
        _asig = d.get("asignado_nombre") or d.get("asignado_email") or ""
        _stage = d.get("_stage") or STAGE_LEAD
        _slbl, _sdot, _sbg, _sfg = _STAGE_META.get(_stage, _STAGE_META[STAGE_LEAD])
        _s = _esc(f"{d.get('nombre','')} {d.get('rut','')} {d.get('email','')} "
                  f"{d.get('telefono','')} {_asig} {d.get('origen','')} {_slbl}".lower())
        _asig_cell = (_esc(_asig) if _asig
                      else '<span style="color:#ea580c;font-weight:700;font-size:0.72rem;">Sin asignar</span>')
        rows += (
            f'<tr data-s="{_s}" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}">'
            f'<td style="font-weight:700;">{_esc(d.get("nombre","") or "—")}</td>'
            f'<td><span class="cli-pill" style="background:{_sbg};color:{_sfg};">{_slbl}</span></td>'
            f'<td>{_esc(d.get("rut","")) or "—"}</td>'
            f'<td>{_esc(d.get("email","")) or "—"}</td>'
            f'<td>{_esc(d.get("telefono","")) or "—"}</td>'
            f'<td>{_origen_pill(d.get("origen","Manual"))}</td>'
            f'<td>{_asig_cell}</td>'
            '</tr>')
    st.markdown(
        '<div class="cli-tbl-wrap"><table><thead><tr>'
        '<th>Cliente</th><th>Etapa</th><th>RUT</th><th>Correo</th><th>Tel&eacute;fono</th>'
        '<th>Origen</th><th>Ejecutivo</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown('<div id="_cli_noresult" class="cli-empty-ph" style="display:none;">'
                'Ningún cliente coincide con tu búsqueda.</div>', unsafe_allow_html=True)


def _render_pipeline(data: list):
    _titulo("Pipeline de oportunidades",
            _svg('<path d="M3 3v18h18"/><rect x="7" y="13" width="3" height="5"/>'
                 '<rect x="12" y="9" width="3" height="9"/><rect x="17" y="5" width="3" height="13"/>', 16))
    por_etapa = {s: [] for s in _STAGE_ORDER}
    for d in data:
        por_etapa.get(d.get("_stage") or STAGE_LEAD, por_etapa[STAGE_LEAD]).append(d)
    cols = ""
    for s in _STAGE_ORDER:
        _lbl, _dot, _bg, _fg = _STAGE_META[s]
        items = por_etapa[s]
        cards = ""
        for d in items:
            _asig = d.get("asignado_nombre") or d.get("asignado_email") or "Sin asignar"
            _mt = (f'<div class="cli-card-mt">{_fmt_money(d.get("_monto"))}</div>'
                   if d.get("_monto") else "")
            _neps = len(d.get("_cotizaciones") or [])
            _ep = (f'{_neps} presupuesto' + ('s' if _neps != 1 else '')) if _neps else "Sin presupuesto"
            _asig_ico = _svg(_ICON_USER_PATH, 12, "#94a3b8")
            cards += (
                f'<div class="cli-card" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}">'
                f'<div class="cli-card-nm">{_esc(d.get("nombre","") or "—")}</div>'
                f'{_mt}'
                f'<div class="cli-card-sub">{_asig_ico}{_esc(_asig)}</div>'
                f'<div class="cli-card-sub" style="margin-top:2px;">{_esc(_ep)}</div>'
                '</div>')
        if not cards:
            cards = '<div class="cli-kb-empty">—</div>'
        cols += (
            '<div class="cli-kb-col">'
            f'<div class="cli-kb-hd"><span class="cli-kb-dot" style="background:{_dot};"></span>'
            f'<span class="cli-kb-nm">{_lbl}</span><span class="cli-kb-ct">{len(items)}</span></div>'
            f'{cards}</div>')
    st.markdown(f'<div class="cli-kb-wrap"><div class="cli-kb">{cols}</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.76rem;color:#94a3b8;margin-top:8px;">'
                'Las etapas <b>En presupuesto</b>, <b>Propuesta enviada</b>, <b>Ganado</b> y '
                '<b>Perdido</b> se derivan solas del estado del presupuesto. Click en una tarjeta '
                'para ver la ficha del cliente.</div>', unsafe_allow_html=True)


def _render_bandeja(data: list):
    leads = [d for d in data if (d.get("_stage") in (STAGE_LEAD, STAGE_CONTACTADO))]
    _titulo(f"Bandeja de leads · {len(leads)}",
            _svg('<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
                 '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>', 16))
    if not leads:
        st.markdown(
            '<div class="cli-empty-ph">Sin leads pendientes por asignar.<br>'
            '<span style="font-weight:500;color:#cbd5e1;">Acá caerán los clientes nuevos '
            '(Shopify / web) para triar y asignar a un ejecutivo.</span></div>',
            unsafe_allow_html=True)
        return
    cards = ""
    for d in leads:
        cards += (
            f'<div class="cli-card" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}" style="margin-bottom:10px;">'
            f'<div class="cli-card-nm">{_esc(d.get("nombre","") or "—")}</div>'
            f'<div class="cli-card-sub" style="margin-top:4px;">{_origen_pill(d.get("origen","Manual"))}</div>'
            f'<div class="cli-card-sub" style="margin-top:4px;">{_esc(d.get("email","") or d.get("telefono","") or "—")}</div>'
            '</div>')
    st.markdown(f'<div style="margin-top:12px;">{cards}</div>', unsafe_allow_html=True)


# ── Ficha 360 ─────────────────────────────────────────────────────────────────

def _render_ficha(cid: str, data: list):
    cli = next((d for d in data if str(d.get("id")) == str(cid)), None)
    if not cli:
        return
    _stage = cli.get("_stage") or STAGE_LEAD
    _slbl, _sdot, _sbg, _sfg = _STAGE_META.get(_stage, _STAGE_META[STAGE_LEAD])

    @st.dialog("Ficha del cliente", width="large")
    def _dlg():
        _asig = cli.get("asignado_nombre") or cli.get("asignado_email") or "Sin asignar"
        st.markdown(
            '<div class="cli-fh">'
            f'<div class="cli-fh-av">{_esc(_initials(cli.get("nombre")))}</div>'
            '<div style="min-width:0;">'
            f'<div class="cli-fh-nm">{_esc(cli.get("nombre","") or "—")}</div>'
            f'<div class="cli-fh-sub">{_esc(cli.get("rut","") or "Sin RUT")} · {_esc(_asig)}</div>'
            '</div></div>'
            '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px;">'
            f'{_origen_pill(cli.get("origen","Manual"))}'
            f'<span class="cli-pill" style="background:{_sbg};color:{_sfg};">{_slbl}</span>'
            '</div>', unsafe_allow_html=True)

        # Datos de contacto
        _tipo = cli.get("tipo") or "natural"
        _empresa = (f'<div><div class="k">Empresa</div>{_esc(cli.get("empresa"))} '
                    f'({_esc(cli.get("rut_empresa"))})</div>') if _tipo == "empresa" and cli.get("empresa") else ""
        st.markdown(
            '<div class="cli-data">'
            f'<div><div class="k">Correo</div>{_esc(cli.get("email","") or "—")}</div>'
            f'<div><div class="k">Teléfono</div>{_esc(cli.get("telefono","") or "—")}</div>'
            f'<div><div class="k">Dirección</div>{_esc(cli.get("direccion","") or "—")}</div>'
            f'<div><div class="k">Comuna</div>{_esc(cli.get("comuna","") or "—")}</div>'
            f'{_empresa}'
            '</div>', unsafe_allow_html=True)

        # Acción principal: crear un presupuesto NUEVO para este cliente con los
        # datos ya cargados (navega al editor). st.rerun() completo → cierra el
        # drawer y va al Presupuesto.
        if st.button("Crear presupuesto", icon=":material/note_add:", type="primary",
                     use_container_width=True, key="_cli_fh_nuevo"):
            _iniciar_presupuesto(cli)
            st.rerun()

        # "Enviar correo" llega con Resend (fase siguiente); "Recordar" abre el
        # mini-formulario inline. El cierre del drawer va por su X / clic fuera /
        # Escape (con animación de salida).
        a1, a2 = st.columns(2)
        with a1:
            if st.button("Enviar correo", icon=":material/mail:", use_container_width=True,
                         key="_cli_fh_mail"):
                st.toast("El envío de correos (Resend) llega en una fase siguiente.")
        with a2:
            if st.button("Recordar", icon=":material/notification_add:", use_container_width=True,
                         key="_cli_fh_rem"):
                st.session_state["_cli_rem_open"] = not st.session_state.get("_cli_rem_open", False)
                st.rerun(scope="fragment")

        # Mini-formulario de recordatorio (inline: NO puede ser otro dialog dentro
        # del dialog). Se muestra al pulsar "Recordar".
        if st.session_state.get("_cli_rem_open"):
            with st.container(border=True):
                st.markdown('<div style="font-size:0.78rem;font-weight:700;color:#0f172a;'
                            'text-transform:uppercase;letter-spacing:.04em;margin-bottom:4px;">'
                            'Nuevo recordatorio</div>', unsafe_allow_html=True)
                _rt = st.text_input("¿Qué recordar?", key="_cli_rem_titulo",
                                    placeholder="Llamar para seguimiento…", label_visibility="collapsed")
                rc1, rc2 = st.columns([1, 1])
                with rc1:
                    _rv = st.date_input("Vence", value=_date.today() + _td(days=3),
                                        min_value=_date.today(), key="_cli_rem_fecha")
                with rc2:
                    _rg = st.button("Guardar recordatorio", type="primary",
                                    use_container_width=True, key="_cli_rem_save")
                if _rg:
                    if not (_rt or "").strip():
                        st.warning("Escribe qué quieres recordar.")
                    else:
                        _actor = (st.session_state.get("auth_nombre")
                                  or st.session_state.get("auth_email", ""))
                        _vence_iso = f"{_rv.isoformat()}T09:00:00-03:00"
                        _tid, _terr = crear_tarea(cid, _rt.strip(), _vence_iso,
                                                  cli.get("asignado_email", ""))
                        if _tid:
                            registrar_actividad(cid, "nota",
                                                f"Recordatorio: {_rt.strip()}",
                                                detalle=f"vence {_rv.isoformat()}", actor=_actor)
                            _n = notificar_recordatorio(cli.get("nombre", "Cliente"), _rt.strip(),
                                                        _rv.isoformat(), cli.get("asignado_email", ""))
                            st.session_state.pop("_cli_rem_open", None)
                            st.toast("Recordatorio guardado"
                                     + (" · avisado por Telegram" if _n else ""))
                            st.rerun(scope="fragment")
                        else:
                            st.error(f"No se pudo guardar: {_terr}")

        # Recordatorios del cliente
        _tareas = listar_tareas_cliente(cid)
        _pend = [t for t in _tareas if not t.get("hecho")]
        st.markdown(f'<div class="cli-sec-t">Recordatorios · {len(_pend)} pendiente(s)</div>',
                    unsafe_allow_html=True)
        if _tareas:
            _hoy = _date.today().isoformat()
            for t in _tareas:
                _venc_d = str(t.get("vence") or "")[:10]
                _hecho = bool(t.get("hecho"))
                _vencida = (not _hecho) and _venc_d and _venc_d <= _hoy
                _col = "#94a3b8" if _hecho else ("#dc2626" if _vencida else "#0f172a")
                _ico = ("#16a34a" if _hecho else ("#dc2626" if _vencida else "#5b7cfa"))
                tc1, tc2 = st.columns([5, 1])
                with tc1:
                    _dec = "text-decoration:line-through;" if _hecho else ""
                    st.markdown(
                        f'<div style="padding:3px 0;">'
                        f'<span style="color:{_ico};">●</span> '
                        f'<span style="font-size:0.86rem;color:{_col};{_dec}">{_esc(t.get("titulo",""))}</span>'
                        f'<span style="font-size:0.72rem;color:#94a3b8;margin-left:6px;">'
                        f'{"vencía" if _vencida else "vence"} {_esc(_venc_d)}</span></div>',
                        unsafe_allow_html=True)
                with tc2:
                    if not _hecho:
                        if st.button("Hecho", key=f"_cli_tdone_{t.get('id')}",
                                     use_container_width=True):
                            completar_tarea(t.get("id"), True)
                            st.rerun(scope="fragment")
        else:
            st.markdown('<div style="font-size:0.8rem;color:#94a3b8;padding:4px 0 8px;">'
                        'Sin recordatorios. Pulsa <b>Recordar</b> para crear uno.</div>',
                        unsafe_allow_html=True)

        # Presupuestos del cliente (derivados de cotizaciones)
        _cots = cli.get("_cotizaciones") or []
        st.markdown(f'<div class="cli-sec-t">Presupuestos · {len(_cots)}</div>', unsafe_allow_html=True)
        if _cots:
            _eprows = ""
            for c in _cots:
                _cst = c.get("stage") or ""
                _cl, _cd, _cbg, _cfg = _STAGE_META.get(_cst, _STAGE_META[STAGE_PRESUPUESTO])
                _eprows += (
                    '<div class="cli-ep-row">'
                    f'<div><span class="cli-ep-n">{_esc(c.get("numero",""))}</span> '
                    f'<span class="cli-pill" style="background:{_cbg};color:{_cfg};margin-left:6px;">{_cl}</span></div>'
                    f'<div class="cli-ep-m">{_fmt_money(c.get("total"))}</div>'
                    '</div>')
            st.markdown('<div style="border:1px solid #e6e9f4;border-radius:12px;overflow:hidden;">'
                        + _eprows + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cli-empty-ph" style="padding:20px;">Este cliente aún no tiene presupuestos.</div>',
                        unsafe_allow_html=True)

        # Línea de tiempo (actividad)
        _acts = listar_actividad(cid)
        st.markdown('<div class="cli-sec-t">Actividad</div>', unsafe_allow_html=True)
        if _acts:
            _TL_ICON = {"correo": "#5b7cfa", "presupuesto": "#7F77DD", "nota": "#94a3b8",
                        "etapa": "#EF9F27", "lead": "#888780", "llamada": "#1D9E75"}
            _tl = ""
            for a in _acts:
                _c = _TL_ICON.get(str(a.get("tipo") or ""), "#94a3b8")
                _fecha = str(a.get("fecha") or "")[:16].replace("T", " ")
                _det = f' — {_esc(a.get("detalle"))}' if a.get("detalle") else ""
                _tl += (
                    '<div class="cli-tl-it">'
                    f'<span class="cli-tl-dot" style="background:{_c};"></span>'
                    f'<div class="cli-tl-t">{_esc(a.get("titulo",""))}{_det}</div>'
                    f'<div class="cli-tl-d">{_esc(_fecha)} · {_esc(a.get("actor","") or "sistema")}</div>'
                    '</div>')
            st.markdown(f'<div class="cli-tl">{_tl}</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cli-empty-ph" style="padding:20px;">Sin actividad registrada.</div>',
                        unsafe_allow_html=True)
    _dlg()


# ── Alta manual ───────────────────────────────────────────────────────────────

def _render_agregar_dialog():
    @st.dialog("Agregar cliente")
    def _dlg():
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre *", key="_cli_add_nombre")
            rut = st.text_input("RUT", key="_cli_add_rut")
            email = st.text_input("Correo", key="_cli_add_email")
        with c2:
            telefono = st.text_input("Teléfono", key="_cli_add_tel")
            tipo = st.selectbox("Tipo", ["natural", "empresa"], key="_cli_add_tipo")
            comuna = st.text_input("Comuna", key="_cli_add_comuna")
        empresa = rut_empresa = ""
        if tipo == "empresa":
            e1, e2 = st.columns(2)
            with e1:
                empresa = st.text_input("Empresa", key="_cli_add_empresa")
            with e2:
                rut_empresa = st.text_input("RUT empresa", key="_cli_add_rutemp")
        direccion = st.text_input("Dirección", key="_cli_add_dir")

        b1, b2 = st.columns(2)
        with b1:
            guardar = st.button("Guardar cliente", type="primary", use_container_width=True,
                                key="_cli_add_save")
        with b2:
            if st.button("Cancelar", use_container_width=True, key="_cli_add_cancel"):
                st.session_state.pop("_cli_add_open", None)
                st.rerun()
        if guardar:
            if not (nombre or "").strip():
                st.warning("El nombre es obligatorio.")
                return
            _pol = _cli_polluted()
            k = dedup_key(rut, email, telefono, nombre, _pol)
            if k[1]:
                for c in _cli_data():
                    if dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), _pol) == k:
                        st.warning(f"Ya existe un cliente con esa identidad: "
                                   f"{c.get('nombre','')}. No se creó un duplicado.")
                        return
            _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
            cid, err = crear_cliente({
                "nombre": nombre.strip(), "rut": (rut or "").strip(),
                "email": (email or "").strip(), "telefono": (telefono or "").strip(),
                "tipo": tipo, "empresa": (empresa or "").strip(),
                "rut_empresa": (rut_empresa or "").strip(),
                "direccion": (direccion or "").strip(), "comuna": (comuna or "").strip(),
                "origen": "Manual", "etapa_manual": "lead_nuevo",
            })
            if cid:
                registrar_actividad(cid, "nota", "Cliente creado manualmente", actor=_actor)
                _cli_data.clear()
                st.session_state.pop("_cli_add_open", None)
                st.session_state["_cli_toast"] = f"Cliente {nombre.strip()} agregado."
                st.rerun()
            else:
                st.error(f"No se pudo guardar: {err}")
    _dlg()


# ── Entrada del tab ───────────────────────────────────────────────────────────

def render_tab_clientes(**kwargs):
    _rol = st.session_state.get("rol_usuario", "ejecutivo")
    # DOBLE LLAVE: aunque no está en la navegación de otros roles, se revalida acá.
    if _rol != _ROL_OK:
        render_page_header("clientes", "Clientes", "CRM")
        st.warning("Esta sección aún no está disponible.")
        return

    render_page_header("clientes", "Clientes",
                       "CRM · maestro de clientes (en construcción)")
    st.markdown(_CLI_CSS, unsafe_allow_html=True)

    _t = st.session_state.pop("_cli_toast", None)
    if _t:
        st.toast(_t)

    # Puente oculto: click en fila/tarjeta → abre la ficha.
    st.markdown('<style>.st-key-_cli_cmd{position:absolute!important;left:-9999px!important;'
                'top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}</style>',
                unsafe_allow_html=True)
    st.text_input("cmd", key="_cli_cmd", label_visibility="collapsed")
    _cmd = str(st.session_state.get("_cli_cmd", "") or "")
    if _cmd and "|" in _cmd:
        _p = _cmd.split("|")
        if _p[-1] != st.session_state.get("_cli_cmd_ts"):
            st.session_state["_cli_cmd_ts"] = _p[-1]
            if _p[0] == "open" and len(_p) >= 3:
                st.session_state["_cli_ficha"] = _p[1]
                st.session_state["_cli_just_opened"] = True   # dispara la animación de entrada
                st.session_state.pop("_cli_rem_open", None)   # ficha nueva → form de recordatorio cerrado
            elif _p[0] == "nuevo" and len(_p) >= 3:
                # Crear presupuesto para este cliente (menú contextual pipeline/maestro).
                _cobj = next((d for d in _cli_data() if str(d.get("id")) == _p[1]), None)
                if _cobj:
                    _iniciar_presupuesto(_cobj)
                    st.rerun()

    data = _cli_data()

    # Recordatorios pendientes (para el KPI) + alerta Telegram de vencidos.
    _pend_tareas = listar_tareas_pendientes()
    _hoy_iso = _date.today().isoformat()
    _venc_hoy = sum(1 for t in _pend_tareas if str(t.get("vence") or "")[:10] <= _hoy_iso)

    # Alerta de vencidos por Telegram — UNA vez por sesión al abrir la pestaña
    # (Streamlit Cloud no tiene cron; se dispara cuando root abre el CRM). Requiere
    # la columna `notificado` (si no existe, tareas_vencidas_… devuelve [] y no pasa nada).
    if not st.session_state.get("_cli_alert_done"):
        st.session_state["_cli_alert_done"] = True
        _venc = tareas_vencidas_no_notificadas()
        if _venc:
            _cmap = {c.get("id"): c for c in data}
            _ok_ids = []
            for t in _venc:
                _c = _cmap.get(t.get("cliente_id"), {})
                notificar_recordatorio(_c.get("nombre", "Cliente"), t.get("titulo", ""),
                                       str(t.get("vence") or "")[:10],
                                       _c.get("asignado_email", ""), vencido=True)
                _ok_ids.append(t.get("id"))
            marcar_notificadas(_ok_ids)

    # KPIs por etapa (con datos reales)
    _cnt = {s: 0 for s in _STAGE_ORDER}
    for d in data:
        _cnt[d.get("_stage") or STAGE_LEAD] = _cnt.get(d.get("_stage") or STAGE_LEAD, 0) + 1
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:12px;margin:6px 0 14px;">'
        + _kpi("Total clientes", len(data))
        + _kpi("En presupuesto", _cnt[STAGE_PRESUPUESTO], "#6d28d9")
        + _kpi("Propuesta enviada", _cnt[STAGE_PROPUESTA], "#b45309")
        + _kpi("Ganados", _cnt[STAGE_GANADO], "#15803d")
        + _kpi("Perdidos", _cnt[STAGE_PERDIDO], "#94a3b8")
        + _kpi("Recordatorios", len(_pend_tareas), "#dc2626" if _venc_hoy else "#0f172a")
        + '</div>', unsafe_allow_html=True)

    # Acciones: Sincronizar (backfill) + Agregar cliente
    a1, a2, _a3 = st.columns([1, 1, 2])
    with a1:
        if st.button("Sincronizar", icon=":material/sync:", use_container_width=True,
                     key="_cli_sync", help="Re-lee las cotizaciones y crea las fichas que falten (solo lectura)"):
            with st.spinner("Sincronizando con cotizaciones…"):
                res = backfill_desde_cotizaciones()
            _cli_data.clear()
            st.session_state["_cli_toast"] = (
                f"Sincronizado: {res['creados']} nuevo(s), {res['existentes']} ya estaban.")
            st.rerun()
    with a2:
        if st.button("Agregar cliente", icon=":material/person_add:", type="primary",
                     use_container_width=True, key="_cli_add_btn"):
            st.session_state["_cli_add_open"] = True
            st.session_state["_cli_just_opened"] = True

    # Selector de vista
    st.markdown(_CLI_SELECTOR_CSS, unsafe_allow_html=True)
    _views = ["Pipeline", "Bandeja", "Maestro"]
    _icons = {"Pipeline": ":material/view_kanban:", "Bandeja": ":material/inbox:",
              "Maestro": ":material/table_rows:"}
    _view = st.radio("Vista", _views, index=0, key="_cli_view", horizontal=True,
                     label_visibility="collapsed",
                     format_func=lambda v: f"{_icons.get(v,'')} {v}")

    if _view == "Maestro":
        _render_maestro(data)
    elif _view == "Bandeja":
        _render_bandeja(data)
    else:
        _render_pipeline(data)

    # Handler de click (abre ficha) + menú contextual + búsqueda + salida del drawer.
    components.html(_CLI_CLICK_JS + _CLI_CTXMENU_JS + _CLI_SEARCH_JS, height=0)
    components.html(_CLI_DRAWER_JS, height=0)

    # Drawer: base siempre; entrada SOLO al abrir desde cerrado, reposo en los
    # reruns con el drawer abierto (neutraliza el translateY(20) por defecto).
    st.markdown(_CLI_DRAWER_CSS, unsafe_allow_html=True)
    st.markdown(_CLI_DRAWER_ANIM_CSS if st.session_state.pop("_cli_just_opened", False)
                else _CLI_DRAWER_STILL_CSS, unsafe_allow_html=True)

    # Ficha 360 (one-shot: pop del flag; el dialog persiste vía su fragment).
    _fid = st.session_state.pop("_cli_ficha", None)
    if _fid:
        _render_ficha(_fid, data)

    # Diálogo de alta (one-shot)
    if st.session_state.get("_cli_add_open"):
        st.session_state.pop("_cli_add_open", None)
        _render_agregar_dialog()
