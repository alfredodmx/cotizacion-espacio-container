"""
Catálogo de países y funciones de formateo/validación de teléfonos internacionales.
"""
import re
import streamlit as st

# ── Catálogo de países ───────────────────────────────────────────────────────
# código_prefijo: (nombre, bandera, dígitos_locales_esperados, fn_formato)
_PAISES_TEL: dict = {
    '1':   ('EE.UU. / Canadá', '🇺🇸',  10, lambda d: f"+1 {d[:3]} {d[3:6]} {d[6:]}"),
    '34':  ('España',          '🇪🇸',   9, lambda d: f"+34 {d[:3]} {d[3:6]} {d[6:]}"),
    '51':  ('Perú',            '🇵🇪',   9, lambda d: f"+51 {d[:3]} {d[3:6]} {d[6:]}"),
    '52':  ('México',          '🇲🇽',  10, lambda d: f"+52 {d[:2]} {d[2:6]} {d[6:]}"),
    '53':  ('Cuba',            '🇨🇺',   8, lambda d: f"+53 {d[:4]} {d[4:]}"),
    '54':  ('Argentina',       '🇦🇷',  10, lambda d: f"+54 {d[:2]} {d[2:6]} {d[6:]}"),
    '55':  ('Brasil',          '🇧🇷',  11, lambda d: f"+55 {d[:2]} {d[2:7]} {d[7:]}"),
    '56':  ('Chile',           '🇨🇱',   9, lambda d: f"+56 {d[:1]} {d[1:5]} {d[5:]}"),
    '57':  ('Colombia',        '🇨🇴',  10, lambda d: f"+57 {d[:3]} {d[3:6]} {d[6:]}"),
    '58':  ('Venezuela',       '🇻🇪',  10, lambda d: f"+58 {d[:3]} {d[3:6]} {d[6:]}"),
    '591': ('Bolivia',         '🇧🇴',   8, lambda d: f"+591 {d[:4]} {d[4:]}"),
    '593': ('Ecuador',         '🇪🇨',   9, lambda d: f"+593 {d[:2]} {d[2:6]} {d[6:]}"),
    '595': ('Paraguay',        '🇵🇾',   9, lambda d: f"+595 {d[:3]} {d[3:6]} {d[6:]}"),
    '598': ('Uruguay',         '🇺🇾',   8, lambda d: f"+598 {d[:4]} {d[4:]}"),
}


def _detectar_pais(digitos_raw: str):
    """
    Dado un string de dígitos (con o sin código de país al inicio),
    retorna (codigo_pais, digitos_locales, info_pais) o None si no detecta prefijo.
    Prueba de mayor a menor longitud de prefijo para evitar ambigüedades.
    """
    for largo in (3, 2, 1):
        prefijo = digitos_raw[:largo]
        if prefijo in _PAISES_TEL:
            resto = digitos_raw[largo:]
            return prefijo, resto, _PAISES_TEL[prefijo]
    return None


def formatear_telefono(telefono_raw: str) -> str:
    """
    Formatea un número de teléfono según su código de país.
    - Si tiene código de país reconocido → aplica formato del país
    - Sin código → asume Chile
    """
    if not telefono_raw:
        return ""
    val = str(telefono_raw).strip()
    digitos = re.sub(r'[^0-9]', '', val)
    if not digitos:
        return ""

    tiene_prefijo = (
        val.startswith('+') or
        (len(digitos) >= 10 and digitos[:2] in ('56','52','54','55','57','58','34')) or
        digitos[:1] == '1'
    )

    if tiene_prefijo:
        det = _detectar_pais(digitos)
        if det:
            codigo, locales, (nombre, bandera, n_esperados, fn) = det
            if len(locales) >= n_esperados:
                locales = locales[:n_esperados]
                return fn(locales)
            elif len(locales) > 0:
                return fn(locales.ljust(n_esperados, '_')).replace('_', '')

    # Sin prefijo → asumir Chile
    if digitos.startswith('56') and len(digitos) >= 11:
        digitos = digitos[2:]
    digitos = digitos[-9:] if len(digitos) > 9 else digitos
    if not digitos:
        return ""
    if len(digitos) == 1:
        return f"+56 {digitos}"
    elif len(digitos) <= 5:
        return f"+56 {digitos[:1]} {digitos[1:]}"
    else:
        return f"+56 {digitos[:1]} {digitos[1:5]} {digitos[5:]}"


