"""
Repositorio del catalogo de materiales y configuracion del formulario cliente.
Tablas: catalogo_materiales, formulario_config, formulario_respuestas
"""
import streamlit as st
from config.supabase import supabase_admin


@st.cache_data(ttl=120, show_spinner=False)
def fetch_catalogo_materiales() -> list:
    """Retorna todos los items activos del catalogo ordenados por categoria/grupo/nombre."""
    try:
        return supabase_admin.table('catalogo_materiales') \
            .select('*').eq('activo', True) \
            .order('categoria').order('orden_grupo').order('titulo_grupo').order('nombre') \
            .execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_formulario_config(ep: str) -> list:
    """Retorna la configuracion del formulario para un EP especifico."""
    try:
        return supabase_admin.table('formulario_config') \
            .select('*').eq('cotizacion_numero', ep) \
            .execute().data or []
    except Exception:
        return []


def fetch_formulario_respuestas(ep: str) -> dict:
    """Retorna las respuestas del cliente para un EP como dict {item_id: valor}."""
    try:
        resp = supabase_admin.table('formulario_respuestas') \
            .select('*').eq('cotizacion_numero', ep) \
            .execute()
        return {str(r['item_id']): r['valor'] for r in (resp.data or [])}
    except Exception:
        return {}


def guardar_respuesta_formulario(ep: str, item_id: str, valor: str) -> bool:
    """Upsert de una respuesta del cliente en formulario_respuestas."""
    try:
        supabase_admin.table('formulario_respuestas').upsert({
            'cotizacion_numero': ep,
            'item_id': item_id,
            'valor': valor,
        }, on_conflict='cotizacion_numero,item_id').execute()
        return True
    except Exception:
        return False
