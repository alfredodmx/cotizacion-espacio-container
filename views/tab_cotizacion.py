"""
Tab PRESUPUESTO — Carrito de cotización, items, margen, PDF.
Migrado desde app.py líneas 9938-10797.
"""
import io as _io_excel
import json as _json
import math
import pandas as pd
import requests as _rq_excel
import streamlit as st
import streamlit.components.v1 as components
from datetime import datetime, timedelta
from repositories.cotizaciones_repo import guardar_cotizacion, generar_numero_unico
from services.cotizacion_service import aplicar_margen
from utils.formato import formato_clp, calcular_hash_estado
from utils.telefono import formatear_telefono


def _get_excel_bytes_activo(supabase_admin):
    try:
        _resp = supabase_admin.table('excel_versiones').select('archivo_url').eq('activa', True).limit(1).execute()
        if _resp.data:
            _url = _resp.data[0]['archivo_url']
            _r = _rq_excel.get(_url, timeout=15)
            _r.raise_for_status()
            return _io_excel.BytesIO(_r.content)
    except:
        pass
    return "cotizador.xlsx"


def _excel_src(supabase_admin):
    if 'excel_bytes_cache' not in st.session_state:
        st.session_state.excel_bytes_cache = _get_excel_bytes_activo(supabase_admin)
    return st.session_state.excel_bytes_cache


@st.cache_data(ttl=300, show_spinner=False)
def _leer_hoja_excel_cached(src_key, nombre_hoja):
    src = st.session_state.get('excel_bytes_cache', 'cotizador.xlsx')
    try:
        return pd.read_excel(src, sheet_name=nombre_hoja)
    except:
        return pd.DataFrame()


def _leer_hoja_excel(nombre_hoja, supabase_admin):
    _excel_src(supabase_admin)
    try:
        src = st.session_state.get('excel_bytes_cache', 'cotizador.xlsx')
        return pd.read_excel(src, sheet_name=nombre_hoja)
    except:
        return pd.DataFrame()


def _leer_bd_total(supabase_admin):
    try:
        src = _excel_src(supabase_admin)
        return pd.read_excel(src, sheet_name="BD Total")[["Item", "P. Unitario real"]]
    except:
        return pd.DataFrame(columns=["Item", "P. Unitario real"])


def _leer_hojas_disponibles(supabase_admin):
    try:
        src = _excel_src(supabase_admin)
        return pd.ExcelFile(src).sheet_names
    except:
        return []


def cargar_modelo(nombre_hoja, supabase_admin):
    df_modelo = _leer_hoja_excel(nombre_hoja, supabase_admin)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[df_modelo["Cantidad"] > 0]
    df_bd = _leer_bd_total(supabase_admin)
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    carrito = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        carrito.append({
            "Categoria": row["Categorias"], "Item": row["Item"],
            "Cantidad": row["Cantidad"], "Precio Unitario": row["P. Unitario real"], "Subtotal": subtotal
        })
    return carrito


def cargar_categoria_desde_modelo(nombre_hoja, categoria_objetivo, supabase_admin):
    df_modelo = _leer_hoja_excel(nombre_hoja, supabase_admin)
    df_modelo = df_modelo[["Categorias", "Item", "Cantidad"]].dropna()
    df_modelo = df_modelo[(df_modelo["Cantidad"] > 0) & (df_modelo["Categorias"] == categoria_objetivo)]
    df_bd = _leer_bd_total(supabase_admin)
    df_final = df_modelo.merge(df_bd, on="Item", how="left")
    categoria_items = []
    for _, row in df_final.iterrows():
        subtotal = row["Cantidad"] * row["P. Unitario real"]
        categoria_items.append({
            "Categoria": row["Categorias"], "Item": row["Item"],
            "Cantidad": row["Cantidad"], "Precio Unitario": row["P. Unitario real"], "Subtotal": subtotal
        })
    return categoria_items


def limpiar_todo():
    st.session_state.carrito = []
    st.session_state.nombre_input = ""
    st.session_state.rut_raw = ""
    st.session_state.rut_display = ""
    st.session_state.rut_valido = False
    st.session_state.rut_mensaje = ""
    st.session_state.correo_input = ""
    st.session_state.telefono_raw = ""
    st.session_state.telefono_valido = False
    st.session_state.telefono_mensaje = ""
    st.session_state.direccion_input = ""
    st.session_state.cliente_comuna = ""
    st.session_state.cliente_region = ""
    st.session_state.proyecto_direccion = ""
    st.session_state.proyecto_comuna = ""
    st.session_state.proyecto_region = ""
    st.session_state.cliente_tipo = "natural"
    st.session_state.cliente_empresa = ""
    st.session_state.cliente_rut_empresa = ""
    st.session_state.rut_empresa_raw = ""
    st.session_state.rut_empresa_display = ""
    st.session_state.rut_empresa_valido = False
    st.session_state.asesor_seleccionado = "Seleccionar asesor"
    st.session_state.correo_asesor = ""
    st.session_state.telefono_asesor = ""
    st.session_state.fecha_inicio = datetime.now().date()
    st.session_state.fecha_termino = (datetime.now() + timedelta(days=15)).date()
    st.session_state.observaciones_input = ""
    st.session_state.plano_adjunto = None
    st.session_state.plano_nombre = ""
    st.session_state.cotizacion_cargada = None
    st.session_state.cotizacion_seleccionada = None
    st.session_state.margen = 0.0
    st.session_state.mostrar_visor = False
    st.session_state.pdf_actual = None
    st.session_state.pdf_nombre = ""
    st.session_state.numero_en_visor = None
    st.session_state.pdf_url = None
    st.session_state.counter += 100


def _construir_datos_guardar_simple():
    ft = formatear_telefono(st.session_state.get('telefono_raw', '') or '')
    dc = {
        'Nombre': st.session_state.get('nombre_input', ''),
        'RUT': st.session_state.get('rut_display', ''),
        'Correo': st.session_state.get('correo_input', ''),
        'Teléfono': ft,
        'Dirección': st.session_state.get('direccion_input', ''),
        'ComunaCliente': st.session_state.get('cliente_comuna', ''),
        'RegionCliente': st.session_state.get('cliente_region', ''),
        'DireccionProyecto': st.session_state.get('proyecto_direccion', ''),
        'ComunaProyecto': st.session_state.get('proyecto_comuna', ''),
        'RegionProyecto': st.session_state.get('proyecto_region', ''),
        'TipoCliente': st.session_state.get('cliente_tipo', 'natural'),
        'EmpresaCliente': st.session_state.get('cliente_empresa', ''),
        'RutEmpresa': st.session_state.get('cliente_rut_empresa', ''),
        'Observaciones': st.session_state.get('observaciones_input', ''),
    }
    nom = st.session_state.get('asesor_seleccionado', '')
    if nom == 'Seleccionar asesor': nom = ''
    da = {
        'Nombre Ejecutivo': nom,
        'Correo Ejecutivo': st.session_state.get('correo_asesor', ''),
        'Teléfono Ejecutivo': st.session_state.get('telefono_asesor', ''),
    }
    fi = st.session_state.get('fecha_inicio', datetime.now().date())
    ft2 = st.session_state.get('fecha_termino', (datetime.now() + timedelta(days=15)).date())
    proy = {
        'fecha_inicio': str(fi), 'fecha_termino': str(ft2),
        'dias_validez': (ft2 - fi).days,
        'observaciones': st.session_state.get('observaciones_input', ''),
    }
    cfg = {'margen': st.session_state.get('margen', 0), 'modo_admin': st.session_state.get('modo_admin', False)}
    carrito = st.session_state.get('carrito', [])
    if carrito:
        df_c = pd.DataFrame(carrito); sb = df_c['Subtotal'].sum()
        mg = st.session_state.get('margen', 0)
        sc = sum(i['Cantidad'] * aplicar_margen(i['Precio Unitario'], mg) for i in carrito) if (st.session_state.get('modo_admin') or mg > 0) else sb
        iva = sc * 0.19; tot = sc + iva
    else:
        sb = sc = iva = tot = 0
    tots = {'subtotal_sin_margen': sb, 'subtotal_con_margen': sc, 'iva': iva, 'total': tot}
    pn = st.session_state.get('plano_nombre') if st.session_state.get('plano_adjunto') else None
    pd2 = st.session_state.get('plano_adjunto') if st.session_state.get('plano_adjunto') else None
    return dc, da, proy, cfg, tots, pn, pd2


