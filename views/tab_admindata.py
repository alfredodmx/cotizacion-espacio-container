"""
Tab ADMINISTRACIÓN DE DATOS — Eliminación permanente de presupuestos y archivos (solo root).

Rediseño 2026: la tabla de resultados usa el MISMO diseño que la tabla de
COTIZACIONES (HTML, header navy, badges de estado idénticos, fullscreen,
búsqueda). Los filtros están ESTANDARIZADOS con COTIZACIONES:
  - Estado → badge bar con los mismos colores e iconos (_BADGE_STYLE/_BADGE_SVG).
  - Ejecutivo → dropdown con foto del asesor (mismo diseño .ecsb-ej*).
Ambos filtran 100% client-side (sin reruns). Lógica de BORRADO: selección por
checkboxes, doble confirmación y auditoría (quién elimina, qué EPs, fecha y hora)
registrada en el sistema (cotizacion_logs / SEGURIDAD).
"""
import json
from collections import Counter
import streamlit as st
import streamlit.components.v1 as components
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL
from views.layout import render_page_header
from utils.avatars import fetch_foto_map
from services.cotizacion_service import (
    calcular_estado_label, ESTADO_BADGE_COLORS, ESTADO_BADGE_ICONS)
from utils.security import log_evento_seguridad

# ── Estados: mismo estilo de badge-filtro que la tabla de COTIZACIONES ────────
# (bg, fg, active). Copiado 1:1 de tab_historial._BADGE_STYLE para estandarizar.
_BADGE_STYLE = {
    'TODOS': ('#ede9fe', '#6d28d9', '#6d28d9'),
    'PROYECTO TERMINADO': ('#ede9fe', '#7c3aed', '#5b21b6'),
    'ADJUDICADO': ('#dbeafe', '#1d4ed8', '#1e40af'),
    'AUTORIZADO CON PLANO': ('#dcfce7', '#15803d', '#166534'),
    'AUTORIZADO': ('#dcfce7', '#15803d', '#166534'),
    'BORRADOR CON PLANO': ('#ffedd5', '#c2410c', '#9a3412'),
    'BORRADOR': ('#fef9c3', '#854d0e', '#713f12'),
    'INCOMPLETO CON PLANO': ('#fee2e2', '#dc2626', '#991b1b'),
    'INCOMPLETO': ('#fee2e2', '#dc2626', '#991b1b'),
    'RECHAZADO': ('#fee2e2', '#b91c1c', '#7f1d1d'),
}
_BADGE_SVG = {
    'TODOS':                '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    'PROYECTO TERMINADO':   '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    'ADJUDICADO':           '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    'AUTORIZADO CON PLANO': '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    'AUTORIZADO':           '<path d="M20 6 9 17l-5-5"/>',
    'BORRADOR CON PLANO':   '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><polyline points="14 2 14 8 20 8"/><path d="M10.4 12.6a2 2 0 1 1 3 3L8 21l-4 1 1-4z"/>',
    'BORRADOR':             '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    'INCOMPLETO CON PLANO': '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    'INCOMPLETO':           '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    'RECHAZADO':            '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
}
_BADGE_ORDER = [
    ('TODOS', 'Todos'), ('PROYECTO TERMINADO', 'terminados'),
    ('ADJUDICADO', 'adjudicados'), ('AUTORIZADO CON PLANO', 'aut. c/plano'),
    ('AUTORIZADO', 'autorizados'), ('BORRADOR CON PLANO', 'borrador c/plano'),
    ('BORRADOR', 'borrador'), ('INCOMPLETO CON PLANO', 'incompleto c/plano'),
    ('INCOMPLETO', 'incompletos'), ('RECHAZADO', 'rechazados'),
]

_IC = {
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
}


def _ic(name, color="#64748b", size=15, mr=8, valign=-2):
    _mr = f"margin-right:{mr}px;" if mr else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:{valign}px;{_mr}flex-shrink:0;">{_IC.get(name, "")}</svg>')


