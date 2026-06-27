"""
Tab USUARIOS — Gestión de cuentas de ejecutivos y admins.
"""
import time
import streamlit as st
import httpx
from views.layout import render_page_header
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Bucket público para fotos de perfil (carpeta avatares/).
_AVATAR_BUCKET = "formulario-imagenes"


# ── helpers ──────────────────────────────────────────────────────────────────

def _avatar_path_from_url(url):
    """Extrae el path dentro del bucket desde una URL pública (ignora ?query/#)."""
    if not url:
        return ""
    marker = f"/public/{_AVATAR_BUCKET}/"
    i = url.find(marker)
    if i < 0:
        return ""
    return url[i + len(marker):].split("?")[0].split("#")[0]


def _subir_foto(uid, file_bytes, ext, content_type):
    """Sube/reemplaza la foto del usuario. Devuelve (url_publica, None) o (None, error).
    Agrega ?v=timestamp para evitar caché del navegador al cambiar la foto."""
    try:
        ext = (ext or "png").lower().replace("jpeg", "jpg")
        path = f"avatares/{uid}.{ext}"
        store = _supa_admin.storage.from_(_AVATAR_BUCKET)
        try:
            store.remove([path])
        except Exception:
            pass
        store.upload(path, file_bytes, {"content-type": content_type or "image/png", "upsert": "true"})
        base = store.get_public_url(path).split("?")[0]
        return f"{base}?v={int(time.time())}", None
    except Exception as e:
        return None, str(e)


def _eliminar_foto_storage(url):
    """Borra el archivo de la foto del storage (best-effort)."""
    try:
        path = _avatar_path_from_url(url)
        if path:
            _supa_admin.storage.from_(_AVATAR_BUCKET).remove([path])
    except Exception:
        pass

def _get_roots():
    raw = st.secrets.get("ROOTS", "") if hasattr(st, "secrets") else ""
    return {r.strip().lower() for r in raw.split(",") if r.strip()}


def _hdr():
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }


# ── REST API ─────────────────────────────────────────────────────────────────

def _listar_usuarios():
    try:
        roots = _get_roots()
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_hdr(),
            params={"per_page": 1000, "page": 1},
            timeout=15,
        )
        r.raise_for_status()
        out = []
        for u in r.json().get("users", []):
            email = u.get("email") or ""
            if email.lower() in roots:
                continue
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            out.append({
                "id": u["id"],
                "email": email,
                "nombre": meta.get("nombre", email),
                "rol": meta.get("rol", "ejecutivo"),
                "telefono": meta.get("telefono", "") or "",
                "foto_url": meta.get("foto_url", "") or "",
                "created_at": str(u.get("created_at", ""))[:10],
            })
        return out, None
    except Exception as e:
        return [], str(e)


def _api_put(uid, payload):
    try:
        r = httpx.put(
            f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
            headers=_hdr(), json=payload, timeout=15,
        )
        if r.status_code in (200, 204):
            return True, None
        try:
            msg = r.json().get("msg") or r.json().get("message") or r.text
        except Exception:
            msg = r.text
        return False, f"HTTP {r.status_code}: {msg}"
    except Exception as e:
        return False, str(e)


def _api_post(payload):
    try:
        r = httpx.post(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_hdr(), json=payload, timeout=15,
        )
        if r.status_code in (200, 201):
            return True, r.json()
        try:
            msg = r.json().get("msg") or r.json().get("message") or r.text
        except Exception:
            msg = r.text
        return False, f"HTTP {r.status_code}: {msg}"
    except Exception as e:
        return False, str(e)


def _api_delete(uid):
    try:
        r = httpx.delete(
            f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
            headers=_hdr(), timeout=15,
        )
        if r.status_code in (200, 204):
            return True, None
        try:
            body = r.json()
            msg = body.get("msg") or body.get("message") or body.get("error") or r.text
        except Exception:
            msg = r.text
        return False, f"HTTP {r.status_code}: {msg}"
    except Exception as e:
        return False, str(e)


