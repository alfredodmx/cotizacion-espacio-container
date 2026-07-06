"""
Repositorio de registros de compras (Rendicion de Cuentas).
Tablas: registro_compras
Buckets: facturas (facturas y actas)
"""
import json
import streamlit as st
from config.supabase import supabase_admin


@st.cache_data(ttl=30, show_spinner=False)
def obtener_registros_compra(cotizacion_numero: str) -> list:
    """Obtiene todos los registros de compra de una cotizacion, ordenados por fecha."""
    try:
        resp = supabase_admin.table("registro_compras") \
            .select("*") \
            .eq("cotizacion_numero", cotizacion_numero) \
            .order("fecha_registro", desc=False) \
            .execute()
        return resp.data or []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def obtener_items_comprados(cotizacion_numero: str) -> dict:
    """
    Consolida todos los registros y retorna dict {item_name: {real, adicional, diferencia, fecha}}
    de los items ya comprados.
    """
    try:
        registros = obtener_registros_compra(cotizacion_numero)
        comprados: dict = {}
        for reg in registros:
            items = reg.get('items') or []
            if isinstance(items, str):
                try:
                    items = json.loads(items)
                except Exception:
                    items = []
            fecha = reg.get('fecha_registro', '')
            for it in items:
                nombre = str(it.get('item', ''))
                real = float(it.get('precio_real', 0) or 0)
                adic = int(it.get('adicional', 0) or 0)
                # "En stock": producto que ya se tiene (precio real $0). Cuenta como
                # comprado (llega al 100%) y es ahorro puro. Se marca con stock=True.
                es_stock = bool(it.get('stock', False))
                if (real > 0 or es_stock) and nombre:
                    comprados[nombre] = {
                        'real': real,
                        'adicional': adic,
                        'diferencia': it.get('diferencia', 0),
                        'fecha': fecha,
                        'stock': es_stock,
                    }
        return comprados
    except Exception:
        return {}


