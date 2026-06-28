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
            'numero,asesor_nombre,asesor_email,cliente_nombre,cliente_email,asesor_telefono,'
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


# Taxonomía de estados → bucket. Orden de presentación dentro de cada bucket.
# (bucket, etiqueta_calcular_estado_label, nombre_a_mostrar)
_ESTADOS_ORDEN = [
    ('ganado',  'ADJUDICADO',           'Adjudicado'),
    ('ganado',  'PROYECTO TERMINADO',   'Proyecto terminado'),
    ('casi',    'AUTORIZADO CON PLANO', 'Autorizado con plano'),
    ('casi',    'AUTORIZADO',           'Autorizado'),
    ('casi',    'BORRADOR CON PLANO',   'Borrador con plano'),
    ('casi',    'BORRADOR',             'Borrador'),
    ('casi',    'INCOMPLETO CON PLANO', 'Incompleto con plano'),
    ('casi',    'INCOMPLETO',           'Incompleto'),
    ('perdido', 'RECHAZADO',            'Rechazado'),
]

# bucket -> (color, etiqueta, icono html-entity)
_BUCKET_META = {
    'ganado':  ('#16a34a', 'Ganado',      '&#128176;'),
    'casi':    ('#f59e0b', 'Casi ganado', '&#9203;'),
    'perdido': ('#dc2626', 'Perdido',     '&#128201;'),
}


def _desglose_estados(rows, period_days=None, only_email=None):
    """Cuenta presupuestos y suma montos por estado dentro del periodo/scope.
    Devuelve {etiqueta_estado: {'n': int, 'monto': float}}."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    out = {}
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        lbl = _clasificar(r)
        e = out.setdefault(lbl, {'n': 0, 'monto': 0.0})
        e['n'] += 1
        e['monto'] += float(r.get('total_total') or 0)
    return out


def _listar_presupuestos(rows, period_days=None, only_email=None):
    """Lista de presupuestos individuales dentro del periodo/scope, orden por monto desc.
    Cada item: {bucket, estado, numero, cliente, asesor, monto}."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    out = []
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        lbl = _clasificar(r)
        out.append({
            'bucket': _bucket(lbl),
            'estado': lbl,
            'numero': (str(r.get('numero') or '').strip() or '—'),
            'cliente': (str(r.get('cliente_nombre') or '').strip() or 'Sin cliente'),
            'asesor': (str(r.get('asesor_nombre') or '').strip() or 'Sin asignar'),
            'monto': float(r.get('total_total') or 0),
        })
    out.sort(key=lambda x: x['monto'], reverse=True)
    return out


