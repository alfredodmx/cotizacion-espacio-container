"""
Repositorio de CLIENTES (CRM) — maestro de clientes.

DISEÑO ADITIVO Y NO INVASIVO (condición dura del proyecto):
- Solo LEE `cotizaciones` (para el backfill / derivar estado) y ESCRIBE en las
  tablas NUEVAS `clientes`, `crm_actividad`, `crm_tareas`.
- NUNCA modifica cotizaciones ni el flujo de presupuestos. El backfill es de
  SOLO LECTURA sobre cotizaciones: si el CRM fallara, el resto ni se entera.
- `cotizaciones` es la fuente de verdad: acá se guarda solo la CAPA CRM
  (asignado, etapa_manual, notas, origen, consentimiento) + identidad. Los datos
  vivos (montos, EP, estado) se leen frescos de cotizaciones al mostrar.

Todas las escrituras van por la service key (`supabase_admin`), server-side, así
que la RLS de las tablas (activada, sin políticas públicas) no bloquea.
"""
import uuid
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa
from services.cotizacion_service import calcular_estado_label

_TABLA = "clientes"
_TZ_CL = timezone(timedelta(hours=-3))  # mismo criterio que el resto del sistema


def _ahora() -> str:
    return datetime.now(_TZ_CL).isoformat()


def _n(s) -> str:
    """Normaliza texto: trim + minúsculas + espacios colapsados."""
    return " ".join(str(s or "").strip().lower().split())


def _norm_rut(r) -> str:
    """RUT sin puntos/guion/espacios, en minúscula (para comparar 16.842.113-4
    con 16842113-4)."""
    return "".join(ch for ch in str(r or "").lower() if ch.isalnum())


def _norm_tel(t) -> str:
    """Últimos 9 dígitos del teléfono (evita que +56 9 … vs 9 … se vean distintos)."""
    dig = "".join(ch for ch in str(t or "") if ch.isdigit())
    return dig[-9:] if len(dig) >= 8 else ""


def dedup_key(rut, email, telefono, nombre="") -> tuple:
    """Clave de identidad para deduplicar, por prioridad RUT > email > teléfono.
    Si no hay ninguno utilizable, cae a nombre normalizado (clave débil). Devuelve
    (tipo, valor) o ('', '') si no hay nada."""
    rk = _norm_rut(rut)
    if rk and rk != "nan":
        return ("rut", rk)
    ek = _n(email)
    if ek and "@" in ek:
        return ("email", ek)
    tk = _norm_tel(telefono)
    if tk:
        return ("tel", tk)
    nk = _n(nombre)
    if nk and nk != "nan":
        return ("nombre", nk)
    return ("", "")


# ── Lectura / CRUD del maestro ────────────────────────────────────────────────

def listar_clientes(solo_activos: bool = True) -> list:
    """Clientes del maestro, más reciente primero."""
    try:
        q = _supa.table(_TABLA).select("*")
        if solo_activos:
            q = q.eq("activo", True)
        return q.order("fecha_modificacion", desc=True).execute().data or []
    except Exception:
        return []


def obtener_cliente(cid: str) -> dict | None:
    try:
        r = _supa.table(_TABLA).select("*").eq("id", cid).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def crear_cliente(campos: dict) -> tuple:
    """Inserta un cliente en el maestro. Devuelve (id, error)."""
    try:
        cid = str(uuid.uuid4())
        now = _ahora()
        payload = dict(campos)
        payload.update(id=cid, fecha_creacion=now, fecha_modificacion=now)
        payload.setdefault("activo", True)
        payload.setdefault("origen", "Manual")
        _supa.table(_TABLA).insert(payload).execute()
        return cid, None
    except Exception as e:
        return None, str(e)


def actualizar_cliente(cid: str, campos: dict) -> tuple:
    """Actualiza campos del cliente. Devuelve (ok, error)."""
    try:
        campos = dict(campos)
        campos["fecha_modificacion"] = _ahora()
        _supa.table(_TABLA).update(campos).eq("id", cid).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ── Actividad (línea de tiempo) ───────────────────────────────────────────────

def registrar_actividad(cliente_id, tipo, titulo, detalle="", ep="", actor="") -> None:
    """Registra un evento en la línea de tiempo del cliente. Nunca lanza (best
    effort): un fallo acá no debe cortar la acción principal."""
    try:
        _supa.table("crm_actividad").insert({
            "id": str(uuid.uuid4()),
            "cliente_id": cliente_id,
            "tipo": str(tipo or ""),
            "titulo": str(titulo or ""),
            "detalle": str(detalle or ""),
            "ep": str(ep or ""),
            "actor": str(actor or ""),
            "fecha": _ahora(),
        }).execute()
    except Exception:
        pass


