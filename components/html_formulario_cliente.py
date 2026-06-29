"""
Genera el HTML del formulario de seleccion de materiales para el cliente.
"""
import json


def build_formulario_cliente_html(cat_items, config_data, resps_map, supa_url, supa_key, ep, nombre_cliente, logo_b64='', hero_b64=''):
    primer_nombre = nombre_cliente.split()[0].capitalize() if nombre_cliente else 'Cliente'
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

    items_by_id = {str(it['id']): it for it in cat_items}

    configs_by_cat = {}
    for cfg in sorted(config_data, key=lambda x: (x.get('categoria',''), x.get('orden', 0))):
        cat = cfg.get('categoria','')
        if cat not in configs_by_cat:
            configs_by_cat[cat] = []
        configs_by_cat[cat].append(cfg)

    total_grupos = len(config_data)
    resp_grupos  = sum(1 for cfg in config_data
                       if any(resps_map.get(str(iid)) for iid in (cfg.get('item_ids') or [])))
    pct = int(resp_grupos / total_grupos * 100) if total_grupos > 0 else 0

    body_html   = ''

    for cat, cfgs in configs_by_cat.items():
        body_html += '<div class="cat-card">'
        body_html += '<div class="cat-card-title">' + cat + '</div>'

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

            if ci > 0:
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
                gid = 'cg-' + str(ci)
                body_html += '<div class="carousel-wrap">'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',-1)">&#8249;</button>'
                body_html += '<div class="carousel-inner"><div class="color-row" id="' + gid + '">'
                for it in group_items:
                    iid = str(it.get('id',''))
                    nm  = it.get('nombre','')
                    hx  = it.get('hex','#ccc') or '#ccc'
                    sel = ' sel' if resps_map.get(iid) == nm else ''
                    body_html += '<div class="c-item' + sel + '" id="ci-' + iid + '" onclick="pick(\'' + iid + '\',\'' + nm.replace("'","") + '\',\'color\')"">'
                    body_html += ('<div class="c-color-block" style="background:' + hx + ';"><span class="c-check">' + _svg('<polyline points="20 6 9 17 4 12"/>', 26, 26, 3) + '</span>'
                                  '<button class="zoom-btn" data-pop-hex="' + hx + '" data-pop-name="' + nm.replace('"', '&quot;') + '" '
                                  'data-pop-iid="' + iid + '" data-pop-type="color" '
                                  'onclick="event.stopPropagation();openP(this)">' + _IC_ZOOM + '</button></div>')
                    body_html += '<div class="c-name">' + nm + '</div>'
                    body_html += '</div>'
                body_html += '</div></div>'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',1)">&#8250;</button>'
                body_html += '</div>'

            elif itipo == 'imagen':
                gid = 'ig-' + str(ci)
                body_html += '<div class="carousel-wrap">'
                body_html += '<button class="nav-btn" onclick="scrollC(\'' + gid + '\',-1)">&#8249;</button>'
                body_html += '<div class="carousel-inner"><div class="img-row" id="' + gid + '">'
                for it in group_items:
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
        body_html += '</div>'

    resps_j  = json.dumps(resps_map, ensure_ascii=True)
    _gmap    = {}
    for cfg in config_data:
        _ids = [str(x) for x in (cfg.get('item_ids') or [])]
        for _id in _ids:
            _gmap[_id] = _ids
    grupos_j = json.dumps(_gmap, ensure_ascii=True)

    _hero_css = ('background-image:url(data:image/jpeg;base64,' + hero_b64 + ');background-size:cover;background-position:center;' if hero_b64 else 'background:linear-gradient(135deg,#0a1628,#0f3460,#1a5276);')

    css = '''
@import url("https://fonts.googleapis.com/css2?family=Poppins:wght@700;900&family=Poppins:wght@400;600;700;900&display=swap");
*{box-sizing:border-box;}
html,body{margin:0;padding:0;background-color:#f0f4f8 !important;}
body{font-family:Poppins,sans-serif;font-size:14px;min-height:100vh;color:#0a1628;}
.wrap{max-width:1240px;margin:0 auto;padding:0 0 120px;background-color:#f0f4f8;min-height:100vh;}
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
.cat-card-title{font-size:0.95rem;font-weight:700;color:#0a1628;font-family:Montserrat,sans-serif;letter-spacing:0.03em;text-transform:uppercase;padding:18px 24px 2px;}
.item-section{padding:16px 24px 18px;}
.item-divider{height:1px;background:linear-gradient(90deg,#e8f0fe,transparent);margin:0 22px;}
.item-title{font-size:0.82rem;font-weight:600;color:#64748b;margin-bottom:12px;display:flex;align-items:center;gap:8px;font-family:Poppins,sans-serif;letter-spacing:0.02em;}
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
        + '''
