"""
Repositorio de CAMPAÑAS (envíos masivos por segmento).

Cada campaña es una fila en la tabla NUEVA `crm_campanas` (el usuario corre el CREATE
TABLE) y sus correos se etiquetan con `crm_correos.campana_id`. El reporte (tasas de
apertura/clic/rebote/spam) se DERIVA de esos correos. TODO DEFENSIVO.
"""
import uuid
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa

_TZ_CL = timezone(timedelta(hours=-3))


def crear_campana(asunto, segmento, actor, total) -> str:
    """Crea la campaña y devuelve su id ('' si falla)."""
    try:
        cid = str(uuid.uuid4())
        _supa.table("crm_campanas").insert({
            "id": cid,
            "fecha": datetime.now(_TZ_CL).isoformat(),
            "asunto": str(asunto or ""),
            "segmento": str(segmento or ""),
            "actor": str(actor or ""),
            "total": int(total or 0),
        }).execute()
        return cid
    except Exception:
        return ""


def listar_campanas() -> list:
    """Campañas, más reciente primero. [] si no existe la tabla."""
    try:
        return (_supa.table("crm_campanas").select("*").order("fecha", desc=True)
                .limit(100).execute().data or [])
    except Exception:
        return []


def correos_de_campana(campana_id) -> list:
    """Correos (con su estado) de una campaña. [] si no existe."""
    try:
        return (_supa.table("crm_correos").select("*").eq("campana_id", str(campana_id))
                .order("para").execute().data or [])
    except Exception:
        return []
