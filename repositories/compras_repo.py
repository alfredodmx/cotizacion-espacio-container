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
