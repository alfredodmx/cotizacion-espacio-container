"""
Tab REPORTE BI — Inteligencia comercial ejecutiva (para dirección / CEO).

Rediseño 2026: KPIs hero, ranking de ejecutivos con avatar circular + podio,
distribución de los 9 estados reales (mismos colores/iconos que COTIZACIONES),
perfil comercial, tiempos de cierre e insights. Selector de período con rango
personalizado (Desde/Hasta). Iconos SVG (sin emojis) + tipografía de títulos
unificada. Todo cacheado y defensivo.
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from views.layout import render_page_header
from services.cotizacion_service import (
    calcular_estado_label, ESTADO_BADGE_COLORS, ESTADO_BADGE_ICONS)

_ESTADO_ORDER = [
    ('PROYECTO TERMINADO', 'Terminados'), ('ADJUDICADO', 'Adjudicados'),
    ('AUTORIZADO CON PLANO', 'Aut. c/plano'), ('AUTORIZADO', 'Autorizados'),
    ('BORRADOR CON PLANO', 'Borrador c/plano'), ('BORRADOR', 'Borrador'),
    ('INCOMPLETO CON PLANO', 'Incompleto c/plano'), ('INCOMPLETO', 'Incompletos'),
    ('RECHAZADO', 'Rechazados'),
]
_GANADOS = ('ADJUDICADO', 'PROYECTO TERMINADO')
_AUTORIZADOS = ('AUTORIZADO CON PLANO', 'AUTORIZADO')

# ── Iconos SVG (Lucide) ──────────────────────────────────────────────────────
_IC = {
    "chart": '<path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "dollar": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "ticket": '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2Z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "building": '<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M16 10h.01"/><path d="M8 10h.01"/>',
    "map": '<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
    "zap": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "turtle": '<path d="M12 10 2 8"/><path d="m12 10 8-4"/><path d="M12 10v6"/><path d="M12 22a8 8 0 0 0 8-8 8 8 0 0 0-16 0 8 8 0 0 0 8 8Z"/>',
    "hourglass": '<path d="M5 22h14"/><path d="M5 2h14"/><path d="M17 22v-4.172a2 2 0 0 0-.586-1.414L12 12l-4.414 4.414A2 2 0 0 0 7 17.828V22"/><path d="M7 2v4.172a2 2 0 0 0 .586 1.414L12 12l4.414-4.414A2 2 0 0 0 17 6.172V2"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "trending": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "download": '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
    "hand": '<path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
}


def _ic(name, color="#64748b", size=15, mr=7, valign=-2):
    _mr = f"margin-right:{mr}px;" if mr else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:{valign}px;{_mr}flex-shrink:0;">{_IC.get(name, "")}</svg>')


def _estado_svg(estado, color, size=13):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
            f'{ESTADO_BADGE_ICONS.get(estado, "")}</svg>')


def _avatar(nombre, foto, size=42):
    _ini = ''.join(p[0] for p in (nombre or '').split()[:2]).upper() or 'EC'
    _inner = (f'<img src="{foto}" style="width:100%;height:100%;object-fit:cover;display:block;" alt="">'
              if foto else _ini)
    return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;flex-shrink:0;overflow:hidden;'
            f'background:linear-gradient(135deg,#0f3460,#2563eb);color:#fff;display:flex;align-items:center;'
            f'justify-content:center;font-family:Montserrat,sans-serif;font-weight:800;font-size:{int(size*0.36)}px;'
            f'box-shadow:0 3px 10px rgba(15,23,42,.2);">{_inner}</div>')


def _rank_badge(idx, size=26):
    _c = {0: ("#f59e0b", "#fff"), 1: ("#94a3b8", "#fff"), 2: ("#b45309", "#fff")}
    _bg, _fg = _c.get(idx, ("#eef2f7", "#64748b"))
    return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;flex-shrink:0;background:{_bg};color:{_fg};'
            f'display:flex;align-items:center;justify-content:center;font-family:Montserrat,sans-serif;'
            f'font-weight:900;font-size:12px;box-shadow:0 2px 6px rgba(15,23,42,.15);">{idx+1}</div>')


# ── Datos (cacheado + defensivo) ─────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_reporte(periodo='mes', desde='', hasta=''):
    try:
        from datetime import datetime as _dt, timedelta as _td
        _ahora = _dt.now()
        _fin = None
        if periodo == 'mes':
            _ini = _ahora.replace(day=1).strftime('%Y-%m-%d')
        elif periodo == '3meses':
            _ini = (_ahora - _td(days=90)).strftime('%Y-%m-%d')
        elif periodo == '6meses':
            _ini = (_ahora - _td(days=180)).strftime('%Y-%m-%d')
        elif periodo == 'año':
            _ini = _ahora.replace(month=1, day=1).strftime('%Y-%m-%d')
        elif periodo == 'rango':
            _ini = desde or '2000-01-01'
            _fin = hasta or _ahora.strftime('%Y-%m-%d')
        else:
            _ini = '2000-01-01'
        _resp = _supa_admin.table('cotizaciones').select(
            'numero,fecha_creacion,fecha_modificacion,cliente_nombre,cliente_email,cliente_tipo,'
            'cliente_region,cliente_comuna,asesor_nombre,asesor_email,asesor_telefono,estado,total_total,'
            'config_margen,plano_url,contrato_generado,contrato_datos,contrato_notariado_url,'
            'acta_url,motivo_rechazo'
        ).execute()
        _rows = _resp.data or []
        def _f(r):
            return (r.get('fecha_creacion') or r.get('fecha_modificacion') or '')[:10]
        if periodo == 'rango':
            _rows = [r for r in _rows if _ini <= _f(r) <= _fin]
        elif periodo != 'todo':
            _rows = [r for r in _rows if _f(r) >= _ini]
        return _rows
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _reporte_avatars():
    out = {}
    try:
        import httpx as _hx
        r = _hx.get(f"{SUPABASE_URL}/auth/v1/admin/users",
                    headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
                    params={"per_page": 1000, "page": 1}, timeout=12)
        if r.status_code == 200:
            for u in r.json().get("users", []):
                meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
                nm = (meta.get("nombre") or "").strip().lower()
                ft = (meta.get("foto_url") or "").strip()
                if nm and ft:
                    out[nm] = ft
    except Exception:
        pass
    return out


def _estado_de(r):
    return calcular_estado_label(
        r.get('cliente_nombre', ''), r.get('cliente_email', ''),
        r.get('asesor_nombre', ''), r.get('asesor_email', ''), r.get('asesor_telefono', ''),
        float(r.get('config_margen') or 0), bool((r.get('plano_url') or '').strip()),
        tiene_notariado=bool((r.get('contrato_notariado_url') or '').strip()),
        tiene_acta=bool((r.get('acta_url') or '').strip()),
        motivo_rechazo=r.get('motivo_rechazo', ''))


# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
<style>
.rep-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;line-height:1.4;padding-bottom:8px;
  border-bottom:2px solid #e2e8f0;margin:26px 0 16px;display:flex;align-items:center;gap:9px;}
.rep-kpi{background:#fff;border-radius:16px;padding:18px 20px;border:1px solid #e8ebf3;
  box-shadow:0 2px 12px rgba(15,23,42,.06);height:100%;position:relative;overflow:hidden;box-sizing:border-box;}
.rep-kpi::before{content:'';position:absolute;top:0;left:0;right:0;height:4px;border-radius:16px 16px 0 0;background:var(--acc);}
.rep-kpi .lab{font-size:0.66rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;
  display:flex;align-items:center;margin-bottom:9px;}
.rep-kpi .val{font-size:1.85rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;line-height:1;}
.rep-kpi .sub{font-size:0.72rem;color:#64748b;margin-top:6px;}
.rep-card{background:#fff;border-radius:14px;padding:18px 20px;border:1px solid #e8ebf3;box-shadow:0 2px 10px rgba(15,23,42,.05);}
.rep-ct{font-size:0.66rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;
  margin-bottom:14px;display:flex;align-items:center;gap:6px;}
.rep-lb{display:flex;align-items:center;gap:12px;padding:11px 0;border-bottom:1px solid #f4f6fb;}
.rep-lb:last-child{border-bottom:none;}
.rep-lb-name{font-size:0.86rem;font-weight:800;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.rep-lb-sub{font-size:0.68rem;color:#94a3b8;font-weight:600;margin-top:1px;}
.rep-lb-bar{background:#f1f5f9;border-radius:99px;height:7px;overflow:hidden;margin-top:6px;}
.rep-lb-monto{font-size:0.95rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;text-align:right;white-space:nowrap;}
.rep-lb-tasa{font-size:0.66rem;color:#64748b;font-weight:700;text-align:right;margin-top:2px;}
.rep-row{display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid #f4f6fb;}
.rep-row:last-child{border-bottom:none;}
.rep-row .k{font-size:0.78rem;color:#475569;display:flex;align-items:center;gap:8px;}
.rep-row .v{font-size:0.84rem;font-weight:800;color:#0f172a;}
.rep-ins{background:#f8fafc;border-left:3px solid var(--ic,#3b82f6);border-radius:0 10px 10px 0;
  padding:11px 15px;margin-bottom:9px;display:flex;gap:10px;align-items:flex-start;}
.rep-ins p{font-size:0.8rem;color:#334155;line-height:1.55;margin:0;}
</style>
"""


