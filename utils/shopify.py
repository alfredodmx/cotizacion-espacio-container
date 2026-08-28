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


# ── Escritura de productos (Fase 2/3) — requiere scope write_products ─────────

def _headers():
    return {"X-Shopify-Access-Token": _token(), "Content-Type": "application/json"}


def _scope_hint(code) -> str:
    return (" — el token todavía NO tiene APROBADO el permiso 'write_products'. En tu app custom "
            "de Shopify: agrega el scope write_products, Guarda, y luego INSTALA/REINSTALA la app "
            "(ese paso es la 'aprobación del comerciante'). Si al reinstalar cambia el Admin API token, "
            "actualízalo en el secret SHOPIFY_TOKEN." if code in (401, 403) else "")


def get_producto(pid) -> tuple:
    """Trae UN producto fresco (para el editor). Devuelve (producto|None, error)."""
    if not configurado():
        return None, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.get(f"https://{_store()}/admin/api/{_version()}/products/{pid}.json",
                         headers=_headers(), timeout=25)
        if r.status_code == 200:
            return (r.json() or {}).get("product"), None
        return None, f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint(r.status_code)
    except Exception as e:
        return None, str(e)


def actualizar_producto(pid, campos: dict) -> tuple:
    """PUT de campos del producto (title, body_html, status, product_type, tags…).
    Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.put(f"https://{_store()}/admin/api/{_version()}/products/{pid}.json",
                         headers=_headers(), json={"product": {"id": pid, **campos}}, timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:250]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def actualizar_variante(vid, campos: dict) -> tuple:
    """PUT de una variante (p.ej. {'price':'15990000'}). Devuelve (ok, error)."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.put(f"https://{_store()}/admin/api/{_version()}/variants/{vid}.json",
                         headers=_headers(), json={"variant": {"id": vid, **campos}}, timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:250]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def agregar_imagen(pid, src: str = "", attachment: str = "", filename: str = "") -> tuple:
    """Agrega una imagen al producto: por `src` (URL) o `attachment` (base64) + filename.
    Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    _img = {}
    if src:
        _img["src"] = src
    if attachment:
        _img["attachment"] = attachment
        if filename:
            _img["filename"] = filename
    if not _img:
        return False, "Falta la URL o el archivo de la imagen."
    import requests
    try:
        r = requests.post(f"https://{_store()}/admin/api/{_version()}/products/{pid}/images.json",
                          headers=_headers(), json={"image": _img}, timeout=40)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:250]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def eliminar_imagen(pid, image_id) -> tuple:
    """Elimina una imagen del producto. Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.delete(
            f"https://{_store()}/admin/api/{_version()}/products/{pid}/images/{image_id}.json",
            headers=_headers(), timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:250]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


# ── Metafields (características/detalles estructurados: m², dormitorios, etc.) ──

def listar_metafields(pid) -> tuple:
    """Metafields del producto. Devuelve (lista, error). DEFENSIVO. Cada metafield:
    {id, namespace, key, type, value, description}."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.get(
            f"https://{_store()}/admin/api/{_version()}/products/{pid}/metafields.json?limit=250",
            headers=_headers(), timeout=25)
        if r.status_code == 200:
            return (r.json() or {}).get("metafields") or [], None
        return [], f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint(r.status_code)
    except Exception as e:
        return [], str(e)


def crear_metafield(pid, namespace, key, mtype, value) -> tuple:
    """Crea un metafield en el producto. Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.post(
            f"https://{_store()}/admin/api/{_version()}/products/{pid}/metafields.json",
            headers=_headers(),
            json={"metafield": {"namespace": namespace, "key": key, "type": mtype, "value": str(value)}},
            timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:280]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def actualizar_metafield(pid, metafield_id, mtype, value) -> tuple:
    """Actualiza el valor de un metafield existente. Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.put(
            f"https://{_store()}/admin/api/{_version()}/products/{pid}/metafields/{metafield_id}.json",
            headers=_headers(),
            json={"metafield": {"id": metafield_id, "type": mtype, "value": str(value)}}, timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:280]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def eliminar_metafield(pid, metafield_id) -> tuple:
    """Elimina un metafield del producto. Devuelve (ok, error). DEFENSIVO."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.delete(
            f"https://{_store()}/admin/api/{_version()}/products/{pid}/metafields/{metafield_id}.json",
            headers=_headers(), timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:250]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def reordenar_imagenes(pid, ordered_ids) -> tuple:
    """Reordena las fotos del producto según `ordered_ids` (lista COMPLETA de ids en el
    orden deseado). Se hace con el PUT del producto fijando `position` a cada imagen.
    Devuelve (ok, error)."""
    try:
        _imgs = [{"id": int(i), "position": _idx + 1} for _idx, i in enumerate(ordered_ids)]
    except Exception:
        return False, "IDs de imagen inválidos."
    if not _imgs:
        return False, "Sin imágenes para reordenar."
    return actualizar_producto(pid, {"images": _imgs})


