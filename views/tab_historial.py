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

from repositories.cotizaciones_repo import (
    buscar_cotizaciones, cargar_cotizacion, guardar_cotizacion, generar_numero_unico
)
from repositories.logs_repo import obtener_logs_ep
from repositories.compras_repo import calcular_estado_compras
from services.cotizacion_service import crear_badge_estado, aplicar_margen
from generators.pdf_cotizacion import generar_pdf_completo, generar_pdf_cliente
from generators.pdf_log import generar_pdf_log
from generators.pdf_seleccion import generar_pdf_seleccion_cliente
from utils.formato import formato_clp
from utils.telefono import formatear_telefono
from config.supabase import supabase_admin as _supa_admin_global


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
    <div class="hdr3" style="display:flex!important;align-items:center!important;">
      <span style="font-size:2.8rem;line-height:1;flex-shrink:0;">📂</span>
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Gestión de Cotizaciones</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;">Busca, carga y administra todas las cotizaciones del sistema.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        tipo_busqueda = st.radio("Buscar por:", ["📋 N° Presupuesto", "👤 Cliente", "👨‍💼 Asesor"],
                                  horizontal=True, key="tipo_busqueda", label_visibility="collapsed")
        tipo_map = {"📋 N° Presupuesto": "numero", "👤 Cliente": "cliente", "👨‍💼 Asesor": "asesor"}
        _bc1, _bc2, _bc3, _bc4, _bc5, _bc6 = st.columns([3, 0.8, 0.8, 0.7, 0.8, 0.8])
        with _bc1:
            termino = st.text_input("Término", placeholder="Ingrese término de búsqueda...",
                                     key="buscar_cotizacion", label_visibility="collapsed")
        with _bc2: buscar_btn = st.button("🔍 Buscar", type="primary", use_container_width=True)
        with _bc3: limpiar_btn = st.button("🗑️ Limpiar", use_container_width=True)
        with _bc4:
            if st.button("📅 Hoy", use_container_width=True, key="filtro_hoy"):
                st.session_state.resultados_busqueda = None; st.rerun()
        with _bc5:
            if st.button("📅 Semana", use_container_width=True, key="filtro_semana"):
                st.session_state.resultados_busqueda = None; st.rerun()
        with _bc6:
            if st.button("📅 Mes", use_container_width=True, key="filtro_mes"):
                st.session_state.resultados_busqueda = None; st.rerun()

    st.markdown("---")
    st.markdown("### Resultados")

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
        st.session_state.resultados_busqueda = buscar_cotizaciones()

    if buscar_btn or (termino and termino != st.session_state.get('ultimo_termino', '')):
        st.session_state.ultimo_termino = termino
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
                 "Cli_Region","Inst_Dir","Inst_Comuna","Inst_Region","NLogs"]
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
            return f'{fh}<br><span style="font-size:0.72em;color:#16a34a;font-weight:700;">✅ {q}</span>' if q else fh
        df_resultados["Fecha_Auth_fmt"] = df_resultados.apply(_fmt_auth_nom, axis=1)
        df_resultados["Plano"] = df_resultados.apply(lambda r: "✅ Sí" if r["Tiene_Plano"] else "—", axis=1)
        df_resultados["MargenCol"] = df_resultados["Margen"].apply(
            lambda x: f'✅ Sí<br><span style="font-size:0.78em;color:#16a34a;">{x:.3f}%</span>' if x and x>0 else "—")
        df_resultados["ContratoCol"] = df_resultados["Tiene_Contrato"].apply(lambda x: "✅ Sí" if x else "—")
        df_resultados["EmpresaCol"] = df_resultados["Empresa"].apply(lambda x: "✅ Sí" if x and str(x).strip() else "—")
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
            try:
                _eps_m=df_resultados["N°"].tolist()
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
                for _ep2,_cfgs2 in _mc2.items():
                    _rs2=_mr2[_ep2]; _tot2=len(_cfgs2)
                    _dn2=sum(1 for _c in _cfgs2 if any(_rs2.get(str(_i)) for _i in (_c.get("item_ids") or [])))
                    _pct2=int(_dn2/_tot2*100) if _tot2>0 else 0
                    from collections import defaultdict as _dd3
                    _cats2=_dd3(list)
                    for _c in sorted(_cfgs2,key=lambda x:(x.get("categoria",""),x.get("orden",0))):
                        _ids2=[str(_i) for _i in (_c.get("item_ids") or [])]
                        _v2=[_rs2[_i] for _i in _ids2 if _rs2.get(_i)]
                        _cats2[_c.get("categoria","")].append({"tg":_c.get("titulo_grupo",""),"val":", ".join(_v2)})
                    _mat_data_map[_ep2]={"pct":_pct2,"done":_dn2,"total":_tot2,
                        "cats":[{"cat":_k,"grupos":_vl} for _k,_vl in _cats2.items()]}
            except: pass

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
                                f'font-weight:700;cursor:pointer;font-family:inherit;line-height:1.4;">📋 Ver</button>'
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
                                f'<span style="color:{c};font-weight:700;font-size:0.75rem;">✅ 100% comprado</span></div>')+_mh()
                    elif "adicionales" in _estado:
                        na=len(_est["adicionales"]); c,b=_cc(100)
                        return (f'<div style="width:80px;"><div style="background:{b};border-radius:4px;height:6px;margin-bottom:3px;">'
                                f'<div style="background:{c};border-radius:4px;height:6px;width:100%;"></div></div>'
                                f'<span style="color:{c};font-weight:700;font-size:0.75rem;">✅ 100% +{na} adic.</span></div>')+_mh()
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

        _filtro_activo = st.session_state.get('filtro_estado_tabla')
        if _filtro_activo:
            import re as _re_f
            df_resultados = df_resultados[df_resultados['Estado'].apply(
                lambda h: _re_f.sub(r'<[^>]+>','',str(h)).strip()==_filtro_activo)].copy()
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

        _cli_data_map = {}
        for _,_mr in df_resultados.iterrows():
            _cli_data_map[str(_mr.get('N°',''))]={
                'nombre':str(_mr.get('Cliente','') or ''),'rut':str(_mr.get('RUT','') or ''),
                'tel':str(_mr.get('Cli_Tel','') or ''),'email':str(_mr.get('Email','') or ''),
                'dir':str(_mr.get('Cli_Dir','') or ''),'comuna':str(_mr.get('Cli_Comuna','') or ''),
                'region':str(_mr.get('Cli_Region','') or ''),'empresa':str(_mr.get('Empresa','') or ''),
                'inst_dir':str(_mr.get('Inst_Dir','') or ''),'inst_comuna':str(_mr.get('Inst_Comuna','') or ''),
                'inst_region':str(_mr.get('Inst_Region','') or '')}
        _cli_data_json_map = json.dumps(_cli_data_map, ensure_ascii=True)
        _mat_data_json_map = json.dumps(_mat_data_map, ensure_ascii=True)

        rows_html = ""
        for _, row in df_resultados.iterrows():
            _mg_color = 'color:#16a34a;font-weight:700;' if '✅' in str(row['MargenCol']) else 'color:#94a3b8;'
            _th_margen = '<th>Margen</th>' if st.session_state.get('modo_admin') else ''
            _td_margen = f'<td style="text-align:center;line-height:1.6;{_mg_color}">{row["MargenCol"]}</td>' if st.session_state.get('modo_admin') else ''
            _tc_val = _tc_map.get(row["N°"],0)
            _tc_fmt = f"${_tc_val:,.0f}".replace(",",".") if _tc_val else "—"
            _th_tc = '<th>Total costo</th>' if st.session_state.get('modo_admin') else ''
            _td_tc = (f'<td style="text-align:right;font-size:0.82rem;font-weight:700;color:#0f172a;">{_tc_fmt}'
                      f'<br><span style="font-size:0.72em;color:#94a3b8;font-weight:400;">base+IVA · sin margen · sin Varios</span></td>'
                      if st.session_state.get('modo_admin') else '')
            _th_compras = '<th class="th-adj">🛒 Compras</th>' if st.session_state.get('modo_admin') else ''
            _td_compras = (f'<td style="text-align:center;background:#fef3c7;font-weight:700;color:#0f172a;">{row.get("ComprasOK","—")}</td>'
                           if st.session_state.get('modo_admin') else '')
            _ct_color = 'color:#16a34a;font-weight:700;' if row['ContratoCol']=='✅ Sí' else 'color:#94a3b8;'
            _emp_color = 'color:#16a34a;font-weight:700;' if row['EmpresaCol']=='✅ Sí' else 'color:#94a3b8;'
            _pln_color = 'color:#16a34a;font-weight:700;' if row['Plano']=='✅ Sí' else 'color:#94a3b8;'
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
                        f'font-family:inherit;">📋 Motivo</button>')
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
                    _lbl='⚠️ FINALIZADO' if _ret else '🟣 FINALIZADO'
                    _fab_html_cot=(f'<span style="color:{_col};font-weight:700;display:inline-block;font-variant-numeric:tabular-nums;">{_tx}</span>'
                                   f'<br><span style="font-size:0.72em;color:{_col};font-weight:700;">{_lbl}</span>')
                except: _fab_html_cot='<span style="color:#7c3aed;font-weight:700;">🟣 FINALIZADO</span>'
            elif _tiene_acta_cot:
                _fab_html_cot='<span style="color:#7c3aed;font-weight:700;">🟣 FINALIZADO</span>'
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
                    _cf='#dc2626' if _cr else '#7c3aed'; _lf='⚠️ FINALIZADO' if _cr else '🟣 FINALIZADO'
                    _fidel_html_cot=(f'<div style="display:flex;align-items:center;gap:8px;">'
                        f'<span style="color:{_cf};font-weight:700;font-variant-numeric:tabular-nums;min-width:70px;">⏳ {_tx4}</span>'
                        f'<span style="font-size:1.3rem;font-weight:900;color:{_cf};">{_pu}%</span></div>'
                        f'<span style="font-size:0.72em;color:#64748b;font-weight:600;">📅 {_fs}</span>'
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
                        _retraso_html_cot=(f'<span style="color:#dc2626;font-weight:700;font-variant-numeric:tabular-nums;">⚠️ {_tr2}</span>'
                                           f'<br><span style="font-size:0.72em;color:#dc2626;font-weight:600;">tiempo en contra</span>')
                    else:
                        _retraso_html_cot=(f'<span style="color:#16a34a;font-weight:700;font-variant-numeric:tabular-nums;">✅ {_tr2}</span>'
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
                                f'style="color:{_col5};font-weight:700;font-variant-numeric:tabular-nums;min-width:70px;">⏳ {_hr5}d háb.</span>'
                                f'<span style="font-size:1.3rem;font-weight:900;color:{_col5};">{_pf5}%</span></div>'
                                f'<span style="font-size:0.72em;color:#64748b;font-weight:600;">📅 {_fs5}</span>'
                                f'<br><span style="font-size:0.68em;color:#94a3b8;">{_pl} días hábiles</span>')
                        else:
                            _hv=dias_habiles_entre(_dent5,_hoy)
                            _fidel_html_cot=('<span style="color:#dc2626;font-weight:700;">⚠️ VENCIDO</span>'
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
            rows_html+=(f"<tr{_fila_class} data-est='{_est_attr}'>"
                f"<td data-ep=\"{row['N°']}\" style=\"cursor:pointer;font-weight:700;color:#3b82f6;\" title=\"Click para copiar {row['N°']}\">{row['N°']} 📋</td>"
                f"<td style='font-size:0.82rem;font-weight:700;color:#0f172a;line-height:1.5;'>{row['Cliente'] or '—'}"
                f"<br><button class='_datos_btn' data-ep=\"{row['N°']}\" style='margin-top:2px;background:#dbeafe;color:#1d4ed8;border:1px solid #93c5fd;border-radius:6px;padding:1px 8px;font-size:0.68rem;font-weight:700;cursor:pointer;font-family:inherit;'>📋 Datos</button></td>"
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
        _todos_activo = not _filtro_activo_badge
        _todos_bg = '#6d28d9' if _todos_activo else '#ede9fe'
        _todos_col = '#fff' if _todos_activo else '#6d28d9'
        _n_total = len(st.session_state.resultados_busqueda)
        _badge_items = [('TODOS',_todos_bg,_todos_col,'',f'Todos ({_n_total})','_fbtn_TODOS')]
        _badge_map = [
            ('PROYECTO TERMINADO','#ede9fe','#7c3aed','#5b21b6','🟣 terminados'),
            ('ADJUDICADO','#dbeafe','#1d4ed8','#1e40af','🔵 adjudicados'),
            ('AUTORIZADO CON PLANO','#dcfce7','#15803d','#166534','🟢 aut. c/plano'),
            ('AUTORIZADO','#dcfce7','#15803d','#166534','🟢 autorizados'),
            ('BORRADOR CON PLANO','#ffedd5','#c2410c','#9a3412','🟠 borrador c/plano'),
            ('BORRADOR','#fef9c3','#854d0e','#713f12','🟡 borrador'),
            ('INCOMPLETO CON PLANO','#fee2e2','#dc2626','#991b1b','🔴 incompleto c/plano'),
            ('INCOMPLETO','#fee2e2','#dc2626','#991b1b','🔴 incompletos'),
            ('RECHAZADO','#fee2e2','#b91c1c','#7f1d1d','❌ rechazados'),
        ]
        _sel_map2 = {
            'PROYECTO TERMINADO':'_fbtn_TER','ADJUDICADO':'_fbtn_ADJ',
            'AUTORIZADO CON PLANO':'_fbtn_ACP','AUTORIZADO':'_fbtn_AUT',
            'BORRADOR CON PLANO':'_fbtn_BCP','BORRADOR':'_fbtn_BOR',
            'INCOMPLETO CON PLANO':'_fbtn_ICP','INCOMPLETO':'_fbtn_INC','RECHAZADO':'_fbtn_REC'
        }
        for _key,_bg,_col,_col_act,_lbl in _badge_map:
            _cnt=_estados_cnt_total.get(_key,0)
            if _cnt:
                _ea=_filtro_activo_badge==_key
                _bg_b=_col_act if _ea else _bg; _col_b='#fff' if _ea else _col
                _shadow=f'box-shadow:0 0 0 2px {_col_act};' if _ea else ''
                _badge_items.append((_key,_bg_b,_col_b,_shadow,f'{_lbl} ({_cnt})',_sel_map2.get(_key,'_fbtn_TODOS')))

        _col_badge, _col_ref = st.columns([5, 0.7])
        with _col_badge:
            _bh=''
            for _bk,_bbg,_bcol,_bshadow,_btxt,_bsel in _badge_items:
                _bh+=(f'<span data-filtro="{_bk}" data-sel="{_bsel}" style="cursor:pointer;background:{_bbg};color:{_bcol};'
                      f'{_bshadow}padding:5px 14px;border-radius:99px;font-size:13px;font-weight:700;'
                      f'font-family:Montserrat,sans-serif;letter-spacing:0.03em;'
                      f'margin-right:6px;display:inline-block;" class="_badge_filtro">{_btxt}</span>')
            st.markdown(_bh, unsafe_allow_html=True)
        with _col_ref:
            if st.button("🔄", key="cot_refresh_tabla", help="Actualizar resultados", use_container_width=True):
                st.session_state.resultados_busqueda = None; st.rerun()

        st.markdown('<style>iframe[height="0"]{display:none!important;margin:0!important;padding:0!important;}</style>', unsafe_allow_html=True)
        components.html("""
<style>html,body{margin:0;padding:0;height:0;overflow:hidden;}</style>
<script>
(function(){
  var D=window.parent.document;var _af='';
  function filterRows(val){
    window.parent._ecBadgeFilter=val||'';
    D.querySelectorAll('tr[data-est]').forEach(function(r){
      r.style.display=(!val||val==='TODOS'||r.getAttribute('data-est')===val)?'':'none';
    });
    D.querySelectorAll('._badge_filtro').forEach(function(b){
      var bv=b.getAttribute('data-filtro');
      var isAct=(!val||val==='TODOS')?(bv==='TODOS'):(bv===val);
      b.style.outline=isAct?('2px solid '+b.style.color):'';
    });
  }
  function navToFilter(val){
    var base=window.parent.location.pathname;
    var dest=(val&&val!=='TODOS')?base+'?_filtro_estado='+encodeURIComponent(val):base;
    window.parent.location.href=dest;
  }
  function init(){
    D.querySelectorAll('._badge_filtro').forEach(function(b){
      if(b._filt_bound) return; b._filt_bound=true;
      b.addEventListener('click',function(){
        var val=this.getAttribute('data-filtro');
        var newVal=(_af===val&&val!=='TODOS')?'':val;
        _af=newVal; filterRows(newVal); navToFilter(newVal);
      });
    });
  }
  setTimeout(function(){
    var qp=new URLSearchParams(window.parent.location.search);
    var qpVal=qp.get('_filtro_estado')||'';
    if(qpVal){_af=qpVal;filterRows(qpVal);} init();
  },400);
  setInterval(init,2000);
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
        </style>
        <div style="border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);border:1px solid #e2e8f0;overflow-x:auto;">
            <div style="{_altura_css}">
                <table class='resultados-table' style='margin:0;border-radius:0;box-shadow:none;min-width:1700px;table-layout:auto;white-space:nowrap;'>
                    <thead style='position:sticky;top:0;z-index:2;'>
                        <tr><th>Presupuesto</th><th>Cliente</th><th>Total proyecto</th>{_th_tc}<th>Asesor</th><th>Estado</th><th>Creación</th><th>Demora</th><th>Autorización</th><th>Empresa</th>{_th_margen}<th>Contrato</th><th>Plano</th><th>Modif.</th><th class="th-cierre">$ Cierre de venta</th><th class="th-adj">Fecha adjudicación</th>{_th_compras}<th class="th-adj">Tiempo fabricación</th><th class="th-adj">Fidelización cliente</th><th class="th-adj">Retraso proyecto</th></tr>
                    </thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
        </div>"""
        st.markdown(html_table, unsafe_allow_html=True)

        _nres_txt = str(n_resultados)+(" resultado" if n_resultados==1 else " resultados")
        _scroll_html=(
            '<style>.tbl-scroll-wrap{display:flex;align-items:center;gap:8px;margin-top:4px;justify-content:space-between;}'
            '.tbl-scroll-right{display:flex;align-items:center;gap:8px;}'
            '.tbl-scroll-btn{background:rgba(15,23,42,0.7);color:#e2e8f0;border:1px solid rgba(255,255,255,0.12);border-radius:8px;padding:4px 14px;font-size:1rem;cursor:pointer;font-weight:700;line-height:1;}'
            '.tbl-scroll-btn:hover{background:rgba(37,99,235,0.7);color:#fff;}'
            '.tbl-scroll-label{font-size:10px;color:#94a3b8;font-family:sans-serif;}'
            '.tbl-n-res{font-size:0.8rem;color:#888;font-family:sans-serif;}</style>'
            '<div class="tbl-scroll-wrap">'
            '  <span class="tbl-n-res">'+_nres_txt+'</span>'
            '  <div class="tbl-scroll-right">'
            '    <button class="tbl-scroll-btn" id="btn-left">&#9664;</button>'
            '    <span class="tbl-scroll-label">scroll horizontal</span>'
            '    <button class="tbl-scroll-btn" id="btn-right">&#9654;</button>'
            '  </div></div>'
            '<script>(function(){'
            'var D=window.parent.document;'
            'function gS(){var t=D.querySelector(".resultados-table");if(!t)return null;var el=t.parentElement;'
            'while(el){var s=window.parent.getComputedStyle(el);if(s.overflowX==="auto"||s.overflowX==="scroll")return el;el=el.parentElement;}return t.parentElement;}'
            'document.getElementById("btn-left").addEventListener("click",function(){var t=gS();if(t)t.scrollBy({left:-300,behavior:"smooth"});});'
            'document.getElementById("btn-right").addEventListener("click",function(){var t=gS();if(t)t.scrollBy({left:300,behavior:"smooth"});});'
            '})();</script>')
        components.html(_scroll_html, height=48)

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
        var ex2=D.getElementById('_datos_modal'); if(ex2) ex2.remove();
        var ov=D.createElement('div'); ov.id='_datos_modal';
        ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:99999;display:flex;align-items:center;justify-content:center;';
        var box=D.createElement('div'); box.style.cssText='background:#1e293b;border:1px solid #334155;border-radius:16px;padding:28px 32px;max-width:460px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,0.5);';
        var hdr=D.createElement('div'); hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;';
        var ttl=D.createElement('div'); ttl.style.cssText='font-size:1rem;font-weight:900;color:#f1f5f9;'; ttl.textContent='👤 Datos del cliente — '+ep;
        var cls=D.createElement('button'); cls.textContent='✖ Cerrar';
        cls.style.cssText='background:rgba(100,116,139,0.2);color:#94a3b8;border:1px solid rgba(100,116,139,0.3);border-radius:6px;padding:3px 10px;cursor:pointer;font-size:0.8rem;font-weight:700;';
        hdr.appendChild(ttl); hdr.appendChild(cls);
        var bdy=D.createElement('div'); bdy.style.cssText='background:#0f172a;border-radius:10px;padding:14px 16px;font-size:0.88rem;color:#e2e8f0;line-height:2;';
        var rows=[['🪪 RUT',cli.rut],['📞 Teléfono',cli.tel],['✉️ Email',cli.email],['🏠 Dirección',cli.dir],
                  ['🏙️ Comuna',cli.comuna],['🗺️ Región',cli.region],['🏢 Empresa',cli.empresa],
                  ['📍 Dir. instalación',cli.inst_dir],['🏙️ Comuna inst.',cli.inst_comuna],['🗺️ Región inst.',cli.inst_region]];
        var html='<table style="width:100%;border-collapse:collapse;">';
        rows.forEach(function(r){if(!r[1])return;html+='<tr><td style="color:#94a3b8;font-size:0.78rem;padding:3px 8px 3px 0;white-space:nowrap;">'+r[0]+'</td><td style="color:#f1f5f9;font-weight:600;padding:3px 0;">'+r[1]+'</td></tr>';});
        html+='</table>'; bdy.innerHTML=html;
        box.appendChild(hdr); box.appendChild(bdy); ov.appendChild(box); D.body.appendChild(ov);
        cls.addEventListener('click',function(){ov.remove();}); ov.addEventListener('click',function(ev){if(ev.target===ov)ov.remove();});
    });
    D.addEventListener('click', function(e) {
        var btn = e.target && e.target.closest ? e.target.closest('._mat_btn') : null;
        if(!btn) return; e.stopPropagation();
        var ep=btn.getAttribute('data-ep')||''; var mat={};
        try{mat=(typeof MAT_DATA!=='undefined'?MAT_DATA:{})[ep]||{};}catch(ex){}
        var ex2=D.getElementById('_mat_modal'); if(ex2) ex2.remove();
        var ov=D.createElement('div'); ov.id='_mat_modal';
        ov.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.65);z-index:99999;display:flex;align-items:center;justify-content:center;';
        var box=D.createElement('div'); box.style.cssText='background:#1e293b;border:1px solid #334155;border-radius:16px;padding:28px 32px;max-width:500px;width:92%;max-height:80vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.5);';
        var hdr=D.createElement('div'); hdr.style.cssText='display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;';
        var ttl=D.createElement('div'); ttl.style.cssText='font-size:1rem;font-weight:900;color:#f1f5f9;'; ttl.textContent='📋 Materiales — '+ep;
        var cls=D.createElement('button'); cls.textContent='✖ Cerrar';
        cls.style.cssText='background:rgba(99,102,241,0.15);color:#a5b4fc;border:1px solid rgba(99,102,241,0.3);border-radius:6px;padding:3px 10px;cursor:pointer;font-size:0.8rem;font-weight:700;';
        hdr.appendChild(ttl); hdr.appendChild(cls);
        var pct=mat.pct||0; var pc=pct===100?'#16a34a':(pct>=50?'#f97316':'#2563eb');
        var pb=D.createElement('div'); pb.style.cssText='background:#0f172a;border-radius:8px;padding:10px 12px;margin-bottom:14px;';
        pb.innerHTML='<div style="background:#1e293b;border-radius:4px;height:6px;margin-bottom:6px;"><div style="background:'+pc+';border-radius:4px;height:6px;width:'+pct+'%;"></div></div><div style="font-size:0.78rem;color:#94a3b8;">'+(mat.done||0)+' de '+(mat.total||0)+' secciones &mdash; '+pct+'%</div>';
        var bdy=D.createElement('div'); var cats=mat.cats||[];
        if(!cats.length){bdy.innerHTML='<div style="color:#64748b;font-size:0.9rem;text-align:center;padding:20px 0;">Sin datos aún</div>';}
        else{cats.forEach(function(c){var ce=D.createElement('div');ce.style.cssText='margin-bottom:12px;';var ct=D.createElement('div');ct.style.cssText='font-size:0.78rem;font-weight:700;color:#60a5fa;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;';ct.textContent=c.cat;ce.appendChild(ct);(c.grupos||[]).forEach(function(g){var rw=D.createElement('div');rw.style.cssText='display:flex;align-items:baseline;gap:8px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,0.05);font-size:0.85rem;';rw.innerHTML='<span>'+(g.val?'✅':'⬜')+'</span><span style="color:#cbd5e1;font-weight:600;">'+g.tg+'</span><span style="color:#64748b;">:</span><span style="color:'+(g.val?'#60a5fa':'#475569')+';">'+(g.val||'—')+'</span>';ce.appendChild(rw);});bdy.appendChild(ce);});}
        box.appendChild(hdr); box.appendChild(pb); box.appendChild(bdy); ov.appendChild(box); D.body.appendChild(ov);
        cls.addEventListener('click',function(){ov.remove();}); ov.addEventListener('click',function(ev){if(ev.target===ov)ov.remove();});
    });
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
            s=s%60;m=m%60;h=h%24; var txt='⚠️ '; if(d>0)txt+=d+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.textContent=txt;
        });
        D.querySelectorAll('.fidel-live').forEach(function(el){
            var hasta=parseInt(el.getAttribute('data-hasta')); var plazo=parseInt(el.getAttribute('data-plazo'))||1; var adjTs=parseInt(el.getAttribute('data-adj'))||0;
            if(!hasta) return; var diff=hasta-Date.now();
            if(diff<=0){el.textContent='⚠️ VENCIDO';el.style.color='#dc2626';return;}
            var ts=Math.floor(diff/1000); var dc=Math.floor(ts/86400); var rs=ts%86400; var h=Math.floor(rs/3600); var m=Math.floor((rs%3600)/60); var s=rs%60;
            var txt='⏳ '; if(dc>0)txt+=dc+'d '; if(h>0)txt+=h+'h '; if(m>0)txt+=m+'m '; txt+=s+'s'; el.textContent=txt;
            var tr=adjTs?(Date.now()-adjTs):0; var tot=plazo*86400000; var pa=adjTs?Math.min((tr/tot)*100,100):0;
            var col=pa<50?'#16a34a':(pa<80?'#f97316':'#dc2626'); el.style.color=col;
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
            var orig=td.innerHTML; var origColor=td.style.color; td.innerHTML='✅ ¡Copiado!'; td.style.color='#10b981';
            setTimeout(function(){td.innerHTML=orig;td.style.color=origColor;},1200);
        });
    }
    setTimeout(initEPCopy,500);
})();
</script>""", height=0)

        st.markdown("### Seleccionar cotización")
        opciones = []
        _dd_options_list = []
        _ec_map={'PROYECTO TERMINADO':('#7c3aed','#fff','🟣'),'ADJUDICADO':('#2563eb','#fff','🔵'),
                 'AUTORIZADO CON PLANO':('#15803d','#fff','🟢'),'AUTORIZADO':('#15803d','#fff','🟢'),
                 'BORRADOR CON PLANO':('#c2410c','#fff','🟠'),'BORRADOR':('#d97706','#212529','🟡'),
                 'INCOMPLETO CON PLANO':('#dc2626','#fff','🔴'),'INCOMPLETO':('#dc2626','#fff','🔴'),
                 'RECHAZADO':('#991b1b','#fbbf24','❌')}
        for idx, row in df_resultados.iterrows():
            if row.get('Acta_URL',''): estado="PROYECTO TERMINADO"
            elif row.get('Tiene_Notariado',0): estado="ADJUDICADO"
            elif str(row.get('Motivo_Rechazo','') or '').strip() not in ('','None','nan'): estado="RECHAZADO"
            else:
                dc2=all([row['Cliente'],row['Email']]); ac2=any([row['Asesor'],row['Asesor_Email'],row['Asesor_Tel']])
                if row['Margen'] and row['Margen']>0:
                    estado=("AUTORIZADO CON PLANO" if row['Tiene_Plano'] else "AUTORIZADO") if (dc2 and ac2) else ("INCOMPLETO CON PLANO" if row['Tiene_Plano'] else "INCOMPLETO")
                else:
                    if dc2 and ac2: estado="BORRADOR CON PLANO" if row['Tiene_Plano'] else "BORRADOR"
                    else: estado="INCOMPLETO CON PLANO" if row['Tiene_Plano'] else "INCOMPLETO"
            plano_ind="📎" if row['Tiene_Plano'] else ""
            _total_limpio=""
            for _rb in (st.session_state.resultados_busqueda or []):
                if str(_rb[0])==str(row['N°']):
                    _total_limpio=f"${_rb[4]:,.0f}".replace(",",".") if _rb[4] else "$0"; break
            _lbl=f"{row['N°']} - {row['Cliente'] or 'S/C'} ({row['FechaPlana']}) - {_total_limpio} - {estado} {plano_ind}".strip()
            opciones.append(_lbl)
            _lbl_m=f"{row['N°']} - {row['Cliente'] or 'S/C'} ({row['FechaPlana']}) - {_total_limpio}".strip()
            _ec=_ec_map.get(estado,('#64748b','#fff',''))
            _dd_options_list.append({'ep':str(row['N°']),'label':_lbl,'est':estado,'lm':_lbl_m,'bg':_ec[0],'col':_ec[1],'em':_ec[2]})

        st.markdown('<style>[data-testid="stTextInput"]:has(input[placeholder="__ecdd_trg__"]){position:fixed!important;top:-9999px!important;left:-9999px!important;opacity:0!important;pointer-events:none!important;}</style>', unsafe_allow_html=True)
        _ecdd_trigger = st.text_input("Selector EP", key="_sel_ep_trigger", label_visibility="collapsed", placeholder="__ecdd_trg__")
        if _ecdd_trigger and st.session_state.get('selector_ep_num') != _ecdd_trigger:
            st.session_state['selector_ep_num'] = _ecdd_trigger
            st.rerun()

        if opciones:
            _sel_ep_now = st.session_state.get('selector_ep_num', '')
            if not _sel_ep_now:
                _sel_ep_now = opciones[0].split(' - ')[0]
                st.session_state['selector_ep_num'] = _sel_ep_now
            _eps_disponibles = [o['ep'] for o in _dd_options_list]
            if _sel_ep_now not in _eps_disponibles and _eps_disponibles:
                _sel_ep_now = _eps_disponibles[0]
                st.session_state['selector_ep_num'] = _sel_ep_now
            _dd_json_str = json.dumps(_dd_options_list, ensure_ascii=False)
            _sel_ep_safe = _sel_ep_now.replace('\\', '\\\\').replace("'", "\\'")
            # Dropdown vive DENTRO del iframe: evita el bug de position:fixed roto por
            # el transform CSS del contenedor principal de Streamlit.
            # El iframe se redimensiona con window.frameElement al abrir/cerrar.
            # Wheel events dentro del iframe NO propagan al padre -> scroll aislado.
            _dd_html_tpl = (
                '<style>'
                '*{box-sizing:border-box;margin:0;padding:0;}'
                'body{background:transparent;overflow:visible;font-family:Montserrat,sans-serif;}'
                '#dt{display:flex;align-items:center;justify-content:space-between;background:#fff;'
                'border:1.5px solid #d1d5db;border-radius:8px;padding:10px 14px;cursor:pointer;'
                'height:46px;font-size:0.82rem;font-family:Montserrat,sans-serif;color:#0f172a;'
                'user-select:none;transition:border-color .15s;}'
                '#dt:hover{border-color:#6366f1;}'
                '#dt.open{border-color:#6366f1;border-bottom-left-radius:0;border-bottom-right-radius:0;}'
                '#dtx{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}'
                '#dar{margin-left:8px;color:#6b7280;font-size:0.66rem;transition:transform .2s;}'
                '#dt.open #dar{transform:rotate(180deg);}'
                '#dd{display:none;background:#fff;border:1.5px solid #6366f1;border-top:none;'
                'border-radius:0 0 8px 8px;box-shadow:0 8px 24px rgba(0,0,0,.14);overflow:hidden;}'
                '#dd_s{width:100%;padding:8px 12px;border:none;border-bottom:1px solid #e5e7eb;'
                'font-size:.82rem;font-family:Montserrat,sans-serif;outline:none;'
                'background:#f8fafc;color:#0f172a;display:block;}'
                '#dd_o{max-height:280px;overflow-y:auto;overscroll-behavior:contain;}'
                '.dd_i{padding:9px 14px;cursor:pointer;font-size:.85rem;'
                'font-family:Montserrat,sans-serif;color:#1e293b;'
                'border-bottom:1px solid #f1f5f9;display:flex;align-items:center;gap:8px;}'
                '.dd_i:hover{background:#eff6ff;}.dd_i.sel{background:#dbeafe;font-weight:700;}'
                '#dd_em{padding:12px;text-align:center;color:#94a3b8;font-size:.8rem;display:none;}'
                '</style>'
                '<div id="dt" onclick="tog()">'
                '<span id="dtx">&#128194; Selecciona una cotizaci&#243;n</span>'
                '<span id="dar">&#9660;</span>'
                '</div>'
                '<div id="dd">'
                '<input id="dd_s" type="text" placeholder="&#128269; Buscar..." oninput="flt(this.value,BF)">'
                '<div id="dd_o"></div>'
                '<div id="dd_em">Sin resultados</div>'
                '</div>'
                "<script>"
                "var SEL='SEL_PLACEHOLDER';var OPTS=OPTS_PLACEHOLDER;var BF='';var isOpen=false;"
                "var PD=window.parent.document;"
                "['_ecdd_css','_ecdd_css2','_ecdd_css3','_ecdd_css4'].forEach(function(id){"
                "var el=PD.getElementById(id);if(el)el.remove();});"
                "function _rz(h){try{if(window.frameElement)window.frameElement.style.height=h+'px';}catch(e){}}"
                "function _co(e){if(!isOpen)return;cls();}"
                "function _ke(e){if(e.key==='Escape')cls();}"
                "function tog(){if(isOpen)cls();else opn();}"
                "function opn(){"
                "isOpen=true;"
                "document.getElementById('dt').classList.add('open');"
                "document.getElementById('dd').style.display='block';"
                "var h=46+42+Math.min(OPTS.length*43,282)+14;_rz(h);"
                "flt('',BF);"
                "setTimeout(function(){document.getElementById('dd_s').focus();},60);"
                "PD.addEventListener('click',_co);"
                "PD.addEventListener('keydown',_ke);"
                "}"
                "function cls(){"
                "isOpen=false;"
                "document.getElementById('dt').classList.remove('open');"
                "document.getElementById('dd').style.display='none';"
                "_rz(52);"
                "PD.removeEventListener('click',_co);"
                "PD.removeEventListener('keydown',_ke);"
                "}"
                "function sel(ep,lbl){"
                "document.getElementById('dtx').textContent=lbl;"
                "cls();"
                "var inp=PD.querySelector('input[placeholder=\"__ecdd_trg__\"]');"
                "if(inp){"
                "var _nv=Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype,'value').set;"
                "_nv.call(inp,ep);"
                "inp.focus();"
                "inp.dispatchEvent(new window.parent.KeyboardEvent('keydown',"
                "{key:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true}));"
                "}}"
                "function flt(q,bf){"
                "var ov=document.getElementById('dd_o');if(!ov)return;var vis=0;q=q.toLowerCase();"
                "ov.querySelectorAll('.dd_i').forEach(function(o){"
                "var est=o.getAttribute('data-est');"
                "var _lbl=o.querySelector('.dd_lbl');"
                "var txt=(_lbl?_lbl.textContent:o.textContent).toLowerCase();"
                "var ok=(!bf||bf==='TODOS'||est===bf)&&(!q||txt.indexOf(q)!==-1);"
                "o.style.display=ok?'':'none';if(ok)vis++;});"
                "document.getElementById('dd_em').style.display=vis===0?'':'none';}"
                "var ov=document.getElementById('dd_o');"
                "OPTS.forEach(function(o){"
                "var d=document.createElement('div');"
                "d.className='dd_i'+(o.ep===SEL?' sel':'');"
                "d.setAttribute('data-ep',o.ep);"
                "d.setAttribute('data-est',o.est);"
                "var _t=document.createElement('span');"
                "_t.className='dd_lbl';"
                "_t.style.cssText='overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0;';"
                "_t.textContent=o.lm||o.label;"
                "d.appendChild(_t);"
                "var _b=document.createElement('span');"
                "_b.textContent=(o.em||'')+' '+(o.est||'');"
                "_b.style.cssText='background:'+(o.bg||'#64748b')+';color:'+(o.col||'#fff')+"
                "';padding:2px 9px;border-radius:99px;font-size:0.65rem;font-weight:700;"
                "white-space:nowrap;flex-shrink:0;font-family:Montserrat,sans-serif;';"
                "d.appendChild(_b);"
                "d.onclick=function(e){e.stopPropagation();sel(o.ep,o.lm||o.label);};"
                "ov.appendChild(d);"
                "});"
                "if(SEL){var s=OPTS.find(function(o){return o.ep===SEL;});"
                "if(s)document.getElementById('dtx').textContent=s.lm||s.label;}"
                "setInterval(function(){"
                "var f=window.parent._ecBadgeFilter||'';"
                "if(f!==BF){BF=f;"
                "var sinp=document.getElementById('dd_s');"
                "flt(sinp?sinp.value:'',BF);"
                "}},100);"
                "</script>"
            )
            _dd_html = _dd_html_tpl.replace('SEL_PLACEHOLDER', _sel_ep_safe).replace('OPTS_PLACEHOLDER', _dd_json_str)
            _col_sel, _col_rec_btn = st.columns([4, 1])
            with _col_sel:
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 4px 0;">&#128194; Selecciona una cotizaci&#243;n</div>', unsafe_allow_html=True)
                components.html(_dd_html, height=52, scrolling=False)
            cotizacion_seleccionada = _sel_ep_now
            with _col_rec_btn:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                _btn_rec_placeholder = st.empty()

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
                            _pdf_log_bytes = generar_pdf_log(numero_seleccionado, _logs_ep)
                            st.download_button(
                                label=f"&#128203; Descargar historial PDF ({len(_logs_ep)} registros · {_n_mods} modif.)",
                                data=_pdf_log_bytes, file_name=f"historial_{numero_seleccionado}.pdf",
                                mime="application/pdf", use_container_width=True, key="btn_download_log")
                        except:
                            st.warning("&#9888;&#65039; No se pudo generar el historial PDF. Intenta nuevamente.")
                    else:
                        st.caption("&#128203; Sin registros de modificaciones a&#250;n")

            st.markdown("---")
            st.markdown("### Acciones")
            _sel_motivo_rec = ""
            _sel_adj_check = False
            try:
                _sel_rec_q = supabase_admin.table("cotizaciones").select("motivo_rechazo,fecha_rechazo,contrato_notariado_url").eq("numero", numero_seleccionado).execute()
                if _sel_rec_q.data:
                    _sel_motivo_rec = _sel_rec_q.data[0].get("motivo_rechazo","") or ""
                    _sel_adj_check = bool(_sel_rec_q.data[0].get("contrato_notariado_url",""))
            except:
                pass
            if not _sel_adj_check:
                if _sel_motivo_rec:
                    st.markdown(f'<div style="background:#fee2e2;border-left:4px solid #dc2626;border-radius:0 8px 8px 0;padding:10px 14px;margin-bottom:10px;"><div style="font-size:12px;font-weight:700;color:#b91c1c;">&#10060; Presupuesto RECHAZADO</div><div style="font-size:11px;color:#991b1b;margin-top:3px;"><b>Motivo:</b> {_sel_motivo_rec}</div></div>', unsafe_allow_html=True)
                    with _btn_rec_placeholder:
                        if st.button("&#8617;&#65039; Quitar rechazo", use_container_width=True, key="btn_quitar_rechazo"):
                            supabase_admin.table("cotizaciones").update({"motivo_rechazo": None, "fecha_rechazo": None}).eq("numero", numero_seleccionado).execute()
                            st.session_state.resultados_busqueda = None
                            st.session_state.pop('_show_rechazo_dialog', None)
                            st.success("&#9989; Rechazo eliminado")
                            st.rerun()
                else:
                    with _btn_rec_placeholder:
                        st.markdown('<style>.st-key-btn_rechazar_cot button{background-color:#dc2626!important;color:white!important;border:none!important;font-size:0.75rem!important;padding:4px 10px!important;}.st-key-btn_rechazar_cot button:hover{background-color:#b91c1c!important;}</style>', unsafe_allow_html=True)
                        if st.button("&#10060; Rechazar", use_container_width=True, key="btn_rechazar_cot"):
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
                                st.session_state.pop('_show_rechazo_dialog', None)
                                st.session_state.resultados_busqueda = None
                                st.success(f"&#9989; {numero_seleccionado} marcado como rechazado")
                                st.rerun()
                            else:
                                st.warning("&#9888;&#65039; Debes ingresar un motivo.")
                _dialogo_rechazo()

            col_acc1, col_acc0, col_acc2, col_acc3, col_acc5, col_acc4 = st.columns(6)
            with col_acc1:
                if tiene_margen_seleccionado and not st.session_state.modo_admin:
                    st.button("&#128194; Cargar presupuesto", use_container_width=True, disabled=True,
                              help="No se puede editar un presupuesto autorizado")
                else:
                    if st.button("&#128194; Cargar presupuesto", use_container_width=True, key="btn_cargar_presupuesto", type="primary"):
                        tiene_sin_guardar = (len(st.session_state.carrito) > 0 and st.session_state.cotizacion_cargada != numero_seleccionado)
                        if tiene_sin_guardar:
                            st.session_state.mostrar_advertencia_carga = True
                            st.session_state.numero_a_cargar_pendiente = numero_seleccionado
                            st.rerun()
                        else:
                            if preparar_carga_cotizacion(numero_seleccionado):
                                st.success(f"&#9989; Cotizaci&#243;n {numero_seleccionado} cargada")
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
                                st.rerun()
                    with col_no:
                        if st.button("&#128465;&#65039; No, descartar", use_container_width=True, key="dialog_btn_no"):
                            st.session_state.mostrar_advertencia_carga = False
                            if preparar_carga_cotizacion(numero_pendiente):
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
                        st.download_button(label="&#128717; PDF Compras", data=_pdf_compras,
                            file_name=f"Compras_{numero_seleccionado}.pdf", mime="application/pdf",
                            use_container_width=True, key=f"pdf_compras_{numero_seleccionado}")
                else:
                    st.button("&#128717; PDF Compras", use_container_width=True, disabled=True,
                              help="Solo disponible para operaciones, admin y root" if _es_ejecutivo_pdf else None)

            with col_acc2:
                if cotizacion_para_pdf and _pdf_habilitado:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    pdf_buffer, _ = generar_pdf_completo(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da,
                                                          margen=margen_c, numero_cotizacion=numero_seleccionado)
                    st.download_button(label="&#128196; PDF Completo", data=pdf_buffer,
                        file_name=f"Presupuesto_Completo_{numero_seleccionado}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"pdf_completo_{numero_seleccionado}")
                else:
                    st.button("&#128196; PDF Completo", use_container_width=True, disabled=True,
                              help="Solo disponible para cotizaciones autorizadas" if _es_ejecutivo_pdf else None)

            with col_acc3:
                if cotizacion_para_pdf and _pdf_habilitado:
                    carrito_df_p, subtotal_p, iva_p, total_p, dc, da, fi, ft, dv, margen_c = preparar_pdf_data(cotizacion_para_pdf)
                    _desc_ep = cargar_descripciones_por_ep(numero_seleccionado, supa_url, bust_cache=True)
                    pdf_buffer, _ = generar_pdf_cliente(carrito_df_p, subtotal_p, iva_p, total_p, dc, fi, ft, dv, da,
                                                         margen=margen_c, numero_cotizacion=numero_seleccionado,
                                                         descripciones_ep=_desc_ep)
                    st.download_button(label="&#128274; PDF Cliente", data=pdf_buffer,
                        file_name=f"Presupuesto_Cliente_{numero_seleccionado}.pdf", mime="application/pdf",
                        use_container_width=True, key=f"pdf_cliente_{numero_seleccionado}")
                else:
                    st.button("&#128274; PDF Cliente", use_container_width=True, disabled=True,
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
                        st.download_button(label='&#127912; PDF Selecci&#243;n', data=_pdf_sel2,
                            file_name=f'Seleccion_Cliente_{_sel_ep2}.pdf', mime='application/pdf',
                            use_container_width=True, key=f'pdf_sel_{_sel_ep2}',
                            help=f'Selecci&#243;n del cliente ({_sel_pct2}% completado)')
                    else:
                        st.button('&#127912; PDF Selecci&#243;n', use_container_width=True, disabled=True,
                                  help='Sin selecciones del cliente a&#250;n')
                except Exception as _esel2:
                    st.button('&#127912; PDF Selecci&#243;n', use_container_width=True, disabled=True,
                              help=str(_esel2)[:200])

            with col_acc4:
                if cotizacion_seleccionada and tiene_plano_seleccionado:
                    label_visor = "&#128260; ACTUALIZAR PLANO" if (st.session_state.mostrar_visor and st.session_state.numero_en_visor == numero_seleccionado) else "&#128065;&#65039; VER PLANO"
                    if st.button(label_visor, use_container_width=True, type="primary", help="Ver plano adjunto"):
                        cot_btn = cargar_cotizacion(numero_seleccionado)
                        if cot_btn and cot_btn.get('plano_url'):
                            st.session_state.pdf_url = cot_btn['plano_url']
                            st.session_state.pdf_nombre = cot_btn.get('plano_nombre', 'plano.pdf')
                            st.session_state.mostrar_visor = True
                            st.session_state.numero_en_visor = numero_seleccionado
                            st.rerun()
                else:
                    st.button("&#128065;&#65039; VER PLANO", use_container_width=True, disabled=True, help="Sin plano adjunto")

            if st.session_state.mostrar_visor and st.session_state.pdf_url:
                with st.expander("&#128196; Vista Previa del Plano", expanded=True):
                    st.markdown(f"**Archivo:** {st.session_state.pdf_nombre} — cotizaci&#243;n `{st.session_state.numero_en_visor}`")
                    navegador = detectar_navegador()
                    pdf_url_visor = st.session_state.pdf_url
                    pdf_url_encoded = urllib.parse.quote(pdf_url_visor, safe='')
                    google_viewer_url = f"https://docs.google.com/viewer?url={pdf_url_encoded}&embedded=true"
                    usar_google = navegador['needs_google_viewer']
                    components.html(f"""<style>@keyframes spin{{from{{transform:rotate(0deg)}}to{{transform:rotate(360deg)}}}}
