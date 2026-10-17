"""
Estado de gestión de cada POSTULANTE (tabla `postulaciones_estado`), independiente de Shopify
(que guarda los datos del postulante). Una fila por postulante (customer_id de Shopify) con:
estado del proceso, clasificación (estrellas 0-5) y nota interna del reclutador.

Las LECTURAS son DEFENSIVAS (si la tabla no existe todavía → {} / dict vacío) para no tumbar la
pestaña POSTULACIONES. Escrituras con service key.

SQL para crear la tabla (correr una vez en Supabase → SQL Editor):

    create table if not exists postulaciones_estado (
      customer_id     text primary key,
      estado          text default 'nuevo',
      clasificacion   int  default 0,
      nota            text default '',
      actualizado_por text,
      actualizado_en  timestamptz default now()
    );
"""
from config.supabase import supabase_admin as _supa

ESTADOS = ("nuevo", "revisado", "contactado", "descartado")


def listar_estados() -> dict:
    """{customer_id(str): {estado, clasificacion, nota, ...}} de todos los postulantes. Defensivo."""
    try:
        rows = _supa.table("postulaciones_estado").select("*").execute().data or []
        return {str(r.get("customer_id")): r for r in rows}
    except Exception:
        return {}


def guardar_estado(customer_id, estado="nuevo", clasificacion=0, nota="", actor="") -> bool:
    """Crea/actualiza (upsert) el estado de gestión de un postulante. Devuelve True si OK."""
    _cid = str(customer_id or "").strip()
    if not _cid:
        return False
    _est = str(estado or "nuevo").strip().lower()
    if _est not in ESTADOS:
        _est = "nuevo"
    try:
        _cl = int(clasificacion or 0)
    except Exception:
        _cl = 0
    _cl = max(0, min(5, _cl))
    try:
        _supa.table("postulaciones_estado").upsert({
            "customer_id": _cid, "estado": _est, "clasificacion": _cl,
            "nota": str(nota or "")[:2000], "actualizado_por": str(actor or "")[:200],
            "actualizado_en": "now()",
        }, on_conflict="customer_id").execute()
        return True
    except Exception:
        return False


def eliminar_estado(customer_id) -> bool:
    """Borra la fila de estado de un postulante (al eliminarlo). Defensivo."""
    _cid = str(customer_id or "").strip()
    if not _cid:
        return False
    try:
        _supa.table("postulaciones_estado").delete().eq("customer_id", _cid).execute()
        return True
    except Exception:
        return False
