"""
Tab USUARIOS — Gestión de cuentas (crear, editar, foto, rol, bloquear, eliminar).

Seguridad: TODAS las mutaciones de cuentas usan la SERVICE KEY y se ejecutan
server-side (Python). La service key NUNCA se expone al navegador. El directorio
se renderiza como HTML propio en un components.html; sus botones de acción enrutan
a Python con el patrón "query param + botón nativo oculto" (sin recargar la página).

Integridad de datos (CRÍTICO): al eliminar un usuario NUNCA se borra su actividad
de presupuestos. La tabla `cotizaciones` tiene `user_id` (FK a auth.users, nullable);
antes de borrar la cuenta se DESVINCULAN sus cotizaciones (user_id=null) — la
atribución sobrevive por `asesor_email`/`asesor_nombre`. Si la desvinculación falla,
el borrado se ABORTA para proteger los datos.
"""
import html as _html
import time

import httpx
import streamlit as st
import streamlit.components.v1 as _components

from views.layout import render_page_header
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY

# Bucket público para fotos de perfil (carpeta avatares/).
_AVATAR_BUCKET = "formulario-imagenes"


# ── Iconos SVG (estilo Lucide) ────────────────────────────────────────────────

def _svg(path, size=16, color="currentColor", sw=2):
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round">{path}</svg>')


_IC = {
    "user_plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><line x1="19" x2="19" y1="8" y2="14"/><line x1="22" x2="16" y1="11" y2="11"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4z"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
    "key": '<circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "unlock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><path d="M14 2v5h5"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><line x1="10" x2="8" y1="9" y2="9"/>',
    "crown": '<path d="m2 4 3 12h14l3-12-6 7-4-7-4 7-6-7z"/><path d="M5 20h14"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18"/><path d="M6 6l12 12"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
}

# Metadatos por rol: (label, icono, color)
_ROLES = {
    "admin":     ("Administrador", "crown",    "#7c3aed"),
    "ejecutivo": ("Ejecutivo",     "user",     "#2563eb"),
    "operacion": ("Operación",     "settings", "#b45309"),
}


# ── helpers de foto ───────────────────────────────────────────────────────────

def _avatar_path_from_url(url):
    if not url:
        return ""
    marker = f"/public/{_AVATAR_BUCKET}/"
    i = url.find(marker)
    if i < 0:
        return ""
    return url[i + len(marker):].split("?")[0].split("#")[0]


def _subir_foto(uid, file_bytes, ext, content_type):
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


# ── REST API (auth admin — service key, server-side) ──────────────────────────

def _listar_usuarios():
    try:
        roots = _get_roots()
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers=_hdr(), params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = []
        for u in r.json().get("users", []):
            email = u.get("email") or ""
            if email.lower() in roots:
                continue
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            _ban = u.get("banned_until")
            out.append({
                "id": u["id"],
                "email": email,
                "nombre": meta.get("nombre", email),
                "rol": meta.get("rol", "ejecutivo"),
                "telefono": meta.get("telefono", "") or "",
                "foto_url": meta.get("foto_url", "") or "",
                "created_at": str(u.get("created_at", ""))[:10],
                "bloqueado": bool(_ban) and str(_ban).lower() not in ("", "none", "null"),
            })
        return out, None
    except Exception as e:
        return [], str(e)


def _api_put(uid, payload):
    try:
        r = httpx.put(f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
                      headers=_hdr(), json=payload, timeout=15)
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
        r = httpx.post(f"{SUPABASE_URL}/auth/v1/admin/users",
                       headers=_hdr(), json=payload, timeout=15)
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
        r = httpx.delete(f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
                         headers=_hdr(), timeout=15)
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


def _bloquear(uid, bloquear=True):
    """Bloquea (ban ~100 años) o desbloquea (ban_duration='none') la cuenta."""
    return _api_put(uid, {"ban_duration": "876000h" if bloquear else "none"})


def _detach_cotizaciones(uid):
    """Desvincula (user_id=null) las cotizaciones del usuario para que NUNCA se
    borren al eliminar la cuenta. La atribución persiste por asesor_email/nombre."""
    try:
        r = httpx.patch(
            f"{SUPABASE_URL}/rest/v1/cotizaciones?user_id=eq.{uid}",
            headers={**_hdr(), "Prefer": "return=minimal"},
            json={"user_id": None}, timeout=30,
        )
        if r.status_code in (200, 204):
            return True, None
        return False, f"HTTP {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


