"""
Tab FORMULARIO CLIENTE — Config catálogo, preguntas, progreso de respuestas.
Código fuente original: app.py líneas 19318-19456
"""
import streamlit as st
import streamlit.components.v1 as _st_components
import pandas as pd
from collections import defaultdict
from views.layout import render_page_header
from utils.formulario import (
    fetch_catalogo_materiales,
    fetch_formulario_config,
    build_catalogo_html,
    build_config_preguntas_html,
)
from config.supabase import supabase_admin as _supa_admin


# Tipografía de títulos de sección (unificada con el resto del sistema).
_SEC_TITLE_STYLE = ("font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;"
                    "font-weight:700;text-transform:uppercase;letter-spacing:0.05em;"
                    "line-height:1.6;display:flex;align-items:center;margin:8px 0 10px;")


def _fic(path, size=16, color="#0f172a", sw=2, mr=0, valign=-3):
    """SVG inline (estilo Lucide) para títulos/íconos en HTML del tab."""
    _s = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        _s += f"margin-right:{mr}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{_s}">{path}</svg>')


_IC_CLIP   = ('<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>'
              '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="m9 14 2 2 4-4"/>')
_IC_CHECK  = '<path d="M20 6 9 17l-5-5"/>'
_IC_CIRCLE = '<circle cx="12" cy="12" r="9"/>'


