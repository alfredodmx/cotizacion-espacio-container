"""
Tab PROYECTO EXCEL — Control de versiones del cotizador.xlsx + Visor 3D Beta.
Código fuente original: app.py líneas 13272-13630 (excel) + visor 3D
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin
from utils.excel_manager import (
    get_excel_bytes_activo,
    leer_hoja_excel,
    leer_bd_total,
    cargar_visibilidad_impresion,
    exportar_csv_completo,
)


def render_tab_proyecto_excel(supabase, supabase_admin=None, supa_url='', supa_key='', **deps):
    supa_admin = supabase_admin or _supa_admin

    _get_excel_bytes_activo       = get_excel_bytes_activo
    _leer_hoja_excel              = leer_hoja_excel
    _leer_bd_total                = leer_bd_total
    _cargar_visibilidad_impresion = cargar_visibilidad_impresion
    _exportar_csv_completo        = exportar_csv_completo

    # ── CSS y Header ──
    st.markdown("""
    <style>
    .excel-header {
        background: linear-gradient(135deg, #0f2240 0%, #1a4d33 100%);
        border-radius: 20px; padding: 34px 36px; margin-bottom: 28px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(26,77,51,0.3);
    }
    .ind-titulo {
        display: flex; align-items: center; gap: 10px;
        font-size: 0.7rem; font-weight: 800; letter-spacing: 0.15em;
        text-transform: uppercase; color: #1e293b;
        border-left: 4px solid #f59e0b;
        padding: 6px 0 6px 12px;
        margin: 20px 0 14px 0;
    }
    .ver-activa {
        background: linear-gradient(90deg, rgba(16,185,129,0.07), rgba(16,185,129,0.02));
        border: 1px solid #10b981; border-left: 5px solid #10b981;
        border-radius: 10px; padding: 14px 18px; margin-bottom: 8px;
    }
    .ver-row {
        background: #f8fafc; border: 1px solid #e2e8f0; border-left: 5px solid #cbd5e1;
        border-radius: 10px; padding: 14px 18px; margin-bottom: 8px;
    }
    .ver-nombre-activa { font-size:1rem; font-weight:700; color:#065f46; }
    .ver-nombre       { font-size:1rem; font-weight:600; color:#1e293b; }
    .ver-badge { display:inline-block; background:#10b981; color:white; font-size:0.6rem;
                 font-weight:800; letter-spacing:0.1em; padding:2px 7px; border-radius:4px;
                 text-transform:uppercase; vertical-align:middle; margin-left:8px; }
    .ver-meta   { font-size:0.75rem; color:#64748b; margin-top:3px; }
    .ver-archivo{ font-size:0.7rem; color:#94a3b8; font-family:monospace; margin-top:2px; }
    </style>
    <div class="excel-header">
      <span style="font-size:2.8rem;line-height:1;flex-shrink:0;">&#128202;</span>
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.6rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Proyecto Excel &mdash; Control de Versiones</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.92rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Sube nuevas versiones del cotizador.xlsx y activa la que necesites. El sistema se actualiza al instante.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Subir nueva versión ──
    st.markdown('<div class="ind-titulo">&#11014; Subir nueva versi&#243;n</div>', unsafe_allow_html=True)

    if "excel_upload_key" not in st.session_state:
        st.session_state.excel_upload_key = 0

    with st.container():
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        _mg_l, _titulo_col, _mg_r = st.columns([0.4, 9, 0.4])
        with _titulo_col:
            st.markdown("##### &#11014;&#65039; Subir nueva versi&#243;n")
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

        _mg, _col_up1, _col_up2, _mg2 = st.columns([0.4, 3, 2, 0.4])
        with _col_up1:
            _excel_file = st.file_uploader(
                "Archivo cotizador.xlsx", type=["xlsx"],
                key=f"uploader_excel_{st.session_state.excel_upload_key}",
                label_visibility="collapsed"
            )
        with _col_up2:
            st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
            _version_nombre = st.text_input(
                "Nombre de versi&#243;n", placeholder="Ej: v2.1 — Abril 2025",
                key=f"input_vnom_{st.session_state.excel_upload_key}",
                label_visibility="collapsed"
            )
            st.caption("&#128221; Nombre de la versi&#243;n")

        if _excel_file and _version_nombre:
            st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
            _mg3, _col_sb, _col_info, _mg4 = st.columns([0.4, 1, 3, 0.4])
            with _col_sb:
                _btn_subir = st.button("&#128228; Subir versi&#243;n", key="btn_subir_excel",
                                       use_container_width=True, type="primary")
            with _col_info:
                st.info(f"&#128193; **{_excel_file.name}** — versi&#243;n: **{_version_nombre}**")

            if _btn_subir:
                with st.spinner("&#9203; Subiendo archivo a Supabase..."):
                    try:
                        import datetime as _dt
                        try:
                            import pytz as _pytz
                            _tz_cl = _pytz.timezone("America/Santiago")
                        except ImportError:
                            from datetime import timezone, timedelta
                            _tz_cl = timezone(timedelta(hours=-3))
                        _ts = _dt.datetime.now(_tz_cl).strftime("%Y%m%d_%H%M%S")
                        _nombre_archivo = f"cotizador_{_ts}.xlsx"
                        _excel_bytes = _excel_file.read()
                        supabase.storage.from_("config").upload(
                            path=_nombre_archivo, file=_excel_bytes,
                            file_options={"content-type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                        )
                        _url_publica = supabase.storage.from_("config").get_public_url(_nombre_archivo)
                        supa_admin.table("excel_versiones").insert({
                            "version_nombre": _version_nombre,
                            "archivo_url": _url_publica,
                            "archivo_nombre": _nombre_archivo,
                            "activa": False,
                            "subida_por": st.session_state.get("auth_nombre", "admin"),
                        }).execute()
                        st.session_state.excel_upload_key += 1
                        st.success(f"&#9989; Versi&#243;n **{_version_nombre}** subida correctamente.")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"&#10060; Error al subir: {_e}")
        elif _excel_file and not _version_nombre:
            _mg5, _col_w, _mg6 = st.columns([0.4, 5, 0.4])
            with _col_w:
                st.warning("&#9888;&#65039; Escribe un nombre para identificar esta versi&#243;n.")

        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)

    # ── Lista de versiones ──
    st.markdown('<div class="ind-titulo">&#128203; Versiones disponibles</div>', unsafe_allow_html=True)
    try:
        _versiones = supa_admin.table("excel_versiones").select("*").order("fecha_subida", desc=True).execute().data or []
    except Exception:
        _versiones = []

    if not _versiones:
        st.info("&#128235; No hay versiones subidas a&#250;n. Sube el cotizador.xlsx para comenzar.")
    else:
        for _v in _versiones:
            _es_activa = _v.get("activa", False)
            try:
                import pytz as _pytz_v
                from datetime import datetime as _dtv
                _tz_cl_v = _pytz_v.timezone("America/Santiago")
                _dtobj = _dtv.fromisoformat(str(_v.get("fecha_subida", "")).replace("Z", "+00:00"))
                _fecha = _dtobj.astimezone(_tz_cl_v).strftime("%d/%m/%Y %H:%M")
            except Exception:
                _fecha = str(_v.get("fecha_subida", ""))[:16].replace("T", " ")

            _cv1, _cv2, _cv3, _cv4 = st.columns([3, 2.5, 1.5, 0.6])

            with _cv1:
                if _es_activa:
                    st.markdown(
                        f'<div class="ver-activa">'
                        f'<div class="ver-nombre-activa">&#128994; {_v["version_nombre"]}<span class="ver-badge">activa</span></div>'
                        f'<div class="ver-meta">&#128197; {_fecha} &nbsp;&middot;&nbsp; &#128100; {_v.get("subida_por","admin")}</div>'
                        f'<div class="ver-archivo">&#128193; {_v.get("archivo_nombre","")}</div>'
                        f'</div>', unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="ver-row">'
                        f'<div class="ver-nombre">&#9711; {_v["version_nombre"]}</div>'
                        f'<div class="ver-meta">&#128197; {_fecha} &nbsp;&middot;&nbsp; &#128100; {_v.get("subida_por","admin")}</div>'
                        f'<div class="ver-archivo">&#128193; {_v.get("archivo_nombre","")}</div>'
                        f'</div>', unsafe_allow_html=True)

            with _cv2:
                st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)

            with _cv3:
                st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                if not _es_activa:
                    if st.button("&#9889; Activar", key=f"btn_act_{_v['id']}",
                                 use_container_width=True, type="primary"):
                        with st.spinner("Activando..."):
                            try:
                                supa_admin.table("excel_versiones").update({"activa": False}).neq("id", "00000000-0000-0000-0000-000000000000").execute()
                                supa_admin.table("excel_versiones").update({"activa": True}).eq("id", _v["id"]).execute()
                                # Limpiar cachés si están disponibles
                                for _fn in (get_excel_bytes_activo, leer_hoja_excel, leer_bd_total):
                                    if hasattr(_fn, 'clear'):
                                        _fn.clear()
                                st.session_state.pop("excel_bytes_cache", None)
                                st.rerun()
                            except Exception as _e:
                                st.error(f"&#10060; {_e}")
                else:
                    st.markdown(
                        '<div style="background:#10b981;color:white;padding:8px 0;border-radius:8px;'
                        'text-align:center;font-size:12px;font-weight:700;">&#128994; ACTIVA</div>',
                        unsafe_allow_html=True)

            with _cv4:
                st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)
                if not _es_activa:
                    if st.button("&#128465;&#65039;", key=f"btn_del_{_v['id']}", help="Eliminar esta versi&#243;n"):
                        try:
                            supabase.storage.from_("config").remove([_v.get("archivo_nombre", "")])
                            supa_admin.table("excel_versiones").delete().eq("id", _v["id"]).execute()
                            st.rerun()
                        except Exception as _e:
                            st.error(f"&#10060; {_e}")

    # ── Vista previa del Excel activo ──
    st.markdown('<div class="ind-titulo">&#128065; Vista previa del Excel activo</div>', unsafe_allow_html=True)
    with st.container(border=True):
        _prev_activa = next((_v for _v in _versiones if _v.get("activa")), None) if _versiones else None
        if _prev_activa:
            try:
                import pandas as _pd_prev
                _prev_src = _get_excel_bytes_activo()
                if _prev_src and hasattr(_prev_src, "read"):
                    _xls = _pd_prev.ExcelFile(_prev_src)
                    _hojas_disp = _xls.sheet_names
                    _col_sel, _col_info = st.columns([2, 3])
                    with _col_sel:
                        _hoja_sel = st.selectbox("Hoja a previsualizar", options=_hojas_disp,
                                                  key="prev_hoja_sel", label_visibility="collapsed")
                    with _col_info:
                        st.caption(f"&#128202; **{len(_hojas_disp)} hojas** en la versi&#243;n activa &middot; **{_prev_activa['version_nombre']}**")
                    if _hoja_sel:
                        _prev_src.seek(0)
                        _df_prev = _pd_prev.read_excel(_prev_src, sheet_name=_hoja_sel, header=None)
                        _df_prev = _df_prev.dropna(how='all').fillna('')
                        _df_str = _df_prev.astype(str).replace('nan', '').replace('0.0', '')
                        _altura = min(600, max(300, len(_df_str) * 35 + 50))
                        st.dataframe(_df_str, use_container_width=True, hide_index=True, height=_altura)
                        st.caption(f"&#128203; {len(_df_prev)} filas &middot; {len(_df_prev.columns)} columnas en esta hoja")
                else:
                    st.info("No se pudo cargar el archivo Excel activo.", icon="&#9888;&#65039;")
            except Exception as _pe:
                st.error(f"Error al previsualizar: {_pe}")
        else:
            st.info("Activa una versi&#243;n para poder previsualizarla.", icon="&#128193;")

    # ── Exportar CSV ──
    st.markdown('<div class="ind-titulo">&#128230; Exportar datos</div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.caption("Descarga todas las cotizaciones del sistema en formato CSV para respaldo o an&#225;lisis externo.")
        _col_csv_btn, _col_csv_info = st.columns([1, 3])
        with _col_csv_btn:
            if st.button("&#128230; Generar CSV", key="btn_generar_csv", use_container_width=True, type="primary"):
                st.session_state._csv_listo = _exportar_csv_completo()
        with _col_csv_info:
            if st.session_state.get('_csv_listo'):
                from datetime import datetime as _dt_csv
                try:
                    import pytz as _pytz_csv
                    _tz_csv = _pytz_csv.timezone("America/Santiago")
                except ImportError:
                    from datetime import timezone, timedelta
                    _tz_csv = timezone(timedelta(hours=-3))
                _fname = f"cotizaciones_backup_{_dt_csv.now(_tz_csv).strftime('%Y%m%d_%H%M')}.csv"
                st.download_button(
                    label="&#11015;&#65039; Descargar CSV",
                    data=st.session_state._csv_listo,
                    file_name=_fname, mime="text/csv",
                    use_container_width=True, key="btn_export_csv"
                )
            else:
                st.info("Haz clic en **Generar CSV** para preparar el archivo.", icon="&#8505;&#65039;")

    # ── Barra de estado ──
    _activa_info = next((_v for _v in _versiones if _v.get("activa")), None) if _versiones else None
    if _activa_info:
        try:
            import pytz as _pytz_fa
            from datetime import datetime as _dtfa
            _raw_fa = str(_activa_info.get("fecha_subida", ""))
            _dtfa_obj = _dtfa.fromisoformat(_raw_fa.replace("Z", "+00:00"))
            _fa = _dtfa_obj.astimezone(_pytz_fa.timezone("America/Santiago")).strftime("%d/%m/%Y %H:%M")
        except Exception:
            _fa = str(_activa_info.get("fecha_subida", ""))[:16].replace("T", " ")
        st.markdown(
            f'<div style="background:linear-gradient(90deg,rgba(16,185,129,0.12),rgba(16,185,129,0.03));'
            f'border:1px solid #10b981;border-radius:10px;padding:14px 20px;margin-top:12px;'
            f'display:flex;align-items:center;gap:12px;">'
            f'<span style="font-size:1.4rem">&#128994;</span>'
            f'<div><span style="color:#065f46;font-weight:700;">Sistema usando versi&#243;n activa:</span> '
            f'<strong style="color:#059669;">{_activa_info["version_nombre"]}</strong>'
            f'<span style="color:#6b7280;font-size:0.8rem;margin-left:10px;">subida el {_fa}</span></div>'
            f'</div>',
            unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="background:rgba(245,158,11,0.08);border:1px solid #f59e0b;'
            'border-radius:10px;padding:14px 20px;margin-top:12px;">'
            '&#9888;&#65039; <strong>Sin versi&#243;n activa</strong> — el sistema usa el archivo local '
            '<code>cotizador.xlsx</code> de GitHub.</div>',
            unsafe_allow_html=True)


def render_tab_3d_visor(supabase=None, supa_url='', anthropic_client=None, **deps):
    """Visor 3D Beta — genera modelo 3D de container desde plano con Claude Vision."""
    import streamlit.components.v1 as _components

    st.markdown("""
    <style>
    .hdr-3d {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 60%, #2d1b69 100%);
        border-radius: 20px; padding: 28px 32px; margin-bottom: 20px;
        display: flex; align-items: center; gap: 16px;
        box-shadow: 0 8px 32px rgba(15,23,42,0.4);
    }
    </style>
    <div class="hdr-3d">
      <span style="font-size:2.6rem;line-height:1;flex-shrink:0;">&#127981;</span>
      <div style="margin-left:16px;">
        <div style="font-family:Montserrat,sans-serif;font-weight:900;font-size:1.4rem;letter-spacing:0.05em;text-transform:uppercase;color:white;line-height:1.1;">Visor 3D Beta</div>
        <div style="font-family:Montserrat,sans-serif;font-weight:300;font-size:0.88rem;color:rgba(255,255,255,0.65);margin-top:2px;line-height:1.2;">Genera un modelo 3D del container desde el plano de planta con Claude Vision.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if anthropic_client is None:
        st.info("&#128274; El visor 3D requiere configuraci&#243;n de Anthropic API. Contacta al administrador.")
        return

    st.markdown("**Sube un plano o ingresa su URL para generar el modelo 3D:**")

    _col_v1, _col_v2 = st.columns([2, 3])
    with _col_v1:
        _plano_file_3d = st.file_uploader("Subir plano", type=["pdf", "png", "jpg", "jpeg"],
                                          key="visor3d_file", label_visibility="collapsed")
    with _col_v2:
        _plano_url_3d = st.text_input("URL del plano", placeholder="https://...",
                                      key="visor3d_url", label_visibility="collapsed")

    if st.button("&#127981; Generar modelo 3D", key="visor3d_generar", type="primary"):
        st.info("&#9203; Analizando plano con Claude Vision...")
        _cache_key = f"layout_3d_{_plano_url_3d or 'file'}"

        if _cache_key in st.session_state:
            _layout_3d = st.session_state[_cache_key]
        else:
            try:
                import base64 as _b64_3d
                import json as _json_3d

                if _plano_file_3d:
                    _img_bytes = _plano_file_3d.read()
                    _img_b64   = _b64_3d.b64encode(_img_bytes).decode()
                    _media_type = _plano_file_3d.type or "image/png"
                    _content_img = [
                        {"type": "image", "source": {"type": "base64", "media_type": _media_type, "data": _img_b64}},
                        {"type": "text", "text": "Analiza este plano de planta de container y devuelve JSON con: width (metros), depth (metros), wallHeight (metros, default 2.8), y walls (array con {side:'front'|'back'|'left'|'right', openings:[{type:'door'|'window', x:float, y:float, w:float, h:float}]})."}
                    ]
                elif _plano_url_3d:
                    _content_img = [
                        {"type": "image", "source": {"type": "url", "url": _plano_url_3d}},
                        {"type": "text", "text": "Analiza este plano de planta de container y devuelve JSON con: width (metros), depth (metros), wallHeight (metros, default 2.8), y walls (array con {side:'front'|'back'|'left'|'right', openings:[{type:'door'|'window', x:float, y:float, w:float, h:float}]})."}
                    ]
                else:
                    st.warning("Sube un plano o ingresa su URL primero.")
                    return

                _resp_3d = anthropic_client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": _content_img}]
                )
                _text_3d = _resp_3d.content[0].text
                _start = _text_3d.find('{')
                _end   = _text_3d.rfind('}') + 1
                _layout_3d = _json_3d.loads(_text_3d[_start:_end]) if _start >= 0 else {
                    "width": 6.0, "depth": 3.0, "wallHeight": 2.8, "walls": []
                }
                st.session_state[_cache_key] = _layout_3d
            except Exception as _e3d:
                st.error(f"Error analizando plano: {_e3d}")
                return

        # Renderizar el modelo 3D con Three.js
        _W = float(_layout_3d.get('width', 6.0))
        _D = float(_layout_3d.get('depth', 3.0))
        _H = float(_layout_3d.get('wallHeight', 2.8))
        _walls_json = str(_layout_3d.get('walls', [])).replace("'", '"')

        _visor_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>body{{margin:0;overflow:hidden;background:#1a1a2e;}}canvas{{display:block;}}</style>
</head>
<body>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
var W={_W},D={_D},H={_H};
var scene=new THREE.Scene();
var camera=new THREE.PerspectiveCamera(60,window.innerWidth/window.innerHeight,0.1,100);
camera.position.set(W*1.5,H*1.2,D*2);camera.lookAt(0,H*0.5,0);
var renderer=new THREE.WebGLRenderer({{antialias:true}});
renderer.setSize(window.innerWidth,window.innerHeight);
renderer.shadowMap.enabled=true;
document.body.appendChild(renderer.domElement);

var mWall=new THREE.MeshLambertMaterial({{color:0x8fbcbb}});
var mRoof=new THREE.MeshLambertMaterial({{color:0x5e81ac}});
var mRib =new THREE.MeshLambertMaterial({{color:0x2e3440}});
var mGlass=new THREE.MeshLambertMaterial({{color:0x88c0d0,transparent:true,opacity:0.4}});
var mDoor =new THREE.MeshLambertMaterial({{color:0xd08770}});
var mFloor=new THREE.MeshLambertMaterial({{color:0x3b4252}});

// Piso
var floor=new THREE.Mesh(new THREE.BoxGeometry(W,0.05,D),mFloor);
floor.position.y=-0.025;floor.receiveShadow=true;scene.add(floor);

// Paredes
var th=0.08;
function makeWall(px,pz,rotY,wallW,openings){{
  var grp=new THREE.Group();grp.position.set(px,H/2,pz);grp.rotation.y=rotY;
  var wall=new THREE.Mesh(new THREE.BoxGeometry(wallW,H,th),mWall);
  wall.castShadow=true;wall.receiveShadow=true;grp.add(wall);
  scene.add(grp);
}}
makeWall(0,D/2,0,W,[]);
makeWall(0,-D/2,0,W,[]);
makeWall(-W/2,0,Math.PI/2,D,[]);
makeWall(W/2,0,Math.PI/2,D,[]);

// Techo
var roof=new THREE.Mesh(new THREE.BoxGeometry(W+th*2,0.1,D+th*2),mRoof);
roof.position.y=H+0.05;scene.add(roof);

// Iluminación
var ambient=new THREE.AmbientLight(0xffffff,0.6);scene.add(ambient);
var sun=new THREE.DirectionalLight(0xffffff,0.8);
sun.position.set(W*2,H*3,D*2);sun.castShadow=true;scene.add(sun);

// Grilla de suelo
var grid=new THREE.GridHelper(20,20,0x444444,0x444444);
grid.position.y=-0.01;scene.add(grid);

// Rotación automática suave
var angle=0;
function animate(){{
  requestAnimationFrame(animate);
  angle+=0.005;
  camera.position.x=Math.cos(angle)*W*2.2;
  camera.position.z=Math.sin(angle)*D*2.2;
  camera.lookAt(0,H*0.4,0);
  renderer.render(scene,camera);
}}
animate();
window.addEventListener('resize',function(){{
  camera.aspect=window.innerWidth/window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth,window.innerHeight);
}});
</script>
</body></html>"""

        _components.html(_visor_html, height=620, scrolling=False)
        st.caption(f"&#9888;&#65039; Beta &mdash; Dimensiones detectadas: {_W:.1f}m &#215; {_D:.1f}m &#215; {_H:.1f}m altura")

        _col_dbg1, _col_dbg2 = st.columns([3, 1])
        with _col_dbg2:
            if st.button("&#128260; Regenerar", key="btn_regen_3d", help="Forzar nuevo an&#225;lisis del plano"):
                st.session_state.pop(_cache_key, None)
                st.rerun()
        with _col_dbg1:
            with st.expander("&#128269; Ver JSON detectado por Claude Vision"):
                st.json(_layout_3d)
    else:
        st.info("&#9757; Sube un plano y presiona **Generar modelo 3D** para comenzar.")
