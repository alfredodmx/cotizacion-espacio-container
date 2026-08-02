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
            data = f.read()
        # upsert=true por si ya existe; distintas versiones de supabase-py aceptan
        # el header en el dict de opciones.
        try:
            _supa.storage.from_(_BUCKET).upload(
                _LOGO_DEST, data, {"content-type": "image/png", "x-upsert": "true"})
        except Exception:
            try:
                _supa.storage.from_(_BUCKET).update(_LOGO_DEST, data,
                                                    {"content-type": "image/png"})
            except Exception:
                pass
        url = f"{str(_URL).rstrip('/')}/storage/v1/object/public/{_BUCKET}/{_LOGO_DEST}"
        cfg["logo_url"] = url
        set_firma("empresa", cfg)
        return url
    except Exception:
        return ""
