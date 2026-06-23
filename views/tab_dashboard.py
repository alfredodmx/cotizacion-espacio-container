"""
Tab DASHBOARD — KPIs, embudo, serie temporal, top categorías/ejecutivos, perfil clientes.
Código fuente original: app.py líneas 7564-7789 (función) + 16117-16617 (UI)
"""
import re
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.sidebar_nav import page_icon_svg as _pi


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_dashboard(periodo='mes'):
    try:
        from datetime import datetime as _dt, timedelta as _td
        from collections import defaultdict as _dd

        _ahora = _dt.now()
        if periodo == 'mes':
            _inicio = _ahora.replace(day=1).strftime('%Y-%m-%d')
            _inicio_ant = (_ahora.replace(day=1) - _td(days=1)).replace(day=1).strftime('%Y-%m-%d')
            _fin_ant = (_ahora.replace(day=1) - _td(days=1)).strftime('%Y-%m-%d')
        elif periodo == '3meses':
            _inicio = (_ahora - _td(days=90)).strftime('%Y-%m-%d')
            _inicio_ant = (_ahora - _td(days=180)).strftime('%Y-%m-%d')
            _fin_ant = (_ahora - _td(days=91)).strftime('%Y-%m-%d')
        elif periodo == 'año':
            _inicio = _ahora.replace(month=1, day=1).strftime('%Y-%m-%d')
            _inicio_ant = _ahora.replace(month=1, day=1, year=_ahora.year - 1).strftime('%Y-%m-%d')
            _fin_ant = (_ahora.replace(month=1, day=1) - _td(days=1)).strftime('%Y-%m-%d')
        else:
            _inicio = '2000-01-01'
            _inicio_ant = None
            _fin_ant = None

        resp = _supa_admin.table('cotizaciones').select(
            'numero,fecha_creacion,fecha_modificacion,estado,'
            'total_total,asesor_nombre,cliente_nombre,cliente_rut,'
            'cliente_comuna,cliente_region,cliente_tipo,'
            'cliente_empresa,config_margen,productos'
        ).execute()

        _rows_all = resp.data or []
        if periodo != 'todo':
            rows = [r for r in _rows_all
                    if (r.get('fecha_creacion') or r.get('fecha_modificacion') or '')[:10] >= _inicio]
        else:
            rows = _rows_all

        rows_ant = []
        if _inicio_ant and _fin_ant:
            resp_ant = _supa_admin.table('cotizaciones').select(
                'total_total,estado,config_margen'
            ).gte('fecha_creacion', _inicio_ant).lte('fecha_creacion', _fin_ant).execute()
            rows_ant = resp_ant.data or []

        total_ep       = len(rows)
        total_monto    = sum(float(r.get('total_total') or 0) for r in rows)
        promedio_monto = total_monto / total_ep if total_ep else 0

        def _clasificar_estado(r):
            e = (r.get('estado') or '').upper()
            if 'AUTORIZADO' in e: return 'autorizado'
            if 'BORRADOR'   in e: return 'borrador'
            return 'incompleto'

        estados     = [_clasificar_estado(r) for r in rows]
        autorizados = estados.count('autorizado')
        borradores  = estados.count('borrador')
        incompletos = estados.count('incompleto')
        pct_conv    = round((autorizados / total_ep) * 100) if total_ep else 0

        total_ep_ant    = len(rows_ant)
        total_monto_ant = sum(float(r.get('total_total') or 0) for r in rows_ant)
        delta_ep        = total_ep - total_ep_ant
        delta_monto     = total_monto - total_monto_ant

        serie   = _dd(float)
        serie_n = _dd(int)
        for r in rows:
            fecha = (r.get('fecha_creacion') or r.get('fecha_modificacion') or '')[:10]
            if fecha and len(fecha) == 10:
                serie[fecha]   += float(r.get('total_total') or 0)
                serie_n[fecha] += 1
        fechas_sorted = sorted(serie.keys())
        serie_montos  = [round(serie[f]) for f in fechas_sorted]
        serie_counts  = [serie_n[f] for f in fechas_sorted]

        cat_montos = _dd(float)
        for r in rows:
            prods = r.get('productos') or []
            if isinstance(prods, str):
                try:
                    import json as _j; prods = _j.loads(prods)
                except Exception: prods = []
            for p in prods:
                cat = p.get('Categoria') or 'Sin categoría'
                subtotal = float(p.get('Subtotal') or 0)
                if subtotal == 0:
                    subtotal = float(p.get('Precio Unitario') or p.get('Precio Final') or 0) * int(p.get('Cantidad') or 1)
                cat_montos[cat] += subtotal
        top_cats = sorted(cat_montos.items(), key=lambda x: x[1], reverse=True)[:6]

        pipeline = sum(float(r.get('total_total') or 0) for r, e in zip(rows, estados) if e == 'borrador')

        ej_montos = _dd(float)
        for r in rows:
            ej = r.get('asesor_nombre') or 'Sin asignar'
            ej_montos[ej] += float(r.get('total_total') or 0)
        top_ej = sorted(ej_montos.items(), key=lambda x: x[1], reverse=True)[:5]

        prod_montos     = _dd(float)
        prod_cantidades = _dd(int)
        prod_categoria  = {}
        for r in rows:
            prods = r.get('productos') or []
            if isinstance(prods, str):
                try:
                    import json as _j2; prods = _j2.loads(prods)
                except Exception: prods = []
            for p in prods:
                item = (p.get('Item') or '').strip()
                if not item: continue
                subtotal = float(p.get('Subtotal') or 0)
                if subtotal == 0:
                    subtotal = float(p.get('Precio Unitario') or 0) * int(p.get('Cantidad') or 1)
                qty = int(p.get('Cantidad') or 1)
                prod_montos[item]     += subtotal
                prod_cantidades[item] += qty
                if item not in prod_categoria:
                    prod_categoria[item] = (p.get('Categoria') or '').strip()
        top_productos = sorted(prod_montos.items(), key=lambda x: x[1], reverse=True)[:30]
        top_productos = [(n, v, prod_cantidades[n], prod_categoria.get(n, '')) for n, v in top_productos]

        comunas  = _dd(int)
        regiones = _dd(int)
        for r in rows:
            _com = (r.get('cliente_comuna') or '').strip()
            _reg = (r.get('cliente_region') or '').strip()
            if _com: comunas[_com]   += 1
            if _reg: regiones[_reg]  += 1
        top_comunas  = sorted(comunas.items(),  key=lambda x: x[1], reverse=True)[:10]
        top_regiones = sorted(regiones.items(), key=lambda x: x[1], reverse=True)[:10]

        n_natural  = sum(1 for r in rows if (r.get('cliente_tipo') or 'natural') == 'natural')
        n_juridica = sum(1 for r in rows if (r.get('cliente_tipo') or '') == 'juridica')
        top_emp = _dd(int)
        for r in rows:
            if (r.get('cliente_tipo') or '') == 'juridica':
                _emp = (r.get('cliente_empresa') or '').strip()
                if _emp: top_emp[_emp] += 1
        top_empresas = sorted(top_emp.items(), key=lambda x: x[1], reverse=True)[:8]

        _MASC = {'carlos','juan','diego','miguel','andrés','andres','pedro','luis','jorge',
                 'gabriel','rodrigo','francisco','felipe','pablo','mario','roberto','sergio',
                 'cristian','christian','nicolás','nicolas','alejandro','manuel','antonio',
                 'jose','josè','josé','daniel','matias','matías','sebastián','sebastian',
                 'gonzalo','mauricio','marcelo','ricardo','eduardo','ignacio','javier',
                 'victor','víctor','claudio','raul','raúl','alfredo','oscar','óscar',
                 'tomás','tomas','alex','alexis','ivan','iván','hugo','alberto','david'}
        _FEM  = {'maria','maría','carolina','andrea','claudia','patricia','alejandra',
                 'valentina','camila','javiera','paula','ana','rosa','carmen','lucia',
                 'lucía','fernanda','daniela','monica','mónica','paola','lorena','isabel',
                 'veronica','verónica','beatriz','sandra','laura','marcela','fabiola',
                 'natalia','jessica','pamela','viviana','pilar','francisca','constanza',
                 'nicole','yasna','ximena','soledad','teresa','angeles','ángeles',
                 'macarena','barbara','bárbara','sofia','sofía','elena','alicia','susana'}
        n_masc = n_fem = n_nd = 0
        for r in rows:
            if (r.get('cliente_tipo') or 'natural') == 'juridica': continue
            _nm = (r.get('cliente_nombre') or '').strip().lower().split()
            _primer = _nm[0] if _nm else ''
            if _primer in _MASC:   n_masc += 1
            elif _primer in _FEM:  n_fem  += 1
            else:                  n_nd   += 1

        rangos = {'< 1975 (50+)': 0, '1975-1995 (30-50)': 0, '> 1995 (< 30)': 0, 'No determinado': 0}
        for r in rows:
            if (r.get('cliente_tipo') or 'natural') == 'juridica': continue
            _rut_str = re.sub(r'[^0-9]', '', str(r.get('cliente_rut') or ''))
            try:
                _rut_n = int(_rut_str[:-1]) if len(_rut_str) > 1 else 0
                if   _rut_n < 1_000_000:  rangos['No determinado'] += 1
                elif _rut_n < 10_000_000: rangos['< 1975 (50+)']   += 1
                elif _rut_n < 15_000_000: rangos['1975-1995 (30-50)'] += 1
                else:                     rangos['> 1995 (< 30)']   += 1
            except Exception:
                rangos['No determinado'] += 1

        return {
            'total_ep': total_ep, 'total_monto': total_monto,
            'promedio_monto': promedio_monto, 'pipeline': pipeline,
            'autorizados': autorizados, 'borradores': borradores,
            'incompletos': incompletos, 'pct_conv': pct_conv,
            'delta_ep': delta_ep, 'delta_monto': delta_monto,
            'fechas': fechas_sorted, 'serie_montos': serie_montos,
            'serie_counts': serie_counts,
            'top_cats': top_cats, 'top_ej': top_ej,
            'top_productos': top_productos,
            'top_comunas': top_comunas, 'top_regiones': top_regiones,
            'n_natural': n_natural, 'n_juridica': n_juridica,
            'top_empresas': top_empresas,
            'n_masc': n_masc, 'n_fem': n_fem, 'n_nd': n_nd,
            'rangos_etarios': rangos,
        }
    except Exception:
        return None


