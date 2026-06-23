"""
Tab EDICIÓN PDF — Edición de descripciones por categoría para PDF cliente.
Código fuente original: app.py líneas 16620-16791 (with tab6)
"""
import json
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from views.layout import render_page_header


def _cargar_cotizacion(supa_admin, numero):
    try:
        if not numero:
            return None
        response = supa_admin.table('cotizaciones').select('*').eq('numero', numero).execute()
        if response.data:
            cot = response.data[0]
            productos = cot.get('productos')
            if isinstance(productos, str):
                cot['productos'] = json.loads(productos)
            elif not isinstance(productos, list):
                cot['productos'] = []
            return cot
        return None
    except Exception as e:
        st.error(f"Error al cargar cotización: {e}")
        return None


def _cargar_descripciones(supa_url, numero, bust_cache=False):
    try:
        import requests as _rq
        import time as _time
        _base = supa_url.rstrip("/")
        _fname = f"pdf_desc_{numero}.json"
        url = f"{_base}/storage/v1/object/public/config/{_fname}"
        if bust_cache:
            url += f"?t={int(_time.time())}"
        r = _rq.get(url, timeout=5, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {}


def _guardar_descripciones(supabase, numero, descripciones: dict):
    try:
        _fname = f"pdf_desc_{numero}.json"
        data = json.dumps(descripciones, ensure_ascii=False, indent=2).encode("utf-8")
        try:
            supabase.storage.from_("config").remove([_fname])
        except Exception:
            pass
        supabase.storage.from_("config").upload(
            path=_fname,
            file=data,
            file_options={"content-type": "application/json", "upsert": "true"}
        )
        return True
    except Exception as e:
        st.error(f"Error al guardar descripciones: {e}")
        return False


def render_tab_pdf(supabase, supa_url, supa_key, **deps):
    supa_admin = deps.get('supabase_admin', _supa_admin)

    st.markdown("""
    <style>
    .hdr6 {
        background: linear-gradient(135deg, #b91c1c 0%, #dc2626 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(220,38,38,0.25);
        position: relative; overflow: hidden;
    }
    </style>
    """, unsafe_allow_html=True)
    render_page_header(
        "edicion_pdf",
        "Edici&#243;n PDF Cliente",
        "Busca tu cotizaci&#243;n por n&#250;mero EP y personaliza la descripci&#243;n de cada categor&#237;a para el cliente.",
    )

    with st.container(border=True):
        st.markdown("#### &#128269; Buscar cotizaci&#243;n")
        col_ep, col_btn = st.columns([3, 1])
        with col_ep:
            _ep_buscar = st.text_input("N&#250;mero EP", placeholder="Ej: EP-22286",
                                       key="pdf_edit_ep_input",
                                       label_visibility="collapsed")
        with col_btn:
            _btn_buscar_ep = st.button("&#128269; Buscar", use_container_width=True,
                                       key="pdf_edit_btn_buscar", type="primary")

    if 'pdf_edit_cotizacion' not in st.session_state:
        st.session_state.pdf_edit_cotizacion = None
    if 'pdf_edit_numero' not in st.session_state:
        st.session_state.pdf_edit_numero = None

    if _btn_buscar_ep and _ep_buscar.strip():
        _cot_found = _cargar_cotizacion(supa_admin, _ep_buscar.strip().upper())
        if _cot_found:
            st.session_state.pdf_edit_cotizacion = _cot_found
            st.session_state.pdf_edit_numero = _ep_buscar.strip().upper()
            st.success(f"&#9989; Cotizaci&#243;n {st.session_state.pdf_edit_numero} encontrada &#8212; {_cot_found.get('cliente_nombre','S/C')}")
        else:
            st.error("&#10060; No se encontr&#243; la cotizaci&#243;n. Verifica el n&#250;mero EP.")
            st.session_state.pdf_edit_cotizacion = None
            st.session_state.pdf_edit_numero = None

    if st.session_state.pdf_edit_cotizacion and st.session_state.pdf_edit_numero:
        _cot_edit = st.session_state.pdf_edit_cotizacion
        _num_edit = st.session_state.pdf_edit_numero

        st.markdown(f"""
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;
                    padding:12px 16px;margin:12px 0;">
            <b>&#128203; {_num_edit}</b> &#8212; {_cot_edit.get('cliente_nombre','S/C')} &nbsp;|&nbsp;
            Asesor: {_cot_edit.get('asesor_nombre','&#8212;')} &nbsp;|&nbsp;
            Fecha: {(_cot_edit.get('fecha_creacion','')[:10])}
        </div>
        """, unsafe_allow_html=True)

        _init_key = f"_desc_init_{_num_edit}"
        if _init_key not in st.session_state:
            _desc_storage = _cargar_descripciones(supa_url, _num_edit, bust_cache=True)
            for _k, _v in _desc_storage.items():
                _ta_key = f"pdf_edit_desc_{_num_edit}_{_k}"
                if _ta_key not in st.session_state:
                    st.session_state[_ta_key] = _v
            st.session_state[_init_key] = True

        _productos = _cot_edit.get('productos', [])
        if _productos:
            _cats_ep = sorted(list({p.get('Categoria','') for p in _productos if p.get('Categoria','')}))
        else:
            _cats_ep = []

        if not _cats_ep:
            st.warning("Esta cotizaci&#243;n no tiene productos con categor&#237;as definidas.")
        else:
            st.markdown(f"#### &#128221; Editar descripciones ({len(_cats_ep)} categor&#237;as)")
            st.caption("Escribe la descripci&#243;n que ver&#225; el cliente en el PDF. Si la dejas vac&#237;a, se mostrar&#225;n los &#237;tems del carrito.")

            _desc_editadas = {}
            for _cat in _cats_ep:
                _key_ta = f"pdf_edit_desc_{_num_edit}_{_cat}"
                _tiene_desc = bool(st.session_state.get(_key_ta, '').strip())
                with st.container(border=True):
                    col_cat, col_estado, col_limpiar_uno = st.columns([3, 1, 1])
                    with col_cat:
                        st.markdown(f"**{_cat}**")
                    with col_estado:
                        if _tiene_desc:
                            st.markdown("&#128995; Personalizada")
                        else:
                            st.markdown("&#11036; Por defecto")
                    with col_limpiar_uno:
                        if _tiene_desc:
                            if st.button("&#128465;&#65039; Limpiar", key=f"pdf_limpiar_{_num_edit}_{_cat}",
                                         use_container_width=True):
                                st.session_state[_key_ta] = ''
                                _dict_sin = {
                                    _c: st.session_state.get(f"pdf_edit_desc_{_num_edit}_{_c}", '')
                                    for _c in _cats_ep
                                    if _c != _cat and st.session_state.get(f"pdf_edit_desc_{_num_edit}_{_c}", '').strip()
                                }
                                _guardar_descripciones(supabase, _num_edit, _dict_sin)
                                st.rerun()

                    _nueva = st.text_area(
                        f"Descripci&#243;n para {_cat}",
                        height=80,
                        placeholder=f"Ej: Incluye todos los elementos de {_cat.lower()}...",
                        key=_key_ta,
                        label_visibility="collapsed"
                    )
                    _desc_editadas[_cat] = _nueva

            st.markdown("")
            col_guardar, col_limpiar = st.columns([2, 1])
            with col_guardar:
                if st.button("&#128190; Guardar todas las descripciones", type="primary",
                             use_container_width=True, key="pdf_edit_guardar_todo"):
                    _dict_final = {k: v.strip() for k, v in _desc_editadas.items() if v.strip()}
                    if _guardar_descripciones(supabase, _num_edit, _dict_final):
                        st.success("&#9989; Descripciones guardadas. Se usar&#225;n al generar el PDF cliente.")
                        if _init_key in st.session_state:
                            del st.session_state[_init_key]
                        st.session_state.pdf_edit_cotizacion = None
                        st.session_state.pdf_edit_numero = None
                        st.rerun()

            with col_limpiar:
                if st.button("&#128465;&#65039; Limpiar todas", use_container_width=True,
                             key="pdf_edit_limpiar_todo"):
                    _guardar_descripciones(supabase, _num_edit, {})
                    for _c in _cats_ep:
                        _kw = f"pdf_edit_desc_{_num_edit}_{_c}"
                        if _kw in st.session_state:
                            del st.session_state[_kw]
                    if _init_key in st.session_state:
                        del st.session_state[_init_key]
                    st.session_state.pdf_edit_cotizacion = None
                    st.session_state.pdf_edit_numero = None
                    st.rerun()
    else:
        st.info("&#128269; Ingresa el n&#250;mero EP y presiona Buscar para editar las descripciones de una cotizaci&#243;n.")
