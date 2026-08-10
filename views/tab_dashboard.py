"""
Tab DASHBOARD — Resumen ejecutivo del sistema.

Rediseño 2026: KPIs + resultados de negocio (adjudicados/terminados/rechazados)
+ embudo + evolución + top categorías/ejecutivos (con avatar circular) + CRM
(leads por fuente) + perfil de clientes + top productos. Iconos SVG (sin emojis)
y tipografía de títulos unificada. Datos cacheados + defensivos.
"""
import re
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from views.layout import render_page_header
from services.cotizacion_service import (
    calcular_estado_label, ESTADO_BADGE_COLORS, ESTADO_BADGE_ICONS)

# Orden y etiquetas de los estados (mismo criterio y familia que COTIZACIONES).
_ESTADO_ORDER = [
    ('PROYECTO TERMINADO', 'Terminados'),
    ('ADJUDICADO', 'Adjudicados'),
    ('AUTORIZADO CON PLANO', 'Aut. c/plano'),
    ('AUTORIZADO', 'Autorizados'),
    ('BORRADOR CON PLANO', 'Borrador c/plano'),
    ('BORRADOR', 'Borrador'),
    ('INCOMPLETO CON PLANO', 'Incompleto c/plano'),
    ('INCOMPLETO', 'Incompletos'),
    ('RECHAZADO', 'Rechazados'),
]


# ── Iconos SVG (estilo Lucide) ───────────────────────────────────────────────
_ICON_PATHS_DASH = {
    "briefcase": '<rect width="20" height="14" x="2" y="7" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    "dollar": '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "trending": '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "mappin": '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
    "map": '<path d="M14.106 5.553a2 2 0 0 0 1.788 0l3.659-1.83A1 1 0 0 1 21 4.619v12.764a1 1 0 0 1-.553.894l-4.553 2.277a2 2 0 0 1-1.788 0l-4.212-2.106a2 2 0 0 0-1.788 0l-3.659 1.83A1 1 0 0 1 3 19.381V6.618a1 1 0 0 1 .553-.894l4.553-2.277a2 2 0 0 1 1.788 0z"/><path d="M15 5.764v15"/><path d="M9 3.236v15"/>',
    "building": '<rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M12 6h.01"/><path d="M12 10h.01"/><path d="M12 14h.01"/><path d="M16 10h.01"/><path d="M16 14h.01"/><path d="M8 10h.01"/><path d="M8 14h.01"/>',
    "zap": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "calendar": '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
    "package": '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M3.3 7 12 12l8.7-5"/><path d="M12 22V12"/>',
    "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
    "checkc": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    "xc": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    "flag": '<path d="M4 22V4a1 1 0 0 1 1-1h13.24a.5.5 0 0 1 .4.8L15 9l3.64 5.2a.5.5 0 0 1-.4.8H4"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "store": '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M12 2v5"/>',
    "download": '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
    "hand": '<path d="M18 11V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2"/><path d="M14 10V4a2 2 0 0 0-2-2a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/>',
    "arrow-up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    "arrow-down": '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
}


def _ic(name, color="#64748b", size=15, mr=7, valign=-2):
    inner = _ICON_PATHS_DASH.get(name, "")
    _mr = f"margin-right:{mr}px;" if mr else ""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:{valign}px;{_mr}flex-shrink:0;">{inner}</svg>')


def _dot(color, size=12):
    return (f'<span style="display:inline-block;width:{size}px;height:{size}px;border-radius:3px;'
            f'background:{color};margin-right:8px;vertical-align:-1px;flex-shrink:0;"></span>')


def _avatar(nombre, foto, size=34):
    """Avatar circular del ejecutivo: foto si hay, si no las iniciales."""
    _ini = ''.join(p[0] for p in (nombre or '').split()[:2]).upper() or 'EC'
    if foto:
        _inner = f'<img src="{foto}" style="width:100%;height:100%;object-fit:cover;display:block;" alt="">'
    else:
        _inner = _ini
    return (f'<div style="width:{size}px;height:{size}px;border-radius:50%;flex-shrink:0;overflow:hidden;'
            f'background:linear-gradient(135deg,#0f3460,#2563eb);color:#fff;display:flex;align-items:center;'
            f'justify-content:center;font-family:Montserrat,sans-serif;font-weight:800;font-size:{int(size*0.36)}px;'
            f'box-shadow:0 2px 6px rgba(15,23,42,.18);">{_inner}</div>')


def _rank_badge(idx):
    """Distintivo de posición (1-3 podio, resto neutro). Sin emojis."""
    _cols = {0: ("#f59e0b", "#fff"), 1: ("#94a3b8", "#fff"), 2: ("#b45309", "#fff")}
    _bg, _fg = _cols.get(idx, ("#eef2f7", "#64748b"))
    return (f'<div style="width:24px;height:24px;border-radius:50%;flex-shrink:0;background:{_bg};color:{_fg};'
            f'display:flex;align-items:center;justify-content:center;font-family:Montserrat,sans-serif;'
            f'font-weight:900;font-size:11px;">{idx+1}</div>')


