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
import json as _json
import unicodedata as _ud
from datetime import date as _date, datetime as _dt, timedelta as _td, timezone as _tz
try:
    from zoneinfo import ZoneInfo as _ZoneInfo
except Exception:   # py<3.9 sin zoneinfo: se usa el fallback UTC-3 en _fmt_fecha_local
    _ZoneInfo = None

import streamlit as st
import streamlit.components.v1 as components

from views.layout import render_page_header
from repositories.clientes_repo import (
    listar_clientes, crear_cliente, actualizar_cliente, registrar_actividad, listar_actividad,
    backfill_desde_cotizaciones, dedup_key, enriquecer_con_pipeline,
    identidades_compartidas,
    crear_tarea, listar_tareas_cliente, completar_tarea, listar_tareas_pendientes,
    tareas_vencidas_no_notificadas, marcar_notificadas, importar_leads, CAMPOS_IMPORT,
    propagar_a_cotizaciones, detectar_duplicados, fusionar_clientes,
    actualizar_etapa_tracking,
    STAGE_LEAD, STAGE_CONTACTADO, STAGE_PRESUPUESTO, STAGE_PROPUESTA,
    STAGE_GANADO, STAGE_PERDIDO,
)
from repositories.guion_repo import (
    listar_preguntas, crear_pregunta, actualizar_pregunta, eliminar_pregunta,
    guardar_calificacion, TIPOS_CAMPO,
)
from config.settings import SUPABASE_URL as _SUPA_URL
try:
    from utils.avatars import avatar_html as _avatar_html
except Exception:
    def _avatar_html(foto, nombre, size=32, ring="#fff", font_scale=0.4):
        _i = "".join(p[0] for p in str(nombre or "EC").split()[:2]).upper() or "EC"
        return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;background:#e0e7ff;'
                f'color:#4338ca;display:flex;align-items:center;justify-content:center;font-weight:800;'
                f'font-size:{int(size*font_scale)}px;flex:0 0 auto;">{_i}</div>')
try:
    from utils.notificaciones import notificar_recordatorio, notificar_lead_asignado
except Exception:   # notificaciones es opcional; si falla, los recordatorios igual se guardan
    def notificar_recordatorio(*a, **k):
        return 0
    def notificar_lead_asignado(*a, **k):
        return 0


@st.cache_data(ttl=120, show_spinner=False)
def _ejecutivos() -> list:
    """Ejecutivos para asignar [{email, nombre, …}]. Cacheado; defensivo."""
    try:
        from utils.avatars import fetch_ejecutivos
        return fetch_ejecutivos(_SUPA_URL)
    except Exception:
        return []


def _usuarios_map() -> dict:
    """email -> {nombre, foto_url} de TODOS los usuarios (cualquier rol). Para
    resolver el nombre/foto del asignado aunque sea admin/operación. Defensivo."""
    try:
        from utils.avatars import fetch_usuarios_map
        return fetch_usuarios_map(_SUPA_URL)
    except Exception:
        return {}


def _resolver_asig(email, nombre="") -> str:
    """Nombre a MOSTRAR de un asignado: usa el nombre guardado si es válido; si está
    vacío o quedó como el propio correo, lo resuelve por el directorio de usuarios
    (incluye admins/operación); en último caso, el correo. '' si no hay asignado."""
    _em = (email or "").strip().lower()
    _nm = (nombre or "").strip()
    if _nm and "@" not in _nm:            # ya tiene un nombre real guardado
        return _nm
    if _em:
        _u = _usuarios_map().get(_em)
        if _u and _u.get("nombre"):
            return _u["nombre"]
    return _nm or (email or "").strip()
try:
    from repositories.notificaciones_repo import crear_notificacion as _crear_notif
except Exception:   # feed opcional; si falla, la actividad igual se guarda
    def _crear_notif(*a, **k):
        return None

try:   # Envío de correos (Resend) — opcional/defensivo
    from utils.resend_mail import (
        enviar_correo as _resend_enviar, render_variables as _resend_render,
        texto_a_html as _resend_texto_html, remitente as _resend_remitente,
        reply_to_default as _resend_reply, configurado as _resend_configurado,
        estado_correo as _resend_estado, estado_lectura_disponible as _resend_estado_ok,
        enviar_lote as _resend_lote, pie_baja_html as _resend_pie,
        unsubscribe_url as _resend_unsub,
    )
except Exception:
    def _resend_configurado():
        return False

    def _resend_enviar(*a, **k):
        return False, "Módulo de correo no disponible."

    def _resend_render(t, c):
        return t

    def _resend_texto_html(t):
        return t

    def _resend_remitente():
        return ""

    def _resend_reply():
        return ""

    def _resend_estado(_id):
        return {"ok": False}

    def _resend_estado_ok():
        return False

    def _resend_lote(_m):
        return False, "Módulo de correo no disponible."

    def _resend_pie(_cid):
        return ""

    def _resend_unsub(_cid):
        return ""

try:   # Seguimiento de correos enviados (tabla crm_correos) — defensivo
    from repositories.correos_repo import (
        registrar_correo as _registrar_correo,
        listar_correos_cliente as _listar_correos_cliente,
    )
except Exception:
    def _registrar_correo(*a, **k):
        return None, None

    def _listar_correos_cliente(_cid):
        return []

try:   # Firma de correo por ejecutivo (tabla crm_firma) — defensivo
    from repositories.firma_repo import (
        get_firma as _get_firma, set_firma as _set_firma,
        listar_firmas as _listar_firmas, logo_url_publica as _logo_url_publica,
    )
except Exception:
    def _get_firma(_c):
        return {}

    def _set_firma(_c, _v):
        return False, "Firma no disponible."

    def _listar_firmas():
        return {}

    def _logo_url_publica():
        return ""

try:   # Ingesta de leads desde Shopify (Fase 4) — defensivo
    from utils.shopify import (
        configurado as _shopify_configurado, listar_clientes as _shopify_listar,
        a_lead as _shopify_a_lead,
    )
except Exception:
    def _shopify_configurado():
        return False

    def _shopify_listar(*a, **k):
        return [], "Módulo de Shopify no disponible."

    def _shopify_a_lead(_c):
        return {}


def _notif_dest(cli: dict) -> str:
    """Destinatario de la campana: el ejecutivo asignado, o el usuario actual."""
    return (cli.get("asignado_email") or st.session_state.get("auth_email", "") or "").strip()

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

# Subtítulo aclaratorio por columna del pipeline: si esa etapa agrupa leads CON o
# SIN presupuesto (para que la sección se entienda de una mirada).
_SUB_ICO_SIN = '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 15h6"/>'
_SUB_ICO_CON = '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m9 15 2 2 4-4"/>'
_STAGE_SUB = {
    STAGE_LEAD:        ("sin", "Sin presupuesto aún", _SUB_ICO_SIN),
    STAGE_CONTACTADO:  ("sin", "Sin presupuesto aún", _SUB_ICO_SIN),
    STAGE_PRESUPUESTO: ("con", "Con presupuesto",     _SUB_ICO_CON),
    STAGE_PROPUESTA:   ("con", "Con presupuesto",     _SUB_ICO_CON),
    STAGE_GANADO:      ("con", "Con presupuesto",     _SUB_ICO_CON),
    STAGE_PERDIDO:     ("con", "Con presupuesto",     _SUB_ICO_CON),
}


# ── Reloj SLA + transiciones de etapa en el timeline ──────────────────────────
_STAGE_TERMINAL = {STAGE_GANADO, STAGE_PERDIDO}   # sin presión (ya cerró)
_SLA_CLOCK_ICO = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
                  'stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/>'
                  '<polyline points="12 6 12 12 16 14"/></svg>')


def _now_cl():
    return _dt.now(_tz(_td(hours=-3)))


def _parse_iso(s):
    try:
        d = _dt.fromisoformat(str(s).replace("Z", "+00:00"))
        return d.replace(tzinfo=_tz.utc) if d.tzinfo is None else d
    except Exception:
        return None


def _fmt_duracion(secs) -> str:
    """Segundos → '2d 5h' / '3h 20m' / '12m 5s' / '45s'."""
    secs = int(max(0, secs or 0))
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _stage_work(c: dict):
    """Etapa 'de trabajo' del lead (para SLA/transiciones): la del trato ACTIVO si
    existe (lo que hay que trabajar ahora); si no, la más avanzada (_stage)."""
    for d in (c.get("_deals") or []):
        if d.get("tipo") == "activo" and d.get("stage"):
            return d["stage"]
    return c.get("_stage")


def _sincronizar_etapas(data: list):
    """LAZY: al cargar el CRM detecta cambios de ETAPA del pipeline y los registra en
    el timeline con el tiempo que estuvo en la etapa anterior. Gateado a 1 vez/~90s
    por sesión + tope de inicializaciones, best-effort → NUNCA frena ni rompe el
    render (el sistema debe seguir rápido)."""
    import time as _time
    if _time.time() - st.session_state.get("_etapas_sync_ts", 0) < 90:
        return
    st.session_state["_etapas_sync_ts"] = _time.time()
    _now = _now_cl()
    _now_iso = _now.isoformat()
    _inits = 0
    for c in data:
        try:
            _work = _stage_work(c)
            if not _work:
                continue
            _prev = (c.get("stage_actual") or "").strip()
            if not _prev:                        # baseline (1 vez por lead), sin loguear
                if _inits >= 60:                 # tope: no frenar la 1ª carga
                    continue
                _desde = c.get("fecha_creacion") or _now_iso
                if actualizar_etapa_tracking(c["id"], _work, _desde):
                    c["stage_actual"] = _work
                    c["stage_desde"] = _desde
                    _inits += 1
                continue
            if _work != _prev:                   # ¡transición! → timeline + tracking
                _pd = _parse_iso(c.get("stage_desde") or c.get("fecha_creacion"))
                _dur = _fmt_duracion((_now - _pd).total_seconds()) if _pd else ""
                _plbl = _STAGE_META.get(_prev, (_prev,))[0]
                _wlbl = _STAGE_META.get(_work, (_work,))[0]
                _det = f"Estuvo {_dur} en {_plbl}" if (_dur and _prev not in _STAGE_TERMINAL) else ""
                registrar_actividad(c["id"], "etapa", f"Pasó a {_wlbl}", detalle=_det)
                actualizar_etapa_tracking(c["id"], _work, _now_iso)
                c["stage_actual"] = _work
                c["stage_desde"] = _now_iso
        except Exception:
            continue


def _sla_clock_html(desde_iso, stage, lg=False) -> str:
    """Reloj SLA (rojo, EN VIVO — lo tickea `_SLA_TICK_JS`) del tiempo que lleva el
    lead en su etapa actual. Solo en etapas ACTIVAS (no en Ganado/Perdido)."""
    if stage in _STAGE_TERMINAL:
        return ""
    _d = _parse_iso(desde_iso)
    if not _d:
        return ""
    _ini = _fmt_duracion((_now_cl() - _d).total_seconds())
    _cls = "cli-sla cli-sla-lg" if lg else "cli-sla"
    return (f'<span class="{_cls}" data-since="{_esc(_d.isoformat())}" title="Tiempo en esta etapa">'
            f'{_SLA_CLOCK_ICO}<span class="cli-sla-t">{_esc(_ini)}</span></span>')