def _he(s): return str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def _ae(s): return _he(s).replace('"', '&quot;')


def _badge_cell(label):
    """Badge de la columna ESTADO (mismo markup que crear_badge_estado)."""
    bg, fg = ESTADO_BADGE_COLORS.get(label, ('#e2e8f0', '#334155'))
    _svg = (f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
            f'{ESTADO_BADGE_ICONS.get(label, "")}</svg>')
    return (f'<span style="display:inline-flex;align-items:center;gap:5px;'
            f'font-family:Montserrat,sans-serif;font-weight:800;font-size:10px;'
            f'letter-spacing:0.03em;text-transform:uppercase;border-radius:99px;'
            f'padding:5px 10px;white-space:nowrap;line-height:1;'
            f'background:{bg};color:{fg};">{_svg}<span>{label}</span></span>')


def _badge_svg_bar(_p):
    return ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
            + _p + '</svg>')


def _build_badge_bar(cnts, n_total, ini='TODOS'):
    parts = [f'<div class="ec-badgebar" id="ad-badgebar" data-init="{ini}">']
    for bk, blbl in _BADGE_ORDER:
        if bk != 'TODOS' and not cnts.get(bk, 0):
            continue
        bg, fg, act = _BADGE_STYLE.get(bk, ('#e2e8f0', '#334155', '#334155'))
        cnt = n_total if bk == 'TODOS' else cnts.get(bk, 0)
        _st = (f'background:{act};color:#fff;box-shadow:0 0 0 2px {act};' if bk == ini
               else f'background:{bg};color:{fg};')
        parts.append(
            f'<button class="ec-badge" data-filter="{bk}" data-bg="{bg}" data-fg="{fg}" '
            f'data-act="{act}" style="{_st}">{_badge_svg_bar(_BADGE_SVG.get(bk, ""))}'
            f'<span>{blbl} ({cnt})</span></button>')
    parts.append('<button class="ec-badge ec-refresh" data-refresh="1" title="Actualizar" '
                 'style="background:#fff;color:#475569;box-shadow:0 0 0 1px #e2e8f0;">'
                 + _badge_svg_bar('<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
                                  '<path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
                                  '<path d="M8 16H3v5"/>') + '</button>')
    parts.append('</div>')
    return ''.join(parts)


def _ej_av(foto, nombre, extra=''):
    if foto:
        return f'<span class="ecsb-av {extra}"><img src="{_ae(foto)}"></span>'
    ini = ''.join(p[0] for p in (nombre or '').split()[:2]).upper() or 'EC'
    return f'<span class="ecsb-av ecsb-av-ini {extra}">{_he(ini)}</span>'


_ALL_AV = ('<span class="ecsb-av ecsb-av-all"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" '
           'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
           '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></span>')


