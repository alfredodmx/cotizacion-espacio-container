"""
Tab RANKING — Perfil del ejecutivo + métricas de dinero (ganado / casi ganado /
perdido) por periodo + ranking del equipo. Rol-aware (ejecutivo vs admin/root).
"""
import streamlit as st
import httpx
from datetime import datetime, timedelta
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from services.cotizacion_service import calcular_estado_label
from views.layout import render_page_header


# ── Datos ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _fetch_cotizaciones_rank(_cb: str = ''):
    try:
        return _supa_admin.table('cotizaciones').select(
            'asesor_nombre,asesor_email,cliente_nombre,cliente_email,asesor_telefono,'
            'config_margen,plano_url,plano_nombre,contrato_notariado_url,acta_url,'
            'motivo_rechazo,total_total,fecha_creacion'
        ).execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_users_map(_cb: str = ''):
    """email(min) -> {foto_url, nombre, rol}. Incluye a todos (también roots)."""
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = {}
        for u in r.json().get("users", []):
            em = (u.get("email") or "").lower()
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            out[em] = {
                "foto_url": meta.get("foto_url", "") or "",
                "nombre": meta.get("nombre", em) or em,
                "rol": meta.get("rol", "ejecutivo"),
            }
        return out
    except Exception:
        return {}


def _clasificar(row):
    """Devuelve la etiqueta de estado (misma fuente que la tabla/badges)."""
    return calcular_estado_label(
        row.get('cliente_nombre', ''), row.get('cliente_email', ''),
        row.get('asesor_nombre', ''), row.get('asesor_email', ''), row.get('asesor_telefono', ''),
        float(row.get('config_margen') or 0),
        bool(row.get('plano_url') or row.get('plano_nombre')),
        tiene_notariado=bool(row.get('contrato_notariado_url')),
        tiene_acta=bool(row.get('acta_url')),
        motivo_rechazo=row.get('motivo_rechazo', '') or '',
    )


def _bucket(label):
    if label in ('PROYECTO TERMINADO', 'ADJUDICADO'):
        return 'ganado'
    if label == 'RECHAZADO':
        return 'perdido'
    return 'casi'


