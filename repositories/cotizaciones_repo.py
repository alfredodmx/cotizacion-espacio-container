"""
Repositorio CRUD de cotizaciones.
Tabla principal: cotizaciones
"""
import json
import random
import pandas as pd
from datetime import datetime
import streamlit as st
from config.supabase import supabase_admin
from repositories.storage_repo import (
    guardar_plano_en_storage, eliminar_plano_de_storage, descargar_plano_desde_url
)
from repositories.logs_repo import registrar_log, contar_logs, diff_datos
from utils.security import analizar_inputs


# ── Cache invalidation ────────────────────────────────────────────────────────

def _invalidar_cache_cotizaciones() -> None:
    """Limpia caches de lectura despues de guardar/modificar datos."""
    for fn in [buscar_cotizaciones, cargar_cotizacion, contar_logs,
               _fetch_cotizaciones_raw]:
        try:
            fn.clear()
        except Exception:
            pass


# ── Queries base ──────────────────────────────────────────────────────────────

_CAMPOS_LISTA = (
    'numero', 'cliente_nombre', 'asesor_nombre', 'fecha_creacion',
    'total_total', 'config_margen', 'cliente_rut', 'cliente_email',
    'asesor_email', 'asesor_telefono', 'plano_url', 'contrato_generado', 'cliente_empresa',
    'fecha_autorizacion', 'autorizado_por', 'contrato_notariado_url',
    'fecha_adjudicacion', 'contrato_datos', 'motivo_rechazo', 'fecha_rechazo',
    'acta_url', 'fecha_entrega',
    'cliente_telefono', 'cliente_direccion', 'cliente_comuna', 'cliente_region',
    'proyecto_direccion', 'proyecto_comuna', 'proyecto_region', 'cliente_rut_empresa'
)


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_cotizaciones_raw(rol: str, email: str) -> list:
    """Fetch raw cotizaciones desde Supabase, cacheado 60s por rol+email."""
    try:
        query = supabase_admin.table('cotizaciones').select(*_CAMPOS_LISTA)
        if rol == 'ejecutivo' and email:
            query = query.ilike('asesor_email', email.strip())
        return query.order('fecha_creacion', desc=True).execute().data or []
    except Exception:
        return []


# ── CRUD ──────────────────────────────────────────────────────────────────────