def render_tab_formulario(supabase, supabase_admin=None, supa_url='', supa_key='', **deps):
    supa_admin = supabase_admin or _supa_admin
    _supa_url = supa_url or deps.get('supa_url', '')
    _supa_key = supa_key or deps.get('supa_key', '')
    _rol = st.session_state.get('rol_usuario', 'ejecutivo')

    render_page_header(
        "formulario",
        "Formulario de Materiales",
        "Configura preguntas por proyecto &middot; Revisa respuestas del cliente",
    )

    if _rol in ('root', 'admin'):
        _ftab_catalogo, _ftab_config, _ftab_progreso = st.tabs([
            ":material/inventory_2: Cat&#225;logo de materiales",
            ":material/quiz: Configurar preguntas",
            ":material/bar_chart: Progreso clientes",
        ])
    else:
        _ftab_catalogo = None
        _ftab_config, _ftab_progreso = st.tabs([
            ":material/quiz: Configurar preguntas",
            ":material/bar_chart: Progreso clientes",
        ])

    # ── TAB CATÁLOGO ──
    if _ftab_catalogo is not None:
        with _ftab_catalogo:
            if _rol not in ('root', 'admin'):
                st.info("Solo administradores pueden gestionar el cat&#225;logo.", icon=":material/lock:")
            else:
                # Botón oculto: el JS del catálogo (dentro del iframe) lo clickea tras
                # una mutación (eliminar/editar/clonar) para forzar un rerun de
                # Streamlit SIN recargar la página. Antes hacía location.reload(), que
                # perdía la sesión (el token ?_sess ya no está en la URL) y obligaba a
                # re-loguear. Al limpiar los caches, "Configurar preguntas" y la página
                # del cliente ven los datos frescos.
                st.markdown(
                    '<style>.st-key-_cat_refresh_btn{position:absolute!important;'
                    'width:1px;height:1px;overflow:hidden;opacity:0;margin:0;padding:0;}</style>',
                    unsafe_allow_html=True)
                if st.button("refrescar catálogo", key="_cat_refresh_btn"):
                    try:
                        fetch_catalogo_materiales.clear()
                        fetch_formulario_config.clear()
                    except Exception:
                        pass
                if 'cat_tipo' not in st.session_state:
                    st.session_state.cat_tipo = 'imagen'
                if 'cat_cantidad' not in st.session_state:
                    st.session_state.cat_cantidad = 4
                _qp_tipo = st.query_params.get('cat_tipo', '')
                _qp_cant = st.query_params.get('cat_cantidad', '')
                if _qp_tipo:
                    st.session_state.cat_tipo = _qp_tipo
                    st.query_params.pop('cat_tipo')
                if _qp_cant:
                    try:
                        st.session_state.cat_cantidad = int(_qp_cant)
                    except Exception:
                        pass
                    st.query_params.pop('cat_cantidad')
                try:
                    _cat_all = supa_admin.table('catalogo_materiales').select('*')\
                        .eq('activo', True).order('categoria').order('orden_grupo')\
                        .order('titulo_grupo').order('nombre').execute().data or []
                    for _ci in _cat_all:
                        if not _ci.get('titulo_grupo'):
                            _ci['titulo_grupo'] = '__sin_grupo__'
                except Exception:
                    _cat_all = []
                _cat_html = build_catalogo_html(
                    _cat_all, _supa_url, _supa_key,
                    st.session_state.cat_tipo, st.session_state.cat_cantidad
                )
                _cat_height = max(700, len(_cat_all) * 20 + 600)
                _st_components.html(_cat_html, height=_cat_height, scrolling=True)

    # ── TAB CONFIGURAR ──
    with _ftab_config:
        if _rol not in ('root', 'admin', 'ejecutivo'):
            st.info("No tienes permisos para configurar formularios.", icon=":material/lock:")
        else:
            # ── Tabla de presupuestos ADJUDICADOS con estado de preguntas ──
            # Título (izq) + link "Abrir formulario cliente" en nueva pestaña (der).
            # La URL se arma desde el parent (origin+pathname+?cliente=1) para que
            # funcione tanto en beta como en producción sin hardcodear.
            _cli_link_html = (
                '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                '*{box-sizing:border-box;}body{margin:0;font-family:"Montserrat","Segoe UI",sans-serif;}'
                'a.cli{display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;'
                'background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;font-weight:800;font-size:12.5px;'
                'letter-spacing:0.02em;padding:10px 14px;border-radius:10px;box-shadow:0 4px 12px rgba(22,163,74,0.30);'
                'transition:transform .12s,box-shadow .15s;}'
                'a.cli:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(22,163,74,0.42);}'
                'a.cli svg{width:15px;height:15px;flex-shrink:0;}'
                '</style></head><body>'
                '<a id="cli" class="cli" target="_blank" rel="noopener" title="Abre la p&#225;gina del cliente en una pesta&#241;a nueva">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
                'stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>'
                'Abrir formulario cliente</a>'
                '<script>(function(){var a=document.getElementById("cli");try{var L=window.parent.location;'
                'a.href=L.origin+L.pathname+"?cliente=1";}catch(e){a.href="/?cliente=1";}})();</script>'
                '</body></html>'
            )
            _ct1, _ct2 = st.columns([3, 1.5], vertical_alignment="center")
            with _ct1:
                st.markdown(
                    f'<div style="{_SEC_TITLE_STYLE}">{_fic(_IC_CLIP, 17, mr=8)}Presupuestos adjudicados</div>',
                    unsafe_allow_html=True)
            with _ct2:
                _st_components.html(_cli_link_html, height=46)
            try:
                _adj_q = supa_admin.table('cotizaciones').select(
                    'numero,cliente_nombre,asesor_nombre,fecha_adjudicacion,estado,asesor_email'
                ).eq('estado', 'ADJUDICADO')
                # Ejecutivo: solo SUS adjudicados (root/admin ven todos). Mismo
                # criterio que el resto del sistema (filtrar por asesor_email).
                if _rol == 'ejecutivo':
                    _adj_email = (st.session_state.get('auth_email', '') or '').strip()
                    if _adj_email:
                        _adj_q = _adj_q.ilike('asesor_email', _adj_email)
                    else:
                        _adj_q = _adj_q.eq('numero', '__none__')  # sin email → nada
                _adj = _adj_q.order('fecha_adjudicacion', desc=True).execute().data or []
            except Exception:
                _adj = []
            try:
                _fc_nums = set(
                    x['cotizacion_numero']
                    for x in (supa_admin.table('formulario_config').select('cotizacion_numero').execute().data or [])
                )
            except Exception:
                _fc_nums = set()
            if not _adj:
                st.info("A&#250;n no tienes presupuestos adjudicados." if _rol == 'ejecutivo'
                        else "A&#250;n no hay presupuestos adjudicados.")
            else:
                _df_adj = pd.DataFrame([{
                    'N° EP':      r.get('numero', ''),
                    'Cliente':    r.get('cliente_nombre') or '—',
                    'Asesor':     r.get('asesor_nombre') or '—',
                    'Adjudicado': (r.get('fecha_adjudicacion') or '')[:10] or '—',
                    'Preguntas':  'SÍ' if r.get('numero') in _fc_nums else 'NO',
                } for r in _adj])
                _n_si = int((_df_adj['Preguntas'] == 'SÍ').sum())
                st.caption(
                    f"{len(_df_adj)} adjudicados · {_n_si} con preguntas configuradas · "
                    f"{len(_df_adj) - _n_si} pendientes. Haz click en una fila para configurar sus preguntas."
                )

                def _color_preg(col):
                    return [('background-color:#dcfce7;color:#15803d;font-weight:800;' if v == 'SÍ'
                             else 'background-color:#fee2e2;color:#dc2626;font-weight:800;') for v in col]
                _sty = _df_adj.style.apply(_color_preg, subset=['Preguntas'])

                _sel_adj = st.dataframe(
                    _sty, use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="single-row", key="_adj_preg_table",
                )
                _rows = []
                try:
                    _rows = list(_sel_adj.selection.rows)
                except Exception:
                    try:
                        _rows = list(_sel_adj["selection"]["rows"])
                    except Exception:
                        _rows = []
                if _rows:
                    _pick = str(_df_adj.iloc[_rows[0]]['N° EP'])
                    # Sólo cargar cuando la fila SELECCIONADA cambia (no en cada
                    # rerun), para no pisar una carga manual posterior por EP.
                    if _pick and _pick != st.session_state.get('_adj_last_pick'):
                        st.session_state['_adj_last_pick'] = _pick
                        st.session_state['_form_ep'] = _pick
                        st.rerun()

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            # ── Buscar / cargar EP manualmente ──
            _c1ep, _c2ep = st.columns([3, 1])
            with _c1ep:
                _ep_form_input = st.text_input(
                    "N&#250;mero EP", placeholder="EP-12345", key="form_ep_input"
                )
            with _c2ep:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Cargar", icon=":material/search:", key="form_cargar_ep", use_container_width=True) and _ep_form_input:
                    st.session_state['_form_ep'] = _ep_form_input.strip().upper()
                    st.rerun()
            _form_ep = st.session_state.get('_form_ep', '')
            if not _form_ep:
                st.info("Ingresa un n&#250;mero EP y haz click en Cargar.")
            else:
                # _cat_ts es el query param que JS setea tras editar el catálogo;
                # cambia el cache key de las funciones @st.cache_data y fuerza re-fetch.
                _cat_ts = st.query_params.get('_cat_ts', '')
                try:
                    _cat_todos = fetch_catalogo_materiales(_cache_buster=_cat_ts)
                except Exception:
                    _cat_todos = []
                try:
                    _cfg_data = fetch_formulario_config(_form_ep, _cache_buster=_cat_ts)
                except Exception:
                    _cfg_data = []
                _cfg_html = build_config_preguntas_html(
                    _cat_todos, _cfg_data, _supa_url, _supa_key, _form_ep
                )
                _cfg_height = max(800, len(_cat_todos) * 40 + 600)
                _st_components.html(_cfg_html, height=_cfg_height, scrolling=True)

    # ── TAB PROGRESO ──
    with _ftab_progreso:
        st.markdown("**Progreso de formularios por proyecto:**")
        try:
            _all_cfg = supa_admin.table('formulario_config').select(
                'cotizacion_numero,categoria,titulo_grupo,item_ids,orden'
            ).execute().data or []
            _all_resps = supa_admin.table('formulario_respuestas').select(
                'cotizacion_numero,item_id,pregunta_id,respuesta'
            ).execute().data or []

            _cfg_by_ep = defaultdict(list)
            for _cc in _all_cfg:
                _cfg_by_ep[_cc['cotizacion_numero']].append(_cc)

            _resps_by_ep = defaultdict(dict)
            for _rr in _all_resps:
                _key = _rr.get('item_id') or _rr.get('pregunta_id') or ''
                if _key:
                    _resps_by_ep[_rr['cotizacion_numero']][_key] = _rr['respuesta']

            if not _cfg_by_ep:
                st.info("No hay formularios configurados a&#250;n.")
            else:
                for _fep, _fcfgs in sorted(_cfg_by_ep.items()):
                    _total = len(_fcfgs)
                    _resp_map = _resps_by_ep[_fep]
                    _done = sum(
                        1 for cfg in _fcfgs
                        if any(_resp_map.get(str(iid)) for iid in (cfg.get('item_ids') or []))
                    )
                    _fpct = int(_done / _total * 100) if _total > 0 else 0
                    _fcol = '#16a34a' if _fpct == 100 else ('#f97316' if _fpct >= 50 else '#2563eb')

                    with st.expander(f"**{_fep}** — {_fpct}% completado ({_done}/{_total} grupos)"):
                        st.markdown(f"""
                        <div style='background:#f8fafc;border-radius:8px;padding:8px 12px;margin-bottom:12px;'>
                          <div style='background:#e2e8f0;border-radius:99px;height:8px;'>
                            <div style='background:{_fcol};border-radius:99px;height:8px;width:{_fpct}%;'></div>
                          </div>
                          <div style='font-size:0.75rem;color:#64748b;margin-top:4px;'>{_done} de {_total} secciones respondidas</div>
                        </div>
                        """, unsafe_allow_html=True)

                        _cats_prog = defaultdict(list)
                        for _cfg2 in sorted(_fcfgs, key=lambda x: (x.get('categoria', ''), x.get('orden', 0))):
                            _cats_prog[_cfg2.get('categoria', '')].append(_cfg2)

                        for _cat4, _clist4 in _cats_prog.items():
                            st.markdown(f"**{_cat4}**")
                            for _cfg4 in _clist4:
                                _tg4 = _cfg4.get('titulo_grupo', '')
                                _ids4 = [str(x) for x in (_cfg4.get('item_ids') or [])]
                                _answered = [_resp_map.get(iid, '') for iid in _ids4 if _resp_map.get(iid)]
                                _ico4 = (_fic(_IC_CHECK, 13, color='#16a34a', mr=5)
                                         if _answered else _fic(_IC_CIRCLE, 13, color='#cbd5e1', mr=5))
                                _val4 = ', '.join(_answered) if _answered else '&#8212;'
                                st.markdown(
                                    f"<div style='font-size:0.82rem;padding:3px 8px;'>"
                                    f"{_ico4} <b>{_tg4}</b>: "
                                    f"<span style='color:#0f3460;'>{_val4}</span></div>",
                                    unsafe_allow_html=True
                                )
        except Exception as _fe:
            st.error(f"Error cargando progreso: {_fe}")