def listar_actividad(cliente_id: str) -> list:
    """Eventos del cliente, más reciente primero."""
    try:
        return (_supa.table("crm_actividad").select("*")
                .eq("cliente_id", cliente_id)
                .order("fecha", desc=True).execute().data or [])
    except Exception:
        return []


# ── Backfill SOLO LECTURA desde cotizaciones ──────────────────────────────────
# Campos de cliente que viven copiados en cada fila de `cotizaciones` (la app aún
# no tiene maestro). Se leen; NUNCA se escriben.
_COLS_COT = (
    "numero,cliente_nombre,cliente_rut,cliente_email,cliente_telefono,"
    "cliente_tipo,cliente_empresa,cliente_rut_empresa,cliente_direccion,"
    "cliente_comuna,cliente_region,asesor_nombre,asesor_email,fecha_creacion"
)


def _leer_clientes_de_cotizaciones() -> list:
    """SOLO LECTURA sobre cotizaciones. Devuelve las filas con los campos de
    cliente (sin traer los `productos`, que son pesados)."""
    try:
        return _supa.table("cotizaciones").select(_COLS_COT).execute().data or []
    except Exception:
        return []


def backfill_desde_cotizaciones() -> dict:
    """Crea fichas en `clientes` para cada cliente real hallado en cotizaciones,
    deduplicando por RUT > email > teléfono > nombre. IDEMPOTENTE: los que ya
    existen (por clave de dedup) no se vuelven a crear. SOLO LECTURA sobre
    cotizaciones. Devuelve {creados, existentes, omitidos}.

    Los importados quedan origen='Manual' y etapa_manual='contactado' (ya tienen
    presupuesto → no son leads nuevos). El asesor de la cotización queda como
    asignado."""
    # 1) Índice de lo que YA existe en el maestro, por clave de dedup.
    idx = set()
    for c in listar_clientes(solo_activos=False):
        k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"))
        if k[1]:
            idx.add(k)

    # 2) Recorrer cotizaciones y juntar candidatos nuevos (uno por clave).
    nuevos: dict = {}   # clave -> payload
    omitidos = 0
    for row in _leer_clientes_de_cotizaciones():
        nombre = str(row.get("cliente_nombre") or "").strip()
        rut = row.get("cliente_rut")
        email = row.get("cliente_email")
        tel = row.get("cliente_telefono")
        k = dedup_key(rut, email, tel, nombre)
        if not k[1]:
            omitidos += 1
            continue
        if k in idx or k in nuevos:
            continue
        nuevos[k] = {
            "id": str(uuid.uuid4()),
            "nombre": nombre or (str(email or "").strip() or "Sin nombre"),
            "rut": str(rut or "").strip(),
            "email": str(email or "").strip(),
            "telefono": str(tel or "").strip(),
            "tipo": (str(row.get("cliente_tipo") or "natural").strip() or "natural"),
            "empresa": str(row.get("cliente_empresa") or "").strip(),
            "rut_empresa": str(row.get("cliente_rut_empresa") or "").strip(),
            "direccion": str(row.get("cliente_direccion") or "").strip(),
            "comuna": str(row.get("cliente_comuna") or "").strip(),
            "region": str(row.get("cliente_region") or "").strip(),
            "origen": "Manual",
            "asignado_email": str(row.get("asesor_email") or "").strip(),
            "asignado_nombre": str(row.get("asesor_nombre") or "").strip(),
            "etapa_manual": "contactado",
            "activo": True,
        }

    # 3) Insertar en lotes (idempotente). La actividad se registra por lote también.
    creados = 0
    now = _ahora()
    items = list(nuevos.values())
    for i in range(0, len(items), 200):
        lote = items[i:i + 200]
        for it in lote:
            it["fecha_creacion"] = now
            it["fecha_modificacion"] = now
        try:
            _supa.table(_TABLA).insert(lote).execute()
            _supa.table("crm_actividad").insert([{
                "id": str(uuid.uuid4()),
                "cliente_id": it["id"],
                "tipo": "lead",
                "titulo": "Cliente importado desde cotizaciones",
                "detalle": "",
                "ep": "",
                "actor": "backfill",
                "fecha": now,
            } for it in lote]).execute()
            creados += len(lote)
        except Exception:
            # Un lote que falle no debe abortar el resto.
            omitidos += len(lote)

    return {"creados": creados, "existentes": len(idx), "omitidos": omitidos}


# ── Derivación del PIPELINE (SOLO LECTURA de cotizaciones) ─────────────────────
# La etapa "en presupuesto / propuesta / ganado / perdido" NO se guarda: se DERIVA
# del estado de las cotizaciones del cliente (misma fuente de verdad que la tabla
# COTIZACIONES). Solo las etapas tempranas (lead_nuevo / contactado) viven en
# clientes.etapa_manual. Así nadie mantiene estados a mano y nunca hay dos
# versiones del mismo dato.

