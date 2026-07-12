"""
Tab NOTIFICACIONES — Config Telegram bot, contactos, observadores, mensajes.
"""
import json as _json
import streamlit as st
import streamlit.components.v1 as components
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from views.layout import render_page_header


# ── Iconos SVG (Lucide) ─────────────────────────────────────────────────────
_IC = {
    "bot":     '<circle cx="12" cy="12" r="10"/><path d="M12 2v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="M2 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="M16 12h.01"/><path d="M8 12h.01"/>',
    "zap":     '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "save":    '<path d="M15.2 3a2 2 0 0 1 1.4.6l3.8 3.8a2 2 0 0 1 .6 1.4V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z"/><path d="M17 21v-7a1 1 0 0 0-1-1H8a1 1 0 0 0-1 1v7"/><path d="M7 3v4a1 1 0 0 0 1 1h7"/>',
    "users":   '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "eye":     '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    "group":   '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
    "msg":     '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22z"/>',
    "check":   '<path d="M20 6 9 17l-5-5"/>',
    "x":       '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "key":     '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
    "shield":  '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "crown":   '<path d="M11.562 3.266a.5.5 0 0 1 .876 0L15.39 8.87a1 1 0 0 0 1.516.294L20.183 6.2a.5.5 0 0 1 .798.519l-1.914 11.485A2 2 0 0 1 17.093 20H6.907a2 2 0 0 1-1.974-1.796L3.02 6.72a.5.5 0 0 1 .798-.519l3.276 2.962a1 1 0 0 0 1.516-.294z"/>',
    "gear":    '<circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
    "send":    '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
    "refresh": '<path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 16h5v5"/>',
    "undo":    '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>',
    "copy":    '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "plus":    '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "trash":   '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    "filter":  '<polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/>',
}

def _svg(key, size=16, color="currentColor", sw=2, mr=0, valign=-3):
    style = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        style += f"margin-right:{mr}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{style}">{_IC.get(key, "")}</svg>')


# ── Helpers de config ────────────────────────────────────────────────────────

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
        return _json.loads(_get_notif_config('contactos_json', '{}'))
    except Exception:
        return {}


def _get_observadores_notif():
    try:
        return _json.loads(_get_notif_config('observadores_json', '[]'))
    except Exception:
        return []


@st.cache_data(ttl=120, show_spinner=False)
def _fetch_users_notif(_cb=''):
    import httpx
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = []
        _roots = [x.strip().lower() for x in st.secrets.get("ROOTS", "").split(",") if x.strip()]
        for u in r.json().get("users", []):
            em = (u.get("email") or "").lower()
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            if em in _roots:
                continue
            out.append({
                "email": em,
                "nombre": meta.get("nombre", em) or em,
                "rol": meta.get("rol", "ejecutivo"),
                "foto_url": meta.get("foto_url", "") or "",
            })
        return out
    except Exception:
        return []


# ── CSS de la pestaña ────────────────────────────────────────────────────────

