"""
Helper compartido para obtener la foto (avatar) de los usuarios por email.
La foto vive en user_metadata.foto_url y se lee vía la API admin (service key),
mismo patrón que el ranking. Cacheado 5 min.
"""
import httpx
import streamlit as st

from config.settings import SUPABASE_SERVICE_KEY


@st.cache_data(ttl=300, show_spinner=False)
def fetch_foto_map(supa_url: str) -> dict:
    """email(minúsculas) -> foto_url. {} si falla."""
    try:
        r = httpx.get(
            f"{supa_url}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY,
                     "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = {}
        for u in r.json().get("users", []):
            em = (u.get("email") or "").lower()
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            out[em] = meta.get("foto_url", "") or ""
        return out
    except Exception:
        return {}


def avatar_html(foto_url: str, nombre: str, size: int = 58,
                ring: str = "#ffffff", font_scale: float = 0.34) -> str:
    """Avatar circular: foto si hay, si no las iniciales sobre degradado azul."""
    partes = [p for p in (nombre or '').split() if p]
    ini = ''.join(p[0] for p in partes[:2]).upper() if partes else 'EC'
    border = f"border:2px solid {ring};box-sizing:border-box;"
    base = (f"width:{size}px;height:{size}px;border-radius:50%;flex:0 0 auto;"
            f"box-shadow:0 6px 18px rgba(5,12,28,.28);{border}")
    if foto_url:
        return (f'<div style="{base}overflow:hidden;background:#fff;">'
                f'<img src="{foto_url}" style="width:100%;height:100%;object-fit:cover;display:block;"></div>')
    return (f'<div style="{base}background:linear-gradient(135deg,#0f3460,#1a5276);'
            f'display:flex;align-items:center;justify-content:center;color:#fff;'
            f'font-family:Montserrat,sans-serif;font-weight:900;font-size:{size * font_scale:.0f}px;">{ini}</div>')
