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


def reordenar_media(pid, ordered_gids) -> tuple:
    """Reordena TODO el media del producto (fotos + videos) según `ordered_gids` (lista
    de media GIDs en el orden deseado). Usa productReorderMedia (asíncrono). Los medios
    no listados (recién agregados) quedan después. Devuelve (ok, error). DEFENSIVO."""
    _moves = [{"id": g, "newPosition": str(i)} for i, g in enumerate(ordered_gids) if g]
    if len(_moves) < 2:
        return True, None                       # nada que reordenar
    q = ("mutation($id:ID!, $moves:[MoveInput!]!){ productReorderMedia(id:$id, moves:$moves){ "
         "job { id } mediaUserErrors { field message } } }")
    data, err = _graphql(q, {"id": _gid_product(pid), "moves": _moves})
    if err:
        return False, err
    _errs = (((data or {}).get("productReorderMedia") or {}).get("mediaUserErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo reordenar el orden."
    return True, None


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


def _gid_collection(cid) -> str:
    return f"gid://shopify/Collection/{cid}"


def productos_de_coleccion(collection_id) -> tuple:
    """Productos de una colección MANUAL en su ORDEN actual (para reordenar). Devuelve
    (lista, sort_order, error). Cada producto: {gid, id, title, status, image, price}."""
    q = ("query($id:ID!){ collection(id:$id){ sortOrder "
         "products(first:250){ nodes { id legacyResourceId title status handle "
         "featuredImage { url } priceRangeV2 { minVariantPrice { amount } maxVariantPrice { amount } } "
         "} } } }")
    data, err = _graphql(q, {"id": _gid_collection(collection_id)})
    if err:
        return [], "", err
    _col = (data or {}).get("collection") or {}
    if not _col:
        return [], "", "La colección no existe o no es accesible."
    _so = _col.get("sortOrder") or ""
    _nodes = ((_col.get("products") or {}).get("nodes")) or []
    out = []
    for n in _nodes:
        _pr = (n.get("priceRangeV2") or {})
        out.append({
            "gid": n.get("id"),
            "id": n.get("legacyResourceId"),
            "title": n.get("title") or "",
            "status": n.get("status") or "",
            "handle": n.get("handle") or "",
            "image": (((n.get("featuredImage") or {}).get("url")) or ""),
            "price": (((_pr.get("minVariantPrice") or {}).get("amount")) or ""),
            "price_max": (((_pr.get("maxVariantPrice") or {}).get("amount")) or ""),
        })
    return out, _so, None


def set_coleccion_manual(collection_id) -> tuple:
    """Cambia el orden de la colección a Manual (requisito para fijar el orden a mano).
    Devuelve (ok, error)."""
    q = ("mutation($input:CollectionInput!){ collectionUpdate(input:$input){ "
         "collection { id sortOrder } userErrors { field message } } }")
    data, err = _graphql(q, {"input": {"id": _gid_collection(collection_id), "sortOrder": "MANUAL"}})
    if err:
        return False, err
    _errs = (((data or {}).get("collectionUpdate") or {}).get("userErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo cambiar a orden manual."
    return True, None


def reordenar_productos_coleccion(collection_id, ordered_gids) -> tuple:
    """Reordena los productos de una colección MANUAL según `ordered_gids` (lista de
    product GIDs). Usa collectionReorderProducts (asíncrono). La colección debe estar en
    orden Manual (el llamador lo asegura). Devuelve (ok, error). DEFENSIVO."""
    _moves = [{"id": g, "newPosition": str(i)} for i, g in enumerate(ordered_gids) if g]
    if len(_moves) < 2:
        return True, None
    q = ("mutation($id:ID!, $moves:[MoveInput!]!){ collectionReorderProducts(id:$id, moves:$moves){ "
         "job { id } userErrors { field message } } }")
    data, err = _graphql(q, {"id": _gid_collection(collection_id), "moves": _moves})
    if err:
        return False, err
    _errs = (((data or {}).get("collectionReorderProducts") or {}).get("userErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo reordenar la colección."
    return True, None


def listar_videos(pid) -> tuple:
    """Videos del producto (subidos + externos YouTube/Vimeo). Devuelve (lista, error).
    Cada uno: {id, type, status, preview_url, origin_url, host, src}. `src` = URL del
    MP4 reproducible (solo videos subidos; para reproducir en el visor fullscreen)."""
    q = ("query($id:ID!){ product(id:$id){ media(first:50){ nodes { "
         "id mediaContentType status preview { image { url } } "
         "... on ExternalVideo { host originUrl } "
         "... on Video { sources { url mimeType height } } } } } }")
    data, err = _graphql(q, {"id": _gid_product(pid)})
    if err:
        return [], err
    _nodes = (((data or {}).get("product") or {}).get("media") or {}).get("nodes") or []
    out = []
    for n in _nodes:
        if n.get("mediaContentType") not in ("VIDEO", "EXTERNAL_VIDEO"):
            continue
        # Mejor fuente MP4 (mayor altura) para reproducir en el visor.
        _src = ""
        _srcs = [s for s in (n.get("sources") or []) if (s or {}).get("url")]
        if _srcs:
            _mp4 = [s for s in _srcs if "mp4" in str(s.get("mimeType") or "").lower()] or _srcs
            _best = max(_mp4, key=lambda s: (s.get("height") or 0))
            _src = _best.get("url") or ""
        out.append({
            "id": n.get("id"),
            "type": n.get("mediaContentType"),
            "status": n.get("status"),
            "preview_url": (((n.get("preview") or {}).get("image") or {}).get("url")) or "",
            "origin_url": n.get("originUrl") or "",
            "host": n.get("host") or "",
            "src": _src,
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


def subir_video(pid, filename, mimetype, filebytes) -> tuple:
    """Sube un video (MP4/MOV) DESDE EL PC al producto vía staged uploads de Shopify.
    Flujo: stagedUploadsCreate (resource VIDEO) → POST del archivo al destino firmado
    (GCS, NO expone el token) → productCreateMedia (VIDEO). Devuelve (ok, error).
    Requiere write_products. Límite Shopify: MP4/MOV, hasta 1 GB y 10 min."""
    if not filebytes:
        return False, "El archivo de video está vacío."
    import requests
    # 1) Destino de subida firmado.
    q1 = ("mutation($input:[StagedUploadInput!]!){ stagedUploadsCreate(input:$input){ "
          "stagedTargets{ url resourceUrl parameters{ name value } } userErrors{ field message } } }")
    _input = [{"filename": filename or "video.mp4", "mimeType": mimetype or "video/mp4",
               "resource": "VIDEO", "fileSize": str(len(filebytes)), "httpMethod": "POST"}]
    data, err = _graphql(q1, {"input": _input})
    if err:
        return False, err
    _res = (data or {}).get("stagedUploadsCreate") or {}
    _ue = _res.get("userErrors") or []
    if _ue:
        return False, "; ".join(e.get("message", "") for e in _ue)
    _targets = _res.get("stagedTargets") or []
    if not _targets:
        return False, "Shopify no entregó un destino de subida para el video."
    _t = _targets[0]
    _url = _t.get("url")
    _params = _t.get("parameters") or []
    _resource_url = _t.get("resourceUrl")
    # 2) POST multipart al destino (los parámetros van primero; el 'file' AL FINAL).
    try:
        _form = [(p.get("name"), (None, p.get("value"))) for p in _params]
        _form.append(("file", (filename or "video.mp4", filebytes, mimetype or "video/mp4")))
        r = requests.post(_url, files=_form, timeout=1800)
        if r.status_code not in (200, 201, 204):
            return False, f"Subida al almacenamiento falló ({r.status_code}): {r.text[:150]}"
    except Exception as e:
        return False, f"Subida al almacenamiento: {e}"
    # 3) Asociar el video al producto.
    q2 = ("mutation($pid:ID!, $media:[CreateMediaInput!]!){ productCreateMedia(productId:$pid, media:$media){ "
          "media{ id mediaContentType } mediaUserErrors{ field message } } }")
    data2, err2 = _graphql(q2, {"pid": _gid_product(pid),
                                "media": [{"originalSource": _resource_url, "mediaContentType": "VIDEO"}]})
    if err2:
        return False, err2
    _errs = (((data2 or {}).get("productCreateMedia") or {}).get("mediaUserErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo asociar el video."
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


def _hint_files(msg) -> str:
    """Si el error es por falta de permiso de archivos, agrega una guía clara en español."""
    _m = str(msg or "").lower()
    if "write_files" in _m or "create files" in _m or "write_images" in _m or "filecreate" in _m:
        return (" — Falta el permiso para subir archivos. En tu app CUSTOM de Shopify: Admin → "
                "Configuración → Apps y canales de venta → Desarrollar apps → tu app → "
                "Configuración de API de Admin → agrega los scopes 'write_files' y 'read_files', "
                "Guarda y REINSTALA/actualiza la app (aprobación del comerciante). Además tu usuario "
                "debe tener permiso de 'Archivos'. Si al reinstalar cambia el token, actualiza SHOPIFY_TOKEN.")
    return ""


def subir_imagen_archivo(filename, mimetype, filebytes) -> tuple:
    """Sube una IMAGEN a Content > Files (staged upload IMAGE → fileCreate). Devuelve
    (gid, preview_url, error). El `gid` (gid://shopify/MediaImage/...) es el valor que espera
    un metacampo de tipo `file_reference`. Requiere write_files (además de write_products)."""
    if not filebytes:
        return None, None, "El archivo de imagen está vacío."
    import requests
    q1 = ("mutation($input:[StagedUploadInput!]!){ stagedUploadsCreate(input:$input){ "
          "stagedTargets{ url resourceUrl parameters{ name value } } userErrors{ field message } } }")
    _input = [{"filename": filename or "imagen.jpg", "mimeType": mimetype or "image/jpeg",
               "resource": "IMAGE", "fileSize": str(len(filebytes)), "httpMethod": "POST"}]
    data, err = _graphql(q1, {"input": _input})
    if err:
        return None, None, err + _hint_files(err)
    _res = (data or {}).get("stagedUploadsCreate") or {}
    _ue = _res.get("userErrors") or []
    if _ue:
        _msg = "; ".join(e.get("message", "") for e in _ue)
        return None, None, _msg + _hint_files(_msg)
    _targets = _res.get("stagedTargets") or []
    if not _targets:
        return None, None, "Shopify no entregó un destino de subida para la imagen."
    _t = _targets[0]
    _url, _params, _resource_url = _t.get("url"), _t.get("parameters") or [], _t.get("resourceUrl")
    try:
        _form = [(p.get("name"), (None, p.get("value"))) for p in _params]
        _form.append(("file", (filename or "imagen.jpg", filebytes, mimetype or "image/jpeg")))
        r = requests.post(_url, files=_form, timeout=600)
        if r.status_code not in (200, 201, 204):
            return None, None, f"Subida al almacenamiento falló ({r.status_code}): {r.text[:150]}"
    except Exception as e:
        return None, None, f"Subida al almacenamiento: {e}"
    q2 = ("mutation($files:[FileCreateInput!]!){ fileCreate(files:$files){ "
          "files{ id fileStatus preview{ image{ url } } ... on MediaImage{ image{ url } } } "
          "userErrors{ field message } } }")
    data2, err2 = _graphql(q2, {"files": [{"originalSource": _resource_url, "contentType": "IMAGE"}]})
    if err2:
        return None, None, err2 + _hint_files(err2)
    _fc = (data2 or {}).get("fileCreate") or {}
    _errs = _fc.get("userErrors") or []
    if _errs:
        _msg = "; ".join(e.get("message", "") for e in _errs)
        return None, None, (_msg or "No se pudo crear el archivo.") + _hint_files(_msg)
    _files = _fc.get("files") or []
    if not _files:
        return None, None, "Shopify no devolvió el archivo creado."
    _f = _files[0]
    _pv = ((((_f.get("preview") or {}).get("image") or {}).get("url"))
           or ((_f.get("image") or {}).get("url")) or "")
    return _f.get("id"), _pv, None


def subir_video_archivo(filename, mimetype, filebytes) -> tuple:
    """Sube un VIDEO a Content > Files (staged upload VIDEO → fileCreate). Devuelve
    (ref, preview_url, src, error). `ref` = 'shopify://files/videos/<filename>' — el valor que
    guarda el bloque reel en el campo 'video'. Requiere write_files. El video puede quedar
    PROCESÁNDOSE (preview/src vacíos por un rato); el ref igual queda válido."""
    if not filebytes:
        return None, None, None, "El archivo de video está vacío."
    import requests
    q1 = ("mutation($input:[StagedUploadInput!]!){ stagedUploadsCreate(input:$input){ "
          "stagedTargets{ url resourceUrl parameters{ name value } } userErrors{ field message } } }")
    _input = [{"filename": filename or "video.mp4", "mimeType": mimetype or "video/mp4",
               "resource": "VIDEO", "fileSize": str(len(filebytes)), "httpMethod": "POST"}]
    data, err = _graphql(q1, {"input": _input})
    if err:
        return None, None, None, err + _hint_files(err)
    _res = (data or {}).get("stagedUploadsCreate") or {}
    _ue = _res.get("userErrors") or []
    if _ue:
        _msg = "; ".join(e.get("message", "") for e in _ue)
        return None, None, None, _msg + _hint_files(_msg)
    _targets = _res.get("stagedTargets") or []
    if not _targets:
        return None, None, None, "Shopify no entregó un destino de subida para el video."
    _t = _targets[0]
    _url, _params, _resource_url = _t.get("url"), _t.get("parameters") or [], _t.get("resourceUrl")
    try:
        _form = [(p.get("name"), (None, p.get("value"))) for p in _params]
        _form.append(("file", (filename or "video.mp4", filebytes, mimetype or "video/mp4")))
        r = requests.post(_url, files=_form, timeout=600)
        if r.status_code not in (200, 201, 204):
            return None, None, None, f"Subida al almacenamiento falló ({r.status_code}): {r.text[:150]}"
    except Exception as e:
        return None, None, None, f"Subida al almacenamiento: {e}"
    q2 = ("mutation($files:[FileCreateInput!]!){ fileCreate(files:$files){ "
          "files{ id fileStatus preview{ image{ url } } "
          "... on Video { filename sources{ url mimeType height format } } } "
          "userErrors{ field message } } }")
    data2, err2 = _graphql(q2, {"files": [{"originalSource": _resource_url, "contentType": "VIDEO"}]})
    if err2:
        return None, None, None, err2 + _hint_files(err2)
    _fc = (data2 or {}).get("fileCreate") or {}
    _errs = _fc.get("userErrors") or []
    if _errs:
        _msg = "; ".join(e.get("message", "") for e in _errs)
        return None, None, None, (_msg or "No se pudo crear el video.") + _hint_files(_msg)
    _files = _fc.get("files") or []
    if not _files:
        return None, None, None, "Shopify no devolvió el video creado."
    _f = _files[0]
    _fn = _f.get("filename") or (filename or "video.mp4")
    _pv = (((_f.get("preview") or {}).get("image") or {}).get("url")) or ""
    return f"shopify://files/videos/{_fn}", _pv, _src_de_video_node(_f), None


def set_metafield_referencia(pid, namespace, key, ref_gid, mtype="file_reference") -> tuple:
    """Fija (crea o actualiza) un metacampo de referencia (p.ej. imagen file_reference) del
    producto al recurso `ref_gid`. Usa metafieldsSet (idempotente por owner+namespace+key).
    Devuelve (ok, error)."""
    if not ref_gid:
        return False, "Falta la referencia (gid) del archivo."
    q = ("mutation($m:[MetafieldsSetInput!]!){ metafieldsSet(metafields:$m){ "
         "metafields{ id } userErrors{ field message } } }")
    _m = [{"ownerId": _gid_product(pid), "namespace": namespace, "key": key,
           "type": mtype, "value": ref_gid}]
    data, err = _graphql(q, {"m": _m})
    if err:
        return False, err
    _errs = (((data or {}).get("metafieldsSet") or {}).get("userErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo fijar el metacampo."
    return True, None


def borrar_metafield_por_clave(pid, namespace, key) -> tuple:
    """Elimina un metacampo del producto por owner+namespace+key (GraphQL). Devuelve (ok, error)."""
    q = ("mutation($m:[MetafieldIdentifierInput!]!){ metafieldsDelete(metafields:$m){ "
         "deletedMetafields{ key } userErrors{ field message } } }")
    _m = [{"ownerId": _gid_product(pid), "namespace": namespace, "key": key}]
    data, err = _graphql(q, {"m": _m})
    if err:
        return False, err
    _errs = (((data or {}).get("metafieldsDelete") or {}).get("userErrors") or [])
    if _errs:
        return False, "; ".join(e.get("message", "") for e in _errs) or "No se pudo eliminar el metacampo."
    return True, None


def resolver_imagenes(gids) -> tuple:
    """Dado un iterable de gids (MediaImage/GenericFile), devuelve ({gid: url}, error) para
    mostrar la miniatura de metacampos de imagen. DEFENSIVO."""
    _ids = [str(g) for g in (gids or []) if g and str(g).startswith("gid://")]
    if not _ids:
        return {}, None
    q = ("query($ids:[ID!]!){ nodes(ids:$ids){ id __typename "
         "... on MediaImage{ image{ url } preview{ image{ url } } } "
         "... on GenericFile{ url preview{ image{ url } } } } }")
    data, err = _graphql(q, {"ids": list(dict.fromkeys(_ids))})
    if err:
        return {}, err
    out = {}
    for n in ((data or {}).get("nodes") or []):
        if not n:
            continue
        out[n.get("id")] = ((((n.get("image") or {}).get("url"))
                             or (((n.get("preview") or {}).get("image") or {}).get("url"))
                             or n.get("url") or ""))
    return out, None


# ── Tema / REELS (Asset API — requiere read_themes / write_themes) ────────────

def _scope_hint_themes(code) -> str:
    return (" — el token NO tiene aprobado 'read_themes'/'write_themes'. En tu app custom de "
            "Shopify: agrega los scopes read_themes y write_themes, Guarda y REINSTALA la app "
            "(aprobación del comerciante). Si al reinstalar cambia el token, actualiza "
            "SHOPIFY_TOKEN." if code in (401, 403) else "")


# Límite de Shopify REST = 2 llamadas/seg. El Asset API se usa en ráfaga (varios temas ×
# varios JSON), así que TODAS las llamadas pasan por un throttle global + reintento en 429.
_LAST_ASSET_CALL = [0.0]
_ASSET_MIN_INTERVAL = 0.55  # ~1.8 req/s, bajo el tope de 2/s


def _asset_api(method, url, **kwargs) -> tuple:
    """GET/PUT al Asset API respetando el límite de 2 req/s (throttle) y reintentando en
    429 (hasta 6 veces, honrando Retry-After). Devuelve (response|None, error_str|None)."""
    import time, requests
    kwargs.setdefault("headers", _headers())
    kwargs.setdefault("timeout", 30)
    _last_err = None
    for _ in range(6):
        _elapsed = time.time() - _LAST_ASSET_CALL[0]
        if _elapsed < _ASSET_MIN_INTERVAL:
            time.sleep(_ASSET_MIN_INTERVAL - _elapsed)
        try:
            r = requests.request(method, url, **kwargs)
        except Exception as e:
            _LAST_ASSET_CALL[0] = time.time()
            _last_err = str(e)
            time.sleep(0.6)
            continue
        _LAST_ASSET_CALL[0] = time.time()
        if r.status_code == 429:
            _ra = r.headers.get("Retry-After")
            try:
                _wait = float(_ra) if _ra else 1.0
            except Exception:
                _wait = 1.0
            time.sleep(min(max(_wait, 0.6), 5.0))
            _last_err = f"Shopify 429: {(r.text or '')[:120]}"
            continue
        return r, None
    return None, (_last_err or "Shopify 429: se excedió el límite de solicitudes.")


def listar_temas() -> tuple:
    """Temas de la tienda (Asset API). Devuelve (lista, error). Cada uno: {id, name, role}."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    r, err = _asset_api("GET", f"https://{_store()}/admin/api/{_version()}/themes.json", timeout=25)
    if err:
        return [], err
    if r.status_code == 200:
        return (r.json() or {}).get("themes") or [], None
    return [], f"Shopify {r.status_code}: {r.text[:150]}" + _scope_hint_themes(r.status_code)


def tema_principal() -> tuple:
    """El tema PUBLICADO (role='main'). Devuelve (theme|None, error)."""
    _temas, err = listar_temas()
    if err:
        return None, err
    _m = next((t for t in (_temas or []) if str(t.get("role")) == "main"), None)
    return _m, (None if _m else "No se encontró el tema principal (publicado).")


def url_preview_tema(theme_id, path: str = "") -> str:
    """URL para VER la tienda (o una ruta, p.ej. '/products/<handle>') renderizada con un
    tema concreto — sirve para previsualizar un tema BORRADOR sin publicarlo. Funciona para
    el staff logueado en Shopify. Devuelve '' si faltan credenciales o theme_id."""
    if not _store() or not theme_id:
        return ""
    _p = str(path or "")
    if _p and not _p.startswith("/"):
        _p = "/" + _p
    _sep = "&" if "?" in _p else "?"
    return f"https://{_store()}{_p}{_sep}preview_theme_id={theme_id}"


def leer_asset(theme_id, key) -> tuple:
    """Lee el valor de un asset del tema (p.ej. 'config/settings_data.json'). Devuelve
    (value_str|None, error). 404 = no existe (no es error duro). DEFENSIVO."""
    if not configurado():
        return None, "Sin credenciales de Shopify."
    r, err = _asset_api("GET", f"https://{_store()}/admin/api/{_version()}/themes/{theme_id}/assets.json",
                        params={"asset[key]": key}, timeout=25)
    if err:
        return None, err
    if r.status_code == 200:
        return ((r.json() or {}).get("asset") or {}).get("value"), None
    if r.status_code == 404:
        return None, None
    return None, f"Shopify {r.status_code}: {r.text[:150]}" + _scope_hint_themes(r.status_code)


def listar_assets_json(theme_id) -> tuple:
    """CLAVES de assets JSON del tema (templates/*.json, sections/*.json y settings_data),
    donde pueden vivir las secciones. Devuelve (keys, error)."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    r, err = _asset_api("GET", f"https://{_store()}/admin/api/{_version()}/themes/{theme_id}/assets.json",
                        timeout=30)
    if err:
        return [], err
    if r.status_code != 200:
        return [], f"Shopify {r.status_code}: {r.text[:150]}" + _scope_hint_themes(r.status_code)
    _keys = [a.get("key") for a in ((r.json() or {}).get("assets") or [])]
    _out = [k for k in _keys if k and k.endswith(".json")
            and (k.startswith("templates/") or k.startswith("sections/")
                 or k == "config/settings_data.json")]
    return _out, None


def escribir_asset(theme_id, key, value) -> tuple:
    """Escribe (REEMPLAZA) un asset del tema. CUIDADO: es la config del tema — el llamador
    hace read-modify-write con respaldo. Devuelve (ok, error)."""
    if not configurado():
        return False, "Sin credenciales de Shopify."
    r, err = _asset_api("PUT", f"https://{_store()}/admin/api/{_version()}/themes/{theme_id}/assets.json",
                        json={"asset": {"key": key, "value": value}}, timeout=45)
    if err:
        return False, err
    if r.status_code in (200, 201):
        return True, None
    return False, f"Shopify {r.status_code}: {r.text[:200]}" + _scope_hint_themes(r.status_code)


# Tipos de bloque que son "asesor" (según cómo esté nombrado el bloque en el tema).
_ADV_TYPES = ("advisor", "asesor", "asesora")


def _secciones_con_reels(obj):
    """TODAS las secciones que tienen algún bloque 'reel' en un JSON parseado. Devuelve
    lista de (section_id, section)."""
    _secs = obj.get("sections") if isinstance(obj, dict) else None
    if not isinstance(_secs, dict):
        return []
    _out = []
    for _sid, _sec in _secs.items():
        if not isinstance(_sec, dict):
            continue
        _blocks = _sec.get("blocks") or {}
        if isinstance(_blocks, dict) and any(
                isinstance(_b, dict) and _b.get("type") == "reel" for _b in _blocks.values()):
            _out.append((_sid, _sec))
    return _out


def _reels_en_tema(tema) -> tuple:
    """Busca la MEJOR sección de reels dentro de UN tema. Devuelve (info|None, error).
    Puede haber VARIAS secciones con bloques 'reel' (p.ej. "Reels de video" y "Reels por
    asesor"); se elige la que tiene bloques de asesor (y más reels). Un error != None es un
    fallo DURO. 'No encontrado' => (None, None) para seguir probando otros temas."""
    import json as _json
    if not isinstance(tema, dict):
        return None, None
    _tid = tema.get("id")
    _keys, err2 = listar_assets_json(_tid)
    if err2:
        return None, err2
    # Los reels viven en la HOME, en settings_data (legacy) o en un section group.
    _sd = [k for k in _keys if k == "config/settings_data.json"]
    _idx = [k for k in _keys if k == "templates/index.json"]
    _idx2 = [k for k in _keys if k.startswith("templates/index.") and k not in _idx]
    _grp = [k for k in _keys if k.startswith("sections/") and k.endswith(".json")]
    _pri = _sd + _idx + _idx2 + _grp
    _cands = []  # (n_advisors, n_reels, asset_key, sid, sec)
    for _key in _pri:
        _val, _e = leer_asset(_tid, _key)
        if _e or not _val:
            continue
        try:
            _obj = _json.loads(_val)
        except Exception:
            continue
        _cand = _obj
        if _key == "config/settings_data.json":
            _cand = _obj.get("current") if isinstance(_obj.get("current"), dict) else {}
        for _sid, _sec in _secciones_con_reels(_cand or {}):
            _blocks = _sec.get("blocks") or {}
            _nr = sum(1 for _b in _blocks.values() if isinstance(_b, dict) and _b.get("type") == "reel")
            _na = sum(1 for _b in _blocks.values() if isinstance(_b, dict) and _b.get("type") in _ADV_TYPES)
            _cands.append((_na, _nr, _key, _sid, _sec))
    if not _cands:
        return None, None
    # Preferir la sección CON asesores (la "Reels por asesor"), luego la que tiene más reels.
    _cands.sort(key=lambda c: (c[0] > 0, c[0], c[1]), reverse=True)
    _na, _nr, _key, _sid, _sec = _cands[0]
    _blocks = _sec.get("blocks") or {}
    _order = _sec.get("block_order") or list(_blocks.keys())
    _adv_type = next((_b.get("type") for _b in _blocks.values()
                      if isinstance(_b, dict) and _b.get("type") in _ADV_TYPES), "advisor")
    _reels, _advisors, _raw, _raw_blocks = [], [], None, []
    for _bid in _order:
        _b = _blocks.get(_bid)
        if not isinstance(_b, dict):
            continue
        _st = _b.get("settings") or {}
        if len(_raw_blocks) < 12:
            _raw_blocks.append({"id": _bid, "type": _b.get("type"), "settings": _st})
        if _b.get("type") == "reel":
            if _raw is None:
                _raw = _b
            _reels.append({"id": _bid, "video": _st.get("video"),
                           "caption": _st.get("caption") or "",
                           "linked_product": _st.get("linked_product"),
                           "advisor_name": _st.get("advisor_name") or ""})
        elif _b.get("type") in _ADV_TYPES:
            _advisors.append({"id": _bid, "name": _st.get("name") or "",
                              "role": _st.get("role") or "", "video": _st.get("video")})
    return ({"theme_id": _tid, "theme_name": tema.get("name") or "",
             "theme_role": str(tema.get("role") or ""), "asset_key": _key,
             "section_id": _sid, "section_type": _sec.get("type") or "",
             "advisor_type": _adv_type, "block_order": _order, "reels": _reels,
             "advisors": _advisors, "raw_reel": _raw, "raw_blocks": _raw_blocks,
             "n_secciones": len(_cands)}, None)


def leer_reels() -> tuple:
    """Encuentra la sección de reels y devuelve (info|None, error). Busca PRIMERO en el
    tema publicado (role='main'); si no está ahí, en los temas BORRADOR (role='unpublished'/
    'development'), para poder editar una versión en construcción. info incluye theme_role
    ('main' = producción, otro = borrador) y theme_name para que la UI lo indique. En cada
    tema escanea todos los JSON (settings_data + templates + section groups) buscando la 1ª
    sección con bloques de tipo 'reel'."""
    _temas, err = listar_temas()
    if err:
        return None, err
    if not _temas:
        return None, "No hay temas en la tienda."
    _main = next((t for t in _temas if str(t.get("role")) == "main"), None)
    # Publicado primero; luego el resto (borradores/desarrollo). Excluye copias de sistema.
    _borradores = [t for t in _temas if t is not _main
                   and str(t.get("role")) not in ("demo", "archived")]
    _orden = ([_main] if _main else []) + _borradores
    _primer_err = None
    for _t in _orden:
        _info, _e = _reels_en_tema(_t)
        if _e:
            _primer_err = _primer_err or _e
            continue
        if _info:
            return _info, None
    return None, (_primer_err
                  or "No se encontró una sección de reels en ningún tema (ni publicado ni borrador).")


def _norm_fn(s) -> str:
    """Normaliza un nombre de archivo para comparar (minúsculas + espacios colapsados)."""
    return " ".join(str(s or "").split()).strip().lower()


def _src_de_video_node(_n) -> str:
    """Mejor URL .mp4 de las 'sources' de un nodo Video."""
    _srcs = [s for s in ((_n or {}).get("sources") or []) if (s or {}).get("url")]
    if not _srcs:
        return ""
    _mp4 = [s for s in _srcs if "mp4" in str(s.get("mimeType") or s.get("format") or "").lower()] or _srcs
    return (max(_mp4, key=lambda s: (s.get("height") or 0)).get("url")) or ""


def _fetch_videos_files() -> list:
    """Nodos Video de Content > Files (hasta 250). DEFENSIVO: si falla devuelve []."""
    def _fetch(_qf):
        q = ("query($q:String){ files(first:250, query:$q){ nodes{ __typename "
             "... on Video { id filename preview{ image{ url } } "
             "sources{ url mimeType height format } } } } }")
        data, err = _graphql(q, {"q": _qf})
        if err:
            return None
        return ((data or {}).get("files") or {}).get("nodes") or []
    _nodes = _fetch("media_type:VIDEO")
    if not _nodes:  # por si el filtro no aplica en esta versión de la API
        _nodes = _fetch(None)
    return [_n for _n in (_nodes or []) if _n and _n.get("__typename") == "Video"]


def _mapa_videos_files() -> dict:
    """Videos de Content > Files como {filename_normalizado: {gid, preview_url, src}}.
    Se usa para resolver referencias 'shopify://files/videos/<nombre>' (los reels guardan
    el video como archivo, no como Video de producto). DEFENSIVO: si falla, devuelve {}."""
    _map = {}
    for _n in _fetch_videos_files():
        _map[_norm_fn(_n.get("filename"))] = {
            "gid": _n.get("id") or "",
            "preview_url": (((_n.get("preview") or {}).get("image") or {}).get("url")) or "",
            "src": _src_de_video_node(_n)}
    return _map


def listar_videos_files() -> tuple:
    """Lista los videos de Content > Files para el SELECTOR al editar reels. Devuelve
    (lista, error) con {filename, ref, preview_url, src}. `ref` es el valor a guardar en el
    campo 'video' del reel: 'shopify://files/videos/<filename>'."""
    if not configurado():
        return [], "Sin credenciales de Shopify."
    _out = []
    for _n in _fetch_videos_files():
        _fn = _n.get("filename") or ""
        if not _fn:
            continue
        _out.append({"filename": _fn, "ref": f"shopify://files/videos/{_fn}",
                     "preview_url": (((_n.get("preview") or {}).get("image") or {}).get("url")) or "",
                     "src": _src_de_video_node(_n)})
    _out.sort(key=lambda v: v["filename"].lower())
    return _out, None


def resolver_videos(video_ids) -> tuple:
    """Dado un iterable de valores de video de los reels, devuelve (dict, error) con
    {valor_original: {gid, preview_url, src}}. Resuelve DOS formatos:
      • id numérico / gid://shopify/Video/... → vía GraphQL nodes (Video de producto)
      • shopify://files/videos/<nombre>.mp4  → vía Content>Files, por nombre de archivo
    DEFENSIVO: lo que no se pueda resolver queda con preview_url/src vacíos."""
    _norm, _files = {}, {}  # gid-based / file-based
    for _v in video_ids or []:
        if not _v:
            continue
        _s = str(_v)
        if _s.startswith("gid://shopify/Video/"):
            _norm[_s] = _s
        elif _s.startswith("shopify://files/") or "/files/videos/" in _s:
            _norm_path = _s.split("/videos/", 1)[-1] if "/videos/" in _s else _s.rsplit("/", 1)[-1]
            try:
                from urllib.parse import unquote
                _norm_path = unquote(_norm_path)
            except Exception:
                pass
            _files[_s] = _norm_path
        elif _s.isdigit():
            _norm[_s] = f"gid://shopify/Video/{_s}"
        else:
            continue
    out = {}
    # 1) Videos de producto por gid/id (nodes)
    if _norm:
        q = ("query($ids:[ID!]!){ nodes(ids:$ids){ id __typename "
             "... on Video { preview { image { url } } sources { url height mimeType } } } }")
        data, err = _graphql(q, {"ids": list(dict.fromkeys(_norm.values()))})
        if err:
            return {}, err
        _by_gid = {}
        for _n in ((data or {}).get("nodes") or []):
            if not _n:
                continue
            _by_gid[_n.get("id")] = {
                "gid": _n.get("id"),
                "preview_url": (((_n.get("preview") or {}).get("image") or {}).get("url")) or "",
                "src": _src_de_video_node(_n)}
        for _o, _g in _norm.items():
            out[_o] = _by_gid.get(_g, {"gid": _g, "preview_url": "", "src": ""})
    # 2) Videos subidos a Files (referencia shopify://files/...) por nombre de archivo
    if _files:
        _fmap = _mapa_videos_files()
        for _o, _fn in _files.items():
            out[_o] = _fmap.get(_norm_fn(_fn)) or {"gid": "", "preview_url": "", "src": ""}
    return out, None


def guardar_reels(theme_id, asset_key, section_id, reels, backup=True, prod_handles=None) -> tuple:
    """FASE 2 — reescribe los bloques 'reel' de la sección en el asset del tema (read-modify-
    write con respaldo). `reels` es la lista FINAL en ORDEN: cada uno {id?, video, caption,
    linked_product, advisor_name}; los que no traen 'id' se CREAN, los que faltan respecto al
    tema se ELIMINAN, y el orden de la lista fija el block_order de los reels. Conserva intactos
    los bloques que no son reel (asesores). `prod_handles`={id:handle} para el caso en que el
    tema guarde el producto por handle. Devuelve (ok, error, backup_key|None).

    CUIDADO: escribe la config del tema. Sólo toca la sección indicada y los campos conocidos;
    antes de escribir guarda un respaldo del asset original en assets/reels_backup_<ts>.json."""
    import json as _json, uuid, time
    if not configurado():
        return False, "Sin credenciales de Shopify.", None
    _val, _e = leer_asset(theme_id, asset_key)
    if _e:
        return False, _e, None
    if not _val:
        return False, "No se pudo leer el asset del tema (¿cambió?).", None
    _raw = _val
    try:
        _obj = _json.loads(_val)
    except Exception:
        try:  # los .json de tema a veces llevan un comentario /* */ inicial
            import re
            _clean = re.sub(r"^\s*/\*.*?\*/\s*", "", _val, flags=re.S)
            _obj = _json.loads(_clean)
            _raw = _clean
        except Exception as ex:
            return False, f"No se pudo interpretar el JSON del tema: {ex}", None
    _cont = _obj
    if asset_key == "config/settings_data.json":
        _cont = _obj.get("current") if isinstance(_obj.get("current"), dict) else None
        if _cont is None:
            return False, "Estructura inesperada de settings_data.json.", None
    _secs = _cont.get("sections") if isinstance(_cont, dict) else None
    if not isinstance(_secs, dict) or section_id not in _secs:
        return False, "No se encontró la sección de reels (¿cambió el tema?).", None
    _sec = _secs[section_id]
    _blocks = _sec.get("blocks") or {}
    _order = _sec.get("block_order") or list(_blocks.keys())
    # Bloques que NO son reel (asesores, etc.), en su orden original: se conservan tal cual.
    _no_reel = [bid for bid in _order if isinstance(_blocks.get(bid), dict)
                and _blocks[bid].get("type") != "reel"]
    _new_blocks = {bid: _blocks[bid] for bid in _no_reel}
    _new_reel_ids = []
    for _r in (reels or []):
        _bid = _r.get("id")
        if _bid and _bid in _blocks and (_blocks.get(_bid) or {}).get("type") == "reel":
            _stt = dict((_blocks[_bid] or {}).get("settings") or {})  # conserva campos extra
        else:
            _bid = "reel_" + uuid.uuid4().hex[:12]
            _stt = {}
        _vid = _r.get("video")
        if _vid in (None, ""):
            _vid = _stt.get("video", "")
        _stt["video"] = _vid
        _stt["caption"] = _r.get("caption", "") or ""
        # El setting 'product' de ESTE tema guarda el HANDLE del producto ("cabana-alerce"),
        # NO el id ni el gid (confirmado con el diagnóstico: un reel asignado desde Shopify guarda
        # el handle; con id numérico o gid la etiqueta NO aparece). Convertimos id→handle con
        # prod_handles. Si viene VACÍO se DESVINCULA (queda ""); la preselección del selector ya
        # normaliza handle→id, así que "(sin producto)" es una acción intencional del usuario.
        _lp = str(_r.get("linked_product", "") or "").strip()
        if _lp.startswith("gid://"):
            _lp = _lp.rsplit("/", 1)[-1]
        if _lp and _lp.isdigit():
            _lp = (prod_handles or {}).get(_lp) or _lp   # id → handle (lo que espera el tema)
        _stt["linked_product"] = _lp   # "" = sin producto (permite quitar el vínculo)
        _stt["advisor_name"] = _r.get("advisor_name", "") or ""
        _new_blocks[_bid] = {"type": "reel", "settings": _stt}
        _new_reel_ids.append(_bid)
    _sec["blocks"] = _new_blocks
    _sec["block_order"] = _no_reel + _new_reel_ids
    # Respaldo best-effort del asset ORIGINAL (por si hay que revertir a mano).
    _bkey = None
    if backup:
        _cand = f"assets/reels_backup_{time.strftime('%Y%m%d_%H%M%S')}.json"
        try:
            _bok, _ = escribir_asset(theme_id, _cand, _raw)
            _bkey = _cand if _bok else None
        except Exception:
            _bkey = None
    _ok, _we = escribir_asset(theme_id, asset_key, _json.dumps(_obj, ensure_ascii=False))
    if not _ok:
        return False, _we, _bkey
    return True, None, _bkey


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
        # Etiquetas del cliente en Shopify (coma-separadas). Sirven para clasificar el
        # ORIGEN del lead: cada formulario del sitio pone su propia etiqueta (p.ej.
        # "FORMULARIO COTIZA") y el CRM la usa para distinguir de qué formulario vino.
        "tags": str(c.get("tags") or "").strip(),
    }
