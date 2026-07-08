"""
Tab FORMULARIO CLIENTE — Config catálogo, preguntas, progreso de respuestas.
Código fuente original: app.py líneas 19318-19456
"""
import html as _html
import streamlit as st
import streamlit.components.v1 as _st_components
import pandas as pd
from collections import defaultdict
from views.layout import render_page_header
from utils.formulario import (
    fetch_catalogo_materiales,
    fetch_formulario_config,
    build_catalogo_html,
    build_config_preguntas_html,
)
from utils.cat_icons import cat_icon_svg
from utils.avatars import fetch_foto_map, avatar_html
from config.supabase import supabase_admin as _supa_admin


# Tipografía de títulos de sección (unificada con el resto del sistema).
_SEC_TITLE_STYLE = ("font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;"
                    "font-weight:700;text-transform:uppercase;letter-spacing:0.05em;"
                    "line-height:1.6;display:flex;align-items:center;margin:8px 0 10px;")


def _fic(path, size=16, color="#0f172a", sw=2, mr=0, valign=-3):
    """SVG inline (estilo Lucide) para títulos/íconos en HTML del tab."""
    _s = f"vertical-align:{valign}px;flex-shrink:0;"
    if mr:
        _s += f"margin-right:{mr}px;"
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="{_s}">{path}</svg>')


_IC_CLIP   = ('<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>'
              '<rect width="8" height="4" x="8" y="2" rx="1"/><path d="m9 14 2 2 4-4"/>')
_IC_CHECK  = '<path d="M20 6 9 17l-5-5"/>'
_IC_CIRCLE = '<circle cx="12" cy="12" r="9"/>'
_IC_BARS   = ('<line x1="12" x2="12" y1="20" y2="10"/><line x1="18" x2="18" y1="20" y2="4"/>'
              '<line x1="6" x2="6" y1="20" y2="16"/>')
_IC_TAG    = ('<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414'
              'l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/>'
              '<circle cx="7.5" cy="7.5" r="1.5"/>')
_IC_USER   = ('<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>')
_IC_TYPE   = ('<polyline points="4 7 4 4 20 4 20 7"/><line x1="9" x2="15" y1="20" y2="20"/>'
              '<line x1="12" x2="12" y1="4" y2="20"/>')
_IC_BILL   = ('<rect width="20" height="12" x="2" y="6" rx="2"/><circle cx="12" cy="12" r="2"/>'
              '<path d="M6 12h.01M18 12h.01"/>')

# CSS del rediseño de PROGRESO CLIENTES (tarjetas con imagen/color seleccionado).
_PROGRESO_CSS = """
<style>
.ec-pg-summary{background:linear-gradient(135deg,#0f3460,#1a5276);border-radius:16px;
  padding:18px 22px;margin:2px 0 18px;box-shadow:0 10px 28px rgba(15,52,96,.18);}
.ec-pg-head{display:flex;align-items:center;gap:15px;margin-bottom:14px;}
.ec-pg-meta{flex:1 1 auto;min-width:0;}
.ec-pg-proj{font-family:'Montserrat',sans-serif;font-size:0.92rem;font-weight:800;color:#fff;
  letter-spacing:.02em;line-height:1.25;margin-bottom:3px;}
.ec-pg-by{font-family:'Poppins',sans-serif;font-size:.8rem;color:rgba(255,255,255,.86);line-height:1.45;}
.ec-pg-by b{color:#fff;font-weight:700;}
.ec-pg-monto{font-family:'Poppins',sans-serif;font-size:.78rem;color:rgba(255,255,255,.86);margin-top:5px;
  display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.12);
  border:1px solid rgba(255,255,255,.2);border-radius:99px;padding:3px 11px;}
.ec-pg-monto b{color:#fff;font-weight:800;font-family:'Montserrat',sans-serif;}
.ec-pg-pctwrap{flex:0 0 auto;text-align:right;}
.ec-pg-pct{font-family:'Montserrat',sans-serif;font-size:1.7rem;font-weight:900;color:#fff;line-height:1;}
.ec-pg-sum-lbl{font-family:'Poppins',sans-serif;font-size:.72rem;font-weight:600;
  color:rgba(255,255,255,.78);margin-top:7px;}
.ec-pg-bar{background:rgba(255,255,255,.18);border-radius:99px;height:9px;overflow:hidden;}
.ec-pg-fill{height:9px;border-radius:99px;background:linear-gradient(90deg,#48cae4,#90e0ef);
  box-shadow:0 0 12px rgba(144,224,239,.6);transition:width .5s ease;}
.ec-pg-catttl{font-family:'Montserrat',sans-serif;color:#0f172a;font-size:0.88rem;font-weight:700;
  text-transform:uppercase;letter-spacing:0.05em;line-height:1.6;display:flex;align-items:center;
  gap:8px;margin:18px 0 11px;}
.ec-pg-grid{display:flex;flex-wrap:wrap;gap:14px;margin:0 0 6px;}
.ec-pg-card{width:172px;background:#fff;border:1px solid #eef2f7;border-radius:16px;overflow:hidden;
  box-shadow:0 4px 16px rgba(15,52,96,.06);transition:transform .16s,box-shadow .16s;}
.ec-pg-card:hover{transform:translateY(-3px);box-shadow:0 14px 30px rgba(15,52,96,.13);}
.ec-pg-card.pend{border-style:dashed;border-color:#e2e8f0;box-shadow:none;background:#fafbfc;}
.ec-pg-visual{height:120px;display:flex;align-items:center;justify-content:center;background:#eef2f7;
  position:relative;overflow:hidden;}
.ec-pg-visual img{width:100%;height:100%;object-fit:cover;display:block;}
.ec-pg-swatch{width:100%;height:100%;}
.ec-pg-textvis{background:linear-gradient(135deg,#f1f5f9,#e2e8f0);}
.ec-pg-check{position:absolute;top:8px;right:8px;width:25px;height:25px;border-radius:50%;
  background:#16a34a;display:flex;align-items:center;justify-content:center;
  box-shadow:0 3px 9px rgba(0,0,0,.2);border:2px solid #fff;}
.ec-pg-body{padding:11px 13px 13px;}
.ec-pg-grp{font-family:'Montserrat',sans-serif;font-size:0.62rem;font-weight:700;letter-spacing:0.05em;
  text-transform:uppercase;color:#94a3b8;line-height:1.4;margin-bottom:3px;}
.ec-pg-val{font-family:'Poppins',sans-serif;font-size:0.86rem;font-weight:600;color:#0f3460;
  line-height:1.3;word-break:break-word;}
.ec-pg-sub{font-family:'Poppins',sans-serif;font-size:0.66rem;font-weight:600;color:#94a3b8;
  margin-top:2px;text-transform:uppercase;letter-spacing:.04em;}
</style>
"""