def guardar_cotizacion(
    numero: str,
    cliente: dict,
    asesor: dict,
    proyecto: dict,
    productos: list,
    config: dict,
    totales: dict,
    plano_nombre=None,
    plano_datos=None,
    usuario_logueado=None
) -> bool:
    """Upsert completo de una cotizacion + log + subida de plano. Retorna True/False."""
    try:
        # ── Blindaje de inputs (XSS / SQLi) ANTES de tocar la base ──────────
        # Escanea los campos de texto que escribe el usuario. Si hay un patrón de
        # ataque de severidad ALTA (p.ej. <script>, UNION SELECT), se registra el
        # evento de seguridad y se ABORTA el guardado (el caller muestra el error).
        _scan = {
            'cliente_nombre': cliente.get('Nombre', ''), 'cliente_rut': cliente.get('RUT', ''),
            'cliente_email': cliente.get('Correo', ''),
            'cliente_telefono': cliente.get('Teléfono', cliente.get('Telefono', '')),
            'cliente_direccion': cliente.get('Dirección', cliente.get('Direccion', '')),
            'cliente_empresa': cliente.get('EmpresaCliente', ''),
            'cliente_rut_empresa': cliente.get('RutEmpresa', ''),
            'proyecto_direccion': cliente.get('DireccionProyecto', ''),
            'observaciones': proyecto.get('observaciones', ''),
            'asesor_nombre': asesor.get('Nombre Ejecutivo', ''),
        }
        _bloquear, _amenazas = analizar_inputs(
            _scan, email=str(usuario_logueado or st.session_state.get('auth_email', '')),
            contexto=f'guardar_cotizacion:{numero}')
        if _bloquear:
            st.error("🚫 Se detectó contenido no permitido en los datos (posible inyección). "
                     "Corrige los campos marcados; el intento quedó registrado en Seguridad.")
            return False

        fecha_actual = datetime.now().isoformat()
        productos_json = json.dumps(productos, ensure_ascii=False)
        tiene_margen = float(config.get('margen', 0) or 0) > 0
        tiene_plano = plano_datos is not None
        datos_completos = all([
            str(cliente.get('Nombre', '')).strip(),
            str(cliente.get('Correo', '')).strip()
        ])
        asesor_completo = any([
            str(asesor.get('Nombre Ejecutivo', '')).strip(),
            str(asesor.get('Correo Ejecutivo', '')).strip(),
            str(asesor.get('Telefono Ejecutivo', '')).strip()
        ])
        if not datos_completos or not asesor_completo:
            estado = "INCOMPLETO CON PLANO" if tiene_plano else "INCOMPLETO"
        elif tiene_margen:
            estado = "AUTORIZADO CON PLANO" if tiene_plano else "AUTORIZADO"
        else:
            estado = "BORRADOR CON PLANO" if tiene_plano else "BORRADOR"

        response = supabase_admin.table('cotizaciones').select('*').eq('numero', numero).execute()
        existe = len(response.data) > 0

        plano_url = None
        if plano_datos:
            if existe and response.data[0].get('plano_url'):
                eliminar_plano_de_storage(response.data[0]['plano_url'])
            plano_url, error = guardar_plano_en_storage(plano_datos, numero, plano_nombre)
            if error:
                st.error(f"Error al subir plano: {error}")

        data = {
            'numero': numero,
            'fecha_modificacion': fecha_actual,
            'estado': estado,
            'cliente_nombre': str(cliente.get('Nombre', '') or ''),
            'cliente_rut': str(cliente.get('RUT', '') or ''),
            'cliente_email': str(cliente.get('Correo', '') or ''),
            'cliente_telefono': str(cliente.get('Teléfono', cliente.get('Telefono', '')) or '').strip(),
            'cliente_direccion': str(cliente.get('Dirección', cliente.get('Direccion', '')) or ''),
            'cliente_comuna': str(cliente.get('ComunaCliente', '') or ''),
            'cliente_region': str(cliente.get('RegionCliente', '') or ''),
            'proyecto_direccion': str(cliente.get('DireccionProyecto', '') or ''),
            'proyecto_comuna': str(cliente.get('ComunaProyecto', '') or ''),
            'proyecto_region': str(cliente.get('RegionProyecto', '') or ''),
            'cliente_tipo': str(cliente.get('TipoCliente', 'natural') or 'natural'),
            'cliente_empresa': str(cliente.get('EmpresaCliente', '') or ''),
            'cliente_rut_empresa': str(cliente.get('RutEmpresa', '') or ''),
            'asesor_nombre': str(asesor.get('Nombre Ejecutivo', '') or ''),
            'asesor_email': str(asesor.get('Correo Ejecutivo', '') or st.session_state.get('auth_email', '') or ''),
            'asesor_telefono': str(asesor.get('Telefono Ejecutivo', '') or ''),
            'proyecto_fecha_inicio': str(proyecto.get('fecha_inicio', '') or ''),
            'proyecto_fecha_termino': str(proyecto.get('fecha_termino', '') or ''),
            'proyecto_dias_validez': int(proyecto.get('dias_validez', 0) or 0),
            'proyecto_observaciones': str(proyecto.get('observaciones', '') or ''),
            'productos': productos_json,
            'config_margen': float(config.get('margen', 0) or 0),
            'config_modo_admin': 1 if config.get('modo_admin', False) else 0,
            'total_subtotal_sin_margen': float(totales.get('subtotal_sin_margen', 0) or 0),
            'total_subtotal_con_margen': float(totales.get('subtotal_con_margen', 0) or 0),
            'total_iva': float(totales.get('iva', 0) or 0),
            'total_total': float(totales.get('total', 0) or 0),
            'total_margen_valor': float(totales.get('margen_valor', 0) or 0),
            'total_comision_vendedor': float(totales.get('comision_vendedor', 0) or 0),
            'total_comision_supervisor': float(totales.get('comision_supervisor', 0) or 0),
            'total_utilidad_real': float(totales.get('utilidad_real', 0) or 0),
            'plano_nombre': plano_nombre if plano_datos else (response.data[0].get('plano_nombre') if existe else None),
            'plano_url': plano_url if plano_datos else (response.data[0].get('plano_url') if existe else None),
            'user_id': st.session_state.get('auth_user') or None,
            'modelo_predefinido': st.session_state.get('modelo_base') or None,
        }

        # Fecha de autorizacion: guardar solo cuando pasa a AUTORIZADO sin fecha previa
        _es_autorizado_nuevo = 'AUTORIZADO' in estado
        if _es_autorizado_nuevo:
            _fecha_auth_anterior = response.data[0].get('fecha_autorizacion') if existe else None
            data['fecha_autorizacion'] = _fecha_auth_anterior or fecha_actual
            if float(config.get('margen', 0) or 0) > 0:
                _auth_por = st.session_state.get('auth_nombre', '') or st.session_state.get('auth_email', '')
                if _auth_por:
                    data['autorizado_por'] = _auth_por
        else:
            data['fecha_autorizacion'] = None
            data['autorizado_por'] = None

        if existe:
            _anterior = response.data[0]
            supabase_admin.table('cotizaciones').update(data).eq('numero', numero).execute()
            _cambios = diff_datos(_anterior, data)
            if _cambios:
                _actor = usuario_logueado or str(asesor.get('Nombre Ejecutivo', '') or 'Sistema')
                registrar_log(numero, _actor, 'modificacion', _cambios)
        else:
            data['fecha_creacion'] = fecha_actual
            supabase_admin.table('cotizaciones').insert(data).execute()
            _actor = usuario_logueado or str(asesor.get('Nombre Ejecutivo', '') or 'Sistema')
            registrar_log(numero, _actor, 'creacion', {'mensaje': f'Cotizacion {numero} creada'})

        _invalidar_cache_cotizaciones()
        return True
    except Exception as e:
        st.error(f"Error al guardar cotizacion: {e}")
        return False