# ── Render ────────────────────────────────────────────────────────────────────

def render_tab_reporte(supabase, supabase_admin=None, **deps):
    if not st.session_state.get('modo_admin'):
        st.info("Esta sección es solo para administradores.", icon=":material/lock:")
        return

    st.markdown(_CSS, unsafe_allow_html=True)
    render_page_header(
        "reporte",
        "Reporte de Inteligencia Comercial",
        "Espacio Container House SpA &middot; visión ejecutiva del negocio &middot; solo admin y root.",
    )

    _opts = {"Este mes": "mes", "Últimos 3 meses": "3meses", "Últimos 6 meses": "6meses",
             "Este año": "año", "Todos los tiempos": "todo", "Rango personalizado": "rango"}
    st.markdown(
        "<style>.st-key-rep_periodo label,.st-key-rep_periodo label *{font-family:Montserrat,sans-serif!important;"
        "font-weight:700!important;font-size:0.86rem!important;letter-spacing:0.05em!important;line-height:1.6!important;"
        "text-transform:uppercase!important;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;}</style>",
        unsafe_allow_html=True)
    _plabel = st.radio("Período", list(_opts.keys()), horizontal=True, index=0,
                       key="rep_periodo", label_visibility="collapsed")
    _periodo = _opts[_plabel]

    _desde = _hasta = ''
    if _periodo == 'rango':
        import datetime as _dtr
        _dc1, _dc2, _dc3 = st.columns([1.3, 1.3, 3.4])
        with _dc1:
            _dd_d = st.date_input("Desde", value=(_dtr.date.today() - _dtr.timedelta(days=30)),
                                  key="rep_desde", format="DD/MM/YYYY")
        with _dc2:
            _dd_h = st.date_input("Hasta", value=_dtr.date.today(), key="rep_hasta", format="DD/MM/YYYY")
        _desde = _dd_d.isoformat() if _dd_d else ''
        _hasta = _dd_h.isoformat() if _dd_h else ''
        if _desde and _hasta and _desde > _hasta:
            _desde, _hasta = _hasta, _desde

    with st.spinner("Cargando reporte de inteligencia comercial..."):
        _data = _cargar_datos_reporte(_periodo, _desde, _hasta)
        _av = _reporte_avatars()

    if not _data:
        st.info("No hay datos para el período seleccionado.")
        return

    def _fmt_m(v):
        v = float(v or 0)
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000: return f"${v/1_000:.0f}K"
        return f"${v:,.0f}"

    # ── Clasificación por estado real ──
    from collections import defaultdict as _dd
    _ef = _dd(int)
    for r in _data:
        _ef[_estado_de(r)] += 1
    _total = len(_data)
    _n_ganados = sum(_ef.get(e, 0) for e in _GANADOS)
    _n_autoriz = sum(_ef.get(e, 0) for e in _AUTORIZADOS)
    _monto_ganado = sum(float(r.get('total_total') or 0) for r in _data if _estado_de(r) in _GANADOS)
    _tasa_cierre = round(_n_ganados / _total * 100) if _total else 0
    _tasa_aut = round(_n_autoriz / _total * 100) if _total else 0
    _ticket = round(_monto_ganado / _n_ganados) if _n_ganados else 0

    # ── Tiempos de cierre (proxy: creación → última modificación de los ganados) ──
    from datetime import datetime as _dt2, timedelta as _td2
    _tiempos = []
    for r in _data:
        if _estado_de(r) not in _GANADOS:
            continue
        try:
            _fc = _dt2.fromisoformat(r['fecha_creacion'][:10])
            _fm = _dt2.fromisoformat(r['fecha_modificacion'][:10])
            _dias = (_fm - _fc).days
            if 0 <= _dias <= 365:
                _tiempos.append(_dias)
        except Exception:
            pass
    _prom_d = round(sum(_tiempos) / len(_tiempos), 1) if _tiempos else 0
    _min_d = min(_tiempos) if _tiempos else 0
    _max_d = max(_tiempos) if _tiempos else 0
    _estancados = sum(1 for r in _data if _estado_de(r) in ('INCOMPLETO', 'INCOMPLETO CON PLANO', 'BORRADOR', 'BORRADOR CON PLANO')
                      and r.get('fecha_creacion') and
                      (_dt2.now() - _dt2.fromisoformat(r['fecha_creacion'][:10])).days > 30)

    # ── Ejecutivos ──
    _ejd = {}
    for r in _data:
        _ej = r.get('asesor_nombre') or 'Sin asignar'
        _ejd.setdefault(_ej, {'total': 0, 'ganados': 0, 'monto': 0})
        _ejd[_ej]['total'] += 1
        if _estado_de(r) in _GANADOS:
            _ejd[_ej]['ganados'] += 1
            _ejd[_ej]['monto'] += float(r.get('total_total') or 0)
    _ejs = sorted(_ejd.items(), key=lambda x: x[1]['monto'], reverse=True)[:6]
    _max_ej = max((v['monto'] for _, v in _ejs), default=1) or 1

    # ── Tipo de cliente + género + regiones ──
    _n_nat = sum(1 for r in _data if (r.get('cliente_tipo') or '') == 'natural')
    _n_jur = _total - _n_nat
    _mnat = sum(float(r.get('total_total') or 0) for r in _data if (r.get('cliente_tipo') or '') == 'natural' and _estado_de(r) in _GANADOS)
    _mjur = sum(float(r.get('total_total') or 0) for r in _data if (r.get('cliente_tipo') or '') == 'juridica' and _estado_de(r) in _GANADOS)
    _gnat = sum(1 for r in _data if (r.get('cliente_tipo') or '') == 'natural' and _estado_de(r) in _GANADOS)
    _gjur = sum(1 for r in _data if (r.get('cliente_tipo') or '') == 'juridica' and _estado_de(r) in _GANADOS)
    _tick_nat = round(_mnat / max(1, _gnat))
    _tick_jur = round(_mjur / max(1, _gjur))

    import json as _json_rep
    _masc = _fem = 0
    for r in _data:
        try:
            _cd = r.get('contrato_datos')
            if isinstance(_cd, str): _cd = _json_rep.loads(_cd)
            _t = (_cd or {}).get('cli_tratamiento', '')
            if _t in ('Don', 'Sr.'): _masc += 1
            elif _t in ('Doña', 'Do&#241;a', 'Sra.'): _fem += 1
        except Exception:
            pass
    _tg = _masc + _fem or 1
    _pct_m = round(_masc / _tg * 100)
    _pct_f = 100 - _pct_m

    _regd = {}
    for r in _data:
        _reg = (r.get('cliente_region') or 'Sin región').replace('Región ', '').strip() or 'Sin región'
        _regd[_reg] = _regd.get(_reg, 0) + 1
    _regs = sorted(_regd.items(), key=lambda x: x[1], reverse=True)[:6]

    # ══ KPIs HERO ══
    st.markdown(f'<div class="rep-sec">{_ic("chart","#0f172a",17,0)}Indicadores del negocio</div>', unsafe_allow_html=True)
    _k = st.columns(5)
    _kpis = [
        ("dollar", "Monto ganado", _fmt_m(_monto_ganado), f'{_n_ganados} proyecto(s) adjudicado(s)', "linear-gradient(90deg,#16a34a,#22c55e)"),
        ("file", "Cotizaciones", f'{_total:,}', f'{_n_autoriz} autorizadas · {_tasa_aut}%', "linear-gradient(90deg,#2563eb,#06b6d4)"),
        ("target", "Tasa de cierre", f'{_tasa_cierre}%', f'{_n_ganados} ganadas de {_total}', "linear-gradient(90deg,#f59e0b,#f97316)"),
        ("ticket", "Ticket promedio", _fmt_m(_ticket), "por proyecto ganado", "linear-gradient(90deg,#7c3aed,#a855f7)"),
        ("clock", "Cierre promedio", f'{_prom_d} d', f'mín {_min_d}d · máx {_max_d}d', "linear-gradient(90deg,#0ea5e9,#38bdf8)"),
    ]
    for col, icon, lab, val, sub, acc in zip(_k, *zip(*_kpis)):
        with col:
            st.markdown(f'<div class="rep-kpi" style="--acc:{acc};"><div class="lab">{_ic(icon,"#94a3b8",13,6)}{lab}</div>'
                        f'<div class="val">{val}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)

    # ══ ESTADOS (mismos colores/iconos que COTIZACIONES) ══
    st.markdown(f'<div class="rep-sec">{_ic("trending","#0f172a",17,0)}Estado de las cotizaciones</div>', unsafe_allow_html=True)
    _pres = [(e, l) for e, l in _ESTADO_ORDER if _ef.get(e, 0) > 0]
    _cf, _cd = st.columns([3, 2])
    with _cf:
        _fh = ('<div class="rep-card"><div style="display:flex;justify-content:space-between;margin-bottom:14px;">'
               '<span class="rep-ct" style="margin:0;">Estado</span><span class="rep-ct" style="margin:0;">% del total</span></div>')
        for _e, _l in _pres:
            _cnt = _ef.get(_e, 0); _bg, _fg = ESTADO_BADGE_COLORS.get(_e, ('#f1f5f9', '#64748b'))
            _pct = round(_cnt / _total * 100)
            _fh += (f'<div style="margin-bottom:12px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;gap:8px;">'
                    f'<span style="font-size:0.82rem;font-weight:700;color:#1e293b;display:inline-flex;align-items:center;gap:8px;">'
                    f'<span style="width:22px;height:22px;border-radius:6px;background:{_bg};display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;">{_estado_svg(_e,_fg)}</span>{_l}</span>'
                    f'<span style="font-size:0.82rem;font-weight:800;color:{_fg};white-space:nowrap;">{_cnt} &nbsp;({_pct}%)</span></div>'
                    f'<div style="background:#f1f5f9;border-radius:10px;height:10px;overflow:hidden;"><div style="height:10px;border-radius:10px;width:{_pct}%;background:{_fg};opacity:.85;"></div></div></div>')
        _fh += '</div>'
        st.markdown(_fh, unsafe_allow_html=True)
    with _cd:
        with st.container(border=True):
            if _pres:
                import plotly.graph_objects as go
                _lbls = [l for e, l in _pres]; _vals = [_ef.get(e, 0) for e, l in _pres]
                _cols = [ESTADO_BADGE_COLORS.get(e, ('#f1f5f9', '#64748b'))[1] for e, l in _pres]
                _fig = go.Figure(go.Pie(labels=_lbls, values=_vals, hole=0.64, sort=False,
                    marker=dict(colors=_cols, line=dict(color='white', width=2)), textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value}<br>%{percent}<extra></extra>'))
                _fig.add_annotation(text=f"<b>{_tasa_cierre}%</b><br><span style='font-size:10px'>cierre</span>",
                    x=0.5, y=0.5, showarrow=False, font=dict(size=18, family='Montserrat'), xref="paper", yref="paper")
                _fig.update_layout(showlegend=True, margin=dict(t=14, b=14, l=14, r=14), height=300,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(font=dict(size=9.5, color='#475569'), orientation='h', yanchor='top', y=-0.02, xanchor='center', x=0.5, bgcolor='rgba(0,0,0,0)'))
                st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})

    # ══ RANKING DE EJECUTIVOS (con foto + podio) ══
    st.markdown(f'<div class="rep-sec">{_ic("award","#0f172a",17,0)}Ranking de ejecutivos</div>', unsafe_allow_html=True)
    if _ejs:
        _hl = '<div class="rep-card">'
        for _i, (_nom, _v) in enumerate(_ejs):
            _foto = _av.get((_nom or '').strip().lower(), '')
            _pctb = round(_v['monto'] / _max_ej * 100)
            _tasa = round(_v['ganados'] / max(1, _v['total']) * 100)
            _hl += (f'<div class="rep-lb">{_rank_badge(_i)}{_avatar(_nom, _foto, 42)}'
                    f'<div style="flex:1;min-width:0;"><div class="rep-lb-name">{_nom[:26]}</div>'
                    f'<div class="rep-lb-sub">{_v["ganados"]} ganada(s) de {_v["total"]} cotización(es)</div>'
                    f'<div class="rep-lb-bar"><div style="width:{_pctb}%;height:100%;border-radius:99px;background:linear-gradient(90deg,#2563eb,#06b6d4);"></div></div></div>'
                    f'<div style="text-align:right;flex-shrink:0;"><div class="rep-lb-monto">{_fmt_m(_v["monto"])}</div>'
                    f'<div class="rep-lb-tasa">{_tasa}% cierre</div></div></div>')
        _hl += '</div>'
        st.markdown(_hl, unsafe_allow_html=True)
    else:
        st.info("Sin datos de ejecutivos.")

    # ══ PERFIL COMERCIAL: tipo cliente + género + tiempos ══
    st.markdown(f'<div class="rep-sec">{_ic("users","#0f172a",17,0)}Perfil comercial</div>', unsafe_allow_html=True)
    _p1, _p2, _p3 = st.columns(3)
    with _p1:
        st.markdown(
            f'<div class="rep-card"><div class="rep-ct">{_ic("building","#94a3b8",13,0)}Tipo de cliente</div>'
            f'<div class="rep-row"><span class="k">{_ic("user","#3b82f6",14,0)}Persona natural</span><span class="v">{_n_nat} ({round(_n_nat/max(1,_total)*100)}%)</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("building","#f59e0b",14,0)}Persona jurídica</span><span class="v">{_n_jur} ({round(_n_jur/max(1,_total)*100)}%)</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("ticket","#3b82f6",14,0)}Ticket natural</span><span class="v">{_fmt_m(_tick_nat)}</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("ticket","#f59e0b",14,0)}Ticket jurídica</span><span class="v">{_fmt_m(_tick_jur)}</span></div>'
            '</div>', unsafe_allow_html=True)
    with _p2:
        _dm = round(3.6 * _pct_m)
        st.markdown(
            f'<div class="rep-card"><div class="rep-ct">{_ic("users","#94a3b8",13,0)}Género del cliente</div>'
            f'<div style="display:flex;align-items:center;gap:16px;justify-content:center;padding-top:6px;">'
            f'<svg width="96" height="96" viewBox="0 0 96 96">'
            f'<circle cx="48" cy="48" r="36" fill="none" stroke="#3b82f6" stroke-width="16" stroke-dasharray="{_dm} {360-_dm}" transform="rotate(-90 48 48)" pathLength="360"/>'
            f'<circle cx="48" cy="48" r="36" fill="none" stroke="#ec4899" stroke-width="16" stroke-dasharray="{360-_dm} {_dm}" stroke-dashoffset="-{_dm}" transform="rotate(-90 48 48)" pathLength="360"/>'
            f'<text x="48" y="53" text-anchor="middle" font-size="15" font-weight="900" fill="#0f172a" font-family="Montserrat">{_pct_m}%</text></svg>'
            f'<div><div style="display:flex;align-items:center;gap:7px;font-size:0.76rem;color:#334155;margin-bottom:6px;font-weight:600;"><span style="width:10px;height:10px;border-radius:3px;background:#3b82f6;"></span>Masculino {_pct_m}%</div>'
            f'<div style="display:flex;align-items:center;gap:7px;font-size:0.76rem;color:#334155;font-weight:600;"><span style="width:10px;height:10px;border-radius:3px;background:#ec4899;"></span>Femenino {_pct_f}%</div>'
            f'<div style="font-size:0.66rem;color:#94a3b8;margin-top:9px;">Inferido del tratamiento del contrato ({_tg if _masc+_fem else 0})</div></div></div></div>',
            unsafe_allow_html=True)
    with _p3:
        st.markdown(
            f'<div class="rep-card"><div class="rep-ct">{_ic("clock","#94a3b8",13,0)}Tiempos de cierre</div>'
            f'<div class="rep-row"><span class="k">{_ic("zap","#16a34a",14,0)}Más rápido</span><span class="v" style="color:#16a34a;">{_min_d} días</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("turtle","#dc2626",14,0)}Más lento</span><span class="v" style="color:#dc2626;">{_max_d} días</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("chart","#64748b",14,0)}Promedio</span><span class="v">{_prom_d} días</span></div>'
            f'<div class="rep-row"><span class="k">{_ic("hourglass","#f97316",14,0)}Estancadas +30d</span><span class="v" style="color:#f97316;">{_estancados}</span></div>'
            '</div>', unsafe_allow_html=True)

    # ══ TOP REGIONES ══
    if _regs:
        st.markdown(f'<div class="rep-sec">{_ic("map","#0f172a",17,0)}Top regiones por cotizaciones</div>', unsafe_allow_html=True)
        _maxr = max(v for _, v in _regs) or 1
        _rh = '<div class="rep-card">'
        for _reg, _cnt in _regs:
            _rh += (f'<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">'
                    f'<div style="width:150px;font-size:0.8rem;color:#334155;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_reg[:22]}</div>'
                    f'<div style="flex:1;background:#f1f5f9;border-radius:99px;height:8px;overflow:hidden;"><div style="width:{round(_cnt/_maxr*100)}%;height:100%;border-radius:99px;background:linear-gradient(90deg,#2563eb,#06b6d4);"></div></div>'
                    f'<div style="width:44px;text-align:right;font-size:0.82rem;font-weight:800;color:#0f172a;">{_cnt}</div></div>')
        _rh += '</div>'
        st.markdown(_rh, unsafe_allow_html=True)

    # ══ INSIGHTS ══
    _ins = []
    if _ejs:
        _t = _ejs[0]; _tt = round(_t[1]['ganados'] / max(1, _t[1]['total']) * 100)
        if _tt < 40:
            _ins.append((f"<b>{_t[0]}</b> lidera en monto ganado pero su tasa de cierre es {_tt}%. Oportunidad de mejorar calidad sobre cantidad.", "#f59e0b"))
    if _estancados > 0:
        _ins.append((f"<b>{_estancados} cotización(es)</b> llevan más de 30 días sin avanzar (borrador/incompleto). Revisión recomendada.", "#dc2626"))
    if _tick_jur > _tick_nat * 1.2 and _n_jur < _n_nat * 0.4:
        _ins.append((f"El ticket de clientes jurídicos ({_fmt_m(_tick_jur)}) supera al de personas naturales. Mayor foco en empresas puede elevar la rentabilidad.", "#2563eb"))
    if _tasa_cierre < 15 and _total > 10:
        _ins.append((f"La tasa de cierre es de <b>{_tasa_cierre}%</b>. Vale la pena revisar el proceso comercial y la calificación de leads.", "#7c3aed"))
    if _prom_d > 15:
        _ins.append((f"El cierre promedio es de <b>{_prom_d} días</b>. Identificar cuellos de botella podría acelerar la conversión.", "#0ea5e9"))
    if not _ins:
        _ins.append(("Todo dentro de rangos normales. Continúa monitoreando los indicadores clave.", "#16a34a"))

    st.markdown(f'<div class="rep-sec">{_ic("bulb","#0f172a",17,0)}Insights automáticos</div>', unsafe_allow_html=True)
    _ih = '<div class="rep-card">'
    for _txt, _cc in _ins:
        _ih += (f'<div class="rep-ins" style="--ic:{_cc};">{_ic("bulb",_cc,16,0)}<p>{_txt}</p></div>')
    _ih += '</div>'
    st.markdown(_ih, unsafe_allow_html=True)

    # ── Descarga CSV + refresh ──
    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    import pandas as _pd
    _csv = _pd.DataFrame(_data).to_csv(index=False).encode('utf-8-sig')
    _cap = (f"Rango: {_desde[8:10]}/{_desde[5:7]}/{_desde[0:4]} → {_hasta[8:10]}/{_hasta[5:7]}/{_hasta[0:4]}"
            if _periodo == 'rango' and _desde and _hasta else f"Período: {_plabel}")
    _d1, _d2, _d3 = st.columns([2, 2, 2])
    with _d1:
        if st.button("Actualizar reporte", key="btn_refresh_rep", use_container_width=True, icon=":material/refresh:"):
            _cargar_datos_reporte.clear()
            _reporte_avatars.clear()
            st.rerun()
    with _d3:
        st.download_button("Descargar datos CSV", data=_csv,
                           file_name=f"reporte_bi_{_periodo}.csv", mime="text/csv",
                           use_container_width=True, key="dl_reporte_csv", icon=":material/download:")
    st.caption(f"{_cap}  ·  {_total} cotización(es)")
