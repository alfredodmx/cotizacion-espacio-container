"""
Repositorio de logs de auditoría de cotizaciones.
Tabla: cotizacion_logs
"""
import json
import streamlit as st
from config.supabase import supabase_admin


def registrar_log(numero: str, asesor: str, tipo_cambio: str, detalle_dict: dict) -> None:
    """Inserta un registro en cotizacion_logs. No interrumpe el flujo si falla."""
    try:
        supabase_admin.table('cotizacion_logs').insert({
            'numero': numero,
            'asesor': asesor,
            'tipo_cambio': tipo_cambio,
            'detalle': detalle_dict,
        }).execute()
    except Exception:
        pass


@st.cache_data(ttl=30, show_spinner=False)
def contar_logs(numeros: list) -> dict:
    """Devuelve dict {numero: count} para una lista de números EP."""
    if not numeros:
        return {}
    try:
        resp = supabase_admin.table('cotizacion_logs').select('numero').in_('numero', numeros).execute()
        counts: dict = {}
        for row in resp.data:
            n = row['numero']
            counts[n] = counts.get(n, 0) + 1
        return counts
    except Exception:
        return {}


def obtener_logs_ep(numero: str) -> list:
    """Devuelve lista de logs ordenados por fecha DESC para un EP."""
    try:
        resp = supabase_admin.table('cotizacion_logs') \
            .select('*').eq('numero', numero) \
            .order('fecha', desc=True).execute()
        return resp.data or []
    except Exception:
        return []


def diff_datos(anterior: dict, nuevo: dict) -> dict:
    """Compara dos dicts de cotización y devuelve solo los campos que cambiaron."""
    LABELS = {
        'cliente_nombre': 'Nombre cliente', 'cliente_rut': 'RUT cliente',
        'cliente_email': 'Correo', 'cliente_telefono': 'Telefono',
        'cliente_tipo': 'Tipo cliente', 'cliente_empresa': 'Empresa',
        'cliente_rut_empresa': 'RUT empresa', 'asesor_nombre': 'Asesor',
        'config_margen': 'Margen %', 'total_total': 'Total',
        'proyecto_observaciones': 'Descripcion del proyecto', 'estado': 'Estado',
        'productos': 'Productos/carrito',
    }

    cambios: dict = {}

    for k, label in LABELS.items():
        v_ant_raw = anterior.get(k, '') or ''
        v_new_raw = nuevo.get(k, '') or ''
        v_ant = str(v_ant_raw)
        v_new = str(v_new_raw)
        if k == 'productos':
            if v_ant != v_new:
                try:
                    _ant_list = json.loads(v_ant_raw) if v_ant_raw else []
                    _new_list = json.loads(v_new_raw) if v_new_raw else []
                    _ant_dict = {it.get('Item', '?'): it.get('Cantidad', 0) for it in _ant_list}
                    _new_dict = {it.get('Item', '?'): it.get('Cantidad', 0) for it in _new_list}
                    _detalles = []
                    for item, cant in _new_dict.items():
                        if item not in _ant_dict:
                            _detalles.append(f"+ {item} (x{cant})")
                    for item, cant in _ant_dict.items():
                        if item not in _new_dict:
                            _detalles.append(f"- {item} (x{cant})")
                    for item in _ant_dict:
                        if item in _new_dict and _ant_dict[item] != _new_dict[item]:
                            _detalles.append(f"~ {item}: {_ant_dict[item]} -> {_new_dict[item]}")
                    if _detalles:
                        cambios['Productos'] = {'antes': '-', 'despues': '\n'.join(_detalles)}
                    else:
                        cambios[label] = {'antes': '(carrito anterior)', 'despues': '(carrito actualizado)'}
                except Exception:
                    cambios[label] = {'antes': '(carrito anterior)', 'despues': '(carrito actualizado)'}
        elif v_ant != v_new:
            cambios[label] = {'antes': v_ant or '-', 'despues': v_new or '-'}

    # Direccion cliente completa
    def _dir_completa(d, prefix_dir, prefix_com, prefix_reg):
        parts = [
            str(d.get(prefix_dir, '') or '').strip(),
            str(d.get(prefix_com, '') or '').strip(),
            str(d.get(prefix_reg, '') or '').strip(),
        ]
        return ', '.join(p for p in parts if p) or ''

    dir_ant = _dir_completa(anterior, 'cliente_direccion', 'cliente_comuna', 'cliente_region')
    dir_new = _dir_completa(nuevo, 'cliente_direccion', 'cliente_comuna', 'cliente_region')
    if dir_ant != dir_new:
        cambios['Direccion cliente'] = {'antes': dir_ant or '-', 'despues': dir_new or '-'}

    proy_ant = _dir_completa(anterior, 'proyecto_direccion', 'proyecto_comuna', 'proyecto_region')
    proy_new = _dir_completa(nuevo, 'proyecto_direccion', 'proyecto_comuna', 'proyecto_region')
    if proy_ant != proy_new:
        cambios['Direccion proyecto'] = {'antes': proy_ant or '-', 'despues': proy_new or '-'}

    return cambios