_SLA_TICK_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function fmt(secs){
    secs=Math.max(0,Math.floor(secs));
    var d=Math.floor(secs/86400); secs-=d*86400;
    var h=Math.floor(secs/3600); secs-=h*3600;
    var m=Math.floor(secs/60), s=secs-m*60;
    if(d) return d+'d '+h+'h';
    if(h) return h+'h '+m+'m';
    if(m) return m+'m '+s+'s';
    return s+'s';
  }
  function tick(){
    var els=D.querySelectorAll('.cli-sla[data-since]'), now=Date.now();
    for(var i=0;i<els.length;i++){
      var since=Date.parse(els[i].getAttribute('data-since')); if(isNaN(since)) continue;
      var t=els[i].querySelector('.cli-sla-t'); if(t) t.textContent=fmt((now-since)/1000);
    }
  }
  if(W._cliSlaTimer){ clearInterval(W._cliSlaTimer); }
  tick(); W._cliSlaTimer=setInterval(tick, 1000);
})();
</script>"""


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
  border-radius:12px;padding:10px 14px;box-shadow:0 3px 16px rgba(30,36,71,.06);margin:6px 0 2px;}
.cli-sbar:focus-within{border-color:#c7d2fe;box-shadow:0 3px 16px rgba(91,124,250,.15);}
.cli-sbar input{flex:1 1 auto;border:none;outline:none;background:transparent;min-width:0;
  font-family:Montserrat,sans-serif;font-size:.86rem;font-weight:600;color:#0f172a;}
.cli-sbar input::placeholder{color:#94a3b8;font-weight:500;}
.cli-sbar .cli-sico{display:inline-flex;flex:0 0 auto;color:#94a3b8;}
/* Paginación del Maestro */
.cli-pgn{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;
  margin-top:12px;padding:2px;font-family:Montserrat,sans-serif;}
.cli-pgn-info{font-size:0.76rem;color:#64748b;font-weight:700;}
.cli-pgn-nav{display:flex;align-items:center;gap:8px;}
.cli-pgn-pages{font-size:0.76rem;color:#334155;font-weight:800;min-width:46px;text-align:center;}
.cli-pgn-btn{background:#fff;border:1px solid #e2e8f0;border-radius:8px;padding:6px 12px;
  font-size:0.78rem;font-weight:700;color:#334155;cursor:pointer;transition:background .12s,border-color .12s,color .12s;}
.cli-pgn-btn:hover:not(:disabled){background:#eef2ff;border-color:#c7d2fe;color:#4f46e5;}
.cli-pgn-btn:disabled{opacity:.45;cursor:default;}
.cli-pgn-size-l{font-size:0.74rem;color:#94a3b8;font-weight:700;display:flex;align-items:center;gap:6px;}
.cli-pgn-size{border:1px solid #e2e8f0;border-radius:7px;padding:4px 7px;font-size:0.76rem;
  font-weight:700;color:#334155;background:#fff;cursor:pointer;}
.cli-empty-ph{text-align:center;color:#94a3b8;padding:40px;font-family:Montserrat,sans-serif;
  font-weight:600;border:1px dashed #d7ddf0;border-radius:14px;margin-top:10px;}
/* Barra de filtros rápidos (badges) — tarjeta agrupada, client-side sin reruns */
.cli-fbar{display:flex;flex-wrap:wrap;gap:10px;background:#fff;border:1px solid #e9edf5;border-radius:14px;
  padding:10px 12px;box-shadow:0 2px 12px rgba(30,36,71,.05);margin:6px 0 16px;}
.cli-fdd{position:relative;flex:1 1 190px;min-width:0;}
.cli-fdd-trg{width:100%;height:48px;display:flex;align-items:center;gap:11px;padding:0 12px;
  border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;cursor:pointer;
  font-family:Montserrat,sans-serif;transition:all .12s;}
.cli-fdd-trg:hover{border-color:#cbd5e1;}
.cli-fdd.active .cli-fdd-trg{border-color:#c7d2fe;background:#f5f7ff;}
.cli-fdd-body{display:flex;align-items:center;gap:11px;flex:1;min-width:0;}
.cli-fdd-ph{font-weight:700;font-size:13px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cli-fdd-cur{font-weight:800;font-size:14px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cli-fdd-cv{margin-left:auto;flex:0 0 auto;color:#94a3b8;transition:transform .15s;}
.cli-fdd.open .cli-fdd-cv{transform:rotate(180deg);}
.cli-fdd-menu{display:none;position:absolute;top:calc(100% + 6px);left:0;min-width:100%;max-height:320px;
  overflow-y:auto;background:#fff;border:1px solid #e2e8f0;border-radius:13px;
  box-shadow:0 14px 40px rgba(15,23,42,.18);z-index:2147483000;padding:6px;}
.cli-fdd.open .cli-fdd-menu{display:block;}
.cli-fdd-menu .cli-fpills{display:flex;flex-direction:column;gap:2px;}
/* Fila de opción (mismo diseño que el dropdown de ejecutivo de COTIZACIONES):
   avatar/icono redondo 32px + nombre 13px/700 Montserrat + conteo facetado. */
.cli-fpill{width:100%;display:flex;align-items:center;gap:10px;background:none;border:none;cursor:pointer;
  padding:7px 9px;border-radius:9px;font-family:Montserrat,sans-serif;font-weight:700;font-size:13px;
  color:#0f172a;text-align:left;transition:background .12s;}
.cli-fpill:hover{background:#f1f5f9;}
.cli-fpill.on{background:#eef2ff;}
.cli-fpill-lb{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.cli-fpill-ic{width:32px;height:32px;border-radius:50%;flex:0 0 auto;display:flex;align-items:center;
  justify-content:center;overflow:hidden;box-shadow:0 3px 9px rgba(5,12,28,.16);}
.cli-fpill-ic svg{width:15px;height:15px;}
.cli-fpill-ic-all{background:#e2e8f0;color:#64748b;box-shadow:none;}
.cli-fpill-av{display:inline-flex;flex:0 0 auto;}
.cli-fpill-av > div{box-shadow:0 3px 9px rgba(5,12,28,.16)!important;}
.cli-fcount{font-size:0.7rem;font-weight:800;color:#94a3b8;background:#f1f5f9;padding:1px 7px;border-radius:99px;
  min-width:16px;text-align:center;flex:0 0 auto;}
.cli-fpill.on .cli-fcount{background:#e0e7ff;color:#4338ca;}
.cli-fpill.on .cli-fpill-ic-all{background:#c7d2fe;color:#4338ca;}
/* Dropdown "Ejecutivo asignado" con foto (estilo dropdown de COTIZACIONES) */
.cli-asig{margin:8px 0 2px;}
.cli-asig-lbl{font-size:0.66rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;margin-bottom:5px;}
.cli-asig-wrap{position:relative;}
.cli-asig-chip{width:100%;min-height:46px;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;
  cursor:pointer;display:flex;align-items:center;gap:10px;padding:6px 12px;font-family:Montserrat,sans-serif;}
.cli-asig-chip:hover{border-color:#cbd5e1;}
.cli-asig-nm{font-weight:700;font-size:13px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;text-align:left;}
.cli-asig-ph{font-weight:700;font-size:13px;color:#94a3b8;flex:1;text-align:left;}
.cli-asig-cv{color:#94a3b8;font-size:11px;margin-left:auto;flex:0 0 auto;}
.cli-asig-menu{display:none;position:absolute;top:calc(100% + 6px);left:0;right:0;max-height:280px;overflow-y:auto;
  background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 12px 34px rgba(15,23,42,0.18);
  z-index:2147483000;padding:5px;}
.cli-asig-menu.open{display:block;}
.cli-asig-opt{width:100%;display:flex;align-items:center;gap:10px;background:none;border:none;cursor:pointer;
  padding:7px 9px;border-radius:8px;font-family:Montserrat,sans-serif;font-size:13px;font-weight:600;color:#0f172a;text-align:left;}
.cli-asig-opt:hover{background:#f1f5f9;}
.cli-asig-opt > span:last-child{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;}
.cli-asig-none{width:26px;height:26px;border-radius:50%;background:#e2e8f0;color:#64748b;display:flex;
  align-items:center;justify-content:center;flex:0 0 auto;}
/* Campos copiables de la ficha (click para copiar) */
.cli-copy{cursor:pointer;transition:color .12s;}
.cli-copy:hover{color:#2563eb;text-decoration:underline dotted;text-underline-offset:2px;}
.cli-wa{display:inline-flex;align-items:center;gap:5px;color:#128c3e;font-weight:600;
  text-decoration:none;cursor:pointer;transition:color .12s;}
.cli-wa:hover{color:#25d366;text-decoration:underline;text-underline-offset:2px;}
/* Botón "Ver plano cliente" (abre el plano en pestaña nueva; NO usa .cli-wa para
   que el handler de WhatsApp no lo intercepte). */
.cli-plano{display:inline-flex;align-items:center;gap:5px;color:#4f46e5;font-weight:700;font-size:0.78rem;
  background:#eef2ff;padding:4px 11px;border-radius:8px;text-decoration:none;cursor:pointer;
  transition:background .13s,color .13s;margin-top:2px;}
.cli-plano svg{width:13px;height:13px;flex-shrink:0;}
.cli-plano:hover{background:#4f46e5;color:#fff;}
/* ── Lead Score (llama por nivel) ── */
.cli-score{display:inline-flex;flex-direction:column;align-items:center;justify-content:center;
  border-radius:11px;flex:0 0 auto;line-height:1;}
.cli-score .n{font-weight:800;margin-top:1px;}
.cli-score-sm{width:38px;height:38px;border-radius:10px;}
.cli-score-sm .n{font-size:0.72rem;}
.cli-score-md{width:56px;height:56px;border-radius:14px;}
.cli-score-md .n{font-size:0.95rem;}
.cli-score-hot{background:rgba(220,38,38,.12);border:1.5px solid #dc2626;color:#dc2626;}
.cli-score-warm{background:rgba(217,119,6,.14);border:1.5px solid #d97706;color:#d97706;}
.cli-score-cold{background:rgba(37,99,235,.12);border:1.5px solid #2563eb;color:#2563eb;}
/* Desglose del score en la ficha */
.cli-scbrk{display:flex;flex-direction:column;gap:7px;margin:2px 0 6px;}
.cli-scrow{display:grid;grid-template-columns:88px 1fr 46px;align-items:center;gap:9px;}
.cli-sck{font-size:0.74rem;color:#475569;}
.cli-scbar{display:block;position:relative;width:100%;height:9px;border-radius:999px;overflow:hidden;
  background:linear-gradient(90deg,#ef4444 0%,#f97316 28%,#facc15 52%,#84cc16 76%,#22c55e 100%);}
.cli-scdim{position:absolute;top:0;bottom:0;right:0;background:rgba(236,239,245,.82);transition:left .3s ease;}
.cli-scv{font-size:0.72rem;font-weight:700;color:#64748b;text-align:right;}
.cli-schint{font-size:0.76rem;color:#475569;background:#fff7ed;border:1px dashed #f59e0b;
  border-radius:9px;padding:7px 10px;margin-top:6px;}

/* ── Kanban ── */
.cli-kb-wrap{overflow-x:auto;padding:6px 6px 18px;margin-top:12px;}
.cli-kb{display:flex;gap:12px;min-width:920px;}
.cli-kb-col{flex:1;min-width:150px;background:#f8fafc;border-radius:12px;padding:10px;}
.cli-kb-hd{display:flex;align-items:center;gap:7px;margin-bottom:3px;}
.cli-kb-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;}
.cli-kb-nm{font-family:'Plus Jakarta Sans',sans-serif;font-size:12px;font-weight:800;color:#0f172a;
  text-transform:uppercase;letter-spacing:.03em;}
.cli-kb-ct{margin-left:auto;font-size:11px;color:#94a3b8;font-weight:700;}
/* Subtítulo aclaratorio de la columna: si los leads de esa etapa tienen o no presupuesto. */
.cli-kb-sub{display:inline-flex;align-items:center;gap:4px;font-size:9.5px;font-weight:700;
  padding:2px 8px;border-radius:20px;margin:0 0 10px 15px;letter-spacing:.02em;}
.cli-kb-sub svg{width:11px;height:11px;flex-shrink:0;}
.cli-kb-sub.sin{background:#fff7ed;color:#c2410c;}
.cli-kb-sub.con{background:#eef2ff;color:#4f46e5;}
.cli-card{background:#fff;border:1px solid #e6e9f4;border-radius:10px;padding:10px;margin-bottom:8px;
  cursor:pointer;transition:box-shadow .16s ease,transform .16s ease,border-color .16s ease;}
/* Hover: la card hace un poco de zoom y se levanta; la SOMBRA toma el color de la
   etapa (data-stage). Cada etapa su color. */
.cli-card:hover{transform:translateY(-3px) scale(1.03);position:relative;z-index:3;
  box-shadow:0 10px 26px rgba(30,36,71,.16);}
.cli-card[data-stage="lead_nuevo"]:hover{box-shadow:0 10px 26px rgba(136,135,128,.32);border-color:#e2e2df;}
.cli-card[data-stage="contactado"]:hover{box-shadow:0 10px 28px rgba(55,138,221,.42);border-color:#bfdbfe;}
.cli-card[data-stage="en_presupuesto"]:hover{box-shadow:0 10px 28px rgba(127,119,221,.44);border-color:#ddd6fe;}
.cli-card[data-stage="propuesta_enviada"]:hover{box-shadow:0 10px 28px rgba(239,159,39,.46);border-color:#fed7aa;}
.cli-card[data-stage="ganado"]:hover{box-shadow:0 10px 28px rgba(29,158,117,.46);border-color:#bbf7d0;}
.cli-card[data-stage="perdido"]:hover{box-shadow:0 10px 26px rgba(148,163,184,.38);border-color:#e2e8f0;}
.cli-card-nm{font-family:Montserrat,sans-serif;font-size:12.5px;font-weight:800;color:#0f172a;line-height:1.3;}
.cli-card-lbl{font-size:8.5px;color:#94a3b8;font-weight:800;text-transform:uppercase;letter-spacing:.05em;margin-top:7px;}
.cli-card-mt{font-size:13px;color:#0f172a;font-weight:800;margin:1px 0 0;}
.cli-card-none{font-size:11px;color:#ea580c;font-weight:800;margin-top:7px;}
.cli-card-sub{font-size:10.5px;color:#94a3b8;font-weight:600;display:flex;align-items:center;gap:5px;}
.cli-fuente-b{display:inline-flex;align-items:center;gap:4px;font-size:9px;font-weight:800;padding:2px 7px;
  border-radius:20px;text-transform:uppercase;letter-spacing:.02em;}
/* Etiqueta de TRATO (solo cuando un cliente tiene activo + historial): distingue
   las 2 cards para que no parezcan un duplicado. */
.cli-card-nota{display:inline-flex;align-items:center;font-size:8.5px;font-weight:800;padding:2px 7px;
  border-radius:20px;text-transform:uppercase;letter-spacing:.02em;}
.cli-nota-activo{background:#dcfce7;color:#15803d;}
.cli-nota-cerrado{background:#f1f5f9;color:#64748b;}
/* Chips de engagement de un correo (Abrió/Click/Rebotó/Spam), bajo el asunto. */
.cli-mchip{display:inline-flex;align-items:center;font-size:9px;font-weight:800;padding:1px 7px;
  border-radius:20px;text-transform:uppercase;letter-spacing:.02em;}
/* Reloj SLA (rojo, en vivo): tiempo que el lead lleva en su etapa actual. */
.cli-sla{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:800;padding:2px 8px;
  border-radius:20px;background:#fee2e2;color:#dc2626;font-variant-numeric:tabular-nums;white-space:nowrap;}
.cli-sla svg{width:11px;height:11px;flex-shrink:0;}
.cli-sla-lg{font-size:12px;padding:4px 11px;}
.cli-card-date{font-size:9px;color:#b4bccd;font-weight:600;text-align:right;margin-top:8px;
  display:flex;align-items:center;justify-content:flex-end;gap:4px;}
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
/* Divisor de ZONA de la ficha: línea de separación + chip de icono + título + conteo */
.cli-zsec{display:flex;align-items:center;gap:9px;margin:22px 0 12px;padding-top:15px;
  border-top:1px solid #e6e9f4;}
.cli-zsec-ic{display:inline-flex;width:24px;height:24px;align-items:center;justify-content:center;
  border-radius:8px;background:#eef2ff;color:#5b7cfa;flex-shrink:0;}
.cli-zsec-t{font-family:Montserrat,sans-serif;font-weight:800;font-size:0.74rem;letter-spacing:.07em;
  text-transform:uppercase;color:#0f172a;}
.cli-zsec-b{margin-left:auto;background:#f1f5f9;color:#64748b;font-family:Montserrat,sans-serif;
  font-weight:800;font-size:0.7rem;padding:2px 9px;border-radius:999px;}
/* Variante para zonas CON botón de acción: la línea separadora va sola (full-width)
   y el título (icono+texto) comparte fila st.columns con el botón (Editar/Crear). */
.cli-zline{border-top:1px solid #e6e9f4;margin:22px 0 14px;}
.cli-zsec-hd{display:flex;align-items:center;gap:9px;}
.cli-zsec-hb{background:#eef2ff;color:#5b7cfa;font-family:Montserrat,sans-serif;font-weight:800;
  font-size:0.7rem;padding:1px 8px;border-radius:999px;margin-left:7px;}
/* Botón "Editar" de la ficha: limpio (sin borde/sombra/fondo), azul → rojo al hover */
.st-key-_cli_ed_open button,[class*="st-key-_cli_calfedit_"] button{
  border:none!important;background:transparent!important;box-shadow:none!important;
  min-height:0!important;padding:4px 2px!important;justify-content:flex-end!important;}
.st-key-_cli_ed_open button:hover,[class*="st-key-_cli_calfedit_"] button:hover,
.st-key-_cli_ed_open button:focus,[class*="st-key-_cli_calfedit_"] button:focus{
  background:transparent!important;border:none!important;box-shadow:none!important;}
.st-key-_cli_ed_open button,.st-key-_cli_ed_open button *,
[class*="st-key-_cli_calfedit_"] button,[class*="st-key-_cli_calfedit_"] button *{
  color:#5b7cfa!important;transition:color .12s;}
.st-key-_cli_ed_open button:hover,.st-key-_cli_ed_open button:hover *,
[class*="st-key-_cli_calfedit_"] button:hover,[class*="st-key-_cli_calfedit_"] button:hover *{
  color:#dc2626!important;}
/* "Crear presupuesto": una sola línea */
.st-key-_cli_fh_nuevo button,.st-key-_cli_fh_nuevo button p{white-space:nowrap!important;}
/* Formulario "Nueva actividad": encabezado, separadores, ayuda y tipografía chica */
.cli-actf-h{font-family:Montserrat,sans-serif;font-weight:700;font-size:0.78rem;letter-spacing:0.05em;
  text-transform:uppercase;color:#0f172a;margin:0 0 8px;}
.cli-actf-sep{height:1px;background:#e6e9f4;margin:12px 0;}
.cli-actf-hint{font-size:0.75rem;color:#64748b;line-height:1.35;margin:0 0 6px;}
/* Compositor de correo: label de herramientas + botones compactos emoji/variable */
.cli-mail-tools-lbl{font-size:0.64rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;
  color:#94a3b8;margin:6px 0 2px;}
.st-key-_cli_mail_form [class*="st-key-_cli_emo_"] button{padding:2px 0!important;min-height:34px!important;
  font-size:1.05rem!important;line-height:1!important;}
.st-key-_cli_mail_form [class*="st-key-_cli_var_"] button{padding:3px 2px!important;min-height:32px!important;
  font-size:0.7rem!important;}
.st-key-_cli_act_form label p,.st-key-_cli_act_form [data-testid="stWidgetLabel"] p,
.st-key-_cli_mail_form label p,.st-key-_cli_mail_form [data-testid="stWidgetLabel"] p,
.st-key-_cli_edit_form label p,.st-key-_cli_edit_form [data-testid="stWidgetLabel"] p{
  font-size:0.72rem!important;}
.st-key-_cli_act_form input,.st-key-_cli_act_form [data-baseweb="select"],
.st-key-_cli_mail_form input,.st-key-_cli_mail_form textarea,
.st-key-_cli_edit_form input,.st-key-_cli_edit_form [data-baseweb="select"]{font-size:0.86rem;}
.st-key-_cli_act_form [data-testid="stElementContainer"]{margin-bottom:2px;}
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


def _cp(val, inner, title="Copiar"):
    """Envuelve `inner` (HTML ya escapado) en un span copiable si `val` no es
    vacío; si no, devuelve `inner` tal cual. El click lo maneja _CLI_COPY_JS."""
    v = str(val or "").strip()
    if not v:
        return inner
    return f'<span class="cli-copy" data-copy="{_esc(v)}" title="{title}">{inner}</span>'


def _fmt_fecha_local(iso_str) -> str:
    """Timestamp ISO → hora de Chile 'dd-mm-YYYY HH:MM'. Supabase devuelve los
    timestamptz en UTC (+00:00); antes se mostraba ese valor crudo (4h adelantado).
    Se convierte a America/Santiago (con DST → UTC-4 en invierno, UTC-3 en verano);
    si no hay tzdata, cae a UTC-3."""
    if not iso_str:
        return ""
    try:
        dt = _dt.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        try:
            if _ZoneInfo is None:
                raise RuntimeError
            dt = dt.astimezone(_ZoneInfo("America/Santiago"))
        except Exception:
            dt = dt.astimezone(_tz(_td(hours=-3)))
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return str(iso_str)[:16].replace("T", " ")


# ── Actividades (tareas) tipo CRM: tipos + hora + resultado de llamada ────────
_ACT_TIPOS = ["llamada", "reunion", "correo", "tarea"]
_ACT_META = {   # tipo -> (label, svg_path)
    "llamada": ("Llamada", '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>'),
    "reunion": ("Reunión", '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'),
    "correo":  ("Correo", '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'),
    "tarea":   ("Tarea", '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>'),
}
_ACT_MAT = {"llamada": ":material/call:", "reunion": ":material/groups:",
            "correo": ":material/mail:", "tarea": ":material/task_alt:"}
_RESULT_META = {  # resultado -> (label, bg, fg)
    "contesto": ("Contestó", "#dcfce7", "#15803d"),
    "no_contesto": ("No contestó", "#fef3c7", "#b45309"),
    "se_corto": ("Se cortó", "#ffedd5", "#c2410c"),
    "llamar_tarde": ("Llamar más tarde", "#e0e7ff", "#4338ca"),
    "no_interesado": ("No interesado", "#fee2e2", "#b91c1c"),
}
# Motivos de "no pude hablar" (todos reagendan). label -> código de resultado.
_REINTENTO_MOTIVOS = {
    "No contestó": "no_contesto",
    "Se cortó la llamada": "se_corto",
    "Llamar más tarde": "llamar_tarde",
}
_TIPO_CAMPO_LABEL = {
    "texto": "Texto", "numero": "Número / monto",
    "opciones": "Opciones", "si_no": "Sí / No",
}


def _ahora_scl():
    try:
        if _ZoneInfo is None:
            raise RuntimeError
        return _dt.now(_ZoneInfo("America/Santiago"))
    except Exception:
        return _dt.now(_tz(_td(hours=-3)))


def _mk_vence(fecha, hora) -> str:
    """Combina fecha + hora en un ISO con la zona de Chile (para que se guarde y
    se muestre en la hora local que eligió el usuario)."""
    dtv = _dt.combine(fecha, hora)
    try:
        if _ZoneInfo is None:
            raise RuntimeError
        return dtv.replace(tzinfo=_ZoneInfo("America/Santiago")).isoformat()
    except Exception:
        return dtv.replace(tzinfo=_tz(_td(hours=-3))).isoformat()


def _act_vencida(vence_iso) -> bool:
    """True si la actividad ya venció (vence <= ahora, comparando en UTC)."""
    try:
        dt = _dt.fromisoformat(str(vence_iso).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_tz.utc)
        return dt <= _dt.now(_tz.utc)
    except Exception:
        return False


def _default_hora():
    """Próxima hora en punto (Chile) como valor por defecto del time_input."""
    return (_ahora_scl() + _td(hours=1)).replace(minute=0, second=0, microsecond=0).time()


# ── Guión de calificación (Fase B) ────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _preguntas_data() -> list:
    """Preguntas ACTIVAS del guión (ordenadas). Cacheado; se limpia al editar el
    guión. Alimenta tanto la captura en la llamada como la ficha."""
    return listar_preguntas(solo_activas=True)


def _cli_calif(cli) -> dict:
    """Respuestas ya capturadas del cliente ({pregunta_id: valor}), tolerando que
    venga como dict (jsonb) o string."""
    v = cli.get("calificacion") or {}
    if isinstance(v, str):
        try:
            v = _json.loads(v)
        except Exception:
            v = {}
    return v if isinstance(v, dict) else {}


def _guion_inputs(cli, key_prefix: str):
    """Renderiza un input por cada pregunta activa, precargado con lo que ya se
    sabe del cliente. Devuelve (valores{pid:val}, preguntas). Si no hay preguntas
    configuradas devuelve (None, [])."""
    preguntas = _preguntas_data()
    if not preguntas:
        return None, []
    actual = _cli_calif(cli)
    valores = {}
    for p in preguntas:
        pid = str(p.get("id"))
        tipo = p.get("tipo_campo") or "texto"
        lbl = p.get("texto", "") or "—"
        k = f"{key_prefix}_{pid}"
        prev = str(actual.get(pid, "") or "")
        if tipo == "opciones":
            ops = [""] + [str(o) for o in (p.get("opciones") or [])]
            idx = ops.index(prev) if prev in ops else 0
            valores[pid] = st.selectbox(lbl, ops, index=idx, key=k,
                                        format_func=lambda x: x or "— Selecciona —")
        elif tipo == "si_no":
            ops = ["", "Sí", "No"]
            idx = ops.index(prev) if prev in ops else 0
            valores[pid] = st.radio(lbl, ops, index=idx, key=k, horizontal=True,
                                    format_func=lambda x: x or "—")
        elif tipo == "numero":
            valores[pid] = st.text_input(lbl, value=prev, key=k,
                                         placeholder="Ej: 25.000.000")
        else:
            valores[pid] = st.text_input(lbl, value=prev, key=k)
    return valores, preguntas


def _resumen_calificacion(valores, preguntas) -> str:
    """Texto corto 'Pregunta: valor · …' para la línea de tiempo (solo campos con
    valor)."""
    if not valores:
        return ""
    txt = {str(p.get("id")): (p.get("texto", "") or "") for p in (preguntas or [])}
    partes = [f"{txt.get(pid, '')}: {v}" for pid, v in valores.items() if str(v or "").strip()]
    return " · ".join(partes)


# ── Lead Score (potencial del lead según qué tan completa es su info) ──────────
# 0–100: Contacto 40 + Calificación 45 + Interés 15. Niveles Frío/Tibio/Caliente.
_FLAME_PATH = ('<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 '
               '2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 '
               '1-3a2.5 2.5 0 0 0 2.5 2.5z"/>')
# umbral inferior -> (key, label). Se evalúa de mayor a menor.
_SCORE_TIERS = [(70, "hot", "Caliente"), (40, "warm", "Tibio"), (0, "cold", "Frío")]
# Campos de contacto que puntúan (label, key, puntos) = 40.
_SCORE_CONTACTO = [("teléfono", "telefono", 10), ("correo", "email", 10),
                   ("RUT", "rut", 8), ("dirección", "direccion", 6), ("comuna", "comuna", 6)]


def _rut_ok(rut) -> bool:
    """RUT cuenta para el score solo si es real (no vacío ni el relleno 00.000.000-0)."""
    r = "".join(ch for ch in str(rut or "").lower() if ch.isalnum())
    core = r[:-1] if r[-1:] == "k" else r
    return bool(r) and len(r) >= 7 and set(core) != {"0"}


def _lead_score(cli, preguntas) -> dict:
    """Calcula el score 0–100 del lead + desglose. `preguntas` = guión activo
    (para la parte de Calificación, que se adapta a lo que configure el admin)."""
    contacto = 0
    for _lbl, _k, _pts in _SCORE_CONTACTO:
        if _k == "rut":
            if _rut_ok(cli.get("rut")):
                contacto += _pts
        elif str(cli.get(_k) or "").strip():
            contacto += _pts
    # Calificación: proporción de preguntas activas respondidas × 45.
    calif = 0
    if preguntas:
        cur = _cli_calif(cli)
        _ans = sum(1 for p in preguntas if str(cur.get(str(p.get("id")), "") or "").strip())
        calif = round(_ans / len(preguntas) * 45)
    # Interés: tiene ≥1 presupuesto (10) + asignado a un ejecutivo (5).
    interes = (10 if (cli.get("_cotizaciones") or []) else 0) \
        + (5 if str(cli.get("asignado_email") or "").strip() else 0)
    total = max(0, min(100, contacto + calif + interes))
    _key, _label = next((k, l) for mn, k, l in _SCORE_TIERS if total >= mn)
    return {"total": total, "contacto": contacto, "calif": calif, "interes": interes,
            "key": _key, "label": _label}


def _score_badge(sc: dict, size: str = "sm") -> str:
    """Badge de llama con el número, coloreado por nivel. size = sm|md."""
    _px = 12 if size == "sm" else 16
    return (f'<div class="cli-score cli-score-{size} cli-score-{sc["key"]}" '
            f'title="Score {sc["total"]} · {sc["label"]}">'
            f'{_svg(_FLAME_PATH, _px, "currentColor")}'
            f'<span class="n">{sc["total"]}</span></div>')


def _score_faltantes(cli, preguntas, sc: dict) -> list:
    """Top ítems que más subirían el score (para el hint de la ficha)."""
    faltan = []
    for _lbl, _k, _pts in _SCORE_CONTACTO:
        _falta = (not _rut_ok(cli.get("rut"))) if _k == "rut" else (not str(cli.get(_k) or "").strip())
        if _falta:
            faltan.append((_lbl, _pts))
    if preguntas:
        cur = _cli_calif(cli)
        _na = sum(1 for p in preguntas if not str(cur.get(str(p.get("id")), "") or "").strip())
        if _na:
            faltan.append((f"{_na} pregunta(s) del guión", round(_na / len(preguntas) * 45)))
    if not (cli.get("_cotizaciones") or []):
        faltan.append(("crear un presupuesto", 10))
    faltan.sort(key=lambda x: -x[1])
    return faltan[:3]


@st.cache_data(ttl=60, show_spinner=False)
def _cli_data(rol: str = "root", email: str = "") -> list:
    """Maestro enriquecido con el pipeline DERIVADO (_stage/_cotizaciones/_monto).
    root/admin ven TODOS; ejecutivo ve SOLO sus clientes asignados (por
    asignado_email). Cacheado por (rol,email); se limpia al mutar/sincronizar."""
    _all = enriquecer_con_pipeline(listar_clientes(solo_activos=True))
    if rol == "ejecutivo":
        _e = (email or "").strip().lower()
        return [c for c in _all if (c.get("asignado_email") or "").strip().lower() == _e]
    return _all


@st.cache_data(ttl=60, show_spinner=False)
def _cli_polluted() -> set:
    """Identidades compartidas (placeholders) para la dedup del alta manual."""
    return identidades_compartidas()


def _kpi(label, valor, color="#0f172a"):
    return (
        '<div style="background:#fff;border:1px solid #e9edf5;border-radius:14px;padding:13px 16px;'
        'box-shadow:0 2px 10px rgba(30,36,71,.045);display:flex;flex-direction:column;gap:4px;">'
        f'<div style="font-size:0.66rem;color:#94a3b8;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:.05em;">{label}</div>'
        f'<div style="font-family:Montserrat,sans-serif;font-size:1.55rem;font-weight:800;'
        f'color:{color};line-height:1.1;">{valor}</div></div>')


_ORIGEN_COLORS = {
    "shopify": ("#ede9fe", "#6d28d9"),
    "web":     ("#e0f2fe", "#0369a1"),
    "manual":  ("#f1f5f9", "#475569"),
}


def _origen_pill(origen: str) -> str:
    _bg, _fg = _ORIGEN_COLORS.get(str(origen or "").split(" ")[0].lower(), _ORIGEN_COLORS["manual"])
    return f'<span class="cli-pill" style="background:{_bg};color:{_fg};">{_esc(origen)}</span>'


# Fuente del lead (para el filtro "Fuente"): etiqueta + icono + color por origen.
# Diseñado para CRECER: hoy Shopify/Importado/Manual/Web; mañana Google Ads,
# Facebook, TikTok, Instagram (solo con que el lead llegue con ese `origen`).
_FUENTE_META = {
    "shopify":    ("Shopify",    '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>', "#6d28d9", "rgba(109,40,217,.12)"),
    "importado":  ("Importado",  '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>', "#0369a1", "rgba(3,105,161,.12)"),
    "manual":     ("Manual",     '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>', "#475569", "rgba(100,116,139,.12)"),
    "web":        ("Web",        '<circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/><path d="M2 12h20"/>', "#0891b2", "rgba(8,145,178,.12)"),
    "google ads": ("Google Ads", '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>', "#ea4335", "rgba(234,67,53,.12)"),
    "google":     ("Google Ads", '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>', "#ea4335", "rgba(234,67,53,.12)"),
    "facebook":   ("Facebook",   '<path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z"/>', "#1877f2", "rgba(24,119,242,.12)"),
    "instagram":  ("Instagram",  '<rect width="20" height="20" x="2" y="2" rx="5" ry="5"/><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"/><line x1="17.5" x2="17.51" y1="6.5" y2="6.5"/>', "#c13584", "rgba(193,53,132,.12)"),
    "tiktok":     ("TikTok",     '<path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5"/>', "#0f172a", "rgba(15,23,42,.10)"),
}
# Icono/colores por defecto para una fuente futura que aún no esté en el mapa.
_FUENTE_DEFAULT = ('<path d="M12 2H2v10l9.29 9.29a1 1 0 0 0 1.42 0l8.58-8.58a1 1 0 0 0 0-1.42Z"/><circle cx="7" cy="7" r="1"/>',
                   "#475569", "rgba(100,116,139,.12)")


def _fuente_norm(origen) -> str:
    """Valor de fuente para agrupar/filtrar: el `origen` tal cual (vacío → Manual)."""
    return (str(origen or "").strip() or "Manual")


def _fuente_meta(fuente: str):
    """(label, icon_path, fg, bg) de una fuente; default para las desconocidas."""
    _m = _FUENTE_META.get(str(fuente or "").strip().lower())
    if _m:
        return _m
    _ic, _fg, _bg = _FUENTE_DEFAULT
    return (str(fuente or "").strip() or "Manual", _ic, _fg, _bg)


def _fuente_badge(origen) -> str:
    """Badge chico (icono + etiqueta + color) de la fuente, para la card del lead."""
    _lbl, _ico, _fg, _bg = _fuente_meta(_fuente_norm(origen))
    return (f'<span class="cli-fuente-b" style="background:{_bg};color:{_fg};">'
            f'{_svg(_ico, 11, "currentColor")}{_esc(_lbl)}</span>')


# Iconos (path SVG) de cada ZONA de la ficha, para los separadores.
_ZIC_DATOS = '<rect width="18" height="18" x="3" y="4" rx="2"/><circle cx="9" cy="10" r="2"/><path d="M15 8h2"/><path d="M15 12h2"/><path d="M7 16h10"/>'
_ZIC_ASIGNAR = '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>'
_ZIC_CORREO = '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>'
_ZIC_ACTIV = '<rect x="3" y="5" width="6" height="6" rx="1"/><path d="m3 17 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>'
_ZIC_CALIF = '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>'
_ZIC_SHOPIFY = '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z"/><path d="M3 6h18"/><path d="M16 10a4 4 0 0 1-8 0"/>'
_ZIC_PRESUP = '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/>'
_ZIC_HIST = '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>'


def _zsec(title: str, icon_path: str, badge=None) -> str:
    """Divisor de ZONA de la ficha: línea separadora + chip de icono + título
    (+ conteo opcional). Deja cada funcionalidad claramente distinguida."""
    _b = (f'<span class="cli-zsec-b">{_esc(str(badge))}</span>'
          if badge not in (None, "") else "")
    return (f'<div class="cli-zsec"><span class="cli-zsec-ic">'
            f'{_svg(icon_path, 13, "currentColor")}</span>'
            f'<span class="cli-zsec-t">{_esc(title)}</span>{_b}</div>')


def _zline() -> str:
    """Solo la línea separadora de zona (cuando el título va en una fila st.columns
    junto a un botón de acción, para que ambos queden en la MISMA fila)."""
    return '<div class="cli-zline"></div>'


def _zsec_hd(title: str, icon_path: str, badge=None) -> str:
    """Encabezado de zona SIN la línea (icono + título + conteo). Va dentro de una
    columna, con el botón de acción (Editar/Crear) en la columna de al lado. El
    conteo va PEGADO al título (no empujado a la derecha, para no chocar el botón)."""
    _b = (f'<span class="cli-zsec-hb">{_esc(str(badge))}</span>'
          if badge not in (None, "") else "")
    return (f'<div class="cli-zsec-hd"><span class="cli-zsec-ic">'
            f'{_svg(icon_path, 13, "currentColor")}</span>'
            f'<span class="cli-zsec-t">{_esc(title)}</span>{_b}</div>')


# Iconos SVG por etapa para los badges de filtro (estilo COTIZACIONES).
_STAGE_ICON = {
    STAGE_LEAD: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    STAGE_CONTACTADO: '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    STAGE_PRESUPUESTO: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    STAGE_PROPUESTA: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    STAGE_GANADO: '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    STAGE_PERDIDO: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
}
_IC_TODOS = '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>'
_IC_USERS = '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>'


def _build_filter_bar(data: list) -> str:
    """Barra de filtros rápidos (badges) por ejecutivo y por estado, con color,
    icono SVG y CANTIDAD (estilo estados de COTIZACIONES). Filtrado 100%
    client-side (ver _CLI_FILTER_JS): NO dispara reruns."""
    _ejset, _ejcnt, _none = {}, {}, 0
    _stcnt = {s: 0 for s in _STAGE_ORDER}
    _tiercnt = {"hot": 0, "warm": 0, "cold": 0}
    _fucnt = {}
    for d in data:
        _e = (d.get("asignado_email") or "").strip().lower()
        if _e:
            _ejset[_e] = _resolver_asig(_e, d.get("asignado_nombre"))
            _ejcnt[_e] = _ejcnt.get(_e, 0) + 1
        else:
            _none += 1
        _stcnt[d.get("_stage") or STAGE_LEAD] += 1
        _sc = d.get("_score") or _lead_score(d, None)
        _tiercnt[_sc["key"]] = _tiercnt.get(_sc["key"], 0) + 1
        _fu = _fuente_norm(d.get("origen"))
        _fucnt[_fu] = _fucnt.get(_fu, 0) + 1
    _stages = [s for s in _STAGE_ORDER if _stcnt[s] > 0]

    def _pill(val, label, kind, count, icon, bg="", fg="", ico_html=None):
        _cls = f"cli-fpill cli-fpill-{kind}" + (" on" if val == "" else "")
        # Icono redondo 32px: avatar del ejecutivo, o círculo con el color de la
        # categoría (estado/potencial/fuente), o neutro (Todos / Sin asignar).
        if ico_html is not None:
            _ic = ico_html
        elif bg:
            _ic = (f'<span class="cli-fpill-ic" style="background:{bg};color:{fg};">'
                   f'{_svg(icon, 15, "currentColor") if icon else ""}</span>')
        else:
            _ic = (f'<span class="cli-fpill-ic cli-fpill-ic-all">'
                   f'{_svg(icon, 15, "currentColor") if icon else ""}</span>')
        return (f'<span class="{_cls}" data-fkind="{kind}" data-fval="{_esc(val)}">'
                f'{_ic}<span class="cli-fpill-lb">{_esc(label)}</span>'
                f'<b class="cli-fcount">{count}</b></span>')

    # Foto+nombre del asignado desde el directorio COMPLETO (ejecutivos + admins +
    # operación) para que ninguno caiga al correo. _usuarios_map cubre a los que no
    # son ejecutivos (fetch_ejecutivos solo trae rol 'ejecutivo').
    _ejinfo = {(e.get("email") or "").strip().lower(): e for e in _ejecutivos()}
    _umap = _usuarios_map()
    _ej = _pill("", "Todos los ejecutivos", "ej", len(data), _IC_USERS)
    for _e, _nm in sorted(_ejset.items(), key=lambda kv: (kv[1] or "").lower()):
        _einf = _ejinfo.get(_e) or {}
        _udir = _umap.get(_e) or {}
        _enm = _nm or _einf.get("nombre") or _udir.get("nombre") or _e
        _foto = _einf.get("foto_url") or _udir.get("foto_url") or ""
        _av = f'<span class="cli-fpill-av">{_avatar_html(_foto, _enm, size=32, ring="#fff", font_scale=0.4)}</span>'
        _ej += _pill(_e, _enm, "ej", _ejcnt.get(_e, 0), "", ico_html=_av)
    if _none:
        _ej += _pill("__none__", "Sin asignar", "ej", _none, _ICON_USER_PATH)
    _st = _pill("", "Todos los estados", "st", len(data), _IC_TODOS)
    for _s in _stages:
        _lbl, _dot, _bg, _fg = _STAGE_META[_s]
        _st += _pill(_s, _lbl, "st", _stcnt[_s], _STAGE_ICON.get(_s, ""), _bg, _fg)
    # Potencial (Lead Score): Caliente / Tibio / Frío, con llama y color por nivel.
    _TIER_META = [("hot", "Caliente", "#dc2626", "rgba(220,38,38,.12)"),
                  ("warm", "Tibio", "#d97706", "rgba(217,119,6,.15)"),
                  ("cold", "Frío", "#2563eb", "rgba(37,99,235,.12)")]
    _sc_pills = _pill("", "Todo el potencial", "tier", len(data), _IC_TODOS)
    for _tk, _tl, _tc, _tb in _TIER_META:
        _sc_pills += _pill(_tk, _tl, "tier", _tiercnt.get(_tk, 0), _FLAME_PATH, _tb, _tc)
    # Fuente: de dónde vino el lead (Shopify / Importado / Manual / … a futuro
    # Google Ads, Facebook, TikTok). Pills DINÁMICAS por cada `origen` presente
    # (más frecuente primero) → las fuentes nuevas aparecen solas.
    _fu = _pill("", "Todas las fuentes", "fuente", len(data), _IC_TODOS)
    for _fk in sorted(_fucnt, key=lambda x: (-_fucnt[x], x.lower())):
        _fl, _fico, _ffg, _fbg = _fuente_meta(_fk)
        _fu += _pill(_fk, _fl, "fuente", _fucnt[_fk], _fico, _fbg, _ffg)
    _chev = ('<svg class="cli-fdd-cv" width="15" height="15" viewBox="0 0 24 24" fill="none" '
             'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="m6 9 6 6 6-6"/></svg>')

    def _dd(kind, ph, pills):
        """Un dropdown de filtro (mismo diseño que el de ejecutivo de COTIZACIONES):
        chip con la selección actual (o placeholder) + menú de opciones. El filtrado
        lo sigue haciendo _CLI_FILTER_JS; el trigger lo actualiza updateTrigger()."""
        return (f'<div class="cli-fdd" data-fkind="{kind}" data-ph="{_esc(ph)}">'
                f'<button class="cli-fdd-trg" type="button" data-fkind="{kind}">'
                f'<span class="cli-fdd-body"><span class="cli-fdd-ph">{_esc(ph)}</span></span>'
                f'{_chev}</button>'
                f'<div class="cli-fdd-menu"><div class="cli-fpills">{pills}</div></div>'
                '</div>')

    return (
        '<div class="cli-fbar">'
        + _dd("ej", "Todos los ejecutivos", _ej)
        + _dd("st", "Todos los estados", _st)
        + _dd("tier", "Todo el potencial", _sc_pills)
        + _dd("fuente", "Todas las fuentes", _fu)
        + '</div>')


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

# Filtros rápidos (badges ejecutivo/estado) + buscador — TODO client-side, sin
# reruns. Aplica a la vez al pipeline (tarjetas) y al maestro (filas). Los valores
# del filtro viven en window.parent (persisten entre reruns / cambios de vista).
_CLI_FILTER_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function okQ(q){ var term=(W._cliQ||''); return !term || (q||'').indexOf(term)>=0; }
  function apply(){
    var ej=W._cliFEj||'', stg=W._cliFSt||'', tier=W._cliFTier||'', fu=W._cliFFu||'';
    function okA(v){ v=v||''; if(!ej) return true; if(ej==='__none__') return v===''; return v===ej; }
    function okS(v){ return !stg || (v||'')===stg; }
    function okT(v){ return !tier || (v||'')===tier; }
    function okF(v){ return !fu || (v||'')===fu; }
    // Tarjetas (Pipeline + Bandeja): pills (si tiene data-asig) + BÚSQUEDA (data-s).
    var cards=D.querySelectorAll('.cli-card');
    for(var i=0;i<cards.length;i++){
      var c=cards[i];
      var pillOk=!c.hasAttribute('data-asig')||(okA(c.getAttribute('data-asig'))&&okS(c.getAttribute('data-stage'))
        &&okT(c.getAttribute('data-tier'))&&okF(c.getAttribute('data-fuente')));
      c.style.display=(pillOk&&okQ(c.getAttribute('data-s')||''))?'':'none';
    }
    var cols=D.querySelectorAll('.cli-kb-col');
    for(var j=0;j<cols.length;j++){
      var cc=cols[j].querySelectorAll('.cli-card[data-asig]'), n=0;
      for(var k=0;k<cc.length;k++){ if(cc[k].style.display!=='none') n++; }
      var ct=cols[j].querySelector('.cli-kb-ct'); if(ct) ct.textContent=n;
    }
    // Maestro: filtra (pills + búsqueda) y PAGINA las filas que pasan.
    var rows=D.querySelectorAll('.cli-tbl-wrap tbody tr[data-asig]'), matching=[];
    for(var r=0;r<rows.length;r++){
      var tr=rows[r];
      var ok=okA(tr.getAttribute('data-asig'))&&okS(tr.getAttribute('data-stage'))
             &&okT(tr.getAttribute('data-tier'))&&okF(tr.getAttribute('data-fuente'))
             &&okQ(tr.getAttribute('data-s')||'');
      if(ok) matching.push(tr); else tr.style.display='none';
    }
    var m=matching.length, pageSize=W._cliPageSize||25;
    var totalPages=Math.max(1, Math.ceil(m/pageSize));
    var page=Math.min(Math.max(1, W._cliPage||1), totalPages); W._cliPage=page;
    var start=(page-1)*pageSize, end=start+pageSize;
    for(var i2=0;i2<m;i2++){ matching[i2].style.display=(i2>=start&&i2<end)?'':'none'; }
    var cnt=D.getElementById('_cli_count'); if(cnt) cnt.textContent=m;
    var pgi=D.getElementById('_cli_pginfo'); if(pgi) pgi.textContent=m?((start+1)+'–'+Math.min(end,m)+' de '+m):'0 de 0';
    var pgp=D.getElementById('_cli_pgpages'); if(pgp) pgp.textContent=page+' / '+totalPages;
    var pv=D.getElementById('_cli_prev'); if(pv) pv.disabled=(page<=1);
    var nx=D.getElementById('_cli_next'); if(nx) nx.disabled=(page>=totalPages);
    var pgn=D.getElementById('_cli_pgn'); if(pgn) pgn.style.display=rows.length?'flex':'none';
    var em=D.getElementById('_cli_noresult'); if(em) em.style.display=(m||!rows.length)?'none':'block';
    // Recuento FACETADO: cada grupo cuenta según los OTROS filtros activos, así se
    // ve que los 3 (ejecutivo/estado/potencial) intersectan entre sí. Fuente = los
    // ítems presentes (tarjetas del pipeline O filas del maestro; una vista a la vez).
    var its=[];
    D.querySelectorAll('.cli-card[data-asig],.cli-tbl-wrap tbody tr[data-asig]').forEach(function(el){
      its.push({a:el.getAttribute('data-asig')||'',s:el.getAttribute('data-stage')||'',
                t:el.getAttribute('data-tier')||'',f:el.getAttribute('data-fuente')||'',
                q:el.getAttribute('data-s')||''});
    });
    function setCnt(kind, match, useA, useS, useT, useF){
      D.querySelectorAll('.cli-fpill[data-fkind="'+kind+'"]').forEach(function(p){
        var val=p.getAttribute('data-fval')||'', n=0;
        for(var i=0;i<its.length;i++){ var it=its[i];
          if(useA&&!okA(it.a)) continue;
          if(useS&&!okS(it.s)) continue;
          if(useT&&!okT(it.t)) continue;
          if(useF&&!okF(it.f)) continue;
          if(!okQ(it.q)) continue;
          if(match(val,it)) n++;
        }
        var b=p.querySelector('.cli-fcount'); if(b) b.textContent=n;
      });
    }
    setCnt('ej',     function(v,it){ return v===''?true:(v==='__none__'?it.a==='':it.a===v); }, false, true, true, true);
    setCnt('st',     function(v,it){ return v===''||it.s===v; }, true, false, true, true);
    setCnt('tier',   function(v,it){ return v===''||it.t===v; }, true, true, false, true);
    setCnt('fuente', function(v,it){ return v===''||it.f===v; }, true, true, true, false);
  }
  W._cliApply=apply;
  // Sincroniza el 'on' de las pills con el filtro persistente.
  function syncPills(kind, val){
    D.querySelectorAll('.cli-fpill[data-fkind="'+kind+'"]').forEach(function(x){
      x.classList.toggle('on', (x.getAttribute('data-fval')||'')===(val||''));
    });
  }
  // Rótulo del trigger del dropdown = la selección actual (o "Todos") + estado activo.
  function fval(kind){ return kind==='ej'?(W._cliFEj||''):(kind==='st'?(W._cliFSt||'')
    :(kind==='tier'?(W._cliFTier||''):(W._cliFFu||''))); }
  function updateTrigger(kind){
    var val=fval(kind), dd=D.querySelector('.cli-fdd[data-fkind="'+kind+'"]'); if(!dd) return;
    var body=dd.querySelector('.cli-fdd-body'); if(!body) return;
    var ph=dd.getAttribute('data-ph')||'Todos';
    function setPh(){ body.textContent=''; var s=D.createElement('span');
      s.className='cli-fdd-ph'; s.textContent=ph; body.appendChild(s); dd.classList.remove('active'); }
    if(!val){ setPh(); return; }
    var pill=null;
    D.querySelectorAll('.cli-fpill[data-fkind="'+kind+'"]').forEach(function(p){
      if((p.getAttribute('data-fval')||'')===val) pill=p;
    });
    if(!pill){ setPh(); return; }
    // Clona el avatar/icono redondo y muestra el nombre (estilo COTIZACIONES).
    var ic=pill.querySelector('.cli-fpill-ic, .cli-fpill-av'), lb=pill.querySelector('.cli-fpill-lb');
    body.textContent='';
    if(ic) body.appendChild(ic.cloneNode(true));
    var cur=D.createElement('span'); cur.className='cli-fdd-cur';
    cur.textContent=lb?lb.textContent:''; body.appendChild(cur);
    dd.classList.add('active');
  }
  function closeAllDd(){ D.querySelectorAll('.cli-fdd.open').forEach(function(x){ x.classList.remove('open'); }); }
  if(W._cliPillH){ D.removeEventListener('click', W._cliPillH, true); }
  W._cliPillH=function(e){
    var t=e.target;
    if(t&&t.closest&&t.closest('.camp-fbar')) return;   // los de la campaña los maneja _campH
    // 1) Botón del dropdown → abre/cierra su menú (cierra los demás).
    var trg=t&&t.closest?t.closest('.cli-fdd-trg'):null;
    if(trg){
      var dd=trg.closest('.cli-fdd'), wasOpen=dd.classList.contains('open');
      closeAllDd(); if(!wasOpen) dd.classList.add('open');
      e.stopPropagation(); e.preventDefault(); return;
    }
    // 2) Pill dentro del menú → aplica el filtro y cierra el dropdown.
    var p=t&&t.closest?t.closest('.cli-fpill'):null;
    if(p){
      var kind=p.getAttribute('data-fkind'), val=p.getAttribute('data-fval')||'';
      if(kind==='ej') W._cliFEj=val; else if(kind==='st') W._cliFSt=val;
      else if(kind==='tier') W._cliFTier=val; else if(kind==='fuente') W._cliFFu=val;
      W._cliPage=1; syncPills(kind, val); updateTrigger(kind); apply();
      var pdd=p.closest('.cli-fdd'); if(pdd) pdd.classList.remove('open');
      e.stopPropagation(); return;
    }
    // 3) Clic fuera de cualquier dropdown → cierra todos.
    if(!t||!t.closest||!t.closest('.cli-fdd')){ closeAllDd(); }
  };
  D.addEventListener('click', W._cliPillH, true);
  // Buscador GLOBAL
  var q=D.getElementById('_cli_q');
  if(q){
    if(W._cliQH){ try{ q.removeEventListener('input', W._cliQH); }catch(e){} }
    W._cliQH=function(){ W._cliQ=(q.value||'').toLowerCase().trim(); W._cliPage=1; apply(); };
    q.addEventListener('input', W._cliQH);
    if(W._cliQ){ q.value=W._cliQ; }
  }
  // Paginación del Maestro (Anterior/Siguiente + tamaño de página)
  function bindClick(id, fn){
    var b=D.getElementById(id); if(!b) return;
    var k='_cliBH_'+id; if(W[k]){ try{ b.removeEventListener('click', W[k]); }catch(e){} }
    W[k]=fn; b.addEventListener('click', fn);
  }
  bindClick('_cli_prev', function(){ W._cliPage=Math.max(1,(W._cliPage||1)-1); apply(); });
  bindClick('_cli_next', function(){ W._cliPage=(W._cliPage||1)+1; apply(); });
  var pgs=D.getElementById('_cli_pgsize');
  if(pgs){
    if(W._cliPgsH){ try{ pgs.removeEventListener('change', W._cliPgsH); }catch(e){} }
    W._cliPgsH=function(){ W._cliPageSize=parseInt(pgs.value,10)||25; W._cliPage=1; apply(); };
    pgs.addEventListener('change', W._cliPgsH);
    pgs.value=String(W._cliPageSize||25);
  }
  syncPills('ej', W._cliFEj||''); syncPills('st', W._cliFSt||''); syncPills('tier', W._cliFTier||'');
  syncPills('fuente', W._cliFFu||'');
  updateTrigger('ej'); updateTrigger('st'); updateTrigger('tier'); updateTrigger('fuente');
  apply();
})();
</script>"""

