"""
Tab CONTRATO CLIENTE — Generador, preview, notariado y editor de plantillas.
Código fuente original: app.py líneas 17082-18539
"""
import json
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, date as _date_cls
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header
from utils.formato import _normalizar_nombre

try:
    from utils.pdf_contrato import generar_pdf_contrato, preparar_pdf_data, generar_pdf_completo
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

try:
    from utils.geografico import REGIONES_COMUNAS
except ImportError:
    REGIONES_COMUNAS = {}

try:
    import requests as _requests
    _REQUESTS_OK = True
except ImportError:
    _REQUESTS_OK = False


# ── Helpers inlineados ──────────────────────────────────────────────────────

def _cargar_cotizacion(numero, supa_admin):
    try:
        if not numero:
            return None
        resp = supa_admin.table('cotizaciones').select('*').eq('numero', numero).execute()
        if resp.data:
            cot = resp.data[0]
            prods = cot.get('productos', [])
            if isinstance(prods, str):
                try:
                    cot['productos'] = json.loads(prods)
                except Exception:
                    cot['productos'] = []
            elif not isinstance(prods, list):
                cot['productos'] = []
            return cot
        return None
    except Exception as _e:
        st.error(f"Error al cargar cotizaci&#243;n: {_e}")
        return None


def _obtener_clausulas_contrato(modelo_predefinido, supa_admin):
    def _inyectar(cls, tipo):
        if cls is None:
            return None
        r = dict(cls)
        r['_tipo_plantilla'] = tipo or 'A'
        return r
    try:
        if modelo_predefinido:
            _todas = supa_admin.table("plantillas_contrato").select("*").eq("activa", True).execute()
            for _p in (_todas.data or []):
                _mods = _p.get("modelos") or []
                if isinstance(_mods, str):
                    try:
                        _mods = json.loads(_mods)
                    except Exception:
                        _mods = []
                if modelo_predefinido in _mods:
                    return _inyectar(_p.get("clausulas"), _p.get("tipo"))
        _res = supa_admin.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).eq("tipo", "A").execute()
        if _res.data and _res.data[0].get("clausulas"):
            return _inyectar(_res.data[0]["clausulas"], _res.data[0].get("tipo"))
        _res2 = supa_admin.table("plantillas_contrato").select("clausulas,tipo").eq("activa", True).execute()
        if _res2.data and _res2.data[0].get("clausulas"):
            return _inyectar(_res2.data[0]["clausulas"], _res2.data[0].get("tipo"))
    except Exception:
        pass
    return None


def _detectar_navegador():
    try:
        ua = st.context.headers.get('User-Agent', '')
        es_chrome = 'Chrome' in ua and 'Edg' not in ua
        es_edge = 'Edg' in ua
        es_safari = 'Safari' in ua and 'Chrome' not in ua
        return {
            'es_chrome': es_chrome, 'es_edge': es_edge, 'es_safari': es_safari,
            'es_firefox': 'Firefox' in ua,
            'needs_google_viewer': es_chrome or es_edge or es_safari,
        }
    except Exception:
        return {'needs_google_viewer': True}


def _leer_hojas_disponibles():
    try:
        import pandas as _pd
        try:
            from utils.excel_manager import get_excel_bytes_activo as _geba
            return _pd.ExcelFile(_geba()).sheet_names
        except Exception:
            pass
        try:
            return _pd.ExcelFile('Actualizaciones_espacio_container.xlsx').sheet_names
        except Exception:
            return []
    except Exception:
        return []


def _pdf_visor_html(pdf_url, google_url, usar_google, height=680, spinner_msg="Cargando..."):
    usar_str = "true" if usar_google else "false"
    return f"""
<style>
@keyframes spin {{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
body,html{{margin:0;padding:0;overflow:hidden;}}
#pdf-wrap{{width:100%;height:{height}px;border:2px solid #0f3460;border-radius:12px;overflow:hidden;
           box-shadow:0 4px 12px rgba(0,0,0,0.15);background:#f0f2f5;position:relative;}}
#pdf-loading{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;
              justify-content:center;background:#f0f2f5;z-index:2;gap:12px;transition:opacity 0.4s ease;}}
#pdf-spinner{{width:40px;height:40px;border:4px solid #cbd5e1;border-top-color:#0f3460;
              border-radius:50%;animation:spin 0.8s linear infinite;}}
#pdf-loading span{{color:#64748b;font-size:0.9rem;font-family:sans-serif;}}
#pdf-iframe{{position:absolute;inset:0;width:100%;height:100%;border:none;display:block;}}
</style>
<div id="pdf-wrap">
  <div id="pdf-loading"><div id="pdf-spinner"></div><span>{spinner_msg}</span></div>
  <iframe id="pdf-iframe" src="" allow="fullscreen"></iframe>
</div>
<script>
(function(){{
  var iframe=document.getElementById('pdf-iframe');
  var loading=document.getElementById('pdf-loading');
  var usingGoogle={usar_str};
  function hide(){{loading.style.opacity='0';setTimeout(function(){{loading.style.display='none';}},400);}}
  iframe.src=usingGoogle?"{google_url}":"{pdf_url}";
  if(usingGoogle){{setTimeout(function(){{if(loading.style.display!=='none')hide();}},3000);}}
  else{{setTimeout(hide,4000);}}
}})();
</script>"""


# ── Iconos SVG (estilo Lucide, stroke) para usar dentro de HTML custom ───────
# En widgets nativos de Streamlit (tabs, botones, alerts, labels) se usa el
# shortcode :material/...: ; aquí van sólo los iconos para el HTML propio.
_IC = {
    "search":   '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "hash":     '<line x1="4" x2="20" y1="9" y2="9"/><line x1="4" x2="20" y1="15" y2="15"/><line x1="10" x2="8" y1="3" y2="21"/><line x1="16" x2="14" y1="3" y2="21"/>',
    "file":     '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    "user":     '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "building": '<rect x="4" y="2" width="16" height="20" rx="2"/><path d="M9 22v-4h6v4"/><line x1="8" y1="6" x2="8" y2="6"/><line x1="16" y1="6" x2="16" y2="6"/><line x1="12" y1="6" x2="12" y2="6"/><line x1="12" y1="10" x2="12" y2="10"/><line x1="8" y1="10" x2="8" y2="10"/><line x1="16" y1="10" x2="16" y2="10"/><line x1="12" y1="14" x2="12" y2="14"/><line x1="8" y1="14" x2="8" y2="14"/><line x1="16" y1="14" x2="16" y2="14"/>',
    "pin":      '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "home":     '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
    "box":      '<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "dollar":   '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "check":    '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    "clock":    '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "lock":     '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "warning":  '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "upload":   '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18v-6"/><path d="m9 15 3-3 3 3"/>',
}


def _svg_ic(key: str, size: int = 16, color: str = "currentColor",
            sw: float = 2, mr: int = 0, mb: int = 0, valign: int = -3) -> str:
    """SVG inline (estilo Lucide) para incrustar en HTML custom."""
    style = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        style += f"margin-right:{mr}px;"
    if mb:
        style += f"margin-bottom:{mb}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{style}">{_IC.get(key, "")}</svg>')


# ── Render principal ─────────────────────────────────────────────────────────

