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


def listar_productos(status: str = "active", max_paginas: int = 20,
                     published_status: str = "") -> tuple:
    """Trae los productos de la tienda (paginado por cursor, 250 por página).
    `status`: 'active' | 'draft' | 'archived' | '' (todos).
    `published_status`: '' (cualquiera) | 'published' | 'unpublished' — filtra por si el
    producto está o no publicado en la tienda online (lo que Shopify muestra como
    'Activo' vs 'No publicado'). Devuelve (lista, error). DEFENSIVO. Si el token no tiene
    `read_products`, Shopify responde 401/403 y se devuelve un mensaje claro."""
    if not configurado():
        return [], "Faltan SHOPIFY_STORE / SHOPIFY_TOKEN (o SHOPIFY_ACCESS_TOKEN) en los secrets."
    import requests
    out = []
    url = f"https://{_store()}/admin/api/{_version()}/products.json?limit=250"
    if status:
        url += f"&status={status}"
    if published_status:
        url += f"&published_status={published_status}"
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


def listar_ids_publicados(max_paginas: int = 20) -> tuple:
    """Conjunto de IDs (str) de productos PUBLICADOS en la tienda online
    (`published_status=published`), que es lo que Shopify muestra como 'Activo' vs
    'No publicado'. IMPORTANTE: el campo `published_at` del REST es el legacy y NO
    siempre coincide (un producto puede estar publicado con published_at nulo, o al
    revés), por eso el estado se decide con ESTE filtro. Devuelve (set|None, error);
    None en error → el llamador cae al heurístico de published_at."""
    if not configurado():
        return None, "Sin credenciales de Shopify."
    import requests
    ids = set()
    url = (f"https://{_store()}/admin/api/{_version()}/products.json"
           f"?limit=250&published_status=published&fields=id")
    try:
        for _ in range(max(1, int(max_paginas))):
            r = requests.get(url, headers=_headers(), timeout=30)
            if r.status_code != 200:
                return None, f"Shopify {r.status_code}: {r.text[:150]}"
            for p in (r.json() or {}).get("products") or []:
                ids.add(str(p.get("id")))
            _nxt = _next_link(r.headers.get("Link", "") or r.headers.get("link", ""))
            if not _nxt:
                break
            url = _nxt
        return ids, None
    except Exception as e:
        return None, str(e)


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


def crear_producto(campos: dict) -> tuple:
    """Crea un producto NUEVO. `campos` puede traer title, body_html, status,
    product_type, tags, variants ([{price}]), images ([{src}]). Devuelve
    (producto|None, error). DEFENSIVO."""
    if not configurado():
        return None, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.post(f"https://{_store()}/admin/api/{_version()}/products.json",
                          headers=_headers(), json={"product": campos}, timeout=40)
        if r.status_code in (200, 201):
            return (r.json() or {}).get("product"), None
        return None, f"Shopify {r.status_code}: {r.text[:280]}" + _scope_hint(r.status_code)
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


def eliminar_producto(pid) -> tuple:
    """Elimina un producto de la tienda (REST DELETE, PERMANENTE). Devuelve (ok, error).
    DEFENSIVO. Requiere write_products."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.delete(f"https://{_store()}/admin/api/{_version()}/products/{pid}.json",
                            headers=_headers(), timeout=30)
        if r.status_code in (200, 204):
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


def listar_definiciones_metafields() -> tuple:
    """Definiciones de metacampos de PRODUCTO de la tienda (GraphQL). Devuelve
    (lista, error). Cada def: {namespace, key, name, type, description}. Sirve para
    mostrar en el editor TODOS los campos definidos (m², baños, dormitorios, clima…)
    aunque el producto todavía no tenga valor. DEFENSIVO."""
    q = ("query{ metafieldDefinitions(first:100, ownerType:PRODUCT){ edges{ node{"
         " namespace key name description type{ name } } } } }")
    data, err = _graphql(q)
    if err:
        return [], err
    _edges = (((data or {}).get("metafieldDefinitions") or {}).get("edges")) or []
    out = []
    for e in _edges:
        n = (e or {}).get("node") or {}
        out.append({
            "namespace": n.get("namespace") or "",
            "key": n.get("key") or "",
            "name": n.get("name") or "",
            "description": n.get("description") or "",
            "type": ((n.get("type") or {}).get("name")) or "single_line_text_field",
        })
    return out, None


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


# ── Colecciones (organización del producto) ──────────────────────────────────

def listar_colecciones(max_paginas: int = 10) -> tuple:
    """Colecciones MANUALES (custom_collections) de la tienda. Devuelve (lista, error).
    Cada una: {id, title, handle}. Las 'smart' (automáticas) no se listan porque su
    membresía la define una regla, no se asigna a mano. DEFENSIVO."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    import requests
    out = []
    url = f"https://{_store()}/admin/api/{_version()}/custom_collections.json?limit=250"
    try:
        for _ in range(max(1, int(max_paginas))):
            r = requests.get(url, headers=_headers(), timeout=30)
            if r.status_code != 200:
                return out, f"Shopify {r.status_code}: {r.text[:150]}" + _scope_hint(r.status_code)
            out.extend((r.json() or {}).get("custom_collections") or [])
            _nxt = _next_link(r.headers.get("Link", "") or r.headers.get("link", ""))
            if not _nxt:
                break
            url = _nxt
        return out, None
    except Exception as e:
        return out, str(e)


