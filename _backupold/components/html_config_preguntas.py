"""
Genera el HTML del panel de configuracion de preguntas del formulario (vista admin).
"""
import json


def build_config_preguntas_html(cat_items, config_data, supa_url, supa_key, form_ep):
    grupos       = {}
    orden_grupos = {}
    for c in cat_items:
        cat = c.get('categoria', 'General')
        if cat not in grupos:
            grupos[cat] = {}
            orden_grupos[cat] = {}
        tg = (c.get('titulo_grupo') or '').strip() or '(Sin grupo)'
        if tg not in grupos[cat]:
            grupos[cat][tg] = []
            orden_grupos[cat][tg] = c.get('orden_grupo') or 0
        grupos[cat][tg].append(c)

    config_map = {}
    for cfg in config_data:
        key = cfg.get('categoria','') + '__' + (cfg.get('titulo_grupo') or '')
        config_map[key] = cfg

    all_cats        = sorted(grupos.keys())
    cat_items_json  = json.dumps(cat_items, ensure_ascii=True)
    config_map_json = json.dumps(config_map, ensure_ascii=True)

    cat_html = ''
    for cat in all_cats:
        subgrupos = grupos[cat]
        cat_html += '<div class="cat-block">'
        cat_html += '<div class="cat-block-title">' + cat + '</div>'

        for tg, items in sorted(subgrupos.items(), key=lambda x: orden_grupos.get(cat, {}).get(x[0], 0)):
            tg_key     = cat + '__' + tg
            cfg        = config_map.get(tg_key, {})
            saved_ids  = set(str(x) for x in (cfg.get('item_ids') or []))
            obs_val    = cfg.get('observaciones') or ''
            mostrar_obs = cfg.get('mostrar_obs', False)
            itipo      = items[0].get('tipo', 'imagen') if items else 'imagen'
            badge      = {'imagen':'🖼','color':'🎨','select':'📋','si_no':'✅'}.get(itipo, '❓')
            tg_id      = (cat + '__' + tg).replace(' ','_').replace("'","").replace('(','').replace(')','')[:50]
            all_sel    = all(str(it['id']) in saved_ids for it in items) if saved_ids else False

            cat_html += '<div class="grupo-block">'
            cat_html += '<div class="grupo-header">'
            cat_html += '<input type="checkbox" id="all-' + tg_id + '" ' + ('checked' if all_sel else '') + ' onchange="window.toggleAll(\'' + tg_id + '\',this.checked)" style="width:15px;height:15px;cursor:pointer;flex-shrink:0;">'
            cat_html += '<span class="grupo-title">' + badge + ' ' + tg + '</span>'
            cat_html += '<span class="grupo-count">(' + str(len(items)) + ' opciones)</span>'
            cat_html += '</div>'

            cat_html += '<div class="items-grid">'
            for it in items:
                iid    = str(it.get('id',''))
                nombre = it.get('nombre','')
                checked = 'checked' if iid in saved_ids else ''
                if it.get('imagen_url'):
                    thumb = '<img src="' + it['imagen_url'] + '" style="width:36px;height:36px;object-fit:cover;border-radius:50%;flex-shrink:0;">'
                elif it.get('hex'):
                    thumb = '<div style="width:36px;height:36px;border-radius:50%;background:' + it['hex'] + ';border:1px solid #e2e8f0;flex-shrink:0;"></div>'
                else:
                    thumb = '<div style="width:36px;height:36px;border-radius:50%;background:#f1f5f9;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:0.9rem;">📦</div>'
                cat_html += '<label class="item-chip" id="chip-' + iid + '">'
                cat_html += '<input type="checkbox" id="chk-' + iid + '" value="' + iid + '" ' + checked + ' data-group="' + tg_id + '" onchange="window.updateGroupCheck(\'' + tg_id + '\')" style="width:14px;height:14px;cursor:pointer;">'
                cat_html += thumb
                cat_html += '<span class="item-name">' + nombre + '</span>'
                cat_html += '</label>'
            cat_html += '</div>'

            cat_html += '<div class="obs-row">'
            cat_html += '<div style="flex:1;">'
            cat_html += '<label class="obs-label">Observaciones</label>'
            cat_html += '<textarea id="obs-' + tg_id + '" rows="2" placeholder="Texto opcional que verá el cliente..." style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;resize:vertical;box-sizing:border-box;">' + obs_val + '</textarea>'
            cat_html += '</div>'
            cat_html += '<div style="display:flex;flex-direction:column;align-items:center;gap:4px;padding-top:16px;">'
            cat_html += '<span style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;">Mostrar</span>'
            cat_html += '<label style="display:flex;align-items:center;gap:4px;cursor:pointer;">'
            cat_html += '<input type="checkbox" id="mostrar-' + tg_id + '" ' + ('checked' if mostrar_obs else '') + ' style="width:15px;height:15px;cursor:pointer;">'
            cat_html += '<span style="font-size:11px;font-weight:700;color:#0f3460;">al cliente</span>'
            cat_html += '</label>'
            cat_html += '</div></div>'
            cat_html += '</div>'

        cat_html += '</div>'

    if not cat_html:
        cat_html = '<div class="empty">No hay materiales en el catálogo. Agrega categorías primero.</div>'

    css = '''
body{margin:0;padding:0;font-family:Poppins,Segoe UI,sans-serif;font-size:13px;background:#f0f4f8;}
.wrap{padding:12px;max-width:900px;margin:0 auto;}
.cat-block{background:white;border-radius:14px;padding:14px 16px;margin-bottom:14px;box-shadow:0 2px 12px rgba(15,52,96,0.07);}
.cat-block-title{font-weight:900;font-size:14px;color:#0a1628;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid #e8f0fe;}
.grupo-block{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:12px;margin-bottom:10px;}
.grupo-header{display:flex;align-items:center;gap:8px;margin-bottom:10px;}
.grupo-title{font-weight:800;font-size:13px;color:#0f3460;}
.grupo-count{font-size:10px;color:#94a3b8;font-weight:600;}
.items-grid{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;}
.item-chip{display:flex;align-items:center;gap:6px;background:white;border:1.5px solid #e2e8f0;border-radius:99px;padding:4px 10px 4px 6px;cursor:pointer;transition:all 0.15s;user-select:none;}
.item-chip:has(input:checked){border-color:#0f3460;background:#eff6ff;}
.item-name{font-size:11px;font-weight:700;color:#0a1628;}
.obs-row{display:flex;gap:10px;align-items:flex-start;}
.obs-label{font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;margin-bottom:3px;display:block;}
.save-bar{position:sticky;bottom:0;background:white;border-top:2px solid #e8f0fe;padding:12px 16px;display:flex;gap:10px;align-items:center;box-shadow:0 -4px 20px rgba(15,52,96,0.08);}
.btn-save{background:linear-gradient(135deg,#0f3460,#1a5276);color:white;border:none;border-radius:10px;padding:12px 28px;font-size:14px;font-weight:900;cursor:pointer;font-family:Poppins,sans-serif;}
.btn-save:disabled{opacity:0.5;}
.status{font-size:12px;font-weight:600;flex:1;}
.empty{color:#94a3b8;text-align:center;padding:40px;font-size:14px;}
.link-box{background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:10px 14px;margin-top:12px;}
.sel-summary{font-size:11px;color:#0f3460;font-weight:700;margin-top:6px;}
'''

    js = '''
var S="''' + supa_url + '''",K="''' + supa_key + '''",EP="''' + form_ep + '''";
var CAT_ITEMS=''' + cat_items_json + ''';
var CONFIG=''' + config_map_json + ''';

window.toggleAll=function(tgId,checked){
  document.querySelectorAll('input[data-group="'+tgId+'"]').forEach(function(cb){
    cb.checked=checked;
  });
  updateSummary();
};

window.updateGroupCheck=function(tgId){
  var cbs=document.querySelectorAll('input[data-group="'+tgId+'"]');
  var all=Array.from(cbs).every(function(cb){return cb.checked;});
  var any=Array.from(cbs).some(function(cb){return cb.checked;});
  var allCb=document.getElementById('all-'+tgId);
  if(allCb){allCb.checked=all;allCb.indeterminate=any&&!all;}
  updateSummary();
};

function updateSummary(){
  var total=document.querySelectorAll('.items-grid input[type=checkbox]:checked').length;
  var el=document.getElementById('sel-summary');
  if(el)el.textContent=total+' opción'+(total!==1?'es':'')+' seleccionada'+(total!==1?'s':'');
}

window.guardarConfig=async function(){
  var btn=document.getElementById('save-btn');
  var st=document.getElementById('save-status');
  btn.disabled=true;
  st.textContent='Guardando...';st.style.color='#2563eb';

  var groups={};
  CAT_ITEMS.forEach(function(it){
    var cat=it.categoria||'';
    var tg=(it.titulo_grupo||'').trim()||'(Sin grupo)';
    var key=cat+'__'+tg;
    var tgId=key.replace(/ /g,'_').replace(/\'/g,'').replace(/\\(/g,'').replace(/\\)/g,'')
              .substring(0,50);
    if(!groups[key])groups[key]={cat:cat,tg:tg,tgId:tgId,ids:[],orden:it.orden_grupo||0};
    var cb=document.getElementById('chk-'+it.id);
    if(cb&&cb.checked)groups[key].ids.push(String(it.id));
  });

  var delR=await fetch(S+'/rest/v1/formulario_config?cotizacion_numero=eq.'+encodeURIComponent(EP),{
    method:'DELETE',
    headers:{'Authorization':'Bearer '+K,'apikey':K}
  });
  if(!delR.ok){st.textContent='Error limpiando config: '+delR.status;st.style.color='#dc2626';btn.disabled=false;return;}

  var saved=0;
  for(var key in groups){
    var g=groups[key];
    var obsEl=document.getElementById('obs-'+g.tgId);
    var mostrarEl=document.getElementById('mostrar-'+g.tgId);
    var obs=obsEl?obsEl.value.trim():'';
    var mostrar=mostrarEl?mostrarEl.checked:false;
    var body={
      cotizacion_numero:EP,
      categoria:g.cat,
      titulo_grupo:g.tg,
      item_ids:g.ids,
      observaciones:obs,
      mostrar_obs:mostrar,
      orden:g.orden
    };
    var r=await fetch(S+'/rest/v1/formulario_config',{
      method:'POST',
      headers:{'Authorization':'Bearer '+K,'apikey':K,'Content-Type':'application/json',
               'Prefer':'return=minimal'},
      body:JSON.stringify(body)
    });
    if(r.ok)saved++;
    else{st.textContent='Error: '+r.status;st.style.color='#dc2626';btn.disabled=false;return;}
  }
  st.textContent='✅ Guardado ('+saved+' grupos)';st.style.color='#16a34a';
  btn.disabled=false;
};

updateSummary();
'''

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;900&display=swap" rel="stylesheet">'
        '<style>' + css + '</style></head>'
        '<body><div class="wrap">'
        + cat_html +
        '<div class="link-box">'
        '<div style="font-weight:700;font-size:12px;color:#15803d;margin-bottom:3px;">🔗 Link para el cliente</div>'
        '<a href="https://cotizacion-espacio-container-zlkgejbxhjbbdeu9gvzkla.streamlit.app/?cliente=1" '
        'target="_blank" style="color:#166534;font-size:12px;font-weight:700;">'
        'https://cotizacion-espacio-container-zlkgejbxhjbbdeu9gvzkla.streamlit.app/?cliente=1</a>'
        '<div style="font-size:10px;color:#64748b;margin-top:2px;">El cliente ingresa con su RUT y código ' + form_ep + '</div>'
        '</div>'
        '</div>'
        '<div class="save-bar">'
        '<div id="sel-summary" class="status" style="color:#0f3460;"></div>'
        '<button id="save-btn" onclick="window.guardarConfig()" class="btn-save">💾 Guardar configuración</button>'
        '<div id="save-status" style="font-size:12px;font-weight:600;min-width:160px;"></div>'
        '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html
