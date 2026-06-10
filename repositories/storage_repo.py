"""
Operaciones de lectura/escritura en Supabase Storage.
Buckets: planos, facturas, config.
"""
import uuid
import json
import requests as _rq
import streamlit as st
from config.supabase import supabase, supabase_admin
from config.settings import SUPABASE_URL


# ── Planos ────────────────────────────────────────────────────────────────────

def guardar_plano_en_storage(archivo_pdf_bytes: bytes, cotizacion_numero: str, nombre_original: str) -> tuple:
    """Sube un plano PDF al bucket 'planos'. Retorna (public_url, error)."""
    try:
        carpeta = cotizacion_numero.replace('/', '_').replace('\\', '_')
        file_name = f"cotizacion-{carpeta}/{uuid.uuid4()}.pdf"
        supabase.storage.from_('planos').upload(
            path=file_name,
            file=archivo_pdf_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = supabase.storage.from_('planos').get_public_url(file_name)
        return public_url, None
    except Exception as e:
        return None, str(e)


def eliminar_plano_de_storage(url_plano: str) -> tuple[bool, str | None]:
    """Elimina un plano del bucket 'planos'. Retorna (ok, error)."""
    try:
        if not url_plano:
            return True, None
        if '/planos/' in url_plano:
            path = url_plano.split('/planos/')[-1]
            supabase.storage.from_('planos').remove([path])
        return True, None
    except Exception as e:
        return False, str(e)


def descargar_plano_desde_url(url_plano: str) -> tuple:
    """Descarga un plano desde su URL pública. Retorna (bytes, error)."""
    try:
        if not url_plano:
            return None, None
        response = _rq.get(url_plano)
        if response.status_code == 200:
            return response.content, None
        else:
            return None, f"Error HTTP: {response.status_code}"
    except Exception as e:
        return None, str(e)


# ── Facturas y actas ──────────────────────────────────────────────────────────

def guardar_factura_en_storage(archivo_bytes: bytes, cotizacion_numero: str, nombre_original: str) -> tuple:
    """Sube una factura PDF al bucket 'facturas'. Retorna (public_url, error)."""
    try:
        carpeta = cotizacion_numero.replace('/', '_').replace('\\', '_')
        file_name = f"cotizacion-{carpeta}/{uuid.uuid4()}.pdf"
        supabase_admin.storage.from_('facturas').upload(
            path=file_name,
            file=archivo_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = supabase_admin.storage.from_('facturas').get_public_url(file_name)
        return public_url, None
    except Exception as e:
        return None, str(e)


def guardar_acta_en_storage(archivo_bytes: bytes, cotizacion_numero: str, nombre_original: str) -> tuple:
    """Sube un acta PDF al bucket 'facturas'. Retorna (public_url, error)."""
    try:
        carpeta = cotizacion_numero.replace('/', '_').replace('\\', '_')
        file_name = f"acta-{carpeta}/{uuid.uuid4()}.pdf"
        supabase_admin.storage.from_('facturas').upload(
            path=file_name,
            file=archivo_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = supabase_admin.storage.from_('facturas').get_public_url(file_name)
        return public_url, None
    except Exception as e:
        return None, str(e)


# ── Config JSON (descripciones PDF) ──────────────────────────────────────────

def cargar_descripciones_por_ep(numero: str, bust_cache: bool = False) -> dict:
    """Carga descripciones de un EP desde el bucket 'config'. Retorna dict o {}."""
    try:
        import time as _time
        _base = SUPABASE_URL.rstrip("/")
        _fname = f"pdf_desc_{numero}.json"
        url = f"{_base}/storage/v1/object/public/config/{_fname}"
        if bust_cache:
            url += f"?t={int(_time.time())}"
        r = _rq.get(url, timeout=5, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def guardar_descripciones_por_ep(numero: str, descripciones: dict) -> bool:
    """Guarda descripciones de un EP como JSON en el bucket 'config'. Retorna True/False."""
    try:
        _fname = f"pdf_desc_{numero}.json"
        data = json.dumps(descripciones, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            supabase.storage.from_("config").remove([_fname])
        except Exception:
            pass
        supabase.storage.from_("config").upload(
            path=_fname,
            file=data,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar descripciones: {e}")
        return False