def _build_ej_menu(ejs):
    opts = [f'<button class="ecsb-ejopt" data-ej="" data-name="Todos los ejecutivos">{_ALL_AV}'
            '<span>Todos los ejecutivos</span></button>']
    for e in ejs:
        nm = e['nombre']
        opts.append(f'<button class="ecsb-ejopt" data-ej="{_ae(nm.lower())}" data-name="{_ae(nm)}">'
                    f'{_ej_av(e["foto"], nm)}<span>{_he(nm)}</span></button>')
    return ''.join(opts)


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

    if st.session_state.get('rol_usuario', 'ejecutivo') not in ('root', 'admin'):
        st.info("Esta sección es solo para administradores (admin y root).", icon=":material/lock:")
        return

    render_page_header(
        "admindata",
        "Administraci&#243;n de datos",
        "Eliminaci&#243;n permanente de presupuestos y archivos &middot; solo disponible para admin y root.",
    )

    st.markdown(
        "<style>"
        ".ad-danger{background:linear-gradient(90deg,rgba(220,38,38,0.08),transparent);border-left:4px solid #dc2626;"
        "border-radius:0 10px 10px 0;padding:11px 16px;display:flex;align-items:flex-start;gap:10px;margin:4px 0 16px;}"
        ".ad-danger p{margin:0;font-size:0.82rem;color:#7f1d1d;line-height:1.5;}"
        ".st-key-_ad_selcmd,.st-key-ad_refresh{position:absolute!important;left:-9999px!important;height:0!important;overflow:hidden!important;}"
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
            _eps_sel = [e.strip() for e in _selcmd.rsplit('|', 1)[0].split(',') if e.strip()]
        except Exception:
            _eps_sel = []
        if _eps_sel:
            st.session_state['ad_confirmar'] = True
            st.session_state['ad_eps_a_eliminar'] = _eps_sel

    # ── Refresh (lo dispara el badge circular del bar, como en COTIZACIONES) ──
    if st.button("refresh", key="ad_refresh"):
        st.session_state.pop('ad_results', None)
        st.rerun()

    # ── Carga de datos (todo, filtrado 100% client-side como COTIZACIONES) ──
    if 'ad_results' not in st.session_state:
        try:
            _ad_res = supa_admin.table("cotizaciones").select(
                "numero,cliente_nombre,cliente_email,asesor_nombre,asesor_email,asesor_telefono,"
                "estado,fecha_creacion,total_total,config_margen,plano_url,"
                "contrato_notariado_url,acta_url,motivo_rechazo"
            ).order("fecha_creacion", desc=True).limit(500).execute()
            st.session_state['ad_results'] = _ad_res.data or []
        except Exception as _ade:
            st.error(f"Error: {_ade}")
            st.session_state['ad_results'] = []

    _ad_data = st.session_state.get('ad_results', [])
    for _r in _ad_data:
        _r['_estado_real'] = _estado_de(_r)

    if not _ad_data:
        st.info("No hay presupuestos para mostrar.")
        return

    # Foto de asesores + lista única de ejecutivos presentes (con avatar).
    try:
        _foto_map = fetch_foto_map(SUPABASE_URL)
    except Exception:
        _foto_map = {}
    _ej_seen, _ejs = set(), []
    for _r in _ad_data:
        _nm = (_r.get('asesor_nombre') or '').strip()
        if not _nm or _nm.lower() in _ej_seen:
            continue
        _ej_seen.add(_nm.lower())
        _mail = (_r.get('asesor_email') or '').strip().lower()
        _ejs.append({'nombre': _nm, 'foto': _foto_map.get(_mail, '') if _mail else ''})
    _ejs.sort(key=lambda x: x['nombre'].lower())

    _cnts = Counter(_r['_estado_real'] for _r in _ad_data)
    _n = len(_ad_data)

    # ── Filas HTML (badges reales + atributos para filtrar) ──
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
            f'<tr data-ep="{_ae(_num)}" data-cli="{_ae(_cli.lower())}" data-ej="{_ae(_ej.lower())}" '
            f'data-estkey="{_ae(_est)}">'
            f'<td class="cchk"><input type="checkbox" class="ad-chk" data-ep="{_ae(_num)}"></td>'
            f'<td class="mono ep">{_he(_num)}</td>'
            f'<td class="cli">{_he(_cli)}</td>'
            f'<td>{_he(_ej)}</td>'
            f'<td>{_badge_cell(_est)}</td>'
            f'<td class="mono muted">{_he(_fecha)}</td>'
            f'<td class="r mono bold">{_he(_tot_fmt)}</td>'
            f'</tr>')

    _tbl_h = max(260, min(_n * 44 + 54, 520))
    _iframe_h = 108 + _tbl_h

    _tbl_html = _TABLE_TEMPLATE \
        .replace('IFRAMEHPX', str(_iframe_h) + 'px') \
        .replace('__NRES__', str(_n)) \
        .replace('__BADGES__', _build_badge_bar(_cnts, _n)) \
        .replace('__EJMENU__', _build_ej_menu(_ejs)) \
        .replace('ROWSPLACEHOLDER', _rows_html)
    components.html(_tbl_html, height=_iframe_h + 4, scrolling=False)

    # ── Confirmación (doble) + auditoría ──
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

                # Auditoría: quién elimina, qué y cuándo.
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


