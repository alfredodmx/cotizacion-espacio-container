"""
Servicio de lectura del Excel de cotizador (cotizador.xlsx o version Supabase).
Todas las funciones son cacheadas para evitar re-parseo en cada render.
"""
import io as _io_excel

import pandas as pd
import requests
import streamlit as st

from config.supabase import supabase_admin


def _get_excel_bytes_activo():
    """Descarga el Excel activo desde Supabase Storage. Sin cache propio (lo maneja _excel_src)."""
    try:
        resp = supabase_admin.table('excel_versiones') \
            .select('archivo_url').eq('activa', True).limit(1).execute()
        if resp.data:
            url = resp.data[0]['archivo_url']
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return _io_excel.BytesIO(r.content)
    except Exception:
        pass
    return "cotizador.xlsx"  # fallback local


@st.cache_data(ttl=300, show_spinner=False)
def _excel_src():
    """Retorna la fuente del Excel (BytesIO desde Supabase o path local)."""
    if 'excel_bytes_cache' not in st.session_state:
        st.session_state.excel_bytes_cache = _get_excel_bytes_activo()
    return st.session_state.excel_bytes_cache


@st.cache_data(ttl=300, show_spinner=False)
def _leer_hoja_excel(nombre_hoja: str) -> pd.DataFrame:
    """Lee y cachea una hoja del Excel."""
    try:
        return pd.read_excel(_excel_src(), sheet_name=nombre_hoja)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def _leer_bd_total() -> pd.DataFrame:
    """Lee y cachea la hoja 'BD Total'."""
    return pd.read_excel(_excel_src(), sheet_name="BD Total")[["Item", "P. Unitario real"]]


@st.cache_data(ttl=120, show_spinner=False)
def _leer_hojas_disponibles() -> list[str]:
    """Lista las hojas disponibles en el Excel."""
    try:
        return pd.ExcelFile(_get_excel_bytes_activo()).sheet_names
    except Exception:
        try:
            return pd.ExcelFile(_excel_src()).sheet_names
        except Exception:
            return []


@st.cache_data(ttl=300, show_spinner=False)
def cargar_modelo(nombre_hoja: str) -> list[dict]:
    """Carga todas las categorias de un modelo de hoja y las cruza con BD Total."""
    df_modelo = _leer_hoja_excel(nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[df_modelo["Cantidad"] > 0]
    df_bd = _leer_bd_total()
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    carrito = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        carrito.append({
            "Categoria": row["Categorias"],
            "Item": row["Item"],
            "Cantidad": row["Cantidad"],
            "Precio Unitario": row["P. Unitario real"],
            "Subtotal": subtotal,
        })
    return carrito


def cargar_categoria_desde_modelo(nombre_hoja: str, categoria_objetivo: str) -> list[dict]:
    """Carga solo los items de una categoria especifica desde un modelo."""
    df_modelo = _leer_hoja_excel(nombre_hoja)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[
        (df_modelo["Cantidad"] > 0) &
        (df_modelo["Categorias"] == categoria_objetivo)
    ]
    df_bd = _leer_bd_total()
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    items = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        items.append({
            "Categoria": row["Categorias"],
            "Item": row["Item"],
            "Cantidad": row["Cantidad"],
            "Precio Unitario": row["P. Unitario real"],
            "Subtotal": subtotal,
        })
    return items
