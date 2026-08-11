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
import re as _re
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


def plan_nombre() -> str:
    """Nombre del plan de Resend (para mostrarlo). Configurable por secret RESEND_PLAN."""
    return str(_sec("RESEND_PLAN", "Free") or "Free").strip()


def limite_diario() -> int:
    """Correos permitidos por DÍA según el plan (Resend Free = 100). Configurable por
    secret RESEND_DAILY_LIMIT para cuando se suba de plan."""
    try:
        return max(0, int(_sec("RESEND_DAILY_LIMIT", 100) or 100))
    except Exception:
        return 100


def limite_mensual() -> int:
    """Correos permitidos por MES según el plan (Resend Free = 3000). Configurable por
    secret RESEND_MONTHLY_LIMIT."""
    try:
        return max(0, int(_sec("RESEND_MONTHLY_LIMIT", 3000) or 3000))
    except Exception:
        return 3000


def app_url() -> str:
    """URL base de la app (para el link de baja). Configurable por secret APP_URL."""
    return str(_sec("APP_URL", "https://cotizador.espaciocontainerhouse.cl") or "").rstrip("/")


def unsubscribe_url(cliente_id) -> str:
    """Link de desuscripción → página de baja de la app (?baja=<cliente_id>)."""
    return f"{app_url()}/?baja={cliente_id}"


def pie_baja_html(cliente_id) -> str:
    """Pie con el link de baja, obligatorio en envíos masivos."""
    _u = unsubscribe_url(cliente_id)
    return (
        '<div style="margin-top:24px;padding-top:12px;border-top:1px solid #e5e7eb;'
        'font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#9ca3af;line-height:1.5;">'
        'Recibes este correo porque dejaste tus datos en Espacio Container House.<br>'
        f'Si no quieres recibir más correos, <a href="{_u}" style="color:#6b7280;">'
        'haz click aquí para darte de baja</a>.</div>')


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


# URLs http(s) en texto plano. Se cortan en espacios y en caracteres que nunca
# forman parte de una URL escrita a mano (`<>"'`), y luego se recorta la puntuación
# final típica (punto, coma, paréntesis de cierre, etc.).
_URL_RE = _re.compile(r'https?://[^\s<>"\']+')


def _linkificar(texto: str) -> str:
    """Convierte las URLs http(s) de un texto plano en enlaces `<a href>` reales,
    escapando TODO (XSS-safe). Necesario para que (a) el enlace sea clickeable en
    cualquier cliente de correo y (b) Resend pueda reescribirlo por `track.mail` y
    así rastrear el clic (una URL de texto plano no tiene href que reescribir). El
    texto sin URLs queda escapado igual que antes."""
    partes, fin = [], 0
    for m in _URL_RE.finditer(texto):
        url, cola = m.group(0), ""
        while url and url[-1] in ".,;:!?)]}":   # puntuación final que no es del link
            cola, url = url[-1] + cola, url[:-1]
        partes.append(_html.escape(texto[fin:m.start()]))
        _href = _html.escape(url, quote=True)
        partes.append(f'<a href="{_href}" style="color:#2563eb;text-decoration:underline;">'
                      f'{_html.escape(url)}</a>')
        partes.append(_html.escape(cola))
        fin = m.end()
    partes.append(_html.escape(texto[fin:]))
    return "".join(partes)


def texto_a_html(texto: str) -> str:
    """Envuelve texto plano (ya personalizado) en un HTML simple y prolijo. Escapa
    el contenido (XSS-safe), respeta los saltos de línea y convierte las URLs en
    enlaces `<a href>` reales (clickeables + rastreables por Resend)."""
    cuerpo = _linkificar(str(texto or "")).replace("\n", "<br>")
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;color:#1f2937;'
        'line-height:1.6;max-width:560px;">'
        f'{cuerpo}'
        '</div>')


def enviar_correo(to, subject, html, reply_to=None, from_addr=None,
                  text=None, tags=None, attachments=None, headers=None) -> tuple:
    """Envía UN correo. `to` puede ser str o lista. `attachments` = lista de
    {filename, content(base64)}. `headers` = dict (p.ej. List-Unsubscribe). Devuelve
    (ok, id | error). DEFENSIVO: nunca lanza."""
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
    if attachments:
        payload["attachments"] = attachments
    if headers:
        payload["headers"] = headers
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


# Se apaga si la API key es "solo-envío" (401): así NO seguimos consultando el
# estado en cada render (evita llenar los Logs de Resend con 401). Se reinicia al
# redeploy (p.ej. tras poner una key con acceso de lectura).
_STATUS_DISABLED = False


def estado_lectura_disponible() -> bool:
    """False si ya detectamos que la API key no puede leer estados (solo-envío)."""
    return not _STATUS_DISABLED


def estado_correo(email_id: str) -> dict:
    """Consulta el estado de un correo enviado (GET /emails/{id}). Devuelve
    {ok, last_event, data} o {ok:False, error}. `last_event` ∈ sent/delivered/
    delivery_delayed/opened/clicked/bounced/complained. DEFENSIVO: nunca lanza.
    Si la key es solo-envío (401), se apaga para no reintentar."""
    global _STATUS_DISABLED
    key = _api_key()
    if not key or not email_id or _STATUS_DISABLED:
        return {"ok": False, "error": "no disponible"}
    try:
        import requests
        r = requests.get(f"{_API_URL}/{email_id}",
                         headers={"Authorization": f"Bearer {key}"}, timeout=15)
        if r.status_code == 200:
            d = r.json() or {}
            return {"ok": True, "last_event": d.get("last_event", "sent"), "data": d}
        if r.status_code in (401, 403):
            _STATUS_DISABLED = True   # key sin permiso de lectura → no reintentar
            return {"ok": False, "error": "restricted"}
        return {"ok": False, "error": f"{r.status_code}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


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
