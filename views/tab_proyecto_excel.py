"""
Tab PROYECTO EXCEL — Control de versiones del cotizador.xlsx + Visor 3D Beta.
Código fuente original: app.py líneas 13272-13630 (excel) + visor 3D

Seguridad: subir/activar/eliminar versiones son operaciones server-side (Python).
La lista de versiones se renderiza como HTML propio en un components.html; sus
botones Activar/Eliminar enrutan a Python con el patrón query param + botón nativo
oculto (sin recargar la página, sin exponer claves). Eliminar pide confirmación.
"""
import html as _html

import streamlit as st
import streamlit.components.v1 as _components

from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header
from utils.excel_manager import (
    get_excel_bytes_activo,
    leer_hoja_excel,
    leer_bd_total,
    cargar_visibilidad_impresion,
    exportar_csv_completo,
)


# ── Iconos SVG (Lucide) + tipografía de títulos unificada ─────────────────────

def _svg(path, size=17, color="#0f3460", sw=2):
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="flex:0 0 auto;">{path}</svg>')


_IC = {
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "sheet": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v5h5"/><path d="M8 13h2"/><path d="M14 13h2"/><path d="M8 17h2"/><path d="M14 17h2"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "zap": '<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "file": '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5Z"/><path d="M14 2v6h6"/>',
    "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
}

_SEC = ("font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;"
        "text-transform:uppercase;letter-spacing:0.05em;line-height:1.6;display:flex;"
        "align-items:center;gap:9px;margin:24px 0 13px;")


def _title(icon, text):
    st.markdown(f'<div style="{_SEC}">{_svg(_IC[icon], 17, "#0f3460")}<span>{text}</span></div>',
                unsafe_allow_html=True)


