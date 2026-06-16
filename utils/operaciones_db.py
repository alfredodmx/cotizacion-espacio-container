"""
Funciones de base de datos y cálculo de días para operaciones de proyecto.
Extraídas de app.py para la arquitectura modular.
"""
import uuid
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from config.settings import ROOTS


# ── USUARIOS ─────────────────────────────────────────────────────────────────

def listar_usuarios_ejecutivos():
    """Lista todos los usuarios excepto supervisores fijos (root)."""
    try:
        res = _supa_admin.auth.admin.list_users()
        users = []
        for u in res:
            email = u.email or ""
            if email.lower() in [s.lower() for s in ROOTS]:
                continue
            meta = u.user_metadata or {}
            nombre = meta.get("nombre", email)
            rol = meta.get("rol", "ejecutivo")
            try:
                _activo = not getattr(u, 'banned_until', None)
            except Exception:
                _activo = True
            users.append({
                "id": str(u.id),
                "email": email,
                "nombre": nombre,
                "rol": rol,
                "telefono": meta.get("telefono", "") or "",
                "created_at": str(u.created_at)[:10] if u.created_at else "",
                "activo": _activo
            })
        return users
    except Exception as e:
        st.session_state['_usuarios_list_error'] = str(e)
        return []


# ── REGISTRO DE COMPRAS ───────────────────────────────────────────────────────

def obtener_registros_compra(cotizacion_numero):
    """Obtiene todos los registros de compra de una cotización."""
    try:
        resp = _supa_admin.table("registro_compras").select("*")\
            .eq("cotizacion_numero", cotizacion_numero)\
            .order("fecha_registro", desc=False).execute()
        return resp.data or []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def obtener_items_comprados(cotizacion_numero):
    """Consolida todos los registros y retorna dict {item_name: {real, adic, fecha}}."""
    import json as _jic
    try:
        registros = obtener_registros_compra(cotizacion_numero)
        comprados = {}
        for reg in registros:
            items = reg.get('items') or []
            if isinstance(items, str):
                try:
                    items = _jic.loads(items)
                except Exception:
                    items = []
            fecha = reg.get('fecha_registro', '')
            for it in items:
                nombre = str(it.get('item', ''))
                real = float(it.get('precio_real', 0) or 0)
                adic = int(it.get('adicional', 0) or 0)
                if real > 0 and nombre:
                    comprados[nombre] = {
                        'real': real,
                        'adicional': adic,
                        'diferencia': it.get('diferencia', 0),
                        'fecha': fecha
                    }
        return comprados
    except Exception:
        return {}


def calcular_estado_compras(cotizacion_numero, productos_presupuesto):
    """Calcula el estado de compras: porcentaje, adicionales, etc."""
    try:
        prods = [p for p in (productos_presupuesto or [])
                 if str(p.get('Categoria', '')).strip().lower() != 'varios']
        total_items = len(prods)
        if total_items == 0:
            return {'pct': 0, 'estado': 'Sin productos', 'comprados': 0, 'total': 0, 'adicionales': []}

        comprados = obtener_items_comprados(cotizacion_numero)
        items_comprados = sum(1 for p in prods if str(p.get('Item', '')) in comprados)
        adicionales = [v for k, v in comprados.items()
                       if not any(str(p.get('Item', '')) == k for p in prods)]

        pct = round(items_comprados / total_items * 100)
        if items_comprados == 0:
            estado = 'Sin compras'
        elif pct >= 100:
            estado = '100% + adicionales' if adicionales else 'Compras 100%'
        else:
            estado = f'Compras al {pct}%'

        return {
            'pct': pct,
            'estado': estado,
            'comprados': items_comprados,
            'total': total_items,
            'adicionales': adicionales
        }
    except Exception:
        return {'pct': 0, 'estado': 'Error', 'comprados': 0, 'total': 0, 'adicionales': []}


# ── ACTA Y ENTREGA ────────────────────────────────────────────────────────────