def _pg_card(grp_title, sel_val, sel_item):
    """Tarjeta de selección del cliente: muestra la imagen/color elegido o el texto.
    sel_val=None ⇒ pendiente."""
    grp = _html.escape(grp_title or '')
    if not sel_val:
        return ('<div class="ec-pg-card pend">'
                '<div class="ec-pg-visual ec-pg-textvis">'
                + _fic(_IC_CIRCLE, 30, color="#cbd5e1", sw=1.6, valign=0) + '</div>'
                '<div class="ec-pg-body"><div class="ec-pg-grp">' + grp + '</div>'
                '<div class="ec-pg-val" style="color:#94a3b8;">Pendiente</div></div></div>')

    val = _html.escape(str(sel_val))
    it = sel_item or {}
    tipo = (it.get('tipo') or '').strip()
    url = (it.get('imagen_url') or '').strip()
    hexc = (it.get('hex') or '').strip()
    sub = ''
    if tipo == 'imagen' and url:
        visual = '<img src="' + _html.escape(url, quote=True) + '" alt="' + val + '" loading="lazy">'
    elif tipo == 'color' and hexc:
        visual = '<div class="ec-pg-swatch" style="background:' + _html.escape(hexc, quote=True) + ';"></div>'
        sub = '<div class="ec-pg-sub">' + _html.escape(hexc) + '</div>'
    else:
        # si_no / select / texto libre
        _vl = (val or '').lower()
        _ic = (_IC_CHECK if _vl in ('sí', 'si', 'yes') else
               (_IC_TYPE if tipo == 'select' else _IC_TAG))
        visual = ('<div style="display:flex;align-items:center;justify-content:center;height:100%;'
                  'width:100%;background:linear-gradient(135deg,#f1f5f9,#e2e8f0);">'
                  + _fic(_ic, 34, color="#0f3460", sw=1.7, valign=0) + '</div>')
    check = '<div class="ec-pg-check">' + _fic(_IC_CHECK, 13, color="#fff", sw=3, valign=0) + '</div>'
    return ('<div class="ec-pg-card"><div class="ec-pg-visual">' + visual + check + '</div>'
            '<div class="ec-pg-body"><div class="ec-pg-grp">' + grp + '</div>'
            '<div class="ec-pg-val">' + val + '</div>' + sub + '</div></div>')

