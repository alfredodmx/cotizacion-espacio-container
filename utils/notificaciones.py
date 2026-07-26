"""
Envío de notificaciones Telegram — funciones de disparo.
Se importan desde tab_cotizacion.py al guardar presupuesto.
"""
import traceback as _tb
import streamlit as st
from config.supabase import supabase_admin as _supa


def _get_cfg(clave, default=""):
    try:
        r = _supa.table('notificaciones_config').select('valor').eq('clave', clave).execute()
        if r.data:
            return r.data[0]['valor'] or default
    except Exception:
        pass
    return default


def _enviar_telegram(chat_id, mensaje, token=None):
    if not chat_id:
        return False
    import requests
    _token = token or _get_cfg('bot_token', st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
    if not _token:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{_token}/sendMessage",
            json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as _e:
        print(f"_enviar_telegram error: {_e}")
        return False


def _get_contactos():
    import json
    try:
        return json.loads(_get_cfg('contactos_json', '{}'))
    except Exception:
        return {}


def _get_observadores():
    import json
    try:
        return json.loads(_get_cfg('observadores_json', '[]'))
    except Exception:
        return []


def _fmt_clp(monto):
    """Formatea un número como pesos chilenos: 17183456 → '$17.183.456'."""
    try:
        m = float(monto or 0)
    except Exception:
        m = 0
    return f"${m:,.0f}".replace(",", ".") if m else "$0"


def notificar_nueva_cotizacion(ep, ejecutivo_nombre, cliente_nombre, monto, estado, ejecutivo_email):
    try:
        plantilla = _get_cfg(
            'msg_nueva_cotizacion',
            '🕐 *Nueva cotización para revisar*\n\n*{ep}* · {ejecutivo}\nCliente: {cliente} · Monto: *{monto}*\nEstado: {estado}'
        )
        msg = plantilla.format(ep=ep, ejecutivo=ejecutivo_nombre, cliente=cliente_nombre, monto=_fmt_clp(monto), estado=estado, margen='', supervisor='')
        contactos = _get_contactos()
        _roots = [r.strip().lower() for r in st.secrets.get("ROOTS", "").split(",") if r.strip()]
        _token = _get_cfg('bot_token', st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
        for _em in _roots:
            chat_id = contactos.get(_em, '')
            if chat_id:
                _enviar_telegram(chat_id, msg, _token)
        _supa_users = _supa.auth.admin.list_users()
        for u in _supa_users:
            meta = u.user_metadata or {}
            _rol = meta.get('rol', 'ejecutivo')
            _em = (u.email or '').lower()
            if _rol in ('admin',) and _em not in _roots and _em != (ejecutivo_email or '').lower():
                chat_id = contactos.get(_em, '')
                if chat_id:
                    _enviar_telegram(chat_id, msg, _token)
        for obs in _get_observadores():
            if obs.get('chat_id'):
                _enviar_telegram(obs['chat_id'], msg, _token)
        grupo_id = _get_cfg('grupo_chat_id', '')
        grupo_filtro = _get_cfg('grupo_filtro', 'todas')
        if grupo_id and grupo_filtro in ('todas', 'solo_nuevas'):
            _enviar_telegram(grupo_id, msg, _token)
    except Exception as _e:
        print(f"ERROR notificar_nueva: {_e}\n{_tb.format_exc()}")


def notificar_cotizacion_autorizada(ep, cliente_nombre, margen, ejecutivo_email, ejecutivo_nombre, supervisor_nombre='', monto=0):
    try:
        _token = _get_cfg('bot_token', st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
        _plantilla = _get_cfg(
            'msg_autorizada',
            '✅ *¡PRESUPUESTO AUTORIZADO!*\n\n📋 *{ep}* · {cliente}\n💰 Margen aplicado: *{margen}%*\n👤 Autorizado por: *{supervisor}*\n\nYa puedes presentárselo a tu cliente 🎉'
        )
        msg = _plantilla.format(ep=ep, cliente=cliente_nombre, margen=margen, ejecutivo=ejecutivo_nombre, supervisor=supervisor_nombre, monto=_fmt_clp(monto), estado='')
        contactos = _get_contactos()
        chat_id = contactos.get((ejecutivo_email or '').lower(), '')
        if chat_id:
            _enviar_telegram(chat_id, msg, _token)
        for obs in _get_observadores():
            if obs.get('chat_id'):
                _enviar_telegram(obs['chat_id'], msg, _token)
        grupo_id = _get_cfg('grupo_chat_id', '')
        grupo_filtro = _get_cfg('grupo_filtro', 'todas')
        if grupo_id and grupo_filtro in ('todas', 'solo_autorizaciones'):
            _enviar_telegram(grupo_id, msg, _token)
    except Exception as _e:
        print(f"ERROR notificar_autorizada: {_e}\n{_tb.format_exc()}")


def notificar_recordatorio(cliente_nombre, titulo, vence, asignado_email="", vencido=False):
    """Aviso Telegram de un recordatorio del CRM. Va al ejecutivo asignado (por su
    chat_id en contactos) + al grupo si está configurado. `vencido`=True cambia el
    texto a alerta de vencimiento. Nunca lanza. Devuelve cuántos envíos hizo."""
    try:
        _token = _get_cfg('bot_token', st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
        contactos = _get_contactos()
        if vencido:
            msg = (f"⏰ *Recordatorio vencido*\n\nCliente: *{cliente_nombre}*\n"
                   f"{titulo}\nVencía: {vence}")
        else:
            msg = (f"🔔 *Nuevo recordatorio*\n\nCliente: *{cliente_nombre}*\n"
                   f"{titulo}\nVence: {vence}")
        enviados = 0
        chat_id = contactos.get((asignado_email or '').lower(), '')
        if chat_id:
            if _enviar_telegram(chat_id, msg, _token):
                enviados += 1
        grupo_id = _get_cfg('grupo_chat_id', '')
        if grupo_id:
            if _enviar_telegram(grupo_id, msg, _token):
                enviados += 1
        return enviados
    except Exception as _e:
        print(f"ERROR notificar_recordatorio: {_e}\n{_tb.format_exc()}")
        return 0


def notificar_lead_asignado(cliente_nombre, ejecutivo_email, asignado_por=""):
    """Aviso Telegram al EJECUTIVO cuando se le asigna un lead/cliente en el CRM.
    Va solo al ejecutivo (por su chat_id en contactos). Nunca lanza. Devuelve
    cuántos envíos hizo."""
    try:
        _token = _get_cfg('bot_token', st.secrets.get("TELEGRAM_BOT_TOKEN", ""))
        contactos = _get_contactos()
        msg = (f"🧲 *Nuevo lead asignado*\n\nCliente: *{cliente_nombre}*"
               + (f"\nAsignado por: {asignado_por}" if asignado_por else "")
               + "\n\nRevísalo en el sistema.")
        chat_id = contactos.get((ejecutivo_email or '').lower(), '')
        if chat_id and _enviar_telegram(chat_id, msg, _token):
            return 1
        return 0
    except Exception as _e:
        print(f"ERROR notificar_lead_asignado: {_e}\n{_tb.format_exc()}")
        return 0


def notificar_margen_removido(ep, cliente_nombre, ejecutivo_email):
    try:
        plantilla = _get_cfg(
            'msg_margen_removido',
            '↩️ La cotización *{ep}* volvió a estado borrador.\nEl supervisor realizó cambios. Revisa el sistema.'
        )
        msg = plantilla.format(ep=ep, cliente=cliente_nombre, ejecutivo='', margen='', supervisor='', monto='', estado='')
        contactos = _get_contactos()
        chat_id = contactos.get((ejecutivo_email or '').lower(), '')
        if chat_id:
            _enviar_telegram(chat_id, msg)
    except Exception as _e:
        print(f"ERROR notificar_margen_removido: {_e}\n{_tb.format_exc()}")
