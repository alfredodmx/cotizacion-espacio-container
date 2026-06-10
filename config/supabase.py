"""
Clientes Supabase cacheados para toda la aplicación.

Uso:
    from config.supabase import supabase, supabase_admin
"""
import streamlit as st
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY, SUPABASE_SERVICE_KEY


@st.cache_resource
def _get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


@st.cache_resource
def _get_supabase_admin() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


# Instancias listas para importar directamente
supabase: Client = _get_supabase()
supabase_admin: Client = _get_supabase_admin()


def get_supabase() -> Client:
    return _get_supabase()


def get_supabase_admin() -> Client:
    return _get_supabase_admin()


def get_supabase_urls() -> tuple[str, str]:
    """Retorna (SUPABASE_URL, SUPABASE_KEY)."""
    return SUPABASE_URL, SUPABASE_KEY