# JS de la tabla HTML de adjudicados (CONFIGURAR PREGUNTAS): click-to-copy en las
# celdas .cp-cell (N° EP / RUT) y "Configurar" que carga ese EP vía query param
# _cfg_ep + click al botón nativo oculto (sin recargar la página). Corre en un
# components.html(height=0) y opera sobre window.parent.document; re-bindea cada run.
_ADJ_TABLE_JS = """
<script>
(function(){
  var D=window.parent.document;
  function flash(el,txt){var o=el.innerHTML,c=el.style.color;el.innerHTML=txt;el.style.color='#16a34a';
    setTimeout(function(){el.innerHTML=o;el.style.color=c;},1100);}
  function copyVal(v,el){
    try{var ta=D.createElement('textarea');ta.value=v;ta.style.cssText='position:fixed;top:-9999px;left:-9999px;';
      D.body.appendChild(ta);ta.focus();ta.select();D.execCommand('copy');ta.remove();}catch(e){}
    try{if(window.parent.navigator.clipboard)window.parent.navigator.clipboard.writeText(v).catch(function(){});}catch(e){}
    flash(el,'\\u2713 copiado');
  }
  function onClick(e){
    var t=e.target;if(!t||!t.closest)return;
    var cp=t.closest('.cp-cell');
    if(cp){var v=cp.getAttribute('data-copy')||'';if(v)copyVal(v,cp);return;}
    var cb=t.closest('.cfg-btn');
    if(cb){var ep=cb.getAttribute('data-ep')||'';
      try{var u=new URL(window.parent.location.href);u.searchParams.set('_cfg_ep',ep);
        window.parent.history.replaceState({},'',u.toString());}catch(e2){}
      var b=D.querySelector('.st-key-_cfg_load_btn button');if(b)b.click();return;}
  }
  if(D.__adjTblH){D.removeEventListener('click',D.__adjTblH);}
  D.__adjTblH=onClick;D.addEventListener('click',onClick);
})();
</script>
"""


def _progreso_empty_ejecutivo(nombre=''):
    """Estado vacío MOTIVADOR para el ejecutivo sin proyectos en progreso."""
    _first = ((nombre or '').split(' ')[0] or '').strip()
    _first = _first[:1].upper() + _first[1:] if _first else ''
    _saludo = f'&iexcl;Vamos, {_html.escape(_first)}! ' if _first else '&iexcl;&Aacute;nimo! '
    _rocket = ('<svg viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" '
               'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
               '<path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/>'
               '<path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/>'
               '<path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/>'
               '<path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5"/></svg>')
    return (
        '<div style="text-align:center;max-width:540px;margin:2.2rem auto;padding:2.3rem 1.9rem;'
        'background:linear-gradient(180deg,#ffffff,#f8fafc);border:1px solid #e6ebf3;border-radius:20px;'
        'box-shadow:0 12px 32px -14px rgba(91,124,250,0.28);">'
        '<div style="width:74px;height:74px;margin:0 auto 1.15rem;border-radius:21px;display:flex;'
        'align-items:center;justify-content:center;color:#fff;'
        'background:linear-gradient(135deg,#5b7cfa,#8aa2ff);'
        'box-shadow:0 14px 28px -8px rgba(91,124,250,0.6);">' + _rocket + '</div>'
        '<div style="font-family:\'Montserrat\',sans-serif;font-weight:700;font-size:1.05rem;'
        'letter-spacing:0.01em;color:#0f172a;line-height:1.35;">'
        + _saludo + 'tu mejor proyecto est&aacute; por venir</div>'
        '<div style="font-family:\'Plus Jakarta Sans\',sans-serif;font-size:0.88rem;color:#64748b;'
        'line-height:1.6;margin-top:0.7rem;">'
        'A&uacute;n no tienes clientes completando su formulario de materiales. '
        'Cada presupuesto que adjudicas es una nueva oportunidad: sigue cotizando con energ&iacute;a y, '
        'cuando tus clientes empiecen a elegir, ver&aacute;s aqu&iacute; su avance en tiempo real.'
        '</div>'
        '</div>'
    )


