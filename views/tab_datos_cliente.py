import re
import streamlit as st
from views.sidebar_nav import page_icon_svg as _pi

from utils.rut import validar_rut, formatear_rut, procesar_cambio_rut, procesar_cambio_rut_empresa
from utils.telefono import formatear_telefono, _validar_telefono_cliente, procesar_cambio_telefono

# ── Regiones y comunas ─────────────────────────────────────────────────────────
REGIONES_COMUNAS = {
    "Arica y Parinacota": ["Arica","Camarones","Putre","General Lagos"],
    "Tarapacá": ["Iquique","Alto Hospicio","Pozo Almonte","Camiña","Colchane","Huara","Pica"],
    "Antofagasta": ["Antofagasta","Mejillones","Sierra Gorda","Taltal","Calama","Ollagüe","San Pedro de Atacama","Tocopilla","María Elena"],
    "Atacama": ["Copiapó","Caldera","Tierra Amarilla","Chañaral","Diego de Almagro","Vallenar","Alto del Carmen","Freirina","Huasco"],
    "Coquimbo": ["La Serena","Coquimbo","Andacollo","La Higuera","Paiguano","Vicuña","Illapel","Canela","Los Vilos","Salamanca","Ovalle","Combarbalá","Monte Patria","Punitaqui","Río Hurtado"],
    "Valparaíso": ["Valparaíso","Casablanca","Concón","Juan Fernández","Puchuncaví","Quintero","Viña del Mar","Isla de Pascua","Los Andes","Calle Larga","Rinconada","San Esteban","La Ligua","Cabildo","Papudo","Petorca","Zapallar","Quillota","Calera","Hijuelas","La Cruz","Nogales","San Antonio","Algarrobo","Cartagena","El Quisco","El Tabo","Santo Domingo","San Felipe","Catemu","Llaillay","Panquehue","Putaendo","Santa María","Quilpué","Limache","Olmué","Villa Alemana"],
    "Metropolitana": ["Santiago","Cerrillos","Cerro Navia","Conchalí","El Bosque","Estación Central","Huechuraba","Independencia","La Cisterna","La Florida","La Granja","La Pintana","La Reina","Las Condes","Lo Barnechea","Lo Espejo","Lo Prado","Macul","Maipú","Ñuñoa","Pedro Aguirre Cerda","Peñalolén","Providencia","Pudahuel","Quilicura","Quinta Normal","Recoleta","Renca","San Joaquín","San Miguel","San Ramón","Vitacura","Puente Alto","Pirque","San José de Maipo","Colina","Lampa","Tiltil","San Bernardo","Buin","Calera de Tango","Paine","Melipilla","Alhué","Curacaví","María Pinto","San Pedro","Talagante","El Monte","Isla de Maipo","Padre Hurtado","Peñaflor"],
    "O'Higgins": ["Rancagua","Codegua","Coinco","Coltauco","Doñihue","Graneros","Las Cabras","Machalí","Malloa","Mostazal","Olivar","Peumo","Pichidegua","Quinta de Tilcoco","Rengo","Requínoa","San Vicente","Pichilemu","La Estrella","Litueche","Marchihue","Navidad","Paredones","San Fernando","Chépica","Chimbarongo","Lolol","Nancagua","Palmilla","Peralillo","Placilla","Pumanque","Santa Cruz"],
    "Maule": ["Talca","Constitución","Curepto","Empedrado","Maule","Pelarco","Pencahue","Río Claro","San Clemente","San Rafael","Cauquenes","Chanco","Pelluhue","Curicó","Hualañé","Licantén","Molina","Rauco","Romeral","Sagrada Familia","Teno","Vichuquén","Linares","Colbún","Longaví","Parral","Retiro","San Javier","Villa Alegre","Yerbas Buenas"],
    "Ñuble": ["Chillán","Bulnes","Chillán Viejo","El Carmen","Pemuco","Pinto","Quillón","San Ignacio","Yungay","Cobquecura","Coelemu","Ninhue","Portezuelo","Quirihue","Ránquil","Treguaco","Coihueco","Ñiquén","San Carlos","San Fabián","San Nicolás"],
    "Biobío": ["Concepción","Coronel","Chiguayante","Florida","Hualpén","Hualqui","Lota","Penco","San Pedro de la Paz","Santa Juana","Talcahuano","Tomé","Lebu","Arauco","Cañete","Contulmo","Curanilahue","Los Álamos","Tirúa","Los Ángeles","Antuco","Cabrero","Laja","Mulchén","Nacimiento","Negrete","Quilaco","Quilleco","San Rosendo","Santa Bárbara","Tucapel","Yumbel","Alto Biobío"],
    "La Araucanía": ["Temuco","Carahue","Cunco","Curarrehue","Freire","Galvarino","Gorbea","Lautaro","Loncoche","Melipeuco","Nueva Imperial","Padre las Casas","Perquenco","Pitrufquén","Pucón","Saavedra","Teodoro Schmidt","Toltén","Vilcún","Villarrica","Cholchol","Angol","Collipulli","Curacautín","Ercilla","Lonquimay","Los Sauces","Lumaco","Purén","Renaico","Traiguén","Victoria"],
    "Los Ríos": ["Valdivia","Corral","Futrono","La Unión","Lago Ranco","Lanco","Los Lagos","Máfil","Mariquina","Paillaco","Panguipulli","Río Bueno"],
    "Los Lagos": ["Puerto Montt","Calbuco","Cochamó","Fresia","Frutillar","Los Muermos","Llanquihue","Maullín","Puerto Varas","Castro","Ancud","Chonchi","Curaco de Vélez","Dalcahue","Puqueldón","Queilén","Quellón","Quemchi","Quinchao","Osorno","Puerto Octay","Purranque","Puyehue","Río Negro","San Juan de la Costa","San Pablo","Chaitén","Futaleufú","Hualaihué","Palena"],
    "Aysén": ["Coyhaique","Lago Verde","Aysén","Cisnes","Guaitecas","Cochrane","O'Higgins","Tortel","Chile Chico","Río Ibáñez"],
    "Magallanes": ["Punta Arenas","Laguna Blanca","Río Verde","San Gregorio","Cabo de Hornos","Antártica","Porvenir","Primavera","Timaukel","Natales","Torres del Paine"],
}