def _money_exacto(v):
    """Monto exacto con separador de miles estilo CL: $25.400.000."""
    return '$' + f'{abs(float(v or 0)):,.0f}'.replace(',', '.')


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
    .rk-card.sel{border:2px solid #6366f1;background:#eef2ff;box-shadow:0 4px 16px rgba(99,102,241,0.25);}
    .rk-rav{width:46px;height:46px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid #e2e8f0;}
    .rk-rav-ph{display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.1rem;
        background:linear-gradient(135deg,#6366f1,#8b5cf6);}
    .rk-pos{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.15rem;width:30px;text-align:center;flex-shrink:0;}
    .rk-est-group{background:#fff;border:1px solid #e7ebf3;border-radius:14px;padding:14px 16px;
        box-shadow:0 2px 10px rgba(15,23,42,0.05);height:100%;}
    .rk-est-head{font-size:0.74rem;font-weight:900;text-transform:uppercase;letter-spacing:0.05em;
        display:flex;align-items:center;gap:8px;}
    .rk-est-badge{color:#fff;font-size:0.7rem;font-weight:800;border-radius:99px;padding:1px 9px;margin-left:auto;}
    .rk-est-tot{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.25rem;color:#0f172a;margin:3px 0 8px;}
    .rk-est-item{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid #f1f5f9;font-size:0.83rem;}
    .rk-est-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
    .rk-est-name{color:#334155;flex:1;min-width:0;}
    .rk-est-n{font-weight:800;color:#0f172a;}
    .rk-est-m{color:#64748b;font-size:0.74rem;min-width:60px;text-align:right;}
    .rk-est-empty{color:#94a3b8;font-size:0.8rem;padding:8px 0;font-style:italic;}
    .rk-pp-wrap{max-height:360px;overflow-y:auto;margin-top:6px;}
    .rk-pp-row{display:flex;align-items:center;gap:10px;padding:8px 4px;border-bottom:1px solid #f1f5f9;}
    .rk-pp-row:last-child{border-bottom:none;}
    .rk-pp-tag{font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.03em;
        color:#fff;border-radius:5px;padding:2px 6px;white-space:nowrap;flex-shrink:0;}
    .rk-pp-mid{flex:1;min-width:0;}
    .rk-pp-num{font-family:'Montserrat',sans-serif;font-weight:800;color:#0f172a;font-size:0.84rem;}
    .rk-pp-cli{font-size:0.74rem;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .rk-pp-m{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.86rem;white-space:nowrap;flex-shrink:0;}
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

    # ── Ejecutivo seleccionado al hacer clic en el ranking del equipo ──
    # rk_perfil_email: None = vista por defecto (admin=equipo, ejecutivo=propio);
    # string (puede ser '' para "Sin asignar") = se muestra el perfil de ese ejecutivo.
    _sel_email = st.session_state.get('rk_perfil_email')
    _sel_nombre = st.session_state.get('rk_perfil_nombre', '')
    _viewing_other = _sel_email is not None

    if _viewing_other:
        _scope = _sel_email
        if st.button(("Volver al equipo" if _es_admin else "Volver a mi panel"),
                     icon=":material/arrow_back:", key="rk_volver"):
            st.session_state.pop('rk_perfil_email', None)
            st.session_state.pop('rk_perfil_nombre', None)
            st.rerun()
    elif _es_admin:
        _scope = None
    else:
        _scope = _email

    # ── Métricas del scope (None = equipo completo) ──
    _agg_f = _agregar(_rows, period_days=_days, only_email=_scope)
    _ganado  = sum(a['ganado'] for a in _agg_f.values())
    _casi    = sum(a['casi'] for a in _agg_f.values())
    _perdido = sum(a['perdido'] for a in _agg_f.values())
    _n_total = sum(a['n_total'] for a in _agg_f.values())
    _n_gan   = sum(a['n_ganado'] for a in _agg_f.values())
    _n_casi  = sum(a['n_casi'] for a in _agg_f.values())
    _n_perd  = sum(a['n_perdido'] for a in _agg_f.values())
    _ventas_win = _ventas_por_ventana(_rows, only_email=_scope)

    # ── HERO: identidad del objetivo (yo / equipo / ejecutivo seleccionado) ──
    if _viewing_other:
        _u_sel = _umap.get((_sel_email or '').lower(), {})
        _disp_nombre = _u_sel.get('nombre') or _sel_nombre or _sel_email or 'Ejecutivo'
        _disp_foto = _u_sel.get('foto_url', '')
        _disp_rol = _u_sel.get('rol', 'ejecutivo')
        _rol_lbl = 'Administrador' if _disp_rol in ('root', 'admin') else 'Ejecutivo de ventas'
        _scope_desc = 'Perfil del ejecutivo'
    else:
        _disp_nombre = _nombre_sesion
        _disp_foto = _umap.get(_email, {}).get('foto_url', '')
        _rol_lbl = 'Administrador' if _es_admin else 'Ejecutivo de ventas'
        _scope_desc = 'Equipo completo' if _es_admin else 'Tu desempe&#241;o'

    _photo_html = (
        f'<img class="rk-photo" src="{_disp_foto}" alt="">' if _disp_foto else
        f'<div class="rk-photo rk-photo-ph">{(_disp_nombre or "?")[0].upper()}</div>'
    )
    st.markdown(
        f'<div class="rk-hero">'
        f'<div style="min-width:0;">'
        f'<div class="rk-hero-name">{_disp_nombre}</div>'
        f'<div class="rk-hero-role">{_rol_lbl}</div>'
        f'<div style="color:rgba(255,255,255,0.7);font-size:0.82rem;margin-top:10px;">'
        f'{_scope_desc} &middot; {_periodo.lower()}'
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

    # ── Estadísticas: selector de tipo de gráfico (barras / circular / ondas) ──
    st.markdown('<div class="rk-sec">&#128202; Estad&#237;sticas</div>', unsafe_allow_html=True)
    _tipo = st.segmented_control(
        "Tipo de gráfico", ['Barras', 'Circular', 'Ondas'], default='Barras',
        key='rk_chart', label_visibility='collapsed',
    ) or 'Barras'

    _comp_lbls = ['Ganado', 'Casi ganado', 'Perdido']
    _comp_vals = [float(_ganado), float(_casi), abs(float(_perdido))]
    _comp_cols = ['#16a34a', '#f59e0b', '#dc2626']
    _tasa = (100.0 * _n_gan / _n_total) if _n_total else 0.0

    with st.container(border=True):
        if not _n_total:
            st.info("No hay presupuestos en este periodo para graficar.")
        elif _tipo == 'Circular':
            st.caption("Composici&#243;n del dinero por estado &#8212; **ganado vs casi ganado vs perdido**. Centro: efectividad (ganados sobre total).")
            _fig = go.Figure(go.Pie(
                labels=_comp_lbls, values=_comp_vals, hole=0.62, sort=False,
                marker=dict(colors=_comp_cols, line=dict(color='#ffffff', width=2)),
                textinfo='label+percent', textfont=dict(size=12, family='Montserrat'),
                hovertemplate='<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>',
            ))
            _fig.update_layout(
                height=330, margin=dict(t=18, b=18, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)', showlegend=False,
                annotations=[dict(
                    text=f'<b style="font-size:26px">{_tasa:.0f}%</b><br><span style="font-size:11px;color:#64748b">efectividad</span>',
                    x=0.5, y=0.5, font=dict(family='Montserrat', color='#0f172a'), showarrow=False)],
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})
        elif _tipo == 'Ondas':
            st.caption("Dinero **ganado** (adjudicados + terminados) acumulado por ventana de tiempo, desde hoy hacia atr&#225;s.")
            _vlbls = [v[0] for v in _ventas_win]
            _vvals = [v[1] for v in _ventas_win]
            _fig = go.Figure(go.Scatter(
                x=_vlbls, y=_vvals, mode='lines+markers',
                line=dict(color='#6366f1', width=3, shape='spline'),
                marker=dict(size=10, color='#4338ca', line=dict(color='#fff', width=2)),
                fill='tozeroy', fillcolor='rgba(99,102,241,0.16)',
                text=[_fmt_money(v) for v in _vvals],
                hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>',
            ))
            _fig.update_layout(
                height=330, margin=dict(t=26, b=10, l=10, r=16),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, tickfont=dict(size=12, family='Montserrat')),
                yaxis=dict(visible=False, range=[0, max(_vvals + [1]) * 1.2]),
                showlegend=False,
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})
        else:  # Barras
            st.caption("Composici&#243;n del dinero por estado &#8212; **ganado vs casi ganado vs perdido** en el periodo.")
            _fig = go.Figure(go.Bar(
                x=_comp_lbls, y=_comp_vals, marker_color=_comp_cols, width=0.55,
                text=[_fmt_money(_ganado), _fmt_money(_casi),
                      (_fmt_money(-abs(_perdido)) if _perdido else '$0')],
                textposition='outside', textfont=dict(size=14, family='Montserrat', color='#1e293b'),
                hovertemplate='<b>%{x}</b><br>%{text}<extra></extra>',
            ))
            _fig.update_layout(
                height=330, margin=dict(t=30, b=10, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, tickfont=dict(size=12, family='Montserrat')),
                yaxis=dict(visible=False, range=[0, max(_comp_vals + [1]) * 1.25]),
                showlegend=False,
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})

    # ── Desglose por estado (cantidad de presupuestos en cada estado) ──
    st.markdown('<div class="rk-sec">&#128203; Presupuestos por estado</div>', unsafe_allow_html=True)
    st.caption(
        "Cada presupuesto se cuenta **una sola vez** por su estado actual. La comisi&#243;n se gana al "
        "**adjudicar**; si despu&#233;s pasa a **terminado** es el mismo proyecto ya construido (no suma de "
        "nuevo). Un presupuesto que queda **rechazado** = el cliente desisti&#243;, comisi&#243;n perdida. "
        "Lo que a&#250;n no llega a adjudicado ni rechazado est&#225; en **casi ganado**.")
    _desg = _desglose_estados(_rows, period_days=_days, only_email=_scope)
    _lista = _listar_presupuestos(_rows, period_days=_days, only_email=_scope)
    _dcols = st.columns(3)
    for _ci, _bk in enumerate(['ganado', 'casi', 'perdido']):
        _bcol, _blbl, _bic = _BUCKET_META[_bk]
        _items = [(disp, _desg.get(code, {'n': 0, 'monto': 0.0}))
                  for (bk, code, disp) in _ESTADOS_ORDEN if bk == _bk]
        _tot_n = sum(it[1]['n'] for it in _items)
        _tot_m = sum(it[1]['monto'] for it in _items)
        _items_html = ''.join(
            f'<div class="rk-est-item">'
            f'<span class="rk-est-dot" style="background:{_bcol};"></span>'
            f'<span class="rk-est-name">{disp}</span>'
            f'<span class="rk-est-n">{e["n"]}</span>'
            f'<span class="rk-est-m">{_fmt_money(-abs(e["monto"]) if _bk == "perdido" else e["monto"])}</span>'
            f'</div>'
            for disp, e in _items if e['n'] > 0)
        if not _items_html:
            _items_html = '<div class="rk-est-empty">Sin presupuestos</div>'
        _tot_m_disp = _fmt_money(-abs(_tot_m)) if (_bk == 'perdido' and _tot_m) else _fmt_money(_tot_m)
        with _dcols[_ci]:
            st.markdown(
                f'<div class="rk-est-group" style="border-top:3px solid {_bcol};">'
                f'<div class="rk-est-head" style="color:{_bcol};">{_bic} {_blbl}'
                f'<span class="rk-est-badge" style="background:{_bcol};">{_tot_n}</span></div>'
                f'<div class="rk-est-tot">{_tot_m_disp}</div>'
                f'{_items_html}'
                f'</div>', unsafe_allow_html=True)
            # Popover "Ver": lista de presupuestos del bucket (N° EP, cliente, monto)
            _bk_items = [p for p in _lista if p['bucket'] == _bk]
            _neg = (_bk == 'perdido')
            with st.popover(f"Ver {_tot_n} presupuesto{'s' if _tot_n != 1 else ''}",
                            use_container_width=True, disabled=(_tot_n == 0)):
                def _pp_row(p, col=_bcol, neg=_neg, adm=(_scope is None)):
                    _cli = p["cliente"] + (f' &middot; {p["asesor"]}' if adm else '')
                    _mt = ('-' if neg else '') + _money_exacto(p["monto"])
                    return (f'<div class="rk-pp-row">'
                            f'<span class="rk-pp-tag" style="background:{col};">{p["estado"]}</span>'
                            f'<div class="rk-pp-mid"><div class="rk-pp-num">{p["numero"]}</div>'
                            f'<div class="rk-pp-cli">{_cli}</div></div>'
                            f'<div class="rk-pp-m" style="color:{col};">{_mt}</div>'
                            f'</div>')
                st.markdown(
                    f'<div style="font-weight:800;color:{_bcol};font-size:0.92rem;margin-bottom:2px;">'
                    f'{_bic} {_blbl} &middot; {_tot_n} &middot; {_tot_m_disp}</div>'
                    f'<div class="rk-pp-wrap">{"".join(_pp_row(p) for p in _bk_items)}</div>',
                    unsafe_allow_html=True)

    # ── Ranking del equipo ──
    st.markdown('<div class="rk-sec">&#127942; Ranking del equipo</div>', unsafe_allow_html=True)
    _agg_team = _agregar(_rows, period_days=_days)
    _team = sorted(_agg_team.values(), key=lambda a: (a['ganado'], a['generado']), reverse=True)
    if not _team:
        st.info("No hay presupuestos en este periodo.")
    else:
        st.caption("Haz clic en **Ver** para cargar arriba el panel completo de ese ejecutivo.")
        _medallas = {1: "&#129351;", 2: "&#129352;", 3: "&#129353;"}
        for i, a in enumerate(_team, 1):
            _u = _umap.get(a['email'], {})
            _f = _u.get('foto_url', '')
            _ini = (a['nombre'] or '?')[0].upper()
            _av = (f'<img class="rk-rav" src="{_f}" alt="">' if _f
                   else f'<div class="rk-rav rk-rav-ph">{_ini}</div>')
            _pos = _medallas.get(i, f'<span style="color:#94a3b8;">{i}</span>')
            _is_me = (a['email'] == _email and not _es_admin)
            _is_sel = _viewing_other and (a['email'] == _sel_email) and (a['nombre'] == (_sel_nombre or a['nombre']))
            _row_cls = ' sel' if _is_sel else (' me' if _is_me else '')
            if _is_sel:
                _badge = ' &middot; <span style="color:#6366f1;font-size:0.7rem;font-weight:800;">VIENDO</span>'
            elif _is_me:
                _badge = ' &middot; <span style="color:#6366f1;font-size:0.7rem;font-weight:800;">T&#218;</span>'
            else:
                _badge = ''
            _c_card, _c_btn = st.columns([8.5, 1.5], vertical_alignment="center")
            with _c_card:
                st.markdown(
                    f'<div class="rk-card{_row_cls}">'
                    f'<div class="rk-pos">{_pos}</div>'
                    f'{_av}'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-weight:800;color:#0f172a;font-size:0.98rem;">{a["nombre"]}{_badge}</div>'
                    f'<div style="font-size:0.74rem;color:#64748b;margin-top:2px;">{a["n_total"]} presupuesto{"s" if a["n_total"]!=1 else ""}</div>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:900;color:#16a34a;font-size:1.05rem;">{_fmt_money(a["ganado"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Ganado</div></div>'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#f59e0b;font-size:0.95rem;">{_fmt_money(a["casi"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Casi</div></div>'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#dc2626;font-size:0.95rem;">{("-" if a["perdido"]>0 else "")}{_fmt_money(a["perdido"])}</div><div style="font-size:0.64rem;color:#94a3b8;text-transform:uppercase;letter-spacing:0.05em;">Perdido</div></div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True)
            with _c_btn:
                if st.button("Ver", icon=":material/visibility:", key=f"rk_ver_{i}",
                             use_container_width=True, disabled=_is_sel,
                             help="Cargar arriba el panel de este ejecutivo"):
                    st.session_state['rk_perfil_email'] = a['email']
                    st.session_state['rk_perfil_nombre'] = a['nombre']
                    st.rerun()
