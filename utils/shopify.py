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
    # Acepta SHOPIFY_TOKEN o SHOPIFY_ACCESS_TOKEN (ambos nombres son comunes).
    return str(_sec("SHOPIFY_TOKEN", "") or _sec("SHOPIFY_ACCESS_TOKEN", "") or "").strip()


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
        return [], "Faltan SHOPIFY_STORE / SHOPIFY_TOKEN (o SHOPIFY_ACCESS_TOKEN) en los secrets."
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


def store_admin_url() -> str:
    """URL del admin de la tienda (para el botón 'Abrir en Shopify')."""
    return f"https://{_store()}/admin" if _store() else ""


def producto_admin_url(pid) -> str:
    return f"https://{_store()}/admin/products/{pid}" if (_store() and pid) else ""


def producto_web_url(handle) -> str:
    """URL pública del producto en la tienda (myshopify)."""
    return f"https://{_store()}/products/{handle}" if (_store() and handle) else ""


def listar_productos(status: str = "active", max_paginas: int = 20) -> tuple:
    """Trae los productos de la tienda (paginado por cursor, 250 por página).
    `status`: 'active' | 'draft' | 'archived' | '' (todos). Devuelve (lista, error).
    DEFENSIVO. Si el token no tiene `read_products`, Shopify responde 401/403 y se
    devuelve un mensaje claro para que el usuario agregue el permiso a su app."""
    if not configurado():
        return [], "Faltan SHOPIFY_STORE / SHOPIFY_TOKEN (o SHOPIFY_ACCESS_TOKEN) en los secrets."
    import requests
    out = []
    url = f"https://{_store()}/admin/api/{_version()}/products.json?limit=250"
    if status:
        url += f"&status={status}"
    headers = {"X-Shopify-Access-Token": _token(), "Content-Type": "application/json"}
    try:
        for _ in range(max(1, int(max_paginas))):
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                _msg = f"Shopify {r.status_code}: {r.text[:200]}"
                if r.status_code in (401, 403):
                    _msg += (" — parece que el token NO tiene el permiso 'read_products'. "
                             "Agrégalo en tu app custom de Shopify (Admin → Apps → tu app → "
                             "Configuración de API → scopes: read_products, write_products) y reinstala.")
                return out, _msg
            out.extend((r.json() or {}).get("products") or [])
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
