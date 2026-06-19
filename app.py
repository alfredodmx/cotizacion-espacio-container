"""
Punto de entrada para Streamlit Cloud (main module: app.py).
Todo el código real vive en streamlit_app.py.
"""
import streamlit as st

st.set_page_config(layout="wide", page_title="Cotizador PRO", page_icon="📊")

from config.supabase import get_supabase, get_supabase_admin, get_supabase_urls

supabase       = get_supabase()
supabase_admin = get_supabase_admin()
SUPABASE_URL, SUPABASE_KEY = get_supabase_urls()

from auth.session import init_session_state, recover_session_from_query_param
from auth.session import check_session_timeout, process_query_params

init_session_state()

if st.query_params.get("cliente") == "1":
    from views.cliente_view import render_cliente_view
    render_cliente_view(supabase_admin, SUPABASE_URL, SUPABASE_KEY)

recover_session_from_query_param(supabase)
check_session_timeout()

if not st.session_state.auth_user:
    from auth.auth_service import login_usuario
    from views.login_view import render_login
    render_login(login_usuario)

process_query_params()

from views.layout import render_layout
render_layout()

from views.tab_cotizacion import render_floating_panels, render_cerrar_cotizacion_control
render_floating_panels()

_rol = st.session_state.get('rol_usuario', 'ejecutivo')
_nombre = st.session_state.get('auth_nombre') or st.session_state.get('auth_email', '')

_deps = dict(
    supabase=supabase,
    supabase_admin=supabase_admin,
    supa_url=SUPABASE_URL,
    supa_key=SUPABASE_KEY,
)

from views.tab_cotizacion      import render_tab_cotizacion
from views.tab_datos_cliente   import render_tab_datos_cliente
from views.tab_historial       import render_tab_historial
from views.tab_contrato        import render_tab_contrato
from views.tab_operaciones     import render_tab_operaciones
from views.tab_usuarios        import render_tab_usuarios
from views.tab_dashboard       import render_tab_dashboard
from views.tab_notificaciones  import render_tab_notificaciones
from views.tab_ranking         import render_tab_ranking
from views.tab_salud           import render_tab_salud
from views.tab_pdf             import render_tab_pdf
from views.tab_proyecto_excel  import render_tab_proyecto_excel, render_tab_3d_visor
from views.tab_formulario      import render_tab_formulario
from views.tab_admindata       import render_tab_admindata
from views.tab_reporte         import render_tab_reporte
from views.sidebar_nav         import render_sidebar

# Definicion de paginas: key -> (label, icono, render callable)
_PAGES = {
    'dashboard':      ('Dashboard',          'dashboard',      lambda: render_tab_dashboard(**_deps)),
    'presupuesto':    ('Presupuesto',        'presupuesto',    lambda: render_tab_cotizacion(**_deps)),
    'datos':          ('Datos cliente',      'datos',          lambda: render_tab_datos_cliente(**_deps)),
    'cotizaciones':   ('Cotizaciones',       'cotizaciones',   lambda: render_tab_historial(**_deps)),
    'edicion_pdf':    ('Edicion PDF',        'edicion_pdf',    lambda: render_tab_pdf(supabase=supabase, supa_url=SUPABASE_URL, supa_key=SUPABASE_KEY)),
    'ranking':        ('Ranking',            'ranking',        lambda: render_tab_ranking(supabase=supabase)),
    'contrato':       ('Contrato',           'contrato',       lambda: render_tab_contrato(**_deps)),
    '3d':             ('Visor 3D BETA',      '3d',             lambda: render_tab_3d_visor(supabase=supabase, supa_url=SUPABASE_URL)),
    'proyecto_excel': ('Proyecto Excel',     'proyecto_excel', lambda: render_tab_proyecto_excel(**_deps)),
    'sistema':        ('Sistema',            'sistema',        lambda: render_tab_salud(**_deps)),
    'usuarios':       ('Usuarios',           'usuarios',       lambda: render_tab_usuarios(supabase_admin=supabase_admin)),
    'notificaciones': ('Notificaciones',     'notificaciones', lambda: render_tab_notificaciones(supabase=supabase)),
    'reporte':        ('Reporte BI',         'reporte',        lambda: render_tab_reporte(supabase=supabase)),
    'operaciones':    ('Operaciones',        'operaciones',    lambda: render_tab_operaciones(**_deps)),
    'admindata':      ('Admin. de datos',    'admindata',      lambda: render_tab_admindata(**_deps)),
    'formulario':     ('Formulario cliente', 'formulario',     lambda: render_tab_formulario(**_deps)),
}

_ORDER = {
    'root':      ['dashboard','presupuesto','datos','cotizaciones','edicion_pdf','ranking','contrato','3d','proyecto_excel','sistema','usuarios','notificaciones','reporte','operaciones','admindata','formulario'],
    'admin':     ['presupuesto','cotizaciones','datos','contrato','operaciones','usuarios','proyecto_excel','edicion_pdf','ranking','3d','notificaciones','dashboard','reporte','admindata','formulario'],
    'operacion': ['operaciones'],
    'ejecutivo': ['presupuesto','datos','cotizaciones','contrato','ranking','3d','formulario'],
}

_keys = _ORDER.get(_rol, _ORDER['ejecutivo'])
_items = [{'key': k, 'label': _PAGES[k][0], 'icon': _PAGES[k][1]} for k in _keys if k in _PAGES]

# Sidebar de navegacion (devuelve la pagina activa) y render de SOLO esa pagina
_pagina = render_sidebar(_items, _rol, _nombre)
_sel = _PAGES.get(_pagina)
if _sel:
    _sel[2]()

# Control de cierre de cotizacion a nivel GLOBAL y AL FINAL: boton oculto +
# dialogo accionado por el boton "Cerrar" del header.
render_cerrar_cotizacion_control()