def _eliminar_seguro(uid):
    """Elimina la cuenta SOLO tras desvincular sus presupuestos. Si la
    desvinculación falla, ABORTA (no se arriesga a borrar la actividad)."""
    ok, err = _detach_cotizaciones(uid)
    if not ok:
        return False, ("No se pudo proteger los presupuestos del usuario "
                       f"(desvinculación falló): {err}. Eliminación cancelada.")
    return _api_delete(uid)


def _presupuestos_por_email():
    """dict email(min) -> cantidad de presupuestos creados."""
    out = {}
    try:
        rows = _supa_admin.table("cotizaciones").select("asesor_email").limit(5000).execute().data or []
        for r in rows:
            em = (r.get("asesor_email") or "").strip().lower()
            if em:
                out[em] = out.get(em, 0) + 1
    except Exception:
        pass
    return out


def _invalidar():
    st.session_state.pop("_usr_data", None)
    st.session_state.pop("_usr_counts", None)


# ── Diálogos (server-side, seguros) ───────────────────────────────────────────

@st.dialog("Crear nuevo usuario", width="large")
def _dlg_crear():
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre completo *", placeholder="Juan Pérez", key="dc_nombre")
        email  = st.text_input("Correo electrónico *", placeholder="juan@empresa.cl", key="dc_email")
    with col2:
        telefono = st.text_input("Teléfono", placeholder="+56912345678", key="dc_tel")
        password = st.text_input("Contraseña *", type="password", placeholder="Mín. 6 caracteres", key="dc_pass")

    labels = {"ejecutivo": "Ejecutivo", "admin": "Administrador", "operacion": "Operación"}
    rol = st.selectbox("Rol", list(labels.keys()), format_func=lambda r: labels[r], key="dc_rol")
    if rol == "admin":
        st.caption("Los administradores ven todas las cotizaciones y gestionan usuarios.")
    elif rol == "operacion":
        st.caption("Los usuarios de Operación solo acceden a la pestaña Operaciones.")

    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("Crear cuenta", type="primary", use_container_width=True,
                     icon=":material/person_add:", key="dc_ok"):
            errores = []
            if not nombre.strip():
                errores.append("nombre")
            if not email.strip() or "@" not in email:
                errores.append("correo válido")
            if len(password) < 6:
                errores.append("contraseña (mín. 6)")
            if errores:
                st.error(f"Requerido: {', '.join(errores)}")
            else:
                with st.spinner("Creando cuenta..."):
                    ok, data = _api_post({
                        "email": email.strip().lower(),
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": {"nombre": nombre.strip().upper(),
                                          "telefono": telefono.strip(), "rol": rol},
                    })
                if ok:
                    _invalidar()
                    st.session_state["_usr_toast"] = f"Cuenta creada: {nombre.strip().upper()}"
                    st.rerun()
                else:
                    st.error(f"{data}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dc_no"):
            st.rerun()


