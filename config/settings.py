"""
Constantes globales del sistema leídas desde st.secrets.
Importar desde aquí en lugar de leer st.secrets directamente en cada módulo.
"""
import os
import streamlit as st

# ── Supabase ────────────────────────────────────────────────
SUPABASE_URL = (
    st.secrets.get("SUPABASE_URL", "") or
    st.secrets.get("supabase_url", "")
)
SUPABASE_KEY = (
    st.secrets.get("SUPABASE_KEY", "") or
    st.secrets.get("supabase_key", "")
)
SUPABASE_SERVICE_KEY = (
    st.secrets.get("SUPABASE_SERVICE_KEY", "") or
    st.secrets.get("supabase_service_key", "")
)

# ── Roles ────────────────────────────────────────────────────
# Emails con acceso root, separados por coma en secrets
_roots_raw = st.secrets.get("ROOTS", "")
ROOTS: list[str] = [r.strip().lower() for r in _roots_raw.split(",") if r.strip()]

# ── Código de acceso OTP ─────────────────────────────────────
ACCESS_CODE_SECRET: str = st.secrets.get("ACCESS_CODE_SECRET", "espacio-container-2024")

# ── Anthropic (Visor 3D) ─────────────────────────────────────
ANTHROPIC_API_KEY: str = (
    os.environ.get("ANTHROPIC_API_KEY", "") or
    (st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else "")
)

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN_DEFAULT: str = st.secrets.get("TELEGRAM_BOT_TOKEN", "")
