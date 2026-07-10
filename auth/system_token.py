"""
Token de sesión del SISTEMA (usuarios/trabajadores) para persistir el login al
refrescar el navegador, guardado en localStorage (NO en la URL de forma
permanente; la URL solo lo transporta un instante al restaurar y se limpia).

A diferencia de `cliente_token` (que da acceso a UN formulario), este token
autoriza la sesión de una CUENTA de usuario, así que:
  - Expira rápido (1 hora por defecto) y se re-emite en cada interacción mientras
    el usuario está activo (sesión "rodante" de 1h de inactividad).
  - Solo lleva el `user_id`. Al restaurar SIEMPRE se re-consulta el usuario por la
    service key (admin) para tomar rol/metadata FRESCOS y respetar baneos: si el
    usuario fue bloqueado o eliminado, el token no restaura nada.

Seguridad:
  - Firmado con HMAC-SHA256; la clave se deriva de ACCESS_CODE_SECRET + la SERVICE
    KEY (secreta y siempre presente) → infalsificable.
  - Expiración embebida y firmada. Verificación en tiempo constante.
  - Vive en localStorage (no viaja en links ni queda en el historial de forma
    permanente). Al cerrar sesión se borra de localStorage.
"""
import hmac
import hashlib
import base64
import time

from config.settings import ACCESS_CODE_SECRET, SUPABASE_SERVICE_KEY

_KEY = hashlib.sha256(
    (str(ACCESS_CODE_SECRET or "") + "::ec-sistema::" + str(SUPABASE_SERVICE_KEY or "")).encode()
).digest()

# Vigencia por defecto: 1 hora (se re-emite en cada run mientras el usuario navega).
_HORAS = 1


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode())


def crear_token_sistema(user_id: str, horas: int = _HORAS) -> str:
    """Token firmado `<payload>.<firma>` que persiste la sesión del `user_id`."""
    exp = int(time.time()) + int(horas) * 3600
    payload = _b64e(f"{user_id}|{exp}".encode())
    sig = hmac.new(_KEY, payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{_b64e(sig)}"


def validar_token_sistema(token: str):
    """Devuelve el `user_id` si el token es válido y no expiró; si no, None. Nunca lanza."""
    try:
        if not token or "." not in token:
            return None
        payload, firma = token.split(".", 1)
        esperado = hmac.new(_KEY, payload.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64d(firma), esperado):
            return None
        uid, exp = _b64d(payload).decode().split("|", 1)
        if int(exp) < int(time.time()):
            return None
        return uid.strip()
    except Exception:
        return None