def buscar_cotizaciones(termino=None, tipo_busqueda='numero') -> list:
    """Busca cotizaciones con filtros de termino y tipo. Aplica filtro por rol automaticamente.

    Usa _fetch_cotizaciones_raw (cacheado 60s por rol+email) y filtra el termino
    en memoria: la primera carga es cacheada y cada busqueda es instantanea (sin
    round-trip a la DB por cada una). El cache se invalida en cada escritura via
    _invalidar_cache_cotizaciones().
    """
    try:
        _rol_q = st.session_state.get('rol_usuario', 'ejecutivo')
        # Para admin/root el email se ignora en el fetch → usamos '' como key
        # para compartir una sola entrada de cache entre sesiones admin/root.
        _email_key = st.session_state.get('auth_email', '') if _rol_q == 'ejecutivo' else ''
        rows = _fetch_cotizaciones_raw(_rol_q, _email_key)

        if termino and termino.strip():
            campo_map = {'numero': 'numero', 'cliente': 'cliente_nombre', 'asesor': 'asesor_nombre'}
            campo = campo_map.get(tipo_busqueda, 'numero')
            _t = termino.strip().lower()
            rows = [r for r in rows if _t in (r.get(campo, '') or '').lower()]

        resultados = []
        for row in rows:
            resultados.append((
                row.get('numero', ''),
                row.get('cliente_nombre', '') or '',
                row.get('asesor_nombre', '') or '',
                row.get('fecha_creacion', '') or '',
                row.get('total_total', 0) or 0,
                row.get('config_margen', 0) or 0,
                row.get('cliente_rut', '') or '',
                row.get('cliente_email', '') or '',
                row.get('asesor_email', '') or '',
                row.get('asesor_telefono', '') or '',
                1 if row.get('plano_url') else 0,
                1 if row.get('contrato_generado') else 0,
                row.get('cliente_empresa', '') or '',
                row.get('fecha_autorizacion', '') or '',
                row.get('autorizado_por', '') or '',
                1 if row.get('contrato_notariado_url') else 0,
                row.get('fecha_adjudicacion', '') or '',
                row.get('contrato_datos', '') or '',
                row.get('contrato_notariado_url', '') or '',
                row.get('motivo_rechazo', '') or '',
                row.get('fecha_rechazo', '') or '',
                row.get('acta_url', '') or '',
                row.get('fecha_entrega', '') or '',
                row.get('cliente_telefono', '') or '',
                row.get('cliente_direccion', '') or '',
                row.get('cliente_comuna', '') or '',
                row.get('cliente_region', '') or '',
                row.get('proyecto_direccion', '') or '',
                row.get('proyecto_comuna', '') or '',
                row.get('proyecto_region', '') or '',
                row.get('cliente_rut_empresa', '') or '',
            ))
        numeros_ep = [r[0] for r in resultados]
        _log_counts = contar_logs(tuple(numeros_ep))
        resultados = [r + (_log_counts.get(r[0], 0),) for r in resultados]
        return resultados
    except Exception as e:
        st.error(f"Error en busqueda: {e}")
        return []


