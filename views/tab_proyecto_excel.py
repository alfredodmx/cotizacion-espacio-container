"""
Tab PROYECTO EXCEL — Carga y gestión del Excel de proyecto (presupuesto detallado).
Código fuente original: app.py líneas 13150-13510 (with tab5) + 16671-16955 (with tab7 3D BETA)
"""
import streamlit as st


def render_tab_proyecto_excel(supabase, supabase_admin, supa_url, supa_key, **deps):
    """
    Renderiza el tab de proyecto Excel (admin).
    deps: cargar_excel_activo, subir_excel, listar_versiones_excel, ...
    """
    # TODO: mover código de app.py líneas 13150-13510 aquí
    st.info("🚧 Tab proyecto Excel — pendiente de migración desde app.py")


def render_tab_3d_visor(supabase, supa_url, **deps):
    """
    Renderiza el tab del visor 3D BETA.
    deps: detectar_navegador, anthropic_client, ...
    """
    # TODO: mover código de app.py líneas 16671-16955 aquí
    st.info("🚧 Tab 3D visor — pendiente de migración desde app.py")
