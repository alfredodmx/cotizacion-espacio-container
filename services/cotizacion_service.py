"""
Logica de negocio de cotizaciones: estados, margenes, comisiones, badges.
"""


# ── Estados ───────────────────────────────────────────────────────────────────

def evaluar_estado_cotizacion(cotizacion: dict) -> str:
    """Retorna el estado textual de una cotizacion con emoji."""
    if cotizacion.get('contrato_notariado_url'):
        return "ADJUDICADO"
    if cotizacion.get('motivo_rechazo') or cotizacion.get('fecha_rechazo'):
        return "RECHAZADO"
    datos_completos = all([
        cotizacion.get('cliente_nombre', ''),
        cotizacion.get('cliente_email', '')
    ])
    asesor_completo = any([
        cotizacion.get('asesor_nombre', ''),
        cotizacion.get('asesor_email', ''),
        cotizacion.get('asesor_telefono', '')
    ])
    tiene_plano = cotizacion.get('plano_nombre') not in (None, '')
    if not datos_completos or not asesor_completo:
        return "INCOMPLETO CON PLANO" if tiene_plano else "INCOMPLETO"
    tiene_margen = cotizacion.get('config_margen', 0) > 0
    if tiene_margen:
        return "AUTORIZADO CON PLANO" if tiene_plano else "AUTORIZADO"
    else:
        return "BORRADOR CON PLANO" if tiene_plano else "BORRADOR"


def calcular_estado_label(cliente_nombre, cliente_email, asesor_nombre, asesor_email,
                          asesor_telefono, config_margen, tiene_plano,
                          tiene_notariado=False, tiene_acta=False, motivo_rechazo='') -> str:
    """Fuente ÚNICA del estado de una cotización. La usan la tabla (crear_badge_estado)
    y el header (badge del presupuesto cargado), para que SIEMPRE coincidan."""
    _mr = motivo_rechazo
    _motivo = str(_mr).strip() if (_mr is not None and str(_mr).strip() not in ('', 'None', 'nan')) else ''
    if tiene_acta:
        return 'PROYECTO TERMINADO'
    if tiene_notariado:
        return 'ADJUDICADO'
    if _motivo:
        return 'RECHAZADO'
    datos_completos = all([cliente_nombre, cliente_email])
    asesor_completo = any([asesor_nombre, asesor_email, asesor_telefono])
    if config_margen and config_margen > 0:
        if datos_completos and asesor_completo:
            return 'AUTORIZADO CON PLANO' if tiene_plano else 'AUTORIZADO'
        return 'INCOMPLETO CON PLANO' if tiene_plano else 'INCOMPLETO'
    if datos_completos and asesor_completo:
        return 'BORRADOR CON PLANO' if tiene_plano else 'BORRADOR'
    return 'INCOMPLETO CON PLANO' if tiene_plano else 'INCOMPLETO'


# Colores del badge por estado (bg, fg). MISMA paleta que los badges-filtro de la
# tabla (tab_historial._BADGE_STYLE) para que el badge de la columna ESTADO y los
# badges-filtro se vean idénticos — si se cambia un color acá, cambiar también allá.
ESTADO_BADGE_COLORS = {
    'PROYECTO TERMINADO':   ('#ede9fe', '#7c3aed'),
    'ADJUDICADO':           ('#dbeafe', '#1d4ed8'),
    'AUTORIZADO CON PLANO': ('#dcfce7', '#15803d'),
    'AUTORIZADO':           ('#dcfce7', '#15803d'),
    'BORRADOR CON PLANO':   ('#ffedd5', '#c2410c'),
    'BORRADOR':             ('#fef9c3', '#854d0e'),
    'INCOMPLETO CON PLANO': ('#fee2e2', '#dc2626'),
    'INCOMPLETO':           ('#fee2e2', '#dc2626'),
    'RECHAZADO':            ('#fee2e2', '#b91c1c'),
}

# Icono SVG por estado. Mismos paths que tab_historial._BADGE_SVG (sin 'TODOS').
ESTADO_BADGE_ICONS = {
    'PROYECTO TERMINADO':   '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    'ADJUDICADO':           '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    'AUTORIZADO CON PLANO': '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    'AUTORIZADO':           '<path d="M20 6 9 17l-5-5"/>',
    'BORRADOR CON PLANO':   '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><polyline points="14 2 14 8 20 8"/><path d="M10.4 12.6a2 2 0 1 1 3 3L8 21l-4 1 1-4z"/>',
    'BORRADOR':             '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    'INCOMPLETO CON PLANO': '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
    'INCOMPLETO':           '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    'RECHAZADO':            '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
}


