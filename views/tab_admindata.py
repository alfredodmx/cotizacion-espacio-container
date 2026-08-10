"""
Tab ADMINISTRACIÓN DE DATOS — Eliminación permanente de presupuestos y archivos (solo root).

Rediseño 2026: la tabla de resultados usa el MISMO diseño que la tabla de
COTIZACIONES (HTML, header navy, badges de estado idénticos vía
calcular_estado_label + ESTADO_BADGE_COLORS/ICONS, fullscreen, búsqueda
client-side) pero con lógica de BORRADO: selección por checkboxes, doble
confirmación y auditoría (quién elimina, qué EPs, con fecha y hora) registrada
en el sistema (cotizacion_logs / SEGURIDAD). Iconos SVG + tipografía unificada.
"""
import streamlit as st
import streamlit.components.v1 as components
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header
from services.cotizacion_service import (
    calcular_estado_label, ESTADO_BADGE_COLORS, ESTADO_BADGE_ICONS)
from utils.security import log_evento_seguridad

# Estados reales (mismo orden que el embudo del dashboard/reporte).
_ESTADO_ORDER = [
    'PROYECTO TERMINADO', 'ADJUDICADO', 'AUTORIZADO CON PLANO', 'AUTORIZADO',
    'BORRADOR CON PLANO', 'BORRADOR', 'INCOMPLETO CON PLANO', 'INCOMPLETO', 'RECHAZADO',
]

_IC = {
    "filter": '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "list": '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/><line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/><line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
}


def _ic(name, color="#64748b", size=15, mr=8, valign=-2):
    _mr = f"margin-right:{mr}px;" if mr else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:{valign}px;{_mr}flex-shrink:0;">{_IC.get(name, "")}</svg>')


def _badge_html(label):
    bg, fg = ESTADO_BADGE_COLORS.get(label, ('#e2e8f0', '#334155'))
    _svg = (f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
            f'{ESTADO_BADGE_ICONS.get(label, "")}</svg>')
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'font-family:Montserrat,sans-serif;font-weight:800;font-size:10px;'
            f'letter-spacing:0.03em;text-transform:uppercase;border-radius:99px;'
            f'padding:5px 10px;white-space:nowrap;line-height:1;'
            f'background:{bg};color:{fg};">{_svg}<span>{label}</span></span>')


def _listar_usuarios_ej(supa_admin):
    try:
        _roots = [r.strip().lower() for r in st.secrets.get("ROOTS", "").split(",") if r.strip()]
        res = supa_admin.auth.admin.list_users()
        users = []
        for u in res:
            email = u.email or ""
            if email.lower() in _roots:
                continue
            meta = u.user_metadata or {}
            users.append({"id": str(u.id), "email": email,
                          "nombre": meta.get("nombre", email), "rol": meta.get("rol", "ejecutivo")})
        return users
    except Exception:
        return []


def _estado_de(r):
    return calcular_estado_label(
        r.get('cliente_nombre', ''), r.get('cliente_email', ''),
        r.get('asesor_nombre', ''), r.get('asesor_email', ''), r.get('asesor_telefono', ''),
        float(r.get('config_margen') or 0), bool((r.get('plano_url') or '').strip()),
        tiene_notariado=bool((r.get('contrato_notariado_url') or '').strip()),
        tiene_acta=bool((r.get('acta_url') or '').strip()),
        motivo_rechazo=r.get('motivo_rechazo', ''))