def _validar_telefono_cliente(valor_ingresado: str) -> tuple[str, bool, str]:
    """
    Normaliza y valida el teléfono del cliente.
    Retorna (valor_normalizado, valido, mensaje).
    - Chile: valor_normalizado = 9 dígitos sin prefijo (ej: '961528744')
    - Extranjero: valor_normalizado = dígitos con prefijo (ej: '+521234567890')
    """
    if not valor_ingresado or not str(valor_ingresado).strip():
        return "", False, ""

    val = str(valor_ingresado).strip()
    digitos = re.sub(r'[^0-9]', '', val)
    if not digitos:
        return "", False, ""

    tiene_plus = val.startswith('+')
    det = _detectar_pais(digitos) if tiene_plus else None

    if tiene_plus and det:
        codigo, locales, (nombre, bandera, n_esperados, fn) = det

        if codigo == '56':
            if len(locales) == n_esperados:
                return locales, True, f"✅ {bandera} {nombre}"
            elif len(locales) == n_esperados - 1:
                return locales, False, f"❌ Falta un dígito (ingresaste +56 más {len(locales)} dígitos, el número debe tener {n_esperados})"
            elif len(locales) < n_esperados - 1:
                return locales, False, f"❌ Número incompleto ({len(locales)} dígitos después del +56, se necesitan {n_esperados})"
            else:
                return locales[:n_esperados], False, "❌ Número demasiado largo después del +56"
        else:
            valor_guardado = '+' + codigo + locales
            if len(locales) == n_esperados:
                return valor_guardado, True, f"✅ {bandera} {nombre}"
            elif len(locales) < n_esperados:
                faltan = n_esperados - len(locales)
                return valor_guardado, False, f"⚠️ {bandera} {nombre} — faltan {faltan} dígito{'s' if faltan>1 else ''}"
            else:
                return '+' + codigo + locales[:n_esperados], False, f"⚠️ {bandera} {nombre} — número demasiado largo"

    # Sin prefijo explícito → asumir Chile
    n_orig = len(digitos)
    if digitos.startswith('56') and n_orig >= 11:
        digitos = digitos[2:]
    elif digitos.startswith('56') and n_orig == 10:
        return digitos[2:], False, "❌ Falta un dígito (ingresaste +56 más 8 dígitos, el número debe tener 9)"

    n = len(digitos)
    if n == 0:
        return "", False, ""
    elif n < 8:
        return digitos, False, f"❌ Número incompleto ({n} dígitos, se necesitan 9)"
    elif n == 8:
        digitos_norm = '9' + digitos
        return digitos_norm, True, "⚠️ 🇨🇱 Chile — se asumió que comienza con 9, verifica si es correcto"
    elif n == 9:
        if not digitos.startswith('9'):
            return digitos, True, "⚠️ 🇨🇱 Chile — el número no comienza con 9, ¿es celular chileno?"
        return digitos, True, "✅ 🇨🇱 Chile"
    elif n == 10:
        return digitos, False, f"❌ Falta un dígito (se ingresaron {n}, se necesitan 9 para Chile)"
    else:
        return digitos[:9], False, f"❌ Número demasiado largo ({n} dígitos)"


def procesar_cambio_telefono() -> None:
    """Callback onChange para el input de teléfono del cliente."""
    telefono_key = f"telefono_input_{st.session_state.get('counter', 0)}"
    if telefono_key in st.session_state:
        valor_actual = st.session_state[telefono_key]
        digitos_norm, valido, mensaje = _validar_telefono_cliente(valor_actual)
        st.session_state.telefono_raw     = digitos_norm
        st.session_state.telefono_valido  = valido
        st.session_state.telefono_mensaje = mensaje
