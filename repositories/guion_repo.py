"""
Repositorio del GUIÓN DE CALIFICACIÓN del CRM (Fase B).

ADITIVO y NO invasivo (condición dura del proyecto):
- Define las PREGUNTAS que el admin configura → tabla NUEVA `crm_preguntas`.
- Guarda las RESPUESTAS del ejecutivo en el propio cliente → columna jsonb NUEVA
  `clientes.calificacion` (un snapshot {pregunta_id: valor} con lo último que se
  sabe del cliente). La historia de la llamada queda además en `crm_actividad`.

Todo por service key (server-side) → la RLS de las tablas no bloquea. LECTURAS
Y ESCRITURAS DEFENSIVAS: si la tabla/columna no existe todavía (SQL no corrido),
devuelven []/{}/(False, err) y el resto del CRM sigue funcionando igual.
"""
import uuid
import json
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa

_TZ_CL = timezone(timedelta(hours=-3))   # mismo criterio que el resto del sistema

# Tipos de campo soportados por una pregunta del guión.
TIPOS_CAMPO = ("texto", "numero", "opciones", "si_no")


def _ahora() -> str:
    return datetime.now(_TZ_CL).isoformat()


def _parse_opciones(op):
    """Normaliza el campo `opciones` a lista de strings (viene jsonb o texto)."""
    if isinstance(op, list):
        return [str(o) for o in op]
    if isinstance(op, str):
        try:
            v = json.loads(op)
            return [str(o) for o in v] if isinstance(v, list) else []
        except Exception:
            return []
    return []


# ── Preguntas (definición del guión, configurable por el admin) ────────────────

def listar_preguntas(solo_activas: bool = True) -> list:
    """Preguntas del guión, ordenadas por `orden`. DEFENSIVO: [] si la tabla no
    existe todavía."""
    try:
        q = _supa.table("crm_preguntas").select("*")
        if solo_activas:
            q = q.eq("activa", True)
        rows = q.order("orden").order("fecha_creacion").execute().data or []
    except Exception:
        return []
    for r in rows:
        r["opciones"] = _parse_opciones(r.get("opciones"))
    return rows


def crear_pregunta(texto, tipo_campo="texto", opciones=None, orden=None) -> tuple:
    """Crea una pregunta. `orden` por defecto = última + 1. Devuelve (id, err)."""
    try:
        if orden is None:
            existentes = listar_preguntas(solo_activas=False)
            orden = max([int(p.get("orden") or 0) for p in existentes], default=0) + 1
        pid = str(uuid.uuid4())
        _supa.table("crm_preguntas").insert({
            "id": pid,
            "texto": str(texto or "").strip(),
            "tipo_campo": tipo_campo if tipo_campo in TIPOS_CAMPO else "texto",
            "opciones": list(opciones or []),
            "orden": int(orden),
            "activa": True,
            "fecha_creacion": _ahora(),
        }).execute()
        return pid, None
    except Exception as e:
        return None, str(e)


def actualizar_pregunta(pid, campos: dict) -> tuple:
    """Actualiza una pregunta. Devuelve (ok, err)."""
    try:
        campos = dict(campos)
        if "opciones" in campos:
            campos["opciones"] = list(campos["opciones"] or [])
        _supa.table("crm_preguntas").update(campos).eq("id", pid).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def eliminar_pregunta(pid) -> tuple:
    """Baja LÓGICA (activa=false): así las respuestas ya capturadas en clientes no
    quedan huérfanas ni se pierden. Devuelve (ok, err)."""
    return actualizar_pregunta(pid, {"activa": False})


# ── Respuestas (calificación guardada EN el cliente) ───────────────────────────

def obtener_calificacion(cliente_id) -> dict:
    """Snapshot {pregunta_id: valor} guardado en el cliente. {} si no hay/columna
    no existe."""
    try:
        r = _supa.table("clientes").select("calificacion").eq("id", cliente_id).limit(1).execute()
        if r.data:
            v = r.data[0].get("calificacion") or {}
            if isinstance(v, str):
                try:
                    v = json.loads(v)
                except Exception:
                    v = {}
            return v if isinstance(v, dict) else {}
    except Exception:
        pass
    return {}


def guardar_calificacion(cliente_id, valores: dict) -> tuple:
    """Fusiona `valores` ({pregunta_id: valor}) sobre la calificación actual del
    cliente y la persiste en `clientes.calificacion`. Devuelve (ok, dict_final) en
    éxito o (False, err_str) si falla (p.ej. la columna aún no existe)."""
    try:
        actual = obtener_calificacion(cliente_id)
        actual.update({str(k): v for k, v in (valores or {}).items()})
        _supa.table("clientes").update({
            "calificacion": actual,
            "fecha_modificacion": _ahora(),
        }).eq("id", cliente_id).execute()
        return True, actual
    except Exception as e:
        return False, str(e)
