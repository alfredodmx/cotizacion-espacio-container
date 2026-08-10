"""
Tab SISTEMA — Estado del sistema (solo root).

Rediseño 2026: 4 bloques → (1) Capacidad Supabase al día (BD/storage/egress/MAU
con TODAS las tablas y buckets actuales), (2) Resumen de datos del sistema,
(3) Estado de integraciones (Telegram/Resend/Shopify/Backup/Seguridad/IA),
(4) Info de la app / build. Diseño limpio con iconos SVG y la tipografía de
títulos unificada. Lecturas DEFENSIVAS y cacheadas (nunca tumban la pestaña).
"""
import os
import sys
import datetime as _dt
import streamlit as st

from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from views.layout import render_page_header

_APP_VERSION = "2026.08"
_TZ_CL = _dt.timezone(_dt.timedelta(hours=-3))

# ── Iconos SVG (Lucide, stroke) ──────────────────────────────────────────────
_IC = {
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
    "box":      '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "upload":   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "zap":      '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "users":    '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "grid":     '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    "plug":     '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "info":     '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "file":     '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    "cart":     '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "mail":     '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "bell":     '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "send":     '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    "store":    '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M12 2v5"/>',
    "shield":   '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "save":     '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    "sparkles": '<path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .962 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.962 0z"/>',
    "clock":    '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "server":   '<rect width="20" height="8" x="2" y="2" rx="2"/><rect width="20" height="8" x="2" y="14" rx="2"/><line x1="6" x2="6.01" y1="6" y2="6"/><line x1="6" x2="6.01" y1="18" y2="18"/>',
    "refresh":  '<path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/><path d="M8 16H3v5"/>',
    "check":    '<path d="M20 6 9 17l-5-5"/>',
}


def _svg(key, size=16, color="currentColor", sw=2, mr=0, valign=-2):
    style = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        style += f"margin-right:{mr}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{style}">{_IC.get(key, "")}</svg>')


# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
<style>
.sysx-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;line-height:1.4;padding-bottom:8px;
  border-bottom:2px solid #e2e8f0;margin:26px 0 16px;display:flex;align-items:center;gap:9px;}