@st.cache_data(ttl=30, show_spinner=False)
def cargar_cotizacion(numero: str) -> dict | None:
    """Carga una cotizacion completa desde Supabase. Retorna dict o None."""
    try:
        if not numero:
            return None
        response = supabase_admin.table('cotizaciones').select('*').eq('numero', numero).execute()
        if response.data:
            cotizacion = response.data[0]
            productos = cotizacion['productos']
            if isinstance(productos, str):
                cotizacion['productos'] = json.loads(productos)
            elif isinstance(productos, list):
                cotizacion['productos'] = productos
            else:
                cotizacion['productos'] = []
            if cotizacion.get('plano_url'):
                cotizacion['plano_datos'] = None
            return cotizacion
        return None
    except Exception as e:
        st.error(f"Error al cargar cotizacion: {e}")
        return None


def eliminar_cotizacion(numero: str) -> bool:
    """Elimina una cotizacion y su plano adjunto. Retorna True/False."""
    try:
        response = supabase_admin.table('cotizaciones').select('plano_url').eq('numero', numero).execute()
        if response.data and response.data[0].get('plano_url'):
            eliminar_plano_de_storage(response.data[0]['plano_url'])
        supabase_admin.table('cotizaciones').delete().eq('numero', numero).execute()
        _invalidar_cache_cotizaciones()
        return True
    except Exception as e:
        st.error(f"Error al eliminar: {e}")
        return False


def actualizar_estado_cotizacion(numero: str, estado: str) -> bool:
    """Actualiza solo el estado de una cotizacion. Retorna True/False."""
    try:
        supabase_admin.table('cotizaciones').update({
            'estado': estado,
            'fecha_modificacion': datetime.now().isoformat()
        }).eq('numero', numero).execute()
        _invalidar_cache_cotizaciones()
        return True
    except Exception as e:
        st.error(f"Error al actualizar estado: {e}")
        return False