# ── Diálogos (deben estar a nivel de módulo) ─────────────────────────────────

@st.dialog("Crear nuevo usuario", width="large")
def _dlg_crear():
    col1, col2 = st.columns(2)
    with col1:
        nombre   = st.text_input("Nombre completo *", placeholder="Juan Perez", key="dc_nombre")
        email    = st.text_input("Correo electrónico *", placeholder="juan@empresa.cl", key="dc_email")
    with col2:
        telefono = st.text_input("Teléfono", placeholder="+56912345678", key="dc_tel")
        password = st.text_input("Contraseña *", type="password", placeholder="Mín. 6 caracteres", key="dc_pass")

    labels = {"ejecutivo": "👤 Ejecutivo", "admin": "👑 Administrador", "operacion": "⚙️ Operación"}
    rol = st.selectbox("Rol", list(labels.keys()), format_func=lambda r: labels[r], key="dc_rol")
    if rol == "admin":
        st.caption("Los administradores ven todas las cotizaciones y pueden gestionar usuarios.")
    elif rol == "operacion":
        st.caption("Los usuarios de Operación solo acceden a la pestaña Operaciones.")

    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("✅ Crear cuenta", type="primary", use_container_width=True, key="dc_ok"):
            errores = []
            if not nombre.strip():
                errores.append("nombre")
            if not email.strip() or "@" not in email:
                errores.append("correo válido")
            if len(password) < 6:
                errores.append("contraseña (mín. 6 caracteres)")
            if errores:
                st.error(f"Requerido: {', '.join(errores)}")
            else:
                with st.spinner("Creando cuenta..."):
                    ok, data = _api_post({
                        "email": email.strip().lower(),
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {
                            "nombre": nombre.strip().upper(),
                            "telefono": telefono.strip(),
                            "rol": rol,
                        },
                    })
                if ok:
                    nuevo = {
                        "id": data.get("id", ""),
                        "email": email.strip().lower(),
                        "nombre": nombre.strip().upper(),
                        "rol": rol,
                        "telefono": telefono.strip(),
                        "created_at": str(data.get("created_at", ""))[:10],
                    }
                    st.session_state.setdefault("_usr_data", []).append(nuevo)
                    st.session_state["_usr_toast"] = f"✅ Cuenta creada: {nombre.strip().upper()}"
                    st.rerun()
                else:
                    st.error(f"❌ {data}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dc_no"):
            st.rerun()