# ── Videos (media) — vía GraphQL Admin API. Requiere write_products ───────────

def _graphql(query, variables=None) -> tuple:
    """POST a la Admin GraphQL API. Devuelve (data, error). DEFENSIVO."""
    if not configurado():
        return None, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.post(f"https://{_store()}/admin/api/{_version()}/graphql.json",
                          headers=_headers(), json={"query": query, "variables": variables or {}}, timeout=40)
        if r.status_code == 200:
            d = r.json() or {}
            if d.get("errors"):
                return None, f"GraphQL: {str(d['errors'])[:250]}"
            return d.get("data"), None
        return None, f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint(r.status_code)
    except Exception as e:
        return None, str(e)


def _gid_product(pid) -> str:
    return f"gid://shopify/Product/{pid}"


def listar_videos(pid) -> tuple:
    """Videos del producto (subidos + externos YouTube/Vimeo). Devuelve (lista, error).
    Cada uno: {id, mediaContentType, status, preview_url, origin_url, host}."""
    q = ("query($id:ID!){ product(id:$id){ media(first:50){ nodes { "
         "id mediaContentType status preview { image { url } } "
         "... on ExternalVideo { host originUrl } } } } }")
    data, err = _graphql(q, {"id": _gid_product(pid)})
    if err:
        return [], err
    _nodes = (((data or {}).get("product") or {}).get("media") or {}).get("nodes") or []
    out = []
    for n in _nodes:
        if n.get("mediaContentType") not in ("VIDEO", "EXTERNAL_VIDEO"):
            continue
        out.append({
            "id": n.get("id"),
            "type": n.get("mediaContentType"),
            "status": n.get("status"),
            "preview_url": (((n.get("preview") or {}).get("image") or {}).get("url")) or "",
            "origin_url": n.get("originUrl") or "",
            "host": n.get("host") or "",
        })
    return out, None


def agregar_video_externo(pid, url) -> tuple:
    """Agrega un video EXTERNO (link de YouTube/Vimeo) al producto. Devuelve (ok, error)."""
    if not (url or "").strip():
        return False, "Falta el enlace del video."
    q = ("mutation($pid:ID!, $media:[CreateMediaInput!]!){ productCreateMedia(productId:$pid, media:$media){ "
         "media { id mediaContentType } mediaUserErrors { field message } } }")
    _vars = {"pid": _gid_product(pid),
             "media": [{"originalSource": url.strip(), "mediaContentType": "EXTERNAL_VIDEO"}]}
    data, err = _graphql(q, _vars)
    if err:
        return False, err
    _errs = (((data or {}).get("productCreateMedia") or {}).get("mediaUserErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo agregar el video."
    return True, None


def eliminar_media(pid, media_id) -> tuple:
    """Elimina un media (video) del producto por su id (gid). Devuelve (ok, error)."""
    q = ("mutation($pid:ID!, $ids:[ID!]!){ productDeleteMedia(productId:$pid, mediaIds:$ids){ "
         "deletedMediaIds mediaUserErrors { field message } } }")
    data, err = _graphql(q, {"pid": _gid_product(pid), "ids": [media_id]})
    if err:
        return False, err
    _errs = (((data or {}).get("productDeleteMedia") or {}).get("mediaUserErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo eliminar el video."
    return True, None


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