# ── Tabla HTML (iframe autocontenido): mismo diseño y filtros que COTIZACIONES ─
_TABLE_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Montserrat:wght@700;800;900&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:IFRAMEHPX;overflow:hidden;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;background:transparent;}
#wrap{display:flex;flex-direction:column;height:100%;position:relative;}

/* ── Badge bar de estados (idéntico a COTIZACIONES) ── */
.ec-badgebar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:0 0 9px;font-family:Montserrat,sans-serif;}
.ec-badge{display:inline-flex;align-items:center;gap:6px;font-family:Montserrat,sans-serif;font-weight:800;
  font-size:11px;letter-spacing:0.03em;text-transform:uppercase;border:none;border-radius:99px;padding:6px 13px;
  cursor:pointer;white-space:nowrap;transition:all .12s;line-height:1;}
.ec-badge:hover{filter:brightness(0.96);}
.ec-badge.ec-refresh{padding:7px 10px;}

/* ── Dropdown de ejecutivo con foto (idéntico a COTIZACIONES) ── */
.ecsb-ejwrap{position:relative;flex:0 0 auto;width:260px;}
.ecsb-ejchip{width:100%;height:42px;border:1px solid #e2e8f0;border-radius:11px;background:#f8fafc;cursor:pointer;
  display:flex;align-items:center;gap:10px;padding:0 11px;font-family:Montserrat,sans-serif;}