def guardar_registro_compra(
    cotizacion_numero: str,
    usuario: str,
    factura_url: str,
    factura_nombre: str,
    items: list,
    total_presupuestado: float,
    total_real: float
) -> tuple[bool, str | None]:
    """Guarda un registro de compra en la tabla registro_compras. Retorna (ok, error)."""
    try:
        balance = total_presupuestado - total_real
        data = {
            "cotizacion_numero": cotizacion_numero,
            "usuario_registro": usuario,
            "factura_url": factura_url or "",
            "factura_nombre": factura_nombre or "",
            "items": items,
            "total_presupuestado": total_presupuestado,
            "total_real": total_real,
            "balance": balance,
        }
        supabase_admin.table("registro_compras").insert(data).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def guardar_registro_compra_full(payload: dict) -> tuple[bool, str | None]:
    """Guarda un registro de compra COMPLETO (todos los campos del formulario de
    operaciones) con la service key. Usada por el guardado SERVER-SIDE: el
    navegador ya no hace POST a registro_compras (clave anon), sino que manda el
    payload a Python y este inserta con la service key (que ignora RLS).

    Escanea los campos de texto libres (defensa XSS/SQLi) y valida antes de
    insertar. El balance se recalcula en el servidor (no se confía en el cliente).
    Devuelve (ok, error)."""
    try:
        from utils.security import analizar_inputs
        p = payload or {}
        ep = str(p.get('cotizacion_numero', '') or '').strip()
        items = p.get('items') or []
        if not ep or not isinstance(items, list) or not items:
            return False, "Registro inválido (sin EP o sin ítems)."

        _bloquear, _ = analizar_inputs({
            'lugar_compra':   p.get('lugar_compra', ''),
            'observaciones':  p.get('observaciones', ''),
            'falto_retirar':  p.get('falto_retirar', ''),
            'usuario':        p.get('usuario_registro', ''),
        }, email=str(p.get('usuario_registro', '')), contexto=f'registro_compras:{ep}')
        if _bloquear:
            return False, "Contenido no permitido en el registro (posible inyección)."

        _tp = float(p.get('total_presupuestado', 0) or 0)
        _tr = float(p.get('total_real', 0) or 0)
        data = {
            'cotizacion_numero':    ep,
            'usuario_registro':     str(p.get('usuario_registro', '') or ''),
            'lugar_compra':         str(p.get('lugar_compra', '') or ''),
            'tipo_compra':          str(p.get('tipo_compra', '') or ''),
            'subtipo_compra':       str(p.get('subtipo_compra', '') or ''),
            'fecha_entrega_compra': str(p.get('fecha_entrega_compra', '') or ''),
            'falto_retirar':        str(p.get('falto_retirar', '') or ''),
            'observaciones':        str(p.get('observaciones', '') or ''),
            'factura_url':          str(p.get('factura_url', '') or ''),
            'factura_nombre':       str(p.get('factura_nombre', '') or ''),
            'items':                items,
            'total_presupuestado':  _tp,
            'total_real':           _tr,
            'balance':              _tp - _tr,
        }
        supabase_admin.table('registro_compras').insert(data).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def eliminar_registro_compra_full(reg_id) -> tuple[bool, str | None]:
    """Elimina POR COMPLETO un registro de compra (la 'factura'/compra) con la
    service key (RLS-safe). Los ítems de ese registro dejan de contar como
    comprados → vuelven a quedar pendientes. Devuelve (ok, error)."""
    try:
        if not reg_id:
            return False, "ID de registro inválido."
        supabase_admin.table('registro_compras').delete().eq('id', reg_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def actualizar_registro_compra_full(reg_id, payload: dict) -> tuple[bool, str | None]:
    """Actualiza un registro existente (corrección de errores de digitación:
    cantidad/precio_real, o quitar ítems; y lugar/observaciones/fecha). Recalcula
    los totales EN EL SERVIDOR (no se confía en el cliente) y escanea el texto
    libre (XSS/SQLi). Service key (RLS-safe). Devuelve (ok, error)."""
    try:
        from utils.security import analizar_inputs
        if not reg_id:
            return False, "ID de registro inválido."
        p = payload or {}
        items = p.get('items') or []
        if not isinstance(items, list):
            return False, "Ítems inválidos."

        _bloquear, _ = analizar_inputs({
            'lugar_compra':  p.get('lugar_compra', ''),
            'observaciones': p.get('observaciones', ''),
        }, email=str(p.get('usuario_registro', '')), contexto=f'editar_registro:{reg_id}')
        if _bloquear:
            return False, "Contenido no permitido en el registro (posible inyección)."

        # Recalcular totales en el servidor (mismo criterio que el formulario:
        # presupuestado = solo ítems normales; real = todos, incluidos adicionales).
        _tp = 0.0
        _tr = 0.0
        for _it in items:
            _c  = float(_it.get('cantidad', 1) or 1)
            _pr = float(_it.get('precio_real', 0) or 0)
            _pp = float(_it.get('precio_presupuestado', 0) or 0)
            _ad = float(_it.get('adicional', 0) or 0)
            _sin = bool(_it.get('sin_registro', False))
            _es_adic = bool(_it.get('es_adicional', False)) or _sin
            _tr += _c * _pr + _ad * _pr
            if not _es_adic:
                _tp += _c * _pp

        data = {
            'items':               items,
            'total_real':          _tr,
            'total_presupuestado': _tp,
            'balance':             _tp - _tr,
        }
        for _k in ('lugar_compra', 'observaciones', 'fecha_entrega_compra'):
            if _k in p:
                data[_k] = str(p.get(_k, '') or '')
        # Reemplazo de factura (solo si vino una URL nueva; la validación de que
        # pertenece al bucket se hace en el handler antes de llamar aquí).
        if p.get('factura_url'):
            data['factura_url'] = str(p.get('factura_url') or '')
            data['factura_nombre'] = str(p.get('factura_nombre') or '')

        supabase_admin.table('registro_compras').update(data).eq('id', reg_id).execute()
        return True, None
    except Exception as e:
        return False, str(e)


def calcular_estado_compras(cotizacion_numero: str, productos_presupuesto: list) -> dict:
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
