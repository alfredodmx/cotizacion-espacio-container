"""
Repositorio de INVENTARIO — maestro de stock propio.

Tabla Supabase `inventario`. La lista de **categoría → ítem** proviene de la
última Excel activa (hoja 'BD Total'), la MISMA fuente que usa el formulario de
REGISTRO DE COMPRA (views/tab_operaciones.py) — NO del catálogo del cliente.

Todas las escrituras van por la service key (`supabase_admin`), server-side, así
que RLS no bloquea. Las fotos (hasta 5) se suben al bucket
`formulario-imagenes/inventario/`, mismo bucket que avatares y catálogo.
"""
import time
import uuid
import mimetypes
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa
from utils.excel_manager import leer_hoja_excel

_TABLA = "inventario"
_BUCKET = "formulario-imagenes"
_FOTO_DIR = "inventario"
MAX_FOTOS = 5

# Hora de Chile (UTC-3) — mismo criterio que utils/operaciones.py y backup_db.py.
_TZ_CL = timezone(timedelta(hours=-3))


def _ahora() -> str:
    return datetime.now(_TZ_CL).isoformat()

# Unidades de medida disponibles para el stock.
UNIDADES = [
    "unidades", "m²", "metros", "ml (metro lineal)", "kg",
    "litros", "planchas", "rollos", "cajas", "sacos", "pares", "global",
]


def fetch_categorias_items() -> dict:
    """{categoria: [{item, precio}]} desde la hoja 'BD Total' de la Excel activa.

    Misma lógica que el formulario de REGISTRO DE COMPRA: columnas
    'Categorias'/'Categoria', 'Item' y 'P. Unitario real'/'Precio Unitario'.
    Se ignoran filas sin categoría o sin ítem y los ítems duplicados por
    categoría. Devuelve {} si no hay Excel o falla la lectura.
    """
    try:
        df = leer_hoja_excel("BD Total")
        out: dict = {}
        for _, row in df.iterrows():
            cat = str(row.get("Categorias", row.get("Categoria", ""))).strip()
            item = str(row.get("Item", "")).strip()
            if not cat or not item or cat.lower() == "nan" or item.lower() == "nan":
                continue
            try:
                precio = round(float(row.get("P. Unitario real",
                                              row.get("Precio Unitario", 0)) or 0))
            except (TypeError, ValueError):
                precio = 0
            lst = out.setdefault(cat, [])
            if not any(x["item"] == item for x in lst):
                lst.append({"item": item, "precio": precio})
        return dict(sorted(out.items(), key=lambda kv: kv[0].lower()))
    except Exception:
        return {}


def _subir_fotos(files, rec_id: str) -> tuple[list, str | None]:
    """Sube hasta MAX_FOTOS archivos al bucket. `files` son UploadedFile de
    Streamlit (tienen .getvalue()/.name/.type). Devuelve (urls, error)."""
    urls: list = []
    if not files:
        return urls, None
    try:
        store = _supa.storage.from_(_BUCKET)
        for i, f in enumerate(files[:MAX_FOTOS]):
            data = f.getvalue() if hasattr(f, "getvalue") else (
                f.read() if hasattr(f, "read") else f)
            name = getattr(f, "name", f"foto{i}.jpg")
            ext = (name.rsplit(".", 1)[-1] if "." in name else "jpg").lower()
            ext = ext.replace("jpeg", "jpg")
            mime = (getattr(f, "type", None)
                    or mimetypes.guess_type(name)[0] or "image/jpeg")
            path = f"{_FOTO_DIR}/{rec_id}_{int(time.time())}_{i}.{ext}"
            store.upload(path, data, {"content-type": mime, "upsert": "true"})
            url = store.get_public_url(path).split("?")[0]
            urls.append(url)
        return urls, None
    except Exception as e:
        return urls, str(e)


def guardar_inventario(categoria, item, cantidad, unidad, calidad, observacion,
                       files, ubicacion, creado_por_email, creado_por_nombre):
    """Inserta un producto en inventario (fotos primero). Devuelve (id, error).

    Si el INSERT falla → (None, error). Si el INSERT va bien pero alguna foto
    no subió → (id, error_de_fotos) para poder avisar sin perder el registro.
    """
    try:
        rec_id = str(uuid.uuid4())
        fotos_urls, ferr = _subir_fotos(files, rec_id)
        now = _ahora()
        try:
            _cal = int(calidad)
        except (TypeError, ValueError):
            _cal = None
        try:
            _cant = float(cantidad or 0)
        except (TypeError, ValueError):
            _cant = 0.0
        payload = {
            "id": rec_id,
            "categoria": str(categoria or "").strip(),
            "item": str(item or "").strip(),
            "cantidad": _cant,
            "unidad": str(unidad or "unidades").strip(),
            "calidad": _cal,
            "observacion": str(observacion or "").strip(),
            "ubicacion": str(ubicacion or "").strip(),
            "fotos": fotos_urls,
            "creado_por_email": str(creado_por_email or ""),
            "creado_por_nombre": str(creado_por_nombre or ""),
            "actualizado_por": str(creado_por_nombre or creado_por_email or ""),
            "fecha_creacion": now,
            "fecha_modificacion": now,
            "activo": True,
        }
        _supa.table(_TABLA).insert(payload).execute()
        return rec_id, ferr
    except Exception as e:
        return None, str(e)


def listar_inventario(busqueda: str = "") -> list:
    """Inventario activo, más reciente primero. Filtro de texto opcional
    (item, categoría, ubicación, observación)."""
    try:
        data = (_supa.table(_TABLA).select("*").eq("activo", True)
                .order("fecha_modificacion", desc=True).execute().data or [])
        if busqueda:
            b = busqueda.strip().lower()
            data = [d for d in data if b in (
                f"{d.get('item','')} {d.get('categoria','')} "
                f"{d.get('ubicacion','')} {d.get('observacion','')}").lower()]
        return data
    except Exception:
        return []