def crear_badge_estado(row) -> str:
    """Retorna HTML del badge de estado para una fila de cotizacion (tuple o Series).
    Mismo diseño (pill + icono) que los badges-filtro de la tabla de COTIZACIONES."""
    if hasattr(row, 'index') and 'Margen' in row.index:
        config_margen   = row['Margen']
        tiene_plano     = row['Tiene_Plano']
        cliente_nombre  = row['Cliente']
        cliente_email   = row['Email']
        asesor_nombre   = row['Asesor']
        asesor_email    = row['Asesor_Email']
        asesor_telefono = row['Asesor_Tel']
        tiene_notariado = bool(row.get('Tiene_Notariado', 0))
        tiene_acta      = bool(row.get('Acta_URL', ''))
        _raw_mr         = row.get('Motivo_Rechazo', '')
    else:
        config_margen   = row[5]
        tiene_plano     = row[10] if len(row) > 10 else False
        cliente_nombre  = row[1]
        cliente_email   = row[7]
        asesor_nombre   = row[2]
        asesor_email    = row[8]
        asesor_telefono = row[9]
        tiene_notariado = bool(row[15]) if len(row) > 15 else False
        tiene_acta      = bool(row[21]) if len(row) > 21 else False
        _raw_mr         = row[19] if len(row) > 19 else ''

    label = calcular_estado_label(cliente_nombre, cliente_email, asesor_nombre, asesor_email,
                                  asesor_telefono, config_margen, tiene_plano,
                                  tiene_notariado=tiene_notariado, tiene_acta=tiene_acta,
                                  motivo_rechazo=_raw_mr)
    bg, fg = ESTADO_BADGE_COLORS.get(label, ('#e2e8f0', '#334155'))
    icon_path = ESTADO_BADGE_ICONS.get(label, '')
    _cls = ' class="badge-rechazado"' if label == 'RECHAZADO' else ''
    _svg = (f'<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
            f'{icon_path}</svg>')
    return (f'<span{_cls} style="display:inline-flex;align-items:center;gap:5px;'
            f'font-family:Montserrat,sans-serif;font-weight:800;font-size:10.5px;'
            f'letter-spacing:0.03em;text-transform:uppercase;border-radius:99px;'
            f'padding:5px 11px;white-space:nowrap;line-height:1;'
            f'background:{bg};color:{fg};">{_svg}<span>{label}</span></span>')


# ── Margen y comisiones ───────────────────────────────────────────────────────

def aplicar_margen(precio_original: float, margen: float) -> float:
    """Aplica porcentaje de margen a un precio. Ej: 100 * 1.15 = 115."""
    return precio_original * (1 + margen / 100)


def calcular_totales_con_margen(carrito: list, margen: float) -> tuple[float, float, float]:
    """Retorna (subtotal_con_margen, iva, total)."""
    subtotal = sum(
        item["Cantidad"] * aplicar_margen(item["Precio Unitario"], margen)
        for item in carrito
    )
    iva = subtotal * 0.19
    return subtotal, iva, subtotal + iva


def calcular_comision_vendedor(subtotal_con_margen: float) -> float:
    return subtotal_con_margen * 0.025


def calcular_comision_supervisor(subtotal_con_margen: float) -> float:
    return subtotal_con_margen * 0.008


def calcular_utilidad_real(margen_valor: float, comision_vendedor: float, comision_supervisor: float) -> float:
    return margen_valor - comision_vendedor - comision_supervisor


# ── Totales RC ────────────────────────────────────────────────────────────────

def calcular_totales_rc(productos_presupuesto: list, registros: list, incluir_varios: bool = False) -> dict:
    """
    Calcula totales del modulo Rendicion de Cuentas.
    Retorna: {'tP': presupuestado, 'tR': real, 'tA': adicionales con registro, 'tS': sin registro}
    Logica identica a la funcion JS calc() de la tabla RC.
    """
    import json as _j

    todos = list(productos_presupuesto or [])
    pn = {str(p.get('Item', '')) for p in todos}
    pu_map = {str(p.get('Item', '')): round(float(p.get('Precio Unitario', 0) or 0))
              for p in todos}

    prods = todos if incluir_varios else [
        p for p in todos
        if str(p.get('Categoria', '')).strip().lower() != 'varios'
    ]

    comprados: dict = {}
    for reg in (registros or []):
        items = reg.get('items') or []
        if isinstance(items, str):
            try:
                items = _j.loads(items)
            except Exception:
                items = []
        for it in items:
            nombre = str(it.get('item', ''))
            pr = float(it.get('precio_real', 0) or 0)
            if pr > 0 and nombre:
                comprados[nombre] = {
                    'real': pr,
                    'cant': float(it.get('cantidad', 1) or 1),
                    'adic': int(it.get('adicional', 0) or 0),
                    'es_adicional': it.get('es_adicional', False),
                    'sin_registro': it.get('sin_registro', False),
                }

    tP = tR = tA = tS = 0.0

    for nombre, data in comprados.items():
        re = data['real']
        c = data['cant']
        ad = data['adic']
        is_sin = data['sin_registro']
        is_adic = (nombre not in pn) and not is_sin

        if is_sin:
            tS += re * c
            tR += re * c + ad * re
        elif is_adic:
            tA += re * c
            tR += re * c + ad * re
        else:
            pu = pu_map.get(nombre, 0)
            tR += re * c + ad * re
            if nombre in pn:
                tP += pu * c

    for p in prods:
        nombre = str(p.get('Item', ''))
        if nombre not in comprados:
            pu = round(float(p.get('Precio Unitario', 0) or 0))
            c = round(float(p.get('Cantidad', 1) or 1))
            tP += pu * c

    return {'tP': tP, 'tR': tR, 'tA': tA, 'tS': tS}
