"""
Cliente mínimo de la API de Shopify — Fase 4 del CRM: traer los clientes de la
tienda (creados por los formularios) como LEADS a la Bandeja.

- Credenciales en los *secrets* de Streamlit (NUNCA en el código):
  `SHOPIFY_STORE` = "tu-tienda.myshopify.com" y `SHOPIFY_TOKEN` = "shpat_...".
  (App CUSTOM del propio admin con permiso `read_customers`.)
- V1: solo datos básicos (nombre/correo/teléfono/dirección). Los metacampos del
  formulario se mapean en una etapa siguiente.
- Todo DEFENSIVO: si faltan credenciales o falla la red, devuelve ([], mensaje) y
  el CRM sigue igual.
"""
import streamlit as st


def _sec(clave, default=""):
    try:
        return st.secrets.get(clave, default)
    except Exception:
        return default


def _store() -> str:
    s = str(_sec("SHOPIFY_STORE", "") or "").strip()
    return s.replace("https://", "").replace("http://", "").strip("/")


def _token() -> str:
    return str(_sec("SHOPIFY_TOKEN", "") or "").strip()


def _version() -> str:
    return str(_sec("SHOPIFY_API_VERSION", "2024-10") or "2024-10").strip()


def configurado() -> bool:
    """True si hay tienda + token cargados (para habilitar/inhabilitar la UI)."""
    return bool(_store() and _token())


def _next_link(link_header: str):
    """Extrae la URL de la página siguiente del header Link de Shopify."""
    for part in (link_header or "").split(","):
        if 'rel="next"' in part:
            _a, _b = part.find("<"), part.find(">")
            if _a != -1 and _b != -1:
                return part[_a + 1:_b]
    return None


def listar_clientes(max_paginas: int = 40) -> tuple:
    """Trae TODOS los clientes de la tienda (paginado por cursor, 250 por página).
    Devuelve (lista, error). DEFENSIVO."""
    if not configurado():
        return [], "Faltan SHOPIFY_STORE / SHOPIFY_TOKEN en los secrets."
    import requests
    out = []
    url = f"https://{_store()}/admin/api/{_version()}/customers.json?limit=250"
    headers = {"X-Shopify-Access-Token": _token(), "Content-Type": "application/json"}
    try:
        for _ in range(max(1, int(max_paginas))):
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                return out, f"Shopify {r.status_code}: {r.text[:200]}"
            out.extend((r.json() or {}).get("customers") or [])
            _nxt = _next_link(r.headers.get("Link", "") or r.headers.get("link", ""))
            if not _nxt:
                break
            url = _nxt
        return out, None
    except Exception as e:
        return out, str(e)


def a_lead(c: dict) -> dict:
    """Mapea un cliente de Shopify a un lead del CRM (llaves de CAMPOS_IMPORT)."""
    _addr = c.get("default_address") or {}
    _nombre = " ".join(x for x in (c.get("first_name"), c.get("last_name")) if x).strip()
    if not _nombre:
        _nombre = str(_addr.get("name") or c.get("email") or "").strip()
    return {
        "nombre": _nombre,
        "email": str(c.get("email") or "").strip(),
        "telefono": str(c.get("phone") or _addr.get("phone") or "").strip(),
        "direccion": str(_addr.get("address1") or "").strip(),
        "comuna": str(_addr.get("city") or "").strip(),
        "region": str(_addr.get("province") or "").strip(),
    }
