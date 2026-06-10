"""
Validación y formateo de RUT chileno.
"""
import re
import streamlit as st


def validar_rut(rut_completo: str) -> tuple[bool, str]:
    rut_limpio = re.sub(r'[^0-9kK]', '', rut_completo)
    if len(rut_limpio) < 2:
        return False, "RUT incompleto"
    cuerpo = rut_limpio[:-1]
    dv_ingresado = rut_limpio[-1].upper()
    if not cuerpo.isdigit():
        return False, "RUT inválido"
    _es_extranjero = len(cuerpo) >= 9 or int(cuerpo) >= 100000000
    suma = 0
    multiplo = 2
    for i in range(len(cuerpo) - 1, -1, -1):
        suma += multiplo * int(cuerpo[i])
        multiplo = multiplo + 1 if multiplo < 7 else 2
    dv_esperado = 11 - (suma % 11)
    if dv_esperado == 10:
        dv_esperado = 'K'
    elif dv_esperado == 11:
        dv_esperado = '0'
    else:
        dv_esperado = str(dv_esperado)
    if dv_ingresado == dv_esperado:
        if _es_extranjero:
            return True, "RUT extranjero válido"
        return True, "RUT válido"
    else:
        if _es_extranjero:
            return True, "RUT inválido o RUT extranjero"
        return False, "RUT inválido"


def formatear_rut(rut_raw: str) -> str:
    if not rut_raw:
        return ""
    if len(rut_raw) > 10:
        rut_raw = rut_raw[:10]
    if len(rut_raw) >= 2:
        cuerpo = rut_raw[:-1]
        dv = rut_raw[-1].upper()
        if cuerpo:
            cuerpo_formateado = ""
            for i, digito in enumerate(reversed(cuerpo)):
                if i > 0 and i % 3 == 0:
                    cuerpo_formateado = "." + cuerpo_formateado
                cuerpo_formateado = digito + cuerpo_formateado
        else:
            cuerpo_formateado = ""
        return f"{cuerpo_formateado}-{dv}"
    else:
        return rut_raw


def procesar_cambio_rut() -> None:
    """Callback onChange para el input de RUT del cliente."""
    rut_key = f"rut_input_{st.session_state.get('counter', 0)}"
    if rut_key in st.session_state:
        valor_actual = st.session_state[rut_key]
        raw = re.sub(r'[^0-9kK]', '', valor_actual)
        if len(raw) > 10:
            raw = raw[:10]
        st.session_state.rut_raw = raw
        st.session_state.rut_display = formatear_rut(raw) if raw else ""
        if len(raw) >= 2:
            valido, mensaje = validar_rut(raw)
            st.session_state.rut_valido = valido
            st.session_state.rut_mensaje = mensaje
        else:
            st.session_state.rut_valido = False
            st.session_state.rut_mensaje = "RUT incompleto"


def procesar_cambio_rut_empresa() -> None:
    """Callback onChange para el input de RUT de empresa."""
    rut_emp_key = f"rut_empresa_input_{st.session_state.get('counter', 0)}"
    if rut_emp_key in st.session_state:
        valor_actual = st.session_state[rut_emp_key]
        raw = re.sub(r'[^0-9kK]', '', valor_actual)
        if len(raw) > 10:
            raw = raw[:10]
        st.session_state.rut_empresa_raw = raw
        if raw:
            st.session_state.rut_empresa_display = formatear_rut(raw)
            st.session_state.cliente_rut_empresa  = formatear_rut(raw)
        else:
            st.session_state.rut_empresa_display = ""
            st.session_state.cliente_rut_empresa  = ""
        if len(raw) >= 2:
            valido, mensaje = validar_rut(raw)
            st.session_state.rut_empresa_valido  = valido
            st.session_state.rut_empresa_mensaje = mensaje
        else:
            st.session_state.rut_empresa_valido  = False
            st.session_state.rut_empresa_mensaje = "RUT incompleto"
