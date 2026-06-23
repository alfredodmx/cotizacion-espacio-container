"""
Tab REPORTE BI — Inteligencia comercial, KPIs, ejecutivos, género, regiones, tiempos.
Código fuente original: app.py líneas 14366-14729
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.sidebar_nav import page_icon_svg as _pi


@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_reporte(rep_dias):
    try:
        from datetime import datetime as _dt, timedelta as _td
        _fecha_desde = (_dt.now() - _td(days=rep_dias)).strftime('%Y-%m-%d')
        _resp = _supa_admin.table('cotizaciones').select(
            'numero,fecha_creacion,fecha_modificacion,cliente_nombre,cliente_tipo,'
            'cliente_region,cliente_comuna,asesor_nombre,estado,total_total,'
            'config_margen,plano_url,contrato_generado,contrato_datos'
        ).gte('fecha_creacion', _fecha_desde).execute()
        return _resp.data or []
    except Exception:
        return []


def render_tab_reporte(supabase, supabase_admin=None, **deps):
    supa_admin = supabase_admin or _supa_admin

    if not st.session_state.get('modo_admin'):
        st.info("&#128274; Esta sección es solo para administradores.")
        return

    _rep_periodo = st.selectbox(
        "Per&#237;odo",
        ["&#218;ltimo mes", "&#218;ltimos 3 meses", "&#218;ltimos 6 meses", "Todo el tiempo"],
        key="rep_periodo", label_visibility="collapsed"
    )
    _rep_dias = {
        "&#218;ltimo mes": 30,
        "&#218;ltimos 3 meses": 90,
        "&#218;ltimos 6 meses": 180,
        "Todo el tiempo": 36500
    }[_rep_periodo]

    st.markdown(f"""
    <style>
    .hdr-reporte {{
        background: linear-gradient(135deg, #312e81 0%, #4f46e5 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(79,70,229,0.35);
        position: relative; overflow: hidden;
    }}
    .hdr-reporte::before {{
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 180px; height: 180px; border-radius: 50%;
        background: rgba(255,255,255,0.04); pointer-events: none;
    }}
    .hdr-reporte::after {{
        content: ''; position: absolute; bottom: -60px; right: 80px;
        width: 240px; height: 240px; border-radius: 50%;
        background: rgba(255,255,255,0.03); pointer-events: none;
    }}
    </style>
    <div class="hdr-reporte" style="display:flex!important;align-items:center!important;">
      """ + _pi("reporte") + """
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Reporte de Inteligencia Comercial</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Espacio Container House SpA &middot; Per&#237;odo: {_rep_periodo} &middot; Solo admin y root</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    from datetime import datetime as _dt, timedelta as _td
    import json as _json_rep
    _data_rep = _cargar_datos_reporte(_rep_dias)

    if not _data_rep:
        st.info("No hay datos para el per&#237;odo seleccionado.")
        return

    # ── Cálculos ──
    _total_cots  = len(_data_rep)
    _autorizadas = [r for r in _data_rep if 'autorizado' in (r.get('estado', '') or '').lower()]
    _borradores  = [r for r in _data_rep if 'borrador' in (r.get('estado', '') or '').lower()]
    _incompletas = [r for r in _data_rep if 'incompleto' in (r.get('estado', '') or '').lower()]
    _con_plano   = [r for r in _data_rep if r.get('plano_url')]
    _n_aut       = len(_autorizadas)
    _tasa_conv   = round(_n_aut / _total_cots * 100) if _total_cots else 0
    _monto_total = sum(r.get('total_total') or 0 for r in _autorizadas)

    def _fmt_m(v):
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000:     return f"${v/1_000:.0f}K"
        return f"${v:,.0f}"

    _tiempos = []
    for r in _autorizadas:
        try:
            from datetime import datetime as _dt2
            _fc = _dt2.fromisoformat(r['fecha_creacion'][:10])
            _fm = _dt2.fromisoformat(r['fecha_modificacion'][:10])
            _dias = (_fm - _fc).days
            if 0 <= _dias <= 365:
                _tiempos.append(_dias)
        except Exception:
            pass
    _prom_dias = round(sum(_tiempos) / len(_tiempos), 1) if _tiempos else 0
    _min_dias  = min(_tiempos) if _tiempos else 0
    _max_dias  = max(_tiempos) if _tiempos else 0
    _sin_aut_30 = sum(1 for r in _borradores + _incompletas
                      if r.get('fecha_creacion') and
                      (_dt.now() - _dt.fromisoformat(r['fecha_creacion'][:10])).days > 30)

    _masc = 0; _fem = 0
    for r in _data_rep:
        try:
            _cd = r.get('contrato_datos')
            if isinstance(_cd, str): _cd = _json_rep.loads(_cd)
            _trat = (_cd or {}).get('cli_tratamiento', '')
            if _trat in ('Don', 'Sr.'): _masc += 1
            elif _trat in ('Do&#241;a', 'Sra.'): _fem += 1
        except Exception:
            pass
    _total_gen = _masc + _fem or 1
    _pct_masc  = round(_masc / _total_gen * 100)
    _pct_fem   = 100 - _pct_masc

    _ej_data = {}
    for r in _data_rep:
        _ej = r.get('asesor_nombre') or 'Sin asignar'
        if _ej not in _ej_data:
            _ej_data[_ej] = {'total': 0, 'monto': 0, 'aut': 0}
        _ej_data[_ej]['total'] += 1
        if 'autorizado' in (r.get('estado', '') or '').lower():
            _ej_data[_ej]['aut'] += 1
            _ej_data[_ej]['monto'] += r.get('total_total') or 0
    _ej_sorted = sorted(_ej_data.items(), key=lambda x: x[1]['monto'], reverse=True)[:6]
    _max_monto_ej = max((v['monto'] for _, v in _ej_sorted), default=1) or 1

    _reg_data = {}
    for r in _data_rep:
        _reg = (r.get('cliente_region') or 'Sin regi&#243;n').replace('Regi&#243;n ', '').strip()
        _reg_data[_reg] = _reg_data.get(_reg, 0) + 1
    _reg_sorted = sorted(_reg_data.items(), key=lambda x: x[1], reverse=True)[:5]

    _n_natural  = sum(1 for r in _data_rep if (r.get('cliente_tipo') or '') == 'natural')
    _n_juridica = _total_cots - _n_natural
    _monto_nat  = sum(r.get('total_total') or 0 for r in _data_rep
                      if (r.get('cliente_tipo') or '') == 'natural'
                      and 'autorizado' in (r.get('estado', '') or '').lower())
    _monto_jur  = sum(r.get('total_total') or 0 for r in _data_rep
                      if (r.get('cliente_tipo') or '') == 'juridica'
                      and 'autorizado' in (r.get('estado', '') or '').lower())
    _aut_nat = sum(1 for r in _autorizadas if (r.get('cliente_tipo') or '') == 'natural')
    _aut_jur = sum(1 for r in _autorizadas if (r.get('cliente_tipo') or '') == 'juridica')
    _tick_nat = round(_monto_nat / max(1, _aut_nat))
    _tick_jur = round(_monto_jur / max(1, _aut_jur))

    # ── KPIs ──
    _k1, _k2, _k3, _k4 = st.columns(4)
    _kpi_style = """
    <div style="background:white;border-radius:12px;padding:16px 18px;
                border:1px solid #e2e8f0;height:100%;">
      <div style="font-size:11px;font-weight:700;color:#94a3b8;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:6px;">{label}</div>
      <div style="font-size:22px;font-weight:900;color:#0f172a;">{val}</div>
      <div style="font-size:11px;color:#94a3b8;margin-top:3px;">{sub}</div>
    </div>"""
    with _k1:
        st.markdown(_kpi_style.format(
            label="Total cotizaciones", val=_total_cots,
            sub=f"{_n_aut} autorizadas &middot; {len(_borradores)} borradores"),
            unsafe_allow_html=True)
    with _k2:
        st.markdown(_kpi_style.format(
            label="Monto total autorizado", val=_fmt_m(_monto_total),
            sub=f"Ticket prom: {_fmt_m(_monto_total//max(1,_n_aut))}"),
            unsafe_allow_html=True)
    with _k3:
        st.markdown(_kpi_style.format(
            label="Tasa de conversi&#243;n", val=f"{_tasa_conv}%",
            sub=f"{_n_aut} de {_total_cots} cotizaciones"),
            unsafe_allow_html=True)
    with _k4:
        st.markdown(_kpi_style.format(
            label="Tiempo promedio cierre", val=f"{_prom_dias} d&#237;as",
            sub=f"M&#237;n {_min_dias}d &middot; M&#225;x {_max_dias}d"),
            unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Ejecutivos + Género ──
    _col_ej, _col_gen = st.columns([1.4, 0.6])

    with _col_ej:
        st.markdown("<div style='background:white;border-radius:12px;padding:18px 20px;"
                    "border:1px solid #e2e8f0;'>", unsafe_allow_html=True)
        st.markdown("<div style='font-size:11px;font-weight:700;color:#64748b;"
                    "text-transform:uppercase;letter-spacing:0.06em;margin-bottom:14px;'>"
                    "Rendimiento por ejecutivo (monto autorizado)</div>", unsafe_allow_html=True)
        _colores_ej = ['#5b7cfa', '#8b5cf6', '#06b6d4', '#10b981', '#f97316', '#ef4444']
        for _idx, (_ej_nom, _ej_v) in enumerate(_ej_sorted):
            _pct_barra = round(_ej_v['monto'] / _max_monto_ej * 100)
            _tasa_ej   = round(_ej_v['aut'] / max(1, _ej_v['total']) * 100)
            _col_b     = _colores_ej[_idx % len(_colores_ej)]
            _nom_corto = _ej_nom[:18] + '&#8230;' if len(_ej_nom) > 18 else _ej_nom
            st.markdown(f"""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
              <div style="width:110px;font-size:11px;color:#374151;white-space:nowrap;
                          overflow:hidden;text-overflow:ellipsis;" title="{_ej_nom}">{_nom_corto}</div>
              <div style="flex:1;background:#f1f5f9;border-radius:99px;height:8px;overflow:hidden;">
                <div style="width:{_pct_barra}%;height:100%;border-radius:99px;background:{_col_b};"></div>
              </div>
              <div style="width:70px;text-align:right;font-size:11px;font-weight:700;color:#374151;">
                {_fmt_m(_ej_v['monto'])}</div>
              <div style="width:36px;text-align:right;font-size:10px;color:#94a3b8;">{_tasa_ej}%</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with _col_gen:
        _donut_masc = round(3.6 * _pct_masc)
        _donut_fem  = 360 - _donut_masc
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:18px 20px;
                    border:1px solid #e2e8f0;height:100%;">
          <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:14px;">G&#233;nero del cliente</div>
          <div style="display:flex;align-items:center;gap:16px;justify-content:center;">
            <svg width="90" height="90" viewBox="0 0 90 90">
              <circle cx="45" cy="45" r="35" fill="none" stroke="#5b7cfa" stroke-width="18"
                stroke-dasharray="{_donut_masc} {_donut_fem}" stroke-dashoffset="0"
                transform="rotate(-90 45 45)"/>
              <circle cx="45" cy="45" r="35" fill="none" stroke="#f472b6" stroke-width="18"
                stroke-dasharray="{_donut_fem} {_donut_masc}" stroke-dashoffset="-{_donut_masc}"
                transform="rotate(-90 45 45)"/>
              <text x="45" y="49" text-anchor="middle" font-size="13" font-weight="900"
                    fill="#0f172a">{_pct_masc}%</text>
            </svg>
            <div>
              <div style="display:flex;align-items:center;gap:6px;font-size:11px;
                          color:#374151;margin-bottom:5px;">
                <div style="width:10px;height:10px;border-radius:2px;background:#5b7cfa;"></div>
                Masc. {_pct_masc}%</div>
              <div style="display:flex;align-items:center;gap:6px;font-size:11px;color:#374151;">
                <div style="width:10px;height:10px;border-radius:2px;background:#f472b6;"></div>
                Fem. {_pct_fem}%</div>
              <div style="font-size:10px;color:#94a3b8;margin-top:8px;">
                Inferido desde<br>tratamiento contrato</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Estados + Tipo cliente + Tiempos ──
    _c31, _c32, _c33 = st.columns(3)

    with _c31:
        _est_items = [
            ('&#129001; Autorizadas', _n_aut),
            ('&#129000; Borradores', len(_borradores)),
            ('&#128308; Incompletas', len(_incompletas)),
            ('&#128208; Con plano', len(_con_plano)),
            ('&#128196; Con contrato', sum(1 for r in _data_rep if r.get('contrato_generado'))),
        ]
        _est_html = "".join(
            f'<div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">'
            f'<span style="font-size:11px;color:#64748b;">{lbl}</span>'
            f'<span style="font-size:12px;font-weight:700;color:#0f172a;">{cnt} ({round(cnt/max(1,_total_cots)*100)}%)</span></div>'
            for lbl, cnt in _est_items
        )
        st.markdown(
            '<div style="background:white;border-radius:12px;padding:18px 20px;border:1px solid #e2e8f0;">'
            '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;'
            'letter-spacing:0.06em;margin-bottom:12px;">Estado de cotizaciones</div>'
            + _est_html + '</div>', unsafe_allow_html=True)

    with _c32:
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:18px 20px;border:1px solid #e2e8f0;">
          <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:12px;">Tipo de cliente</div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#128100; Persona natural</span>
            <span style="font-size:12px;font-weight:700;color:#0f172a;">{_n_natural} ({round(_n_natural/max(1,_total_cots)*100)}%)</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#127970; Persona jur&#237;dica</span>
            <span style="font-size:12px;font-weight:700;color:#0f172a;">{_n_juridica} ({round(_n_juridica/max(1,_total_cots)*100)}%)</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#128176; Ticket prom. natural</span>
            <span style="font-size:12px;font-weight:700;color:#0f172a;">{_fmt_m(_tick_nat)}</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;">
            <span style="font-size:11px;color:#64748b;">&#128176; Ticket prom. jur&#237;dica</span>
            <span style="font-size:12px;font-weight:700;color:#0f172a;">{_fmt_m(_tick_jur)}</span>
          </div>
        </div>""", unsafe_allow_html=True)

    with _c33:
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:18px 20px;border:1px solid #e2e8f0;">
          <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:12px;">Tiempos de cierre</div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#9889; M&#225;s r&#225;pido</span>
            <span style="font-size:12px;font-weight:700;color:#10b981;">{_min_dias} d&#237;as</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#128034; M&#225;s lento</span>
            <span style="font-size:12px;font-weight:700;color:#ef4444;">{_max_dias} d&#237;as</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #f1f5f9;">
            <span style="font-size:11px;color:#64748b;">&#128202; Promedio</span>
            <span style="font-size:12px;font-weight:700;color:#0f172a;">{_prom_dias} d&#237;as</span>
          </div>
          <div style="display:flex;justify-content:space-between;padding:6px 0;">
            <span style="font-size:11px;color:#64748b;">&#9203; Sin autorizar +30d</span>
            <span style="font-size:12px;font-weight:700;color:#f97316;">{_sin_aut_30} cotizaciones</span>
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ── Top regiones ──
    if _reg_sorted:
        _max_reg = max(v for _, v in _reg_sorted) or 1
        _reg_html = "".join([f"""
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
          <div style="width:120px;font-size:11px;color:#374151;white-space:nowrap;
                      overflow:hidden;text-overflow:ellipsis;">{reg[:20]}</div>
          <div style="flex:1;background:#f1f5f9;border-radius:99px;height:7px;overflow:hidden;">
            <div style="width:{round(cnt/max(1,_max_reg)*100)}%;height:100%;
                        border-radius:99px;background:#5b7cfa;"></div>
          </div>
          <div style="width:40px;text-align:right;font-size:11px;font-weight:700;color:#374151;">{cnt}</div>
        </div>""" for reg, cnt in _reg_sorted])

        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:18px 20px;
                    border:1px solid #e2e8f0;margin-bottom:16px;">
          <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:14px;">Top regiones por cotizaciones</div>
          {_reg_html}
        </div>""", unsafe_allow_html=True)

    # ── Insights automáticos ──
    _insights = []
    if _ej_sorted:
        _ej_top = _ej_sorted[0]
        _ej_top_tasa = round(_ej_top[1]['aut'] / max(1, _ej_top[1]['total']) * 100)
        if _ej_top_tasa < 40:
            _insights.append(f"<b>{_ej_top[0]}</b> lidera en monto pero tiene tasa de conversi&#243;n de solo {_ej_top_tasa}%. Oportunidad de mejorar calidad sobre cantidad.")
    if _sin_aut_30 > 0:
        _insights.append(f"<b>{_sin_aut_30} cotizaciones</b> llevan m&#225;s de 30 d&#237;as sin autorizar. Revisi&#243;n urgente recomendada.")
    if _tick_jur > _tick_nat * 1.2 and _n_juridica < _n_natural * 0.3:
        _insights.append(f"El ticket promedio de clientes jur&#237;dicos ({_fmt_m(_tick_jur)}) es significativamente mayor. Aumentar foco en empresas puede mejorar rentabilidad.")
    if _pct_masc > 70 or _pct_fem > 70:
        _gen_dom = "masculino" if _pct_masc > 70 else "femenino"
        _pct_dom = _pct_masc if _pct_masc > 70 else _pct_fem
        _insights.append(f"El <b>{_pct_dom}% de los clientes son de g&#233;nero {_gen_dom}</b>. Considerar estrategias de marketing diferenciadas.")
    if _prom_dias > 15:
        _insights.append(f"El tiempo promedio de cierre es de <b>{_prom_dias} d&#237;as</b>. Revisar el proceso comercial para identificar cuellos de botella.")
    if not _insights:
        _insights.append("Todo dentro de rangos normales. Contin&#250;a monitoreando los indicadores clave.")

    _insights_html = "".join([f"""
    <div style="background:#eff6ff;border-left:3px solid #3b82f6;border-radius:0 8px 8px 0;
                padding:10px 14px;margin-bottom:8px;">
      <p style="font-size:11px;color:#1e40af;line-height:1.5;margin:0;">&#128161; {ins}</p>
    </div>""" for ins in _insights])

    st.markdown(f"""
    <div style="background:white;border-radius:12px;padding:18px 20px;border:1px solid #e2e8f0;">
      <div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:14px;">&#128161; Insights autom&#225;ticos</div>
      {_insights_html}
    </div>""", unsafe_allow_html=True)

    # ── Descarga CSV ──
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    import pandas as _pd_rep
    _df_dl = _pd_rep.DataFrame(_data_rep)
    _csv_rep = _df_dl.to_csv(index=False).encode('utf-8-sig')
    _dc1, _dc2, _dc3 = st.columns([2, 2, 2])
    with _dc2:
        st.download_button(
            "&#8595;&#65039; Descargar datos CSV", data=_csv_rep,
            file_name=f"reporte_bi_{_rep_periodo.replace(' ', '_')}.csv",
            mime="text/csv", use_container_width=True, key="dl_reporte_csv")