_CSS = """
<style>
.ntf-sec {
    font-family:'Montserrat',sans-serif; font-weight:700; font-size:0.88rem;
    letter-spacing:0.05em; text-transform:uppercase; color:#0f172a;
    display:flex; align-items:center; gap:8px; margin:0 0 14px;
}
.ntf-sec svg { flex-shrink:0; }
.ntf-hint {
    font-family:'Plus Jakarta Sans',sans-serif; font-size:0.76rem; color:#94a3b8;
    font-weight:500; margin:-8px 0 14px; line-height:1.4;
}
.ntf-card {
    background:#fff; border:1px solid #e8ebf5; border-radius:14px;
    padding:22px 24px; margin-bottom:20px;
    box-shadow:0 2px 10px rgba(15,23,42,0.04);
}
/* Contenedor blanco de la lista de contactos (st.container keyed) */
.st-key-ntf_contacts_card {
    background:#fff; border:1px solid #e8ebf5; border-radius:14px;
    padding:22px 28px; margin:8px 0 20px;
    box-shadow:0 2px 10px rgba(15,23,42,0.04);
}
.st-key-ntf_contacts_card [data-testid="stVerticalBlockBorderWrapper"] {
    border:none; background:none; box-shadow:none;
}
.ntf-user-row {
    display:flex; align-items:center; gap:12px; padding:10px 0;
    border-bottom:1px solid #f1f5f9;
}
.ntf-user-row:last-child { border-bottom:none; }
.ntf-avatar {
    width:40px; height:40px; border-radius:50%; flex:0 0 40px;
    background:linear-gradient(135deg,#0f3460,#1a5276);
    display:flex; align-items:center; justify-content:center;
    color:#fff; font-family:'Montserrat',sans-serif; font-weight:900; font-size:14px;
    overflow:hidden; box-shadow:0 3px 10px rgba(5,12,28,0.18);
}
.ntf-avatar img { width:100%; height:100%; object-fit:cover; display:block; }
.ntf-user-info { flex:1; min-width:0; }
.ntf-user-name {
    font-family:'Plus Jakarta Sans',sans-serif; font-weight:700;
    font-size:0.85rem; color:#0f172a; line-height:1.2;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.ntf-user-email {
    font-family:'Plus Jakarta Sans',sans-serif; font-size:0.72rem;
    color:#94a3b8; line-height:1.2; margin-top:1px;
    white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
.ntf-badge {
    display:inline-flex; align-items:center; gap:4px;
    padding:3px 10px; border-radius:20px;
    font-family:'Plus Jakarta Sans',sans-serif; font-weight:700;
    font-size:0.68rem; letter-spacing:0.04em; text-transform:uppercase;
    white-space:nowrap;
}
.ntf-badge.root { background:#f3e8ff; color:#7c3aed; }
.ntf-badge.admin { background:#ede9fe; color:#8b5cf6; }
.ntf-badge.operacion { background:#fef3c7; color:#92400e; }
.ntf-badge.ejecutivo { background:#dbeafe; color:#2563eb; }
.ntf-status-dot {
    width:10px; height:10px; border-radius:50%; flex:0 0 10px;
}
.ntf-status-dot.on { background:#22c55e; box-shadow:0 0 6px rgba(34,197,94,0.4); }
.ntf-status-dot.off { background:#e2e8f0; }
.ntf-obs-row {
    display:flex; align-items:center; gap:10px; padding:8px 0;
    border-bottom:1px solid #f1f5f9;
}
.ntf-obs-row:last-child { border-bottom:none; }
.ntf-msg-header {
    display:flex; flex-direction:column; gap:2px; margin-bottom:8px;
}
.ntf-msg-title {
    font-family:'Plus Jakarta Sans',sans-serif; font-weight:700;
    font-size:0.82rem; color:#0f172a; display:flex; align-items:center; gap:6px;
}
.ntf-msg-dest {
    font-family:'Plus Jakarta Sans',sans-serif; font-size:0.7rem;
    color:#94a3b8; display:flex; align-items:center; gap:4px;
}
.ntf-msg-when {
    font-family:'Plus Jakarta Sans',sans-serif; font-size:0.68rem;
    color:#cbd5e1; font-style:italic;
}
.ntf-var-guide {
    background:#f8fafc; border:1px solid #e8ebf5; border-radius:12px;
    padding:12px 16px; margin-bottom:16px;
}
.ntf-var-title {
    font-family:'Montserrat',sans-serif; font-size:0.7rem; font-weight:700;
    color:#64748b; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:8px;
    display:flex; align-items:center; gap:6px;
}
.ntf-var-chips { display:flex; flex-wrap:wrap; gap:5px; }
.ntf-var-chip {
    display:inline-block; background:#fff; border:1px solid #e2e8f0; border-radius:20px;
    padding:3px 10px; font-size:0.76rem; font-family:'JetBrains Mono',monospace;
    color:#3b82f6; cursor:pointer; transition:all 0.15s; user-select:none;
}
.ntf-var-chip:hover { background:#dbeafe; border-color:#93c5fd; transform:scale(1.05); }
.ntf-tg-detected {
    display:flex; align-items:center; gap:10px; padding:8px 12px;
    background:#f8fafc; border:1px solid #e8ebf5; border-radius:10px; margin-bottom:6px;
}
.ntf-tg-name { font-weight:700; font-size:0.82rem; color:#0f172a; flex:1; min-width:0; }
.ntf-tg-user { font-size:0.72rem; color:#94a3b8; font-family:'JetBrains Mono',monospace; }
.ntf-tg-id { font-size:0.75rem; color:#64748b; font-family:'JetBrains Mono',monospace; }
</style>
"""


# ── Render principal ─────────────────────────────────────────────────────────

