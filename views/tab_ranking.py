"""
Tab RANKING — Ranking de ejecutivos, métricas de cotizaciones.
Código fuente original: app.py líneas 16794-17078 (with tab7)
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin


def _cargar_ranking(supa_admin, periodo='mes'):
    try:
        from datetime import datetime as _dt
        _inicio = None
        if periodo == 'mes':
            _inicio = _dt.now().replace(day=1).strftime('%Y-%m-%d')
        resp = supa_admin.rpc('get_ranking_data', {'fecha_inicio': _inicio}).execute()
        resp_data = resp.data if resp.data else []
        if not resp_data:
            return []
        asesores = {}
        for row in resp_data:
            nombre = row.get('asesor_nombre') or 'Sin asignar'
            if nombre not in asesores:
                asesores[nombre] = {
                    'nombre': nombre,
                    'total_presupuestos': 0,
                    'total_generado': 0.0,
                    'autorizados': 0,
                    'borradores': 0,
                    'incompletos': 0,
                }
            a = asesores[nombre]
            a['total_presupuestos'] += 1
            a['total_generado'] += float(row.get('total_total') or 0)
            margen   = float(row.get('config_margen') or 0)
            datos_ok = all([row.get('cliente_nombre'), row.get('cliente_email')])
            asesor_ok = any([row.get('asesor_nombre'), row.get('asesor_email'), row.get('asesor_telefono')])
            if margen > 0 and datos_ok and asesor_ok:
                a['autorizados'] += 1
            elif datos_ok and asesor_ok:
                a['borradores'] += 1
            else:
                a['incompletos'] += 1
        ranking = []
        for nombre, a in asesores.items():
            n = a['total_presupuestos']
            a['promedio']       = a['total_generado'] / n if n > 0 else 0
            a['pct_autorizado'] = round((a['autorizados'] / n) * 100) if n > 0 else 0
            max_total = max((x['total_generado'] for x in asesores.values()), default=1) or 1
            max_n     = max((x['total_presupuestos'] for x in asesores.values()), default=1) or 1
            a['score'] = round(
                (a['total_generado'] / max_total) * 60 +
                (a['pct_autorizado'] / 100) * 25 +
                (a['total_presupuestos'] / max_n) * 15
            )
            ranking.append(a)
        ranking.sort(key=lambda x: x['score'], reverse=True)
        return ranking
    except Exception:
        return []


def render_tab_ranking(supabase, **deps):
    supa_admin = deps.get('supabase_admin', _supa_admin)

    st.markdown("""
    <style>
    .hdr7 {
        background: linear-gradient(135deg, #78350f 0%, #d97706 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(217,119,6,0.25);
        position: relative; overflow: hidden;
    }
    .rank-chart-title {
        font-size: 0.78rem; font-weight: 800; color: #64748b;
        text-transform: uppercase; letter-spacing: 0.08em;
        margin-bottom: 14px; padding-bottom: 12px;
        border-bottom: 2px solid #f1f5f9;
    }
    .rank-kpi-label { font-size: 0.72rem; font-weight: 700; color: #94a3b8;
                      text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 8px; }
    .rank-kpi-value { font-size: 2rem; font-weight: 900; color: #0f172a;
                      font-family: 'Montserrat', sans-serif; line-height: 1; }
    .rank-section {
        font-size: 0.75rem; font-weight: 900; color: #1e293b;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 24px 0 14px; padding: 8px 16px;
        background: linear-gradient(90deg, rgba(217,119,6,0.1), transparent);
        border-left: 4px solid #d97706; border-radius: 0 8px 8px 0;
    }
    </style>
    <div class="hdr7" style="display:flex!important;align-items:center!important;">
      <span style="font-size:2.8rem;line-height:1;flex-shrink:0;">&#127942;</span>
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Ranking de Ejecutivos</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Desempe&#241;o del equipo de ventas &#8212; este mes.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.spinner("Cargando ranking..."):
        _ranking = _cargar_ranking(supa_admin, periodo='mes')

    if not _ranking:
        st.info("No hay cotizaciones registradas este mes.")
    else:
        import plotly.graph_objects as go
        from datetime import datetime as _dt

        def _fmt_r(v):
            if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
            if v >= 1_000:     return f"${v/1_000:.0f}K"
            return f"${v:,.0f}"

        _mes_actual   = _dt.now().strftime("%B %Y").capitalize()
        _total_mes    = sum(a['total_generado'] for a in _ranking)
        _total_presup = sum(a['total_presupuestos'] for a in _ranking)
        _total_autori = sum(a['autorizados'] for a in _ranking)
        _pct_g        = round((_total_autori / _total_presup) * 100) if _total_presup else 0
        _n_ejs        = len(_ranking)
        _h_bar        = max(280, 52 * _n_ejs)
        _nombres      = [a['nombre'].split()[0] for a in _ranking]
        _colores      = ["#f59e0b" if i==0 else "#94a3b8" if i==1 else "#cd7c3a" if i==2 else "#cbd5e1"
                         for i in range(_n_ejs)]

        st.markdown(f'<div class="rank-section">&#128197; {_mes_actual} &middot; {_n_ejs} ejecutivo{"s" if _n_ejs!=1 else ""}</div>', unsafe_allow_html=True)
        rk1, rk2, rk3, rk4 = st.columns(4)
        for _col, _lbl, _val in [
            (rk1, "&#128176; Total generado", _fmt_r(_total_mes)),
            (rk2, "&#128203; Presupuestos",   str(_total_presup)),
            (rk3, "&#128994; Autorizados",    str(_total_autori)),
            (rk4, "&#128200; % Conversi&#243;n", f"{_pct_g}%"),
        ]:
            with _col:
                with st.container(border=True):
                    st.markdown(f'''<div style="text-align:center;padding:8px 4px;">
                      <div class="rank-kpi-label">{_lbl}</div>
                      <div class="rank-kpi-value">{_val}</div>
                    </div>''', unsafe_allow_html=True)

        st.markdown("")

        st.markdown('<div class="rank-section">&#128176; Monto generado por ejecutivo</div>', unsafe_allow_html=True)
        _fig_bar = go.Figure(go.Bar(
            y=_nombres[::-1],
            x=[a['total_generado'] for a in _ranking[::-1]],
            orientation='h',
            marker_color=_colores[::-1],
            marker_line_width=0,
            text=[_fmt_r(a['total_generado']) for a in _ranking[::-1]],
            textposition='outside',
            textfont=dict(size=11, family='Montserrat', color='#1e293b'),
            hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>',
        ))
        _fig_bar.update_layout(
            height=_h_bar, margin=dict(t=10, b=10, l=10, r=90),
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=True, gridcolor='#f1f5f9', visible=False),
            yaxis=dict(showgrid=False, tickfont=dict(size=12, family='Montserrat')),
            showlegend=False,
        )
        with st.container(border=True):
            st.markdown('<div class="rank-chart-title">&#128176; Monto total generado</div>', unsafe_allow_html=True)
            st.plotly_chart(_fig_bar, use_container_width=True, config={'displayModeBar': False})

        st.markdown('<div class="rank-section">&#128202; Presupuestos y conversi&#243;n por ejecutivo</div>', unsafe_allow_html=True)
        col_bars, col_conv = st.columns([3, 2])

        with col_bars:
            _fig_combo = go.Figure()
            _fig_combo.add_trace(go.Bar(
                name='Total EP', y=_nombres[::-1],
                x=[a['total_presupuestos'] for a in _ranking[::-1]],
                orientation='h',
                marker_color='rgba(99,102,241,0.75)',
                text=[a['total_presupuestos'] for a in _ranking[::-1]],
                textposition='auto',
                hovertemplate='<b>%{y}</b><br>%{x} EP<extra></extra>',
            ))
            _fig_combo.add_trace(go.Bar(
                name='Autorizados', y=_nombres[::-1],
                x=[a['autorizados'] for a in _ranking[::-1]],
                orientation='h',
                marker_color='rgba(22,163,74,0.8)',
                text=[a['autorizados'] for a in _ranking[::-1]],
                textposition='auto',
                hovertemplate='<b>%{y}</b><br>%{x} autorizados<extra></extra>',
            ))
            _fig_combo.update_layout(
                barmode='group', height=_h_bar,
                margin=dict(t=10, b=10, l=10, r=20),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', tickfont=dict(size=10)),
                yaxis=dict(showgrid=False, tickfont=dict(size=11)),
                legend=dict(orientation='h', yanchor='bottom', y=1.02,
                            xanchor='right', x=1, font=dict(size=11)),
            )
            with st.container(border=True):
                st.markdown('<div class="rank-chart-title">&#128203; EP totales vs autorizados</div>', unsafe_allow_html=True)
                st.plotly_chart(_fig_combo, use_container_width=True, config={'displayModeBar': False})

        with col_conv:
            _fig_conv = go.Figure(go.Bar(
                y=_nombres[::-1],
                x=[a['pct_autorizado'] for a in _ranking[::-1]],
                orientation='h',
                marker=dict(
                    color=[a['pct_autorizado'] for a in _ranking[::-1]],
                    colorscale=[[0,'#ef4444'],[0.5,'#f59e0b'],[1,'#16a34a']],
                    showscale=False,
                ),
                text=[f"{a['pct_autorizado']}%" for a in _ranking[::-1]],
                textposition='outside',
                hovertemplate='<b>%{y}</b><br>%{text}<extra></extra>',
            ))
            _fig_conv.update_layout(
                height=_h_bar, margin=dict(t=10, b=10, l=10, r=50),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=True, gridcolor='#f1f5f9', range=[0,115],
                           ticksuffix='%', tickfont=dict(size=10)),
                yaxis=dict(showgrid=False, tickfont=dict(size=11)),
            )
            with st.container(border=True):
                st.markdown('<div class="rank-chart-title">&#128200; % Conversi&#243;n</div>', unsafe_allow_html=True)
                st.plotly_chart(_fig_conv, use_container_width=True, config={'displayModeBar': False})

        st.markdown('<div class="rank-section">&#127894; Detalle por ejecutivo</div>', unsafe_allow_html=True)
        _medallas = {1:"&#127945;", 2:"&#129352;", 3:"&#129353;"}
        _border_colors = {1:'#f59e0b', 2:'#94a3b8', 3:'#b45309'}

        for i, ej in enumerate(_ranking, 1):
            total_fmt = _fmt_r(ej['total_generado'])
            prom_fmt  = _fmt_r(ej['promedio'])
            score     = ej['score']
            _pct_aut  = ej['pct_autorizado']
            _pc_color = "#16a34a" if _pct_aut >= 50 else "#f59e0b" if _pct_aut >= 25 else "#ef4444"

            _r = 45
            _cx, _cy = 55, 55
            _circum = 2 * 3.14159 * _r
            _dash = _circum * _pct_aut / 100
            _gap  = _circum - _dash
            _svg_donut = (
                f'<svg width="110" height="110" viewBox="0 0 110 110" xmlns="http://www.w3.org/2000/svg">' +
                f'<circle cx="{_cx}" cy="{_cy}" r="{_r}" fill="none" stroke="#f1f5f9" stroke-width="14"/>' +
                f'<circle cx="{_cx}" cy="{_cy}" r="{_r}" fill="none" stroke="{_pc_color}" stroke-width="14" ' +
                f'stroke-dasharray="{_dash:.1f} {_gap:.1f}" stroke-dashoffset="{_circum/4:.1f}" stroke-linecap="round"/>' +
                f'<text x="{_cx}" y="{_cy-4}" text-anchor="middle" font-size="14" font-weight="bold" fill="{_pc_color}">{_pct_aut}%</text>' +
                f'<text x="{_cx}" y="{_cy+12}" text-anchor="middle" font-size="9" fill="#94a3b8">Conv.</text>' +
                f'</svg>'
            )
            _border_color = _border_colors.get(i, '#e2e8f0')
            _medal = _medallas.get(i, f"#{i}")
            st.markdown(f'''
            <div style="display:flex;align-items:center;gap:16px;padding:12px 16px;
                background:#fff;border-radius:16px;border:1px solid #e2e8f0;
                border-left:5px solid {_border_color};
                box-shadow:0 4px 20px rgba(0,0,0,0.07);">
              <span style="font-size:1.8rem;flex-shrink:0;">{_medal}</span>
              <div style="flex:1;min-width:160px;">
                <div style="font-size:1rem;font-weight:800;color:#1e293b;font-family:'Montserrat',sans-serif;">{ej['nombre']}</div>
                <div style="background:#f1f5f9;border-radius:8px;height:10px;margin:6px 0 2px;overflow:hidden;">
                  <div style="width:{score}%;height:10px;border-radius:8px;background:linear-gradient(90deg,#f59e0b,#d97706);"></div>
                </div>
                <div style="font-size:0.72rem;color:#94a3b8;">Score {score}/100</div>
              </div>
              <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;">
                <div style="text-align:center;"><div style="font-size:1.2rem;font-weight:800;color:#0f172a;">{ej['total_presupuestos']}</div><div style="font-size:0.7rem;color:#64748b;">EP</div></div>
                <div style="text-align:center;"><div style="font-size:1.2rem;font-weight:800;color:#0f172a;">{total_fmt}</div><div style="font-size:0.7rem;color:#64748b;">Total</div></div>
                <div style="text-align:center;"><div style="font-size:1.2rem;font-weight:800;color:#0f172a;">{prom_fmt}</div><div style="font-size:0.7rem;color:#64748b;">Promedio</div></div>
                <div style="text-align:center;"><div style="font-size:1.2rem;font-weight:800;color:#16a34a;">{ej['autorizados']}</div><div style="font-size:0.7rem;color:#64748b;">&#128994; Auth.</div></div>
                <div style="text-align:center;"><div style="font-size:1.2rem;font-weight:800;color:#f59e0b;">{ej['borradores']}</div><div style="font-size:0.7rem;color:#64748b;">&#128993; Borr.</div></div>
              </div>
              <div style="flex-shrink:0;">{_svg_donut}</div>
            </div>
            ''', unsafe_allow_html=True)
            st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)
