"""
Tab RANKING — Perfil del ejecutivo + métricas de dinero (ganado / casi ganado /
perdido) por periodo + ranking del equipo. Rol-aware (ejecutivo vs admin/root).
"""
import json
import streamlit as st
import streamlit.components.v1 as components
import httpx
from datetime import datetime, timedelta
from config.supabase import supabase_admin as _supa_admin
from config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
from services.cotizacion_service import calcular_estado_label
from views.layout import render_page_header


# ── Iconos SVG (estilo Lucide) — reemplazan emojis en HTML custom ─────────────
_IC = {
    "dollar":    '<line x1="12" x2="12" y1="2" y2="22"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>',
    "clock":     '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "trenddown": '<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "chart":     '<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="16"/>',
    "list":      '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    "trophy":    '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
    "flame":     '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"/>',
    "alert":     '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "medal":     '<path d="M7.21 15 2.66 7.14a2 2 0 0 1 .13-2.2L4.4 2.8A2 2 0 0 1 6 2h12a2 2 0 0 1 1.6.8l1.6 2.14a2 2 0 0 1 .14 2.2L16.79 15"/><path d="M11 12 5.43 2.31"/><path d="m13 12 5.57-9.69"/><path d="M8 7h8"/><circle cx="12" cy="17" r="5"/><path d="M12 18v-2h-.5"/>',
    "users":     '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
}


# Lightbox glass para ampliar la foto del asesor (clic en la foto del hero).
# Se inyecta vía components.html: bindea el clic sobre `.rk-photo[data-zurl]` en
# el documento padre y monta un overlay full-screen con la imagen grande + nombre.
_LIGHTBOX_JS = """
<script>
(function(){
  var P = window.parent, D = P.document;
  function open(url, name){
    if(P.__ecLb){ try{ P.__ecLb.remove(); }catch(e){} }
    var ov = D.createElement('div');
    ov.style.cssText = 'position:fixed;inset:0;z-index:2147483647;display:flex;align-items:center;'
      + 'justify-content:center;background:rgba(8,12,24,0.72);-webkit-backdrop-filter:blur(9px);backdrop-filter:blur(9px);';
    ov.innerHTML =
      '<div data-card="1" style="position:relative;display:flex;flex-direction:column;align-items:center;gap:18px;'
      + 'padding:26px 26px 22px;background:rgba(255,255,255,0.09);border:1px solid rgba(255,255,255,0.18);'
      + 'border-radius:26px;-webkit-backdrop-filter:blur(20px);backdrop-filter:blur(20px);box-shadow:0 30px 90px rgba(0,0,0,.55);">'
      +   '<img src="'+url+'" style="width:min(78vw,460px);height:min(78vw,460px);border-radius:20px;object-fit:cover;'
      +     'border:4px solid rgba(255,255,255,0.22);box-shadow:0 24px 60px rgba(0,0,0,.5);display:block;">'
      +   '<div style="font-family:Montserrat,sans-serif;font-weight:800;font-size:1.35rem;color:#fff;letter-spacing:0.01em;text-align:center;">'+name+'</div>'
      +   '<div data-close="1" style="position:absolute;top:12px;right:12px;width:36px;height:36px;border-radius:50%;'
      +     'background:rgba(255,255,255,0.16);border:1px solid rgba(255,255,255,0.25);color:#fff;display:flex;align-items:center;'
      +     'justify-content:center;cursor:pointer;font-size:22px;line-height:1;font-family:system-ui;">&times;</div>'
      + '</div>';
    function close(){ try{ ov.remove(); }catch(e){} P.__ecLb=null; D.removeEventListener('keydown', onKey); }
    function onKey(e){ if(e.key==='Escape') close(); }
    ov.addEventListener('click', function(e){
      if(!e.target.closest('[data-card]') || e.target.closest('[data-close]')) close();
    });
    D.addEventListener('keydown', onKey);
    D.body.appendChild(ov);
    P.__ecLb = ov;
  }
  function bind(){
    var ph = D.querySelector('.rk-photo[data-zurl]');
    if(!ph) return false;
    if(ph.__ecLbBound) return true;
    ph.__ecLbBound = true;
    ph.style.cursor = 'zoom-in';
    ph.addEventListener('click', function(){ open(ph.getAttribute('data-zurl'), ph.getAttribute('data-zname')||''); });
    return true;
  }
  var n=0, iv=setInterval(function(){ n++; if(bind() || n>50) clearInterval(iv); }, 120);
})();
</script>
"""


def _svg_ic(key, size=16, color="currentColor", sw=2, mr=0, valign=-3):
    """SVG inline (Lucide) para incrustar en HTML custom."""
    style = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        style += f"margin-right:{mr}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{style}">{_IC.get(key, "")}</svg>')


# ── Datos ────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120, show_spinner=False)
def _fetch_cotizaciones_rank(_cb: str = ''):
    try:
        return _supa_admin.table('cotizaciones').select(
            'numero,asesor_nombre,asesor_email,cliente_nombre,cliente_email,asesor_telefono,'
            'config_margen,plano_url,plano_nombre,contrato_notariado_url,acta_url,'
            'motivo_rechazo,total_total,total_comision_vendedor,fecha_creacion'
        ).execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_users_map(_cb: str = ''):
    """email(min) -> {foto_url, nombre, rol}. Incluye a todos (también roots)."""
    try:
        r = httpx.get(
            f"{SUPABASE_URL}/auth/v1/admin/users",
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            params={"per_page": 1000, "page": 1}, timeout=15,
        )
        r.raise_for_status()
        out = {}
        for u in r.json().get("users", []):
            em = (u.get("email") or "").lower()
            meta = u.get("user_metadata") or u.get("raw_user_meta_data") or {}
            out[em] = {
                "foto_url": meta.get("foto_url", "") or "",
                "nombre": meta.get("nombre", em) or em,
                "rol": meta.get("rol", "ejecutivo"),
            }
        return out
    except Exception:
        return {}


def _clasificar(row):
    """Devuelve la etiqueta de estado (misma fuente que la tabla/badges)."""
    return calcular_estado_label(
        row.get('cliente_nombre', ''), row.get('cliente_email', ''),
        row.get('asesor_nombre', ''), row.get('asesor_email', ''), row.get('asesor_telefono', ''),
        float(row.get('config_margen') or 0),
        bool(row.get('plano_url') or row.get('plano_nombre')),
        tiene_notariado=bool(row.get('contrato_notariado_url')),
        tiene_acta=bool(row.get('acta_url')),
        motivo_rechazo=row.get('motivo_rechazo', '') or '',
    )


def _bucket(label):
    if label in ('PROYECTO TERMINADO', 'ADJUDICADO'):
        return 'ganado'
    if label == 'RECHAZADO':
        return 'perdido'
    return 'casi'


