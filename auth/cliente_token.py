"""
Token de sesión del cliente (magic link firmado) para el portal ?cliente=1.

Objetivo: que la sesión del cliente sobreviva a una recarga de página sin volver
a pedir RUT+código, para poder mover el guardado del formulario al servidor
(server-side) sin desloguearlo. El token va en la URL (`?cliente=1&ct=<token>`).

Seguridad:
  - Firmado con HMAC-SHA256. La clave se deriva de ACCESS_CODE_SECRET + la SERVICE
    KEY (secreta y siempre presente) → el token es INFALSIFICABLE aunque
    ACCESS_CODE_SECRET quedara en su valor por defecto.
  - Lleva expiración embebida y firmada (no se puede extender sin re-firmar).
  - Verificación en tiempo constante (hmac.compare_digest) → sin fuga por timing.
  - El token SOLO se crea DESPUÉS de un login válido con RUT+código; es la
    persistencia de la propia sesión del cliente, no un acceso nuevo.

Es un "bearer token": quien tenga la URL entra a ESE formulario hasta que expire.
Por eso la expiración es acotada. Ante cualquier duda de validez → None (y el
caller cae al login normal).
"""
import hmac
import hashlib
import base64
import time

from config.settings import ACCESS_CODE_SECRET, SUPABASE_SERVICE_KEY

# Clave HMAC de 32 bytes derivada de dos secretos (uno de ellos, la service key,
# es fuerte y siempre está configurado en el server).
_KEY = hashlib.sha256(
    (str(ACCESS_CODE_SECRET or "") + "::ec-cliente::" + str(SUPABASE_SERVICE_KEY or "")).encode()
).digest()

# Vigencia por defecto del enlace (el cliente puede tardar días en completar).
_DIAS_VALIDEZ = 21


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s.encode())


def crear_token_cliente(ep: str, dias: int = _DIAS_VALIDEZ) -> str:
    """Devuelve un token firmado `<payload>.<firma>` que autoriza el acceso al
    formulario del presupuesto `ep` hasta que expire."""
    exp = int(time.time()) + int(dias) * 86400
    payload = _b64e(f"{ep}|{exp}".encode())
    sig = hmac.new(_KEY, payload.encode(), hashlib.sha256).digest()
    return f"{payload}.{_b64e(sig)}"


def validar_token_cliente(token: str):
    """Devuelve el `ep` si el token es válido y no expiró; si no, None.
    Nunca lanza."""
    try:
        if not token or "." not in token:
            return None
        payload, firma = token.split(".", 1)
        esperado = hmac.new(_KEY, payload.encode(), hashlib.sha256).digest()
        # Comparación en tiempo constante (anti timing-attack).
        if not hmac.compare_digest(_b64d(firma), esperado):
            return None
        ep, exp = _b64d(payload).decode().split("|", 1)
        if int(exp) < int(time.time()):
            return None
        return ep.strip()
    except Exception:
        return None
