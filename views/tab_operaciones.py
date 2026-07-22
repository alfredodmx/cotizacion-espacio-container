"""
Tab OPERACIONES — Panel RC (registro compras), acta entrega.
Código fuente original: app.py líneas 14730-15999
"""
import json
import re
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timezone, timedelta, date as _date_cls
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header
from utils.operaciones_db import (
    listar_usuarios_ejecutivos,
    obtener_registros_compra,
    obtener_items_comprados,
    calcular_estado_compras,
    dias_habiles_entre,
    sumar_dias_habiles,
    guardar_acta_en_storage,
    registrar_entrega_proyecto,
)
from repositories.compras_repo import (
    guardar_registro_compra_full,
    eliminar_registro_compra_full,
    actualizar_registro_compra_full,
)
from utils.excel_manager import leer_hoja_excel
from utils.security import escape_html as _esc_html

# ── Importar builders y helpers de utils ────────────────────────────────────

try:
    from utils.operaciones import (
        build_rc_html,
        build_historial_rc_html,
        calcular_totales_rc,
        generar_pdf_balance,
        generar_excel_balance,
    )
    _OPER_OK = True
except ImportError:
    _OPER_OK = False

try:
    from utils.pdf_contrato import generar_pdf_completo, preparar_pdf_data
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

try:
    from utils.telefono import formatear_telefono
except ImportError:
    def formatear_telefono(t): return t or ""

_tz_cl = timezone(timedelta(hours=-3))

# Drawer lateral derecho para el modal "Cargar proyecto" (mismo patrón que la
# pestaña Inventario: st.dialog nativo estilizado como panel derecho). Se inyecta
# solo cuando el loader está abierto.
_RC_LOADER_CSS = """
<style>
div[data-testid="stDialog"] > div{align-items:flex-start!important;justify-content:flex-end!important;}
div[data-testid="stDialog"] div[role="dialog"]{position:fixed!important;top:65px!important;right:0!important;
  left:auto!important;bottom:auto!important;transform:none!important;margin:0!important;
  height:calc(100vh - 65px)!important;max-height:calc(100vh - 65px)!important;background:#fff!important;
  border-radius:0!important;box-shadow:none!important;overflow-y:auto!important;overflow-x:hidden!important;}
div[data-testid="stDialog"] [data-testid="stVerticalBlockBorderWrapper"]{
  background:transparent!important;border:none!important;box-shadow:none!important;border-radius:0!important;}
div[data-testid="stDialog"] div[role="dialog"] > div:first-child{
  font-family:'Montserrat',sans-serif!important;font-weight:700!important;font-size:0.92rem!important;
  letter-spacing:0.05em!important;text-transform:uppercase!important;color:#0f172a!important;}
</style>
"""

# Interceptor del botón "Salir del proyecto": revisa por JS si la tabla del iframe
# tiene datos SIN GUARDAR (window.rcHasData del iframe RC) ANTES del rerun — porque
# el rerun re-renderiza el iframe y pierde lo escrito. Si hay datos → confirma; si
# no → deja pasar el click (Python limpia el proyecto). Bind en el doc padre.
_RC_EXIT_INTERCEPT_JS = """
<script>
(function(){
  var P=window.parent, D=P&&P.document; if(!D) return;
  function rcIframe(){ var ifs=D.querySelectorAll("iframe"); for(var i=0;i<ifs.length;i++){ try{ if(ifs[i].contentWindow && typeof ifs[i].contentWindow.rcHasData==="function") return ifs[i]; }catch(e){} } return null; }
  function hasData(){ var ifr=rcIframe(); if(!ifr) return false; try{ return !!ifr.contentWindow.rcHasData(); }catch(e){ return false; } }
  function confirmExit(onYes){
    var old=D.getElementById("rc-exit-confirm"); if(old) old.remove();
    var ov=D.createElement("div"); ov.id="rc-exit-confirm";
    ov.style.cssText="position:fixed;inset:0;z-index:2147483600;background:rgba(15,23,42,.5);display:flex;align-items:center;justify-content:center;padding:20px;font-family:Montserrat,'Segoe UI',sans-serif;";
    ov.innerHTML='<div style="background:#fff;border-radius:16px;max-width:440px;width:100%;padding:22px 24px;box-shadow:0 24px 60px rgba(0,0,0,.3);">'
      +'<div style="font-weight:800;font-size:1rem;color:#0f172a;margin-bottom:8px;">Cambios sin guardar</div>'
      +'<div style="font-size:.86rem;color:#475569;line-height:1.5;margin-bottom:18px;">Escribiste precios o cantidades en la tabla que <b>no has guardado</b>. Si sales, se perderan. Deseas salir del proyecto de todas formas?</div>'
      +'<div style="display:flex;gap:10px;"><button id="rc-exit-no" style="flex:1;padding:10px;border:1px solid #e2e8f0;border-radius:10px;background:#f1f5f9;color:#334155;font-weight:700;cursor:pointer;">Cancelar</button>'
      +'<button id="rc-exit-yes" style="flex:1;padding:10px;border:none;border-radius:10px;background:#dc2626;color:#fff;font-weight:700;cursor:pointer;">Si, salir</button></div></div>';
    D.body.appendChild(ov);
    D.getElementById("rc-exit-yes").addEventListener("click", function(){ ov.remove(); onYes(); });
    D.getElementById("rc-exit-no").addEventListener("click", function(){ ov.remove(); });
  }
  if(P._rcExitH) D.removeEventListener("click", P._rcExitH, true);
  P._rcExitH=function(ev){
    var t=ev.target; if(!t||!t.closest) return;
    var btn=t.closest(".st-key-_rc_salir_btn button"); if(!btn) return;
    if(P._rcForceExit){ P._rcForceExit=false; return; }
    if(!hasData()) return;
    ev.preventDefault(); ev.stopImmediatePropagation();
    confirmExit(function(){ P._rcForceExit=true; btn.click(); });
  };
  D.addEventListener("click", P._rcExitH, true);
})();
</script>
"""


# ── Iconos SVG (reemplazan emoticones) ───────────────────────────────────────
_ICON_PATHS_OP = {
    "cart":      '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "history":   '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "plus":      '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "chart":     '<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
    "eye":       '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "file":      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    "download":  '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
    "store":     '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M2 7h20"/><path d="M18 12v.01"/><path d="M6 12v.01"/>',
    "check":     '<path d="M20 6 9 17l-5-5"/>',
    "x":         '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "alert":     '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "calendar":  '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "save":      '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "grid":      '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>',
    "package":   '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
    "refresh":   '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
    "search":    '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "trend-down":'<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "trend-up":  '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "user":      '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "clock":     '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
}


def _ic_op(name, color="#0f172a", size=15, mr=8, valign=-2, sw=2):
    """SVG inline (reemplaza emoticones). mr=margin-right en px."""
    inner = _ICON_PATHS_OP.get(name, "")
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="vertical-align:{valign}px;margin-right:{mr}px;flex-shrink:0;">'
        f'{inner}</svg>'
    )


def _titulo_op(icon, texto, color_ic="#0f172a"):
    """Título de sección unificado (Montserrat 700 / 0.88rem / 0.05em / uppercase / #0f172a)."""
    return (
        '<div style="display:flex;align-items:center;font-family:Montserrat,sans-serif;'
        'font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;'
        'color:#0f172a;margin:0 0 12px 0;">'
        + _ic_op(icon, color=color_ic, size=17, mr=9) + f'<span>{texto}</span></div>'
    )


def _norm_prov_key(s):
    """Clave para agrupar variantes del MISMO proveedor: minúsculas + espacios
    colapsados + letras dobles colapsadas (Rener↔RENNER) + 's' final (plural)
    colapsada (servicontainer↔servicontainers)."""
    s = re.sub(r'\s+', ' ', str(s).strip().lower())
    s = re.sub(r'(.)\1+', r'\1', s)
    s = re.sub(r's$', '', s)
    return s


# Alias MANUALES de proveedores: unifican nombres que la normalización automática
# no puede inferir (misma empresa escrita distinto, razón social, abreviaturas).
# clave = variante tal cual se escribió; valor = nombre canónico a MOSTRAR.
# Para agregar otro: añade las variantes con su nombre canónico.
_PROVEEDOR_ALIASES = {
    "MOSAICO": "MOSAICO S.A.",
    "MOSAICO STRETTO": "MOSAICO S.A.",
}
# Precomputado: clave normalizada -> canónica (para override en el mapeo).
_PROV_ALIAS_BY_KEY = {_norm_prov_key(_k): _v for _k, _v in _PROVEEDOR_ALIASES.items()}


def _fmt_clp(v):
    return "${:,.0f}".format(v or 0).replace(",", ".")


def _fmt_fecha_h(x):
    if not x:
        return "—"
    try:
        _d = datetime.fromisoformat(x.replace("Z", "+00:00")).astimezone(_tz_cl)
        return (f'<span style="font-weight:700;">{_d.strftime("%d/%m/%Y")}</span>'
                f'<br><span style="font-size:0.75em;color:#64748b;">{_d.strftime("%H:%M")}</span>')
    except Exception:
        return str(x)[:10]


def _detectar_navegador():
    try:
        ua = st.context.headers.get('User-Agent', '')
        return {
            'needs_google_viewer': 'Chrome' in ua or 'Edg' in ua or 'Safari' in ua
        }
    except Exception:
        return {'needs_google_viewer': True}


# Estados operacionales (subconjunto de calcular_estado_label): SOLO los que tienen
# margen aprobado y que interesan a operaciones. Un presupuesto RECHAZADO
# (motivo_rechazo, sin notariado ni acta) NO es operacional y se excluye del panel.
# Precedencia idéntica a services.cotizacion_service.calcular_estado_label:
# acta > notariado > rechazo > margen.
def _estado_oper_label(row) -> str:
    if row.get('acta_url'):
        return 'PROYECTO TERMINADO'
    if row.get('contrato_notariado_url'):
        return 'ADJUDICADO'
    _mr = row.get('motivo_rechazo')
    if _mr is not None and str(_mr).strip() not in ('', 'None', 'nan'):
        return 'RECHAZADO'
    if (row.get('config_margen') or 0) > 0:
        return 'PENDIENTE COMPRAS'
    return ''


# Colores del badge de la CELDA (bg, border, text) — mismo formato visual que
# services.cotizacion_service.crear_badge_estado (relleno sólido + borde + sombra,
# SIN emojis) para que coincidan con los badges de la pestaña COTIZACIONES.
_OPER_ESTADO_COLORS = {
    'PROYECTO TERMINADO': ('#7c3aed', '#5b21b6', 'white'),
    'ADJUDICADO':         ('#2563eb', '#1d4ed8', 'white'),
    'PENDIENTE COMPRAS':  ('#ffc107', '#d39e00', '#212529'),
}