def render_tab_formulario(supabase, supabase_admin=None, supa_url='', supa_key='', **deps):
    supa_admin = supabase_admin or _supa_admin
    _supa_url = supa_url or deps.get('supa_url', '')
    _supa_key = supa_key or deps.get('supa_key', '')
    _rol = st.session_state.get('rol_usuario', 'ejecutivo')

    render_page_header(
        "formulario",
        "Formulario de Materiales",
        "Configura preguntas por proyecto &middot; Revisa respuestas del cliente",
    )

    if _rol in ('root', 'admin'):
        _ftab_catalogo, _ftab_config, _ftab_progreso = st.tabs([
            ":material/inventory_2: Cat&#225;logo de materiales",
            ":material/quiz: Configurar preguntas",
            ":material/bar_chart: Progreso clientes",
        ])
    else:
        _ftab_catalogo = None
        _ftab_config, _ftab_progreso = st.tabs([
            ":material/quiz: Configurar preguntas",
            ":material/bar_chart: Progreso clientes",
        ])

    # ── TAB CATÁLOGO ──
    if _ftab_catalogo is not None:
        with _ftab_catalogo:
            if _rol not in ('root', 'admin'):
                st.info("Solo administradores pueden gestionar el cat&#225;logo.", icon=":material/lock:")
            else:
                # Botón oculto: el JS del catálogo (dentro del iframe) lo clickea tras
                # una mutación (eliminar/editar/clonar) para forzar un rerun de
                # Streamlit SIN recargar la página. Antes hacía location.reload(), que
                # perdía la sesión (el token ?_sess ya no está en la URL) y obligaba a
                # re-loguear. Al limpiar los caches, "Configurar preguntas" y la página
                # del cliente ven los datos frescos.
                st.markdown(
                    '<style>.st-key-_cat_refresh_btn{position:absolute!important;'
                    'width:1px;height:1px;overflow:hidden;opacity:0;margin:0;padding:0;}</style>',
                    unsafe_allow_html=True)
                if st.button("refrescar catálogo", key="_cat_refresh_btn"):
                    try:
                        fetch_catalogo_materiales.clear()
                        fetch_formulario_config.clear()
                    except Exception:
                        pass
                if 'cat_tipo' not in st.session_state:
                    st.session_state.cat_tipo = 'imagen'
                if 'cat_cantidad' not in st.session_state:
                    st.session_state.cat_cantidad = 4
                _qp_tipo = st.query_params.get('cat_tipo', '')
                _qp_cant = st.query_params.get('cat_cantidad', '')
                if _qp_tipo:
                    st.session_state.cat_tipo = _qp_tipo
                    st.query_params.pop('cat_tipo')
                if _qp_cant:
                    try:
                        st.session_state.cat_cantidad = int(_qp_cant)
                    except Exception:
                        pass
                    st.query_params.pop('cat_cantidad')
                try:
                    _cat_all = supa_admin.table('catalogo_materiales').select('*')\
                        .eq('activo', True).order('categoria').order('orden_grupo')\
                        .order('titulo_grupo').order('nombre').execute().data or []
                    for _ci in _cat_all:
                        if not _ci.get('titulo_grupo'):
                            _ci['titulo_grupo'] = '__sin_grupo__'
                except Exception:
                    _cat_all = []
                _cat_html = build_catalogo_html(
                    _cat_all, _supa_url, _supa_key,
                    st.session_state.cat_tipo, st.session_state.cat_cantidad
                )
                _cat_height = max(700, len(_cat_all) * 20 + 600)
                _st_components.html(_cat_html, height=_cat_height, scrolling=True)

    # ── TAB CONFIGURAR ──
    with _ftab_config:
        if _rol not in ('root', 'admin', 'ejecutivo'):
            st.info("No tienes permisos para configurar formularios.", icon=":material/lock:")
        else:
            # ── Tabla de presupuestos ADJUDICADOS con estado de preguntas ──
            # Título (izq) + link "Abrir formulario cliente" en nueva pestaña (der).
            # La URL se arma desde el parent (origin+pathname+?cliente=1) para que
            # funcione tanto en beta como en producción sin hardcodear.
            _cli_link_html = (
                '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
                '*{box-sizing:border-box;}body{margin:0;font-family:"Montserrat","Segoe UI",sans-serif;}'
                'a.cli{display:flex;align-items:center;justify-content:center;gap:8px;text-decoration:none;'
                'background:linear-gradient(135deg,#16a34a,#15803d);color:#fff;font-weight:800;font-size:12.5px;'
                'letter-spacing:0.02em;padding:10px 14px;border-radius:10px;box-shadow:0 4px 12px rgba(22,163,74,0.30);'
                'transition:transform .12s,box-shadow .15s;}'
                'a.cli:hover{transform:translateY(-1px);box-shadow:0 6px 16px rgba(22,163,74,0.42);}'
                'a.cli svg{width:15px;height:15px;flex-shrink:0;}'
                '</style></head><body>'
                '<a id="cli" class="cli" target="_blank" rel="noopener" title="Abre la p&#225;gina del cliente en una pesta&#241;a nueva">'
                '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
                'stroke-linecap="round" stroke-linejoin="round">'
                '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>'
                'Abrir formulario cliente</a>'
                '<script>(function(){var a=document.getElementById("cli");try{var L=window.parent.location;'
                'a.href=L.origin+L.pathname+"?cliente=1";}catch(e){a.href="/?cliente=1";}})();</script>'
                '</body></html>'
            )
            _ct1, _ct2 = st.columns([3, 1.5], vertical_alignment="center")
            with _ct1:
                st.markdown(
                    f'<div style="{_SEC_TITLE_STYLE}">{_fic(_IC_CLIP, 17, mr=8)}Presupuestos adjudicados</div>',
                    unsafe_allow_html=True)
            with _ct2:
                _st_components.html(_cli_link_html, height=46)
            try:
                _adj_q = supa_admin.table('cotizaciones').select(
                    'numero,cliente_nombre,cliente_rut,asesor_nombre,fecha_adjudicacion,estado,asesor_email'
                ).eq('estado', 'ADJUDICADO')
                # Ejecutivo: solo SUS adjudicados (root/admin ven todos). Mismo
                # criterio que el resto del sistema (filtrar por asesor_email).
                if _rol == 'ejecutivo':
                    _adj_email = (st.session_state.get('auth_email', '') or '').strip()
                    if _adj_email:
                        _adj_q = _adj_q.ilike('asesor_email', _adj_email)
                    else:
                        _adj_q = _adj_q.eq('numero', '__none__')  # sin email → nada
                _adj = _adj_q.order('fecha_adjudicacion', desc=True).execute().data or []
            except Exception:
                _adj = []
            try:
                _fc_rows = supa_admin.table('formulario_config').select(
                    'cotizacion_numero,item_ids'
                ).execute().data or []
            except Exception:
                _fc_rows = []
            _fc_nums = set(x['cotizacion_numero'] for x in _fc_rows)

            # % de avance del formulario por EP = grupos respondidos por el cliente /
            # grupos RENDERABLES (item_ids que existen en el catálogo). Mismo criterio
            # que la pestaña PROGRESO CLIENTES y que el render del formulario.
            try:
                _resp_rows = supa_admin.table('formulario_respuestas').select(
                    'cotizacion_numero,item_id,pregunta_id'
                ).execute().data or []
            except Exception:
                _resp_rows = []
            try:
                _cat_ids_av = set(str(c['id']) for c in (fetch_catalogo_materiales(
                    _cache_buster=st.query_params.get('_cat_ts', '')) or []))
            except Exception:
                _cat_ids_av = set()
            _resp_by_ep_av = defaultdict(set)
            for _rr in _resp_rows:
                _kk = _rr.get('item_id') or _rr.get('pregunta_id')
                if _kk:
                    _resp_by_ep_av[str(_rr['cotizacion_numero'])].add(str(_kk))
            _cfg_groups_av = defaultdict(list)
            for _cr in _fc_rows:
                _cfg_groups_av[str(_cr['cotizacion_numero'])].append(
                    [str(x) for x in (_cr.get('item_ids') or [])])
            _pct_by_ep = {}
            for _epk, _grps in _cfg_groups_av.items():
                _rend = [g for g in _grps if any(i in _cat_ids_av for i in g)]
                if not _rend:
                    continue
                _ansset = _resp_by_ep_av.get(_epk, set())
                _donen = sum(1 for g in _rend if any(i in _ansset for i in g))
                _pct_by_ep[_epk] = int(_donen / len(_rend) * 100)
            if not _adj:
                st.info("A&#250;n no tienes presupuestos adjudicados." if _rol == 'ejecutivo'
                        else "A&#250;n no hay presupuestos adjudicados.")
            else:
                import html as _h
                _n_si = sum(1 for r in _adj if r.get('numero') in _fc_nums)
                st.caption(
                    f"{len(_adj)} adjudicados · {_n_si} con preguntas configuradas · "
                    f"{len(_adj) - _n_si} pendientes. Click en el N&#176; EP o el RUT para copiarlos; "
                    f'"Configurar" para editar las preguntas de ese EP.'
                )
                _pill_si = ('background:#dcfce7;color:#15803d;border:1px solid #86efac;'
                            'border-radius:99px;padding:2px 10px;font-size:0.72rem;font-weight:800;')
                _pill_no = ('background:#fee2e2;color:#dc2626;border:1px solid #fca5a5;'
                            'border-radius:99px;padding:2px 10px;font-size:0.72rem;font-weight:800;')
                # Badge de estado ADJUDICADO (mismo estilo que la tabla de cotizaciones).
                _estado_badge = ('<span style="background-color:#2563eb;color:white;padding:3px 11px;'
                                 'border-radius:20px;font-size:0.68rem;font-weight:700;display:inline-block;'
                                 'border:1px solid #1d4ed8;box-shadow:0 2px 4px rgba(0,0,0,0.1);'
                                 'white-space:nowrap;letter-spacing:0.03em;">ADJUDICADO</span>')
                _rows_html = ''
                for r in _adj:
                    _ep = str(r.get('numero') or '')
                    _rut = str(r.get('cliente_rut') or '').strip()
                    _cli = _h.escape(str(r.get('cliente_nombre') or '—'))
                    _ase = _h.escape(str(r.get('asesor_nombre') or '—'))
                    _preg = (f'<span style="{_pill_si}">S&#205;</span>' if _ep in _fc_nums
                             else f'<span style="{_pill_no}">NO</span>')
                    _p = _pct_by_ep.get(_ep)
                    if _p is None:
                        _avance = '<td class="ctr"><span class="pg-na">&#8212;</span></td>'
                    else:
                        _pcol = ('#16a34a' if _p == 100 else
                                 ('#f97316' if _p >= 50 else ('#2563eb' if _p > 0 else '#94a3b8')))
                        _avance = (
                            '<td class="ctr"><div class="pgcell">'
                            f'<div class="pgbar"><div class="pgfill" style="width:{_p}%;background:{_pcol};"></div></div>'
                            f'<span class="pgtxt" style="color:{_pcol};">{_p}%</span></div></td>'
                        )
                    if _rut:
                        _rut_cell = (f'<td class="cp-cell" data-copy="{_h.escape(_rut, quote=True)}" '
                                     f'title="Click para copiar el RUT">{_h.escape(_rut)} '
                                     f'<span class="cp-ic">&#9112;</span></td>')
                    else:
                        _rut_cell = '<td style="color:#cbd5e1;">&#8212;</td>'
                    _rows_html += (
                        '<tr>'
                        f'{_rut_cell}'
                        f'<td class="cp-cell" data-copy="{_h.escape(_ep, quote=True)}" '
                        f'title="Click para copiar el N&#176; EP">{_h.escape(_ep)} '
                        f'<span class="cp-ic">&#9112;</span></td>'
                        f'<td>{_cli}</td>'
                        f'<td>{_ase}</td>'
                        f'<td class="ctr">{_estado_badge}</td>'
                        f'<td class="ctr">{_preg}</td>'
                        f'{_avance}'
                        f'<td class="ctr"><button class="cfg-btn" data-ep="{_h.escape(_ep, quote=True)}">'
                        'Configurar</button></td>'
                        '</tr>'
                    )
                _table_html = (
                    '<style>'
                    '.st-key-_cfg_load_btn{display:none!important;}'
                    '.ep-tbl-wrap{overflow-x:auto;border:1px solid #e7ebf3;border-radius:12px;'
                    'box-shadow:0 1px 3px rgba(15,23,42,0.05);}'
                    ".ep-tbl{width:100%;border-collapse:collapse;font-family:'Inter','Segoe UI',sans-serif;font-size:0.82rem;}"
                    '.ep-tbl thead th{background:#0f172a;color:#fff;font-family:Montserrat,sans-serif;font-weight:700;'
                    'font-size:0.66rem;text-transform:uppercase;letter-spacing:0.05em;padding:10px 12px;text-align:left;white-space:nowrap;}'
                    '.ep-tbl tbody td{padding:9px 12px;border-bottom:1px solid #eef2f7;color:#0f172a;font-weight:600;vertical-align:middle;}'
                    '.ep-tbl tbody tr:hover{background:#f8fafc;}'
                    '.ep-tbl tbody tr:last-child td{border-bottom:none;}'
                    '.ep-tbl .ctr{text-align:center;}'
                    '.ep-tbl .cp-cell{cursor:pointer;font-weight:800;color:#2563eb;white-space:nowrap;font-variant-numeric:tabular-nums;}'
                    '.ep-tbl .cp-cell:hover{color:#1d4ed8;text-decoration:underline;}'
                    '.ep-tbl .cp-ic{font-size:0.85em;opacity:0.55;}'
                    '.ep-tbl .cfg-btn{background:#eef2ff;color:#4338ca;border:1px solid #c7d2fe;border-radius:7px;'
                    'padding:5px 12px;font-size:0.72rem;font-weight:700;cursor:pointer;font-family:inherit;transition:background .15s;}'
                    '.ep-tbl .cfg-btn:hover{background:#e0e7ff;}'
                    '.ep-tbl .pgcell{display:flex;align-items:center;gap:8px;justify-content:center;}'
                    '.ep-tbl .pgbar{width:64px;height:7px;background:#e8edf3;border-radius:99px;overflow:hidden;flex:0 0 auto;}'
                    '.ep-tbl .pgfill{height:7px;border-radius:99px;transition:width .4s;}'
                    ".ep-tbl .pgtxt{font-weight:800;font-size:0.74rem;font-variant-numeric:tabular-nums;min-width:32px;text-align:left;}"
                    '.ep-tbl .pg-na{color:#cbd5e1;font-weight:700;}'
                    '</style>'
                    '<div class="ep-tbl-wrap"><table class="ep-tbl"><thead><tr>'
                    '<th>RUT cliente</th><th>N&#176; EP</th><th>Cliente</th><th>Asesor</th>'
                    '<th class="ctr">Estado</th><th class="ctr">Preguntas</th>'
                    '<th class="ctr">Avance</th><th class="ctr">Acci&#243;n</th>'
                    '</tr></thead><tbody>' + _rows_html + '</tbody></table></div>'
                )
                st.markdown(_table_html, unsafe_allow_html=True)
                # Botón nativo OCULTO: el JS de la tabla lo clickea para cargar el EP
                # elegido (vía query param _cfg_ep) y configurar sus preguntas, sin
                # recargar la página (mismo patrón que el refresco del catálogo).
                if st.button("cfgload", key="_cfg_load_btn"):
                    _qep = (st.query_params.get('_cfg_ep') or '').strip().upper()
                    if _qep:
                        st.session_state['_form_ep'] = _qep
                    st.rerun()
                _st_components.html(_ADJ_TABLE_JS, height=0)

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            # ── Buscar / cargar EP manualmente ──
            _c1ep, _c2ep = st.columns([3, 1])
            with _c1ep:
                _ep_form_input = st.text_input(
                    "N&#250;mero EP", placeholder="EP-12345", key="form_ep_input"
                )
            with _c2ep:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("Cargar", icon=":material/search:", key="form_cargar_ep", use_container_width=True) and _ep_form_input:
                    st.session_state['_form_ep'] = _ep_form_input.strip().upper()
                    st.rerun()
            _form_ep = st.session_state.get('_form_ep', '')
            if not _form_ep:
                st.info("Ingresa un n&#250;mero EP y haz click en Cargar.")
            else:
                # _cat_ts es el query param que JS setea tras editar el catálogo;
                # cambia el cache key de las funciones @st.cache_data y fuerza re-fetch.
                _cat_ts = st.query_params.get('_cat_ts', '')
                try:
                    _cat_todos = fetch_catalogo_materiales(_cache_buster=_cat_ts)
                except Exception:
                    _cat_todos = []
                try:
                    _cfg_data = fetch_formulario_config(_form_ep, _cache_buster=_cat_ts)
                except Exception:
                    _cfg_data = []
                _cfg_html = build_config_preguntas_html(
                    _cat_todos, _cfg_data, _supa_url, _supa_key, _form_ep
                )
                # Alto inicial aproximado; el JS (fitHeight) lo ajusta al contenido
                # real vía window.frameElement → sin scroll interno.
                _cfg_height = max(600, len(_cat_todos) * 40 + 400)
                _st_components.html(_cfg_html, height=_cfg_height, scrolling=False)

    # ── TAB PROGRESO ──
    with _ftab_progreso:
        st.markdown(_PROGRESO_CSS, unsafe_allow_html=True)
        st.markdown(
            f"<div style='{_SEC_TITLE_STYLE}'>{_fic(_IC_BARS, 17, mr=8)}"
            f"Progreso de formularios por proyecto</div>",
            unsafe_allow_html=True,
        )
        try:
            _cat_ts = st.query_params.get('_cat_ts', '')
            try:
                _cat_all = fetch_catalogo_materiales(_cache_buster=_cat_ts) or []
            except Exception:
                _cat_all = []
            _cat_by_id = {str(_it.get('id')): _it for _it in _cat_all}

            _all_cfg = supa_admin.table('formulario_config').select(
                'cotizacion_numero,categoria,titulo_grupo,item_ids,orden'
            ).execute().data or []
            _all_resps = supa_admin.table('formulario_respuestas').select(
                'cotizacion_numero,item_id,pregunta_id,respuesta'
            ).execute().data or []

            _cfg_by_ep = defaultdict(list)
            for _cc in _all_cfg:
                _cfg_by_ep[_cc['cotizacion_numero']].append(_cc)

            # Datos del proyecto (cliente, asesor, monto) + foto del asesor.
            _eps = list(_cfg_by_ep.keys())
            _coti_by_ep = {}
            try:
                _coti_rows = supa_admin.table('cotizaciones').select(
                    'numero,cliente_nombre,asesor_nombre,asesor_email,total_total'
                ).in_('numero', _eps).execute().data or []
                _coti_by_ep = {str(r.get('numero')): r for r in _coti_rows}
            except Exception:
                _coti_by_ep = {}
            try:
                _foto_map = fetch_foto_map(_supa_url) if _supa_url else {}
            except Exception:
                _foto_map = {}

            _resps_by_ep = defaultdict(dict)
            for _rr in _all_resps:
                _key = _rr.get('item_id') or _rr.get('pregunta_id') or ''
                if _key:
                    _resps_by_ep[str(_rr['cotizacion_numero'])][str(_key)] = _rr['respuesta']

            # Ejecutivo: SOLO los proyectos donde él es el asesor (root/admin ven
            # todos). Mismo criterio que la pestaña CONFIGURAR (asesor_email).
            _prog_items = sorted(_cfg_by_ep.items())
            if _rol == 'ejecutivo':
                _my_email = (st.session_state.get('auth_email', '') or '').strip().lower()
                _prog_items = [
                    (_ep, _cfgs) for (_ep, _cfgs) in _prog_items
                    if (_coti_by_ep.get(str(_ep), {}).get('asesor_email') or '').strip().lower() == _my_email
                ]

            if not _prog_items:
                if _rol == 'ejecutivo':
                    st.markdown(
                        _progreso_empty_ejecutivo(st.session_state.get('auth_nombre', '')),
                        unsafe_allow_html=True)
                else:
                    st.info("No hay formularios configurados a&#250;n.")
            else:
                for _ei, (_fep, _fcfgs) in enumerate(_prog_items):
                    _total = len(_fcfgs)
                    _resp_map = _resps_by_ep.get(str(_fep), {})
                    _done = sum(
                        1 for cfg in _fcfgs
                        if any(_resp_map.get(str(iid)) for iid in (cfg.get('item_ids') or []))
                    )
                    _fpct = int(_done / _total * 100) if _total > 0 else 0

                    # Datos del proyecto
                    _ci = _coti_by_ep.get(str(_fep), {})
                    _cliente = (_ci.get('cliente_nombre') or '').strip() or 'Sin nombre'
                    _asesor = (_ci.get('asesor_nombre') or '').strip() or 'Sin asignar'
                    _ase_email = (_ci.get('asesor_email') or '').strip().lower()
                    _ase_foto = _foto_map.get(_ase_email, '') if _ase_email else ''
                    try:
                        _monto_v = float(_ci.get('total_total') or 0)
                    except (TypeError, ValueError):
                        _monto_v = 0.0
                    _monto = '$' + f'{_monto_v:,.0f}'.replace(',', '.')

                    _lbl_cli = _cliente if _cliente != 'Sin nombre' else _fep
                    with st.expander(f"**{_fep}**  ·  {_lbl_cli}  ·  {_fpct}% completado",
                                     expanded=(_ei == 0)):
                        _monto_html = (
                            f"<div class='ec-pg-monto'>{_fic(_IC_BILL, 13, color='#fff', sw=2, valign=0)}"
                            f"Monto del proyecto <b>{_monto}</b></div>"
                        ) if _monto_v > 0 else ""
                        _html_parts = [
                            "<div class='ec-pg-summary'>"
                            "<div class='ec-pg-head'>"
                            + avatar_html(_ase_foto, _asesor, 58)
                            + "<div class='ec-pg-meta'>"
                            f"<div class='ec-pg-proj'>Proyecto N&deg; {_html.escape(str(_fep))}</div>"
                            f"<div class='ec-pg-by'>Realizado por <b>{_html.escape(_asesor)}</b> "
                            f"&middot; a nombre de <b>{_html.escape(_cliente)}</b></div>"
                            + _monto_html
                            + "</div>"
                            "<div class='ec-pg-pctwrap'>"
                            f"<div class='ec-pg-pct'>{_fpct}%</div>"
                            f"<div class='ec-pg-sum-lbl'>{_done}/{_total} secciones</div>"
                            "</div>"
                            "</div>"
                            f"<div class='ec-pg-bar'><div class='ec-pg-fill' style='width:{_fpct}%;'></div></div>"
                            "</div>"
                        ]

                        _cats_prog = defaultdict(list)
                        for _cfg2 in sorted(_fcfgs, key=lambda x: (x.get('categoria', ''), x.get('orden', 0))):
                            _cats_prog[_cfg2.get('categoria', '')].append(_cfg2)

                        for _cat4, _clist4 in _cats_prog.items():
                            _html_parts.append(
                                "<div class='ec-pg-catttl'>" + cat_icon_svg(_cat4, 17, '#0f3460', 2)
                                + "<span>" + _html.escape(_cat4 or '') + "</span></div>"
                                "<div class='ec-pg-grid'>"
                            )
                            for _cfg4 in _clist4:
                                _tg4 = _cfg4.get('titulo_grupo', '')
                                _ids4 = [str(x) for x in (_cfg4.get('item_ids') or [])]
                                _sel_val, _sel_item = None, None
                                for _iid in _ids4:
                                    _v = _resp_map.get(_iid)
                                    if _v:
                                        _sel_val, _sel_item = _v, _cat_by_id.get(_iid)
                                        break
                                _html_parts.append(_pg_card(_tg4, _sel_val, _sel_item))
                            _html_parts.append("</div>")

                        st.markdown(''.join(_html_parts), unsafe_allow_html=True)
        except Exception as _fe:
            st.error(f"Error cargando progreso: {_fe}")