def render_tab_contrato(supabase, supabase_admin=None, **deps):
    supa_admin = supabase_admin or _supa_admin

    # ── Header ──
    st.markdown("""
    <style>
    .hdr-contrato {
        background: linear-gradient(135deg, #0f3460 0%, #16213e 60%, #1a1a2e 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(15,52,96,0.3);
    }
    .cont-section { font-family:'Montserrat',sans-serif; color:#0f172a; font-size:0.88rem;
                    font-weight:700; text-transform:uppercase; letter-spacing:0.05em;
                    line-height:1.6; padding-bottom:8px; border-bottom:2px solid #e2e8f0;
                    margin-bottom:14px; display:flex; align-items:center; gap:8px; }
    .cont-section svg { color:#0f172a; }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "contrato",
        "Contrato Cliente",
        "Genera y administra el contrato de fabricaci&#243;n y venta.",
    )

    # ── Sub-pestañas ──
    if st.session_state.get('modo_admin'):
        _sub_imprimir, _sub_preview, _sub_notariado, _sub_editar = st.tabs([
            ":material/description: Generador de contrato",
            ":material/visibility: Previsualizar contrato",
            ":material/attach_file: Contrato notariado",
            ":material/edit_note: Editar contrato",
        ])
    else:
        _sub_imprimir, _sub_preview = st.tabs([
            ":material/description: Generador de contrato",
            ":material/visibility: Previsualizar contrato",
        ])
        _sub_notariado = None
        _sub_editar = None

    # ================================================================
    # SUB-PESTAÑA: GENERADOR
    # ================================================================
    with _sub_imprimir:
        _ep_contrato = st.session_state.get('cotizacion_cargada', '')
        _adj_contrato = (
            st.session_state.get('_adj_es_adj', False)
            and st.session_state.get('_adj_check_ep') == _ep_contrato
        )
        if _adj_contrato and _ep_contrato:
            st.markdown(f"""
            <div style="background:#dbeafe;border:2px solid #2563eb;border-radius:14px;
                        padding:28px 32px;text-align:center;margin-top:20px;">
              <div style="margin-bottom:12px;">{_svg_ic("check", 46, color="#2563eb")}</div>
              <div style="font-size:1.2rem;font-weight:900;color:#1d4ed8;margin-bottom:8px;">
                Presupuesto ADJUDICADO &#8212; {_ep_contrato}</div>
              <div style="font-size:0.92rem;color:#1e40af;max-width:480px;margin:0 auto;line-height:1.6;">
                El contrato notariado ya fue firmado.<br>
                <b>No es posible generar un nuevo contrato.</b><br><br>
                Puedes visualizar el contrato en <b>Previsualizar contrato</b>.
              </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="cont-section">{_svg_ic("search", 17)}Paso 1 &#8212; Buscar cotizaci&#243;n</div>', unsafe_allow_html=True)
            _col_ep, _col_btn = st.columns([3, 1])
            with _col_ep:
                _ep_input = st.text_input("N&#176; de cotizaci&#243;n", placeholder="Ej: EP-12345",
                                          key="cont_ep_input", label_visibility="collapsed")
            with _col_btn:
                _buscar = st.button("Buscar EP", icon=":material/search:", use_container_width=True, key="cont_buscar")

            if _buscar and _ep_input:
                _cot_found = _cargar_cotizacion(_ep_input.strip().upper(), supa_admin)
                if _cot_found:
                    st.session_state["cont_cot"]            = _cot_found
                    st.session_state["cont_ep"]             = _ep_input.strip().upper()
                    st.session_state["cont_tiene_contrato"] = bool(_cot_found.get("contrato_generado"))
                    st.session_state["cont_precio"]         = float(_cot_found.get("total_total") or 0)
                    st.session_state.pop("cont_usar_juridica", None)  # reset toggle persona jurídica
                    st.rerun()
                else:
                    st.error(f"No se encontr&#243; la cotizaci&#243;n {_ep_input}")

            if st.session_state.get("cont_cot"):
                _cot    = st.session_state["cont_cot"]
                _ep_num = st.session_state.get("cont_ep", "")

                # Verificar si ya está adjudicado
                _cont_es_adj = bool(_cot.get("contrato_notariado_url", ""))
                if not _cont_es_adj:
                    try:
                        _adj_q = supa_admin.table("cotizaciones").select("contrato_notariado_url").eq("numero", _ep_num).execute()
                        _cont_es_adj = bool((_adj_q.data or [{}])[0].get("contrato_notariado_url", "")) if _adj_q.data else False
                    except Exception:
                        pass

                if _cont_es_adj:
                    st.markdown(f"""
                    <div style="background:#dbeafe;border:2px solid #2563eb;border-radius:14px;
                                padding:28px 32px;text-align:center;margin-top:12px;">
                      <div style="margin-bottom:12px;">{_svg_ic("check", 46, color="#2563eb")}</div>
                      <div style="font-size:1.2rem;font-weight:900;color:#1d4ed8;margin-bottom:8px;">
                        Presupuesto ADJUDICADO &#8212; {_ep_num}</div>
                      <div style="font-size:0.92rem;color:#1e40af;max-width:480px;margin:0 auto;line-height:1.6;">
                        El contrato notariado ya fue firmado.<br>
                        <b>No es posible generar un nuevo contrato.</b>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    _tiene_cont = st.session_state.get("cont_tiene_contrato", False)
                    if _tiene_cont:
                        st.success(f"Cotizaci&#243;n **{_ep_num}** cargada &#8212; {_cot.get('cliente_nombre','')} &middot; Ya tiene contrato generado")
                    else:
                        st.success(f"Cotizaci&#243;n **{_ep_num}** cargada &#8212; {_cot.get('cliente_nombre','')} &middot; Sin contrato previo")

                    st.markdown(f'<div class="cont-section">{_svg_ic("file", 17)}Paso 2 &#8212; Completar datos del contrato</div>', unsafe_allow_html=True)

                    _meses_es = {
                        1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
                        7:"julio",8:"agosto",9:"septiembre",10:"octubre",
                        11:"noviembre",12:"diciembre"
                    }

                    _ep_nombre   = (_cot.get("proyecto_observaciones", "") or "").strip() or "&#8212;"
                    _es_juridica = _cot.get("cliente_tipo", "natural") == "juridica"
                    _cli_nombre      = _cot.get("cliente_nombre", "")
                    _cli_rut         = _cot.get("cliente_rut", "")
                    _cli_empresa     = _cot.get("cliente_empresa", "")
                    _cli_rut_empresa = _cot.get("cliente_rut_empresa", "")

                    _todas_regiones = list(REGIONES_COMUNAS.keys())
                    _todas_comunas  = [c for cs in REGIONES_COMUNAS.values() for c in cs]

                    def _norm(val, lista):
                        if not val or not lista:
                            return val
                        return _normalizar_nombre(val, lista)

                    _cli_dom  = _cot.get("cliente_direccion", "")
                    _cli_com  = _norm(_cot.get("cliente_comuna", ""), _todas_comunas)
                    _cli_reg  = _norm(_cot.get("cliente_region", ""), _todas_regiones)
                    _inst_dom = _cot.get("proyecto_direccion", "")
                    _inst_com = _norm(_cot.get("proyecto_comuna", ""), _todas_comunas)
                    _inst_reg = _norm(_cot.get("proyecto_region", ""), _todas_regiones)

                    _precio  = int(st.session_state.get("cont_precio", 0))
                    _pago50  = round(_precio * 0.50)
                    _pago25a = round(_precio * 0.25)
                    _pago25b = _precio - _pago50 - _pago25a
                    _fmt_p   = lambda v: "${:,.0f}".format(v).replace(",", ".")

                    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                    # ── Toggle Persona natural / jurídica (habilitado solo si el
                    #    cliente es empresa con datos de empresa cargados) ──
                    _puede_juridica = _es_juridica and bool(_cli_empresa) and bool(_cli_rut_empresa)
                    if not _puede_juridica and st.session_state.get("cont_usar_juridica"):
                        st.session_state["cont_usar_juridica"] = False
                    _tg1, _tg2 = st.columns([2, 3])
                    with _tg1:
                        _usar_juridica = st.toggle(
                            "Generar a nombre de la empresa",
                            key="cont_usar_juridica",
                            disabled=not _puede_juridica,
                            help=("El contrato usará el NOMBRE y RUT de la empresa (persona "
                                  "jurídica) en lugar de los datos personales del cliente."
                                  if _puede_juridica else
                                  "Solo disponible para clientes empresa (persona jurídica)."),
                        )
                    _usar_juridica = bool(_usar_juridica) and _puede_juridica
                    with _tg2:
                        if _usar_juridica:
                            _mhtml = f"{_svg_ic('building', 13, color='#1d4ed8', mr=6)}Persona jur&#237;dica &#8212; datos de la <b>empresa</b>"
                            _mbg, _mcol = "#dbeafe", "#1d4ed8"
                        else:
                            _mhtml = f"{_svg_ic('user', 13, color='#475569', mr=6)}Persona natural &#8212; datos del <b>cliente</b>"
                            _mbg, _mcol = "#f1f5f9", "#475569"
                        st.markdown(
                            f"<div style='display:inline-flex;align-items:center;background:{_mbg};"
                            f"color:{_mcol};border-radius:8px;padding:8px 14px;font-size:0.82rem;"
                            f"font-weight:700;margin-top:4px;'>{_mhtml}</div>", unsafe_allow_html=True)

                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                    _c1, _c2, _c3 = st.columns([2, 2, 1])
                    with _c1:
                        _fecha_obj = st.date_input(":material/calendar_month: Fecha del contrato", value=_date_cls.today(), key="cont_fecha")
                        _fecha_str = f"{_fecha_obj.day} de {_meses_es[_fecha_obj.month]} de {_fecha_obj.year}"
                    with _c2:
                        if _usar_juridica:
                            st.text_input(":material/person: Tratamiento", value="No aplica (empresa)",
                                          disabled=True, key="cont_trat_juridica")
                            _tratamiento = ""
                        else:
                            _trat_opts = ["— Selecciona —", "Don", "Doña", "Sr.", "Sra."]
                            _tratamiento = st.selectbox(":material/person: Tratamiento", _trat_opts, key="cont_tratamiento")
                            _tratamiento = "" if "Selecciona" in _tratamiento else _tratamiento
                    with _c3:
                        _plazo = st.number_input(":material/event: Plazo d&#237;as", min_value=1, max_value=180, value=45, key="cont_plazo")

                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                    _c4, _c5 = st.columns([1, 3])
                    with _c4:
                        st.markdown(
                            f"<div style='background:#1e3a5f;border-radius:10px;padding:12px 14px;height:72px;"
                            f"display:flex;flex-direction:column;justify-content:center;'>"
                            f"<div style='font-size:0.6rem;font-weight:900;color:rgba(255,255,255,0.5);"
                            f"text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;'>{_svg_ic('hash', 11, color='rgba(255,255,255,0.55)', mr=5)}N&#176; EP</div>"
                            f"<div style='font-size:1.1rem;font-weight:900;color:#fff;'>{_ep_num}</div>"
                            f"</div>", unsafe_allow_html=True)
                    with _c5:
                        st.markdown(
                            f"<div style='background:#1e3a5f;border-radius:10px;padding:12px 14px;height:72px;"
                            f"display:flex;flex-direction:column;justify-content:center;'>"
                            f"<div style='font-size:0.6rem;font-weight:900;color:rgba(255,255,255,0.5);"
                            f"text-transform:uppercase;letter-spacing:0.1em;margin-bottom:4px;'>{_svg_ic('file', 11, color='rgba(255,255,255,0.55)', mr=5)}Nombre del proyecto</div>"
                            f"<div style='font-size:0.9rem;font-weight:700;color:#fff;'>{_ep_nombre}</div>"
                            f"</div>", unsafe_allow_html=True)

                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                    _c6, _c7 = st.columns([3, 2])
                    with _c6:
                        if _usar_juridica:
                            _card_label  = f"{_svg_ic('building', 11, color='rgba(255,255,255,0.5)', mr=5)}Cliente (empresa)"
                            _card_nombre = _cli_empresa or '&#8212;'
                            _card_sub    = (f"RUT: {_cli_rut_empresa or '&#8212;'} &middot; "
                                            f"{_svg_ic('building', 11, color='rgba(255,255,255,0.6)', mr=4)}Persona jur&#237;dica")
                            _card_extra  = (f"<div style='margin-top:6px;font-size:0.75rem;color:rgba(255,255,255,0.6);'>"
                                            f"{_svg_ic('user', 11, color='rgba(255,255,255,0.6)', mr=4)}Representante: {_cli_nombre or '&#8212;'} &middot; RUT {_cli_rut or '&#8212;'}</div>")
                        else:
                            _tag_tipo = (_svg_ic('building', 11, color='rgba(255,255,255,0.6)', mr=4) + "Persona jur&#237;dica") if _es_juridica else (_svg_ic('user', 11, color='rgba(255,255,255,0.6)', mr=4) + "Persona natural")
                            _card_label  = f"{_svg_ic('user', 11, color='rgba(255,255,255,0.5)', mr=5)}Cliente"
                            _card_nombre = f"{_tratamiento} {_cli_nombre or '&#8212;'}"
                            _card_sub    = f"RUT: {_cli_rut or '&#8212;'} &middot; {_tag_tipo}"
                            _card_extra  = (
                                f"<div style='margin-top:6px;font-size:0.75rem;color:rgba(255,255,255,0.6);'>"
                                f"{_svg_ic('building', 11, color='rgba(255,255,255,0.6)', mr=4)}{_cli_empresa or '&#8212;'} &middot; RUT empresa: {_cli_rut_empresa or '&#8212;'}</div>"
                            ) if _es_juridica else ""
                        st.markdown(
                            f"<div style='background:#1e3a5f;border-radius:10px;padding:14px 16px;margin-bottom:8px;'>"
                            f"<div style='font-size:0.6rem;font-weight:900;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>{_card_label}</div>"
                            f"<div style='font-size:1rem;font-weight:800;color:#fff;'>{_card_nombre}</div>"
                            f"<div style='font-size:0.75rem;color:rgba(255,255,255,0.6);margin-top:2px;'>{_card_sub}</div>"
                            f"{_card_extra}"
                            f"</div>", unsafe_allow_html=True)
                        st.markdown(
                            f"<div style='background:#1e3a5f;border-radius:10px;padding:14px 16px;'>"
                            f"<div style='font-size:0.6rem;font-weight:900;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>{_svg_ic('pin', 11, color='rgba(255,255,255,0.5)', mr=5)}Domicilios</div>"
                            f"<div style='font-size:0.78rem;font-weight:700;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;'>{_svg_ic('home', 11, color='rgba(255,255,255,0.5)', mr=4)}Domicilio cliente</div>"
                            f"<div style='font-size:0.88rem;font-weight:700;color:#fff;margin-bottom:2px;'>{_cli_dom or '&#8212;'}</div>"
                            f"<div style='font-size:0.75rem;color:rgba(255,255,255,0.55);margin-bottom:10px;'>{_cli_com or '&#8212;'} &middot; {_cli_reg or '&#8212;'}</div>"
                            f"<div style='font-size:0.78rem;font-weight:700;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;'>{_svg_ic('box', 11, color='rgba(255,255,255,0.5)', mr=4)}Direcci&#243;n instalaci&#243;n</div>"
                            f"<div style='font-size:0.88rem;font-weight:700;color:#fff;margin-bottom:2px;'>{_inst_dom or '&#8212;'}</div>"
                            f"<div style='font-size:0.75rem;color:rgba(255,255,255,0.55);'>{_inst_com or '&#8212;'} &middot; {_inst_reg or '&#8212;'}</div>"
                            f"</div>", unsafe_allow_html=True)
                    with _c7:
                        st.markdown(
                            f"<div style='background:#1e3a5f;border-radius:10px;padding:16px 18px;'>"
                            f"<div style='font-size:0.6rem;font-weight:900;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:10px;'>{_svg_ic('dollar', 11, color='rgba(255,255,255,0.5)', mr=5)}Detalle de pagos</div>"
                            f"<div style='font-size:1.7rem;font-weight:900;color:#fff;letter-spacing:-0.02em;margin-bottom:14px;'>{_fmt_p(_precio)}</div>"
                            f"<div style='display:flex;flex-direction:column;gap:8px;'>"
                            f"<div style='background:rgba(255,255,255,0.08);border-radius:8px;padding:10px 12px;'>"
                            f"<div style='font-size:0.6rem;color:rgba(255,255,255,0.5);font-weight:700;text-transform:uppercase;'>50% Inicial</div>"
                            f"<div style='font-size:1rem;font-weight:800;color:#fff;margin-top:2px;'>{_fmt_p(_pago50)}</div></div>"
                            f"<div style='background:rgba(255,255,255,0.08);border-radius:8px;padding:10px 12px;'>"
                            f"<div style='font-size:0.6rem;color:rgba(255,255,255,0.5);font-weight:700;text-transform:uppercase;'>25% Intermedio</div>"
                            f"<div style='font-size:1rem;font-weight:800;color:#fff;margin-top:2px;'>{_fmt_p(_pago25a)}</div></div>"
                            f"<div style='background:rgba(255,255,255,0.08);border-radius:8px;padding:10px 12px;'>"
                            f"<div style='font-size:0.6rem;color:rgba(255,255,255,0.5);font-weight:700;text-transform:uppercase;'>25% Final</div>"
                            f"<div style='font-size:1rem;font-weight:800;color:#fff;margin-top:2px;'>{_fmt_p(_pago25b)}</div></div>"
                            f"</div></div>", unsafe_allow_html=True)

                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                    _, _gen_col, _ = st.columns([2, 3, 2])
                    with _gen_col:
                        _generar = st.button("Generar y descargar contrato PDF", icon=":material/picture_as_pdf:",
                                             type="primary", use_container_width=True, key="cont_generar")
                    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

                    if _generar:
                        if not _PDF_OK:
                            st.error("El m&#243;dulo de generaci&#243;n de PDF no est&#225; disponible en esta instalaci&#243;n modular.")
                        else:
                            _modelo_check = _cot.get("modelo_predefinido") or st.session_state.get('modelo_base') or None
                            if _modelo_check:
                                try:
                                    _todas_check = supa_admin.table("plantillas_contrato").select("modelos").eq("activa", True).execute()
                                    _modelo_asignado = any(
                                        _modelo_check in (_p.get("modelos") or [])
                                        for _p in (_todas_check.data or [])
                                    )
                                except Exception:
                                    _modelo_asignado = True
                                if not _modelo_asignado:
                                    st.warning(f"El modelo **{_modelo_check}** no tiene plantilla de contrato asignada.")
                                    st.stop()
                            if not _usar_juridica and (not _tratamiento or "Selecciona" in str(_tratamiento)):
                                st.error("Debes seleccionar un tratamiento antes de generar el contrato.")
                                st.stop()
                            if _usar_juridica:
                                # Modo empresa: requiere datos de la empresa + domicilio.
                                _campos_req = [_cli_empresa, _cli_rut_empresa, _cli_dom, _cli_com,
                                               _ep_nombre.replace("&#8212;", "")]
                            else:
                                _campos_req = [_cli_nombre, _cli_rut, _cli_dom, _cli_com,
                                               _ep_nombre.replace("&#8212;", "")]
                                if _es_juridica:
                                    _campos_req += [_cli_empresa, _cli_rut_empresa]
                            if not all(_campos_req):
                                st.error("Faltan datos obligatorios del cliente o domicilio.")
                            else:
                                with st.spinner("Generando contrato..."):
                                    _datos_contrato = {
                                        "fecha_str": _fecha_str,
                                        "tipo_cliente": "empresa" if _usar_juridica else ("juridica" if _es_juridica else "natural"),
                                        "cli_tratamiento": "" if _usar_juridica else _tratamiento,
                                        "cli_nombre": _cli_nombre,
                                        "cli_rut": _cli_rut,
                                        "cli_empresa": _cli_empresa,
                                        "cli_rut_empresa": _cli_rut_empresa,
                                        "cli_domicilio": _cli_dom,
                                        "cli_comuna": _cli_com,
                                        "cli_region": _cli_reg,
                                        "inst_domicilio": _inst_dom,
                                        "inst_comuna": _inst_com,
                                        "inst_region": _inst_reg,
                                        "ep_numero": _ep_num,
                                        "ep_nombre": _ep_nombre,
                                        "precio_total": _precio,
                                        "plazo_dias": int(_plazo),
                                        "pago_50": _pago50,
                                        "pago_25a": _pago25a,
                                        "pago_25b": _pago25b,
                                    }
                                    try:
                                        _cls_activas = _obtener_clausulas_contrato(
                                            _cot.get("modelo_predefinido") or st.session_state.get('modelo_base'),
                                            supa_admin
                                        )
                                        _pdf_bytes = generar_pdf_contrato(_datos_contrato, clausulas_externas=_cls_activas)
                                        _pdf_nom = f"Contrato_{_ep_num.replace('-','_')}.pdf"
                                        try:
                                            supa_admin.table("cotizaciones").update({
                                                "contrato_generado": True,
                                                "contrato_datos": json.dumps(_datos_contrato, ensure_ascii=False),
                                                "contrato_fecha": _datos_contrato["fecha_str"],
                                            }).eq("numero", _ep_num).execute()
                                        except Exception:
                                            pass
                                        import base64 as _b64
                                        _b64_pdf = _b64.b64encode(_pdf_bytes).decode()
                                        st.markdown(
                                            f'<a href="data:application/pdf;base64,{_b64_pdf}"'
                                            f' download="{_pdf_nom}"'
                                            f' style="display:inline-block;background:#0f3460;color:white;'
                                            f'padding:10px 24px;border-radius:8px;font-weight:700;'
                                            f'font-size:0.9rem;text-decoration:none;margin-top:8px;">'
                                            f'{_svg_ic("download", 15, color="white", mr=6)}Descargar contrato PDF</a>',
                                            unsafe_allow_html=True)
                                        st.success("Contrato generado exitosamente.")
                                    except Exception as _e:
                                        st.error(f"Error al generar PDF: {_e}")
            else:
                st.info("Ingresa un n&#250;mero EP y presiona **Buscar EP** para cargar los datos.")

    # ================================================================
    # SUB-PESTAÑA: PREVISUALIZAR
    # ================================================================
    with _sub_preview:
        st.markdown(f'<div class="cont-section">{_svg_ic("search", 17)}Buscar cotizaci&#243;n para previsualizar</div>', unsafe_allow_html=True)
        _col_ep_pv, _col_btn_pv = st.columns([3, 1])
        with _col_ep_pv:
            _ep_pv = st.text_input("N&#176; EP", placeholder="Ej: EP-12345",
                                   key="prev_ep_input", label_visibility="collapsed")
        with _col_btn_pv:
            _buscar_pv = st.button("Buscar EP", icon=":material/search:", use_container_width=True, key="prev_buscar")

        if _buscar_pv and _ep_pv:
            _cot_pv = _cargar_cotizacion(_ep_pv.strip().upper(), supa_admin)
            if _cot_pv:
                st.session_state["prev_cot"] = _cot_pv
                st.session_state["prev_ep"]  = _ep_pv.strip().upper()
                st.rerun()
            else:
                st.error(f"No se encontr&#243; {_ep_pv}")

        if st.session_state.get("prev_cot"):
            _cot_pv    = st.session_state["prev_cot"]
            _ep_pv_num = st.session_state["prev_ep"]
            _cli_pv    = _cot_pv.get("cliente_nombre", "&#8212;")
            _total_pv  = _cot_pv.get("total_total", 0) or 0
            _proy_pv   = _cot_pv.get("proyecto_observaciones", "") or "&#8212;"
            _fmt_pv    = lambda v: "${:,.0f}".format(v).replace(",", ".")

            st.success(f"**{_ep_pv_num}** &#8212; {_cli_pv} &middot; {_proy_pv} &middot; {_fmt_pv(_total_pv)}")

            if not _cot_pv.get("contrato_generado"):
                st.warning("Este EP a&#250;n no tiene contrato generado. Genera el contrato desde **Generador** primero.")
            elif not _PDF_OK:
                st.warning("El m&#243;dulo de generaci&#243;n de PDF no est&#225; disponible.")
            else:
                with st.spinner("Generando vista previa..."):
                    try:
                        import base64 as _b64pv
                        import io as _iopv
                        try:
                            from pypdf import PdfWriter as _PdfWriter, PdfReader as _PdfReader
                        except ImportError:
                            from PyPDF2 import PdfWriter as _PdfWriter, PdfReader as _PdfReader

                        _datos_pv = {}
                        try:
                            _raw = _cot_pv.get("contrato_datos", "{}")
                            _datos_pv = json.loads(_raw) if isinstance(_raw, str) else (_raw or {})
                        except Exception:
                            pass

                        _cls_pv = _obtener_clausulas_contrato(_cot_pv.get("modelo_predefinido"), supa_admin)
                        _pdf_contrato = generar_pdf_contrato(_datos_pv, clausulas_externas=_cls_pv)

                        _pdf_presupuesto = None
                        try:
                            _pdata = preparar_pdf_data(_cot_pv)
                            _pdf_presupuesto, _ = generar_pdf_completo(
                                _pdata[0], _pdata[1], _pdata[2], _pdata[3],
                                _pdata[4], _pdata[6], _pdata[7], _pdata[8],
                                _pdata[5], margen=_pdata[9],
                                numero_cotizacion=_ep_pv_num
                            )
                        except Exception as _ep2:
                            st.warning(f"No se pudo generar el presupuesto PDF: {_ep2}")

                        _pdf_plano = None
                        _plano_url = _cot_pv.get("plano_url", "") or ""
                        if _plano_url:
                            try:
                                import urllib.request as _urlreq
                                with _urlreq.urlopen(_plano_url) as _resp:
                                    _pdf_plano = _resp.read()
                            except Exception as _ep3:
                                st.warning(f"No se pudo cargar el plano: {_ep3}")

                        # Generar páginas de anexo con reportlab
                        _pdf_anexo1 = None
                        _pdf_anexo2 = None
                        try:
                            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
                            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                            from reportlab.lib.pagesizes import A4
                            from reportlab.lib import colors
                            from reportlab.lib.units import cm as _cm
                            from reportlab.lib.enums import TA_JUSTIFY
                            import os as _os_anx

                            _AZUL   = colors.HexColor('#0f3460')
                            _AZUL_LT = colors.HexColor('#e8eef7')
                            _GRIS   = colors.HexColor('#64748b')

                            def _generar_anexo_pdf(numero, texto):
                                from reportlab.lib.utils import ImageReader as _ImgReader

                                def _hf_anx(canvas, doc):
                                    canvas.saveState()
                                    _pw = doc.pagesize[0]; _ph = doc.pagesize[1]
                                    if _os_anx.path.exists("logo.png"):
                                        _img = _ImgReader("logo.png")
                                        _iw, _ih = _img.getSize()
                                        _lw = 4.5 * _cm
                                        _lh = _lw * (_ih / float(_iw))
                                        canvas.drawImage(_img, x=(_pw-_lw)/2, y=_ph-doc.topMargin+0.3*_cm,
                                                         width=_lw, height=_lh, preserveAspectRatio=True, mask='auto')
                                    canvas.setStrokeColor(_AZUL); canvas.setLineWidth(1.2)
                                    canvas.line(doc.leftMargin, _ph-doc.topMargin+0.1*_cm,
                                                _pw-doc.rightMargin, _ph-doc.topMargin+0.1*_cm)
                                    _fy = doc.bottomMargin - 0.5*_cm
                                    canvas.setStrokeColor(_GRIS); canvas.setLineWidth(0.4)
                                    canvas.line(doc.leftMargin, _fy+0.35*_cm, _pw-doc.rightMargin, _fy+0.35*_cm)
                                    canvas.setFont('Helvetica', 8); canvas.setFillColor(_GRIS)
                                    canvas.drawCentredString(_pw/2, _fy,
                                        f"Inversiones Container House SpA  ·  RUT 78.268.851-0  ·  Página {doc.page}")
                                    canvas.restoreState()

                                _buf_anx = _iopv.BytesIO()
                                _doc_anx = SimpleDocTemplate(_buf_anx, pagesize=A4,
                                    leftMargin=3*_cm, rightMargin=3*_cm,
                                    topMargin=3.8*_cm, bottomMargin=2.2*_cm)
                                _base = getSampleStyleSheet()
                                _st_sec = ParagraphStyle(f'AxSec{numero}', parent=_base['Normal'],
                                    fontName='Helvetica-Bold', fontSize=9.5, leading=13,
                                    spaceBefore=14, spaceAfter=5, textColor=colors.white,
                                    backColor=_AZUL, leftIndent=-0.3*_cm, rightIndent=-0.3*_cm,
                                    borderPadding=(4,8,4,8))
                                _st_norm = ParagraphStyle(f'AxNorm{numero}', parent=_base['Normal'],
                                    fontName='Times-Roman', fontSize=12.5, leading=19,
                                    spaceAfter=6, alignment=TA_JUSTIFY, firstLineIndent=0)
                                _story = [
                                    Spacer(1, 0.5*_cm),
                                    Paragraph(f"ANEXO Nº{numero}", _st_sec),
                                    Spacer(1, 0.4*_cm),
                                    HRFlowable(width="100%", thickness=0.6, color=_AZUL_LT, spaceAfter=8, spaceBefore=2),
                                    Paragraph(texto, _st_norm),
                                ]
                                _doc_anx.build(_story, onFirstPage=_hf_anx, onLaterPages=_hf_anx)
                                return _buf_anx.getvalue()

                            if _pdf_plano:
                                _pdf_anexo1 = _generar_anexo_pdf(1,
                                    "En el presente Anexo N°1 se incorpora el plano del proyecto a construir, "
                                    "el cual se entiende formar parte integrante, esencial e inseparable del presente contrato.")
                            if _pdf_presupuesto:
                                _pdf_anexo2 = _generar_anexo_pdf(2,
                                    "En el presente Anexo N°2 se incorpora la lista de materiales correspondiente "
                                    "a la cotización, la cual se entiende formar parte integrante e inseparable del presente contrato.")
                        except Exception:
                            pass

                        # Normalizar a A4 con PyMuPDF si disponible
                        try:
                            import fitz as _fitz_pv

                            def _norm_a4(data):
                                if not data:
                                    return None
                                _raw = data if isinstance(data, bytes) else data.getvalue()
                                _src = _fitz_pv.open(stream=_raw, filetype="pdf")
                                _dst = _fitz_pv.open()
                                _W, _H = 595, 842
                                _M = 20
                                for _pg in _src:
                                    _np = _dst.new_page(width=_W, height=_H)
                                    _r = _pg.rect
                                    _s = min((_W-2*_M)/max(_r.width,1), (_H-2*_M)/max(_r.height,1))
                                    _nw, _nh = _r.width*_s, _r.height*_s
                                    _x0 = (_W-_nw)/2; _y0 = (_H-_nh)/2
                                    _np.show_pdf_page(_fitz_pv.Rect(_x0,_y0,_x0+_nw,_y0+_nh), _src, _pg.number)
                                _out = _iopv.BytesIO(); _dst.save(_out); return _out.getvalue()
                        except ImportError:
                            _norm_a4 = lambda x: x if isinstance(x, bytes) else (x.getvalue() if x else None)

                        _writer = _PdfWriter()

                        def _add(data):
                            if not data:
                                return
                            _n = _norm_a4(data)
                            if not _n:
                                return
                            for _page in _PdfReader(_iopv.BytesIO(_n)).pages:
                                _writer.add_page(_page)

                        _add(_pdf_contrato)
                        if _pdf_plano:
                            _add(_pdf_anexo1)
                            _add(_pdf_plano)
                        if _pdf_presupuesto:
                            _add(_pdf_anexo2)
                            _add(_pdf_presupuesto)

                        _combined_buf = _iopv.BytesIO()
                        _writer.write(_combined_buf)
                        _combined_bytes = _combined_buf.getvalue()

                        _prev_url = None
                        _nom_tmp = f"preview_{_ep_pv_num.replace('-','_')}.pdf"
                        try:
                            try:
                                supabase.storage.from_("planos").remove([f"preview/{_nom_tmp}"])
                            except Exception:
                                pass
                            supabase.storage.from_("planos").upload(
                                f"preview/{_nom_tmp}", _combined_bytes,
                                {"content-type": "application/pdf", "upsert": "true"}
                            )
                            _prev_url = supabase.storage.from_("planos").get_public_url(f"preview/{_nom_tmp}")
                        except Exception as _eu:
                            st.warning(f"No se pudo subir preview: {_eu}")

                        if _prev_url:
                            _nav_pv = _detectar_navegador()
                            _enc_pv = urllib.parse.quote(_prev_url, safe='')
                            _goog_pv = f"https://docs.google.com/viewer?url={_enc_pv}&embedded=true"
                            components.html(_pdf_visor_html(_prev_url, _goog_pv, _nav_pv['needs_google_viewer'],
                                                            spinner_msg="Cargando contrato completo..."), height=710, scrolling=False)

                        _dc1, _dc2, _dc3 = st.columns([1, 2, 1])
                        with _dc2:
                            st.download_button(
                                label="Descargar contrato completo", icon=":material/download:",
                                data=_combined_bytes,
                                file_name=f"ContratoCompleto_{_ep_pv_num.replace('-','_')}.pdf",
                                mime="application/pdf", use_container_width=True, key="dl_contrato_completo"
                            )
                    except Exception as _epv_err:
                        st.error(f"Error generando vista previa: {_epv_err}")
        else:
            st.info("Ingresa un n&#250;mero EP y presiona **Buscar EP** para previsualizar el contrato.")

    # ================================================================
    # SUB-PESTAÑA: CONTRATO NOTARIADO
    # ================================================================
    if _sub_notariado is not None:
        with _sub_notariado:
            st.markdown(f'<div class="cont-section">{_svg_ic("file", 17)}Contratos notariales</div>', unsafe_allow_html=True)

            _cn_c1, _cn_c2 = st.columns([3, 0.8])
            with _cn_c1:
                _cn_ep = st.text_input("Buscar", placeholder="Buscar por N° EP...",
                                       key="cn_ep", label_visibility="collapsed")
            with _cn_c2:
                _cn_buscar = st.button("Buscar", icon=":material/search:", use_container_width=True, key="cn_buscar")

            if _cn_buscar or 'cn_results' not in st.session_state:
                try:
                    _cn_q = supa_admin.table("cotizaciones").select(
                        "numero,cliente_nombre,asesor_nombre,fecha_modificacion,"
                        "config_margen,plano_url,contrato_notariado_url,contrato_notariado_nombre,"
                        "fecha_adjudicacion"
                    )
                    if _cn_ep.strip():
                        _cn_q = _cn_q.ilike("numero", f"%{_cn_ep.strip()}%")
                    else:
                        _cn_q = _cn_q.gt("config_margen", 0)
                    _cn_resp = _cn_q.order("fecha_modificacion", desc=True).limit(100).execute()
                    _cn_rows = _cn_resp.data or []
                    if not _cn_ep.strip():
                        _cn_rows = [r for r in _cn_rows if (r.get('config_margen') or 0) > 0]
                    st.session_state['cn_results'] = _cn_rows
                except Exception as _cne:
                    st.error(f"Error: {_cne}")
                    st.session_state['cn_results'] = []

            _cn_data = st.session_state.get('cn_results', [])

            if not _cn_data:
                st.info("No hay presupuestos autorizados o adjudicados.")
            else:
                _cn_n_adj  = sum(1 for r in _cn_data if r.get('contrato_notariado_url'))
                _cn_n_pend = len(_cn_data) - _cn_n_adj
                st.markdown(
                    f"<span style='background:#ede9fe;color:#6d28d9;padding:3px 12px;border-radius:99px;font-size:11px;font-weight:700;margin-right:6px;'>{len(_cn_data)} resultados</span>"
                    f"<span style='background:#dbeafe;color:#1d4ed8;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:700;margin-right:6px;'>{_svg_ic('check', 11, color='#1d4ed8', mr=4)}{_cn_n_adj} adjudicados</span>"
                    f"<span style='background:#fef9c3;color:#854d0e;padding:3px 10px;border-radius:99px;font-size:11px;font-weight:700;'>{_svg_ic('clock', 11, color='#854d0e', mr=4)}{_cn_n_pend} pendiente</span>",
                    unsafe_allow_html=True)
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                import pandas as _pd_cn
                _cn_df = _pd_cn.DataFrame([{
                    'N&#176; EP': r.get('numero', ''),
                    'Cliente': r.get('cliente_nombre', '&#8212;'),
                    'Ejecutivo': r.get('asesor_nombre', '&#8212;'),
                    'Estado': 'ADJUDICADO' if r.get('contrato_notariado_url') else 'PENDIENTE',
                    'Fecha mod.': (r.get('fecha_modificacion', '')[:10] if r.get('fecha_modificacion') else '&#8212;'),
                } for r in _cn_data])
                st.dataframe(_cn_df, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**Selecciona un presupuesto para adjuntar contrato notariado:**")

            _cn_data_adj  = [r for r in (_cn_data or []) if r.get("contrato_notariado_url")]
            _cn_data_pend = [r for r in (_cn_data or []) if not r.get("contrato_notariado_url")]
            _cn_opts = (
                [f"ADJ · {r['numero']} · {r.get('cliente_nombre','')}" for r in _cn_data_adj] +
                [f"PEND · {r['numero']} · {r.get('cliente_nombre','')}" for r in _cn_data_pend]
            )
            if not _cn_opts:
                st.info("No hay presupuestos disponibles.")
            else:
                _cn_sel = st.selectbox("EP", _cn_opts, key="cn_sel_ep", label_visibility="collapsed")
                _cn_ep_sel = _cn_sel.split(" · ")[1].strip()
                _cn_row = next((r for r in (_cn_data or []) if r.get("numero") == _cn_ep_sel), None)

                if _cn_row:
                    _cn_ya_adj = bool(_cn_row.get("contrato_notariado_url"))
                    _cot_cn_full = _cargar_cotizacion(_cn_ep_sel, supa_admin)

                    if _cn_ya_adj:
                        _not_url = _cn_row["contrato_notariado_url"]
                        _nav_cn  = _detectar_navegador()
                        _enc_cn  = urllib.parse.quote(_not_url, safe='')
                        _goog_cn = f"https://docs.google.com/viewer?url={_enc_cn}&embedded=true"
                        components.html(_pdf_visor_html(_not_url, _goog_cn, _nav_cn['needs_google_viewer'],
                                                        spinner_msg="Cargando contrato notariado..."), height=710, scrolling=False)
                        if _REQUESTS_OK:
                            try:
                                _bytes_dl = _requests.get(_not_url, timeout=15).content
                                _dc1n, _dc2n, _dc3n = st.columns([1, 2, 1])
                                with _dc2n:
                                    st.download_button("Descargar contrato notariado", icon=":material/download:",
                                        data=_bytes_dl,
                                        file_name=_cn_row.get("contrato_notariado_nombre", "contrato_notariado.pdf"),
                                        mime="application/pdf", use_container_width=True, key="cn_dl_not")
                            except Exception:
                                st.warning("No se pudo preparar la descarga.")
                        st.success(f"{_cn_ep_sel} &#8212; ADJUDICADO")
                    else:
                        _cn_tiene_contrato = bool(_cot_cn_full and _cot_cn_full.get('contrato_generado'))
                        if not _cn_tiene_contrato:
                            st.error("No se puede adjuntar el contrato notariado porque este EP a&#250;n no tiene contrato generado. Ve a **Generador** primero.", icon=":material/lock:")
                        else:
                            st.markdown(f"""
                            <div style="background:#eff6ff;border-left:4px solid #2563eb;border-radius:0 8px 8px 0;
                                        padding:10px 14px;margin-bottom:12px;">
                              <p style="font-size:12px;color:#1e40af;margin:0;">{_svg_ic('file', 13, color='#1e40af', mr=5)}Sube el PDF firmado y notariado.
                              Una vez subido el estado cambia a <b>{_svg_ic('check', 13, color='#1d4ed8', mr=4)}ADJUDICADO</b> &#8212; acci&#243;n permanente e irreversible.</p>
                            </div>
                            """, unsafe_allow_html=True)
                            _cn_file = st.file_uploader("PDF del contrato notariado",
                                                        type=["pdf"], key=f"cn_upload_{_cn_ep_sel}")
                            if _cn_file is not None:
                                st.markdown(f"**{_cn_file.name}** &middot; {round(_cn_file.size/1024)} KB")
                                if st.button("Adjuntar y marcar como ADJUDICADO", icon=":material/upload_file:",
                                             type="primary", use_container_width=True, key="cn_btn_adj"):
                                    with st.spinner("Subiendo..."):
                                        try:
                                            _cn_bytes  = _cn_file.read()
                                            _cn_nombre = _cn_file.name
                                            _cn_path   = f"notariados/{_cn_ep_sel}/{_cn_nombre}"
                                            supa_admin.storage.from_("planos").upload(
                                                _cn_path, _cn_bytes,
                                                {"content-type": "application/pdf", "upsert": "true"}
                                            )
                                            _cn_url = supa_admin.storage.from_("planos").get_public_url(_cn_path)
                                            _fecha_adj = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                                            supa_admin.table("cotizaciones").update({
                                                "contrato_notariado_url": _cn_url,
                                                "contrato_notariado_nombre": _cn_nombre,
                                                "fecha_adjudicacion": _fecha_adj,
                                                "estado": "ADJUDICADO"
                                            }).eq("numero", _cn_ep_sel).execute()
                                            st.success(f"{_cn_ep_sel} ahora es ADJUDICADO")
                                            st.session_state.pop('cn_results', None)
                                            st.rerun()
                                        except Exception as _cne2:
                                            st.error(f"Error: {_cne2}")

    # ================================================================
    # SUB-PESTAÑA: EDITAR CONTRATO
    # ================================================================
    if _sub_editar is not None:
        with _sub_editar:
            if not st.session_state.get('modo_admin'):
                st.info("Solo administradores pueden editar la plantilla global del contrato.", icon=":material/lock:")
            else:
                _CLAUSULAS_BASE = {
                    "intro":                 "En Santiago de Chile, a {{FECHA}}, comparecen:",
                    "comparecencia_cliente": "{{TRATAMIENTO}} {{CLIENTE}}, cédula nacional de identidad N° {{RUT_CLIENTE}}, con domicilio en {{DOMICILIO_CLIENTE}}, comuna de {{COMUNA_CLIENTE}}, Región {{REGION_CLIENTE}}, quien en adelante se denominará \"el Cliente\".",
                    "definiciones":          "a) Proyecto: La vivienda tipo container identificada como Proyecto N° {{EP}} – \"{{EP_NOMBRE}}\".",
                    "objeto":                "El Cliente encarga al Proveedor la fabricación y venta del Proyecto conforme a los planos entregados, las especificaciones técnicas, y al presupuesto detallado contenido en el Anexo N°2.",
                    "alcance":               "El Proveedor declara contar con la experiencia, conocimientos técnicos, personal calificado, herramientas e infraestructura necesarias para la correcta ejecución del Proyecto.",
                    "visitas":               "El Cliente podrá realizar visitas de seguimiento a las instalaciones del Proveedor ubicadas en Portezuelo, parcela 3, Colina, Región Metropolitana, previa coordinación con al menos 48 horas hábiles de anticipación.",
                    "precio":                "El precio total del Proyecto asciende a la suma de {{TOTAL}} ({{TOTAL_PALABRAS}}), IVA incluido.",
                    "forma_pago":            "El precio será pagado en las siguientes etapas:\na) 50% inicial: {{PAGO_50}}\nb) 25% intermedio: {{PAGO_25A}}\nc) 25% final: {{PAGO_25B}}",
                    "inicio":                "La fabricación del Proyecto se iniciará única y exclusivamente una vez recibido y efectivamente abonado el pago inicial del 50% del valor total del contrato.",
                    "plazo":                 "El plazo máximo de fabricación y entrega será de {{PLAZO}} días hábiles administrativos.",
                    "penalidad":             "En caso de atraso imputable exclusivamente al Proveedor, éste pagará al Cliente una suma equivalente al 1% del valor neto correspondiente al último 25% del Proyecto por cada 7 días hábiles de atraso, con un tope máximo del 10%.",
                    "bodegaje":              "Una vez notificada la finalización del Proyecto, el Cliente dispondrá de un plazo máximo de 10 días hábiles para coordinar el retiro o despacho del módulo.",
                    "garantia":              "El Proveedor otorga una garantía de 6 meses contados desde la entrega del módulo, limitada exclusivamente a defectos de fabricación o construcción imputables al proceso productivo.",
                    "terminacion":           "El presente contrato podrá terminarse anticipadamente por incumplimiento grave, mutuo acuerdo por escrito, o no pago oportuno de cualquiera de las etapas de pago.",
                    "jurisdiccion":          "Para todos los efectos legales derivados del presente contrato, las partes fijan su domicilio en la ciudad de Santiago y se someten a la competencia de sus Tribunales Ordinarios de Justicia.",
                    "suministro_energia":    "",
                    "firma":                 "El presente contrato se firma en dos ejemplares de igual tenor y fecha, quedando uno en poder de cada parte.",
                }
                _LABELS_READONLY = {"definiciones", "medios_pago"}
                _LABELS = {
                    "intro":                 "Introducción",
                    "comparecencia_cliente": "I. Comparecencia — El Cliente",
                    "definiciones":          "II. Definiciones (solo lectura)",
                    "objeto":                "III. Objeto del contrato",
                    "alcance":               "IV. Alcance técnico",
                    "visitas":               "V. Visitas y seguimiento",
                    "precio":                "VI. Precio",
                    "forma_pago":            "VII. Forma de pago",
                    "inicio":                "VIII. Inicio de fabricación",
                    "medios_pago":           "IX. Medios de pago (solo lectura)",
                    "plazo":                 "X. Plazo",
                    "penalidad":             "XI. Penalidad por atraso",
                    "bodegaje":              "XII. Retiro y bodegaje",
                    "garantia":              "XIII. Garantía",
                    "terminacion":           "XIV. Terminación anticipada",
                    "jurisdiccion":          "XV. Domicilio y jurisdicción",
                    "suministro_energia":    "XVI. Suministro de energía eléctrica",
                    "firma":                 "XVII. Firma",
                }

                def _cargar_plantilla_activa(tipo='A'):
                    try:
                        _res = supa_admin.table("plantillas_contrato").select("*").eq("activa", True).eq("tipo", tipo).execute()
                        return _res.data[0] if _res.data else None
                    except Exception:
                        return None

                def _cargar_historial(tipo=None):
                    try:
                        _q = supa_admin.table("plantillas_contrato").select("*").order("version", desc=True)
                        if tipo:
                            _q = _q.eq("tipo", tipo)
                        return _q.execute().data or []
                    except Exception:
                        return []

                def _guardar_plantilla(clausulas_dict, usuario, tipo='A', modelos_lista=None):
                    try:
                        supa_admin.table("plantillas_contrato").update({"activa": False}).eq("tipo", tipo).execute()
                        _hist_all = _cargar_historial()
                        _next_v = (_hist_all[0]["version"] + 1) if _hist_all else 2
                        supa_admin.table("plantillas_contrato").insert({
                            "version":    _next_v,
                            "nombre":     f"Plantilla {tipo} v{_next_v}",
                            "clausulas":  clausulas_dict,
                            "activa":     True,
                            "creado_por": usuario,
                            "tipo":       tipo,
                            "modelos":    modelos_lista or [],
                        }).execute()
                        return True
                    except Exception as _e:
                        return str(_e)

                def _activar_plantilla(pid, tipo='A'):
                    try:
                        supa_admin.table("plantillas_contrato").update({"activa": False}).eq("tipo", tipo).execute()
                        supa_admin.table("plantillas_contrato").update({"activa": True}).eq("id", pid).execute()
                        return True
                    except Exception:
                        return False

                _historial_all = _cargar_historial()
                if not _historial_all:
                    try:
                        supa_admin.table("plantillas_contrato").insert({
                            "version": 1, "nombre": "Plantilla A v1 — original sistema",
                            "clausulas": _CLAUSULAS_BASE, "activa": True,
                            "creado_por": "Sistema", "tipo": "A", "modelos": [],
                        }).execute()
                    except Exception:
                        pass

                _hojas_modelo_ed = [h for h in _leer_hojas_disponibles() if h.lower().startswith("modelo")]
                try:
                    _todas_activas = supa_admin.table("plantillas_contrato").select("tipo,modelos").eq("activa", True).execute()
                    _modelos_por_tipo = {'A': [], 'B': [], 'E': []}
                    for _pa in (_todas_activas.data or []):
                        _t = _pa.get('tipo') or 'A'
                        if _t in _modelos_por_tipo:
                            _modelos_por_tipo[_t] = list(_pa.get('modelos') or [])
                except Exception:
                    _modelos_por_tipo = {'A': [], 'B': [], 'E': []}

                st.markdown(f"""
                <div style='background:#e8eef7;border:1px solid #0f3460;border-radius:10px;
                            padding:12px 16px;margin-bottom:16px;font-size:13px;color:#0f3460;'>
                <strong>{_svg_ic('warning', 14, color='#0f3460', mr=5)}Plantillas</strong> &#8212;
                <b>Plantilla A</b> para modelos &#8804;30m&#178; &middot;
                <b>Plantilla B</b> para modelos &gt;30m&#178; &middot;
                <b>Plantilla Especial</b> para clientes especiales.
                </div>
                """, unsafe_allow_html=True)

                _tab_plt_a, _tab_plt_b, _tab_plt_e = st.tabs([
                    ":material/article: Plantilla A — ≤30m²",
                    ":material/article: Plantilla B — >30m²",
                    ":material/star: Plantilla Especial",
                ])

                def _render_editor_plantilla(tipo_plt, key_pfx):
                    _plt_activa = _cargar_plantilla_activa(tipo_plt)
                    _cls_act    = _plt_activa["clausulas"] if _plt_activa else _CLAUSULAS_BASE
                    _mods_act   = list(_plt_activa.get("modelos") or []) if _plt_activa else []

                    _ocupados = set()
                    for _ot in ('A', 'B', 'E'):
                        if _ot == tipo_plt:
                            continue
                        for _m in _modelos_por_tipo.get(_ot, []):
                            _ocupados.add(_m)
                        for _m in st.session_state.get(f"plt_{_ot.lower()}_modelos_sel", []):
                            _ocupados.add(_m)

                    _disponibles = [m for m in _hojas_modelo_ed if m not in _ocupados or m in _mods_act]

                    st.markdown(":material/link: **Modelos asociados a esta plantilla:**")
                    _mods_sel = st.multiselect(
                        "Modelos", options=_disponibles,
                        default=[m for m in _mods_act if m in _disponibles],
                        key=f"{key_pfx}_modelos_sel",
                        label_visibility="collapsed",
                        placeholder="Selecciona los modelos que usan esta plantilla...",
                    )
                    st.markdown("<div style='margin-bottom:8px'></div>", unsafe_allow_html=True)

                    _edits = {}
                    for _key, _label in _LABELS.items():
                        if _key == 'suministro_energia' and tipo_plt == 'A':
                            continue
                        if _key == 'bodegaje' and tipo_plt == 'E':
                            continue
                        _val = _cls_act.get(_key, _CLAUSULAS_BASE.get(_key, ""))
                        _h   = max(120, (_val.count("\n") + max(1, len(_val) // 85)) * 22)
                        if _key in _LABELS_READONLY:
                            st.markdown(
                                f'<div style="background:#1e3a5f;color:white;font-size:0.78rem;font-weight:900;'
                                f'text-transform:uppercase;letter-spacing:0.08em;padding:8px 14px;'
                                f'border-radius:8px 8px 0 0;">{_svg_ic("lock", 12, color="white", mr=5)}{_label.upper()}</div>',
                                unsafe_allow_html=True)
                            st.markdown(
                                f'<div style="background:#fff5f5;border:1.5px solid #dc2626;border-top:none;'
                                f'border-radius:0 0 8px 8px;padding:14px 16px;margin-bottom:16px;">'
                                f'<div style="font-size:13px;line-height:1.7;color:#7f1d1d;">'
                                f'{_val.replace(chr(10),"<br>")}</div></div>',
                                unsafe_allow_html=True)
                            _edits[_key] = _val
                        else:
                            st.markdown(
                                f'<div style="background:#1e3a5f;color:white;font-size:0.78rem;font-weight:900;'
                                f'text-transform:uppercase;letter-spacing:0.08em;padding:8px 14px;'
                                f'border-radius:8px 8px 0 0;">{_label.upper()}</div>',
                                unsafe_allow_html=True)
                            _edits[_key] = st.text_area("Texto del campo", value=_val, height=_h,
                                                         key=f"{key_pfx}_plt_{_key}",
                                                         label_visibility="collapsed")
                            st.markdown("<div style='margin-bottom:12px;'></div>", unsafe_allow_html=True)

                    _bc1, _bc2, _bc3 = st.columns([2, 2, 2])
                    with _bc1:
                        if st.button("Restaurar original", icon=":material/undo:", use_container_width=True, key=f"{key_pfx}_restaurar"):
                            for _k in _LABELS:
                                _sk = f"{key_pfx}_plt_{_k}"
                                if _sk in st.session_state:
                                    st.session_state[_sk] = _CLAUSULAS_BASE.get(_k, "")
                            st.rerun()
                    with _bc3:
                        if st.button("Guardar nueva versión", icon=":material/save:", type="primary",
                                     use_container_width=True, key=f"{key_pfx}_guardar"):
                            import re as _re
                            _strip = lambda t: _re.sub(r'<[^>]+>', '', t).strip()
                            _cambios = {k: v for k, v in _edits.items()
                                        if _strip(v) != _strip(_CLAUSULAS_BASE.get(k, ""))}
                            if not _cambios and set(_mods_sel) == set(_mods_act):
                                st.warning("No hay cambios en cláusulas ni en modelos asignados.")
                            else:
                                _cls_guardar = {k: v for k, v in _edits.items() if v.strip()}
                                _usr = st.session_state.get("auth_nombre", "") or st.session_state.get("auth_email", "Sistema")
                                _res = _guardar_plantilla(_cls_guardar, _usr, tipo=tipo_plt, modelos_lista=_mods_sel)
                                if _res is True:
                                    st.success(f"Plantilla {tipo_plt} guardada.")
                                    st.rerun()
                                else:
                                    st.error(f"Error: {_res}")

                    st.markdown("---")
                    st.markdown(f":material/history: **Historial — Plantilla {tipo_plt}:**")
                    for _plt in _cargar_historial(tipo=tipo_plt):
                        _es_activa = _plt.get("activa", False)
                        _creador   = _plt.get("creado_por", "—")
                        _fecha_p   = (_plt.get("fecha_creacion", "")[:16].replace("T", " ")
                                      if _plt.get("fecha_creacion") else "—")
                        _version   = _plt.get("nombre", f"v{_plt.get('version','?')}")
                        _bg  = "#e8eef7" if _es_activa else "var(--color-background-primary)"
                        _brd = "1.5px solid #0f3460" if _es_activa else "0.5px solid var(--color-border-tertiary)"
                        _badge = (f'<span style="background:#0f3460;color:white;border-radius:20px;padding:4px 14px;font-size:11px;font-weight:700;">{_svg_ic("check", 11, color="white", mr=4)}ACTIVA</span>'
                                  if _es_activa else '<span style="font-size:11px;color:#94a3b8;">inactiva</span>')
                        st.markdown(
                            f'<div style="background:{_bg};border:{_brd};border-radius:12px;'
                            f'padding:14px 18px;display:flex;justify-content:space-between;'
                            f'align-items:center;margin-bottom:8px;">'
                            f'<div><div style="font-size:14px;font-weight:700;color:#0f3460;">{_version}</div>'
                            f'<div style="font-size:12px;color:#64748b;">{_creador} &middot; {_fecha_p}</div></div>'
                            f'{_badge}</div>',
                            unsafe_allow_html=True)
                        if not _es_activa:
                            _col_act, _ = st.columns([1, 3])
                            with _col_act:
                                if st.button(f"Activar {_version}",
                                             key=f"{key_pfx}_act_{_plt['id']}", use_container_width=True):
                                    if _activar_plantilla(_plt["id"], tipo=tipo_plt):
                                        st.success(f"{_version} activada.")
                                        st.rerun()

                with _tab_plt_a:
                    _render_editor_plantilla('A', 'plt_a')
                with _tab_plt_b:
                    _render_editor_plantilla('B', 'plt_b')
                with _tab_plt_e:
                    _render_editor_plantilla('E', 'plt_e')