@st.dialog("Editar usuario", width="large")
def _dlg_editar(u):
    _foto = u.get("foto_url", "") or ""
    # ── Foto de perfil ──
    st.markdown("**Foto de perfil**")
    fc1, fc2 = st.columns([1, 3])
    with fc1:
        if _foto:
            st.markdown(
                f'<img src="{_foto}" style="width:96px;height:96px;border-radius:50%;'
                f'object-fit:cover;border:3px solid #e2e8f0;display:block;">',
                unsafe_allow_html=True)
        else:
            _ini = (u.get("nombre") or u.get("email") or "?")[0].upper()
            st.markdown(
                f'<div style="width:96px;height:96px;border-radius:50%;background:#e2e8f0;'
                f'display:flex;align-items:center;justify-content:center;font-size:2.2rem;'
                f'font-weight:800;color:#64748b;">{_ini}</div>', unsafe_allow_html=True)
    with fc2:
        _file = st.file_uploader(
            "Subir nueva foto", type=["png", "jpg", "jpeg", "webp"],
            key=f"de_foto_{u['id']}", label_visibility="collapsed")
        b_sub, b_del = st.columns(2)
        with b_sub:
            if st.button(("Cambiar foto" if _foto else "Subir foto"), icon=":material/upload:",
                         use_container_width=True, key="de_foto_sub", disabled=_file is None):
                _ext = _file.name.rsplit(".", 1)[-1] if "." in _file.name else "png"
                with st.spinner("Subiendo foto..."):
                    _url, _e = _subir_foto(u["id"], _file.getvalue(), _ext, _file.type)
                    if _url:
                        ok, err = _api_put(u["id"], {"user_metadata": {
                            "nombre": u["nombre"], "telefono": u.get("telefono", ""),
                            "rol": u["rol"], "foto_url": _url}})
                    else:
                        ok, err = False, _e
                if ok:
                    for cu in st.session_state.get("_usr_data", []):
                        if cu["id"] == u["id"]:
                            cu["foto_url"] = _url
                            break
                    st.session_state["_usr_toast"] = f"✅ Foto de {u['nombre']} actualizada."
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
        with b_del:
            if st.button("Eliminar foto", icon=":material/delete:", use_container_width=True,
                         key="de_foto_del", disabled=not _foto):
                with st.spinner("Eliminando..."):
                    _eliminar_foto_storage(_foto)
                    ok, err = _api_put(u["id"], {"user_metadata": {
                        "nombre": u["nombre"], "telefono": u.get("telefono", ""),
                        "rol": u["rol"], "foto_url": ""}})
                if ok:
                    for cu in st.session_state.get("_usr_data", []):
                        if cu["id"] == u["id"]:
                            cu["foto_url"] = ""
                            break
                    st.session_state["_usr_toast"] = f"✅ Foto de {u['nombre']} eliminada."
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre completo", value=u["nombre"], key="de_nombre")
    with col2:
        email  = st.text_input("Correo electrónico", value=u["email"], key="de_email")
    telefono = st.text_input("Teléfono", value=u.get("telefono", ""), key="de_tel")

    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("✅ Guardar cambios", type="primary", use_container_width=True, key="de_ok"):
            if not nombre.strip() or not email.strip() or "@" not in email:
                st.error("Nombre y correo válidos son requeridos.")
            else:
                with st.spinner("Guardando..."):
                    ok, err = _api_put(u["id"], {
                        "email": email.strip().lower(),
                        "user_metadata": {
                            "nombre": nombre.strip().upper(),
                            "telefono": telefono.strip(),
                            "rol": u["rol"],
                            "foto_url": u.get("foto_url", ""),
                        },
                    })
                if ok:
                    for cu in st.session_state.get("_usr_data", []):
                        if cu["id"] == u["id"]:
                            cu.update(
                                nombre=nombre.strip().upper(),
                                email=email.strip().lower(),
                                telefono=telefono.strip(),
                            )
                            break
                    st.session_state["_usr_toast"] = f"✅ Datos de {u['nombre']} actualizados."
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="de_no"):
            st.rerun()


@st.dialog("Cambiar contraseña")
def _dlg_password(u):
    st.markdown(f"**{u['nombre']}** · {u['email']}")
    st.divider()
    nueva    = st.text_input("Nueva contraseña", type="password", placeholder="Mínimo 6 caracteres", key="dp_pwd")
    confirma = st.text_input("Confirmar contraseña", type="password", key="dp_pwd2")
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("✅ Actualizar", type="primary", use_container_width=True, key="dp_ok"):
            if len(nueva or "") < 6:
                st.error("Mínimo 6 caracteres.")
            elif nueva != confirma:
                st.error("Las contraseñas no coinciden.")
            else:
                with st.spinner("Actualizando..."):
                    ok, err = _api_put(u["id"], {"password": nueva})
                if ok:
                    st.session_state["_usr_toast"] = f"✅ Contraseña de {u['nombre']} actualizada."
                    st.rerun()
                else:
                    st.error(f"❌ {err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dp_no"):
            st.rerun()


