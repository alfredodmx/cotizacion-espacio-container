"""
Tab SALUD — Diagnóstico del sistema: Supabase, Storage, tablas, límites.
Código fuente original: app.py líneas 13636-13965 (with tab_salud)
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.sidebar_nav import page_icon_svg as _pi


def render_tab_salud(supabase, supabase_admin, supa_url, supa_key, **deps):
    if not st.session_state.get('es_root'):
        st.info("&#128274; Solo el root puede ver el estado del sistema.")
        return

    st.markdown("""
    <style>
    .hdr-salud {
        background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 60%, #2d2d2d 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
        position: relative; overflow: hidden;
    }
    .sys-card {
        background: white; border-radius: 16px; padding: 20px 24px;
        border: 1px solid rgba(226,232,240,0.8);
        box-shadow: 0 4px 20px rgba(0,0,0,0.06);
        margin-bottom: 16px;
    }
    .sys-card-title {
        font-size: 0.72rem; font-weight: 800; color: #94a3b8;
        text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 14px;
        display: flex; align-items: center; gap: 8px;
    }
    .sys-metric-val {
        font-size: 2rem; font-weight: 900; color: #0f172a;
        font-family: 'Montserrat', sans-serif; line-height: 1;
    }
    .sys-metric-sub { font-size: 0.78rem; color: #64748b; margin-top: 4px; }
    .sys-bar-wrap { background: #f1f5f9; border-radius: 8px; height: 12px; overflow: hidden; margin: 10px 0 6px; }
    .sys-bar-inner { height: 12px; border-radius: 8px; transition: width 0.5s ease; }
    .sys-bar-ok   { background: linear-gradient(90deg, #10b981, #34d399); }
    .sys-bar-warn { background: linear-gradient(90deg, #f59e0b, #fbbf24); }
    .sys-bar-crit { background: linear-gradient(90deg, #ef4444, #f97316); }
    .sys-pct-label { font-size: 0.75rem; font-weight: 700; display: flex; justify-content: space-between; }
    .sys-section-title {
        font-size: 0.78rem; font-weight: 900; color: #1e293b;
        text-transform: uppercase; letter-spacing: 0.1em;
        margin: 24px 0 14px; padding: 8px 16px;
        background: linear-gradient(90deg, rgba(15,15,15,0.07), transparent);
        border-left: 4px solid #374151; border-radius: 0 8px 8px 0;
    }
    .sys-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    .sys-table th {
        background: #f8fafc; color: #64748b; font-weight: 700;
        font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
        padding: 10px 14px; text-align: left; border-bottom: 2px solid #e2e8f0;
    }
    .sys-table td { padding: 10px 14px; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
    .sys-table tr:last-child td { border-bottom: none; }
    .sys-badge-ok   { background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.7rem; }
    .sys-badge-warn { background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.7rem; }
    .sys-badge-crit { background:#fee2e2; color:#dc2626; padding:2px 8px; border-radius:4px; font-weight:700; font-size:0.7rem; }
    </style>
    <div class="hdr-salud" style="display:flex!important;align-items:center!important;">
      """ + _pi("sistema") + """
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Salud del Sistema</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Monitoreo de capacidad y estado de Supabase &#8212; Plan Core (actualizado al cargar)</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    import datetime as _dt_sys

    with st.spinner("Consultando m&#233;tricas del sistema..."):
        _db_size_mb = 0
        _db_rows = {}
        try:
            import httpx as _hx
            _headers_sys = {
                "apikey": supa_key,
                "Authorization": f"Bearer {supa_key}",
                "Content-Type": "application/json",
            }
            _sql_resp = _hx.post(
                f"{supa_url}/rest/v1/rpc/get_db_stats",
                headers=_headers_sys, json={}, timeout=10
            )
            if _sql_resp.status_code == 200:
                _db_size_mb = round(_sql_resp.json() / (1024*1024), 2)
        except Exception:
            pass

        for _tbl in ['cotizaciones','cotizacion_logs','excel_versiones','registro_compras',
                     'catalogo_materiales','formulario_config','formulario_respuestas',
                     'formulario_preguntas','plantillas_contrato','usuarios']:
            try:
                _r = supabase_admin.table(_tbl).select('id', count='exact').execute()
                _db_rows[_tbl] = _r.count or 0
            except Exception:
                _db_rows[_tbl] = 0

        if _db_size_mb == 0:
            _total_filas = sum(_db_rows.values())
            _db_size_mb = round((_total_filas * 2048) / (1024*1024), 2)
            _db_size_estimado = True
        else:
            _db_size_estimado = False

        _storage_info = {}
        try:
            _n_planos = supabase_admin.table('cotizaciones').select('numero',count='exact').not_.is_('plano_url','null').execute().count or 0
            _storage_info['planos'] = {'archivos':_n_planos,'mb':round((_n_planos*500*1024)/(1024*1024),2),'estimado':True}
        except Exception:
            _storage_info['planos'] = {'archivos':0,'mb':0,'estimado':True}
        try:
            _n_excel = supabase_admin.table('excel_versiones').select('id',count='exact').execute().count or 0
            _n_jsons = supabase_admin.table('cotizaciones').select('numero',count='exact').eq('estado','Autorizado').execute().count or 0
            _storage_info['config'] = {'archivos':_n_excel+_n_jsons,'mb':round((_n_excel*2*1024+_n_jsons*5)/1024,2),'estimado':True}
        except Exception:
            _storage_info['config'] = {'archivos':0,'mb':0,'estimado':True}
        try:
            _n_fimg = supabase_admin.table('catalogo_materiales').select('id',count='exact').not_.is_('imagen_url','null').neq('imagen_url','').execute().count or 0
            _storage_info['formulario-imagenes'] = {'archivos':_n_fimg,'mb':round((_n_fimg*200*1024)/(1024*1024),2),'estimado':True}
        except Exception:
            _storage_info['formulario-imagenes'] = {'archivos':0,'mb':0,'estimado':True}
        try:
            _n_cont = supabase_admin.table('cotizaciones').select('id',count='exact').not_.is_('contrato_url','null').neq('contrato_url','').execute().count or 0
            _storage_info['contratos'] = {'archivos':_n_cont,'mb':round((_n_cont*300*1024)/(1024*1024),2),'estimado':True}
        except Exception:
            _storage_info['contratos'] = {'archivos':0,'mb':0,'estimado':True}
        try:
            _n_fact = supabase_admin.table('registro_compras').select('id',count='exact').execute().count or 0
            _storage_info['facturas'] = {'archivos':_n_fact,'mb':round((_n_fact*150*1024)/(1024*1024),2),'estimado':True}
        except Exception:
            _storage_info['facturas'] = {'archivos':0,'mb':0,'estimado':True}

        _storage_total_mb = sum(v['mb'] for v in _storage_info.values())
        _egress_gb        = st.session_state.get('_sys_egress_gb', 0.0)
        _egress_cached_gb = st.session_state.get('_sys_egress_cached_gb', 0.0)
        _mau              = st.session_state.get('_sys_mau', 0)

    _DB_LIMIT_MB      = 500
    _STG_LIMIT_MB     = 1024
    _EGRESS_LIMIT_GB  = 5.0
    _EGRESS_C_LIMIT_GB= 5.0
    _MAU_LIMIT        = 50000

    _db_pct  = min(round((_db_size_mb / _DB_LIMIT_MB) * 100, 1), 100) if _db_size_mb > 0 else 0
    _stg_pct = min(round((_storage_total_mb / _STG_LIMIT_MB) * 100, 1), 100)
    _eg_pct  = min(round((_egress_gb / _EGRESS_LIMIT_GB) * 100, 1), 200) if _egress_gb > 0 else 0
    _egc_pct = min(round((_egress_cached_gb / _EGRESS_C_LIMIT_GB) * 100, 1), 200) if _egress_cached_gb > 0 else 0

    def _bar_class(pct):
        if pct >= 80: return "sys-bar-crit"
        if pct >= 50: return "sys-bar-warn"
        return "sys-bar-ok"

    def _badge(pct):
        if pct >= 100: return "sys-badge-crit", "&#128308; Excedido"
        if pct >= 80:  return "sys-badge-crit", "&#9888;&#65039; Cr&#237;tico"
        if pct >= 50:  return "sys-badge-warn", "&#128993; Atenci&#243;n"
        return "sys-badge-ok", "&#128994; Normal"

    st.markdown('<div class="sys-section-title">&#9999;&#65039; Actualizar m&#233;tricas de Supabase</div>', unsafe_allow_html=True)
    st.caption('Copia los valores desde Supabase Dashboard &#8594; Usage')
    _sys_c1, _sys_c2, _sys_c3, _sys_c4 = st.columns(4)
    with _sys_c1:
        _eg_input = st.number_input('&#128228; Egress (GB)', min_value=0.0, max_value=999.0, step=0.1,
            value=float(st.session_state.get('_sys_egress_gb', 0.0)), key='_inp_egress')
        st.session_state['_sys_egress_gb'] = _eg_input
    with _sys_c2:
        _egc_input = st.number_input('&#9889; Cached Egress (GB)', min_value=0.0, max_value=999.0, step=0.1,
            value=float(st.session_state.get('_sys_egress_cached_gb', 0.0)), key='_inp_egress_cached')
        st.session_state['_sys_egress_cached_gb'] = _egc_input
    with _sys_c3:
        _mau_input = st.number_input('&#128101; MAU', min_value=0, max_value=50000, step=1,
            value=int(st.session_state.get('_sys_mau', 0)), key='_inp_mau')
        st.session_state['_sys_mau'] = _mau_input
    with _sys_c4:
        st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if st.button('&#128260; Actualizar', key='_btn_sys_update', use_container_width=True):
            st.session_state['_sys_egress_gb']        = _eg_input
            st.session_state['_sys_egress_cached_gb'] = _egc_input
            st.session_state['_sys_mau']              = _mau_input
            st.rerun()

    if _egress_cached_gb > 0 and _egc_pct >= 100:
        st.error(f"&#128680; **Cached Egress excedido:** {_egress_cached_gb} GB / {_EGRESS_C_LIMIT_GB} GB ({_egc_pct:.0f}%). Supabase puede restringir el servicio.")
    elif _egress_cached_gb > 0 and _egc_pct >= 80:
        st.warning(f"&#9888;&#65039; **Cached Egress casi al l&#237;mite:** {_egress_cached_gb} GB de {_EGRESS_C_LIMIT_GB} GB usados ({_egc_pct:.0f}%).")

    st.markdown('<div class="sys-section-title">&#128190; Almacenamiento</div>', unsafe_allow_html=True)
    _col_db, _col_stg = st.columns(2)
    with _col_db:
        _bc, _bl = _badge(_db_pct)
        _est_txt = "&nbsp;&middot; <i style='color:#94a3b8;font-size:0.7rem'>estimado</i>" if _db_size_estimado else ""
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#128441;&#65039; Base de datos PostgreSQL</div>
          <div class="sys-metric-val">{_db_size_mb} MB</div>
          <div class="sys-metric-sub">L&#237;mite: {_DB_LIMIT_MB} MB &nbsp;&middot;&nbsp; <span class="{_bc}">{_bl}</span>{_est_txt}</div>
          <div class="sys-bar-wrap"><div class="sys-bar-inner {_bar_class(_db_pct)}" style="width:{_db_pct}%"></div></div>
          <div class="sys-pct-label"><span>{_db_pct}% usado</span><span>{round(_DB_LIMIT_MB - _db_size_mb, 1)} MB libres</span></div>
        </div>
        """, unsafe_allow_html=True)
    with _col_stg:
        _bc2, _bl2 = _badge(_stg_pct)
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#128230; Storage (todos los buckets)</div>
          <div class="sys-metric-val">{round(_storage_total_mb, 1)} MB</div>
          <div class="sys-metric-sub">L&#237;mite: {_STG_LIMIT_MB} MB (1 GB) &nbsp;&middot;&nbsp; <span class="{_bc2}">{_bl2}</span></div>
          <div class="sys-bar-wrap"><div class="sys-bar-inner {_bar_class(_stg_pct)}" style="width:{_stg_pct}%"></div></div>
          <div class="sys-pct-label"><span>{_stg_pct}% usado</span><span>{round(_STG_LIMIT_MB - _storage_total_mb, 1)} MB libres</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="sys-section-title">&#128225; Ancho de banda (Egress)</div>', unsafe_allow_html=True)
    _col_eg, _col_egc = st.columns(2)
    with _col_eg:
        _bc3, _bl3 = _badge(_eg_pct)
        _eg_display = f"{_egress_gb} GB" if _egress_gb > 0 else "Sin datos"
        _eg_bar = f"<div class='sys-bar-wrap'><div class='sys-bar-inner {_bar_class(_eg_pct)}' style='width:{min(_eg_pct,100)}%'></div></div><div class='sys-pct-label'><span>{_eg_pct}% usado</span></div>" if _egress_gb > 0 else "<div style='color:#94a3b8;font-size:0.78rem;margin-top:8px;'>API de uso no disponible &#8212; ver en Supabase Dashboard</div>"
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#128228; Egress directo</div>
          <div class="sys-metric-val">{_eg_display}</div>
          <div class="sys-metric-sub">L&#237;mite: {_EGRESS_LIMIT_GB} GB / mes &nbsp;&middot;&nbsp; <span class="{_bc3}">{_bl3}</span></div>
          {_eg_bar}
        </div>
        """, unsafe_allow_html=True)
    with _col_egc:
        _bc4, _bl4 = _badge(_egc_pct)
        _egc_display = f"{_egress_cached_gb} GB" if _egress_cached_gb > 0 else "Sin datos"
        _egc_bar = f"<div class='sys-bar-wrap'><div class='sys-bar-inner {_bar_class(_egc_pct)}' style='width:{min(_egc_pct,100)}%'></div></div><div class='sys-pct-label'><span>{_egc_pct}% usado</span></div>" if _egress_cached_gb > 0 else "<div style='color:#94a3b8;font-size:0.78rem;margin-top:8px;'>Ver en Supabase Dashboard &#8594; Usage</div>"
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#9889; Cached Egress <span style="font-size:0.65rem;background:#fee2e2;color:#dc2626;padding:1px 6px;border-radius:4px;margin-left:4px;">CR&#205;TICO</span></div>
          <div class="sys-metric-val" style="color:{'#dc2626' if _egc_pct >= 100 else 'inherit'}">{_egc_display}</div>
          <div class="sys-metric-sub">L&#237;mite: {_EGRESS_C_LIMIT_GB} GB / mes &nbsp;&middot;&nbsp; <span class="{_bc4}">{_bl4}</span></div>
          {_egc_bar}
        </div>
        """, unsafe_allow_html=True)

    _col_tbl, _col_bkt = st.columns(2)
    with _col_tbl:
        st.markdown('<div class="sys-section-title">&#128203; Filas por tabla</div>', unsafe_allow_html=True)
        _tbl_html = '<div class="sys-card"><table class="sys-table"><thead><tr><th>Tabla</th><th>Filas</th></tr></thead><tbody>'
        _tbl_labels = {
            'cotizaciones':'&#128196; Cotizaciones','cotizacion_logs':'&#128221; Logs auditor&#237;a',
            'excel_versiones':'&#128202; Versiones Excel','registro_compras':'&#128722; Registro compras',
            'catalogo_materiales':'&#127991;&#65039; Cat&#225;logo materiales','formulario_config':'&#9881;&#65039; Config formularios',
            'formulario_respuestas':'&#9989; Respuestas clientes','formulario_preguntas':'&#10067; Preguntas formulario',
            'plantillas_contrato':'&#128196; Plantillas contrato','usuarios':'&#128101; Usuarios',
        }
        for _t, _cnt in _db_rows.items():
            _lbl = _tbl_labels.get(_t, _t)
            _tbl_html += f'<tr><td>{_lbl}</td><td><b>{_cnt:,}</b></td></tr>'
        _tbl_html += '</tbody></table></div>'
        st.markdown(_tbl_html, unsafe_allow_html=True)

    with _col_bkt:
        st.markdown('<div class="sys-section-title">&#128193; Archivos por bucket</div>', unsafe_allow_html=True)
        _bkt_html = '<div class="sys-card"><table class="sys-table"><thead><tr><th>Bucket</th><th>Archivos</th><th>Tama&#241;o</th></tr></thead><tbody>'
        _bkt_icons = {
            'planos':'&#128208; planos','config':'&#9881;&#65039; config',
            'formulario-imagenes':'&#128444;&#65039; formulario-imagenes',
            'contratos':'&#128196; contratos','facturas':'&#129534; facturas',
        }
        for _bn, _bv in _storage_info.items():
            _blbl = _bkt_icons.get(_bn, f'&#128193; {_bn}')
            _est = ' <i style="color:#94a3b8;font-size:0.7rem">(est.)</i>' if _bv.get('estimado') else ''
            _bkt_html += f'<tr><td>{_blbl}</td><td>{_bv["archivos"]}</td><td>{_bv["mb"]} MB{_est}</td></tr>'
        _bkt_html += '</tbody></table></div>'
        st.markdown(_bkt_html, unsafe_allow_html=True)

    st.markdown('<div class="sys-section-title">&#128101; Usuarios y conexiones</div>', unsafe_allow_html=True)
    _col_mau, _col_lim = st.columns(2)
    with _col_mau:
        _mau_val = st.session_state.get('_sys_mau', 0)
        _mau_pct = min(round((_mau_val / _MAU_LIMIT) * 100, 1), 100) if _mau_val > 0 else 0
        _bc5, _bl5 = _badge(_mau_pct)
        _mau_bar = f"<div class='sys-bar-wrap'><div class='sys-bar-inner {_bar_class(_mau_pct)}' style='width:{_mau_pct}%'></div></div>" if _mau_val > 0 else ""
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#128100; Monthly Active Users (MAU)</div>
          <div class="sys-metric-val">{_mau_val if _mau_val > 0 else '&#8212;'}</div>
          <div class="sys-metric-sub">L&#237;mite: {_MAU_LIMIT:,} MAU &nbsp;&middot;&nbsp; <span class="{'sys-badge-ok' if _mau_val == 0 else _bc5}">{'&#128994; Normal' if _mau_val == 0 else _bl5}</span></div>
          {_mau_bar}
        </div>
        """, unsafe_allow_html=True)
    with _col_lim:
        _bc_db  = _badge(_db_pct)
        _bc_stg = _badge(_stg_pct)
        _bc_eg  = _badge(_eg_pct)
        _bc_egc = _badge(_egc_pct)
        st.markdown(f"""
        <div class="sys-card">
          <div class="sys-card-title">&#128202; Resumen plan Free</div>
          <table class="sys-table" style="margin-top:4px;">
            <tr><td>&#128441;&#65039; BD</td><td>{_DB_LIMIT_MB} MB</td><td><span class="{_bc_db[0]}">{_bc_db[1]}</span></td></tr>
            <tr><td>&#128230; Storage</td><td>1 GB</td><td><span class="{_bc_stg[0]}">{_bc_stg[1]}</span></td></tr>
            <tr><td>&#128228; Egress</td><td>5 GB/mes</td><td><span class="{_bc_eg[0]}">{_bc_eg[1]}</span></td></tr>
            <tr><td>&#9889; Cached</td><td>5 GB/mes</td><td><span class="{_bc_egc[0]}">{_bc_egc[1]}</span></td></tr>
            <tr><td>&#128101; MAU</td><td>50,000</td><td><span class="sys-badge-ok">&#128994; Normal</span></td></tr>
            <tr><td>&#128564; Pausa</td><td>7 d&#237;as sin uso</td><td><span class="sys-badge-warn">&#128993; Atenci&#243;n</span></td></tr>
          </table>
        </div>
        """, unsafe_allow_html=True)

    _now_cl = _dt_sys.datetime.now(_dt_sys.timezone(_dt_sys.timedelta(hours=-3)))
    st.caption(f"&#128336; Actualizado: {_now_cl.strftime('%d/%m/%Y %H:%M')} hora Chile")
    st.info("&#128161; **Para reducir el Cached Egress:** Los `@st.cache_data` ya agregados reducen queries repetidas.")

    if st.button("&#128260; Actualizar m&#233;tricas", key="btn_refresh_salud"):
        st.rerun()
