"""
Tab ADMINISTRACIÓN DE DATOS — Eliminación permanente de presupuestos y archivos (solo root).
Código fuente original: app.py líneas 13972-14148
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header


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
            users.append({
                "id": str(u.id),
                "email": email,
                "nombre": meta.get("nombre", email),
                "rol": meta.get("rol", "ejecutivo"),
            })
        return users
    except Exception:
        return []


def render_tab_admindata(supabase, supabase_admin=None, **deps):
    supa_admin = supabase_admin or _supa_admin

    if not st.session_state.get('es_root'):
        st.info("🔒 Esta sección es solo para administradores root.")
        return

    st.markdown("""
    <style>
    .hdr-admindata {
        background: linear-gradient(135deg, #7f1d1d 0%, #dc2626 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(220,38,38,0.35);
        position: relative; overflow: hidden;
    }
    .hdr-admindata::before { content:''; position:absolute; top:-40px; right:-40px;
        width:180px; height:180px; border-radius:50%;
        background:rgba(255,255,255,0.04); pointer-events:none; }
    .hdr-admindata::after { content:''; position:absolute; bottom:-60px; right:80px;
        width:240px; height:240px; border-radius:50%;
        background:rgba(255,255,255,0.03); pointer-events:none; }
    .hdr-admindata h2 { color:#fff !important; margin:0; font-size:0.88rem; font-weight:700;
        font-family:'Montserrat',sans-serif; letter-spacing:0.05em; text-transform:uppercase; }
    .hdr-admindata p { color:rgba(255,255,255,0.65) !important; margin:1px 0 0; font-size:0.92rem; }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "admindata",
        "Administraci&#243;n de datos",
        "Eliminaci&#243;n permanente de presupuestos y archivos &middot; Solo disponible para root",
    )

    # ── Filtros ──
    st.markdown('<div style="font-size:0.78rem;font-weight:800;color:#1e293b;text-transform:uppercase;letter-spacing:0.1em;margin:14px 0 8px;padding:6px 14px;background:linear-gradient(90deg,rgba(220,38,38,0.07),transparent);border-left:4px solid #dc2626;border-radius:0 8px 8px 0;">&#128269; Filtrar presupuestos</div>', unsafe_allow_html=True)
    _ad_c1, _ad_c2, _ad_c3, _ad_c4, _ad_c5 = st.columns([1.5, 1.5, 1.2, 1.2, 0.6])
    with _ad_c1:
        _ad_ep = st.text_input("N&#176; EP", placeholder="Ej: EP-12345", key="ad_ep", label_visibility="collapsed")
    with _ad_c2:
        try:
            _ad_usu = _listar_usuarios_ej(supa_admin) or []
            _ad_ej_opts = ['Todos'] + [u.get('nombre', '') for u in _ad_usu if u.get('nombre')]
        except Exception:
            _ad_ej_opts = ['Todos']
        _ad_ej = st.selectbox("Ejecutivo", _ad_ej_opts, key="ad_ej", label_visibility="collapsed")
    with _ad_c3:
        _ad_estados = ['Todos', 'Borrador', 'Incompleto', 'Autorizado', 'Adjudicado']
        _ad_estado = st.selectbox("Estado", _ad_estados, key="ad_estado", label_visibility="collapsed")
    with _ad_c4:
        _ad_fecha = st.date_input("Hasta fecha", value=None, key="ad_fecha", label_visibility="collapsed")
    with _ad_c5:
        _ad_buscar = st.button("&#128269;", use_container_width=True, key="ad_buscar")

    # ── Carga de datos ──
    if 'ad_results' not in st.session_state or _ad_buscar:
        try:
            _adq = supa_admin.table("cotizaciones").select(
                "numero,cliente_nombre,asesor_nombre,estado,fecha_creacion,"
                "total_total,config_margen,contrato_notariado_url"
            )
            if _ad_ep.strip():
                _adq = _adq.ilike("numero", f"%{_ad_ep.strip()}%")
            if _ad_ej != 'Todos':
                _adq = _adq.eq("asesor_nombre", _ad_ej)
            if _ad_estado != 'Todos':
                if _ad_estado == 'Adjudicado':
                    _adq = _adq.not_.is_("contrato_notariado_url", "null")
                elif _ad_estado == 'Autorizado':
                    _adq = _adq.gt("config_margen", 0).is_("contrato_notariado_url", "null")
                elif _ad_estado == 'Borrador':
                    _adq = _adq.eq("estado", "borrador")
                elif _ad_estado == 'Incompleto':
                    _adq = _adq.eq("estado", "incompleto")
            if _ad_fecha:
                _adq = _adq.lte("fecha_creacion", str(_ad_fecha))
            _ad_res = _adq.order("fecha_creacion", desc=True).limit(200).execute()
            st.session_state['ad_results'] = _ad_res.data or []
        except Exception as _ade:
            st.error(f"Error: {_ade}")
            st.session_state['ad_results'] = []

    _ad_data = st.session_state.get('ad_results', [])

    if not _ad_data:
        st.info("No se encontraron presupuestos con los filtros aplicados.")
    else:
        st.markdown(f"<span style='background:#fee2e2;color:#dc2626;padding:3px 12px;border-radius:99px;font-size:11px;font-weight:700;'>{len(_ad_data)} presupuestos encontrados</span>", unsafe_allow_html=True)
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        import pandas as _pd_ad
        _ad_df = _pd_ad.DataFrame([{
            'Seleccionar': False,
            'N° EP': r.get('numero', ''),
            'Cliente': r.get('cliente_nombre', '—'),
            'Ejecutivo': r.get('asesor_nombre', '—'),
            'Estado': ('&#128309; ADJUDICADO' if r.get('contrato_notariado_url') else
                       ('&#128994; AUTORIZADO' if r.get('config_margen', 0) else
                        r.get('estado', '—').upper())),
            'Fecha': (r.get('fecha_creacion', '')[:10] if r.get('fecha_creacion') else '—'),
            'Total': ('${:,.0f}'.format(r.get('total_total', 0) or 0).replace(',', '.') if r.get('total_total') else '—'),
        } for r in _ad_data])

        _ad_edited = st.data_editor(
            _ad_df, use_container_width=True, hide_index=True,
            height=min(len(_ad_df) * 38 + 60, 500),
            key="ad_editor",
            column_config={
                'Seleccionar': st.column_config.CheckboxColumn('&#9745;&#65039;', width='small'),
                'N° EP': st.column_config.TextColumn('N° EP', width='small'),
                'Cliente': st.column_config.TextColumn('Cliente'),
                'Ejecutivo': st.column_config.TextColumn('Ejecutivo'),
                'Estado': st.column_config.TextColumn('Estado'),
                'Fecha': st.column_config.TextColumn('Fecha', width='small'),
                'Total': st.column_config.TextColumn('Total', width='small'),
            })

        _ad_seleccionados = _ad_edited[_ad_edited['Seleccionar'] == True]['N° EP'].tolist()

        if _ad_seleccionados:
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            _ad_n = len(_ad_seleccionados)
            _ad_col1, _ad_col2 = st.columns([2, 1])
            with _ad_col1:
                st.markdown(f"""
                <div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:10px;padding:12px 16px;">
                  <div style="font-size:13px;font-weight:700;color:#dc2626;">&#9888;&#65039; {_ad_n} presupuesto(s) seleccionado(s) para eliminar:</div>
                  <div style="font-size:11px;color:#991b1b;margin-top:4px;">{' &middot; '.join(_ad_seleccionados)}</div>
                </div>
                """, unsafe_allow_html=True)
            with _ad_col2:
                if st.button(f"&#128465;&#65039; Eliminar seleccionados ({_ad_n})", type="primary",
                             use_container_width=True, key="ad_btn_eliminar"):
                    st.session_state['ad_confirmar'] = True
                    st.session_state['ad_eps_a_eliminar'] = _ad_seleccionados
                    st.rerun()

        # ── Confirmación ──
        if st.session_state.get('ad_confirmar') and st.session_state.get('ad_eps_a_eliminar'):
            _eps_el = st.session_state['ad_eps_a_eliminar']
            st.markdown("---")
            st.error(f"&#9888;&#65039; **CONFIRMACIÓN REQUERIDA** — Estás a punto de eliminar **{len(_eps_el)} presupuesto(s)** de forma **permanente e irreversible**. Se eliminarán todos los archivos PDF y datos asociados.")
            st.markdown(f"**EPs a eliminar:** {', '.join(_eps_el)}")
            _conf_c1, _conf_c2 = st.columns(2)
            with _conf_c1:
                if st.button("&#10006;&#65039; Cancelar", use_container_width=True, key="ad_btn_cancelar"):
                    st.session_state.pop('ad_confirmar', None)
                    st.session_state.pop('ad_eps_a_eliminar', None)
                    st.rerun()
            with _conf_c2:
                if st.button("&#9888;&#65039; Sí, eliminar definitivamente", type="primary",
                             use_container_width=True, key="ad_btn_confirmar"):
                    _errores = []
                    _eliminados = []
                    with st.spinner("Eliminando presupuestos y archivos..."):
                        for _ep_del in _eps_el:
                            try:
                                for _path in [
                                    f"planos/{_ep_del}/",
                                    f"notariados/{_ep_del}/",
                                    f"preview/preview_{_ep_del.replace('-', '_')}.pdf",
                                ]:
                                    try:
                                        _files = supa_admin.storage.from_("planos").list(_path.rstrip('/'))
                                        if _files:
                                            _to_del = [f"{_path}{f['name']}" for f in _files]
                                            supa_admin.storage.from_("planos").remove(_to_del)
                                    except Exception:
                                        pass
                                supa_admin.table("cotizaciones").delete().eq("numero", _ep_del).execute()
                                _eliminados.append(_ep_del)
                            except Exception as _del_e:
                                _errores.append(f"{_ep_del}: {_del_e}")

                    st.session_state.pop('ad_confirmar', None)
                    st.session_state.pop('ad_eps_a_eliminar', None)
                    st.session_state.pop('ad_results', None)
                    if _eliminados:
                        st.success(f"&#9989; Eliminados correctamente: {', '.join(_eliminados)}")
                    if _errores:
                        st.error(f"&#10060; Errores: {'; '.join(_errores)}")
                    st.rerun()