# Dropdown "Ejecutivo asignado" con foto (chip + menú, estilo COTIZACIONES). Al
# elegir una opción escribe en el puente _cli_asigcmd → Python asigna + re-render.
_CLI_ASIG_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function fire(cid, em){
    var inp=D.querySelector('.st-key-_cli_asigcmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, cid+'|'+em+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  if(W._cliAsigH){ D.removeEventListener('click', W._cliAsigH, true); }
  W._cliAsigH=function(e){
    var t=e.target; if(!t||!t.closest) return;
    var chip=t.closest('.cli-asig-chip');
    if(chip){ var w=chip.closest('.cli-asig-wrap'); var m=w?w.querySelector('.cli-asig-menu'):null;
      if(m) m.classList.toggle('open'); e.preventDefault(); e.stopPropagation(); return; }
    var opt=t.closest('.cli-asig-opt');
    if(opt){ var w2=opt.closest('.cli-asig-wrap'); var cid=w2?w2.getAttribute('data-acid'):'';
      var mm=w2?w2.querySelector('.cli-asig-menu'):null; if(mm) mm.classList.remove('open');
      fire(cid, opt.getAttribute('data-em')||''); e.preventDefault(); e.stopPropagation(); return; }
    var op=D.querySelector('.cli-asig-menu.open');
    if(op && !(t.closest && t.closest('.cli-asig-wrap'))) op.classList.remove('open');
  };
  D.addEventListener('click', W._cliAsigH, true);
})();
</script>"""

# Click-para-copiar en los campos de la ficha (nombre/RUT/correo/teléfono/EP).
_CLI_COPY_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function cp(txt){
    try{ if(W.navigator && W.navigator.clipboard){ W.navigator.clipboard.writeText(txt); return true; } }catch(e){}
    try{ var ta=D.createElement('textarea'); ta.value=txt; ta.style.cssText='position:fixed;top:-9999px;left:-9999px;';
      D.body.appendChild(ta); ta.focus(); ta.select(); D.execCommand('copy'); ta.remove(); return true; }catch(e){ return false; }
  }
  function fb(x,y){
    var f=D.createElement('div'); f.textContent='✓ Copiado';
    f.style.cssText='position:fixed;z-index:2147483600;left:'+x+'px;top:'+(y-26)+'px;transform:translateX(-50%);'
      +'background:#0f172a;color:#fff;font-family:Montserrat,sans-serif;font-size:11px;font-weight:700;'
      +'padding:4px 9px;border-radius:7px;pointer-events:none;opacity:0;transition:opacity .12s,top .25s;';
    D.body.appendChild(f);
    W.requestAnimationFrame(function(){ f.style.opacity='1'; f.style.top=(y-34)+'px'; });
    W.setTimeout(function(){ f.style.opacity='0'; W.setTimeout(function(){ f.remove(); },200); },900);
  }
  if(W._cliCopyH){ D.removeEventListener('click', W._cliCopyH, true); }
  W._cliCopyH=function(e){
    var el=e.target&&e.target.closest?e.target.closest('.cli-copy'):null; if(!el) return;
    var txt=(el.getAttribute('data-copy')||el.textContent||'').trim(); if(!txt) return;
    e.preventDefault(); e.stopPropagation();
    if(cp(txt)) fb(e.clientX, e.clientY);
  };
  D.addEventListener('click', W._cliCopyH, true);

  // WhatsApp: abre wa.me en pestaña nueva (robusto, sin depender de <a target>).
  function openWa(el){
    var n=(el.getAttribute('data-wa')||'').trim(); if(!n) return;
    try{ W.open('https://wa.me/'+n, '_blank', 'noopener'); }catch(e){}
  }
  if(W._cliWaH){ D.removeEventListener('click', W._cliWaH, true); }
  W._cliWaH=function(e){
    var el=e.target&&e.target.closest?e.target.closest('.cli-wa'):null; if(!el) return;
    e.preventDefault(); e.stopPropagation(); openWa(el);
  };
  D.addEventListener('click', W._cliWaH, true);
  if(W._cliWaKeyH){ D.removeEventListener('keydown', W._cliWaKeyH, true); }
  W._cliWaKeyH=function(e){
    if(e.key!=='Enter'&&e.key!==' ') return;
    var el=e.target&&e.target.closest?e.target.closest('.cli-wa'):null; if(!el) return;
    e.preventDefault(); openWa(el);
  };
  D.addEventListener('keydown', W._cliWaKeyH, true);
})();
</script>"""


# ── Renders de cada vista ─────────────────────────────────────────────────────

def _render_maestro(data: list):
    _titulo(f'Maestro · <span id="_cli_count">{len(data)}</span> cliente(s)',
            _svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                 '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', 16))
    if not data:
        st.markdown('<div class="cli-empty-ph">Aún no hay clientes. Pulsa '
                    '<b>Sincronizar</b> para importar desde tus cotizaciones, o '
                    '<b>Agregar cliente</b>.</div>', unsafe_allow_html=True)
        return
    rows = ""
    for d in data:
        _asig = _resolver_asig(d.get("asignado_email"), d.get("asignado_nombre"))
        _stage = d.get("_stage") or STAGE_LEAD
        _slbl, _sdot, _sbg, _sfg = _STAGE_META.get(_stage, _STAGE_META[STAGE_LEAD])
        _s = _esc(f"{d.get('nombre','')} {d.get('rut','')} {d.get('email','')} "
                  f"{d.get('telefono','')} {_asig} {d.get('origen','')} {_slbl}".lower())
        _asig_cell = (_esc(_asig) if _asig
                      else '<span style="color:#ea580c;font-weight:700;font-size:0.72rem;">Sin asignar</span>')
        _asig_email = (d.get("asignado_email") or "").strip().lower()
        _sc = d.get("_score") or _lead_score(d, None)
        rows += (
            f'<tr data-s="{_s}" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}"'
            f' data-asig="{_esc(_asig_email)}" data-stage="{_esc(_stage)}" data-tier="{_sc["key"]}"'
            f' data-fuente="{_esc(_fuente_norm(d.get("origen")))}">'
            f'<td>{_score_badge(_sc, "sm")}</td>'
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
        '<th>Score</th><th>Cliente</th><th>Etapa</th><th>RUT</th><th>Correo</th><th>Tel&eacute;fono</th>'
        '<th>Origen</th><th>Ejecutivo</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>', unsafe_allow_html=True)
    st.markdown('<div id="_cli_noresult" class="cli-empty-ph" style="display:none;">'
                'Ningún cliente coincide con tu búsqueda.</div>', unsafe_allow_html=True)
    # Paginación client-side (la maneja _CLI_FILTER_JS: pagina las filas que pasan
    # los filtros + la búsqueda; sin reruns).
    st.markdown(
        '<div class="cli-pgn" id="_cli_pgn">'
        '<div class="cli-pgn-info" id="_cli_pginfo">—</div>'
        '<div class="cli-pgn-nav">'
        '<button id="_cli_prev" class="cli-pgn-btn" type="button">‹ Anterior</button>'
        '<span id="_cli_pgpages" class="cli-pgn-pages">1 / 1</span>'
        '<button id="_cli_next" class="cli-pgn-btn" type="button">Siguiente ›</button>'
        '</div>'
        '<label class="cli-pgn-size-l">Por página '
        '<select id="_cli_pgsize" class="cli-pgn-size">'
        '<option value="25">25</option><option value="50">50</option><option value="100">100</option>'
        '</select></label></div>', unsafe_allow_html=True)


def _render_pipeline(data: list):
    _titulo("Pipeline de oportunidades",
            _svg('<path d="M3 3v18h18"/><rect x="7" y="13" width="3" height="5"/>'
                 '<rect x="12" y="9" width="3" height="9"/><rect x="17" y="5" width="3" height="13"/>', 16))
    # Pipeline POR PROYECTO: cada cliente aporta 1-2 TRATOS (activo + historial) y
    # cada trato es su propia card en su etapa (ver enriquecer_con_pipeline._deals).
    por_etapa = {s: [] for s in _STAGE_ORDER}
    for d in data:
        _deals = d.get("_deals") or [{"stage": d.get("_stage") or STAGE_LEAD,
                                      "cotizaciones": d.get("_cotizaciones") or [],
                                      "monto": d.get("_monto") or 0.0, "tipo": "lead",
                                      "fecha": d.get("fecha_creacion") or "", "nota": ""}]
        for _dl in _deals:
            por_etapa.setdefault(_dl.get("stage") or STAGE_LEAD, por_etapa[STAGE_LEAD]).append((d, _dl))
    cols = ""
    for s in _STAGE_ORDER:
        _lbl, _dot, _bg, _fg = _STAGE_META[s]
        items = por_etapa[s]
        cards = ""
        for d, _dl in items:
            _asig = _resolver_asig(d.get("asignado_email"), d.get("asignado_nombre")) or "Sin asignar"
            _neps = len(_dl.get("cotizaciones") or [])
            _asig_email = (d.get("asignado_email") or "").strip().lower()
            _sc = d.get("_score") or _lead_score(d, None)
            # Presupuesto: label gris con la CANTIDAD de ESTE trato + su monto; o
            # "Sin presupuesto" (naranjo) si el lead no tiene ninguno.
            if _neps:
                _plbl = f"{_neps} presupuesto" + ("s" if _neps != 1 else "")
                _pre = (f'<div class="cli-card-lbl">{_plbl}</div>'
                        f'<div class="cli-card-mt">{_fmt_money(_dl.get("monto"))}</div>')
            else:
                _pre = '<div class="cli-card-none">Sin presupuesto</div>'
            # Pie: ejecutivo (o "Sin asignar" naranjo) + fecha del trato, misma fila.
            if _asig_email:
                _asig_inner = (f'<div class="cli-card-sub" style="min-width:0;overflow:hidden;">'
                               f'{_svg(_ICON_USER_PATH, 12, "#94a3b8")}{_esc(_asig)}</div>')
            else:
                _asig_inner = (f'<div class="cli-card-sub" style="color:#ea580c;">'
                               f'{_svg(_ICON_USER_PATH, 12, "#ea580c")}Sin asignar</div>')
            _fecha = _fmt_fecha_local(_dl.get("fecha") or d.get("fecha_creacion"))
            _fecha_inner = (f'<div class="cli-card-date" style="margin-top:0;flex-shrink:0;">'
                            f'{_svg(_ZIC_HIST, 10, "#b4bccd")}{_esc(_fecha)}</div>') if _fecha else ""
            _foot = ('<div style="display:flex;justify-content:space-between;align-items:center;'
                     f'gap:8px;margin-top:8px;">{_asig_inner}{_fecha_inner}</div>')
            # Etiqueta del trato SOLO si el cliente tiene activo + historial (así se
            # ve que son tratos distintos del mismo cliente, no un duplicado).
            _nota = _dl.get("nota") or ""
            _nota_html = (f'<span class="cli-card-nota cli-nota-{_dl.get("tipo","")}">{_esc(_nota)}</span>'
                          if _nota else "")
            # Reloj SLA (rojo, en vivo) del tiempo en la etapa; solo en tratos ACTIVOS.
            _sla = _sla_clock_html(d.get("stage_desde") or d.get("fecha_creacion"), _dl.get("stage"))
            _s_blob = _esc(f"{d.get('nombre','')} {d.get('rut','')} {d.get('email','')} "
                           f"{d.get('telefono','')} {_asig} {d.get('origen','')}".lower())
            cards += (
                f'<div class="cli-card" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}"'
                f' data-asig="{_esc(_asig_email)}" data-stage="{_esc(s)}" data-tier="{_sc["key"]}"'
                f' data-fuente="{_esc(_fuente_norm(d.get("origen")))}" data-s="{_s_blob}">'
                '<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
                '<div style="min-width:0;">'
                f'<div class="cli-card-nm">{_esc(d.get("nombre","") or "—")}</div>'
                '<div style="margin-top:5px;display:flex;flex-wrap:wrap;gap:5px;align-items:center;">'
                f'{_fuente_badge(d.get("origen"))}{_nota_html}{_sla}</div>'
                '</div>'
                f'{_score_badge(_sc, "sm")}</div>'
                f'{_pre}'
                f'{_foot}'
                '</div>')
        if not cards:
            cards = '<div class="cli-kb-empty">—</div>'
        _subcls, _subtxt, _subico = _STAGE_SUB.get(s, ("con", "", ""))
        _sub_html = (f'<div class="cli-kb-sub {_subcls}">{_svg(_subico, 11, "currentColor")}{_subtxt}</div>'
                     if _subtxt else "")
        cols += (
            '<div class="cli-kb-col">'
            f'<div class="cli-kb-hd"><span class="cli-kb-dot" style="background:{_dot};"></span>'
            f'<span class="cli-kb-nm">{_lbl}</span><span class="cli-kb-ct">{len(items)}</span></div>'
            f'{_sub_html}{cards}</div>')
    st.markdown(f'<div class="cli-kb-wrap"><div class="cli-kb">{cols}</div></div>',
                unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.76rem;color:#94a3b8;margin-top:8px;">'
                'Cada card es un <b>trato</b>. Un cliente que ya ganó y vuelve con un presupuesto '
                'nuevo aparece como dos tratos — <b>Venta anterior</b> (historial) y <b>Trato nuevo</b> '
                '(activo) — no es un duplicado. Click en una card para ver la ficha del cliente.</div>',
                unsafe_allow_html=True)


