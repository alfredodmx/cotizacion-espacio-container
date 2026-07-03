"""
Tab SEGURIDAD — Panel de eventos y alertas de posibles ataques al sistema.
Solo root/admin. Lee los eventos de seguridad registrados por utils/security.py
(logins fallidos, bloqueos, inputs sospechosos con XSS/SQLi).

IMPORTANTE: todo lo que muestra este panel viene potencialmente de un atacante
(el payload que intentó inyectar), así que TODO se escapa con escape_html antes
de renderizar — si no, el propio dashboard sería vulnerable a XSS almacenado.
"""
import json
from datetime import datetime, timezone, timedelta

import streamlit as st

from views.layout import render_page_header
from utils.security import fetch_eventos_seguridad, escape_html, TIPOS_SEGURIDAD

_TZ_CL = timezone(timedelta(hours=-3))

# tipo → (label, color, ícono SVG path)
_TIPO_META = {
    'login_fallido':   ('Login fallido',   '#eab308',
                        '<path d="M2 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H2"/><path d="m9 12 4 4"/><path d="m13 12-4 4"/><path d="M22 12H10"/>'),
    'login_bloqueado': ('Login bloqueado', '#dc2626',
                        '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>'),
    'input_sospechoso':('Input sospechoso','#ef4444',
                        '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>'),
    'acceso_denegado': ('Acceso denegado', '#b91c1c',
                        '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>'),
}
_SEV_META = {
    'alta':  ('ALTA',  '#dc2626', '#fee2e2'),
    'media': ('MEDIA', '#c2410c', '#ffedd5'),
    'baja':  ('BAJA',  '#854d0e', '#fef9c3'),
}


def _svg(path, color, size=16):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" style="flex-shrink:0;">{path}</svg>')


def _fmt_fecha(iso):
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(_TZ_CL)
        return d.strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        return str(iso or "—")[:19]


def _resumen_detalle(tipo, det):
    """Texto corto (ya escapado) describiendo el evento para la tabla."""
    det = det or {}
    if tipo == 'input_sospechoso':
        ams = det.get('amenazas', []) or []
        campos = ", ".join(sorted({str(a.get('campo', '?')) for a in ams}))
        tipos = ", ".join(sorted({str(a.get('tipo', '?')) for a in ams}))
        ctx = det.get('contexto', '')
        blk = ' · BLOQUEADO' if det.get('bloqueado') else ''
        muestra = ""
        if ams:
            muestra = str(ams[0].get('muestra', ''))[:120]
        base = f"{ctx} — campos: {campos} — patrones: {tipos}{blk}"
        if muestra:
            base += f'\n↳ "{muestra}"'
        return escape_html(base)
    if tipo == 'login_bloqueado':
        return escape_html(f"Bloqueado tras {det.get('intentos_recientes', '?')} intentos recientes")
    if tipo == 'login_fallido':
        return escape_html(f"Credenciales incorrectas (intento {det.get('intentos_sesion', '?')} en la sesión)")
    try:
        return escape_html(json.dumps(det, ensure_ascii=False)[:180])
    except Exception:
        return escape_html(str(det)[:180])