@st.dialog("Cambiar rol")
def _dlg_rol(u):
    rol_actual = u.get("rol", "ejecutivo")
    labels = {"ejecutivo": "👤 Ejecutivo", "operacion": "⚙️ Operación", "admin": "👑 Admin"}
    st.markdown(f"**{u['nombre']}** · Rol actual: **{labels.get(rol_actual, rol_actual)}**")
    st.divider()
    opciones  = [r for r in ["ejecutivo", "operacion", "admin"] if r != rol_actual]
    nuevo_rol = st.selectbox("Nuevo rol", opciones, format_func=lambda r: labels[r], key="dr_rol")
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("✅ Confirmar cambio", type="primary", use_container_width=True, key="dr_ok"):
            with st.spinner("Actualizando..."):
                ok, err = _api_put(u["id"], {
                    "user_metadata": {
                        "nombre": u["nombre"],
                        "telefono": u.get("telefono", ""),
                        "rol": nuevo_rol,
                        "foto_url": u.get("foto_url", ""),
                    }
                })
            if ok:
                for cu in st.session_state.get("_usr_data", []):
                    if cu["id"] == u["id"]:
                        cu["rol"] = nuevo_rol
                        break
                st.session_state["_usr_toast"] = f"✅ {u['nombre']} ahora es {labels[nuevo_rol]}."
                st.rerun()
            else:
                st.error(f"❌ {err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dr_no"):
            st.rerun()


@st.dialog("⚠️ Confirmar eliminación")
def _dlg_eliminar(u):
    st.warning(f"¿Eliminar permanentemente a **{u['nombre']}**?")
    st.caption(f"✉️ {u['email']}")
    st.error("Esta acción **no se puede deshacer**.")
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("🗑️ Sí, eliminar", type="primary", use_container_width=True, key="dd_ok"):
            with st.spinner("Eliminando..."):
                ok, err = _api_delete(u["id"])
            if ok:
                st.session_state["_usr_data"] = [
                    cu for cu in st.session_state.get("_usr_data", [])
                    if cu["id"] != u["id"]
                ]
                st.session_state["_usr_toast"] = f"✅ Usuario {u['nombre']} eliminado."
                st.rerun()
            else:
                st.error(f"❌ {err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dd_no"):
            st.rerun()


# ── estilos ───────────────────────────────────────────────────────────────────

_CSS = """<style>
.hdr-usr {
    background: linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);
    border-radius:16px; padding:28px 32px; margin-bottom:20px;
    box-shadow:0 8px 32px rgba(15,52,96,.4);
    display:flex; align-items:center; gap:16px;
}
.usr-card {
    background:var(--background-color,#fff);
    border-radius:12px; border:1.5px solid #e8eaf0;
    padding:12px 16px; display:flex; align-items:center; gap:14px;
    box-shadow:0 2px 6px rgba(0,0,0,.04); transition:box-shadow .2s;
}
.usr-card:hover { box-shadow:0 4px 14px rgba(0,0,0,.09); }
.usr-card.r-admin     { border-left:4px solid #8b5cf6; }
.usr-card.r-ejecutivo { border-left:4px solid #3b82f6; }
.usr-card.r-operacion { border-left:4px solid #f59e0b; }
.usr-av {
    width:42px; height:42px; border-radius:50%;
    display:flex; align-items:center; justify-content:center;
    font-size:1.1rem; font-weight:800; color:#fff; flex-shrink:0;
}
.av-admin     { background:linear-gradient(135deg,#7c3aed,#a78bfa); }
.av-ejecutivo { background:linear-gradient(135deg,#2563eb,#60a5fa); }
.av-operacion { background:linear-gradient(135deg,#b45309,#f59e0b); }
.usr-nm { font-weight:700; font-size:.94rem; color:#1e2447; }
.usr-em { font-size:.79rem; color:#64748b; margin-top:1px; }
.usr-mt { font-size:.72rem; color:#94a3b8; margin-top:1px; }
.rpill { display:inline-block; padding:2px 9px; border-radius:20px; font-size:.70rem; font-weight:700; }
.rp-admin     { background:#ede9fe; color:#6d28d9; }
.rp-ejecutivo { background:#dbeafe; color:#1d4ed8; }
.rp-operacion { background:#fef3c7; color:#b45309; }
</style>"""