COMUNA_A_REGION = {c: r for r, cs in REGIONES_COMUNAS.items() for c in cs}


def selector_comuna_region(label_com, label_reg, key_com, key_reg, val_com="", val_reg=""):
    """Región filtra comunas. Elegir comuna auto-completa región. Default: Metropolitana/Santiago."""
    todas_regiones = list(REGIONES_COMUNAS.keys())
    _reg_init = val_reg if val_reg in todas_regiones else COMUNA_A_REGION.get(val_com, "Metropolitana")
    _idx_reg = todas_regiones.index(_reg_init) if _reg_init in todas_regiones else todas_regiones.index("Metropolitana")
    region_sel = st.selectbox(label_reg, todas_regiones, index=_idx_reg, key=key_reg)
    comunas_region = REGIONES_COMUNAS.get(region_sel, [])
    if val_com in comunas_region:
        _idx_com = comunas_region.index(val_com)
    elif region_sel == "Metropolitana" and "Santiago" in comunas_region:
        _idx_com = comunas_region.index("Santiago")
    else:
        _idx_com = 0
    comuna_sel = st.selectbox(label_com, comunas_region, index=_idx_com, key=key_com)
    return comuna_sel, region_sel


def _rerun_hb():
    pass


def _listar_usuarios_ejecutivos(supabase_admin, roots):
    """Lista usuarios excluyendo roots."""
    try:
        res = supabase_admin.auth.admin.list_users()
        users = []
        for u in res:
            email = u.email or ""
            if email.lower() in [s.lower() for s in roots]:
                continue
            meta = u.user_metadata or {}
            nombre = meta.get("nombre", email)
            rol = meta.get("rol", "ejecutivo")
            try:
                _activo = not getattr(u, 'banned_until', None)
            except:
                _activo = True
            users.append({
                "id": str(u.id),
                "email": email,
                "nombre": nombre,
                "rol": rol,
                "telefono": meta.get("telefono", "") or "",
                "created_at": str(u.created_at)[:10] if u.created_at else "",
                "activo": _activo
            })
        return users
    except Exception as e:
        st.session_state['_usuarios_list_error'] = str(e)
        return []


