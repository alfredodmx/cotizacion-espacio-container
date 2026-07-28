"""
Envío de correos vía Resend (API HTTP). Fase 5 del CRM.

- La API key vive en los *secrets* de Streamlit (`RESEND_API_KEY`), nunca en el
  código, igual que el token de Telegram.
- El dominio verificado en Resend es el SUBDOMINIO `mail.espaciocontainerhouse.cl`,
  así que el remitente DEBE ser `@mail.espaciocontainerhouse.cl`. Las respuestas se
  redirigen (reply-to) al buzón real de Zoho `@espaciocontainerhouse.cl`.
- Remitente y reply-to son configurables por secrets (RESEND_FROM / RESEND_REPLY_TO)
  con valores por defecto sensatos.

Todo DEFENSIVO: si falta la key o falla la red, devuelve (False, mensaje) y nunca
lanza — el CRM sigue funcionando.
"""
import html as _html
import streamlit as st

_API_URL = "https://api.resend.com/emails"
_BATCH_URL = "https://api.resend.com/emails/batch"

FROM_DEFAULT = "Espacio Container House <ventas@mail.espaciocontainerhouse.cl>"
REPLY_TO_DEFAULT = "ventas@espaciocontainerhouse.cl"


def _sec(clave, default=""):
    try:
        return st.secrets.get(clave, default)
    except Exception:
        return default


def _api_key() -> str:
    return str(_sec("RESEND_API_KEY", "") or "").strip()


def remitente() -> str:
    return str(_sec("RESEND_FROM", FROM_DEFAULT) or FROM_DEFAULT).strip()


def reply_to_default() -> str:
    return str(_sec("RESEND_REPLY_TO", REPLY_TO_DEFAULT) or "").strip()


def configurado() -> bool:
    """True si hay API key cargada (para habilitar/inhabilitar la UI)."""
    return bool(_api_key())


def render_variables(texto: str, cliente: dict) -> str:
    """Reemplaza {{nombre}}, {{comuna}}, {{correo}}, {{telefono}} por los datos del
    cliente. Devuelve el texto plano ya personalizado (sin escapar)."""
    t = str(texto or "")
    _map = {
        "{{nombre}}": cliente.get("nombre", "") or "",
        "{{comuna}}": cliente.get("comuna", "") or "",
        "{{correo}}": cliente.get("email", "") or "",
        "{{telefono}}": cliente.get("telefono", "") or "",
        "{{direccion}}": cliente.get("direccion", "") or "",
    }
    for k, v in _map.items():
        t = t.replace(k, v)
    return t


def texto_a_html(texto: str) -> str:
    """Envuelve texto plano (ya personalizado) en un HTML simple y prolijo. Escapa
    el contenido y respeta los saltos de línea."""
    cuerpo = _html.escape(str(texto or "")).replace("\n", "<br>")
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#1f2937;'
        'line-height:1.6;max-width:560px;">'
        f'{cuerpo}'
        '</div>')


def enviar_correo(to, subject, html, reply_to=None, from_addr=None,
                  text=None, tags=None) -> tuple:
    """Envía UN correo. `to` puede ser str o lista. Devuelve (ok, id | error).
    DEFENSIVO: nunca lanza."""
    key = _api_key()
    if not key:
        return False, "Falta RESEND_API_KEY en los secrets de Streamlit."
    if isinstance(to, str):
        to = [to]
    to = [t for t in (to or []) if str(t or "").strip()]
    if not to:
        return False, "Sin destinatario."
    payload = {
        "from": from_addr or remitente(),
        "to": to,
        "subject": str(subject or "").strip() or "(sin asunto)",
        "html": html or "",
    }
    if text:
        payload["text"] = text
    _rt = reply_to if reply_to is not None else reply_to_default()
    if _rt:
        payload["reply_to"] = _rt
    if tags:
        payload["tags"] = tags
    try:
        import requests
        r = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=20)
        if r.status_code in (200, 201):
            try:
                return True, (r.json() or {}).get("id", "")
            except Exception:
                return True, ""
        return False, f"Resend {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)


def enviar_lote(mensajes: list) -> tuple:
    """Envía hasta 100 correos en UNA llamada (endpoint batch). `mensajes` = lista de
    dicts {from,to,subject,html,reply_to,...}. Devuelve (ok, data | error). Para
    segmentos grandes, el llamador trocea en grupos de 100. DEFENSIVO."""
    key = _api_key()
    if not key:
        return False, "Falta RESEND_API_KEY en los secrets de Streamlit."
    if not mensajes:
        return False, "Sin mensajes."
    try:
        import requests
        r = requests.post(
            _BATCH_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=mensajes[:100], timeout=30)
        if r.status_code in (200, 201):
            try:
                return True, r.json()
            except Exception:
                return True, {}
        return False, f"Resend {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return False, str(e)
