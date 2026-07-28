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


def _rut_placeholder(rk: str) -> bool:
    """True si el RUT normalizado NO es un RUT real (vacío, de puros ceros, o
    demasiado corto). En los presupuestos de prueba/relleno el RUT quedó como
    00.000.000-0 → NO puede tratarse como identidad (fusionaría personas
    distintas). Un RUT chileno real normalizado tiene 7+ caracteres."""
    if not rk:
        return True
    core = rk[:-1] if rk[-1] == "k" else rk   # separa dígito verificador 'k'
    if not core or set(core) == {"0"}:
        return True
    if len(rk) < 7:
        return True
    return False


def _polluted_from_rows(rows: list) -> set:
    """Detecta valores de identidad COMPARTIDOS (placeholders) analizando el
    dataset: un RUT/correo/teléfono asociado a 2+ NOMBRES distintos NO es una
    identidad real (p.ej. el correo de la empresa equipo…@gmail.com usado en
    muchos presupuestos, o un RUT de relleno). Esos valores se marcan como
    'contaminados' y dejan de servir para fusionar → cada nombre queda como
    cliente distinto. Devuelve un set de claves (tipo, valor) a excluir.

    `rows` son filas de cotizaciones con cliente_nombre/rut/email/telefono."""
    from collections import defaultdict
    m = {"rut": defaultdict(set), "email": defaultdict(set), "tel": defaultdict(set)}
    for row in rows:
        nm = _n(row.get("cliente_nombre"))
        if not nm:
            continue
        rk = _norm_rut(row.get("cliente_rut"))
        if rk and not _rut_placeholder(rk):
            m["rut"][rk].add(nm)
        ek = _n(row.get("cliente_email"))
        if ek and "@" in ek:
            m["email"][ek].add(nm)
        tk = _norm_tel(row.get("cliente_telefono"))
        if tk:
            m["tel"][tk].add(nm)
    polluted = set()
    for kind, mp in m.items():
        for val, nombres in mp.items():
            if len(nombres) >= 2:
                polluted.add((kind, val))
    return polluted


def dedup_key(rut, email, telefono, nombre="", polluted=None) -> tuple:
    """Clave de identidad para deduplicar, por prioridad RUT > email > teléfono >
    nombre. Un valor se SALTA si es placeholder (RUT de ceros) o está 'contaminado'
    (compartido por varias personas — ver _polluted_from_rows) → así no se fusionan
    clientes distintos que comparten un correo/RUT de relleno. Devuelve (tipo,
    valor) o ('', '') si no hay nada usable."""
    polluted = polluted or ()
    rk = _norm_rut(rut)
    if rk and not _rut_placeholder(rk) and ("rut", rk) not in polluted:
        return ("rut", rk)
    ek = _n(email)
    if ek and "@" in ek and ("email", ek) not in polluted:
        return ("email", ek)
    tk = _norm_tel(telefono)
    if tk and ("tel", tk) not in polluted:
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
    cot_rows = _leer_clientes_de_cotizaciones()
    # Valores de identidad compartidos (correo/RUT de relleno) → no fusionan.
    polluted = _polluted_from_rows(cot_rows)

    # 1) Índice de lo que YA existe en el maestro, por clave de dedup.
    idx = set()
    for c in listar_clientes(solo_activos=False):
        k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), polluted)
        if k[1]:
            idx.add(k)

    # 2) Recorrer cotizaciones y juntar candidatos nuevos (uno por clave).
    nuevos: dict = {}   # clave -> payload
    omitidos = 0
    for row in cot_rows:
        nombre = str(row.get("cliente_nombre") or "").strip()
        rut = row.get("cliente_rut")
        email = row.get("cliente_email")
        tel = row.get("cliente_telefono")
        k = dedup_key(rut, email, tel, nombre, polluted)
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


# Campos de cliente que acepta la importación (llave interna -> se guarda tal cual).
CAMPOS_IMPORT = ("nombre", "rut", "email", "telefono", "direccion", "comuna",
                 "region", "empresa", "rut_empresa")


