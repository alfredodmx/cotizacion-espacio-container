"""
Tab FORMULARIO CLIENTE — Config catálogo, preguntas, progreso de respuestas.
Código fuente original: app.py líneas 19318-19456
"""
import streamlit as st
import streamlit.components.v1 as _st_components
from collections import defaultdict
from views.layout import render_page_header
from utils.formulario import (
    fetch_catalogo_materiales,
    fetch_formulario_config,
    build_catalogo_html,
    build_config_preguntas_html,
)
from config.supabase import supabase_admin as _supa_admin


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
            "&#128230; Cat&#225;logo de materiales",
            "&#9881;&#65039; Configurar preguntas",
            "&#128202; Progreso clientes",
        ])
    else:
        _ftab_catalogo = None
        _ftab_config, _ftab_progreso = st.tabs([
            "&#9881;&#65039; Configurar preguntas",
            "&#128202; Progreso clientes",
        ])

    # ── TAB CATÁLOGO ──
    if _ftab_catalogo is not None:
        with _ftab_catalogo:
            if _rol not in ('root', 'admin'):
                st.info("&#128274; Solo administradores pueden gestionar el cat&#225;logo.")
            else:
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
            st.info("&#128274; No tienes permisos para configurar formularios.")
        else:
            _c1ep, _c2ep = st.columns([3, 1])
            with _c1ep:
                _ep_form_input = st.text_input(
                    "N&#250;mero EP", placeholder="EP-12345", key="form_ep_input"
                )
            with _c2ep:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("&#128269; Cargar", key="form_cargar_ep", use_container_width=True) and _ep_form_input:
                    st.session_state['_form_ep'] = _ep_form_input.strip().upper()
                    st.rerun()
            _form_ep = st.session_state.get('_form_ep', '')
            if not _form_ep:
                st.info("Ingresa un n&#250;mero EP y haz click en Cargar.")
            else:
                try:
                    _cat_todos = fetch_catalogo_materiales()
                except Exception:
                    _cat_todos = []
                try:
                    _cfg_data = fetch_formulario_config(_form_ep)
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
                                _ico4 = '&#9989;' if _answered else '&#11036;'
                                _val4 = ', '.join(_answered) if _answered else '&#8212;'
                                st.markdown(
                                    f"<div style='font-size:0.82rem;padding:3px 8px;'>"
                                    f"{_ico4} <b>{_tg4}</b>: "
                                    f"<span style='color:#0f3460;'>{_val4}</span></div>",
                                    unsafe_allow_html=True
                                )
        except Exception as _fe:
            st.error(f"Error cargando progreso: {_fe}")
