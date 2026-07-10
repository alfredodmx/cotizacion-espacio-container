"""
Tab COTIZACIONES — Gestión de cotizaciones, búsqueda, filtrado, selección y PDFs.
Migrado desde app.py líneas 10798-12671.
"""
import re
import json
import pandas as pd
import requests
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from views.layout import render_page_header

from repositories.cotizaciones_repo import (
    buscar_cotizaciones, cargar_cotizacion, guardar_cotizacion, generar_numero_unico
)
from repositories.logs_repo import obtener_logs_ep
from repositories.compras_repo import calcular_estado_compras
from services.cotizacion_service import crear_badge_estado, aplicar_margen, calcular_estado_label
from generators.pdf_cotizacion import generar_pdf_completo, generar_pdf_cliente
from generators.pdf_log import generar_pdf_log
from generators.pdf_seleccion import generar_pdf_seleccion_cliente
from utils.formato import formato_clp
from utils.telefono import formatear_telefono
from utils.avatars import fetch_foto_map, avatar_html
from utils.formulario import fetch_catalogo_materiales
from config.settings import SUPABASE_URL
from config.supabase import supabase_admin as _supa_admin_global


# ── Iconos SVG inline (reemplazan emoticones en la tabla de resultados) ──────────
_HIC_PATHS = {
    "check":    '<path d="M20 6 9 17l-5-5"/>',
    "copy":     '<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
    "eye":      '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "cart":     '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "clipboard":'<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "alert":    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
    "clock":    '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    "calendar": '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "flag":     '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
    "file":     '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
    "user":     '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "folder":   '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "image":    '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>',
}


def _hic(name, color="#0f172a", size=14, mr=6, valign=-2, sw=2):
    """SVG inline para celdas de la tabla (reemplaza emoticones). mr = margin-right px."""
    inner = _HIC_PATHS.get(name, "")
    _m = f'margin-right:{mr}px;' if mr else ''
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="vertical-align:{valign}px;{_m}flex-shrink:0;">'
        f'{inner}</svg>'
    )


# Visor PDF.js del drawer de documentos: renderiza __SRC__ (URL del plano o data-URL
# base64 de un PDF generado) a canvas — cross-browser, ver [[project_pdf_viewer_pdfjs]].
_PV_VIEWER = """<style>
*{box-sizing:border-box;}
@keyframes spin{from{transform:rotate(0)}to{transform:rotate(360deg)}}
html,body{margin:0;padding:0;height:100%;overflow:hidden;font-family:sans-serif;background:#525659;}
#pdf-wrap{position:absolute;inset:0;overflow:auto;-webkit-overflow-scrolling:touch;}
#pdf-pages{padding:16px;display:flex;flex-direction:column;align-items:center;gap:14px;min-width:min-content;}
#pdf-pages canvas{display:block;box-shadow:0 3px 12px rgba(0,0,0,.45);background:#fff;}
#pdf-loading{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f0f2f5;z-index:5;gap:12px;transition:opacity .35s;}
#pdf-spinner{width:38px;height:38px;border:4px solid #cbd5e1;border-top-color:#5b7cfa;border-radius:50%;animation:spin .8s linear infinite;}
#pdf-loading span{color:#64748b;font-size:.88rem;padding:0 16px;text-align:center;}
#zoombar{position:absolute;bottom:16px;left:50%;transform:translateX(-50%);z-index:6;display:flex;align-items:center;gap:2px;background:rgba(15,23,42,.92);border-radius:99px;padding:5px 7px;box-shadow:0 6px 20px rgba(0,0,0,.45);}
.zb{width:32px;height:32px;border-radius:50%;border:none;background:transparent;color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;}
.zb:hover{background:rgba(255,255,255,.16);}
.zb svg{width:17px;height:17px;}
#zlbl{color:#fff;font-size:12px;font-weight:600;min-width:46px;text-align:center;}
</style>
<div id="pdf-wrap"><div id="pdf-pages"></div></div>
<div id="pdf-loading"><div id="pdf-spinner"></div><span id="pdf-status">Cargando documento...</span></div>
<div id="zoombar">
  <button class="zb" id="zout" title="Alejar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
  <span id="zlbl">100%</span>
  <button class="zb" id="zin" title="Acercar"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button>
  <button class="zb" id="zfit" title="Ajustar al ancho"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3 4 7l4 4"/><path d="M4 7h16"/><path d="m16 21 4-4-4-4"/><path d="M20 17H4"/></svg></button>
</div>
<script>
(function(){
  var SRC=__SRC__, pdfDoc=null, zoom=1, rendering=false, fitScale=1;
  var wrap=document.getElementById('pdf-wrap'), pagesEl=document.getElementById('pdf-pages');
  var loading=document.getElementById('pdf-loading'), statusEl=document.getElementById('pdf-status'), zlbl=document.getElementById('zlbl');
  function hide(){loading.style.opacity='0';setTimeout(function(){loading.style.display='none';},350);}
  function render(){
    if(!pdfDoc||rendering) return; rendering=true;
    var scale=fitScale*zoom; pagesEl.innerHTML='';
    var seq=Promise.resolve(), first=true;
    for(var i=1;i<=pdfDoc.numPages;i++){(function(n){
      seq=seq.then(function(){return pdfDoc.getPage(n).then(function(page){
        var vp=page.getViewport({scale:scale});
        var c=document.createElement('canvas');var ctx=c.getContext('2d');
        c.width=vp.width;c.height=vp.height;pagesEl.appendChild(c);
        return page.render({canvasContext:ctx,viewport:vp}).promise.then(function(){if(first){first=false;hide();}});
      });});
    })(i);}
    seq.then(function(){rendering=false;});
  }
  function computeFit(){
    if(!pdfDoc) return Promise.resolve();
    return pdfDoc.getPage(1).then(function(p){
      var vp1=p.getViewport({scale:1});
      fitScale=Math.max(0.2,(wrap.clientWidth-34)/vp1.width);
    });
  }
  function setZoom(z){ zoom=Math.min(4,Math.max(0.4,z)); zlbl.textContent=Math.round(zoom*100)+'%'; render(); }
  document.getElementById('zin').onclick=function(){setZoom(zoom*1.25);};
  document.getElementById('zout').onclick=function(){setZoom(zoom*0.8);};
  document.getElementById('zfit').onclick=function(){zoom=1;zlbl.textContent='100%';computeFit().then(render);};
  var rt;
  window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(function(){if(zoom===1)computeFit().then(render);},220);});
  function start(){
    if(typeof pdfjsLib==='undefined'){statusEl.textContent='No se pudo cargar el visor.';return;}
    pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    var task;
    if(typeof SRC==='string'&&SRC.indexOf('data:')===0){
      var b64=SRC.substring(SRC.indexOf(',')+1),bin=atob(b64),n=bin.length,arr=new Uint8Array(n);
      for(var i=0;i<n;i++)arr[i]=bin.charCodeAt(i);
      task=pdfjsLib.getDocument({data:arr});
    } else { task=pdfjsLib.getDocument({url:SRC,withCredentials:false}); }
    task.promise.then(function(pdf){pdfDoc=pdf;return computeFit();}).then(render).catch(function(e){statusEl.textContent='No se pudo mostrar el documento.';});
  }
  window._ecPvBoot=start;
})();
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js" onload="_ecPvBoot()" onerror="var s=document.getElementById('pdf-status');if(s)s.textContent='No se pudo cargar el visor.';"></script>
"""


# ── Wrappers cacheados (evitan trabajo pesado en cada rerun, p.ej. al filtrar) ──
@st.cache_data(ttl=60, show_spinner=False)
def _money_cards_global() -> tuple:
    """Agrega el dinero de TODAS las cotizaciones del sistema por bucket
    (ganado/casi/perdido). Independiente del término/filtro de búsqueda: las cards
    muestran SIEMPRE el total histórico. Devuelve (mg, mc, mp, cg, cc, cp).
    Índices del tuple de buscar_cotizaciones: 1 cliente, 2 asesor, 4 total,
    5 margen, 7 email, 8 asesor_email, 9 asesor_tel, 10 plano, 15 notariado,
    19 motivo_rechazo, 21 acta_url."""
    rows = buscar_cotizaciones()
    mg = mc = mp = 0.0
    cg = cc = cp = 0
    for r in rows or []:
        try:
            _lbl = calcular_estado_label(
                r[1], r[7], r[2], r[8], r[9],
                float(r[5] or 0), bool(r[10]),
                tiene_notariado=bool(r[15]) if len(r) > 15 else False,
                tiene_acta=bool(r[21]) if len(r) > 21 else False,
                motivo_rechazo=r[19] if len(r) > 19 else '')
            _tot = float(r[4] or 0)
        except Exception:
            continue
        if _lbl in ('PROYECTO TERMINADO', 'ADJUDICADO'):
            mg += _tot; cg += 1
        elif _lbl == 'RECHAZADO':
            mp += _tot; cp += 1
        else:
            mc += _tot; cc += 1
    return (mg, mc, mp, cg, cc, cp)


@st.cache_data(ttl=60, show_spinner=False)
def _lista_ejecutivos() -> list:
    """Nombres únicos de ejecutivos (asesor_nombre) presentes en las cotizaciones,
    para el dropdown de filtrado rápido."""
    rows = buscar_cotizaciones()
    return sorted({(r[2] or '').strip() for r in (rows or []) if (r[2] or '').strip()})


@st.cache_data(ttl=30, show_spinner=False)
def _pdf_log_cached(ep: str, n_logs: int) -> bytes:
    """PDF del historial cacheado por EP y nº de logs (regenera si cambian los logs)."""
    return generar_pdf_log(ep, obtener_logs_ep(ep))


@st.cache_data(ttl=20, show_spinner=False)
def _rechazo_status_cached(ep: str) -> dict:
    """Estado de rechazo/adjudicación cacheado por EP. Limpiar al rechazar/quitar."""
    try:
        _q = _supa_admin_global.table("cotizaciones").select(
            "motivo_rechazo,fecha_rechazo,contrato_notariado_url"
        ).eq("numero", ep).execute()
        return _q.data[0] if _q.data else {}
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_plano_bytes(url: str):
    """Descarga los bytes del plano desde su URL (cacheado 5min por URL) para el
    botón DESCARGAR PLANO. Devuelve None si falla."""
    try:
        r = requests.get(url, timeout=20)
        return r.content if r.ok else None
    except Exception:
        return None


@st.cache_data(ttl=60, show_spinner=False)
def _modelos_predefinidos(eps: tuple) -> dict:
    """Mapa {numero: modelo_predefinido} cacheado 60s por set de EPs (completo)."""
    if not eps:
        return {}
    try:
        _q = _supa_admin_global.table("cotizaciones").select(
            "numero,modelo_predefinido"
        ).in_("numero", list(eps)).execute()
        return {str(_r.get("numero", "")): (_r.get("modelo_predefinido") or "")
                for _r in (_q.data or [])}
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def _eps_con_seleccion(eps: tuple) -> set:
    """EPs (de las mostradas) que tienen al menos una respuesta del formulario del
    cliente → habilita 'PDF selección' en el menú contextual sin consultar por fila."""
    if not eps:
        return set()
    try:
        _r = _supa_admin_global.table('formulario_respuestas').select(
            'cotizacion_numero').in_('cotizacion_numero', list(eps)).execute().data or []
        return {str(x.get('cotizacion_numero')) for x in _r if x.get('cotizacion_numero')}
    except Exception:
        return set()


def _feriados_chile(year):
    from datetime import date, timedelta as _td
    f = set()
    for mes, dia in [(1,1),(5,1),(9,18),(9,19),(10,12),(11,1),(12,8),(12,25)]:
        f.add(date(year, mes, dia))
    a=year%19; b=year//100; c=year%100; d=b//4; e=b%4
    g=(8*b+13)//25; h=(19*a+b-d-g+15)%30; i=c//4; k=c%4
    l=(32+2*e+2*i-h-k)%7; m=(a+11*h+19*l)//433
    n=(h+l-7*m+90)//25; p=(h+l-7*m+33*n+19)%32
    pascua=date(year,n,p)
    f.add(pascua-_td(days=2)); f.add(pascua-_td(days=1))
    if year>=2021: f.add(date(year,6,20))
    f.add(date(year,5,1))
    base=date(year,6,29)
    if base.weekday()==1: f.add(base-_td(1))
    else: f.add(base)
    f.add(date(year,8,15))
    if date(year,9,18).weekday()==4: f.add(date(year,9,19))
    f.add(date(year,10,31))
    return f


def sumar_dias_habiles(fecha_inicio, dias_habiles):
    from datetime import timedelta as _td
    yn=set(); d=fecha_inicio; yn.add(d.year)
    fer=_feriados_chile(d.year)|_feriados_chile(d.year+1)
    count=0
    while count<dias_habiles:
        d+=_td(days=1)
        if d.year not in yn: yn.add(d.year); fer|=_feriados_chile(d.year)
        if d.weekday()<5 and d not in fer: count+=1
    return d


def dias_habiles_entre(fecha_inicio, fecha_fin):
    from datetime import timedelta as _td
    if fecha_fin<=fecha_inicio: return 0
    fer=_feriados_chile(fecha_inicio.year)
    if fecha_fin.year!=fecha_inicio.year: fer|=_feriados_chile(fecha_fin.year)
    count=0; d=fecha_inicio
    while d<fecha_fin:
        d+=_td(days=1)
        if d.weekday()<5 and d not in fer: count+=1
    return count


def detectar_navegador():
    try:
        ua=st.context.headers.get('User-Agent','')
        ec='Chrome' in ua and 'Edg' not in ua; ee='Edg' in ua
        es='Safari' in ua and 'Chrome' not in ua
        return {'es_chrome':ec,'es_edge':ee,'es_safari':es,'es_firefox':'Firefox' in ua,
                'needs_google_viewer':ec or ee or es}
    except: return {'needs_google_viewer':True}


def preparar_carga_cotizacion(numero_cotizacion):
    cot=cargar_cotizacion(numero_cotizacion)
    if cot:
        if cot.get('config_margen',0)>0 and not st.session_state.get('modo_admin',False):
            return False
        st.session_state.cotizacion_a_cargar=cot
        st.session_state.cargar_cotizacion_trigger=True
        return True
    return False


def _fetch_formulario_config(ep):
    try:
        return _supa_admin_global.table('formulario_config').select('*')\
            .eq('cotizacion_numero',ep).execute().data or []
    except: return []


def cargar_descripciones_por_ep(numero, supa_url, bust_cache=False):
    try:
        import time as _t
        url=f'{supa_url.rstrip("/")}/storage/v1/object/public/config/pdf_desc_{numero}.json'
        if bust_cache: url+=f'?t={int(_t.time())}'
        r=requests.get(url,timeout=5,headers={'Cache-Control':'no-cache'})
        if r.status_code==200: return r.json()
    except: pass
    return {}


def _construir_datos_guardar_simple():
    ft=formatear_telefono(st.session_state.get('telefono_raw','') or '')
    dc={'Nombre':st.session_state.get('nombre_input',''),'RUT':st.session_state.get('rut_display',''),
        'Correo':st.session_state.get('correo_input',''),'Teléfono':ft,
        'Dirección':st.session_state.get('direccion_input',''),
        'ComunaCliente':st.session_state.get('cliente_comuna',''),
        'RegionCliente':st.session_state.get('cliente_region',''),
        'DireccionProyecto':st.session_state.get('proyecto_direccion',''),
        'ComunaProyecto':st.session_state.get('proyecto_comuna',''),
        'RegionProyecto':st.session_state.get('proyecto_region',''),
        'TipoCliente':st.session_state.get('cliente_tipo','natural'),
        'EmpresaCliente':st.session_state.get('cliente_empresa',''),
        'RutEmpresa':st.session_state.get('cliente_rut_empresa',''),
        'Observaciones':st.session_state.get('observaciones_input','')}
    nom=st.session_state.get('asesor_seleccionado','')
    if nom=='Seleccionar asesor': nom=''
    da={'Nombre Ejecutivo':nom,'Correo Ejecutivo':st.session_state.get('correo_asesor',''),
        'Teléfono Ejecutivo':st.session_state.get('telefono_asesor','')}
    fi=st.session_state.get('fecha_inicio',datetime.now().date())
    ft2=st.session_state.get('fecha_termino',(datetime.now()+timedelta(days=15)).date())
    proy={'fecha_inicio':str(fi),'fecha_termino':str(ft2),'dias_validez':(ft2-fi).days,
          'observaciones':st.session_state.get('observaciones_input','')}
    cfg={'margen':st.session_state.get('margen',0),'modo_admin':st.session_state.get('modo_admin',False)}
    carrito=st.session_state.get('carrito',[])
    if carrito:
        df_c=pd.DataFrame(carrito); sb=df_c['Subtotal'].sum()
        mg=st.session_state.get('margen',0)
        sc=sum(i['Cantidad']*aplicar_margen(i['Precio Unitario'],mg) for i in carrito) if (st.session_state.get('modo_admin') or mg>0) else sb
        iva=sc*0.19; tot=sc+iva
    else:
        sb=sc=iva=tot=0
    tots={'subtotal_sin_margen':sb,'subtotal_con_margen':sc,'iva':iva,'total':tot}
    pn=st.session_state.get('plano_nombre') if st.session_state.get('plano_adjunto') else None
    pd2=st.session_state.get('plano_adjunto') if st.session_state.get('plano_adjunto') else None
    return dc,da,proy,cfg,tots,pn,pd2


# ── View principal ────────────────────────────────────────────────────────────