def obtener_inventario(inv_id: str) -> dict | None:
    """Un registro por id (o None)."""
    try:
        r = _supa.table(_TABLA).select("*").eq("id", inv_id).limit(1).execute()
        return r.data[0] if r.data else None
    except Exception:
        return None


def actualizar_inventario(inv_id, campos: dict, files_nuevas=None,
                          fotos_conservar=None, actor: str = "") -> tuple:
    """Actualiza un registro. Si se pasan `files_nuevas`, se suben y se
    concatenan a `fotos_conservar` (las que el usuario decidió mantener),
    respetando el tope MAX_FOTOS. Devuelve (ok, error)."""
    try:
        campos = dict(campos)
        if files_nuevas is not None or fotos_conservar is not None:
            base = list(fotos_conservar or [])
            libres = max(0, MAX_FOTOS - len(base))
            nuevas, ferr = _subir_fotos((files_nuevas or [])[:libres], inv_id)
            campos["fotos"] = base + nuevas
        else:
            ferr = None
        campos["fecha_modificacion"] = _ahora()
        if actor:
            campos["actualizado_por"] = actor
        _supa.table(_TABLA).update(campos).eq("id", inv_id).execute()
        return True, ferr
    except Exception as e:
        return False, str(e)


def eliminar_inventario(inv_id) -> tuple:
    """Baja LÓGICA (activo=False). No destruye el registro ni las fotos."""
    try:
        _supa.table(_TABLA).update({
            "activo": False,
            "fecha_modificacion": _ahora(),
        }).eq("id", inv_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ── DISPONIBILIDAD / CONSUMO (unión INVENTARIO ↔ REGISTRO DE COMPRAS) ──────────
# El stock de INVENTARIO se "descuenta" cuando REGISTRO DE COMPRAS marca un ítem
# EN STOCK con desde_inventario=true. NO se muta la tabla inventario: el consumo
# se DERIVA de los registros (robusto ante ediciones/borrados). El emparejamiento
# ítem inventario ↔ ítem presupuesto es por (categoría, ítem) normalizado (ambos
# vienen de la misma Excel 'BD Total').
import json as _json


def norm_key(cat, item) -> tuple:
    """Clave normalizada (categoría, ítem): trim + espacios colapsados + minúsculas.
    MISMA normalización que build_rc_html._dnk (split()/join) para que las claves
    coincidan al emparejar inventario ↔ presupuesto."""
    def _n(s):
        return ' '.join(str(s or '').strip().lower().split())
    return (_n(cat), _n(item))


def _consumo_desde_inventario() -> dict:
    """Consumo de stock DESDE INVENTARIO por (cat,item) normalizado, leyendo TODOS
    los registro_compras. Solo cuenta ítems con desde_inventario=true (los de
    prueba, sin el flag, NO cuentan). Devuelve
    {key: {'consumido': N, 'detalle': [{ep, cant, fecha}]}}."""
    out: dict = {}
    try:
        resp = _supa.table("registro_compras").select(
            "cotizacion_numero,items,fecha_registro").execute()
        for reg in (resp.data or []):
            ep = str(reg.get("cotizacion_numero") or "")
            fecha = reg.get("fecha_registro", "")
            items = reg.get("items") or []
            if isinstance(items, str):
                try:
                    items = _json.loads(items)
                except Exception:
                    items = []
            for it in items:
                if not it.get("desde_inventario"):
                    continue
                try:
                    cant = int(float(it.get("stock_cantidad", 0) or 0))
                except (TypeError, ValueError):
                    cant = 0
                if cant <= 0:
                    continue
                k = norm_key(it.get("categoria"), it.get("item"))
                e = out.setdefault(k, {"consumido": 0, "detalle": []})
                e["consumido"] += cant
                e["detalle"].append({"ep": ep, "cant": cant, "fecha": fecha})
    except Exception:
        pass
    return out


def disponibilidad_inventario() -> dict:
    """Disponibilidad de stock por (categoría,ítem) normalizado:
      {key: {agregado, consumido, disponible, cat, item, detalle}}
    · agregado   = Σ cantidad en inventario ACTIVO para ese ítem.
    · consumido  = stock desde_inventario en registro_compras (todos los proyectos).
    · disponible = max(0, agregado − consumido).
    · detalle    = [{ep, cant, fecha}] de cada consumo (para el botón VER).
    Todo DERIVADO (no muta la tabla inventario)."""
    agg: dict = {}
    try:
        recs = (_supa.table(_TABLA).select("categoria,item,cantidad")
                .eq("activo", True).execute().data or [])
        for r in recs:
            k = norm_key(r.get("categoria"), r.get("item"))
            e = agg.setdefault(k, {"agregado": 0.0,
                                   "cat": str(r.get("categoria") or ""),
                                   "item": str(r.get("item") or "")})
            try:
                e["agregado"] += float(r.get("cantidad", 0) or 0)
            except (TypeError, ValueError):
                pass
    except Exception:
        pass
    cons = _consumo_desde_inventario()
    out: dict = {}
    for k in (set(agg) | set(cons)):
        a = float(agg.get(k, {}).get("agregado", 0.0))
        c = int(cons.get(k, {}).get("consumido", 0))
        out[k] = {
            "agregado": a, "consumido": c, "disponible": max(0.0, a - c),
            "cat": agg.get(k, {}).get("cat", ""),
            "item": agg.get(k, {}).get("item", ""),
            "detalle": cons.get(k, {}).get("detalle", []),
        }
    return out
