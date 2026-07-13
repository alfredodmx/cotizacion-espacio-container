"""
Backup completo de la base de datos: extrae TODAS las tablas públicas de
Supabase y arma un ZIP con un JSON por tabla + un manifiesto. Solo lo usan
admin/root desde la pestaña COTIZACIONES (medida de seguridad / recuperación
ante cualquier eventualidad).

Diseño defensivo:
- Pagina cada tabla de 1000 en 1000 (evita el tope de PostgREST).
- NUNCA lanza por tabla: si una falla (RLS, no existe), lo anota en el
  manifiesto (campo `error`) y sigue con las demás.
- La lógica de extracción no depende de Streamlit: recibe un `progress_cb`
  opcional para reportar el avance a la UI.
"""
import io
import csv
import json
import math
import zipfile
from datetime import datetime, timezone, timedelta

# Todas las tablas públicas ACTIVAS del sistema. Si agregas una tabla nueva a
# Supabase, súmala aquí para que entre en el backup.
TABLAS_BACKUP = [
    "cotizaciones",
    "registro_compras",
    "catalogo_materiales",
    "formulario_config",
    "formulario_respuestas",
    "excel_versiones",
    "cotizacion_logs",
    "plantillas_contrato",
    "notificaciones_config",
]

# Etiqueta legible por tabla (para la UI de progreso).
_LABELS = {
    "cotizaciones":          "Cotizaciones",
    "registro_compras":      "Registro de compras",
    "catalogo_materiales":   "Catálogo de materiales",
    "formulario_config":     "Config. formulario",
    "formulario_respuestas": "Respuestas formulario",
    "excel_versiones":       "Versiones Excel",
    "cotizacion_logs":       "Logs / auditoría",
    "plantillas_contrato":   "Plantillas de contrato",
    "notificaciones_config": "Config. notificaciones",
}

_TZ_CL = timezone(timedelta(hours=-3))
_PAGE = 1000


def etiqueta_tabla(t: str) -> str:
    return _LABELS.get(t, t)


def _filas_a_csv(filas: list) -> str:
    """Convierte una lista de dicts (filas de una tabla) a texto CSV.
    - Cabecera = unión de todas las claves (preservando orden de aparición).
    - Valores dict/list se serializan a JSON (una celda no puede anidar).
    - BOM UTF-8 al inicio para que Excel muestre bien los acentos.
    """
    if not filas:
        return "﻿"
    keys, seen = [], set()
    for row in filas:
        if isinstance(row, dict):
            for k in row.keys():
                if k not in seen:
                    seen.add(k); keys.append(k)
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=keys, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for row in filas:
        if not isinstance(row, dict):
            continue
        norm = {}
        for k in keys:
            v = row.get(k)
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False, default=str)
            norm[k] = v
        w.writerow(norm)
    return "﻿" + out.getvalue()


def contar_filas(supabase_admin, tabla: str) -> int:
    """Cuenta exacta de filas de una tabla (0 si falla)."""
    try:
        r = supabase_admin.table(tabla).select("*", count="exact").limit(1).execute()
        return int(r.count or 0)
    except Exception:
        return 0


def _fetch_tabla(supabase_admin, tabla: str, on_batch=None) -> list:
    """Trae TODAS las filas de una tabla paginando. on_batch(n_acumulado) por lote."""
    filas = []
    start = 0
    while True:
        r = supabase_admin.table(tabla).select("*").range(start, start + _PAGE - 1).execute()
        lote = r.data or []
        filas.extend(lote)
        if on_batch:
            on_batch(len(filas))
        if len(lote) < _PAGE:
            break
        start += _PAGE
    return filas