def render_tab_cotizacion(supabase, supabase_admin, supa_url, supa_key, **deps):
    st.markdown("""
    <style>
    .hdr1 {
        background: linear-gradient(135deg, #0d2266 0%, #0d47a1 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(37,99,235,0.25);
        position: relative; overflow: hidden;
    }
    .hdr1::before {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 180px; height: 180px; border-radius: 50%;
        background: rgba(255,255,255,0.04); pointer-events: none;
    }
    .hdr1::after {
        content: ''; position: absolute; bottom: -60px; right: 80px;
        width: 240px; height: 240px; border-radius: 50%;
        background: rgba(255,255,255,0.03); pointer-events: none;
    }
    .hdr1 h2 { color: #fff !important; margin: 0; font-size: 0.88rem; font-weight: 700;
                 font-family: 'Montserrat', sans-serif; letter-spacing: 0.05em; text-transform: uppercase; }
    .hdr1 p  { color: rgba(255,255,255,0.65) !important; margin: 1px 0 0; font-size: 0.92rem; font-family: 'Montserrat', sans-serif; font-weight: 500; letter-spacing: 0.01em; }
    .metric-card-special {
        border-radius: 18px; padding: 1.5rem;
        box-shadow: 0 8px 28px rgba(0,0,0,0.14);
        transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
        border: 1px solid rgba(255,255,255,0.2);
        height: 100%; display: flex; flex-direction: column;
        position: relative; overflow: hidden;
    }
    .metric-card-special::before {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 120px; height: 120px; border-radius: 50%;
        background: rgba(255,255,255,0.1);
    }
    .metric-card-special::after {
        content: ''; position: absolute; bottom: -20px; left: -20px;
        width: 80px; height: 80px; border-radius: 50%;
        background: rgba(255,255,255,0.06);
    }
    .metric-card-special:hover { transform: translateY(-5px); box-shadow: 0 20px 50px rgba(0,0,0,0.2); }
    .metric-card-total       { background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%); }
    .metric-card-comisiones  { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); }
    .metric-card-utilidad    { background: linear-gradient(135deg, #10b981 0%, #059669 100%); }
    </style>
    <div class="hdr1" style="display:flex!important;align-items:center!important;">
      <span style="font-size:2.8rem;line-height:1;flex-shrink:0;">&#9745;&#65039;</span>
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Gesti&#243;n de Presupuesto</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Agrega productos, aplica m&#225;rgenes y genera tu cotizaci&#243;n en PDF.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _es_adjudicado = st.session_state.get('_adj_es_adj', False)
    if _es_adjudicado and st.session_state.modo_admin and not st.session_state.get('es_root'):
        st.markdown("""
        <div style="background:#dbeafe;border-left:4px solid #2563eb;border-radius:0 10px 10px 0;
                    padding:12px 16px;margin-bottom:16px;display:flex;align-items:center;gap:10px;">
          <span style="font-size:1.3rem;">&#128309;</span>
          <div>
            <div style="font-size:13px;font-weight:700;color:#1d4ed8;">Presupuesto ADJUDICADO &#8212; Solo lectura</div>
            <div style="font-size:11px;color:#1e40af;margin-top:2px;">
              Este presupuesto tiene contrato notariado adjuntado. Solo el rol Root puede modificarlo.</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

    fecha_inicio = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino

    components.html("""<script>
(function(){
    var D = window.parent.document;
    var _keys = ['modelo_select','cat_manual','item_manual','cat_eliminar','modelo_origen','cat_agregar'];

    function _applyWidth(focusDiv, fwStr) {
        focusDiv.setAttribute('style', 'width:' + fwStr + ';');
        var ul = focusDiv.querySelector('ul');
        if (!ul) return;
        ul.style.width = fwStr;
        var scrollCont = ul.firstElementChild;
        if (scrollCont) {
            scrollCont.style.width = fwStr;
            var virtualInner = scrollCont.firstElementChild;
            if (virtualInner) virtualInner.style.width = fwStr;
        }
        var items = ul.querySelectorAll('li');
        items.forEach(function(li) {
            li.style.whiteSpace = 'nowrap';
            li.style.overflow = 'visible';
            li.style.width = fwStr;
            var txtDiv = li.querySelector('div div');
            if (txtDiv) {
                txtDiv.style.whiteSpace = 'nowrap';
                txtDiv.style.overflow = 'visible';
                txtDiv.style.textOverflow = 'unset';
            }
        });
    }

    function _expand() {
        var focusDivs = D.querySelectorAll('[data-no-focus-lock="true"]');
        if (!focusDivs.length) return;
        focusDivs.forEach(function(focusDiv) {
            var ul = focusDiv.querySelector('ul');
            if (!ul) return;
            var items = ul.querySelectorAll('li');
            if (!items.length) return;
            var maxW = 0;
            items.forEach(function(li) {
                var txt = (li.textContent || li.innerText || '').trim();
                if (!txt) return;
                var sp = D.createElement('span');
                sp.style.cssText = 'position:fixed;top:-9999px;left:-9999px;white-space:nowrap;font-size:14px;font-family:Plus Jakarta Sans,sans-serif;padding:0 24px;visibility:hidden;pointer-events:none;';
                sp.textContent = txt;
                D.body.appendChild(sp);
                var w = sp.getBoundingClientRect().width;
                D.body.removeChild(sp);
                if (w > maxW) maxW = w;
            });
            if (maxW < 50) return;
            var fw = Math.min(maxW + 380, 1200);
            var fwStr = fw + 'px';
            _applyWidth(focusDiv, fwStr);
            if (focusDiv._echObserver) focusDiv._echObserver.disconnect();
            var _savedFw = fwStr;
            var obs = new MutationObserver(function(mutations) {
                mutations.forEach(function(m) {
                    if (m.type === 'attributes' && m.attributeName === 'style') {
                        var cur = focusDiv.getAttribute('style') || '';
                        if (cur.indexOf(_savedFw) === -1) { _applyWidth(focusDiv, _savedFw); }
                    }
                    if (m.type === 'childList') { _applyWidth(focusDiv, _savedFw); }
                });
            });
            obs.observe(focusDiv, { attributes: true, childList: true, subtree: true });
            focusDiv._echObserver = obs;
            setTimeout(function() {
                var still = D.querySelector('[data-no-focus-lock="true"]');
                if (!still && obs) obs.disconnect();
            }, 5000);
        });
    }

    function _attachListeners() {
        _keys.forEach(function(k) {
            var el = D.querySelector('.st-key-' + k);
            if (!el || el._echBound) return;
            el._echBound = true;
            el.addEventListener('mousedown', function() {
                setTimeout(_expand, 100);
                setTimeout(_expand, 300);
                setTimeout(_expand, 600);
            }, true);
        });
    }

    var _pageObs = new MutationObserver(function() { _attachListeners(); });
    _pageObs.observe(D.body, { childList: true, subtree: true });
    setTimeout(_attachListeners, 900);
    setTimeout(_attachListeners, 2200);
})();
</script>""", height=0)

    es_solo_lectura = bool(
        st.session_state.cotizacion_cargada and
        st.session_state.margen > 0 and
        not st.session_state.modo_admin
    )

    if es_solo_lectura:
        st.warning("&#128274; Esta cotizaci&#243;n tiene m&#225;rgenes aplicados. Modo solo lectura. Solo puedes visualizar y generar PDFs.")

    if not es_solo_lectura:
        hojas_modelo = [h for h in _leer_hojas_disponibles(supabase_admin) if h.lower().startswith("modelo")]
        def _total_modelo(nombre_hoja):
            try:
                items = cargar_modelo(nombre_hoja, supabase_admin)
                subtotal = sum(float(i.get('Subtotal', 0) or 0) for i in items)
                return f"${subtotal:,.0f}".replace(',', '.')
            except:
                return ''
        _mod_labels = {f"{h} — {_total_modelo(h)}": h for h in hojas_modelo}
        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([1, 1, 1, 1, 0.7])

        with col_m1:
            with st.container(border=True):
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;">&#128203; Modelo Predefinido</div>', unsafe_allow_html=True)
                try:
                    if hojas_modelo:
                        _mod_sel_label = st.selectbox("Modelo", list(_mod_labels.keys()), key="modelo_select", label_visibility="collapsed")
                        modelo_seleccionado = _mod_labels.get(_mod_sel_label, hojas_modelo[0])
                        if st.button("Cargar", key="btn_modelo", use_container_width=True):
                            st.session_state.carrito = cargar_modelo(modelo_seleccionado, supabase_admin)
                            st.session_state.modelo_base = modelo_seleccionado
                            st.session_state.margen = 0.0
                            st.session_state['_toast_msg'] = f"&#9989; Modelo '{modelo_seleccionado}' cargado correctamente."
                            st.rerun()
                    else:
                        st.caption("Sin modelos")
                except Exception as _e1:
                    st.caption(f"Error: {_e1}")

        with col_m2:
            with st.container(border=True):
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;">&#128269; &#205;tems</div>', unsafe_allow_html=True)
                try:
                    df = _leer_hoja_excel("BD Total", supabase_admin)
                    categorias = df["Categorias"].dropna().unique()
                    categoria_seleccionada = st.selectbox("Categor&#237;a", categorias, key="cat_manual", label_visibility="collapsed")
                    items_filtrados = df[df["Categorias"] == categoria_seleccionada].copy()
                    _item_labels = {
                        f"{row['Item']} — ${row['P. Unitario real']:,.0f}".replace(',', '.'): row['Item']
                        for _, row in items_filtrados.iterrows()
                        if row.get('P. Unitario real', 0)
                    }
                    _item_sel_label = st.selectbox("&#205;tem", list(_item_labels.keys()), key="item_manual", label_visibility="collapsed")
                    item = _item_labels.get(_item_sel_label, items_filtrados["Item"].iloc[0] if len(items_filtrados) else '')
                    cantidad = st.number_input("Cantidad", min_value=1, value=1, key="cantidad_manual", label_visibility="collapsed")
                    if st.button("Agregar", key="btn_agregar_manual", use_container_width=True):
                        existe = False
                        for producto in st.session_state.carrito:
                            if producto["Item"] == item:
                                producto["Cantidad"] += cantidad
                                producto["Subtotal"] = producto["Cantidad"] * producto["Precio Unitario"]
                                existe = True
                                break
                        if not existe:
                            precio_unitario_original = items_filtrados[items_filtrados["Item"] == item]["P. Unitario real"].values[0]
                            st.session_state.carrito.append({
                                "Categoria": categoria_seleccionada, "Item": item,
                                "Cantidad": cantidad, "Precio Unitario": precio_unitario_original,
                                "Subtotal": precio_unitario_original * cantidad
                            })
                            st.session_state['_toast_msg'] = f"&#9989; {item} agregado exitosamente ({cantidad} un.)"
                        else:
                            st.session_state['_toast_msg'] = f"&#9989; {item} actualizado &#8212; {cantidad} un. m&#225;s agregadas"
                        st.rerun()
                except Exception as _e2:
                    st.caption(f"Error: {_e2}")

        with col_m3:
            with st.container(border=True):
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;">&#128465;&#65039; Eliminar Categor&#237;a</div>', unsafe_allow_html=True)
                try:
                    if st.session_state.carrito:
                        carrito_df_temp = pd.DataFrame(st.session_state.carrito)
                        categorias_carrito = carrito_df_temp["Categoria"].unique()
                        def _total_cat(cat):
                            try:
                                t = carrito_df_temp[carrito_df_temp['Categoria'] == cat]['Subtotal'].sum()
                                return f"${t:,.0f}".replace(',', '.')
                            except:
                                return ''
                        _cat_elim_labels = {f"{c} — {_total_cat(c)}": c for c in categorias_carrito}
                        _cat_elim_sel = st.selectbox("Eliminar", ["-- Seleccionar --"] + list(_cat_elim_labels.keys()), key="cat_eliminar", label_visibility="collapsed")
                        categoria_eliminar = _cat_elim_labels.get(_cat_elim_sel, _cat_elim_sel)
                        if st.button("Eliminar", key="btn_eliminar_categoria", use_container_width=True):
                            if categoria_eliminar != "-- Seleccionar --":
                                st.session_state.carrito = [i for i in st.session_state.carrito if i["Categoria"] != categoria_eliminar]
                                st.session_state['_toast_msg'] = f"&#128465;&#65039; Categor&#237;a '{categoria_eliminar}' eliminada del presupuesto."
                                st.rerun()
                    else:
                        st.caption("Sin categor&#237;as")
                except Exception as _e3:
                    st.caption(f"Error: {_e3}")

        with col_m4:
            with st.container(border=True):
                st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;">&#10133; Agregar Categor&#237;a</div>', unsafe_allow_html=True)
                try:
                    if hojas_modelo:
                        _mod_ori_label = st.selectbox("Modelo", list(_mod_labels.keys()), key="modelo_origen", label_visibility="collapsed")
                        modelo_origen = _mod_labels.get(_mod_ori_label, hojas_modelo[0])
                        df_temp = _leer_hoja_excel(modelo_origen, supabase_admin)
                        categorias_disponibles = df_temp["Categorias"].dropna().unique()
                        try:
                            _items_modelo = cargar_modelo(modelo_origen, supabase_admin)
                            _df_modelo_agr = pd.DataFrame(_items_modelo)
                            _cat_totales = _df_modelo_agr.groupby('Categoria')['Subtotal'].sum()
                        except:
                            _cat_totales = {}
                        def _total_cat_modelo(cat):
                            try:
                                t = _cat_totales.get(cat, 0) if hasattr(_cat_totales, 'get') else _cat_totales[cat]
                                return f"${t:,.0f}".replace(',', '.') if t > 0 else ''
                            except:
                                return ''
                        _cat_agr_labels = {f"{c} — {_total_cat_modelo(c)}": c for c in categorias_disponibles}
                        _cat_agr_sel = st.selectbox("Categor&#237;a", list(_cat_agr_labels.keys()), key="cat_agregar", label_visibility="collapsed")
                        categoria_agregar = _cat_agr_labels.get(_cat_agr_sel, categorias_disponibles[0] if len(categorias_disponibles) else '')
                        if st.button("Agregar", key="btn_agregar_categoria", use_container_width=True):
                            nuevos_items = cargar_categoria_desde_modelo(modelo_origen, categoria_agregar, supabase_admin)
                            for _ni in nuevos_items:
                                _existe = False
                                for _ci in st.session_state.carrito:
                                    if _ci["Item"] == _ni["Item"]:
                                        _ci["Cantidad"] += _ni["Cantidad"]
                                        _ci["Subtotal"] = _ci["Cantidad"] * _ci["Precio Unitario"]
                                        _existe = True
                                        break
                                if not _existe:
                                    st.session_state.carrito.append(_ni)
                            st.session_state['_toast_msg'] = f"&#9989; Categor&#237;a '{categoria_agregar}' mezclada al presupuesto."
                            st.rerun()
                    else:
                        st.caption("Sin modelos")
                except Exception as _e4:
                    st.caption(f"Error: {_e4}")

        with col_m5:
            with st.container(border=True):
                _plano_placeholder = st.empty()
                st.markdown('''
                <style>
                [data-testid="stFileUploader"] section {
                    border: none !important; padding: 0 !important; background: transparent !important;
                }
                [data-testid="stFileUploadDropzone"] {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
                    border: none !important; border-radius: 8px !important;
                    padding: 8px 16px !important; min-height: 0 !important;
                }
                [data-testid="stFileUploadDropzone"]:hover { opacity: 0.85 !important; cursor: pointer !important; }
                [data-testid="stFileUploadDropzone"] span { display: none !important; }
                [data-testid="stFileUploadDropzone"] button { display: none !important; }
                [data-testid="stFileUploadDropzone"] p {
                    color: white !important; font-weight: 600 !important;
                    font-size: 14px !important; margin: 0 !important;
                }
                [data-testid="stFileUploadDropzone"] p::before { content: "&#128206; " !important; }
                div[data-testid="stFileUploader"] > label { display:none !important; }
                [data-testid="stFileUploader"] small { display:none !important; }
                </style>
                ''', unsafe_allow_html=True)
                uploaded_file = st.file_uploader("Subir Plano PDF", type=["pdf"], key=f"plano_uploader_{st.session_state.counter}", label_visibility="collapsed")
                if uploaded_file is not None:
                    if uploaded_file.name != st.session_state.plano_nombre:
                        st.session_state.plano_adjunto = uploaded_file.getvalue()
                        st.session_state.plano_nombre = uploaded_file.name
                        st.session_state['_toast_msg'] = f"&#128206; Plano '{uploaded_file.name}' adjuntado exitosamente."
                    st.success(f"&#9989; {st.session_state.plano_nombre}")
                elif st.session_state.plano_nombre:
                    st.info(f"&#128206; {st.session_state.plano_nombre}")
                    if st.button("&#10060; Quitar plano", key="btn_quitar_plano", use_container_width=True):
                        st.session_state.plano_adjunto = None
                        st.session_state.plano_nombre = ""
                        st.rerun()
                _plano_ok_post = bool(st.session_state.get('plano_adjunto') or st.session_state.get('pdf_url') or st.session_state.get('plano_nombre'))
                _plano_dot_post = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _plano_ok_post else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                _plano_mostrar_hb = len(st.session_state.get('carrito', [])) > 0 and not es_solo_lectura
                _plano_placeholder.markdown(f'<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;"><span class="_hb_wrap">&#128206; Plano PDF{_plano_dot_post if _plano_mostrar_hb else ""}</span></div>', unsafe_allow_html=True)

    else:
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        for col, label in zip([col_m1, col_m2, col_m3, col_m4], ["MODELO PREDEFINIDO", "ITEMS", "ELIMINAR CATEGOR&#205;A", "AGREGAR CATEGOR&#205;A"]):
            with col:
                st.markdown(f"**{label}**")
                st.info("Modo lectura")

    # Variables de m&#233;tricas con valores por defecto
    utilidad_real = 0
    total_comisiones = 0
    comision_vendedor = 0
    comision_supervisor = 0
    margen_valor = 0
    subtotal_base = 0
    subtotal_general = 0
    total = 0
    iva = 0

    if st.session_state.carrito:
        st.markdown("---")
        if not st.session_state.modo_admin:
            st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;text-align:center;">&#128202; Resumen del Presupuesto</div>', unsafe_allow_html=True)
            if st.session_state.margen > 0:
                st.caption(f"&#8505;&#65039; Margen del {st.session_state.margen}% aplicado")
        if st.session_state.modo_admin:
            st.markdown('<div style="font-family:Montserrat,sans-serif;font-weight:700;font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;color:#0f172a;margin:0 0 6px 0;-webkit-text-fill-color:#0f172a;text-align:center;">&#128202; Resumen del Presupuesto</div>', unsafe_allow_html=True)

        # Trigger oculto para click de fila → popup de edición (mismo patrón que EP selector)
        st.markdown('<style>.st-key-_item_click_trigger{display:none!important;}</style>', unsafe_allow_html=True)
        _item_trg = st.text_input("Item trigger", key="_item_click_trigger",
                                   label_visibility="collapsed", placeholder="__item_trg__")
        if _item_trg:
            # Formato: "CategoryName ||| ItemName" (el CF viene del iframe)
            if ' ||| ' in _item_trg:
                _trg_cf, _trg_item = _item_trg.split(' ||| ', 1)
            else:
                _trg_cf, _trg_item = '', _item_trg
            if _trg_cf:
                st.session_state['_cat_filtro_activo'] = _trg_cf
            else:
                st.session_state.pop('_cat_filtro_activo', None)
            _found_item = next((i for i in st.session_state.carrito if i["Item"] == _trg_item), None)
            if _found_item:
                st.session_state['_item_pendiente_eliminar'] = {
                    'item': _found_item, 'nueva_cantidad': int(_found_item.get('Cantidad', 1))
                }
            st.session_state['_item_click_trigger'] = ''
            st.session_state.counter += 1
            st.rerun()

        _cat_filtro_activo = st.session_state.get('_cat_filtro_activo', '')
        _df_cat = pd.DataFrame(st.session_state.carrito)
        _cat_colors = ['#3b82f6','#10b981','#f59e0b','#8b5cf6','#ef4444',
                       '#06b6d4','#f97316','#84cc16','#ec4899','#6366f1',
                       '#14b8a6','#eab308','#dc2626','#7c3aed','#0ea5e9']
        _cats_summary = (
            _df_cat.groupby('Categoria')
            .agg(items=('Item', 'count'), cantidades=('Cantidad', 'sum'), subtotal=('Subtotal', 'sum'))
            .reset_index().sort_values('Categoria')
        )
        # Preparar datos de categorías para el componente unificado
        _cats_data = []
        for _ci, (_, _crow) in enumerate(_cats_summary.iterrows()):
            _cc = _cat_colors[_ci % len(_cat_colors)]
            _cats_data.append({
                'cat': str(_crow['Categoria']),
                'color': _cc,
                'sub': f"${_crow['subtotal']:,.0f}".replace(',', '.'),
                'items': int(_crow['items']),
                'cant': int(_crow['cantidades']),
            })
        # ── CARDS via st.markdown() — siempre visibles, JS adjunta listeners (igual que tab_historial) ──
        def _hex_to_rgba(h, a):
            r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
            return f'rgba({r},{g},{b},{a})'
        _cards_css = ('<style>.pres-cards{display:flex;flex-wrap:wrap;gap:6px;padding:4px 0 10px 0;}'
                      '._pres_card{border-radius:7px;padding:7px 11px;min-width:110px;flex:1;cursor:pointer;transition:background .13s,border .13s;}'
                      '._pres_card:hover{opacity:.85;}'
                      '.pres-cname{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;}'
                      '.pres-csub{font-size:12px;font-weight:700;color:#0f172a;}'
                      '.pres-cmeta{font-size:10px;color:#64748b;margin-top:1px;}</style>')
        _cards_html_md = '<div class="pres-cards">'
        for _c in _cats_data:
            _is_act = (_c['cat'] == _cat_filtro_activo)
            _col = _c['color']
            _bg   = _hex_to_rgba(_col, 0.15) if _is_act else '#fff'
            _brd  = f'2px solid {_col}' if _is_act else f'1.5px solid {_hex_to_rgba(_col, 0.3)}'
            _tick = ' ✓' if _is_act else ''
            _dcat = _c['cat'].replace('"', '&quot;')
            _cards_html_md += (
                f'<div class="_pres_card" data-catpres="{_dcat}" data-colorpres="{_col}"'
                f' style="background:{_bg};border:{_brd};border-left:4px solid {_col};">'
                f'<div class="pres-cname" style="color:{_col};">{_c["cat"]}{_tick}</div>'
                f'<div class="pres-csub">{_c["sub"]}<span style="font-size:9px;color:#64748b;margin-left:3px;">s/IVA</span></div>'
                f'<div class="pres-cmeta">{_c["items"]} ítems · {_c["cant"]} uds.</div>'
                f'</div>'
            )
        _cards_html_md += '</div>'
        st.markdown(_cards_css + _cards_html_md, unsafe_allow_html=True)

        carrito_df = pd.DataFrame(st.session_state.carrito)
        subtotal_base = carrito_df["Subtotal"].sum()

        if st.session_state.modo_admin or st.session_state.margen > 0:
            carrito_df_con_margen = carrito_df.copy()
            carrito_df_con_margen["Precio Unitario"] = carrito_df_con_margen["Precio Unitario"].apply(lambda x: aplicar_margen(x, st.session_state.margen))
            carrito_df_con_margen["Subtotal"] = carrito_df_con_margen["Cantidad"] * carrito_df_con_margen["Precio Unitario"]
            subtotal_general = carrito_df_con_margen["Subtotal"].sum()
        else:
            carrito_df_con_margen = carrito_df.copy()
            subtotal_general = subtotal_base

        iva = subtotal_general * 0.19
        total = subtotal_general + iva
        margen_valor = subtotal_general - subtotal_base
        tiene_margen = st.session_state.margen > 0
        comision_vendedor = subtotal_general * 0.025 if (st.session_state.modo_admin and tiene_margen) else 0
        comision_supervisor = subtotal_general * 0.008 if (st.session_state.modo_admin and tiene_margen) else 0
        total_comisiones = comision_vendedor + comision_supervisor
        utilidad_real = margen_valor - total_comisiones if (st.session_state.modo_admin and tiene_margen) else 0

        _color_map_tbl = {c['cat']: c['color'] for c in _cats_data}
        _tbl_df = carrito_df_con_margen.copy()
        _tbl_df["P. Unit + IVA"]  = _tbl_df["Precio Unitario"].apply(lambda x: formato_clp(round(x * 1.19)))
        _tbl_df["Subtotal + IVA"] = _tbl_df["Subtotal"].apply(lambda x: formato_clp(round(x * 1.19)))
        _tbl_df["Precio Unitario"] = _tbl_df["Precio Unitario"].apply(formato_clp)
        _tbl_df["Subtotal"]        = _tbl_df["Subtotal"].apply(formato_clp)
        _tbl_df["Cantidad"]        = pd.to_numeric(_tbl_df["Cantidad"], errors="coerce").fillna(0).astype(int)
        _pend_item  = (st.session_state.get('_item_pendiente_eliminar') or {})
        _pend_name  = ((_pend_item.get('item') or {}).get('Item', ''))

        # ── BARRA DE BÚSQUEDA + TABLA en un solo components.html() con filas pre-construidas ──
        # Las filas van DENTRO del iframe: onclick funciona sin que Streamlit las elimine.
        _total_hdr_fmt = '$' + '{:,.0f}'.format(total).replace(',', '.')
        _cf_js   = _json.dumps(_cat_filtro_activo or '', ensure_ascii=False)
        _edit_js = 'true' if not es_solo_lectura else 'false'
        _pend_js = _json.dumps(_pend_name, ensure_ascii=False)

        def _hesc(s): return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
        def _aesc(s): return _hesc(s).replace('"','&quot;')

        _rows_html = ''
        for _, _r in _tbl_df.iterrows():
            _cat  = str(_r['Categoria'])
            _item = str(_r['Item'])
            _color = _color_map_tbl.get(_cat, '#6366f1')
            _ri, _gi, _bi = int(_color[1:3], 16), int(_color[3:5], 16), int(_color[5:7], 16)
            _bbg = f'rgba({_ri},{_gi},{_bi},0.12)'
            _is_pend = (_item == _pend_name)
            _cls = 'editable' if not es_solo_lectura else ''
            if _is_pend: _cls += ' pending'
            _onclick = ' onclick="cr(this)"' if not es_solo_lectura else ''
            _cursor  = 'cursor:pointer;' if not es_solo_lectura else ''
            _hint    = '<span class="hint">editar / eliminar</span>' if not es_solo_lectura and not _is_pend else ''
            _rows_html += (
                f'<tr class="{_cls.strip()}" data-cat="{_aesc(_cat)}" data-item="{_aesc(_item)}"{_onclick} style="{_cursor}">'
                f'<td><span class="badge" style="background:{_bbg};color:{_color};">{_hesc(_cat)}</span></td>'
                f'<td><span class="item-n">{_hesc(_item)}</span>{_hint}</td>'
                f'<td class="r mono">{_r["Cantidad"]}</td>'
                f'<td class="r mono">{_r["Precio Unitario"]}</td>'
                f'<td class="r mono bold">{_r["Subtotal"]}</td>'
                f'<td class="r mono muted">{_r["P. Unit + IVA"]}</td>'
                f'<td class="r mono muted">{_r["Subtotal + IVA"]}</td>'
                f'</tr>'
            )

        _n_tbl = len(_tbl_df)
        _tbl_h = max(120, min(_n_tbl * 42 + 54, 460))
        _iframe_total_h = 46 + 8 + _tbl_h

        if es_solo_lectura:
            st.caption("&#128274; Vista de solo lectura")

        _tbl_html = ("""<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0;padding:0;}
html,body{height:IFRAMEHPX;overflow:hidden;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;}
#wrap{display:flex;flex-direction:column;height:100%;}
#bar{display:flex;align-items:center;gap:8px;padding:4px 0;flex-shrink:0;height:46px;}
#search{flex:1;border:1.5px solid #e2e8f0;border-radius:7px;padding:6px 11px;font-size:0.84rem;
  font-family:inherit;outline:none;color:#1e293b;background:#f8fafc;
  transition:border-color .2s,box-shadow .2s;}
#search:focus{border-color:#5b7cfa;background:#fff;box-shadow:0 0 0 3px rgba(91,124,250,.1);}
#cnt{font-size:0.72rem;color:#94a3b8;white-space:nowrap;font-weight:600;min-width:64px;text-align:right;}
#tbl-w{flex:1;overflow:auto;border:1px solid #e2e8f0;border-radius:10px;
  box-shadow:0 2px 6px rgba(0,0,0,.06);margin-top:4px;}
#tbl-w::-webkit-scrollbar{width:4px;height:4px;}
#tbl-w::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px;}
table{width:100%;border-collapse:collapse;font-size:.8rem;table-layout:auto;}
thead th{background:linear-gradient(135deg,#1e2447,#2a3060);color:#fff;
  font-weight:700;font-size:.7rem;letter-spacing:.06em;text-transform:uppercase;
  padding:9px 11px;white-space:nowrap;position:sticky;top:0;z-index:2;text-align:left;}
thead th.r{text-align:right;}
tbody tr:nth-child(even){background:#f8fafc;}
tbody tr:nth-child(odd){background:#fff;}
tbody tr.editable:hover{background:#eef1ff!important;}
tbody tr.pending{background:#fff4f4!important;box-shadow:inset 3px 0 0 #ef4444;}
td{padding:7px 11px;border-bottom:1px solid #f0f4f8;vertical-align:middle;color:#334155;}
td.r{text-align:right;}
.badge{display:inline-block;padding:2px 7px;border-radius:20px;font-size:.68rem;
  font-weight:700;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;}
.item-n{font-weight:600;color:#1e293b;font-size:.82rem;line-height:1.35;}
.hint{font-size:.62rem;color:#94a3b8;font-style:italic;display:block;margin-top:1px;}
.mono{font-family:'JetBrains Mono','Courier New',monospace;font-size:.77rem;}
.bold{font-weight:700;color:#0f172a;}
.muted{color:#64748b;}
</style></head>
<body>
<div id="wrap">
<div id="bar">
  <svg width="14" height="14" fill="none" stroke="#94a3b8" stroke-width="2.2" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
  <input id="search" type="text" placeholder="Filtrar por categoría o ítem..." autocomplete="off">
  <span id="cnt"></span>
</div>
<div id="tbl-w">
<table>
<thead><tr>
  <th>Categoría</th><th>Ítem</th>
  <th class="r">Cant.</th><th class="r">P. Unitario</th>
  <th class="r">Subtotal</th><th class="r">P.Unit+IVA</th><th class="r">Sub+IVA</th>
</tr></thead>
<tbody>ROWSPLACEHOLDER</tbody>
</table>
</div>
</div>
<script>
(function(){
var CF=__CF__;var EM=__EM__;var PI=__PI__;
var PD;try{PD=window.parent.document;}catch(e){return;}
function filterRows(){
  var q=document.getElementById('search').value.toLowerCase().trim();
  var rows=document.querySelectorAll('tbody tr[data-cat]');var vis=0;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var cat=(r.getAttribute('data-cat')||'').toLowerCase();
    var item=(r.getAttribute('data-item')||'').toLowerCase();
    var show=true;
    if(CF&&r.getAttribute('data-cat')!==CF)show=false;
    if(q&&cat.indexOf(q)<0&&item.indexOf(q)<0)show=false;
    r.style.display=show?'':'none';
    if(show)vis++;
  }
  var el=document.getElementById('cnt');
  if(el)el.textContent=vis+' ítem'+(vis!==1?'s':'');
}
window.cr=function(el){
  var item=el.getAttribute('data-item');if(!item)return;
  var combined=(CF||'')+' ||| '+item;
  var inp=PD.querySelector('input[placeholder="__item_trg__"]');
  if(!inp)return;
  try{Object.getOwnPropertyDescriptor(window.parent.HTMLInputElement.prototype,'value').set.call(inp,combined);}
  catch(e){inp.value=combined;}
  inp.dispatchEvent(new window.parent.Event('input',{bubbles:true}));
};
function updateCards(){
  PD.querySelectorAll('._pres_card').forEach(function(el){
    var cat=el.getAttribute('data-catpres');
    var color=el.getAttribute('data-colorpres');
    if(!color)return;
    var isAct=(cat===CF);
    var r=parseInt(color.slice(1,3),16),g=parseInt(color.slice(3,5),16),b=parseInt(color.slice(5,7),16);
    el.style.background=isAct?'rgba('+r+','+g+','+b+',0.15)':'#fff';
    el.style.border=isAct?('2px solid '+color):('1.5px solid rgba('+r+','+g+','+b+',0.3)');
    el.style.borderLeft='4px solid '+color;
    var nm=el.querySelector('.pres-cname');
    if(nm)nm.textContent=cat+(isAct?' ✓':'');
  });
}
function toggleCF(cat){CF=(CF===cat)?'':cat;updateCards();filterRows();}
function attachCardListeners(){
  PD.querySelectorAll('._pres_card').forEach(function(el){
    if(el._pb)return;el._pb=true;
    var cat=el.getAttribute('data-catpres');
    el.addEventListener('click',function(){toggleCF(cat);});
  });
}
function injectTotal(){
  var bar=PD.getElementById('_usr_header_bar');if(!bar)return;
  var ex=PD.getElementById('_hdr_total_cot');if(ex)ex.remove();
  var tf=__TH__;if(!tf)return;
  var d=PD.createElement('div');d.id='_hdr_total_cot';
  d.style.cssText='position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none;';
  d.innerHTML='<div style="font-size:0.58rem;font-weight:700;color:rgba(255,255,255,0.45);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:2px;">Total + IVA</div>'
    +'<div style="font-size:1.25rem;font-weight:900;color:#fff;letter-spacing:-0.02em;font-family:Montserrat,sans-serif;line-height:1;">'+tf+'</div>';
  bar.appendChild(d);
}
document.getElementById('search').addEventListener('input',filterRows);
setTimeout(function(){attachCardListeners();updateCards();filterRows();injectTotal();},300);
setTimeout(injectTotal,1200);
setInterval(attachCardListeners,3000);
})();
</script>
</body></html>"""
            .replace('__CF__', _cf_js)
            .replace('__EM__', _edit_js)
            .replace('__PI__', _pend_js)
            .replace('__TH__', _json.dumps(_total_hdr_fmt, ensure_ascii=False))
            .replace('IFRAMEHPX', str(_iframe_total_h) + 'px')
            .replace('ROWSPLACEHOLDER', _rows_html)
        )
        components.html(_tbl_html, height=_iframe_total_h, scrolling=False)

        if st.session_state.get('_item_pendiente_eliminar'):
            _pend = st.session_state['_item_pendiente_eliminar']
            _item_data = _pend['item']
            _nombre_item = _item_data.get('Item', '')
            _cantidad_orig = int(_item_data.get('Cantidad', 1))
            _precio = float(_item_data.get('Precio Unitario', 0))
            _categoria = _item_data.get('Categoria', '')
            _nueva_cant = int(_pend.get('nueva_cantidad', _cantidad_orig))
            _container_key = f"popup_container_{st.session_state.counter}"
            _css_key = _container_key.replace('-', '_')
            st.markdown(f'''
            <style>
            .st-key-{_css_key} > div[data-testid="stVerticalBlockBorderWrapper"] {{
                background: #FCEBEB !important; border: 1.5px solid #E24B4A !important;
                border-radius: 14px !important; box-shadow: none !important;
            }}
            .st-key-{_css_key} label {{ color: #791F1F !important; font-weight: 600 !important; }}
            .st-key-{_css_key} input[type="number"] {{
                background: #fff !important; border-color: #E24B4A !important;
                color: #501313 !important; font-weight: 700 !important;
            }}
            .st-key-{_css_key} button[data-testid="stNumberInputStepUp"],
            .st-key-{_css_key} button[data-testid="stNumberInputStepDown"] {{
                background: #FCEBEB !important; color: #A32D2D !important;
            }}
            [class*="st-key-btn_copy_"] button {{
                font-family: 'Plus Jakarta Sans', sans-serif !important; font-weight: 900 !important;
                font-size: 1rem !important; color: #501313 !important;
                border: 1.5px solid #E24B4A !important; background: #fff !important;
                text-align: left !important; letter-spacing: -0.01em !important;
            }}
            .st-key-popup_cancelar_btn button {{ background: transparent !important; border: 1px solid #F09595 !important; color: #791F1F !important; }}
            .st-key-popup_aplicar_btn button {{ background: #fff !important; border: 1.5px solid #E24B4A !important; color: #A32D2D !important; font-weight: 600 !important; }}
            .st-key-popup_eliminar_btn button {{ background: #E24B4A !important; border: none !important; color: #fff !important; font-weight: 600 !important; }}
            </style>
            ''', unsafe_allow_html=True)
            with st.container(border=True, key=_container_key):
                _cat_esc = str(_categoria).replace('<', '&lt;').replace('>', '&gt;')
                _precio_fmt = formato_clp(_precio)
                _sub_fmt = formato_clp(_nueva_cant * _precio)
                st.markdown(f'<div style="font-size:11px;color:#A32D2D;font-weight:600;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">{_cat_esc}</div>', unsafe_allow_html=True)
                if st.button(f"&#128203; {_nombre_item}", key=f"btn_copy_{st.session_state.counter}", help="Click para copiar nombre"):
                    st.session_state['_copiar_nombre_producto'] = _nombre_item
                    st.rerun()
                st.markdown(
                    f'<div style="display:flex;gap:12px;margin-bottom:4px;">'
                    f'<div style="background:#fff;border:.5px solid #F09595;border-radius:10px;padding:10px 14px;text-align:center;flex:1;">'
                    f'<div style="font-size:11px;color:#A32D2D;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">P. unitario</div>'
                    f'<div style="font-size:15px;font-weight:700;color:#501313;margin-top:3px;">{_precio_fmt}</div></div>'
                    f'<div style="background:#fff;border:.5px solid #F09595;border-radius:10px;padding:10px 14px;text-align:center;flex:1;">'
                    f'<div style="font-size:11px;color:#A32D2D;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">Cant. original</div>'
                    f'<div style="font-size:15px;font-weight:700;color:#791F1F;margin-top:3px;">{_cantidad_orig}</div></div>'
                    f'<div style="background:#fff;border:.5px solid #E24B4A;border-radius:10px;padding:10px 14px;text-align:center;flex:1;">'
                    f'<div style="font-size:11px;color:#A32D2D;font-weight:600;text-transform:uppercase;letter-spacing:.06em;">Subtotal nuevo</div>'
                    f'<div style="font-size:15px;font-weight:700;color:#E24B4A;margin-top:3px;">{_sub_fmt}</div></div></div>',
                    unsafe_allow_html=True
                )
                _cant_input = st.number_input("Nueva cantidad", min_value=1, value=_nueva_cant, step=1, key=f"ni_{st.session_state.counter}")
                if int(_cant_input) != _nueva_cant and not st.session_state.get('_rerun_lock'):
                    st.session_state['_item_pendiente_eliminar']['nueva_cantidad'] = int(_cant_input)
                    st.rerun()
                _ba1, _ba2, _ba3 = st.columns([1, 1.5, 1.5])
                with _ba1:
                    if st.button("&#10006;&#65039; Cancelar", use_container_width=True, key="popup_cancelar_btn"):
                        st.session_state.pop('_item_pendiente_eliminar', None)
                        st.session_state.pop('_rerun_lock', None)
                        st.session_state.counter += 1
                        st.rerun()
                with _ba2:
                    if st.button("&#9989; Aplicar cambio", use_container_width=True, key="popup_aplicar_btn"):
                        for item in st.session_state.carrito:
                            if item['Item'] == _nombre_item:
                                item['Cantidad'] = int(_cant_input)
                                item['Subtotal'] = int(_cant_input) * float(item['Precio Unitario'])
                                break
                        st.session_state.pop('_item_pendiente_eliminar', None)
                        st.session_state.pop('_rerun_lock', None)
                        st.session_state.counter += 1
                        st.rerun()
                with _ba3:
                    if st.button("&#128465;&#65039; Eliminar todo", use_container_width=True, key="popup_eliminar_btn"):
                        st.session_state.carrito = [i for i in st.session_state.carrito if i['Item'] != _nombre_item]
                        st.session_state.pop('_item_pendiente_eliminar', None)
                        st.session_state.pop('_rerun_lock', None)
                        st.session_state.counter += 1
                        st.rerun()

        st.markdown("---")
        col_btn_limpiar, _, _, _ = st.columns(4)
        with col_btn_limpiar:
            if not es_solo_lectura:
                if st.button("&#129529; Limpiar", use_container_width=True):
                    st.session_state.pop('_item_pendiente_eliminar', None)
                    st.session_state.pop('_rerun_lock', None)
                    limpiar_todo()
                    st.rerun()
            else:
                st.button("&#129529; Limpiar", use_container_width=True, disabled=True)

        datos_cliente_pdf = {
            "Nombre": st.session_state.nombre_input,
            "RUT": st.session_state.rut_display or '',
            "Correo": st.session_state.correo_input,
            "Teléfono": formatear_telefono(st.session_state.telefono_raw) if st.session_state.telefono_raw else '',
            "Dirección": st.session_state.direccion_input,
            "ComunaCliente": st.session_state.cliente_comuna or "",
            "RegionCliente": st.session_state.cliente_region or "",
            "DireccionProyecto": st.session_state.proyecto_direccion or "",
            "ComunaProyecto": st.session_state.proyecto_comuna or "",
            "RegionProyecto": st.session_state.proyecto_region or "",
            "TipoCliente": st.session_state.cliente_tipo or "natural",
            "EmpresaCliente": st.session_state.cliente_empresa or "",
            "RutEmpresa": st.session_state.cliente_rut_empresa or "",
            "Observaciones": st.session_state.observaciones_input,
        }
        nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
        datos_asesor_pdf = {
            "Nombre Ejecutivo": nombre_asesor_final,
            "Correo Ejecutivo": st.session_state.correo_asesor or "",
            "Teléfono Ejecutivo": st.session_state.telefono_asesor or "",
        }
        carrito_df_pdf = carrito_df_con_margen.copy()
        if not carrito_df_pdf.empty and 'Categoria' in carrito_df_pdf.columns:
            carrito_df_pdf = carrito_df_pdf.sort_values(['Categoria', 'Item'], ignore_index=True)
        margen_actual = st.session_state.margen
        numero_para_pdf = st.session_state.cotizacion_cargada if st.session_state.cotizacion_cargada else None

        if st.session_state.modo_admin and st.session_state.margen > 0:
            st.caption(f"*Precios calculados con margen del {st.session_state.margen}%")

        st.markdown("---")
        st.markdown("#### Métricas")
        col_m1, col_m2, col_m3 = st.columns(3)
        total_productos = sum(item["Cantidad"] for item in st.session_state.carrito)
        categorias_unicas = len(set(item["Categoria"] for item in st.session_state.carrito))
        with col_m1:
            st.markdown(f'<div class="stats-card"><div class="stats-title">&#205;TEMS</div><div class="stats-number" style="color:#3b82f6;border:none;padding:0;">{len(st.session_state.carrito)}</div><div class="stats-desc">En presupuesto</div></div>', unsafe_allow_html=True)
        with col_m2:
            st.markdown(f'<div class="stats-card"><div class="stats-title">PRODUCTOS</div><div class="stats-number" style="color:#f59e0b;border:none;padding:0;">{total_productos}</div><div class="stats-desc">Unidades</div></div>', unsafe_allow_html=True)
        with col_m3:
            st.markdown(f'<div class="stats-card"><div class="stats-title">CATEGOR&#205;AS</div><div class="stats-number" style="color:#10b981;border:none;padding:0;">{categorias_unicas}</div><div class="stats-desc">Diferentes</div></div>', unsafe_allow_html=True)

        st.markdown("---")

        if st.session_state.modo_admin:
            col_total_card, col_comisiones_card, col_utilidad_card = st.columns(3)
            with col_total_card:
                st.markdown(f'''
                <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;font-family:Montserrat,sans-serif;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>+ Margen {st.session_state.margen}%:</span><span>{formato_clp(margen_valor)}</span></div>
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>= Subtotal c/margen:</span><span>{formato_clp(subtotal_general)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.1rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:0.04em;">&#128176; TOTAL + IVA</span>
                        <span style="font-size:2.2rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:-0.02em;">{formato_clp(total)}</span>
                    </div>''', unsafe_allow_html=True)
            with col_comisiones_card:
                st.markdown(f'''
                <div class="metric-card-special metric-card-comisiones" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;font-family:Montserrat,sans-serif;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Vendedor 2.5%:</span><span>{formato_clp(comision_vendedor)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>Supervisor 0.8%:</span><span>{formato_clp(comision_supervisor)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.1rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:0.04em;">&#128202; COMISIONES</span>
                        <span style="font-size:2.2rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:-0.02em;">{formato_clp(total_comisiones)}</span>
                    </div>''', unsafe_allow_html=True)
            with col_utilidad_card:
                st.markdown(f'''
                <div class="metric-card-special metric-card-utilidad" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;font-family:Montserrat,sans-serif;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Margen bruto:</span><span>{formato_clp(margen_valor)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>- Comisiones:</span><span>{formato_clp(total_comisiones)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.1rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:0.04em;">&#128200; UTILIDAD REAL</span>
                        <span style="font-size:2.2rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:-0.02em;">{formato_clp(utilidad_real)}</span>
                    </div>''', unsafe_allow_html=True)
        else:
            col_t1, col_t2, col_t3 = st.columns([1, 2, 1])
            with col_t2:
                st.markdown(f'''
                <div class="metric-card-special metric-card-total" style="padding:1.5rem;display:flex;flex-direction:column;justify-content:space-between;">
                    <div style="color:rgba(255,255,255,0.85);font-size:0.9rem;font-family:Montserrat,sans-serif;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:0.3rem;"><span>Costo base:</span><span>{formato_clp(subtotal_base)}</span></div>
                        <div style="display:flex;justify-content:space-between;"><span>+ IVA 19%:</span><span>{formato_clp(iva)}</span></div>
                    </div>
                    <div style="border-top:2px solid rgba(255,255,255,0.5);margin-top:1rem;padding-top:0.6rem;display:flex;justify-content:space-between;align-items:center;">
                        <span style="font-size:1.1rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:0.04em;">&#128176; TOTAL + IVA</span>
                        <span style="font-size:2.2rem;font-weight:900;color:white;font-family:Montserrat,sans-serif;letter-spacing:-0.02em;">{formato_clp(total)}</span>
                    </div>
                </div>''', unsafe_allow_html=True)
            if st.session_state.margen > 0:
                st.info("&#128274; Los detalles de comisiones y utilidad solo est&#225;n disponibles para administradores.")
    else:
        st.info("&#128072; Agrega productos al presupuesto usando los controles de la izquierda")

    # ── FAB GUARDAR FLOTANTE ────────────────────────────────────────────────
    _es_solo_lectura_fab = st.session_state.get('_adj_es_adj', False) and not st.session_state.get('es_root', False)
    _hash_actual = calcular_hash_estado()
    _hay_cambios = _hash_actual != st.session_state.get('hash_ultimo_guardado')
    _mostrar_fab = (
        len(st.session_state.get('carrito', [])) > 0
        and not _es_solo_lectura_fab
        and not st.session_state.get('recien_guardado', False)
        and not st.session_state.get('recien_cargado', False)
        and _hay_cambios
    )
    if st.session_state.get('recien_guardado', False):
        st.session_state.recien_guardado = False
    if st.session_state.get('recien_cargado', False):
        st.session_state.recien_cargado = False

    if _mostrar_fab:
        st.markdown("""
<style>
@keyframes pfab{
    0%{box-shadow:0 8px 24px rgba(91,124,250,0.5);}
    50%{box-shadow:0 8px 40px rgba(91,124,250,0.9),0 0 0 12px rgba(91,124,250,0.15);}
    100%{box-shadow:0 8px 24px rgba(91,124,250,0.5);}
}
.st-key-btn_fab_guardar {
    position: fixed !important; bottom: 1.5rem !important;
    left: 2rem !important; z-index: 999999 !important;
}
.st-key-btn_fab_guardar button {
    background: linear-gradient(135deg,#5b7cfa,#8b5cf6) !important;
    color: #fff !important; border: none !important;
    border-radius: 50px !important; padding: 0.85rem 1.6rem !important;
    font-size: 0.95rem !important; font-weight: 700 !important;
    animation: pfab 2s infinite !important; white-space: nowrap !important;
    min-width: 140px !important;
}
.st-key-btn_fab_guardar button:hover {
    transform: translateY(-3px) !important; animation: none !important;
}
</style>""", unsafe_allow_html=True)
        if st.button("\U0001f4be Guardar", key="btn_fab_guardar"):
            try:
                dc_g, da_g, proy_g, cfg_g, tots_g, pn_g, pd_g = _construir_datos_guardar_simple()
                num_g = st.session_state.cotizacion_cargada or generar_numero_unico()
                _usr_log = st.session_state.get('auth_nombre', '') or st.session_state.get('auth_email', '')
                guardar_cotizacion(num_g, dc_g, da_g, proy_g,
                                   st.session_state.carrito, cfg_g, tots_g, pn_g, pd_g,
                                   usuario_logueado=_usr_log)
                st.session_state.cotizacion_cargada = num_g
                st.session_state.hash_ultimo_guardado = calcular_hash_estado()
                st.session_state.recien_guardado = True
                st.session_state.counter += 1
                st.rerun()
            except Exception as _eg:
                st.error(f"Error al guardar: {_eg}")

    # ── MARGEN FAB (solo admin) ─────────────────────────────────────────────
    _margen_actual = st.session_state.margen
    _mstr = f"{_margen_actual:.3f}"
    if st.session_state.modo_admin and not _es_solo_lectura_fab:
        _color_fab = '#10b981' if _margen_actual > 0 else '#6b7280'
        _pct_bar = min(int(_margen_actual), 100)
        st.markdown(f"""
<style>
section[data-testid="stMain"] div[data-testid="stPopover"] {{
    position: fixed !important; left: 0 !important; top: 50% !important;
    transform: translateY(-50%) !important; bottom: unset !important;
    z-index: 99998 !important; width: 160px !important;
}}
section[data-testid="stMain"] div[data-testid="stPopover"] > div > button {{
    background: white !important; color: {_color_fab} !important;
    border: 1px solid #e2e8f0 !important; border-left: none !important;
    border-radius: 0 10px 10px 0 !important; padding: 14px 8px !important;
    width: 54px !important; min-height: unset !important; height: auto !important;
    display: flex !important; flex-direction: column !important;
    align-items: center !important; justify-content: center !important;
    gap: 2px !important; box-shadow: 0 4px 20px rgba(0,0,0,0.15) !important; font-size: 0 !important;
}}
section[data-testid="stMain"] div[data-testid="stPopover"] > div > button::before {{
    content: "{_mstr}%" !important; font-size: 0.72rem !important;
    font-weight: 900 !important; color: {_color_fab} !important; display: block !important;
}}
section[data-testid="stMain"] div[data-testid="stPopover"] > div > button::after {{
    content: "VER" !important; font-size: 0.5rem !important;
    font-weight: 700 !important; color: #9ca3af !important;
    display: block !important; white-space: pre !important;
}}
section[data-testid="stMain"] [data-testid="stPopoverBody"] {{
    background: white !important; border-radius: 0 14px 14px 0 !important;
    border: 1px solid #e2e8f0 !important; border-left: none !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.12) !important;
    padding: 12px 10px !important; width: 160px !important;
    left: 54px !important; top: 0 !important;
}}
</style>""", unsafe_allow_html=True)
        with st.popover(""):
            st.markdown(f"""
            <div style="text-align:center;margin-bottom:6px;">
              <div style="font-size:1.4rem;font-weight:900;color:{_color_fab};line-height:1;">{_mstr}%</div>
              <div style="font-size:0.6rem;color:#9ca3af;text-transform:uppercase;letter-spacing:0.05em;">Margen</div>
            </div>
            <div style="background:#f1f5f9;border-radius:99px;height:5px;margin-bottom:10px;overflow:hidden;">
              <div style="width:{_pct_bar}%;height:100%;border-radius:99px;background:{_color_fab};"></div>
            </div>""", unsafe_allow_html=True)
            _mg_pop = st.number_input(
                "Margen %", min_value=0.0, max_value=100.0,
                value=float(_margen_actual), step=0.001, format="%.3f",
                key="margen_popover"
            )
            if st.button("✅ Aplicar", key="btn_aplicar_margen", use_container_width=True):
                st.session_state.margen = _mg_pop
                st.session_state.counter += 1
                st.rerun()

    # ── PANEL PROGRESO FLOTANTE (derecha) ───────────────────────────────────
    _mostrar_prog = bool(
        st.session_state.get('cotizacion_cargada') or
        len(st.session_state.get('carrito', [])) > 0
    )
    if _mostrar_prog:
        _ss = st.session_state
        _es_juridica = _ss.get('cliente_tipo', 'natural') == 'juridica'
        _asesor_ok = bool(_ss.get('asesor_seleccionado', '') and _ss.get('asesor_seleccionado') != 'Seleccionar asesor')
        _campos_prog = [
            ('Presupuesto',     25, bool(len(_ss.get('carrito', [])) > 0)),
            ('Plano PDF',       10, bool(_ss.get('plano_adjunto') or _ss.get('pdf_url') or _ss.get('plano_nombre'))),
            ('Datos asesor',    10, _asesor_ok),
            ('Nombre cliente',  10, bool(str(_ss.get('nombre_input', '')).strip())),
            ('Correo',           8, bool(str(_ss.get('correo_input', '')).strip())),
            ('RUT',              8, bool(str(_ss.get('rut_display', '')).strip())),
            ('Teléfono',    5, bool(str(_ss.get('telefono_raw', '')).strip())),
            ('Descripción', 5, bool(str(_ss.get('observaciones_input', '')).strip())),
            ('Dir. cliente',     5, bool(str(_ss.get('direccion_input', '')).strip())),
            ('Dir. proyecto',    5, bool(str(_ss.get('proyecto_direccion', '')).strip())),
        ]
        if _es_juridica:
            _campos_prog.append(('Empresa', 5, bool(str(_ss.get('cliente_empresa', '')).strip())))
            _campos_prog.append(('RUT empresa', 4, bool(str(_ss.get('cliente_rut_empresa', '')).strip())))
        _total_peso_p = sum(p for _, p, _ in _campos_prog)
        _peso_ok_p = sum(p for _, p, v in _campos_prog if v)
        _pct_p = int(round(_peso_ok_p / _total_peso_p * 100)) if _total_peso_p > 0 else 0
        if _pct_p == 100:   _pc_p = '#10b981'
        elif _pct_p >= 70:  _pc_p = '#f97316'
        elif _pct_p >= 40:  _pc_p = '#eab308'
        else:               _pc_p = '#ef4444'
        _items_parts_p = []
        for _lbl_p, _, _ok_p in _campos_prog:
            _ic_p = '&#9989;' if _ok_p else '&#11036;'
            _col_p = '#374151' if _ok_p else '#9ca3af'
            _fw_p = '600' if _ok_p else '400'
            _items_parts_p.append(
                f'<div style="display:flex;align-items:center;gap:6px;padding:2px 0;">'
                f'<span style="font-size:0.7rem;">{_ic_p}</span>'
                f'<span style="font-size:0.7rem;color:{_col_p};font-weight:{_fw_p};">{_lbl_p}</span>'
                f'</div>'
            )
        _items_html_p = ''.join(_items_parts_p)
        _prog_html = (
            f'<div id="_prog_panel" style="position:fixed;right:0;top:50%;transform:translateY(-50%);'
            f'z-index:99997;background:#ffffff;border-radius:14px 0 0 14px;padding:12px 10px;width:148px;'
            f'box-shadow:0 4px 24px rgba(0,0,0,0.12),0 1px 4px rgba(0,0,0,0.06);border:1px solid #e2e8f0;">'
            f'<div style="text-align:center;margin-bottom:8px;">'
            f'<div style="font-size:1.4rem;font-weight:900;color:{_pc_p};line-height:1;">{_pct_p}%</div>'
            f'<div style="font-size:0.62rem;color:#9ca3af;margin-top:1px;text-transform:uppercase;letter-spacing:0.05em;">Completado</div>'
            f'</div>'
            f'<div style="background:#f1f5f9;border-radius:99px;height:6px;margin-bottom:10px;overflow:hidden;">'
            f'<div style="width:{_pct_p}%;height:100%;border-radius:99px;background:{_pc_p};transition:width 0.4s ease;"></div>'
            f'</div>'
            f'<div style="display:flex;flex-direction:column;gap:1px;">{_items_html_p}</div>'
            f'<div id="_prog_toggle" data-action="prog-toggle" style="margin-top:16px;text-align:center;'
            f'cursor:pointer;font-size:0.65rem;color:#9ca3af;padding:3px 0;'
            f'border-top:1px solid #f1f5f9;user-select:none;" title="Ocultar">› Ocultar</div>'
            f'</div>'
            f'<div id="_prog_mini" style="display:none;position:fixed;right:0;top:50%;'
            f'transform:translateY(-50%);z-index:99997;background:{_pc_p};'
            f'border-radius:10px 0 0 10px;padding:14px 8px;cursor:pointer;'
            f'box-shadow:0 4px 20px rgba(0,0,0,0.2);text-align:center;width:54px;" data-action="prog-show">'
            f'<div style="font-size:1.15rem;font-weight:900;color:#fff;line-height:1;">{_pct_p}%</div>'
            f'<div style="font-size:0.7rem;color:rgba(255,255,255,0.85);margin-top:5px;">\U0001f4ca</div>'
            f'<div style="font-size:0.58rem;font-weight:700;color:rgba(255,255,255,0.75);margin-top:3px;letter-spacing:0.06em;">VER</div>'
            f'</div>'
        )
        st.markdown(_prog_html, unsafe_allow_html=True)
        components.html("""<script>
(function(){
    var D=window.parent.document;
    function initToggle(){
        D.addEventListener('click',function(e){
            var el=e.target&&e.target.closest?e.target.closest('[data-action]'):null;
            if(!el)return;
            var action=el.getAttribute('data-action');
            var panel=D.getElementById('_prog_panel');
            var mini=D.getElementById('_prog_mini');
            if(!panel||!mini)return;
            if(action==='prog-toggle'){panel.style.display='none';mini.style.display='block';}
            else if(action==='prog-show'){panel.style.display='block';mini.style.display='none';}
        });
    }
    setTimeout(initToggle,300);
})();
</script>""", height=1)