_ROL_META = {
    "admin":          ("👑 Admin",     "r-admin",     "av-admin",     "rp-admin"),
    "administrador":  ("👑 Admin",     "r-admin",     "av-admin",     "rp-admin"),
    "ejecutivo":      ("👤 Ejecutivo", "r-ejecutivo", "av-ejecutivo", "rp-ejecutivo"),
    "operacion":      ("⚙️ Operación", "r-operacion", "av-operacion", "rp-operacion"),
}


# ── render principal ──────────────────────────────────────────────────────────

def _diagnostico_api():
    """Panel de diagnóstico para verificar conectividad con Supabase Auth."""
    import httpx as _hx
    st.markdown("#### 🔬 Diagnóstico API Supabase")
    url  = SUPABASE_URL or "(no configurado)"
    key  = (SUPABASE_SERVICE_KEY or "")
    masked = f"{key[:8]}…{key[-4:]}" if len(key) > 12 else "(vacío)"
    st.code(f"SUPABASE_URL       = {url}\nSERVICE_KEY (mask) = {masked}", language="text")

    if st.button("▶ Ejecutar prueba GET /auth/v1/admin/users", key="diag_test_btn"):
        with st.spinner("Llamando a Supabase..."):
            try:
                r = _hx.get(
                    f"{SUPABASE_URL}/auth/v1/admin/users",
                    headers=_hdr(),
                    params={"per_page": 5, "page": 1},
                    timeout=15,
                )
                st.code(
                    f"HTTP status : {r.status_code}\n"
                    f"Headers resp: {dict(r.headers)}\n"
                    f"Body (500c) : {r.text[:500]}",
                    language="json",
                )
            except Exception as ex:
                st.error(f"Excepción: {ex}")

    if st.button("▶ Probar DELETE de usuario (ingresa ID)", key="diag_del_btn"):
        uid_test = st.text_input("UUID del usuario a eliminar", key="diag_del_uid")
        if uid_test.strip():
            with st.spinner("Llamando DELETE..."):
                try:
                    r = _hx.delete(
                        f"{SUPABASE_URL}/auth/v1/admin/users/{uid_test.strip()}",
                        headers=_hdr(),
                        timeout=15,
                    )
                    st.code(f"HTTP {r.status_code}\n{r.text[:500]}", language="json")
                except Exception as ex:
                    st.error(f"Excepción: {ex}")