def render_tab_admindata(supabase, supabase_admin=None, **deps):
    supa_admin = supabase_admin or _supa_admin

    if not st.session_state.get('es_root'):
        st.info("Esta sección es solo para administradores root.", icon=":material/lock:")
        return

    render_page_header(
        "admindata",
        "Administraci&#243;n de datos",
        "Eliminaci&#243;n permanente de presupuestos y archivos &middot; solo disponible para root.",
    )

    st.markdown(
        "<style>"
        ".ad-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.05em;padding-bottom:8px;border-bottom:2px solid #e2e8f0;"
        "margin:22px 0 14px;display:flex;align-items:center;gap:9px;}"
        ".ad-danger{background:linear-gradient(90deg,rgba(220,38,38,0.08),transparent);border-left:4px solid #dc2626;"
        "border-radius:0 10px 10px 0;padding:11px 16px;display:flex;align-items:flex-start;gap:10px;margin:4px 0 18px;}"
        ".ad-danger p{margin:0;font-size:0.82rem;color:#7f1d1d;line-height:1.5;}"
        ".st-key-_ad_selcmd{position:absolute!important;left:-9999px!important;height:0!important;overflow:hidden!important;}"
        "</style>",
        unsafe_allow_html=True)

    st.markdown(
        f'<div class="ad-danger">{_ic("shield","#dc2626",18,0,0)}'
        '<p><b>Zona sensible.</b> La eliminación es permanente e irreversible: borra el presupuesto, sus archivos '
        '(planos, notariados, preview) y todos los datos asociados. Cada eliminación queda auditada en el sistema '
        '(quién, qué y cuándo).</p></div>',
        unsafe_allow_html=True)

    # ── Puente JS→Python: EPs seleccionados para eliminar (oculto) ──
    _selcmd = st.text_input("selcmd", key="_ad_selcmd", label_visibility="collapsed")
    if _selcmd and _selcmd != st.session_state.get('_ad_selcmd_last', ''):
        st.session_state['_ad_selcmd_last'] = _selcmd
        try:
            _payload = _selcmd.rsplit('|', 1)[0]
            _eps_sel = [e.strip() for e in _payload.split(',') if e.strip()]
        except Exception:
            _eps_sel = []
        if _eps_sel:
            st.session_state['ad_confirmar'] = True
            st.session_state['ad_eps_a_eliminar'] = _eps_sel

    # ── Filtros ──
    st.markdown(f'<div class="ad-sec">{_ic("filter","#0f172a",16,0)}Filtrar presupuestos</div>', unsafe_allow_html=True)
    _c1, _c2, _c3, _c4, _c5 = st.columns([1.5, 1.5, 1.4, 1.2, 0.6])
    with _c1:
        _ad_ep = st.text_input("N&#176; EP", placeholder="Ej: EP-12345", key="ad_ep", label_visibility="collapsed")
    with _c2:
        try:
            _ad_usu = _listar_usuarios_ej(supa_admin) or []
            _ad_ej_opts = ['Todos los ejecutivos'] + [u.get('nombre', '') for u in _ad_usu if u.get('nombre')]
        except Exception:
            _ad_ej_opts = ['Todos los ejecutivos']
        _ad_ej = st.selectbox("Ejecutivo", _ad_ej_opts, key="ad_ej", label_visibility="collapsed")
    with _c3:
        _ad_estado = st.selectbox("Estado", ['Todos los estados'] + _ESTADO_ORDER, key="ad_estado", label_visibility="collapsed")
    with _c4:
        _ad_fecha = st.date_input("Hasta fecha", value=None, key="ad_fecha", label_visibility="collapsed", format="DD/MM/YYYY")
    with _c5:
        _ad_buscar = st.button("Buscar", use_container_width=True, key="ad_buscar", icon=":material/search:")

    # ── Carga de datos ──
    if 'ad_results' not in st.session_state or _ad_buscar:
        try:
            _adq = supa_admin.table("cotizaciones").select(
                "numero,cliente_nombre,cliente_email,asesor_nombre,asesor_email,asesor_telefono,"
                "estado,fecha_creacion,total_total,config_margen,plano_url,"
                "contrato_notariado_url,acta_url,motivo_rechazo")
            if _ad_ep.strip():
                _adq = _adq.ilike("numero", f"%{_ad_ep.strip()}%")
            if _ad_ej != 'Todos los ejecutivos':
                _adq = _adq.eq("asesor_nombre", _ad_ej)
            if _ad_fecha:
                _adq = _adq.lte("fecha_creacion", str(_ad_fecha))
            _ad_res = _adq.order("fecha_creacion", desc=True).limit(500).execute()
            st.session_state['ad_results'] = _ad_res.data or []
        except Exception as _ade:
            st.error(f"Error: {_ade}")
            st.session_state['ad_results'] = []

    _ad_data = st.session_state.get('ad_results', [])
    # Estado real por fila + filtro por estado (post-carga).
    for _r in _ad_data:
        _r['_estado_real'] = _estado_de(_r)
    if _ad_estado != 'Todos los estados':
        _ad_data = [r for r in _ad_data if r.get('_estado_real') == _ad_estado]

    if not _ad_data:
        st.info("No se encontraron presupuestos con los filtros aplicados.")
    else:
        # ── Filas HTML (badges reales) ──
        def _he(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        def _ae(s): return _he(s).replace('"', '&quot;')

        _rows_html = ''
        for _r in _ad_data:
            _num = str(_r.get('numero', ''))
            _cli = str(_r.get('cliente_nombre') or '—')
            _ej = str(_r.get('asesor_nombre') or '—')
            _est = _r.get('_estado_real', 'INCOMPLETO')
            _fecha = (str(_r.get('fecha_creacion', '') or '')[:10]) or '—'
            _tot_raw = _r.get('total_total') or 0
            try:
                _tot_fmt = ('$' + '{:,.0f}'.format(float(_tot_raw)).replace(',', '.')) if _tot_raw else '—'
            except Exception:
                _tot_fmt = '—'
            _rows_html += (
                f'<tr data-ep="{_ae(_num)}" data-cli="{_ae(_cli.lower())}" data-ej="{_ae(_ej.lower())}" data-est="{_ae(_est.lower())}">'
                f'<td class="cchk"><input type="checkbox" class="ad-chk" data-ep="{_ae(_num)}"></td>'
                f'<td class="mono ep">{_he(_num)}</td>'
                f'<td class="cli">{_he(_cli)}</td>'
                f'<td>{_he(_ej)}</td>'
                f'<td>{_badge_html(_est)}</td>'
                f'<td class="mono muted">{_he(_fecha)}</td>'
                f'<td class="r mono bold">{_he(_tot_fmt)}</td>'
                f'</tr>')

        _n = len(_ad_data)
        _tbl_h = max(160, min(_n * 44 + 52, 520))
        _iframe_h = 52 + 10 + _tbl_h

        _tbl_html = _TABLE_TEMPLATE \
            .replace('IFRAMEHPX', str(_iframe_h) + 'px') \
            .replace('__NRES__', str(_n)) \
            .replace('ROWSPLACEHOLDER', _rows_html)
        components.html(_tbl_html, height=_iframe_h + 4, scrolling=False)

        # ── Confirmación (doble) ──
        if st.session_state.get('ad_confirmar') and st.session_state.get('ad_eps_a_eliminar'):
            _eps_el = st.session_state['ad_eps_a_eliminar']
            st.markdown(
                f'<div style="background:#fff1f2;border:1.5px solid #fca5a5;border-radius:14px;padding:16px 20px;margin-top:6px;">'
                f'<div style="display:flex;align-items:center;gap:10px;font-family:Montserrat,sans-serif;font-weight:800;'
                f'font-size:0.9rem;color:#b91c1c;text-transform:uppercase;letter-spacing:0.03em;">'
                f'{_ic("alert","#dc2626",18,0,0)}Confirmación requerida</div>'
                f'<p style="margin:8px 0 4px;font-size:0.85rem;color:#7f1d1d;line-height:1.5;">Estás a punto de eliminar '
                f'<b>{len(_eps_el)} presupuesto(s)</b> de forma <b>permanente e irreversible</b>, junto con todos sus '
                f'archivos y datos asociados.</p>'
                f'<div style="font-size:0.76rem;color:#991b1b;background:#fee2e2;border-radius:8px;padding:8px 11px;margin-top:8px;'
                f'font-family:monospace;word-break:break-word;">{" · ".join(_he(e) for e in _eps_el)}</div>'
                f'</div>', unsafe_allow_html=True)
            _cc1, _cc2 = st.columns(2)
            with _cc1:
                if st.button("Cancelar", use_container_width=True, key="ad_btn_cancelar", icon=":material/close:"):
                    st.session_state.pop('ad_confirmar', None)
                    st.session_state.pop('ad_eps_a_eliminar', None)
                    st.rerun()
            with _cc2:
                if st.button(f"Sí, eliminar definitivamente ({len(_eps_el)})", type="primary",
                             use_container_width=True, key="ad_btn_confirmar", icon=":material/delete_forever:"):
                    _errores, _eliminados = [], []
                    with st.spinner("Eliminando presupuestos y archivos..."):
                        for _ep_del in _eps_el:
                            try:
                                for _path in [f"planos/{_ep_del}/", f"notariados/{_ep_del}/",
                                              f"preview/preview_{_ep_del.replace('-', '_')}.pdf"]:
                                    try:
                                        _files = supa_admin.storage.from_("planos").list(_path.rstrip('/'))
                                        if _files:
                                            supa_admin.storage.from_("planos").remove([f"{_path}{f['name']}" for f in _files])
                                    except Exception:
                                        pass
                                supa_admin.table("cotizaciones").delete().eq("numero", _ep_del).execute()
                                _eliminados.append(_ep_del)
                            except Exception as _del_e:
                                _errores.append(f"{_ep_del}: {_del_e}")

                    # ── Auditoría: quién elimina, qué y cuándo ──
                    try:
                        from datetime import datetime as _dtn
                        try:
                            from zoneinfo import ZoneInfo
                            _now = _dtn.now(ZoneInfo('America/Santiago'))
                        except Exception:
                            _now = _dtn.now()
                        _autor_email = st.session_state.get('auth_email', '') or 'root'
                        log_evento_seguridad('eliminacion_datos', _autor_email, {
                            'autor_nombre': st.session_state.get('auth_nombre', '') or _autor_email,
                            'rol': st.session_state.get('rol_usuario', 'root'),
                            'fecha_hora_chile': _now.strftime('%d/%m/%Y %H:%M:%S'),
                            'eps_solicitados': _eps_el,
                            'eps_eliminados': _eliminados,
                            'total_eliminados': len(_eliminados),
                            'errores': _errores,
                        }, severidad='alta')
                    except Exception:
                        pass

                    st.session_state.pop('ad_confirmar', None)
                    st.session_state.pop('ad_eps_a_eliminar', None)
                    st.session_state.pop('ad_results', None)
                    if _eliminados:
                        st.success(f"Eliminados correctamente: {', '.join(_eliminados)}")
                    if _errores:
                        st.error(f"Errores: {'; '.join(_errores)}")
                    st.rerun()


# ── Tabla HTML (iframe autocontenido): mismo diseño que COTIZACIONES ──────────
_TABLE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Montserrat:wght@700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:IFRAMEHPX;overflow:hidden;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;background:transparent;}
#wrap{display:flex;flex-direction:column;height:100%;position:relative;}
#bar{display:flex;align-items:center;gap:8px;padding:2px 0 8px;flex-shrink:0;}
#search{flex:1;border:1.5px solid #e2e8f0;border-radius:8px;padding:8px 12px;font-size:0.84rem;
  font-family:inherit;outline:none;color:#1e293b;background:#f8fafc;transition:border-color .2s,box-shadow .2s;}
