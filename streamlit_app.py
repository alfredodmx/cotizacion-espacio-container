"""
Router principal — reemplaza el monolito app.py.
Orquesta: config → sesión → auth → vistas.

Para activar: cambia el punto de entrada en .streamlit/config.toml o ejecuta
    streamlit run main.py
"""
import streamlit as st

# ── 1. Config de página (DEBE ir antes de cualquier otro st.*) ─────────────
st.set_page_config(layout="wide", page_title="Cotizador PRO", page_icon="📊")

# ── 2. Clientes Supabase ───────────────────────────────────────────────────
from config.supabase import get_supabase, get_supabase_admin, get_supabase_urls

supabase       = get_supabase()
supabase_admin = get_supabase_admin()
SUPABASE_URL, SUPABASE_KEY = get_supabase_urls()

# ── 3. Inicializar session_state ───────────────────────────────────────────
from auth.session import init_session_state, recover_session_from_query_param
from auth.session import check_session_timeout, process_query_params

init_session_state()

# ── 4. Ruta pública: ?cliente=1 ────────────────────────────────────────────
if st.query_params.get("cliente") == "1":
    from views.cliente_view import render_cliente_view
    render_cliente_view(supabase_admin, SUPABASE_URL, SUPABASE_KEY)
    # render_cliente_view termina con st.stop()

# ── 5. Recuperar sesión desde ?_sess ──────────────────────────────────────
recover_session_from_query_param(supabase)

# ── 6. Timeout de inactividad (8h) ─────────────────────────────────────────
check_session_timeout()

# ── 7. Pantalla de login ───────────────────────────────────────────────────
if not st.session_state.auth_user:
    from auth.auth_service import login_usuario
    from views.login_view import render_login
    render_login(login_usuario)
    # render_login termina con st.stop()

# ── 8. Query params post-login ─────────────────────────────────────────────
process_query_params()

# ── 9. Routing por rol → tabs ──────────────────────────────────────────────
_rol = st.session_state.get('rol_usuario', 'ejecutivo')

if _rol == 'root':
    (tab_dash, tab1, tab2, tab3, tab6, tab7, tab_contrato,
     tab4, tab5, tab_salud, tab_usuarios, tab_notif,
     tab_reporte, tab_oper, tab_admindata, tab_formulario) = st.tabs([
        "📊 DASHBOARD", "📋 PRESUPUESTO", "👤 DATOS", "📂 COTIZACIONES",
        "✏️ EDICIÓN PDF", "🏆 RANKING", "📄 CONTRATO", "🧊 3D BETA",
        "📊 PROYECTO EXCEL", "🛡️ SISTEMA", "👥 USUARIOS", "📣 NOTIFICACIONES",
        "📈 REPORTE BI", "⚙️ OPERACIONES", "⚠️ ADMINISTRACIÓN DE DATOS",
        "📝 FORMULARIO CLIENTE",
    ])

elif _rol == 'admin':
    (tab1, tab3, tab2, tab_contrato, tab_oper, tab_usuarios,
     tab5, tab6, tab7, tab4, tab_notif, tab_dash,
     tab_reporte, tab_admindata, tab_formulario) = st.tabs([
        "📋 PRESUPUESTO", "📂 COTIZACIONES", "👤 DATOS", "📄 CONTRATO",
        "⚙️ OPERACIONES", "👥 USUARIOS", "📊 PROYECTO EXCEL", "✏️ EDICIÓN PDF",
        "🏆 RANKING", "🧊 3D BETA", "📣 NOTIFICACIONES", "📊 DASHBOARD",
        "📈 REPORTE BI", "⚠️ ADMINISTRACIÓN DE DATOS", "📝 FORMULARIO CLIENTE",
    ])
    tab_salud = None

elif _rol == 'operacion':
    (tab_oper,) = st.tabs(["⚙️ OPERACIONES"])
    (tab_dash, tab1, tab2, tab3, tab4, tab5, tab6, tab7,
     tab_contrato, tab_salud, tab_usuarios, tab_notif,
     tab_reporte, tab_admindata, tab_formulario) = (None,) * 15

else:  # ejecutivo
    (tab1, tab2, tab3, tab_contrato, tab7, tab4, tab_formulario) = st.tabs([
        "📋 PRESUPUESTO", "👤 DATOS", "📂 COTIZACIONES", "📄 CONTRATO",
        "🏆 RANKING", "🧊 3D BETA", "📝 FORMULARIO CLIENTE",
    ])
    (tab_dash, tab_reporte, tab_salud, tab5, tab6,
     tab_usuarios, tab_notif, tab_oper, tab_admindata) = (None,) * 9

# ── 10. Renderizar cada tab ────────────────────────────────────────────────
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

if tab1          is not None:
    with tab1:          render_tab_cotizacion(**_deps)
if tab2          is not None:
    with tab2:          render_tab_datos_cliente(**_deps)
if tab3          is not None:
    with tab3:          render_tab_historial(**_deps)
if tab_contrato  is not None:
    with tab_contrato:  render_tab_contrato(**_deps)
if tab_oper      is not None:
    with tab_oper:      render_tab_operaciones(**_deps)
if tab_usuarios  is not None:
    with tab_usuarios:  render_tab_usuarios(supabase_admin=supabase_admin)
if tab_dash      is not None:
    with tab_dash:      render_tab_dashboard(**_deps)
if tab_notif     is not None:
    with tab_notif:     render_tab_notificaciones(supabase=supabase)
if tab4          is not None:
    with tab4:          render_tab_3d_visor(supabase=supabase, supa_url=SUPABASE_URL)
if tab_salud     is not None:
    with tab_salud:     render_tab_salud(**_deps)
if tab6          is not None:
    with tab6:          render_tab_pdf(supabase=supabase, supa_url=SUPABASE_URL, supa_key=SUPABASE_KEY)
if tab5          is not None:
    with tab5:          render_tab_proyecto_excel(**_deps)
if tab7          is not None:
    with tab7:          render_tab_ranking(supabase=supabase)
if tab_formulario is not None:
    with tab_formulario: render_tab_formulario(**_deps)
if tab_admindata is not None:
    with tab_admindata: render_tab_admindata(**_deps)
if tab_reporte   is not None:
    with tab_reporte:   render_tab_reporte(supabase=supabase)