def importar_leads(rows: list, origen: str = "Importado",
                   asignado_email: str = "", asignado_nombre: str = "") -> dict:
    """Importa leads desde filas ya MAPEADAS (cada fila = dict con llaves de
    CAMPOS_IMPORT). Deduplica con el MISMO criterio del backfill (RUT>email>tel>
    nombre, ignorando rellenos) contra el maestro existente y dentro del mismo
    archivo. Los nuevos quedan origen='Importado', etapa 'lead_nuevo' (caen en la
    Bandeja) y opcionalmente asignados. Devuelve {creados, duplicados, omitidos}.

    ADITIVO: solo INSERTA en `clientes` (+ actividad); nunca toca lo existente."""
    polluted = identidades_compartidas()

    idx = set()
    for c in listar_clientes(solo_activos=False):
        k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), polluted)
        if k[1]:
            idx.add(k)

    nuevos: dict = {}
    duplicados = 0
    omitidos = 0
    for row in rows:
        nombre = str(row.get("nombre") or "").strip()
        if not nombre:
            omitidos += 1
            continue
        k = dedup_key(row.get("rut"), row.get("email"), row.get("telefono"), nombre, polluted)
        if not k[1]:
            k = ("nombre", _n(nombre))   # sin clave fuerte → dedup por nombre
        if k in idx or k in nuevos:
            duplicados += 1
            continue
        payload = {
            "id": str(uuid.uuid4()),
            "nombre": nombre,
            "tipo": "natural",
            "origen": origen or "Importado",
            "asignado_email": str(asignado_email or "").strip(),
            "asignado_nombre": str(asignado_nombre or "").strip(),
            "etapa_manual": "lead_nuevo",
            "activo": True,
        }
        for _f in CAMPOS_IMPORT:
            if _f != "nombre":
                payload[_f] = str(row.get(_f) or "").strip()
        nuevos[k] = payload

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
                "titulo": "Lead importado desde archivo",
                "detalle": origen or "Importado",
                "ep": "",
                "actor": "import",
                "fecha": now,
            } for it in lote]).execute()
            creados += len(lote)
        except Exception:
            omitidos += len(lote)

    return {"creados": creados, "duplicados": duplicados, "omitidos": omitidos}


# ── Sincronización cliente CRM ↔ cotizaciones (datos de contacto) ─────────────
# Mapeo campo CRM (clientes) -> campo en cotizaciones. SOLO datos de contacto:
# nunca montos, productos ni estado.
_CRM_A_COT = {
    "nombre": "cliente_nombre", "rut": "cliente_rut", "email": "cliente_email",
    "telefono": "cliente_telefono", "direccion": "cliente_direccion",
    "comuna": "cliente_comuna", "region": "cliente_region", "tipo": "cliente_tipo",
    "empresa": "cliente_empresa", "rut_empresa": "cliente_rut_empresa",
}


def propagar_a_cotizaciones(old_rut, old_email, old_tel, old_nombre, campos: dict) -> int:
    """Propaga los datos de contacto editados en la ficha del CRM a TODAS las
    cotizaciones de ese cliente (identificado por su dedup key ANTERIOR, así sigue
    matcheando aunque se corrija el RUT/correo). SOLO escribe campos NO vacíos (para
    no borrar datos con blancos) y SOLO de contacto. best-effort → devuelve cuántas
    cotizaciones actualizó."""
    try:
        rows = _leer_clientes_de_cotizaciones()
        polluted = _polluted_from_rows(rows)
        target = dedup_key(old_rut, old_email, old_tel, old_nombre, polluted)
        if not target[1]:
            return 0
        payload = {}
        for k, v in (campos or {}).items():
            col = _CRM_A_COT.get(k)
            if col and str(v or "").strip():
                payload[col] = str(v).strip()
        if not payload:
            return 0
        n = 0
        for row in rows:
            k = dedup_key(row.get("cliente_rut"), row.get("cliente_email"),
                          row.get("cliente_telefono"), row.get("cliente_nombre"), polluted)
            if k == target and row.get("numero"):
                try:
                    _supa.table("cotizaciones").update(payload).eq("numero", row["numero"]).execute()
                    n += 1
                except Exception:
                    pass
        return n
    except Exception:
        return 0


def upsert_desde_cotizacion(cli_fields: dict, asesor_fields: dict = None) -> None:
    """Mantiene el CRM al día tras guardar un presupuesto (dirección inversa): si el
    cliente ya existe (por dedup key) actualiza sus datos de contacto NO vacíos; si
    no existe, lo crea (origen Manual, etapa contactado). best-effort: NUNCA lanza
    (no puede romper el guardado del presupuesto)."""
    try:
        nombre = str(cli_fields.get("nombre") or "").strip()
        if not nombre:
            return
        polluted = _polluted_from_rows(_leer_cotizaciones_para_pipeline())
        target = dedup_key(cli_fields.get("rut"), cli_fields.get("email"),
                           cli_fields.get("telefono"), nombre, polluted)
        # Campos de contacto (no vacíos, para no pisar con blancos).
        campos = {}
        for k in ("nombre", "rut", "email", "telefono", "direccion", "comuna",
                  "region", "tipo", "empresa", "rut_empresa"):
            v = str(cli_fields.get(k) or "").strip()
            if v:
                campos[k] = v
        campos["nombre"] = nombre
        match = None
        for c in listar_clientes(solo_activos=False):
            k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), polluted)
            if k[1] and k == target:
                match = c
                break
        if match:
            actualizar_cliente(match["id"], campos)
        else:
            payload = dict(campos)
            payload.setdefault("tipo", "natural")
            payload["origen"] = "Manual"
            payload["etapa_manual"] = "contactado"
            if asesor_fields:
                payload["asignado_email"] = str(asesor_fields.get("email") or "").strip()
                payload["asignado_nombre"] = str(asesor_fields.get("nombre") or "").strip()
            crear_cliente(payload)
    except Exception:
        pass


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