def render_tab_datos_cliente(supabase, supabase_admin, supa_url, supa_key, **deps):
    _roots_raw = st.secrets.get("ROOTS", "")
    ROOTS = [r.strip().lower() for r in _roots_raw.split(",") if r.strip()]

    st.markdown("""
    <style>
    .hdr2 {
        background: linear-gradient(135deg, #2d0d66 0%, #5b0d7a 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(91,13,122,0.25);
        position: relative; overflow: hidden;
    }
    .hdr2::before {
        content: ''; position: absolute; top: -40px; right: -40px;
        width: 180px; height: 180px; border-radius: 50%;
        background: rgba(255,255,255,0.04); pointer-events: none;
    }
    .hdr2::after {
        content: ''; position: absolute; bottom: -60px; right: 80px;
        width: 240px; height: 240px; border-radius: 50%;
        background: rgba(255,255,255,0.03); pointer-events: none;
    }
    .hdr2 h2 { color: #fff !important; margin: 0; font-size: 0.88rem; font-weight: 700;
                 font-family: 'Montserrat', sans-serif; letter-spacing: 0.05em; text-transform: uppercase; }
    .hdr2 p  { color: rgba(255,255,255,0.65) !important; margin: 1px 0 0; font-size: 0.92rem;
               font-family: 'Montserrat', sans-serif; font-weight: 500; letter-spacing: 0.01em; }
    </style>
    <div class="hdr2" style="display:flex!important;align-items:center!important;">
      """ + _pi("datos") + """
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Datos del Cliente</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Completa la información del cliente y del proyecto antes de guardar.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    es_solo_lectura = bool(
        st.session_state.cotizacion_cargada and
        st.session_state.margen > 0 and
        not st.session_state.modo_admin
    )
    _mostrar_hb = len(st.session_state.get('carrito', [])) > 0 and not es_solo_lectura

    fecha_inicio  = st.session_state.fecha_inicio
    fecha_termino = st.session_state.fecha_termino
    dias_validez  = (fecha_termino - fecha_inicio).days

    # ── Modo solo lectura ─────────────────────────────────────────────────────
    if es_solo_lectura:
        st.warning("&#128274; Modo solo lectura — cotización con márgenes aplicados.")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            with st.container(border=True):
                st.markdown("**&#128100; Cliente**")
                _tipo_lbl = "Persona jurídica" if st.session_state.cliente_tipo == "juridica" else "Persona natural"
                st.caption(f"&#127991; {_tipo_lbl}")
                st.text_input("Nombre", value=st.session_state.nombre_input, disabled=True, key="nombre_readonly")
                st.text_input("RUT", value=st.session_state.rut_display, disabled=True, key="rut_readonly")
                st.text_input("Correo", value=st.session_state.correo_input, disabled=True, key="correo_readonly")
                st.text_input("Teléfono", value=st.session_state.telefono_raw, disabled=True, key="telefono_readonly")
                if st.session_state.cliente_tipo == "juridica":
                    st.markdown("**&#127970; Empresa**")
                    st.text_input("Razón social", value=st.session_state.cliente_empresa, disabled=True, key="empresa_readonly")
                    st.text_input("RUT empresa", value=st.session_state.cliente_rut_empresa, disabled=True, key="rut_empresa_readonly")
        with col2:
            with st.container(border=True):
                st.markdown("**&#128205; Cliente**")
                st.text_input("Dirección cliente", value=st.session_state.direccion_input, disabled=True, key="direccion_readonly")
                st.text_input("Comuna cliente", value=st.session_state.cliente_comuna, disabled=True, key="cliente_comuna_readonly")
                st.text_input("Región cliente", value=st.session_state.cliente_region, disabled=True, key="cliente_region_readonly")
                st.markdown("**&#127959; Proyecto**")
                st.text_input("Dirección instalación", value=st.session_state.proyecto_direccion, disabled=True, key="proyecto_dir_readonly")
                st.text_input("Comuna instalación", value=st.session_state.proyecto_comuna, disabled=True, key="proyecto_com_readonly")
                st.text_input("Región instalación", value=st.session_state.proyecto_region, disabled=True, key="proyecto_reg_readonly")
        with col3:
            with st.container(border=True):
                st.markdown("**&#128188; Ejecutivo**")
                st.text_input("Asesor", value=st.session_state.asesor_seleccionado, disabled=True, key="asesor_readonly")
                st.text_input("Correo Ejecutivo", value=st.session_state.correo_asesor, disabled=True, key="correo_asesor_readonly")
                st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, disabled=True, key="telefono_asesor_readonly")
        with col4:
            with st.container(border=True):
                st.markdown("**&#128197; Validez**")
                st.date_input("Fecha Inicio", value=fecha_inicio, disabled=True, key="fecha_inicio_readonly")
                st.date_input("Fecha Término", value=fecha_termino, disabled=True, key="fecha_termino_readonly")
                st.markdown(f"**&#9201; Duración:** {dias_validez} días")
                if dias_validez > 0:
                    st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días")
        with st.container(border=True):
            st.markdown("**&#128221; Descripción del proyecto**")
            st.text_area("Descripción del proyecto", value=st.session_state.observaciones_input,
                         disabled=True, height=80, key="observaciones_readonly")

    else:
        # ── Cargar asesores desde Supabase ────────────────────────────────────
        def _cargar_asesores():
            try:
                _users = _listar_usuarios_ejecutivos(supabase_admin, ROOTS)
                _d = {"Seleccionar asesor": {"correo": "", "telefono": ""}}
                for _usr in _users:
                    _nm = (_usr.get('nombre') or _usr.get('email', '')).upper()
                    if _nm and _nm != "SELECCIONAR ASESOR":
                        _d[_nm] = {
                            "correo": _usr.get('email', '').upper(),
                            "telefono": _usr.get('telefono', '') or ''
                        }
                return _d
            except:
                return {
                    "Seleccionar asesor": {"correo": "", "telefono": ""},
                    "BERNARD BUSTAMANTE": {"correo": "BALDAY@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56956786366"},
                    "ANDREA OSORIO": {"correo": "AOSORIO@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56927619483"},
                    "REBECA CALDERON": {"correo": "RCALDERON@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56955286708"},
                    "MAURICIO CEVO": {"correo": "MCEVO@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56971406162"},
                    "JACQUELINE PÉREZ": {"correo": "JPEREZ@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56992286057"},
                    "JAVIER QUEZADA": {"correo": "JQUEZADA@ESPACIOCONTAINERHOUSE.CL", "telefono": "+56966983700"}
                }

        if ('_asesores_cache' not in st.session_state or
                st.session_state.get('_asesores_cache_dirty', False)):
            st.session_state['_asesores_cache'] = _cargar_asesores()
            st.session_state['_asesores_cache_dirty'] = False

        asesores = st.session_state['_asesores_cache']

        col1, col2, col3, col4 = st.columns(4)

        # ── Columna 1: Cliente ────────────────────────────────────────────────
        with col1:
            with st.container(border=True):
                st.markdown("**&#128100; Cliente**")

                tipo_key = f"cliente_tipo_{st.session_state.counter}"
                _tipo_options = ["natural", "juridica"]
                _tipo_labels  = ["Persona natural", "Persona jurídica"]
                _tipo_idx = _tipo_options.index(st.session_state.cliente_tipo) if st.session_state.cliente_tipo in _tipo_options else 0
                _tipo_sel = st.radio("Tipo", _tipo_labels, index=_tipo_idx,
                                     horizontal=True, key=tipo_key, label_visibility="collapsed")
                _tipo_val = _tipo_options[_tipo_labels.index(_tipo_sel)]
                if _tipo_val != st.session_state.cliente_tipo:
                    st.session_state.cliente_tipo = _tipo_val
                    st.rerun()

                nombre_key = f"nombre_input_{st.session_state.counter}"
                _nombre_ok  = bool(str(st.session_state.nombre_input).strip())
                _nombre_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _nombre_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Nombre Completo*</b>{_nombre_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                nombre = st.text_input("Nombre Completo*", placeholder="Ej: Juan Pérez", key=nombre_key,
                                       value=st.session_state.nombre_input, label_visibility="collapsed",
                                       on_change=_rerun_hb)
                if nombre != st.session_state.nombre_input:
                    st.session_state.nombre_input = nombre

                correo_key = f"correo_input_{st.session_state.counter}"
                _correo_ok  = bool(str(st.session_state.correo_input).strip())
                _correo_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _correo_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Correo Electrónico*</b>{_correo_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                correo = st.text_input("Correo Electrónico*", placeholder="ejemplo@correo.cl", key=correo_key,
                                       value=st.session_state.correo_input, label_visibility="collapsed",
                                       on_change=_rerun_hb)
                if correo != st.session_state.correo_input:
                    st.session_state.correo_input = correo
                if correo and "@" not in correo:
                    st.warning("&#9888;&#65039; El correo debe contener @")

                rut_key = f"rut_input_{st.session_state.counter}"
                _rut_ok  = bool(str(st.session_state.rut_display).strip())
                _rut_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _rut_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">RUT</b>{_rut_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                st.text_input("RUT", value=st.session_state.rut_display, key=rut_key,
                              placeholder="12.345.678-9", on_change=procesar_cambio_rut, label_visibility="collapsed")
                if st.session_state.rut_raw:
                    if len(st.session_state.rut_raw) >= 2:
                        if st.session_state.rut_valido:
                            if "extranjero" in st.session_state.rut_mensaje.lower():
                                st.warning(f"&#9888;&#65039; {st.session_state.rut_mensaje}")
                            else:
                                st.success("&#9989; RUT válido")
                        else:
                            _msg_rut = st.session_state.rut_mensaje
                            if "extranjero" in _msg_rut.lower():
                                st.warning("&#9888;&#65039; RUT inválido o RUT extranjero")
                            else:
                                st.error(f"&#10060; {_msg_rut}")
                    else:
                        st.info("&#9203; RUT incompleto")

                telefono_key = f"telefono_input_{st.session_state.counter}"
                _tel_ok2  = bool(str(st.session_state.telefono_raw).strip())
                _tel_dot2 = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _tel_ok2 else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Teléfono</b>{_tel_dot2 if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                st.text_input("Teléfono", value=st.session_state.telefono_raw, key=telefono_key,
                              placeholder="961528954 (9 dígitos sin +56)", on_change=procesar_cambio_telefono,
                              label_visibility="collapsed")
                if st.session_state.telefono_raw:
                    _tel_msg = st.session_state.get('telefono_mensaje', '')
                    _tel_ok  = st.session_state.get('telefono_valido', False)
                    if _tel_msg:
                        if _tel_msg.startswith('✅'):
                            st.success(_tel_msg)
                        elif _tel_msg.startswith('⚠️'):
                            st.warning(_tel_msg)
                        else:
                            st.error(_tel_msg)
                    if _tel_ok:
                        _tel_preview = formatear_telefono(st.session_state.telefono_raw)
                        st.caption(f"&#128241; Se guardará como: {_tel_preview}")

                if st.session_state.cliente_tipo == "juridica":
                    st.markdown("---")
                    st.markdown("**&#127970; Empresa**")
                    emp_key = f"cliente_empresa_{st.session_state.counter}"
                    _emp_ok  = bool(str(st.session_state.cliente_empresa).strip())
                    _emp_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _emp_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Razón social*</b>{_emp_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                    empresa = st.text_input("Razón social*", placeholder="Ej: Constructora ABC SpA",
                                            key=emp_key, value=st.session_state.cliente_empresa,
                                            label_visibility="collapsed", on_change=_rerun_hb)
                    if empresa != st.session_state.cliente_empresa:
                        st.session_state.cliente_empresa = empresa

                    rut_emp_key = f"rut_empresa_input_{st.session_state.counter}"
                    _rut_emp_ok  = bool(str(st.session_state.rut_empresa_display).strip())
                    _rut_emp_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _rut_emp_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">RUT empresa*</b>{_rut_emp_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                    st.text_input("RUT empresa*", placeholder="76.123.456-7",
                                  key=rut_emp_key, value=st.session_state.rut_empresa_display,
                                  on_change=procesar_cambio_rut_empresa, label_visibility="collapsed")
                    if st.session_state.rut_empresa_raw:
                        if len(st.session_state.rut_empresa_raw) >= 2:
                            if st.session_state.rut_empresa_valido:
                                if "extranjero" in (st.session_state.rut_empresa_mensaje or '').lower():
                                    st.warning(f"&#9888;&#65039; {st.session_state.rut_empresa_mensaje}")
                                else:
                                    st.success("&#9989; RUT válido")
                            else:
                                st.error(f"&#10060; {st.session_state.rut_empresa_mensaje}")
                        else:
                            st.info("&#9203; RUT incompleto")

        # ── Columna 2: Dirección ──────────────────────────────────────────────
        with col2:
            with st.container(border=True):
                st.markdown("**&#128205; Cliente**")
                direccion_key = f"direccion_input_{st.session_state.counter}"
                _dir_ok  = bool(str(st.session_state.direccion_input).strip())
                _dir_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _dir_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Dirección cliente</b>{_dir_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                direccion = st.text_input("Dirección cliente", placeholder="Calle, número",
                                          key=direccion_key, value=st.session_state.direccion_input,
                                          label_visibility="collapsed", on_change=_rerun_hb)
                if direccion != st.session_state.direccion_input:
                    st.session_state.direccion_input = direccion
                _com_cli, _reg_cli = selector_comuna_region(
                    "Comuna cliente", "Región cliente",
                    f"cliente_comuna_{st.session_state.counter}",
                    f"cliente_region_{st.session_state.counter}",
                    val_com=st.session_state.cliente_comuna,
                    val_reg=st.session_state.cliente_region,
                )
                st.session_state.cliente_comuna = _com_cli
                st.session_state.cliente_region = _reg_cli

                st.markdown("**&#127959; Proyecto**")
                proy_dir_key = f"proyecto_direccion_{st.session_state.counter}"
                _proy_ok  = bool(str(st.session_state.proyecto_direccion).strip())
                _proy_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _proy_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Dirección instalación</b>{_proy_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                proy_dir = st.text_input("Dirección instalación", placeholder="Calle, número",
                                         key=proy_dir_key, value=st.session_state.proyecto_direccion,
                                         label_visibility="collapsed", on_change=_rerun_hb)
                if proy_dir != st.session_state.proyecto_direccion:
                    st.session_state.proyecto_direccion = proy_dir
                _com_proy, _reg_proy = selector_comuna_region(
                    "Comuna instalación", "Región instalación",
                    f"proyecto_comuna_{st.session_state.counter}",
                    f"proyecto_region_{st.session_state.counter}",
                    val_com=st.session_state.proyecto_comuna,
                    val_reg=st.session_state.proyecto_region,
                )
                st.session_state.proyecto_comuna = _com_proy
                st.session_state.proyecto_region = _reg_proy

        # ── Columna 3: Ejecutivo ──────────────────────────────────────────────
        _rol_actual  = st.session_state.get('rol_usuario', 'ejecutivo')
        _es_ejecutivo = _rol_actual == 'ejecutivo'

        if _es_ejecutivo:
            _email_logueado  = st.session_state.get('auth_email', '').upper()
            _nombre_logueado = st.session_state.get('auth_nombre', '').upper()
            _datos_ej = None
            for _nm, _dat in asesores.items():
                if _nm == "Seleccionar asesor":
                    continue
                if _dat["correo"].upper() == _email_logueado or _nm.upper() == _nombre_logueado:
                    _datos_ej = (_nm, _dat)
                    break
            if not _datos_ej and _nombre_logueado:
                _datos_ej = (_nombre_logueado, {
                    "correo": st.session_state.get('auth_email', ''),
                    "telefono": st.session_state.get('auth_telefono', '')
                })
            if _datos_ej and st.session_state.asesor_seleccionado != _datos_ej[0]:
                st.session_state.asesor_seleccionado = _datos_ej[0]
                st.session_state.correo_asesor   = _datos_ej[1]["correo"]
                st.session_state.telefono_asesor = _datos_ej[1]["telefono"]

        with col3:
            with st.container(border=True):
                st.markdown("**&#128188; Ejecutivo**")

                if _es_ejecutivo:
                    _dot_check = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Nombre</b>{_dot_check}</span>', unsafe_allow_html=True)
                    st.text_input("Nombre", value=st.session_state.asesor_seleccionado, disabled=True,
                                  key=f"ej_nombre_fixed_{st.session_state.counter}", label_visibility="collapsed")
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Correo Ejecutivo</b>{_dot_check}</span>', unsafe_allow_html=True)
                    st.text_input("Correo Ejecutivo*", value=st.session_state.correo_asesor, disabled=True,
                                  key=f"ej_correo_fixed_{st.session_state.counter}", label_visibility="collapsed")
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Teléfono Ejecutivo</b>{_dot_check}</span>', unsafe_allow_html=True)
                    st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor, disabled=True,
                                  key=f"ej_tel_fixed_{st.session_state.counter}", label_visibility="collapsed")
                    st.caption("&#128274; Tus datos están asignados automáticamente.")
                else:
                    _asesor_sel_ok  = (st.session_state.asesor_seleccionado not in ("", "Seleccionar asesor"))
                    _asesor_sel_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _asesor_sel_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
                    st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">Asesor</b>{_asesor_sel_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                    nombres_asesores = list(asesores.keys())
                    asesor_key = f"asesor_select_{st.session_state.counter}"
                    indice_actual = nombres_asesores.index(st.session_state.asesor_seleccionado) if st.session_state.asesor_seleccionado in nombres_asesores else 0
                    asesor_elegido = st.selectbox("Asesor", nombres_asesores, index=indice_actual,
                                                  key=asesor_key, label_visibility="collapsed")
                    if asesor_elegido != st.session_state.asesor_seleccionado:
                        st.session_state.asesor_seleccionado = asesor_elegido
                        if asesor_elegido != "Seleccionar asesor":
                            st.session_state.correo_asesor   = asesores[asesor_elegido]["correo"]
                            st.session_state.telefono_asesor = asesores[asesor_elegido]["telefono"]
                        else:
                            st.session_state.correo_asesor   = ""
                            st.session_state.telefono_asesor = ""
                        st.session_state.counter += 1
                        st.rerun()

                    correo_asesor_key = f"asesor_correo_input_{st.session_state.counter}"
                    correo_input = st.text_input("Correo Ejecutivo*", value=st.session_state.correo_asesor,
                                                 placeholder="ejecutivo@empresa.cl", key=correo_asesor_key)
                    if correo_input and "@" not in correo_input:
                        st.warning("&#9888;&#65039; El correo debe contener @")
                    if correo_input != st.session_state.correo_asesor:
                        st.session_state.correo_asesor = correo_input
                        st.session_state.asesor_seleccionado = "Seleccionar asesor"
                        st.session_state.counter += 1
                        st.rerun()

                    telefono_asesor_key = f"asesor_telefono_input_{st.session_state.counter}"
                    telefono_input = st.text_input("Teléfono Ejecutivo", value=st.session_state.telefono_asesor,
                                                   key=telefono_asesor_key, placeholder="912345678 (9 dígitos)")
                    if telefono_input != st.session_state.telefono_asesor:
                        raw = re.sub(r'[^0-9]', '', telefono_input)
                        if len(raw) >= 11 and raw.startswith('56'):
                            raw = raw[2:]
                        if len(raw) > 9:
                            raw = raw[:9]
                        st.session_state.telefono_asesor = raw
                        st.session_state.asesor_seleccionado = "Seleccionar asesor"
                        st.session_state.counter += 1
                        st.rerun()

        # ── Columna 4: Validez ────────────────────────────────────────────────
        with col4:
            with st.container(border=True):
                _fecha_dot_a = '<span class="_hb_dot"><span class="_hb_ring_a"></span><span class="_hb_core_a"></span></span>'
                st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">&#128197; Validez</b>{_fecha_dot_a if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
                fecha_inicio_key = f"fecha_inicio_{st.session_state.counter}"
                fecha_inicio = st.date_input("Fecha de Inicio", value=st.session_state.fecha_inicio,
                                             key=fecha_inicio_key)
                if fecha_inicio != st.session_state.fecha_inicio:
                    st.session_state.fecha_inicio = fecha_inicio

                fecha_termino_key = f"fecha_termino_{st.session_state.counter}"
                fecha_termino = st.date_input("Fecha de Término", value=st.session_state.fecha_termino,
                                              key=fecha_termino_key)
                if fecha_termino != st.session_state.fecha_termino:
                    st.session_state.fecha_termino = fecha_termino

                dias_validez = (fecha_termino - fecha_inicio).days
                if dias_validez < 0:
                    st.error("&#9888;&#65039; Fecha de término anterior a inicio.")
                else:
                    st.markdown(f"**&#9201; Duración:** {dias_validez} días")
                    if dias_validez > 0:
                        st.progress(min(dias_validez/30, 1.0), text=f"{dias_validez} días de validez")

        # ── Observaciones (ancho completo) ────────────────────────────────────
        with st.container(border=True):
            _obs_ok  = bool(str(st.session_state.observaciones_input).strip())
            _obs_dot = '<span class="_hb_dot"><span class="_hb_check_wrap"></span><svg style="position:absolute;inset:0;width:20px;height:20px;" viewBox="0 0 20 20"><polyline points="3,10 7.5,14.5 17,5" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></span>' if _obs_ok else '<span class="_hb_dot"><span class="_hb_ring_r"></span><span class="_hb_core_r"></span></span>'
            st.markdown(f'<span class="_hb_wrap"><b style="font-size:0.85rem;">&#128221; Descripción del proyecto</b>{_obs_dot if _mostrar_hb else ""}</span>', unsafe_allow_html=True)
            observaciones_key = f"observaciones_input_{st.session_state.counter}"
            observaciones = st.text_area("Descripción del proyecto",
                                         placeholder="Describe el proyecto, características especiales o información relevante...",
                                         height=80, key=observaciones_key,
                                         value=st.session_state.observaciones_input,
                                         label_visibility="collapsed", on_change=_rerun_hb)
            if observaciones != st.session_state.observaciones_input:
                st.session_state.observaciones_input = observaciones

    # ── Exponer datos_cliente / datos_asesor en session_state ─────────────────
    nombre_asesor_final = st.session_state.asesor_seleccionado if st.session_state.asesor_seleccionado != "Seleccionar asesor" else ""
    st.session_state['_datos_cliente'] = {
        "Nombre": st.session_state.nombre_input or "",
        "RUT": st.session_state.rut_display or "",
        "Correo": st.session_state.correo_input or "",
        "Teléfono": formatear_telefono(st.session_state.telefono_raw) if st.session_state.telefono_raw else "",
        "Dirección": st.session_state.direccion_input or "",
        "ComunaCliente": st.session_state.cliente_comuna or "",
        "RegionCliente": st.session_state.cliente_region or "",
        "DireccionProyecto": st.session_state.proyecto_direccion or "",
        "ComunaProyecto": st.session_state.proyecto_comuna or "",
        "RegionProyecto": st.session_state.proyecto_region or "",
        "TipoCliente": st.session_state.cliente_tipo or "natural",
        "EmpresaCliente": st.session_state.cliente_empresa or "",
        "RutEmpresa": st.session_state.cliente_rut_empresa or "",
        "Observaciones": st.session_state.observaciones_input or ""
    }
    st.session_state['_datos_asesor'] = {
        "Nombre Ejecutivo": nombre_asesor_final,
        "Correo Ejecutivo": st.session_state.correo_asesor or "",
        "Teléfono Ejecutivo": st.session_state.telefono_asesor or ""
    }
