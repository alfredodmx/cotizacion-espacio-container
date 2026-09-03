"""
Repositorio de CORREOS enviados (CRM Fase 5 — seguimiento).

Guarda cada correo enviado con Resend (su `resend_id`) para poder mostrar el
estado (entregado / abierto / click / rebotado) y contar cuántos se enviaron.
Tabla NUEVA `crm_correos` (el usuario corre el CREATE TABLE). LECTURAS/ESCRITURAS
DEFENSIVAS: si la tabla no existe aún, devuelven []/0/(None,err) y el envío de
correo sigue funcionando igual (el seguimiento simplemente no se registra).
"""
import uuid
from datetime import datetime, timezone, timedelta

from config.supabase import supabase_admin as _supa

_TZ_CL = timezone(timedelta(hours=-3))


def _ahora() -> str:
    return datetime.now(_TZ_CL).isoformat()


def registrar_correo(cliente_id, resend_id, para, asunto,
                     enviado_por="", adjuntos=0, campana_id=None,
                     cuerpo="", adjuntos_nombres=None) -> tuple:
    """Guarda un correo enviado (para el seguimiento). `campana_id` agrupa los correos
    de un mismo envío masivo (para el reporte por campaña). `cuerpo` (HTML/texto enviado)
    y `adjuntos_nombres` (lista de nombres de archivo) permiten «Ver correo» en la ficha.
    Devuelve (id, err). DEFENSIVO: si faltan las columnas nuevas (ALTER no corrido),
    reintenta sin ellas para no perder el seguimiento."""
    cid = str(uuid.uuid4())
    _base = {
        "id": cid,
        "cliente_id": str(cliente_id) if cliente_id else None,
        "resend_id": str(resend_id or ""),
        "para": str(para or ""),
        "asunto": str(asunto or ""),
        "enviado_por": str(enviado_por or ""),
        "adjuntos": int(adjuntos or 0),
        "fecha": _ahora(),
    }
    if campana_id:
        _base["campana_id"] = str(campana_id)
    _full = dict(_base)
    if cuerpo:
        _full["cuerpo"] = str(cuerpo)
    if adjuntos_nombres:
        _full["adjuntos_nombres"] = ", ".join(str(n) for n in adjuntos_nombres if str(n or "").strip())
    try:
        _supa.table("crm_correos").insert(_full).execute()
        return cid, None
    except Exception:
        try:                                   # reintento sin las columnas nuevas
            _supa.table("crm_correos").insert(_base).execute()
            return cid, None
        except Exception as e:
            return None, str(e)


def listar_correos_cliente(cliente_id) -> list:
    """Correos enviados a un cliente, más reciente primero. [] si no existe la tabla."""
    try:
        return (_supa.table("crm_correos").select("*").eq("cliente_id", cliente_id)
                .order("fecha", desc=True).execute().data or [])
    except Exception:
        return []


def contar_correos(cliente_id=None) -> int:
    """Total de correos enviados (a un cliente, o global). 0 si no existe la tabla."""
    try:
        q = _supa.table("crm_correos").select("id", count="exact").limit(1)
        if cliente_id:
            q = q.eq("cliente_id", cliente_id)
        return q.execute().count or 0
    except Exception:
        return 0


def campanas_por_cliente() -> dict:
    """{cliente_id -> [ {nombre, fecha, last_event, opened, clicked, bounced, complained}, … ]
    asc por fecha} para pintar en las cards del CRM el historial de CAMPAÑAS MASIVAS
    recibidas por cada lead (con su estado de correo). Solo correos con campana_id (los
    individuales no cuentan). DEFENSIVO → {} si algo falla."""
    out = {}
    try:
        _camps = _supa.table("crm_campanas").select("*").execute().data or []
        _cn = {str(c.get("id")): (c.get("nombre") or c.get("asunto") or "Campaña") for c in _camps}
        _cors = (_supa.table("crm_correos").select("*")
                 .not_.is_("campana_id", "null").execute().data or [])
        for co in _cors:
            _cid = co.get("cliente_id")
            if not _cid:
                continue
            out.setdefault(str(_cid), []).append({
                "nombre": _cn.get(str(co.get("campana_id"))) or co.get("asunto") or "Campaña",
                "fecha": co.get("fecha"),
                "last_event": co.get("last_event"),
                "opened": co.get("opened"), "clicked": co.get("clicked"),
                "bounced": co.get("bounced"), "complained": co.get("complained"),
            })
        for _cid in out:
            out[_cid].sort(key=lambda x: str(x.get("fecha") or ""))
    except Exception:
        pass
    return out


def contar_correos_hoy() -> int:
    """Correos registrados HOY (hora Chile) — para la cuota diaria de Resend. Cada fila
    de crm_correos es un envío (individual/campaña/prueba), así que cuenta 1:1 el uso
    del día. 0 si no existe la tabla."""
    try:
        ini = datetime.now(_TZ_CL).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        return (_supa.table("crm_correos").select("id", count="exact")
                .gte("fecha", ini).limit(1).execute().count or 0)
    except Exception:
        return 0


def contar_correos_mes() -> int:
    """Correos registrados este MES (hora Chile) — para la cuota mensual de Resend.
    0 si no existe la tabla."""
    try:
        ini = datetime.now(_TZ_CL).replace(day=1, hour=0, minute=0, second=0,
                                           microsecond=0).isoformat()
        return (_supa.table("crm_correos").select("id", count="exact")
                .gte("fecha", ini).limit(1).execute().count or 0)
    except Exception:
        return 0