# ── Datos (cacheados + defensivos) ───────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_dashboard(periodo='mes'):
    try:
        from datetime import datetime as _dt, timedelta as _td
        from collections import defaultdict as _dd

        _ahora = _dt.now()
        if periodo == 'mes':
            _inicio = _ahora.replace(day=1).strftime('%Y-%m-%d')
            _inicio_ant = (_ahora.replace(day=1) - _td(days=1)).replace(day=1).strftime('%Y-%m-%d')
            _fin_ant = (_ahora.replace(day=1) - _td(days=1)).strftime('%Y-%m-%d')
        elif periodo == '3meses':
            _inicio = (_ahora - _td(days=90)).strftime('%Y-%m-%d')
            _inicio_ant = (_ahora - _td(days=180)).strftime('%Y-%m-%d')
            _fin_ant = (_ahora - _td(days=91)).strftime('%Y-%m-%d')
        elif periodo == 'año':
            _inicio = _ahora.replace(month=1, day=1).strftime('%Y-%m-%d')
            _inicio_ant = _ahora.replace(month=1, day=1, year=_ahora.year - 1).strftime('%Y-%m-%d')
            _fin_ant = (_ahora.replace(month=1, day=1) - _td(days=1)).strftime('%Y-%m-%d')
        else:
            _inicio = '2000-01-01'
            _inicio_ant = None
            _fin_ant = None

        resp = _supa_admin.table('cotizaciones').select(
            'numero,fecha_creacion,fecha_modificacion,estado,'
            'total_total,asesor_nombre,asesor_email,asesor_telefono,'
            'cliente_nombre,cliente_email,cliente_rut,'
            'cliente_comuna,cliente_region,cliente_tipo,'
            'cliente_empresa,config_margen,productos,plano_url,'
            'contrato_notariado_url,acta_url,motivo_rechazo'
        ).execute()

        _rows_all = resp.data or []
        if periodo != 'todo':
            rows = [r for r in _rows_all
                    if (r.get('fecha_creacion') or r.get('fecha_modificacion') or '')[:10] >= _inicio]
        else:
            rows = _rows_all

        rows_ant = []
        if _inicio_ant and _fin_ant:
            resp_ant = _supa_admin.table('cotizaciones').select(
                'total_total,estado,config_margen'
            ).gte('fecha_creacion', _inicio_ant).lte('fecha_creacion', _fin_ant).execute()
            rows_ant = resp_ant.data or []

        total_ep = len(rows)
        total_monto = sum(float(r.get('total_total') or 0) for r in rows)
        promedio_monto = total_monto / total_ep if total_ep else 0

        def _clasificar_estado(r):
            e = (r.get('estado') or '').upper()
            if 'AUTORIZADO' in e: return 'autorizado'
            if 'BORRADOR' in e: return 'borrador'
            return 'incompleto'

        estados = [_clasificar_estado(r) for r in rows]
        autorizados = estados.count('autorizado')
        borradores = estados.count('borrador')
        incompletos = estados.count('incompleto')
        pct_conv = round((autorizados / total_ep) * 100) if total_ep else 0

        # Estados REALES (misma clasificación/labels que COTIZACIONES) para el embudo.
        estados_full = _dd(int)
        for r in rows:
            _lbl = calcular_estado_label(
                r.get('cliente_nombre', ''), r.get('cliente_email', ''),
                r.get('asesor_nombre', ''), r.get('asesor_email', ''), r.get('asesor_telefono', ''),
                float(r.get('config_margen') or 0), bool((r.get('plano_url') or '').strip()),
                tiene_notariado=bool((r.get('contrato_notariado_url') or '').strip()),
                tiene_acta=bool((r.get('acta_url') or '').strip()),
                motivo_rechazo=r.get('motivo_rechazo', ''))
            estados_full[_lbl] += 1
        estados_full = dict(estados_full)

        # Resultados de negocio (por hitos reales del proyecto)
        adjudicados = sum(1 for r in rows if (r.get('contrato_notariado_url') or '').strip())
        terminados = sum(1 for r in rows if (r.get('acta_url') or '').strip())
        rechazados = sum(1 for r in rows if (r.get('motivo_rechazo') or '').strip())
        con_plano = sum(1 for r in rows if (r.get('plano_url') or '').strip())
        monto_adj = sum(float(r.get('total_total') or 0) for r in rows if (r.get('contrato_notariado_url') or '').strip())
        tasa_cierre = round((adjudicados / total_ep) * 100) if total_ep else 0

        total_ep_ant = len(rows_ant)
        total_monto_ant = sum(float(r.get('total_total') or 0) for r in rows_ant)
        delta_ep = total_ep - total_ep_ant
        delta_monto = total_monto - total_monto_ant

        serie = _dd(float)
        serie_n = _dd(int)
        for r in rows:
            fecha = (r.get('fecha_creacion') or r.get('fecha_modificacion') or '')[:10]
            if fecha and len(fecha) == 10:
                serie[fecha] += float(r.get('total_total') or 0)
                serie_n[fecha] += 1
        fechas_sorted = sorted(serie.keys())
        serie_montos = [round(serie[f]) for f in fechas_sorted]
        serie_counts = [serie_n[f] for f in fechas_sorted]

        cat_montos = _dd(float)
        for r in rows:
            prods = r.get('productos') or []
            if isinstance(prods, str):
                try:
                    import json as _j; prods = _j.loads(prods)
                except Exception: prods = []
            for p in prods:
                cat = p.get('Categoria') or 'Sin categoría'
                subtotal = float(p.get('Subtotal') or 0)
                if subtotal == 0:
                    subtotal = float(p.get('Precio Unitario') or p.get('Precio Final') or 0) * int(p.get('Cantidad') or 1)
                cat_montos[cat] += subtotal
        top_cats = sorted(cat_montos.items(), key=lambda x: x[1], reverse=True)[:6]

        pipeline = sum(float(r.get('total_total') or 0) for r, e in zip(rows, estados) if e == 'borrador')

        ej_montos = _dd(float)
        ej_n = _dd(int)
        for r in rows:
            ej = r.get('asesor_nombre') or 'Sin asignar'
            ej_montos[ej] += float(r.get('total_total') or 0)
            ej_n[ej] += 1
        top_ej = sorted(ej_montos.items(), key=lambda x: x[1], reverse=True)[:6]
        top_ej = [(n, v, ej_n[n]) for n, v in top_ej]

        prod_montos = _dd(float)
        prod_cantidades = _dd(int)
        prod_categoria = {}
        for r in rows:
            prods = r.get('productos') or []
            if isinstance(prods, str):
                try:
                    import json as _j2; prods = _j2.loads(prods)
                except Exception: prods = []
            for p in prods:
                item = (p.get('Item') or '').strip()
                if not item: continue
                subtotal = float(p.get('Subtotal') or 0)
                if subtotal == 0:
                    subtotal = float(p.get('Precio Unitario') or 0) * int(p.get('Cantidad') or 1)
                qty = int(p.get('Cantidad') or 1)
                prod_montos[item] += subtotal
                prod_cantidades[item] += qty
                if item not in prod_categoria:
                    prod_categoria[item] = (p.get('Categoria') or '').strip()
        top_productos = sorted(prod_montos.items(), key=lambda x: x[1], reverse=True)[:30]
        top_productos = [(n, v, prod_cantidades[n], prod_categoria.get(n, '')) for n, v in top_productos]

        comunas = _dd(int)
        regiones = _dd(int)
        for r in rows:
            _com = (r.get('cliente_comuna') or '').strip()
            _reg = (r.get('cliente_region') or '').strip()
            if _com: comunas[_com] += 1
            if _reg: regiones[_reg] += 1
        top_comunas = sorted(comunas.items(), key=lambda x: x[1], reverse=True)[:10]
        top_regiones = sorted(regiones.items(), key=lambda x: x[1], reverse=True)[:10]

        n_natural = sum(1 for r in rows if (r.get('cliente_tipo') or 'natural') == 'natural')
        n_juridica = sum(1 for r in rows if (r.get('cliente_tipo') or '') == 'juridica')
        top_emp = _dd(int)
        for r in rows:
            if (r.get('cliente_tipo') or '') == 'juridica':
                _emp = (r.get('cliente_empresa') or '').strip()
                if _emp: top_emp[_emp] += 1
        top_empresas = sorted(top_emp.items(), key=lambda x: x[1], reverse=True)[:8]

        _MASC = {'carlos','juan','diego','miguel','andrés','andres','pedro','luis','jorge',
                 'gabriel','rodrigo','francisco','felipe','pablo','mario','roberto','sergio',
                 'cristian','christian','nicolás','nicolas','alejandro','manuel','antonio',
                 'jose','josè','josé','daniel','matias','matías','sebastián','sebastian',
                 'gonzalo','mauricio','marcelo','ricardo','eduardo','ignacio','javier',
                 'victor','víctor','claudio','raul','raúl','alfredo','oscar','óscar',
                 'tomás','tomas','alex','alexis','ivan','iván','hugo','alberto','david'}
        _FEM = {'maria','maría','carolina','andrea','claudia','patricia','alejandra',
                'valentina','camila','javiera','paula','ana','rosa','carmen','lucia',
                'lucía','fernanda','daniela','monica','mónica','paola','lorena','isabel',
                'veronica','verónica','beatriz','sandra','laura','marcela','fabiola',
                'natalia','jessica','pamela','viviana','pilar','francisca','constanza',
                'nicole','yasna','ximena','soledad','teresa','angeles','ángeles',
                'macarena','barbara','bárbara','sofia','sofía','elena','alicia','susana'}
        n_masc = n_fem = n_nd = 0
        for r in rows:
            if (r.get('cliente_tipo') or 'natural') == 'juridica': continue
            _nm = (r.get('cliente_nombre') or '').strip().lower().split()
            _primer = _nm[0] if _nm else ''
            if _primer in _MASC: n_masc += 1
            elif _primer in _FEM: n_fem += 1
            else: n_nd += 1

        rangos = {'< 1975 (50+)': 0, '1975-1995 (30-50)': 0, '> 1995 (< 30)': 0, 'No determinado': 0}
        for r in rows:
            if (r.get('cliente_tipo') or 'natural') == 'juridica': continue
            _rut_str = re.sub(r'[^0-9]', '', str(r.get('cliente_rut') or ''))
            try:
                _rut_n = int(_rut_str[:-1]) if len(_rut_str) > 1 else 0
                if _rut_n < 1_000_000: rangos['No determinado'] += 1
                elif _rut_n < 10_000_000: rangos['< 1975 (50+)'] += 1
                elif _rut_n < 15_000_000: rangos['1975-1995 (30-50)'] += 1
                else: rangos['> 1995 (< 30)'] += 1
            except Exception:
                rangos['No determinado'] += 1

        return {
            'total_ep': total_ep, 'total_monto': total_monto,
            'promedio_monto': promedio_monto, 'pipeline': pipeline,
            'autorizados': autorizados, 'borradores': borradores,
            'incompletos': incompletos, 'pct_conv': pct_conv,
            'estados_full': estados_full,
            'adjudicados': adjudicados, 'terminados': terminados,
            'rechazados': rechazados, 'con_plano': con_plano,
            'monto_adj': monto_adj, 'tasa_cierre': tasa_cierre,
            'delta_ep': delta_ep, 'delta_monto': delta_monto,
            'fechas': fechas_sorted, 'serie_montos': serie_montos,
            'serie_counts': serie_counts,
            'top_cats': top_cats, 'top_ej': top_ej,
            'top_productos': top_productos,
            'top_comunas': top_comunas, 'top_regiones': top_regiones,
            'n_natural': n_natural, 'n_juridica': n_juridica,
            'top_empresas': top_empresas,
            'n_masc': n_masc, 'n_fem': n_fem, 'n_nd': n_nd,
            'rangos_etarios': rangos,
        }
    except Exception:
        return None