def _parse_fecha(fc):
    if not fc:
        return None
    try:
        return datetime.fromisoformat(str(fc).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def _agregar(rows, period_days=None, only_email=None):
    """Agrega por ejecutivo dentro del periodo (filtra por fecha_creacion)."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    agg = {}
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        nm = (r.get('asesor_nombre') or '').strip() or 'Sin asignar'
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        key = em or nm
        a = agg.setdefault(key, {
            'email': em, 'nombre': nm, 'ganado': 0.0, 'casi': 0.0, 'perdido': 0.0,
            'generado': 0.0, 'n_total': 0, 'n_ganado': 0, 'n_casi': 0, 'n_perdido': 0,
            'com_ganado': 0.0, 'com_casi': 0.0, 'com_perdido': 0.0,
        })
        monto = float(r.get('total_total') or 0)
        com = float(r.get('total_comision_vendedor') or 0)   # comisión del ejecutivo
        b = _bucket(_clasificar(r))
        a['n_total'] += 1
        a['generado'] += monto
        if b == 'ganado':
            a['ganado'] += monto; a['n_ganado'] += 1; a['com_ganado'] += com
        elif b == 'perdido':
            a['perdido'] += monto; a['n_perdido'] += 1; a['com_perdido'] += com
        else:
            a['casi'] += monto; a['n_casi'] += 1; a['com_casi'] += com
    return agg


# Taxonomía de estados → bucket. Orden de presentación dentro de cada bucket.
# (bucket, etiqueta_calcular_estado_label, nombre_a_mostrar)
_ESTADOS_ORDEN = [
    ('ganado',  'ADJUDICADO',           'Adjudicado'),
    ('ganado',  'PROYECTO TERMINADO',   'Proyecto terminado'),
    ('casi',    'AUTORIZADO CON PLANO', 'Autorizado con plano'),
    ('casi',    'AUTORIZADO',           'Autorizado'),
    ('casi',    'BORRADOR CON PLANO',   'Borrador con plano'),
    ('casi',    'BORRADOR',             'Borrador'),
    ('casi',    'INCOMPLETO CON PLANO', 'Incompleto con plano'),
    ('casi',    'INCOMPLETO',           'Incompleto'),
    ('perdido', 'RECHAZADO',            'Rechazado'),
]

# bucket -> (color base, etiqueta, clave de icono, color claro para fondo oscuro)
_BUCKET_META = {
    'ganado':  ('#16a34a', 'Ganado',      'dollar',    '#4ade80'),
    'casi':    ('#f59e0b', 'Casi ganado', 'clock',     '#fbbf24'),
    'perdido': ('#dc2626', 'Perdido',     'trenddown', '#f87171'),
}


def _desglose_estados(rows, period_days=None, only_email=None):
    """Cuenta presupuestos y suma montos por estado dentro del periodo/scope.
    Devuelve {etiqueta_estado: {'n': int, 'monto': float}}."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    out = {}
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        lbl = _clasificar(r)
        e = out.setdefault(lbl, {'n': 0, 'monto': 0.0})
        e['n'] += 1
        e['monto'] += float(r.get('total_total') or 0)
    return out


def _listar_presupuestos(rows, period_days=None, only_email=None):
    """Lista de presupuestos individuales dentro del periodo/scope, orden por monto desc.
    Cada item: {bucket, estado, numero, cliente, asesor, monto}."""
    cutoff = (datetime.now() - timedelta(days=period_days)) if period_days else None
    out = []
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        if cutoff:
            d = _parse_fecha(r.get('fecha_creacion'))
            if d is None or d < cutoff:
                continue
        lbl = _clasificar(r)
        out.append({
            'bucket': _bucket(lbl),
            'estado': lbl,
            'numero': (str(r.get('numero') or '').strip() or '—'),
            'cliente': (str(r.get('cliente_nombre') or '').strip() or 'Sin cliente'),
            'asesor': (str(r.get('asesor_nombre') or '').strip() or 'Sin asignar'),
            'monto': float(r.get('total_total') or 0),
        })
    out.sort(key=lambda x: x['monto'], reverse=True)
    return out


def _money_exacto(v):
    """Monto exacto con separador de miles estilo CL: $25.400.000."""
    return '$' + f'{abs(float(v or 0)):,.0f}'.replace(',', '.')


def _granularidad(period_days):
    """Tamaño de bucket temporal según el periodo: día / semana / mes."""
    if period_days is None:
        return 'mes'
    if period_days <= 31:
        return 'dia'
    if period_days <= 92:
        return 'semana'
    return 'mes'


def _serie_temporal(rows, period_days=None, only_email=None):
    """Presupuestos por bucket temporal (día/semana/mes según el periodo), por
    fecha_creacion. Devuelve (lista_buckets, granularidad). Cada bucket:
    {label, fecha_full, n, items:[{numero,cliente,asesor,estado}]}. Incluye
    buckets vacíos para que la línea de tiempo sea continua."""
    now = datetime.now()
    gran = _granularidad(period_days)

    def _kf(d):
        if gran == 'dia':
            return (d.strftime('%Y-%m-%d'), d.strftime('%d/%m'), d.strftime('%d/%m/%Y'))
        if gran == 'semana':
            wk = d - timedelta(days=d.weekday())
            return (wk.strftime('%Y-%m-%d'), wk.strftime('%d/%m'), 'Semana del ' + wk.strftime('%d/%m/%Y'))
        return (d.strftime('%Y-%m'), d.strftime('%m/%Y'), d.strftime('%m/%Y'))

    cutoff = (now - timedelta(days=period_days)) if period_days else None
    sel, fechas = [], []
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        d = _parse_fecha(r.get('fecha_creacion'))
        if d is None or (cutoff and d < cutoff):
            continue
        sel.append((d, r)); fechas.append(d)

    buckets = {}

    def _ensure(d):
        k, lbl, full = _kf(d)
        if k not in buckets:
            buckets[k] = {'label': lbl, 'fecha_full': full, 'n': 0, 'items': []}
        return k

    # Rango completo de buckets (incluye vacíos) desde el cutoff (o la fecha más
    # antigua si es "Todo") hasta hoy.
    start = cutoff if cutoff else (min(fechas) if fechas else now)
    if gran == 'dia':
        cur = start
        while cur <= now:
            _ensure(cur); cur += timedelta(days=1)
    elif gran == 'semana':
        cur = start - timedelta(days=start.weekday())
        while cur <= now:
            _ensure(cur); cur += timedelta(days=7)
    else:
        y, m = start.year, start.month
        while (y, m) <= (now.year, now.month):
            _ensure(datetime(y, m, 1))
            m += 1
            if m > 12:
                m = 1; y += 1

    for d, r in sel:
        b = buckets[_ensure(d)]
        b['n'] += 1
        b['items'].append({
            'numero': (str(r.get('numero') or '').strip() or '—'),
            'cliente': (str(r.get('cliente_nombre') or '').strip() or 'Sin cliente'),
            'asesor': (str(r.get('asesor_nombre') or '').strip() or 'Sin asignar'),
            'asesor_email': (str(r.get('asesor_email') or '').strip().lower()),
            'estado': _clasificar(r),
        })

    return [buckets[k] for k in sorted(buckets.keys())], gran


def _ventas_este_mes(rows, only_email=None):
    """Ventas (ganado: adjudicado/terminado) creadas en el MES calendario actual, en el scope."""
    now = datetime.now()
    ini = datetime(now.year, now.month, 1)
    c = 0
    for r in rows:
        em = (r.get('asesor_email') or '').lower()
        if only_email is not None and em != only_email:
            continue
        d = _parse_fecha(r.get('fecha_creacion'))
        if d is None or d < ini:
            continue
        if _bucket(_clasificar(r)) == 'ganado':
            c += 1
    return c


def _dias_restantes_mes():
    """Días que faltan para terminar el mes calendario actual."""
    now = datetime.now()
    nxt = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)
    total = (nxt - datetime(now.year, now.month, 1)).days
    return total - now.day