def _fmt_fecha(raw):
    try:
        import pytz as _pytz
        from datetime import datetime as _dt
        _obj = _dt.fromisoformat(str(raw).replace("Z", "+00:00"))
        return _obj.astimezone(_pytz.timezone("America/Santiago")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(raw)[:16].replace("T", " ")


# ── Lista de versiones (HTML propio en iframe) ────────────────────────────────

def _build_versiones_html(versiones):
    def esc(s):
        return _html.escape(str(s or ""))

    cards = []
    for v in versiones:
        activa = v.get("activa", False)
        nombre = esc(v.get("version_nombre", "—"))
        fecha = esc(_fmt_fecha(v.get("fecha_subida", "")))
        por = esc(v.get("subida_por", "admin"))
        arch = esc(v.get("archivo_nombre", ""))
        vid = esc(v.get("id"))

        meta = (f'<div class="xv-meta">'
                f'<span>{_svg(_IC["calendar"], 12, "#94a3b8", 2)}{fecha}</span>'
                f'<span>{_svg(_IC["user"], 12, "#94a3b8", 2)}{por}</span>'
                f'</div>'
                f'<div class="xv-file">{_svg(_IC["file"], 11, "#cbd5e1", 2)}<code>{arch}</code></div>')

        if activa:
            cards.append(
                f'<div class="xv xv-on">'
                f'<div class="xv-ic xv-ic-on">{_svg(_IC["check"], 22, "#fff", 2.4)}</div>'
                f'<div class="xv-body"><div class="xv-name">{nombre}'
                f'<span class="xv-badge">Activa</span></div>{meta}</div>'
                f'<div class="xv-actions"><span class="xv-active-pill">'
                f'{_svg(_IC["check"], 14, "#fff", 2.6)}EN USO</span></div>'
                f'</div>'
            )
        else:
            cards.append(
                f'<div class="xv">'
                f'<div class="xv-ic">{_svg(_IC["sheet"], 20, "#64748b", 2)}</div>'
                f'<div class="xv-body"><div class="xv-name">{nombre}</div>{meta}</div>'
                f'<div class="xv-actions">'
                f'<button class="xv-btn xv-act" data-act="activar" data-id="{vid}" data-nm="{nombre}">'
                f'{_svg(_IC["zap"], 15, "#fff", 2.2)}Activar</button>'
                f'<button class="xv-btn xv-del" data-act="eliminar" data-id="{vid}" data-nm="{nombre}" '
                f'title="Eliminar versión">{_svg(_IC["trash"], 15, "#dc2626", 2)}</button>'
                f'</div></div>'
            )

    if cards:
        _n = len(cards)
        _count = (f'<div class="xv-count">{_n} '
                  + ("versiones" if _n != 1 else "versi&#243;n")
                  + ' &middot; la activa es la que usa el sistema</div>')
        grid = (_count + '<div class="xv-scroll"><div class="xv-list">' + "".join(cards) + "</div></div>")
    else:
        grid = '<div class="xv-empty">No hay versiones subidas aún. Sube el cotizador.xlsx para comenzar.</div>'

    css = """
*{box-sizing:border-box;}
body{margin:0;font-family:'Inter','Segoe UI',sans-serif;background:transparent;}
.xv-count{font-size:0.74rem;color:#94a3b8;font-weight:600;margin:0 2px 9px;}
.xv-scroll{max-height:540px;overflow-y:auto;padding:2px 8px 2px 2px;}
.xv-scroll::-webkit-scrollbar{width:8px;}
.xv-scroll::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:8px;}
.xv-scroll::-webkit-scrollbar-track{background:transparent;}
.xv-list{display:flex;flex-direction:column;gap:11px;padding:2px;}
.xv-empty{padding:34px;text-align:center;color:#94a3b8;font-weight:600;background:#f8fafc;
  border:1px dashed #cbd5e1;border-radius:14px;}
.xv{display:flex;align-items:center;gap:15px;background:#fff;border:1px solid #e7ebf3;
  border-radius:14px;padding:14px 16px;box-shadow:0 2px 8px rgba(15,23,42,.05);transition:box-shadow .16s,transform .16s;}
.xv:hover{box-shadow:0 8px 22px rgba(15,52,96,.10);transform:translateY(-1px);}
.xv-on{border:1px solid #10b981;background:linear-gradient(90deg,rgba(16,185,129,.06),rgba(16,185,129,.01));}
.xv-ic{width:46px;height:46px;border-radius:12px;flex:0 0 auto;display:flex;align-items:center;
  justify-content:center;background:#f1f5f9;}
.xv-ic-on{background:linear-gradient(135deg,#059669,#10b981);box-shadow:0 6px 16px rgba(16,185,129,.35);}
.xv-body{flex:1;min-width:0;}
.xv-name{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.95rem;color:#1e293b;
  display:flex;align-items:center;gap:9px;flex-wrap:wrap;line-height:1.3;}
.xv-badge{background:#10b981;color:#fff;font-size:0.58rem;font-weight:800;letter-spacing:.1em;
  padding:2px 8px;border-radius:5px;text-transform:uppercase;}
.xv-meta{display:flex;gap:16px;flex-wrap:wrap;margin-top:5px;}
.xv-meta span{display:inline-flex;align-items:center;gap:5px;font-size:0.76rem;color:#64748b;font-weight:500;}
.xv-file{display:flex;align-items:center;gap:5px;margin-top:3px;}
.xv-file code{font-size:0.68rem;color:#94a3b8;font-family:ui-monospace,monospace;}
.xv-actions{display:flex;align-items:center;gap:8px;flex:0 0 auto;}
.xv-btn{display:inline-flex;align-items:center;gap:6px;border:none;border-radius:10px;cursor:pointer;
  font-family:inherit;font-weight:700;font-size:0.8rem;padding:9px 14px;transition:transform .1s,box-shadow .15s,background .15s;}
.xv-act{background:linear-gradient(135deg,#0f3460,#1a5276);color:#fff;box-shadow:0 6px 16px rgba(15,52,96,.28);}
.xv-act:hover{transform:translateY(-1px);box-shadow:0 9px 22px rgba(15,52,96,.36);}
.xv-del{background:#fff;border:1px solid #fca5a5;padding:9px 11px;}
.xv-del:hover{background:#fef2f2;}
.xv-active-pill{display:inline-flex;align-items:center;gap:6px;background:linear-gradient(135deg,#059669,#10b981);
  color:#fff;font-weight:800;font-size:0.72rem;letter-spacing:.05em;padding:8px 15px;border-radius:10px;
  box-shadow:0 6px 16px rgba(16,185,129,.3);}
"""

    js = """
<script>
(function(){
  document.addEventListener('click', function(e){
    var b = e.target.closest && e.target.closest('.xv-btn');
    if(!b) return;
    e.preventDefault();
    try{
      var W = window.parent;
      var u = new URL(W.location.href);
      u.searchParams.set('_xls_act', b.getAttribute('data-act'));
      u.searchParams.set('_xls_id', b.getAttribute('data-id'));
      W.history.replaceState({}, '', u.toString());
      var hb = W.document.querySelector('.st-key-_xls_action_btn button');
      if(hb) hb.click();
    }catch(err){}
  });
  function fit(){
    try{
      var h = Math.ceil(document.body.scrollHeight);
      if(window.frameElement) window.frameElement.style.height = (h+4)+'px';
      window.parent.postMessage({type:'streamlit:setFrameHeight',height:h}, '*');
    }catch(e){}
  }
  window.addEventListener('load', fit);
  [60,200,500,1000].forEach(function(t){setTimeout(fit,t);});
  try{ new ResizeObserver(fit).observe(document.documentElement); }catch(e){}
  fit();
})();
</script>
"""
    return ('<!DOCTYPE html><html><head><meta charset="utf-8">'
            '<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">'
            '<style>' + css + '</style></head><body>' + grid + js + '</body></html>')


# ── Diálogo: eliminar versión (confirmación segura) ───────────────────────────

@st.dialog("Eliminar versión")
def _dlg_eliminar_version(v, supabase):
    st.markdown(f"### {v.get('version_nombre', '—')}")
    st.caption(v.get("archivo_nombre", ""))
    st.error("Se eliminará el archivo del almacenamiento y su registro. "
             "Esta acción no se puede deshacer. (No afecta a las cotizaciones existentes.)")
    st.divider()
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Sí, eliminar versión", type="primary", use_container_width=True,
                     icon=":material/delete_forever:", key="_xls_del_ok"):
            try:
                if v.get("archivo_nombre"):
                    supabase.storage.from_("config").remove([v["archivo_nombre"]])
                _supa_admin.table("excel_versiones").delete().eq("id", v["id"]).execute()
                st.session_state["_xls_toast"] = f"Versión «{v.get('version_nombre','')}» eliminada."
                st.rerun()
            except Exception as e:
                st.error(f"Error al eliminar: {e}")
    with c2:
        if st.button("Cancelar", use_container_width=True, key="_xls_del_no"):
            st.rerun()


