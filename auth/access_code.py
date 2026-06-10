"""
Generación y validación del código de acceso OTP rotativo por bloque horario.
El código cambia cada 2 horas según la zona horaria de Chile.
"""
import datetime as _dth
import hashlib as _hl
from config.settings import ACCESS_CODE_SECRET


def _get_bloque_horario(dt=None) -> str:
    """Retorna el identificador del bloque horario actual en Chile."""
    # Chile: UTC-3 (CLST) Oct-Mar, UTC-4 (CLT) Abr-Sep
    _mo = _dth.datetime.utcnow().month
    _chile_offset = -3 if _mo in (10, 11, 12, 1, 2, 3) else -4
    if dt is None:
        dt = _dth.datetime.now(_dth.timezone(_dth.timedelta(hours=_chile_offset)))
    h = dt.hour
    d = dt.strftime("%Y-%m-%d")
    if 8 <= h < 18:
        bloque = "0800-1800"
    elif 18 <= h < 20:
        bloque = "1800-2000"
    elif 20 <= h < 22:
        bloque = "2000-2200"
    elif 22 <= h < 24:
        bloque = "2200-0000"
    elif 0 <= h < 2:
        bloque = "0000-0200"
    elif 2 <= h < 4:
        bloque = "0200-0400"
    elif 4 <= h < 6:
        bloque = "0400-0600"
    else:
        bloque = "0600-0800"
    return f"{d}-{bloque}"


def generar_codigo_acceso() -> str:
    """Genera el código de acceso vigente para el bloque horario actual."""
    bloque = _get_bloque_horario()
    raw = f"{bloque}-{ACCESS_CODE_SECRET}"
    h = _hl.sha256(raw.encode()).hexdigest().upper()
    # 6 caracteres alfanuméricos legibles (sin 0, O, 1, I para evitar confusiones)
    clean = "".join(c for c in h if c not in "01IO")[:6]
    return clean


def validar_codigo_acceso(codigo_ingresado: str) -> bool:
    """Valida si el código ingresado es correcto para el bloque actual."""
    return (codigo_ingresado or "").strip().upper() == generar_codigo_acceso()