def render_tab_notificaciones(supabase, **deps):
    if not st.session_state.get('es_supervisor'):
        st.info("Esta sección es solo para supervisores y administradores.")
        return

    _TELEGRAM_BOT_TOKEN_DEFAULT = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
    _ROOTS = [r.strip() for r in st.secrets.get("ROOTS", "").split(",") if r.strip()]

    st.markdown(_CSS, unsafe_allow_html=True)
    render_page_header(
        "notificaciones",
        "Notificaciones",
        "Configura Telegram, contactos, observadores y mensajes automáticos.",
    )

    # ── 1. Configuración del Bot ─────────────────────────────────────────
    st.markdown(f'<div class="ntf-sec">{_svg("bot", 18, "#5b7cfa", mr=2)}Configuración del Bot</div>', unsafe_allow_html=True)
    _token_actual = _get_notif_config('bot_token', _TELEGRAM_BOT_TOKEN_DEFAULT)
    _bot_nombre   = _get_notif_config('bot_nombre', 'Cotizador ECH Bot')

    _c1, _c2 = st.columns([2, 1.5])
    with _c1:
        _token_inp = st.text_input("Token del Bot", value=_token_actual, type="password", key="notif_token")
    with _c2:
        _nombre_inp = st.text_input("Nombre del Bot", value=_bot_nombre, key="notif_nombre")

    _ba, _bb, _spacer = st.columns([1, 1, 3])
    with _ba:
        if st.button(":material/wifi_tethering: Probar conexión", key="btn_probar_bot", use_container_width=True):
            with st.spinner("Probando..."):
                try:
                    import requests as _rtest
                    _r = _rtest.get(f"https://api.telegram.org/bot{_token_inp}/getMe", timeout=10)
                    _rdata = _r.json()
                    _bot_ok = _rdata.get('ok', False)
                except Exception:
                    _bot_ok = False; _rdata = {}
            if _bot_ok:
                st.toast(f"Conectado: @{_rdata.get('result',{}).get('username','')}", icon=":material/check_circle:")
            else:
                st.toast("Token inválido o sin conexión", icon=":material/error:")
    with _bb:
        if st.button(":material/save: Guardar bot", key="btn_guardar_bot", use_container_width=True, type="primary"):
            _set_notif_config('bot_token', _token_inp)
            _set_notif_config('bot_nombre', _nombre_inp)
            st.toast("Bot guardado", icon=":material/check_circle:")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 2. Contactos del sistema ─────────────────────────────────────────
    st.markdown(f'<div class="ntf-sec">{_svg("users", 18, "#5b7cfa", mr=2)}Contactos del sistema</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ntf-hint">{_svg("send", 13, "#94a3b8", mr=4)}Cada usuario debe escribirle <b>/start</b> al bot una vez para obtener su Chat ID</div>', unsafe_allow_html=True)

    with st.expander(":material/sync: Detectar usuarios desde Telegram", expanded=False):
        st.markdown(f'<div class="ntf-hint">{_svg("refresh", 13, "#94a3b8", mr=4)}Muestra las personas que le han escrito al bot</div>', unsafe_allow_html=True)
        if st.button(":material/download: Obtener usuarios del bot", key="btn_get_updates"):
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
                    st.toast("Error al consultar el bot", icon=":material/error:")
            except Exception as _ue:
                st.toast(f"Error: {_ue}", icon=":material/error:")

        if st.session_state.get('_tg_updates') is not None:
            _updates = st.session_state['_tg_updates']
            if not _updates:
                st.info("No hay usuarios registrados aún. Pídeles que escriban /start al bot.")
            else:
                _det_html = ""
                for _up in _updates:
                    _uname = f"@{_up['username']}" if _up['username'] else "sin username"
                    _det_html += (
                        f'<div class="ntf-tg-detected">'
                        f'<span class="ntf-tg-name">{_up["nombre"]}</span>'
                        f'<span class="ntf-tg-user">{_uname}</span>'
                        f'<span class="ntf-tg-id">{_up["chat_id"]}</span>'
                        f'</div>'
                    )
                st.markdown(f'<div style="margin-top:8px">{_det_html}</div>', unsafe_allow_html=True)

    _contactos = _get_contactos_notif()
    _todos_usuarios = []
    try:
        _todos_usuarios = _fetch_users_notif()
        for _re_root in _ROOTS:
            _todos_usuarios.insert(0, {'email': _re_root.lower(), 'nombre': 'Root', 'rol': 'root', 'foto_url': ''})
    except Exception:
        pass

    _contactos_nuevos = dict(_contactos)

    with st.container(key="ntf_contacts_card"):
        for _idx, _uu in enumerate(_todos_usuarios):
            _ue  = _uu.get('email', '').lower()
            _ur  = _uu.get('rol', 'ejecutivo')
            _un  = _uu.get('nombre', _ue)
            _foto = _uu.get('foto_url', '')
            _iniciales = ''.join(p[0] for p in _un.split()[:2]).upper() if _un.split() else 'EC'
            _avatar_inner = f'<img src="{_foto}" alt="">' if _foto else _iniciales

            _badge_cls = _ur if _ur in ('root', 'admin', 'operacion') else 'ejecutivo'
            _badge_ico = {"root": "key", "admin": "crown", "operacion": "gear"}.get(_ur, "shield")
            _badge_txt = {"root": "Root", "admin": "Admin", "operacion": "Operación"}.get(_ur, "Ejecutivo")

            _has_chat = bool(_contactos.get(_ue, ''))
            _dot_cls = "on" if _has_chat else "off"

            _c_avatar, _c_input, _c_badge = st.columns([3, 2, 1.5])
            with _c_avatar:
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:12px;height:52px;">'
                    f'<div class="ntf-avatar">{_avatar_inner}</div>'
                    f'<div class="ntf-user-info">'
                    f'<div class="ntf-user-name">{_un}</div>'
                    f'<div class="ntf-user-email">{_ue}</div>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            with _c_input:
                _chat_val = _contactos.get(_ue, '')
                _new_chat = st.text_input(
                    "Chat ID", value=_chat_val, placeholder="Chat ID o @usuario",
                    key=f"chat_{_idx}_{_ue}", label_visibility="collapsed",
                )
                _contactos_nuevos[_ue] = _new_chat
            with _c_badge:
                st.markdown(
                    f'<div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;height:52px;">'
                    f'<span class="ntf-badge {_badge_cls}">{_svg(_badge_ico, 12, "currentColor", 2.2, 0, -1)}{_badge_txt}</span>'
                    f'<div class="ntf-status-dot {_dot_cls}"></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if st.button(":material/save: Guardar contactos", key="btn_guardar_contactos", type="primary"):
        _set_notif_config('contactos_json', _json.dumps(_contactos_nuevos))
        st.toast("Contactos guardados", icon=":material/check_circle:")
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 3. Observadores ──────────────────────────────────────────────────
    st.markdown(f'<div class="ntf-sec">{_svg("eye", 18, "#5b7cfa", mr=2)}Observadores externos</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ntf-hint">{_svg("send", 13, "#94a3b8", mr=4)}Sin cuenta en el sistema · Reciben todas las notificaciones</div>', unsafe_allow_html=True)

    _obs_list = _get_observadores_notif()
    _obs_list_edit = list(_obs_list) + [{'nombre': '', 'chat_id': ''}]
    _obs_nuevos = []
    for _oi, _ob in enumerate(_obs_list_edit):
        _oc1, _oc2, _oc3 = st.columns([2, 2, 0.5])
        with _oc1:
            _on = st.text_input("Nombre", value=_ob.get('nombre', ''), placeholder="Nombre (ej: Gerente)",
                                key=f"obs_nm_{_oi}", label_visibility="collapsed")
        with _oc2:
            _oid = st.text_input("Chat ID", value=_ob.get('chat_id', ''), placeholder="Chat ID o @usuario",
                                 key=f"obs_id_{_oi}", label_visibility="collapsed")
        with _oc3:
            _del = st.button(":material/delete:", key=f"obs_del_{_oi}", help="Eliminar")
        if _on.strip() and not _del:
            _obs_nuevos.append({'nombre': _on.strip(), 'chat_id': _oid.strip()})

    if st.button(":material/save: Guardar observadores", key="btn_guardar_obs", type="primary"):
        _set_notif_config('observadores_json', _json.dumps(_obs_nuevos))
        st.toast("Observadores guardados", icon=":material/check_circle:")
        st.rerun()

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 4. Grupo ─────────────────────────────────────────────────────────
    st.markdown(f'<div class="ntf-sec">{_svg("group", 18, "#5b7cfa", mr=2)}Grupo de Telegram</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="ntf-hint">{_svg("send", 13, "#94a3b8", mr=4)}Agrega el bot al grupo y escribe /start para obtener el ID</div>', unsafe_allow_html=True)

    _grupo_id     = _get_notif_config('grupo_chat_id', '')
    _grupo_filtro = _get_notif_config('grupo_filtro', 'todas')
    _gc1, _gc2 = st.columns(2)
    with _gc1:
        _g_id_inp = st.text_input("Chat ID del grupo", value=_grupo_id,
                                  placeholder="-1001234567890", key="notif_grupo_id")
    with _gc2:
        _filtro_opts = {
            "todas": "Todas las notificaciones",
            "solo_nuevas": "Solo nuevas cotizaciones",
            "solo_autorizaciones": "Solo autorizaciones",
            "ninguna": "No usar grupo"
        }
        _filtro_idx = list(_filtro_opts.keys()).index(_grupo_filtro) if _grupo_filtro in _filtro_opts else 0
        _filtro_sel = st.selectbox("Filtro de grupo", list(_filtro_opts.values()),
                                   index=_filtro_idx, key="notif_grupo_filtro")
        _filtro_val = list(_filtro_opts.keys())[list(_filtro_opts.values()).index(_filtro_sel)]

    if st.button(":material/save: Guardar grupo", key="btn_guardar_grupo", type="primary"):
        _set_notif_config('grupo_chat_id', _g_id_inp)
        _set_notif_config('grupo_filtro', _filtro_val)
        st.toast("Grupo guardado", icon=":material/check_circle:")

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── 5. Mensajes personalizables ──────────────────────────────────────
    st.markdown(f'<div class="ntf-sec">{_svg("msg", 18, "#5b7cfa", mr=2)}Mensajes personalizables</div>', unsafe_allow_html=True)

    _msg_defaults = {
        'msg_nueva_cotizacion': "\U0001f552 *Nueva cotización para revisar*\n\n*{ep}* · {ejecutivo}\nCliente: {cliente} · Monto: *{monto}*\nEstado: {estado}",
        'msg_autorizada':       "✅ *¡PRESUPUESTO AUTORIZADO!*\n\n\U0001f4cb *{ep}* · {cliente}\n\U0001f4b0 Margen aplicado: *{margen}%*\n\U0001f464 Autorizado por: *{supervisor}*\n\nYa puedes presentárselo a tu cliente \U0001f389",
        'msg_margen_removido':  "↩️ La cotización *{ep}* volvió a estado borrador.\nEl supervisor realizó cambios. Revisa el sistema."
    }

    _vars_html = ''.join(
        f'<span class="ntf-var-chip" onclick="navigator.clipboard.writeText(\'{v}\')">{v}</span>'
        for v in ['{ep}', '{ejecutivo}', '{cliente}', '{monto}', '{estado}', '{margen}', '{supervisor}']
    )
    st.markdown(
        f'<div class="ntf-var-guide">'
        f'<div class="ntf-var-title">{_svg("copy", 14, "#64748b", mr=3)}Variables — click para copiar</div>'
        f'<div class="ntf-var-chips">{_vars_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    _msg_configs = [
        ('msg_nueva_cotizacion', "Nueva cotización",       "send", "supervisores / admins / obs.", "Al guardar con plano"),
        ('msg_autorizada',       "Presupuesto autorizado",      "check","ejecutivo + observadores",     "Al guardar con margen"),
        ('msg_margen_removido',  "Margen removido",             "undo", "ejecutivo",                    "Al quitar margen"),
    ]
    _msgs_nuevos = {}
    _mcols = st.columns(3)
    for (_mk, _mtitulo, _micon, _mdest, _mcuando), _mcol in zip(_msg_configs, _mcols):
        _mval = _get_notif_config(_mk, _msg_defaults[_mk])
        with _mcol:
            st.markdown(
                f'<div class="ntf-msg-header">'
                f'<div class="ntf-msg-title">{_svg(_micon, 15, "#5b7cfa", mr=2)}{_mtitulo}</div>'
                f'<div class="ntf-msg-dest">{_svg("send", 11, "#94a3b8", mr=2)}{_mdest}</div>'
                f'<div class="ntf-msg-when">{_mcuando}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            _msgs_nuevos[_mk] = st.text_area("Mensaje", value=_mval, height=350,
                                              key=f"msg_{_mk}", label_visibility="collapsed")

    _mb1, _mb2 = st.columns([1, 1])
    with _mb1:
        if st.button(":material/undo: Restaurar por defecto", key="btn_restaurar_msgs"):
            for _mk, _mdef in _msg_defaults.items():
                _set_notif_config(_mk, _mdef)
            st.toast("Mensajes restaurados", icon=":material/check_circle:")
            st.rerun()
    with _mb2:
        if st.button(":material/save: Guardar mensajes", key="btn_guardar_msgs",
                     type="primary", use_container_width=True):
            for _mk, _mv in _msgs_nuevos.items():
                _set_notif_config(_mk, _mv)
            st.toast("Mensajes guardados", icon=":material/check_circle:")