body,html{{margin:0;padding:0;overflow:hidden;}}
#pdf-wrap{{width:100%;height:680px;border:2px solid #e2e8f0;border-radius:12px;overflow:hidden;box-shadow:0 4px 12px rgba(0,0,0,0.1);background:#f0f2f5;position:relative;}}
#pdf-loading{{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;background:#f0f2f5;z-index:2;gap:12px;transition:opacity 0.4s ease;}}
#pdf-spinner{{width:40px;height:40px;border:4px solid #cbd5e1;border-top-color:#5b7cfa;border-radius:50%;animation:spin 0.8s linear infinite;}}
#pdf-loading span{{color:#64748b;font-size:0.9rem;font-family:sans-serif;}}
#pdf-iframe{{position:absolute;inset:0;width:100%;height:100%;border:none;display:block;}}</style>
<div id="pdf-wrap"><div id="pdf-loading"><div id="pdf-spinner"></div><span id="pdf-status">Cargando PDF...</span></div><iframe id="pdf-iframe" src="" allow="fullscreen"></iframe></div>
<script>(function(){{
var iframe=document.getElementById('pdf-iframe');var loading=document.getElementById('pdf-loading');
var googleUrl="{google_viewer_url}";var directUrl="{pdf_url_visor}";var usingGoogle={"true" if usar_google else "false"};
function hideLoading(){{loading.style.opacity='0';setTimeout(function(){{loading.style.display='none';}},400);}}
if(usingGoogle){{iframe.src=googleUrl;setTimeout(function(){{if(loading.style.display!=='none')hideLoading();}},3000);
setTimeout(function(){{if(usingGoogle){{try{{var doc=iframe.contentDocument||iframe.contentWindow.document;if(!doc||!doc.body||doc.body.children.length===0){{usingGoogle=false;iframe.src=directUrl;setTimeout(hideLoading,4000);}}}}catch(e){{}}}};}},8000);
}}else{{iframe.src=directUrl;setTimeout(hideLoading,4000);}}}})();</script>""", height=710, scrolling=False)
                    try:
                        pdf_bytes = requests.get(st.session_state.pdf_url, timeout=15).content
                        st.download_button(label="&#128229; Descargar Plano", data=pdf_bytes,
                            file_name=st.session_state.pdf_nombre, mime="application/pdf",
                            use_container_width=True, key=f"descargar_plano_{st.session_state.numero_en_visor}")
                    except:
                        st.warning("&#9888;&#65039; No se pudo preparar la descarga. Intenta de nuevo.")

        st.markdown("---")
        st.markdown("### Estadisticas Rapidas")
        autorizadas = autorizadas_con_plano = borradores_con_plano = borradores = 0
        incompletos_con_plano = incompletos = total_cotizado = 0
        for row in st.session_state.resultados_busqueda:
            datos_completos = all([row[1], row[6], row[7]])
            asesor_completo = any([row[2], row[8], row[9]])
            total_cotizado += row[4] if row[4] else 0
            tiene_plano = bool(row[10]) if len(row) > 10 else False
            if not datos_completos or not asesor_completo:
                if tiene_plano: incompletos_con_plano += 1
                else: incompletos += 1
            elif row[5] and row[5] > 0:
                if tiene_plano: autorizadas_con_plano += 1
                else: autorizadas += 1
            else:
                if tiene_plano: borradores_con_plano += 1
                else: borradores += 1
        autorizadas_total = autorizadas + autorizadas_con_plano
        col_e1, col_e2, col_e3, col_e4, col_e5, col_e6 = st.columns(6)
        stats = [
            (col_e1, "&#128176; TOTAL COTIZADO", formato_clp(total_cotizado), "total", "Total de cotizaciones"),
            (col_e2, "&#127802; AUTORIZADAS", str(autorizadas_total), "autorizadas", f"{autorizadas_con_plano} con plano"),
            (col_e3, "&#129505; BORRADOR C/P", str(borradores_con_plano), "color:#f97316;", "Borradores con plano"),
            (col_e4, "&#127833; BORRADOR", str(borradores), "borradores", "Borradores sin plano"),
            (col_e5, "&#128308; INCOMPLETO C/P", str(incompletos_con_plano), "color:#ef4444;", "Incompletos con plano"),
            (col_e6, "&#128308; INCOMPLETO", str(incompletos), "incompletas", "Incompletos sin plano"),
        ]
        for col, title, number, css_class, desc in stats:
            with col:
                font_size = "1.6rem" if len(number) > 12 else ("2rem" if len(number) > 8 else "2.8rem")
                if css_class.startswith("color:"):
                    num_html = f'<div class="stats-number" style="{css_class};font-size:{font_size};">{number}</div>'
                else:
                    num_html = f'<div class="stats-number {css_class}" style="font-size:{font_size};">{number}</div>'
                st.markdown(f'<div class="stats-card"><div class="stats-title">{title}</div>{num_html}<div class="stats-desc">{desc}</div></div>', unsafe_allow_html=True)

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
    else:
        st.info("💡 No hay resultados. Realice una búsqueda para ver cotizaciones guardadas.")