def render_tab_seguridad(**_kwargs):
    _rol = st.session_state.get('rol_usuario', 'ejecutivo')
    if _rol not in ('root', 'admin'):
        st.error("No tienes permisos para ver el panel de seguridad.")
        st.stop()

    render_page_header(
        "seguridad",
        "Seguridad",
        "Eventos y alertas de posibles intentos de ataque al sistema.",
    )

    # ── Controles: rango temporal + refrescar ──────────────────────────────
    _c1, _c2, _c3 = st.columns([1.4, 2.6, 1], vertical_alignment="bottom")
    with _c1:
        _rango = st.selectbox("Rango", ["Últimas 24 h", "Últimos 7 días", "Últimos 30 días"],
                              index=1, key="seg_rango")
    _horas = {"Últimas 24 h": 24, "Últimos 7 días": 168, "Últimos 30 días": 720}[_rango]
    with _c3:
        if st.button("↻ Actualizar", key="seg_refresh", use_container_width=True):
            fetch_eventos_seguridad.clear()
            st.rerun()

    eventos = fetch_eventos_seguridad(horas=_horas)

    # ── KPIs (siempre sobre 24 h para las alertas "en caliente") ────────────
    _ahora = datetime.now(timezone.utc)
    def _en_ventana(ev, horas):
        try:
            d = datetime.fromisoformat(str(ev.get('fecha', '')).replace("Z", "+00:00"))
            return (_ahora - d) <= timedelta(hours=horas)
        except Exception:
            return False

    _24 = [e for e in eventos if _en_ventana(e, 24)]
    _n_login_fail = sum(1 for e in _24 if e.get('tipo_cambio') == 'login_fallido')
    _n_bloqueos   = sum(1 for e in _24 if e.get('tipo_cambio') == 'login_bloqueado')
    _n_inputs     = sum(1 for e in _24 if e.get('tipo_cambio') == 'input_sospechoso')
    _n_altas      = sum(1 for e in _24 if str((e.get('detalle') or {}).get('severidad')) == 'alta')

    _kpis = [
        ('#eab308', _TIPO_META['login_fallido'][2],   "Logins fallidos", _n_login_fail, "últimas 24 h"),
        ('#dc2626', _TIPO_META['login_bloqueado'][2], "Bloqueos",        _n_bloqueos,   "últimas 24 h"),
        ('#ef4444', _TIPO_META['input_sospechoso'][2],"Inputs sospechosos", _n_inputs,  "XSS / SQLi 24 h"),
        ('#b91c1c', '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
                     "Alertas severidad ALTA", _n_altas, "últimas 24 h"),
    ]
    _cards = ''.join(
        f'<div class="seg-kpi" style="--c:{c};">'
        f'<div class="seg-kpi-top">{_svg(ic, c, 18)}<span>{escape_html(lbl)}</span></div>'
        f'<div class="seg-kpi-val" style="color:{c};">{val}</div>'
        f'<div class="seg-kpi-sub">{escape_html(sub)}</div></div>'
        for c, ic, lbl, val, sub in _kpis
    )
    st.markdown(
        "<style>"
        ".seg-kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;margin:6px 0 10px;}"
        ".seg-kpi{background:#fff;border:1px solid #e6eaf2;border-left:4px solid var(--c);border-radius:14px;"
        "padding:14px 16px;box-shadow:0 2px 12px rgba(15,23,42,0.06);}"
        ".seg-kpi-top{display:flex;align-items:center;gap:8px;font-family:Montserrat,sans-serif;font-weight:800;"
        "font-size:0.66rem;letter-spacing:0.05em;text-transform:uppercase;color:#64748b;}"
        ".seg-kpi-val{font-family:'Plus Jakarta Sans',sans-serif;font-weight:900;font-size:2rem;line-height:1;margin:8px 0 4px;}"
        ".seg-kpi-sub{font-size:0.72rem;color:#94a3b8;font-weight:500;}"
        "</style>"
        f'<div class="seg-kpis">{_cards}</div>',
        unsafe_allow_html=True)

    if _n_altas > 0 or _n_bloqueos > 0:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;background:#fef2f2;border:1px solid #fecaca;'
            f'border-radius:12px;padding:12px 16px;color:#991b1b;font-weight:600;font-size:0.9rem;margin-bottom:6px;">'
            f'{_svg(_TIPO_META["input_sospechoso"][2], "#dc2626", 18)}'
            f'<span>Hay actividad de riesgo en las últimas 24 h. Revisa los eventos de severidad ALTA abajo.</span></div>',
            unsafe_allow_html=True)

    st.markdown("---")

    # ── Filtro por tipo ─────────────────────────────────────────────────────
    _tlabels = {t: _TIPO_META.get(t, (t, '#64748b', ''))[0] for t in TIPOS_SEGURIDAD}
    _opts = ["Todos"] + [_tlabels[t] for t in TIPOS_SEGURIDAD]
    _sel = st.multiselect("Filtrar por tipo de evento", _opts, default=["Todos"], key="seg_filtro_tipos")
    if not _sel or "Todos" in _sel:
        _tipos_activos = set(TIPOS_SEGURIDAD)
    else:
        _rev = {v: k for k, v in _tlabels.items()}
        _tipos_activos = {_rev[s] for s in _sel if s in _rev}

    _filtrados = [e for e in eventos if e.get('tipo_cambio') in _tipos_activos]

    st.markdown(f"### Eventos  ·  {len(_filtrados)}")

    if not _filtrados:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;background:#f0fdf4;border:1px solid #bbf7d0;'
            'border-radius:12px;padding:14px 18px;color:#166534;font-weight:600;">'
            + _svg('<path d="M20 6 9 17l-5-5"/>', '#16a34a', 18)
            + '<span>Sin eventos de seguridad en el rango seleccionado. Todo tranquilo.</span></div>',
            unsafe_allow_html=True)
        return

    # ── Tabla de eventos (todo escapado) ────────────────────────────────────
    _rows = ""
    for e in _filtrados[:500]:
        _tipo = e.get('tipo_cambio', '')
        _lbl, _col, _icp = _TIPO_META.get(_tipo, (_tipo, '#64748b', ''))
        _det = e.get('detalle') or {}
        if isinstance(_det, str):
            try: _det = json.loads(_det)
            except Exception: _det = {'raw': _det}
        _sev = str(_det.get('severidad', 'baja'))
        _sl, _sc, _sbg = _SEV_META.get(_sev, _SEV_META['baja'])
        _rows += (
            '<tr>'
            f'<td class="mono">{escape_html(_fmt_fecha(e.get("fecha")))}</td>'
            f'<td><span class="seg-badge" style="color:{_col};">{_svg(_icp, _col, 13)}{escape_html(_lbl)}</span></td>'
            f'<td><span class="seg-sev" style="color:{_sc};background:{_sbg};">{escape_html(_sl)}</span></td>'
            f'<td class="mono">{escape_html(e.get("asesor") or "—")}</td>'
            f'<td class="det">{_resumen_detalle(_tipo, _det)}</td>'
            '</tr>'
        )
    _table = (
        "<style>"
        ".seg-wrap{overflow:auto;max-height:560px;border:1px solid #e7ebf3;border-radius:12px;box-shadow:0 1px 3px rgba(15,23,42,.05);}"
        ".seg-tbl{width:100%;border-collapse:collapse;font-family:'Inter','Segoe UI',sans-serif;font-size:0.82rem;}"
        ".seg-tbl thead th{background:#0f172a;color:#fff;font-family:Montserrat,sans-serif;font-weight:700;font-size:0.64rem;"
        "text-transform:uppercase;letter-spacing:0.05em;padding:10px 14px;text-align:left;white-space:nowrap;position:sticky;top:0;z-index:2;}"
        ".seg-tbl tbody td{padding:9px 14px;border-bottom:1px solid #eef2f7;color:#0f172a;vertical-align:top;}"
        ".seg-tbl tbody tr:hover{background:#f8fafc;}"
        ".seg-tbl .mono{font-family:'JetBrains Mono',monospace;font-size:0.76rem;color:#334155;white-space:nowrap;}"
        ".seg-tbl .det{white-space:pre-wrap;word-break:break-word;color:#334155;font-size:0.78rem;max-width:520px;}"
        ".seg-badge{display:inline-flex;align-items:center;gap:6px;font-weight:800;font-size:0.72rem;white-space:nowrap;}"
        ".seg-sev{display:inline-block;font-weight:800;font-size:0.62rem;letter-spacing:0.05em;padding:2px 9px;border-radius:99px;}"
        "</style>"
        '<div class="seg-wrap"><table class="seg-tbl"><thead><tr>'
        '<th>Fecha (Chile)</th><th>Tipo</th><th>Severidad</th><th>Usuario / Email</th><th>Detalle</th>'
        '</tr></thead><tbody>' + _rows + '</tbody></table></div>'
    )
    st.markdown(_table, unsafe_allow_html=True)
    st.caption("Los datos mostrados (incluidos posibles payloads de ataque) se muestran como texto escapado — no se ejecutan.")