var S="''' + supa_url + '''",K="''' + supa_key + '''",EP="''' + ep + '''";
var R=''' + resps_j + ''';
var G=''' + grupos_j + ''';
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

// Popup en window.parent.document para que position:fixed se ancle a la
// viewport real (no al iframe, que es muy alto y genera scroll/espacio negro).
function openP(btn){
  var url=btn.getAttribute("data-pop-url");
  var hex=btn.getAttribute("data-pop-hex");
  var nm=btn.getAttribute("data-pop-name");
  var iid=btn.getAttribute("data-pop-iid");
  var typ=btn.getAttribute("data-pop-type")||"imagen";
  var D, W;
  try { D=window.parent.document; W=window.parent; } catch(e){ D=document; W=window; }
  var existing=D.getElementById("_ec_cli_popup");
  if(existing) existing.remove();
  var prevOv=D.body.style.overflow;
  D.body.style.overflow="hidden";
  var pop=D.createElement("div");
  pop.id="_ec_cli_popup";
  pop.style.cssText="position:fixed;inset:0;background:rgba(5,10,20,0.95);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:Poppins,sans-serif;padding:20px;box-sizing:border-box;";
  var visual = url
    ? '<img src="'+url+'" style="max-width:90vw;max-height:75vh;width:auto;height:auto;object-fit:contain;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,0.5);">'
    : '<div style="width:min(72vw,420px);height:min(48vh,420px);border-radius:20px;background:'+(hex||"#ccc")+';box-shadow:0 30px 80px rgba(0,0,0,0.5);border:1px solid rgba(255,255,255,0.25);"></div>';
  pop.innerHTML=
    '<button class="_ec_pop_close" style="position:absolute;top:20px;right:24px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:white;font-size:1.2rem;cursor:pointer;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;line-height:1;">'+
    '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="M6 6l12 12"/></svg></button>'+
    visual+
    '<div style="color:white;font-size:1.1rem;font-weight:700;margin-top:14px;text-align:center;">'+nm+'</div>'+
    '<button class="_ec_pop_sel" style="margin-top:16px;background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:10px;padding:12px 32px;font-size:14px;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 24px rgba(15,52,96,0.3);">Seleccionar</button>';
  D.body.appendChild(pop);
  function close(){
    if(pop.parentNode) pop.parentNode.removeChild(pop);
    D.body.style.overflow=prevOv||"";
    D.removeEventListener("keydown", onKey);
  }
  function onKey(e){ if(e.key==="Escape") close(); }
  pop.addEventListener("click", function(e){ if(e.target===pop) close(); });
  pop.querySelector("._ec_pop_close").addEventListener("click", close);
  pop.querySelector("._ec_pop_sel").addEventListener("click", function(){
    pick(iid, nm, typ);
    close();
  });
  D.addEventListener("keydown", onKey);
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
}

async function guardar(){
  var btn=fabEl("_ec_fab_save");
  var entries=Object.entries(P);
  if(!entries.length){setSt("No hay cambios por guardar","#94a3b8");return;}
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
    try{
      var secs=document.querySelectorAll('.item-section'), done=0;
      secs.forEach(function(s){ if(s.querySelector('.c-item.sel,.i-item.sel,.sino-btn.sel')||(s.querySelector('.sel-inp')&&s.querySelector('.sel-inp').value.trim()))done++; });
      if(secs.length>0 && done>=secs.length){
        await fetch(S+"/rest/v1/cotizaciones?numero=eq."+EP,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({fecha_formulario_completado:new Date().toISOString()})});
      }
    }catch(e2){}
  }catch(e){setSt("Error: "+e.message,"#dc2626");}
  if(btn)btn.disabled=false;
}

// Barra flotante (Guardar selección con % + Salir). Se monta en el documento
// PADRE para que position:fixed se ancle a la viewport real (el iframe es muy alto).
(function(){
  var D; try{D=window.parent.document;}catch(e){D=document;}
  var old=D.getElementById("_ec_cli_fab"); if(old) old.remove();
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