.sysx-sec svg{color:#0f172a;}
.sysx-card{background:#fff;border:1px solid #e8ebf3;border-radius:14px;padding:18px 20px;
  box-shadow:0 1px 3px rgba(15,23,42,.05);height:100%;box-sizing:border-box;}
.sysx-klab{font-size:0.66rem;font-weight:800;color:#94a3b8;text-transform:uppercase;
  letter-spacing:.09em;display:flex;align-items:center;gap:6px;margin-bottom:8px;}
.sysx-kval{font-size:1.75rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;line-height:1;}
.sysx-ksub{font-size:0.74rem;color:#64748b;margin-top:5px;}
.sysx-bar{background:#f1f5f9;border-radius:8px;height:9px;overflow:hidden;margin:11px 0 5px;}
.sysx-bar>div{height:9px;border-radius:8px;transition:width .5s ease;}
.sysx-ok>div{background:linear-gradient(90deg,#10b981,#34d399);}
.sysx-warn>div{background:linear-gradient(90deg,#f59e0b,#fbbf24);}
.sysx-crit>div{background:linear-gradient(90deg,#ef4444,#f97316);}
.sysx-pct{font-size:0.72rem;font-weight:700;display:flex;justify-content:space-between;color:#64748b;}
.sysx-badge{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:20px;
  font-weight:800;font-size:0.64rem;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;}
.sysx-b-ok{background:#dcfce7;color:#15803d;}
.sysx-b-warn{background:#fef3c7;color:#b45309;}
.sysx-b-crit{background:#fee2e2;color:#dc2626;}
.sysx-b-off{background:#f1f5f9;color:#64748b;}
.sysx-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:12px;}
.sysx-mini{background:#fff;border:1px solid #e8ebf3;border-radius:12px;padding:13px 15px;}
.sysx-mini .n{font-size:1.5rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;line-height:1;}
.sysx-mini .l{font-size:0.68rem;color:#64748b;margin-top:4px;display:flex;align-items:center;gap:5px;font-weight:600;}
.sysx-tbl{width:100%;border-collapse:collapse;font-size:0.8rem;}
.sysx-tbl th{background:#f8fafc;color:#64748b;font-weight:700;font-size:0.64rem;text-transform:uppercase;
  letter-spacing:.06em;padding:9px 13px;text-align:left;border-bottom:2px solid #eef2f7;}
.sysx-tbl td{padding:8px 13px;border-bottom:1px solid #f4f6fb;color:#1e293b;}
.sysx-tbl tr:last-child td{border-bottom:none;}
.sysx-tbl td.r{text-align:right;font-variant-numeric:tabular-nums;font-weight:700;}
.sysx-grp{font-size:0.6rem;font-weight:800;color:#a8b0bd;text-transform:uppercase;letter-spacing:.09em;
  padding:9px 13px 4px;}
.sysx-intg{display:flex;align-items:center;gap:12px;background:#fff;border:1px solid #e8ebf3;
  border-radius:12px;padding:13px 16px;}
.sysx-intg .ico{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.sysx-intg .tt{font-weight:800;font-size:0.86rem;color:#0f172a;}
.sysx-intg .ss{font-size:0.72rem;color:#64748b;margin-top:1px;}
.sysx-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;margin-left:auto;}
.sysx-info-row{display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:0.82rem;}
.sysx-info-row:last-child{border-bottom:none;}
.sysx-info-row .k{color:#64748b;display:flex;align-items:center;gap:7px;}
.sysx-info-row .v{color:#0f172a;font-weight:700;}
</style>
"""


# ── Datos del sistema (cacheado + defensivo) ─────────────────────────────────

_TABLAS = [
    ("Operación", [
        ("cotizaciones", "Cotizaciones"),
        ("cotizacion_logs", "Logs de auditoría"),
        ("registro_compras", "Registro de compras"),
        ("inventario", "Inventario"),
        ("excel_versiones", "Versiones de Excel"),
        ("plantillas_contrato", "Plantillas de contrato"),
    ]),
    ("Formularios y materiales", [
        ("catalogo_materiales", "Catálogo de materiales"),
        ("formulario_config", "Config. de formularios"),
        ("formulario_respuestas", "Respuestas de clientes"),
    ]),
    ("CRM", [
        ("clientes", "Clientes / leads"),
        ("crm_actividad", "Actividad CRM"),
        ("crm_tareas", "Tareas / recordatorios"),
        ("crm_preguntas", "Guion de calificación"),
        ("crm_campanas", "Campañas de correo"),
        ("crm_correos", "Correos enviados"),
        ("crm_firma", "Firmas de correo"),
    ]),
    ("Notificaciones", [
        ("notificaciones", "Feed de notificaciones"),
        ("notificaciones_config", "Config. de Telegram"),
    ]),
]


def _count(tbl):
    try:
        return int(_supa_admin.table(tbl).select("*", count="exact").limit(1).execute().count or 0)
    except Exception:
        return None  # None = tabla no existe / sin acceso


def _count_filtro(tbl, col, val=None, not_null=False):
    try:
        q = _supa_admin.table(tbl).select("*", count="exact").limit(1)
        if not_null:
            q = q.not_.is_(col, "null")
        else:
            q = q.eq(col, val)
        return int(q.execute().count or 0)
    except Exception:
        return 0


@st.cache_data(ttl=90, show_spinner=False)
def _sys_data():
    """Snapshot completo del sistema. Todo DEFENSIVO → nunca lanza."""
    import httpx as _hx

    d = {}

    # DB size (RPC get_db_stats) o estimado por filas
    _db_mb = 0.0
    _db_est = False
    try:
        r = _hx.post(f"{SUPABASE_URL}/rest/v1/rpc/get_db_stats",
                     headers={"apikey": SUPABASE_SERVICE_KEY,
                              "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                              "Content-Type": "application/json"},
                     json={}, timeout=10)
        if r.status_code == 200:
            _db_mb = round(float(r.json()) / (1024 * 1024), 2)
    except Exception:
        pass

    # Conteo de filas por tabla (agrupado)
    tablas = []
    total_filas = 0
    for grupo, items in _TABLAS:
        for tname, tlabel in items:
            c = _count(tname)
            tablas.append({"grupo": grupo, "name": tname, "label": tlabel, "count": c})
            if c:
                total_filas += c
    d["tablas"] = tablas
    d["total_filas"] = total_filas

    if _db_mb == 0 and total_filas > 0:
        _db_mb = round((total_filas * 2048) / (1024 * 1024), 2)
        _db_est = True
    d["db_mb"] = _db_mb
    d["db_est"] = _db_est

    # Storage (estimado por archivos referenciados)
    def _c(tbl, col=None, not_null=False):
        return _count_filtro(tbl, col, not_null=not_null) if col else (_count(tbl) or 0)
    _planos = _c("cotizaciones", "plano_url", True)
    _contr = _c("cotizaciones", "contrato_notariado_url", True)
    _fimg = _c("catalogo_materiales", "imagen_url", True)
    _fact = _c("registro_compras")
    _excel = _c("excel_versiones")
    buckets = [
        {"name": "planos", "arch": _planos, "mb": round(_planos * 500 * 1024 / (1024 * 1024), 2)},
        {"name": "contratos/notariados", "arch": _contr, "mb": round(_contr * 300 * 1024 / (1024 * 1024), 2)},
        {"name": "formulario-imagenes", "arch": _fimg, "mb": round(_fimg * 200 * 1024 / (1024 * 1024), 2)},
        {"name": "facturas", "arch": _fact, "mb": round(_fact * 150 * 1024 / (1024 * 1024), 2)},
        {"name": "config (excel/json)", "arch": _excel, "mb": round(_excel * 2 * 1024 / 1024, 2)},
    ]
    d["buckets"] = buckets
    d["storage_mb"] = round(sum(b["mb"] for b in buckets), 2)

    # Resumen de datos
    d["cot_total"] = _count("cotizaciones") or 0
    d["cot_adj"] = _count_filtro("cotizaciones", "contrato_notariado_url", not_null=True)
    d["cot_term"] = _count_filtro("cotizaciones", "acta_url", not_null=True)
    d["cot_rech"] = _count_filtro("cotizaciones", "motivo_rechazo", not_null=True)
    d["cli_total"] = _count("clientes") or 0
    d["cli_shopify"] = _count_filtro("clientes", "origen", "Shopify")
    d["cli_import"] = _count_filtro("clientes", "origen", "Importado")
    d["compras_total"] = _count("registro_compras") or 0
    d["correos_total"] = _count("crm_correos") or 0
    d["notif_total"] = _count("notificaciones") or 0
    d["inv_total"] = _count("inventario") or 0

    # Actividad reciente (últimos 7 días) en cotizacion_logs
    try:
        _hace7 = (_dt.datetime.now(_TZ_CL) - _dt.timedelta(days=7)).isoformat()
        d["logs_7d"] = int(_supa_admin.table("cotizacion_logs").select("*", count="exact")
                           .gte("fecha", _hace7).limit(1).execute().count or 0)
    except Exception:
        d["logs_7d"] = None

    # Eventos de seguridad (cotizacion_logs numero=SEGURIDAD, últimos 30 días)
    try:
        _hace30 = (_dt.datetime.now(_TZ_CL) - _dt.timedelta(days=30)).isoformat()
        d["seg_30d"] = int(_supa_admin.table("cotizacion_logs").select("*", count="exact")
                           .eq("numero", "SEGURIDAD").gte("fecha", _hace30).limit(1).execute().count or 0)
    except Exception:
        d["seg_30d"] = None

    # Usuarios por rol (auth admin)
    roles = {"root": 0, "admin": 0, "ejecutivo": 0, "operacion": 0}
    _users_total = 0
    try:
        _roots = [x.strip().lower() for x in st.secrets.get("ROOTS", "").split(",") if x.strip()]
        rr = _hx.get(f"{SUPABASE_URL}/auth/v1/admin/users",
                     headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
                     params={"per_page": 1000, "page": 1}, timeout=12)
        if rr.status_code == 200:
            for u in rr.json().get("users", []):
                _users_total += 1
                em = (u.get("email") or "").lower()
                meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
                rol = "root" if em in _roots else meta.get("rol", "ejecutivo")
                if rol in roles:
                    roles[rol] += 1
                else:
                    roles["ejecutivo"] += 1
    except Exception:
        pass
    d["roles"] = roles
    d["users_total"] = _users_total

    # Integraciones (config presente)
    _tg = bool(st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
    try:
        _cfgtok = _supa_admin.table("notificaciones_config").select("valor").eq("clave", "bot_token").execute()
        if _cfgtok.data and _cfgtok.data[0].get("valor"):
            _tg = True
    except Exception:
        pass
    try:
        _contactos = _supa_admin.table("notificaciones_config").select("valor").eq("clave", "contactos_json").execute()
        import json as _j
        _tg_ct = len(_j.loads((_contactos.data or [{}])[0].get("valor") or "{}")) if _contactos.data else 0
    except Exception:
        _tg_ct = 0
    d["intg"] = {
        "telegram": {"on": _tg, "det": (f"{_tg_ct} contacto(s) con Chat ID" if _tg else "Falta el token del bot")},
        "resend": {"on": bool(st.secrets.get("RESEND_API_KEY", "")),
                   "det": (f"{d['correos_total']} correo(s) enviados" if st.secrets.get("RESEND_API_KEY", "") else "Falta RESEND_API_KEY")},
        "shopify": {"on": bool(st.secrets.get("SHOPIFY_STORE", "") and (st.secrets.get("SHOPIFY_TOKEN", "") or st.secrets.get("SHOPIFY_ACCESS_TOKEN", ""))),
                    "det": (f"{d['cli_shopify']} lead(s) desde Shopify" if st.secrets.get("SHOPIFY_STORE", "") else "Falta configurar la tienda")},
        "ia": {"on": bool(st.secrets.get("ANTHROPIC_API_KEY", "")),
               "det": ("Asistente IA disponible" if st.secrets.get("ANTHROPIC_API_KEY", "") else "Falta ANTHROPIC_API_KEY")},
    }

    d["ts"] = _dt.datetime.now(_TZ_CL).strftime("%d/%m/%Y %H:%M")
    return d


# ── Helpers de render ────────────────────────────────────────────────────────

def _sec(title, icon):
    st.markdown(f'<div class="sysx-sec">{_svg(icon, 17)}{title}</div>', unsafe_allow_html=True)


def _bar_cls(pct):
    return "sysx-crit" if pct >= 80 else ("sysx-warn" if pct >= 50 else "sysx-ok")


def _estado_badge(pct):
    if pct >= 100:
        return "sysx-b-crit", "Excedido"
    if pct >= 80:
        return "sysx-b-crit", "Crítico"
    if pct >= 50:
        return "sysx-b-warn", "Atención"
    return "sysx-b-ok", "Normal"


def _cap_card(icon, label, val, sub, pct, show_bar=True):
    _bc, _bl = _estado_badge(pct)
    _bar = (f'<div class="sysx-bar {_bar_cls(pct)}"><div style="width:{min(pct,100)}%"></div></div>'
            f'<div class="sysx-pct"><span>{pct}% usado</span><span class="sysx-badge {_bc}">{_bl}</span></div>'
            if show_bar else '')
    return (f'<div class="sysx-card"><div class="sysx-klab">{_svg(icon, 13, "#5b7cfa", mr=0)}{label}</div>'
            f'<div class="sysx-kval">{val}</div><div class="sysx-ksub">{sub}</div>{_bar}</div>')


def _mini(icon, n, label, color="#5b7cfa"):
    return (f'<div class="sysx-mini"><div class="n">{n}</div>'
            f'<div class="l">{_svg(icon, 12, color, mr=0)}{label}</div></div>')


# ── Render principal ─────────────────────────────────────────────────────────

def render_tab_salud(supabase, supabase_admin, supa_url, supa_key, **deps):
    if not st.session_state.get('es_root'):
        st.info("Solo el root puede ver el estado del sistema.", icon=":material/lock:")
        return

    st.markdown(_CSS, unsafe_allow_html=True)
    render_page_header(
        "sistema",
        "Estado del Sistema",
        "Capacidad, datos, integraciones y build &#8212; monitoreo del sistema completo.",
    )

    with st.spinner("Consultando el estado del sistema..."):
        D = _sys_data()

    # Límites del plan
    _LIM = {"db": 500, "stg": 1024, "eg": 5.0, "egc": 5.0, "mau": 50000}
    _eg = float(st.session_state.get('_sys_egress_gb', 0.0))
    _egc = float(st.session_state.get('_sys_egress_cached_gb', 0.0))
    _mau = int(st.session_state.get('_sys_mau', 0))

    _db_pct = min(round(D["db_mb"] / _LIM["db"] * 100, 1), 100) if D["db_mb"] else 0
    _stg_pct = min(round(D["storage_mb"] / _LIM["stg"] * 100, 1), 100)
    _eg_pct = min(round(_eg / _LIM["eg"] * 100, 1), 200) if _eg else 0
    _egc_pct = min(round(_egc / _LIM["egc"] * 100, 1), 200) if _egc else 0
    _mau_pct = min(round(_mau / _LIM["mau"] * 100, 1), 100) if _mau else 0

    # Salud general
    _worst = max(_db_pct, _stg_pct, _eg_pct, _egc_pct)
    if _worst >= 100:
        _health = ("#dc2626", "Crítico", "Un límite del plan fue excedido")
    elif _worst >= 80:
        _health = ("#f59e0b", "Atención", "Un recurso está cerca del límite")
    else:
        _health = ("#16a34a", "Operativo", "Todos los recursos dentro del plan")

    if _egc and _egc_pct >= 100:
        st.error(f"**Cached Egress excedido:** {_egc} GB / {_LIM['egc']} GB ({_egc_pct:.0f}%). Supabase puede restringir el servicio.")
    elif _egc and _egc_pct >= 80:
        st.warning(f"**Cached Egress casi al límite:** {_egc} GB de {_LIM['egc']} GB ({_egc_pct:.0f}%).")

    # ── Tira de salud general (4 KPIs) ──
    _c1, _c2, _c3, _c4 = st.columns(4)
    with _c1:
        st.markdown(
            f'<div class="sysx-card" style="border-left:4px solid {_health[0]};">'
            f'<div class="sysx-klab">{_svg("activity", 13, _health[0], mr=0)}Salud general</div>'
            f'<div class="sysx-kval" style="color:{_health[0]};">{_health[1]}</div>'
            f'<div class="sysx-ksub">{_health[2]}</div></div>', unsafe_allow_html=True)
    with _c2:
        st.markdown(_cap_card("database", "Base de datos", f'{D["db_mb"]} MB',
                              f'de {_LIM["db"]} MB' + (' · estimado' if D["db_est"] else ''), _db_pct), unsafe_allow_html=True)
    with _c3:
        st.markdown(_cap_card("box", "Storage", f'{round(D["storage_mb"],1)} MB',
                              f'de {_LIM["stg"]} MB (1 GB) · est.', _stg_pct), unsafe_allow_html=True)
    with _c4:
        st.markdown(_cap_card("users", "Usuarios", f'{D["users_total"]}',
                              f'{D["roles"]["ejecutivo"]} ejecutivos · {D["roles"]["admin"]} admin', 0, show_bar=False),
                    unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # 1. CAPACIDAD SUPABASE
    # ══════════════════════════════════════════════════════════════
    _sec("Capacidad Supabase", "database")
    _e1, _e2, _e3, _e4 = st.columns(4)
    with _e1:
        _egd = f"{_eg} GB" if _eg else "Sin datos"
        st.markdown(_cap_card("upload", "Egress directo", _egd, f'de {_LIM["eg"]} GB/mes', _eg_pct, show_bar=bool(_eg)),
                    unsafe_allow_html=True)
    with _e2:
        _egcd = f"{_egc} GB" if _egc else "Sin datos"
        st.markdown(_cap_card("zap", "Cached Egress", _egcd, f'de {_LIM["egc"]} GB/mes', _egc_pct, show_bar=bool(_egc)),
                    unsafe_allow_html=True)
    with _e3:
        _maud = f"{_mau:,}" if _mau else "Sin datos"
        st.markdown(_cap_card("users", "MAU", _maud, f'de {_LIM["mau"]:,}', _mau_pct, show_bar=bool(_mau)),
                    unsafe_allow_html=True)
    with _e4:
        st.markdown(_cap_card("grid", "Filas totales", f'{D["total_filas"]:,}',
                              f'{len([t for t in D["tablas"] if t["count"] is not None])} tablas activas', 0, show_bar=False),
                    unsafe_allow_html=True)

    with st.expander("Actualizar métricas manuales (Egress / MAU desde Supabase → Usage)", expanded=False):
        _m1, _m2, _m3, _m4 = st.columns([2, 2, 2, 1])
        with _m1:
            _eg_i = st.number_input("Egress (GB)", min_value=0.0, max_value=999.0, step=0.1, value=_eg, key="_inp_egress")
        with _m2:
            _egc_i = st.number_input("Cached Egress (GB)", min_value=0.0, max_value=999.0, step=0.1, value=_egc, key="_inp_egress_cached")
        with _m3:
            _mau_i = st.number_input("MAU", min_value=0, max_value=50000, step=1, value=_mau, key="_inp_mau")
        with _m4:
            st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
            if st.button("Guardar", key="_btn_sys_update", use_container_width=True, type="primary"):
                st.session_state['_sys_egress_gb'] = _eg_i
                st.session_state['_sys_egress_cached_gb'] = _egc_i
                st.session_state['_sys_mau'] = _mau_i
                st.rerun()

    # ══════════════════════════════════════════════════════════════
    # 2. RESUMEN DE DATOS
    # ══════════════════════════════════════════════════════════════
    _sec("Resumen de datos", "activity")
    _minis = (
        _mini("file", f'{D["cot_total"]:,}', "Cotizaciones", "#3b82f6")
        + _mini("check", f'{D["cot_adj"]:,}', "Adjudicadas", "#16a34a")
        + _mini("shield", f'{D["cot_term"]:,}', "Terminadas", "#7c3aed")
        + _mini("info", f'{D["cot_rech"]:,}', "Rechazadas", "#dc2626")
        + _mini("users", f'{D["cli_total"]:,}', "Clientes / leads", "#0ea5e9")
        + _mini("store", f'{D["cli_shopify"]:,}', "Leads Shopify", "#6d28d9")
        + _mini("cart", f'{D["compras_total"]:,}', "Reg. de compras", "#f97316")
        + _mini("box", f'{D["inv_total"]:,}', "Ítems inventario", "#0d9488")
        + _mini("mail", f'{D["correos_total"]:,}', "Correos enviados", "#db2777")
        + _mini("bell", f'{D["notif_total"]:,}', "Notificaciones", "#eab308")
        + _mini("activity", f'{D["logs_7d"] if D["logs_7d"] is not None else "—"}', "Cambios (7 días)", "#5b7cfa")
        + _mini("shield", f'{D["seg_30d"] if D["seg_30d"] is not None else "—"}', "Seguridad (30 días)",
                "#dc2626" if (D["seg_30d"] or 0) else "#16a34a")
    )
    st.markdown(f'<div class="sysx-grid">{_minis}</div>', unsafe_allow_html=True)

    # Usuarios por rol
    _r = D["roles"]
    st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
    _ru = (_mini("shield", _r["root"], "Root", "#7c3aed")
           + _mini("users", _r["admin"], "Admin", "#8b5cf6")
           + _mini("users", _r["ejecutivo"], "Ejecutivos", "#2563eb")
           + _mini("box", _r["operacion"], "Operación", "#b45309"))
    st.markdown(f'<div class="sysx-grid">{_ru}</div>', unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # 3. TABLAS Y BUCKETS
    # ══════════════════════════════════════════════════════════════
    _sec("Tablas y almacenamiento", "grid")
    _tc, _bc2 = st.columns([3, 2])
    with _tc:
        _rows = ""
        _last_grp = None
        for t in D["tablas"]:
            if t["grupo"] != _last_grp:
                _rows += f'<tr><td colspan="2" class="sysx-grp">{t["grupo"]}</td></tr>'
                _last_grp = t["grupo"]
            _cval = f'{t["count"]:,}' if t["count"] is not None else '<span style="color:#cbd5e1;">n/d</span>'
            _rows += f'<tr><td>{t["label"]} <span style="color:#cbd5e1;font-size:.72rem;">{t["name"]}</span></td><td class="r">{_cval}</td></tr>'
        st.markdown(f'<div class="sysx-card" style="padding:0;overflow:hidden;"><table class="sysx-tbl">'
                    f'<thead><tr><th>Tabla</th><th style="text-align:right;">Filas</th></tr></thead>'
                    f'<tbody>{_rows}</tbody></table></div>', unsafe_allow_html=True)
    with _bc2:
        _brows = ""
        for b in D["buckets"]:
            _brows += f'<tr><td>{b["name"]}</td><td class="r">{b["arch"]}</td><td class="r">{b["mb"]} MB</td></tr>'
        st.markdown(f'<div class="sysx-card" style="padding:0;overflow:hidden;"><table class="sysx-tbl">'
                    f'<thead><tr><th>Bucket</th><th style="text-align:right;">Arch.</th><th style="text-align:right;">Tamaño</th></tr></thead>'
                    f'<tbody>{_brows}</tbody></table></div>', unsafe_allow_html=True)
        st.caption("Tamaños de storage estimados por archivos referenciados.")

    # ══════════════════════════════════════════════════════════════
    # 4. INTEGRACIONES
    # ══════════════════════════════════════════════════════════════
    _sec("Estado de integraciones", "plug")
    _intg = D["intg"]

    def _intg_card(icon, nombre, on, det, bg, fg):
        _dot = "#16a34a" if on else "#cbd5e1"
        _bcls, _blbl = ("sysx-b-ok", "Activo") if on else ("sysx-b-off", "Inactivo")
        return (f'<div class="sysx-intg"><div class="ico" style="background:{bg};">{_svg(icon, 19, fg, mr=0)}</div>'
                f'<div style="min-width:0;"><div class="tt">{nombre}</div><div class="ss">{det}</div></div>'
                f'<span class="sysx-badge {_bcls}" style="margin-left:auto;">{_blbl}</span>'
                f'<span class="sysx-dot" style="background:{_dot};"></span></div>')

    _seg_on = (D["seg_30d"] is not None)
    _bkp_det = "Extrae las 9 tablas a un ZIP (bajo la tabla de COTIZACIONES)"
    _ig1, _ig2 = st.columns(2)
    with _ig1:
        st.markdown(_intg_card("send", "Telegram", _intg["telegram"]["on"], _intg["telegram"]["det"], "#e0f2fe", "#0284c7"), unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        st.markdown(_intg_card("mail", "Correo (Resend)", _intg["resend"]["on"], _intg["resend"]["det"], "#fce7f3", "#db2777"), unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        st.markdown(_intg_card("store", "Shopify", _intg["shopify"]["on"], _intg["shopify"]["det"], "#ede9fe", "#6d28d9"), unsafe_allow_html=True)
    with _ig2:
        st.markdown(_intg_card("save", "Backup de la BD", True, _bkp_det, "#dcfce7", "#16a34a"), unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        _seg_txt = (f'{D["seg_30d"]} evento(s) en 30 días' if _seg_on else "Registro de seguridad activo")
        st.markdown(_intg_card("shield", "Seguridad", True, _seg_txt, "#fee2e2", "#dc2626"), unsafe_allow_html=True)
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        st.markdown(_intg_card("sparkles", "Asistente IA", _intg["ia"]["on"], _intg["ia"]["det"], "#f3e8ff", "#9333ea"), unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════
    # 5. INFO DE LA APP
    # ══════════════════════════════════════════════════════════════
    _sec("Información de la app", "info")
    _entorno = "Streamlit Cloud" if ("/mount/src" in os.getcwd() or os.environ.get("HOSTNAME", "").startswith("streamlit")) else "Local / self-host"
    try:
        _st_ver = st.__version__
    except Exception:
        _st_ver = "—"
    _py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    _now = _dt.datetime.now(_TZ_CL)

    _if1, _if2 = st.columns(2)
    with _if1:
        st.markdown(
            '<div class="sysx-card">'
            f'<div class="sysx-info-row"><span class="k">{_svg("info", 13, "#94a3b8", mr=0)}Versión de la app</span><span class="v">{_APP_VERSION}</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("server", 13, "#94a3b8", mr=0)}Entorno</span><span class="v">{_entorno}</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("activity", 13, "#94a3b8", mr=0)}Streamlit</span><span class="v">{_st_ver}</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("activity", 13, "#94a3b8", mr=0)}Python</span><span class="v">{_py_ver}</span></div>'
            '</div>', unsafe_allow_html=True)
    with _if2:
        st.markdown(
            '<div class="sysx-card">'
            f'<div class="sysx-info-row"><span class="k">{_svg("clock", 13, "#94a3b8", mr=0)}Hora del servidor</span><span class="v">{_now.strftime("%d/%m/%Y %H:%M")} (Chile)</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("refresh", 13, "#94a3b8", mr=0)}Datos actualizados</span><span class="v">{D["ts"]}</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("database", 13, "#94a3b8", mr=0)}Plan Supabase</span><span class="v">Free (Core)</span></div>'
            f'<div class="sysx-info-row"><span class="k">{_svg("clock", 13, "#94a3b8", mr=0)}Pausa por inactividad</span><span class="v">7 días sin uso</span></div>'
            '</div>', unsafe_allow_html=True)

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    _rc1, _rc2, _rc3 = st.columns([1, 1, 1])
    with _rc2:
        if st.button("Actualizar estado del sistema", key="btn_refresh_salud", use_container_width=True, icon=":material/refresh:"):
            _sys_data.clear()
            st.rerun()