@st.cache_data(ttl=300, show_spinner=False)
def _dash_extra():
    """CRM (leads por fuente) + mapa nombre→foto de ejecutivos. Defensivo."""
    d = {"cli_total": 0, "por_fuente": {}, "sin_asignar": 0, "avatars": {}}
    try:
        _cli = _supa_admin.table('clientes').select('origen,asignado_email,activo').execute().data or []
        _cli = [c for c in _cli if c.get('activo', True)]
        d["cli_total"] = len(_cli)
        from collections import defaultdict as _dd
        _fu = _dd(int)
        for c in _cli:
            _o = (c.get('origen') or 'Manual').strip() or 'Manual'
            _fu[_o] += 1
            if not (c.get('asignado_email') or '').strip():
                d["sin_asignar"] += 1
        d["por_fuente"] = dict(sorted(_fu.items(), key=lambda x: x[1], reverse=True))
    except Exception:
        pass
    try:
        import httpx as _hx
        r = _hx.get(f"{SUPABASE_URL}/auth/v1/admin/users",
                    headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
                    params={"per_page": 1000, "page": 1}, timeout=12)
        if r.status_code == 200:
            for u in r.json().get("users", []):
                meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
                _nm = (meta.get("nombre") or "").strip().lower()
                _ft = (meta.get("foto_url") or "").strip()
                if _nm and _ft:
                    d["avatars"][_nm] = _ft
    except Exception:
        pass
    return d