def _fmt_money(v):
    v = float(v or 0)
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000:
        return f"{sign}${v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{sign}${v/1_000:.0f}K"
    return f"{sign}${v:,.0f}"


# ── Render ───────────────────────────────────────────────────────────────────

_PERIODOS = {'Semana': 7, 'Mes': 30, '3 meses': 90, 'Año': 365, 'Todo': None}

# Overlay del gráfico temporal: tarjeta con cabecera (fecha · total), burbujas
# (foto del asesor 70x70 + badge rojo con su conteo) y la lista de presupuestos
# (N° EP · cliente · asesor). Plotly no soporta imágenes en su tooltip, así que
# se inyecta vía components.html un listener sobre el div del gráfico (documento
# padre). HOVER: muestra el overlay y oscurece la barra. CLICK: fija el overlay
# (queda pegado) y pone borde naranjo a la barra; clic fuera de barra lo suelta.
# Se pinta por DOM (sin depender de window.Plotly). Re-bindea cada run.
# __DATA__ se reemplaza por el JSON de buckets.
_FACE_TIP_JS = """
<script>
(function(){
  var P = window.parent, D = P.document;
  var DATA = __DATA__;
  var BASE='#6366f1', HOV='#4338ca', ORANGE='#f59e0b';
  if (P.__ecRkTip){ try{ P.__ecRkTip.remove(); }catch(e){} }
  var tip = D.createElement('div');
  tip.style.cssText = 'position:fixed;z-index:2147483646;pointer-events:none;display:none;';
  D.body.appendChild(tip);
  P.__ecRkTip = tip;
  var lastX=0, lastY=0, pinned=null, gd=null, N=0, isBar=true, curIdx=null, pressIdx=null;

  function bubble(a){
    var ph = a.photo
      ? '<img src="'+a.photo+'" style="width:70px;height:70px;border-radius:50%;object-fit:cover;border:3px solid #fff;box-shadow:0 5px 14px rgba(0,0,0,.3);display:block;">'
      : '<div style="width:70px;height:70px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-family:Montserrat,sans-serif;font-weight:800;color:#fff;font-size:1.6rem;background:linear-gradient(135deg,#6366f1,#8b5cf6);border:3px solid #fff;box-shadow:0 5px 14px rgba(0,0,0,.3);">'+(a.ini||'?')+'</div>';
    var badge = '<div style="position:absolute;top:-7px;right:-7px;min-width:24px;height:24px;border-radius:50%;background:#dc2626;color:#fff;font-family:Montserrat,sans-serif;font-weight:800;font-size:0.74rem;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.3);padding:0 4px;box-sizing:border-box;">'+a.count+'</div>';
    var nm = '<div style="text-align:center;margin-top:5px;font-family:Montserrat,sans-serif;font-size:0.62rem;font-weight:700;color:#0f172a;white-space:nowrap;max-width:90px;overflow:hidden;text-overflow:ellipsis;">'+a.name+'</div>';
    return '<div style="display:flex;flex-direction:column;align-items:center;"><div style="position:relative;display:inline-block;">'+ph+badge+'</div>'+nm+'</div>';
  }
  function line(it, sa){
    var s = '<b>'+it.num+'</b> &middot; '+it.cli + (sa ? ' &middot; '+it.ase : '');
    return '<div style="padding:3px 0;border-top:1px solid #f1f5f9;font-size:0.78rem;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">'+s+'</div>';
  }
  function html(d, isPinned){
    var bs = (d.asesores||[]).map(bubble).join('');
    var lst = (d.items||[]).map(function(it){ return line(it, d.showAse); }).join('');
    var hint = isPinned
      ? '<span style="color:#f59e0b;font-weight:800;">FIJADO</span> &middot; clic para soltar'
      : 'clic en la barra para fijar';
    return ''
      + '<div style="background:#fff;border:1px solid #e2e8f0;border-radius:15px;box-shadow:0 14px 38px rgba(0,0,0,.30);padding:12px 14px;width:360px;max-width:92vw;font-family:Montserrat,sans-serif;">'
      +   '<div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:9px;">'
      +     '<div style="font-weight:800;color:#0f172a;font-size:0.9rem;">'+d.date+' &middot; '+d.total+' presupuesto'+(d.total===1?'':'s')+'</div>'
      +     '<div style="font-size:0.6rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;">'+hint+'</div>'
      +   '</div>'
      +   '<div style="display:flex;flex-wrap:wrap;gap:11px;margin-bottom:9px;">'+bs+'</div>'
      +   '<div style="max-height:210px;overflow-y:auto;">'+lst+'</div>'
      + '</div>';
  }
  function barPath(i){
    if(!gd) return null;
    var els = gd.querySelectorAll(isBar ? '.barlayer .point' : '.scatterlayer .points path');
    var el = els[i]; if(!el) return null;
    return (el.tagName && el.tagName.toLowerCase()==='path') ? el : el.querySelector('path');
  }
  function paint(hoverIdx){
    for(var i=0;i<N;i++){
      var pa = barPath(i); if(!pa) continue;
      if(i===pinned){ pa.style.fill=HOV; pa.style.stroke=ORANGE; pa.style.strokeWidth='3px'; }
      else if(i===hoverIdx){ pa.style.fill=HOV; pa.style.stroke='none'; pa.style.strokeWidth='0'; }
      else { pa.style.fill=BASE; pa.style.stroke='none'; pa.style.strokeWidth='0'; }
    }
  }
  function place(idx){
    var w=tip.offsetWidth||360, h=tip.offsetHeight||220, x, y;
    var pa = barPath(idx), r = pa ? pa.getBoundingClientRect() : null;
    if(r && r.width){
      x = r.left + r.width/2 - w/2;
      y = (r.top - h - 12 >= 6) ? (r.top - h - 12) : (r.bottom + 12);
    } else { x = lastX+16; y = lastY-h-16; }
    if(x+w > P.innerWidth-6) x = P.innerWidth-w-6;
    if(x<6) x=6;
    if(y+h > P.innerHeight-6) y = P.innerHeight-h-6;
    if(y<6) y=6;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function show(idx, isPinned){
    var d = DATA[idx];
    if(!d || !d.total){ tip.style.display='none'; return; }
    tip.innerHTML = html(d, isPinned);
    tip.style.pointerEvents = isPinned ? 'auto' : 'none';
    tip.style.display='block';
    place(idx);
  }
  function onHover(ev){
    var pt = ev && ev.points && ev.points[0]; if(!pt) return;
    curIdx = (pt.pointNumber!=null?pt.pointNumber:pt.pointIndex);
    paint(curIdx);
    if(pinned===null) show(curIdx, false);
  }
  function onUnhover(){ curIdx=null; paint(-1); if(pinned===null) tip.style.display='none'; }
  function onDown(){ pressIdx = curIdx; }   // captura la barra bajo el cursor antes del click
  function onClick(){
    var i = (pressIdx!==null) ? pressIdx : curIdx;
    pressIdx = null;
    if(i!==null){                                // clic sobre una barra
      if(pinned===i){ pinned=null; paint(i); show(i, false); }   // soltar (sigo encima)
      else { pinned=i; paint(i); show(i, true); }                // fijar
    } else if(pinned!==null){                     // clic fuera de barra -> dinámico
      pinned=null; paint(-1); tip.style.display='none';
    }
  }
  function bind(g){
    if(!g || !g.on) return false;
    gd = g;
    N = (g.data && g.data[0] && g.data[0].x) ? g.data[0].x.length : 0;
    isBar = !(g.data && g.data[0] && g.data[0].type==='scatter');
    try{ if(g.removeAllListeners){ g.removeAllListeners('plotly_hover'); g.removeAllListeners('plotly_unhover'); } }catch(e){}
    if(g.__ecMM){ try{ g.removeEventListener('mousemove', g.__ecMM); }catch(e){} }
    if(g.__ecDN){ try{ g.removeEventListener('mousedown', g.__ecDN); }catch(e){} }
    if(g.__ecCL){ try{ g.removeEventListener('click', g.__ecCL); }catch(e){} }
    g.__ecMM = function(e){ lastX=e.clientX; lastY=e.clientY; };
    g.addEventListener('mousemove', g.__ecMM);
    g.__ecDN = onDown; g.addEventListener('mousedown', g.__ecDN);
    g.__ecCL = onClick; g.addEventListener('click', g.__ecCL);
    g.on('plotly_hover', onHover);
    g.on('plotly_unhover', onUnhover);
    return true;
  }
  var tries=0;
  var iv = setInterval(function(){
    tries++;
    var g = D.querySelector('.js-plotly-plot');
    if((g && bind(g)) || tries>50){ clearInterval(iv); }
  }, 120);
})();
</script>
"""