def registrar_entrega_proyecto(cotizacion_numero: str, acta_url: str, acta_nombre: str) -> tuple[bool, str | None]:
    """Actualiza cotizacion con acta de entrega y cambia estado a PROYECTO TERMINADO."""
    try:
        from datetime import timezone, timedelta
        _tz = timezone(timedelta(hours=-3))
        _ahora = datetime.now(_tz).isoformat()
        supabase_admin.table("cotizaciones").update({
            "acta_url": acta_url,
            "acta_nombre": acta_nombre,
            "fecha_entrega": _ahora,
            "estado": "PROYECTO TERMINADO"
        }).eq("numero", cotizacion_numero).execute()
        _invalidar_cache_cotizaciones()
        return True, None
    except Exception as e:
        return False, str(e)


def clonar_cotizacion(source_ep: str, asesor_nombre: str, asesor_email: str,
                      asesor_telefono: str = "", actor: str = "") -> tuple[str | None, str | None]:
    """Clona un presupuesto y lo asigna a un ejecutivo.

    - Copia los productos (ítems, precios, cantidades) y el modelo predefinido.
    - COPIA EL PLANO como archivo INDEPENDIENTE (no comparte el mismo objeto de
      storage), para que reemplazar/borrar el plano de un clon no afecte al
      origen ni a otros clones.
    - Deja VACÍOS todos los datos del cliente y del proyecto (los llena el
      ejecutivo asignado).
    - Resetea margen/config y los totales (sin margen); limpia todo el ciclo de
      vida (autorización, rechazo, adjudicación, contrato, acta).
    - Estado: 'INCOMPLETO CON PLANO' (o 'INCOMPLETO' si no hay plano).

    Retorna (nuevo_numero, None) o (None, error).
    """
    try:
        src = supabase_admin.table('cotizaciones').select('*').eq('numero', source_ep).execute()
        if not src.data:
            return None, "No se encontró el presupuesto de origen."
        s = src.data[0]
        nuevo = generar_numero_unico()
        fecha = datetime.now().isoformat()

        # Productos (mismos ítems / precios / cantidades)
        _prods = s.get('productos')
        if isinstance(_prods, list):
            _prods_json = json.dumps(_prods, ensure_ascii=False)
        elif isinstance(_prods, str):
            _prods_json = _prods
        else:
            _prods_json = '[]'

        # Plano: copia INDEPENDIENTE (descarga el del origen y sube uno nuevo).
        _plano_url = None
        _plano_nombre = s.get('plano_nombre')
        if s.get('plano_url'):
            _bytes, _errd = descargar_plano_desde_url(s['plano_url'])
            if _bytes:
                _url_new, _erru = guardar_plano_en_storage(_bytes, nuevo, _plano_nombre or 'plano.pdf')
                if _url_new:
                    _plano_url = _url_new
        _tiene_plano = bool(_plano_url)
        estado = "INCOMPLETO CON PLANO" if _tiene_plano else "INCOMPLETO"

        _sm = float(s.get('total_subtotal_sin_margen', 0) or 0)
        data = {
            'numero': nuevo,
            'fecha_creacion': fecha, 'fecha_modificacion': fecha,
            'estado': estado,
            # Cliente / proyecto: VACÍOS (los completa el ejecutivo asignado)
            'cliente_nombre': '', 'cliente_rut': '', 'cliente_email': '', 'cliente_telefono': '',
            'cliente_direccion': '', 'cliente_comuna': '', 'cliente_region': '',
            'cliente_tipo': 'natural', 'cliente_empresa': '', 'cliente_rut_empresa': '',
            'proyecto_direccion': '', 'proyecto_comuna': '', 'proyecto_region': '',
            # Columnas DATE: NULL (no '' → Postgres error 22007 "invalid input syntax for type date")
            'proyecto_fecha_inicio': None, 'proyecto_fecha_termino': None,
            'proyecto_dias_validez': 0, 'proyecto_observaciones': '',
            # Asesor: el ejecutivo asignado (lo hace visible en su cuenta por asesor_email)
            'asesor_nombre': asesor_nombre or '',
            'asesor_email': (asesor_email or '').strip(),
            'asesor_telefono': asesor_telefono or '',
            # Se clonan
            'productos': _prods_json,
            'plano_nombre': _plano_nombre if _tiene_plano else None,
            'plano_url': _plano_url,
            'modelo_predefinido': s.get('modelo_predefinido'),
            # Margen / config: reset
            'config_margen': 0.0, 'config_modo_admin': 0,
            'total_subtotal_sin_margen': _sm,
            'total_subtotal_con_margen': _sm,
            'total_iva': round(_sm * 0.19, 2),
            'total_total': round(_sm * 1.19, 2),
            'total_margen_valor': 0.0, 'total_comision_vendedor': 0.0,
            'total_comision_supervisor': 0.0, 'total_utilidad_real': 0.0,
            # Ciclo de vida: limpio
            'fecha_autorizacion': None, 'autorizado_por': None,
            'motivo_rechazo': None, 'fecha_rechazo': None,
            'fecha_adjudicacion': None,
            'user_id': None,
        }
        supabase_admin.table('cotizaciones').insert(data).execute()
        try:
            registrar_log(nuevo, actor or 'Sistema', 'creacion',
                          {'mensaje': f'Clon de {source_ep} asignado a {asesor_nombre or asesor_email}'})
        except Exception:
            pass
        _invalidar_cache_cotizaciones()
        return nuevo, None
    except Exception as e:
        return None, str(e)