# ── Render ────────────────────────────────────────────────────────────────────

def render_tab_dashboard(supabase, supabase_admin=None, **deps):
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@300;400;700;800;900&display=swap');
    .dash-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
      text-transform:uppercase;letter-spacing:0.05em;line-height:1.4;padding-bottom:8px;
      border-bottom:2px solid #e2e8f0;margin:26px 0 16px;display:flex;align-items:center;gap:9px;}
    .kpi-card{background:#fff;border-radius:16px;padding:20px 22px;border:1px solid #e8ebf3;
      box-shadow:0 2px 10px rgba(0,0,0,.05);height:100%;position:relative;overflow:hidden;}
    .kpi-card::after{content:'';position:absolute;top:0;left:0;right:0;height:3px;border-radius:16px 16px 0 0;
      background:linear-gradient(90deg,#2563eb,#06b6d4);}
    .kpi-label{font-size:0.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;
      margin-bottom:8px;display:flex;align-items:center;}
    .kpi-value{font-size:2rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;line-height:1;}
    .kpi-delta-pos{font-size:0.73rem;font-weight:700;color:#16a34a;margin-top:8px;display:flex;align-items:center;gap:4px;}
    .kpi-delta-neg{font-size:0.73rem;font-weight:700;color:#dc2626;margin-top:8px;display:flex;align-items:center;gap:4px;}
    .kpi-delta-neu{font-size:0.73rem;font-weight:600;color:#94a3b8;margin-top:8px;}
    .dash-panel{background:#fff;border-radius:14px;padding:18px 20px;border:1px solid #e8ebf3;box-shadow:0 2px 10px rgba(0,0,0,.05);}
    .dash-mini{background:#fff;border:1px solid #e8ebf3;border-radius:14px;padding:16px 18px;height:100%;box-sizing:border-box;}
    .dash-mini .n{font-size:1.7rem;font-weight:900;color:#0f172a;font-family:'Montserrat',sans-serif;line-height:1;}
    .dash-mini .l{font-size:0.7rem;color:#64748b;margin-top:6px;display:flex;align-items:center;gap:6px;font-weight:600;}
    .funnel-bar-wrap{background:#f1f5f9;border-radius:10px;overflow:hidden;height:10px;}
    .cat-row{display:flex;align-items:center;gap:12px;margin-bottom:12px;}
    .cat-name{font-size:0.82rem;font-weight:700;color:#334155;min-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .cat-bar-wrap{flex:1;background:#f1f5f9;border-radius:6px;height:8px;overflow:hidden;}
    .cat-bar-inner{height:8px;border-radius:6px;background:linear-gradient(90deg,#2563eb,#06b6d4);}
    .cat-monto{font-size:0.8rem;font-weight:800;color:#2563eb;min-width:70px;text-align:right;}
    .ej-row{display:flex;align-items:center;gap:11px;padding:9px 0;border-bottom:1px solid #f4f6fb;}
    .ej-row:last-child{border-bottom:none;}
    .ej-name{font-size:0.85rem;font-weight:700;color:#1e293b;flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .ej-sub{font-size:0.68rem;color:#94a3b8;font-weight:600;}
    .ej-monto{font-size:0.85rem;font-weight:900;color:#2563eb;text-align:right;white-space:nowrap;}
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "dashboard",
        "Dashboard",
        "Resumen ejecutivo del rendimiento comercial y del CRM en tiempo real.",
    )

    _periodo_opciones = {"Este mes": "mes", "Últimos 3 meses": "3meses",
                         "Este año": "año", "Todos los tiempos": "todo"}
    st.markdown(
        "<style>.st-key-dash_periodo label,.st-key-dash_periodo label *{font-family:Montserrat,sans-serif!important;"
        "font-weight:700!important;font-size:0.88rem!important;letter-spacing:0.05em!important;line-height:1.6!important;"
        "text-transform:uppercase!important;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;}</style>",
        unsafe_allow_html=True)
    _periodo_label = st.radio("Período", list(_periodo_opciones.keys()),
                              horizontal=True, index=0, key="dash_periodo", label_visibility="collapsed")
    _periodo = _periodo_opciones[_periodo_label]

    with st.spinner("Cargando datos..."):
        _d = _cargar_datos_dashboard(_periodo)
        _x = _dash_extra()

    if not _d:
        st.error("No se pudieron cargar los datos del dashboard.")
        return

    def _fmt_monto(v):
        if v >= 1_000_000: return f"${v/1_000_000:.1f}M"
        if v >= 1_000: return f"${v/1_000:.0f}K"
        return f"${v:,.0f}"

    def _delta_html(val, prefix=""):
        if val > 0:
            return f'<div class="kpi-delta-pos">{_ic("arrow-up","#16a34a",12,4)}{prefix}{abs(val):,} vs período ant.</div>'
        if val < 0:
            return f'<div class="kpi-delta-neg">{_ic("arrow-down","#dc2626",12,4)}{prefix}{abs(val):,} vs período ant.</div>'
        return '<div class="kpi-delta-neu">Sin cambio</div>'

    # ── KPIs ──
    st.markdown(f'<div class="dash-sec">{_ic("briefcase","#0f172a",17,0)}Métricas clave</div>', unsafe_allow_html=True)
    k1, k2, k3, k4 = st.columns(4)
    for col, icon, label, val, delta in [
        (k1, "briefcase", "Presupuestos", str(_d['total_ep']), _delta_html(_d['delta_ep'])),
        (k2, "dollar", "Monto total", _fmt_monto(_d['total_monto']), _delta_html(int(_d['delta_monto']), prefix="$")),
        (k3, "trending", "Ticket promedio", _fmt_monto(_d['promedio_monto']), '<div class="kpi-delta-neu">por cotización</div>'),
        (k4, "refresh", "Pipeline", _fmt_monto(_d['pipeline']), '<div class="kpi-delta-neu">borradores activos</div>'),
    ]:
        with col:
            st.markdown(f'<div class="kpi-card"><div class="kpi-label">{_ic(icon,"#94a3b8",13,6)}{label}</div>'
                        f'<div class="kpi-value">{val}</div>{delta}</div>', unsafe_allow_html=True)

    # ── Resultados de negocio (NUEVO) ──
    st.markdown(f'<div class="dash-sec">{_ic("target","#0f172a",17,0)}Resultados de negocio</div>', unsafe_allow_html=True)
    _b1, _b2, _b3, _b4, _b5 = st.columns(5)
    _biz = [
        (_b1, "hand", f'{_d["adjudicados"]}', "Adjudicados", "#16a34a"),
        (_b2, "flag", f'{_d["terminados"]}', "Terminados", "#7c3aed"),
        (_b3, "xc", f'{_d["rechazados"]}', "Rechazados", "#dc2626"),
        (_b4, "dollar", _fmt_monto(_d["monto_adj"]), "Monto adjudicado", "#0ea5e9"),
        (_b5, "target", f'{_d["tasa_cierre"]}%', "Tasa de cierre", "#f59e0b"),
    ]
    for col, icon, n, lab, color in _biz:
        with col:
            st.markdown(f'<div class="dash-mini"><div class="n" style="color:{color};">{n}</div>'
                        f'<div class="l">{_ic(icon,color,12,0)}{lab}</div></div>', unsafe_allow_html=True)

    # ── Embudo de conversión (los 9 estados reales, mismos colores/iconos que COTIZACIONES) ──
    st.markdown(f'<div class="dash-sec">{_ic("trending","#0f172a",17,0)}Embudo de conversión</div>', unsafe_allow_html=True)
    _total_ep = _d['total_ep'] or 1
    _ef = _d.get('estados_full', {})

    def _estado_svg(estado, color, size=13):
        return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" '
                f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
                f'{ESTADO_BADGE_ICONS.get(estado, "")}</svg>')

    _presentes = [(e, l) for e, l in _ESTADO_ORDER if _ef.get(e, 0) > 0]
    col_funnel, col_donut = st.columns([3, 2])
    with col_funnel:
        _fh = ('<div class="dash-panel"><div style="display:flex;justify-content:space-between;margin-bottom:16px;">'
               '<span style="font-size:0.72rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">Estado</span>'
               '<span style="font-size:0.72rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;">% del total</span></div>')
        for _e, _l in _presentes:
            _cnt = _ef.get(_e, 0)
            _bg, _fg = ESTADO_BADGE_COLORS.get(_e, ('#f1f5f9', '#64748b'))
            _pct = round((_cnt / _total_ep) * 100)
            _fh += (f'<div style="margin-bottom:12px;"><div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px;gap:8px;">'
                    f'<span style="font-size:0.82rem;font-weight:700;color:#1e293b;display:inline-flex;align-items:center;gap:8px;min-width:0;">'
                    f'<span style="width:22px;height:22px;border-radius:6px;background:{_bg};display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;">{_estado_svg(_e, _fg)}</span>{_l}</span>'
                    f'<span style="font-size:0.82rem;font-weight:800;color:{_fg};white-space:nowrap;">{_cnt} &nbsp;({_pct}%)</span></div>'
                    f'<div class="funnel-bar-wrap"><div style="height:10px;border-radius:10px;width:{_pct}%;background:{_fg};opacity:0.85;"></div></div></div>')
        _fh += "</div>"
        st.markdown(_fh, unsafe_allow_html=True)
    with col_donut:
        with st.container(border=True):
            if _presentes:
                import plotly.graph_objects as go
                _labels = [l for e, l in _presentes]
                _values = [_ef.get(e, 0) for e, l in _presentes]
                _colors = [ESTADO_BADGE_COLORS.get(e, ('#f1f5f9', '#64748b'))[1] for e, l in _presentes]
                _ganados = _ef.get('ADJUDICADO', 0) + _ef.get('PROYECTO TERMINADO', 0)
                _pct_g = round((_ganados / _total_ep) * 100)
                _fig_d = go.Figure(go.Pie(labels=_labels, values=_values, hole=0.62, sort=False,
                    marker=dict(colors=_colors, line=dict(color='white', width=2)), textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} cotizaciones<br>%{percent}<extra></extra>'))
                _fig_d.add_annotation(text=f"<b>{_pct_g}%</b><br><span style='font-size:10px'>ganados</span>",
                    x=0.5, y=0.5, showarrow=False, font=dict(size=18, family='Montserrat'), xref="paper", yref="paper")
                _fig_d.update_layout(showlegend=True, margin=dict(t=14, b=14, l=14, r=14), height=300,
                    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                    legend=dict(font=dict(size=9.5, color='#475569'), orientation='h', yanchor='top', y=-0.02, xanchor='center', x=0.5, bgcolor='rgba(0,0,0,0)'))
                st.plotly_chart(_fig_d, use_container_width=True, config={'displayModeBar': False})

    # ── Evolución temporal ──
    if _d['fechas']:
        st.markdown(f'<div class="dash-sec">{_ic("calendar","#0f172a",17,0)}Evolución de cotizaciones</div>', unsafe_allow_html=True)
        with st.container(border=True):
            import plotly.graph_objects as go
            _fig_l = go.Figure()
            _fig_l.add_trace(go.Bar(x=_d['fechas'], y=_d['serie_counts'], name='N° EP',
                marker=dict(color='rgba(99,102,241,0.25)', line=dict(width=0)), yaxis='y2',
                hovertemplate='<b>%{x}</b><br>%{y} EP<extra></extra>'))
            _fig_l.add_trace(go.Scatter(x=_d['fechas'], y=_d['serie_montos'], mode='lines+markers', name='Monto ($)',
                line=dict(color='#2563eb', width=3.5, shape='spline'),
                marker=dict(size=8, color='#2563eb', line=dict(color='white', width=2.5)),
                fill='tozeroy', fillcolor='rgba(37,99,235,0.07)',
                hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'))
            _fig_l.update_layout(height=320, margin=dict(t=20, b=40, l=70, r=60),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(248,250,252,0.6)',
                xaxis=dict(showgrid=False, tickfont=dict(size=10, color='#64748b'), linecolor='#e2e8f0'),
                yaxis=dict(showgrid=True, gridcolor='rgba(226,232,240,0.6)', tickformat='$,.0f', tickfont=dict(size=10, color='#64748b'), zeroline=False),
                yaxis2=dict(overlaying='y', side='right', showgrid=False, tickfont=dict(size=10, color='#94a3b8'), title=''),
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1, font=dict(size=11), bgcolor='rgba(0,0,0,0)'),
                hovermode='x unified')
            st.plotly_chart(_fig_l, use_container_width=True, config={'displayModeBar': False})

    # ── Top categorías + Top ejecutivos (avatar circular) ──
    col_cats, col_ejs = st.columns(2)
    with col_cats:
        st.markdown(f'<div class="dash-sec">{_ic("package","#0f172a",17,0)}Top categorías</div>', unsafe_allow_html=True)
        if _d['top_cats']:
            _max_cat = _d['top_cats'][0][1] or 1
            _hc = '<div class="dash-panel">'
            for cat_name, cat_val in _d['top_cats']:
                pct_c = round((cat_val / _max_cat) * 100)
                _hc += (f'<div class="cat-row"><div class="cat-name">{cat_name[:18]}</div>'
                        f'<div class="cat-bar-wrap"><div class="cat-bar-inner" style="width:{pct_c}%;"></div></div>'
                        f'<div class="cat-monto">{_fmt_monto(cat_val)}</div></div>')
            _hc += '</div>'
            st.markdown(_hc, unsafe_allow_html=True)
        else:
            st.info("Sin datos de categorías.")
    with col_ejs:
        st.markdown(f'<div class="dash-sec">{_ic("award","#0f172a",17,0)}Top ejecutivos</div>', unsafe_allow_html=True)
        if _d['top_ej']:
            _av = _x.get("avatars", {})
            _he = '<div class="dash-panel">'
            for idx_e, (ej_name, ej_val, ej_cnt) in enumerate(_d['top_ej']):
                _foto = _av.get((ej_name or '').strip().lower(), '')
                _he += (f'<div class="ej-row">{_rank_badge(idx_e)}{_avatar(ej_name, _foto, 34)}'
                        f'<div style="flex:1;min-width:0;"><div class="ej-name">{ej_name[:24]}</div>'
                        f'<div class="ej-sub">{ej_cnt} cotización(es)</div></div>'
                        f'<div class="ej-monto">{_fmt_monto(ej_val)}</div></div>')
            _he += '</div>'
            st.markdown(_he, unsafe_allow_html=True)
        else:
            st.info("Sin datos de ejecutivos.")

    # ── CRM · Leads (NUEVO) ──
    st.markdown(f'<div class="dash-sec">{_ic("users","#0f172a",17,0)}CRM · Leads</div>', unsafe_allow_html=True)
    _fuente_ico = {"Shopify": ("store", "#6d28d9"), "Importado": ("download", "#0ea5e9"),
                   "Manual": ("briefcase", "#64748b"), "Web": ("target", "#2563eb")}
    _cc = st.columns(5)
    with _cc[0]:
        st.markdown(f'<div class="dash-mini"><div class="n">{_x["cli_total"]:,}</div>'
                    f'<div class="l">{_ic("users","#0ea5e9",12,0)}Total clientes / leads</div></div>', unsafe_allow_html=True)
    with _cc[1]:
        _sa = _x["sin_asignar"]
        st.markdown(f'<div class="dash-mini"><div class="n" style="color:{"#dc2626" if _sa else "#16a34a"};">{_sa:,}</div>'
                    f'<div class="l">{_ic("alert","#dc2626" if _sa else "#16a34a",12,0)}Sin asignar</div></div>', unsafe_allow_html=True)
    _fu_items = list(_x.get("por_fuente", {}).items())[:3]
    for _i, (_fname, _fval) in enumerate(_fu_items):
        _fi, _fcol = _fuente_ico.get(_fname, ("briefcase", "#64748b"))
        with _cc[2 + _i]:
            st.markdown(f'<div class="dash-mini"><div class="n" style="color:{_fcol};">{_fval:,}</div>'
                        f'<div class="l">{_ic(_fi,_fcol,12,0)}{_fname}</div></div>', unsafe_allow_html=True)

    # ── Perfil de clientes ──
    st.markdown(f'<div class="dash-sec">{_ic("users","#0f172a",17,0)}Perfil de clientes</div>', unsafe_allow_html=True)
    _tc = _d.get('top_comunas', []); _tr = _d.get('top_regiones', [])
    _nn = _d.get('n_natural', 0); _nj = _d.get('n_juridica', 0)
    _nm = _d.get('n_masc', 0); _nf = _d.get('n_fem', 0); _nd_g = _d.get('n_nd', 0)
    _re = _d.get('rangos_etarios', {}); _te = _d.get('top_empresas', [])

    import plotly.graph_objects as go
    _TMPL = dict(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                 font=dict(family='Inter, sans-serif', color='#1e293b'), margin=dict(l=10, r=10, t=20, b=10))

    col_com, col_reg = st.columns(2)
    with col_com:
        st.markdown(f'<div class="dash-sec" style="margin-top:8px;">{_ic("mappin","#0f172a",16,0)}Top comunas</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _tc:
                _coms = [x[0] for x in _tc]; _vals_c = [x[1] for x in _tc]
                _fc = go.Figure(go.Bar(x=_vals_c[::-1], y=_coms[::-1], orientation='h',
                    marker=dict(color=_vals_c[::-1], colorscale=[[0, '#bfdbfe'], [1, '#1d4ed8']], showscale=False),
                    text=[str(v) for v in _vals_c[::-1]], textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>'))
                _fc.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), yaxis=dict(tickfont=dict(size=11)), height=320)
                st.plotly_chart(_fc, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos de comunas aún")
    with col_reg:
        st.markdown(f'<div class="dash-sec" style="margin-top:8px;">{_ic("map","#0f172a",16,0)}Top regiones</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _tr:
                _regs = [x[0] for x in _tr]; _vals_r = [x[1] for x in _tr]
                _fr = go.Figure(go.Bar(x=_vals_r[::-1], y=_regs[::-1], orientation='h',
                    marker=dict(color=_vals_r[::-1], colorscale=[[0, '#bbf7d0'], [1, '#15803d']], showscale=False),
                    text=[str(v) for v in _vals_r[::-1]], textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>'))
                _fr.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), yaxis=dict(tickfont=dict(size=11)), height=320)
                st.plotly_chart(_fr, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos de regiones aún")

    col_tipo, col_gen, col_edad = st.columns(3)
    with col_tipo:
        st.markdown(f'<div class="dash-sec" style="margin-top:8px;">{_ic("building","#0f172a",16,0)}Tipo de cliente</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _nn + _nj > 0:
                _ft = go.Figure(go.Pie(labels=['Persona natural', 'Persona jurídica'], values=[_nn, _nj], hole=0.55,
                    marker=dict(colors=['#3b82f6', '#f59e0b'], line=dict(color='white', width=2)), textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>'))
                _ft.add_annotation(text=f"<b>{_nn+_nj}</b><br>clientes", x=0.5, y=0.5, showarrow=False, font=dict(size=13, color='#0f172a'))
                _ft.update_layout(**_TMPL, showlegend=True, legend=dict(orientation='h', y=-0.15, font=dict(size=9)), height=280)
                st.plotly_chart(_ft, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sin datos")
    with col_gen:
        st.markdown(f'<div class="dash-sec" style="margin-top:8px;">{_ic("zap","#0f172a",16,0)}Género estimado</div>', unsafe_allow_html=True)
        with st.container(border=True):
            if _nm + _nf + _nd_g > 0:
                _lg, _vg, _cg = [], [], []
                if _nm: _lg.append('Masculino'); _vg.append(_nm); _cg.append('#3b82f6')
                if _nf: _lg.append('Femenino'); _vg.append(_nf); _cg.append('#ec4899')
                if _nd_g: _lg.append('No determinado'); _vg.append(_nd_g); _cg.append('#94a3b8')
                _fg = go.Figure(go.Pie(labels=_lg, values=_vg, hole=0.55,
                    marker=dict(colors=_cg, line=dict(color='white', width=2)), textinfo='percent',
                    hovertemplate='<b>%{label}</b><br>%{value} (%{percent})<extra></extra>'))
                _fg.add_annotation(text=f"<b>{_nm+_nf}</b><br>detect.", x=0.5, y=0.5, showarrow=False, font=dict(size=13, color='#0f172a'))
                _fg.update_layout(**_TMPL, showlegend=True, legend=dict(orientation='h', y=-0.15, font=dict(size=9)), height=280)
                st.plotly_chart(_fg, use_container_width=True, config={'displayModeBar': False})
                st.caption("Estimado por primer nombre", help="Aproximación; no es un dato declarado.")
            else:
                st.info("Sin datos")
    with col_edad:
        st.markdown(f'<div class="dash-sec" style="margin-top:8px;">{_ic("calendar","#0f172a",16,0)}Rango etario est.</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _re_f = {k: v for k, v in _re.items() if v > 0}
            if _re_f:
                _orden = ['< 1975 (50+)', '1975-1995 (30-50)', '> 1995 (< 30)', 'No determinado']
                _le = [k for k in _orden if k in _re_f]; _ve = [_re_f[k] for k in _le]
                _ce = ['#7c3aed', '#2563eb', '#0891b2', '#94a3b8'][:len(_le)]
                _fe = go.Figure(go.Bar(x=_ve, y=_le, orientation='h',
                    marker=dict(color=_ce, line=dict(color='white', width=1)), text=_ve, textposition='outside',
                    hovertemplate='<b>%{y}</b><br>%{x} clientes<extra></extra>'))
                _fe.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), yaxis=dict(tickfont=dict(size=10), automargin=True), height=280)
                st.plotly_chart(_fe, use_container_width=True, config={'displayModeBar': False})
                st.caption("Estimado por correlación de RUT")
            else:
                st.info("Sin datos")

    if _te:
        st.markdown(f'<div class="dash-sec">{_ic("building","#0f172a",17,0)}Top empresas cotizantes</div>', unsafe_allow_html=True)
        with st.container(border=True):
            _en = [x[0] for x in _te]; _ev = [x[1] for x in _te]
            _fe2 = go.Figure(go.Bar(x=_ev[::-1], y=_en[::-1], orientation='h',
                marker=dict(color=_ev[::-1], colorscale=[[0, '#fde68a'], [1, '#d97706']], showscale=False),
                text=[str(v) for v in _ev[::-1]], textposition='outside',
                hovertemplate='<b>%{y}</b><br>%{x} cotizaciones<extra></extra>'))
            _fe2.update_layout(**_TMPL, xaxis=dict(showgrid=False, showticklabels=False, zeroline=False), yaxis=dict(tickfont=dict(size=11)), height=max(200, len(_te) * 38))
            st.plotly_chart(_fe2, use_container_width=True, config={'displayModeBar': False})

    # ── Top 30 productos ──
    st.markdown(f'<div class="dash-sec">{_ic("package","#0f172a",17,0)}Top 30 productos más cotizados</div>', unsafe_allow_html=True)
    if _d.get('top_productos'):
        _max_prod = _d['top_productos'][0][1] or 1
        _hp = ('<div class="dash-panel"><div style="display:flex;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid #f1f5f9;">'
               '<span style="font-size:0.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:24px;">#</span>'
               '<span style="font-size:0.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;flex:1;">Producto</span>'
               '<span style="font-size:0.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:55px;text-align:center;">Cant.</span>'
               '<span style="font-size:0.68rem;font-weight:800;color:#94a3b8;text-transform:uppercase;letter-spacing:0.08em;min-width:100px;text-align:right;">Monto</span></div>')
        for idx_p, (prod_name, prod_val, prod_qty, prod_cat) in enumerate(_d['top_productos'], 1):
            pct_p = round((prod_val / _max_prod) * 100)
            _cp = "#3b82f6" if idx_p <= 3 else "#6366f1" if idx_p <= 10 else "#94a3b8"
            _bp = "800" if idx_p <= 3 else "600"
            _hp += (f'<div style="display:flex;align-items:center;gap:8px;margin-bottom:9px;">'
                    f'<span style="font-size:0.78rem;font-weight:700;color:{_cp};min-width:24px;text-align:center;">{idx_p}</span>'
                    f'<div style="flex:1;min-width:0;"><div style="font-size:0.82rem;font-weight:{_bp};color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{prod_name}</div>'
                    f'<div style="font-size:0.7rem;color:#94a3b8;margin-bottom:3px;">{prod_cat}</div>'
                    f'<div style="background:#f1f5f9;border-radius:4px;height:5px;overflow:hidden;"><div style="width:{pct_p}%;height:5px;border-radius:4px;background:{_cp};opacity:0.7;"></div></div></div>'
                    f'<span style="font-size:0.8rem;font-weight:700;color:#475569;min-width:55px;text-align:center;">{prod_qty:,}</span>'
                    f'<span style="font-size:0.82rem;font-weight:800;color:{_cp};min-width:100px;text-align:right;">{_fmt_monto(prod_val)}</span></div>')
        _hp += '</div>'
        st.markdown(_hp, unsafe_allow_html=True)
    else:
        st.info("Sin datos de productos para el período seleccionado.")

    st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
    _rc1, _rc2, _rc3 = st.columns([1, 1, 1])
    with _rc2:
        if st.button("Actualizar dashboard", key="btn_refresh_dash", use_container_width=True, icon=":material/refresh:"):
            _cargar_datos_dashboard.clear()
            _dash_extra.clear()
            st.rerun()
    st.caption(f"Período: {_periodo_label}")
