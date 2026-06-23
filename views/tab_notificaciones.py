"""
Tab NOTIFICACIONES — Config Telegram bot, contactos, observadores, mensajes.
Código fuente original: app.py líneas 531-607 (helpers) + 19011-19314 (UI)
"""
import json as _json_notif
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header


def _get_notif_config(clave, default=""):
    try:
        r = _supa_admin.table('notificaciones_config').select('valor').eq('clave', clave).execute()
        if r.data:
            return r.data[0]['valor'] or default
    except Exception:
        pass
    return default


def _set_notif_config(clave, valor):
    try:
        _supa_admin.table('notificaciones_config').upsert(
            {'clave': clave, 'valor': valor, 'updated_at': 'now()'},
            on_conflict='clave'
        ).execute()
        return True
    except Exception:
        return False


def _get_contactos_notif():
    try:
        raw = _get_notif_config('contactos_json', '{}')
        return _json_notif.loads(raw)
    except Exception:
        return {}


def _get_observadores_notif():
    try:
        raw = _get_notif_config('observadores_json', '[]')
        return _json_notif.loads(raw)
    except Exception:
        return []


def _listar_usuarios_ej():
    try:
        _roots = [r.strip().lower() for r in st.secrets.get("ROOTS", "").split(",") if r.strip()]
        res = _supa_admin.auth.admin.list_users()
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


