"""
Feed de notificaciones por usuario (la campana del header). Tabla `notificaciones`
(distinta de `notificaciones_config`, que es la config de Telegram).

General: sirve para CUALQUIER evento (recordatorio, vencido, adjudicado, lead…),
con leído/no-leído por destinatario. Escrituras por service key. Las LECTURAS son
DEFENSIVAS (si la tabla no existe todavía → 0 / [], sin lanzar) porque alimentan
el HEADER, que es compartido por todo el sistema: un fallo acá no puede tumbar la
barra superior.
"""
import uuid
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa

_TZ_CL = timezone(timedelta(hours=-3))


def _ahora() -> str:
    return datetime.now(_TZ_CL).isoformat()


def _norm_email(e) -> str:
    return str(e or "").strip().lower()


def crear_notificacion(user_email, titulo, tipo="recordatorio", detalle="",
                       cliente_id=None) -> str | None:
    """Crea una notificación para `user_email` (el destinatario). Nunca lanza."""
    em = _norm_email(user_email)
    if not em:
        return None
    try:
        nid = str(uuid.uuid4())
        _supa.table("notificaciones").insert({
            "id": nid,
            "user_email": em,
            "tipo": str(tipo or "recordatorio"),
            "titulo": str(titulo or "")[:300],
            "detalle": str(detalle or "")[:500],
            "cliente_id": cliente_id,
            "leido": False,
            "fecha": _ahora(),
        }).execute()
        return nid
    except Exception:
        return None


def contar_no_leidas(user_email) -> int:
    """Cantidad de notificaciones sin leer del usuario. Defensivo → 0 si falla."""
    em = _norm_email(user_email)
    if not em:
        return 0
    try:
        r = (_supa.table("notificaciones").select("id", count="exact")
             .eq("user_email", em).eq("leido", False).execute())
        return int(r.count or 0)
    except Exception:
        return 0


def listar_notificaciones(user_email, limit: int = 15) -> list:
    """Notificaciones del usuario: no leídas primero, luego por fecha desc."""
    em = _norm_email(user_email)
    if not em:
        return []
    try:
        return (_supa.table("notificaciones").select("*")
                .eq("user_email", em)
                .order("leido").order("fecha", desc=True)
                .limit(limit).execute().data or [])
    except Exception:
        return []


def marcar_leidas(user_email, ids=None) -> bool:
    """Marca como leídas todas (o `ids`) las notificaciones del usuario."""
    em = _norm_email(user_email)
    if not em:
        return False
    try:
        q = _supa.table("notificaciones").update({"leido": True}).eq("user_email", em)
        if ids:
            q = q.in_("id", ids)
        else:
            q = q.eq("leido", False)
        q.execute()
        return True
    except Exception:
        return False
