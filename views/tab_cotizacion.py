"""
Tab PRESUPUESTO — Carrito de cotización, items, margen, PDF.
Código fuente original: app.py líneas 9938-10797 (with tab1)
"""
import streamlit as st


def render_tab_cotizacion(supabase, supabase_admin, supa_url, supa_key, **deps):
    """
    Renderiza el tab de presupuesto/carrito.
    deps contiene funciones y datos inyectados desde el router:
        cargar_catalogo, guardar_cotizacion, generar_pdf_completo,
        generar_pdf_cliente, calcular_totales_rc, ...
    """
    # TODO: mover código de app.py líneas 9938-10797 aquí
    st.info("🚧 Tab presupuesto — pendiente de migración desde app.py")