def render_tab_notificaciones(supabase, **deps):
    if not st.session_state.get('es_supervisor'):
        st.info("&#128274; Esta sección es solo para supervisores y administradores.")
        return

    _TELEGRAM_BOT_TOKEN_DEFAULT = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    _ROOTS = [r.strip() for r in st.secrets.get("ROOTS", "").split(",") if r.strip()]

    st.markdown("""
    <style>
    .hdr-notif {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #0f172a 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
    }
    .hdr-notif h2 { color:#fff !important; margin:0; }
    .hdr-notif p  { color:rgba(255,255,255,0.65) !important; margin:1px 0 0; }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "notificaciones",
        "Notificaciones",
        "Configura Telegram, contactos, observadores y mensajes autom&#225;ticos.",
    )

    # ── 1. Configuración del Bot ──
    with st.container(border=True):
        st.markdown("**&#9881;&#65039; 1 &middot; Configuraci&#243;n del Bot**")
        _token_actual = _get_notif_config('bot_token', _TELEGRAM_BOT_TOKEN_DEFAULT)
        _bot_nombre   = _get_notif_config('bot_nombre', 'Cotizador ECH Bot')
        _c1, _c2, _c3 = st.columns([2, 1.5, 1])
        with _c1:
            _token_inp = st.text_input("Token del Bot", value=_token_actual, type="password", key="notif_token")
        with _c2:
            _nombre_inp = st.text_input("Nombre del Bot", value=_bot_nombre, key="notif_nombre")
        with _c3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            _cb1, _cb2 = st.columns(2)
            with _cb1:
                if st.button("&#128268; Probar", key="btn_probar_bot", use_container_width=True):
                    with st.spinner("Probando..."):
                        try:
                            import requests as _rtest
                            _r = _rtest.get(f"https://api.telegram.org/bot{_token_inp}/getMe", timeout=10)
                            _rdata = _r.json()
                            _bot_ok = _rdata.get('ok', False)
                        except Exception:
                            _bot_ok = False; _rdata = {}
                    if _bot_ok:
                        st.success(f"&#9989; @{_rdata.get('result',{}).get('username','')}")
                    else:
                        st.error("&#10060; Token inv&#225;lido")
            with _cb2:
                if st.button("&#128190; Guardar", key="btn_guardar_bot", use_container_width=True, type="primary"):
                    _set_notif_config('bot_token', _token_inp)
                    _set_notif_config('bot_nombre', _nombre_inp)
                    st.success("&#9989; Guardado")

    # ── 2. Contactos del sistema ──
    with st.container(border=True):
        st.markdown("**&#128101; 2 &middot; Contactos del sistema**")
        st.caption("Cada usuario debe escribirle /start al bot una vez para obtener su Chat ID")

        with st.expander("&#128225; Detectar usuarios desde Telegram (getUpdates)", expanded=False):
            st.caption("Muestra las personas que le han escrito al bot. Haz click en &#10133; para asignar su Chat ID.")
            if st.button("&#128260; Obtener usuarios del bot", key="btn_get_updates"):
                st.session_state['_tg_updates'] = None
                try:
                    import requests as _ru
                    _tok = _get_notif_config('bot_token', _TELEGRAM_BOT_TOKEN_DEFAULT)
                    _resp = _ru.get(f"https://api.telegram.org/bot{_tok}/getUpdates?limit=100", timeout=10)
                    _data = _resp.json()
                    if _data.get('ok'):
                        _vistos = {}
                        for _upd in _data.get('result', []):
                            _msg = _upd.get('message', {})
                            _ch  = _msg.get('chat', {})
                            if _ch.get('id'):
                                _uid = str(_ch['id'])
                                _vistos[_uid] = {
                                    'chat_id': _uid,
                                    'nombre':  _ch.get('first_name','') + (' ' + _ch.get('last_name','') if _ch.get('last_name') else ''),
                                    'username': _ch.get('username','')
                                }
                        st.session_state['_tg_updates'] = list(_vistos.values())
                    else:
                        st.error("&#10060; Error al consultar el bot")
                except Exception as _ue:
                    st.error(f"&#10060; {_ue}")

            if st.session_state.get('_tg_updates') is not None:
                _updates = st.session_state['_tg_updates']
                if not _updates:
                    st.info("No hay usuarios registrados a&#250;n. P&#237;deles que escriban /start al bot.")
                else:
                    st.markdown(f"**{len(_updates)} persona(s) encontradas:**")
                    for _up in _updates:
                        _uc1, _uc2, _uc3 = st.columns([2, 1.5, 1])
                        with _uc1:
                            _uname = f"@{_up['username']}" if _up['username'] else "sin username"
                            st.markdown(f"**{_up['nombre']}** &middot; `{_uname}`")
                        with _uc2:
                            st.code(_up['chat_id'], language=None)
                        with _uc3:
                            if st.button(f"&#10133; Asignar", key=f"asignar_{_up['chat_id']}"):
                                st.info(f"Copia el Chat ID `{_up['chat_id']}` en el campo del contacto correspondiente abajo &#8595;")

        st.divider()

        _contactos = _get_contactos_notif()
        _todos_usuarios = []
        try:
            _todos_usuarios = _listar_usuarios_ej()
            for _re_root in _ROOTS:
                _todos_usuarios.insert(0, {'email': _re_root, 'nombre': 'Root', 'rol': 'root'})
        except Exception:
            pass
        _contactos_nuevos = dict(_contactos)
        for _idx, _uu in enumerate(_todos_usuarios):
            _ue  = _uu.get('email', '').lower()
            _ur  = _uu.get('rol', 'ejecutivo')
            _un  = _uu.get('nombre', _ue)
            _rol_color = "#7c3aed" if _ur == 'root' else ("#8b5cf6" if _ur == 'admin' else "#2563eb")
            _rol_txt   = "&#128273; Root" if _ur == 'root' else ("&#128081; Admin" if _ur == 'admin' else ("&#9881;&#65039; Operaci&#243;n" if _ur == 'operacion' else "&#128100; Ejecutivo"))
            _col_nm, _col_em, _col_chat, _col_rol, _col_est = st.columns([1.5, 1.8, 1.5, 1, 0.7])
            with _col_nm:
                st.markdown(f"<div style='padding:6px 0;font-size:0.88rem;font-weight:600'>{_un}</div>", unsafe_allow_html=True)
            with _col_em:
                st.markdown(f"<div style='padding:6px 0;font-size:0.78rem;color:#64748b'>{_ue}</div>", unsafe_allow_html=True)
            with _col_chat:
                _chat_val = _contactos.get(_ue, '')
                _new_chat = st.text_input("Chat ID", value=_chat_val, placeholder="@usuario o Chat ID",
                                          key=f"chat_{_idx}_{_ue}", label_visibility="collapsed")
                _contactos_nuevos[_ue] = _new_chat
            with _col_rol:
                st.markdown(f"<div style='padding:6px 0;font-size:0.75rem;color:{_rol_color};font-weight:700'>{_rol_txt}</div>", unsafe_allow_html=True)
            with _col_est:
                _esta = "&#128994;" if _contactos.get(_ue, '') else "&#128993;"
                st.markdown(f"<div style='padding:6px 0;text-align:center'>{_esta}</div>", unsafe_allow_html=True)
        if st.button("&#128190; Guardar contactos", key="btn_guardar_contactos", type="primary"):
            _set_notif_config('contactos_json', _json_notif.dumps(_contactos_nuevos))
            st.success("&#9989; Contactos guardados")
            st.rerun()

    # ── 3. Observadores ──
    with st.container(border=True):
        st.markdown("**&#128065; 3 &middot; Observadores externos**")
        st.caption("Sin cuenta en el sistema &middot; Reciben todas las notificaciones")
        _obs_list = _get_observadores_notif()
        _obs_list_edit = list(_obs_list) + [{'nombre': '', 'chat_id': ''}]
        _obs_nuevos = []
        for _oi, _ob in enumerate(_obs_list_edit):
            _oc1, _oc2, _oc3 = st.columns([2, 2, 0.5])
            with _oc1:
                _on = st.text_input("Nombre observador", value=_ob.get('nombre', ''), placeholder="Nombre (ej: Gerente)",
                                    key=f"obs_nm_{_oi}", label_visibility="collapsed")
            with _oc2:
                _oid = st.text_input("Chat ID observador", value=_ob.get('chat_id', ''), placeholder="@usuario o Chat ID",
                                     key=f"obs_id_{_oi}", label_visibility="collapsed")
            with _oc3:
                _del = st.button("&#10005;", key=f"obs_del_{_oi}", help="Eliminar")
            if _on.strip() and not _del:
                _obs_nuevos.append({'nombre': _on.strip(), 'chat_id': _oid.strip()})
        if st.button("&#128190; Guardar observadores", key="btn_guardar_obs", type="primary"):
            _set_notif_config('observadores_json', _json_notif.dumps(_obs_nuevos))
            st.success("&#9989; Observadores guardados")
            st.rerun()

    # ── 4. Grupo ──
    with st.container(border=True):
        st.markdown("**&#128226; 4 &middot; Grupo de Telegram (opcional)**")
        _grupo_id     = _get_notif_config('grupo_chat_id', '')
        _grupo_filtro = _get_notif_config('grupo_filtro', 'todas')
        _gc1, _gc2, _gc3 = st.columns([2, 2, 1])
        with _gc1:
            _g_id_inp = st.text_input("Chat ID del grupo", value=_grupo_id,
                                      placeholder="-1001234567890", key="notif_grupo_id")
            st.caption("Agrega el bot al grupo y escribe /start para obtener el ID")
        with _gc2:
            _filtro_opts = {
                "todas": "Todas las notificaciones",
                "solo_nuevas": "Solo nuevas cotizaciones",
                "solo_autorizaciones": "Solo autorizaciones",
                "ninguna": "No usar grupo"
            }
            _filtro_idx = list(_filtro_opts.keys()).index(_grupo_filtro) if _grupo_filtro in _filtro_opts else 0
            _filtro_sel = st.selectbox("Qu&#233; notificar al grupo", list(_filtro_opts.values()),
                                       index=_filtro_idx, key="notif_grupo_filtro")
            _filtro_val = list(_filtro_opts.keys())[list(_filtro_opts.values()).index(_filtro_sel)]
        with _gc3:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.button("&#128190; Guardar grupo", key="btn_guardar_grupo",
                         use_container_width=True, type="primary"):
                _set_notif_config('grupo_chat_id', _g_id_inp)
                _set_notif_config('grupo_filtro', _filtro_val)
                st.success("&#9989; Guardado")

    # ── 5. Mensajes personalizables ──
    with st.container(border=True):
        st.markdown("**&#9999;&#65039; 5 &middot; Mensajes personalizables**")
        _msg_defaults = {
            'msg_nueva_cotizacion': "&#128338; *Nueva cotizaci&#243;n para revisar*\n\n*{ep}* &middot; {ejecutivo}\nCliente: {cliente} &middot; Monto: *{monto}*\nEstado: {estado}",
            'msg_autorizada':       "&#9989; *&#161;PRESUPUESTO AUTORIZADO!*\n\n&#128203; *{ep}* &middot; {cliente}\n&#128176; Margen aplicado: *{margen}%*\n&#128100; Autorizado por: *{supervisor}*\n\nYa puedes present&#225;rselo a tu cliente &#127881;",
            'msg_margen_removido':  "&#8617;&#65039; La cotizaci&#243;n *{ep}* volvi&#243; a estado borrador.\nEl supervisor realiz&#243; cambios. Revisa el sistema."
        }

        st.markdown("""
        <style>
        .var-guide{background:rgba(0,0,0,0.03);border-radius:10px;padding:12px 16px;margin-bottom:14px;}
        .var-guide-title{font-size:0.75rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;}
        .var-chips{display:flex;flex-wrap:wrap;gap:5px;}
        .var-chip{display:inline-block;background:#f1f5f9;border:1px solid #e2e8f0;border-radius:20px;
            padding:2px 9px;font-size:0.76rem;font-family:monospace;color:#3b82f6;cursor:pointer;
            transition:all 0.15s;user-select:none;}
        .var-chip:hover{background:#dbeafe;border-color:#93c5fd;transform:scale(1.05);}
        .var-chip.copied{background:#dcfce7;border-color:#86efac;color:#16a34a;}
        </style>
        <div class="var-guide">
          <div class="var-guide-title">&#128203; Variables &#8212; click para copiar</div>
          <div class="var-chips">
            <span class="var-chip" onclick="navigator.clipboard.writeText('{ep}')">&#123;ep&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{ejecutivo}')">&#123;ejecutivo&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{cliente}')">&#123;cliente&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{monto}')">&#123;monto&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{estado}')">&#123;estado&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{margen}')">&#123;margen&#125;</span>
            <span class="var-chip" onclick="navigator.clipboard.writeText('{supervisor}')">&#123;supervisor&#125;</span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        _msg_configs = [
            ('msg_nueva_cotizacion', "&#128338; Nueva cotizaci&#243;n", "supervisores/admins/obs.", "Al guardar cotizaci&#243;n"),
            ('msg_autorizada',       "&#9989; Cotizaci&#243;n autorizada", "ejecutivo + obs.", "Al guardar con margen"),
            ('msg_margen_removido',  "&#8617;&#65039; Margen removido", "ejecutivo", "Al quitar margen"),
        ]
        _msgs_nuevos = {}
        _mcol1, _mcol2, _mcol3 = st.columns(3)
        for (_mk, _mtitulo, _mdest, _mcuando), _mcol in zip(_msg_configs, [_mcol1, _mcol2, _mcol3]):
            _mval = _get_notif_config(_mk, _msg_defaults[_mk])
            with _mcol:
                st.markdown(f"""
                <div style='margin-bottom:6px'>
                    <div style='font-size:0.85rem;font-weight:700'>{_mtitulo}</div>
                    <div style='font-size:0.72rem;color:#94a3b8'>&#8594; {_mdest}</div>
                    <div style='font-size:0.7rem;color:#cbd5e1;font-style:italic'>{_mcuando}</div>
                </div>""", unsafe_allow_html=True)
                _msgs_nuevos[_mk] = st.text_area("Mensaje", value=_mval, height=400,
                                                  key=f"msg_{_mk}", label_visibility="collapsed")
        _mb1, _mb2 = st.columns([1, 1])
        with _mb1:
            if st.button("&#8617;&#65039; Restaurar por defecto", key="btn_restaurar_msgs"):
                for _mk, _mdef in _msg_defaults.items():
                    _set_notif_config(_mk, _mdef)
                st.success("&#9989; Mensajes restaurados")
                st.rerun()
        with _mb2:
            if st.button("&#128190; Guardar mensajes", key="btn_guardar_msgs",
                         type="primary", use_container_width=True):
                for _mk, _mv in _msgs_nuevos.items():
                    _set_notif_config(_mk, _mv)
                st.success("&#9989; Mensajes guardados")