.ecsb-ejchip:hover{border-color:#cbd5e1;}
.ecsb-ejchip-body{display:flex;align-items:center;gap:10px;flex:1;min-width:0;}
.ecsb-ejph{font-weight:700;font-size:12.5px;color:#64748b;}
.ecsb-ejname{font-weight:800;font-size:13px;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.ecsb-chev{color:#94a3b8;flex-shrink:0;margin-left:auto;}
.ecsb-av{width:30px;height:30px;border-radius:50%;flex:0 0 auto;overflow:hidden;display:flex;align-items:center;
  justify-content:center;box-shadow:0 3px 9px rgba(5,12,28,.22);background:#fff;}
.ecsb-av img{width:100%;height:100%;object-fit:cover;display:block;}
.ecsb-av-ini{background:linear-gradient(135deg,#0f3460,#1a5276);color:#fff;font-weight:900;font-size:12px;}
.ecsb-av-all{background:#e2e8f0;color:#64748b;box-shadow:none;}
.ecsb-ejmenu{position:absolute;top:calc(100% + 6px);left:0;right:0;max-height:240px;overflow-y:auto;
  background:#fff;border:1px solid #e2e8f0;border-radius:13px;box-shadow:0 14px 40px rgba(15,23,42,.18);
  z-index:99999;padding:6px;display:none;}
.ecsb-ejmenu.open{display:block;}
.ecsb-ejopt{width:100%;display:flex;align-items:center;gap:10px;background:none;border:none;cursor:pointer;
  padding:7px 9px;border-radius:9px;font-family:Montserrat,sans-serif;font-weight:700;font-size:13px;color:#0f172a;text-align:left;}
.ecsb-ejopt:hover{background:#f1f5f9;}
.ecsb-ejopt span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}

/* ── Barra de acciones (búsqueda + eliminar + fullscreen) ── */
#bar2{display:flex;align-items:center;gap:8px;padding:0 0 9px;flex-shrink:0;}
#search{flex:1;min-width:0;height:42px;border:1.5px solid #e2e8f0;border-radius:11px;padding:0 13px;font-size:0.84rem;
  font-family:inherit;outline:none;color:#1e293b;background:#f8fafc;transition:border-color .2s,box-shadow .2s;}
#search:focus{border-color:#5b7cfa;background:#fff;box-shadow:0 0 0 3px rgba(91,124,250,.1);}
#cnt{font-size:0.72rem;color:#94a3b8;white-space:nowrap;font-weight:700;min-width:70px;text-align:right;}
#del-btn{display:inline-flex;align-items:center;gap:7px;height:42px;padding:0 15px;border:none;border-radius:11px;
  background:#e2e8f0;color:#94a3b8;font-family:inherit;font-size:0.78rem;font-weight:800;letter-spacing:.02em;
  cursor:not-allowed;white-space:nowrap;transition:all .16s;flex-shrink:0;}
#del-btn.on{background:linear-gradient(135deg,#ef4444,#dc2626);color:#fff;cursor:pointer;box-shadow:0 4px 14px rgba(220,38,38,.35);}
#del-btn.on:hover{filter:brightness(1.06);transform:translateY(-1px);}
#del-btn svg{width:15px;height:15px;}
#fsbtn{width:42px;height:42px;border:1px solid #e2e8f0;border-radius:11px;background:#fff;color:#475569;
  cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;padding:0;transition:all .15s;}
#fsbtn:hover{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;border-color:transparent;box-shadow:0 4px 12px rgba(37,99,235,.3);}
#fsbtn svg{width:17px;height:17px;display:block;}
html.fs,html.fs body,html.fs #wrap{height:100vh!important;}
html.fs body{padding:12px 16px!important;}

/* ── Tabla (idéntica a .resultados-table de COTIZACIONES) ── */
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
  __BADGES__
  <div id="bar2">
    <div class="ecsb-ejwrap">
      <button type="button" id="ej-chip" class="ecsb-ejchip">
        <span id="ej-chip-body" class="ecsb-ejchip-body"><span class="ecsb-av ecsb-av-all"></span><span class="ecsb-ejph">Todos los ejecutivos</span></span>
        <svg class="ecsb-chev" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg>
      </button>
      <div id="ej-menu" class="ecsb-ejmenu">__EJMENU__</div>
    </div>
    <input id="search" type="text" placeholder="Filtrar por EP, cliente o ejecutivo..." autocomplete="off">
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
    <div id="empty">Sin resultados para los filtros.</div>
  </div>
</div>
<script>
(function(){
var NRES=__NRES__;
var doc=document;
var F={badge:'TODOS', ej:'', term:''};
function chks(){ return [].slice.call(doc.querySelectorAll('.ad-chk')); }
function visRows(){ return [].slice.call(doc.querySelectorAll('tbody tr[data-ep]')).filter(function(r){return r.style.display!=='none';}); }

function applyFilters(){
  var rows=doc.querySelectorAll('tbody tr[data-ep]');var vis=0;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var blob=((r.getAttribute('data-ep')||'')+' '+(r.getAttribute('data-cli')||'')+' '+(r.getAttribute('data-ej')||'')+' '+(r.getAttribute('data-estkey')||'')).toLowerCase();
    var okTerm=(!F.term||blob.indexOf(F.term)>=0);
    var okBadge=(F.badge==='TODOS'||(r.getAttribute('data-estkey')||'')===F.badge);
    var okEj=(!F.ej||(r.getAttribute('data-ej')||'')===F.ej);
    var show=okTerm&&okBadge&&okEj;
    r.style.display=show?'':'none';
    if(!show){ var c=r.querySelector('.ad-chk'); if(c&&c.checked){ c.checked=false; } r.classList.remove('ad-sel'); }
    if(show)vis++;
  }
  var el=doc.getElementById('cnt'); if(el)el.textContent=vis+' de '+NRES;
  doc.getElementById('empty').style.display=vis?'none':'block';
  syncAll();
}

/* ── Badges de estado ── */
function setBadge(f){
  var bb=doc.getElementById('ad-badgebar'); if(!bb) return;
  bb.querySelectorAll('.ec-badge[data-filter]').forEach(function(b){
    var on=b.getAttribute('data-filter')===f;
    if(on){ b.style.background=b.getAttribute('data-act'); b.style.color='#fff'; b.style.boxShadow='0 0 0 2px '+b.getAttribute('data-act'); }
    else{ b.style.background=b.getAttribute('data-bg'); b.style.color=b.getAttribute('data-fg'); b.style.boxShadow='none'; }
  });
}
(function(){
  var bb=doc.getElementById('ad-badgebar'); if(!bb) return;
  bb.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('.ec-badge'):null; if(!b) return;
    if(b.getAttribute('data-refresh')){ try{ var rb=window.parent.document.querySelector('.st-key-ad_refresh button'); if(rb) rb.click(); }catch(_){ } return; }
    var f=b.getAttribute('data-filter'); if(f===F.badge) f='TODOS'; F.badge=f; setBadge(f); applyFilters();
  });
})();

/* ── Dropdown ejecutivo ── */
(function(){
  var chip=doc.getElementById('ej-chip'), menu=doc.getElementById('ej-menu');
  if(!chip||!menu) return;
  chip.addEventListener('click',function(e){ e.stopPropagation(); menu.classList.toggle('open'); });
  menu.addEventListener('click',function(e){
    var o=e.target.closest?e.target.closest('.ecsb-ejopt'):null; if(!o) return;
    F.ej=o.getAttribute('data-ej')||'';
    var av=o.querySelector('.ecsb-av'); var nm=o.getAttribute('data-name')||'';
    var body=doc.getElementById('ej-chip-body');
    if(F.ej){ body.innerHTML=(av?av.outerHTML:'')+'<span class="ecsb-ejname">'+nm.replace(/</g,'&lt;')+'</span>'; }
    else{ body.innerHTML='<span class="ecsb-av ecsb-av-all"></span><span class="ecsb-ejph">Todos los ejecutivos</span>'; }
    menu.classList.remove('open'); applyFilters();
  });
  doc.addEventListener('click',function(e){ if(!chip.contains(e.target)&&!menu.contains(e.target)) menu.classList.remove('open'); });
})();

/* ── Búsqueda ── */
doc.getElementById('search').addEventListener('input',function(){ F.term=(this.value||'').trim().toLowerCase(); applyFilters(); });

/* ── Selección + eliminar ── */
function syncRow(cb){ var tr=cb.closest('tr'); if(tr){ tr.classList.toggle('ad-sel', cb.checked); } }
function syncAll(){
  var vr=visRows(); var all=doc.getElementById('chk-all');
  var checked=vr.filter(function(r){var c=r.querySelector('.ad-chk');return c&&c.checked;}).length;
  if(all){ all.checked=vr.length>0&&checked===vr.length; all.indeterminate=checked>0&&checked<vr.length; }
  updateDel();
}
function updateDel(){
  var n=visRows().filter(function(r){var c=r.querySelector('.ad-chk');return c&&c.checked;}).length;
  var b=doc.getElementById('del-btn'), l=doc.getElementById('del-lbl');
  if(n>0){ b.classList.add('on'); b.disabled=false; l.textContent='Eliminar seleccionados ('+n+')'; }
  else{ b.classList.remove('on'); b.disabled=true; l.textContent='Eliminar'; }
}
doc.addEventListener('change',function(e){
  var t=e.target;
  if(t.classList&&t.classList.contains('ad-chk')){ syncRow(t); syncAll(); }
  else if(t.id==='chk-all'){
    var on=t.checked; visRows().forEach(function(r){ var c=r.querySelector('.ad-chk'); if(c){ c.checked=on; syncRow(c);} });
    updateDel();
  }
});
function fireDelete(){
  var eps=visRows().filter(function(r){var c=r.querySelector('.ad-chk');return c&&c.checked;})
    .map(function(r){return r.querySelector('.ad-chk').getAttribute('data-ep');});
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

/* ── Fullscreen (mismo mecanismo/z-index que COTIZACIONES) ── */
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

applyFilters();
})();
</script>
</body></html>"""