def _traer_de_shopify():
    """Trae los clientes de Shopify a la Bandeja como leads (origen 'Shopify'),
    deduplicados. Deja el resultado en el toast."""
    if not _shopify_configurado():
        st.session_state["_cli_toast"] = ("Falta configurar Shopify: agrega SHOPIFY_STORE y "
                                          "SHOPIFY_TOKEN (o SHOPIFY_ACCESS_TOKEN) en los secrets.")
        return
    with st.spinner("Trayendo clientes de Shopify…"):
        _cust, _err = _shopify_listar()
    if _err:
        st.session_state["_cli_toast"] = f"Shopify: {_err}"
        return
    _rows = [_shopify_a_lead(c) for c in _cust]
    _res = importar_leads(_rows, origen="Shopify")
    _cli_data.clear()
    st.session_state["_cli_toast"] = (
        f"Shopify: {_res['creados']} nuevo(s), {_res['duplicados']} ya estaban, "
        f"{_res['omitidos']} sin nombre.")


def _render_bandeja(data: list):
    leads = [d for d in data if (d.get("_stage") in (STAGE_LEAD, STAGE_CONTACTADO))]
    _titulo(f"Bandeja de leads · {len(leads)}",
            _svg('<path d="M22 12h-6l-2 3h-4l-2-3H2"/>'
                 '<path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>', 16))
    # Traer leads de Shopify (root/admin). Se muestra aunque la bandeja esté vacía.
    if st.session_state.get("rol_usuario") in ("root", "admin"):
        _sc1, _sc2 = st.columns([1, 3], vertical_alignment="center")
        with _sc1:
            if st.button("Traer de Shopify", icon=":material/storefront:",
                         use_container_width=True, key="_cli_shopify"):
                _traer_de_shopify()
                st.rerun()
        with _sc2:
            if not _shopify_configurado():
                st.markdown('<div class="cli-actf-hint" style="margin:0;">Configura '
                            '<code>SHOPIFY_STORE</code> y <code>SHOPIFY_TOKEN</code> '
                            '(o <code>SHOPIFY_ACCESS_TOKEN</code>) en los secrets '
                            'para activar la ingesta.</div>', unsafe_allow_html=True)
    if not leads:
        st.markdown(
            '<div class="cli-empty-ph">Sin leads pendientes por asignar.<br>'
            '<span style="font-weight:500;color:#cbd5e1;">Acá caerán los clientes nuevos '
            '(Shopify / web) para triar y asignar a un ejecutivo.</span></div>',
            unsafe_allow_html=True)
        return
    cards = ""
    for d in leads:
        _asig_b = _resolver_asig(d.get("asignado_email"), d.get("asignado_nombre"))
        _sb = _esc(f"{d.get('nombre','')} {d.get('rut','')} {d.get('email','')} "
                   f"{d.get('telefono','')} {_asig_b} {d.get('origen','')}".lower())
        cards += (
            f'<div class="cli-card" data-cid="{_esc(d.get("id"))}" data-cname="{_esc(d.get("nombre",""))}"'
            f' data-s="{_sb}" style="margin-bottom:10px;">'
            f'<div class="cli-card-nm">{_esc(d.get("nombre","") or "—")}</div>'
            f'<div class="cli-card-sub" style="margin-top:4px;">{_origen_pill(d.get("origen","Manual"))}</div>'
            f'<div class="cli-card-sub" style="margin-top:4px;">{_esc(d.get("email","") or d.get("telefono","") or "—")}</div>'
            '</div>')
    st.markdown(f'<div style="margin-top:12px;">{cards}</div>', unsafe_allow_html=True)


# ── Ficha 360 ─────────────────────────────────────────────────────────────────

def _render_asignar(cid, cli):
    """Dropdown 'Ejecutivo asignado' CON FOTO (chip + menú, estilo COTIZACIONES).
    Solo root/admin. La selección va por el puente _cli_asigcmd → _do_asignar."""
    _ejs = _ejecutivos()
    _cur_em = (cli.get("asignado_email") or "").strip().lower()
    _cur_nm = _resolver_asig(cli.get("asignado_email"), cli.get("asignado_nombre"))
    _cur_foto = ""
    for e in _ejs:
        if e["email"].lower() == _cur_em:
            _cur_foto = e.get("foto_url", "")
            _cur_nm = e.get("nombre") or _cur_nm
            break
    if _cur_em:
        _chip_body = (_avatar_html(_cur_foto, _cur_nm, size=30, ring="#e2e8f0", font_scale=0.4)
                      + f'<span class="cli-asig-nm">{_esc(_cur_nm)}</span>')
    else:
        _chip_body = '<span class="cli-asig-ph">— Sin asignar —</span>'
    _none_ico = ('<span class="cli-asig-none">'
                 + _svg('<path d="M19 21v-2a4 4 0 0 0-4-4H8"/><circle cx="10" cy="7" r="4"/>'
                        '<line x1="17" x2="22" y1="8" y2="13"/><line x1="22" x2="17" y1="8" y2="13"/>',
                        14, "currentColor") + '</span>')
    _opts = (f'<button type="button" class="cli-asig-opt" data-em="__none__">'
             f'{_none_ico}<span>— Sin asignar —</span></button>')
    for e in sorted(_ejs, key=lambda x: (x.get("nombre") or "").lower()):
        _av = _avatar_html(e.get("foto_url", ""), e.get("nombre") or e["email"],
                           size=26, ring="#e2e8f0", font_scale=0.42)
        _opts += (f'<button type="button" class="cli-asig-opt" data-em="{_esc(e["email"])}">'
                  f'{_av}<span>{_esc(e.get("nombre") or e["email"])}</span></button>')
    _cv = _svg('<polyline points="6 9 12 15 18 9"/>', 12, "currentColor")
    st.markdown(
        '<div class="cli-asig"><div class="cli-asig-lbl">Ejecutivo asignado</div>'
        f'<div class="cli-asig-wrap" data-acid="{_esc(cid)}">'
        f'<button type="button" class="cli-asig-chip">{_chip_body}'
        f'<span class="cli-asig-cv">{_cv}</span></button>'
        f'<div class="cli-asig-menu">{_opts}</div></div></div>',
        unsafe_allow_html=True)


def _do_asignar(cli, new_email):
    """Aplica la asignación (usado por el puente _cli_asigcmd). Muta `cli` en sitio
    + notifica (campana + Telegram). NO hace rerun: el caller re-renderiza la ficha."""
    new_email = (new_email or "").strip()
    if new_email == "__none__":
        new_email = ""
    _cur = (cli.get("asignado_email") or "").strip().lower()
    if new_email.lower() == _cur:
        return
    _nm = ""
    if new_email:
        for e in _ejecutivos():
            if e["email"].lower() == new_email.lower():
                _nm = e.get("nombre") or e["email"]
                break
    _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
    _ok, _err = actualizar_cliente(cli["id"], {"asignado_email": new_email, "asignado_nombre": _nm})
    if not _ok:
        st.toast(f"No se pudo asignar: {_err}")
        return
    cli["asignado_email"] = new_email
    cli["asignado_nombre"] = _nm
    if new_email:
        registrar_actividad(cli["id"], "nota", f"Asignado a {_nm}", actor=_actor)
        _crear_notif(new_email, f"Nuevo lead asignado · {cli.get('nombre','Cliente')}",
                     tipo="lead", detalle=f"Asignado por {_actor}", cliente_id=cli["id"])
        _tg = notificar_lead_asignado(cli.get("nombre", "Cliente"), new_email, _actor)
        st.toast(f"Lead asignado a {_nm}" + (" · avisado por Telegram" if _tg else ""))
    else:
        registrar_actividad(cli["id"], "nota", "Cliente desasignado", actor=_actor)
        st.toast("Cliente desasignado")


