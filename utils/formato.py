"""
Funciones de formato de texto y números.
"""
import unicodedata
import json
import hashlib
import streamlit as st


def formato_clp(valor: float) -> str:
    """Formatea un número como pesos chilenos: $1.234.567"""
    return f"${valor:,.0f}".replace(",", ".")


def _normalizar_nombre(texto: str, catalogo: list[str]) -> str:
    """Busca el nombre oficial ignorando tildes, mayúsculas y 'Región de/del'."""
    def _strip(s):
        s = s.lower().strip()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        for prefix in ('region de los ', 'region de la ', 'region del ', 'region de ', 'region '):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s

    txt_norm = _strip(texto)
    for nombre in catalogo:
        if _strip(nombre) == txt_norm:
            return nombre
    for nombre in catalogo:
        if txt_norm in _strip(nombre) or _strip(nombre) in txt_norm:
            return nombre
    return texto


def calcular_hash_estado() -> str:
    """Calcula un hash MD5 del estado actual del formulario para detectar cambios no guardados."""
    estado = {
        "nombre":            st.session_state.get('nombre_input', ''),
        "rut":               st.session_state.get('rut_display', ''),
        "correo":            st.session_state.get('correo_input', ''),
        "telefono":          st.session_state.get('telefono_raw', ''),
        "direccion":         st.session_state.get('direccion_input', ''),
        "cliente_comuna":    st.session_state.get('cliente_comuna', ''),
        "cliente_region":    st.session_state.get('cliente_region', ''),
        "proyecto_direccion":st.session_state.get('proyecto_direccion', ''),
        "proyecto_comuna":   st.session_state.get('proyecto_comuna', ''),
        "proyecto_region":   st.session_state.get('proyecto_region', ''),
        "cliente_tipo":      st.session_state.get('cliente_tipo', 'natural'),
        "cliente_empresa":   st.session_state.get('cliente_empresa', ''),
        "cliente_rut_empresa":st.session_state.get('cliente_rut_empresa', ''),
        "observaciones":     st.session_state.get('observaciones_input', ''),
        "asesor":            st.session_state.get('asesor_seleccionado', ''),
        "correo_asesor":     st.session_state.get('correo_asesor', ''),
        "telefono_asesor":   st.session_state.get('telefono_asesor', ''),
        "fecha_inicio":      str(st.session_state.get('fecha_inicio', '')),
        "fecha_termino":     str(st.session_state.get('fecha_termino', '')),
        "carrito":           json.dumps(st.session_state.get('carrito', []), sort_keys=True),
        "margen":            st.session_state.get('margen', 0),
        "plano_nombre":      st.session_state.get('plano_nombre', ''),
    }
    estado_str = json.dumps(estado, sort_keys=True)
    return hashlib.md5(estado_str.encode()).hexdigest()