# Columnas de cotizaciones necesarias para derivar el estado (mismas que usa
# calcular_estado_label) + total + identidad del cliente. SOLO LECTURA.
_COLS_PIPE = (
    "numero,cliente_nombre,cliente_rut,cliente_email,cliente_telefono,"
    "asesor_nombre,asesor_email,asesor_telefono,config_margen,plano_url,"
    "contrato_notariado_url,acta_url,motivo_rechazo,total_total,fecha_creacion"
)

# Etapas del pipeline (orden y rango para elegir la "más avanzada" cuando un
# cliente tiene varias cotizaciones).
STAGE_LEAD = "lead_nuevo"
STAGE_CONTACTADO = "contactado"
STAGE_PRESUPUESTO = "en_presupuesto"
STAGE_PROPUESTA = "propuesta_enviada"
STAGE_GANADO = "ganado"
STAGE_PERDIDO = "perdido"

_STAGE_RANK = {STAGE_PERDIDO: 1, STAGE_PRESUPUESTO: 3, STAGE_PROPUESTA: 4, STAGE_GANADO: 5}


def _estado_a_stage(label: str) -> str:
    """Mapea el estado de una cotización (calcular_estado_label) a etapa de pipeline."""
    if label in ("PROYECTO TERMINADO", "ADJUDICADO"):
        return STAGE_GANADO
    if str(label).startswith("AUTORIZADO"):
        return STAGE_PROPUESTA
    if label == "RECHAZADO":
        return STAGE_PERDIDO
    return STAGE_PRESUPUESTO   # BORRADOR / INCOMPLETO (con o sin plano)


def _leer_cotizaciones_para_pipeline() -> list:
    """SOLO LECTURA sobre cotizaciones (sin traer los `productos`, pesados)."""
    try:
        return _supa.table("cotizaciones").select(_COLS_PIPE).execute().data or []
    except Exception:
        return []


def pipeline_por_dedupkey() -> dict:
    """{dedup_key: {stage, cotizaciones:[{numero,total,estado,stage,fecha}], monto}}
    derivado de las cotizaciones. `stage` = la etapa MÁS AVANZADA entre las
    cotizaciones del cliente; `monto` = total de esa cotización representativa."""
    out: dict = {}
    for row in _leer_cotizaciones_para_pipeline():
        k = dedup_key(row.get("cliente_rut"), row.get("cliente_email"),
                      row.get("cliente_telefono"), row.get("cliente_nombre"))
        if not k[1]:
            continue
        try:
            _mg = float(row.get("config_margen") or 0)
        except (TypeError, ValueError):
            _mg = 0.0
        label = calcular_estado_label(
            row.get("cliente_nombre"), row.get("cliente_email"),
            row.get("asesor_nombre"), row.get("asesor_email"), row.get("asesor_telefono"),
            _mg, bool(row.get("plano_url")),
            tiene_notariado=bool(row.get("contrato_notariado_url")),
            tiene_acta=bool(row.get("acta_url")),
            motivo_rechazo=row.get("motivo_rechazo") or "")
        stage = _estado_a_stage(label)
        try:
            total = float(row.get("total_total") or 0)
        except (TypeError, ValueError):
            total = 0.0
        e = out.setdefault(k, {"stage": None, "cotizaciones": [], "monto": 0.0})
        e["cotizaciones"].append({
            "numero": row.get("numero"), "total": total, "estado": label,
            "stage": stage, "fecha": row.get("fecha_creacion"),
        })
        if e["stage"] is None or _STAGE_RANK.get(stage, 0) > _STAGE_RANK.get(e["stage"], 0):
            e["stage"] = stage
            e["monto"] = total
    return out


def enriquecer_con_pipeline(clientes: list) -> list:
    """Agrega a cada cliente (en memoria, no en BD) los campos DERIVADOS:
    `_stage`, `_cotizaciones` (lista) y `_monto`. Si el cliente no tiene ninguna
    cotización, cae a su `etapa_manual` (lead_nuevo / contactado)."""
    pipe = pipeline_por_dedupkey()
    for c in clientes:
        k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"))
        info = pipe.get(k)
        if info and info["stage"]:
            c["_stage"] = info["stage"]
            c["_cotizaciones"] = sorted(info["cotizaciones"],
                                        key=lambda x: str(x.get("fecha") or ""), reverse=True)
            c["_monto"] = info["monto"]
        else:
            c["_stage"] = c.get("etapa_manual") or STAGE_LEAD
            c["_cotizaciones"] = []
            c["_monto"] = 0.0
    return clientes
