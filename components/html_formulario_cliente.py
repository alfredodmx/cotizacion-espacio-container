"""
Genera el HTML del formulario de seleccion de materiales para el cliente.
"""
import json


def build_formulario_cliente_html(cat_items, config_data, resps_map, supa_url, supa_key, ep, nombre_cliente, logo_b64='', hero_b64=''):
    primer_nombre = nombre_cliente.split()[0].capitalize() if nombre_cliente else 'Cliente'
    logo_html = ('<img src="data:image/png;base64,' + logo_b64 + '" style="height:49px;width:auto;object-fit:contain;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.25));">') if logo_b64 else ''

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
                    body_html += '<div class="c-color-block" style="background:' + hx + ';"><span class="c-check">✓</span></div>'
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
                        body_html += '<div class="i-placeholder">&#128230;</div>'
                    body_html += '</div>'
                    body_html += '<div class="i-badge">✓</div>'
                    if url:
                        # Popup se crea dinámicamente en window.parent.document (ver openP en JS)
                        # para que position:fixed se ancle a la viewport real, no al iframe.
                        body_html += ('<button class="zoom-btn" '
                                      'data-pop-url="' + url + '" '
                                      'data-pop-name="' + nm_attr + '" '
                                      'data-pop-iid="' + iid + '" '
                                      'onclick="event.stopPropagation();openP(this)">&#128269;</button>')
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
                body_html += '<button class="sino-btn' + si_sel + '" id="sib-' + si_id + '" onclick="pick(\'' + si_id + '\',\'Sí\',\'si_no\')">✅ Sí</button>'
                body_html += '<button class="sino-btn' + no_sel + '" id="nob-' + no_id + '" onclick="pick(\'' + no_id + '\',\'No\',\'si_no\')">❌ No</button>'
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
body{margin:0;padding:0;font-family:Poppins,sans-serif;font-size:14px;background:#f0f4f8;}
.wrap{max-width:1000px;margin:0 auto;padding:0 0 32px;}
.header{''' + _hero_css + '''padding:0;margin:20px 16px 20px;border-radius:20px;color:white;box-shadow:0 16px 48px rgba(10,22,40,0.28);position:relative;overflow:hidden;min-height:260px;display:flex;flex-direction:column;justify-content:flex-end;margin:20px 16px 20px;}
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
.cat-card{background:white;border-radius:18px;margin:0 16px 14px;border:1px solid #e8f0fe;box-shadow:0 3px 16px rgba(15,52,96,0.07);overflow:hidden;}
.cat-card-title{font-size:0.85rem;font-weight:600;color:#0a1628;font-family:Poppins,sans-serif;letter-spacing:0.04em;padding:16px 22px 0;}
.item-section{padding:14px 22px 16px;}
.item-divider{height:1px;background:linear-gradient(90deg,#e8f0fe,transparent);margin:0 22px;}
.item-title{font-size:0.82rem;font-weight:600;color:#64748b;margin-bottom:12px;display:flex;align-items:center;gap:8px;font-family:Poppins,sans-serif;letter-spacing:0.02em;}
.done-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;display:inline-block;flex-shrink:0;}
.obs-box{background:#eff6ff;border-left:3px solid #60a5fa;border-radius:6px;padding:8px 12px;font-size:0.82rem;color:#374151;margin-bottom:12px;line-height:1.5;}
.carousel-wrap{display:flex;align-items:center;gap:8px;}
.carousel-inner{flex:1;overflow:hidden;}
.nav-btn{background:white;color:#0f3460;border:none;border-radius:50%;width:38px;height:38px;font-size:21px;cursor:pointer;flex-shrink:0;display:flex;align-items:center;justify-content:center;box-shadow:0 3px 14px rgba(0,0,0,0.11);}
.nav-btn:active{transform:scale(0.93);}
.color-row{display:flex;gap:15px;overflow-x:hidden;padding:4px 2px 10px;}
.c-item{cursor:pointer;flex-shrink:0;width:110px;border-radius:12px;overflow:hidden;background:white;box-shadow:0 2px 12px rgba(15,52,96,0.1);transition:all 0.18s;border:2px solid transparent;}
.c-item:active{transform:scale(0.93);}
.c-color-block{width:100%;height:80px;position:relative;}
.c-item.sel{border-color:#0f3460;box-shadow:0 0 0 3px rgba(15,52,96,0.15),0 4px 16px rgba(15,52,96,0.15);}
.c-check{display:none;position:absolute;inset:0;align-items:center;justify-content:center;color:white;font-size:1.4rem;font-weight:900;text-shadow:0 1px 4px rgba(0,0,0,0.4);}
.c-item.sel .c-check{display:flex;}.c-name{font-size:10px;font-weight:400;color:#64748b;padding:6px 6px 7px;text-align:center;line-height:1.2;font-family:Poppins,sans-serif;}
.img-row{display:flex;gap:15px;overflow-x:hidden;padding:4px 2px 12px;}
.i-item{cursor:pointer;flex:0 0 110px;width:110px;border-radius:12px;overflow:hidden;background:white;box-shadow:0 2px 12px rgba(15,52,96,0.1);transition:all 0.18s;border:2px solid transparent;position:relative;}
.i-item:active{transform:scale(0.97);}
.i-circle{width:100%;height:80px;overflow:hidden;display:block;}
.i-item.sel{border-color:#0f3460;box-shadow:0 0 0 3px rgba(15,52,96,0.15),0 4px 16px rgba(15,52,96,0.15);}
.i-circle img{width:100%;height:100%;object-fit:cover;display:block;}
.i-placeholder{width:100%;height:80px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:2rem;}
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

    js = '''
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
}

function scrollC(gid,dir){
  var el=document.getElementById(gid);
  if(el) el.scrollBy({left:dir*230,behavior:"smooth"});
}

// Popup en window.parent.document para que position:fixed se ancle a la
// viewport real (no al iframe, que es muy alto y genera scroll/espacio negro).
function openP(btn){
  var url=btn.getAttribute("data-pop-url");
  var nm=btn.getAttribute("data-pop-name");
  var iid=btn.getAttribute("data-pop-iid");
  var D, W;
  try { D=window.parent.document; W=window.parent; } catch(e){ D=document; W=window; }
  var existing=D.getElementById("_ec_cli_popup");
  if(existing) existing.remove();
  var prevOv=D.body.style.overflow;
  D.body.style.overflow="hidden";
  var pop=D.createElement("div");
  pop.id="_ec_cli_popup";
  pop.style.cssText="position:fixed;inset:0;background:rgba(5,10,20,0.95);z-index:2147483647;display:flex;flex-direction:column;align-items:center;justify-content:center;font-family:Poppins,sans-serif;padding:20px;box-sizing:border-box;";
  pop.innerHTML=
    '<button class="_ec_pop_close" style="position:absolute;top:20px;right:24px;background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);color:white;font-size:1.2rem;cursor:pointer;border-radius:50%;width:36px;height:36px;display:flex;align-items:center;justify-content:center;line-height:1;">'+
    '✕</button>'+
    '<img src="'+url+'" style="max-width:90vw;max-height:75vh;width:auto;height:auto;object-fit:contain;border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,0.5);">'+
    '<div style="color:white;font-size:1.1rem;font-weight:700;margin-top:14px;text-align:center;">'+nm+'</div>'+
    '<button class="_ec_pop_sel" style="margin-top:16px;background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:10px;padding:12px 32px;font-size:14px;font-weight:700;cursor:pointer;font-family:Poppins,sans-serif;box-shadow:0 8px 24px rgba(15,52,96,0.3);">✅ Seleccionar</button>';
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
    pick(iid, nm, "imagen");
    close();
  });
  D.addEventListener("keydown", onKey);
}

async function guardar(){
  var btn=document.getElementById("sbtn");
  var st=document.getElementById("sst");
  var entries=Object.entries(P);
  if(!entries.length){st.textContent="Sin cambios";st.style.color="#94a3b8";return;}
  btn.disabled=true;st.textContent="Guardando...";st.style.color="#2563eb";
  try{
    for(var i=0;i<entries.length;i++){
      var iid=entries[i][0],val=entries[i][1];
      var grp=G[iid]||[];
      for(var j=0;j<grp.length;j++){
        if(grp[j]!==iid){
          await fetch(S+"/rest/v1/formulario_respuestas?cotizacion_numero=eq."+EP+"&item_id=eq."+grp[j],{
            method:"DELETE",
            headers:{"Authorization":"Bearer "+K,"apikey":K}
          });
          delete R[grp[j]];
        }
      }
      await fetch(S+"/rest/v1/formulario_respuestas",{
        method:"POST",
        headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json",
                 "Prefer":"resolution=merge-duplicates,return=minimal"},
        body:JSON.stringify({cotizacion_numero:EP,item_id:iid,respuesta:val})
      });
    }
    P={};
    st.textContent="✅ Guardado";st.style.color="#16a34a";
    try{
      var totalGrupos=document.querySelectorAll('.grupo').length;
      var completados=document.querySelectorAll('.grupo.completado').length;
      if(totalGrupos>0 && completados>=totalGrupos){
        await fetch(S+"/rest/v1/cotizaciones?numero=eq."+EP,{
          method:"PATCH",
          headers:{"Authorization":"Bearer "+K,"apikey":K,
                   "Content-Type":"application/json","Prefer":"return=minimal"},
          body:JSON.stringify({fecha_formulario_completado:new Date().toISOString()})
        });
      }
    }catch(e2){}
  }catch(e){st.textContent="Error: "+e.message;st.style.color="#dc2626";}
  btn.disabled=false;
}
'''

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>' + css + '</style></head><body>'
        '<div class="wrap">'
        '<div class="header">'
        '<div class="h-inner">'
        '<div class="h-top">'
        '<div class="h-badge">✦ Tu selección de materiales ✦</div>'
        '<div>' + logo_html + '</div>'
        '</div>'
        '<div class="h-title">Bienvenida/o,<br>' + primer_nombre + ' 🏡</div>'
        '<div class="h-sub">Estás eligiendo los materiales que van a darle vida y personalidad a tu casa container. ¡Cada elección cuenta!</div>'
        '<div class="h-ep">📋 ' + ep + '</div>'
        '<div class="prog-bar"><div class="prog-fill" style="width:' + str(pct) + '%;"></div></div>'
        '<div class="prog-lbl">' + str(resp_grupos) + ' de ' + str(total_grupos) + ' completadas — ' + str(pct) + '%</div>'
        '</div>'
        '</div>'
        + body_html
        + '<div class="save-wrap">'
        '<button class="save-btn" id="sbtn" onclick="guardar()">💾 Guardar mis elecciones</button>'
        '<div class="save-st" id="sst"></div>'
        '</div>'
        '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html