def colecciones_de_producto(pid) -> tuple:
    """Collects del producto (a qué colecciones manuales pertenece). Devuelve
    (lista, error). Cada uno: {id (collect id), collection_id}. DEFENSIVO."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.get(
            f"https://{_store()}/admin/api/{_version()}/collects.json?product_id={pid}&limit=250",
            headers=_headers(), timeout=25)
        if r.status_code == 200:
            return (r.json() or {}).get("collects") or [], None
        return [], f"Shopify {r.status_code}: {r.text[:150]}" + _scope_hint(r.status_code)
    except Exception as e:
        return [], str(e)


def agregar_a_coleccion(pid, collection_id) -> tuple:
    """Agrega el producto a una colección manual (crea un collect). Devuelve (ok, error)."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.post(f"https://{_store()}/admin/api/{_version()}/collects.json",
                          headers=_headers(),
                          json={"collect": {"product_id": int(pid), "collection_id": int(collection_id)}},
                          timeout=30)
        if r.status_code in (200, 201):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


def quitar_de_coleccion(collect_id) -> tuple:
    """Quita el producto de una colección manual (borra el collect). Devuelve (ok, error)."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    import requests
    try:
        r = requests.delete(f"https://{_store()}/admin/api/{_version()}/collects/{collect_id}.json",
                           headers=_headers(), timeout=30)
        if r.status_code in (200, 204):
            return True, None
        return False, f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint(r.status_code)
    except Exception as e:
        return False, str(e)


# ── Canales de venta (publicaciones) — GraphQL, requiere read/write_publications ─

def listar_publicaciones() -> tuple:
    """Canales de venta / publicaciones de la tienda (Tienda online, Point of Sale,
    etc.). GraphQL. Devuelve (lista, error). Cada uno: {id (GID), name}. Requiere el
    scope read_publications."""
    q = "query{ publications(first:30){ edges{ node{ id name } } } }"
    data, err = _graphql(q)
    if err:
        return [], err
    _edges = (((data or {}).get("publications") or {}).get("edges")) or []
    return [{"id": (e.get("node") or {}).get("id"),
             "name": (e.get("node") or {}).get("name") or "Canal"} for e in _edges], None


def publicaciones_de_producto(pid) -> tuple:
    """Set de IDs (GID) de publicaciones donde el producto ESTÁ publicado. Devuelve
    (set|None, error). None en error."""
    q = ("query($id:ID!){ product(id:$id){ resourcePublicationsV2(first:30){ edges{ node{ "
         "isPublished publication{ id } } } } } }")
    data, err = _graphql(q, {"id": _gid_product(pid)})
    if err:
        return None, err
    _edges = ((((data or {}).get("product") or {}).get("resourcePublicationsV2") or {}).get("edges")) or []
    ids = set()
    for e in _edges:
        n = e.get("node") or {}
        if n.get("isPublished"):
            _pu = ((n.get("publication") or {}).get("id"))
            if _pu:
                ids.add(_pu)
    return ids, None


def publicar_en_canales(pid, publication_ids) -> tuple:
    """Publica el producto en las publicaciones dadas (GIDs). Devuelve (ok, error).
    Requiere write_publications."""
    if not publication_ids:
        return True, None
    q = ("mutation($id:ID!, $input:[PublicationInput!]!){ publishablePublish(id:$id, input:$input){ "
         "userErrors{ field message } } }")
    _input = [{"publicationId": p} for p in publication_ids]
    data, err = _graphql(q, {"id": _gid_product(pid), "input": _input})
    if err:
        return False, err
    _errs = (((data or {}).get("publishablePublish") or {}).get("userErrors")) or []
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo publicar."
    return True, None


def despublicar_de_canales(pid, publication_ids) -> tuple:
    """Quita el producto de las publicaciones dadas (GIDs). Devuelve (ok, error).
    Requiere write_publications."""
    if not publication_ids:
        return True, None
    q = ("mutation($id:ID!, $input:[PublicationInput!]!){ publishableUnpublish(id:$id, input:$input){ "
         "userErrors{ field message } } }")
    _input = [{"publicationId": p} for p in publication_ids]
    data, err = _graphql(q, {"id": _gid_product(pid), "input": _input})
    if err:
        return False, err
    _errs = (((data or {}).get("publishableUnpublish") or {}).get("userErrors")) or []
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo despublicar."
    return True, None


def _online_store_pub_id():
    """GID de la publicación 'Tienda online' (para saber si un producto está publicado
    en la web, que es lo que el admin muestra como Activo vs No publicado). None si no
    se puede (sin scope read_publications o no existe)."""
    _pubs, _err = listar_publicaciones()
    if _err or not _pubs:
        return None
    for p in _pubs:
        if "online" in (p.get("name") or "").strip().lower():   # "Online Store" / "Tienda online"
            return p.get("id")
    return None


def ids_publicados_online_store(max_paginas: int = 15) -> tuple:
    """Set de IDs (str, numéricos) publicados en la TIENDA ONLINE según la API de
    publicaciones (AUTORITATIVA: coincide con el 'Activo/No publicado' del admin, a
    diferencia de published_at / published_status del REST que son legacy y se
    desincronizan). Devuelve (set|None, error). None si falta scope/publicación."""
    _os = _online_store_pub_id()
    if not _os:
        return None, "No se identificó la publicación Tienda online (¿falta read_publications?)."
    ids, cursor = set(), None
    q = ("query($cursor:String,$pub:ID!){ products(first:100, after:$cursor){ "
         "pageInfo{ hasNextPage endCursor } "
         "edges{ node{ legacyResourceId publishedOnPublication(publicationId:$pub) } } } }")
    try:
        for _ in range(max(1, int(max_paginas))):
            data, err = _graphql(q, {"cursor": cursor, "pub": _os})
            if err:
                return None, err
            _conn = ((data or {}).get("products") or {})
            for e in _conn.get("edges") or []:
                n = e.get("node") or {}
                if n.get("publishedOnPublication"):
                    ids.add(str(n.get("legacyResourceId")))
            _pi = _conn.get("pageInfo") or {}
            if not _pi.get("hasNextPage"):
                break
            cursor = _pi.get("endCursor")
        return ids, None
    except Exception as e:
        return None, str(e)


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


def duplicar_producto(pid, new_title, include_images: bool = True, new_status: str = "DRAFT") -> tuple:
    """Duplica un producto (copia título/desc/variantes/opciones/tags/tipo + fotos si
    `include_images`) como BORRADOR por defecto. Devuelve (nuevo_id_numérico|None, error).
    NOTA: los metafields NO los copia Shopify; el llamador los copia aparte."""
    q = ("mutation($productId:ID!, $newTitle:String!, $includeImages:Boolean, $newStatus:ProductStatus){"
         " productDuplicate(productId:$productId, newTitle:$newTitle, includeImages:$includeImages, newStatus:$newStatus){"
         " newProduct { id } userErrors { field message } } }")
    _vars = {"productId": _gid_product(pid), "newTitle": str(new_title or "Copia"),
             "includeImages": bool(include_images), "newStatus": (new_status or "DRAFT")}
    data, err = _graphql(q, _vars)
    if err:
        return None, err
    _res = (data or {}).get("productDuplicate") or {}
    _errs = _res.get("userErrors") or []
    if _errs:
        return None, "; ".join(e.get("message", "") for e in _errs) or "No se pudo duplicar."
    _gid = ((_res.get("newProduct") or {}).get("id")) or ""
    return (_gid.rsplit("/", 1)[-1] if _gid else None), None


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