def render_tab_dashboard(supabase, supabase_admin=None, **deps):
    supa_admin = supabase_admin or _supa_admin

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;700;800;900&display=swap');
    .dash-hdr {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #2563eb 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(37,99,235,0.25);
        position: relative; overflow: hidden;
    }
    .kpi-card {
        background: white; border-radius: 18px; padding: 22px 24px;
        border: 1px solid rgba(226,232,240,0.8);
        box-shadow: 0 4px 24px rgba(0,0,0,0.07);
        height: 100%; position: relative; overflow: hidden;
    }
    .kpi-card::after {
        content: ''; position: absolute; top: 0; left: 0; right: 0;
        height: 3px; border-radius: 18px 18px 0 0;
        background: linear-gradient(90deg, #2563eb, #06b6d4);
    }
    .kpi-label { font-size: 0.72rem; font-weight: 800; color: #94a3b8;
                 text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
    .kpi-value { font-size: 2.1rem; font-weight: 900; color: #0f172a;
                 font-family: 'Montserrat', sans-serif; line-height: 1; }
    .kpi-delta-pos { font-size: 0.75rem; font-weight: 700; color: #16a34a; margin-top: 8px; }
    .kpi-delta-neg { font-size: 0.75rem; font-weight: 700; color: #dc2626; margin-top: 8px; }
    .kpi-delta-neu { font-size: 0.75rem; font-weight: 600; color: #94a3b8; margin-top: 8px; }
    .section-title {
        font-size: 0.78rem; font-weight: 900; color: #1e293b;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 24px 0 14px; padding: 8px 16px;
        background: linear-gradient(90deg, rgba(37,99,235,0.07), transparent);
        border-left: 4px solid #2563eb; border-radius: 0 8px 8px 0;
    }
    .dash-panel {
        background: white; border-radius: 16px; padding: 20px 22px;
        border: 1px solid rgba(226,232,240,0.8);
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
    }
    .funnel-bar-wrap { background: #f1f5f9; border-radius: 10px; overflow: hidden; height: 10px; }
    .funnel-bar-inner { height: 10px; border-radius: 10px; }
    .cat-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
    .cat-name { font-size: 0.82rem; font-weight: 700; color: #334155; min-width: 130px; }
    .cat-bar-wrap { flex: 1; background: #f1f5f9; border-radius: 6px; height: 8px; overflow: hidden; }
    .cat-bar-inner { height: 8px; border-radius: 6px; background: linear-gradient(90deg,#2563eb,#06b6d4); }
    .cat-monto { font-size: 0.8rem; font-weight: 800; color: #3b82f6; min-width: 70px; text-align: right; }
    .ej-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
    .ej-pos { font-size: 1.2rem; min-width: 28px; }
    .ej-name { font-size: 0.85rem; font-weight: 700; color: #1e293b; flex: 1; }
    .ej-monto { font-size: 0.83rem; font-weight: 900; color: #2563eb; min-width: 80px; text-align: right; }
    </style>
    <div class="dash-hdr" style="display:flex!important;align-items:center!important;">
      """ + _pi("dashboard") + """
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Dashboard</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Resumen ejecutivo del rendimiento comercial en tiempo real.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _periodo_opciones = {
        "Este mes": "mes",
        "&#218;ltimos 3 meses": "3meses",
        "Este a&#241;o": "año",
        "Todos los tiempos": "todo"
    }
    _periodo_label = st.radio("Per&#237;odo", list(_periodo_opciones.keys()),
                               horizontal=True, index=0, key="dash_periodo",
                               label_visibility="collapsed")
    _periodo = _periodo_opciones[_periodo_label]

    with st.spinner("Cargando datos..."):
        _d = _cargar_datos_dashboard(_periodo)

    if not _d:
        st.error("No se pudieron cargar los datos del dashboard.")
        return

    def _fmt_monto(v):
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000:     return f"${v/1_000:.0f}K"
        return f"${v:,.0f}"

    def _delta_html(val, prefix=""):
        if val > 0:  return f'<div class="kpi-delta-pos">&#9650; {prefix}{abs(val):,} vs per&#237;odo ant.</div>'
        if val < 0:  return f'<div class="kpi-delta-neg">&#9660; {prefix}{abs(val):,} vs per&#237;odo ant.</div>'
        return f'<div class="kpi-delta-neu">&#8212; Sin cambio</div>'

    # ── KPIs ──
    st.markdown('<div class="section-title">M&#233;tricas clave</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    kpis = [
        (k1, "&#128188; Presupuestos", str(_d['total_ep']), _delta_html(_d['delta_ep'])),
        (k2, "&#128176; Monto total", _fmt_monto(_d['total_monto']), _delta_html(int(_d['delta_monto']), prefix="$")),
        (k3, "&#128200; Ticket promedio", _fmt_monto(_d['promedio_monto']), '<div class="kpi-delta-neu">por cotizaci&#243;n</div>'),
        (k4, "&#128260; Pipeline", _fmt_monto(_d['pipeline']), '<div class="kpi-delta-neu">borradores activos</div>'),
    ]
    for col, label, val, delta in kpis:
        with col:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-label">{label}</div>
              <div class="kpi-value">{val}</div>
              {delta}
            </div>""", unsafe_allow_html=True)

    st.markdown("")

    # ── Embudo de conversión ──
    st.markdown('<div class="section-title">Embudo de conversi&#243;n</div>', unsafe_allow_html=True)
    _total_ep = _d['total_ep'] or 1
    _funnel_data = [
        ("&#129001; Autorizados", _d['autorizados'], "#16a34a"),
        ("&#128992; Borradores",  _d['borradores'],  "#f59e0b"),
        ("&#128308; Incompletos", _d['incompletos'],  "#ef4444"),
    ]
    col_funnel, col_donut = st.columns([3, 2])
    with col_funnel:
        _funnel_html = '<div class="dash-panel"><div style="display:flex;justify-content:space-between;margin-bottom:20px;"><span style="font-size:0.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">Estado</span><span style="font-size:0.78rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">% del total</span></div>'
        for label_f, count_f, color_f in _funnel_data:
            pct_f = round((count_f / _total_ep) * 100) if _total_ep else 0
            _funnel_html += f'<div style="margin-bottom:16px;"><div style="display:flex;justify-content:space-between;margin-bottom:5px;"><span style="font-size:0.85rem;font-weight:700;color:#1e293b;">{label_f}</span><span style="font-size:0.85rem;font-weight:800;color:{color_f};">{count_f} &nbsp;({pct_f}%)</span></div><div class="funnel-bar-wrap"><div class="funnel-bar-inner" style="width:{pct_f}%;background:{color_f};opacity:0.85;"></div></div></div>'
        _funnel_html += "</div>"
        st.markdown(_funnel_html, unsafe_allow_html=True)

    with col_donut:
        with st.container(border=True):
            if _d['autorizados'] + _d['borradores'] + _d['incompletos'] > 0:
                import plotly.graph_objects as go
                _fig_donut = go.Figure(go.Pie(
                    labels=["Autorizados", "Borradores", "Incompletos"],
                    values=[_d['autorizados'], _d['borradores'], _d['incompletos']],
                    hole=0.62,
                    marker=dict(colors=["#16a34a", "#f59e0b", "#ef4444"], line=dict(color='white', width=3)),
                    textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} cotizaciones<br>%{percent}<extra></extra>',
                ))
                _fig_donut.add_annotation(
                    text=f"<b>{_d['pct_conv']}%</b><br><span style='font-size:10px'>conv.</span>",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=18, family='Montserrat'), xref="paper", yref="paper", align="center"
                )
                _fig_donut.update_layout(
                    showlegend=True, margin=dict(t=16, b=16, l=16, r=16),
                    height=240, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(font=dict(size=11, color='#475569'), orientation='h',
                                yanchor='bottom', y=-0.18, xanchor='center', x=0.5, bgcolor='rgba(0,0,0,0)'),
                )
                st.plotly_chart(_fig_donut, use_container_width=True, config={'displayModeBar': False})

    # ── Evolución temporal ──
    if _d['fechas']:
        st.markdown('<div class="section-title">Evoluci&#243;n de cotizaciones</div>', unsafe_allow_html=True)
        with st.container(border=True):
            import plotly.graph_objects as go
            _fig_line = go.Figure()
            _fig_line.add_trace(go.Bar(
                x=_d['fechas'], y=_d['serie_counts'], name='N&#186; EP',
                marker=dict(color='rgba(99,102,241,0.25)', line=dict(width=0)),
                yaxis='y2', hovertemplate='<b>%{x}</b><br>%{y} EP<extra></extra>',
            ))
            _fig_line.add_trace(go.Scatter(
                x=_d['fechas'], y=_d['serie_montos'], mode='lines+markers', name='Monto ($)',
                line=dict(color='#2563eb', width=3.5, shape='spline'),
                marker=dict(size=8, color='#2563eb', line=dict(color='white', width=2.5)),
                fill='tozeroy', fillcolor='rgba(37,99,235,0.07)',
                hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>',
            ))
            _fig_line.update_layout(
                height=320, margin=dict(t=20, b=40, l=70, r=60),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(248,250,252,0.6)',
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color='#64748b'), linecolor='#e2e8f0'),
                yaxis=dict(showgrid=True, gridcolor='rgba(226,232,240,0.6)', tickformat='$,.0f',
                           tickfont=dict(size=10, color='#64748b'), zeroline=False),
                yaxis2=dict(overlaying='y', side='right', showgrid=False, tickfont=dict(size=10, color='#94a3b8'), title=''),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
                            font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
                hovermode='x unified',
            )
            st.plotly_chart(_fig_line, use_container_width=True, config={'displayModeBar': False})

    # ── Top categorías + Top ejecutivos ──
    col_cats, col_ejs = st.columns(2)
    with col_cats:
        st.markdown('<div class="section-title">Top categor&#237;as</div>', unsafe_allow_html=True)
        if _d['top_cats']:
            _max_cat = _d['top_cats'][0][1] or 1
            html_cats = '<div class="dash-panel">'
            for cat_name, cat_val in _d['top_cats']:
                pct_c = round((cat_val / _max_cat) * 100)
                html_cats += f'<div class="cat-row"><div class="cat-name">{cat_name[:18]}</div><div class="cat-bar-wrap"><div class="cat-bar-inner" style="width:{pct_c}%;"></div></div><div class="cat-monto">{_fmt_monto(cat_val)}</div></div>'
            html_cats += '</div>'
            st.markdown(html_cats, unsafe_allow_html=True)
        else:
            st.info("Sin datos de categor&#237;as.")

    with col_ejs:
        st.markdown('<div class="section-title">Top ejecutivos</div>', unsafe_allow_html=True)
        if _d['top_ej']:
            _medallas_d = {0: "&#129351;", 1: "&#129352;", 2: "&#129353;", 3: "4&#65039;&#8419;", 4: "5&#65039;&#8419;"}
            html_ejs = '<div class="dash-panel">'
            for idx_e, (ej_name, ej_val) in enumerate(_d['top_ej']):
                html_ejs += f'<div class="ej-row"><div class="ej-pos">{_medallas_d.get(idx_e, str(idx_e+1))}</div><div class="ej-name">{ej_name[:22]}</div><div class="ej-monto">{_fmt_monto(ej_val)}</div></div>'
            html_ejs += '</div>'
            st.markdown(html_ejs, unsafe_allow_html=True)
        else:
            st.info("Sin datos de ejecutivos.")

    # ── Perfil de clientes ──
    st.markdown('<div class="section-title">&#128101; Perfil de Clientes</div>', unsafe_allow_html=True)
    _tc = _d.get('top_comunas', [])
    _tr = _d.get('top_regiones', [])
    _nn = _d.get('n_natural', 0)
    _nj = _d.get('n_juridica', 0)
    _nm = _d.get('n_masc', 0)
    _nf = _d.get('n_fem', 0)
    _nd_g = _d.get('n_nd', 0)
    _re = _d.get('rangos_etarios', {})
    _te = _d.get('top_empresas', [])

    import plotly.graph_objects as go
    _TMPL = dict(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family='Inter, sans-serif', color='#1e293b'),
        margin=dict(l=10, r=10, t=35, b=10),
    )

    col_com, col_reg = st.columns(2)
    with col_com:
        st.markdown('<div class="section-title">&#128205; Top Comunas</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _tc:
                _coms   = [x[0] for x in _tc]
                _vals_c = [x[1] for x in _tc]
                _fig_com = go.Figure(go.Bar(
                    x=_vals_c[::-1], y=_coms[::-1], orientation='h',
                    marker=dict(color=_vals_c[::-1], colorscale=[[0,'#bfdbfe'],[1,'#1d4ed8']], showscale=False),
                    text=[str(v) for v in _vals_c[::-1]], textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>',
                ))
                _fig_com.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                                       yaxis=dict(tickfont=dict(size=11)), height=320)
                st.plotly_chart(_fig_com, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos de comunas a&#250;n")

    with col_reg:
        st.markdown('<div class="section-title">&#128506;&#65039; Top Regiones</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _tr:
                _regs   = [x[0] for x in _tr]
                _vals_r = [x[1] for x in _tr]
                _fig_reg = go.Figure(go.Bar(
                    x=_vals_r[::-1], y=_regs[::-1], orientation='h',
                    marker=dict(color=_vals_r[::-1], colorscale=[[0,'#bbf7d0'],[1,'#15803d']], showscale=False),
                    text=[str(v) for v in _vals_r[::-1]], textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>',
                ))
                _fig_reg.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                                       yaxis=dict(tickfont=dict(size=11)), height=320)
                st.plotly_chart(_fig_reg, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos de regiones a&#250;n")

    col_tipo, col_gen, col_edad = st.columns(3)
    with col_tipo:
        st.markdown('<div class="section-title">&#127970; Tipo Cliente</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _total_tipo = _nn + _nj
            if _total_tipo > 0:
                _fig_tipo = go.Figure(go.Pie(
                    labels=['Persona Natural', 'Persona Jur&#237;dica'], values=[_nn, _nj], hole=0.55,
                    marker=dict(colors=['#3b82f6','#f59e0b'], line=dict(color='white', width=2)),
                    textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>',
                ))
                _fig_tipo.add_annotation(text=f"<b>{_total_tipo}</b><br>clientes",
                    x=0.5, y=0.5, showarrow=False, font=dict(size=13, color='#0f172a'), align='center')
                _fig_tipo.update_layout(**_TMPL, showlegend=True,
                    legend=dict(orientation='h', y=-0.15, font=dict(size=9)), height=280)
                st.plotly_chart(_fig_tipo, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos")

    with col_gen:
        st.markdown('<div class="section-title">&#9889; G&#233;nero Estimado</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _total_gen = _nm + _nf + _nd_g
            if _total_gen > 0:
                _lbl_g, _val_g, _col_g = [], [], []
                if _nm: _lbl_g.append('Masculino'); _val_g.append(_nm); _col_g.append('#3b82f6')
                if _nf: _lbl_g.append('Femenino');  _val_g.append(_nf); _col_g.append('#ec4899')
                if _nd_g: _lbl_g.append('No determinado'); _val_g.append(_nd_g); _col_g.append('#94a3b8')
                _fig_gen = go.Figure(go.Pie(
                    labels=_lbl_g, values=_val_g, hole=0.55,
                    marker=dict(colors=_col_g, line=dict(color='white', width=2)),
                    textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>',
                ))
                _fig_gen.add_annotation(text=f"<b>{_nm+_nf}</b><br>detect.",
                    x=0.5, y=0.5, showarrow=False, font=dict(size=13, color='#0f172a'), align='center')
                _fig_gen.update_layout(**_TMPL, showlegend=True,
                    legend=dict(orientation='h', y=-0.15, font=dict(size=9)), height=280)
                st.plotly_chart(_fig_gen, use_container_width=True, config={'displayModeBar': False})
                st.caption("&#9888;&#65039; Estimado por primer nombre")
            else:
                st.info("Sin datos")

    with col_edad:
        st.markdown('<div class="section-title">&#128197; Rango Etario Est.</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _re_f = {k: v for k, v in _re.items() if v > 0}
            if _re_f:
                _orden_e = ['< 1975 (50+)', '1975-1995 (30-50)', '> 1995 (< 30)', 'No determinado']
                _lbl_e = [k for k in _orden_e if k in _re_f]
                _val_e = [_re_f[k] for k in _lbl_e]
                _col_e = ['#7c3aed','#2563eb','#0891b2','#94a3b8'][:len(_lbl_e)]
                _fig_edad = go.Figure(go.Bar(
                    x=_val_e, y=_lbl_e, orientation='h',
                    marker=dict(color=_col_e, line=dict(color='white', width=1)),
                    text=_val_e, textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} clientes<extra></extra>',
                ))
                _fig_edad.update_layout(**_TMPL,
                    xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                    yaxis=dict(tickfont=dict(size=10), automargin=True), height=280)
                st.plotly_chart(_fig_edad, use_container_width=True, config={'displayModeBar': False})
                st.caption("&#9888;&#65039; Estimado por correlaci&#243;n RUT")
            else:
                st.info("Sin datos")

    # ── Top empresas ──
    if _te:
        st.markdown('<div class="section-title">&#127970; Top Empresas Cotizantes</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _emp_n = [x[0] for x in _te]
            _emp_v = [x[1] for x in _te]
            _fig_emp = go.Figure(go.Bar(
                x=_emp_v[::-1], y=_emp_n[::-1], orientation='h',
                marker=dict(color=_emp_v[::-1], colorscale=[[0,'#fde68a'],[1,'#d97706']], showscale=False),
                text=[str(v) for v in _emp_v[::-1]], textposition='outside',
                hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>',
            ))
            _fig_emp.update_layout(**_TMPL,
                xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
                yaxis=dict(tickfont=dict(size=11)), height=max(200, len(_te) * 38))
            st.plotly_chart(_fig_emp, use_container_width=True, config={'displayModeBar': False})

    # ── Top 30 productos ──
    st.markdown('<div class="section-title">&#127885; Top 30 productos m&#225;s cotizados</div>', unsafe_allow_html=True)
    if _d.get('top_productos'):
        _max_prod = _d['top_productos'][0][1] or 1
        _html_prods = '<div class="dash-panel">'
        _html_prods += '<div style="display:flex;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #f1f5f9;"><span style="font-size:0.72rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:24px;">#</span><span style="font-size:0.72rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;flex:1;">Producto</span><span style="font-size:0.72rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:55px;text-align:center;">Cant.</span><span style="font-size:0.72rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:100px;text-align:right;">Monto</span></div>'
        for idx_p, (prod_name, prod_val, prod_qty, prod_cat) in enumerate(_d['top_productos'], 1):
            pct_p    = round((prod_val / _max_prod) * 100)
            _color_p = "#3b82f6" if idx_p <= 3 else "#6366f1" if idx_p <= 10 else "#94a3b8"
            _bold_p  = "800" if idx_p <= 3 else "600"
            _html_prods += f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:9px;"><span style="font-size:0.78rem;font-weight:700;color:{_color_p};min-width:24px;text-align:center;">{idx_p}</span><div style="flex:1;min-width:0;"><div style="font-size:0.82rem;font-weight:{_bold_p};color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{prod_name}</div><div style="font-size:0.72rem;color:#94a3b8;margin-bottom:3px;">{prod_cat}</div><div style="background:#f1f5f9;border-radius:4px;height:5px;overflow:hidden;"><div style="width:{pct_p}%;height:5px;border-radius:4px;background:{_color_p};opacity:0.7;"></div></div></div><span style="font-size:0.8rem;font-weight:700;color:#475569;min-width:55px;text-align:center;">{prod_qty:,}</span><span style="font-size:0.82rem;font-weight:800;color:{_color_p};min-width:100px;text-align:right;">{_fmt_monto(prod_val)}</span></div>'
        _html_prods += '</div>'
        st.markdown(_html_prods, unsafe_allow_html=True)
    else:
        st.info("Sin datos de productos para el per&#237;odo seleccionado.")

    st.caption(f"Datos actualizados al abrir la pesta&#241;a &middot; Per&#237;odo: {_periodo_label}")