def _activar_version(vid):
    """Activa la versión (desactiva las demás) y limpia todas las cachés para que
    el sistema use el nuevo Excel al instante."""
    try:
        _supa_admin.table("excel_versiones").update({"activa": False}).neq(
            "id", "00000000-0000-0000-0000-000000000000").execute()
        _supa_admin.table("excel_versiones").update({"activa": True}).eq("id", vid).execute()
        for _fn in (get_excel_bytes_activo, leer_hoja_excel, leer_bd_total):
            if hasattr(_fn, "clear"):
                _fn.clear()
        st.session_state.pop("excel_bytes_cache", None)
        st.session_state.pop("excel_url_cache", None)
        st.cache_data.clear()
        return True, None
    except Exception as e:
        return False, str(e)


# ── render principal ──────────────────────────────────────────────────────────

def render_tab_proyecto_excel(supabase, supabase_admin=None, supa_url='', supa_key='', **deps):
    supa_admin = supabase_admin or _supa_admin

    if "_xls_toast" in st.session_state:
        st.toast(st.session_state.pop("_xls_toast"))
    if "excel_upload_key" not in st.session_state:
        st.session_state.excel_upload_key = 0

    st.markdown(
        "<style>"
        ".st-key-_xls_action_btn{position:absolute!important;width:1px!important;height:1px!important;"
        "overflow:hidden!important;opacity:0!important;}"
        ".xls-card{background:#fff;border:1px solid #e7ebf3;border-radius:16px;padding:18px 20px;"
        "box-shadow:0 2px 10px rgba(15,23,42,.05);}"
        "</style>",
        unsafe_allow_html=True,
    )

    render_page_header(
        "proyecto_excel",
        "Proyecto Excel &mdash; Control de Versiones",
        "Sube versiones del cotizador.xlsx y activa la que necesites. El sistema se actualiza al instante.",
    )

    # Cargar versiones
    try:
        _versiones = supa_admin.table("excel_versiones").select("*").order(
            "fecha_subida", desc=True).execute().data or []
    except Exception:
        _versiones = []
    _activa = next((_v for _v in _versiones if _v.get("activa")), None)

    # ── Estado actual (hero) ──
    if _activa:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:14px;'
            'background:linear-gradient(120deg,#059669,#10b981);border-radius:16px;'
            'padding:18px 22px;box-shadow:0 10px 28px rgba(16,185,129,.28);margin-bottom:6px;">'
            f'<div style="width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.18);'
            f'display:flex;align-items:center;justify-content:center;flex:0 0 auto;">'
            f'{_svg(_IC["check"], 24, "#fff", 2.5)}</div>'
            '<div style="color:#fff;min-width:0;">'
            '<div style="font-size:.68rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;'
            'opacity:.85;">Versión activa en el sistema</div>'
            f'<div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.18rem;'
            f'line-height:1.25;">{_html.escape(_activa.get("version_nombre",""))}</div>'
            f'<div style="font-size:.78rem;opacity:.9;margin-top:2px;">Subida el '
            f'{_html.escape(_fmt_fecha(_activa.get("fecha_subida","")))} · por '
            f'{_html.escape(_activa.get("subida_por","admin"))}</div>'
            '</div></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:14px;background:rgba(245,158,11,.08);'
            'border:1px solid #f59e0b;border-radius:16px;padding:16px 20px;margin-bottom:6px;">'
            f'<div style="flex:0 0 auto;">{_svg(_IC["alert"], 26, "#d97706", 2.2)}</div>'
            '<div style="color:#92400e;font-size:.9rem;font-weight:600;">'
            '<b>Sin versión activa.</b> El sistema usa el archivo local '
            '<code>cotizador.xlsx</code> de GitHub.</div></div>',
            unsafe_allow_html=True,
        )

    # ── Subir nueva versión ──
    _title("upload", "Subir nueva versión")
    with st.container(border=True):
        _c1, _c2 = st.columns([3, 2])
        with _c1:
            _excel_file = st.file_uploader(
                "Archivo cotizador.xlsx", type=["xlsx"],
                key=f"uploader_excel_{st.session_state.excel_upload_key}",
                label_visibility="collapsed")
        with _c2:
            _version_nombre = st.text_input(
                "Nombre de versión", placeholder="Ej: v2.1 — Abril 2025",
                key=f"input_vnom_{st.session_state.excel_upload_key}",
                label_visibility="collapsed")
            st.caption("Nombre para identificar la versión")

        if _excel_file and _version_nombre:
            _cb1, _cb2 = st.columns([1.4, 3])
            with _cb1:
                _btn_subir = st.button("Subir versión", key="btn_subir_excel",
                                       use_container_width=True, type="primary",
                                       icon=":material/cloud_upload:")
            with _cb2:
                st.caption(f"**{_excel_file.name}** → versión **{_version_nombre}**")
            if _btn_subir:
                with st.spinner("Subiendo archivo a Supabase..."):
                    try:
                        import datetime as _dt
                        try:
                            import pytz as _pytz
                            _tz_cl = _pytz.timezone("America/Santiago")
                        except ImportError:
                            from datetime import timezone, timedelta
                            _tz_cl = timezone(timedelta(hours=-3))
                        _ts = _dt.datetime.now(_tz_cl).strftime("%Y%m%d_%H%M%S")
                        _nombre_archivo = f"cotizador_{_ts}.xlsx"
                        _excel_bytes = _excel_file.read()
                        supabase.storage.from_("config").upload(
                            path=_nombre_archivo, file=_excel_bytes,
                            file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"})
                        _url_publica = supabase.storage.from_("config").get_public_url(_nombre_archivo)
                        supa_admin.table("excel_versiones").insert({
                            "version_nombre": _version_nombre,
                            "archivo_url": _url_publica,
                            "archivo_nombre": _nombre_archivo,
                            "activa": False,
                            "subida_por": st.session_state.get("auth_nombre", "admin"),
                        }).execute()
                        st.session_state.excel_upload_key += 1
                        st.session_state["_xls_toast"] = f"Versión «{_version_nombre}» subida correctamente."
                        st.rerun()
                    except Exception as _e:
                        st.error(f"Error al subir: {_e}")
        elif _excel_file and not _version_nombre:
            st.warning("Escribe un nombre para identificar esta versión.")

    # ── Versiones disponibles (HTML propio) ──
    _title("layers", "Versiones disponibles")
    _vers_html = _build_versiones_html(_versiones)
    # Panel acotado con scroll interno (la .xv-scroll limita a ~540px); fitHeight
    # ajusta el iframe a ese alto, no al de las 100+ versiones completas.
    _h0 = min(600, max(160, len(_versiones) * 96 + 60)) if _versiones else 130
    _components.html(_vers_html, height=_h0, scrolling=False)

    # Botón nativo OCULTO: el JS del iframe lo clickea para enrutar Activar/Eliminar.
    if st.button("acc", key="_xls_action_btn"):
        _act = st.query_params.get("_xls_act")
        _vid = st.query_params.get("_xls_id")
        for _k in ("_xls_act", "_xls_id"):
            try:
                del st.query_params[_k]
            except Exception:
                pass
        st.session_state["_xls_pending"] = (_act, _vid)
        st.rerun()

    _pend = st.session_state.pop("_xls_pending", None)
    if _pend:
        _act, _vid = _pend
        if _act == "activar" and _vid:
            with st.spinner("Activando versión..."):
                _ok, _err = _activar_version(_vid)
            _v = next((x for x in _versiones if str(x["id"]) == str(_vid)), None)
            _nm = _v.get("version_nombre", "") if _v else ""
            st.session_state["_xls_toast"] = (
                f"Versión «{_nm}» activada." if _ok else f"Error al activar: {_err}")
            st.rerun()
        elif _act == "eliminar" and _vid:
            _v = next((x for x in _versiones if str(x["id"]) == str(_vid)), None)
            if _v:
                _dlg_eliminar_version(_v, supabase)

    # ── Vista previa del Excel activo ──
    _title("eye", "Vista previa del Excel activo")
    with st.container(border=True):
        if _activa:
            try:
                import pandas as _pd
                _src = get_excel_bytes_activo()
                if _src and hasattr(_src, "read"):
                    _xls = _pd.ExcelFile(_src)
                    _hojas = _xls.sheet_names
                    _cs, _ci = st.columns([2, 3])
                    with _cs:
                        _hoja = st.selectbox("Hoja a previsualizar", options=_hojas,
                                             key="prev_hoja_sel", label_visibility="collapsed")
                    with _ci:
                        st.caption(f"**{len(_hojas)} hojas** · versión activa **{_activa['version_nombre']}**")
                    if _hoja:
                        _src.seek(0)
                        _df = _pd.read_excel(_src, sheet_name=_hoja, header=None)
                        _df = _df.dropna(how="all").fillna("")
                        _df = _df.astype(str).replace("nan", "").replace("0.0", "")
                        _alt = min(600, max(300, len(_df) * 35 + 50))
                        st.dataframe(_df, use_container_width=True, hide_index=True, height=_alt)
                        st.caption(f"{len(_df)} filas · {len(_df.columns)} columnas en esta hoja")
                else:
                    st.info("No se pudo cargar el archivo Excel activo.")
            except Exception as _pe:
                st.error(f"Error al previsualizar: {_pe}")
        else:
            st.info("Activa una versión para poder previsualizarla.")

    # ── Exportar datos ──
    _title("download", "Exportar datos")
    with st.container(border=True):
        st.caption("Descarga todas las cotizaciones del sistema en CSV para respaldo o análisis externo.")
        _e1, _e2 = st.columns([1.2, 3])
        with _e1:
            if st.button("Generar CSV", key="btn_generar_csv", use_container_width=True,
                         type="primary", icon=":material/database:"):
                st.session_state._csv_listo = exportar_csv_completo()
        with _e2:
            if st.session_state.get("_csv_listo"):
                from datetime import datetime as _dtc
                try:
                    import pytz as _pytzc
                    _tzc = _pytzc.timezone("America/Santiago")
                except ImportError:
                    from datetime import timezone, timedelta
                    _tzc = timezone(timedelta(hours=-3))
                _fname = f"cotizaciones_backup_{_dtc.now(_tzc).strftime('%Y%m%d_%H%M')}.csv"
                st.download_button("Descargar CSV", data=st.session_state._csv_listo,
                                   file_name=_fname, mime="text/csv", use_container_width=True,
                                   key="btn_export_csv", icon=":material/download:")
            else:
                st.caption("Haz clic en **Generar CSV** para preparar el archivo.")


def render_tab_3d_visor(supabase=None, supa_url='', anthropic_client=None, **deps):
    """Visor 3D Beta — genera modelo 3D de container desde plano con Claude Vision."""
    import streamlit.components.v1 as _components

    st.markdown("""
    <style>
    .hdr-3d {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #2d1b69 100%);
        border-radius: 20px; padding: 28px 32px; margin-bottom: 20px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(15,23,42,0.4);
    }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "3d",
        "Visor 3D Beta",
        "Genera un modelo 3D del container desde el plano de planta con Claude Vision.",
    )

    if anthropic_client is None:
        st.info("&#128274; El visor 3D requiere configuraci&#243;n de Anthropic API. Contacta al administrador.")
        return

    st.markdown("**Sube un plano o ingresa su URL para generar el modelo 3D:**")

    _col_v1, _col_v2 = st.columns([2, 3])
    with _col_v1:
        _plano_file_3d = st.file_uploader("Subir plano", type=["pdf", "png", "jpg", "jpeg"],
                                          key="visor3d_file", label_visibility="collapsed")
    with _col_v2:
        _plano_url_3d = st.text_input("URL del plano", placeholder="https://...",
                                      key="visor3d_url", label_visibility="collapsed")

    if st.button("&#127981; Generar modelo 3D", key="visor3d_generar", type="primary"):
        st.info("&#9203; Analizando plano con Claude Vision...")
        _cache_key = f"layout_3d_{_plano_url_3d or 'file'}"

        if _cache_key in st.session_state:
            _layout_3d = st.session_state[_cache_key]
        else:
            try:
                import base64 as _b64_3d
                import json as _json_3d

                if _plano_file_3d:
                    _img_bytes = _plano_file_3d.read()
                    _img_b64   = _b64_3d.b64encode(_img_bytes).decode()
                    _media_type = _plano_file_3d.type or "image/png"
                    _content_img = [
                        {"type": "image", "source": {"type": "base64", "media_type": _media_type, "data": _img_b64}},
                        {"type": "text", "text": "Analiza este plano de planta de container y devuelve JSON con: width (metros), depth (metros), wallHeight (metros, default 2.8), y walls (array con {side:'front'|'back'|'left'|'right', openings:[{type:'door'|'window', x:float, y:float, w:float, h:float}]})."}
                    ]
                elif _plano_url_3d:
                    _content_img = [
                        {"type": "image", "source": {"type": "url", "url": _plano_url_3d}},
                        {"type": "text", "text": "Analiza este plano de planta de container y devuelve JSON con: width (metros), depth (metros), wallHeight (metros, default 2.8), y walls (array con {side:'front'|'back'|'left'|'right', openings:[{type:'door'|'window', x:float, y:float, w:float, h:float}]})."}
                    ]
                else:
                    st.warning("Sube un plano o ingresa su URL primero.")
                    return

                _resp_3d = anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": _content_img}]
                )
                _text_3d = _resp_3d.content[0].text
                _start = _text_3d.find('{')
                _end   = _text_3d.rfind('}') + 1
                _layout_3d = _json_3d.loads(_text_3d[_start:_end]) if _start >= 0 else {
                    "width": 6.0, "depth": 3.0, "wallHeight": 2.8, "walls": []
                }
                st.session_state[_cache_key] = _layout_3d
            except Exception as _e3d:
                st.error(f"Error analizando plano: {_e3d}")
                return

        # Renderizar el modelo 3D con Three.js
        _W = float(_layout_3d.get('width', 6.0))
        _D = float(_layout_3d.get('depth', 3.0))
        _H = float(_layout_3d.get('wallHeight', 2.8))
        _walls_json = str(_layout_3d.get('walls', [])).replace("'", '"')

        _visor_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>body{{margin:0;overflow:hidden;background:#1a1a2e;}}canvas{{display:block;}}</style>
</head>
<body>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
var W={_W},D={_D},H={_H};
var scene=new THREE.Scene();
var camera=new THREE.PerspectiveCamera(60,window.innerWidth/window.innerHeight,0.1,100);
camera.position.set(W*1.5,H*1.2,D*2);camera.lookAt(0,H*0.5,0);
var renderer=new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(window.innerWidth,window.innerHeight);
renderer.shadowMap.enabled=true;
document.body.appendChild(renderer.domElement);

var mWall=new THREE.MeshLambertMaterial({{color:0x8fbcbb}});
var mRoof=new THREE.MeshLambertMaterial({{color:0x5e81ac}});
var mRib =new THREE.MeshLambertMaterial({{color:0x2e3440}});
var mGlass=new THREE.MeshLambertMaterial({{color:0x88c0d0,transparent:true,opacity:0.4}});
var mDoor =new THREE.MeshLambertMaterial({{color:0xd08770}});
var mFloor=new THREE.MeshLambertMaterial({{color:0x3b4252}});

// Piso
var floor=new THREE.Mesh(new THREE.BoxGeometry(W,0.05,D),mFloor);
floor.position.y=-0.025;floor.receiveShadow=true;scene.add(floor);

// Paredes
var th=0.08;
function makeWall(px,pz,rotY,wallW,openings){{
  var grp=new THREE.Group();grp.position.set(px,H/2,pz);grp.rotation.y=rotY;
  var wall=new THREE.Mesh(new THREE.BoxGeometry(wallW,H,th),mWall);
  wall.castShadow=true;wall.receiveShadow=true;grp.add(wall);
  scene.add(grp);
}}
makeWall(0,D/2,0,W,[]);
makeWall(0,-D/2,0,W,[]);
makeWall(-W/2,0,Math.PI/2,D,[]);
makeWall(W/2,0,Math.PI/2,D,[]);

// Techo
var roof=new THREE.Mesh(new THREE.BoxGeometry(W+th*2,0.1,D+th*2),mRoof);
roof.position.y=H+0.05;scene.add(roof);

// Iluminación
var ambient=new THREE.AmbientLight(0xffffff,0.6);scene.add(ambient);
var sun=new THREE.DirectionalLight(0xffffff,0.8);
sun.position.set(W*2,H*3,D*2);sun.castShadow=true;scene.add(sun);

// Grilla de suelo
var grid=new THREE.GridHelper(20,20,0x444444,0x444444);
grid.position.y=-0.01;scene.add(grid);

// Rotación automática suave
var angle=0;
function animate(){{
  requestAnimationFrame(animate);
  angle+=0.005;
  camera.position.x=Math.cos(angle)*W*2.2;
  camera.position.z=Math.sin(angle)*D*2.2;
  camera.lookAt(0,H*0.4,0);
  renderer.render(scene,camera);
}}
animate();
window.addEventListener('resize',function(){{
  camera.aspect=window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth,window.innerHeight);
}});
</script>
</body></html>"""

        _components.html(_visor_html, height=620, scrolling=False)
        st.caption(f"&#9888;&#65039; Beta &mdash; Dimensiones detectadas: {_W:.1f}m &#215; {_D:.1f}m &#215; {_H:.1f}m altura")

        _col_dbg1, _col_dbg2 = st.columns([3, 1])
        with _col_dbg2:
            if st.button("&#128260; Regenerar", key="btn_regen_3d", help="Forzar nuevo an&#225;lisis del plano"):
                st.session_state.pop(_cache_key, None)
                st.rerun()
        with _col_dbg1:
            with st.expander("&#128269; Ver JSON detectado por Claude Vision"):
                st.json(_layout_3d)
    else:
        st.info("&#9757; Sube un plano y presiona **Generar modelo 3D** para comenzar.")