def render_tab_usuarios(supabase_admin=None, **deps):
    if not st.session_state.get("modo_admin"):
        st.info("🔒 Solo administradores pueden gestionar usuarios.")
        return

    st.markdown(_CSS, unsafe_allow_html=True)

    # Toast de feedback que viene de los dialogs tras st.rerun()
    if "_usr_toast" in st.session_state:
        st.toast(st.session_state.pop("_usr_toast"))

    # Cargar lista una sola vez por sesión
    if "_usr_data" not in st.session_state:
        with st.spinner("Cargando usuarios..."):
            data, err = _listar_usuarios()
        if err:
            st.error(f"❌ Error al cargar usuarios: {err}")
            with st.expander("🔬 Diagnóstico", expanded=True):
                _diagnostico_api()
            if st.button("🔄 Reintentar", key="btn_usr_retry"):
                st.rerun()
            return
        st.session_state["_usr_data"] = data

    usuarios = st.session_state["_usr_data"]

    # Header
    render_page_header(
        "usuarios",
        "Gesti&#243;n de Usuarios",
        "Crea y administra las cuentas de acceso del equipo.",
    )

    # Stats + botones de acción global
    n_adm = sum(1 for u in usuarios if u.get("rol") in ("admin", "administrador"))
    n_ej  = sum(1 for u in usuarios if u.get("rol") == "ejecutivo")
    n_op  = sum(1 for u in usuarios if u.get("rol") == "operacion")

    c_stats, c_nuevo, c_ref = st.columns([5, 1.6, 1])
    with c_stats:
        st.markdown(
            f'<div style="display:flex;gap:10px;align-items:center;padding-top:6px;">'
            f'<span style="font-weight:800;color:#1e2447;">👥 {len(usuarios)} usuarios</span>'
            f'<span class="rpill rp-admin">👑 {n_adm} Admin</span>'
            f'<span class="rpill rp-ejecutivo">👤 {n_ej} Ejecutivo</span>'
            f'<span class="rpill rp-operacion">⚙️ {n_op} Operación</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with c_nuevo:
        if st.button("➕ Nuevo usuario", type="primary", use_container_width=True, key="btn_usr_nuevo"):
            _dlg_crear()
    with c_ref:
        if st.button("🔄 Actualizar", use_container_width=True, key="btn_usr_ref"):
            st.session_state.pop("_usr_data", None)
            st.rerun()

    with st.expander("🔬 Diagnóstico API", expanded=False):
        _diagnostico_api()

    st.markdown("---")

    if not usuarios:
        st.info("No hay usuarios registrados aún.")
        return

    es_root    = st.session_state.get("es_root", False)
    rol_sesion = st.session_state.get("rol_usuario", "")

    for u in usuarios:
        rol_u = u.get("rol", "ejecutivo")
        lbl, cls_row, cls_av, cls_rp = _ROL_META.get(
            rol_u, (f"👤 {rol_u.capitalize()}", "r-ejecutivo", "av-ejecutivo", "rp-ejecutivo")
        )
        inicial  = (u.get("nombre") or u.get("email") or "?")[0].upper()
        tel_txt  = f" · 📞 {u['telefono']}" if u.get("telefono") else ""
        puede    = (es_root or rol_sesion == "admin") and rol_u != "root"
        _foto_u  = u.get("foto_url", "") or ""
        _av_html = (f'<img class="usr-av {cls_av}" src="{_foto_u}" style="object-fit:cover;" alt="">'
                    if _foto_u else f'<div class="usr-av {cls_av}">{inicial}</div>')

        c_card, c_btns = st.columns([6, 2])
        with c_card:
            st.markdown(
                f'<div class="usr-card {cls_row}">'
                f'{_av_html}'
                f'<div style="flex:1;min-width:0;">'
                f'<div class="usr-nm">{u["nombre"]}</div>'
                f'<div class="usr-em">✉️ {u["email"]}{tel_txt}</div>'
                f'<div class="usr-mt">📅 {u["created_at"]}'
                f' &nbsp;<span class="rpill {cls_rp}">{lbl}</span></div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with c_btns:
            if puede:
                st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
                b1, b2, b3, b4 = st.columns(4)
                with b1:
                    if st.button("✏️", key=f"e_{u['id']}", use_container_width=True, help="Editar datos"):
                        _dlg_editar(u)
                with b2:
                    if st.button("🔄", key=f"r_{u['id']}", use_container_width=True, help="Cambiar rol"):
                        _dlg_rol(u)
                with b3:
                    if st.button("🔑", key=f"p_{u['id']}", use_container_width=True, help="Cambiar contraseña"):
                        _dlg_password(u)
                with b4:
                    if st.button("🗑️", key=f"d_{u['id']}", use_container_width=True, help="Eliminar usuario"):
                        _dlg_eliminar(u)
            elif rol_u == "root":
                st.markdown(
                    "<div style='padding:10px 0;'>"
                    "<span style='color:#f59e0b;font-size:.8rem;font-weight:600;'>🔑 Cuenta Root — protegida</span>"
                    "</div>",
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
