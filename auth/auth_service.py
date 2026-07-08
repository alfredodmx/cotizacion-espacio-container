"""
Servicios de autenticación: login, logout, gestión de usuarios.
Todas las funciones que interactúan con Supabase Auth.
"""
import streamlit as st
from config.supabase import supabase, supabase_admin
from config.settings import ROOTS, SUPABASE_URL, SUPABASE_KEY
from auth.roles import get_rol


# ── Login / Logout ────────────────────────────────────────────────────────────

def login_usuario(email: str, password: str) -> tuple:
    """Inicia sesión con email y contraseña. Retorna (user, error)."""
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        return res.user, None
    except Exception as e:
        return None, str(e)


def logout_usuario() -> None:
    """Cierra sesión y limpia completamente el session_state."""
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    _keys_to_clear = list(st.session_state.keys())
    for k in _keys_to_clear:
        try:
            del st.session_state[k]
        except Exception:
            pass
    try:
        st.query_params.clear()
    except Exception:
        pass


# ── Gestión de usuarios ───────────────────────────────────────────────────────

def crear_usuario_ejecutivo(email: str, password: str, nombre: str) -> tuple:
    """Crea un nuevo usuario ejecutivo (requiere service role). Retorna (user, error)."""
    try:
        res = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"nombre": nombre, "rol": "ejecutivo"}
        })
        return res.user, None
    except Exception as e:
        return None, str(e)


def cambiar_rol_usuario(user_id: str, nuevo_rol: str) -> tuple[bool, str | None]:
    """Cambia el rol de un usuario en sus metadatos. Retorna (ok, error)."""
    try:
        supabase_admin.auth.admin.update_user_by_id(
            user_id, {"user_metadata": {"rol": nuevo_rol}}
        )
        return True, None
    except Exception as e:
        return False, str(e)


def verificar_password_actual(email: str, password: str) -> bool:
    """Verifica la contraseña ACTUAL del usuario SIN tocar la sesión global.

    Usa un cliente Supabase temporal y aislado (no el singleton compartido de
    `@st.cache_resource`): así validar la contraseña no pisa la sesión de los
    demás usuarios del servidor ni la del propio usuario. Devuelve True si la
    contraseña es correcta.
    """
    if not email or not password:
        return False
    try:
        from supabase import create_client
        _tmp = create_client(SUPABASE_URL, SUPABASE_KEY)
        try:
            res = _tmp.auth.sign_in_with_password({"email": email, "password": password})
            return bool(res and res.user)
        finally:
            try:
                _tmp.auth.sign_out()
            except Exception:
                pass
    except Exception:
        return False


def cambiar_password_propio(nueva_password: str, user_id: str | None = None) -> tuple[bool, str | None]:
    """El usuario cambia su propia contraseña.

    Se hace con la SERVICE KEY (admin) apuntando al `user_id`, en vez de depender
    de la sesión del cliente anon compartido (`@st.cache_resource`): ese singleton
    se comparte entre TODOS los usuarios del servidor y su sesión no está
    garantizada para el usuario actual (la restaura `get_user`, no `set_session`),
    por lo que `update_user` fallaba con "contraseña inválida" / sesión ausente y
    le pasaba a todos los ejecutivos. El admin API es determinista y no depende de
    la sesión. Retorna (ok, error).
    """
    try:
        if user_id:
            supabase_admin.auth.admin.update_user_by_id(user_id, {"password": nueva_password})
        else:
            # Retrocompatibilidad: sin user_id, intenta con la sesión del cliente.
            supabase.auth.update_user({"password": nueva_password})
        return True, None
    except Exception as e:
        return False, str(e)


def resetear_password_admin(user_id: str, nueva_password: str) -> tuple[bool, str | None]:
    """Admin/Root resetea la contraseña de otro usuario (requiere service role)."""
    try:
        supabase_admin.auth.admin.update_user_by_id(user_id, {"password": nueva_password})
        return True, None
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=300, show_spinner=False)
def listar_usuarios_ejecutivos() -> list[dict]:
    """Lista todos los usuarios del sistema (excepto roots)."""
    try:
        res = supabase_admin.auth.admin.list_users()
        users = []
        for u in res:
            email = u.email or ""
            if email.lower() in [s.lower() for s in ROOTS]:
                continue
            meta = u.user_metadata or {}
            nombre = meta.get("nombre", email)
            rol = meta.get("rol", "ejecutivo")
            try:
                _activo = not getattr(u, 'banned_until', None)
            except Exception:
                _activo = True
            users.append({
                "id": str(u.id),
                "email": email,
                "nombre": nombre,
                "rol": rol,
                "telefono": meta.get("telefono", "") or "",
                "created_at": str(u.created_at)[:10] if u.created_at else "",
                "activo": _activo
            })
        return users
    except Exception as e:
        st.session_state['_usuarios_list_error'] = str(e)
        return []


def eliminar_usuario_ejecutivo(user_id: str) -> tuple[bool, str | None]:
    """Elimina un usuario ejecutivo. Retorna (ok, error)."""
    try:
        supabase_admin.auth.admin.delete_user(user_id)
        return True, None
    except Exception as e:
        return False, str(e)


@st.cache_data(ttl=60, show_spinner=False)
def verificar_conexion_supabase() -> bool:
    """Health check de la conexión a Supabase."""
    if st.session_state.get('_supabase_ok'):
        return True
    try:
        supabase_admin.table('cotizaciones').select('numero').limit(1).execute()
        st.session_state['_supabase_ok'] = True
        return True
    except Exception as e:
        st.error(f"❌ Error conectando a Supabase: {e}")
        return False