def render_tab_historial(supabase, supabase_admin, supa_url, supa_key, **deps):
    _rol_actual = st.session_state.get('rol_usuario', 'ejecutivo')

    st.markdown("""
    <style>
    .hdr3 { background:linear-gradient(135deg,#6b4e00 0%,#e65100 100%);
        border-radius:20px;padding:34px 36px;margin-bottom:28px;
        display:flex;align-items:center;gap:16px;
        box-shadow:0 8px 32px rgba(230,81,0,0.25);position:relative;overflow:hidden; }
    .hdr3::before { content:'';position:absolute;top:-40px;right:-40px;
        width:180px;height:180px;border-radius:50%;
        background:rgba(255,255,255,0.04);pointer-events:none; }
    .hdr3::after { content:'';position:absolute;bottom:-60px;right:80px;
        width:240px;height:240px;border-radius:50%;
        background:rgba(255,255,255,0.03);pointer-events:none; }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "cotizaciones",
        "Gesti&#243;n de Cotizaciones",
        "Busca, carga y administra todas las cotizaciones del sistema.",
    )

    # ── Cards de dinero (Ganado / Casi ganado / Perdido) — estilo RANKING ─────
    # Resumen de la cartera por estado. Se rellenan más abajo con los datos reales
    # (df_resultados); acá sólo se define el helper + un render inicial en cero.
    def _fmt_money_short(v):
        v = float(v or 0); _s = '-' if v < 0 else ''; v = abs(v)
        if v >= 1_000_000: return f"{_s}${v/1_000_000:.1f}M"
        if v >= 1_000:     return f"{_s}${v/1_000:.0f}K"
        return f"{_s}${v:,.0f}"

    _CARD_ICON_PATHS = {
        'ganado':  "<line x1='12' x2='12' y1='2' y2='22'/><path d='M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'/>",
        'casi':    "<circle cx='12' cy='12' r='10'/><polyline points='12 6 12 12 16 14'/>",
        'perdido': "<polyline points='22 17 13.5 8.5 8.5 13.5 2 7'/><polyline points='16 17 22 17 22 11'/>",
    }
    _CARD_CSS = (
        "<style>"
        ".cot-mcards{display:flex;gap:10px;width:100%;}"
        ".cot-mcard{flex:1;min-width:0;background:#fff;border:1px solid #e6eaf2;"
        "border-left:4px solid var(--acc);border-radius:14px;padding:12px 14px;"
        "box-shadow:0 2px 12px rgba(15,23,42,0.06);display:flex;flex-direction:column;justify-content:center;}"
        ".cot-mc-lbl{display:flex;align-items:center;gap:6px;font-family:Montserrat,sans-serif;"
        "font-weight:800;font-size:0.66rem;letter-spacing:0.05em;text-transform:uppercase;color:var(--acc);white-space:nowrap;}"
        ".cot-mc-lbl svg{flex-shrink:0;}"
        ".cot-mc-val{font-family:'Plus Jakarta Sans',sans-serif;font-weight:800;font-size:1.45rem;"
        "color:#0f172a;line-height:1.05;margin:5px 0 2px;}"
        ".cot-mc-sub{font-size:0.7rem;color:#94a3b8;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}"
        "</style>"
    )

    def _svg_card(key, color):
        return (f"<svg width='13' height='13' viewBox='0 0 24 24' fill='none' stroke='{color}' "
                f"stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'>{_CARD_ICON_PATHS[key]}</svg>")

    def _render_money_cards(slot, gan, casi, perd, ng, nc, nperd):
        _defs = [
            ('#16a34a', 'ganado',  'Ganado',      gan,               f'{ng} adjudicado{"s" if ng!=1 else ""} / terminado{"s" if ng!=1 else ""}'),
            ('#f59e0b', 'casi',    'Casi ganado', casi,              f'{nc} en proceso'),
            ('#dc2626', 'perdido', 'Perdido',     -abs(perd) if perd else 0, f'{nperd} rechazado{"s" if nperd!=1 else ""}'),
        ]
        _cards = ''.join(
            f'<div class="cot-mcard" style="--acc:{_c};">'
            f'<div class="cot-mc-lbl">{_svg_card(_k, _c)}{_lbl}</div>'
            f'<div class="cot-mc-val" style="color:{_c};">{_fmt_money_short(_val)}</div>'
            f'<div class="cot-mc-sub">{_sub}</div></div>'
            for _c, _k, _lbl, _val, _sub in _defs
        )
        slot.markdown(_CARD_CSS + f'<div class="cot-mcards">{_cards}</div>', unsafe_allow_html=True)

    _top_left, _top_right = st.columns([1.15, 1], gap="medium", vertical_alignment="center")
    # Cards SIEMPRE con el total global del sistema (no dependen del filtro/búsqueda).
    _mg, _mc, _mp, _cg, _cc, _cp = _money_cards_global()
    _render_money_cards(_top_right.empty(), _mg, _mc, _mp, _cg, _cc, _cp)

    with _top_left, st.container(border=True):
        # Botones de búsqueda SOLO ícono (texto oculto con font-size:0 + ícono via
        # CSS ::before). El significado de cada botón va en el tooltip (help=).
        def _btn_svg_before(key, svg_path, color="%23475569"):
            return (
                f'.st-key-{key} button{{display:inline-flex!important;align-items:center!important;'
                f'justify-content:center!important;gap:0!important;font-size:0!important;}}'
                f'.st-key-{key} button::before{{content:""!important;flex-shrink:0!important;'
                f'width:17px!important;height:17px!important;'
                f'background:url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' '
                f'width=\'17\' height=\'17\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'{color}\' '
                f'stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E{svg_path}'
                f'%3C/svg%3E") no-repeat center/contain!important;}}'
            )
        _SVG_SEARCH = "%3Ccircle cx=\'11\' cy=\'11\' r=\'8\'/%3E%3Cpath d=\'m21 21-4.3-4.3\'/%3E"
        _SVG_TRASH = "%3Cpath d=\'M3 6h18\'/%3E%3Cpath d=\'M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2\'/%3E"
        _SVG_SUN = "%3Ccircle cx=\'12\' cy=\'12\' r=\'4\'/%3E%3Cpath d=\'M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4\'/%3E"
        _SVG_CAL_WEEK = "%3Crect width=\'18\' height=\'18\' x=\'3\' y=\'4\' rx=\'2\'/%3E%3Cpath d=\'M3 10h18M8 2v4M16 2v4M7 15h.01M11 15h.01M15 15h.01\'/%3E"
        _SVG_CAL = "%3Crect width=\'18\' height=\'18\' x=\'3\' y=\'4\' rx=\'2\'/%3E%3Cpath d=\'M3 10h18M8 2v4M16 2v4\'/%3E"
        st.markdown(
            "<style>"
            + _btn_svg_before("btn_buscar_cot", _SVG_SEARCH, "white")
            + _btn_svg_before("btn_limpiar_cot", _SVG_TRASH)
            + _btn_svg_before("filtro_hoy", _SVG_SUN)
            + _btn_svg_before("filtro_semana", _SVG_CAL_WEEK)
            + _btn_svg_before("filtro_mes", _SVG_CAL)
            # Radio "Buscar por" (N° Presupuesto/Cliente/Asesor): MISMA tipografía
            # que los títulos de módulo de PRESUPUESTO (Montserrat uppercase). Las
            # props de fuente van a todos los descendientes; el color se restringe
            # al texto (label) para no teñir el punto del radio.
            + ".st-key-tipo_busqueda label,.st-key-tipo_busqueda label *{font-family:Montserrat,sans-serif!important;"
            + "font-weight:700!important;font-size:0.82rem!important;letter-spacing:0.04em!important;line-height:1.6!important;"
            + "text-transform:uppercase!important;color:#0f172a!important;-webkit-text-fill-color:#0f172a!important;}"
            + "</style>",
            unsafe_allow_html=True,
        )
        tipo_busqueda = st.radio("Buscar por:", ["N° Presupuesto", "Cliente", "Ejecutivo"],
                                  horizontal=True, key="tipo_busqueda", label_visibility="collapsed")
        tipo_map = {"N° Presupuesto": "numero", "Cliente": "cliente", "Ejecutivo": "asesor"}
        _bc1, _bc2, _bc3, _bc4, _bc5, _bc6 = st.columns([3, 0.7, 0.7, 0.7, 0.7, 0.7])
        with _bc1:
            if tipo_busqueda == "Ejecutivo":
                # Dropdown de ejecutivos: filtra al instante al seleccionar.
                _ejs = _lista_ejecutivos()
                _TODOS_EJ = "Todos los ejecutivos"
                _sel_ej = st.selectbox("Ejecutivo", [_TODOS_EJ] + _ejs,
                                       key="buscar_ejecutivo_sel", label_visibility="collapsed")
                if _sel_ej != st.session_state.get('_prev_ejecutivo_sel'):
                    st.session_state['_prev_ejecutivo_sel'] = _sel_ej
                    st.session_state.filtro_estado_tabla = None
                    st.session_state.mostrar_visor = False
                    with st.spinner("Filtrando..."):
                        st.session_state.resultados_busqueda = (
                            buscar_cotizaciones() if _sel_ej == _TODOS_EJ
                            else buscar_cotizaciones(_sel_ej, "asesor"))
                    st.rerun()
                termino = ""   # en modo ejecutivo el filtro lo maneja el dropdown
            else:
                st.session_state.pop('_prev_ejecutivo_sel', None)
                termino = st.text_input("Término", placeholder="Ingrese término de búsqueda...",
                                         key="buscar_cotizacion", label_visibility="collapsed")
        with _bc2: buscar_btn = st.button(" ", type="primary", use_container_width=True, key="btn_buscar_cot", help="Buscar")
        with _bc3: limpiar_btn = st.button(" ", use_container_width=True, key="btn_limpiar_cot", help="Limpiar")
        with _bc4:
            if st.button(" ", use_container_width=True, key="filtro_hoy", help="Hoy"):
                st.session_state.resultados_busqueda = None; st.rerun()
        with _bc5:
            if st.button(" ", use_container_width=True, key="filtro_semana", help="Esta semana"):
                st.session_state.resultados_busqueda = None; st.rerun()
        with _bc6:
            if st.button(" ", use_container_width=True, key="filtro_mes", help="Este mes"):
                st.session_state.resultados_busqueda = None; st.rerun()

    st.markdown("---")
    st.markdown("### Resultados")

    _qp_sel_ep = st.query_params.get('_sel_ep')
    if _qp_sel_ep:
        st.session_state['selector_ep_num'] = str(_qp_sel_ep)
        st.query_params.clear()
    _qp_filtro = st.query_params.get('_filtro_estado')
    if _qp_filtro is not None:
        _prev = st.session_state.get('filtro_estado_tabla')
        st.session_state.filtro_estado_tabla = _qp_filtro if _qp_filtro != 'TODOS' else None
        if _prev != st.session_state.filtro_estado_tabla:
            st.session_state.pop('selector_cotizaciones', None)
            st.session_state.pop('selector_ep_num', None)
        st.query_params.clear()
    if st.session_state.get('_tab3_necesita_refresh', False):
        st.session_state.resultados_busqueda = None
        st.session_state['_tab3_necesita_refresh'] = False
    if 'filtro_estado_tabla' not in st.session_state:
        st.session_state.filtro_estado_tabla = None
    if 'resultados_busqueda' not in st.session_state or st.session_state.resultados_busqueda is None:
        with st.spinner("Cargando cotizaciones..."):
            st.session_state.resultados_busqueda = buscar_cotizaciones()

    if buscar_btn or (termino and termino != st.session_state.get('ultimo_termino', '')):
        st.session_state.ultimo_termino = termino
        with st.spinner("Buscando..."):
            st.session_state.resultados_busqueda = buscar_cotizaciones(termino or None, tipo_map[tipo_busqueda])
        st.session_state.filtro_estado_tabla = None
        st.session_state.mostrar_visor = False
        st.session_state.pdf_actual = None; st.session_state.pdf_nombre = ""
        st.session_state.numero_en_visor = None; st.session_state.pdf_url = None

    if limpiar_btn:
        st.session_state.resultados_busqueda = []
        st.session_state.ultimo_termino = ""
        st.session_state.mostrar_visor = False
        st.session_state.pdf_actual = None; st.session_state.pdf_nombre = ""
        st.session_state.numero_en_visor = None; st.session_state.pdf_url = None
        st.rerun()

    if st.session_state.resultados_busqueda:
        _cols = ["N°","Cliente","Asesor","Fecha","Total","Margen","RUT","Email","Asesor_Email",
                 "Asesor_Tel","Tiene_Plano","Tiene_Contrato","Empresa","Fecha_Auth","Autorizado_Por",
                 "Tiene_Notariado","Fecha_Adj","Contrato_Datos","Not_URL","Motivo_Rechazo",
                 "Fecha_Rechazo","Acta_URL","Fecha_Entrega","Cli_Tel","Cli_Dir","Cli_Comuna",
                 "Cli_Region","Inst_Dir","Inst_Comuna","Inst_Region","RutEmpresa","NLogs"]
        if len(st.session_state.resultados_busqueda[0]) < len(_cols):
            st.session_state.resultados_busqueda = buscar_cotizaciones()
        _rn = []
        for _r in st.session_state.resultados_busqueda:
            _r = list(_r)
            while len(_r) < len(_cols): _r.append(0)
            _rn.append(_r[:len(_cols)])
        df_resultados = pd.DataFrame(_rn, columns=_cols)
        _sub_lbl = ("<br><span style='font-size:0.72em;color:#94a3b8;font-weight:400;'>base+IVA+margen+Varios</span>"
                    if st.session_state.get('modo_admin')
                    else "<br><span style='font-size:0.72em;color:#94a3b8;font-weight:400;'>IVA incluido</span>")
        df_resultados["Total"] = df_resultados["Total"].apply(
            lambda x: (f"${x:,.0f}".replace(",",".") + _sub_lbl) if x else ("$0" + _sub_lbl))

        def _fmt_fecha_auth(x):
            if not x or not isinstance(x,str) or not x.strip(): return "—"
            try:
                from datetime import datetime as _dt, timezone, timedelta as _td
                _d=_dt.fromisoformat(str(x).replace("Z","+00:00")).astimezone(timezone(_td(hours=-3)))
                return (f'<span style="font-weight:700;">{_d.strftime("%d/%m/%Y")}</span>'
                        f'<br><span style="font-size:0.75em;color:#64748b;">{_d.strftime("%H:%M")}</span>')
            except: return str(x)[:10] if x else "—"

        df_resultados["Fecha_raw"] = df_resultados["Fecha"].copy()

        def _fmt_demora_v2(row):
            fc=row.get("Fecha_raw",""); fa=row["Fecha_Auth"]
            if not fc: return "—"
            try:
                from datetime import datetime as _dt, timezone as _tz, timedelta as _td
                _tz_cl=_tz(_td(hours=-3)); d1=_dt.fromisoformat(fc.replace("Z","+00:00")).astimezone(_tz_cl)
                if row["Margen"] and row["Margen"]>0 and fa and isinstance(fa,str) and fa.strip():
                    d2=_dt.fromisoformat(fa.replace("Z","+00:00")).astimezone(_tz_cl)
                    df=d2-d1; p=[]
                    if df.days>0: p.append(f"{df.days}d")
                    if df.seconds//3600>0: p.append(f"{df.seconds//3600}h")
                    p.append(f"{(df.seconds%3600)//60}m")
                    return (f'<span style="color:#2563eb;font-weight:700;">{" ".join(p)}</span>'
                            f'<br><span style="font-size:0.72em;color:#2563eb;">finalizado</span>')
                else:
                    ts=int(d1.timestamp()*1000)
                    return (f'<span class="demora-live" data-desde="{ts}" '
                            f'style="color:#dc2626;font-weight:700;display:inline-block;'
                            f'min-width:80px;font-variant-numeric:tabular-nums;">...</span>')
            except: return "—"
        df_resultados["Demora"] = df_resultados.apply(_fmt_demora_v2, axis=1)

        def _fmt_fecha(x):
            if not x: return ""
            try:
                from datetime import datetime as _dt, timezone, timedelta as _td
                _d=_dt.fromisoformat(x.replace("Z","+00:00")).astimezone(timezone(_td(hours=-3)))
                return (f'<span style="font-weight:700;">{_d.strftime("%d/%m/%Y")}</span>'
                        f'<br><span style="font-size:0.75em;color:#64748b;">{_d.strftime("%H:%M")}</span>')
            except: return x[:10]

        def _fmt_fecha_plana(x):
            if not x: return ""
            try:
                from datetime import datetime as _dt, timezone, timedelta as _td
                _d=_dt.fromisoformat(x.replace("Z","+00:00")).astimezone(timezone(_td(hours=-3)))
                return _d.strftime("%d/%m/%Y %H:%M")
            except: return x[:10]

        df_resultados["FechaPlana"] = df_resultados["Fecha"].apply(_fmt_fecha_plana)
        df_resultados["Fecha"] = df_resultados["Fecha"].apply(_fmt_fecha)
        df_resultados["Estado"] = df_resultados.apply(crear_badge_estado, axis=1)
        import re as _re_est
        df_resultados["EstadoKey"] = df_resultados["Estado"].apply(
            lambda h: _re_est.sub(r"<[^>]+>","",str(h)).strip())

        def _fmt_auth_nom(row):
            fh=_fmt_fecha_auth(row["Fecha_Auth"]); q=str(row.get("Autorizado_Por","") or "").strip()
            if not fh or fh=="—": return "—"
            return f'{fh}<br><span style="font-size:0.72em;color:#16a34a;font-weight:700;">{_hic("check","#16a34a",12,4)}{q}</span>' if q else fh
        df_resultados["Fecha_Auth_fmt"] = df_resultados.apply(_fmt_auth_nom, axis=1)
        _si_html = _hic("check", "#16a34a", 13, 4) + "S&#237;"
        df_resultados["Plano"] = df_resultados.apply(lambda r: _si_html if r["Tiene_Plano"] else "—", axis=1)
        df_resultados["MargenCol"] = df_resultados["Margen"].apply(
            lambda x: f'{_si_html}<br><span style="font-size:0.78em;color:#16a34a;">{x:.3f}%</span>' if x and x>0 else "—")
        df_resultados["ContratoCol"] = df_resultados["Tiene_Contrato"].apply(lambda x: _si_html if x else "—")
        df_resultados["EmpresaCol"] = df_resultados["Empresa"].apply(lambda x: _si_html if x and str(x).strip() else "—")
        df_resultados["ModCol"] = df_resultados["NLogs"].apply(
            lambda x: (f'<span style="font-weight:700;color:#3b82f6;">{int(float(x))}</span>'
                       if x and str(x).strip() and int(float(x))>0
                       else '<span style="color:#94a3b8;">0</span>'))

        if _rol_actual in ('root', 'admin'):
            _eps_c = df_resultados["N°"].tolist()
            _ck = 'prods_map_' + ','.join(sorted(_eps_c))
            if '_prods_map_ts' not in st.session_state: st.session_state['_prods_map_ts'] = 0
            import time as _tpm
            if st.session_state.get('_prods_map_key') != _ck or (_tpm.time()-st.session_state['_prods_map_ts'])>60:
                try:
                    _pr=supabase_admin.table("cotizaciones").select("numero,productos").in_("numero",_eps_c).execute()
                    _pm={}
                    for _p in (_pr.data or []):
                        try:
                            _pl=_p.get("productos") or []
                            if isinstance(_pl,str): _pl=json.loads(_pl)
                            _pm[_p["numero"]]=_pl
                        except: pass
                    st.session_state['_prods_map_cache']=_pm
                    st.session_state['_prods_map_key']=_ck
                    st.session_state['_prods_map_ts']=_tpm.time()
                except: st.session_state['_prods_map_cache']={}
            _prods_map = st.session_state.get('_prods_map_cache',{})

            _mat_data_map = {}
            _eps_m=df_resultados["N°"].tolist()
            _mck='mat_map_'+','.join(sorted(_eps_m))
            if '_mat_map_ts' not in st.session_state: st.session_state['_mat_map_ts']=0
            # Cache en session (60s) por set de EPs (completo, pre-filtro): evita 2
            # queries a Supabase en CADA rerun, p.ej. al filtrar por badge.
            if st.session_state.get('_mat_map_key')!=_mck or (_tpm.time()-st.session_state['_mat_map_ts'])>60:
                try:
                    _mcfg=supabase_admin.table("formulario_config").select(
                        "cotizacion_numero,categoria,titulo_grupo,item_ids,orden"
                    ).in_("cotizacion_numero",_eps_m).execute().data or []
                    _mres=supabase_admin.table("formulario_respuestas").select(
                        "cotizacion_numero,item_id,respuesta"
                    ).in_("cotizacion_numero",_eps_m).execute().data or []
                    from collections import defaultdict as _dd2
                    _mr2=_dd2(dict)
                    for _r in _mres:
                        if _r.get("item_id"): _mr2[_r["cotizacion_numero"]][_r["item_id"]]=_r["respuesta"]
                    _mc2=_dd2(list)
                    for _c in _mcfg: _mc2[_c["cotizacion_numero"]].append(_c)
                    # Lookup imagen/color del catálogo por (categoria,nombre) y por
                    # nombre, para adjuntar la foto del material seleccionado.
                    _cat_by_cn={}; _cat_by_n={}
                    for _cm in (fetch_catalogo_materiales() or []):
                        _nm=str(_cm.get("nombre","") or "").strip().lower()
                        if not _nm: continue
                        _info={"img":str(_cm.get("imagen_url","") or ""),"hex":str(_cm.get("hex","") or "")}
                        _cat_by_cn[(str(_cm.get("categoria","") or "").strip().lower(),_nm)]=_info
                        _cat_by_n.setdefault(_nm,_info)
                    def _mat_img(_cat,_val):
                        _k=str(_val).strip().lower()
                        return _cat_by_cn.get((str(_cat).strip().lower(),_k)) or _cat_by_n.get(_k) or {}
                    for _ep2,_cfgs2 in _mc2.items():
                        _rs2=_mr2[_ep2]; _tot2=len(_cfgs2)
                        _dn2=sum(1 for _c in _cfgs2 if any(_rs2.get(str(_i)) for _i in (_c.get("item_ids") or [])))
                        _pct2=int(_dn2/_tot2*100) if _tot2>0 else 0
                        from collections import defaultdict as _dd3
                        _cats2=_dd3(list)
                        for _c in sorted(_cfgs2,key=lambda x:(x.get("categoria",""),x.get("orden",0))):
                            _ids2=[str(_i) for _i in (_c.get("item_ids") or [])]
                            _v2=[str(_rs2[_i]) for _i in _ids2 if _rs2.get(_i)]
                            _cat2=_c.get("categoria","")
                            _vals2=[{"n":_x,"img":_mat_img(_cat2,_x).get("img",""),
                                     "hex":_mat_img(_cat2,_x).get("hex","")} for _x in _v2]
                            _cats2[_cat2].append({"tg":_c.get("titulo_grupo",""),
                                                  "val":", ".join(_v2),"vals":_vals2})
                        _mat_data_map[_ep2]={"pct":_pct2,"done":_dn2,"total":_tot2,
                            "cats":[{"cat":_k,"grupos":_vl} for _k,_vl in _cats2.items()]}
                    st.session_state['_mat_map_cache']=_mat_data_map
                    st.session_state['_mat_map_key']=_mck
                    st.session_state['_mat_map_ts']=_tpm.time()
                except: st.session_state['_mat_map_cache']={}
            _mat_data_map=st.session_state.get('_mat_map_cache',{})

            def _fmt_compras_ok(row):
                try:
                    _num=row.get("N°",""); _mat=_mat_data_map.get(_num,{})
                    _mp=_mat.get("pct",0); _mt=_mat.get("total",0)
                    def _mh():
                        if not _mt: return ""
                        _mc="#16a34a" if _mp==100 else ("#f97316" if _mp>=50 else "#2563eb")
                        _mb="#dcfce7" if _mp==100 else ("#ffedd5" if _mp>=50 else "#dbeafe")
                        return (f'<div style="margin-top:4px;padding-top:4px;border-top:1px solid #e2e8f0;">'
                                f'<div style="font-size:0.65rem;font-weight:700;color:#64748b;margin-bottom:2px;">MATERIALES</div>'
                                f'<div style="background:{_mb};border-radius:4px;height:4px;margin-bottom:3px;">'
                                f'<div style="background:{_mc};border-radius:4px;height:4px;width:{_mp}%;"></div></div>'
                                f'<div style="display:flex;align-items:center;justify-content:space-between;gap:4px;">'
                                f'<span style="color:{_mc};font-weight:700;font-size:0.68rem;">{_mp}%</span>'
                                f'<button class="_mat_btn" data-ep="{_num}" style="background:#eff6ff;color:#1d4ed8;'
                                f'border:1px solid #bfdbfe;border-radius:4px;padding:1px 5px;font-size:0.62rem;'
                                f'font-weight:700;cursor:pointer;font-family:inherit;line-height:1.4;">{_hic("eye","#1d4ed8",12,4)}Ver</button>'
                                f'</div></div>')
                    _pr=_prods_map.get(_num) or []
                    if isinstance(_pr,str):
                        try: _pr=json.loads(_pr)
                        except: _pr=[]
                    _est=calcular_estado_compras(_num,_pr)
                    _pct=_est["pct"]; _estado=_est["estado"]
                    def _cc(p):
                        if p<=33: return '#dc2626','#fee2e2'
                        elif p<=66: return '#f97316','#ffedd5'
                        elif p<100: return '#16a34a','#dcfce7'
                        else: return '#2563eb','#dbeafe'
                    if _estado=="Sin compras":
                        return f'<span style="color:#94a3b8;font-size:0.78rem;">Sin compras</span>'+_mh()
                    elif _estado=="Compras 100%":
                        c,b=_cc(100)
                        return (f'<div style="width:80px;"><div style="background:{b};border-radius:4px;height:6px;margin-bottom:3px;">'
                                f'<div style="background:{c};border-radius:4px;height:6px;width:100%;"></div></div>'
                                f'<span style="color:{c};font-weight:700;font-size:0.75rem;">{_hic("check",c,12,3)}100% comprado</span></div>')+_mh()
                    elif "adicionales" in _estado:
                        na=len(_est["adicionales"]); c,b=_cc(100)
                        return (f'<div style="width:80px;"><div style="background:{b};border-radius:4px;height:6px;margin-bottom:3px;">'
                                f'<div style="background:{c};border-radius:4px;height:6px;width:100%;"></div></div>'
                                f'<span style="color:{c};font-weight:700;font-size:0.75rem;">{_hic("check",c,12,3)}100% +{na} adic.</span></div>')+_mh()
                    else:
                        c,b=_cc(_pct)
                        return (f'<div style="width:80px;"><div style="background:{b};border-radius:4px;height:6px;margin-bottom:3px;">'
                                f'<div style="background:{c};border-radius:4px;height:6px;width:{_pct}%;"></div></div>'
                                f'<span style="color:{c};font-weight:700;font-size:0.75rem;">{_pct}% comprado</span></div>')+_mh()
                except: return '<span style="color:#94a3b8;font-size:0.78rem;">—</span>'
            df_resultados["ComprasOK"] = df_resultados.apply(_fmt_compras_ok, axis=1)
        else:
            _mat_data_map = {}
            df_resultados["ComprasOK"] = ""

        import re as _re_cnt
        _estados_cnt_total = {}
        for _bv in df_resultados['Estado']:
            _bt=_re_cnt.sub(r'<[^>]+>','',str(_bv)).strip()
            _estados_cnt_total[_bt]=_estados_cnt_total.get(_bt,0)+1

        # El filtrado por estado ahora es 100% CLIENT-SIDE (JS oculta filas por data-est,
        # SIN rerun) → instantáneo y sin el crash de React (removeChild) que causaba el
        # rerun del badge. Por eso NO se filtra df_resultados aquí: se renderizan TODAS
        # las filas y el badge sólo cambia su visibilidad en el navegador.
        n_resultados = len(df_resultados)

        _tc_map = {}
        if st.session_state.get('modo_admin'):
            try:
                for _tn,_tp in st.session_state.get('_prods_map_cache',{}).items():
                    try:
                        _pl=_tp if isinstance(_tp,list) else []
                        _df=pd.DataFrame(_pl) if _pl else pd.DataFrame()
                        if not _df.empty and 'Categoria' in _df.columns:
                            _df=_df[_df['Categoria'].str.strip().str.lower()!='varios']
                        _tc_map[_tn]=(_df['Subtotal'].sum() if not _df.empty and 'Subtotal' in _df.columns else 0)*1.19
                    except: pass
            except: pass

        # Modelo predefinido (tabla cotizaciones) — keyed por el set COMPLETO de EPs
        # para que no se re-consulte al filtrar por badge.
        _eps_full = [str(_r[0]) for _r in (st.session_state.resultados_busqueda or [])]
        _modelos_map = _modelos_predefinidos(tuple(sorted(_eps_full)))
        _foto_map = fetch_foto_map(SUPABASE_URL)   # email(minúsculas) -> foto_url
        _cli_data_map = {}
        for _,_mr in df_resultados.iterrows():
            _ase_nom = str(_mr.get('Asesor','') or '')
            _ase_mail = str(_mr.get('Asesor_Email','') or '')
            _ase_foto = _foto_map.get(_ase_mail.lower(), '') if _ase_mail else ''
            _cli_data_map[str(_mr.get('N°',''))]={
                'nombre':str(_mr.get('Cliente','') or ''),'rut':str(_mr.get('RUT','') or ''),
                'tel':str(_mr.get('Cli_Tel','') or ''),'email':str(_mr.get('Email','') or ''),
                'dir':str(_mr.get('Cli_Dir','') or ''),'comuna':str(_mr.get('Cli_Comuna','') or ''),
                'region':str(_mr.get('Cli_Region','') or ''),'empresa':str(_mr.get('Empresa','') or ''),
                'inst_dir':str(_mr.get('Inst_Dir','') or ''),'inst_comuna':str(_mr.get('Inst_Comuna','') or ''),
                'inst_region':str(_mr.get('Inst_Region','') or ''),
                'rut_empresa':str(_mr.get('RutEmpresa','') or ''),
                'modelo':str(_modelos_map.get(str(_mr.get('N°','')),'') or ''),
                'asesor':_ase_nom,
                'asesor_avatar':avatar_html(_ase_foto, _ase_nom, size=100, ring='#334155', font_scale=0.34)}
        _cli_data_json_map = json.dumps(_cli_data_map, ensure_ascii=True)
        _mat_data_json_map = json.dumps(_mat_data_map, ensure_ascii=True)

        # Para las banderas por-fila del menú contextual (habilitar/deshabilitar cada
        # acción): rol/modo_admin son constantes y las EPs con selección se consultan
        # en UNA query batcheada (no por fila).
        _modo_adm_ctx = bool(st.session_state.get('modo_admin'))
        _es_ej_ctx_tbl = _rol_actual == 'ejecutivo'
        _es_admin_ctx = _rol_actual in ('admin', 'root')
        _eps_sel_set = _eps_con_seleccion(tuple(sorted({str(_r[0]) for _r in (st.session_state.resultados_busqueda or [])})))
        _attresc = lambda v: (str(v).replace('&', '&amp;').replace('"', '&quot;')
                              .replace('<', '&lt;').replace('>', '&gt;').replace("'", '&#39;'))

        rows_html = ""
        for _, row in df_resultados.iterrows():
            _mg_color = 'color:#16a34a;font-weight:700;' if str(row['MargenCol']) != '—' else 'color:#94a3b8;'
            _th_margen = '<th>Margen</th>' if st.session_state.get('modo_admin') else ''
            _td_margen = f'<td style="text-align:center;line-height:1.6;{_mg_color}">{row["MargenCol"]}</td>' if st.session_state.get('modo_admin') else ''
            _tc_val = _tc_map.get(row["N°"],0)
            _tc_fmt = f"${_tc_val:,.0f}".replace(",",".") if _tc_val else "—"
            _th_tc = '<th>Total costo</th>' if st.session_state.get('modo_admin') else ''
            _td_tc = (f'<td style="text-align:right;font-size:0.82rem;font-weight:700;color:#0f172a;">{_tc_fmt}'
                      f'<br><span style="font-size:0.72em;color:#94a3b8;font-weight:400;">base+IVA · sin margen · sin Varios</span></td>'
                      if st.session_state.get('modo_admin') else '')
            _th_compras = (f'<th class="th-adj">{_hic("cart","#0f172a",14,6)}Compras</th>'
                           if st.session_state.get('modo_admin') else '')
            _td_compras = (f'<td style="text-align:center;background:#fef3c7;font-weight:700;color:#0f172a;">{row.get("ComprasOK","—")}</td>'
                           if st.session_state.get('modo_admin') else '')
            _ct_color = 'color:#16a34a;font-weight:700;' if str(row['ContratoCol'])!='—' else 'color:#94a3b8;'
            _emp_color = 'color:#16a34a;font-weight:700;' if str(row['EmpresaCol'])!='—' else 'color:#94a3b8;'
            _pln_color = 'color:#16a34a;font-weight:700;' if str(row['Plano'])!='—' else 'color:#94a3b8;'
            from datetime import datetime as _dt_cot, timezone as _tz_cot, timedelta as _td_cot
            _tz_cl_cot = _tz_cot(_td_cot(hours=-3))
            _proc_not_html = '<span style="color:#94a3b8;">—</span>'
            _fadj_html_cot = '<span style="color:#94a3b8;">—</span>'
            _fab_html_cot = '<span style="color:#94a3b8;">—</span>'
            _fidel_html_cot = '<span style="color:#94a3b8;">—</span>'
            _retraso_html_cot = '<span style="color:#94a3b8;">—</span>'
            _es_adj_cot = bool(str(row.get('Not_URL','') or ''))
            _fadj_raw_cot = str(row.get('Fecha_Adj','') or '')
            _fauth_raw_cot = str(row.get('Fecha_Auth','') or '')
            _acta_url_cot = str(row.get('Acta_URL','') or '')
            _fecha_entrega_cot = str(row.get('Fecha_Entrega','') or '')
            _tiene_acta_cot = bool(_acta_url_cot)
            _motivo_rec = str(row.get('Motivo_Rechazo','') or '')
            _fecha_rec_raw = str(row.get('Fecha_Rechazo','') or '')
            _margen_cot = float(row.get('Margen',0) or 0)
            _ep_num_row = str(row.get('N°',''))
            if not _fadj_raw_cot: _fadj_raw_cot = _fauth_raw_cot

            if _motivo_rec:
                try:
                    if _fauth_raw_cot and _fecha_rec_raw:
                        _da=_dt_cot.fromisoformat(_fauth_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                        _dr=_dt_cot.fromisoformat(_fecha_rec_raw.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                        _df=_dr-_da; _p=[]
                        if _df.days>0: _p.append(f"{_df.days}d")
                        if _df.seconds//3600>0: _p.append(f"{_df.seconds//3600}h")
                        if (_df.seconds%3600)//60>0: _p.append(f"{(_df.seconds%3600)//60}m")
                        _p.append(f"{_df.seconds%60}s"); _tr=" ".join(_p)
                    else: _tr="—"
                    _proc_not_html=(f'<span style="color:#dc2626;font-weight:700;">{_tr}</span>'
                        f'<br><span style="font-size:0.72em;color:#dc2626;font-weight:600;">rechazado</span>'
                        f'<br><button class="_motivo_btn" data-ep="{_ep_num_row}" data-motivo="{_motivo_rec.replace(chr(34),chr(39))}"'
                        f' style="margin-top:2px;background:#fee2e2;color:#b91c1c;border:1px solid #fca5a5;'
                        f'border-radius:6px;padding:1px 8px;font-size:0.68rem;font-weight:700;cursor:pointer;'
                        f'font-family:inherit;">{_hic("clipboard","#b91c1c",11,4)}Motivo</button>')
                except: _proc_not_html='<span style="color:#dc2626;font-weight:700;">rechazado</span>'
            elif _es_adj_cot and _fauth_raw_cot and _fadj_raw_cot:
                try:
                    _da=_dt_cot.fromisoformat(_fauth_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _dj=_dt_cot.fromisoformat(_fadj_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _df=_dj-_da; _p=[]
                    if _df.days>0: _p.append(f"{_df.days}d")
                    if _df.seconds//3600>0: _p.append(f"{_df.seconds//3600}h")
                    _p.append(f"{(_df.seconds%3600)//60}m")
                    _proc_not_html=(f'<span style="color:#2563eb;font-weight:700;">{" ".join(_p)}</span>'
                                    f'<br><span style="font-size:0.72em;color:#2563eb;">finalizado</span>')
                except: pass
            elif _fauth_raw_cot and not _motivo_rec and not _es_adj_cot and _margen_cot>0:
                try:
                    _d_desde_pn=_dt_cot.fromisoformat(_fauth_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _ts_pn=int(_d_desde_pn.timestamp()*1000)
                    _proc_not_html=(f'<span class="demora-live" data-desde="{_ts_pn}" '
                                    f'style="color:#dc2626;font-weight:700;display:inline-block;'
                                    f'min-width:90px;font-variant-numeric:tabular-nums;">...</span>')
                except: pass

            if _es_adj_cot and _fadj_raw_cot:
                try:
                    _d_fadj=_dt_cot.fromisoformat(_fadj_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _fadj_html_cot=(f'<span style="font-weight:700;">{_d_fadj.strftime("%d/%m/%Y")}</span>'
                                    f'<br><span style="font-size:0.75em;color:#64748b;">{_d_fadj.strftime("%H:%M")}</span>')
                except: _fadj_html_cot=_fadj_raw_cot[:10]
            else: _fadj_html_cot='<span style="color:#94a3b8;">—</span>'

            if _tiene_acta_cot and _fadj_raw_cot and _fecha_entrega_cot not in ('','None','nan'):
                try:
                    _da2=_dt_cot.fromisoformat(_fadj_raw_cot.replace('Z','+00:00')).astimezone(_tz_cl_cot)
                    _de2=_dt_cot.fromisoformat(_fecha_entrega_cot.replace('Z','+00:00')).astimezone(_tz_cl_cot)
                    _df2=_de2-_da2; _sg=int(_df2.total_seconds())
                    _dd=_sg//86400; _hh=(_sg%86400)//3600; _mm=(_sg%3600)//60; _ss=_sg%60
                    _tx='';
                    if _dd>0: _tx+=f'{_dd}d '
                    if _hh>0: _tx+=f'{_hh}h '
                    if _mm>0: _tx+=f'{_mm}m '
                    _tx+=f'{_ss}s'
                    _cd=row.get('Contrato_Datos') or {}
                    if isinstance(_cd,str) and _cd:
                        try: _cd=json.loads(_cd)
                        except: _cd={}
                    _pl=int((_cd or {}).get('plazo_dias',0) or 45)
                    _dlim=sumar_dias_habiles(_da2.date(),_pl)
                    _ret=_de2.date()>_dlim
                    _col='#dc2626' if _ret else '#7c3aed'
                    _lbl=(_hic("alert",_col,11,3)+'FINALIZADO') if _ret else (_hic("flag",_col,11,3)+'FINALIZADO')
                    _fab_html_cot=(f'<span style="color:{_col};font-weight:700;display:inline-block;font-variant-numeric:tabular-nums;">{_tx}</span>'
                                   f'<br><span style="font-size:0.72em;color:{_col};font-weight:700;">{_lbl}</span>')
                except: _fab_html_cot=f'<span style="color:#7c3aed;font-weight:700;">{_hic("flag","#7c3aed",11,3)}FINALIZADO</span>'
            elif _tiene_acta_cot:
                _fab_html_cot=f'<span style="color:#7c3aed;font-weight:700;">{_hic("flag","#7c3aed",11,3)}FINALIZADO</span>'
            elif _es_adj_cot and _fadj_raw_cot:
                try:
                    _da3=_dt_cot.fromisoformat(_fadj_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _ts3=int(_da3.timestamp()*1000)
                    _fab_html_cot=(f'<span class="fab-live" data-desde="{_ts3}" '
                                   f'style="color:#2563eb;font-weight:700;display:inline-block;'
                                   f'min-width:100px;font-variant-numeric:tabular-nums;">...</span>')
                except: _fab_html_cot='—'
            else: _fab_html_cot='<span style="color:#94a3b8;">—</span>'

            if _tiene_acta_cot and _fadj_raw_cot:
                try:
                    _cd=row.get('Contrato_Datos') or {}
                    if isinstance(_cd,str) and _cd:
                        try: _cd=json.loads(_cd)
                        except: _cd={}
                    _pl=int((_cd or {}).get('plazo_dias',0) or 45)
                    _da4=_dt_cot.fromisoformat(_fadj_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                    _dad=_da4.date(); _dent=sumar_dias_habiles(_dad,_pl)
                    _ms=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
                    _fs=f"{_dent.day} {_ms[_dent.month-1]} {_dent.year}"
                    _fec=_fecha_entrega_cot if _fecha_entrega_cot not in ('','None','nan') else ''
                    _dr4=(_dt_cot.fromisoformat(_fec.replace("Z","+00:00")).astimezone(_tz_cl_cot) if _fec else _dt_cot.now(_tz_cl_cot))
                    _dc4=_dr4-_da4; _sg4=int(_dc4.total_seconds())
                    _tx4=''; _dd4=_sg4//86400; _hh4=(_sg4%86400)//3600; _mm4=(_sg4%3600)//60; _ss4=_sg4%60
                    if _dd4>0: _tx4+=f'{_dd4}d '
                    if _hh4>0: _tx4+=f'{_hh4}h '
                    if _mm4>0: _tx4+=f'{_mm4}m '
                    _tx4+=f'{_ss4}s'
                    _hu=dias_habiles_entre(_dad,_dr4.date())
                    _cr=_dr4.date()>_dent; _pu=min(round((_hu/_pl)*100,2),100.0) if _pl>0 else 100.0
                    _cf='#dc2626' if _cr else '#7c3aed'; _lf=(_hic("alert",_cf,11,3)+'FINALIZADO') if _cr else (_hic("flag",_cf,11,3)+'FINALIZADO')
                    _fidel_html_cot=(f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<span style="color:{_cf};font-weight:700;font-variant-numeric:tabular-nums;min-width:70px;">{_hic("clock",_cf,11,3)}{_tx4}</span>'
                        f'<span style="font-size:1.3rem;font-weight:900;color:{_cf};">{_pu}%</span></div>'
                        f'<span style="font-size:0.72em;color:#64748b;font-weight:600;">{_hic("calendar","#64748b",11,3)}{_fs}</span>'
                        f'<br><span style="font-size:0.68em;color:#94a3b8;">{_pl} días hábiles</span>'
                        f'<br><span style="font-size:0.72em;color:{_cf};font-weight:700;">{_lf}</span>')
                    _dlt=_dt_cot.combine(_dent,_dt_cot.min.time()).replace(tzinfo=_tz_cl_cot)
                    _drf=_dr4-_dlt; _sr=int(abs(_drf.total_seconds()))
                    _tr2=''; _dr2=_sr//86400; _hr2=(_sr%86400)//3600; _mr2=(_sr%3600)//60; _sr2=_sr%60
                    if _dr2>0: _tr2+=f'{_dr2}d '
                    if _hr2>0: _tr2+=f'{_hr2}h '
                    if _mr2>0: _tr2+=f'{_mr2}m '
                    _tr2+=f'{_sr2}s'
                    if _dr4.date()>_dent:
                        _retraso_html_cot=(f'<span style="color:#dc2626;font-weight:700;font-variant-numeric:tabular-nums;">{_hic("alert","#dc2626",11,3)}{_tr2}</span>'
                                           f'<br><span style="font-size:0.72em;color:#dc2626;font-weight:600;">tiempo en contra</span>')
                    else:
                        _retraso_html_cot=(f'<span style="color:#16a34a;font-weight:700;font-variant-numeric:tabular-nums;">{_hic("check","#16a34a",11,3)}{_tr2}</span>'
                                           f'<br><span style="font-size:0.72em;color:#16a34a;font-weight:600;">tiempo a favor</span>')
                except: pass
            elif _es_adj_cot and _fadj_raw_cot:
                try:
                    _cd=row.get('Contrato_Datos') or {}
                    if isinstance(_cd,str) and _cd:
                        try: _cd=json.loads(_cd)
                        except: _cd={}
                    _pl=int((_cd or {}).get('plazo_dias',0) or 45)
                    if _pl>0:
                        _da5=_dt_cot.fromisoformat(_fadj_raw_cot.replace("Z","+00:00")).astimezone(_tz_cl_cot)
                        _hoy=_dt_cot.now(_tz_cl_cot).date(); _dad5=_da5.date()
                        _ht=dias_habiles_entre(_dad5,_hoy); _dent5=sumar_dias_habiles(_dad5,_pl)
                        _ms=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"]
                        _fs5=f"{_dent5.day} {_ms[_dent5.month-1]} {_dent5.year}"
                        _det5=_dt_cot.combine(_dent5,_dt_cot.min.time()).replace(tzinfo=_tz_cl_cot)
                        _ts5=int(_det5.timestamp()*1000); _ta5=int(_da5.timestamp()*1000)
                        _hr5=dias_habiles_entre(_hoy,_dent5) if _hoy<_dent5 else 0
                        _pf5=min(round((_ht/_pl)*100,2),100.0)
                        if _hoy<=_dent5:
                            _col5="#16a34a" if _pf5<50 else ("#f97316" if _pf5<80 else "#dc2626")
                            _fidel_html_cot=(f'<div style="display:flex;align-items:center;gap:8px;">'
                                f'<span class="fidel-live" data-hasta="{_ts5}" data-plazo="{_pl}" data-adj="{_ta5}" '
                                f'style="color:{_col5};font-weight:700;font-variant-numeric:tabular-nums;min-width:70px;">{_hr5}d háb.</span>'
                                f'<span style="font-size:1.3rem;font-weight:900;color:{_col5};">{_pf5}%</span></div>'
                                f'<span style="font-size:0.72em;color:#64748b;font-weight:600;">{_hic("calendar","#64748b",11,3)}{_fs5}</span>'
                                f'<br><span style="font-size:0.68em;color:#94a3b8;">{_pl} días hábiles</span>')
                        else:
                            _hv=dias_habiles_entre(_dent5,_hoy)
                            _fidel_html_cot=(f'<span style="color:#dc2626;font-weight:700;">{_hic("alert","#dc2626",11,3)}VENCIDO</span>'
                                             f'<br><span style="font-size:0.72em;color:#94a3b8;">{_pl}d háb.</span>')
                            _retraso_html_cot=(f'<span class="retraso-live" data-desde="{_ts5}" '
                                               f'style="color:#dc2626;font-weight:700;display:inline-block;min-width:100px;font-variant-numeric:tabular-nums;">...</span>'
                                               f'<br><span style="font-size:0.72em;color:#dc2626;">{_hv}d hábiles</span>')
                except: pass

            import re as _re_dem
            if _motivo_rec:
                _demora_raw=str(row.get('Demora','') or '')
                _demora_txt=_re_dem.sub('<[^>]+>','',_demora_raw).strip() or '—'
                _demora_display=f'<span style="color:#991b1b;font-weight:700;">{_demora_txt}</span><br><span style="font-size:0.7em;color:#b91c1c;font-weight:600;">congelado</span>'
            else:
                _demora_display=row.get('Demora','—')
            _fila_class=' class="fila-rechazada"' if _motivo_rec else ''
            _est_attr=str(row.get('EstadoKey','')).replace("'",'')
            # Banderas del menú contextual (1/0) por fila.
            _cx_mg = float(row.get('Margen',0) or 0)
            _cx_datos = bool(str(row.get('Cliente','') or '').strip() and str(row.get('Email','') or '').strip())
            _cx_ase = bool(str(row.get('Asesor','') or '').strip() or str(row.get('Asesor_Email','') or '').strip() or str(row.get('Asesor_Tel','') or '').strip())
            _cx_autoriz = (_cx_mg > 0 and _cx_datos and _cx_ase)
            _cx_pdf = '1' if (not _es_ej_ctx_tbl or _cx_autoriz) else '0'
            # Rechazar: 'quitar' si ya está rechazado, '0' si es adjudicado/terminado
            # (no se puede rechazar), '1' si se puede rechazar.
            if _est_attr == 'RECHAZADO':
                _cx_rech = 'quitar'
            elif _est_attr in ('ADJUDICADO', 'PROYECTO TERMINADO'):
                _cx_rech = '0'
            else:
                _cx_rech = '1'
            _cx_selok = str(row.get('N°','')) in _eps_sel_set
            _cx_planook = bool(row.get('Tiene_Plano'))
            _cx_contrato = '1' if row.get('Tiene_Contrato') else '0'
            try:
                _cx_nlogs = int(float(row.get('NLogs', 0) or 0))
            except Exception:
                _cx_nlogs = 0
            _cx_modif = '1' if (_es_admin_ctx and _cx_nlogs > 0) else '0'
            _ase_email2 = str(row.get('Asesor_Email', '') or '').strip().lower()
            _ase_foto2 = _foto_map.get(_ase_email2, '') if _ase_email2 else ''
            # Ver documentos: hay algo que ver si el rol puede ver algún documento.
            _cx_ver = '1' if (_cx_planook or (not _es_ej_ctx_tbl) or _cx_pdf == '1' or _cx_selok or _cx_contrato == '1') else '0'
            _ctx_attrs = (
                f" data-ver='{_cx_ver}'"
                f" data-cargar='{'1' if (_modo_adm_ctx or _cx_mg <= 0) else '0'}'"
                f" data-compras='{'0' if _es_ej_ctx_tbl else '1'}'"
                f" data-completo='{_cx_pdf}' data-cliente='{_cx_pdf}'"
                f" data-seleccion='{'1' if _cx_selok else '0'}'"
                f" data-plano='{'1' if _cx_planook else '0'}'"
                f" data-rechazar='{_cx_rech}'"
                f" data-contrato='{_cx_contrato}' data-modif='{_cx_modif}'"
                f' data-cli="{_attresc(row.get("Cliente","") or "")}"'
                f' data-asesor="{_attresc(row.get("Asesor","") or "")}"'
                f' data-avatar="{_attresc(_ase_foto2)}"')
            rows_html+=(f"<tr{_fila_class} data-est='{_est_attr}'{_ctx_attrs}>"
                f"<td data-ep=\"{row['N°']}\" style=\"cursor:pointer;font-weight:700;color:#3b82f6;\" title=\"Click para copiar {row['N°']}\">{row['N°']} {_hic('copy','#3b82f6',12,0)}</td>"
                f"<td style='font-size:0.82rem;font-weight:700;color:#0f172a;line-height:1.5;'>{row['Cliente'] or '—'}"
                f"<br><button class='_datos_btn' data-ep=\"{row['N°']}\" style='margin-top:2px;background:#dbeafe;color:#1d4ed8;border:1px solid #93c5fd;border-radius:6px;padding:1px 8px;font-size:0.68rem;font-weight:700;cursor:pointer;font-family:inherit;'>{_hic('clipboard','#1d4ed8',11,4)}Datos</button></td>"
                f"<td style='text-align:right;font-size:0.82rem;font-weight:700;color:#0f172a;line-height:1.6;'>{row['Total']}</td>"
                f"{_td_tc}"
                f"<td style='font-size:0.82rem;font-weight:700;color:#0f172a;'>{row['Asesor'] or '—'}</td>"
                f"<td class='td-estado' style='text-align:center;'>{row['Estado']}</td>"
                f"<td style='line-height:1.6;'>{row['Fecha']}</td>"
                f"<td class='demora-col' style='text-align:center;font-size:0.82rem;font-weight:700;'>{_demora_display}</td>"
                f"<td style='line-height:1.6;'>{row['Fecha_Auth_fmt']}</td>"
                f"<td style='text-align:center;{_emp_color}'>{row['EmpresaCol']}</td>"
                f"{_td_margen}"
                f"<td style='text-align:center;{_ct_color}'>{row['ContratoCol']}</td>"
                f"<td style='text-align:center;{_pln_color}'>{row['Plano']}</td>"
                f"<td style='text-align:center;'>{row['ModCol']}</td>"
                f"<td style='text-align:center;font-size:0.82rem;'>{_proc_not_html}</td>"
                f"<td style='line-height:1.6;'>{_fadj_html_cot}</td>"
                f"{_td_compras}"
                f"<td style='text-align:center;font-size:0.82rem;'>{_fab_html_cot}</td>"
                f"<td style='text-align:center;font-size:0.82rem;'>{_fidel_html_cot}</td>"
                f"<td style='text-align:center;font-size:0.82rem;'>{_retraso_html_cot}</td></tr>")

        _filtro_activo_badge = st.session_state.get('filtro_estado_tabla')
        _n_total = len(st.session_state.resultados_busqueda)
        _BADGE_STYLE = {
            'TODOS': ('#ede9fe', '#6d28d9', '#6d28d9'),
            'PROYECTO TERMINADO': ('#ede9fe', '#7c3aed', '#5b21b6'),
            'ADJUDICADO': ('#dbeafe', '#1d4ed8', '#1e40af'),
            'AUTORIZADO CON PLANO': ('#dcfce7', '#15803d', '#166534'),
            'AUTORIZADO': ('#dcfce7', '#15803d', '#166534'),
            'BORRADOR CON PLANO': ('#ffedd5', '#c2410c', '#9a3412'),
            'BORRADOR': ('#fef9c3', '#854d0e', '#713f12'),
            'INCOMPLETO CON PLANO': ('#fee2e2', '#dc2626', '#991b1b'),
            'INCOMPLETO': ('#fee2e2', '#dc2626', '#991b1b'),
            'RECHAZADO': ('#fee2e2', '#b91c1c', '#7f1d1d'),
        }
        # Icono SVG inline por estado (misma familia que las stat cards de abajo).
        _BADGE_SVG = {
            'TODOS':                '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
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
        _badge_order = [
            ('TODOS', 'Todos'), ('PROYECTO TERMINADO', 'terminados'),
            ('ADJUDICADO', 'adjudicados'), ('AUTORIZADO CON PLANO', 'aut. c/plano'),
            ('AUTORIZADO', 'autorizados'), ('BORRADOR CON PLANO', 'borrador c/plano'),
            ('BORRADOR', 'borrador'), ('INCOMPLETO CON PLANO', 'incompleto c/plano'),
            ('INCOMPLETO', 'incompletos'), ('RECHAZADO', 'rechazados'),
        ]

        def _badge_svg(_p):
            return ('<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                    'stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
                    + _p + '</svg>')

        _ini_filtro = _filtro_activo_badge or 'TODOS'
        _bbar = ['<style>'
            '.ec-badgebar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:2px 0 6px;}'
            '.ec-badge{display:inline-flex;align-items:center;gap:7px;font-family:Montserrat,sans-serif;'
            'font-weight:800;font-size:11.5px;letter-spacing:0.03em;text-transform:uppercase;border:none;'
            'border-radius:99px;padding:6px 15px;cursor:pointer;white-space:nowrap;transition:all .12s;line-height:1;}'
            '.ec-badge:hover{filter:brightness(0.96);}'
            '.ec-badge.ec-refresh{padding:7px 11px;}'
            '</style>'
            f'<div class="ec-badgebar" id="_ec_badgebar" data-init="{_ini_filtro}">']
        for _bk, _blbl in _badge_order:
            if _bk != 'TODOS' and not _estados_cnt_total.get(_bk, 0):
                continue
            _bg, _fg, _act = _BADGE_STYLE.get(_bk, ('#e2e8f0', '#334155', '#334155'))
            _cnt = _n_total if _bk == 'TODOS' else _estados_cnt_total.get(_bk, 0)
            _is_act = (_bk == _ini_filtro)
            _st = (f'background:{_act};color:#fff;box-shadow:0 0 0 2px {_act};' if _is_act
                   else f'background:{_bg};color:{_fg};')
            _bbar.append(
                f'<button class="ec-badge" data-filter="{_bk}" data-bg="{_bg}" data-fg="{_fg}" '
                f'data-act="{_act}" style="{_st}">{_badge_svg(_BADGE_SVG.get(_bk, ""))}'
                f'<span>{_blbl} ({_cnt})</span></button>')
        _bbar.append('<button class="ec-badge ec-refresh" data-refresh="1" title="Actualizar" '
                     'style="background:#fff;color:#475569;box-shadow:0 0 0 1px #e2e8f0;">'
                     + _badge_svg('<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>'
                                  '<path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>'
                                  '<path d="M8 16H3v5"/>') + '</button>')
        _bbar.append(f'<span id="_ec_nres" style="margin-left:4px;font-family:Plus Jakarta Sans,sans-serif;'
                     f'font-size:0.8rem;color:#64748b;font-weight:700;">{n_resultados} resultados</span>')
        _bbar.append('</div>')
        st.markdown(''.join(_bbar), unsafe_allow_html=True)

        # Boton nativo OCULTO para el refresh real (re-consulta la BD -> rerun). El badge
        # HTML de refresh lo clickea por JS.
        st.markdown('<style>.st-key-cot_refresh_tabla{position:absolute!important;left:-9999px!important;'
                    'top:-9999px!important;height:0!important;overflow:hidden!important;}'
                    'iframe[height="0"]{display:none!important;margin:0!important;padding:0!important;}</style>',
                    unsafe_allow_html=True)
        if st.button("refresh", key='cot_refresh_tabla'):
            st.session_state.resultados_busqueda = None
            st.rerun()

        # JS: filtra la tabla EN EL CLIENTE (oculta filas por data-est) sin rerun.
        # Handler dedup en window.parent (sobrevive a reruns). El refresh si dispara rerun.
        components.html(r"""<script>
(function(){
  var W=window.parent, D=W.document;
  function apply(filter){
    var rows=D.querySelectorAll('.resultados-table tbody tr'); var vis=0;
    rows.forEach(function(tr){
      var est=tr.getAttribute('data-est')||'';
      var show=(!filter||filter==='TODOS'||est===filter);
      tr.style.display=show?'':'none'; if(show)vis++;
    });
    var n=D.getElementById('_ec_nres'); if(n) n.textContent=vis+(vis===1?' resultado':' resultados');
  }
  function setActive(btn){
    var bar=D.getElementById('_ec_badgebar'); if(!bar||!btn) return;
    bar.querySelectorAll('.ec-badge[data-filter]').forEach(function(b){
      b.style.background=b.getAttribute('data-bg'); b.style.color=b.getAttribute('data-fg'); b.style.boxShadow='none';
    });
    var act=btn.getAttribute('data-act'); btn.style.background=act; btn.style.color='#fff'; btn.style.boxShadow='0 0 0 2px '+act;
  }
  if(W._ecBadgeH) D.removeEventListener('click', W._ecBadgeH, true);
  W._ecBadgeH=function(e){
    var t=e.target&&e.target.closest?e.target.closest('#_ec_badgebar .ec-badge'):null; if(!t) return;
    e.preventDefault(); e.stopPropagation();
    if(t.getAttribute('data-refresh')){ var rb=D.querySelector('.st-key-cot_refresh_tabla button'); if(rb) rb.click(); return; }
    var bar=D.getElementById('_ec_badgebar'); var f=t.getAttribute('data-filter');
    if(f===(bar&&bar.getAttribute('data-active'))) f='TODOS';
    if(bar) bar.setAttribute('data-active', f);
    setActive(bar.querySelector('.ec-badge[data-filter="'+f+'"]'));
    apply(f);
  };
  D.addEventListener('click', W._ecBadgeH, true);
  var bar=D.getElementById('_ec_badgebar');
  if(bar){ var ini=bar.getAttribute('data-init')||'TODOS'; bar.setAttribute('data-active', ini); apply(ini); }
})();
</script>""", height=0)

        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        _altura_real = n_resultados * 60 + 60
        _usar_scroll = _altura_real > 550
        _altura_css = f"max-height:{min(_altura_real,550)}px;overflow-y:auto;" if _usar_scroll else ""
        html_table = f"""
        <style>
        .resultados-table tr.fila-rechazada td {{ background-color:#fee2e2!important;color:#991b1b!important; }}
        .resultados-table tr.fila-rechazada td span:not(.badge-rechazado) {{ color:#991b1b!important; }}
        .resultados-table .badge-rechazado {{ color:#fbbf24!important; }}
        .resultados-table tr.fila-rechazada td .badge-rechazado {{ color:#fbbf24!important;background-color:#dc2626!important; }}
        .resultados-table tr.fila-rechazada:hover td {{ background-color:#fecaca!important; }}
        .resultados-table th.th-adj {{ background-color:#fbbf24!important;background:#fbbf24!important;color:#0f172a!important; }}
        .resultados-table th.th-cierre {{ background-color:#2563eb!important;background:#2563eb!important;color:#ffffff!important; }}
        .resultados-table tbody tr.ec-ctx-row td {{ background-color:#dbeafe!important; }}
        .resultados-table tbody tr.ec-ctx-row td:first-child {{ box-shadow:inset 3px 0 0 #2563eb; }}
        </style>
        <div id="_ec_restable" data-selep="{st.session_state.get('selector_ep_num','')}" style="border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid #e2e8f0;overflow-x:auto;">
            <div style="{_altura_css}">
                <table class='resultados-table' style='margin:0;border-radius:0;box-shadow:none;min-width:1700px;table-layout:auto;white-space:nowrap;'>
                    <thead style='position:sticky;top:0;z-index:2;'>
                        <tr><th>Presupuesto</th><th>Cliente</th><th>Total proyecto</th>{_th_tc}<th>Ejecutivo</th><th>Estado</th><th>Creación</th><th>Demora</th><th>Autorización</th><th>Empresa</th>{_th_margen}<th>Contrato</th><th>Plano</th><th>Modif.</th><th class="th-cierre">$ Cierre de venta</th><th class="th-adj">Fecha adjudicación</th>{_th_compras}<th class="th-adj">Tiempo fabricación</th><th class="th-adj">Fidelización cliente</th><th class="th-adj">Retraso proyecto</th></tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>"""
        st.markdown(html_table, unsafe_allow_html=True)

        _nres_txt = str(n_resultados)+(" resultado" if n_resultados==1 else " resultados")
        _CHEV_L = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
                   'stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>')
        _CHEV_R = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
                   'stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>')
        _MOVEH = ('<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" '
                  'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
                  '<polyline points="18 8 22 12 18 16"/><polyline points="6 8 2 12 6 16"/>'
                  '<line x1="2" x2="22" y1="12" y2="12"/></svg>')
        _scroll_html=(
            "<style>*{box-sizing:border-box;}"
            ".tbl-scroll-wrap{display:flex;align-items:center;justify-content:space-between;margin-top:6px;"
            "font-family:'Plus Jakarta Sans',system-ui,sans-serif;}"
            ".tbl-n-res{font-size:0.8rem;color:#64748b;font-weight:600;}"
            ".tbl-scroll-right{display:flex;align-items:center;gap:10px;}"
            ".tbl-scroll-hint{display:flex;align-items:center;gap:6px;font-size:0.66rem;font-weight:700;"
            "letter-spacing:0.07em;text-transform:uppercase;color:#94a3b8;}"
            ".tbl-scroll-btn{width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;"
            "background:#fff;color:#475569;border:1px solid #e2e8f0;border-radius:10px;cursor:pointer;padding:0;"
            "box-shadow:0 1px 3px rgba(15,23,42,0.08);transition:all .16s cubic-bezier(.22,1,.36,1);}"
            ".tbl-scroll-btn svg{width:18px;height:18px;display:block;}"
            ".tbl-scroll-btn:hover{background:linear-gradient(135deg,#5b7cfa,#2563eb);color:#fff;"
            "border-color:transparent;box-shadow:0 6px 16px rgba(37,99,235,0.35);transform:translateY(-1px);}"
            ".tbl-scroll-btn:active{transform:translateY(0) scale(0.93);box-shadow:0 1px 3px rgba(15,23,42,0.12);}"
            "</style>"
            '<div class="tbl-scroll-wrap">'
            '  <span class="tbl-n-res"></span>'  # conteo vivo ahora en la barra de badges (#_ec_nres)
            '  <div class="tbl-scroll-right">'
            '    <button class="tbl-scroll-btn" id="btn-left" title="Desplazar a la izquierda">'+_CHEV_L+'</button>'
            '    <span class="tbl-scroll-hint">'+_MOVEH+'Scroll horizontal</span>'
            '    <button class="tbl-scroll-btn" id="btn-right" title="Desplazar a la derecha">'+_CHEV_R+'</button>'
            '  </div></div>'
            '<script>(function(){'
            'var D=window.parent.document;'
            'function gS(){var t=D.querySelector(".resultados-table");if(!t)return null;var el=t.parentElement;'
            'while(el){var s=window.parent.getComputedStyle(el);if(s.overflowX==="auto"||s.overflowX==="scroll")return el;el=el.parentElement;}return t.parentElement;}'
            'document.getElementById("btn-left").addEventListener("click",function(){var t=gS();if(t)t.scrollBy({left:-300,behavior:"smooth"});});'
            'document.getElementById("btn-right").addEventListener("click",function(){var t=gS();if(t)t.scrollBy({left:300,behavior:"smooth"});});'
            '})();</script>')
        components.html(_scroll_html, height=50)

        components.html("""<script>
var CLI_DATA = """ + _cli_data_json_map + """;
var MAT_DATA = """ + _mat_data_json_map + """;
(function(){
    var D = window.parent.document;
    D.addEventListener('click', function(e) {
        var btn = e.target && e.target.closest ? e.target.closest('._motivo_btn') : null;
        if(!btn) return;
        var ep=btn.getAttribute('data-ep')||''; var motivo=btn.getAttribute('data-motivo')||'';
        var ex=D.getElementById('_motivo_modal'); if(ex) ex.remove();
        var ov=D.createElement('div'); ov.id='_motivo_modal';
        ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center;';
        var box=D.createElement('div'); box.style.cssText='background:#1e293b;border:1px solid #334155;border-radius:16px;padding:28px 32px;max-width:480px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);';
        var hdr=D.createElement('div'); hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;';
        var ttl=D.createElement('div'); ttl.style.cssText='font-size:1rem;font-weight:900;color:#f1f5f9;'; ttl.textContent='❌ Motivo de rechazo — '+ep;
        var cls=D.createElement('button'); cls.textContent='✖ Cerrar';
        cls.style.cssText='background:rgba(239,68,68,0.15);color:#fca5a5;border:1px solid rgba(239,68,68,0.3);border-radius:6px;padding:3px 10px;cursor:pointer;font-size:0.8rem;font-weight:700;';
        hdr.appendChild(ttl); hdr.appendChild(cls);
        var bdy=D.createElement('div'); bdy.style.cssText='background:#0f172a;border-radius:10px;padding:14px 16px;font-size:0.92rem;color:#e2e8f0;line-height:1.6;word-break:break-word;'; bdy.textContent=motivo;
        box.appendChild(hdr); box.appendChild(bdy); ov.appendChild(box); D.body.appendChild(ov);
        cls.addEventListener('click',function(){ov.remove();}); ov.addEventListener('click',function(ev){if(ev.target===ov)ov.remove();});
    });
    D.addEventListener('click', function(e) {
        var btn = e.target && e.target.closest ? e.target.closest('._datos_btn') : null;
        if(!btn) return;
        var ep=btn.getAttribute('data-ep')||''; var cli={};
        try{cli=(typeof CLI_DATA!=='undefined'?CLI_DATA:{})[ep]||{};}catch(ex){}
        function _svg(p,c,s,m){s=s||14;c=c||'#94a3b8';return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin:'+(m||'0 7px 0 0')+';flex-shrink:0;">'+p+'</svg>';}
        var IC={
            rut:'<rect width="18" height="14" x="3" y="5" rx="2"/><path d="M7 9h4M7 13h2"/><circle cx="15.5" cy="11" r="1.5"/>',
            phone:'<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72c.13.96.36 1.9.7 2.81a2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45c.91.34 1.85.57 2.81.7A2 2 0 0 1 22 16.92z"/>',
            mail:'<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
            home:'<path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>',
            city:'<path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4M10 10h4M10 14h4M10 18h4"/>',
            map:'<polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" x2="9" y1="3" y2="18"/><line x1="15" x2="15" y1="6" y2="21"/>',
            building:'<rect width="16" height="20" x="4" y="2" rx="2"/><path d="M9 22v-4h6v4M8 6h.01M12 6h.01M16 6h.01M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M16 14h.01"/>',
            pin:'<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
            copy:'<rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
            user:'<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
            badge:'<path d="M20 7h-9M14 17H5M17 3a3 3 0 0 0 0 6M7 21a3 3 0 0 0 0-6"/>'
        };
        // Escape XSS: los datos del cliente pueden traer <script> etc. almacenado.
        function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
        var ex2=D.getElementById('_datos_modal'); if(ex2) ex2.remove();
        var ov=D.createElement('div'); ov.id='_datos_modal';
        ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center;';
        var box=D.createElement('div'); box.style.cssText='background:#1e293b;border:1px solid #334155;border-radius:16px;padding:24px 28px;max-width:440px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);';
        var hdr=D.createElement('div'); hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;gap:10px;';
        var ttl=D.createElement('div'); ttl.style.cssText='font-size:0.98rem;font-weight:900;color:#f1f5f9;display:flex;align-items:center;';
        ttl.innerHTML=_svg(IC.user,'#a5b4fc',18)+'Datos del cliente &mdash; <span class="_dcopy" data-copy="'+esc(ep)+'" title="Click para copiar" style="cursor:pointer;color:#93c5fd;margin-left:5px;text-decoration:underline dotted;">'+esc(ep)+'</span>';
        var cls=D.createElement('button'); cls.innerHTML=_svg('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>','#94a3b8',15,'0')+'';
        cls.style.cssText='background:rgba(100,116,139,0.2);color:#94a3b8;border:1px solid rgba(100,116,139,0.3);border-radius:8px;padding:5px 8px;cursor:pointer;line-height:0;flex-shrink:0;';
        cls.title='Cerrar';
        hdr.appendChild(ttl); hdr.appendChild(cls);
        // Perfil del ejecutivo a cargo (foto 100x100 + nombre)
        var prof=D.createElement('div'); prof.style.cssText='display:flex;flex-direction:column;align-items:center;gap:9px;margin-bottom:16px;';
        prof.innerHTML=(cli.asesor_avatar||'')
            +'<div style="text-align:center;">'
            +'<div style="font-size:0.95rem;font-weight:800;color:#f1f5f9;font-family:\\'Plus Jakarta Sans\\',sans-serif;">'+esc(cli.asesor||'—')+'</div>'
            +'<div style="font-size:0.64rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.07em;display:flex;align-items:center;justify-content:center;margin-top:2px;">'+_svg(IC.badge,'#94a3b8',12,'0 5px 0 0')+'Ejecutivo a cargo</div>'
            +'</div>';
        var bdy=D.createElement('div'); bdy.style.cssText='background:#0f172a;border-radius:10px;padding:12px 14px;font-size:0.88rem;color:#e2e8f0;';
        var rows=[['user','Nombre',cli.nombre],['rut','RUT',cli.rut],['phone','Teléfono',cli.tel],['mail','Email',cli.email],
                  ['home','Dirección',cli.dir],['city','Comuna',cli.comuna],['map','Región',cli.region],
                  ['building','Empresa',cli.empresa],['rut','RUT empresa',cli.rut_empresa],
                  ['pin','Dir. instalación',cli.inst_dir],['city','Comuna inst.',cli.inst_comuna],['map','Región inst.',cli.inst_region]];
        var html='<table style="width:100%;border-collapse:collapse;">';
        rows.forEach(function(r){if(!r[2])return;var v=String(r[2]).replace(/"/g,'&quot;');
            html+='<tr>'
                +'<td style="color:#94a3b8;font-size:0.76rem;padding:5px 12px 5px 0;white-space:nowrap;vertical-align:top;">'+_svg(IC[r[0]])+r[1]+'</td>'
                +'<td class="_dcopy" data-copy="'+v+'" title="Click para copiar" style="padding:5px 0;cursor:pointer;">'
                +'<div style="display:flex;align-items:center;gap:8px;">'
                +'<span style="color:#f1f5f9;font-weight:600;word-break:break-all;overflow-wrap:anywhere;">'+esc(r[2])+'</span>'
                +_svg(IC.copy,'#475569',13,'0')+'</div></td></tr>';
        });
        html+='</table>'; bdy.innerHTML=html;
        if(cli.modelo){
            var mdl=D.createElement('div'); mdl.style.cssText='margin-top:14px;padding-top:12px;border-top:1px solid #334155;';
            mdl.innerHTML='<div style="font-size:0.7rem;font-weight:800;color:#94a3b8;letter-spacing:0.06em;text-transform:uppercase;margin-bottom:3px;font-family:Montserrat,sans-serif;">Modelo predefinido</div>'
                +'<div class="_dcopy" data-copy="'+String(cli.modelo).replace(/"/g,'&quot;')+'" title="Click para copiar" style="display:flex;align-items:center;gap:8px;font-size:1.05rem;font-weight:900;color:#fbbf24;font-family:Montserrat,sans-serif;letter-spacing:0.02em;cursor:pointer;"><span style="word-break:break-word;">'+esc(cli.modelo)+'</span>'+_svg(IC.copy,'#a16207',13,'0')+'</div>';
            bdy.appendChild(mdl);
        }
        // Copiar al click en cualquier celda ._dcopy (RUT, teléfono, EP, etc.)
        box.addEventListener('click',function(ev){
            var c=ev.target&&ev.target.closest?ev.target.closest('._dcopy'):null; if(!c)return;
            var txt=c.getAttribute('data-copy')||''; if(!txt)return;
            try{var ta=D.createElement('textarea');ta.value=txt;ta.style.cssText='position:fixed;top:-9999px;left:-9999px;';D.body.appendChild(ta);ta.focus();ta.select();try{D.execCommand('copy');}catch(_e){}ta.remove();}catch(_e2){}
            if(window.parent.navigator&&window.parent.navigator.clipboard)window.parent.navigator.clipboard.writeText(txt).catch(function(){});
            var oc=c.style.color; c.style.color='#10b981'; var ot=c.getAttribute('title'); c.setAttribute('title','¡Copiado!');
            clearTimeout(c._ct); c._ct=setTimeout(function(){c.style.color=oc||'';if(ot)c.setAttribute('title',ot);},1000);
        });
        box.appendChild(hdr); box.appendChild(prof); box.appendChild(bdy); ov.appendChild(box); D.body.appendChild(ov);
        cls.addEventListener('click',function(){ov.remove();}); ov.addEventListener('click',function(ev){if(ev.target===ov)ov.remove();});
    });
    D.addEventListener('click', function(e) {
        var btn = e.target && e.target.closest ? e.target.closest('._mat_btn') : null;
        if(!btn) return; e.stopPropagation();
        var ep=btn.getAttribute('data-ep')||''; var mat={};
        try{mat=(typeof MAT_DATA!=='undefined'?MAT_DATA:{})[ep]||{};}catch(ex){}
        var cli={}; try{cli=(typeof CLI_DATA!=='undefined'?CLI_DATA:{})[ep]||{};}catch(_e){}
        function _svg(p,c,s,m){s=s||14;c=c||'#94a3b8';return '<svg width="'+s+'" height="'+s+'" viewBox="0 0 24 24" fill="none" stroke="'+c+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin:'+(m||'0 7px 0 0')+';flex-shrink:0;">'+p+'</svg>';}
        function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
        var IC={
            mats:'<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect width="8" height="4" x="8" y="2" rx="1"/><path d="M9 12h6M9 16h6"/>',
            x:'<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
            zoom:'<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/><line x1="11" x2="11" y1="8" y2="14"/><line x1="8" x2="14" y1="11" y2="11"/>',
            check:'<path d="M20 6 9 17l-5-5"/>',
            square:'<rect width="18" height="18" x="3" y="3" rx="2"/>',
            tag:'<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>',
            badge:'<path d="M20 7h-9M14 17H5M17 3a3 3 0 0 0 0 6M7 21a3 3 0 0 0 0-6"/>'
        };
        if(!D.getElementById('_matmodal_css')){var stl=D.createElement('style');stl.id='_matmodal_css';
            stl.textContent='.mm-cat{margin-bottom:16px;}.mm-cat-t{font-size:0.72rem;font-weight:800;color:#60a5fa;text-transform:uppercase;letter-spacing:0.07em;margin-bottom:9px;border-bottom:1px solid rgba(96,165,250,0.2);padding-bottom:5px;}.mm-grp{margin-bottom:13px;}.mm-grp-t{display:flex;align-items:center;font-size:0.8rem;font-weight:700;color:#cbd5e1;margin-bottom:8px;}.mm-vals{display:flex;flex-wrap:wrap;gap:12px;}.mm-val{width:100px;}.mm-thumb{position:relative;width:100px;height:100px;border-radius:12px;overflow:hidden;border:1px solid #334155;background:#0f172a;display:flex;align-items:center;justify-content:center;}.mm-thumb img{width:100%;height:100%;object-fit:cover;display:block;}.mm-zoom{position:absolute;bottom:5px;right:5px;width:26px;height:26px;border-radius:8px;border:none;background:rgba(15,23,42,0.8);display:flex;align-items:center;justify-content:center;cursor:pointer;transition:background .15s;}.mm-zoom:hover{background:#2563eb;}.mm-name{margin-top:6px;font-size:0.74rem;font-weight:600;color:#e2e8f0;text-align:center;line-height:1.25;word-break:break-word;}.mm-empty{font-size:0.8rem;color:#64748b;padding:2px 0;}';
            D.head.appendChild(stl);}
        var ex2=D.getElementById('_mat_modal'); if(ex2) ex2.remove();
        var ov=D.createElement('div'); ov.id='_mat_modal';
        ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:99999;display:flex;align-items:center;justify-content:center;';
        var box=D.createElement('div'); box.style.cssText='background:#1e293b;border:1px solid #334155;border-radius:16px;padding:24px 28px;max-width:560px;width:92%;max-height:84vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.5);';
        var hdr=D.createElement('div'); hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;gap:10px;';
        var ttl=D.createElement('div'); ttl.style.cssText='font-size:0.98rem;font-weight:900;color:#f1f5f9;display:flex;align-items:center;'; ttl.innerHTML=_svg(IC.mats,'#a5b4fc',18)+'Materiales &mdash; '+ep;
        var cls=D.createElement('button'); cls.innerHTML=_svg(IC.x,'#a5b4fc',15,'0'); cls.title='Cerrar';
        cls.style.cssText='background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.3);border-radius:8px;padding:5px 8px;cursor:pointer;line-height:0;flex-shrink:0;';
        hdr.appendChild(ttl); hdr.appendChild(cls);
        var prof=D.createElement('div'); prof.style.cssText='display:flex;flex-direction:column;align-items:center;gap:9px;margin-bottom:14px;';
        prof.innerHTML=(cli.asesor_avatar||'')+'<div style="text-align:center;"><div style="font-size:0.95rem;font-weight:800;color:#f1f5f9;">'+esc(cli.asesor||'—')+'</div><div style="font-size:0.64rem;font-weight:700;color:#94a3b8;text-transform:uppercase;letter-spacing:0.07em;display:flex;align-items:center;justify-content:center;margin-top:2px;">'+_svg(IC.badge,'#94a3b8',12,'0 5px 0 0')+'Ejecutivo a cargo</div></div>';
        var pct=mat.pct||0; var pc=pct===100?'#16a34a':(pct>=50?'#f97316':'#2563eb');
        var pb=D.createElement('div'); pb.style.cssText='background:#0f172a;border-radius:8px;padding:10px 12px;margin-bottom:16px;';
        pb.innerHTML='<div style="background:#1e293b;border-radius:4px;height:6px;margin-bottom:6px;"><div style="background:'+pc+';border-radius:4px;height:6px;width:'+pct+'%;"></div></div><div style="font-size:0.78rem;color:#94a3b8;">'+(mat.done||0)+' de '+(mat.total||0)+' secciones &mdash; '+pct+'%</div>';
        function matVal(v){
            var thumb;
            if(v.img){thumb='<div class="mm-thumb"><img src="'+esc(v.img)+'" loading="lazy"><button class="mm-zoom _matzoom" data-img="'+esc(v.img)+'" data-name="'+esc(v.n)+'" title="Ampliar imagen">'+_svg(IC.zoom,'#fff',15,'0')+'</button></div>';}
            else if(v.hex){thumb='<div class="mm-thumb" style="background:'+esc(v.hex)+';"></div>';}
            else{thumb='<div class="mm-thumb">'+_svg(IC.tag,'#475569',26,'0')+'</div>';}
            return '<div class="mm-val">'+thumb+'<div class="mm-name">'+esc(v.n)+'</div></div>';
        }
        function matGrp(g){
            var vals=g.vals||[];
            var inner=vals.length?'<div class="mm-vals">'+vals.map(matVal).join('')+'</div>':'<div class="mm-empty">&mdash; sin selección</div>';
            var ok=vals.length>0;
            return '<div class="mm-grp"><div class="mm-grp-t">'+_svg(ok?IC.check:IC.square,ok?'#22c55e':'#475569',15,'0 6px 0 0')+'<span>'+esc(g.tg)+'</span></div>'+inner+'</div>';
        }
        var bdy=D.createElement('div'); var cats=mat.cats||[];
        if(!cats.length){bdy.innerHTML='<div style="color:#64748b;font-size:0.9rem;text-align:center;padding:20px 0;">Sin datos aún</div>';}
        else{var h='';cats.forEach(function(c){h+='<div class="mm-cat"><div class="mm-cat-t">'+esc(c.cat)+'</div>';(c.grupos||[]).forEach(function(g){h+=matGrp(g);});h+='</div>';});bdy.innerHTML=h;}
        // Lupa → lightbox con la imagen grande
        box.addEventListener('click',function(ev){
            var z=ev.target&&ev.target.closest?ev.target.closest('._matzoom'):null; if(!z)return;
            ev.stopPropagation();
            var img=z.getAttribute('data-img'); var nm=z.getAttribute('data-name')||'';
            var lb=D.createElement('div'); lb.id='_mat_lightbox';
            lb.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.88);z-index:100001;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:14px;cursor:zoom-out;';
            lb.innerHTML='<img src="'+esc(img)+'" style="max-width:90vw;max-height:80vh;border-radius:14px;box-shadow:0 20px 60px rgba(0,0,0,0.6);">'+(nm?'<div style="color:#fff;font-family:sans-serif;font-weight:700;font-size:1rem;">'+esc(nm)+'</div>':'');
            lb.addEventListener('click',function(){lb.remove();});
            D.body.appendChild(lb);
        });
        box.appendChild(hdr); box.appendChild(prof); box.appendChild(pb); box.appendChild(bdy); ov.appendChild(box); D.body.appendChild(ov);
        cls.addEventListener('click',function(){ov.remove();}); ov.addEventListener('click',function(ev){if(ev.target===ov)ov.remove();});
    });
    function _liveIcon(name,color){
        var p={'alert':'<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>','clock':'<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>','check':'<path d="M20 6 9 17l-5-5"/>'}[name]||'';
        return '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="'+color+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-1px;margin-right:3px;">'+p+'</svg>';
    }
    function updateLiveTimers(){
        D.querySelectorAll('.demora-live').forEach(function(el){
            var desde=parseInt(el.getAttribute('data-desde')); if(!desde) return;
            var diff=Date.now()-desde; var s=Math.floor(diff/1000); var m=Math.floor(s/60); var h=Math.floor(m/60); var d=Math.floor(h/24);
            s=s%60;m=m%60;h=h%24; var txt=''; if(d>0)txt+=d+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.textContent=txt;
        });
        D.querySelectorAll('.fab-live').forEach(function(el){
            var desde=parseInt(el.getAttribute('data-desde')); if(!desde) return;
            var diff=Date.now()-desde; var s=Math.floor(diff/1000); var m=Math.floor(s/60); var h=Math.floor(m/60); var d=Math.floor(h/24);
            s=s%60;m=m%60;h=h%24; var txt=''; if(d>0)txt+=d+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.textContent=txt;
        });
        D.querySelectorAll('.retraso-live').forEach(function(el){
            var desde=parseInt(el.getAttribute('data-desde')); if(!desde) return;
            var diff=Date.now()-desde; var s=Math.floor(diff/1000); var m=Math.floor(s/60); var h=Math.floor(m/60); var d=Math.floor(h/24);
            s=s%60;m=m%60;h=h%24; var txt=''; if(d>0)txt+=d+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.innerHTML=_liveIcon('alert','#dc2626')+txt;
        });
        D.querySelectorAll('.fidel-live').forEach(function(el){
            var hasta=parseInt(el.getAttribute('data-hasta')); var plazo=parseInt(el.getAttribute('data-plazo'))||1; var adjTs=parseInt(el.getAttribute('data-adj'))||0;
            if(!hasta) return; var diff=hasta-Date.now();
            if(diff<=0){el.innerHTML=_liveIcon('alert','#dc2626')+'VENCIDO';el.style.color='#dc2626';return;}
            var ts=Math.floor(diff/1000); var dc=Math.floor(ts/86400); var rs=ts%86400; var h=Math.floor(rs/3600); var m=Math.floor((rs%3600)/60); var s=rs%60;
            var tr=adjTs?(Date.now()-adjTs):0; var tot=plazo*86400000; var pa=adjTs?Math.min((tr/tot)*100,100):0;
            var col=pa<50?'#16a34a':(pa<80?'#f97316':'#dc2626'); el.style.color=col;
            var txt=''; if(dc>0)txt+=dc+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.innerHTML=_liveIcon('clock',col)+txt;
            var pe=el.nextElementSibling; if(pe&&pe.style!==undefined){pe.textContent=pa.toFixed(2)+'%';pe.style.color=col;}
        });
    }
    setInterval(updateLiveTimers,1000); updateLiveTimers();
    function initEPCopy(){
        D.addEventListener('click',function(e){
            var td=e.target&&e.target.closest?e.target.closest('td[data-ep]'):null; if(!td) return;
            var ep=td.getAttribute('data-ep'); if(!ep) return;
            var ta=D.createElement('textarea'); ta.value=ep; ta.style.cssText='position:fixed;top:-9999px;left:-9999px;'; D.body.appendChild(ta); ta.focus(); ta.select();
            try{D.execCommand('copy');}catch(err){}; ta.remove();
            if(window.parent.navigator.clipboard) window.parent.navigator.clipboard.writeText(ep).catch(function(){});
            var orig=td.innerHTML; var origColor=td.style.color; td.innerHTML=_liveIcon('check','#10b981')+'&#161;Copiado!'; td.style.color='#10b981';
            setTimeout(function(){td.innerHTML=orig;td.style.color=origColor;},1200);
        });
    }
    setTimeout(initEPCopy,500);
})();
</script>""", height=0)

        # ── Menú contextual (click derecho) — reemplaza el dropdown lento ─────────
        # El menú aparece AL INSTANTE (client-side, banderas por fila en data-*). Cada
        # acción escribe "accion|ep|nonce" en este text_input oculto + blur → UN rerun
        # LIGERO que genera SOLO ese documento y lo auto-descarga. No hay selectbox ni
        # pre-generación de 4 PDFs por rerun (el cuello de botella anterior).
        st.markdown('<style>.st-key-_ctx_cmd,.st-key-_ctx_dl{position:absolute!important;'
            'left:-9999px!important;top:-9999px!important;width:240px!important;height:0!important;'
            'overflow:hidden!important;}</style>', unsafe_allow_html=True)
        st.text_input('ctx', key='_ctx_cmd', label_visibility='collapsed')
        _ctx_raw = str(st.session_state.get('_ctx_cmd', '') or '')
        _ctx_action = ''; _ctx_ep = ''
        if _ctx_raw.count('|') >= 2:
            _a, _e, _n = _ctx_raw.split('|', 2)
            if _n and _n != st.session_state.get('_ctx_done', ''):
                st.session_state['_ctx_done'] = _n
                _ctx_action = _a.strip(); _ctx_ep = _e.strip()

        def _ctx_prep(cot):
            _df = pd.DataFrame(cot['productos'])
            if not _df.empty and 'Categoria' in _df.columns:
                _df = _df.sort_values(['Categoria', 'Item'], ignore_index=True)
            _mg = cot.get('config_margen', 0)
            if _mg and _mg > 0:
                _df = _df.copy()
                _df["Precio Unitario"] = _df["Precio Unitario"].apply(lambda x: aplicar_margen(x, _mg))
                _df["Subtotal"] = _df["Cantidad"] * _df["Precio Unitario"]
            _sub = _df["Subtotal"].sum(); _iva = _sub * 0.19; _tot = _sub + _iva
            _dc = {
                "Nombre": cot.get('cliente_nombre',''), "RUT": cot.get('cliente_rut',''),
                "Correo": cot.get('cliente_email',''),
                "Tel&#233;fono": formatear_telefono(cot.get('cliente_telefono','')),
                "Direcci&#243;n": cot.get('cliente_direccion',''),
                "ComunaCliente": cot.get('cliente_comuna',''), "RegionCliente": cot.get('cliente_region',''),
                "DireccionProyecto": cot.get('proyecto_direccion',''),
                "ComunaProyecto": cot.get('proyecto_comuna',''), "RegionProyecto": cot.get('proyecto_region',''),
                "TipoCliente": cot.get('cliente_tipo','natural'), "EmpresaCliente": cot.get('cliente_empresa',''),
                "RutEmpresa": cot.get('cliente_rut_empresa',''), "Observaciones": cot.get('proyecto_observaciones',''),
            }
            _da = {
                "Nombre Ejecutivo": cot.get('asesor_nombre',''),
                "Correo Ejecutivo": cot.get('asesor_email',''),
                "Tel&#233;fono Ejecutivo": formatear_telefono(cot.get('asesor_telefono','')),
            }
            _fi = datetime.strptime(cot.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
            _ft = datetime.strptime(cot.get('proyecto_fecha_termino', (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
            _dv = cot.get('proyecto_dias_validez', 15)
            return _df, _sub, _iva, _tot, _dc, _da, _fi, _ft, _dv, _mg

        def _ctx_gen(doc, ep, cot):
            """Genera/obtiene (bytes, filename, mime) del documento pedido, o None.
            Compartido por la descarga (menú) y el visor de documentos (drawer)."""
            if doc == 'pdf_completo':
                _df,_sub,_iva,_tot,_dc,_da,_fi,_ft,_dv,_mg = _ctx_prep(cot)
                _b,_ = generar_pdf_completo(_df,_sub,_iva,_tot,_dc,_fi,_ft,_dv,_da,margen=_mg,numero_cotizacion=ep)
                return (_b, f"Presupuesto_Completo_{ep}.pdf", "application/pdf")
            if doc == 'pdf_cliente':
                _df,_sub,_iva,_tot,_dc,_da,_fi,_ft,_dv,_mg = _ctx_prep(cot)
                _desc = cargar_descripciones_por_ep(ep, supa_url, bust_cache=True)
                _b,_ = generar_pdf_cliente(_df,_sub,_iva,_tot,_dc,_fi,_ft,_dv,_da,margen=_mg,numero_cotizacion=ep,descripciones_ep=_desc)
                return (_b, f"Presupuesto_Cliente_{ep}.pdf", "application/pdf")
            if doc == 'pdf_compras':
                _dfr = pd.DataFrame(cot['productos'])
                _dfc = _dfr[_dfr['Categoria'].str.strip().str.lower() != 'varios'].copy()
                _sub = _dfc['Subtotal'].sum(); _iva = _sub*0.19; _tot = _sub+_iva
                _dc = {
                    "Nombre": cot.get('cliente_nombre',''), "RUT": cot.get('cliente_rut',''),
                    "Correo": cot.get('cliente_email',''),
                    "Tel&#233;fono": formatear_telefono(cot.get('cliente_telefono','')),
                    "Direcci&#243;n": cot.get('cliente_direccion',''),
                    "ComunaCliente": cot.get('cliente_comuna',''), "RegionCliente": cot.get('cliente_region',''),
                    "DireccionProyecto": cot.get('proyecto_direccion',''),
                    "ComunaProyecto": cot.get('proyecto_comuna',''), "RegionProyecto": cot.get('proyecto_region',''),
                    "TipoCliente": cot.get('cliente_tipo','natural'), "EmpresaCliente": cot.get('cliente_empresa',''),
                    "RutEmpresa": cot.get('cliente_rut_empresa',''), "Observaciones": cot.get('proyecto_observaciones',''),
                }
                _da = {
                    "Nombre Ejecutivo": cot.get('asesor_nombre',''),
                    "Correo Ejecutivo": cot.get('asesor_email',''),
                    "Tel&#233;fono Ejecutivo": formatear_telefono(cot.get('asesor_telefono','')),
                }
                _fic = datetime.strptime(cot.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                _ftc = datetime.strptime(cot.get('proyecto_fecha_termino', (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                _dvc = cot.get('proyecto_dias_validez', 15)
                _fadj = cot.get('fecha_adjudicacion') or None
                _ffid = cot.get('fecha_entrega') or None
                try:
                    _cdr = cot.get('contrato_datos') or {}
                    if isinstance(_cdr, str): _cdr = json.loads(_cdr)
                    _plz = int(_cdr.get('plazo_dias', 45) or 45)
                except Exception:
                    _plz = 45
                _b,_ = generar_pdf_completo(_dfc,_sub,_iva,_tot,_dc,_fic,_ftc,_dvc,_da,margen=0,
                    numero_cotizacion=ep,mostrar_precios=True,
                    fecha_adjudicacion=_fadj,fecha_fidelizacion=_ffid,plazo_obra_dias=_plz)
                return (_b, f"Compras_{ep}.pdf", "application/pdf")
            if doc == 'pdf_seleccion':
                _cfg = _fetch_formulario_config(ep)
                if not _cfg:
                    return None
                _rr = supabase_admin.table('formulario_respuestas').select('item_id,respuesta').eq('cotizacion_numero', ep).execute().data or []
                _res = {r['item_id']: r['respuesta'] for r in _rr if r.get('item_id')}
                _ids = [str(i) for c in _cfg for i in (c.get('item_ids') or [])]
                _mit = {}
                if _ids:
                    _m = supabase_admin.table('catalogo_materiales').select('id,nombre,imagen_url,hex,tipo').in_('id', _ids).execute().data or []
                    _mit = {str(x['id']): x for x in _m}
                _fecha = ''
                try:
                    _fc = cot.get('fecha_formulario_completado','')
                    if _fc: _fecha = datetime.fromisoformat(_fc[:19]).strftime('%d/%m/%Y')
                except Exception:
                    pass
                if not _fecha: _fecha = datetime.now().strftime('%d/%m/%Y')
                _b = generar_pdf_seleccion_cliente(ep, cot.get('cliente_nombre',''), _cfg, _res, _mit, fecha_formulario=_fecha)
                return (_b, f"Seleccion_Cliente_{ep}.pdf", "application/pdf")
            if doc == 'plano':
                _pu = cot.get('plano_url')
                if not _pu:
                    return None
                _pb = _fetch_plano_bytes(_pu)
                if not _pb:
                    return None
                _pn = cot.get('plano_nombre') or f"Plano_{ep}.pdf"
                _pm = 'application/pdf' if str(_pn).lower().endswith('.pdf') else 'application/octet-stream'
                return (_pb, _pn, _pm)
            if doc == 'contrato':
                if not cot.get('contrato_generado'):
                    return None
                from utils.pdf_contrato import generar_pdf_contrato, _obtener_clausulas_contrato
                _raw_c = cot.get('contrato_datos', '{}')
                try:
                    _datos_c = json.loads(_raw_c) if isinstance(_raw_c, str) else (_raw_c or {})
                except Exception:
                    _datos_c = {}
                _cls_c = _obtener_clausulas_contrato(cot.get('modelo_predefinido'), supabase_admin)
                _bc = generar_pdf_contrato(_datos_c, clausulas_externas=_cls_c)
                return (_bc, f"Contrato_{ep}.pdf", "application/pdf")
            if doc == 'pdf_modificaciones':
                _bm = generar_pdf_log(ep, obtener_logs_ep(ep))
                return (_bm, f"Modificaciones_{ep}.pdf", "application/pdf")
            return None

        _ctx_dl = None  # (bytes, filename, mime) del documento pedido
        if _ctx_action and _ctx_ep:
            if _ctx_action == 'cargar':
                if preparar_carga_cotizacion(_ctx_ep):
                    st.session_state.nav_page = 'presupuesto'
                    st.session_state['_toast_cargado'] = _ctx_ep
                    st.rerun()
            elif _ctx_action == 'rechazar':
                # Abre el diálogo de motivo (se renderiza más abajo este mismo run).
                st.session_state['_show_rechazo_dialog'] = _ctx_ep
            elif _ctx_action == 'quitar_rechazo':
                try:
                    supabase_admin.table("cotizaciones").update(
                        {"motivo_rechazo": None, "fecha_rechazo": None}).eq("numero", _ctx_ep).execute()
                    _rechazo_status_cached.clear()
                    st.session_state.resultados_busqueda = None
                    st.toast(f"Rechazo eliminado en {_ctx_ep}", icon=":material/undo:")
                    st.rerun()
                except Exception as _qre:
                    st.toast(f"No se pudo quitar el rechazo: {_qre}", icon=":material/error:")
            elif _ctx_action == 'ver' or _ctx_action.startswith('preview_'):
                # Abre/cambia el visor de documentos (drawer). doc='' => elige el default.
                _pv_doc = _ctx_action[len('preview_'):] if _ctx_action.startswith('preview_') else ''
                st.session_state['_preview'] = {'ep': _ctx_ep, 'doc': _pv_doc}
            else:
                try:
                    _cot = cargar_cotizacion(_ctx_ep)
                    if _cot:
                        _ctx_dl = _ctx_gen(_ctx_action, _ctx_ep, _cot)
                except Exception as _ctxe:
                    st.toast(f"No se pudo generar el documento: {_ctxe}", icon=":material/error:")

        # Descarga: botón oculto con los bytes + auto-click (misma pestaña, sin recargar).
        # (st.download_button NO acepta label_visibility → el botón se oculta por CSS
        #  con .st-key-_ctx_dl, no por el parámetro.)
        if _ctx_dl is not None:
            st.download_button('descarga', data=_ctx_dl[0], file_name=_ctx_dl[1], mime=_ctx_dl[2],
                               key='_ctx_dl')
            components.html("""<script>(function(){var D=window.parent.document;
  setTimeout(function(){var b=D.querySelector('.st-key-_ctx_dl button'); if(b) b.click();},60);})();</script>""", height=0)

        # Diálogo de rechazo (lo dispara el ítem "Rechazar" del menú → _show_rechazo_dialog).
        _rej_ep = st.session_state.get('_show_rechazo_dialog')
        if _rej_ep:
            @st.dialog("Motivo de rechazo")
            def _dlg_rechazo_ctx():
                st.markdown(f"**Presupuesto:** {_rej_ep}")
                _motivo_in = st.text_area(
                    "Describe el motivo del rechazo",
                    placeholder="Ej: Cliente desisti&#243; por cambio de presupuesto personal...",
                    key="motivo_rechazo_input", height=120)
                _rc1, _rc2 = st.columns(2)
                with _rc1:
                    if st.button("Cancelar", use_container_width=True, key="btn_rec_cancel"):
                        st.session_state.pop('_show_rechazo_dialog', None)
                        st.rerun()
                with _rc2:
                    if st.button("Confirmar rechazo", type="primary", use_container_width=True, key="btn_rec_confirm"):
                        if _motivo_in.strip():
                            try:
                                supabase_admin.table("cotizaciones").update({
                                    "motivo_rechazo": _motivo_in.strip(),
                                    "fecha_rechazo": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                                }).eq("numero", _rej_ep).execute()
                                _rechazo_status_cached.clear()
                                st.session_state.pop('_show_rechazo_dialog', None)
                                st.session_state.resultados_busqueda = None
                                st.toast(f"{_rej_ep} marcado como rechazado", icon=":material/block:")
                                st.rerun()
                            except Exception as _rce:
                                st.warning(f"No se pudo rechazar: {_rce}")
                        else:
                            st.warning("Debes ingresar un motivo.")
            _dlg_rechazo_ctx()

        # ── Visor de documentos (panel deslizante desde la derecha) ──────────────
        # Se abre con "Ver documentos" del menú. Pestañas = documentos disponibles y
        # PERMITIDOS por rol. Plano se ve por URL (instantáneo); los PDF se generan al
        # abrir su pestaña (rerun ligero) y se muestran como data-URL en PDF.js.
        _preview = st.session_state.get('_preview')
        if _preview and _preview.get('ep'):
            # CSS del panel: FUERA del fragment (estatico) para que persista en los
            # reruns del fragment. El width del iframe se ancla al viewport (mismo vw
            # del panel) porque el bloque interno de Streamlit no se reduce al 50vw.
            st.markdown(
                "<style>"
                ".st-key-ec_drawer{position:fixed!important;top:0;right:0;height:100vh!important;width:50vw!important;"
                "min-width:400px;z-index:1000000!important;background:#fff!important;"
                "box-shadow:-16px 0 44px rgba(15,23,42,0.24)!important;border-left:1px solid #e2e8f0!important;"
                "overflow:hidden!important;padding:14px 18px!important;}"
                ".st-key-ec_drawer [data-testid='stVerticalBlockBorderWrapper']{box-shadow:none!important;background:transparent!important;}"
                ".st-key-_pv_close,.st-key-_pv_cmd{position:absolute!important;left:-9999px!important;top:-9999px!important;height:0!important;overflow:hidden!important;}"
                "#_ec_pv_backdrop{position:fixed;inset:0;background:rgba(15,23,42,0.42);z-index:999998;}"
                ".pvhead{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;}"
                ".pvkick{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:#94a3b8;font-weight:800;}"
                ".pvtitle{font-size:15px;font-weight:800;color:#0f172a;margin-top:1px;}"
                ".pvx{width:32px;height:32px;border-radius:9px;border:1px solid #e2e8f0;background:#fff;color:#64748b;"
                "display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex-shrink:0;}"
                ".pvx:hover{background:#f1f5f9;color:#0f172a;}"
                ".pvtabs{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px;}"
                ".pvtab{display:inline-flex;align-items:center;gap:7px;font-family:Montserrat,sans-serif;font-weight:800;"
                "font-size:11.5px;letter-spacing:.03em;text-transform:uppercase;border:1px solid #e2e8f0;border-radius:99px;"
                "padding:7px 14px;cursor:pointer;background:#fff;color:#334155;white-space:nowrap;transition:all .12s;}"
                ".pvtab:hover{background:#f1f5f9;}"
                ".pvtab.on{background:#dbeafe;color:#1d4ed8;border-color:#93c5fd;}"
                ".pverr{background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;border-radius:10px;padding:16px;"
                "font-size:0.86rem;line-height:1.5;}"
                ".st-key-ec_drawer iframe{width:calc(50vw - 40px)!important;max-width:calc(50vw - 40px)!important;"
                "height:calc(100vh - 150px)!important;min-height:320px!important;border:1px solid #e2e8f0!important;"
                "border-radius:10px!important;display:block!important;}"
                "</style>", unsafe_allow_html=True)

            @st.fragment
            def _pv_fragment():
                import base64 as _b64pv
                _pv0 = st.session_state.get('_preview')
                if not _pv0 or not _pv0.get('ep'):
                    return
                _pv_ep = str(_pv0['ep'])
                # Bridge de PESTANA dentro del fragment: cambiar de documento rerun SOLO
                # el fragment (no la pagina) => sin flash ni reconstruir la tabla de 88 filas.
                st.text_input('pvc', key='_pv_cmd', label_visibility='collapsed')
                _pvraw = str(st.session_state.get('_pv_cmd', '') or '')
                if _pvraw.count('|') >= 2:
                    _pa, _pe, _pn = _pvraw.split('|', 2)
                    if _pn and _pn != st.session_state.get('_pv_done', '') and _pa.startswith('preview_'):
                        st.session_state['_pv_done'] = _pn
                        st.session_state['_preview']['doc'] = _pa[len('preview_'):]

                _pv_cot = cargar_cotizacion(_pv_ep)
                _pvc = _pv_cot or {}
                _pv_es_ej = _rol_actual == 'ejecutivo'
                _pv_margen = float(_pvc.get('config_margen', 0) or 0)
                _pv_datos = bool(_pvc.get('cliente_nombre') and _pvc.get('cliente_email'))
                _pv_ase = bool(_pvc.get('asesor_nombre') or _pvc.get('asesor_email') or _pvc.get('asesor_telefono'))
                _pv_autoriz = (_pv_margen > 0 and _pv_datos and _pv_ase)
                _pv_pdf_ok = (not _pv_es_ej) or _pv_autoriz
                _pv_tiene_sel = _pv_ep in _eps_con_seleccion(
                    tuple(sorted({str(_r[0]) for _r in (st.session_state.resultados_busqueda or [])})))
                _pv_es_admin = _rol_actual in ('admin', 'root')
                _PV_ALL = [
                    ('plano',        'Plano',     bool(_pvc.get('plano_url')), '<path d="M9 6 2 3v15l7 3 6-3 7 3V6l-7-3-6 3Z"/><path d="M9 6v15"/><path d="M15 3v15"/>'),
                    ('contrato',     'Contrato',  bool(_pvc.get('contrato_generado')), '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'),
                    ('pdf_compras',  'Compras',   (not _pv_es_ej), '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>'),
                    ('pdf_completo', 'Completo',  _pv_pdf_ok, '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>'),
                    ('pdf_cliente',  'Cliente',   _pv_pdf_ok, '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'),
                    ('pdf_seleccion','Selecci&#243;n', _pv_tiene_sel, '<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'),
                    ('pdf_modificaciones', 'Modificaciones', _pv_es_admin, '<path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/>'),
                ]
                _pv_docs = [(k, l, s) for (k, l, ok, s) in _PV_ALL if ok]
                _pv_keys = [k for k, _, _ in _pv_docs]
                _pv_cur = st.session_state['_preview'].get('doc') or ''
                if _pv_cur not in _pv_keys:
                    _pv_cur = 'plano' if 'plano' in _pv_keys else (_pv_keys[0] if _pv_keys else '')
                    st.session_state['_preview']['doc'] = _pv_cur

                _pv_src = ''; _pv_err = ''
                try:
                    if _pv_cur == 'plano':
                        _pv_src = _pvc.get('plano_url') or ''
                        if not _pv_src:
                            _pv_err = 'Esta cotizaci&#243;n no tiene plano adjunto.'
                    elif not _pv_cot:
                        _pv_err = 'No se pudo cargar la cotizaci&#243;n.'
                    elif _pv_cur:
                        _pvr = _ctx_gen(_pv_cur, _pv_ep, _pv_cot)
                        if _pvr:
                            _raw = _pvr[0]
                            if hasattr(_raw, 'getvalue'):
                                _raw = _raw.getvalue()
                            elif hasattr(_raw, 'read'):
                                _raw = _raw.read()
                            _pv_src = 'data:application/pdf;base64,' + _b64pv.b64encode(_raw).decode('ascii')
                        else:
                            _pv_err = 'No hay datos suficientes para generar este documento.'
                except Exception as _pve:
                    _pv_src = ''
                    _pv_err = 'Error al generar el documento: ' + str(_pve)[:240]

                def _pv_ic(_p, _sz=15):
                    return (f'<svg width="{_sz}" height="{_sz}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">{_p}</svg>')
                _pv_x_ico = _pv_ic('<path d="M18 6 6 18"/><path d="m6 6 12 12"/>', 17)
                _pv_tabs_html = ''
                for _k, _l, _s in _pv_docs:
                    _on = ' on' if _k == _pv_cur else ''
                    _pv_tabs_html += (f'<button class="pvtab{_on}" data-doc="{_k}">' + _pv_ic(_s) + f'<span>{_l}</span></button>')
                _pv_cli_txt = str(_pvc.get('cliente_nombre', '') or '&#8212;').replace('<', '&lt;').replace('>', '&gt;')

                with st.container(key='ec_drawer'):
                    st.markdown(
                        '<div class="pvhead"><div>'
                        '<div class="pvkick">Documentos</div>'
                        '<div class="pvtitle">' + _pv_ep + ' &middot; ' + _pv_cli_txt + '</div></div>'
                        '<button id="_pv_x" class="pvx">' + _pv_x_ico + '</button></div>'
                        '<div class="pvtabs">' + _pv_tabs_html + '</div>',
                        unsafe_allow_html=True)
                    if _pv_src:
                        components.html(_PV_VIEWER.replace("__SRC__", json.dumps(_pv_src)), height=760, scrolling=False)
                    else:
                        st.markdown('<div class="pverr">' + (_pv_err or 'Documento no disponible.') + '</div>',
                                    unsafe_allow_html=True)
                    if st.button("cerrar", key='_pv_close'):
                        st.session_state.pop('_preview', None)
                        st.rerun(scope="app")  # cierra el panel (rerun de toda la app)

                # Backdrop + Esc + pestanas (escriben en _pv_cmd => rerun SOLO del fragment).
                components.html(("""<script>
(function(){
  var W=window.parent, D=W.document, EP=__EP__;
  function closeBtn(){var b=D.querySelector('.st-key-_pv_close button'); if(b) b.click();}
  function fire(action){
    var inp=D.querySelector('.st-key-_pv_cmd input'); if(!inp) return;
    try{ var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true}); setter.call(inp, action+'|'+EP+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  var ex=D.getElementById('_ec_pv_backdrop'); if(ex) ex.remove();
  var bd=D.createElement('div'); bd.id='_ec_pv_backdrop'; bd.addEventListener('click', closeBtn); D.body.appendChild(bd);
  var dr=D.querySelector('.st-key-ec_drawer');
  if(dr){
    dr.querySelectorAll('.pvtab').forEach(function(t){ t.addEventListener('click', function(){ fire('preview_'+t.getAttribute('data-doc')); }); });
    var x=dr.querySelector('#_pv_x'); if(x) x.addEventListener('click', closeBtn);
  }
  if(W._ecPvKey) D.removeEventListener('keydown', W._ecPvKey, true);
  W._ecPvKey=function(e){if(e.key==='Escape') closeBtn();};
  D.addEventListener('keydown', W._ecPvKey, true);
})();
</script>""").replace("__EP__", json.dumps(_pv_ep)), height=0)

            _pv_fragment()
        else:
            components.html("""<script>(function(){var D=window.parent.document;
  var b=D.getElementById('_ec_pv_backdrop'); if(b) b.remove();})();</script>""", height=0)

        # JS del menú: aparece AL INSTANTE (sin rerun) leyendo las banderas data-* de
        # la fila. Cada acción escribe en el bridge oculto (_ctx_cmd) → Python genera y
        # auto-descarga. Handlers deduplicados en window.parent (sobreviven al rerun).
        components.html(r"""<script>
(function(){
  var W=window.parent, D=W.document, MENU_ID='_ec_ctxmenu';
  var ITEMS=[
    {k:'ver',           lbl:'Ver documentos', attr:'ver', ico:'<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>'},
    {k:'cargar',        lbl:'Cargar presupuesto', attr:'cargar',    ico:'<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>'},
    {k:'pdf_compras',   lbl:'PDF compras',   attr:'compras',   ico:'<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>'},
    {k:'pdf_completo',  lbl:'PDF completo',  attr:'completo',  ico:'<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>'},
    {k:'pdf_cliente',   lbl:'PDF cliente',   attr:'cliente',   ico:'<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>'},
    {k:'pdf_seleccion', lbl:'PDF seleccion', attr:'seleccion', ico:'<rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>'},
    {k:'contrato',      lbl:'PDF contrato', attr:'contrato', ico:'<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>'},
    {k:'pdf_modificaciones', lbl:'PDF modificaciones', attr:'modif', ico:'<path d="M3 3v5h5"/><path d="M3.05 13A9 9 0 1 0 6 5.3L3 8"/><path d="M12 7v5l4 2"/>'},
    {k:'plano',         lbl:'Descargar plano', div:true, attr:'plano', ico:'<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>'}
  ];
  function ic(p){return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'+p+'</svg>';}
  function closeMenu(){var m=D.getElementById(MENU_ID);if(m)m.remove();}
  function fire(action,ep){
    var inp=D.querySelector('.st-key-_ctx_cmd input'); if(!inp) return;
    try{
      var setter=Object.getOwnPropertyDescriptor(W.HTMLInputElement.prototype,'value').set;
      inp.focus({preventScroll:true});
      setter.call(inp, action+'|'+ep+'|'+Date.now());
      inp.dispatchEvent(new Event('input',{bubbles:true}));
      inp.dispatchEvent(new Event('change',{bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',keyCode:13,which:13,bubbles:true}));
      inp.blur();
    }catch(e){}
  }
  function build(tr,ep,x,y){
    closeMenu();
    var m=D.createElement('div'); m.id=MENU_ID;
    m.style.cssText='position:absolute;z-index:2147483000;min-width:236px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 12px 34px rgba(15,23,42,0.18);padding:6px;font-family:-apple-system,Segoe UI,Roboto,sans-serif;';
    var hdr=D.createElement('div');
    hdr.style.cssText='display:flex;align-items:center;gap:10px;padding:8px 10px 10px;border-bottom:1px solid #f1f5f9;margin-bottom:4px;';
    var cli=tr.getAttribute('data-cli')||'', av=tr.getAttribute('data-avatar')||'', ase=tr.getAttribute('data-asesor')||'';
    if(av){
      var img=D.createElement('img'); img.src=av; img.referrerPolicy='no-referrer';
      img.style.cssText='width:50px;height:50px;border-radius:50%;object-fit:cover;flex-shrink:0;border:2px solid #e2e8f0;background:#e0e7ff;';
      hdr.appendChild(img);
    } else {
      var avd=D.createElement('div');
      avd.style.cssText='width:50px;height:50px;border-radius:50%;background:#e0e7ff;color:#4338ca;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:19px;flex-shrink:0;';
      avd.textContent=((ase||cli||'?').trim().charAt(0)||'?').toUpperCase();
      hdr.appendChild(avd);
    }
    var box=D.createElement('div'); box.style.cssText='min-width:0;';
    var t1=D.createElement('div'); t1.style.cssText='font-size:12.5px;font-weight:800;color:#0f172a;'; t1.textContent=ep;
    var t2=D.createElement('div'); t2.style.cssText='font-size:11.5px;color:#64748b;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:158px;'; t2.textContent=cli||'—';
    box.appendChild(t1); box.appendChild(t2); hdr.appendChild(box);
    m.appendChild(hdr);
    ITEMS.forEach(function(it){
      if(it.div){var dv=D.createElement('div');dv.style.cssText='height:1px;background:#f1f5f9;margin:5px 8px;';m.appendChild(dv);}
      var enabled=tr.getAttribute('data-'+it.attr)==='1';
      var row=D.createElement('div');
      row.style.cssText='display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:13px;font-weight:600;'+(enabled?'color:#0f172a;cursor:pointer;':'color:#cbd5e1;cursor:default;');
      row.innerHTML=ic(it.ico)+'<span>'+it.lbl+'</span>';
      if(enabled){
        row.addEventListener('mouseenter',function(){row.style.background='#eef2ff';});
        row.addEventListener('mouseleave',function(){row.style.background='transparent';});
        row.addEventListener('click',function(ev){ev.stopPropagation();closeMenu();fire(it.k,ep);});
      }
      m.appendChild(row);
    });
    // Rechazar / Quitar rechazo (rojo) — según data-rechazar de la fila.
    var rech=tr.getAttribute('data-rechazar');
    if(rech==='1'||rech==='quitar'){
      var dv2=D.createElement('div');dv2.style.cssText='height:1px;background:#f1f5f9;margin:5px 8px;';m.appendChild(dv2);
      var isQ=(rech==='quitar'); var col=isQ?'#b45309':'#dc2626'; var hov=isQ?'#fef3c7':'#fee2e2';
      var rrow=D.createElement('div');
      rrow.style.cssText='display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;color:'+col+';';
      var rico=isQ?'<path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 5.5 5.5 5.5 5.5 0 0 1-5.5 5.5H11"/>':'<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>';
      rrow.innerHTML=ic(rico)+'<span>'+(isQ?'Quitar rechazo':'Rechazar')+'</span>';
      rrow.addEventListener('mouseenter',function(){rrow.style.background=hov;});
      rrow.addEventListener('mouseleave',function(){rrow.style.background='transparent';});
      rrow.addEventListener('click',function(ev){ev.stopPropagation();closeMenu();fire(isQ?'quitar_rechazo':'rechazar',ep);});
      m.appendChild(rrow);
    }
    D.body.appendChild(m);
    var vw=W.innerWidth, vh=W.innerHeight;
    var sx=W.pageXOffset||D.documentElement.scrollLeft||0, sy=W.pageYOffset||D.documentElement.scrollTop||0;
    var rw=m.offsetWidth, rh=m.offsetHeight, px=x, py=y;
    if(px-sx+rw>vw) px=sx+vw-rw-8;
    if(py-sy+rh>vh) py=sy+vh-rh-8;
    m.style.left=Math.max(sx+4,px)+'px'; m.style.top=Math.max(sy+4,py)+'px';
  }
  if(W._ecCtxH) D.removeEventListener('contextmenu', W._ecCtxH, true);
  W._ecCtxH=function(e){
    var tr=e.target&&e.target.closest?e.target.closest('.resultados-table tbody tr'):null; if(!tr) return;
    var td=tr.querySelector('td[data-ep]'); if(!td) return;
    var ep=td.getAttribute('data-ep'); if(!ep) return;
    e.preventDefault();
    // Resalta la fila en azul claro para ver sobre cuál se está trabajando.
    D.querySelectorAll('.resultados-table tbody tr.ec-ctx-row').forEach(function(r){r.classList.remove('ec-ctx-row');});
    tr.classList.add('ec-ctx-row');
    build(tr, ep, e.pageX, e.pageY);
  };
  D.addEventListener('contextmenu', W._ecCtxH, true);
  if(W._ecCtxDown) D.removeEventListener('mousedown', W._ecCtxDown, true);
  W._ecCtxDown=function(e){var m=D.getElementById(MENU_ID); if(m && !m.contains(e.target)) closeMenu();};
  D.addEventListener('mousedown', W._ecCtxDown, true);
  if(W._ecCtxKey) D.removeEventListener('keydown', W._ecCtxKey, true);
  W._ecCtxKey=function(e){if(e.key==='Escape') closeMenu();};
  D.addEventListener('keydown', W._ecCtxKey, true);
})();
</script>""", height=0)

        # DROPDOWN "Seleccionar cotización" + fila de botones de acción DESCONECTADOS
        # (prueba de velocidad): eran un widget nativo lento y pre-generaban 4 PDFs en
        # CADA rerun (y los badges los filtraban junto con la tabla). Ahora las acciones
        # de cada cotización van por el MENÚ CONTEXTUAL (click derecho). Dejar `opciones`
        # vacío hace que se salte TODO el bloque `if opciones:` (dropdown + botones +
        # rechazar + historial + visor de plano). Para reactivarlo, repoblar `opciones`.
        opciones = []
        _dd_options_list = []

        if opciones:
            _sel_ep_now = st.session_state.get('selector_ep_num', '')
            if not _sel_ep_now:
                _sel_ep_now = opciones[0].split(' - ')[0]
                st.session_state['selector_ep_num'] = _sel_ep_now
            _eps_disponibles = [o['ep'] for o in _dd_options_list]
            if _sel_ep_now not in _eps_disponibles and _eps_disponibles:
                _sel_ep_now = _eps_disponibles[0]
                st.session_state['selector_ep_num'] = _sel_ep_now
            # -- Selector nativo (st.selectbox): rerun garantizado al elegir EP --
            # El dropdown-iframe NO puede disparar rerun: el sandbox de components.html
            # bloquea window.parent.location (about:srcdoc no puede navegar al padre).
            # st.selectbox es un widget nativo => al cambiar dispara rerun de Streamlit
            # automaticamente y carga detalles/PDFs de la cotizacion seleccionada.
            _ep_opts = [o['ep'] for o in _dd_options_list]
            _ep_lbl_map = {}
            for _o in _dd_options_list:
                _em = _o.get('em', '')
                _lm = _o.get('lm') or _o.get('label') or _o['ep']
                _est = _o.get('est', '')
                _ep_lbl_map[_o['ep']] = (f"{_em} {_lm}  -  {_est}" if _est else f"{_em} {_lm}").strip()
            # Si el valor guardado del selectbox ya no existe en las opciones (cambio
            # busqueda/filtro), se limpia para que 'index' vuelva a mandar.
            if st.session_state.get('selector_cotizaciones') not in _ep_opts:
                st.session_state.pop('selector_cotizaciones', None)
            _cur_idx = _ep_opts.index(_sel_ep_now) if _sel_ep_now in _ep_opts else 0
            _col_sel, _col_rec_btn = st.columns([4, 1])
            with _col_sel:
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 4px 0;display:flex;align-items:center;gap:7px;"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#0f172a" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2"/></svg>Selecciona una cotizaci&#243;n</div>', unsafe_allow_html=True)
                _ep_pick = st.selectbox(
                    'Selecciona una cotizacion',
                    _ep_opts,
                    index=_cur_idx,
                    format_func=lambda e: _ep_lbl_map.get(e, e),
                    key='selector_cotizaciones',
                    label_visibility='collapsed',
                )
            with _col_rec_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                _btn_rec_placeholder = st.empty()
            # selectbox dispara rerun nativo al cambiar; sincronizamos selector_ep_num
            if _ep_pick and _ep_pick != _sel_ep_now:
                st.session_state['selector_ep_num'] = _ep_pick
                _sel_ep_now = _ep_pick
            cotizacion_seleccionada = _sel_ep_now

            if cotizacion_seleccionada:
                numero_seleccionado = cotizacion_seleccionada
                tiene_margen_seleccionado = False
                tiene_plano_seleccionado = False
                for _row_s in st.session_state.resultados_busqueda:
                    if _row_s[0] == numero_seleccionado:
                        tiene_margen_seleccionado = bool(_row_s[5] and _row_s[5] > 0)
                        tiene_plano_seleccionado = bool(_row_s[10]) if len(_row_s) > 10 else False
                        break
                if numero_seleccionado != st.session_state.numero_en_visor:
                    if tiene_plano_seleccionado and st.session_state.mostrar_visor:
                        cot_visor = cargar_cotizacion(numero_seleccionado)
                        if cot_visor and cot_visor.get('plano_url'):
                            st.session_state.pdf_url = cot_visor['plano_url']
                            st.session_state.pdf_nombre = cot_visor.get('plano_nombre', 'plano.pdf')
                            st.session_state.numero_en_visor = numero_seleccionado
                            st.rerun()
                        else:
                            st.session_state.mostrar_visor = False
                            st.session_state.pdf_actual = None
                            st.session_state.pdf_nombre = ""
                            st.session_state.numero_en_visor = None
                            st.session_state.pdf_url = None
                            st.rerun()
                    else:
                        if st.session_state.mostrar_visor:
                            st.session_state.mostrar_visor = False
                            st.session_state.pdf_actual = None
                            st.session_state.pdf_nombre = ""
                            st.session_state.numero_en_visor = None
                            st.session_state.pdf_url = None
                            st.rerun()
                if tiene_margen_seleccionado and not st.session_state.modo_admin:
                    st.warning("&#128274; Cotizaci&#243;n autorizada - Solo puedes generar PDFs")
                if _rol_actual in ('admin', 'root'):
                    _logs_ep = obtener_logs_ep(numero_seleccionado)
                    if _logs_ep:
                        _n_mods = len([l for l in _logs_ep if l.get("tipo_cambio") == "modificacion"])
                        try:
                            _pdf_log_bytes = _pdf_log_cached(numero_seleccionado, len(_logs_ep))
                            st.download_button(
                                label=f"Descargar historial PDF ({len(_logs_ep)} registros · {_n_mods} modif.)",
                                data=_pdf_log_bytes, file_name=f"historial_{numero_seleccionado}.pdf",
                                mime="application/pdf", use_container_width=True, key="btn_download_log")
                        except:
                            st.warning("&#9888;&#65039; No se pudo generar el historial PDF. Intenta nuevamente.")
                    else:
                        st.caption("&#128203; Sin registros de modificaciones a&#250;n")

            st.markdown("---")
            st.markdown("### Acciones")
            # Iconos SVG en los botones de acción (data-URI ::before). Soporta
            # keys exactas (.st-key-X) y prefijos dinámicos ([class*=st-key-X]).
            def _abtn_svg(sel, svg_path, color="%23475569", disabled_color="%239ca3af"):
                def _url(c):
                    return (
                        f'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' '
                        f'width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'{c}\' '
                        f'stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E{svg_path}'
                        f'%3C/svg%3E")'
                    )
                return (
                    f'{sel} button{{display:inline-flex!important;align-items:center!important;'
                    f'justify-content:center!important;gap:7px!important;}}'
                    f'{sel} button::before{{content:""!important;flex-shrink:0!important;'
                    f'width:16px!important;height:16px!important;'
                    f'background:{_url(color)} no-repeat center/contain!important;}}'
                    # En estado disabled el botón queda con fondo transparente y texto
                    # gris → un icono blanco sería invisible. Usamos un icono gris.
                    f'{sel} button:disabled::before{{background:{_url(disabled_color)} '
                    f'no-repeat center/contain!important;}}'
                )
            _SVG_FILETXT = "%3Cpath d=\'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z\'/%3E%3Cpath d=\'M14 2v4a2 2 0 0 0 2 2h4\'/%3E%3Cpath d=\'M16 13H8\'/%3E%3Cpath d=\'M16 17H8\'/%3E"
            _SVG_X = "%3Cpath d=\'M18 6 6 18\'/%3E%3Cpath d=\'m6 6 12 12\'/%3E"
            _SVG_FOLDER = "%3Cpath d=\'m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.55 6a2 2 0 0 1-1.94 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.93a2 2 0 0 1 1.66.9l.82 1.2a2 2 0 0 0 1.66.9H18a2 2 0 0 1 2 2v2\'/%3E"
            _SVG_PKG = "%3Cpath d=\'M11 21.7a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.7l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.7z\'/%3E%3Cpath d=\'M3.3 7 12 12l8.7-5\'/%3E%3Cpath d=\'M12 22V12\'/%3E"
            _SVG_FILE = "%3Cpath d=\'M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z\'/%3E%3Cpath d=\'M14 2v4a2 2 0 0 0 2 2h4\'/%3E"
            _SVG_LOCK = "%3Crect width=\'18\' height=\'11\' x=\'3\' y=\'11\' rx=\'2\' ry=\'2\'/%3E%3Cpath d=\'M7 11V7a5 5 0 0 1 10 0v4\'/%3E"
            _SVG_EYE = "%3Cpath d=\'M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z\'/%3E%3Ccircle cx=\'12\' cy=\'12\' r=\'3\'/%3E"
            _SVG_IMG = "%3Crect width=\'18\' height=\'18\' x=\'3\' y=\'3\' rx=\'2\' ry=\'2\'/%3E%3Ccircle cx=\'9\' cy=\'9\' r=\'2\'/%3E%3Cpath d=\'m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21\'/%3E"
            _SVG_DL = "%3Cpath d=\'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4\'/%3E%3Cpolyline points=\'7 10 12 15 17 10\'/%3E%3Cline x1=\'12\' x2=\'12\' y1=\'15\' y2=\'3\'/%3E"
            st.markdown(
                "<style>"
                + _abtn_svg(".st-key-btn_download_log", _SVG_FILETXT, "white")
                + _abtn_svg(".st-key-btn_rechazar_cot", _SVG_X, "%23dc2626")
                + _abtn_svg(".st-key-btn_cargar_presupuesto", _SVG_FOLDER, "white")
                + _abtn_svg("[class*='st-key-pdf_compras_']", _SVG_PKG, "white")
                + _abtn_svg("[class*='st-key-pdf_completo_']", _SVG_FILE, "white")
                + _abtn_svg("[class*='st-key-pdf_cliente_']", _SVG_LOCK, "white")
                + _abtn_svg("[class*='st-key-pdf_sel']", _SVG_IMG, "white")
                + _abtn_svg(".st-key-btn_ver_plano", _SVG_EYE, "white")
                + _abtn_svg(".st-key-btn_descargar_plano", _SVG_DL, "white")
                + _abtn_svg("[class*='st-key-descargar_plano_']", _SVG_DL, "white")
                + "</style>",
                unsafe_allow_html=True,
            )
            _rec_status = _rechazo_status_cached(numero_seleccionado)
            _sel_motivo_rec = _rec_status.get("motivo_rechazo", "") or ""
            _sel_adj_check = bool(_rec_status.get("contrato_notariado_url", ""))
            if not _sel_adj_check:
                if _sel_motivo_rec:
                    st.markdown(f'<div style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;"><div style="font-size:12px;font-weight:700;color:#b91c1c;">&#10060; Presupuesto RECHAZADO</div><div style="font-size:11px;color:#991b1b;margin-top:3px;"><b>Motivo:</b> {_sel_motivo_rec}</div></div>', unsafe_allow_html=True)
                    with _btn_rec_placeholder:
                        if st.button("&#8617;&#65039; Quitar rechazo", use_container_width=True, key="btn_quitar_rechazo"):
                            supabase_admin.table("cotizaciones").update({"motivo_rechazo": None, "fecha_rechazo": None}).eq("numero", numero_seleccionado).execute()
                            _rechazo_status_cached.clear()
                            st.session_state.resultados_busqueda = None
                            st.session_state.pop('_show_rechazo_dialog', None)
                            st.success("&#9989; Rechazo eliminado")
                            st.rerun()
                else:
                    with _btn_rec_placeholder:
                        st.markdown('<style>.st-key-btn_rechazar_cot button{background-color:#dc2626!important;color:white!important;border:none!important;font-size:0.75rem!important;padding:4px 10px!important;}.st-key-btn_rechazar_cot button:hover{background-color:#b91c1c!important;}</style>', unsafe_allow_html=True)
                        if st.button("Rechazar", use_container_width=True, key="btn_rechazar_cot"):
                            st.session_state['_show_rechazo_dialog'] = numero_seleccionado
                            st.rerun()

            if st.session_state.get('_show_rechazo_dialog') == numero_seleccionado:
                @st.dialog("Motivo de rechazo")
                def _dialogo_rechazo():
                    st.markdown(f"**Presupuesto:** {numero_seleccionado}")
                    _motivo_input = st.text_area("Describe el motivo del rechazo",
                                                  placeholder="Ej: Cliente desisti&#243; por cambio de presupuesto personal...",
                                                  key="motivo_rechazo_input", height=120)
                    _c1, _c2 = st.columns(2)
                    with _c1:
                        if st.button("Cancelar", use_container_width=True, key="btn_rec_cancel"):
                            st.session_state.pop('_show_rechazo_dialog', None)
                            st.rerun()
                    with _c2:
                        if st.button("Confirmar rechazo", type="primary", use_container_width=True, key="btn_rec_confirm"):
                            if _motivo_input.strip():
                                _fecha_rec_now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                                supabase_admin.table("cotizaciones").update({
                                    "motivo_rechazo": _motivo_input.strip(),
                                    "fecha_rechazo": _fecha_rec_now
                                }).eq("numero", numero_seleccionado).execute()
                                _rechazo_status_cached.clear()
                                st.session_state.pop('_show_rechazo_dialog', None)
                                st.session_state.resultados_busqueda = None
                                st.success(f"&#9989; {numero_seleccionado} marcado como rechazado")
                                st.rerun()
                            else:
                                st.warning("&#9888;&#65039; Debes ingresar un motivo.")
                _dialogo_rechazo()

            col_acc1, col_acc0, col_acc2, col_acc3, col_acc5, col_acc6, col_acc4 = st.columns(7)
            with col_acc1:
                if tiene_margen_seleccionado and not st.session_state.modo_admin:
                    st.button("Cargar presupuesto", use_container_width=True, disabled=True,
                              help="No se puede editar un presupuesto autorizado")
                else:
                    if st.button("Cargar presupuesto", use_container_width=True, key="btn_cargar_presupuesto", type="primary"):
                        tiene_sin_guardar = (len(st.session_state.carrito) > 0 and st.session_state.cotizacion_cargada != numero_seleccionado)
                        if tiene_sin_guardar:
                            st.session_state.mostrar_advertencia_carga = True
                            st.session_state.numero_a_cargar_pendiente = numero_seleccionado
                            st.rerun()
                        else:
                            if preparar_carga_cotizacion(numero_seleccionado):
                                # Navegar al editor (Presupuesto): en el modular cada
                                # página se renderiza por separado, así que hay que
                                # llevar al usuario a Presupuesto para que el trigger
                                # se procese y vea el presupuesto cargado. (Antes, con
                                # st.tabs monolítico, la pestaña ya estaba renderizada.)
                                st.session_state.nav_page = 'presupuesto'
                                st.session_state['_toast_cargado'] = numero_seleccionado
                                st.rerun()

            if st.session_state.get('mostrar_advertencia_carga', False):
                @st.dialog("Productos sin guardar")
                def dialogo_advertencia():
                    numero_pendiente = st.session_state.get('numero_a_cargar_pendiente', '')
                    st.markdown(f'<div style="text-align:center;padding:1rem 0;"><div style="font-size:3rem;margin-bottom:0.5rem;">&#9888;&#65039;</div><div style="font-size:1rem;font-weight:700;color:#1e2447;margin-bottom:0.5rem;">Tienes productos sin guardar</div><div style="font-size:0.88rem;color:#5a6080;line-height:1.6;">Est&#225;s a punto de cargar la cotizaci&#243;n <strong>{numero_pendiente}</strong>.<br/>&#191;Deseas guardar el presupuesto actual antes de continuar?</div></div>', unsafe_allow_html=True)
                    col_si, col_no, col_cancelar = st.columns(3)
                    with col_si:
                        if st.button("&#128190; S&#237;, guardar", use_container_width=True, type="primary", key="dialog_btn_si"):
                            datos_cliente_g, datos_asesor_g, proyecto_g, config_g, totales_g, plano_n, plano_d = _construir_datos_guardar_simple()
                            if st.session_state.cotizacion_cargada:
                                num_g = st.session_state.cotizacion_cargada
                            else:
                                num_g = generar_numero_unico()
                            _usr_log3 = st.session_state.get('auth_nombre','') or st.session_state.get('auth_email','')
                            guardar_cotizacion(num_g, datos_cliente_g, datos_asesor_g, proyecto_g,
                                               st.session_state.carrito, config_g, totales_g, plano_n, plano_d,
                                               usuario_logueado=_usr_log3)
                            st.session_state.mostrar_advertencia_carga = False
                            if preparar_carga_cotizacion(numero_pendiente):
                                st.session_state.nav_page = 'presupuesto'
                                st.session_state['_toast_cargado'] = numero_pendiente
                                st.rerun()
                    with col_no:
                        if st.button("&#128465;&#65039; No, descartar", use_container_width=True, key="dialog_btn_no"):
                            st.session_state.mostrar_advertencia_carga = False
                            if preparar_carga_cotizacion(numero_pendiente):
                                st.session_state.nav_page = 'presupuesto'
                                st.session_state['_toast_cargado'] = numero_pendiente
                                st.rerun()
                    with col_cancelar:
                        if st.button("Cancelar", use_container_width=True, key="dialog_btn_cancelar"):
                            st.session_state.mostrar_advertencia_carga = False
                            st.session_state.numero_a_cargar_pendiente = None
                            st.rerun()
                dialogo_advertencia()

            cotizacion_para_pdf = cargar_cotizacion(numero_seleccionado) if cotizacion_seleccionada else None

            def preparar_pdf_data(cotizacion):
                carrito_df_t = pd.DataFrame(cotizacion['productos'])
                if not carrito_df_t.empty and 'Categoria' in carrito_df_t.columns:
                    carrito_df_t = carrito_df_t.sort_values(['Categoria', 'Item'], ignore_index=True)
                margen_c = cotizacion.get('config_margen', 0)
                if margen_c > 0:
                    carrito_df_p = carrito_df_t.copy()
                    carrito_df_p["Precio Unitario"] = carrito_df_p["Precio Unitario"].apply(lambda x: aplicar_margen(x, margen_c))
                    carrito_df_p["Subtotal"] = carrito_df_p["Cantidad"] * carrito_df_p["Precio Unitario"]
                else:
                    carrito_df_p = carrito_df_t.copy()
                subtotal_p = carrito_df_p["Subtotal"].sum()
                iva_p = subtotal_p * 0.19
                total_p = subtotal_p + iva_p
                dc = {
                    "Nombre": cotizacion.get('cliente_nombre',''), "RUT": cotizacion.get('cliente_rut',''),
                    "Correo": cotizacion.get('cliente_email',''),
                    "Tel&#233;fono": formatear_telefono(cotizacion.get('cliente_telefono','')),
                    "Direcci&#243;n": cotizacion.get('cliente_direccion',''),
                    "ComunaCliente": cotizacion.get('cliente_comuna',''), "RegionCliente": cotizacion.get('cliente_region',''),
                    "DireccionProyecto": cotizacion.get('proyecto_direccion',''),
                    "ComunaProyecto": cotizacion.get('proyecto_comuna',''), "RegionProyecto": cotizacion.get('proyecto_region',''),
                    "TipoCliente": cotizacion.get('cliente_tipo','natural'), "EmpresaCliente": cotizacion.get('cliente_empresa',''),
                    "RutEmpresa": cotizacion.get('cliente_rut_empresa',''), "Observaciones": cotizacion.get('proyecto_observaciones',''),
                }
                da = {
                    "Nombre Ejecutivo": cotizacion.get('asesor_nombre',''),
                    "Correo Ejecutivo": cotizacion.get('asesor_email',''),
                    "Tel&#233;fono Ejecutivo": formatear_telefono(cotizacion.get('asesor_telefono','')),
                }
                fi = datetime.strptime(cotizacion.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                ft = datetime.strptime(cotizacion.get('proyecto_fecha_termino', (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                dv = cotizacion.get('proyecto_dias_validez', 15)
                return carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c

            _es_ejecutivo_pdf = _rol_actual == 'ejecutivo'
            _estado_sel = ''
            for _row in st.session_state.resultados_busqueda:
                if _row[0] == numero_seleccionado:
                    _margen_sel = _row[5] or 0
                    _datos_ok = all([_row[1], _row[7]])
                    _asesor_ok = any([_row[2], _row[8], _row[9]])
                    if _margen_sel > 0 and _datos_ok and _asesor_ok:
                        _estado_sel = 'autorizado'
                    break
            _pdf_habilitado = (not _es_ejecutivo_pdf) or (_estado_sel == 'autorizado')

            with col_acc0:
                if cotizacion_para_pdf and not _es_ejecutivo_pdf:
                    _cot_compras = cargar_cotizacion(numero_seleccionado)
                    if _cot_compras:
                        _df_compras_raw = pd.DataFrame(_cot_compras['productos'])
                        _df_compras = _df_compras_raw[_df_compras_raw['Categoria'].str.strip().str.lower() != 'varios'].copy()
                        _sub_compras = _df_compras['Subtotal'].sum()
                        _iva_compras = _sub_compras * 0.19
                        _tot_compras = _sub_compras + _iva_compras
                        _dc_compras = {
                            "Nombre": _cot_compras.get('cliente_nombre',''), "RUT": _cot_compras.get('cliente_rut',''),
                            "Correo": _cot_compras.get('cliente_email',''),
                            "Tel&#233;fono": formatear_telefono(_cot_compras.get('cliente_telefono','')),
                            "Direcci&#243;n": _cot_compras.get('cliente_direccion',''),
                            "ComunaCliente": _cot_compras.get('cliente_comuna',''), "RegionCliente": _cot_compras.get('cliente_region',''),
                            "DireccionProyecto": _cot_compras.get('proyecto_direccion',''),
                            "ComunaProyecto": _cot_compras.get('proyecto_comuna',''), "RegionProyecto": _cot_compras.get('proyecto_region',''),
                            "TipoCliente": _cot_compras.get('cliente_tipo','natural'), "EmpresaCliente": _cot_compras.get('cliente_empresa',''),
                            "RutEmpresa": _cot_compras.get('cliente_rut_empresa',''), "Observaciones": _cot_compras.get('proyecto_observaciones',''),
                        }
                        _da_compras = {
                            "Nombre Ejecutivo": _cot_compras.get('asesor_nombre',''),
                            "Correo Ejecutivo": _cot_compras.get('asesor_email',''),
                            "Tel&#233;fono Ejecutivo": formatear_telefono(_cot_compras.get('asesor_telefono','')),
                        }
                        _fi_c = datetime.strptime(_cot_compras.get('proyecto_fecha_inicio', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                        _ft_c = datetime.strptime(_cot_compras.get('proyecto_fecha_termino', (datetime.now()+timedelta(days=15)).strftime('%Y-%m-%d')), '%Y-%m-%d').date()
                        _dv_c = _cot_compras.get('proyecto_dias_validez', 15)
                        _fadj_c = _cot_compras.get('fecha_adjudicacion') or None
                        _ffid_c = _cot_compras.get('fecha_entrega') or None
                        try:
                            _cd_raw = _cot_compras.get('contrato_datos') or {}
                            if isinstance(_cd_raw, str): _cd_raw = json.loads(_cd_raw)
                            _plazo_c = int(_cd_raw.get('plazo_dias', 45) or 45)
                        except:
                            _plazo_c = 45
                        _pdf_compras, _ = generar_pdf_completo(
                            _df_compras, _sub_compras, _iva_compras, _tot_compras, _dc_compras,
                            _fi_c, _ft_c, _dv_c, _da_compras, margen=0,
                            numero_cotizacion=numero_seleccionado, mostrar_precios=True,
                            fecha_adjudicacion=_fadj_c, fecha_fidelizacion=_ffid_c, plazo_obra_dias=_plazo_c)
                        st.download_button(label="PDF Compras", data=_pdf_compras,
                            file_name=f"Compras_{numero_seleccionado}.pdf", mime="application/pdf",
                            use_container_width=True, key=f"pdf_compras_{numero_seleccionado}")
                else:
                    st.button("PDF Compras", use_container_width=True, disabled=True,
                              help="Solo disponible para operaciones, admin y root" if _es_ejecutivo_pdf else None)

            with col_acc2:
                if cotizacion_para_pdf and _pdf_habilitado:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    pdf_buffer, _ = generar_pdf_completo(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da,
                                                          margen=margen_c, numero_cotizacion=numero_seleccionado)
                    st.download_button(label="PDF Completo", data=pdf_buffer,
                        file_name=f"Presupuesto_Completo_{numero_seleccionado}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"pdf_completo_{numero_seleccionado}")
                else:
                    st.button("PDF Completo", use_container_width=True, disabled=True,
                              help="Solo disponible para cotizaciones autorizadas" if _es_ejecutivo_pdf else None)

            with col_acc3:
                if cotizacion_para_pdf and _pdf_habilitado:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    _desc_ep = cargar_descripciones_por_ep(numero_seleccionado, supa_url, bust_cache=True)
                    pdf_buffer, _ = generar_pdf_cliente(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da,
                                                         margen=margen_c, numero_cotizacion=numero_seleccionado,
                                                         descripciones_ep=_desc_ep)
                    st.download_button(label="PDF Cliente", data=pdf_buffer,
                        file_name=f"Presupuesto_Cliente_{numero_seleccionado}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"pdf_cliente_{numero_seleccionado}")
                else:
                    st.button("PDF Cliente", use_container_width=True, disabled=True,
                              help="Solo disponible para cotizaciones autorizadas" if _es_ejecutivo_pdf else None)

            with col_acc5:
                try:
                    _sel_ep2 = numero_seleccionado if cotizacion_seleccionada else ''
                    _sel_pct2 = 0; _sel_cfg2 = []; _sel_res2 = {}; _sel_mit2 = {}
                    if _sel_ep2:
                        _sel_cfg2 = _fetch_formulario_config(_sel_ep2)
                        if _sel_cfg2:
                            _sel_r = supabase_admin.table('formulario_respuestas').select('item_id,respuesta').eq('cotizacion_numero', _sel_ep2).execute().data or []
                            _sel_res2 = {r['item_id']: r['respuesta'] for r in _sel_r if r.get('item_id')}
                            _tot2 = len(_sel_cfg2)
                            _don2 = sum(1 for c in _sel_cfg2 if any(_sel_res2.get(str(i)) for i in (c.get('item_ids') or [])))
                            _sel_pct2 = int(_don2 / _tot2 * 100) if _tot2 > 0 else 0
                            if _sel_pct2 >= 1:
                                _all_ids2 = [str(i) for c in _sel_cfg2 for i in (c.get('item_ids') or [])]
                                if _all_ids2:
                                    _mit2 = supabase_admin.table('catalogo_materiales').select('id,nombre,imagen_url,hex,tipo').in_('id', _all_ids2).execute().data or []
                                    _sel_mit2 = {str(m['id']): m for m in _mit2}
                    if _sel_pct2 >= 1 and _sel_cfg2:
                        _cot_sel2 = cargar_cotizacion(_sel_ep2)
                        _sel_fecha = ''
                        try:
                            _fcomp = (_cot_sel2 or {}).get('fecha_formulario_completado','')
                            if _fcomp:
                                from datetime import datetime as _dtt2
                                _sel_fecha = _dtt2.fromisoformat(_fcomp[:19]).strftime('%d/%m/%Y')
                        except:
                            pass
                        if not _sel_fecha:
                            _sel_fecha = datetime.now().strftime('%d/%m/%Y')
                        _pdf_sel2 = generar_pdf_seleccion_cliente(
                            _sel_ep2, _cot_sel2.get('cliente_nombre','') if _cot_sel2 else '',
                            _sel_cfg2, _sel_res2, _sel_mit2, fecha_formulario=_sel_fecha)
                        st.download_button(label='PDF Selección', data=_pdf_sel2,
                            file_name=f'Seleccion_Cliente_{_sel_ep2}.pdf', mime='application/pdf',
                            use_container_width=True, key=f'pdf_sel_{_sel_ep2}',
                            help=f'Selección del cliente ({_sel_pct2}% completado)')
                    else:
                        st.button('PDF Selección', use_container_width=True, disabled=True,
                                  key='pdf_sel_dis', help='Sin selecciones del cliente aún')
                except Exception as _esel2:
                    st.button('PDF Selección', use_container_width=True, disabled=True,
                              key='pdf_sel_err', help=str(_esel2)[:200])

            with col_acc6:
                # Descargar el plano directamente (sin previsualizar). El plano vive
                # en plano_url; bajamos los bytes (cacheados) y los servimos vía
                # download_button. Si no hay plano → botón deshabilitado.
                _pl_url6 = (cotizacion_para_pdf or {}).get('plano_url') if cotizacion_para_pdf else None
                if cotizacion_seleccionada and tiene_plano_seleccionado and _pl_url6:
                    _pl_name6 = (cotizacion_para_pdf or {}).get('plano_nombre') or f'Plano_{numero_seleccionado}.pdf'
                    _pl_bytes6 = _fetch_plano_bytes(_pl_url6)
                    if _pl_bytes6:
                        _pl_mime6 = 'application/pdf' if _pl_name6.lower().endswith('.pdf') else 'application/octet-stream'
                        st.download_button("DESCARGAR PLANO", data=_pl_bytes6, file_name=_pl_name6,
                            mime=_pl_mime6, use_container_width=True, key="btn_descargar_plano",
                            help="Descarga el plano adjunto directamente")
                    else:
                        st.button("DESCARGAR PLANO", use_container_width=True, disabled=True,
                                  key="btn_descargar_plano", help="No se pudo obtener el plano")
                else:
                    st.button("DESCARGAR PLANO", use_container_width=True, disabled=True,
                              key="btn_descargar_plano", help="Sin plano adjunto")

            with col_acc4:
                if cotizacion_seleccionada and tiene_plano_seleccionado:
                    label_visor = "ACTUALIZAR PLANO" if (st.session_state.mostrar_visor and st.session_state.numero_en_visor == numero_seleccionado) else "VER PLANO"
                    if st.button(label_visor, use_container_width=True, type="primary", help="Ver plano adjunto", key="btn_ver_plano"):
                        cot_btn = cargar_cotizacion(numero_seleccionado)
                        if cot_btn and cot_btn.get('plano_url'):
                            st.session_state.pdf_url = cot_btn['plano_url']
                            st.session_state.pdf_nombre = cot_btn.get('plano_nombre', 'plano.pdf')
                            st.session_state.mostrar_visor = True
                            st.session_state.numero_en_visor = numero_seleccionado
                            st.rerun()
                else:
                    st.button("VER PLANO", use_container_width=True, disabled=True, help="Sin plano adjunto", key="btn_ver_plano")

            if st.session_state.mostrar_visor and st.session_state.pdf_url:
                with st.expander("Vista Previa del Plano", expanded=True, icon=":material/picture_as_pdf:"):
                    st.markdown(f"**Archivo:** {st.session_state.pdf_nombre} — cotizaci&#243;n `{st.session_state.numero_en_visor}`")
                    pdf_url_visor = st.session_state.pdf_url
                    # Visor con PDF.js (render a canvas). Antes se usaba el Google Docs
                    # viewer, que Google descontinuó → dejó de cargar. El embed directo
                    # en <iframe> tampoco es fiable cross-browser: Safari y Brave no
                    # renderizan PDF cross-origin embebido. PDF.js funciona en TODOS
                    # (Safari/Chrome/Brave/Edge/Firefox) porque dibuja en canvas; solo
                    # necesita CORS para el fetch (Supabase ya envía allow-origin: *).
                    _pdf_url_js = json.dumps(pdf_url_visor)
                    _visor_html = """<style>
@keyframes spin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}
body,html{margin:0;padding:0;}
#pdf-wrap{width:100%;height:680px;border:2px solid #e2e8f0;border-radius:12px;overflow-y:auto;overflow-x:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);background:#525659;position:relative;}
#pdf-loading{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f0f2f5;z-index:2;gap:12px;transition:opacity .4s ease;}
#pdf-spinner{width:40px;height:40px;border:4px solid #cbd5e1;border-top-color:#5b7cfa;border-radius:50%;animation:spin .8s linear infinite;}
#pdf-loading span{color:#64748b;font-size:.9rem;font-family:sans-serif;text-align:center;padding:0 16px;}
#pdf-pages{padding:12px 0;text-align:center;}
#pdf-pages canvas{display:block;margin:0 auto 12px;max-width:96%;box-shadow:0 2px 10px rgba(0,0,0,.4);background:#fff;}
</style>
<div id="pdf-wrap"><div id="pdf-loading"><div id="pdf-spinner"></div><span id="pdf-status">Cargando PDF...</span></div><div id="pdf-pages"></div></div>
<script>
function _ecStartPdf(){
  var url=__PDF_URL__;
  var loading=document.getElementById('pdf-loading');
  var statusEl=document.getElementById('pdf-status');
  var pages=document.getElementById('pdf-pages');
  function hide(){loading.style.opacity='0';setTimeout(function(){loading.style.display='none';},400);}
  if(typeof pdfjsLib==='undefined'){statusEl.textContent='No se pudo cargar el visor. Usa el boton Descargar Plano.';return;}
  pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
  pdfjsLib.getDocument({url:url,withCredentials:false}).promise.then(function(pdf){
    var first=true;var seq=Promise.resolve();
    for(var i=1;i<=pdf.numPages;i++){(function(num){
      seq=seq.then(function(){return pdf.getPage(num).then(function(page){
        var vp=page.getViewport({scale:1.6});
        var c=document.createElement('canvas');var ctx=c.getContext('2d');
        c.width=vp.width;c.height=vp.height;pages.appendChild(c);
        return page.render({canvasContext:ctx,viewport:vp}).promise.then(function(){if(first){first=false;hide();}});
      });});
    })(i);}
  }).catch(function(err){statusEl.textContent='No se pudo mostrar el PDF. Usa el boton Descargar Plano.';});
}
</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js" onload="_ecStartPdf()" onerror="var s=document.getElementById('pdf-status');if(s)s.textContent='No se pudo cargar el visor. Usa el boton Descargar Plano.';"></script>
""".replace("__PDF_URL__", _pdf_url_js)
                    components.html(_visor_html, height=710, scrolling=False)
                    _dl_bytes_v = _fetch_plano_bytes(st.session_state.pdf_url)
                    if _dl_bytes_v:
                        st.download_button(label="Descargar Plano", data=_dl_bytes_v,
                            file_name=st.session_state.pdf_nombre, mime="application/pdf",
                            use_container_width=True, key=f"descargar_plano_{st.session_state.numero_en_visor}")
                    else:
                        st.warning("No se pudo preparar la descarga. Intenta de nuevo.")

        st.markdown("---")
        st.markdown("### Estadisticas Rapidas")
        # Conteo por estado usando la FUENTE ÚNICA (calcular_estado_label), la misma
        # que la tabla/badges → las stats siempre coinciden con los filtros.
        _estado_cnt = {}
        for row in st.session_state.resultados_busqueda:
            _lbl = calcular_estado_label(
                row[1], row[7], row[2], row[8], row[9],
                float(row[5] or 0), bool(row[10]) if len(row) > 10 else False,
                tiene_notariado=bool(row[15]) if len(row) > 15 else False,
                tiene_acta=bool(row[21]) if len(row) > 21 else False,
                motivo_rechazo=row[19] if len(row) > 19 else '')
            _estado_cnt[_lbl] = _estado_cnt.get(_lbl, 0) + 1
        def _ec(k): return _estado_cnt.get(k, 0)
        # ── Stat cards: grid responsivo (auto-fit) + estilo potente con SVG ──
        _SVG_STAT = {
            "trophy": '<path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/>',
            "award": '<path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526"/><circle cx="12" cy="8" r="6"/>',
            "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
            "checkline": '<path d="M20 6 9 17l-5-5"/>',
            "fileedit": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z"/><polyline points="14 2 14 8 20 8"/><path d="M10.4 12.6a2 2 0 1 1 3 3L8 21l-4 1 1-4z"/>',
            "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
            "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
            "xcircle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
            "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
        }
        def _stat_ic(name, color):
            return (
                f'<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="{color}" '
                f'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
                f'{_SVG_STAT.get(name, "")}</svg>'
            )
        # (icon, color, título, número, descripción)
        _stat_cards = [
            ("trophy",   "#7c3aed", "Terminado",       str(_ec('PROYECTO TERMINADO')),   "Proyectos terminados"),
            ("award",    "#2563eb", "Adjudicado",      str(_ec('ADJUDICADO')),           "Adjudicados"),
            ("check",    "#10b981", "Autorizado C/P",  str(_ec('AUTORIZADO CON PLANO')), "Autorizados con plano"),
            ("checkline","#16a34a", "Autorizado",      str(_ec('AUTORIZADO')),           "Autorizados sin plano"),
            ("fileedit", "#f97316", "Borrador C/P",    str(_ec('BORRADOR CON PLANO')),   "Borradores con plano"),
            ("file",     "#eab308", "Borrador",        str(_ec('BORRADOR')),             "Borradores sin plano"),
            ("alert",    "#ef4444", "Incompleto C/P",  str(_ec('INCOMPLETO CON PLANO')), "Incompletos con plano"),
            ("xcircle",  "#dc2626", "Incompleto",      str(_ec('INCOMPLETO')),           "Incompletos sin plano"),
            ("ban",      "#b91c1c", "Rechazado",       str(_ec('RECHAZADO')),            "Rechazados"),
        ]
        _cards_html = (
            '<style>'
            '.ec-stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));'
            'gap:14px;margin-top:6px;}'
            '.ec-stat{position:relative;background:#fff;border-radius:16px;padding:18px 18px 16px;'
            'border:1px solid #eaedf5;box-shadow:0 4px 18px rgba(15,23,42,0.06);overflow:hidden;'
            'transition:transform .18s cubic-bezier(.22,1,.36,1),box-shadow .18s;}'
            '.ec-stat:hover{transform:translateY(-4px);box-shadow:0 14px 34px rgba(15,23,42,0.13);}'
            '.ec-stat::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;}'
            '.ec-stat-top{display:flex;align-items:center;gap:9px;margin-bottom:12px;}'
            '.ec-stat-ico{width:38px;height:38px;border-radius:11px;display:flex;align-items:center;'
            'justify-content:center;flex-shrink:0;}'
            '.ec-stat-ttl{font-size:0.66rem;font-weight:800;color:#9099be;text-transform:uppercase;'
            'letter-spacing:0.07em;line-height:1.15;}'
            '.ec-stat-num{font-weight:900;line-height:1;letter-spacing:-0.03em;margin-bottom:5px;'
            'font-family:"Plus Jakarta Sans",sans-serif;}'
            '.ec-stat-desc{font-size:0.74rem;color:#a0a8c8;font-weight:500;}'
            '</style><div class="ec-stats-grid">'
        )
        for _ic, _col, _ttl, _num, _desc in _stat_cards:
            _fs = "1.5rem" if len(_num) > 11 else ("1.9rem" if len(_num) > 7 else "2.4rem")
            _cards_html += (
                f'<div class="ec-stat" style="--c:{_col};">'
                f'<div style="position:absolute;top:0;left:0;right:0;height:4px;'
                f'background:linear-gradient(90deg,{_col},{_col}99);"></div>'
                f'<div class="ec-stat-top">'
                f'<div class="ec-stat-ico" style="background:{_col}1a;">{_stat_ic(_ic, _col)}</div>'
                f'<div class="ec-stat-ttl">{_ttl}</div></div>'
                f'<div class="ec-stat-num" style="color:{_col};font-size:{_fs};">{_num}</div>'
                f'<div class="ec-stat-desc">{_desc}</div>'
                f'</div>'
            )
        _cards_html += '</div>'
        st.markdown(_cards_html, unsafe_allow_html=True)

    # Toasts
    if st.session_state.get('_toast_msg'):
        st.toast(st.session_state['_toast_msg'])
        st.session_state['_toast_msg'] = None
    if st.session_state.get('mostrar_toast_exito', False):
        ep = st.session_state.get('toast_numero_ep', '')
        components.html(f"""<script>
(function(){{
    var D=window.parent.document;
    if(D.getElementById('_toast_ep')) return;
    var t=D.createElement('div');
    t.id='_toast_ep';
    t.style.cssText='position:fixed;bottom:5rem;left:2rem;z-index:9999999;'+
        'background:linear-gradient(135deg,#10b981,#059669);color:white;'+
        'padding:14px 22px;border-radius:12px;font-size:0.95rem;font-weight:700;'+
        'font-family:Plus Jakarta Sans,sans-serif;'+
        'box-shadow:0 8px 24px rgba(16,185,129,0.4);'+
        'display:flex;align-items:center;gap:10px;'+
        'animation:slideInToast 0.3s ease;';
    t.innerHTML='<span style="font-size:1.2rem">&#9989;</span> Cotizaci&#243;n <b style="margin:0 4px">{ep}</b> guardada correctamente' +
        '<button onclick="this.parentElement.remove()" style="background:none;border:none;color:rgba(255,255,255,0.8);' +
        'font-size:1.1rem;cursor:pointer;margin-left:10px;padding:0;line-height:1;" title="Cerrar">&#10005;</button>';
    var s=D.createElement('style');
    s.innerHTML='@keyframes slideInToast{{from{{transform:translateY(20px);opacity:0}}to{{transform:translateY(0);opacity:1}}}}';
    D.head.appendChild(s);
    D.body.appendChild(t);
    setTimeout(function(){{
        t.style.transition='opacity 0.4s';
        t.style.opacity='0';
        setTimeout(function(){{t.remove();}},400);
    }},3500);
}})();
</script>""", height=0)

    # Estado vacío: SOLO cuando de verdad no hay resultados que mostrar (antes
    # colgaba del else del toast y aparecía aun habiendo cotizaciones).
    if not st.session_state.get('resultados_busqueda'):
        _svg_bulb = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563eb" '
                     'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">'
                     '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>'
                     '<path d="M9 18h6"/><path d="M10 22h4"/></svg>')
        st.markdown(
            '<div style="display:flex;align-items:center;gap:10px;background:#eff6ff;'
            'border:1px solid #bfdbfe;border-radius:12px;padding:14px 18px;color:#1e40af;'
            'font-family:\'Plus Jakarta Sans\',sans-serif;font-weight:500;font-size:0.9rem;">'
            f'{_svg_bulb}<span>No hay resultados. Realiza una búsqueda para ver cotizaciones guardadas.</span></div>',
            unsafe_allow_html=True)