# Estilo de los BADGES-FILTRO nativos (bg, texto, activo) — misma paleta que
# tab_historial._BADGE_STYLE. Iconos Material como en COTIZACIONES/CONTRATO.
_OPER_BADGE_STYLE = {
    'TODOS':              ('#ede9fe', '#6d28d9', '#6d28d9'),
    'PROYECTO TERMINADO': ('#ede9fe', '#7c3aed', '#5b21b6'),
    'ADJUDICADO':         ('#dbeafe', '#1d4ed8', '#1e40af'),
    'PENDIENTE COMPRAS':  ('#fef9c3', '#854d0e', '#713f12'),
}
_OPER_BADGE_ICON = {
    'TODOS':              ':material/apps:',
    'PROYECTO TERMINADO': ':material/emoji_events:',
    'ADJUDICADO':         ':material/military_tech:',
    'PENDIENTE COMPRAS':  ':material/schedule:',
}
# Orden fijo de los estados operacionales para badges/selector.
_OPER_ESTADOS = ('PROYECTO TERMINADO', 'ADJUDICADO', 'PENDIENTE COMPRAS')
# Tarjeta de selección: (bg, color acento, icono _ic_op) por estado.
_OPER_CARD_META = {
    'PROYECTO TERMINADO': ('#ede9fe', '#7c3aed', 'package'),
    'ADJUDICADO':         ('#dbeafe', '#2563eb', 'check'),
    'PENDIENTE COMPRAS':  ('#fef9c3', '#f59e0b', 'clock'),
}
# Prioridad de orden en el selector (terminado/adjudicado arriba, pendiente al final).
_OPER_ORD_ESTADO = {'PROYECTO TERMINADO': 0, 'ADJUDICADO': 1, 'PENDIENTE COMPRAS': 2}


def _badge_estado_oper(row):
    _lbl = _estado_oper_label(row)
    _c = _OPER_ESTADO_COLORS.get(_lbl)
    if not _c:
        return ('<span style="background:#e2e8f0;color:#64748b;padding:2px 7px;'
                'border-radius:20px;font-size:0.68rem;font-weight:700;white-space:nowrap;">— —</span>')
    color, border, text_color = _c
    return (f'<span style="background-color:{color};color:{text_color};padding:2px 7px;'
            f'border-radius:20px;font-size:0.68rem;font-weight:700;display:inline-block;'
            f'border:1px solid {border};box-shadow:0 2px 4px rgba(0,0,0,0.1);white-space:nowrap;">{_lbl}</span>')


def _calc_total_costo(row):
    try:
        _prods = row.get("productos") or []
        if isinstance(_prods, str):
            _prods = json.loads(_prods)
        import pandas as _pd
        _df = _pd.DataFrame(_prods) if _prods else _pd.DataFrame()
        if not _df.empty and 'Categoria' in _df.columns:
            _df = _df[_df['Categoria'].str.strip().str.lower() != 'varios']
        _sub = _df['Subtotal'].sum() if not _df.empty and 'Subtotal' in _df.columns else 0
        return _sub * 1.19
    except Exception:
        return 0


# ── Render principal ─────────────────────────────────────────────────────────

