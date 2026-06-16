"""
Repositorio de configuracion de notificaciones Telegram.
Tabla: notif_config
"""
import streamlit as st
from config.supabase import supabase_admin


@st.cache_data(ttl=300, show_spinner=False)
def get_notif_config(clave: str, default: str = "") -> str:
    """Lee un valor de configuracion de notificaciones desde Supabase."""
    try:
        resp = supabase_admin.table('notif_config') \
            .select('valor').eq('clave', clave).limit(1).execute()
        if resp.data:
            return resp.data[0].get('valor', default)
        return default
    except Exception:
        return default


def set_notif_config(clave: str, valor: str) -> bool:
    """Guarda un valor de configuracion de notificaciones en Supabase."""
    try:
        supabase_admin.table('notif_config').upsert(
            {'clave': clave, 'valor': valor},
            on_conflict='clave'
        ).execute()
        get_notif_config.clear()
        return True
    except Exception:
        return False


def get_contactos_notif() -> list[dict]:
    """Lista de contactos que reciben notificaciones directas."""
    try:
        resp = supabase_admin.table('notif_config') \
            .select('*').like('clave', 'contacto_%').execute()
        return resp.data or []
    except Exception:
        return []


def get_observadores_notif() -> list[dict]:
    """Lista de observadores pasivos de notificaciones."""
    try:
        resp = supabase_admin.table('notif_config') \
            .select('*').like('clave', 'observador_%').execute()
        return resp.data or []
    except Exception:
        return []