def render_tab_ranking(supabase, **deps):
    import plotly.graph_objects as go

    _rol   = st.session_state.get('rol_usuario', 'ejecutivo')
    _email = (st.session_state.get('auth_email', '') or '').lower()
    _nombre_sesion = st.session_state.get('auth_nombre') or _email
    _es_admin = _rol in ('root', 'admin')

    st.markdown("""
    <style>
    .rk-hero{display:flex;gap:24px;align-items:center;justify-content:space-between;
        background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#334155 100%);
        border-radius:22px;padding:26px 30px;margin-bottom:18px;box-shadow:0 10px 40px rgba(15,23,42,0.25);}
    .rk-hero-name{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.9rem;color:#fff;line-height:1.05;letter-spacing:-0.01em;}
    .rk-hero-role{display:inline-flex;align-items:center;gap:6px;margin-top:8px;font-size:0.72rem;font-weight:800;
        text-transform:uppercase;letter-spacing:0.08em;color:#0f172a;background:#fbbf24;border-radius:99px;padding:4px 12px;}
    .rk-photo{width:clamp(150px,22vw,250px);height:clamp(150px,22vw,250px);border-radius:50%;object-fit:cover;
        border:5px solid rgba(255,255,255,0.18);box-shadow:0 12px 40px rgba(0,0,0,0.4);flex-shrink:0;}
    .rk-photo-ph{display:flex;align-items:center;justify-content:center;font-family:'Montserrat',sans-serif;
        font-weight:900;color:#fff;font-size:clamp(3rem,7vw,5rem);background:linear-gradient(135deg,#6366f1,#8b5cf6);}
    .rk-hero-left{flex:1;min-width:0;display:flex;flex-direction:column;}
    .rk-hero-top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;}
    .rk-hero-pos{display:inline-flex;align-items:center;gap:11px;padding:10px 16px;border-radius:16px;flex-shrink:0;
        background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.16);
        -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);}
    .rk-hero-pos-num{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.05rem;color:#fff;line-height:1.1;}
    .rk-hero-pos-lbl{font-size:0.6rem;color:rgba(255,255,255,0.6);text-transform:uppercase;letter-spacing:0.04em;margin-top:2px;}
    .rk-hero-sub{color:rgba(255,255,255,0.7);font-size:0.82rem;margin-top:9px;}
    .rk-hero-msg{display:inline-flex;align-self:flex-start;align-items:center;gap:7px;margin-top:13px;
        font-size:0.84rem;font-weight:700;padding:7px 14px;border-radius:99px;
        -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);}
    .rk-hero-msg.alerta{background:rgba(245,158,11,0.16);border:1px solid rgba(251,191,36,0.45);color:#fde68a;}
    .rk-hero-msg.ok{background:rgba(34,197,94,0.16);border:1px solid rgba(74,222,128,0.45);color:#bbf7d0;}
    .rk-hero-money{display:flex;gap:12px;margin-top:16px;flex-wrap:wrap;}
    .rk-gcard{flex:1;min-width:148px;background:rgba(255,255,255,0.07);
        -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);
        border:1px solid rgba(255,255,255,0.14);border-radius:14px;padding:12px 15px;}
    .rk-gc-lbl{font-size:0.63rem;font-weight:800;text-transform:uppercase;letter-spacing:0.05em;color:rgba(255,255,255,0.72);}
    .rk-gc-val{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.5rem;line-height:1.1;margin-top:3px;}
    .rk-gc-sub{font-size:0.66rem;color:rgba(255,255,255,0.55);margin-top:3px;}
    .rk-gc-com{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:8px;
        padding-top:7px;border-top:1px solid rgba(255,255,255,0.12);}
    .rk-gc-com span:first-child{font-size:0.62rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.04em;color:rgba(255,255,255,0.6);}
    .rk-gc-com span:last-child{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.92rem;}
    .rk-sec{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
        text-transform:uppercase;letter-spacing:0.05em;line-height:1.6;padding-bottom:8px;
        border-bottom:2px solid #e2e8f0;margin:24px 0 14px;display:flex;align-items:center;gap:8px;}
    .rk-sec svg{color:#0f172a;flex-shrink:0;}
    .rk-card{display:flex;align-items:center;gap:14px;padding:12px 16px;border-radius:14px;
        background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#334155 100%);
        border:1px solid rgba(255,255,255,0.08);box-shadow:0 4px 16px rgba(15,23,42,0.22);margin-bottom:9px;}
    .rk-card.me{border:2px solid #818cf8;box-shadow:0 6px 20px rgba(99,102,241,0.35);}
    .rk-card.sel{border:2px solid #818cf8;box-shadow:0 6px 22px rgba(99,102,241,0.45);}
    .rk-rav{width:46px;height:46px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid rgba(255,255,255,0.18);}
    .rk-rav-ph{display:flex;align-items:center;justify-content:center;font-weight:800;color:#fff;font-size:1.1rem;
        background:linear-gradient(135deg,#6366f1,#8b5cf6);}
    .rk-pos{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.15rem;width:30px;text-align:center;flex-shrink:0;}
    .rk-est-group{background:linear-gradient(135deg,#0f172a 0%,#1e293b 55%,#334155 100%);
        border:1px solid rgba(255,255,255,0.08);border-radius:14px;padding:14px 16px;
        box-shadow:0 6px 20px rgba(15,23,42,0.22);height:100%;}
    .rk-est-head{font-size:0.74rem;font-weight:900;text-transform:uppercase;letter-spacing:0.05em;
        display:flex;align-items:center;gap:8px;}
    .rk-est-badge{color:#fff;font-size:0.7rem;font-weight:800;border-radius:99px;padding:1px 9px;margin-left:auto;}
    .rk-est-tot{font-family:'Montserrat',sans-serif;font-weight:900;font-size:1.25rem;color:#fff;margin:3px 0 8px;}
    .rk-est-item{display:flex;align-items:center;gap:8px;padding:6px 0;border-top:1px solid rgba(255,255,255,0.08);font-size:0.83rem;}
    .rk-est-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
    .rk-est-name{color:rgba(255,255,255,0.82);flex:1;min-width:0;}
    .rk-est-n{font-weight:800;color:#fff;}
    .rk-est-m{color:rgba(255,255,255,0.55);font-size:0.74rem;min-width:60px;text-align:right;}
    .rk-est-empty{color:rgba(255,255,255,0.5);font-size:0.8rem;padding:8px 0;font-style:italic;}
    .rk-est-com{display:flex;justify-content:space-between;align-items:center;margin-top:9px;padding-top:9px;
        border-top:1px solid rgba(255,255,255,0.14);}
    .rk-est-com span:first-child{font-size:0.62rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.04em;color:rgba(255,255,255,0.62);}
    .rk-est-com span:last-child{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.98rem;}
    .rk-pp-wrap{max-height:360px;overflow-y:auto;margin-top:6px;}
    .rk-pp-row{display:flex;align-items:center;gap:10px;padding:8px 4px;border-bottom:1px solid #f1f5f9;}
    .rk-pp-row:last-child{border-bottom:none;}
    .rk-pp-tag{font-size:0.6rem;font-weight:800;text-transform:uppercase;letter-spacing:0.03em;
        color:#fff;border-radius:5px;padding:2px 6px;white-space:nowrap;flex-shrink:0;}
    .rk-pp-mid{flex:1;min-width:0;}
    .rk-pp-num{font-family:'Montserrat',sans-serif;font-weight:800;color:#0f172a;font-size:0.84rem;}
    .rk-pp-cli{font-size:0.74rem;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
    .rk-pp-m{font-family:'Montserrat',sans-serif;font-weight:800;font-size:0.86rem;white-space:nowrap;flex-shrink:0;}
    div.st-key-rk_chart{display:flex;justify-content:flex-end;}
    </style>
    """, unsafe_allow_html=True)

    render_page_header(
        "ranking",
        "Ranking de Ejecutivos",
        "Tu desempe&#241;o y el del equipo &#8212; dinero ganado, casi ganado y perdido.",
    )

    with st.spinner("Cargando ranking..."):
        _rows = _fetch_cotizaciones_rank()
        _umap = _fetch_users_map()

    # ── Periodo ── (el widget se renderiza más abajo, junto al tipo de gráfico;
    # aquí solo leemos el valor para calcular hero/cards/desglose que van antes).
    _periodo = st.session_state.get('rk_periodo', 'Mes') or 'Mes'
    _days = _PERIODOS.get(_periodo)

    # ── Ejecutivo seleccionado al hacer clic en el ranking del equipo ──
    # rk_perfil_email: None = vista por defecto (admin=equipo, ejecutivo=propio);
    # string (puede ser '' para "Sin asignar") = se muestra el perfil de ese ejecutivo.
    _sel_email = st.session_state.get('rk_perfil_email')
    _sel_nombre = st.session_state.get('rk_perfil_nombre', '')
    _viewing_other = _sel_email is not None

    if _viewing_other:
        _scope = _sel_email
        if st.button(("Volver al equipo" if _es_admin else "Volver a mi panel"),
                     icon=":material/arrow_back:", key="rk_volver"):
            st.session_state.pop('rk_perfil_email', None)
            st.session_state.pop('rk_perfil_nombre', None)
            st.rerun()
    elif _es_admin:
        _scope = None
    else:
        _scope = _email

    # ── Métricas del scope (None = equipo completo) ──
    _agg_f = _agregar(_rows, period_days=_days, only_email=_scope)
    _ganado  = sum(a['ganado'] for a in _agg_f.values())
    _casi    = sum(a['casi'] for a in _agg_f.values())
    _perdido = sum(a['perdido'] for a in _agg_f.values())
    _n_total = sum(a['n_total'] for a in _agg_f.values())
    _n_gan   = sum(a['n_ganado'] for a in _agg_f.values())
    _n_casi  = sum(a['n_casi'] for a in _agg_f.values())
    _n_perd  = sum(a['n_perdido'] for a in _agg_f.values())
    _com_g   = sum(a['com_ganado'] for a in _agg_f.values())
    _com_c   = sum(a['com_casi'] for a in _agg_f.values())
    _com_p   = sum(a['com_perdido'] for a in _agg_f.values())
    # Comisión del asesor: visible para admin/root o cuando el ejecutivo ve SU panel
    # (no la de un compañero).
    _show_com = _es_admin or (not _viewing_other)

    # ── Ranking del equipo (ordenado + filtrado por rol) — se usa para la
    # posición en el hero y para la sección de más abajo (se calcula una vez) ──
    _agg_team = _agregar(_rows, period_days=_days)
    _team = sorted(_agg_team.values(), key=lambda a: (a['ganado'], a['generado']), reverse=True)
    if not _es_admin:
        _team = [a for a in _team
                 if a.get('email') and _umap.get(a['email'], {}).get('rol', 'ejecutivo') == 'ejecutivo']
    _pos_idx = None
    if _scope is not None:
        for _i, _a in enumerate(_team):
            if _a.get('email') == _scope:
                _pos_idx = _i
                break

    # ── HERO: identidad del objetivo (yo / equipo / ejecutivo seleccionado) ──
    if _viewing_other:
        _u_sel = _umap.get((_sel_email or '').lower(), {})
        _disp_nombre = _u_sel.get('nombre') or _sel_nombre or _sel_email or 'Ejecutivo'
        _disp_foto = _u_sel.get('foto_url', '')
        _disp_rol = _u_sel.get('rol', 'ejecutivo')
        _rol_lbl = 'Administrador' if _disp_rol in ('root', 'admin') else 'Ejecutivo de ventas'
        _scope_desc = 'Perfil del ejecutivo'
    else:
        _disp_nombre = _nombre_sesion
        _disp_foto = _umap.get(_email, {}).get('foto_url', '')
        _rol_lbl = 'Administrador' if _es_admin else 'Ejecutivo de ventas'
        _scope_desc = 'Equipo completo' if _es_admin else 'Tu desempe&#241;o'

    _photo_html = (
        f'<img class="rk-photo" src="{_disp_foto}" data-zurl="{_disp_foto}" data-zname="{_disp_nombre}" alt="">'
        if _disp_foto else
        f'<div class="rk-photo rk-photo-ph">{(_disp_nombre or "?")[0].upper()}</div>'
    )

    # ── Badge de posición (lugar en el ranking) ──
    if _pos_idx is not None:
        _pn = _pos_idx + 1
        _ord = {1: '1er', 2: '2do', 3: '3er'}.get(_pn, f'{_pn}&#186;')
        _mcol = {1: '#facc15', 2: '#cbd5e1', 3: '#cd7f32'}.get(_pn, '#94a3b8')
        _pos_html = (
            f'<div class="rk-hero-pos">{_svg_ic("medal", 30, color=_mcol)}'
            f'<div><div class="rk-hero-pos-num">{_ord} lugar</div>'
            f'<div class="rk-hero-pos-lbl">de {len(_team)} en el equipo</div></div></div>'
        )
    else:
        _pos_html = (
            f'<div class="rk-hero-pos">{_svg_ic("users", 26, color="#a5b4fc")}'
            f'<div><div class="rk-hero-pos-num">{len(_team)}</div>'
            f'<div class="rk-hero-pos-lbl">ejecutivos en competencia</div></div></div>'
        )

    # ── Mensaje motivacional (ventas del mes calendario + presión de cierre) ──
    _vm = _ventas_este_mes(_rows, only_email=_scope)
    _dias_rest = _dias_restantes_mes()
    _vtxt = f"{_vm} venta" + ("" if _vm == 1 else "s")
    if _viewing_other:
        _suj = (_disp_nombre or 'Ejecutivo').split()[0].title() + " lleva"
    elif _es_admin:
        _suj = "el equipo lleva"
    else:
        _suj = "llevas"
    if _dias_rest <= 10:
        _msg_txt = (f"Quedan {_dias_rest} d&#237;a{'s' if _dias_rest != 1 else ''} para fin de mes "
                    f"y {_suj} {_vtxt} este mes")
    else:
        _msg_txt = f"Este mes {_suj} {_vtxt}"
    if _dias_rest <= 10 and _vm == 0:
        _msg_icon, _msg_cls = _svg_ic('flame', 16, color='#fb923c'), 'alerta'
    elif _vm == 0:
        _msg_icon, _msg_cls = _svg_ic('alert', 16, color='#fbbf24'), 'alerta'
    else:
        _msg_icon, _msg_cls = _svg_ic('trophy', 16, color='#4ade80'), 'ok'

    # ── 3 cards de dinero en estilo glass, dentro del hero ──
    def _gc(accent, ickey, label, val, sub, com_lbl, com_val):
        _com = (f'<div class="rk-gc-com"><span>{com_lbl}</span>'
                f'<span style="color:{accent};">{com_val}</span></div>') if _show_com else ''
        return (f'<div class="rk-gcard">'
                f'<div class="rk-gc-lbl">{_svg_ic(ickey, 13, color=accent, mr=5)}{label}</div>'
                f'<div class="rk-gc-val" style="color:{accent};">{val}</div>'
                f'<div class="rk-gc-sub">{sub}</div>{_com}</div>')
    _gc_html = (
        _gc('#4ade80', 'dollar', 'Ganado', _fmt_money(_ganado),
            f'{_n_gan} adjudicado{"s" if _n_gan!=1 else ""} / terminado{"s" if _n_gan!=1 else ""}',
            'Comisi&#243;n ganada', _money_exacto(_com_g))
        + _gc('#fbbf24', 'clock', 'Casi ganado', _fmt_money(_casi),
              f'{_n_casi} en proceso', 'Comisi&#243;n en juego', _money_exacto(_com_c))
        + _gc('#f87171', 'trenddown', 'Perdido',
              f'{("-" if _perdido>0 else "")}{_fmt_money(_perdido)}',
              f'{_n_perd} rechazado{"s" if _n_perd!=1 else ""}',
              'Comisi&#243;n perdida', f'{("-" if _com_p>0 else "")}{_money_exacto(_com_p)}')
    )

    st.markdown(
        f'<div class="rk-hero">'
        f'<div class="rk-hero-left">'
        f'<div class="rk-hero-top">'
        f'<div style="min-width:0;">'
        f'<div class="rk-hero-name">{_disp_nombre}</div>'
        f'<div class="rk-hero-role">{_rol_lbl}</div>'
        f'<div class="rk-hero-sub">{_scope_desc} &middot; {_periodo.lower()}'
        f' &middot; {_n_total} presupuesto{"s" if _n_total!=1 else ""}</div>'
        f'</div>'
        f'{_pos_html}'
        f'</div>'
        f'<div class="rk-hero-msg {_msg_cls}">{_msg_icon}<span>{_msg_txt}</span></div>'
        f'<div class="rk-hero-money">{_gc_html}</div>'
        f'</div>'
        f'{_photo_html}'
        f'</div>',
        unsafe_allow_html=True)
    if _disp_foto:
        components.html(_LIGHTBOX_JS, height=0)

    # ── Estadísticas: periodo (izq) + tipo de gráfico (der) en la misma fila ──
    st.markdown(f'<div class="rk-sec">{_svg_ic("chart", 18)}Estad&#237;sticas</div>', unsafe_allow_html=True)
    _fcol_p, _fcol_t = st.columns([1.5, 1], vertical_alignment="center")
    with _fcol_p:
        st.segmented_control(
            "Periodo", list(_PERIODOS.keys()), default='Mes', key='rk_periodo',
            label_visibility='collapsed',
        )
    with _fcol_t:
        _tipo = st.segmented_control(
            "Tipo de gráfico", ['Barras', 'Circular', 'Ondas'], default='Barras',
            key='rk_chart', label_visibility='collapsed',
        ) or 'Barras'

    _comp_lbls = ['Ganado', 'Casi ganado', 'Perdido']
    _comp_vals = [float(_ganado), float(_casi), abs(float(_perdido))]
    _comp_cols = ['#16a34a', '#f59e0b', '#dc2626']
    _tasa = (100.0 * _n_gan / _n_total) if _n_total else 0.0

    with st.container(border=True):
        if not _n_total:
            st.info("No hay presupuestos en este periodo para graficar.")
        elif _tipo == 'Circular':
            st.caption("Composici&#243;n del dinero por estado &#8212; **ganado vs casi ganado vs perdido**. Centro: efectividad (ganados sobre total).")
            _fig = go.Figure(go.Pie(
                labels=_comp_lbls, values=_comp_vals, hole=0.62, sort=False,
                marker=dict(colors=_comp_cols, line=dict(color='#ffffff', width=2)),
                textinfo='label+percent', textfont=dict(size=12, family='Montserrat'),
                hovertemplate='<b>%{label}</b><br>%{value:$,.0f}<br>%{percent}<extra></extra>',
            ))
            _fig.update_layout(
                height=330, margin=dict(t=18, b=18, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)', showlegend=False,
                annotations=[dict(
                    text=f'<b style="font-size:26px">{_tasa:.0f}%</b><br><span style="font-size:11px;color:#64748b">efectividad</span>',
                    x=0.5, y=0.5, font=dict(family='Montserrat', color='#0f172a'), showarrow=False)],
            )
            st.plotly_chart(_fig, use_container_width=True, config={'displayModeBar': False})
        else:  # Barras u Ondas — serie temporal por fecha del presupuesto
            _serie, _gran = _serie_temporal(_rows, period_days=_days, only_email=_scope)
            _gword = {'dia': 'día', 'semana': 'semana', 'mes': 'mes'}[_gran]
            _show_asesor = (_scope is None)
            st.caption(
                f"Presupuestos creados por **{_gword}**. Pasa el cursor para ver el detalle "
                f"(N° EP, cliente{' y asesor' if _show_asesor else ''}) y **haz clic en una barra "
                f"para fijarlo**.")
            _xs = [b['label'] for b in _serie]
            _ys = [b['n'] for b in _serie]
            _txt = [str(v) if v else '' for v in _ys]
            _ang = -45 if (_gran in ('dia', 'semana') and len(_xs) > 8) else 0
            if _tipo == 'Ondas':
                _fig = go.Figure(go.Scatter(
                    x=_xs, y=_ys, mode='lines+markers+text',
                    line=dict(color='#6366f1', width=3, shape='spline'),
                    marker=dict(size=9, color='#6366f1', line=dict(color='#fff', width=1.5)),
                    fill='tozeroy', fillcolor='rgba(99,102,241,0.16)',
                    text=_txt, textposition='top center',
                    textfont=dict(size=11, family='Montserrat', color='#1e293b'),
                    hoverinfo='none',
                ))
            else:  # Barras
                _fig = go.Figure(go.Bar(
                    x=_xs, y=_ys, marker_color='#6366f1',
                    text=_txt, textposition='outside',
                    textfont=dict(size=12, family='Montserrat', color='#1e293b'),
                    hoverinfo='none',
                ))
            _fig.update_layout(
                height=330, margin=dict(t=28, b=10, l=10, r=10),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, tickangle=_ang, tickfont=dict(size=11, family='Montserrat')),
                yaxis=dict(visible=False, range=[0, max(_ys + [1]) * 1.25]),
                showlegend=False, hovermode='closest',
            )
            st.plotly_chart(_fig, use_container_width=True,
                            config={'displayModeBar': False, 'doubleClick': False})
            # Overlay: cabecera (fecha · total) + burbujas (foto+badge por asesor)
            # + lista de presupuestos. Hover muestra/colorea; clic fija + naranjo.
            _ttd = []
            for b in _serie:
                _ca, _cn = {}, {}
                for it in b['items']:
                    em = it['asesor_email']
                    _ca[em] = _ca.get(em, 0) + 1
                    _cn[em] = it['asesor']
                _ases = [{'photo': _umap.get(em, {}).get('foto_url', ''),
                          'ini': (_cn.get(em) or '?')[0].upper(),
                          'name': _cn.get(em, ''),
                          'count': cnt}
                         for em, cnt in sorted(_ca.items(), key=lambda kv: -kv[1])]
                _items = [{'num': it['numero'], 'cli': it['cliente'], 'ase': it['asesor']}
                          for it in b['items']]
                _ttd.append({'date': b['fecha_full'], 'total': b['n'],
                             'showAse': _show_asesor, 'asesores': _ases, 'items': _items})
            components.html(_FACE_TIP_JS.replace('__DATA__', json.dumps(_ttd)), height=0)

    # ── Desglose por estado (cantidad de presupuestos en cada estado) ──
    st.markdown(f'<div class="rk-sec">{_svg_ic("list", 18)}Presupuestos por estado</div>', unsafe_allow_html=True)
    st.caption(
        "Cada presupuesto se cuenta **una sola vez** por su estado actual. La comisi&#243;n se gana al "
        "**adjudicar**; si despu&#233;s pasa a **terminado** es el mismo proyecto ya construido (no suma de "
        "nuevo). Un presupuesto que queda **rechazado** = el cliente desisti&#243;, comisi&#243;n perdida. "
        "Lo que a&#250;n no llega a adjudicado ni rechazado est&#225; en **casi ganado**.")
    _desg = _desglose_estados(_rows, period_days=_days, only_email=_scope)
    _lista = _listar_presupuestos(_rows, period_days=_days, only_email=_scope)
    _dcols = st.columns(3)
    for _ci, _bk in enumerate(['ganado', 'casi', 'perdido']):
        _bcol, _blbl, _bic, _blight = _BUCKET_META[_bk]
        _items = [(disp, _desg.get(code, {'n': 0, 'monto': 0.0}))
                  for (bk, code, disp) in _ESTADOS_ORDEN if bk == _bk]
        _tot_n = sum(it[1]['n'] for it in _items)
        _tot_m = sum(it[1]['monto'] for it in _items)
        _items_html = ''.join(
            f'<div class="rk-est-item">'
            f'<span class="rk-est-dot" style="background:{_blight};"></span>'
            f'<span class="rk-est-name">{disp}</span>'
            f'<span class="rk-est-n">{e["n"]}</span>'
            f'<span class="rk-est-m">{_fmt_money(-abs(e["monto"]) if _bk == "perdido" else e["monto"])}</span>'
            f'</div>'
            for disp, e in _items if e['n'] > 0)
        if not _items_html:
            _items_html = '<div class="rk-est-empty">Sin presupuestos</div>'
        _tot_m_disp = _fmt_money(-abs(_tot_m)) if (_bk == 'perdido' and _tot_m) else _fmt_money(_tot_m)
        # Comisión del ejecutivo para este bucket (mismo scope/periodo que el desglose)
        _com_bk = {'ganado': _com_g, 'casi': _com_c, 'perdido': _com_p}[_bk]
        _com_bk_lbl = {'ganado': 'Comisi&#243;n ganada', 'casi': 'Comisi&#243;n en juego',
                       'perdido': 'Comisi&#243;n perdida'}[_bk]
        _com_bk_disp = (f'-{_money_exacto(_com_bk)}' if (_bk == 'perdido' and _com_bk) else _money_exacto(_com_bk))
        _com_row = (f'<div class="rk-est-com"><span>{_com_bk_lbl}</span>'
                    f'<span style="color:{_blight};">{_com_bk_disp}</span></div>') if _show_com else ''
        with _dcols[_ci]:
            st.markdown(
                f'<div class="rk-est-group" style="border-top:3px solid {_blight};">'
                f'<div class="rk-est-head" style="color:{_blight};">{_svg_ic(_bic, 15, color=_blight)}{_blbl}'
                f'<span class="rk-est-badge" style="background:{_bcol};">{_tot_n}</span></div>'
                f'<div class="rk-est-tot" style="color:{_blight};">{_tot_m_disp}</div>'
                f'{_items_html}'
                f'{_com_row}'
                f'</div>', unsafe_allow_html=True)
            # Popover "Ver": lista de presupuestos del bucket (N° EP, cliente, monto)
            _bk_items = [p for p in _lista if p['bucket'] == _bk]
            _neg = (_bk == 'perdido')
            with st.popover(f"Ver {_tot_n} presupuesto{'s' if _tot_n != 1 else ''}",
                            use_container_width=True, disabled=(_tot_n == 0)):
                def _pp_row(p, col=_bcol, neg=_neg, adm=(_scope is None)):
                    _cli = p["cliente"] + (f' &middot; {p["asesor"]}' if adm else '')
                    _mt = ('-' if neg else '') + _money_exacto(p["monto"])
                    return (f'<div class="rk-pp-row">'
                            f'<span class="rk-pp-tag" style="background:{col};">{p["estado"]}</span>'
                            f'<div class="rk-pp-mid"><div class="rk-pp-num">{p["numero"]}</div>'
                            f'<div class="rk-pp-cli">{_cli}</div></div>'
                            f'<div class="rk-pp-m" style="color:{col};">{_mt}</div>'
                            f'</div>')
                st.markdown(
                    f'<div style="font-weight:800;color:{_bcol};font-size:0.92rem;margin-bottom:6px;">'
                    f'{_svg_ic(_bic, 14, color=_bcol, mr=6)}{_blbl} &middot; {_tot_n} &middot; {_tot_m_disp}</div>'
                    f'<div class="rk-pp-wrap">{"".join(_pp_row(p) for p in _bk_items)}</div>',
                    unsafe_allow_html=True)

    # ── Ranking del equipo ── (_team ya calculado arriba: ordenado + filtrado por rol)
    st.markdown(f'<div class="rk-sec">{_svg_ic("trophy", 18)}Ranking del equipo</div>', unsafe_allow_html=True)
    if not _team:
        st.info("No hay presupuestos en este periodo.")
    else:
        st.caption("Haz clic en **Ver** para cargar arriba el panel completo de ese ejecutivo.")
        _medallas = {1: _svg_ic('medal', 23, color='#facc15'),   # oro
                     2: _svg_ic('medal', 23, color='#94a3b8'),   # plata
                     3: _svg_ic('medal', 23, color='#cd7f32')}   # bronce
        for i, a in enumerate(_team, 1):
            _u = _umap.get(a['email'], {})
            _f = _u.get('foto_url', '')
            _ini = (a['nombre'] or '?')[0].upper()
            _av = (f'<img class="rk-rav" src="{_f}" alt="">' if _f
                   else f'<div class="rk-rav rk-rav-ph">{_ini}</div>')
            _pos = _medallas.get(i, f'<span style="color:rgba(255,255,255,0.55);">{i}</span>')
            _is_me = (a['email'] == _email and not _es_admin)
            _is_sel = _viewing_other and (a['email'] == _sel_email) and (a['nombre'] == (_sel_nombre or a['nombre']))
            _row_cls = ' sel' if _is_sel else (' me' if _is_me else '')
            if _is_sel:
                _badge = ' &middot; <span style="color:#a5b4fc;font-size:0.7rem;font-weight:800;">VIENDO</span>'
            elif _is_me:
                _badge = ' &middot; <span style="color:#a5b4fc;font-size:0.7rem;font-weight:800;">T&#218;</span>'
            else:
                _badge = ''
            _c_card, _c_btn = st.columns([8.5, 1.5], vertical_alignment="center")
            with _c_card:
                st.markdown(
                    f'<div class="rk-card{_row_cls}">'
                    f'<div class="rk-pos">{_pos}</div>'
                    f'{_av}'
                    f'<div style="flex:1;min-width:0;">'
                    f'<div style="font-weight:800;color:#fff;font-size:0.98rem;">{a["nombre"]}{_badge}</div>'
                    f'<div style="font-size:0.74rem;color:rgba(255,255,255,0.55);margin-top:2px;">{a["n_total"]} presupuesto{"s" if a["n_total"]!=1 else ""}</div>'
                    f'</div>'
                    f'<div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap;justify-content:flex-end;">'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:900;color:#4ade80;font-size:1.05rem;">{_fmt_money(a["ganado"])}</div><div style="font-size:0.64rem;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.05em;">Ganado</div></div>'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#fbbf24;font-size:0.95rem;">{_fmt_money(a["casi"])}</div><div style="font-size:0.64rem;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.05em;">Casi</div></div>'
                    f'<div style="text-align:right;"><div style="font-family:Montserrat;font-weight:800;color:#f87171;font-size:0.95rem;">{("-" if a["perdido"]>0 else "")}{_fmt_money(a["perdido"])}</div><div style="font-size:0.64rem;color:rgba(255,255,255,0.5);text-transform:uppercase;letter-spacing:0.05em;">Perdido</div></div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True)
            with _c_btn:
                if st.button("Ver", icon=":material/visibility:", key=f"rk_ver_{i}",
                             use_container_width=True, disabled=_is_sel,
                             help="Cargar arriba el panel de este ejecutivo"):
                    st.session_state['rk_perfil_email'] = a['email']
                    st.session_state['rk_perfil_nombre'] = a['nombre']
                    st.rerun()