def generar_backup(supabase_admin, generado_por: str = "", tablas=None, progress_cb=None,
                   formato: str = "json"):
    """Extrae todas las tablas y devuelve (filename, zip_bytes, manifest).

    formato: 'json' (un .json por tabla) o 'csv' (un .csv por tabla). En ambos
    casos se incluye _manifest.json. progress_cb(pct, tabla, hechas, counts) se
    llama durante la extracción para actualizar la UI. Nunca lanza por tabla.
    """
    formato = "csv" if str(formato).lower() == "csv" else "json"
    _ext = "csv" if formato == "csv" else "json"
    tablas = list(tablas or TABLAS_BACKUP)

    # 1) Conteo previo → total de filas para el porcentaje.
    counts = {}
    for t in tablas:
        counts[t] = contar_filas(supabase_admin, t)
        if progress_cb:
            progress_cb(0, t, [], counts)
    total = sum(counts.values()) or 1

    ahora = datetime.now(_TZ_CL)
    manifest = {
        "generado_en": ahora.isoformat(),
        "generado_por": generado_por or "desconocido",
        "zona_horaria": "America/Santiago (UTC-3)",
        "version": 1,
        "formato": formato,
        "total_tablas": len(tablas),
        "tablas": [],
    }

    buf = io.BytesIO()
    hechas = []
    acumulado = [0]  # filas totales ya extraídas (todas las tablas), en lista para el closure

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for t in tablas:
            base_previa = acumulado[0]

            def _on_batch(n_tabla, _base=base_previa, _t=t):
                if progress_cb:
                    pct = min(99, int((_base + n_tabla) / total * 100))
                    progress_cb(pct, _t, hechas, counts)

            error = ""
            filas = []
            try:
                filas = _fetch_tabla(supabase_admin, t, on_batch=_on_batch)
            except Exception as e:
                error = str(e)[:300]

            acumulado[0] = base_previa + len(filas)
            try:
                if formato == "csv":
                    zf.writestr(f"{t}.csv", _filas_a_csv(filas))
                else:
                    zf.writestr(f"{t}.json", json.dumps(filas, ensure_ascii=False, default=str))
            except Exception as e:
                error = error or f"serializacion: {str(e)[:200]}"
                zf.writestr(f"{t}.{_ext}", "" if formato == "csv" else "[]")

            manifest["tablas"].append({
                "nombre": t,
                "etiqueta": etiqueta_tabla(t),
                "registros": len(filas),
                "error": error,
            })
            hechas.append(t)
            if progress_cb:
                pct = min(99, int(acumulado[0] / total * 100))
                progress_cb(pct, t, hechas, counts)

        manifest["total_registros"] = acumulado[0]
        zf.writestr("_manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2, default=str))

    if progress_cb:
        progress_cb(100, "", hechas, counts)

    filename = f"backup_bd_{formato}_{ahora.strftime('%Y%m%d_%H%M%S')}.zip"
    return filename, buf.getvalue(), manifest


# ── Presentación del progreso (HTML puro, sin Streamlit) ──────────────────────

def progress_svg_html(pct, tabla, hechas, counts, tablas=None) -> str:
    """Indicador circular de progreso (anillo + % + chips por tabla). Se
    re-renderiza en un st.empty() a medida que avanza la extracción."""
    tablas = list(tablas or TABLAS_BACKUP)
    counts = counts or {}
    hechas_set = set(hechas or [])
    pct = max(0, min(100, int(pct)))
    R = 54
    C = 2 * math.pi * R
    off = C * (1 - pct / 100.0)

    if pct >= 100:
        sub = "Backup completado"
    elif tabla:
        sub = f"Extrayendo {etiqueta_tabla(tabla)}…"
    else:
        sub = "Preparando…"

    _check = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#15803d" '
              'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
              '<path d="M20 6 9 17l-5-5"/></svg>')
    chips = []
    for t in tablas:
        done = t in hechas_set
        activo = (t == tabla) and not done
        if done:
            bg, fg, bd, ic = "#dcfce7", "#15803d", "#86efac", _check
        elif activo:
            bg, fg, bd, ic = "#dbeafe", "#1d4ed8", "#93c5fd", '<span class="ecbk-spin"></span>'
        else:
            bg, fg, bd, ic = "#f1f5f9", "#94a3b8", "#e2e8f0", ""
        n = counts.get(t, 0)
        chips.append(
            f'<span class="ecbk-chip" style="background:{bg};color:{fg};border-color:{bd};">'
            f'{ic}<span>{etiqueta_tabla(t)}</span>'
            f'<b style="opacity:.65;font-weight:800;margin-left:2px;">{n}</b></span>'
        )

    return (
        '<div class="ecbk-run">'
        '<style>'
        '.ecbk-run{display:flex;flex-direction:column;align-items:center;gap:4px;'
        'padding:16px 6px 8px;font-family:Montserrat,sans-serif;}'
        '.ecbk-ring-wrap{position:relative;width:132px;height:132px;}'
        '.ecbk-pct{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;'
        'font-size:33px;font-weight:900;color:#0f172a;letter-spacing:-1px;}'
        '.ecbk-sub{font-size:13px;font-weight:700;color:#475569;margin-top:9px;min-height:18px;}'
        '.ecbk-chips{display:flex;flex-wrap:wrap;gap:7px;justify-content:center;max-width:660px;margin-top:14px;}'
        '.ecbk-chip{display:inline-flex;align-items:center;gap:6px;padding:5px 11px;border-radius:99px;'
        'border:1px solid;font-size:11px;font-weight:700;transition:all .3s;}'
        '.ecbk-spin{width:11px;height:11px;border-radius:50%;border:2px solid #bfdbfe;border-top-color:#1d4ed8;'
        'display:inline-block;animation:ecbkspin .7s linear infinite;}'
        '@keyframes ecbkspin{to{transform:rotate(360deg)}}'
        '</style>'
        '<div class="ecbk-ring-wrap">'
        '<svg width="132" height="132" viewBox="0 0 132 132">'
        f'<circle cx="66" cy="66" r="{R}" fill="none" stroke="#eef2f7" stroke-width="9"/>'
        f'<circle cx="66" cy="66" r="{R}" fill="none" stroke="#5b7cfa" stroke-width="9" '
        f'stroke-linecap="round" stroke-dasharray="{C:.1f}" stroke-dashoffset="{off:.1f}" '
        'transform="rotate(-90 66 66)" style="transition:stroke-dashoffset .3s ease;"/></svg>'
        f'<div class="ecbk-pct">{pct}%</div>'
        '</div>'
        f'<div class="ecbk-sub">{sub}</div>'
        f'<div class="ecbk-chips">{"".join(chips)}</div>'
        '</div>'
    )