#search:focus{border-color:#5b7cfa;background:#fff;box-shadow:0 0 0 3px rgba(91,124,250,.1);}
#cnt{font-size:0.72rem;color:#94a3b8;white-space:nowrap;font-weight:700;min-width:70px;text-align:right;}
#del-btn{display:inline-flex;align-items:center;gap:7px;height:36px;padding:0 15px;border:none;border-radius:9px;
  background:#e2e8f0;color:#94a3b8;font-family:inherit;font-size:0.78rem;font-weight:800;letter-spacing:.02em;
  cursor:not-allowed;white-space:nowrap;transition:all .16s;flex-shrink:0;}
#del-btn.on{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;cursor:pointer;
  box-shadow:0 4px 14px rgba(220,38,38,.35);}
#del-btn.on:hover{filter:brightness(1.06);transform:translateY(-1px);}
#del-btn svg{width:15px;height:15px;}
#fsbtn{width:36px;height:36px;border:1px solid #e2e8f0;border-radius:9px;background:#fff;color:#475569;
  cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;padding:0;transition:all .15s;}
#fsbtn:hover{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(37,99,235,.3);}
#fsbtn svg{width:17px;height:17px;display:block;}
html.fs,html.fs body,html.fs #wrap{height:100vh!important;}
html.fs body{padding:12px 16px!important;}
#tbl-w{flex:1;overflow:auto;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.08);border:1px solid #e2e8f0;}
#tbl-w::-webkit-scrollbar{width:7px;height:7px;}
#tbl-w::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:4px;}
table{width:100%;border-collapse:separate;border-spacing:0;font-size:0.86rem;table-layout:auto;background:#fff;}
thead th{background:linear-gradient(135deg,#1e2447 0%,#2a3060 100%);color:#fff;font-weight:900;
  font-size:0.7rem;letter-spacing:0.07em;text-transform:uppercase;padding:11px 12px;white-space:nowrap;
  position:sticky;top:0;z-index:2;text-align:left;}
thead th.r{text-align:right;}
thead th.cchk{width:44px;text-align:center;padding:11px 8px;}
tbody td{padding:9px 12px;border-bottom:1px solid #f0f2f8;color:#3a4070;vertical-align:middle;white-space:nowrap;}
tbody td.cchk{text-align:center;padding:9px 8px;}
tbody tr:hover td{background:#f5f7ff;}
tbody tr.ad-sel td{background:#fff1f2!important;}
tbody tr.ad-sel td.cchk{box-shadow:inset 3px 0 0 #dc2626;}
tbody tr:last-child td{border-bottom:none;}
td.ep{font-weight:800;color:#1e293b;font-variant-numeric:tabular-nums;}
td.cli{font-weight:600;color:#1e293b;max-width:260px;overflow:hidden;text-overflow:ellipsis;}
td.r{text-align:right;}
td.bold{font-weight:800;color:#0f172a;}
td.muted{color:#64748b;}
.mono{font-variant-numeric:tabular-nums;}
input[type=checkbox]{width:17px;height:17px;accent-color:#dc2626;cursor:pointer;vertical-align:middle;}
#empty{display:none;padding:26px;text-align:center;color:#94a3b8;font-size:0.85rem;}
</style></head>
<body>
<div id="wrap">
  <div id="bar">
    <svg width="15" height="15" fill="none" stroke="#94a3b8" stroke-width="2.2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
    <input id="search" type="text" placeholder="Filtrar por EP, cliente, ejecutivo o estado..." autocomplete="off">
    <span id="cnt"></span>
    <button id="del-btn" type="button" disabled><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span id="del-lbl">Eliminar</span></button>
    <button id="fsbtn" type="button" title="Pantalla completa"></button>
  </div>
  <div id="tbl-w">
    <table>
      <thead><tr>
        <th class="cchk"><input type="checkbox" id="chk-all" title="Seleccionar todo"></th>
        <th>Presupuesto</th><th>Cliente</th><th>Ejecutivo</th><th>Estado</th><th>Creación</th><th class="r">Total proyecto</th>
      </tr></thead>
      <tbody>ROWSPLACEHOLDER</tbody>
    </table>
    <div id="empty">Sin resultados para la búsqueda.</div>
  </div>
</div>
<script>
(function(){
var NRES=__NRES__;
var doc=document;
function chks(){ return [].slice.call(doc.querySelectorAll('.ad-chk')); }
function visRows(){ return [].slice.call(doc.querySelectorAll('tbody tr[data-ep]')).filter(function(r){return r.style.display!=='none';}); }

function filterRows(){
  var q=(doc.getElementById('search').value||'').toLowerCase().trim();
  var rows=doc.querySelectorAll('tbody tr[data-ep]');var vis=0;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var hay=(r.getAttribute('data-ep')||'').toLowerCase()+' '+(r.getAttribute('data-cli')||'')+' '+(r.getAttribute('data-ej')||'')+' '+(r.getAttribute('data-est')||'');
    var show=(!q||hay.indexOf(q)>=0);
    r.style.display=show?'':'none';
    if(show)vis++;
  }
  var el=doc.getElementById('cnt'); if(el)el.textContent=vis+' de '+NRES;
  doc.getElementById('empty').style.display=vis?'none':'block';
  syncAll();
}

function syncRow(cb){ var tr=cb.closest('tr'); if(tr){ tr.classList.toggle('ad-sel', cb.checked); } }
function syncAll(){
  var vr=visRows(); var all=doc.getElementById('chk-all');
  var checked=vr.filter(function(r){var c=r.querySelector('.ad-chk');return c&&c.checked;}).length;
  if(all){ all.checked=vr.length>0&&checked===vr.length; all.indeterminate=checked>0&&checked<vr.length; }
  updateDel();
}
function updateDel(){
  var n=chks().filter(function(c){return c.checked;}).length;
  var b=doc.getElementById('del-btn'), l=doc.getElementById('del-lbl');
  if(n>0){ b.classList.add('on'); b.disabled=false; l.textContent='Eliminar seleccionados ('+n+')'; }
  else{ b.classList.remove('on'); b.disabled=true; l.textContent='Eliminar'; }
}

doc.getElementById('search').addEventListener('input',filterRows);
doc.addEventListener('change',function(e){
  var t=e.target;
  if(t.classList&&t.classList.contains('ad-chk')){ syncRow(t); syncAll(); }
  else if(t.id==='chk-all'){
    var on=t.checked; visRows().forEach(function(r){ var c=r.querySelector('.ad-chk'); if(c){ c.checked=on; syncRow(c);} });
    updateDel();
  }
});

/* ── Puente: enviar EPs seleccionados a Python (input oculto en el padre) ── */
function fireDelete(){
  var eps=chks().filter(function(c){return c.checked;}).map(function(c){return c.getAttribute('data-ep');});
  if(!eps.length) return;
  try{
    var W=window.parent, D=W.document;
    var inp=D.querySelector('.st-key-_ad_selcmd input'); if(!inp) return;
    var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
    inp.focus({preventScroll:true});
    setter.call(inp, eps.join(',')+'|'+Date.now());
    inp.dispatchEvent(new Event('input',{bubbles:true}));
    inp.dispatchEvent(new Event('change',{bubbles:true}));
    inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
    inp.blur();
  }catch(e){}
}
doc.getElementById('del-btn').addEventListener('click',function(){ if(!this.disabled) fireDelete(); });

/* ── Fullscreen del iframe (mismo mecanismo/z-index que COTIZACIONES) ── */
(function(){
  var P=window.parent, IFR=null;
  try{ IFR=window.frameElement; }catch(e){}
  if(!IFR){ try{ var ifs=P.document.querySelectorAll('iframe'); for(var i=0;i<ifs.length;i++){ if(ifs[i].contentWindow===window){ IFR=ifs[i]; break; } } }catch(e){} }
  var EXP='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/></svg>';
  var SHR='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14h6v6"/><path d="M20 10h-6V4"/><path d="M14 10l7-7"/><path d="M3 21l7-7"/></svg>';
  var btn=doc.getElementById('fsbtn');
  var PROPS=[['position','fixed'],['top','0'],['left','0'],['width','100vw'],['height','100vh'],['z-index','999999'],['border','none'],['border-radius','0'],['margin','0'],['background','#fff']];
  function isFS(){ return P._adFsActive===true; }
  function apply(){
    if(!IFR) return;
    for(var i=0;i<PROPS.length;i++) IFR.style.setProperty(PROPS[i][0], PROPS[i][1], 'important');
    doc.documentElement.classList.add('fs'); P._adFsActive=true;
    if(btn){ btn.innerHTML=SHR; btn.title='Salir de pantalla completa'; }
  }
  function remove(){
    if(IFR){ for(var i=0;i<PROPS.length;i++) IFR.style.removeProperty(PROPS[i][0]); }
    doc.documentElement.classList.remove('fs'); P._adFsActive=false;
    if(btn){ btn.innerHTML=EXP; btn.title='Pantalla completa'; }
  }
  function toggle(){ if(isFS()) remove(); else apply(); }
  if(btn){ btn.onclick=toggle; btn.innerHTML=isFS()?SHR:EXP; }
  if(isFS()) apply();
  doc.addEventListener('keydown',function(e){ if(e.key==='Escape'&&isFS()) remove(); });
  try{
    if(P._adFsEsc) P.document.removeEventListener('keydown', P._adFsEsc, true);
    P._adFsEsc=function(e){ if(e.key==='Escape'&&isFS()) remove(); };
    P.document.addEventListener('keydown', P._adFsEsc, true);
  }catch(e){}
})();

filterRows();
})();
</script>
</body></html>"""
