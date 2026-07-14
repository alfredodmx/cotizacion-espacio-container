"""
Helper compartido para obtener la foto (avatar) de los usuarios por email.
La foto vive en user_metadata.foto_url y se lee vía la API admin (service key),
mismo patrón que el ranking. Cacheado 5 min.
"""
import time
import httpx
import streamlit as st

from config.settings import SUPABASE_SERVICE_KEY, SUPABASE_URL

# Bucket público donde viven las fotos de perfil (carpeta avatares/).
_AVATAR_BUCKET = "formulario-imagenes"


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


@st.cache_data(ttl=300, show_spinner=False)
def fetch_ejecutivos(supa_url: str) -> list:
    """Lista de ejecutivos para asignar (clonar presupuesto).
    Devuelve [{email, nombre, telefono, foto_url}] ordenada por nombre. [] si falla.
    Solo usuarios con rol 'ejecutivo' (o sin rol explícito, que por defecto lo son)."""
    try:
        r = httpx.get(
            f"{supa_url}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY,
                     "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = []
        for u in r.json().get("users", []):
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            if (meta.get("rol", "ejecutivo") or "ejecutivo") != "ejecutivo":
                continue
            em = (u.get("email") or "").strip()
            if not em:
                continue
            out.append({
                "email": em,
                "nombre": meta.get("nombre", em) or em,
                "telefono": meta.get("telefono", "") or "",
                "foto_url": meta.get("foto_url", "") or "",
            })
        out.sort(key=lambda x: (x["nombre"] or "").lower())
        return out
    except Exception:
        return []


def _admin_headers(json: bool = False) -> dict:
    h = {"apikey": SUPABASE_SERVICE_KEY,
         "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"}
    if json:
        h["Content-Type"] = "application/json"
    return h


def subir_foto_perfil(uid: str, file_bytes: bytes, ext: str,
                      content_type: str) -> tuple[str | None, str | None]:
    """Sube la foto al bucket (avatares/<uid>.<ext>) y la fija en
    user_metadata.foto_url del propio usuario (merge para no borrar el resto de
    la metadata). Devuelve (foto_url, None) o (None, error). Invalida la caché
    de fetch_foto_map al terminar."""
    try:
        from config.supabase import supabase_admin
        ext = (ext or "png").lower().replace("jpeg", "jpg")
        path = f"avatares/{uid}.{ext}"
        store = supabase_admin.storage.from_(_AVATAR_BUCKET)
        try:
            store.remove([path])
        except Exception:
            pass
        store.upload(path, file_bytes,
                     {"content-type": content_type or "image/png", "upsert": "true"})
        base = store.get_public_url(path).split("?")[0]
        url = f"{base}?v={int(time.time())}"

        # Merge: leer la metadata actual y solo pisar foto_url (no perder
        # nombre / rol / telefono).
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
                      headers=_admin_headers(), timeout=15)
        r.raise_for_status()
        meta = r.json().get("user_metadata") or {}
        meta["foto_url"] = url
        r2 = httpx.put(f"{SUPABASE_URL}/auth/v1/admin/users/{uid}",
                       headers=_admin_headers(True),
                       json={"user_metadata": meta}, timeout=15)
        r2.raise_for_status()

        fetch_foto_map.clear()
        return url, None
    except Exception as e:
        return None, str(e)


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