def identidades_compartidas() -> set:
    """Set de identidades compartidas (correo/RUT/teléfono de relleno usados por
    varias personas) de las cotizaciones actuales, para que la dedup del alta
    manual use el MISMO criterio que el backfill/pipeline. Ver _polluted_from_rows."""
    return _polluted_from_rows(_leer_cotizaciones_para_pipeline())


def pipeline_por_dedupkey(rows=None, polluted=None) -> dict:
    """{dedup_key: {stage, cotizaciones:[{numero,total,estado,stage,fecha}], monto}}
    derivado de las cotizaciones. `stage` = la etapa MÁS AVANZADA entre las
    cotizaciones del cliente; `monto` = total de esa cotización representativa.
    `polluted` = valores de identidad compartidos a excluir (ver
    _polluted_from_rows); si no se pasa, se calcula de las filas."""
    rows = rows if rows is not None else _leer_cotizaciones_para_pipeline()
    polluted = polluted if polluted is not None else _polluted_from_rows(rows)
    out: dict = {}
    for row in rows:
        k = dedup_key(row.get("cliente_rut"), row.get("cliente_email"),
                      row.get("cliente_telefono"), row.get("cliente_nombre"), polluted)
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


# ── Tareas / recordatorios (crm_tareas) ───────────────────────────────────────

def crear_tarea(cliente_id, titulo, vence, asignado_email="", tipo="tarea") -> tuple:
    """Crea una actividad/recordatorio. `vence` = ISO string (timestamptz), `tipo`
    = llamada|reunion|correo|tarea. Devuelve (id, err). DEFENSIVO: si la columna
    `tipo` no existe todavía (ALTER no corrido), reintenta sin ella."""
    tid = str(uuid.uuid4())
    base = {
        "id": tid,
        "cliente_id": cliente_id,
        "titulo": str(titulo or "").strip(),
        "vence": vence,
        "hecho": False,
        "asignado_email": str(asignado_email or "").strip(),
        "fecha_creacion": _ahora(),
    }
    try:
        _supa.table("crm_tareas").insert({**base, "tipo": tipo}).execute()
        return tid, None
    except Exception:
        try:
            _supa.table("crm_tareas").insert(base).execute()   # sin columna tipo aún
            return tid, None
        except Exception as e:
            return None, str(e)


def listar_tareas_cliente(cliente_id) -> list:
    """Tareas de un cliente: pendientes primero, luego por fecha de vencimiento."""
    try:
        return (_supa.table("crm_tareas").select("*").eq("cliente_id", cliente_id)
                .order("hecho").order("vence").execute().data or [])
    except Exception:
        return []


def completar_tarea(tid, hecho=True, resultado=None) -> tuple:
    """Marca una actividad como hecha (o la reabre) y, opcionalmente, guarda el
    `resultado` (contesto|no_contesto|no_interesado). DEFENSIVO: si la columna
    `resultado` no existe todavía, reintenta solo con `hecho`."""
    upd = {"hecho": bool(hecho)}
    if resultado is not None:
        upd["resultado"] = resultado
    try:
        _supa.table("crm_tareas").update(upd).eq("id", tid).execute()
        return True, None
    except Exception:
        try:
            _supa.table("crm_tareas").update({"hecho": bool(hecho)}).eq("id", tid).execute()
            return True, None
        except Exception as e:
            return False, str(e)


def listar_tareas_pendientes() -> list:
    """Todas las tareas sin completar, por vencimiento."""
    try:
        return (_supa.table("crm_tareas").select("*").eq("hecho", False)
                .order("vence").execute().data or [])
    except Exception:
        return []


def tareas_vencidas_no_notificadas() -> list:
    """Tareas vence<=ahora, hecho=false y notificado=false (para la alerta
    Telegram de 'vencido'). DEFENSIVO: si la columna `notificado` no existe aún,
    devuelve [] (las alertas de vencimiento quedan deshabilitadas hasta correr el
    ALTER TABLE) — el resto del sistema de recordatorios funciona igual."""
    try:
        return (_supa.table("crm_tareas").select("*")
                .eq("hecho", False).eq("notificado", False)
                .lte("vence", _ahora()).order("vence").execute().data or [])
    except Exception:
        return []


def marcar_notificadas(ids: list) -> None:
    """Marca tareas como ya notificadas (best effort)."""
    if not ids:
        return
    try:
        _supa.table("crm_tareas").update({"notificado": True}).in_("id", ids).execute()
    except Exception:
        pass


def enriquecer_con_pipeline(clientes: list) -> list:
    """Agrega a cada cliente (en memoria, no en BD) los campos DERIVADOS:
    `_stage`, `_cotizaciones` (lista) y `_monto`. Si el cliente no tiene ninguna
    cotización, cae a su `etapa_manual` (lead_nuevo / contactado)."""
    rows = _leer_cotizaciones_para_pipeline()
    polluted = _polluted_from_rows(rows)   # MISMO set para cliente y cotizaciones
    pipe = pipeline_por_dedupkey(rows, polluted)
    for c in clientes:
        k = dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre"), polluted)
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