def guardar_acta_en_storage(archivo_bytes, cotizacion_numero, nombre_original):
    """Sube un acta PDF al bucket 'facturas' de Supabase."""
    try:
        carpeta = cotizacion_numero.replace('/', '_').replace('\\', '_')
        file_name = f"acta-{carpeta}/{uuid.uuid4()}.pdf"
        _supa_admin.storage.from_('facturas').upload(
            path=file_name,
            file=archivo_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = _supa_admin.storage.from_('facturas').get_public_url(file_name)
        return public_url, None
    except Exception as e:
        return None, str(e)


def registrar_entrega_proyecto(cotizacion_numero, acta_url, acta_nombre):
    """Actualiza cotización con acta de entrega y cambia estado a PROYECTO TERMINADO."""
    try:
        from datetime import datetime, timezone, timedelta
        _tz = timezone(timedelta(hours=-3))
        _ahora = datetime.now(_tz).isoformat()
        _supa_admin.table("cotizaciones").update({
            "acta_url": acta_url,
            "acta_nombre": acta_nombre,
            "fecha_entrega": _ahora,
            "estado": "PROYECTO TERMINADO"
        }).eq("numero", cotizacion_numero).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ── DÍAS HÁBILES CHILE ────────────────────────────────────────────────────────

def _feriados_chile(year):
    """Retorna set de fechas feriadas en Chile para el año dado."""
    from datetime import date, timedelta
    f = set()
    fijos = [(1, 1), (5, 1), (9, 18), (9, 19), (10, 12), (11, 1), (12, 8), (12, 25)]
    for mes, dia in fijos:
        f.add(date(year, mes, dia))
    # Semana Santa — algoritmo Meeus/Jones/Butcher
    a = year % 19
    b = year // 100; c = year % 100
    d = b // 4; e = b % 4
    g = (8 * b + 13) // 25; h = (19 * a + b - d - g + 15) % 30
    i = c // 4; k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 19 * l) // 433
    n = (h + l - 7 * m + 90) // 25
    p = (h + l - 7 * m + 33 * n + 19) % 32
    pascua = date(year, n, p)
    f.add(pascua - timedelta(days=2))  # Viernes Santo
    f.add(pascua - timedelta(days=1))  # Sábado Santo
    if year >= 2021:
        f.add(date(year, 6, 20))  # Solsticio / Pueblos Originarios
    f.add(date(year, 5, 1))      # Día del Trabajo
    base_spp = date(year, 6, 29)
    if base_spp.weekday() == 1:
        f.add(base_spp - timedelta(1))
    else:
        f.add(base_spp)
    f.add(date(year, 8, 15))     # Asunción de la Virgen
    if date(year, 9, 18).weekday() == 4:
        f.add(date(year, 9, 19))
    f.add(date(year, 10, 31))    # Reforma Protestante
    return f


def sumar_dias_habiles(fecha_inicio, dias_habiles):
    """Suma N días hábiles a fecha_inicio (date), retorna date de entrega."""
    from datetime import timedelta
    years_needed = set()
    d = fecha_inicio
    years_needed.add(d.year)
    feriados = _feriados_chile(d.year) | _feriados_chile(d.year + 1)
    count = 0
    while count < dias_habiles:
        d += timedelta(days=1)
        if d.year not in years_needed:
            years_needed.add(d.year)
            feriados |= _feriados_chile(d.year)
        if d.weekday() < 5 and d not in feriados:
            count += 1
    return d


def dias_habiles_entre(fecha_inicio, fecha_fin):
    """Cuenta días hábiles entre dos fechas (date)."""
    from datetime import timedelta
    if fecha_fin <= fecha_inicio:
        return 0
    feriados = _feriados_chile(fecha_inicio.year)
    if fecha_fin.year != fecha_inicio.year:
        feriados |= _feriados_chile(fecha_fin.year)
    count = 0
    d = fecha_inicio
    while d < fecha_fin:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in feriados:
            count += 1
    return count
