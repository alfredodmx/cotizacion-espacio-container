"""
Widgets reutilizables de Streamlit: selector region/comuna y deteccion de navegador.
"""
import unicodedata
import streamlit as st


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


def _normalizar_nombre(texto: str, catalogo) -> str:
    def _strip(s):
        s = s.lower().strip()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        for prefix in ('region de los ', 'region de la ', 'region del ', 'region de ', 'region '):
            if s.startswith(prefix):
                s = s[len(prefix):]
        return s
    txt_norm = _strip(texto)
    for nombre in catalogo:
        if _strip(nombre) == txt_norm:
            return nombre
    for nombre in catalogo:
        if txt_norm in _strip(nombre) or _strip(nombre) in txt_norm:
            return nombre
    return texto


def selector_comuna_region(label_com, label_reg, key_com, key_reg, val_com="", val_reg="", col_layout=None):
    """Selectbox región/comuna con auto-completado bidireccional. Default: Metropolitana/Santiago."""
    todas_regiones = list(REGIONES_COMUNAS.keys())
    _reg_init = val_reg if val_reg in todas_regiones else (
        COMUNA_A_REGION.get(val_com, "Metropolitana")
    )
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


def detectar_navegador() -> dict:
    """Detecta el navegador del usuario via User-Agent."""
    try:
        user_agent = st.context.headers.get('User-Agent', '')
        es_chrome = 'Chrome' in user_agent and 'Edg' not in user_agent
        es_edge   = 'Edg' in user_agent
        es_safari = 'Safari' in user_agent and 'Chrome' not in user_agent
        return {
            'es_chrome': es_chrome,
            'es_edge':   es_edge,
            'es_safari': es_safari,
            'es_firefox': 'Firefox' in user_agent,
            'needs_google_viewer': es_chrome or es_edge or es_safari,
        }
    except Exception:
        return {'needs_google_viewer': True}