def generar_numero_unico() -> str:
    """Genera un numero EP unico no existente en la BD."""
    intentos = 0
    while intentos < 20:
        numero = f"EP-{random.randint(10000, 99999)}"
        try:
            response = supabase_admin.table('cotizaciones').select('numero').eq('numero', numero).execute()
            if not response.data:
                return numero
        except Exception:
            pass
        intentos += 1
    return f"EP-{int(datetime.now().timestamp())}"


def exportar_csv_completo() -> bytes | None:
    """Exporta todas las cotizaciones a CSV. Retorna bytes UTF-8 o None."""
    try:
        response = supabase_admin.table('cotizaciones').select(
            'numero', 'fecha_creacion', 'fecha_modificacion',
            'cliente_nombre', 'cliente_rut', 'cliente_email', 'cliente_telefono',
            'cliente_direccion', 'cliente_comuna', 'cliente_region',
            'cliente_tipo', 'cliente_empresa', 'cliente_rut_empresa',
            'proyecto_direccion', 'proyecto_comuna', 'proyecto_region',
            'asesor_nombre', 'asesor_email', 'asesor_telefono',
            'config_margen',
            'total_subtotal_sin_margen', 'total_subtotal_con_margen',
            'total_iva', 'total_total', 'total_margen_valor',
            'total_comision_vendedor', 'total_comision_supervisor', 'total_utilidad_real',
            'estado', 'plano_nombre', 'plano_url',
            'contrato_generado', 'contrato_fecha'
        ).order('fecha_creacion', desc=True).execute()
        if not response.data:
            return None
        df = pd.DataFrame(response.data)
        df.columns = [
            'N Presupuesto', 'Fecha Creacion', 'Fecha Modificacion',
            'Cliente', 'RUT', 'Email Cliente', 'Telefono Cliente',
            'Direccion Cliente', 'Comuna Cliente', 'Region Cliente',
            'Tipo Cliente', 'Empresa', 'RUT Empresa',
            'Direccion Proyecto', 'Comuna Proyecto', 'Region Proyecto',
            'Asesor', 'Email Asesor', 'Telefono Asesor',
            'Margen %',
            'Subtotal sin Margen', 'Subtotal con Margen',
            'IVA', 'Total con IVA', 'Valor Margen',
            'Comision Vendedor', 'Comision Supervisor', 'Utilidad Real',
            'Estado', 'Nombre Plano', 'URL Plano',
            'Contrato Generado', 'Fecha Contrato'
        ]
        return df.to_csv(index=False).encode('utf-8-sig')
    except Exception as e:
        st.error(f"Error al exportar: {e}")
        return None