def _parse_fecha(fc):
    if not fc:
        return None
    try:
        return datetime.fromisoformat(str(fc).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _agregar(rows, period_days=None, only_email=None):
    """Agrega por ejecutivo dentro del periodo (filtra por fecha_creacion)."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    agg = {}
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        nm = (r.get('asesor_nombre') or '').strip() or 'Sin asignar'
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        key = em or nm
        a = agg.setdefault(key, {
            'email': em, 'nombre': nm, 'ganado': 0.0, 'casi': 0.0, 'perdido': 0.0,
            'generado': 0.0, 'n_total': 0, 'n_ganado': 0, 'n_casi': 0, 'n_perdido': 0,
        })
        monto = float(r.get('total_total') or 0)
        b = _bucket(_clasificar(r))
        a['n_total'] += 1
        a['generado'] += monto
        if b == 'ganado':
            a['ganado'] += monto; a['n_ganado'] += 1
        elif b == 'perdido':
            a['perdido'] += monto; a['n_perdido'] += 1
        else:
            a['casi'] += monto; a['n_casi'] += 1
    return agg


def _ventas_por_ventana(rows, only_email=None):
    """Dinero GANADO en ventanas: 7d, 30d, 90d, 365d (acumulado desde hoy)."""
    ventanas = [('Semana', 7), ('Mes', 30), ('3 meses', 90), ('Año', 365)]
    res = []
    for lbl, dias in ventanas:
        agg = _agregar(rows, period_days=dias, only_email=only_email)
        total = sum(a['ganado'] for a in agg.values())
        res.append((lbl, total))
    return res


def _fmt_money(v):
    v = float(v or 0)
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}${v/1_000:.0f}K"
    return f"{sign}${v:,.0f}"


# ── Render ───────────────────────────────────────────────────────────────────

_PERIODOS = {'Semana': 7, 'Mes': 30, '3 meses': 90, 'Año': 365, 'Todo': None}


def render_tab_ranking(supabase, **deps):
    import plotly.graph_objects as go

    _rol   = st.session_state.get('rol_usuario', 'ejecutivo')
    _email = (st.session_state.get('auth_email', '') or '').lower()
    _nombre_sesion = st.session_state.get('auth_nombre') or _email
    _es_admin = _rol in ('root', 'admin')

    st.markdown("""
    <style>
    .rk-hero{display:flex;gap:24px;align-items:center;justify-content:space-between;
        background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#334155 100%);
        border-radius:22px;padding:26px 30px;margin-bottom:18px;box-shadow:0 10px 40px rgba(15,23,42,0.25);}
    .rk-hero-name{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.9rem;color:#fff;line-height:1.05;letter-spacing:-0.01em;}
    .rk-hero-role{display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:0.72rem;font-weight:800;
        text-transform:uppercase;letter-spacing:0.08em;color:#0f172a;background:#fbbf24;border-radius:99px;padding:4px 12px;}
    .rk-photo{width:clamp(150px,22vw,250px);height:clamp(150px,22vw,250px);border-radius:50%;object-fit:cover;
        border:5px solid rgba(255,255,255,0.18);box-shadow:0 12px 40px rgba(0,0,0,0.4);flex-shrink:0;}
    .rk-photo-ph{display:flex;align-items:center;justify-content:center;font-family:'Montserrat',sans-serif;
        font-weight:900;color:#fff;font-size:clamp(3rem,7vw,5rem);background:linear-gradient(135deg,#6366f1,#8b5cf6);}
    .rk-money{border-radius:16px;padding:16px 18px;color:#fff;position:relative;overflow:hidden;}
    .rk-money .lbl{font-size:0.66rem;font-weight:800;text-transform:uppercase;letter-spacing:0.07em;opacity:0.92;}
    .rk-money .val{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.7rem;line-height:1.1;margin-top:4px;}
    .rk-money .sub{font-size:0.68rem;opacity:0.85;margin-top:2px;}
    .rk-sec{font-size:0.75rem;font-weight:900;color:#1e293b;text-transform:uppercase;letter-spacing:0.1em;
        margin:24px 0 12px;padding:8px 14px;background:linear-gradient(90deg,rgba(99,102,241,0.10),transparent);
        border-left:4px solid #6366f1;border-radius:0 8px 8px 0;}
    .rk-card{display:flex;align-items:center;gap:14px;padding:12px 16px;background:#fff;border-radius:14px;
        border:1px solid #e7ebf3;box-shadow:0 2px 10px rgba(15,23,42,0.05);margin-bottom:9px;}
    .rk-card.me{border:2px solid #6366f1;background:#f5f7ff;}
    .rk-rav{width:46px;height:46px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid #e2e8f0;}
    .rk-rav-ph{display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.1rem;
        background:linear-gradient(135deg,#6366f1,#8b5cf6);}
    .rk-pos{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.15rem;width:30px;text-align:center;flex-shrink:0;}
    </style>
    """, unsafe_allow_html=True)

    render_page_header(
        "ranking",
        "Ranking de Ejecutivos",
        "Tu desempe&#241;o y el del equipo &#8212; dinero ganado, casi ganado y perdido.",
    )

    with st.spinner("Cargando ranking..."):
        _rows = _fetch_cotizaciones_rank()
        _umap = _fetch_users_map()

    # ── Selector de periodo ──
    _periodo = st.segmented_control(
        "Periodo", list(_PERIODOS.keys()), default='Mes', key='rk_periodo',
        label_visibility='collapsed',
    ) or 'Mes'
    _days = _PERIODOS.get(_periodo)

    # Foto/rol del usuario actual
    _me = _umap.get(_email, {})
    _foto = _me.get('foto_url', '')
    _rol_lbl = 'Administrador' if _es_admin else 'Ejecutivo de ventas'

    # ── Métricas del HERO ──
    if _es_admin:
        _agg_periodo = _agregar(_rows, period_days=_days)
        _ganado  = sum(a['ganado'] for a in _agg_periodo.values())
        _casi    = sum(a['casi'] for a in _agg_periodo.values())
        _perdido = sum(a['perdido'] for a in _agg_periodo.values())
        _n_total = sum(a['n_total'] for a in _agg_periodo.values())
        _n_gan   = sum(a['n_ganado'] for a in _agg_periodo.values())
        _n_casi  = sum(a['n_casi'] for a in _agg_periodo.values())
        _n_perd  = sum(a['n_perdido'] for a in _agg_periodo.values())
        _ventas_win = _ventas_por_ventana(_rows)
    else:
        _agg_me = _agregar(_rows, period_days=_days, only_email=_email).get(_email, {
            'ganado': 0, 'casi': 0, 'perdido': 0, 'n_total': 0, 'n_ganado': 0, 'n_casi': 0, 'n_perdido': 0})
        _ganado, _casi, _perdido = _agg_me['ganado'], _agg_me['casi'], _agg_me['perdido']
        _n_total = _agg_me['n_total']
        _n_gan, _n_casi, _n_perd = _agg_me['n_ganado'], _agg_me['n_casi'], _agg_me['n_perdido']
        _ventas_win = _ventas_por_ventana(_rows, only_email=_email)

    # ── HERO: nombre+rol (izq) + foto (der) ──
    _photo_html = (
        f'<img class="rk-photo" src="{_foto}" alt="">' if _foto else
        f'<div class="rk-photo rk-photo-ph">{(_nombre_sesion or "?")[0].upper()}</div>'
    )
    st.markdown(
        f'<div class="rk-hero">'
        f'<div style="min-width:0;">'
        f'<div class="rk-hero-name">{_nombre_sesion}</div>'
        f'<div class="rk-hero-role">{_rol_lbl}</div>'
        f'<div style="color:rgba(255,255,255,0.7);font-size:0.82rem;margin-top:10px;">'
        f'{"Equipo completo" if _es_admin else "Tu desempe&#241;o"} &middot; {_periodo.lower()}'
        f' &middot; {_n_total} presupuesto{"s" if _n_total!=1 else ""}</div>'
        f'</div>'
        f'{_photo_html}'
        f'</div>',
        unsafe_allow_html=True)

    # ── 3 cards de dinero ──
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown(
            f'<div class="rk-money" style="background:linear-gradient(135deg,#16a34a,#15803d);">'
            f'<div class="lbl">&#128176; Dinero ganado</div>'
            f'<div class="val">{_fmt_money(_ganado)}</div>'
            f'<div class="sub">{_n_gan} adjudicado{"s" if _n_gan!=1 else ""} / terminado{"s" if _n_gan!=1 else ""}</div>'
            f'</div>', unsafe_allow_html=True)
    with mc2:
        st.markdown(
            f'<div class="rk-money" style="background:linear-gradient(135deg,#f59e0b,#d97706);">'
            f'<div class="lbl">&#9203; Dinero casi ganado</div>'
            f'<div class="val">{_fmt_money(_casi)}</div>'
            f'<div class="sub">{_n_casi} en proceso (borrador/incompleto/autorizado)</div>'
            f'</div>', unsafe_allow_html=True)
    with mc3:
        st.markdown(
            f'<div class="rk-money" style="background:linear-gradient(135deg,#dc2626,#b91c1c);">'
            f'<div class="lbl">&#128201; Dinero perdido</div>'
            f'<div class="val">{("-" if _perdido>0 else "")}{_fmt_money(_perdido)}</div>'
            f'<div class="sub">{_n_perd} rechazado{"s" if _n_perd!=1 else ""}</div>'
            f'</div>', unsafe_allow_html=True)

    # ── Gráfico: ventas (dinero ganado) por ventana de tiempo ──
    st.markdown('<div class="rk-sec">&#128200; Ventas por periodo</div>', unsafe_allow_html=True)
    _vlbls = [v[0] for v in _ventas_win]
    _vvals = [v[1] for v in _ventas_win]
    _fig = go.Figure(go.Bar(
        x=_vlbls, y=_vvals,
        marker_color=['#a5b4fc', '#818cf8', '#6366f1', '#4338ca'],
        text=[_fmt_money(v) for v in _vvals], textposition='outside',
        textfont=dict(size=12, family='Montserrat', color='#1e293b'),
        hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>',
    ))
    _maxv = max(_vvals + [1])
    _fig.update_layout(
        height=300, margin=dict(t=24, b=10, l=10, r=10),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, tickfont=dict(size=12, family='Montserrat')),
        yaxis=dict(visible=False, range=[0, _maxv * 1.25]),
        showlegend=False,
    )
    with st.container(border=True):
        st.caption("Dinero **ganado** (adjudicados + terminados) acumulado en cada ventana, desde hoy hacia atrás.")
        st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})

    # ── Ranking del equipo ──
    st.markdown('<div class="rk-sec">&#127942; Ranking del equipo</div>', unsafe_allow_html=True)
    _agg_team = _agregar(_rows, period_days=_days)
    _team = sorted(_agg_team.values(), key=lambda a: (a['ganado'], a['generado']), reverse=True)
    if not _team:
        st.info("No hay presupuestos en este periodo.")
    else:
        _medallas = {1: "&#129351;", 2: "&#129352;", 3: "&#129353;"}
        for i, a in enumerate(_team, 1):
            _u = _umap.get(a['email'], {})
            _f = _u.get('foto_url', '')
            _ini = (a['nombre'] or '?')[0].upper()
            _av = (f'<img class="rk-rav" src="{_f}" alt="">' if _f
                   else f'<div class="rk-rav rk-rav-ph">{_ini}</div>')
            _pos = _medallas.get(i, f'<span style="color:#94a3b8;">{i}</span>')
            _is_me = (a['email'] == _email and not _es_admin)
            _me_cls = ' me' if _is_me else ''
            _tu_badge = (' &middot; <span style="color:#6366f1;font-size:0.7rem;font-weight:800;">T&#218;</span>'
                         if _is_me else '')
            st.markdown(
                f'<div class="rk-card{_me_cls}">'
                f'<div class="rk-pos">{_pos}</div>'
                f'{_av}'
                f'<div style="flex:1;min-width:0;">'
                f'<div style="font-weight:800;color:#0f172a;font-size:0.98rem;">{a["nombre"]}{_tu_badge}</div>'
                f'<div style="font-size:0.74rem;color:#64748b;margin-top:2px;">{a["n_total"]} presupuesto{"s" if a["n_total"]!=1 else ""}</div>'
                f'</div>'
                f'<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">'
                f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:900;color:#16a34a;font-size:1.05rem;">{_fmt_money(a["ganado"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Ganado</div></div>'
                f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#f59e0b;font-size:0.95rem;">{_fmt_money(a["casi"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Casi</div></div>'
                f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#dc2626;font-size:0.95rem;">{("-" if a["perdido"]>0 else "")}{_fmt_money(a["perdido"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Perdido</div></div>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True)
