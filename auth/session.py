"""
Inicializacion y gestion del session_state de Streamlit.
Incluye: valores por defecto, recuperacion de sesion via ?_sess, timeout 8h.
"""
import time
from datetime import datetime, timedelta

import streamlit as st

from auth.roles import get_rol

SESSION_TIMEOUT = 8 * 3600  # segundos


_SESSION_DEFAULTS: dict = {
    # ── Auth ──
    'modo_admin':           False,
    'mostrar_login':        False,
    'auth_user':            None,
    'auth_email':           "",
    'auth_nombre':          "",
    'es_supervisor':        False,
    'es_root':              False,
    'es_operacion':         False,
    'rol_usuario':          "ejecutivo",
    # ── Datos del cliente ──
    'nombre_input':         "",
    'correo_input':         "",
    'direccion_input':      "",
    'cliente_comuna':       "",
    'cliente_region':       "",
    'proyecto_direccion':   "",
    'proyecto_comuna':      "",
    'proyecto_region':      "",
    'cliente_tipo':         "natural",
    'cliente_empresa':      "",
    'cliente_rut_empresa':  "",
    'rut_empresa_raw':      "",
    'rut_empresa_display':  "",
    'rut_empresa_valido':   False,
    'rut_empresa_mensaje':  "",
    'observaciones_input':  "",
    # ── RUT / teléfono ──
    'rut_raw':              "",
    'rut_display':          "",
    'rut_valido':           False,
    'rut_mensaje':          "",
    'telefono_raw':         "",
    'telefono_valido':      False,
    'telefono_mensaje':     "",
    # ── Asesor ──
    'asesor_seleccionado':  "Seleccionar asesor",
    'correo_asesor':        "",
    'telefono_asesor':      "",
    'telefono_asesor_raw':  "",
    'asesor_correo_temp':   "",
    # ── Cotización ──
    'carrito':              [],
    'margen':               0.0,
    'cotizacion_seleccionada': None,
    'cotizacion_cargada':   None,
    'cotizacion_a_cargar':  None,
    'numero_a_cargar_pendiente': None,
    'cargar_cotizacion_trigger': False,
    'recien_guardado':      False,
    'hash_ultimo_guardado': None,
    'recien_cargado':       False,
    # ── UI / visor ──
    'mostrar_visor':        False,
    'pdf_actual':           None,
    'pdf_nombre':           "",
    'numero_en_visor':      None,
    'pdf_url':              None,
    'mostrar_toast_exito':  False,
    'toast_numero_ep':      "",
    'mostrar_advertencia_cerrar': False,
    'trigger_cerrar_cotizacion':  False,
    'datos_pendientes_cerrar':    None,
    # ── Planos / archivos ──
    'plano_adjunto':        None,
    'plano_nombre':         "",
    # ── Misceláneos ──
    'counter':              0,
    '_rerun_lock':          False,
}


def _defaults_fecha():
    """Retorna defaults de fechas calculados en tiempo real."""
    return {
        'fecha_inicio':  datetime.now().date(),
        'fecha_termino': (datetime.now() + timedelta(days=15)).date(),
    }


def init_session_state() -> None:
    """Inicializa todas las variables de session_state con sus valores por defecto."""
    for key, val in _SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = val

    for key, val in _defaults_fecha().items():
        if key not in st.session_state:
            st.session_state[key] = val


def recover_session_from_query_param(supabase_client) -> None:
    """Recupera sesion Supabase desde el query param ?_sess=<token>."""
    _sess_token = st.query_params.get("_sess")
    if not st.session_state.auth_user and _sess_token:
        try:
            _sess_user = supabase_client.auth.get_user(_sess_token)
            if _sess_user and _sess_user.user:
                _u    = _sess_user.user
                _meta = _u.user_metadata or {}
                _rol  = get_rol(_u.email, _meta)
                st.session_state.auth_user    = str(_u.id)
                st.session_state.auth_email   = _u.email or ""
                st.session_state.auth_nombre  = _meta.get("nombre", _u.email or "")
                st.session_state.rol_usuario  = _rol
                st.session_state.es_supervisor = _rol in ("root", "admin")
                st.session_state.es_root       = _rol == "root"
                st.session_state.es_operacion  = _rol == "operacion"
                st.session_state.modo_admin    = _rol in ("root", "admin")
                st.query_params.clear()
                st.rerun()
        except Exception:
            st.query_params.clear()


def process_query_params() -> None:
    """Procesa query params especiales: mgfab, hist_filtro_rc, cat_filtro, rc_cat_filtro, _fabg."""
    # Margen desde FAB
    _mgfab = st.query_params.get("mgfab")
    if _mgfab is not None:
        try:
            _mgfab_val = max(0.0, min(100.0, float(_mgfab)))
            st.session_state['margen'] = _mgfab_val
        except ValueError:
            pass
        st.query_params.clear()

    # Filtro historial RC
    _qp_hist = st.query_params.get('hist_filtro_rc', '')
    if 'hist_filtro_rc' in st.query_params:
        st.session_state['_hist_filtro_rc'] = _qp_hist
        st.query_params.pop('hist_filtro_rc')
        st.rerun()

    # Filtro de categoría en presupuesto
    _qp_cat_filtro = st.query_params.get('cat_filtro', '')
    if _qp_cat_filtro:
        if _qp_cat_filtro == '__clear__' or _qp_cat_filtro == st.session_state.get('_cat_filtro_activo', ''):
            st.session_state.pop('_cat_filtro_activo', None)
        else:
            st.session_state['_cat_filtro_activo'] = _qp_cat_filtro
        st.query_params.pop('cat_filtro')

    _qp_rc_cat_filtro = st.query_params.get('rc_cat_filtro', '')
    if _qp_rc_cat_filtro:
        if _qp_rc_cat_filtro == '__clear__' or _qp_rc_cat_filtro == st.session_state.get('_rc_cat_filtro_activo', ''):
            st.session_state.pop('_rc_cat_filtro_activo', None)
        else:
            st.session_state['_rc_cat_filtro_activo'] = _qp_rc_cat_filtro
        st.query_params.pop('rc_cat_filtro')
        st.rerun()

    # Acción guardar desde FAB
    if st.query_params.get("_fabg") == "1":
        st.query_params.clear()
        st.session_state['_trigger_guardar_fab'] = True


def check_session_timeout() -> None:
    """Cierra la sesion si lleva mas de SESSION_TIMEOUT segundos sin actividad."""
    _now = time.time()
    _last = st.session_state.get('_last_activity', 0)
    if st.session_state.auth_user and _last > 0:
        if (_now - _last) > SESSION_TIMEOUT:
            for _k in list(st.session_state.keys()):
                del st.session_state[_k]
            st.warning("⏱️ Tu sesión expiró por inactividad. Por favor inicia sesión nuevamente.")
            st.rerun()
    if st.session_state.get('auth_user'):
        st.session_state['_last_activity'] = _now
