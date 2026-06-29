"""
Genera el HTML del formulario de seleccion de materiales para el cliente.
"""
import json

from utils.cat_icons import cat_icon_path


def build_formulario_cliente_html(cat_items, config_data, resps_map, supa_url, supa_key, ep, nombre_cliente, logo_b64='', hero_b64='', asesor_nombre='', asesor_foto=''):
    primer_nombre = nombre_cliente.split()[0].capitalize() if nombre_cliente else 'Cliente'
    # Iniciales del asesor para el avatar de respaldo (cuando no hay foto).
    _ase_partes = [p for p in (asesor_nombre or '').split() if p]
    asesor_ini = ''.join(p[0] for p in _ase_partes[:2]).upper() if _ase_partes else 'EC'
    logo_html = ('<img src="data:image/png;base64,' + logo_b64 + '" style="height:49px;width:auto;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.25));">') if logo_b64 else ''
    _IC_ZOOM = ('<svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" '
                'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
                '<circle cx="11" cy="11" r="7"/><path d="m21 21-3.5-3.5"/></svg>')

    def _svg(p, w=15, h=15, sw=2.2, color='currentColor'):
        return ('<svg viewBox="0 0 24 24" width="' + str(w) + '" height="' + str(h) + '" fill="none" stroke="' + color +
                '" stroke-width="' + str(sw) + '" stroke-linecap="round" stroke-linejoin="round" '
                'style="vertical-align:-2px;flex-shrink:0;">' + p + '</svg>')
    _IC_STAR = '<path d="M12 2.5l2.4 6.1 6.6.4-5.1 4.2 1.7 6.4L12 16.7 6 19.6l1.7-6.4-5.1-4.2 6.6-.4z"/>'
    _IC_HOME = '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'
    _IC_TAG  = '<path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect width="8" height="4" x="8" y="2" rx="1"/>'
    _IC_SAVE = '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>'
    _IC_EXIT = '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>'
    _save_svg = _svg(_IC_SAVE, 16, 16, 2.2, '#ffffff')
    _exit_svg = _svg(_IC_EXIT, 15, 15, 2.2, '#475569')

    # Icono por categoría detectado del título (sin acentos). Mapeo compartido
    # con la pestaña de progreso (utils.cat_icons) para que sean idénticos.
    def _cat_icon(nombre):
        return _svg(cat_icon_path(nombre), 18, 18, 2, '#0f3460')

    items_by_id = {str(it['id']): it for it in cat_items}

    configs_by_cat = {}
    for cfg in sorted(config_data, key=lambda x: (x.get('categoria',''), x.get('orden', 0))):
        cat = cfg.get('categoria','')
        if cat not in configs_by_cat:
            configs_by_cat[cat] = []
        configs_by_cat[cat].append(cfg)

    # Sólo cuentan los grupos RENDERABLES (con al menos un item_id que exista en
    # el catálogo); así el conteo inicial coincide con lo que ve el cliente y con
    # el recompute() del JS (ignora configs huérfanas con item_ids vacío).
    def _grupo_renderable(cfg):
        return any(str(x) in items_by_id for x in (cfg.get('item_ids') or []))
    _render_cfgs = [cfg for cfg in config_data if _grupo_renderable(cfg)]
    total_grupos = len(_render_cfgs)
    resp_grupos  = sum(1 for cfg in _render_cfgs
                       if any(resps_map.get(str(iid)) for iid in (cfg.get('item_ids') or [])))
    pct = int(resp_grupos / total_grupos * 100) if total_grupos > 0 else 0

    body_html   = ''
    # Datos de cada grupo para el lightbox/carrusel del popup (key única por grupo).
    groups_data = {}
    _gk_counter = 0

    for cat, cfgs in configs_by_cat.items():
        # Marcamos dónde empieza la cat-card para poder TRUNCARLA si al final no
        # se renderizó ningún grupo (config huérfana con item_ids vacío / items
        # eliminados del catálogo) → no mostrar categorías sin contenido.
        _cat_start = len(body_html)
        _cat_rendered = 0
        body_html += '<div class="cat-card">'
        body_html += '<div class="cat-card-title">' + _cat_icon(cat) + '<span>' + cat + '</span></div>'

        for ci, cfg in enumerate(cfgs):
            tg          = cfg.get('titulo_grupo','')
            ids         = [str(x) for x in (cfg.get('item_ids') or [])]
            obs         = (cfg.get('observaciones') or '').strip()
            mostrar_obs = cfg.get('mostrar_obs', False)
            if not ids:
                continue

            group_items = [items_by_id[iid] for iid in ids if iid in items_by_id]
            if not group_items:
                continue

            itipo   = group_items[0].get('tipo','imagen')
            answered = any(resps_map.get(iid) for iid in ids)

            if _cat_rendered > 0:
                body_html += '<div class="item-divider"></div>'

            body_html += '<div class="item-section">'
            body_html += '<div class="item-title">'
            body_html += tg
            if answered:
                body_html += '<span class="done-dot"></span>'
            body_html += '</div>'

            if obs and mostrar_obs:
                body_html += '<div class="obs-box">' + obs + '</div>'

            if itipo == 'color':
                _gk = str(_gk_counter); _gk_counter += 1
                gid = 'cg-' + _gk
                groups_data[_gk] = {'cat': cat, 'sub': tg, 'type': 'color',
                    'items': [{'iid': str(it.get('id', '')), 'name': it.get('nombre', ''),
                               'hex': (it.get('hex', '#ccc') or '#ccc')} for it in group_items]}
                body_html += '<div class="carousel-wrap">'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',-1)">&#8249;</button>'
                body_html += '<div class="carousel-inner"><div class="color-row" id="' + gid + '">'
                for i, it in enumerate(group_items):
                    iid = str(it.get('id',''))
                    nm  = it.get('nombre','')
                    hx  = it.get('hex','#ccc') or '#ccc'
                    sel = ' sel' if resps_map.get(iid) == nm else ''
                    body_html += '<div class="c-item' + sel + '" id="ci-' + iid + '" onclick="pick(\'' + iid + '\',\'' + nm.replace("'","") + '\',\'color\')"">'
                    body_html += ('<div class="c-color-block" style="background:' + hx + ';"><span class="c-check">' + _svg('<polyline points="20 6 9 17 4 12"/>', 26, 26, 3) + '</span>'
                                  '<button class="zoom-btn" data-pop-gid="' + _gk + '" data-pop-idx="' + str(i) + '" data-pop-hex="' + hx + '" data-pop-name="' + nm.replace('"', '&quot;') + '" '
                                  'data-pop-iid="' + iid + '" data-pop-type="color" '
                                  'onclick="event.stopPropagation();openP(this)">' + _IC_ZOOM + '</button></div>')
                    body_html += '<div class="c-name">' + nm + '</div>'
                    body_html += '</div>'
                body_html += '</div></div>'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',1)">&#8250;</button>'
                body_html += '</div>'

            elif itipo == 'imagen':
                _gk = str(_gk_counter); _gk_counter += 1
                gid = 'ig-' + _gk
                groups_data[_gk] = {'cat': cat, 'sub': tg, 'type': 'imagen',
                    'items': [{'iid': str(it.get('id', '')), 'name': it.get('nombre', ''),
                               'url': (it.get('imagen_url', '') or '')} for it in group_items]}
                body_html += '<div class="carousel-wrap">'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',-1)">&#8249;</button>'
                body_html += '<div class="carousel-inner"><div class="img-row" id="' + gid + '">'
                for i, it in enumerate(group_items):
                    iid = str(it.get('id',''))
                    nm  = it.get('nombre','')
                    url = it.get('imagen_url','') or ''
                    sel = ' sel' if resps_map.get(iid) == nm else ''
                    nm_attr = nm.replace('"', '&quot;')
                    nm_js = nm.replace("'", "")
                    body_html += '<div class="i-item' + sel + '" id="ii-' + iid + '" onclick="pick(\'' + iid + '\',\'' + nm_js + '\',\'imagen\')">'
                    body_html += '<div class="i-circle">'
                    if url:
                        body_html += '<img src="' + url + '" alt="' + nm_attr + '">'
                    else:
                        body_html += '<div class="i-placeholder">' + _svg('<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.1-3.1a2 2 0 0 0-2.8 0L6 21"/>', 30, 30, 2, '#cbd5e1') + '</div>'
                    body_html += '</div>'
                    body_html += '<div class="i-badge">' + _svg('<polyline points="20 6 9 17 4 12"/>', 13, 13, 3) + '</div>'
                    if url:
                        # Popup se crea dinámicamente en window.parent.document (ver openP en JS)
                        # para que position:fixed se ancle a la viewport real, no al iframe.
                        body_html += ('<button class="zoom-btn" '
                                      'data-pop-gid="' + _gk + '" data-pop-idx="' + str(i) + '" '
                                      'data-pop-url="' + url + '" '
                                      'data-pop-name="' + nm_attr + '" '
                                      'data-pop-iid="' + iid + '" '
                                      'data-pop-type="imagen" '
                                      'onclick="event.stopPropagation();openP(this)">' + _IC_ZOOM + '</button>')
                    body_html += '<div class="i-name">' + nm + '</div>'
                    body_html += '</div>'
                body_html += '</div></div>'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',1)">&#8250;</button>'
                body_html += '</div>'

            elif itipo == 'si_no':
                si_it = next((x for x in group_items if x.get('nombre','').strip() in ('Sí','Si','sí','si','YES','Yes')), group_items[0] if group_items else {})
                no_it = next((x for x in group_items if x.get('nombre','').strip() in ('No','NO','no')), group_items[1] if len(group_items)>1 else {})
                si_id = str(si_it.get('id',''))
                no_id = str(no_it.get('id',''))
                si_sel = ' sel' if resps_map.get(si_id) in ('Sí','Si') else ''
                no_sel = ' sel' if resps_map.get(no_id) == 'No' else ''
                body_html += '<div class="sino-row">'
                body_html += '<button class="sino-btn' + si_sel + '" id="sib-' + si_id + '" onclick="pick(\'' + si_id + '\',\'Sí\',\'si_no\')">' + _svg('<polyline points="20 6 9 17 4 12"/>', 15, 15, 2.6) + ' S&#237;</button>'
                body_html += '<button class="sino-btn' + no_sel + '" id="nob-' + no_id + '" onclick="pick(\'' + no_id + '\',\'No\',\'si_no\')">' + _svg('<path d="M18 6 6 18"/><path d="M6 6l12 12"/>', 15, 15, 2.6) + ' No</button>'
                body_html += '</div>'

            elif itipo == 'select':
                body_html += '<select class="sel-inp" onchange="var p=this.value.split(\'|\');if(p.length==2)pick(p[0],p[1],\'select\')">'
                body_html += '<option value="">-- Selecciona --</option>'
                for it in group_items:
                    iid = str(it.get('id',''))
                    nm  = it.get('nombre','')
                    sel = ' selected' if resps_map.get(iid) == nm else ''
                    body_html += '<option value="' + iid + '|' + nm + '"' + sel + '>' + nm + '</option>'
                body_html += '</select>'

            body_html += '</div>'
            _cat_rendered += 1
        # Cierra la cat-card sólo si tuvo grupos; si no, la quita por completo.
        if _cat_rendered == 0:
            body_html = body_html[:_cat_start]
        else:
            body_html += '</div>'

    resps_j  = json.dumps(resps_map, ensure_ascii=True)
    _gmap    = {}
    for cfg in config_data:
        _ids = [str(x) for x in (cfg.get('item_ids') or [])]
        for _id in _ids:
            _gmap[_id] = _ids
    grupos_j = json.dumps(_gmap, ensure_ascii=True)
    groups_j = json.dumps(groups_data, ensure_ascii=True)

    _hero_css = ('background-image:url(data:image/jpeg;base64,' + hero_b64 + ');background-size:cover;background-position:center;' if hero_b64 else 'background:linear-gradient(135deg,#0a1628,#0f3460,#1a5276);')

    css = '''
@import url("https://fonts.googleapis.com/css2?family=Montserrat:wght@600;700;800;900&family=Poppins:wght@400;600;700;900&display=swap");
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background-color:#f0f4f8 !important;}
body{font-family:Poppins,sans-serif;font-size:14px;color:#0a1628;}
.wrap{max-width:1240px;margin:0 auto;padding:0 0 40px;background-color:#f0f4f8;}
.header{''' + _hero_css + '''padding:0;border-radius:22px;color:white;box-shadow:0 18px 50px rgba(10,22,40,0.30);position:relative;overflow:hidden;min-height:280px;display:flex;flex-direction:column;justify-content:flex-end;margin:6px 18px 22px;}
.header::before{content:"";position:absolute;inset:0;background:linear-gradient(to bottom,rgba(5,10,20,0.15) 0%,rgba(5,10,20,0.65) 100%);border-radius:20px;}
.h-top{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:14px;}
.h-inner{padding:24px 24px 22px;position:relative;z-index:1;}
.h-badge{display:inline-block;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);border-radius:99px;padding:3px 12px;font-size:0.68rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;backdrop-filter:blur(4px);}
.h-title{font-size:1.65rem;font-weight:900;line-height:1.15;margin-bottom:8px;font-family:Poppins,sans-serif;background:linear-gradient(90deg,#fff,#a8d8f0);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.h-sub{font-size:0.82rem;opacity:0.7;line-height:1.5;margin-bottom:12px;}
.h-ep{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.15);border-radius:99px;padding:4px 14px;font-size:0.75rem;font-weight:700;}
.prog-bar{background:rgba(255,255,255,0.12);border-radius:99px;height:5px;margin-top:14px;}
.prog-fill{border-radius:99px;height:5px;background:linear-gradient(90deg,#48cae4,#90e0ef);transition:width 0.5s;}
.prog-lbl{font-size:0.7rem;opacity:0.6;margin-top:4px;}
.cat-card{background:white;border-radius:20px;margin:0 18px 16px;border:1px solid #e8f0fe;box-shadow:0 4px 20px rgba(15,52,96,0.08);overflow:hidden;}
.cat-card-title{font-family:'Montserrat',sans-serif;font-size:0.88rem;font-weight:700;color:#0f172a;letter-spacing:0.05em;text-transform:uppercase;line-height:1.6;padding:18px 24px 2px;display:flex;align-items:center;gap:9px;}
.cat-card-title svg{flex:0 0 auto;}
.item-section{padding:16px 24px 18px;}
.item-divider{height:1px;background:linear-gradient(90deg,#e8f0fe,transparent);margin:0 22px;}
.item-title{font-family:Montserrat,sans-serif;font-size:0.74rem;font-weight:700;color:#475569;letter-spacing:0.05em;text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:8px;}
.done-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;flex-shrink:0;}
.obs-box{background:#eff6ff;border-left:3px solid #60a5fa;border-radius:6px;padding:8px 12px;font-size:0.82rem;color:#374151;margin-bottom:12px;line-height:1.5;}
.carousel-wrap{display:flex;align-items:center;gap:8px;}
.carousel-inner{flex:1;overflow:hidden;}
.nav-btn{background:white;color:#0f3460;border:none;border-radius:50%;width:38px;height:38px;font-size:21px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 14px rgba(0,0,0,0.11);}
.nav-btn:active{transform:scale(0.93);}
.color-row{display:flex;gap:15px;overflow-x:hidden;padding:4px 2px 10px;}
.c-item{cursor:pointer;flex-shrink:0;width:122px;border-radius:12px;overflow:hidden;background:white;box-shadow:0 2px 12px rgba(15,52,96,0.1);transition:all 0.18s;border:2px solid transparent;}
.c-item:active{transform:scale(0.93);}
.c-color-block{width:100%;height:92px;position:relative;}
.c-item.sel{border-color:#0f3460;box-shadow:0 0 0 3px rgba(15,52,96,0.15),0 4px 16px rgba(15,52,96,0.15);}
.c-check{display:none;position:absolute;inset:0;align-items:center;justify-content:center;color:white;font-size:1.4rem;font-weight:900;text-shadow:0 1px 4px rgba(0,0,0,0.4);}
.c-item.sel .c-check{display:flex;}.c-name{font-size:10px;font-weight:400;color:#64748b;padding:6px 6px 7px;text-align:center;line-height:1.2;font-family:Poppins,sans-serif;}
.img-row{display:flex;gap:15px;overflow-x:hidden;padding:4px 2px 12px;}
.i-item{cursor:pointer;flex:0 0 122px;width:122px;border-radius:12px;overflow:hidden;background:white;box-shadow:0 2px 12px rgba(15,52,96,0.1);transition:all 0.18s;border:2px solid transparent;position:relative;}
.i-item:active{transform:scale(0.97);}
.i-circle{width:100%;height:92px;overflow:hidden;display:block;}
.i-item.sel{border-color:#0f3460;box-shadow:0 0 0 3px rgba(15,52,96,0.15),0 4px 16px rgba(15,52,96,0.15);}
.i-circle img{width:100%;height:100%;object-fit:cover;display:block;}
.i-placeholder{width:100%;height:92px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:2rem;}
.i-name{font-size:10px;font-weight:400;color:#64748b;padding:6px 6px 7px;text-align:center;line-height:1.2;font-family:Poppins,sans-serif;}
.i-badge{display:none;position:absolute;top:6px;right:6px;background:#0f3460;color:white;border-radius:50%;width:22px;height:22px;align-items:center;justify-content:center;font-size:12px;font-weight:900;box-shadow:0 2px 8px rgba(15,52,96,0.3);}
.i-item.sel .i-badge{display:flex;}
.zoom-btn{position:absolute;bottom:6px;right:6px;background:rgba(255,255,255,0.9);color:#0f3460;border:none;border-radius:50%;width:24px;height:24px;cursor:pointer;font-size:12px;display:flex;align-items:center;justify-content:center;box-shadow:0 2px 8px rgba(15,52,96,0.2);}
.sino-row{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
.sino-btn{padding:14px;border:2px solid #e2e8f0;border-radius:12px;font-size:14px;font-weight:400;cursor:pointer;background:white;font-family:Poppins,sans-serif;color:#0a1628;box-shadow:0 2px 8px rgba(15,52,96,0.05);transition:all 0.15s;}
.sino-btn.sel{background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border-color:#0f3460;box-shadow:0 6px 20px rgba(15,52,96,0.25);}
.sel-inp{width:100%;padding:11px 14px;border:2px solid #e2e8f0;border-radius:10px;font-size:14px;font-family:Poppins,sans-serif;color:#0a1628;outline:none;}
.sel-inp:focus{border-color:#0f3460;}
.popup{display:none;position:fixed;inset:0;background:rgba(5,10,20,0.95);z-index:9999;flex-direction:column;align-items:center;justify-content:center;}
.popup.open{display:flex;}
.popup img{max-width:90vw;max-height:75vh;object-fit:contain;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,0.5);}
.pop-name{color:white;font-size:1.1rem;font-weight:700;margin-top:14px;}
.pop-close{position:absolute;top:20px;right:24px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:white;font-size:1.2rem;cursor:pointer;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;}
.pop-sel{margin-top:16px;background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:10px;padding:12px 32px;font-size:14px;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 24px rgba(15,52,96,0.3);}
.save-wrap{margin:20px 16px 24px;}
.save-btn{width:100%;padding:15px;background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:14px;font-size:14px;font-weight:500;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 28px rgba(15,52,96,0.28);letter-spacing:0.02em;}
.save-btn:disabled{opacity:0.5;}
.save-st{text-align:center;font-size:13px;font-weight:600;margin-top:8px;min-height:18px;}
'''

    js = (
        'var IC_SAVE_JS=' + json.dumps(_save_svg) + ';'
        'var IC_EXIT_JS=' + json.dumps(_exit_svg) + ';'
        'var ASE_N=' + json.dumps(asesor_nombre or '') + ';'
        'var ASE_F=' + json.dumps(asesor_foto or '') + ';'
        'var ASE_INI=' + json.dumps(asesor_ini) + ';'
        'var CLI_N=' + json.dumps(primer_nombre) + ';'
        + '''
var S="''' + supa_url + '''",K="''' + supa_key + '''",EP="''' + ep + '''";
var R=''' + resps_j + ''';
var G=''' + grupos_j + ''';
var GD=''' + groups_j + ''';
var P={};

function pick(iid,val,tipo){
  R[iid]=val; P[iid]=val;
  if(tipo==="color"){
    var el=document.getElementById("ci-"+iid);
    if(el){
      var row=el.closest(".color-row");
      if(row) row.querySelectorAll(".c-item").forEach(function(e){e.classList.remove("sel");});
      el.classList.add("sel");
    }
  } else if(tipo==="imagen"){
    var el=document.getElementById("ii-"+iid);
    if(el){
      var row=el.closest(".img-row");
      if(row) row.querySelectorAll(".i-item").forEach(function(e){e.classList.remove("sel");});
      el.classList.add("sel");
    }
  } else if(tipo==="si_no"){
    var clickedBtn=document.getElementById("sib-"+iid)||document.getElementById("nob-"+iid);
    if(clickedBtn){
      var row=clickedBtn.closest(".sino-row");
      if(row) row.querySelectorAll(".sino-btn").forEach(function(b){b.classList.remove("sel");});
      clickedBtn.classList.add("sel");
    }
  }
  recompute();
}

function scrollC(gid,dir){
  var el=document.getElementById(gid);
  if(el) el.scrollBy({left:dir*230,behavior:"smooth"});
}

// Lightbox/carrusel del grupo en window.parent.document (position:fixed se ancla a
// la viewport real, no al iframe alto). Muestra categoría + subtítulo, imagen/color
// central grande, miniaturas, flechas, swipe/drag y transición al cambiar.
function openP(btn){
  var D, W;
  try { D=window.parent.document; W=window.parent; } catch(e){ D=document; W=window; }
  var gid=btn.getAttribute("data-pop-gid");
  var idx=parseInt(btn.getAttribute("data-pop-idx")||"0",10); if(isNaN(idx)) idx=0;
  var grp=(typeof GD!=="undefined" && gid!=null && GD[gid]) ? GD[gid] : null;
  if(!grp){
    grp={cat:"",sub:"",type:btn.getAttribute("data-pop-type")||"imagen",
         items:[{iid:btn.getAttribute("data-pop-iid"),name:btn.getAttribute("data-pop-name")||"",
                 url:btn.getAttribute("data-pop-url")||"",hex:btn.getAttribute("data-pop-hex")||""}]};
    idx=0;
  }
  var items=grp.items||[]; if(!items.length) return;
  if(idx<0)idx=0; if(idx>=items.length)idx=items.length-1;
  var typ=grp.type||"imagen";
  var multi=items.length>1;
  var stripDragged=false;

  function esc(s){ return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
  function bigHtml(it){
    if(typ==="color"){
      return '<div style="width:min(70vw,460px);height:min(54vh,460px);border-radius:22px;background:'+(it.hex||"#ccc")+';box-shadow:0 30px 80px rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.25);"></div>';
    }
    return it.url
      ? '<img src="'+esc(it.url)+'" draggable="false" style="max-width:74vw;max-height:60vh;width:auto;height:auto;object-fit:contain;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,0.5);background:#fff;">'
      : '<div style="width:min(70vw,460px);height:min(40vh,360px);border-radius:22px;background:#1e293b;display:flex;align-items:center;justify-content:center;color:#64748b;">Sin imagen</div>';
  }
  function thumbHtml(it,i){
    var inner = (typ==="color")
      ? '<span style="display:block;width:100%;height:100%;border-radius:9px;background:'+(it.hex||"#ccc")+';"></span>'
      : (it.url? '<img src="'+esc(it.url)+'" draggable="false" style="width:100%;height:100%;object-fit:cover;border-radius:9px;display:block;">'
               : '<span style="display:block;width:100%;height:100%;border-radius:9px;background:#1e293b;"></span>');
    return '<button class="_ec_thumb" data-i="'+i+'" style="flex:0 0 auto;width:64px;height:64px;padding:0;border-radius:11px;border:2px solid transparent;background:rgba(255,255,255,0.06);cursor:pointer;overflow:hidden;transition:border-color .2s,transform .2s,box-shadow .2s;">'+inner+'</button>';
  }
  var chevL='<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>';
  var chevR='<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="m9 18 6-6-6-6"/></svg>';
  var arrowCss="flex:0 0 auto;width:46px;height:46px;border-radius:50%;background:rgba(255,255,255,0.12);border:1px solid rgba(255,255,255,0.22);color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s;";

  var existing=D.getElementById("_ec_cli_popup"); if(existing) existing.remove();
  if(!D.getElementById("_ec_pop_css")){
    var s=D.createElement("style"); s.id="_ec_pop_css";
    s.textContent="@keyframes _ecPopInR{from{opacity:0;transform:translateX(34px)}to{opacity:1;transform:translateX(0)}}"
      +"@keyframes _ecPopInL{from{opacity:0;transform:translateX(-34px)}to{opacity:1;transform:translateX(0)}}"
      +"@keyframes _ecPopBd{from{opacity:0}to{opacity:1}}"
      +"#_ec_cli_popup ._ec_stage img{pointer-events:none;-webkit-user-drag:none;}"
      +"#_ec_cli_popup img{-webkit-user-drag:none;user-select:none;}"
      +"#_ec_cli_popup ._ec_strip::-webkit-scrollbar{height:6px}"
      +"#_ec_cli_popup ._ec_strip::-webkit-scrollbar-thumb{background:rgba(255,255,255,.25);border-radius:9px}";
    (D.head||D.body).appendChild(s);
  }
  var prevOv=D.body.style.overflow; D.body.style.overflow="hidden";
  var pop=D.createElement("div"); pop.id="_ec_cli_popup";
  pop.style.cssText="position:fixed;inset:0;background:rgba(5,10,20,0.92);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:Poppins,sans-serif;padding:18px;box-sizing:border-box;animation:_ecPopBd .25s ease both;";

  var head=(grp.cat||grp.sub)
    ? '<div style="text-align:center;margin-bottom:16px;max-width:90vw;">'
      + (grp.cat? '<div style="color:#90e0ef;font-family:Montserrat,sans-serif;font-size:.72rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;margin-bottom:5px;">'+esc(grp.cat)+'</div>':'')
      + (grp.sub? '<div style="color:#fff;font-family:Montserrat,sans-serif;font-size:1.08rem;font-weight:800;letter-spacing:.02em;">'+esc(grp.sub)+'</div>':'')
      + '</div>'
    : '';

  pop.innerHTML=
    '<button class="_ec_pop_close" style="position:absolute;top:18px;right:22px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:white;cursor:pointer;border-radius:50%;width:38px;height:38px;display:flex;align-items:center;justify-content:center;">'
    +'<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg></button>'
    + head
    +'<div style="display:flex;align-items:center;gap:14px;max-width:96vw;">'
    + (multi? '<button class="_ec_prev" style="'+arrowCss+'">'+chevL+'</button>':'')
    +'<div class="_ec_stage" style="display:flex;align-items:center;justify-content:center;min-width:min(70vw,460px);min-height:160px;touch-action:pan-y;cursor:grab;user-select:none;overflow:hidden;">'+bigHtml(items[idx])+'</div>'
    + (multi? '<button class="_ec_next" style="'+arrowCss+'">'+chevR+'</button>':'')
    +'</div>'
    +'<div class="_ec_pop_nm" style="color:white;font-size:1.05rem;font-weight:700;margin-top:16px;text-align:center;max-width:80vw;">'+esc(items[idx].name||"")+'</div>'
    + (multi? '<div class="_ec_strip" style="display:flex;gap:10px;margin-top:14px;max-width:92vw;overflow-x:auto;padding:6px 2px 8px;cursor:grab;scrollbar-width:thin;">'+items.map(thumbHtml).join('')+'</div>':'')
    +'<button class="_ec_pop_sel" style="margin-top:16px;background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:11px;padding:13px 40px;font-size:14px;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 24px rgba(15,52,96,0.35);">Seleccionar</button>';

  D.body.appendChild(pop);

  var stage=pop.querySelector("._ec_stage");
  var nmEl=pop.querySelector("._ec_pop_nm");
  var strip=pop.querySelector("._ec_strip");

  function paintThumbs(){
    if(!strip) return;
    var ts=strip.querySelectorAll("._ec_thumb");
    for(var i=0;i<ts.length;i++){
      var on=(i===idx);
      ts[i].style.borderColor=on?"#48cae4":"transparent";
      ts[i].style.transform=on?"scale(1.06)":"scale(1)";
      ts[i].style.boxShadow=on?"0 6px 18px rgba(72,202,228,.4)":"none";
    }
    if(ts[idx] && ts[idx].scrollIntoView){ try{ts[idx].scrollIntoView({inline:"center",block:"nearest",behavior:"smooth"});}catch(e){} }
  }
  function render(dir){
    stage.innerHTML=bigHtml(items[idx]);
    var inner=stage.firstElementChild;
    if(inner) inner.style.animation=(dir<0?"_ecPopInL":"_ecPopInR")+" .3s ease both";
    nmEl.textContent=items[idx].name||"";
    paintThumbs();
  }
  function go(d){ var n=items.length; idx=(idx+d+n)%n; render(d); }
  function onKey(e){ if(e.key==="Escape") close(); else if(multi&&e.key==="ArrowRight") go(1); else if(multi&&e.key==="ArrowLeft") go(-1); }
  function close(){ if(pop.parentNode) pop.parentNode.removeChild(pop); D.body.style.overflow=prevOv||""; D.removeEventListener("keydown",onKey); }

  paintThumbs();
  pop.querySelector("._ec_pop_close").addEventListener("click", close);
  pop.querySelector("._ec_pop_sel").addEventListener("click", function(){ pick(items[idx].iid, items[idx].name, typ); close(); });
  var pv=pop.querySelector("._ec_prev"); if(pv) pv.addEventListener("click", function(){go(-1);});
  var nx=pop.querySelector("._ec_next"); if(nx) nx.addEventListener("click", function(){go(1);});
  pop.addEventListener("click", function(e){ if(e.target===pop) close(); });
  D.addEventListener("keydown", onKey);

  // swipe en el escenario
  (function(el){
    if(!el) return; var sx=0, down=false;
    el.addEventListener("pointerdown", function(e){ down=true; sx=e.clientX; el.style.cursor="grabbing"; try{el.setPointerCapture(e.pointerId);}catch(_){} });
    el.addEventListener("pointermove", function(e){ if(!down||!multi) return; var dx=e.clientX-sx; var inner=el.firstElementChild; if(inner){ inner.style.transition="none"; inner.style.transform="translateX("+(dx*0.35)+"px)"; } });
    function up(e){ if(!down) return; down=false; el.style.cursor="grab"; var dx=(e.clientX||sx)-sx; var inner=el.firstElementChild; if(inner){ inner.style.transition="transform .25s ease"; inner.style.transform="translateX(0)"; } if(multi && Math.abs(dx)>45){ go(dx<0?1:-1); } }
    el.addEventListener("pointerup", up); el.addEventListener("pointercancel", up);
  })(stage);

  // arrastre horizontal del filmstrip + click en miniatura
  if(strip){
    (function(el){
      var down=false, sx=0, sl=0;
      el.addEventListener("pointerdown", function(e){ down=true; stripDragged=false; sx=e.clientX; sl=el.scrollLeft; el.style.cursor="grabbing"; });
      el.addEventListener("pointermove", function(e){ if(!down) return; var dx=e.clientX-sx; if(Math.abs(dx)>5) stripDragged=true; el.scrollLeft=sl-dx; });
      function up(){ down=false; el.style.cursor="grab"; setTimeout(function(){stripDragged=false;},30); }
      el.addEventListener("pointerup", up); el.addEventListener("pointerleave", up); el.addEventListener("pointercancel", up);
    })(strip);
    strip.addEventListener("click", function(e){
      var t=e.target.closest("._ec_thumb"); if(!t||stripDragged) return;
      var i=parseInt(t.getAttribute("data-i"),10);
      if(!isNaN(i)&&i!==idx){ var d=i>idx?1:-1; idx=i; render(d); }
    });
  }
}

function fabEl(id){ try{return window.parent.document.getElementById(id);}catch(e){return document.getElementById(id);} }
function setSt(t,c){ var el=fabEl("_ec_fab_st"); if(el){el.textContent=t;el.style.color=c;} }

function recompute(){
  var secs=document.querySelectorAll('.item-section');
  var total=secs.length, done=0;
  secs.forEach(function(s){
    var ok=s.querySelector('.c-item.sel,.i-item.sel,.sino-btn.sel');
    if(!ok){var inp=s.querySelector('.sel-inp'); if(inp&&inp.value.trim())ok=true;}
    var t=s.querySelector('.item-title'); var dot=t?t.querySelector('.done-dot'):null;
    if(ok){done++; if(t&&!dot){var d=document.createElement('span');d.className='done-dot';t.appendChild(d);}}
    else if(dot){dot.remove();}
  });
  var pct=total?Math.round(done/total*100):0;
  var hf=document.querySelector('.prog-fill'); if(hf)hf.style.width=pct+'%';
  var hl=document.querySelector('.prog-lbl'); if(hl)hl.textContent=done+' de '+total+' completadas — '+pct+'%';
  var fp=fabEl('_ec_fab_pct'); if(fp)fp.textContent=pct+'%';
  var fb=fabEl('_ec_fab_bar'); if(fb)fb.style.width=pct+'%';
  var fl=fabEl('_ec_fab_lbl'); if(fl)fl.textContent=done+' de '+total+' completadas';
  if(typeof fitHeight==="function") fitHeight();
}

function progresoActual(){
  var secs=document.querySelectorAll('.item-section'), done=0;
  secs.forEach(function(s){ if(s.querySelector('.c-item.sel,.i-item.sel,.sino-btn.sel')||(s.querySelector('.sel-inp')&&s.querySelector('.sel-inp').value.trim()))done++; });
  return {done:done, total:secs.length, pct:(secs.length?Math.round(done/secs.length*100):0)};
}

async function guardar(){
  var btn=fabEl("_ec_fab_save");
  var entries=Object.entries(P);
  if(!entries.length){
    setSt("Tu selección ya estaba guardada","#16a34a");
    showThanks(progresoActual().pct);
    return;
  }
  if(btn)btn.disabled=true; setSt("Guardando...","#2563eb");
  try{
    for(var i=0;i<entries.length;i++){
      var iid=entries[i][0],val=entries[i][1];
      var grp=G[iid]||[];
      for(var j=0;j<grp.length;j++){
        if(grp[j]!==iid){
          await fetch(S+"/rest/v1/formulario_respuestas?cotizacion_numero=eq."+EP+"&item_id=eq."+grp[j],{method:"DELETE",headers:{"Authorization":"Bearer "+K,"apikey":K}});
          delete R[grp[j]];
        }
      }
      await fetch(S+"/rest/v1/formulario_respuestas",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"resolution=merge-duplicates,return=minimal"},body:JSON.stringify({cotizacion_numero:EP,item_id:iid,respuesta:val})});
    }
    P={};
    setSt("Selección guardada correctamente","#16a34a");
    var pr=progresoActual();
    try{
      if(pr.total>0 && pr.done>=pr.total){
        await fetch(S+"/rest/v1/cotizaciones?numero=eq."+EP,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({fecha_formulario_completado:new Date().toISOString()})});
      }
    }catch(e2){}
    if(btn)btn.disabled=false;
    showThanks(pr.pct);
    return;
  }catch(e){setSt("Error: "+e.message,"#dc2626");}
  if(btn)btn.disabled=false;
}

// Modal de agradecimiento (se monta en el documento PADRE para que el overlay
// fixed cubra la viewport real, no el iframe alto). Muestra la foto circular del
// asesor (como el hero del ranking) + mensaje según el % completado.
function showThanks(pct){
  var D; try{D=window.parent.document;}catch(e){D=document;}
  if(!D.getElementById("_ec_modal_css")){
    var stl=D.createElement("style"); stl.id="_ec_modal_css";
    stl.textContent="@keyframes _ecBdIn{from{opacity:0}to{opacity:1}}"
      +"@keyframes _ecCardIn{0%{opacity:0;transform:translateY(28px) scale(.9)}100%{opacity:1;transform:translateY(0) scale(1)}}"
      +"@keyframes _ecAvPop{0%{opacity:0;transform:scale(.4)}60%{transform:scale(1.1)}100%{opacity:1;transform:scale(1)}}"
      +"@keyframes _ecBadgePop{0%{opacity:0;transform:scale(0)}70%{transform:scale(1.25)}100%{opacity:1;transform:scale(1)}}";
    (D.head||D.body).appendChild(stl);
  }
  var old=D.getElementById("_ec_thanks"); if(old) old.remove();
  var done=(pct>=100);
  var accent=done?"#16a34a":"#0f3460";
  var grad2=done?"#22c55e":"#1a5276";
  var AV="min(300px,64vw)";  // tamaño de la foto del asesor (responsivo)
  var primer=CLI_N||"Cliente";
  var ase=ASE_N||"tu asesor";
  var titulo=done?("¡Excelente decisión, "+primer+"!"):("¡Buen avance, "+primer+"!");
  var msg=done
    ? "Has completado de forma exitosa tu formulario de materiales."
    : "Llevas completado el <b style='color:"+accent+"'>"+pct+"%</b> de tu formulario. Si necesitas ayuda, recuerda que estoy para atenderte.";
  var avatar=ASE_F
    ? '<img src="'+ASE_F+'" style="width:100%;height:100%;border-radius:50%;object-fit:cover;display:block;">'
    : '<div style="width:100%;height:100%;border-radius:50%;background:linear-gradient(135deg,#0f3460,#1a5276);display:flex;align-items:center;justify-content:center;color:#fff;font-family:Montserrat,sans-serif;font-weight:900;font-size:1.9rem;">'+(ASE_INI||"EC")+'</div>';
  var badge=done
    ? '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>'
    : '<span style="color:#fff;font-family:Montserrat,sans-serif;font-weight:900;font-size:.92rem;line-height:1;">'+pct+'%</span>';
  var prevOv=D.body.style.overflow; D.body.style.overflow="hidden";
  var ov=D.createElement("div"); ov.id="_ec_thanks";
  ov.style.cssText="position:fixed;inset:0;z-index:2147483646;background:rgba(5,12,28,.62);backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px);display:flex;align-items:center;justify-content:center;padding:22px;box-sizing:border-box;font-family:Poppins,sans-serif;animation:_ecBdIn .3s ease both;";
  ov.innerHTML=
    '<div style="position:relative;background:#fff;border-radius:24px;max-width:472px;width:100%;padding:40px 34px 30px;text-align:center;box-shadow:0 40px 90px rgba(5,12,28,.45);animation:_ecCardIn .55s cubic-bezier(.16,1,.3,1) both;">'
    +'<button id="_ec_th_x" aria-label="Cerrar" style="position:absolute;top:14px;right:14px;width:32px;height:32px;border:none;background:#f1f5f9;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;z-index:2;"><svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="#64748b" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg></button>'
    +'<div style="position:relative;width:'+AV+';height:'+AV+';margin:6px auto 22px;animation:_ecAvPop .6s cubic-bezier(.16,1,.3,1) both;">'
      +'<div style="width:100%;height:100%;border-radius:50%;padding:4px;background:linear-gradient(135deg,'+accent+',#48cae4);box-shadow:0 18px 44px rgba(15,52,96,.34);box-sizing:border-box;">'
        +'<div style="width:100%;height:100%;border-radius:50%;border:4px solid #fff;overflow:hidden;background:#fff;box-sizing:border-box;">'+avatar+'</div>'
      +'</div>'
      +'<div style="position:absolute;bottom:6%;right:6%;width:54px;height:54px;border-radius:50%;background:'+accent+';border:4px solid #fff;display:flex;align-items:center;justify-content:center;box-shadow:0 6px 16px rgba(0,0,0,.2);animation:_ecBadgePop .5s .4s cubic-bezier(.16,1,.3,1) both;">'+badge+'</div>'
    +'</div>'
    +'<div style="font-family:Montserrat,sans-serif;font-weight:800;font-size:1.18rem;color:#0a1628;letter-spacing:.01em;margin-bottom:9px;line-height:1.3;">'+titulo+'</div>'
    +'<div style="color:#475569;font-size:.92rem;line-height:1.6;margin:0 auto 18px;max-width:340px;">'+msg+'</div>'
    +'<div style="border-top:1px solid #eef2f7;padding-top:15px;margin-top:2px;">'
      +'<div style="font-size:.74rem;color:#94a3b8;margin-bottom:2px;">Un saludo,</div>'
      +'<div style="font-family:Montserrat,sans-serif;font-weight:800;font-size:.96rem;color:#0f3460;">'+ase+'</div>'
      +'<div style="font-size:.66rem;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;margin-top:3px;">Tu asesor &middot; Espacio Container</div>'
    +'</div>'
    +'<button id="_ec_th_ok" style="margin-top:20px;width:100%;background:linear-gradient(135deg,'+accent+','+grad2+');color:#fff;border:none;border-radius:13px;padding:13px;font-size:.9rem;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 10px 26px rgba(15,52,96,.28);">'+(done?"¡Genial!":"Entendido")+'</button>'
    +'</div>';
  D.body.appendChild(ov);
  function close(){ if(ov.parentNode)ov.parentNode.removeChild(ov); D.body.style.overflow=prevOv||""; D.removeEventListener("keydown",onKey); }
  function onKey(e){ if(e.key==="Escape") close(); }
  ov.addEventListener("click",function(e){ if(e.target===ov) close(); });
  ov.querySelector("#_ec_th_x").addEventListener("click",close);
  ov.querySelector("#_ec_th_ok").addEventListener("click",close);
  D.addEventListener("keydown",onKey);
}

// Barra flotante (Guardar selección con % + Salir). Se monta en el documento
// PADRE para que position:fixed se ancle a la viewport real (el iframe es muy alto).
(function(){
  var D; try{D=window.parent.document;}catch(e){D=document;}
  var old=D.getElementById("_ec_cli_fab"); if(old) old.remove();
  var oldTh=D.getElementById("_ec_thanks"); if(oldTh){oldTh.remove(); D.body.style.overflow="";}
  var fab=D.createElement("div"); fab.id="_ec_cli_fab";
  fab.style.cssText="position:fixed;right:22px;bottom:22px;z-index:2147483600;display:flex;flex-direction:column;gap:11px;width:240px;font-family:Poppins,sans-serif;";
  fab.innerHTML=
    '<div style="background:#fff;border-radius:18px;box-shadow:0 16px 40px rgba(15,52,96,0.28);border:1px solid #e8f0fe;padding:15px 17px;">'
    +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:9px;">'
    +'<span style="font-size:0.64rem;font-weight:800;color:#64748b;text-transform:uppercase;letter-spacing:0.06em;">Tu progreso</span>'
    +'<span id="_ec_fab_pct" style="font-family:Montserrat,sans-serif;font-size:1.05rem;font-weight:900;color:#0f3460;">0%</span>'
    +'</div>'
    +'<div style="background:#e8f0fe;border-radius:99px;height:8px;overflow:hidden;"><div id="_ec_fab_bar" style="height:8px;border-radius:99px;background:linear-gradient(90deg,#0f3460,#48cae4);width:0%;transition:width .45s ease;"></div></div>'
    +'<div id="_ec_fab_lbl" style="font-size:0.64rem;color:#94a3b8;margin-top:6px;">0 de 0 completadas</div>'
    +'<button id="_ec_fab_save" style="margin-top:12px;width:100%;display:flex;align-items:center;justify-content:center;gap:8px;background:linear-gradient(135deg,#0f3460,#1a5276);color:#fff;border:none;border-radius:12px;padding:12px;font-size:0.84rem;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 22px rgba(15,52,96,0.32);">'+IC_SAVE_JS+' Guardar selección</button>'
    +'<div id="_ec_fab_st" style="text-align:center;font-size:0.7rem;font-weight:600;margin-top:7px;min-height:14px;"></div>'
    +'</div>'
    +'<button id="_ec_fab_exit" style="display:flex;align-items:center;justify-content:center;gap:8px;background:#fff;color:#475569;border:1px solid #e2e8f0;border-radius:12px;padding:10px;font-size:0.8rem;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 4px 16px rgba(15,52,96,0.12);">'+IC_EXIT_JS+' Salir</button>';
  D.body.appendChild(fab);
  var sb=fab.querySelector("#_ec_fab_save"); if(sb) sb.addEventListener("click", guardar);
  var eb=fab.querySelector("#_ec_fab_exit"); if(eb) eb.addEventListener("click", function(){
    try{fab.remove();}catch(e){}
    var b=D.querySelector(".st-key-cli_logout button"); if(b) b.click();
  });
  recompute();
})();

// Ajusta el alto del iframe al contenido real (components.html trae alto fijo y
// el postMessage no lo encoge; se redimensiona el frameElement directo, mismo origen).
function fitHeight(){
  try{
    var h=document.body.scrollHeight;
    if(window.frameElement) window.frameElement.style.height=(h+6)+"px";
    window.parent.postMessage({type:"streamlit:setFrameHeight",height:h},"*");
  }catch(e){}
}
window.addEventListener("load",fitHeight);
[120,400,900,1600,2600].forEach(function(t){setTimeout(fitHeight,t);});
document.querySelectorAll("img").forEach(function(im){im.addEventListener("load",fitHeight);});
''' )

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + css + '</style></head><body>'
        '<div class="wrap">'
        '<div class="header">'
        '<div class="h-inner">'
        '<div class="h-top">'
        '<div class="h-badge">' + _svg(_IC_STAR, 11, 11, 2, '#a8d8f0') + ' Tu selecci&#243;n de materiales</div>'
        '<div>' + logo_html + '</div>'
        '</div>'
        '<div class="h-title">Bienvenida/o,<br>' + primer_nombre + ' ' + _svg(_IC_HOME, 27, 27, 2, '#a8d8f0') + '</div>'
        '<div class="h-sub">Est&#225;s eligiendo los materiales que van a darle vida y personalidad a tu casa container. &#161;Cada elecci&#243;n cuenta!</div>'
        '<div class="h-ep">' + _svg(_IC_TAG, 13, 13, 2.2) + ' ' + ep + '</div>'
        '<div class="prog-bar"><div class="prog-fill" style="width:' + str(pct) + '%;"></div></div>'
        '<div class="prog-lbl">' + str(resp_grupos) + ' de ' + str(total_grupos) + ' completadas &#8212; ' + str(pct) + '%</div>'
        '</div>'
        '</div>'
        + body_html
        + '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html