def render_tab_operaciones(supabase, supabase_admin=None, supa_url='', supa_key='', **deps):
    supa_admin = supabase_admin or _supa_admin
    _rol = st.session_state.get('rol_usuario', 'ejecutivo')
    SUPABASE_URL = supa_url or deps.get('supa_url', '')
    SUPABASE_KEY = supa_key or deps.get('supa_key', '')

    # Aliases a módulos utils
    _listar_usuarios_ej      = listar_usuarios_ejecutivos
    _obtener_registros_rc    = obtener_registros_compra
    _obtener_items_comprados = obtener_items_comprados
    _calcular_estado_compras = calcular_estado_compras
    _dias_habiles_entre      = dias_habiles_entre
    _sumar_dias_habiles      = sumar_dias_habiles
    _guardar_acta            = guardar_acta_en_storage
    _registrar_entrega       = registrar_entrega_proyecto
    _leer_hoja_excel         = leer_hoja_excel

    # ── Header ──
    st.markdown("""
    <style>
    .hdr-oper {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(30,58,95,0.35);
    }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "operaciones",
        "Operaciones",
        "PDF de compras &middot; planos &middot; seguimiento de fabricaci&#243;n y fidelizaci&#243;n de clientes",
    )

    _sub_panel, _sub_compras, _sub_acta = st.tabs([
        ":material/dashboard: Panel Operacional",
        ":material/shopping_cart: Registro de Compras",
        ":material/assignment: Acta de Clientes",
    ])

    # ================================================================
    # SUB-PESTAÑA: PANEL OPERACIONAL
    # ================================================================
    with _sub_panel:
        st.markdown(_titulo_op("grid", "Panel Operacional"), unsafe_allow_html=True)
        # Cargar ejecutivos para dropdown
        try:
            _oper_usuarios = _listar_usuarios_ej() or []
            _oper_ejs = [u for u in _oper_usuarios if u.get('rol', '') in ('ejecutivo', 'admin', 'administrador')]
            _oper_ej_opts = ['Todos'] + [u.get('nombre', '') for u in _oper_ejs if u.get('nombre')]
        except Exception:
            _oper_ej_opts = ['Todos']

        # Filtros
        _oc1, _oc2, _oc3, _oc4 = st.columns([2.5, 2, 0.8, 0.4])
        with _oc1:
            _oper_ep = st.text_input("EP", placeholder="Buscar por N&#176; EP...",
                                     key="oper_ep", label_visibility="collapsed")
        with _oc2:
            _oper_ej_sel = st.selectbox("Ejecutivo", _oper_ej_opts,
                                        key="oper_ej_sel", label_visibility="collapsed")
        with _oc3:
            _oper_buscar = st.button("Buscar", icon=":material/search:",
                                     use_container_width=True, key="oper_buscar")
        with _oc4:
            if st.button("", icon=":material/refresh:", key="oper_refresh",
                         help="Actualizar", use_container_width=True):
                st.session_state.pop('oper_results', None)
                st.rerun()

        def _cargar_oper_results(ep_filter=None, ej_filter=None):
            _oq = supa_admin.table("cotizaciones").select(
                "numero,fecha_creacion,fecha_modificacion,cliente_nombre,cliente_email,"
                "asesor_nombre,asesor_email,asesor_telefono,estado,plano_url,plano_nombre,"
                "config_margen,contrato_generado,productos,total_subtotal_sin_margen,"
                "contrato_notariado_url,fecha_adjudicacion,contrato_datos,acta_url,fecha_entrega,"
                "motivo_rechazo"
            ).gt("config_margen", 0)
            if ep_filter and ep_filter.strip():
                _oq = _oq.ilike("numero", f"%{ep_filter.strip()}%")
            if ej_filter and ej_filter != 'Todos':
                _oq = _oq.eq("asesor_nombre", ej_filter)
            # limit alto porque el filtro por estado se hace en Python (abajo) y los
            # RECHAZADOS se descartan: así no quedan menos de ~100 resultados válidos.
            _rows = _oq.order("fecha_creacion", desc=True).limit(300).execute().data or []
            # SOLO estados operacionales (ADJUDICADO / PROYECTO TERMINADO / PENDIENTE
            # COMPRAS). Excluye los RECHAZADOS aunque tengan margen > 0.
            return [r for r in _rows if _estado_oper_label(r) in _OPER_ESTADOS]

        if _oper_buscar:
            st.session_state['oper_filtro_estado'] = None
            try:
                st.session_state['oper_results'] = _cargar_oper_results(_oper_ep, _oper_ej_sel)
            except Exception as _oe:
                st.error(f"Error: {_oe}")
                st.session_state['oper_results'] = []

        if 'oper_results' not in st.session_state or (
            not _oper_buscar and _oper_ej_sel != st.session_state.get('_oper_ej_prev')
        ):
            st.session_state['_oper_ej_prev'] = _oper_ej_sel
            st.session_state['oper_filtro_estado'] = None
            try:
                st.session_state['oper_results'] = _cargar_oper_results(None, _oper_ej_sel)
            except Exception:
                st.session_state['oper_results'] = []

        _oper_all = st.session_state.get('oper_results', [])

        # ── Badges de estado (mismo diseño y comportamiento que COTIZACIONES) ──
        # Conteo por estado sobre el set COMPLETO (ya sin RECHAZADOS).
        _oper_cnt = {}
        for _r in _oper_all:
            _lbl_r = _estado_oper_label(_r)
            _oper_cnt[_lbl_r] = _oper_cnt.get(_lbl_r, 0) + 1
        _oper_filtro = st.session_state.get('oper_filtro_estado')

        _ej_chip = ''
        if _oper_ej_sel != 'Todos':
            _ej_chip = (
                "<span style='display:inline-flex;align-items:center;background:#ede9fe;color:#6d28d9;"
                "padding:3px 12px;border-radius:99px;font-size:11px;font-weight:700;margin-right:8px;'>"
                + _ic_op("user", color="#6d28d9", size=13, mr=5, valign=-2)
                + f"{_oper_ej_sel}</span>")
        if _ej_chip:
            st.markdown(_ej_chip, unsafe_allow_html=True)

        _oper_badge_lbls = {
            'PROYECTO TERMINADO': 'terminados',
            'ADJUDICADO':         'adjudicados',
            'PENDIENTE COMPRAS':  'pend. compras',
        }
        _oper_badges = [('TODOS', f'Todos ({len(_oper_all)})', '_ofbtn_0')]
        for _bi, _bk in enumerate(_OPER_ESTADOS):
            if _oper_cnt.get(_bk, 0):
                _oper_badges.append((_bk, f'{_oper_badge_lbls[_bk]} ({_oper_cnt[_bk]})', f'_ofbtn_{_bi+1}'))

        _obbase = ('font-family:Montserrat,sans-serif!important;font-weight:800!important;'
                   'font-size:11.5px!important;border-radius:99px!important;border:none!important;'
                   'padding:5px 14px!important;min-height:0!important;letter-spacing:0.03em!important;'
                   'transition:all .12s!important;white-space:nowrap!important;text-transform:uppercase!important;')
        _ocss = ['<style>']
        for _bk, _blbl, _bkey in _oper_badges:
            _bg, _fg, _act = _OPER_BADGE_STYLE.get(_bk, ('#e2e8f0', '#334155', '#334155'))
            _is_act = (_bk == 'TODOS' and not _oper_filtro) or (_bk == _oper_filtro)
            if _is_act:
                _ocss.append(f'.st-key-{_bkey} button{{{_obbase}background:{_act}!important;'
                             f'color:#fff!important;box-shadow:0 0 0 2px {_act}!important;}}')
            else:
                _ocss.append(f'.st-key-{_bkey} button{{{_obbase}background:{_bg}!important;color:{_fg}!important;}}')
            _ocss.append(f'.st-key-{_bkey} button:hover{{background:{_act}!important;color:#fff!important;}}')
            # SÓLO el texto lleva Montserrat/uppercase (a `button *` rompe la ligadura del ícono).
            _ocss.append(f'.st-key-{_bkey} button p,.st-key-{_bkey} button [data-testid="stMarkdownContainer"]'
                         f'{{font-family:Montserrat,sans-serif!important;'
                         f'font-size:11.5px!important;font-weight:800!important;text-transform:uppercase!important;}}')
        _ocss.append('</style>')
        st.markdown(''.join(_ocss), unsafe_allow_html=True)

        def _set_oper_filter(_k):
            _cur = st.session_state.get('oper_filtro_estado')
            st.session_state['oper_filtro_estado'] = (None if _k == _cur else _k)
            st.session_state.pop('oper_ep_sel', None)

        _oweights = [max(len(_b[1]) * 0.42 + 0.9, 3.2) for _b in _oper_badges]
        _obcols = st.columns(_oweights)
        for _bci, (_bk, _blbl, _bkey) in enumerate(_oper_badges):
            with _obcols[_bci]:
                st.button(_blbl, key=_bkey, use_container_width=True,
                          icon=_OPER_BADGE_ICON.get(_bk),
                          on_click=_set_oper_filter,
                          args=(None if _bk == 'TODOS' else _bk,))
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Aplica el filtro activo por estado a los datos mostrados.
        if _oper_filtro:
            _oper_data = [r for r in _oper_all if _estado_oper_label(r) == _oper_filtro]
        else:
            _oper_data = list(_oper_all)

        if not _oper_all:
            st.info("No se encontraron cotizaciones.")
        elif not _oper_data:
            st.info("No hay cotizaciones con ese estado.")
        else:
            import pandas as _pd_op

            # Construir filas HTML
            _rows_op = ""
            for _or in _oper_data:
                _ep_r  = _or.get("numero", "—")
                _cli   = _or.get("cliente_nombre", "—")
                _ej    = _or.get("asesor_nombre", "—")
                _tc    = _calc_total_costo(_or)
                _tc_html = (f'<span style="font-weight:700;">{_fmt_clp(_tc)}</span>'
                            f'<br><span style="font-size:0.75em;color:#64748b;">base+IVA</span>')

                _fadj_raw  = _or.get("fecha_adjudicacion", "") or ""
                _fadj_html = _fmt_fecha_h(_fadj_raw) if _or.get("contrato_notariado_url") else '<span style="color:#94a3b8;">—</span>'

                # Tiempo fabricación (si adjudicado)
                _fab_html    = '<span style="color:#94a3b8;">—</span>'
                _fidel_html  = '<span style="color:#94a3b8;">—</span>'
                _retraso_html = '<span style="color:#94a3b8;">—</span>'

                if _or.get("contrato_notariado_url") and _fadj_raw:
                    try:
                        _cd = _or.get("contrato_datos") or {}
                        if isinstance(_cd, str):
                            _cd = json.loads(_cd)
                        _plazo_dias = int((_cd or {}).get("plazo_dias", 0) or 0)
                        _d_adj_dt = datetime.fromisoformat(_fadj_raw.replace("Z", "+00:00")).astimezone(_tz_cl)
                        _d_adj_date = _d_adj_dt.date()
                        _hoy = datetime.now(_tz_cl).date()
                        _hab_trans = _dias_habiles_entre(_d_adj_date, _hoy)
                        _ts_adj = int(_d_adj_dt.timestamp() * 1000)
                        _fab_html = (f'<span class="fab-live" data-desde="{_ts_adj}" '
                                     f'style="color:#2563eb;font-weight:700;">{_hab_trans}d h&#225;biles</span>')
                        if _plazo_dias > 0:
                            _d_ent = _sumar_dias_habiles(_d_adj_date, _plazo_dias)
                            _hab_rest = max(0, _dias_habiles_entre(_hoy, _d_ent))
                            _pct_av = min(100.0, round(_hab_trans / _plazo_dias * 100, 1))
                            _col_f = "#16a34a" if _pct_av < 50 else ("#f97316" if _pct_av < 80 else "#dc2626")
                            if _hoy <= _d_ent:
                                _fidel_html = (
                                    f'<span style="color:{_col_f};font-weight:700;">'
                                    + _ic_op("clock", color=_col_f, size=12, mr=4, valign=-2)
                                    + f'{_hab_rest}d h&#225;b.</span>'
                                    f'<br><span style="font-size:0.72em;color:#64748b;">{_pct_av}% &middot; {_plazo_dias}d plazo</span>'
                                )
                            else:
                                _hab_ret = _dias_habiles_entre(_d_ent, _hoy)
                                _fidel_html = ('<span style="color:#dc2626;font-weight:700;">'
                                    + _ic_op("alert", color="#dc2626", size=12, mr=4, valign=-2)
                                    + f'VENCIDO +{_hab_ret}d h&#225;b.</span>')
                                _retraso_html = f'<span style="color:#dc2626;font-weight:700;">{_hab_ret}d h&#225;b.</span>'
                    except Exception:
                        pass

                # Estado compras
                _compras_html = '<span style="color:#94a3b8;">—</span>'
                try:
                    _prods_r = _or.get('productos') or []
                    if isinstance(_prods_r, str):
                        _prods_r = json.loads(_prods_r)
                    _op_est = _calcular_estado_compras(_ep_r, _prods_r)
                    _op_pct = _op_est.get('pct', 0)
                    _op_estado = _op_est.get('estado', '')
                    if _op_estado == 'Sin compras':
                        _compras_html = '<span style="color:#94a3b8;font-size:0.78rem;">Sin compras</span>'
                    else:
                        # Barra de progreso — MISMO diseño que la columna COMPRAS de
                        # COTIZACIONES (colores por avance) para que se vean iguales.
                        if _op_pct <= 33:
                            _oc, _ob = '#dc2626', '#fee2e2'
                        elif _op_pct <= 66:
                            _oc, _ob = '#f97316', '#ffedd5'
                        elif _op_pct < 100:
                            _oc, _ob = '#16a34a', '#dcfce7'
                        else:
                            _oc, _ob = '#2563eb', '#dbeafe'
                        _ow = min(100, _op_pct)
                        _olbl = ((_ic_op("check", color=_oc, size=11, mr=3, valign=-1) + '100% comprado')
                                 if _op_pct >= 100 else f'{_op_pct}% comprado')
                        _compras_html = (
                            f'<div style="width:80px;">'
                            f'<div style="background:{_ob};border-radius:4px;height:6px;margin-bottom:3px;">'
                            f'<div style="background:{_oc};border-radius:4px;height:6px;width:{_ow}%;"></div></div>'
                            f'<span style="color:{_oc};font-weight:700;font-size:0.72rem;">{_olbl}</span></div>'
                        )
                except Exception:
                    pass

                _rows_op += (
                    f"<tr>"
                    f"<td data-ep='{_ep_r}' style='cursor:pointer;font-weight:700;color:#3b82f6;' title='Click para copiar'>{_ep_r} "
                    + _ic_op("clipboard", color="#3b82f6", size=12, mr=0, valign=-2) + "</td>"
                    f"<td style='font-size:0.82rem;font-weight:700;'>{_cli}</td>"
                    f"<td style='text-align:right;line-height:1.6;'>{_tc_html}</td>"
                    f"<td style='font-size:0.82rem;font-weight:700;'>{_ej}</td>"
                    f"<td style='text-align:center;'>{_badge_estado_oper(_or)}</td>"
                    f"<td style='line-height:1.6;'>{_fadj_html}</td>"
                    f"<td style='text-align:center;font-size:0.82rem;'>{_fab_html}</td>"
                    f"<td style='text-align:center;font-size:0.82rem;'>{_fidel_html}</td>"
                    f"<td style='text-align:center;font-size:0.82rem;'>{_retraso_html}</td>"
                    f"<td style='text-align:center;font-size:0.82rem;'>{_compras_html}</td>"
                    f"</tr>"
                )

            _altura_op = min(len(_oper_data) * 60 + 60, 550)
            _html_op = f"""
            <div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid #e2e8f0;overflow-x:auto;">
              <div style="max-height:{_altura_op}px;overflow-y:auto;">
                <table class='resultados-table' style='margin:0;border-radius:0;box-shadow:none;min-width:900px;'>
                  <thead style='position:sticky;top:0;z-index:2;'>
                    <tr>
                      <th>Presupuesto</th><th>Cliente</th><th>Total costo</th><th>Asesor</th>
                      <th>Estado</th><th>Fecha adjudicaci&#243;n</th><th>Tiempo fabricaci&#243;n</th>
                      <th>Fidelizaci&#243;n</th><th>Retraso</th><th>Compras</th>
                    </tr>
                  </thead>
                  <tbody>{_rows_op}</tbody>
                </table>
              </div>
            </div>
            <p style="font-size:0.8rem;color:#888;margin-top:6px;">Mostrando {len(_oper_data)} resultado(s)</p>
            """
            st.markdown(_html_op, unsafe_allow_html=True)

            # JS copiar EP
            components.html("""<script>
(function(){
  var D=window.parent.document;
  D.addEventListener('click',function(e){
    var td=e.target&&e.target.closest?e.target.closest('td[data-ep]'):null;
    if(!td)return;
    var ep=td.getAttribute('data-ep');if(!ep)return;
    var ta=D.createElement('textarea');ta.value=ep;
    ta.style.cssText='position:fixed;top:-9999px;left:-9999px;';
    D.body.appendChild(ta);ta.focus();ta.select();
    try{D.execCommand('copy');}catch(e){}
    D.body.removeChild(ta);
  });
})();
</script>""", height=0)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            # Selectbox enriquecido. El estado va como TEXTO (el dropdown no renderiza
            # SVG ni :material:); el icono de estado se muestra en la tarjeta de abajo.
            _ep_opts_op = []
            _ep_labels_op = {}
            _ep_estado_op = {}
            for _r in _oper_data:
                _r_ep  = _r.get("numero", "")
                _r_cli = _r.get("cliente_nombre", "—")
                _r_ej  = _r.get("asesor_nombre", "—")
                _r_tc  = _calc_total_costo(_r)
                _r_lbl = _estado_oper_label(_r)
                _ep_estado_op[_r_ep] = _r_lbl
                if _r_lbl == 'ADJUDICADO':
                    _label = f"{_r_ep} · ADJUDICADO · {_fmt_clp(_r_tc)} · Cliente: {_r_cli} · Ejecutivo: {_r_ej}"
                else:
                    _label = f"{_r_ep} · {_r_lbl} · Cliente: {_r_cli} · Ejecutivo: {_r_ej}"
                _ep_opts_op.append(_r_ep)
                _ep_labels_op[_r_ep] = _label

            _ep_opts_op = sorted(_ep_opts_op,
                                 key=lambda x: _OPER_ORD_ESTADO.get(_ep_estado_op.get(x, ''), 3))

            _ep_sel_op = st.selectbox(
                "Selecciona una cotizaci&#243;n para acciones:",
                _ep_opts_op,
                format_func=lambda x: _ep_labels_op.get(x, x),
                key="oper_ep_sel"
            )

            if _ep_sel_op and _ep_sel_op in _ep_labels_op:
                _sel_lbl_card = _ep_estado_op.get(_ep_sel_op, 'PENDIENTE COMPRAS')
                _sel_adj_card = _sel_lbl_card in ('ADJUDICADO', 'PROYECTO TERMINADO')
                _bg_card, _bc_card, _ic_card = _OPER_CARD_META.get(
                    _sel_lbl_card, ('#fef9c3', '#f59e0b', 'clock'))
                _badge_txt = (_ic_op(_ic_card, color="#ffffff", size=12, mr=5, valign=-2)
                              + _sel_lbl_card)
                _sel_r    = next((r for r in _oper_data if r.get("numero") == _ep_sel_op), {})
                _sel_tc   = _calc_total_costo(_sel_r) if _sel_adj_card else 0
                _tc_span  = f'<span style="font-size:13px;font-weight:700;color:{_bc_card};">{_fmt_clp(_sel_tc)}</span>' if _sel_adj_card else ""
                st.markdown(
                    f'<div style="background:{_bg_card};border-left:4px solid {_bc_card};border-radius:0 10px 10px 0;'
                    f'padding:12px 16px;margin-bottom:12px;display:flex;align-items:center;gap:16px;">'
                    f'<div style="font-size:14px;font-weight:900;color:#0f172a;min-width:90px;">{_ep_sel_op}</div>'
                    f'<div style="flex:1;">'
                    f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">'
                    f'<span style="background:{_bc_card};color:white;padding:2px 10px;border-radius:99px;font-size:10px;font-weight:700;">{_badge_txt}</span>'
                    f'{_tc_span}</div>'
                    f'<div style="font-size:11px;color:#374151;display:flex;gap:14px;">'
                    f'<span>Cliente: <b>{_sel_r.get("cliente_nombre","—")}</b></span>'
                    f'<span>Ejecutivo: <b>{_sel_r.get("asesor_nombre","—")}</b></span>'
                    f'</div></div></div>',
                    unsafe_allow_html=True)

            if _ep_sel_op:
                _sel_data = next((r for r in _oper_data if r.get("numero") == _ep_sel_op), None)
                if _sel_data:
                    _sel_plano = _sel_data.get("plano_url", "") or ""
                    _sel_adj   = bool(_sel_data.get("contrato_notariado_url", ""))
                    _sb1, _sb2 = st.columns([2, 2])

                    with _sb1:
                        if _sel_adj and _PDF_OK:
                            try:
                                import pandas as _pd_sel
                                _sel_prods = _sel_data.get('productos') or []
                                if isinstance(_sel_prods, str):
                                    _sel_prods = json.loads(_sel_prods)
                                _sel_df = _pd_sel.DataFrame(_sel_prods)
                                if not _sel_df.empty and 'Categoria' in _sel_df.columns:
                                    _sel_df = _sel_df[_sel_df['Categoria'].str.strip().str.lower() != 'varios'].copy()
                                _sel_sub = _sel_df['Subtotal'].sum() if not _sel_df.empty and 'Subtotal' in _sel_df.columns else 0
                                _sel_iva = _sel_sub * 0.19
                                _sel_tot = _sel_sub + _sel_iva
                                _sel_dc = {
                                    "Nombre": _sel_data.get('cliente_nombre', ''),
                                    "RUT": _sel_data.get('cliente_rut', ''),
                                    "Correo": _sel_data.get('cliente_email', ''),
                                    "Teléfono": formatear_telefono(_sel_data.get('cliente_telefono', '')),
                                    "Dirección": _sel_data.get('cliente_direccion', ''),
                                    "ComunaCliente": _sel_data.get('cliente_comuna', ''),
                                    "RegionCliente": _sel_data.get('cliente_region', ''),
                                    "DireccionProyecto": _sel_data.get('proyecto_direccion', ''),
                                    "ComunaProyecto": _sel_data.get('proyecto_comuna', ''),
                                    "RegionProyecto": _sel_data.get('proyecto_region', ''),
                                    "TipoCliente": _sel_data.get('cliente_tipo', 'natural'),
                                    "Observaciones": _sel_data.get('proyecto_observaciones', ''),
                                }
                                _sel_da = {"Nombre Ejecutivo": _sel_data.get('asesor_nombre', '')}
                                from datetime import timedelta as _td2
                                _fi = _date_cls.today()
                                _ft = _fi + timedelta(days=15)
                                _sel_pdf, _ = generar_pdf_completo(
                                    _sel_df, _sel_sub, _sel_iva, _sel_tot,
                                    _sel_dc, _fi, _ft, 15, _sel_da,
                                    margen=0, numero_cotizacion=_ep_sel_op, mostrar_precios=True
                                )
                                st.download_button("PDF Compras", icon=":material/shopping_cart:", data=_sel_pdf,
                                    file_name=f"Compras_{_ep_sel_op}.pdf",
                                    mime="application/pdf", use_container_width=True, key="oper_dl_pdf")
                            except Exception as _se:
                                st.button("PDF Compras", icon=":material/shopping_cart:", disabled=True,
                                          use_container_width=True, key="oper_dl_pdf", help=f"Error: {_se}")
                        else:
                            st.button("PDF Compras", icon=":material/shopping_cart:", disabled=True,
                                      use_container_width=True, key="oper_dl_pdf",
                                      help="Solo disponible con estado ADJUDICADO")

                    with _sb2:
                        _plano_showing = st.session_state.get('oper_show_plano')
                        _lbl_plano = "ACTUALIZAR PLANO" if _plano_showing else "VER PLANO"
                        _ico_plano = ":material/refresh:" if _plano_showing else ":material/visibility:"
                        _plano_disabled = not bool(_sel_plano and _sel_adj)
                        if st.button(_lbl_plano, icon=_ico_plano, use_container_width=True,
                                     disabled=_plano_disabled, key="oper_ver_plano"):
                            st.session_state['oper_show_plano'] = not st.session_state.get('oper_show_plano', False)
                            st.session_state['oper_plano_url']    = _sel_plano
                            st.session_state['oper_plano_nombre'] = _sel_data.get('plano_nombre', 'plano.pdf')
                            st.rerun()

                    if st.session_state.get('oper_show_plano') and st.session_state.get('oper_plano_url'):
                        with st.expander("Vista Previa del Plano", expanded=True, icon=":material/picture_as_pdf:"):
                            st.markdown(f"**Archivo:** {st.session_state.get('oper_plano_nombre','plano.pdf')} — cotizaci&#243;n `{_ep_sel_op}`")
                            _nav_op   = _detectar_navegador()
                            _url_op   = st.session_state['oper_plano_url']
                            _enc_op   = urllib.parse.quote(_url_op, safe='')
                            _goog_op  = f"https://docs.google.com/viewer?url={_enc_op}&embedded=true"
                            _src_op   = _goog_op if _nav_op['needs_google_viewer'] else _url_op
                            components.html(f"""
<style>
@keyframes spin {{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
body,html{{margin:0;padding:0;overflow:hidden;}}
#pdf-wrap{{width:100%;height:680px;border:2px solid #e2e8f0;border-radius:12px;overflow:hidden;position:relative;}}
#pdf-loading{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f0f2f5;z-index:2;gap:12px;}}
#pdf-spinner{{width:40px;height:40px;border:4px solid #cbd5e1;border-top-color:#5b7cfa;border-radius:50%;animation:spin 0.8s linear infinite;}}
#pdf-iframe{{position:absolute;inset:0;width:100%;height:100%;border:none;display:block;}}
</style>
<div id="pdf-wrap">
  <div id="pdf-loading"><div id="pdf-spinner"></div><span style="color:#64748b;font-size:0.9rem;">Cargando PDF...</span></div>
  <iframe id="pdf-iframe" src="{_src_op}" allow="fullscreen"></iframe>
</div>
<script>(function(){{setTimeout(function(){{document.getElementById('pdf-loading').style.display='none';}},4000);}})();</script>
""", height=710, scrolling=False)
                            try:
                                import requests as _req_op
                                _plano_bytes = _req_op.get(_url_op, timeout=15).content
                                st.download_button("Descargar Plano", icon=":material/download:", data=_plano_bytes,
                                    file_name=st.session_state.get('oper_plano_nombre', 'plano.pdf'),
                                    mime="application/pdf", use_container_width=True,
                                    key=f"oper_dl_plano_{_ep_sel_op}")
                            except Exception:
                                st.warning("No se pudo preparar la descarga del plano.", icon=":material/warning:")

        # NOTA: el GUARDADO de un registro nuevo ya NO pasa por Python. El iframe del
        # formulario inserta el registro DIRECTO en Supabase (anon key; RLS lo permite,
        # igual que la subida de la factura) y luego clickea el botón oculto _rc_apply
        # para refrescar. Esto elimina el guardado intermitente por query param/popstate.
        # Se mantiene el handler rc_save por compatibilidad (por si llega un guardado
        # legacy vía query param); normalmente no se dispara.
        _rc_save_raw = st.query_params.get('rc_save')
        if _rc_save_raw:
            import json as _json_rc
            try:
                _rc_payload = _json_rc.loads(_rc_save_raw)
            except Exception:
                _rc_payload = None
            _rc_ok, _rc_err = (guardar_registro_compra_full(_rc_payload)
                               if _rc_payload else (False, "Payload inválido."))
            try:
                del st.query_params['rc_save']
            except Exception:
                pass
            try:
                obtener_items_comprados.clear()  # cache ttl 30s (registros lee fresco)
            except Exception:
                pass
            for _k in list(st.session_state.keys()):
                if _k.startswith('rc_json_'):
                    st.session_state[_k] = '[]'
            if not _rc_ok:
                st.session_state['_rc_save_error'] = _rc_err or "Error al guardar."
            st.rerun()

        # Edición SERVER-SIDE de un registro (rc_edit) desde el iframe del historial.
        # El navegador manda SOLO deltas (índice de ítem + cantidad + precio + quitar).
        # Tomamos los ítems ORIGINALES de la BD (no confiamos en el cliente para el
        # precio presupuestado) y aplicamos los cambios con la service key.
        _rc_edit_raw = st.query_params.get('rc_edit')
        if _rc_edit_raw:
            import json as _json_re
            try:
                _pe = _json_re.loads(_rc_edit_raw)
            except Exception:
                _pe = None
            if _pe and _pe.get('id'):
                _re_ok = True
                _re_err = None
                try:
                    _orig = supa_admin.table('registro_compras').select('items').eq(
                        'id', _pe['id']).limit(1).execute().data
                except Exception as _e_o:
                    _orig, _re_ok, _re_err = None, False, str(_e_o)
                if _orig:
                    _oitems = _orig[0].get('items') or []
                    if isinstance(_oitems, str):
                        try:
                            _oitems = _json_re.loads(_oitems)
                        except Exception:
                            _oitems = []
                    _new = []
                    for _d in (_pe.get('items') or []):
                        _di = _d.get('i')
                        if not isinstance(_di, int) or _di < 0 or _di >= len(_oitems):
                            continue
                        if _d.get('rm'):
                            continue
                        _m = dict(_oitems[_di])
                        _m['precio_real'] = int(_d.get('p', 0) or 0)
                        # Si un ítem "en stock" pasa a tener precio real (>0) al
                        # editarlo, deja de ser ahorro puro → se limpia el flag.
                        if _m.get('stock') and _m['precio_real'] > 0:
                            _m['stock'] = False
                        # La cantidad SOLO es editable para adicionales SIN registro
                        # (texto libre). Para el resto se conserva la de la BD (no se
                        # confía en el cliente).
                        if _m.get('sin_registro'):
                            _m['cantidad'] = int(_d.get('c', 0) or 0)
                        _new.append(_m)
                    _upd = {
                        'items': _new,
                        'lugar_compra': _pe.get('lugar', ''),
                        'observaciones': _pe.get('obs', ''),
                        'fecha_entrega_compra': _pe.get('fent', ''),
                        'usuario_registro': st.session_state.get('auth_nombre', ''),
                    }
                    # Reemplazo de factura: solo se acepta la URL si apunta al
                    # bucket público 'facturas' de ESTE Supabase (evita inyectar
                    # una URL arbitraria en la BD).
                    _fac_new = str(_pe.get('factura_url', '') or '')
                    _fac_pref = (SUPABASE_URL or '').rstrip('/') + '/storage/v1/object/public/facturas/'
                    if _fac_new and _fac_new.startswith(_fac_pref):
                        _upd['factura_url'] = _fac_new
                        _upd['factura_nombre'] = str(_pe.get('factura_nom', '') or '')
                    _re_ok, _re_err = actualizar_registro_compra_full(_pe['id'], _upd)
                elif _re_ok:
                    _re_ok, _re_err = False, "Registro no encontrado."
            else:
                _re_ok, _re_err = False, "Datos de edición inválidos."
            try:
                del st.query_params['rc_edit']
            except Exception:
                pass
            try:
                obtener_items_comprados.clear()  # cache ttl 30s (registros lee fresco)
            except Exception:
                pass
            for _k in list(st.session_state.keys()):
                if _k.startswith('rc_json_'):
                    st.session_state[_k] = '[]'
            if not _re_ok:
                st.session_state['_rc_mut_error'] = _re_err or "Error al editar."
            st.rerun()

        # Borrado SERVER-SIDE de un registro completo (rc_delete) desde el historial.
        _rc_del_raw = st.query_params.get('rc_delete')
        if _rc_del_raw:
            _rd_ok, _rd_err = eliminar_registro_compra_full(_rc_del_raw)
            try:
                del st.query_params['rc_delete']
            except Exception:
                pass
            try:
                obtener_items_comprados.clear()  # cache ttl 30s (registros lee fresco)
            except Exception:
                pass
            for _k in list(st.session_state.keys()):
                if _k.startswith('rc_json_'):
                    st.session_state[_k] = '[]'
            if not _rd_ok:
                st.session_state['_rc_mut_error'] = _rd_err or "Error al eliminar."
            st.rerun()

        # Aviso si el guardado server-side del registro falló.
        _rc_err_msg = st.session_state.pop('_rc_save_error', None)
        if _rc_err_msg:
            st.error(f"&#10060; No se pudo guardar el registro de compra: {_rc_err_msg}")

        # Detectar guardado de compra via query param (compat: refresco legacy)
        if st.query_params.get('rc_saved'):
            st.query_params.pop('rc_saved')
            for _k in list(st.session_state.keys()):
                if _k.startswith('rc_json_'):
                    st.session_state[_k] = '[]'
            st.rerun()

    # ================================================================
    # SUB-PESTAÑA: REGISTRO DE COMPRAS
    # ================================================================
    with _sub_compras:
        _rc_admin_role = _rol in ('root', 'admin')
        # Etiqueta del toggle con la tipografía de los títulos de sección + toggle
        # alineado a la derecha de su columna.
        st.markdown(
            "<style>"
            ".st-key-rc_modo_admin_global{display:flex;justify-content:flex-end;align-items:center;}"
            ".st-key-rc_modo_admin_global p,.st-key-rc_modo_admin_global [data-testid=\"stWidgetLabel\"] *{"
            "font-family:Montserrat,sans-serif !important;font-weight:700 !important;font-size:0.88rem !important;"
            "letter-spacing:0.05em !important;text-transform:uppercase !important;color:#0f172a !important;}"
            "</style>", unsafe_allow_html=True)
        # Título "Registro de Compras" + toggle Modo Admin en la MISMA fila (toggle
        # a la derecha), arriba del dropdown.
        if _rc_admin_role:
            _th1, _th2 = st.columns([1.5, 1], vertical_alignment="center")
            with _th1:
                st.markdown(_titulo_op("cart", "Registro de Compras"), unsafe_allow_html=True)
            with _th2:
                _modo_admin_rc = st.toggle('Modo Admin (incluye Varios)', key='rc_modo_admin_global')
        else:
            st.markdown(_titulo_op("cart", "Registro de Compras"), unsafe_allow_html=True)
            _modo_admin_rc = False

        try:
            _rc_resp = supa_admin.table('cotizaciones').select(
                'numero,cliente_nombre,contrato_notariado_url,productos,estado,asesor_nombre,acta_url'
            ).not_.is_('contrato_notariado_url', 'null').order('fecha_creacion', desc=True).execute()
            _rc_cots = [r for r in (_rc_resp.data or []) if r.get('contrato_notariado_url')]
        except Exception:
            _rc_cots = []

        if not _rc_cots:
            st.info('No hay proyectos adjudicados a&#250;n.')
        else:
            # % de compras por proyecto para el dropdown: UNA sola query con todos
            # los registros de los proyectos adjudicados (evita N consultas).
            _eps_all = [r['numero'] for r in _rc_cots if r.get('numero')]
            _regs_by_ep = {}
            _proveedores = []        # canónicas (MAYÚSCULAS) → autocompletar
            _prov_canon_by_key = {}  # clave normalizada → canónica (para el historial)
            try:
                if _eps_all:
                    _rb_all = supa_admin.table('registro_compras').select(
                        'cotizacion_numero,items,lugar_compra').in_('cotizacion_numero', _eps_all).execute()
                    _prov_counts = {}
                    for _rr in (_rb_all.data or []):
                        _regs_by_ep.setdefault(_rr.get('cotizacion_numero'), []).append(_rr)
                        _lg = str(_rr.get('lugar_compra', '') or '').strip()
                        if _lg:
                            _prov_counts[_lg] = _prov_counts.get(_lg, 0) + 1
                    # Agrupar variantes del mismo proveedor y elegir una canónica por
                    # grupo: la más usada; empate → la más larga (plural). MAYÚSCULAS.
                    _prov_groups = {}
                    for _v, _c in _prov_counts.items():
                        _prov_groups.setdefault(_norm_prov_key(_v), {})[_v] = _c
                    for _k, _grp in _prov_groups.items():
                        # Alias manual tiene prioridad (p.ej. MOSAICO / MOSAICO
                        # STRETTO → MOSAICO S.A.); si no, canónica automática.
                        _prov_canon_by_key[_k] = _PROV_ALIAS_BY_KEY.get(_k) or sorted(
                            _grp.items(),
                            key=lambda kv: (-kv[1], -len(kv[0]), kv[0].lower())
                        )[0][0].upper()
                    _proveedores = sorted(set(_prov_canon_by_key.values()))
            except Exception:
                _regs_by_ep = {}
                _proveedores = []
                _prov_canon_by_key = {}

            def _pct_proyecto(_r):
                _pp = _r.get('productos') or []
                if isinstance(_pp, str):
                    try:
                        _pp = json.loads(_pp)
                    except Exception:
                        _pp = []
                _pp = [p for p in _pp if str(p.get('Categoria', '')).strip().lower() != 'varios']
                _tot = len(_pp)
                if _tot == 0:
                    return None
                _pn = {str(p.get('Item', '')) for p in _pp}
                _comp = set()
                for _reg in _regs_by_ep.get(_r.get('numero'), []):
                    _its = _reg.get('items') or []
                    if isinstance(_its, str):
                        try:
                            _its = json.loads(_its)
                        except Exception:
                            _its = []
                    for _it in _its:
                        _nm = str(_it.get('item', ''))
                        # Cuenta como "comprado" si tiene compra real (>$0) O está en
                        # stock/inventario ($0) — igual que el progreso del formulario;
                        # antes ignoraba el stock y el % salía más bajo que en la tabla.
                        if _nm in _pn and (float(_it.get('precio_real', 0) or 0) > 0
                                           or bool(_it.get('stock'))):
                            _comp.add(_nm)
                # Contar POR LÍNEA (no por nombre único): si el presupuesto tiene
                # ítems con el mismo nombre repetido, cada línea cubierta cuenta —
                # igual que el formulario y las columnas COMPRAS. Antes se deduplicaba
                # el numerador pero no el denominador → el % salía más bajo.
                _ncomp = sum(1 for p in _pp if str(p.get('Item', '')) in _comp)
                return round(_ncomp / _tot * 100, 1)

            def _label_proyecto(_r):
                _term = bool(_r.get('acta_url'))
                _dot  = '🟣' if _term else '🔵'
                _est  = 'PROYECTO TERMINADO' if _term else 'ADJUDICADO'
                _p    = _pct_proyecto(_r)
                _ptxt = 'Sin productos' if _p is None else ('Sin compras' if _p == 0 else f'{_p}% comprado')
                return (f"{_r.get('numero')} {_dot} {_est} — cliente: {_r.get('cliente_nombre') or 'S/C'}"
                        f" — ejecutivo: {_r.get('asesor_nombre') or '—'} — {_ptxt}")

            # Valor de la opción = EP (estable) → la selección no se pierde aunque el
            # % cambie; la etiqueta enriquecida se arma en format_func.
            _rc_by_ep   = {r['numero']: r for r in _rc_cots}
            _rc_labels  = {r['numero']: _label_proyecto(r) for r in _rc_cots}
            # Proyecto ACTIVO (cargado). Se elige desde un drawer (botón "Cargar
            # proyecto") para descongestionar la interfaz. "Salir del proyecto"
            # avisa si hay datos sin guardar en la tabla (interceptor JS).
            _rc_active_ep = st.session_state.get('_rc_active_ep')
            if _rc_active_ep and _rc_active_ep not in _rc_by_ep:
                _rc_active_ep = None
                st.session_state.pop('_rc_active_ep', None)

            if _rc_active_ep:
                _rc_bcol1, _rc_bcol2, _rc_bcol3 = st.columns([1, 1, 2])
                with _rc_bcol1:
                    if st.button('Salir del proyecto', key='_rc_salir_btn',
                                 use_container_width=True, icon=":material/logout:"):
                        st.session_state.pop('_rc_active_ep', None)
                        st.rerun()
                with _rc_bcol2:
                    if st.button('Abrir menú', key='_rc_menu_btn',
                                 use_container_width=True, icon=":material/folder_open:"):
                        st.session_state['_rc_open_loader'] = True
                        st.rerun()
                with _rc_bcol3:
                    st.markdown(
                        '<div style="padding-top:9px;font-weight:600;font-size:0.86rem;color:#334155;'
                        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                        f'{_esc_html(_rc_labels.get(_rc_active_ep, _rc_active_ep))}</div>',
                        unsafe_allow_html=True)
            else:
                _rc_bcol1, _rc_bcol2 = st.columns([1, 3])
                with _rc_bcol1:
                    if st.button('Cargar proyecto', type='primary', key='_rc_cargar_btn',
                                 use_container_width=True, icon=":material/folder_open:"):
                        st.session_state['_rc_open_loader'] = True
                        st.rerun()

            # Drawer para elegir/cargar proyecto (se puede abrir también con un
            # proyecto activo, para cambiar a otro).
            if st.session_state.get('_rc_open_loader'):
                st.markdown(_RC_LOADER_CSS, unsafe_allow_html=True)

                @st.dialog('Cargar proyecto', width='large')
                def _rc_loader_dlg():
                    _sel = st.selectbox('Seleccionar proyecto', list(_rc_by_ep.keys()),
                                        format_func=lambda e: _rc_labels.get(e, e),
                                        key='rc_sel_proyecto')
                    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                    _lc1, _lc2 = st.columns(2)
                    with _lc1:
                        if st.button('Cargar proyecto', type='primary',
                                     use_container_width=True, key='_rc_loader_ok'):
                            st.session_state['_rc_active_ep'] = _sel
                            st.session_state.pop('_rc_open_loader', None)
                            st.rerun()
                    with _lc2:
                        if st.button('Cancelar', use_container_width=True, key='_rc_loader_cancel'):
                            st.session_state.pop('_rc_open_loader', None)
                            st.rerun()
                _rc_loader_dlg()

            _rc_ep = _rc_active_ep
            _rc_row = _rc_by_ep.get(_rc_ep, {}) if _rc_ep else {}

            if _rc_ep:
                _rc_prods_raw = _rc_row.get('productos') or []
                if isinstance(_rc_prods_raw, str):
                    try:
                        _rc_prods_raw = json.loads(_rc_prods_raw)
                    except Exception:
                        _rc_prods_raw = []

                if _rol in ('root', 'admin'):
                    _rc_prods = list(_rc_prods_raw)
                else:
                    _rc_prods = [p for p in _rc_prods_raw if str(p.get('Categoria', '')).strip().lower() != 'varios']

                _rc_existentes = _obtener_registros_rc(_rc_ep)

                # Agregar adicionales de registros anteriores
                _prods_sin_varios = [p for p in _rc_prods_raw if str(p.get('Categoria', '')).strip().lower() != 'varios']
                _prods_nombres = {str(p.get('Item', '')) for p in _prods_sin_varios}
                for _reg_ad in _rc_existentes:
                    _items_ad = _reg_ad.get('items') or []
                    if isinstance(_items_ad, str):
                        try:
                            _items_ad = json.loads(_items_ad)
                        except Exception:
                            _items_ad = []
                    for _it_ad in _items_ad:
                        _it_nombre = str(_it_ad.get('item', ''))
                        _it_es_adic = _it_ad.get('es_adicional', False) or _it_nombre not in _prods_nombres
                        if _it_nombre and _it_es_adic and _it_nombre not in _prods_nombres:
                            _rc_prods.append({
                                'Categoria': str(_it_ad.get('categoria', '')),
                                'Item': _it_nombre,
                                'Cantidad': float(_it_ad.get('cantidad', 1) or 1),
                                'Precio Unitario': float(_it_ad.get('precio_presupuestado', 0) or 0),
                                '_adicional': True,
                                # Conservar si el adicional es SIN registro (antes se
                                # perdía → los sin-registro se veían como con-registro
                                # y el panel mostraba $0 en "sin registro").
                                '_sin_registro': bool(_it_ad.get('sin_registro', False)),
                            })
                            _prods_nombres.add(_it_nombre)

                # Modo Admin OFF → ocultar Varios (el toggle está en la fila del título)
                if _rc_admin_role and not _modo_admin_rc:
                    _rc_prods = [p for p in _rc_prods if str(p.get('Categoria', '')).strip().lower() != 'varios']

                if not _rc_prods:
                    st.warning('Este presupuesto no tiene productos cargados.')
                elif not _OPER_OK:
                    st.warning("&#9888;&#65039; El m&#243;dulo de registro de compras no est&#225; disponible. Contacta al administrador del sistema.")
                else:
                    # Cargar catálogo
                    _rc_cat_json = '{}'
                    if _leer_hoja_excel:
                        try:
                            _rc_df_cat = _leer_hoja_excel('BD Total')
                            _rc_cat_data = {}
                            for _, _crow in _rc_df_cat.iterrows():
                                _ccat = str(_crow.get('Categorias', _crow.get('Categoria', ''))).strip()
                                _citem = str(_crow.get('Item', '')).strip()
                                _cprice = round(float(_crow.get('P. Unitario real', _crow.get('Precio Unitario', 0)) or 0))
                                if _ccat and _citem:
                                    if not _modo_admin_rc and _ccat.strip().lower() == 'varios':
                                        continue
                                    if _ccat not in _rc_cat_data:
                                        _rc_cat_data[_ccat] = []
                                    _rc_cat_data[_ccat].append({'item': _citem, 'precio': _cprice})
                            _rc_cat_json = json.dumps(_rc_cat_data, ensure_ascii=False)
                        except Exception:
                            pass

                    _rc_items_comprados = _obtener_items_comprados(_rc_ep)
                    _rc_es_admin = _rol in ('root', 'admin')
                    _rc_ya_comprados_json = json.dumps(list(_rc_items_comprados.keys()))

                    # Tarjetas de categoría — mosaico estilo PRESUPUESTO: orden por
                    # valor DESCENDENTE (mayor a la izquierda), ancho proporcional al
                    # subtotal. Además son filtros FUNCIONALES: clic filtra la tabla
                    # del formulario (window.rcFilterCat, definido en build_rc_html).
                    _rc_cat_colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444',
                                      '#06b6d4','#f97316','#84cc16','#ec4899','#6366f1',
                                      '#14b8a6','#eab308','#dc2626','#7c3aed','#0ea5e9']
                    _rc_cats_seen = {}
                    for _rcp in _rc_prods:
                        _rcc = str(_rcp.get('Categoria', '')).strip()
                        if _rcc:
                            if _rcc not in _rc_cats_seen:
                                _rc_cats_seen[_rcc] = {'items': 0, 'subtotal': 0.0}
                            _rc_cats_seen[_rcc]['items'] += 1
                            _rc_cats_seen[_rcc]['subtotal'] += (
                                float(_rcp.get('Cantidad', 1) or 1) * float(_rcp.get('Precio Unitario', 0) or 0)
                            )

                    def _rc_hex_rgba(_h, _a):
                        _h = _h.lstrip('#')
                        return f'rgba({int(_h[0:2],16)},{int(_h[2:4],16)},{int(_h[4:6],16)},{_a})'

                    _rc_cats_data = []
                    for _rci, (_rcc, _rcv) in enumerate(_rc_cats_seen.items()):
                        _rc_cats_data.append({
                            'cat': _rcc,
                            'color': _rc_cat_colors[_rci % len(_rc_cat_colors)],
                            'sub': f'${_rcv["subtotal"]:,.0f}'.replace(',', '.'),
                            'subtotal_raw': float(_rcv['subtotal']),
                            'items': int(_rcv['items']),
                        })
                    # Orden por valor desc → efecto mosaico
                    _rc_sorted_m = sorted(_rc_cats_data, key=lambda x: x['subtotal_raw'], reverse=True)
                    # 1 fila si ≤4 categorías; 2 filas balanceadas por peso visual (^0.3) si >4
                    if len(_rc_sorted_m) <= 4:
                        _rc_rows_m = [_rc_sorted_m]
                    else:
                        _rc_r1, _rc_r2, _rc_s1, _rc_s2 = [], [], 0.0, 0.0
                        for _mc in _rc_sorted_m:
                            _w = _mc['subtotal_raw'] ** 0.3
                            if _rc_s1 <= _rc_s2:
                                _rc_r1.append(_mc); _rc_s1 += _w
                            else:
                                _rc_r2.append(_mc); _rc_s2 += _w
                        _rc_rows_m = [r for r in (_rc_r1, _rc_r2) if r]

                    _rc_cards_css = (
                        '<style>'
                        '.rc-cats{display:flex;flex-direction:column;gap:5px;margin-bottom:8px;}'
                        '.rc-mrow{display:flex;gap:5px;align-items:stretch;}'
                        '.rc-cat-card{border-radius:7px;padding:7px 11px;min-width:118px;cursor:pointer;'
                        'transition:background .13s,border .13s,opacity .13s;box-sizing:border-box;'
                        'display:flex;flex-direction:column;align-items:flex-start;user-select:none;}'
                        '.rc-cat-card:hover{opacity:.82;}'
                        '.rc-cname{font-family:Montserrat,sans-serif;font-size:11px;font-weight:700;'
                        'text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px;white-space:nowrap;'
                        'overflow:hidden;text-overflow:ellipsis;width:100%;}'
                        '.rc-csub{font-family:Montserrat,sans-serif;font-size:13px;font-weight:800;color:#0f172a;'
                        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;width:100%;}'
                        '.rc-civa{font-family:Montserrat,sans-serif;font-size:9px;font-weight:400;color:#94a3b8;margin-left:4px;}'
                        '.rc-cmeta{font-size:10px;color:#64748b;margin-top:3px;white-space:nowrap;'
                        'overflow:hidden;text-overflow:ellipsis;width:100%;}'
                        '</style>'
                    )
                    _rc_cards_divs = '<div class="rc-cats">'
                    for _row in _rc_rows_m:
                        _row_max = max((c['subtotal_raw'] ** 0.3 for c in _row), default=1) or 1
                        _rc_cards_divs += '<div class="rc-mrow">'
                        for _c in _row:
                            _col = _c['color']
                            _brd = f'1.5px solid {_rc_hex_rgba(_col, 0.3)}'
                            _grow = max(1, round((_c['subtotal_raw'] ** 0.3) / _row_max * 1000))
                            _ni = _c['items']
                            _meta = f"{_ni} {'ítem' if _ni == 1 else 'ítems'}"
                            _dcat = _c['cat'].replace('"', '&quot;')
                            _rc_cards_divs += (
                                f'<div class="rc-cat-card" data-cat="{_dcat}" data-color="{_col}" '
                                f'data-name="{_dcat}" onclick="window.rcFilterCat(this)" '
                                f'style="background:#fff;border:{_brd};border-left:4px solid {_col};flex:{_grow} {_grow} 0;">'
                                f'<div class="rc-cname" style="color:{_col};">{_c["cat"]}</div>'
                                f'<div class="rc-csub">{_c["sub"]}<span class="rc-civa">s/IVA</span></div>'
                                f'<div class="rc-cmeta">{_meta}</div>'
                                f'</div>'
                            )
                        _rc_cards_divs += '</div>'
                    _rc_cards_divs += '</div>'
                    _cats_cards_html = _rc_cards_css + _rc_cards_divs
                    # Mapa categoría→color (mismo palette del mosaico) para pintar
                    # los badges de categoría en cada fila de la tabla.
                    _rc_cat_color_map = {_c['cat']: _c['color'] for _c in _rc_cats_data}

                    _rc_html = build_rc_html(
                        _rc_prods, _rc_cat_json, {},
                        _rc_items_comprados, _rc_es_admin,
                        supa_url=SUPABASE_URL, supa_key=SUPABASE_KEY,
                        ep=_rc_ep,
                        usuario=st.session_state.get('auth_nombre', ''),
                        items_ya_comprados_json=_rc_ya_comprados_json,
                        total_items_presupuesto=len(_rc_prods),
                        cats_cards_html=_cats_cards_html,
                        proveedores=_proveedores,
                        cat_colors=_rc_cat_color_map,
                    )
                    # Alto extra por las filas del mosaico de categorías (1 ó 2 filas)
                    _rc_cats_rows = len(_rc_rows_m) if _rc_rows_m else 1
                    _rc_cards_extra = _rc_cats_rows * 66 + 8
                    _rc_height = min(len(_rc_prods) * 37 + 580 + _rc_cards_extra, 1200)
                    # Hash que cambia ante CUALQUIER cambio de cobertura (no solo de
                    # llaves): si un ítem pasa de parcial a completo, o se guarda un
                    # nuevo stock, el iframe se regenera (si no, se queda pegado en
                    # "Guardado. Actualizando..." mostrando el estado viejo).
                    _rc_items_hash = str(sorted(
                        (str(_k), int(_v.get('stock_units', 0) or 0),
                         int(_v.get('bought_units', 0) or 0), float(_v.get('real', 0) or 0))
                        for _k, _v in _rc_items_comprados.items()
                    )) + f'|{len(_rc_existentes)}'
                    components.html(_rc_html + f'<!-- {_rc_items_hash} -->', height=_rc_height, scrolling=False)
                    # Botón nativo OCULTO de refresco. El iframe guarda el registro
                    # DIRECTO en Supabase (anon key) y luego clickea este botón: acá
                    # limpiamos la cache de "ya comprados" y re-renderizamos para que
                    # el nuevo registro aparezca de inmediato (fiable, sin query param).
                    st.markdown(
                        "<style>.st-key-_rc_apply{height:0!important;overflow:hidden!important;"
                        "margin:0!important;padding:0!important;position:absolute!important;"
                        "left:-9999px!important}.st-key-_rc_apply>div{height:0!important;"
                        "overflow:hidden!important}</style>",
                        unsafe_allow_html=True)
                    if st.button("apply", key="_rc_apply"):
                        try:
                            obtener_items_comprados.clear()
                        except Exception:
                            pass
                        st.rerun()

                    # Interceptor del botón "Salir del proyecto": revisa (por JS,
                    # antes del rerun) si la tabla tiene datos sin guardar → avisa.
                    components.html(_RC_EXIT_INTERCEPT_JS, height=0)

                if _rc_existentes:
                    st.markdown(_titulo_op("file", "Información de facturas"), unsafe_allow_html=True)
                    _mut_err = st.session_state.pop('_rc_mut_error', None)
                    if _mut_err:
                        st.error(f"&#10060; No se pudo aplicar el cambio: {_mut_err}")

                    # Datos para el iframe interactivo del historial (edición IN-PLACE).
                    # _pn_set: nombres de ítems del presupuesto → clasificar cada
                    # compra (normal / adicional con-registro / sin-registro).
                    _pn_set = {str(_p.get('Item', '')) for _p in _rc_prods_raw}
                    _regs_data = []
                    _hist_rows_total = 0
                    for _rce in _rc_existentes:
                        _items_h = _rce.get('items') or []
                        if isinstance(_items_h, str):
                            try:
                                _items_h = json.loads(_items_h)
                            except Exception:
                                _items_h = []
                        _fecha_raw = _rce.get('fecha_registro', '') or ''
                        try:
                            _fecha_txt = datetime.fromisoformat(
                                _fecha_raw.replace('Z', '+00:00')).astimezone(_tz_cl).strftime('%d/%m/%Y %H:%M')
                        except Exception:
                            _fecha_txt = str(_fecha_raw)[:10]
                        # Badge de tipo del registro (misma clasificación que MAIN):
                        # sin registro / adicional con registro / normal / mixto.
                        _sn = any(_i.get('sin_registro') for _i in _items_h)
                        _cn = any(_i.get('es_adicional') and not _i.get('sin_registro') for _i in _items_h)
                        _nm = any(str(_i.get('item', '')) in _pn_set for _i in _items_h if _i.get('item'))
                        if sum([_nm, _cn, _sn]) >= 2:
                            _tipo_lbl, _tipo_bg, _tipo_fg = 'Mixto', '#ede9fe', '#6d28d9'
                        elif _sn:
                            _tipo_lbl, _tipo_bg, _tipo_fg = 'Adicional sin registro', '#fce7f3', '#be185d'
                        elif _cn:
                            _tipo_lbl, _tipo_bg, _tipo_fg = 'Adicional con registro', '#ffedd5', '#c2410c'
                        else:
                            _tipo_lbl, _tipo_bg, _tipo_fg = 'Normal', '#dcfce7', '#15803d'
                        # Nombre del proveedor unificado (canónico, mayúsculas) para
                        # que el historial quede uniforme; el input de edición también
                        # se pre-llena con esta forma → normaliza al guardar.
                        _lugar_raw = str(_rce.get('lugar_compra', '') or '').strip()
                        _lugar_canon = (_prov_canon_by_key.get(_norm_prov_key(_lugar_raw), _lugar_raw)
                                        if _lugar_raw else 'Compra sin lugar')
                        # Registro de INVENTARIO (stock propio; $0 = ahorro puro):
                        # tipo_compra == "stock" o lugar == "INVENTARIO". Se etiqueta
                        # verde y su "proveedor" se unifica como INVENTARIO.
                        _tipo_raw = str(_rce.get('tipo_compra', '') or '').strip().lower()
                        _es_inv = (_tipo_raw == 'stock') or (_lugar_raw.upper() == 'INVENTARIO')
                        if _es_inv:
                            _lugar_canon = 'INVENTARIO'
                            _tipo_lbl, _tipo_bg, _tipo_fg = 'Inventario', '#dcfce7', '#166534'
                        _furl_h = (_rce.get('factura_url') or '').strip()
                        _fnom_h = (_rce.get('factura_nombre') or '').strip() or 'Factura'
                        _ext_h = _fnom_h.lower().rsplit('.', 1)[-1] if '.' in _fnom_h else ''
                        if _ext_h not in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'pdf') and '.' in _furl_h:
                            _ext_h = _furl_h.split('?')[0].lower().rsplit('.', 1)[-1]
                        _regs_data.append({
                            'id':          _rce.get('id'),
                            'lugar':       _lugar_canon,
                            'obs':         _rce.get('observaciones', '') or '',
                            'fent':        _rce.get('fecha_entrega_compra', '') or '',
                            'tipo':        (str(_rce.get('tipo_compra', '') or '').capitalize() or '—'),
                            'tipo_lbl':    _tipo_lbl,
                            'tipo_bg':     _tipo_bg,
                            'tipo_fg':     _tipo_fg,
                            'inv':         _es_inv,
                            'fecha':       _fecha_txt,
                            'usuario':     _rce.get('usuario_registro', '') or '—',
                            'balance':     float(_rce.get('balance', 0) or 0),
                            'tp':          float(_rce.get('total_presupuestado', 0) or 0),
                            'tr':          float(_rce.get('total_real', 0) or 0),
                            'factura_url': _furl_h,
                            'factura_nom': _fnom_h,
                            'is_img':      _ext_h in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'),
                            'items': [{
                                'cat':  str(_it.get('categoria', '')),
                                'item': str(_it.get('item', '')),
                                'cant': float(_it.get('cantidad', 1) or 1),
                                'pp':   float(_it.get('precio_presupuestado', 0) or 0),
                                'pr':   float(_it.get('precio_real', 0) or 0),
                                'sin':  bool(_it.get('sin_registro', False)),
                                'stock': bool(_it.get('stock', False)),
                                'sqty': float(_it.get('stock_cantidad', _it.get('cantidad', 1)) or 0)
                                        if _it.get('stock') else 0,
                            } for _it in _items_h],
                        })
                        _hist_rows_total += max(1, len(_items_h))

                    # Alto INICIAL del iframe ~ tarjetas CONTRAÍDAS + filtros. El
                    # iframe se auto-ajusta (fit por body.scrollHeight + ResizeObserver)
                    # al expandir/contraer, así que no deja huecos ni scroll interno;
                    # este valor es solo el punto de partida / fallback.
                    # +300 aprox. para el título + cards de proveedor (van dentro
                    # del mismo iframe); el auto-fit ajusta el valor real.
                    _n_reg = len(_regs_data)
                    _hist_h = min(150 + _n_reg * 62 + 300, 3200)
                    if _OPER_OK:
                        components.html(build_historial_rc_html(
                            _regs_data, _rc_ep,
                            supa_url=SUPABASE_URL, supa_key=SUPABASE_KEY),
                            height=_hist_h, scrolling=True)

                    # ── Productos EN STOCK (ahorro puro): precio real $0 ──
                    # Cada ítem NORMAL del presupuesto registrado con precio real $0
                    # (marcado "en stock" o ingresado en $0) es un producto que ya se
                    # tenía: no se invirtió en él, y su presupuestado es AHORRO PURO.
                    _stock_list = []
                    _stock_seen = set()
                    _stock_total = 0.0
                    for _rg in _regs_data:
                        for _it in _rg['items']:
                            _nom = _it['item']
                            _es_norm = _nom in _pn_set and not _it['sin']
                            # Un ítem con flag stock SIEMPRE es inventario (aunque su
                            # nombre no calce exacto con el presupuesto); además, un
                            # ítem normal a $0 se considera stock.
                            _es_stock = bool(_it.get('stock')) or (_it['pr'] == 0 and _es_norm)
                            if _nom and _es_stock and _nom not in _stock_seen:
                                _stock_seen.add(_nom)
                                # Unidades en stock (ahorro puro). Sin sqty explícito
                                # (datos previos o $0 sin flag) → todas las unidades.
                                _sq = _it.get('sqty') or _it['cant']
                                _sq = min(_sq, _it['cant'])
                                _ah = _it['pp'] * _sq
                                _stock_total += _ah
                                _stock_list.append((_it['cat'], _nom, _sq, _ah))
                    if _stock_list:
                        _stock_list.sort(key=lambda _x: _x[3], reverse=True)
                        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
                        st.markdown(_titulo_op("package", "Productos en stock · Ahorro puro", "#16a34a"),
                                    unsafe_allow_html=True)
                        _rows_html = ""
                        for _c, _n, _q, _a in _stock_list:
                            _rows_html += (
                                '<div style="display:flex;align-items:center;justify-content:space-between;'
                                'gap:10px;padding:10px 14px;border-bottom:1px solid #ecfdf5;">'
                                '<div style="min-width:0;">'
                                '<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.9rem;'
                                'color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'
                                f'{_esc_html(_n)}</div>'
                                '<div style="font-size:0.72rem;color:#64748b;text-transform:uppercase;'
                                f'letter-spacing:.04em;margin-top:2px;">{_esc_html(_c)} · {int(_q)} u.</div>'
                                '</div>'
                                '<div style="text-align:right;white-space:nowrap;">'
                                '<div style="font-family:Montserrat,sans-serif;font-weight:800;font-size:0.95rem;'
                                f'color:#16a34a;">{_fmt_clp(_a)}</div>'
                                '<div style="font-size:0.66rem;color:#16a34a;text-transform:uppercase;'
                                'letter-spacing:.05em;">Ahorro</div>'
                                '</div></div>'
                            )
                        _cnt = len(_stock_list)
                        st.markdown(
                            '<div style="border:1.5px solid #bbf7d0;border-radius:14px;overflow:hidden;'
                            'box-shadow:0 1px 3px rgba(16,163,74,0.08);background:#fff;">'
                            '<div style="display:flex;align-items:center;justify-content:space-between;'
                            'gap:10px;padding:12px 14px;background:linear-gradient(90deg,#f0fdf4,#ffffff);'
                            'border-bottom:1px solid #bbf7d0;">'
                            '<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.78rem;'
                            'color:#166534;letter-spacing:.04em;text-transform:uppercase;">'
                            f'{_ic_op("check", "#16a34a", 15, 7, -2)}{_cnt} '
                            f'producto{"s" if _cnt != 1 else ""} que ya tenías (sin inversión)</div>'
                            '<div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.05rem;'
                            f'color:#16a34a;white-space:nowrap;">{_fmt_clp(_stock_total)}</div>'
                            '</div>'
                            + _rows_html +
                            '</div>', unsafe_allow_html=True)

                    # ── Exportar Balance (admin/root) — al final, bajo proveedores ──
                    if _rol in ('root', 'admin') and _OPER_OK:
                        _bal_dc = {'Nombre': _rc_row.get('cliente_nombre', ''), 'RUT': _rc_row.get('cliente_rut', '')}
                        _bal_da = {'Nombre Ejecutivo': _rc_row.get('asesor_nombre', '')}
                        _bal_prods = _rc_prods_raw
                        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
                        st.markdown(_titulo_op("chart", "Exportar Balance"), unsafe_allow_html=True)
                        _ekeys = [f".st-key-pdf_balance_{_rc_ep}", f".st-key-pdf_balance_v_{_rc_ep}",
                                  f".st-key-xls_balance_{_rc_ep}"]
                        st.markdown(
                            "<style>"
                            + ",".join(_k + " button" for _k in _ekeys)
                            + "{border:1.5px solid #e2e8f0 !important;border-radius:11px !important;"
                            "padding:16px 12px !important;font-weight:700 !important;color:#334155 !important;"
                            "box-shadow:0 1px 3px rgba(15,23,42,0.05) !important;transition:all .15s ease !important;}"
                            + ",".join(_k + " button:hover" for _k in _ekeys)
                            + "{border-color:#5b7cfa !important;color:#5b7cfa !important;"
                            "box-shadow:0 8px 18px rgba(91,124,250,0.18) !important;transform:translateY(-2px);}"
                            "</style>", unsafe_allow_html=True)
                        st.markdown(
                            '<div style="font-size:0.78rem;color:#64748b;margin:0 0 10px 2px;">'
                            'Descarga el balance de compras del proyecto (presupuestado vs. precio real).'
                            '</div>', unsafe_allow_html=True)
                        _bcol1, _bcol2, _bcol3 = st.columns(3)
                        with _bcol1:
                            if st.button('PDF Balance', icon=":material/picture_as_pdf:", key=f'pdf_balance_{_rc_ep}', use_container_width=True):
                                with st.spinner('Generando PDF...'):
                                    try:
                                        _bal_pdf = generar_pdf_balance(_rc_ep, _bal_dc, _bal_da, _rc_existentes, _bal_prods, incluir_varios=False)
                                        st.download_button('Descargar (sin Varios)', icon=":material/download:", data=_bal_pdf,
                                            file_name=f'Balance_{_rc_ep}_sin_varios.pdf', mime='application/pdf',
                                            key=f'dl_balance_{_rc_ep}')
                                    except Exception as _e_bal:
                                        st.error(f'Error: {_e_bal}')
                        with _bcol2:
                            if st.button('PDF Balance + Varios', icon=":material/picture_as_pdf:", key=f'pdf_balance_v_{_rc_ep}', use_container_width=True):
                                with st.spinner('Generando PDF...'):
                                    try:
                                        _bal_pdf_v = generar_pdf_balance(_rc_ep, _bal_dc, _bal_da, _rc_existentes, _bal_prods, incluir_varios=True)
                                        st.download_button('Descargar (con Varios)', icon=":material/download:", data=_bal_pdf_v,
                                            file_name=f'Balance_{_rc_ep}_con_varios.pdf', mime='application/pdf',
                                            key=f'dl_balance_v_{_rc_ep}')
                                    except Exception as _e_bal_v:
                                        st.error(f'Error: {_e_bal_v}')
                        with _bcol3:
                            if st.button('Excel Precios', icon=":material/table_view:", key=f'xls_balance_{_rc_ep}', use_container_width=True):
                                with st.spinner('Generando Excel...'):
                                    try:
                                        _bal_xls = generar_excel_balance(_rc_ep, _rc_existentes, _bal_prods)
                                        st.download_button('Descargar Excel', icon=":material/download:", data=_bal_xls,
                                            file_name=f'Precios_Reales_{_rc_ep}.xlsx',
                                            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                            key=f'dl_xls_{_rc_ep}')
                                    except Exception as _e_xls:
                                        st.error(f'Error: {_e_xls}')


    # ================================================================
    # SUB-PESTAÑA: ACTA DE CLIENTES
    # ================================================================
    with _sub_acta:
        st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 12px 0;">&#128203; Acta de Clientes</div>', unsafe_allow_html=True)

        try:
            _ac_resp = supa_admin.table('cotizaciones').select(
                'numero,cliente_nombre,contrato_notariado_url,acta_url,acta_nombre,fecha_entrega,estado'
            ).not_.is_('contrato_notariado_url', 'null').order('fecha_creacion', desc=True).execute()
            _ac_cots = [r for r in (_ac_resp.data or []) if r.get('contrato_notariado_url')]
        except Exception:
            _ac_cots = []

        if not _ac_cots:
            st.info('No hay proyectos adjudicados a&#250;n.')
        else:
            _ac_opts = {f"{r['numero']} — {r.get('cliente_nombre') or 'S/C'}": r for r in _ac_cots}
            _ac_sel_label = st.selectbox('Seleccionar proyecto', list(_ac_opts.keys()), key='ac_sel_proyecto')
            _ac_row = _ac_opts.get(_ac_sel_label, {})
            _ac_ep  = _ac_row.get('numero', '')

            if _ac_ep:
                _ac_tiene_acta = bool(_ac_row.get('acta_url'))

                if _ac_tiene_acta:
                    try:
                        _ac_fecha = datetime.fromisoformat(
                            _ac_row['fecha_entrega'].replace('Z', '+00:00')
                        ).astimezone(_tz_cl).strftime('%d/%m/%Y %H:%M')
                    except Exception:
                        _ac_fecha = '—'
                    st.success(f'&#9989; Acta subida el {_ac_fecha}')
                    st.markdown(f'<div style="font-size:0.85rem;margin:4px 0;">&#128196; <b>{_ac_row.get("acta_nombre","acta.pdf")}</b></div>', unsafe_allow_html=True)
                    st.markdown(f'<div style="font-size:0.85rem;margin:4px 0;">Estado: <span style="background:#7c3aed;color:#fff;padding:2px 10px;border-radius:99px;font-weight:700;font-size:0.78rem;">&#128995; PROYECTO TERMINADO</span></div>', unsafe_allow_html=True)
                    if _ac_row.get('acta_url'):
                        st.markdown(f'[&#128206; Ver acta]({_ac_row["acta_url"]})', unsafe_allow_html=True)
                else:
                    st.markdown('<div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:10px 14px;font-size:0.85rem;margin-bottom:12px;">&#9888;&#65039; Este proyecto a&#250;n no tiene acta de recepci&#243;n conforme.</div>', unsafe_allow_html=True)
                    _ac_file = st.file_uploader('&#128206; Subir acta firmada (PDF)', type=['pdf'], key=f'ac_file_{_ac_ep}')
                    if _ac_file:
                        st.success(f'&#9989; Archivo listo: {_ac_file.name}')
                        st.warning('Al confirmar, el estado cambiar&#225; a **PROYECTO TERMINADO** y se congelar&#225;n los contadores.')
                        if st.button('&#128203; Confirmar entrega y subir acta',
                                     key=f'ac_confirmar_{_ac_ep}', use_container_width=True):
                            with st.spinner('Subiendo acta...'):
                                if _guardar_acta is None or _registrar_entrega is None:
                                    st.error("&#10060; Las funciones de entrega no est&#225;n disponibles en modo modular.")
                                else:
                                    _ac_url, _ac_err = _guardar_acta(_ac_file.getvalue(), _ac_ep, _ac_file.name)
                                    if _ac_err:
                                        st.error(f'Error subiendo acta: {_ac_err}')
                                    else:
                                        _ac_ok, _ac_err2 = _registrar_entrega(_ac_ep, _ac_url, _ac_file.name)
                                        if _ac_ok:
                                            st.success(f'&#9989; Proyecto {_ac_ep} marcado como PROYECTO TERMINADO')
                                            for _k in ['oper_results', 'resultados_busqueda', '_oper_ej_prev']:
                                                st.session_state.pop(_k, None)
                                            st.balloons()
                                            st.rerun()
                                        else:
                                            st.error(f'Error registrando entrega: {_ac_err2}')