def _crear_reintento(cid, cli, titulo, actor, cuando) -> str:
    """Crea una llamada de reintento (`cuando` = '1h' | '2h' | 'manana'), registra
    la reagenda en la línea de tiempo y avisa (campana + Telegram). Devuelve el ISO
    del nuevo vencimiento. Compartido por el panel de Resultado y el form de alta."""
    if cuando == "manana":
        _nx = (_ahora_scl() + _td(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        _h = 1 if cuando == "1h" else 2
        _nx = (_ahora_scl() + _td(hours=_h)).replace(second=0, microsecond=0)
    _iso = _nx.isoformat()
    _t = (titulo or "").strip()
    _tt = f"Volver a llamar — {_t}" if _t else "Volver a llamar"
    crear_tarea(cid, _tt, _iso, cli.get("asignado_email", ""), tipo="llamada")
    registrar_actividad(cid, "llamada", "Llamada — reagendada",
                        detalle=_fmt_fecha_local(_iso), actor=actor)
    notificar_recordatorio(cli.get("nombre", "Cliente"),
                           f"Volver a llamar: {_t}" if _t else "Volver a llamar",
                           _fmt_fecha_local(_iso), cli.get("asignado_email", ""))
    _crear_notif(_notif_dest(cli),
                 f"Volver a llamar · {cli.get('nombre','Cliente')}" + (f": {_t}" if _t else ""),
                 tipo="llamada", detalle=_fmt_fecha_local(_iso), cliente_id=cid)
    return _iso


def _guardar_contesto(cid, cli, tid, valores, preguntas, actor) -> None:
    """Marca la llamada como 'contestó', guarda la calificación EN el cliente (si
    hay respuestas) y registra el evento con un resumen. Compartido por el panel de
    Resultado y el form de alta."""
    completar_tarea(tid, True, "contesto")
    _resumen = ""
    if valores:
        _ok, _merged = guardar_calificacion(cid, valores)
        if _ok:
            cli["calificacion"] = _merged   # refleja al toque en la ficha abierta
            _cli_data.clear()
        else:
            st.toast("La llamada se marcó, pero no se pudo guardar la calificación "
                     "(falta la columna 'calificacion').", icon="⚠️")
        _resumen = _resumen_calificacion(valores, preguntas)
    registrar_actividad(cid, "llamada",
                        "Llamada — contestó (calificado)" if _resumen else "Llamada — contestó",
                        detalle=_resumen, actor=actor)


def _wa_num(telefono) -> str:
    """Normaliza un teléfono a formato internacional para wa.me (Chile). Devuelve
    solo dígitos con prefijo país, o '' si no hay teléfono usable.
    Ej: '+56 9 1234 5678' / '912345678' → '56912345678'."""
    d = "".join(ch for ch in str(telefono or "") if ch.isdigit())
    if not d:
        return ""
    if d.startswith("56"):
        return d
    if len(d) == 9 and d.startswith("9"):   # móvil chileno sin país
        return "56" + d
    if len(d) == 8:                          # faltaba el 9 inicial
        return "569" + d
    return d                                  # mejor esfuerzo (deja lo que haya)


# Logo de WhatsApp (marca) para el enlace de la ficha.
_WA_SVG = ('<svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" '
           'style="flex:0 0 auto;"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.372-.025-.521-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51l-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.263.489 1.694.626.712.226 1.36.194 1.872.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.885-9.885 9.885M20.52 3.449C18.24 1.245 15.24 0 12.045 0 5.463 0 .104 5.359.101 11.892c0 2.096.549 4.142 1.595 5.945L0 24l6.335-1.652a11.882 11.882 0 005.71 1.454h.006c6.585 0 11.946-5.359 11.949-11.893a11.821 11.821 0 00-3.481-8.454"/></svg>')


def _wa_cell(telefono) -> str:
    """Celda 'WhatsApp' de la ficha: si hay número, un elemento clickeable (verde
    WhatsApp) que abre wa.me en pestaña nueva vía _CLI_WA_JS; si no, '—'. Se usa un
    span con data-wa (no un <a>) para no depender de que Streamlit conserve
    target=_blank y para abrir en pestaña nueva de forma robusta."""
    _n = _wa_num(telefono)
    if not _n:
        return '<div><div class="k">WhatsApp</div>—</div>'
    return (f'<div><div class="k">WhatsApp</div>'
            f'<span class="cli-wa" data-wa="{_n}" role="link" tabindex="0" '
            f'title="Abrir WhatsApp">{_WA_SVG}<span>{_esc(str(telefono).strip())}</span></span></div>')


_SHOPIFY_META_LABELS = [
    ("presupuesto", "Presupuesto"), ("modelo", "Modelo"), ("precio", "Precio"),
    ("descripcion", "Qué busca / describe"), ("tipo_persona", "Tipo de persona"),
]


def _norm_presupuesto(s) -> str:
    """Repara el monto que llega MAL AGRUPADO desde la máscara del form de Shopify:
    agrupa los miles desde la IZQUIERDA (ej. '$5.000.0000') en vez de desde la
    derecha ('$50.000.000'). Los dígitos SÍ se conservan → se extraen y se reagrupan
    de a 3 desde la derecha. Si no parece un monto (tiene letras o largo raro), se
    deja igual. Idempotente (un monto correcto queda igual)."""
    raw = str(s or "").strip()
    if not raw or any(c.isalpha() for c in raw):   # texto libre / con "CLP" → no tocar
        return raw
    digits = "".join(c for c in raw if c.isdigit())
    if not (4 <= len(digits) <= 12):               # no parece un monto → no tocar
        return raw
    return "$" + f"{int(digits):,}".replace(",", ".")


def _render_shopify_datos(cli):
    """Muestra los datos que vinieron del FORMULARIO de Shopify (metacampos) si el
    lead los trae en `shopify_meta`. Incluye el plano si viene."""
    _m = cli.get("shopify_meta") or {}
    if isinstance(_m, str):
        try:
            _m = _json.loads(_m)
        except Exception:
            _m = {}
    if not isinstance(_m, dict) or not any(str(v or "").strip() for v in _m.values()):
        return
    st.markdown(_zsec("Datos del formulario (Shopify)", _ZIC_SHOPIFY), unsafe_allow_html=True)

    def _val(_k):
        # Presupuesto/precio: reparar el mal-agrupado que llega de Shopify.
        _v = str(_m.get(_k) or "")
        return _norm_presupuesto(_v) if _k in ("presupuesto", "precio") else _v
    _items = "".join(
        f'<div><div class="k">{_esc(_lbl)}</div>{_cp(_val(_k), _esc(_val(_k)), "Copiar")}</div>'
        for _k, _lbl in _SHOPIFY_META_LABELS if str(_m.get(_k) or "").strip())
    # Plano: como un ítem MÁS de la grilla (queda EN ORDEN, no flotando abajo). Link
    # propio (.cli-plano, NO .cli-wa) → abre el plano en una pestaña nueva.
    _plano = str(_m.get("plano_url") or "").strip()
    if _plano and _plano.lower().startswith("http"):
        _ico = _svg('<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
                    '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M9 13h6"/><path d="M9 17h4"/>',
                    13, "currentColor")
        _items += (f'<div><div class="k">Plano</div>'
                   f'<a class="cli-plano" href="{_esc(_plano)}" target="_blank" rel="noopener">'
                   f'{_ico}Ver plano cliente</a></div>')
    if _items:
        st.markdown(f'<div class="cli-data">{_items}</div>', unsafe_allow_html=True)


def _render_calificacion(cid, cli):
    """Sección 'Calificación' (respuestas del guión). Ver + Editar. Se muestra solo
    si el admin configuró preguntas. Va en la zona de actividades de la ficha."""
    _pregs_f = _preguntas_data()
    if not _pregs_f:
        return
    _cal_edit = st.session_state.get("_cli_cal_edit") == cid
    # Encabezado de zona: línea + (título | botón Editar) en la MISMA fila.
    st.markdown(_zline(), unsafe_allow_html=True)
    _hc1, _hc2 = st.columns([3, 1], vertical_alignment="center")
    with _hc1:
        st.markdown(_zsec_hd("Calificación", _ZIC_CALIF), unsafe_allow_html=True)
    with _hc2:
        if not _cal_edit and st.button("Editar", key=f"_cli_calfedit_{cid}",
                                       use_container_width=True, icon=":material/edit:"):
            st.session_state["_cli_cal_edit"] = cid
            st.rerun(scope="fragment")
    if _cal_edit:
        _fvals, _fpregs = _guion_inputs(cli, f"_ficcal_{cid}")
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            if st.button("Guardar", key=f"_cli_calfsave_{cid}", type="primary",
                         use_container_width=True, icon=":material/save:"):
                _ok, _mg = guardar_calificacion(cid, _fvals or {})
                if _ok:
                    cli["calificacion"] = _mg
                    _cli_data.clear()
                    st.toast("Calificación guardada")
                else:
                    st.error("No se pudo guardar (¿falta la columna calificacion?).")
                st.session_state.pop("_cli_cal_edit", None)
                st.rerun(scope="fragment")
        with _cc2:
            if st.button("Cancelar", key=f"_cli_calfcancel_{cid}", use_container_width=True):
                st.session_state.pop("_cli_cal_edit", None)
                st.rerun(scope="fragment")
    else:
        _cur = _cli_calif(cli)
        _items = "".join(
            f'<div><div class="k">{_esc(p.get("texto",""))}</div>'
            f'{_esc(str(_cur.get(str(p.get("id")), "") or "") or "—")}</div>'
            for p in _pregs_f)
        st.markdown(f'<div class="cli-data">{_items}</div>', unsafe_allow_html=True)


def _render_datos(cid, cli):
    """Datos de contacto del cliente: vista de solo lectura (copiables + WhatsApp)
    o formulario de EDICIÓN. Guardar → actualiza la tabla `clientes` del CRM (y el
    Lead Score y el WhatsApp se recalculan solos). No toca cotizaciones."""
    _editing = st.session_state.get("_cli_edit") == cid
    # Encabezado de zona: línea separadora + (título | botón Editar) en la MISMA fila.
    st.markdown(_zline(), unsafe_allow_html=True)
    _hc1, _hc2 = st.columns([3, 1], vertical_alignment="center")
    with _hc1:
        st.markdown(_zsec_hd("Datos del cliente", _ZIC_DATOS), unsafe_allow_html=True)
    with _hc2:
        if not _editing and st.button("Editar", use_container_width=True,
                                      icon=":material/edit:", key="_cli_ed_open"):
            st.session_state["_cli_edit"] = cid
            st.rerun(scope="fragment")
    if _editing:
        with st.container(border=True, key="_cli_edit_form"):
            _e1, _e2 = st.columns(2)
            with _e1:
                _n = st.text_input("Nombre", value=cli.get("nombre", "") or "", key="_cli_ed_nombre")
                _r = st.text_input("RUT", value=cli.get("rut", "") or "", key="_cli_ed_rut")
                _co = st.text_input("Correo", value=cli.get("email", "") or "", key="_cli_ed_email")
                _te = st.text_input("Teléfono", value=cli.get("telefono", "") or "", key="_cli_ed_tel")
            with _e2:
                _di = st.text_input("Dirección", value=cli.get("direccion", "") or "", key="_cli_ed_dir")
                _cm = st.text_input("Comuna", value=cli.get("comuna", "") or "", key="_cli_ed_com")
                _rg = st.text_input("Región", value=cli.get("region", "") or "", key="_cli_ed_reg")
                _tp = st.selectbox("Tipo", ["natural", "empresa"],
                                   index=0 if (cli.get("tipo") or "natural") != "empresa" else 1,
                                   key="_cli_ed_tipo",
                                   format_func=lambda x: "Persona natural" if x == "natural" else "Empresa")
            _emp = _rutemp = ""
            if _tp == "empresa":
                _emp = st.text_input("Empresa / razón social", value=cli.get("empresa", "") or "",
                                     key="_cli_ed_emp")
                _rutemp = st.text_input("RUT empresa", value=cli.get("rut_empresa", "") or "",
                                        key="_cli_ed_rutemp")
            st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
            _b1, _b2 = st.columns(2)
            with _b1:
                if st.button("Guardar cambios", type="primary", use_container_width=True,
                             icon=":material/save:", key="_cli_ed_save"):
                    if not (_n or "").strip():
                        st.warning("El nombre no puede quedar vacío.")
                    else:
                        _campos = {
                            "nombre": _n.strip(), "rut": _r.strip(), "email": _co.strip(),
                            "telefono": _te.strip(), "direccion": _di.strip(), "comuna": _cm.strip(),
                            "region": _rg.strip(), "tipo": _tp,
                            "empresa": _emp.strip() if _tp == "empresa" else "",
                            "rut_empresa": _rutemp.strip() if _tp == "empresa" else "",
                        }
                        # Identidad ANTERIOR (para ubicar sus cotizaciones aunque se
                        # corrija RUT/correo) antes de tocar el registro del CRM.
                        _old = (cli.get("rut"), cli.get("email"),
                                cli.get("telefono"), cli.get("nombre"))
                        _ok, _err = actualizar_cliente(cid, _campos)
                        if _ok:
                            _np = propagar_a_cotizaciones(cid, _old[0], _old[1], _old[2], _old[3], _campos)
                            cli.update(_campos)
                            cli["_score"] = _lead_score(cli, _preguntas_data())  # score al día
                            _cli_data.clear()
                            _actor = (st.session_state.get("auth_nombre")
                                      or st.session_state.get("auth_email", ""))
                            registrar_actividad(cid, "nota", "Datos del cliente editados", actor=_actor)
                            st.session_state.pop("_cli_edit", None)
                            st.toast("Datos actualizados"
                                     + (f" · {_np} presupuesto(s) sincronizado(s)" if _np else ""))
                            st.rerun(scope="fragment")
                        else:
                            st.error(f"No se pudo guardar: {_err}")
            with _b2:
                if st.button("Cancelar", use_container_width=True, key="_cli_ed_cancel"):
                    st.session_state.pop("_cli_edit", None)
                    st.rerun(scope="fragment")
        return

    _tipo = cli.get("tipo") or "natural"
    _empresa = (f'<div><div class="k">Empresa</div>{_esc(cli.get("empresa"))} '
                f'({_esc(cli.get("rut_empresa"))})</div>') if _tipo == "empresa" and cli.get("empresa") else ""
    _correo = cli.get("email", "") or ""
    _tel = cli.get("telefono", "") or ""
    _dir = cli.get("direccion", "") or ""
    _com = cli.get("comuna", "") or ""
    st.markdown(
        '<div class="cli-data">'
        f'<div><div class="k">Correo</div>{_cp(_correo, _esc(_correo or "—"), "Copiar correo")}</div>'
        f'<div><div class="k">Teléfono</div>{_cp(_tel, _esc(_tel or "—"), "Copiar teléfono")}</div>'
        f'{_wa_cell(_tel)}'
        f'<div><div class="k">Dirección</div>{_cp(_dir, _esc(_dir or "—"), "Copiar dirección")}</div>'
        f'<div><div class="k">Comuna</div>{_cp(_com, _esc(_com or "—"), "Copiar comuna")}</div>'
        f'{_empresa}'
        '</div>', unsafe_allow_html=True)


_CORREO_META = {   # last_event de Resend -> (label, bg, fg)
    "sent": ("Enviado", "#f1f5f9", "#475569"),
    "delivered": ("Entregado", "#dcfce7", "#15803d"),
    "delivery_delayed": ("Demorado", "#fef3c7", "#b45309"),
    "opened": ("Abrió", "#e0f2fe", "#0369a1"),
    "clicked": ("Clickeado", "#ede9fe", "#6d28d9"),
    "bounced": ("Rebotado", "#fee2e2", "#b91c1c"),
    "complained": ("Spam", "#fee2e2", "#b91c1c"),
}


@st.cache_data(ttl=300, show_spinner=False)
def _correo_estado(resend_id: str) -> str:
    """last_event de un correo por POLLING (fallback si hay key de lectura). '' si
    no se pudo consultar. El camino principal es el webhook (columnas guardadas)."""
    if not resend_id:
        return ""
    r = _resend_estado(resend_id)
    return r.get("last_event", "") if r.get("ok") else ""


def _correo_estado_meta(c: dict):
    """(label,bg,fg) del correo. Se decide por los FLAGS guardados por el webhook de
    Resend (opened/clicked/bounced/complained) — son 'sticky', así que son robustos
    aunque los eventos lleguen fuera de orden. Si no hay nada guardado, cae al
    polling (solo funciona con una key de lectura)."""
    if c.get("complained"):
        return _CORREO_META["complained"]
    if c.get("bounced"):
        return _CORREO_META["bounced"]
    if c.get("clicked"):
        return _CORREO_META["clicked"]
    if c.get("opened"):
        return _CORREO_META["opened"]
    _ev = str(c.get("last_event") or "").strip() or _correo_estado(c.get("resend_id") or "")
    return _CORREO_META.get(_ev, _CORREO_META["sent"])


def _render_correos_enviados(cid, cli=None):
    """Sección 'Correos enviados': contador + estado por correo (entregado/abierto/
    click/rebote/spam) que llega EN VIVO por el webhook de Resend, + aviso de baja."""
    _cors = _listar_correos_cliente(cid)
    if not _cors:
        return
    st.markdown(f'<div class="cli-sec-t">Correos enviados · {len(_cors)}</div>',
                unsafe_allow_html=True)
    _rows = ""
    for c in _cors:
        _lbl, _bg, _fg = _correo_estado_meta(c)
        _adj = (f' · {c.get("adjuntos")} adjunto(s)' if c.get("adjuntos") else "")
        # Chips de engagement (además del badge): se ven aunque el "último evento"
        # haya avanzado (ej. abrió Y luego hizo click).
        _chips = ""
        for _fl, _tx, _cbg, _cfg in (("opened", "Abrió", "#e0f2fe", "#0369a1"),
                                     ("clicked", "Clickeado", "#ede9fe", "#6d28d9"),
                                     ("bounced", "Rebotado", "#fee2e2", "#b91c1c"),
                                     ("complained", "Spam", "#fee2e2", "#b91c1c")):
            if c.get(_fl):
                _chips += f'<span class="cli-mchip" style="background:{_cbg};color:{_cfg};">{_tx}</span>'
        _chips_html = (f'<div style="display:flex;gap:4px;flex-wrap:wrap;margin-top:4px;">{_chips}</div>'
                       if _chips else "")
        _rows += (
            '<div class="cli-ep-row">'
            f'<div style="min-width:0;"><div style="font-size:0.84rem;color:#0f172a;font-weight:600;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_esc(c.get("asunto") or "(sin asunto)")}</div>'
            f'<div style="font-size:0.72rem;color:#94a3b8;">{_esc(_fmt_fecha_local(c.get("fecha")))}{_esc(_adj)}</div>'
            f'{_chips_html}</div>'
            f'<span class="cli-pill" style="background:{_bg};color:{_fg};">{_lbl}</span>'
            '</div>')
    _baja_html = ('<div style="font-size:0.72rem;color:#b91c1c;font-weight:700;margin-top:4px;">'
                  '⛔ Este cliente se dio de baja — no recibirá correos masivos.</div>'
                  if (cli and cli.get("no_email")) else "")
    st.markdown('<div style="border:1px solid #e6e9f4;border-radius:12px;overflow:hidden;">'
                + _rows + '</div>' + _baja_html
                + '<div style="font-size:0.72rem;color:#94a3b8;margin-top:4px;">'
                'El estado (entregado/abierto/click/rebote/spam) se actualiza en vivo por el webhook '
                'de Resend. Las respuestas llegan a tu buzón, no aparecen acá.</div>',
                unsafe_allow_html=True)


def _mail_insert(txt):
    """Callback para insertar (append) texto/emoji/variable en el cuerpo del correo.
    Va en on_click → corre ANTES de re-instanciar el text_area, así se puede tocar
    su session_state sin error."""
    st.session_state["_cli_mail_body"] = (st.session_state.get("_cli_mail_body") or "") + txt


_MAIL_VARS = [("Nombre", "{{nombre}}"), ("Comuna", "{{comuna}}"),
              ("Teléfono", "{{telefono}}"), ("Correo", "{{correo}}")]
_MAIL_EMOJIS = ["😀", "😊", "👍", "🙌", "🎉", "🔥", "🏠", "✅", "✨", "📞", "🙏", "💬"]


def _render_correo(cid, cli):
    """Compositor de correo (Resend) inline en la ficha. Emojis + variables
    clickeables + adjuntos. Reply-to al buzón real (Zoho). Todo defensivo: sin API
    key, el botón queda deshabilitado."""
    _to = (cli.get("email") or "").strip()
    # Reply-to = buzón del EJECUTIVO que atiende al cliente (asignado). Así la
    # respuesta del cliente le llega a ESE ejecutivo, no a la casilla general.
    # Cae al correo del usuario que envía, y por último al reply-to por defecto.
    _reply_to = ((cli.get("asignado_email") or "").strip().lower()
                 or (st.session_state.get("auth_email") or "").strip().lower()
                 or _resend_reply())
    _asig_nm = cli.get("asignado_nombre") or ""
    with st.container(border=True, key="_cli_mail_form"):
        st.markdown('<div class="cli-actf-h">Enviar correo</div>', unsafe_allow_html=True)
        if not _resend_configurado():
            st.warning("Aún no está cargada la RESEND_API_KEY en los secrets. "
                       "Cuando la agregues, el envío se activa solo.")
        st.markdown(
            f'<div class="cli-actf-hint">Para: <b>{_esc(_to or "—")}</b><br>'
            f'Desde <b>{_esc(_resend_remitente() or "—")}</b>'
            + (f'<br>Si responde, le llega a <b>{_esc(_reply_to)}</b>'
               + (f' ({_esc(_asig_nm)})' if _asig_nm else '') if _reply_to else "")
            + '</div>', unsafe_allow_html=True)
        if not _to:
            st.warning("Este cliente no tiene correo; agrégalo para poder enviarle.")
        st.text_input("Asunto", key="_cli_mail_subj",
                      placeholder="Tu casa container a medida")
        st.text_area("Mensaje", key="_cli_mail_body", height=180,
                     placeholder="Hola {{nombre}}, gracias por tu interés en Espacio Container House…")
        # Toolbar: variables + colección completa de emojis; inserta en el campo
        # enfocado (asunto o mensaje) en la posición del cursor.
        st.markdown(_mail_toolbar_html(), unsafe_allow_html=True)
        components.html(_mail_tools_js("_cli_mail_subj", "_cli_mail_body"), height=0)

        # Adjuntos (Resend soporta PDF/imágenes/etc.).
        _files = st.file_uploader("Adjuntar archivos (opcional)", accept_multiple_files=True,
                                  key="_cli_mail_files")
        st.markdown('<div class="cli-actf-hint">Las variables se reemplazan por los datos de '
                    'cada cliente al enviar.</div>', unsafe_allow_html=True)

        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
        _mc1, _mc2 = st.columns(2)
        with _mc1:
            if st.button("Enviar", type="primary", use_container_width=True,
                         key="_cli_mail_send", icon=":material/send:",
                         disabled=(not _to or not _resend_configurado())):
                _subj = st.session_state.get("_cli_mail_subj", "")
                _body = st.session_state.get("_cli_mail_body", "")
                if not (_subj or "").strip() or not (_body or "").strip():
                    st.warning("Escribe el asunto y el mensaje.")
                else:
                    _subject = _resend_render(_subj, cli)
                    _texto = _resend_render(_body, cli)
                    # Adjuntos → base64
                    _att = []
                    for _f in (_files or []):
                        try:
                            import base64
                            _att.append({"filename": _f.name,
                                         "content": base64.b64encode(_f.getvalue()).decode()})
                        except Exception:
                            pass
                    _ok, _res = _resend_enviar(_to, _subject,
                                               _resend_texto_html(_texto) + _firma_html(_reply_to),
                                               reply_to=_reply_to or None,
                                               attachments=_att or None)
                    if _ok:
                        _actor = (st.session_state.get("auth_nombre")
                                  or st.session_state.get("auth_email", ""))
                        _adj = f" · {len(_att)} adjunto(s)" if _att else ""
                        registrar_actividad(cid, "correo", f"Correo enviado: {_subject}",
                                            detalle=(_texto[:200] + _adj), actor=_actor)
                        # Guardar para el seguimiento (estado/entregado/click/rebote).
                        _registrar_correo(cid, _res, _to, _subject, _actor, len(_att))
                        st.session_state.pop("_cli_mail_open", None)
                        for _k in ("_cli_mail_subj", "_cli_mail_body", "_cli_mail_files"):
                            st.session_state.pop(_k, None)
                        st.toast("Correo enviado ✅")
                        st.rerun(scope="fragment")
                    else:
                        st.error(f"No se pudo enviar: {_res}")
        with _mc2:
            if st.button("Cancelar", use_container_width=True, key="_cli_mail_cancel"):
                st.session_state.pop("_cli_mail_open", None)
                st.rerun(scope="fragment")


def _render_actividad(cid, cli, t):
    """Una fila de la lista de actividades. Para llamadas pendientes muestra el
    botón "Resultado" que despliega Contestó→guión / No interesado / No pude
    hablar→reagendar. El resto de tipos solo tiene "Hecho"."""
    tid = t.get("id")
    tipo = t.get("tipo") or "tarea"
    _lbl, _path = _ACT_META.get(tipo, _ACT_META["tarea"])
    hecho = bool(t.get("hecho"))
    resultado = t.get("resultado") or ""
    vence = t.get("vence")
    vencida = (not hecho) and _act_vencida(vence)
    _col = "#94a3b8" if hecho else ("#dc2626" if vencida else "#0f172a")
    _icol = "#16a34a" if hecho else ("#dc2626" if vencida else "#5b7cfa")
    _dec = "text-decoration:line-through;" if hecho else ""
    _resb = ""
    if resultado:
        _rl, _rb, _rf = _RESULT_META.get(resultado, (resultado, "#f1f5f9", "#475569"))
        _resb = f'<span class="cli-pill" style="background:{_rb};color:{_rf};margin-left:6px;">{_rl}</span>'
    _cuando = "venció" if vencida else ("hecho" if hecho else "vence")
    rc1, rc2 = st.columns([5, 2], vertical_alignment="center")
    with rc1:
        st.markdown(
            '<div style="padding:4px 0;display:flex;align-items:center;gap:7px;flex-wrap:wrap;">'
            + _svg(_path, 15, _icol) +
            f'<span style="font-size:0.86rem;color:{_col};{_dec}">{_esc(t.get("titulo",""))}</span>'
            f'{_resb}'
            f'<span style="font-size:0.72rem;color:#94a3b8;">{_cuando} {_esc(_fmt_fecha_local(vence))}</span>'
            '</div>', unsafe_allow_html=True)
    with rc2:
        if not hecho and tipo == "llamada":
            if st.button("Resultado", key=f"_cli_res_{tid}", use_container_width=True):
                _cur = st.session_state.get("_cli_act_res")
                st.session_state["_cli_act_res"] = None if _cur == tid else tid
                st.rerun(scope="fragment")
        elif not hecho:
            if st.button("Hecho", key=f"_cli_done_{tid}", use_container_width=True):
                completar_tarea(tid, True)
                registrar_actividad(cid, "nota", f"{_lbl} realizada: {t.get('titulo','')}")
                st.rerun(scope="fragment")

    # Panel de resultado (solo llamadas pendientes, cuando está abierto).
    if (not hecho) and tipo == "llamada" and st.session_state.get("_cli_act_res") == tid:
        _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
        _titulo = t.get("titulo", "")
        with st.container(border=True):
            # ── Sub-panel: CONTESTÓ → captura del guión de calificación ──
            if st.session_state.get("_cli_res_cal") == tid:
                st.markdown('<div class="cli-sec-t" style="margin:0 0 4px;">'
                            'Contestó — captura del guión</div>', unsafe_allow_html=True)
                _vals, _pregs = _guion_inputs(cli, f"_resq_{cid}")
                if not _pregs:
                    st.info("Aún no hay preguntas configuradas. El admin puede crearlas "
                            "con el botón «Guión».")
                gb1, gb2 = st.columns(2)
                with gb1:
                    if st.button("Guardar", key=f"_cli_calsave_{tid}", type="primary",
                                 use_container_width=True, icon=":material/save:"):
                        _guardar_contesto(cid, cli, tid, _vals, _pregs, _actor)
                        st.session_state.pop("_cli_res_cal", None)
                        st.session_state.pop("_cli_act_res", None)
                        st.toast("Calificación guardada")
                        st.rerun(scope="fragment")
                with gb2:
                    if st.button("Cancelar", key=f"_cli_calcancel_{tid}", use_container_width=True):
                        st.session_state.pop("_cli_res_cal", None)
                        st.rerun(scope="fragment")
            else:
                o1, o2 = st.columns(2)
                with o1:
                    if st.button("Contestó", key=f"_cli_rok_{tid}", type="primary",
                                 use_container_width=True, icon=":material/check_circle:"):
                        # Con guión → abre la captura; sin guión → marca contestó directo.
                        if _preguntas_data():
                            st.session_state["_cli_res_cal"] = tid
                        else:
                            _guardar_contesto(cid, cli, tid, None, [], _actor)
                            st.session_state.pop("_cli_act_res", None)
                            st.toast("Marcado: contestó")
                        st.rerun(scope="fragment")
                with o2:
                    if st.button("No interesado", key=f"_cli_rno_{tid}",
                                 use_container_width=True, icon=":material/block:"):
                        completar_tarea(tid, True, "no_interesado")
                        registrar_actividad(cid, "llamada", "Llamada — no interesado",
                                            detalle=_titulo, actor=_actor)
                        st.session_state.pop("_cli_act_res", None)
                        st.rerun(scope="fragment")
                st.markdown('<div style="font-size:0.72rem;color:#94a3b8;margin:6px 0 2px;">'
                            'No pude hablar → motivo + volver a llamar:</div>',
                            unsafe_allow_html=True)
                _motivo = st.selectbox("Motivo", list(_REINTENTO_MOTIVOS.keys()),
                                       key=f"_cli_rmot_{tid}", label_visibility="collapsed")
                _code = _REINTENTO_MOTIVOS[_motivo]
                n1, n2, n3 = st.columns(3)
                for _cw, (_ol, _cuando) in zip((n1, n2, n3),
                                               [("En 1 h", "1h"), ("En 2 h", "2h"), ("Mañana", "manana")]):
                    with _cw:
                        if st.button(_ol, key=f"_cli_rre_{tid}_{_cuando}", use_container_width=True):
                            completar_tarea(tid, True, _code)
                            registrar_actividad(cid, "llamada",
                                                f"Llamada — {_RESULT_META[_code][0].lower()}",
                                                detalle=_titulo, actor=_actor)
                            _crear_reintento(cid, cli, _titulo, _actor, _cuando)
                            st.session_state.pop("_cli_act_res", None)
                            st.toast("Reagendado")
                            st.rerun(scope="fragment")


# ── Fusionar duplicados ───────────────────────────────────────────────────────
def _tiene_calif(cli) -> bool:
    _v = cli.get("calificacion")
    if isinstance(_v, str):
        return _v not in ("", "{}", "null")
    return bool(_v)


def _render_dedup_dialog(data):
    """Diálogo (root/admin): detecta fichas con el mismo nombre y las fusiona en una
    principal (mueve presupuestos/actividades/datos; la otra queda inactiva)."""

    @st.dialog("Fusionar duplicados", width="large")
    def _dlg():
        _grupos = detectar_duplicados()
        if not _grupos:
            st.success("No se detectaron fichas duplicadas por nombre. 🎉")
            return
        st.markdown('<div class="cli-actf-hint">Fichas con el <b>mismo nombre</b> que probablemente '
                    'son la misma persona. Elige cuál queda como <b>principal</b> y fusiona: los '
                    'presupuestos, actividades y datos se mueven a la principal; la otra queda '
                    '<b>inactiva</b> (no se borra nada).</div>', unsafe_allow_html=True)
        _byid = {str(c.get("id")): c for c in data}
        for _gi, _grupo in enumerate(_grupos):
            with st.container(border=True, key=f"_dedup_grp_{_gi}"):
                st.markdown(f'<div class="cli-sec-t" style="margin:0 0 4px;">'
                            f'{_esc(_grupo[0].get("nombre",""))} · {len(_grupo)} fichas</div>',
                            unsafe_allow_html=True)
                _opts, _labels, _best_i, _best = [], {}, 0, -1
                for _i, _m in enumerate(_grupo):
                    _mid = str(_m.get("id"))
                    _en = _byid.get(_mid, _m)
                    _nc = len(_en.get("_cotizaciones") or [])
                    _hc = _tiene_calif(_m)
                    # La ficha CON calificación (la que gestionaste) manda como
                    # principal, para no perder los datos editados; los presupuestos
                    # se mueven igual a la que sobreviva.
                    _sc = _nc + (5 if _hc else 0)
                    if _sc > _best:
                        _best, _best_i = _sc, _i
                    _opts.append(_mid)
                    _labels[_mid] = (f"{_m.get('email') or _m.get('telefono') or 's/contacto'} · "
                                     f"{_nc} presup." + (" · con calificación" if _hc else ""))
                _sel = st.radio("Ficha principal (sobrevive)", _opts, index=_best_i,
                                key=f"_dedup_sv_{_gi}", format_func=lambda x: _labels.get(x, x))
                if st.button("Fusionar en la principal", type="primary",
                             key=f"_dedup_go_{_gi}", icon=":material/merge:", use_container_width=True):
                    _r = fusionar_clientes(_sel, [o for o in _opts if o != _sel])
                    if _r.get("error"):
                        st.error(f"No se pudo fusionar: {_r['error']}")
                    else:
                        _cli_data.clear()
                        st.session_state["_cli_toast"] = (
                            f"Fusionado: {_r['fusionados']} ficha(s), "
                            f"{_r['cotizaciones']} presupuesto(s) movido(s).")
                        st.rerun()

    _dlg()


# ── Envío masivo por segmento (campañas) ──────────────────────────────────────
_TIER_OPTS = {"Todos": "", "🔥 Caliente": "hot", "🔥 Tibio": "warm", "❄️ Frío": "cold"}


def _en_segmento(d, tier, ejemail, stage, fuente="") -> bool:
    """True si el cliente cae en el segmento y es enviable (tiene correo y NO se dio
    de baja)."""
    if tier and (d.get("_score") or {}).get("key") != tier:
        return False
    if ejemail and (d.get("asignado_email") or "").strip().lower() != ejemail:
        return False
    if stage and (d.get("_stage") or STAGE_LEAD) != stage:
        return False
    if fuente and _fuente_norm(d.get("origen")) != fuente:
        return False
    if not (d.get("email") or "").strip():
        return False
    if d.get("no_email"):
        return False
    return True


def _parece_html(texto: str) -> bool:
    """True si el cuerpo parece una plantilla HTML (para enviarla TAL CUAL en vez de
    convertir texto plano). Detecta doctype o etiquetas típicas de correos."""
    import re as _re2
    t = str(texto or "")
    if "<!doctype" in t.lower():
        return True
    return bool(_re2.search(
        r'<(html|body|table|div|p|a|img|h[1-6]|span|td|tr|center|style|strong|ul|ol|li|button)\b',
        t, _re2.I))


def _enviar_campana(segmento, subj_tpl, body_tpl, actor, adjuntos=None) -> dict:
    """Envía el correo personalizado a cada cliente del segmento. Si el cuerpo es una
    plantilla HTML se manda TAL CUAL (solo se reemplazan {{variables}}); si es texto,
    se convierte a HTML. Cada correo: reply-to al ejecutivo asignado + pie con link de
    baja + header List-Unsubscribe, y se registra en crm_correos para el seguimiento
    (entregado/abierto/clic/rebote, igual que el correo individual). CON adjuntos se
    envía UNO POR UNO (el batch de Resend no soporta adjuntos); SIN adjuntos, en lotes
    de 100. Devuelve {enviados, fallidos}."""
    res = {"enviados": 0, "fallidos": 0}
    _from = _resend_remitente()
    _es_html = _parece_html(body_tpl)
    _att = adjuntos or None
    _n_att = len(_att) if _att else 0

    def _componer(_cli):
        _subj = _resend_render(subj_tpl, _cli)
        _cuerpo = _resend_render(body_tpl, _cli)
        _reply = (_cli.get("asignado_email") or "").strip().lower() or _resend_reply()
        _html = ((_cuerpo if _es_html else _resend_texto_html(_cuerpo))
                 + _firma_html(_reply, masivo=True) + _resend_pie(_cli.get("id")))
        _hdr = {"List-Unsubscribe": f"<{_resend_unsub(_cli.get('id'))}>"}
        return _subj, _html, _reply, _hdr

    # CON adjuntos → uno por uno (el batch no soporta adjuntos).
    if _att:
        for _cli in segmento:
            _to = (_cli.get("email") or "").strip()
            _subj, _html, _reply, _hdr = _componer(_cli)
            _ok, _r = _resend_enviar(_to, _subj, _html, reply_to=(_reply or None),
                                     attachments=_att, headers=_hdr)
            if _ok:
                res["enviados"] += 1
                _registrar_correo(_cli.get("id"), _r, _to, _subj, actor, _n_att)
            else:
                res["fallidos"] += 1
        return res

    # SIN adjuntos → batch (100 por lote).
    _buf, _meta = [], []

    def _flush():
        if not _buf:
            return
        _ok, _r = _resend_lote(list(_buf))
        _ids = []
        if _ok and isinstance(_r, dict):
            _ids = [x.get("id", "") for x in (_r.get("data") or [])]
        for _i, (_cli, _subj) in enumerate(_meta):
            if _ok:
                res["enviados"] += 1
                _registrar_correo(_cli.get("id"), (_ids[_i] if _i < len(_ids) else ""),
                                  _cli.get("email", ""), _subj, actor, 0)
            else:
                res["fallidos"] += 1
        _buf.clear()
        _meta.clear()

    for _cli in segmento:
        _to = (_cli.get("email") or "").strip()
        _subj, _html, _reply, _hdr = _componer(_cli)
        _msg = {"from": _from, "to": [_to], "subject": _subj, "html": _html, "headers": _hdr}
        if _reply:
            _msg["reply_to"] = _reply
        _buf.append(_msg)
        _meta.append((_cli, _subj))
        if len(_buf) >= 100:
            _flush()
    _flush()
    return res


_CAMP_CSS = """<style>
/* Diálogo de campaña MÁS ANCHO (scoped con :has para no tocar otros diálogos). */
div[role="dialog"]:has(.cli-camp-intro){width:min(1180px,95vw)!important;max-width:1180px!important;}
.cli-camp-badge{display:inline-flex;align-items:center;gap:6px;font-family:Montserrat,sans-serif;
  font-weight:800;font-size:0.7rem;padding:4px 10px;border-radius:99px;margin:2px 0 8px;}
.cli-camp-badge svg{width:13px;height:13px;}
.cli-camp-badge-ok{background:#dcfce7;color:#15803d;}
.cli-camp-intro{font-size:0.78rem;color:#64748b;line-height:1.4;margin:0 0 12px;}
/* Barra de dropdowns del segmento (reusa el look .cli-fdd/.cli-fpill del home). */
.camp-fbar{display:flex;flex-wrap:wrap;gap:10px;margin:0 0 8px;}
/* (El CSS del toolbar de inserción vive inline en _MAIL_TOOLS_CSS, para que
   funcione también en la ficha, no solo en la campaña.) */
</style>"""

# Comportamiento de los dropdowns de la campaña (mismo look que el home, pero su
# selección va por el puente _camp_segcmd → Python recomputa el segmento). __CAMP_INIT__
# se reemplaza en cada render con la selección actual.
_CAMP_DD_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  __CAMP_INIT__
  // Ensanchar el diálogo de campaña (el CSS :has no siempre pega en Streamlit).
  try{
    var intro=D.querySelector('.cli-camp-intro');
    var dlg=intro&&intro.closest?intro.closest('[data-testid="stDialog"]'):null;
    var modal=dlg?(dlg.querySelector('[role="dialog"]')||dlg.firstElementChild):null;
    if(modal){ modal.style.setProperty('max-width','min(1180px,96vw)','important');
               modal.style.setProperty('width','min(1180px,96vw)','important'); }
  }catch(e){}
  function fireSel(){
    var inp=D.querySelector('.st-key-_camp_segcmd input'); if(!inp) return;
    var s=W._campSel||{}, val=[s.tier||'',s.ej||'',s.st||'',s.fu||'',Date.now()].join('|');
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true}); setter.call(inp, val);
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  function closeAll(){ D.querySelectorAll('.camp-dd.open').forEach(function(x){x.classList.remove('open');}); }
  function updTrg(dd){
    var k=dd.getAttribute('data-campk'), v=(W._campSel||{})[k]||'', body=dd.querySelector('.cli-fdd-body');
    var ph=dd.getAttribute('data-ph')||'Todos', pill=null;
    dd.querySelectorAll('.cli-fpill').forEach(function(p){ if((p.getAttribute('data-campv')||'')===v) pill=p; });
    body.textContent='';
    if(v && pill){
      var ic=pill.querySelector('.cli-fpill-ic,.cli-fpill-av'), lb=pill.querySelector('.cli-fpill-lb');
      if(ic) body.appendChild(ic.cloneNode(true));
      var cur=D.createElement('span'); cur.className='cli-fdd-cur'; cur.textContent=lb?lb.textContent:'';
      body.appendChild(cur); dd.classList.add('active');
    }else{
      var s=D.createElement('span'); s.className='cli-fdd-ph'; s.textContent=ph; body.appendChild(s);
      dd.classList.remove('active');
    }
  }
  if(W._campH){ D.removeEventListener('click', W._campH, true); }
  W._campH=function(e){
    var t=e.target; if(!t||!t.closest) return;
    if(!t.closest('.camp-fbar')){ closeAll(); return; }
    var trg=t.closest('.cli-fdd-trg');
    if(trg){ var dd=trg.closest('.camp-dd'), wo=dd.classList.contains('open');
      closeAll(); if(!wo) dd.classList.add('open'); e.preventDefault(); e.stopPropagation(); return; }
    var p=t.closest('.cli-fpill');
    if(p){ var k=p.getAttribute('data-campk'), v=p.getAttribute('data-campv')||'', dd2=p.closest('.camp-dd');
      (W._campSel=W._campSel||{})[k]=v;
      p.parentNode.querySelectorAll('.cli-fpill').forEach(function(x){x.classList.toggle('on',x===p);});
      updTrg(dd2); dd2.classList.remove('open'); fireSel();
      e.preventDefault(); e.stopPropagation(); return; }
  };
  D.addEventListener('click', W._campH, true);
})();
</script>"""


# Colección de emojis por categoría (para el picker tipo Outlook de la campaña).
_EMOJI_CATS = [
    ("Caras", ["😀", "😃", "😄", "😁", "😆", "😅", "😂", "🤣", "😊", "😇", "🙂", "🙃", "😉", "😌",
               "😍", "🥰", "😘", "😗", "😙", "😚", "😋", "😛", "😝", "😜", "🤪", "🤨", "🧐", "🤓",
               "😎", "🥳", "🤩", "😏", "😒", "😞", "😔", "😟", "😕", "🙁", "😣", "😖", "😫", "😩",
               "🥺", "😢", "😭", "😤", "😠", "😡", "🤬", "🤯", "😳", "🥵", "🥶", "😱", "😨", "😰",
               "😥", "😓", "🤗", "🤔", "🤭", "🤫", "😶", "😐", "😑", "😬", "🙄", "😮", "😲", "🥱",
               "😴", "🤤", "😪", "🤐", "🥴", "🤢", "🤮", "🤧", "😷", "🤒", "🤕", "🤠"]),
    ("Gestos", ["👍", "👎", "👌", "✌️", "🤞", "🤟", "🤘", "🤙", "👋", "🤚", "🖐️", "✋", "🖖", "👏",
                "🙌", "👐", "🤲", "🙏", "✍️", "💪", "👈", "👉", "👆", "👇", "☝️", "✊", "👊", "🤛",
                "🤜", "🤝"]),
    ("Corazones", ["❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍", "🤎", "💔", "❣️", "💕", "💞",
                   "💓", "💗", "💖", "💘", "💝"]),
    ("Símbolos", ["✨", "⭐", "🌟", "💫", "🔥", "💯", "✅", "❌", "⚡", "🎉", "🎊", "🎁", "🏆", "🥇",
                  "🔔", "📌", "⚠️", "♻️", "✔️", "💡", "➡️", "⬅️", "⬆️", "⬇️", "🔗"]),
    ("Hogar", ["🏠", "🏡", "🏘️", "🏢", "🏗️", "🔑", "🚪", "🛋️", "🛏️", "🚿", "🪟", "🧱", "🔨",
               "🛠️", "🧰", "📦", "📐", "📏", "🏙️", "🌆", "🌇"]),
    ("Naturaleza", ["🌲", "🌳", "🌴", "🌵", "🌿", "☘️", "🍀", "🌊", "🏔️", "⛰️", "🌄", "🌅", "☀️",
                    "⛅", "☁️", "🌧️", "🌈", "❄️", "🌙"]),
    ("Negocio", ["📞", "📱", "💬", "📧", "✉️", "📨", "📩", "💼", "📊", "📈", "📉", "💰", "💵", "💳",
                 "🧾", "📝", "📋", "✏️", "🖊️", "📅", "⏰"]),
]


# CSS del toolbar — va INLINE con el HTML para que funcione en cualquier compositor
# (campaña Y ficha), sin depender de que se haya inyectado _CAMP_CSS.
_MAIL_TOOLS_CSS = """<style>
.camp-tools{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin:8px 0 2px;position:relative;}
.camp-tools-lbl{font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;
  color:#94a3b8;margin-right:2px;}
.camp-ins{cursor:pointer;user-select:none;}
.camp-var-chip{display:inline-flex;align-items:center;font-size:0.72rem;font-weight:700;color:#4338ca;
  background:#eef2ff;border:1px solid #c7d2fe;border-radius:99px;padding:3px 10px;transition:all .12s;}
.camp-var-chip:hover{background:#e0e7ff;}
.camp-emoji-btn{display:inline-flex;align-items:center;gap:5px;font-size:0.72rem;font-weight:700;color:#475569;
  background:#f8fafc;border:1px solid #e2e8f0;border-radius:99px;padding:3px 11px;transition:all .12s;}
.camp-emoji-btn:hover{background:#f1f5f9;border-color:#cbd5e1;}
.camp-emoji-btn svg{width:14px;height:14px;flex:0 0 auto;}
.camp-emoji-panel{display:none;position:absolute;top:calc(100% + 6px);left:0;z-index:2147483001;width:342px;
  max-height:290px;overflow-y:auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;
  box-shadow:0 14px 40px rgba(15,23,42,.2);padding:6px 10px 10px;}
.camp-emoji-panel.open{display:block;}
.camp-emoji-cat{font-size:0.58rem;font-weight:800;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;
  margin:6px 0 3px;position:sticky;top:0;background:#fff;padding-top:2px;}
.camp-emoji-grid{display:grid;grid-template-columns:repeat(8,1fr);gap:2px;}
.camp-emoji{font-size:20px;line-height:1;text-align:center;padding:4px 0;border-radius:7px;transition:background .1s;}
.camp-emoji:hover{background:#eef2ff;}
</style>"""


def _mail_toolbar_html() -> str:
    """Toolbar de inserción: chips de variable + botón de emoji con panel (colección
    completa). Todo se inserta EN EL CAMPO ENFOCADO (asunto o mensaje) vía JS. Lo usan
    la campaña por segmento Y el correo individual de la ficha. Trae su CSS inline."""
    _chips = "".join(f'<span class="camp-ins camp-var-chip" data-ins="{_var}">{_lbl}</span>'
                     for _lbl, _var in _MAIL_VARS)
    _grid = ""
    for _cat, _ems in _EMOJI_CATS:
        _grid += (f'<div class="camp-emoji-cat">{_cat}</div><div class="camp-emoji-grid">'
                  + "".join(f'<span class="camp-ins camp-emoji" data-ins="{_e}">{_e}</span>' for _e in _ems)
                  + '</div>')
    _emoji_ic = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
                 'stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/>'
                 '<line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>')
    return (
        _MAIL_TOOLS_CSS
        + '<div class="camp-tools">'
        '<span class="camp-tools-lbl">Insertar (donde tengas el cursor)</span>'
        f'{_chips}'
        f'<span class="camp-ins camp-emoji-btn" id="_camp_emoji_btn">{_emoji_ic}Emoji</span>'
        f'<div class="camp-emoji-panel" id="_camp_emoji_panel">{_grid}</div>'
        '</div>')


# Inserta variables/emojis en el campo enfocado (asunto o mensaje) en la posición del
# cursor. mousedown.preventDefault evita robar el foco (si no, el blur cerraría el panel
# y dispararía un rerun). Solo dispara 'input' → sin rerun, el panel queda abierto.
# __SUBJ__/__BODY__ = keys de los widgets del compositor (campaña o ficha).
_MAIL_TOOLS_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  function fld(){
    var subj=D.querySelector('.st-key-__SUBJ__ input');
    var body=D.querySelector('.st-key-__BODY__ textarea');
    if(subj && !subj._cB){ subj._cB=1; subj.addEventListener('focus',function(){W._campFld=subj;}); }
    if(body && !body._cB){ body._cB=1; body.addEventListener('focus',function(){W._campFld=body;}); }
    var f=W._campFld;
    if(f && D.contains(f)) return f;
    return body||subj;
  }
  function insert(txt){
    var el=fld(); if(!el) return;
    var s=el.selectionStart, e=el.selectionEnd, v=el.value;
    if(typeof s!=='number'){ s=e=v.length; }
    var nv=v.slice(0,s)+txt+v.slice(e);
    var proto=(el.tagName==='TEXTAREA')?W.HTMLTextAreaElement.prototype:W.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto,'value').set.call(el, nv);
    el.dispatchEvent(new Event('input',{bubbles:true}));
    var p=s+txt.length;
    try{ el.focus(); el.setSelectionRange(p,p); }catch(_){}
    W._campFld=el;
  }
  fld(); setTimeout(fld,300); setTimeout(fld,800);
  if(W._campMD){ D.removeEventListener('mousedown', W._campMD, true); }
  W._campMD=function(ev){
    var t=ev.target;
    if(t&&t.closest&&(t.closest('.camp-tools')||t.closest('.camp-emoji-panel'))) ev.preventDefault();
  };
  D.addEventListener('mousedown', W._campMD, true);
  if(W._campToolsH){ D.removeEventListener('click', W._campToolsH, true); }
  W._campToolsH=function(ev){
    var t=ev.target; if(!t||!t.closest) return;
    if(t.closest('#_camp_emoji_btn')){
      var pan=D.getElementById('_camp_emoji_panel'); if(pan) pan.classList.toggle('open');
      ev.preventDefault(); ev.stopPropagation(); return;
    }
    var ins=t.closest('.camp-ins:not(.camp-emoji-btn)');
    if(ins && ins.hasAttribute('data-ins')){
      insert(ins.getAttribute('data-ins')); ev.preventDefault(); ev.stopPropagation(); return;
    }
    if(!t.closest('.camp-emoji-panel')){
      var pn=D.getElementById('_camp_emoji_panel'); if(pn) pn.classList.remove('open');
    }
  };
  D.addEventListener('click', W._campToolsH, true);
})();
</script>"""


def _mail_tools_js(subj_key: str, body_key: str) -> str:
    """JS del toolbar apuntando a los campos de ESTE compositor (asunto/mensaje)."""
    return _MAIL_TOOLS_JS.replace("__SUBJ__", subj_key).replace("__BODY__", body_key)


# ── Firma de correo por ejecutivo ─────────────────────────────────────────────
def _firma_defaults() -> dict:
    """Bloque de empresa por defecto (datos del PDF)."""
    return {"empresa": "Inversiones Container House SpA", "web": "espaciocontainerhouse.cl",
            "direccion": "Villasana 2039, Quinta Normal, Santiago", "telefono": "",
            "logo_url": "", "incluir": True}


def _firma_cfg_empresa() -> dict:
    _d = _firma_defaults()
    _d.update({k: v for k, v in (_get_firma("empresa") or {}).items() if v not in (None, "")})
    return _d


def _firma_activa(masivo: bool = False) -> bool:
    """True si la firma está activada para este tipo de envío. `masivo`=campaña,
    si no = correo uno-a-uno. Sin config → no se agrega. Compatibilidad: si solo
    existe el flag viejo 'incluir', vale para ambos."""
    _cfg = _get_firma("empresa")
    if not _cfg:
        return False
    _k = "incluir_masivo" if masivo else "incluir_individual"
    return bool(_cfg.get(_k, _cfg.get("incluir", True)))


def _firma_render(nombre, foto, cargo, tel, correo, cfg) -> str:
    """Firma HTML (tabla email-safe) a partir de valores explícitos. La usan el envío
    (datos guardados) y la vista previa (datos del formulario, en vivo)."""
    nombre = str(nombre or "").strip() or "Espacio Container House"
    cargo = str(cargo or "").strip() or "Ejecutivo/a de Ventas"
    tel = str(tel or "").strip()
    correo = str(correo or "").strip()
    logo = str(cfg.get("logo_url") or "").strip()
    web = str(cfg.get("web") or "").strip()
    empresa = str(cfg.get("empresa") or "").strip()
    direccion = str(cfg.get("direccion") or "").strip()

    _foto = (f'<img src="{_esc(foto)}" width="56" height="56" alt="" '
             'style="border-radius:50%;object-fit:cover;display:block;">') if foto else ""
    _logo = (f'<img src="{_esc(logo)}" width="118" alt="" '
             'style="display:block;max-width:118px;height:auto;">') if logo else (
             f'<b style="color:#0f172a;font-size:13px;">{_esc(empresa)}</b>' if empresa else "")
    _tel = (f'<a href="tel:{_esc(tel)}" style="color:#475569;text-decoration:none;">☎ {_esc(tel)}</a>'
            if tel else "")
    _mail = (f'<a href="mailto:{_esc(correo)}" style="color:#2563eb;text-decoration:none;">✉ {_esc(correo)}</a>'
             if correo else "")
    _web = (f'<a href="https://{_esc(web)}" style="color:#2563eb;text-decoration:none;">{_esc(web)}</a>'
            if web else "")
    _left = f'<td style="padding:0 14px 0 0;vertical-align:top;">{_foto}</td>' if _foto else ""
    _sep = ' &nbsp;·&nbsp; ' if (_tel and _mail) else ''
    return (
        '<div style="margin-top:26px;border-top:1px solid #e5e7eb;padding-top:14px;'
        'font-family:Arial,Helvetica,sans-serif;">'
        '<table cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tr>'
        f'{_left}<td style="vertical-align:top;">'
        f'<div style="font-size:15px;font-weight:700;color:#0f172a;">{_esc(nombre)}</div>'
        f'<div style="font-size:12.5px;color:#64748b;margin:1px 0 6px;">{_esc(cargo)}</div>'
        f'<div style="font-size:12.5px;line-height:1.7;">{_tel}{_sep}{_mail}</div>'
        f'<div style="margin-top:8px;">{_logo}</div>'
        '<div style="font-size:11.5px;color:#94a3b8;margin-top:5px;line-height:1.6;">'
        f'{_web}' + (f'<br>{_esc(direccion)}' if direccion else '') + '</div>'
        '</td></tr></table></div>')


def _firma_html(exec_email: str, masivo: bool = False) -> str:
    """Firma del ejecutivo remitente para agregar al correo. '' si está desactivada
    para este tipo de envío (`masivo`=campaña / si no = uno-a-uno)."""
    if not _firma_activa(masivo):
        return ""
    cfg = _firma_cfg_empresa()
    em = (exec_email or "").strip().lower()
    ex = _get_firma(em) or {}
    u = (_usuarios_map() or {}).get(em) or {}
    return _firma_render(u.get("nombre") or ex.get("nombre") or em, u.get("foto_url") or "",
                         ex.get("cargo"), ex.get("telefono") or cfg.get("telefono"), em, cfg)


def _render_firma_dialog(data):
    """Diálogo (root/admin): configurar la firma de correo — bloque de empresa +
    cargo/teléfono por ejecutivo, con vista previa EN VIVO. Se agrega sola a los
    correos (ficha y campaña) si está activada."""

    @st.dialog("Firma de correo", width="large")
    def _dlg():
        st.markdown(_CAMP_CSS, unsafe_allow_html=True)
        cfg = _firma_cfg_empresa()
        _logo0 = str(cfg.get("logo_url") or "").strip() or _logo_url_publica()
        st.markdown('<div class="cli-camp-intro">La firma se agrega automáticamente al final de '
                    'cada correo (ficha y campaña) con los datos del ejecutivo que atiende. El logo '
                    'se toma del <code>logo.png</code> del sistema.</div>', unsafe_allow_html=True)

        st.markdown('<div class="cli-sec-t" style="margin:0 0 6px;">Empresa (compartido)</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="cli-mail-tools-lbl">¿Dónde agregar la firma?</div>',
                    unsafe_allow_html=True)
        _ti1, _ti2 = st.columns(2)
        with _ti1:
            _inc_ind = st.toggle("Correos uno a uno (ficha)",
                                 value=bool(cfg.get("incluir_individual", cfg.get("incluir", True))),
                                 key="_firma_inc_ind")
        with _ti2:
            _inc_mas = st.toggle("Campañas masivas",
                                 value=bool(cfg.get("incluir_masivo", cfg.get("incluir", True))),
                                 key="_firma_inc_mas")
        _e1, _e2 = st.columns(2)
        with _e1:
            _empresa = st.text_input("Empresa", value=cfg.get("empresa", ""), key="_firma_empresa")
            _web = st.text_input("Sitio web", value=cfg.get("web", ""), key="_firma_web")
        with _e2:
            _tel_emp = st.text_input("Teléfono general", value=cfg.get("telefono", ""), key="_firma_tel")
            _dir = st.text_input("Dirección", value=cfg.get("direccion", ""), key="_firma_dir")
        _logo_in = st.text_input("URL del logo", value=_logo0, key="_firma_logo",
                                 help="Se llena solo subiendo logo.png; puedes pegar otra URL.")

        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
        st.markdown('<div class="cli-sec-t" style="margin:0 0 6px;">Datos del ejecutivo</div>',
                    unsafe_allow_html=True)
        _umap = _usuarios_map() or {}
        _ejs = sorted({e for e in ((d.get("asignado_email") or "").strip().lower() for d in data) if e}
                      | set(_umap.keys()))
        _opts = {(_umap.get(e, {}).get("nombre") or e): e for e in _ejs} or {
            st.session_state.get("auth_email", "yo"): st.session_state.get("auth_email", "")}
        _sel_nm = st.selectbox("Ejecutivo", list(_opts.keys()), key="_firma_ej_sel")
        _sel_em = _opts[_sel_nm]
        _exd = _get_firma(_sel_em) or {}
        _c1, _c2 = st.columns(2)
        with _c1:
            _cargo = st.text_input("Cargo", value=_exd.get("cargo", "Ejecutivo/a de Ventas"),
                                   key="_firma_cargo")
        with _c2:
            _tel_ej = st.text_input("Teléfono directo", value=_exd.get("telefono", ""), key="_firma_tel_ej")

        if st.button("Guardar firma", type="primary", use_container_width=True,
                     key="_firma_save", icon=":material/save:"):
            _ok1, _ = _set_firma("empresa", {"empresa": _empresa, "web": _web, "telefono": _tel_emp,
                                             "direccion": _dir, "logo_url": _logo_in,
                                             "incluir_individual": _inc_ind, "incluir_masivo": _inc_mas})
            _ok2, _ = _set_firma(_sel_em, {"cargo": _cargo, "telefono": _tel_ej, "nombre": _sel_nm})
            if _ok1 and _ok2:
                st.session_state["_cli_toast"] = "Firma guardada."
                st.rerun()
            else:
                st.error("No se pudo guardar. ¿Creaste la tabla crm_firma en Supabase?")

        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
        st.markdown('<div class="cli-sec-t" style="margin:0 0 6px;">Vista previa</div>',
                    unsafe_allow_html=True)
        _prev = _firma_render(_sel_nm, _umap.get(_sel_em, {}).get("foto_url", ""), _cargo,
                              _tel_ej or _tel_emp, _sel_em,
                              {"empresa": _empresa, "web": _web, "telefono": _tel_emp,
                               "direccion": _dir, "logo_url": _logo_in})
        components.html(f'<div style="background:#fff;padding:16px 18px;border-radius:8px;">{_prev}</div>',
                        height=250, scrolling=True)

    _dlg()


def _render_campana_dialog(data):
    """Diálogo (root/admin): campaña de correo a un SEGMENTO (potencial/ejecutivo/
    estado/fuente). Redacción en texto o pegando/importando una plantilla HTML
    profesional (autodetectada, con vista previa). Adjuntos opcionales (envío
    individual). Cada correo lleva link de baja, reply-to al ejecutivo asignado y
    seguimiento (track) — igual que el correo individual de la ficha."""

    @st.dialog("Nueva campaña · correo por segmento", width="large")
    def _dlg():
        st.markdown(_CAMP_CSS, unsafe_allow_html=True)
        if not _resend_configurado():
            st.warning("Falta la RESEND_API_KEY en los secrets. Cuando la agregues, se activa.")
        st.markdown('<div class="cli-camp-intro">Envía un correo personalizado a un grupo de '
                    'clientes. Filtra el segmento, redacta o <b>pega una plantilla HTML</b> '
                    'profesional, y envía.</div>', unsafe_allow_html=True)

        # ── Segmento (dropdowns con avatar, idénticos a los del home) ───────
        st.markdown('<div class="cli-sec-t" style="margin:0 0 6px;">Segmento</div>',
                    unsafe_allow_html=True)
        _sel = st.session_state.get("_camp_sel", {}) or {}
        _tier, _ejemail = _sel.get("tier", ""), _sel.get("ej", "")
        _stage, _fuente = _sel.get("st", ""), _sel.get("fu", "")

        _chev = ('<svg class="cli-fdd-cv" width="15" height="15" viewBox="0 0 24 24" fill="none" '
                 'stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                 '<path d="m6 9 6 6 6-6"/></svg>')

        def _ic_all(pth):
            return f'<span class="cli-fpill-ic cli-fpill-ic-all">{_svg(pth, 15, "currentColor")}</span>'

        def _ic_col(pth, bg, fg):
            return (f'<span class="cli-fpill-ic" style="background:{bg};color:{fg};">'
                    f'{_svg(pth, 15, "currentColor") if pth else ""}</span>')

        def _opt(campk, campv, label, ic, cur):
            _c = "cli-fpill" + (" on" if campv == cur else "")
            return (f'<span class="{_c}" data-campk="{campk}" data-campv="{_esc(campv)}">'
                    f'{ic}<span class="cli-fpill-lb">{_esc(label)}</span></span>')

        def _dd(campk, ph, opts, cur, cur_ic, cur_lbl):
            if cur and cur_lbl:
                _body = f'{cur_ic}<span class="cli-fdd-cur">{_esc(cur_lbl)}</span>'
                _act = " active"
            else:
                _body, _act = f'<span class="cli-fdd-ph">{_esc(ph)}</span>', ""
            return (f'<div class="cli-fdd camp-dd{_act}" data-campk="{campk}" data-ph="{_esc(ph)}">'
                    f'<button class="cli-fdd-trg" type="button"><span class="cli-fdd-body">{_body}</span>'
                    f'{_chev}</button><div class="cli-fdd-menu"><div class="cli-fpills">{opts}</div></div></div>')

        # Potencial
        _TM = [("hot", "Caliente", "#dc2626", "rgba(220,38,38,.12)"),
               ("warm", "Tibio", "#d97706", "rgba(217,119,6,.15)"),
               ("cold", "Frío", "#2563eb", "rgba(37,99,235,.12)")]
        _o = _opt("tier", "", "Todo el potencial", _ic_all(_IC_TODOS), _tier)
        _ti, _tl = {}, {}
        for _k, _l, _fg, _bg in _TM:
            _ic = _ic_col(_FLAME_PATH, _bg, _fg)
            _o += _opt("tier", _k, _l, _ic, _tier)
            _ti[_k], _tl[_k] = _ic, _l
        _dd_tier = _dd("tier", "Todo el potencial", _o, _tier, _ti.get(_tier, ""), _tl.get(_tier, ""))

        # Ejecutivo (con foto/iniciales, como el home)
        _ejinfo = {(e.get("email") or "").strip().lower(): e for e in _ejecutivos()}
        _umap = _usuarios_map()
        _ejset = {}
        for d in data:
            _e = (d.get("asignado_email") or "").strip().lower()
            if _e:
                _ejset[_e] = _resolver_asig(_e, d.get("asignado_nombre")) or _e
        _o = _opt("ej", "", "Todos los ejecutivos", _ic_all(_IC_USERS), _ejemail)
        _ei, _el = {}, {}
        for _e in sorted(_ejset, key=lambda x: (_ejset[x] or "").lower()):
            _einf, _udir = _ejinfo.get(_e) or {}, _umap.get(_e) or {}
            _enm = _ejset[_e] or _einf.get("nombre") or _udir.get("nombre") or _e
            _foto = _einf.get("foto_url") or _udir.get("foto_url") or ""
            _av = (f'<span class="cli-fpill-av">'
                   f'{_avatar_html(_foto, _enm, size=32, ring="#fff", font_scale=0.4)}</span>')
            _o += _opt("ej", _e, _enm, _av, _ejemail)
            _ei[_e], _el[_e] = _av, _enm
        _dd_ej = _dd("ej", "Todos los ejecutivos", _o, _ejemail, _ei.get(_ejemail, ""), _el.get(_ejemail, ""))

        # Estado
        _o = _opt("st", "", "Todos los estados", _ic_all(_IC_TODOS), _stage)
        _si, _sl = {}, {}
        for _s in _STAGE_ORDER:
            _lbl, _dot, _bg, _fg = _STAGE_META[_s]
            _ic = _ic_col(_STAGE_ICON.get(_s, ""), _bg, _fg)
            _o += _opt("st", _s, _lbl, _ic, _stage)
            _si[_s], _sl[_s] = _ic, _lbl
        _dd_st = _dd("st", "Todos los estados", _o, _stage, _si.get(_stage, ""), _sl.get(_stage, ""))

        # Fuente
        _fucnt = {}
        for d in data:
            _fk = _fuente_norm(d.get("origen"))
            _fucnt[_fk] = _fucnt.get(_fk, 0) + 1
        _o = _opt("fu", "", "Todas las fuentes", _ic_all(_IC_TODOS), _fuente)
        _fi, _fl_ = {}, {}
        for _fk in sorted(_fucnt, key=lambda x: (-_fucnt[x], x)):
            _flbl, _fico, _ffg, _fbg = _fuente_meta(_fk)
            _ic = _ic_col(_fico, _fbg, _ffg)
            _o += _opt("fu", _fk, _flbl, _ic, _fuente)
            _fi[_fk], _fl_[_fk] = _ic, _flbl
        _dd_fu = _dd("fu", "Todas las fuentes", _o, _fuente, _fi.get(_fuente, ""), _fl_.get(_fuente, ""))

        st.markdown(f'<div class="camp-fbar">{_dd_ej}{_dd_st}{_dd_tier}{_dd_fu}</div>',
                    unsafe_allow_html=True)
        _init = ("W._campSel={tier:'%s',ej:'%s',st:'%s',fu:'%s'};" % (
            _tier, _ejemail.replace("'", "\\'"), _stage, _fuente))
        components.html(_CAMP_DD_JS.replace("__CAMP_INIT__", _init), height=0)

        _seg = [d for d in data if _en_segmento(d, _tier, _ejemail, _stage, _fuente)]
        st.markdown(
            f'<div class="cli-actf-hint">Se enviará a <b>{len(_seg)} destinatario(s)</b> '
            '(con correo y sin baja). Se excluyen los sin correo y los dados de baja.</div>',
            unsafe_allow_html=True)
        if not _seg:
            st.info("Ningún cliente en este segmento tiene correo para enviar.")

        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)

        # ── Mensaje ─────────────────────────────────────────────────────────
        st.markdown('<div class="cli-sec-t" style="margin:0 0 6px;">Mensaje</div>',
                    unsafe_allow_html=True)
        with st.container(key="_cli_mail_form"):
            st.text_input("Asunto", key="_camp_subj",
                          placeholder="Tu casa container a medida, {{nombre}}")
            st.text_area("Mensaje", key="_camp_body", height=180,
                         placeholder="Hola {{nombre}}, seguimos con tu proyecto en {{comuna}}…\n\n"
                         "O pega aquí el HTML de una plantilla profesional (Stripo, BeeFree…). "
                         "El sistema lo detecta solo.")
            # Toolbar: variables + colección completa de emojis; inserta en el campo
            # enfocado (asunto o mensaje) en la posición del cursor.
            st.markdown(_mail_toolbar_html(), unsafe_allow_html=True)
        components.html(_mail_tools_js("_camp_subj", "_camp_body"), height=0)

        # Plantilla HTML: subir un .html (opcional) — tiene prioridad sobre el cuadro.
        _html_file = st.file_uploader("Importar plantilla .html (opcional)",
                                      type=["html", "htm"], key="_camp_html_file")
        _body = st.session_state.get("_camp_body", "") or ""
        if _html_file is not None:
            try:
                _body = _html_file.getvalue().decode("utf-8", "ignore")
            except Exception:
                pass
        _es_html = _parece_html(_body)

        # Badge de detección + vista previa (con el 1er destinatario o datos de ejemplo).
        if (_body or "").strip():
            if _es_html:
                st.markdown('<div class="cli-camp-badge cli-camp-badge-ok">'
                            + _svg('<path d="M20 6 9 17l-5-5"/>', 13, "currentColor")
                            + 'Plantilla HTML detectada — se envía tal cual</div>',
                            unsafe_allow_html=True)
            _muestra = _seg[0] if _seg else {"nombre": "Juan", "comuna": "Santiago",
                                             "email": "juan@correo.cl", "telefono": "+56 9 …"}
            _prev = _resend_render(_body, _muestra)
            _prev_html = _prev if _es_html else _resend_texto_html(_prev)
            with st.expander("Vista previa del correo", expanded=_es_html):
                components.html(
                    f'<div style="background:#fff;padding:14px;border-radius:8px;font-family:Arial,'
                    f'sans-serif;">{_prev_html}</div>', height=380, scrolling=True)

        # Adjuntos (PDF/imágenes/…). Con adjuntos, el envío es individual.
        _files = st.file_uploader("Adjuntar archivos (opcional)", accept_multiple_files=True,
                                  key="_camp_files")

        _hint = ('Cada correo lleva <b>link de baja</b>, reply-to al <b>ejecutivo asignado</b> '
                 'y seguimiento (entregado/abrió/clic/rebote).')
        if _files:
            _hint += ' Con adjuntos el envío es <b>uno por uno</b> (más lento en listas grandes).'
        st.markdown(f'<div class="cli-actf-hint">{_hint}</div>', unsafe_allow_html=True)
        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)

        # ── Enviar prueba (ver cómo llega la plantilla antes de la campaña) ──
        st.markdown('<div class="cli-mail-tools-lbl">Enviar prueba</div>', unsafe_allow_html=True)
        if "_camp_test_to" not in st.session_state:
            st.session_state["_camp_test_to"] = st.session_state.get("auth_email", "") or ""
        _tc1, _tc2 = st.columns([3, 1])
        with _tc1:
            _test_to = st.text_input("Correo de prueba", key="_camp_test_to",
                                     placeholder="tucorreo@ejemplo.cl", label_visibility="collapsed")
        with _tc2:
            _test_click = st.button("Enviar prueba", key="_camp_test_send", use_container_width=True,
                                    icon=":material/outgoing_mail:", disabled=(not _resend_configurado()))
        if _test_click:
            _subj_t = st.session_state.get("_camp_subj", "")
            if not (_test_to or "").strip() or not (_subj_t or "").strip() or not (_body or "").strip():
                st.warning("Escribe el asunto, el mensaje y el correo de prueba.")
            else:
                _mtest = _seg[0] if _seg else {"nombre": "Prueba", "comuna": "Santiago",
                                               "email": _test_to, "telefono": "+56 9 1234 5678"}
                _es_h = _parece_html(_body)
                _subj_r = _resend_render(_subj_t, _mtest)
                _cuerpo_r = _resend_render(_body, _mtest)
                _html_r = (_cuerpo_r if _es_h else _resend_texto_html(_cuerpo_r))
                if _mtest.get("id"):
                    _html_r += _resend_pie(_mtest.get("id"))
                _att_t = []
                for _f in (_files or []):
                    try:
                        import base64
                        _att_t.append({"filename": _f.name,
                                       "content": base64.b64encode(_f.getvalue()).decode()})
                    except Exception:
                        pass
                with st.spinner("Enviando prueba…"):
                    _okt, _rt = _resend_enviar(_test_to.strip(), "[PRUEBA] " + _subj_r, _html_r,
                                               reply_to=(_resend_reply() or None),
                                               attachments=_att_t or None)
                if _okt:
                    st.success(f"Prueba enviada a {_test_to}. Revisa tu bandeja (asunto [PRUEBA]).")
                else:
                    st.error(f"No se pudo enviar la prueba: {_rt}")
        st.markdown('<div class="cli-actf-hint">Se envía UN correo con el asunto <b>[PRUEBA]</b> al correo '
                    'que indiques, con esta misma plantilla — para revisar cómo llega.</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)

        if st.button(f"Enviar campaña a {len(_seg)}", type="primary", use_container_width=True,
                     key="_camp_send", icon=":material/send:",
                     disabled=(not _seg or not _resend_configurado())):
            _subj = st.session_state.get("_camp_subj", "")
            if not (_subj or "").strip() or not (_body or "").strip():
                st.warning("Escribe el asunto y el mensaje (o sube una plantilla HTML).")
            else:
                _att = []
                for _f in (_files or []):
                    try:
                        import base64
                        _att.append({"filename": _f.name,
                                     "content": base64.b64encode(_f.getvalue()).decode()})
                    except Exception:
                        pass
                _actor = (st.session_state.get("auth_nombre")
                          or st.session_state.get("auth_email", ""))
                with st.spinner(f"Enviando {len(_seg)} correo(s)…"):
                    _r = _enviar_campana(_seg, _subj, _body, _actor, adjuntos=_att or None)
                for _k in ("_camp_subj", "_camp_body"):
                    st.session_state.pop(_k, None)
                st.session_state["_cli_toast"] = (
                    f"Campaña enviada: {_r['enviados']} correo(s)"
                    + (f" · {_r['fallidos']} fallaron" if _r['fallidos'] else "") + ".")
                st.rerun()

    _dlg()


def _camp_insert(txt):
    """Append de variable/emoji al cuerpo de la campaña (on_click)."""
    st.session_state["_camp_body"] = (st.session_state.get("_camp_body") or "") + txt


# ── Importar leads desde CSV / Excel (con mapeo de columnas) ──────────────────
_IMPORT_LABELS = {
    "nombre": "Nombre *", "rut": "RUT", "email": "Correo", "telefono": "Teléfono",
    "direccion": "Dirección", "comuna": "Comuna", "region": "Región",
    "empresa": "Empresa", "rut_empresa": "RUT empresa",
}
_IMPORT_SYN = {
    "nombre": ["nombre", "name", "cliente", "nombrecompleto", "fullname", "razonsocial",
               "contacto", "clientenombre", "nombreapellido"],
    "rut": ["rut", "run", "dni", "documento", "identificacion", "rutcliente"],
    "email": ["email", "correo", "mail", "emailcliente", "correoelectronico", "email"],
    "telefono": ["telefono", "fono", "phone", "celular", "movil", "whatsapp", "numero",
                 "telefonocliente", "contactotelefono"],
    "direccion": ["direccion", "address", "domicilio", "calle"],
    "comuna": ["comuna", "ciudad", "city", "localidad"],
    "region": ["region", "state", "provincia", "estado"],
    "empresa": ["empresa", "company", "compania", "negocio"],
    "rut_empresa": ["rutempresa", "companyrut", "rutcompania"],
}


def _norm_header(s) -> str:
    """Nombre de columna normalizado: sin acentos, minúsculas, solo alfanumérico."""
    s = _ud.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def _auto_map(columns: list) -> dict:
    """Adivina el mapeo columna→campo. Primero por match EXACTO del header, luego
    por substring. Cada columna se usa una sola vez."""
    norm = {c: _norm_header(c) for c in columns}
    out = {f: "" for f in _IMPORT_SYN}
    used = set()
    for f, syns in _IMPORT_SYN.items():
        for c in columns:
            if c not in used and norm[c] in syns:
                out[f] = c
                used.add(c)
                break
    for f, syns in _IMPORT_SYN.items():
        if out[f]:
            continue
        for c in columns:
            if c in used:
                continue
            nc = norm[c]
            if nc and any(s in nc or nc in s for s in syns):
                out[f] = c
                used.add(c)
                break
    return out


def _read_upload(upload):
    """Lee el archivo subido (CSV/XLSX) a un DataFrame de strings. (df, error)."""
    import pandas as pd
    name = (getattr(upload, "name", "") or "").lower()
    try:
        upload.seek(0)
    except Exception:
        pass
    try:
        if name.endswith(".csv"):
            try:
                df = pd.read_csv(upload, sep=None, engine="python", dtype=str, keep_default_na=False)
            except UnicodeDecodeError:
                upload.seek(0)
                df = pd.read_csv(upload, sep=None, engine="python", dtype=str,
                                 keep_default_na=False, encoding="latin-1")
        else:
            df = pd.read_excel(upload, dtype=str).fillna("")
        df.columns = [str(c).strip() for c in df.columns]
        return df, None
    except Exception as e:
        return None, str(e)


def _render_importar_dialog():
    """Diálogo (root/admin): importa leads desde CSV/Excel con mapeo de columnas."""

    @st.dialog("Importar leads", width="large")
    def _dlg():
        st.markdown('<div class="cli-actf-hint">Sube un CSV o Excel, ajusta a qué campo va cada '
                    'columna y confirma. Se omiten los que ya existen (por RUT, correo, teléfono '
                    'o nombre). Los importados caen en la <b>Bandeja</b> como leads nuevos.</div>',
                    unsafe_allow_html=True)
        up = st.file_uploader("Archivo", type=["csv", "xlsx"], key="_imp_file",
                              label_visibility="collapsed")
        if not up:
            return
        df, err = _read_upload(up)
        if df is None:
            st.error(f"No se pudo leer el archivo: {err}")
            return
        if df.empty:
            st.warning("El archivo no tiene filas.")
            return

        cols = list(df.columns)
        _guess = _auto_map(cols)
        st.markdown('<div class="cli-sec-t" style="margin:10px 0 2px;">Mapeo de columnas</div>',
                    unsafe_allow_html=True)
        _opts = ["— ninguna —"] + cols
        mapping = {}
        _mc = st.columns(2)
        for _i, (_f, _lbl) in enumerate(_IMPORT_LABELS.items()):
            with _mc[_i % 2]:
                _def = _guess.get(_f, "")
                _idx = _opts.index(_def) if _def in _opts else 0
                _sel = st.selectbox(_lbl, _opts, index=_idx, key=f"_imp_map_{_f}")
                mapping[_f] = "" if _sel == "— ninguna —" else _sel

        if not mapping.get("nombre"):
            st.warning("Debes mapear al menos la columna de **Nombre**.")
            return

        rows = []
        for _, _r in df.iterrows():
            _row = {_f: (str(_r.get(_col, "") or "").strip() if _col else "")
                    for _f, _col in mapping.items()}
            if _row.get("nombre"):
                rows.append(_row)

        st.markdown(f'<div class="cli-sec-t" style="margin:12px 0 2px;">Vista previa · '
                    f'{len(rows)} lead(s) con nombre</div>', unsafe_allow_html=True)
        _pv = "".join(
            f'<tr><td style="font-weight:700;">{_esc(r.get("nombre",""))}</td>'
            f'<td>{_esc(r.get("rut","") or "—")}</td>'
            f'<td>{_esc(r.get("email","") or "—")}</td>'
            f'<td>{_esc(r.get("telefono","") or "—")}</td>'
            f'<td>{_esc(r.get("comuna","") or "—")}</td></tr>'
            for r in rows[:5])
        st.markdown('<div class="cli-tbl-wrap"><table><thead><tr>'
                    '<th>Nombre</th><th>RUT</th><th>Correo</th><th>Tel&eacute;fono</th><th>Comuna</th>'
                    f'</tr></thead><tbody>{_pv}</tbody></table></div>', unsafe_allow_html=True)
        if len(rows) > 5:
            st.markdown(f'<div style="font-size:0.74rem;color:#94a3b8;margin-top:4px;">'
                        f'… y {len(rows) - 5} más.</div>', unsafe_allow_html=True)

        _oc1, _oc2 = st.columns(2)
        with _oc1:
            _origen = st.text_input("Origen", value="Importado", key="_imp_origen")
        with _oc2:
            _ejs = _ejecutivos()
            _asig_opts = ["— Sin asignar —"] + [(e.get("nombre") or e.get("email")) for e in _ejs]
            _asig_sel = st.selectbox("Asignar a (opcional)", _asig_opts, key="_imp_asig")

        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
        if st.button(f"Importar {len(rows)} lead(s)", type="primary", use_container_width=True,
                     key="_imp_go", disabled=not rows, icon=":material/upload_file:"):
            _ae, _an = "", ""
            if _asig_sel != "— Sin asignar —":
                for e in _ejs:
                    if (e.get("nombre") or e.get("email")) == _asig_sel:
                        _ae, _an = e.get("email", ""), (e.get("nombre") or e.get("email") or "")
                        break
            with st.spinner("Importando…"):
                res = importar_leads(rows, origen=(_origen or "").strip() or "Importado",
                                     asignado_email=_ae, asignado_nombre=_an)
            _cli_data.clear()
            st.session_state["_cli_toast"] = (
                f"Importados: {res['creados']} nuevo(s) · {res['duplicados']} ya existían · "
                f"{res['omitidos']} sin nombre.")
            st.rerun()

    _dlg()


def _render_guion_config():
    """Diálogo (solo root/admin): CRUD de las preguntas del guión de calificación.
    Baja lógica al eliminar (no se pierden respuestas). Reordenable por número."""

    @st.dialog("Guión de calificación", width="large")
    def _dlg():
        st.markdown('<div style="font-size:0.82rem;color:#475569;margin-bottom:8px;">'
                    'Preguntas que el ejecutivo captura cuando el cliente <b>contesta</b> la '
                    'llamada. Ordénalas con el número (menor primero).</div>',
                    unsafe_allow_html=True)
        _pregs = listar_preguntas(solo_activas=True)

        for p in _pregs:
            pid = str(p.get("id"))
            if st.session_state.get("_guion_edit") == pid:
                with st.container(border=True):
                    _etxt = st.text_input("Pregunta", value=p.get("texto", ""),
                                          key=f"_ged_txt_{pid}")
                    _ec1, _ec2 = st.columns([2, 1])
                    with _ec1:
                        _etp = st.selectbox("Tipo", list(TIPOS_CAMPO),
                                            index=list(TIPOS_CAMPO).index(p.get("tipo_campo", "texto"))
                                            if p.get("tipo_campo") in TIPOS_CAMPO else 0,
                                            key=f"_ged_tipo_{pid}",
                                            format_func=lambda x: _TIPO_CAMPO_LABEL.get(x, x))
                    with _ec2:
                        _eord = st.number_input("Orden", value=int(p.get("orden") or 0),
                                                step=1, key=f"_ged_ord_{pid}")
                    _eops = ""
                    if _etp == "opciones":
                        _eops = st.text_input("Opciones (separadas por coma)",
                                              value=", ".join(p.get("opciones") or []),
                                              key=f"_ged_ops_{pid}", placeholder="Invertir, Vivir")
                    _sc1, _sc2 = st.columns(2)
                    with _sc1:
                        if st.button("Guardar", key=f"_ged_save_{pid}", type="primary",
                                     use_container_width=True, icon=":material/save:"):
                            _campos = {"texto": _etxt.strip(), "tipo_campo": _etp,
                                       "orden": int(_eord)}
                            _campos["opciones"] = ([o.strip() for o in _eops.split(",") if o.strip()]
                                                   if _etp == "opciones" else [])
                            actualizar_pregunta(pid, _campos)
                            _preguntas_data.clear()
                            st.session_state.pop("_guion_edit", None)
                            st.rerun(scope="fragment")
                    with _sc2:
                        if st.button("Cancelar", key=f"_ged_cancel_{pid}",
                                     use_container_width=True):
                            st.session_state.pop("_guion_edit", None)
                            st.rerun(scope="fragment")
            else:
                rc1, rc2, rc3 = st.columns([8, 1, 1], vertical_alignment="center")
                with rc1:
                    _opsx = (" · " + ", ".join(p.get("opciones") or [])) if p.get("tipo_campo") == "opciones" else ""
                    st.markdown(
                        f'<div style="padding:2px 0;"><span style="color:#94a3b8;font-size:0.8rem;">'
                        f'{int(p.get("orden") or 0)}.</span> '
                        f'<b style="font-size:0.9rem;color:#0f172a;">{_esc(p.get("texto",""))}</b> '
                        f'<span class="cli-pill" style="background:#eef2ff;color:#4338ca;">'
                        f'{_TIPO_CAMPO_LABEL.get(p.get("tipo_campo","texto"), "Texto")}</span>'
                        f'<span style="color:#94a3b8;font-size:0.78rem;">{_esc(_opsx)}</span></div>',
                        unsafe_allow_html=True)
                with rc2:
                    if st.button("", key=f"_gli_ed_{pid}", use_container_width=True,
                                 icon=":material/edit:", help="Editar"):
                        st.session_state["_guion_edit"] = pid
                        st.rerun(scope="fragment")
                with rc3:
                    if st.button("", key=f"_gli_del_{pid}", use_container_width=True,
                                 icon=":material/delete:", help="Quitar"):
                        eliminar_pregunta(pid)
                        _preguntas_data.clear()
                        st.rerun(scope="fragment")

        if not _pregs:
            st.markdown('<div style="font-size:0.82rem;color:#94a3b8;padding:6px 0;">'
                        'Aún no hay preguntas. Crea la primera abajo.</div>',
                        unsafe_allow_html=True)

        st.divider()
        st.markdown('<div class="cli-sec-t" style="margin:0 0 4px;">Nueva pregunta</div>',
                    unsafe_allow_html=True)
        _ntxt = st.text_input("Pregunta nueva", key="_gnew_txt",
                              placeholder="Ej: ¿Cuál es el presupuesto del cliente?",
                              label_visibility="collapsed")
        _ntp = st.selectbox("Tipo de campo", list(TIPOS_CAMPO), key="_gnew_tipo",
                            format_func=lambda x: _TIPO_CAMPO_LABEL.get(x, x))
        _nops = ""
        if _ntp == "opciones":
            _nops = st.text_input("Opciones (separadas por coma)", key="_gnew_ops",
                                  placeholder="Invertir, Vivir")
        if st.button("Agregar pregunta", key="_gnew_add", type="primary",
                     use_container_width=True, icon=":material/add:"):
            if not _ntxt.strip():
                st.warning("Escribe la pregunta.")
            else:
                _opts = [o.strip() for o in _nops.split(",") if o.strip()] if _ntp == "opciones" else []
                _pid, _err = crear_pregunta(_ntxt.strip(), _ntp, _opts)
                if _pid:
                    _preguntas_data.clear()
                    for _k in ("_gnew_txt", "_gnew_ops"):
                        st.session_state.pop(_k, None)
                    st.toast("Pregunta agregada")
                    st.rerun(scope="fragment")
                else:
                    st.error(f"No se pudo crear: {_err}")

    _dlg()


def _render_ficha(cid: str, data: list):
    cli = next((d for d in data if str(d.get("id")) == str(cid)), None)
    if not cli:
        return
    _stage = cli.get("_stage") or STAGE_LEAD
    _slbl, _sdot, _sbg, _sfg = _STAGE_META.get(_stage, _STAGE_META[STAGE_LEAD])

    @st.dialog("Ficha del cliente", width="large")
    def _dlg():
        _asig = _resolver_asig(cli.get("asignado_email"), cli.get("asignado_nombre")) or "Sin asignar"
        _nombre = cli.get("nombre", "") or ""
        _nm_html = (f'<div class="cli-fh-nm cli-copy" data-copy="{_esc(_nombre)}" title="Copiar nombre">{_esc(_nombre)}</div>'
                    if _nombre else '<div class="cli-fh-nm">—</div>')
        _rut = cli.get("rut", "") or ""
        _rut_html = (_cp(_rut, _esc(_rut), "Copiar RUT") if _rut else "Sin RUT")
        _sc = cli.get("_score") or _lead_score(cli, _preguntas_data())
        st.markdown(
            '<div class="cli-fh">'
            f'<div class="cli-fh-av">{_esc(_initials(cli.get("nombre")))}</div>'
            '<div style="min-width:0;flex:1;">'
            f'{_nm_html}'
            f'<div class="cli-fh-sub">{_rut_html} · {_esc(_asig)}</div>'
            '</div>'
            f'<div style="margin-left:auto;">{_score_badge(_sc, "md")}</div>'
            '</div>'
            '<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:6px;">'
            f'{_origen_pill(cli.get("origen","Manual"))}'
            f'<span class="cli-pill" style="background:{_sbg};color:{_sfg};">{_slbl}</span>'
            f'{_sla_clock_html(cli.get("stage_desde") or cli.get("fecha_creacion"), _stage_work(cli), lg=True)}'
            '</div>', unsafe_allow_html=True)

        # Potencial del lead: nivel + desglose (qué falta para subirlo).
        _SC_COL = {"hot": "#dc2626", "warm": "#d97706", "cold": "#2563eb"}
        _tcol = _SC_COL[_sc["key"]]
        # Barra estilo MEDIDOR: la pista es el degradado rojo→amarillo→verde (igual
        # para las 3) y la parte NO alcanzada se atenúa (`.cli-scdim` desde el %).
        def _scbar(k, v, mx):
            _pct = round(v / mx * 100) if mx else 0
            return (f'<div class="cli-scrow"><span class="cli-sck">{k}</span>'
                    f'<span class="cli-scbar"><span class="cli-scdim" style="left:{_pct}%;"></span></span>'
                    f'<span class="cli-scv">{v}/{mx}</span></div>')
        _falt = _score_faltantes(cli, _preguntas_data(), _sc)
        _hint = ("💡 Sube el potencial: " + " · ".join(f"{l} (+{p})" for l, p in _falt)
                 if _falt else "✅ Lead completo, máximo potencial.")
        st.markdown(
            f'<div class="cli-sec-t" style="margin:6px 0 4px;">Potencial del lead · '
            f'<span style="color:{_tcol};">{_sc["label"]} {_sc["total"]}/100</span></div>'
            '<div class="cli-scbrk">'
            + _scbar("Contacto", _sc["contacto"], 40)
            + _scbar("Calificación", _sc["calif"], 45)
            + _scbar("Interés", _sc["interes"], 15)
            + '</div>'
            f'<div class="cli-schint">{_hint}</div>', unsafe_allow_html=True)

        # Datos de contacto (ver + Editar). Copiables al click; WhatsApp derivado.
        _render_datos(cid, cli)

        # ── Asignar a un ejecutivo (dispara la notificación a ese ejecutivo) ──
        # SOLO root/admin (re)asignan; el ejecutivo ve su ficha pero no reasigna.
        if st.session_state.get("rol_usuario") in ("root", "admin"):
            st.markdown(_zsec("Asignación de ejecutivo", _ZIC_ASIGNAR), unsafe_allow_html=True)
            _render_asignar(cid, cli)

        # "Enviar correo" abre el compositor (Resend); "Nueva actividad" abre el
        # formulario para agendar. El cierre del drawer va por su X / clic fuera /
        # Escape (con animación de salida).
        st.markdown(_zsec("Correos y actividades", _ZIC_CORREO), unsafe_allow_html=True)
        a1, a2 = st.columns(2)
        with a1:
            if st.button("Enviar correo", icon=":material/mail:", use_container_width=True,
                         key="_cli_fh_mail"):
                st.session_state["_cli_mail_open"] = not st.session_state.get("_cli_mail_open", False)
                st.session_state.pop("_cli_act_open", None)
                st.rerun(scope="fragment")
        with a2:
            if st.button("Nueva actividad", icon=":material/add_task:", use_container_width=True,
                         key="_cli_fh_act"):
                st.session_state["_cli_act_open"] = not st.session_state.get("_cli_act_open", False)
                st.session_state.pop("_cli_mail_open", None)
                st.rerun(scope="fragment")

        # ── Compositor de correo (Resend) ──
        if st.session_state.get("_cli_mail_open"):
            _render_correo(cid, cli)

        # ── Correos enviados (seguimiento: estado/entregado/click/rebote) ──
        _render_correos_enviados(cid, cli)

        # ── Formulario de nueva actividad ──
        # LLAMADA: el "Estado de la llamada" decide el flujo:
        #   · Registrar una llamada YA hecha (Contestó→guión / No contestó… / No
        #     interesado): NO pide fecha/hora/título; queda con la hora actual.
        #   · Programar recordatorio de llamada: pide motivo + fecha + hora.
        # REUNIÓN/CORREO/TAREA: se agendan → motivo + fecha + hora.
        if st.session_state.get("_cli_act_open"):
            with st.container(border=True, key="_cli_act_form"):
                _actor = (st.session_state.get("auth_nombre")
                          or st.session_state.get("auth_email", ""))
                st.markdown('<div class="cli-actf-h">Nueva actividad</div>', unsafe_allow_html=True)
                _tipo = st.radio("Tipo", _ACT_TIPOS, key="_cli_act_tipo", horizontal=True,
                                 format_func=lambda t: f"{_ACT_MAT.get(t, '')} {_ACT_META[t][0]}")

                if _tipo == "llamada":
                    _CALL_ESTADOS = {
                        "Contestó — calificar": "contesto",
                        "No contestó": "no_contesto",
                        "Se cortó la llamada": "se_corto",
                        "Llamar más tarde": "llamar_tarde",
                        "No interesado": "no_interesado",
                        "Programar recordatorio de llamada": "__prog__",
                    }
                    _estado = st.selectbox("Estado de la llamada", list(_CALL_ESTADOS.keys()),
                                           key="_cli_actnew_estado")
                    _code = _CALL_ESTADOS[_estado]
                    st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)

                    if _code == "__prog__":
                        # Recordatorio: motivo + fecha + hora.
                        st.markdown('<div class="cli-actf-hint">Programa la próxima llamada. Se '
                                    'te avisará por la campana y por Telegram.</div>',
                                    unsafe_allow_html=True)
                        _mot = st.text_input("Motivo del recordatorio", key="_cli_act_titulo",
                                             placeholder="Ej: Llamar para cerrar el presupuesto")
                        pc1, pc2 = st.columns(2)
                        with pc1:
                            _af = st.date_input("Fecha", value=_date.today(),
                                                min_value=_date.today(), key="_cli_act_fecha")
                        with pc2:
                            _ah = st.time_input("Hora", value=_default_hora(), key="_cli_act_hora")
                        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
                        if st.button("Agendar recordatorio", type="primary",
                                     use_container_width=True, key="_cli_act_save"):
                            if not (_mot or "").strip():
                                st.warning("Escribe el motivo del recordatorio.")
                            else:
                                _vence = _mk_vence(_af, _ah)
                                _tid, _terr = crear_tarea(cid, _mot.strip(), _vence,
                                                          cli.get("asignado_email", ""), tipo="llamada")
                                if _tid:
                                    registrar_actividad(cid, "nota", f"Llamada agendada: {_mot.strip()}",
                                                        detalle=_fmt_fecha_local(_vence), actor=_actor)
                                    _n = notificar_recordatorio(cli.get("nombre", "Cliente"),
                                                                f"Llamada: {_mot.strip()}",
                                                                _fmt_fecha_local(_vence),
                                                                cli.get("asignado_email", ""))
                                    _crear_notif(_notif_dest(cli),
                                                 f"Llamada · {cli.get('nombre','Cliente')}: {_mot.strip()}",
                                                 tipo="llamada", detalle=_fmt_fecha_local(_vence), cliente_id=cid)
                                    st.session_state.pop("_cli_act_open", None)
                                    st.toast("Recordatorio agendado" + (" · avisado por Telegram" if _n else ""))
                                    st.rerun(scope="fragment")
                                else:
                                    st.error(f"No se pudo guardar: {_terr}")
                    else:
                        # Registrar una llamada YA realizada (queda con la hora actual).
                        _cal_vals, _cal_pregs, _reint = None, [], None
                        if _code == "contesto":
                            st.markdown('<div class="cli-actf-hint">Responde el guión con lo que '
                                        'capturaste en la llamada.</div>', unsafe_allow_html=True)
                            _cal_vals, _cal_pregs = _guion_inputs(cli, f"_actnewq_{cid}")
                            if not _cal_pregs:
                                st.info("Aún no hay preguntas configuradas. El admin puede crearlas "
                                        "con el botón «Guión».")
                        elif _code in ("no_contesto", "se_corto", "llamar_tarde"):
                            _reint = st.selectbox("¿Volver a llamar?",
                                                  ["No reagendar", "En 1 hora", "En 2 horas", "Mañana"],
                                                  key="_cli_actnew_reint")
                        else:  # no_interesado
                            st.markdown('<div class="cli-actf-hint">Se marcará la llamada como '
                                        '«no interesado».</div>', unsafe_allow_html=True)
                        st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
                        if st.button("Registrar llamada", type="primary",
                                     use_container_width=True, key="_cli_act_save"):
                            _lbl = _RESULT_META[_code][0]
                            _tid, _terr = crear_tarea(cid, f"Llamada — {_lbl.lower()}",
                                                      _ahora_scl().isoformat(),
                                                      cli.get("asignado_email", ""), tipo="llamada")
                            if not _tid:
                                st.error(f"No se pudo guardar: {_terr}")
                            else:
                                if _code == "contesto":
                                    _guardar_contesto(cid, cli, _tid, _cal_vals, _cal_pregs, _actor)
                                elif _code == "no_interesado":
                                    completar_tarea(_tid, True, "no_interesado")
                                    registrar_actividad(cid, "llamada", "Llamada — no interesado",
                                                        actor=_actor)
                                else:  # no_contesto / se_corto / llamar_tarde
                                    completar_tarea(_tid, True, _code)
                                    registrar_actividad(cid, "llamada", f"Llamada — {_lbl.lower()}",
                                                        actor=_actor)
                                    _mp = {"En 1 hora": "1h", "En 2 horas": "2h", "Mañana": "manana"}
                                    if _reint in _mp:
                                        _crear_reintento(cid, cli, "", _actor, _mp[_reint])
                                st.session_state.pop("_cli_act_open", None)
                                st.toast("Llamada registrada")
                                st.rerun(scope="fragment")
                else:
                    # Reunión / Correo / Tarea → se agendan (motivo + fecha + hora).
                    _at = st.text_input("Motivo / descripción", key="_cli_act_titulo",
                                        placeholder="Ej: Reunión en oficina para ver el proyecto")
                    gc1, gc2 = st.columns(2)
                    with gc1:
                        _af = st.date_input("Fecha", value=_date.today(),
                                            min_value=_date.today(), key="_cli_act_fecha")
                    with gc2:
                        _ah = st.time_input("Hora", value=_default_hora(), key="_cli_act_hora")
                    st.markdown('<div class="cli-actf-sep"></div>', unsafe_allow_html=True)
                    if st.button("Agendar actividad", type="primary", use_container_width=True,
                                 key="_cli_act_save"):
                        if not (_at or "").strip():
                            st.warning("Escribe el motivo o la descripción.")
                        else:
                            _vence = _mk_vence(_af, _ah)
                            _tid, _terr = crear_tarea(cid, _at.strip(), _vence,
                                                      cli.get("asignado_email", ""), tipo=_tipo)
                            if _tid:
                                _tl = _ACT_META[_tipo][0]
                                registrar_actividad(cid, "nota", f"{_tl} agendada: {_at.strip()}",
                                                    detalle=_fmt_fecha_local(_vence), actor=_actor)
                                _n = notificar_recordatorio(cli.get("nombre", "Cliente"),
                                                            f"{_tl}: {_at.strip()}",
                                                            _fmt_fecha_local(_vence),
                                                            cli.get("asignado_email", ""))
                                _crear_notif(_notif_dest(cli),
                                             f"{_tl} · {cli.get('nombre','Cliente')}: {_at.strip()}",
                                             tipo=_tipo, detalle=_fmt_fecha_local(_vence), cliente_id=cid)
                                st.session_state.pop("_cli_act_open", None)
                                st.toast("Actividad agendada" + (" · avisado por Telegram" if _n else ""))
                                st.rerun(scope="fragment")
                            else:
                                st.error(f"No se pudo guardar: {_terr}")

        # ── Lista de actividades (pendientes primero) ──
        _tareas = listar_tareas_cliente(cid)
        _pend = [t for t in _tareas if not t.get("hecho")]
        st.markdown(_zsec("Actividades pendientes", _ZIC_ACTIV, badge=len(_pend)),
                    unsafe_allow_html=True)
        if not _tareas:
            st.markdown('<div style="font-size:0.8rem;color:#94a3b8;padding:4px 0 8px;">'
                        'Sin actividades. Pulsa <b>Nueva actividad</b> para agendar una.</div>',
                        unsafe_allow_html=True)
        else:
            for t in _tareas:
                _render_actividad(cid, cli, t)

        # ── Calificación (guión) — antes de los datos de Shopify ──
        _render_calificacion(cid, cli)

        # ── Datos del formulario de Shopify (si el lead vino de ahí) ──
        _render_shopify_datos(cli)

        # Presupuestos del cliente (derivados de cotizaciones). El botón "Crear
        # presupuesto" va en la MISMA fila que el encabezado (a la derecha).
        _cots = cli.get("_cotizaciones") or []
        st.markdown(_zline(), unsafe_allow_html=True)
        _pc1, _pc2 = st.columns([3, 2], vertical_alignment="center")
        with _pc1:
            st.markdown(_zsec_hd("Presupuestos", _ZIC_PRESUP, badge=len(_cots)), unsafe_allow_html=True)
        with _pc2:
            # Crea un presupuesto NUEVO para este cliente con los datos ya cargados
            # (navega al editor). st.rerun() completo → cierra el drawer y va al editor.
            if st.button("Crear presupuesto", icon=":material/note_add:", type="primary",
                         use_container_width=True, key="_cli_fh_nuevo"):
                _iniciar_presupuesto(cli)
                st.rerun()
        if _cots:
            _eprows = ""
            for c in _cots:
                _cst = c.get("stage") or ""
                _cl, _cd, _cbg, _cfg = _STAGE_META.get(_cst, _STAGE_META[STAGE_PRESUPUESTO])
                _epn = c.get("numero", "")
                _eprows += (
                    '<div class="cli-ep-row">'
                    f'<div><span class="cli-ep-n cli-copy" data-copy="{_esc(_epn)}" title="Copiar EP">{_esc(_epn)}</span> '
                    f'<span class="cli-pill" style="background:{_cbg};color:{_cfg};margin-left:6px;">{_cl}</span></div>'
                    f'<div class="cli-ep-m">{_fmt_money(c.get("total"))}</div>'
                    '</div>')
            st.markdown('<div style="border:1px solid #e6e9f4;border-radius:12px;overflow:hidden;">'
                        + _eprows + '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="cli-empty-ph" style="padding:20px;">Este cliente aún no tiene presupuestos.</div>',
                        unsafe_allow_html=True)

        # Historial: línea de tiempo COMBINADA para que nunca esté vacía y muestre
        # SIEMPRE cuándo empezó todo (con fecha/hora): la creación del lead + cada
        # presupuesto como hito + las actividades registradas (crm_actividad).
        _acts = listar_actividad(cid)
        st.markdown(_zsec("Historial", _ZIC_HIST), unsafe_allow_html=True)
        _eventos = []
        # "Lead creado" anclado al evento MÁS ANTIGUO (creación del CRM o el primer
        # presupuesto, lo que sea más viejo) → siempre queda como el origen del
        # timeline, incluso en leads importados cuyo presupuesto es anterior al alta.
        _fechas_ini = [cli.get("fecha_creacion")] + [
            _co.get("fecha") for _co in (cli.get("_cotizaciones") or [])]
        _fechas_ini = [f for f in _fechas_ini if f]
        if _fechas_ini:
            _eventos.append({"tipo": "lead", "titulo": "Lead creado",
                             "detalle": f"Origen: {_fuente_norm(cli.get('origen'))}",
                             "fecha": min(_fechas_ini), "actor": "sistema"})
        for _co in (cli.get("_cotizaciones") or []):   # cada presupuesto = un hito
            if _co.get("fecha"):
                _eventos.append({
                    "tipo": "presupuesto",
                    "titulo": f"Presupuesto {_co.get('numero', '') or ''}".strip(),
                    "detalle": f"{_co.get('estado', '')} · {_fmt_money(_co.get('total'))}",
                    "fecha": _co.get("fecha"), "actor": "sistema"})
        for a in _acts:                       # actividades ya registradas
            _eventos.append({"tipo": a.get("tipo"), "titulo": a.get("titulo", ""),
                             "detalle": a.get("detalle", ""), "fecha": a.get("fecha"),
                             "actor": a.get("actor", "") or "sistema"})
        _eventos.sort(key=lambda e: str(e.get("fecha") or ""), reverse=True)  # reciente arriba
        if _eventos:
            _TL_ICON = {"correo": "#5b7cfa", "presupuesto": "#7F77DD", "nota": "#94a3b8",
                        "etapa": "#EF9F27", "lead": "#888780", "llamada": "#1D9E75"}
            _tl = ""
            for a in _eventos:
                _c = _TL_ICON.get(str(a.get("tipo") or ""), "#94a3b8")
                _fecha = _fmt_fecha_local(a.get("fecha"))
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

def _render_agregar_dialog(rol="root", user_email=""):
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
                for c in _cli_data(rol, user_email):
                    if dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), _pol) == k:
                        st.warning(f"Ya existe un cliente con esa identidad: "
                                   f"{c.get('nombre','')}. No se creó un duplicado.")
                        return
            _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
            # El ejecutivo se auto-asigna el cliente que crea (así lo ve); root/admin
            # lo dejan sin asignar para asignarlo luego desde la ficha.
            _payload = {
                "nombre": nombre.strip(), "rut": (rut or "").strip(),
                "email": (email or "").strip(), "telefono": (telefono or "").strip(),
                "tipo": tipo, "empresa": (empresa or "").strip(),
                "rut_empresa": (rut_empresa or "").strip(),
                "direccion": (direccion or "").strip(), "comuna": (comuna or "").strip(),
                "origen": "Manual", "etapa_manual": "lead_nuevo",
            }
            if rol == "ejecutivo":
                _payload["asignado_email"] = (user_email or "").strip()
                _payload["asignado_nombre"] = st.session_state.get("auth_nombre", "") or ""
            cid, err = crear_cliente(_payload)
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
    _email = st.session_state.get("auth_email", "")
    _es_gestor = _rol in ("root", "admin")   # ven todo + pueden sincronizar/asignar
    # DOBLE LLAVE: solo root / admin / ejecutivo (operación no tiene CRM).
    if _rol not in ("root", "admin", "ejecutivo"):
        render_page_header("clientes", "Mis Clientes CRM", "CRM")
        st.warning("Esta sección no está disponible para tu rol.")
        return

    _sub = ("CRM · todos los clientes" if _es_gestor
            else "CRM · mis clientes asignados")
    render_page_header("clientes", "Mis Clientes CRM", _sub)
    st.markdown(_CLI_CSS, unsafe_allow_html=True)

    _t = st.session_state.pop("_cli_toast", None)
    if _t:
        st.toast(_t)

    data = _cli_data(_rol, _email)
    # Lead Score por cliente (potencial según completitud). Se adjunta acá para que
    # tarjetas / maestro / filtros / ficha lean el MISMO valor.
    _pregs_score = _preguntas_data()
    for _d in data:
        _d["_score"] = _lead_score(_d, _pregs_score)

    # Registrar transiciones de ETAPA en el timeline + mantener el reloj SLA (lazy,
    # gateado, best-effort → no frena el render).
    try:
        _sincronizar_etapas(data)
    except Exception:
        pass

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
                # ficha nueva → formularios/paneles (actividad, correo, edición) cerrados
                st.session_state.pop("_cli_act_open", None)
                st.session_state.pop("_cli_act_res", None)
                st.session_state.pop("_cli_mail_open", None)
                st.session_state.pop("_cli_edit", None)
            elif _p[0] == "nuevo" and len(_p) >= 3:
                # Crear presupuesto para este cliente (menú contextual pipeline/maestro).
                _cobj = next((d for d in data if str(d.get("id")) == _p[1]), None)
                if _cobj:
                    _iniciar_presupuesto(_cobj)
                    st.rerun()

    # Puente de asignación (dropdown con foto de la ficha). "cid|email|ts". Solo
    # root/admin. Muta el cliente en `data` y mantiene la ficha abierta (setea
    # _cli_ficha); NO hace rerun extra: la ficha se renderiza al final de este run.
    st.markdown('<style>.st-key-_cli_asigcmd{position:absolute!important;left:-9999px!important;'
                'top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}</style>',
                unsafe_allow_html=True)
    st.text_input("asigcmd", key="_cli_asigcmd", label_visibility="collapsed")
    _acmd = str(st.session_state.get("_cli_asigcmd", "") or "")
    if _es_gestor and _acmd and "|" in _acmd:
        _apar = _acmd.split("|")
        if _apar[-1] != st.session_state.get("_cli_asigcmd_ts") and len(_apar) >= 3:
            st.session_state["_cli_asigcmd_ts"] = _apar[-1]
            _acid, _aem = _apar[0], _apar[1]
            _cobj = next((d for d in data if str(d.get("id")) == _acid), None)
            if _cobj:
                _do_asignar(_cobj, _aem)
                _cli_data.clear()
                st.session_state["_cli_ficha"] = _acid   # mantener la ficha abierta

    # Puente de los dropdowns (custom) de la campaña → selección del segmento. Vive en
    # el flujo principal (FUERA del @st.dialog, si no NO commitea). El dropdown del
    # diálogo escribe 'tier|ej|st|fu|ts'; aquí se parsea y se re-abre la campaña.
    st.markdown('<style>.st-key-_camp_segcmd{position:absolute!important;left:-9999px!important;'
                'top:-9999px!important;height:0!important;width:0!important;overflow:hidden!important;}</style>',
                unsafe_allow_html=True)
    st.text_input("segcmd", key="_camp_segcmd", label_visibility="collapsed")
    _scmd = str(st.session_state.get("_camp_segcmd", "") or "")
    if _es_gestor and _scmd.count("|") >= 4:
        _sp = _scmd.split("|")
        if _sp[-1] != st.session_state.get("_camp_segcmd_ts"):
            st.session_state["_camp_segcmd_ts"] = _sp[-1]
            st.session_state["_camp_sel"] = {"tier": _sp[0], "ej": _sp[1],
                                             "st": _sp[2], "fu": _sp[3]}
            st.session_state["_camp_open"] = True   # re-render la campaña con lo elegido

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

    # KPIs por etapa (con datos reales) — se arman aparte para ir a la DERECHA de
    # los botones, en la misma fila.
    _cnt = {s: 0 for s in _STAGE_ORDER}
    for d in data:
        _cnt[d.get("_stage") or STAGE_LEAD] = _cnt.get(d.get("_stage") or STAGE_LEAD, 0) + 1
    _kpi_html = (
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;">'
        + _kpi("Total clientes", len(data))
        + _kpi("En presupuesto", _cnt[STAGE_PRESUPUESTO], "#6d28d9")
        + _kpi("Propuesta enviada", _cnt[STAGE_PROPUESTA], "#b45309")
        + _kpi("Ganados", _cnt[STAGE_GANADO], "#15803d")
        + _kpi("Perdidos", _cnt[STAGE_PERDIDO], "#94a3b8")
        + _kpi("Recordatorios", len(_pend_tareas), "#dc2626" if _venc_hoy else "#0f172a")
        + '</div>')

    def _add_btn():
        if st.button("Agregar", icon=":material/person_add:", type="primary",
                     use_container_width=True, key="_cli_add_btn"):
            st.session_state["_cli_add_open"] = True
            st.session_state["_cli_just_opened"] = True

    # KPI cards (fila propia).
    st.markdown('<div style="margin-top:4px;">' + _kpi_html + '</div>', unsafe_allow_html=True)

    # Aviso de posibles duplicados (root/admin): solo texto; el botón «Fusionar» va
    # en la barra de acciones (a la derecha de las pestañas).
    if _es_gestor:
        _dupmap = {}
        for _d in data:
            _nk = " ".join(str(_d.get("nombre") or "").strip().lower().split())
            if _nk:
                _dupmap.setdefault(_nk, 0)
                _dupmap[_nk] += 1
        _ndup = sum(1 for _n2 in _dupmap.values() if _n2 >= 2)
        if _ndup:
            st.warning(f"Hay {_ndup} grupo(s) de fichas con el mismo nombre (posibles duplicados). "
                       "Usa «Fusionar», arriba a la derecha.")

    # Fila ÚNICA: pestañas (izquierda) + barra de acciones (derecha). Los iconos
    # abren cada diálogo (sincronizar / guión / importar / campaña / fusionar) y
    # «Agregar» crea una ficha.
    st.markdown('<div style="height:16px;"></div>', unsafe_allow_html=True)
    st.markdown(_CLI_SELECTOR_CSS, unsafe_allow_html=True)
    _views = ["Pipeline", "Bandeja", "Maestro"]
    _icons = {"Pipeline": ":material/view_kanban:", "Bandeja": ":material/inbox:",
              "Maestro": ":material/table_rows:"}
    if _es_gestor:
        _c_tabs, _c_sync, _c_guion, _c_imp, _c_camp, _c_firma, _c_merge, _c_add = st.columns(
            [6, 1, 1, 1, 1, 1, 1, 2], vertical_alignment="center")
    else:
        _c_tabs, _c_add = st.columns([9, 2], vertical_alignment="center")
    with _c_tabs:
        _view = st.radio("Vista", _views, index=0, key="_cli_view", horizontal=True,
                         label_visibility="collapsed",
                         format_func=lambda v: f"{_icons.get(v,'')} {v}")
    if _es_gestor:
        with _c_sync:
            if st.button("", icon=":material/sync:", use_container_width=True,
                         key="_cli_sync", help="Sincronizar con cotizaciones"):
                with st.spinner("Sincronizando…"):
                    res = backfill_desde_cotizaciones()
                _cli_data.clear()
                _est = res.get("estampados", 0)
                st.session_state["_cli_toast"] = (
                    f"Sincronizado: {res['creados']} nuevo(s), {res['existentes']} ya estaban"
                    + (f" · {_est} presupuesto(s) vinculado(s)" if _est else "") + ".")
                st.rerun()
        with _c_guion:
            if st.button("", icon=":material/fact_check:", use_container_width=True,
                         key="_cli_guion", help="Configurar guión de calificación"):
                st.session_state["_guion_open"] = True
                st.session_state["_cli_just_opened"] = True
                st.session_state.pop("_cli_ficha", None)
                st.rerun()
        with _c_imp:
            if st.button("", icon=":material/upload_file:", use_container_width=True,
                         key="_cli_import", help="Importar leads desde CSV / Excel"):
                for _k in [k for k in st.session_state if str(k).startswith("_imp_")]:
                    st.session_state.pop(_k, None)
                st.session_state["_import_open"] = True
                st.session_state["_cli_just_opened"] = True
                st.session_state.pop("_cli_ficha", None)
                st.session_state.pop("_guion_open", None)
                st.rerun()
        with _c_camp:
            if st.button("", icon=":material/campaign:", use_container_width=True,
                         key="_cli_camp", help="Enviar campaña de correo por segmento"):
                st.session_state["_camp_open"] = True
                st.session_state["_cli_just_opened"] = True
                st.session_state.pop("_cli_ficha", None)
                st.session_state.pop("_guion_open", None)
                st.session_state.pop("_import_open", None)
                st.rerun()
        with _c_firma:
            if st.button("", icon=":material/signature:", use_container_width=True,
                         key="_cli_firma_btn", help="Configurar la firma de correo"):
                st.session_state["_firma_open"] = True
                st.session_state["_cli_just_opened"] = True
                st.session_state.pop("_cli_ficha", None)
                st.session_state.pop("_guion_open", None)
                st.session_state.pop("_import_open", None)
                st.rerun()
        with _c_merge:
            if st.button("", icon=":material/merge:", use_container_width=True,
                         key="_cli_dedup_btn", help="Fusionar duplicados"):
                st.session_state["_dedup_open"] = True
                st.session_state["_cli_just_opened"] = True
                st.session_state.pop("_cli_ficha", None)
                st.session_state.pop("_guion_open", None)
                st.session_state.pop("_import_open", None)
                st.rerun()
        with _c_add:
            _add_btn()
    else:
        with _c_add:
            _add_btn()

    # Buscador GLOBAL (todas las vistas, siempre visible): filtra al instante las
    # tarjetas del Pipeline/Bandeja y las filas del Maestro (client-side, sin reruns).
    st.markdown(
        '<div class="cli-sbar"><span class="cli-sico">'
        + _svg('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', 16, "currentColor")
        + '</span><input id="_cli_q" type="text" autocomplete="off" '
        'placeholder="Buscar cliente por nombre, RUT, correo, teléfono o ejecutivo…"></div>',
        unsafe_allow_html=True)

    # Filtros rápidos (badges por ejecutivo/estado) — solo root/admin, en Pipeline
    # y Maestro. Client-side (ver _CLI_FILTER_JS): no disparan reruns.
    if _es_gestor and _view in ("Pipeline", "Maestro"):
        st.markdown(_build_filter_bar(data), unsafe_allow_html=True)

    if _view == "Maestro":
        _render_maestro(data)
    elif _view == "Bandeja":
        _render_bandeja(data)
    else:
        _render_pipeline(data)

    # Handler de click (abre ficha) + menú contextual + filtros/búsqueda + salida.
    components.html(_CLI_CLICK_JS + _CLI_CTXMENU_JS + _CLI_FILTER_JS + _CLI_ASIG_JS + _CLI_COPY_JS
                    + _SLA_TICK_JS, height=0)
    components.html(_CLI_DRAWER_JS, height=0)

    # Drawer: base siempre; entrada SOLO al abrir desde cerrado, reposo en los
    # reruns con el drawer abierto (neutraliza el translateY(20) por defecto).
    st.markdown(_CLI_DRAWER_CSS, unsafe_allow_html=True)
    st.markdown(_CLI_DRAWER_ANIM_CSS if st.session_state.pop("_cli_just_opened", False)
                else _CLI_DRAWER_STILL_CSS, unsafe_allow_html=True)

    # Diálogos: un solo st.dialog a la vez. Guión e Importar (gestores) tienen
    # prioridad sobre la ficha. One-shot: se cierran al hacer rerun completo.
    if st.session_state.pop("_guion_open", False) and _es_gestor:
        _render_guion_config()
    elif st.session_state.pop("_import_open", False) and _es_gestor:
        _render_importar_dialog()
    elif st.session_state.pop("_dedup_open", False) and _es_gestor:
        _render_dedup_dialog(data)
    elif st.session_state.pop("_firma_open", False) and _es_gestor:
        _render_firma_dialog(data)
    elif st.session_state.pop("_camp_open", False) and _es_gestor:
        _render_campana_dialog(data)
    else:
        # Ficha 360 (one-shot: pop del flag; el dialog persiste vía su fragment).
        _fid = st.session_state.pop("_cli_ficha", None)
        if _fid:
            _render_ficha(_fid, data)

    # Diálogo de alta (one-shot). El ejecutivo lo crea auto-asignado a sí mismo.
    if st.session_state.get("_cli_add_open"):
        st.session_state.pop("_cli_add_open", None)
        _render_agregar_dialog(_rol, _email)
