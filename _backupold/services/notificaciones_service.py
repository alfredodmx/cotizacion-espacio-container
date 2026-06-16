"""
Servicio de notificaciones Telegram para eventos de cotizaciones.
"""
import requests
from repositories.notif_repo import get_notif_config, get_contactos_notif, get_observadores_notif


def _enviar_telegram(bot_token: str, chat_id: str, mensaje: str) -> bool:
    """Envia un mensaje via Telegram Bot API. Retorna True si fue exitoso."""
    if not bot_token or not chat_id:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML"
        }
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception:
        return False


def _get_contactos() -> list[dict]:
    return get_contactos_notif()


def _get_observadores() -> list[dict]:
    return get_observadores_notif()


def notificar_nueva_cotizacion(
    ep: str,
    cliente_nombre: str,
    cliente_email: str,
    ejecutivo_nombre: str,
    total: float,
    bot_token_override: str | None = None
) -> bool:
    """Envia notificacion de nueva cotizacion a todos los contactos configurados."""
    bot_token = bot_token_override or get_notif_config('bot_token_default', '')
    if not bot_token:
        return False

    mensaje = (
        f"<b>Nueva cotizacion generada</b>\n\n"
        f"<b>EP:</b> {ep}\n"
        f"<b>Cliente:</b> {cliente_nombre}\n"
        f"<b>Email:</b> {cliente_email}\n"
        f"<b>Ejecutivo:</b> {ejecutivo_nombre}\n"
        f"<b>Total:</b> ${total:,.0f}"
    )

    ok = False
    for contacto in _get_contactos():
        chat_id = contacto.get('valor', '')
        if chat_id:
            result = _enviar_telegram(bot_token, chat_id, mensaje)
            ok = ok or result

    for observador in _get_observadores():
        chat_id = observador.get('valor', '')
        if chat_id:
            _enviar_telegram(bot_token, chat_id, mensaje)

    return ok


def notificar_cotizacion_autorizada(
    ep: str,
    cliente_nombre: str,
    ejecutivo_nombre: str,
    margen: float,
    total_con_margen: float,
    bot_token_override: str | None = None
) -> bool:
    """Envia notificacion cuando una cotizacion es autorizada (margen asignado)."""
    bot_token = bot_token_override or get_notif_config('bot_token_default', '')
    if not bot_token:
        return False

    mensaje = (
        f"<b>Cotizacion autorizada</b>\n\n"
        f"<b>EP:</b> {ep}\n"
        f"<b>Cliente:</b> {cliente_nombre}\n"
        f"<b>Ejecutivo:</b> {ejecutivo_nombre}\n"
        f"<b>Margen:</b> {margen}%\n"
        f"<b>Total con margen:</b> ${total_con_margen:,.0f}"
    )

    ok = False
    for contacto in _get_contactos():
        chat_id = contacto.get('valor', '')
        if chat_id:
            result = _enviar_telegram(bot_token, chat_id, mensaje)
            ok = ok or result

    return ok


def notificar_margen_removido(
    ep: str,
    cliente_nombre: str,
    removido_por: str,
    bot_token_override: str | None = None
) -> bool:
    """Envia notificacion cuando el margen de una cotizacion es removido."""
    bot_token = bot_token_override or get_notif_config('bot_token_default', '')
    if not bot_token:
        return False

    mensaje = (
        f"<b>Margen removido</b>\n\n"
        f"<b>EP:</b> {ep}\n"
        f"<b>Cliente:</b> {cliente_nombre}\n"
        f"<b>Removido por:</b> {removido_por}"
    )

    ok = False
    for contacto in _get_contactos():
        chat_id = contacto.get('valor', '')
        if chat_id:
            result = _enviar_telegram(bot_token, chat_id, mensaje)
            ok = ok or result

    return ok
