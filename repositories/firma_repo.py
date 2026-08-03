"""
Repositorio de la FIRMA de correo del CRM.

Almacén clave→valor en la tabla NUEVA `crm_firma` (el usuario corre el CREATE TABLE):
  - clave 'empresa'      → bloque compartido {empresa, web, direccion, telefono, logo_url, incluir}
  - clave '<email exec>' → datos del ejecutivo {cargo, telefono}

Además hospeda el `logo.png` del proyecto en el bucket público de imágenes (el mismo
de los avatares) para poder embeberlo en los correos (Gmail bloquea imágenes base64,
por eso necesita una URL pública). TODO DEFENSIVO: si algo falla, devuelve vacío y el
envío de correo sigue funcionando (solo no se agrega la firma).
"""
import os

from config.supabase import supabase_admin as _supa
from config.settings import SUPABASE_URL as _URL

_BUCKET = "formulario-imagenes"          # bucket público existente (avatares)
_LOGO_DEST = "crm/logo-firma.png"
_ICON_FILES = {"mail": "mail.png", "phone": "phone.png",
               "whatsapp": "whatsapp.png", "location": "location.png"}


def _subir(dest: str, data: bytes):
    """Sube (upsert) bytes al bucket público. Tolera distintas versiones de supabase-py."""
    try:
        _supa.storage.from_(_BUCKET).upload(dest, data,
                                            {"content-type": "image/png", "x-upsert": "true"})
    except Exception:
        try:
            _supa.storage.from_(_BUCKET).update(dest, data, {"content-type": "image/png"})
        except Exception:
            pass


def _url_publica(dest: str) -> str:
    return f"{str(_URL).rstrip('/')}/storage/v1/object/public/{_BUCKET}/{dest}"


def get_firma(clave: str) -> dict:
    """Valor (dict) de una clave. {} si no existe la tabla/clave."""
    try:
        r = _supa.table("crm_firma").select("valor").eq("clave", str(clave)).limit(1).execute()
        d = r.data or []
        return (d[0].get("valor") or {}) if d else {}
    except Exception:
        return {}


def set_firma(clave: str, valor: dict) -> tuple:
    """Upsert de una clave. Devuelve (ok, err). DEFENSIVO."""
    try:
        _supa.table("crm_firma").upsert({"clave": str(clave), "valor": valor or {}}).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def listar_firmas() -> dict:
    """{clave: valor} de todas las filas. {} si no existe la tabla."""
    try:
        r = _supa.table("crm_firma").select("clave,valor").execute()
        return {x.get("clave"): (x.get("valor") or {}) for x in (r.data or [])}
    except Exception:
        return {}


def logo_url_publica() -> str:
    """URL pública del logo para la firma. La primera vez sube `logo.png` al bucket
    público y guarda la URL en la config 'empresa'. '' si no se pudo."""
    cfg = get_firma("empresa")
    u = str(cfg.get("logo_url") or "").strip()
    if u:
        return u
    try:
        ruta = os.path.join(os.getcwd(), "logo.png")
        if not os.path.exists(ruta):
            return ""
        with open(ruta, "rb") as f:
            _subir(_LOGO_DEST, f.read())
        url = _url_publica(_LOGO_DEST)
        cfg["logo_url"] = url
        set_firma("empresa", cfg)
        return url
    except Exception:
        return ""


def iconos_urls() -> dict:
    """Sube (una vez) los iconos de la firma (correo/teléfono/WhatsApp/ubicación) al
    bucket público y devuelve {nombre: url}. Cachea las URLs en la config 'empresa'.
    {} si no se pudo (la firma cae a símbolos de texto)."""
    cfg = get_firma("empresa")
    cache = dict(cfg.get("iconos") or {})
    if all(cache.get(k) for k in _ICON_FILES):
        return cache
    cambio = False
    for name, fname in _ICON_FILES.items():
        if cache.get(name):
            continue
        try:
            ruta = os.path.join(os.getcwd(), "assets", "firma", fname)
            if not os.path.exists(ruta):
                continue
            with open(ruta, "rb") as f:
                _subir(f"crm/firma-{name}.png", f.read())
            cache[name] = _url_publica(f"crm/firma-{name}.png")
            cambio = True
        except Exception:
            pass
    if cambio:
        cfg["iconos"] = cache
        set_firma("empresa", cfg)
    return cache