@st.dialog("Editar usuario", width="large")
def _dlg_editar(u):
    _foto = u.get("foto_url", "") or ""
    st.markdown("**Foto de perfil**")
    fc1, fc2 = st.columns([1, 3])
    with fc1:
        if _foto:
            st.markdown(f'<img src="{_foto}" style="width:96px;height:96px;border-radius:50%;'
                        f'object-fit:cover;border:3px solid #e2e8f0;display:block;">',
                        unsafe_allow_html=True)
        else:
            _ini = (u.get("nombre") or u.get("email") or "?")[0].upper()
            st.markdown(f'<div style="width:96px;height:96px;border-radius:50%;background:#e2e8f0;'
                        f'display:flex;align-items:center;justify-content:center;font-size:2.2rem;'
                        f'font-weight:800;color:#64748b;">{_ini}</div>', unsafe_allow_html=True)
    with fc2:
        _file = st.file_uploader("Subir nueva foto", type=["png", "jpg", "jpeg", "webp"],
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
                    _invalidar()
                    st.session_state["_usr_toast"] = f"Foto de {u['nombre']} actualizada."
                    st.rerun()
                else:
                    st.error(f"{err}")
        with b_del:
            if st.button("Eliminar foto", icon=":material/delete:", use_container_width=True,
                         key="de_foto_del", disabled=not _foto):
                with st.spinner("Eliminando..."):
                    _eliminar_foto_storage(_foto)
                    ok, err = _api_put(u["id"], {"user_metadata": {
                        "nombre": u["nombre"], "telefono": u.get("telefono", ""),
                        "rol": u["rol"], "foto_url": ""}})
                if ok:
                    _invalidar()
                    st.session_state["_usr_toast"] = f"Foto de {u['nombre']} eliminada."
                    st.rerun()
                else:
                    st.error(f"{err}")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        nombre = st.text_input("Nombre completo", value=u["nombre"], key="de_nombre")
    with col2:
        email = st.text_input("Correo electrónico", value=u["email"], key="de_email")
    telefono = st.text_input("Teléfono", value=u.get("telefono", ""), key="de_tel")

    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("Guardar cambios", type="primary", use_container_width=True,
                     icon=":material/save:", key="de_ok"):
            if not nombre.strip() or not email.strip() or "@" not in email:
                st.error("Nombre y correo válidos son requeridos.")
            else:
                with st.spinner("Guardando..."):
                    ok, err = _api_put(u["id"], {
                        "email": email.strip().lower(),
                        "user_metadata": {"nombre": nombre.strip().upper(),
                                          "telefono": telefono.strip(), "rol": u["rol"],
                                          "foto_url": u.get("foto_url", "")},
                    })
                if ok:
                    _invalidar()
                    st.session_state["_usr_toast"] = f"Datos de {u['nombre']} actualizados."
                    st.rerun()
                else:
                    st.error(f"{err}")
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
        if st.button("Actualizar", type="primary", use_container_width=True,
                     icon=":material/lock_reset:", key="dp_ok"):
            if len(nueva or "") < 6:
                st.error("Mínimo 6 caracteres.")
            elif nueva != confirma:
                st.error("Las contraseñas no coinciden.")
            else:
                with st.spinner("Actualizando..."):
                    ok, err = _api_put(u["id"], {"password": nueva})
                if ok:
                    st.session_state["_usr_toast"] = f"Contraseña de {u['nombre']} actualizada."
                    st.rerun()
                else:
                    st.error(f"{err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dp_no"):
            st.rerun()


@st.dialog("Cambiar rol")
def _dlg_rol(u):
    rol_actual = u.get("rol", "ejecutivo")
    labels = {"ejecutivo": "Ejecutivo", "operacion": "Operación", "admin": "Administrador"}
    st.markdown(f"**{u['nombre']}** · Rol actual: **{labels.get(rol_actual, rol_actual)}**")
    st.divider()
    opciones  = [r for r in ["ejecutivo", "operacion", "admin"] if r != rol_actual]
    nuevo_rol = st.selectbox("Nuevo rol", opciones, format_func=lambda r: labels[r], key="dr_rol")
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("Confirmar cambio", type="primary", use_container_width=True,
                     icon=":material/admin_panel_settings:", key="dr_ok"):
            with st.spinner("Actualizando..."):
                ok, err = _api_put(u["id"], {"user_metadata": {
                    "nombre": u["nombre"], "telefono": u.get("telefono", ""),
                    "rol": nuevo_rol, "foto_url": u.get("foto_url", "")}})
            if ok:
                _invalidar()
                st.session_state["_usr_toast"] = f"{u['nombre']} ahora es {labels[nuevo_rol]}."
                st.rerun()
            else:
                st.error(f"{err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dr_no"):
            st.rerun()


@st.dialog("Bloquear / Desbloquear acceso")
def _dlg_bloquear(u):
    blocked = u.get("bloqueado")
    if blocked:
        st.success(f"**{u['nombre']}** está **bloqueado** actualmente.")
        st.caption("Al desbloquear, el usuario podrá volver a iniciar sesión. Sus datos y "
                   "presupuestos nunca se vieron afectados.")
        _txt, _ico = "Desbloquear acceso", ":material/lock_open:"
    else:
        st.warning(f"¿Bloquear el acceso de **{u['nombre']}**?")
        st.caption("El usuario no podrá iniciar sesión, pero **se conserva la cuenta y toda su "
                   "actividad** (presupuestos, etc.). Es reversible en cualquier momento. "
                   "Recomendado cuando alguien se va de la empresa.")
        _txt, _ico = "Bloquear acceso", ":material/block:"
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button(_txt, type="primary", use_container_width=True, icon=_ico, key="db_ok"):
            with st.spinner("Aplicando..."):
                ok, err = _bloquear(u["id"], bloquear=not blocked)
            if ok:
                _invalidar()
                st.session_state["_usr_toast"] = (
                    f"{u['nombre']} {'desbloqueado' if blocked else 'bloqueado'}.")
                st.rerun()
            else:
                st.error(f"{err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="db_no"):
            st.rerun()


@st.dialog("Eliminar usuario")
def _dlg_eliminar(u, n_presup=0):
    st.markdown(f"### {u['nombre']}")
    st.caption(u["email"])
    st.divider()
    if n_presup > 0:
        st.info(f"Este usuario tiene **{n_presup} presupuesto(s)** creados. "
                "Al eliminar la cuenta, **esos presupuestos SE CONSERVAN** (no se borran); "
                "solo se desvinculan de la cuenta, manteniendo la atribución por nombre y correo.")
        st.caption("Si solo quieres impedir el acceso, considera **Bloquear** en lugar de eliminar.")
    st.error("Eliminar la cuenta de acceso es **permanente** y no se puede deshacer.")
    st.divider()
    ok_col, no_col = st.columns(2)
    with ok_col:
        if st.button("Sí, eliminar cuenta", type="primary", use_container_width=True,
                     icon=":material/delete_forever:", key="dd_ok"):
            with st.spinner("Protegiendo presupuestos y eliminando cuenta..."):
                ok, err = _eliminar_seguro(u["id"])
            if ok:
                _invalidar()
                st.session_state["_usr_toast"] = (
                    f"Usuario {u['nombre']} eliminado. {n_presup} presupuesto(s) conservados.")
                st.rerun()
            else:
                st.error(f"{err}")
    with no_col:
        if st.button("Cancelar", use_container_width=True, key="dd_no"):
            st.rerun()


# ── Directorio (HTML propio en iframe) ────────────────────────────────────────

def _build_directory_html(usuarios, counts):
    """Grid de tarjetas de usuario con acciones. Los botones enrutan a Python vía
    query param + botón nativo oculto (la service key nunca toca el navegador)."""
    def esc(s):
        return _html.escape(str(s or ""))

    cards = []
    for u in usuarios:
        rol = u.get("rol", "ejecutivo")
        rlabel, ricon, rcol = _ROLES.get(rol, (rol.capitalize(), "user", "#2563eb"))
        nombre = esc(u.get("nombre") or u.get("email") or "—")
        email = esc(u.get("email") or "—")
        tel = esc(u.get("telefono") or "")
        fecha = esc(u.get("created_at") or "—")
        uid = esc(u.get("id"))
        foto = (u.get("foto_url") or "").strip()
        ini = (u.get("nombre") or u.get("email") or "?")[0].upper()
        n_pres = counts.get((u.get("email") or "").strip().lower(), 0)
        blocked = u.get("bloqueado")

        if foto:
            avatar = (f'<div class="uc-av" style="border-color:{rcol};">'
                      f'<img src="{esc(foto)}" alt=""></div>')
        else:
            avatar = (f'<div class="uc-av uc-ini" style="background:{rcol};border-color:{rcol};">'
                      f'{esc(ini)}</div>')

        pill = (f'<span class="uc-pill" style="background:{rcol}1a;color:{rcol};">'
                f'{_svg(_IC[ricon], 12, rcol, 2.2)}{esc(rlabel)}</span>')
        blocked_badge = ('<span class="uc-blocked">' + _svg(_IC["ban"], 12, "#dc2626", 2.4)
                         + 'Bloqueado</span>') if blocked else ''

        tel_row = (f'<div class="uc-line">{_svg(_IC["phone"], 13, "#94a3b8", 2)}<span>{tel}</span></div>'
                   if tel else '')

        # Botón bloquear/desbloquear según estado
        if blocked:
            blk_btn = (f'<button class="usr-act-btn act-unlock" data-act="bloquear" data-uid="{uid}" '
                       f'title="Desbloquear acceso">{_svg(_IC["unlock"], 16, "#16a34a", 2)}</button>')
        else:
            blk_btn = (f'<button class="usr-act-btn act-lock" data-act="bloquear" data-uid="{uid}" '
                       f'title="Bloquear acceso">{_svg(_IC["lock"], 16, "#b45309", 2)}</button>')

        actions = (
            f'<button class="usr-act-btn" data-act="editar" data-uid="{uid}" title="Editar datos / foto">'
            f'{_svg(_IC["edit"], 16, "#2563eb", 2)}</button>'
            f'<button class="usr-act-btn" data-act="rol" data-uid="{uid}" title="Cambiar rol">'
            f'{_svg(_IC["shield"], 16, "#7c3aed", 2)}</button>'
            f'<button class="usr-act-btn" data-act="password" data-uid="{uid}" title="Cambiar contraseña">'
            f'{_svg(_IC["key"], 16, "#0891b2", 2)}</button>'
            f'{blk_btn}'
            f'<button class="usr-act-btn act-del" data-act="eliminar" data-uid="{uid}" '
            f'data-np="{n_pres}" title="Eliminar usuario">'
            f'{_svg(_IC["trash"], 16, "#dc2626", 2)}</button>'
        )

        cards.append(
            f'<div class="uc{" uc-off" if blocked else ""}" style="--rc:{rcol};">'
            f'<div class="uc-accent" style="background:{rcol};"></div>'
            f'<div class="uc-top">{avatar}'
            f'<div class="uc-id"><div class="uc-name">{nombre}</div>{pill}</div>'
            f'{blocked_badge}</div>'
            f'<div class="uc-contact">'
            f'<div class="uc-line">{_svg(_IC["mail"], 13, "#94a3b8", 2)}<span>{email}</span></div>'
            f'{tel_row}'
            f'</div>'
            f'<div class="uc-foot">'
            f'<span class="uc-chip" title="Presupuestos creados">{_svg(_IC["file"], 13, "#0f3460", 2)}'
            f'<b>{n_pres}</b> presupuesto{"s" if n_pres != 1 else ""}</span>'
            f'<span class="uc-date">{_svg(_IC["calendar"], 12, "#cbd5e1", 2)}{fecha}</span>'
            f'</div>'
            f'<div class="uc-actions">{actions}</div>'
            f'</div>'
        )

    grid = '<div class="usr-grid">' + ''.join(cards) + '</div>' if cards else \
           '<div class="usr-empty">No hay usuarios registrados aún.</div>'

    css = """
*{box-sizing:border-box;}
body{margin:0;font-family:'Inter','Segoe UI',sans-serif;background:transparent;}
.usr-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;padding:2px;}
.usr-empty{padding:40px;text-align:center;color:#94a3b8;font-weight:600;}
.uc{position:relative;background:#fff;border:1px solid #e8eaf0;border-radius:18px;padding:18px 18px 16px;
  box-shadow:0 2px 10px rgba(15,23,42,.05);overflow:hidden;transition:transform .16s,box-shadow .16s;}
.uc:hover{transform:translateY(-3px);box-shadow:0 14px 32px rgba(15,52,96,.12);}
.uc-off{opacity:.62;}
.uc-accent{position:absolute;top:0;left:0;width:5px;height:100%;}
.uc-top{display:flex;align-items:center;gap:13px;margin-bottom:13px;}
.uc-av{width:54px;height:54px;border-radius:50%;flex:0 0 auto;border:2.5px solid #e2e8f0;overflow:hidden;
  box-shadow:0 4px 12px rgba(15,52,96,.16);}
.uc-av img{width:100%;height:100%;object-fit:cover;display:block;}
.uc-ini{display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;font-size:1.3rem;
  font-family:'Montserrat',sans-serif;}
.uc-id{min-width:0;flex:1;}
.uc-name{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.96rem;color:#1e2447;
  line-height:1.2;margin-bottom:5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.uc-pill{display:inline-flex;align-items:center;gap:5px;padding:3px 10px 3px 8px;border-radius:99px;
  font-size:0.68rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em;}
.uc-blocked{position:absolute;top:14px;right:14px;display:inline-flex;align-items:center;gap:4px;
  background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;border-radius:99px;padding:2px 9px;
  font-size:0.62rem;font-weight:800;text-transform:uppercase;letter-spacing:.04em;}
.uc-contact{display:flex;flex-direction:column;gap:5px;margin-bottom:12px;}
.uc-line{display:flex;align-items:center;gap:8px;color:#64748b;font-size:0.8rem;font-weight:500;min-width:0;}
.uc-line span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.uc-foot{display:flex;align-items:center;justify-content:space-between;gap:8px;
  padding:10px 0 12px;border-top:1px solid #f1f5f9;}
.uc-chip{display:inline-flex;align-items:center;gap:6px;background:#eef4fb;color:#0f3460;
  border-radius:99px;padding:4px 11px;font-size:0.72rem;font-weight:600;}
.uc-chip b{font-family:'Montserrat',sans-serif;font-weight:900;}
.uc-date{display:inline-flex;align-items:center;gap:5px;color:#94a3b8;font-size:0.7rem;font-weight:600;}
.uc-actions{display:flex;gap:8px;}
.usr-act-btn{flex:1;display:flex;align-items:center;justify-content:center;height:38px;border-radius:11px;
  background:#f8fafc;border:1px solid #e7ebf3;cursor:pointer;transition:background .15s,border-color .15s,transform .1s;}
.usr-act-btn:hover{background:#eef2ff;border-color:#c7d2fe;transform:translateY(-1px);}
.usr-act-btn.act-del:hover{background:#fef2f2;border-color:#fca5a5;}
.usr-act-btn.act-lock:hover{background:#fff7ed;border-color:#fed7aa;}
.usr-act-btn.act-unlock:hover{background:#ecfdf5;border-color:#86efac;}
.usr-act-btn:active{transform:translateY(0);}
"""

    js = """
<script>
(function(){
  function go(act, uid, np){
    try{
      var W = window.parent;
      var u = new URL(W.location.href);
      u.searchParams.set('_usr_act', act);
      u.searchParams.set('_usr_id', uid);
      if(np!=null) u.searchParams.set('_usr_np', np);
      W.history.replaceState({}, '', u.toString());
      var b = W.document.querySelector('.st-key-_usr_action_btn button');
      if(b) b.click();
    }catch(e){}
  }
  document.addEventListener('click', function(e){
    var btn = e.target.closest && e.target.closest('.usr-act-btn, .usr-new-btn');
    if(!btn) return;
    e.preventDefault();
    if(btn.classList.contains('usr-new-btn')){ go('crear', '_', null); return; }
    go(btn.getAttribute('data-act'), btn.getAttribute('data-uid'), btn.getAttribute('data-np'));
  });
  function fit(){
    try{
      var h = Math.ceil(document.body.scrollHeight);
      if(window.frameElement) window.frameElement.style.height = (h+4)+'px';
      window.parent.postMessage({type:'streamlit:setFrameHeight',height:h}, '*');
    }catch(e){}
  }
  window.addEventListener('load', fit);
  [60,200,500,1000].forEach(function(t){setTimeout(fit,t);});
  document.querySelectorAll('img').forEach(function(im){im.addEventListener('load', fit);});
  try{ new ResizeObserver(fit).observe(document.documentElement); }catch(e){}
  fit();
})();
</script>
"""
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
            '<style>' + css + '</style></head><body>' + grid + js + '</body></html>')


# ── render principal ──────────────────────────────────────────────────────────

def render_tab_usuarios(supabase_admin=None, **deps):
    if not st.session_state.get("modo_admin"):
        st.info("Solo administradores pueden gestionar usuarios.")
        return

    if "_usr_toast" in st.session_state:
        st.toast(st.session_state.pop("_usr_toast"))

    # Cargar datos (cache por sesión)
    if "_usr_data" not in st.session_state:
        with st.spinner("Cargando usuarios..."):
            data, err = _listar_usuarios()
        if err:
            st.error(f"Error al cargar usuarios: {err}")
            if st.button("Reintentar", key="btn_usr_retry"):
                _invalidar(); st.rerun()
            return
        st.session_state["_usr_data"] = data
    if "_usr_counts" not in st.session_state:
        st.session_state["_usr_counts"] = _presupuestos_por_email()

    usuarios = st.session_state["_usr_data"]
    counts   = st.session_state["_usr_counts"]

    render_page_header("usuarios", "Gesti&#243;n de Usuarios",
                       "Crea y administra las cuentas de acceso del equipo.")

    # Barra de stats + acciones (HTML propio)
    n_adm = sum(1 for u in usuarios if u.get("rol") in ("admin", "administrador"))
    n_ej  = sum(1 for u in usuarios if u.get("rol") == "ejecutivo")
    n_op  = sum(1 for u in usuarios if u.get("rol") == "operacion")
    n_blk = sum(1 for u in usuarios if u.get("bloqueado"))

    def _stat(icon, color, n, lbl):
        return (f'<span class="us-stat"><span class="us-ico" style="background:{color}1a;color:{color};">'
                f'{_svg(_IC[icon], 14, color, 2.2)}</span><b>{n}</b> {lbl}</span>')

    _blk_html = (f'<span class="us-stat us-blk">{_svg(_IC["ban"], 13, "#dc2626", 2.4)}'
                 f'<b>{n_blk}</b> bloqueado{"s" if n_blk != 1 else ""}</span>') if n_blk else ''
    st.markdown(
        "<style>"
        ".us-bar{display:flex;align-items:center;gap:18px;flex-wrap:wrap;background:#fff;border:1px solid #e8eaf0;"
        "border-radius:14px;padding:13px 20px;margin:2px 0 16px;box-shadow:0 2px 8px rgba(15,23,42,.04);}"
        ".us-total{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.05rem;color:#0f3460;}"
        ".us-stat{display:inline-flex;align-items:center;gap:7px;font-size:.82rem;color:#475569;font-weight:600;}"
        ".us-stat b{font-family:'Montserrat',sans-serif;font-weight:800;color:#1e2447;}"
        ".us-ico{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;border-radius:8px;}"
        ".us-blk{color:#dc2626;}.us-blk b{color:#dc2626;}"
        ".us-sep{flex:1;}"
        ".st-key-_usr_new_btn button{background:linear-gradient(135deg,#0f3460,#1a5276)!important;color:#fff!important;"
        "border:none!important;border-radius:11px!important;font-weight:700!important;box-shadow:0 8px 20px rgba(15,52,96,.28)!important;}"
        ".st-key-_usr_new_btn button:hover{transform:translateY(-1px);}"
        ".st-key-_usr_action_btn{position:absolute!important;width:1px!important;height:1px!important;overflow:hidden!important;opacity:0!important;}"
        "</style>"
        '<div class="us-bar">'
        f'<span class="us-total">{len(usuarios)} usuarios</span>'
        + _stat("crown", "#7c3aed", n_adm, "Admin")
        + _stat("user", "#2563eb", n_ej, "Ejecutivos")
        + _stat("settings", "#b45309", n_op, "Operación")
        + _blk_html
        + '</div>',
        unsafe_allow_html=True,
    )

    c1, c2, _ = st.columns([1.6, 1, 5])
    with c1:
        if st.button("Nuevo usuario", type="primary", use_container_width=True,
                     icon=":material/person_add:", key="_usr_new_btn"):
            _dlg_crear()
    with c2:
        if st.button("Actualizar", use_container_width=True,
                     icon=":material/refresh:", key="_usr_ref_btn"):
            _invalidar(); st.rerun()

    # Directorio (HTML propio en iframe)
    _dir_html = _build_directory_html(usuarios, counts)
    _h0 = max(360, ((len(usuarios) + 1) // 2) * 250 + 60)
    _components.html(_dir_html, height=_h0, scrolling=False)

    # Botón nativo OCULTO que el JS del iframe clickea para enrutar acciones.
    if st.button("acc", key="_usr_action_btn"):
        _act = st.query_params.get("_usr_act")
        _uid = st.query_params.get("_usr_id")
        _np  = st.query_params.get("_usr_np")
        try:
            _np = int(_np) if _np not in (None, "", "None") else 0
        except (TypeError, ValueError):
            _np = 0
        # Limpiar de la URL para no re-disparar
        for _k in ("_usr_act", "_usr_id", "_usr_np"):
            try:
                del st.query_params[_k]
            except Exception:
                pass
        st.session_state["_usr_pending"] = (_act, _uid, _np)
        st.rerun()

    # Abrir el diálogo correspondiente a la acción pendiente (one-shot)
    _pend = st.session_state.pop("_usr_pending", None)
    if _pend:
        _act, _uid, _np = _pend
        if _act == "crear":
            _dlg_crear()
        else:
            _u = next((x for x in usuarios if str(x["id"]) == str(_uid)), None)
            if _u:
                if _act == "editar":
                    _dlg_editar(_u)
                elif _act == "rol":
                    _dlg_rol(_u)
                elif _act == "password":
                    _dlg_password(_u)
                elif _act == "bloquear":
                    _dlg_bloquear(_u)
                elif _act == "eliminar":
                    _dlg_eliminar(_u, n_presup=_np or counts.get((_u.get("email") or "").strip().lower(), 0))
