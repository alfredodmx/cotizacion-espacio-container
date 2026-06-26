"""
Helpers para el módulo de formulario de materiales.
Extraído de app.py líneas 120-2159.
"""
import streamlit as st
from config.supabase import supabase_admin as _supa_admin


@st.cache_data(ttl=120, show_spinner=False)
def fetch_catalogo_materiales(_cache_buster: str = ''):
    """_cache_buster: query param que cambia tras editar el catálogo,
    invalida el cache para que el siguiente render lea de Supabase fresco."""
    try:
        return _supa_admin.table('catalogo_materiales').select('*').eq('activo', True)\
            .order('categoria').order('orden_grupo').order('titulo_grupo').order('nombre')\
            .execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=30, show_spinner=False)
def fetch_formulario_config(ep, _cache_buster: str = ''):
    try:
        return _supa_admin.table('formulario_config').select('*')\
            .eq('cotizacion_numero', ep).execute().data or []
    except Exception:
        return []


def build_config_preguntas_html(cat_items, config_data, supa_url, supa_key, form_ep):
    import json

    grupos = {}
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
        key = cfg.get('categoria', '') + '__' + (cfg.get('titulo_grupo') or '')
        config_map[key] = cfg

    all_cats = sorted(grupos.keys())
    cat_items_json = json.dumps(cat_items, ensure_ascii=True)
    config_map_json = json.dumps(config_map, ensure_ascii=True)

    cat_html = ''
    for cat in all_cats:
        subgrupos = grupos[cat]
        cat_html += '<div class="cat-block">'
        cat_html += '<div class="cat-block-title">' + cat + '</div>'

        for tg, items in sorted(subgrupos.items(), key=lambda x: orden_grupos.get(cat, {}).get(x[0], 0)):
            tg_key = cat + '__' + tg
            cfg = config_map.get(tg_key, {})
            saved_ids = set(str(x) for x in (cfg.get('item_ids') or []))
            obs_val = cfg.get('observaciones') or ''
            mostrar_obs = cfg.get('mostrar_obs', False)
            itipo = items[0].get('tipo', 'imagen') if items else 'imagen'
            badge = {'imagen': '&#128444;', 'color': '&#127912;', 'select': '&#128203;', 'si_no': '&#9989;'}.get(itipo, '?')
            tg_id = (cat + '__' + tg).replace(' ', '_').replace("'", "").replace('(', '').replace(')', '')[:50]
            all_sel = all(str(it['id']) in saved_ids for it in items) if saved_ids else False

            cat_html += '<div class="grupo-block">'
            cat_html += '<div class="grupo-header">'
            cat_html += '<input type="checkbox" id="all-' + tg_id + '" ' + ('checked' if all_sel else '') + ' onchange="window.toggleAll(\'' + tg_id + '\',this.checked)" style="width:15px;height:15px;cursor:pointer;flex-shrink:0;">'
            cat_html += '<span class="grupo-title">' + badge + ' ' + tg + '</span>'
            cat_html += '<span class="grupo-count">(' + str(len(items)) + ' opciones)</span>'
            cat_html += '</div>'
            cat_html += '<div class="items-grid">'
            for it in items:
                iid = str(it.get('id', ''))
                nombre = it.get('nombre', '')
                checked = 'checked' if iid in saved_ids else ''
                if it.get('imagen_url'):
                    thumb = '<img src="' + it['imagen_url'] + '" style="width:36px;height:36px;object-fit:cover;border-radius:50%;flex-shrink:0;">'
                elif it.get('hex'):
                    thumb = '<div style="width:36px;height:36px;border-radius:50%;background:' + it['hex'] + ';border:1px solid #e2e8f0;flex-shrink:0;"></div>'
                else:
                    thumb = '<div style="width:36px;height:36px;border-radius:50%;background:#f1f5f9;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:0.9rem;">&#128230;</div>'
                cat_html += '<label class="item-chip" id="chip-' + iid + '">'
                cat_html += '<input type="checkbox" id="chk-' + iid + '" value="' + iid + '" ' + checked + ' data-group="' + tg_id + '" onchange="window.updateGroupCheck(\'' + tg_id + '\')" style="width:14px;height:14px;cursor:pointer;">'
                cat_html += thumb
                cat_html += '<span class="item-name">' + nombre + '</span>'
                cat_html += '</label>'
            cat_html += '</div>'

            cat_html += '<div class="obs-row">'
            cat_html += '<div style="flex:1;">'
            cat_html += '<label class="obs-label">Observaciones</label>'
            cat_html += '<textarea id="obs-' + tg_id + '" rows="2" placeholder="Texto opcional que ver&#225; el cliente..." style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:6px;font-size:12px;resize:vertical;box-sizing:border-box;">' + obs_val + '</textarea>'
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
        cat_html = '<div class="empty">No hay materiales en el cat&#225;logo. Agrega categor&#237;as primero.</div>'

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
.sel-summary{font-size:11px;color:#0f3460;font-weight:700;margin-top:6px;}
'''

    js = (
        'var S="' + supa_url + '",K="' + supa_key + '",EP="' + form_ep + '";\n'
        'var CAT_ITEMS=' + cat_items_json + ';\n'
        'var CONFIG=' + config_map_json + ';\n'
        '''
window.toggleAll=function(tgId,checked){
  document.querySelectorAll('input[data-group="'+tgId+'"]').forEach(function(cb){cb.checked=checked;});
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
  btn.disabled=true;st.textContent='Guardando...';st.style.color='#2563eb';
  var groups={};
  CAT_ITEMS.forEach(function(it){
    var cat=it.categoria||'';var tg=(it.titulo_grupo||'').trim()||'(Sin grupo)';
    var key=cat+'__'+tg;
    var tgId=key.replace(/ /g,'_').replace(/\'/g,'').replace(/\\(/g,'').replace(/\\)/g,'').substring(0,50);
    if(!groups[key])groups[key]={cat:cat,tg:tg,tgId:tgId,ids:[],orden:it.orden_grupo||0};
    var cb=document.getElementById('chk-'+it.id);
    if(cb&&cb.checked)groups[key].ids.push(String(it.id));
  });
  var delR=await fetch(S+'/rest/v1/formulario_config?cotizacion_numero=eq.'+encodeURIComponent(EP),{
    method:'DELETE',headers:{'Authorization':'Bearer '+K,'apikey':K}
  });
  if(!delR.ok){st.textContent='Error: '+delR.status;st.style.color='#dc2626';btn.disabled=false;return;}
  var saved=0;
  for(var key in groups){
    var g=groups[key];
    var obsEl=document.getElementById('obs-'+g.tgId);
    var mostrarEl=document.getElementById('mostrar-'+g.tgId);
    var body={cotizacion_numero:EP,categoria:g.cat,titulo_grupo:g.tg,item_ids:g.ids,
              observaciones:obsEl?obsEl.value.trim():'',mostrar_obs:mostrarEl?mostrarEl.checked:false,orden:g.orden};
    var r=await fetch(S+'/rest/v1/formulario_config',{
      method:'POST',headers:{'Authorization':'Bearer '+K,'apikey':K,'Content-Type':'application/json','Prefer':'return=minimal'},
      body:JSON.stringify(body)
    });
    if(r.ok)saved++;
    else{st.textContent='Error: '+r.status;st.style.color='#dc2626';btn.disabled=false;return;}
  }
  st.textContent='✅ Guardado ('+saved+' grupos)';st.style.color='#16a34a';btn.disabled=false;
};
updateSummary();
'''
    )

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700;900&display=swap" rel="stylesheet">'
        '<style>' + css + '</style></head>'
        '<body><div class="wrap">'
        + cat_html +
        '<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:10px;padding:10px 14px;margin-top:12px;">'
        '<div style="font-weight:700;font-size:12px;color:#15803d;margin-bottom:3px;">&#128279; Link para el cliente</div>'
        '<div style="font-size:10px;color:#64748b;margin-top:2px;">El cliente ingresa con su RUT y c&#243;digo ' + form_ep + '</div>'
        '</div>'
        '</div>'
        '<div class="save-bar">'
        '<div id="sel-summary" class="status" style="color:#0f3460;"></div>'
        '<button id="save-btn" onclick="window.guardarConfig()" class="btn-save">&#128190; Guardar configuraci&#243;n</button>'
        '<div id="save-status" style="font-size:12px;font-weight:600;min-width:160px;"></div>'
        '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html


def build_catalogo_html(cat_items, supa_url, supa_key, tipo='imagen', cantidad=4):
    import json

    grupos = {}
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

    all_cats = sorted(grupos.keys())
    all_cats_json = json.dumps(all_cats, ensure_ascii=False)
    cat_items_json = json.dumps(cat_items, ensure_ascii=True)

    cat_html = ''
    for cat in all_cats:
        subgrupos = grupos[cat]
        total = sum(len(v) for v in subgrupos.values())
        cat_html += '<div class="cat-block" id="catblock-' + cat + '">'
        cat_html += '<div class="cat-header">'
        cat_html += '<span class="cat-title">' + cat + '</span>'
        cat_html += '<div style="display:flex;gap:6px;align-items:center;">'
        cat_html += '<span style="font-size:11px;opacity:0.7;">' + str(total) + ' &#237;tems</span>'
        cat_html += '<button onclick="window.toggleEdit(\'' + cat + '\')" class="btn-edit" id="btn-edit-' + cat + '">&#9998;&#65039; Editar</button>'
        cat_html += '<button onclick="window.eliminarCategoria(\'' + cat + '\')" class="btn-del-cat">&#128465;</button>'
        cat_html += '</div></div>'
        cat_html += '<div id="preview-' + cat + '" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:4px;margin-top:6px;">'
        for tg, items in sorted(subgrupos.items()):
            for it in items:
                iurl = it.get('imagen_url') or ''
                itipo = it.get('tipo', 'imagen')
                badge = {'imagen': '&#128444;', 'color': '&#127912;', 'select': '&#128203;', 'si_no': '&#9989;'}.get(itipo, '?')
                if iurl:
                    preview = '<img src="' + iurl + '" style="width:100%;height:55px;object-fit:cover;display:block;">'
                elif it.get('hex'):
                    preview = '<div style="width:100%;height:55px;background:' + it['hex'] + ';"></div>'
                else:
                    preview = '<div style="width:100%;height:55px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:1rem;">&#128230;</div>'
                cat_html += '<div style="background:white;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">'
                cat_html += preview
                cat_html += '<div style="font-size:9px;font-weight:700;padding:2px 4px;display:flex;justify-content:space-between;">'
                cat_html += '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + it.get('nombre', '') + '</span>'
                cat_html += '<span>' + badge + '</span></div></div>'
        cat_html += '</div>'
        cat_html += '<div id="edit-' + cat + '" style="display:none;margin-top:10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;">'
        cat_html += '<div style="display:flex;gap:8px;margin-bottom:14px;align-items:flex-end;padding-bottom:12px;border-bottom:1px solid #e2e8f0;">'
        cat_html += '<div style="flex:1"><label class="field-label">Nombre de categor&#237;a</label>'
        cat_html += '<input id="rename-' + cat + '" type="text" value="' + cat + '" class="mini-input"></div>'
        cat_html += '<button onclick="window.renombrarCategoria(\'' + cat + '\')" class="btn-primary">Renombrar</button>'
        cat_html += '<div id="rename-st-' + cat + '" style="font-size:11px;font-weight:600;align-self:center;min-width:40px;"></div>'
        cat_html += '</div>'
        for tg, items in sorted(subgrupos.items(), key=lambda x: orden_grupos.get(cat, {}).get(x[0], 0)):
            tg_display = tg
            tg_id = tg.replace(' ', '_').replace("'", "").replace('(', '').replace(')', '')[:30]
            itipo = items[0].get('tipo', 'imagen') if items else 'imagen'
            badge = {'imagen': '&#128444;', 'color': '&#127912;', 'select': '&#128203;', 'si_no': '&#9989;'}.get(itipo, '?')
            ids_json = json.dumps([str(it['id']) for it in items])
            cat_html += '<div class="subgroup-block" id="sg-' + cat + '-' + tg_id + '">'
            cat_html += '<div class="subgroup-header">'
            _orden_val = str(orden_grupos.get(cat, {}).get(tg, 0))
            cat_html += '<div style="display:flex;align-items:center;gap:8px;flex:1;">'
            cat_html += '<div style="display:flex;flex-direction:column;align-items:center;gap:1px;">'
            cat_html += '<span style="font-size:9px;color:#94a3b8;font-weight:700;">ORDEN</span>'
            cat_html += '<input type="number" value="' + _orden_val + '" id="tg-orden-' + cat + '-' + tg_id + '" min="0" max="99" style="width:48px;padding:3px 5px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;font-weight:700;text-align:center;">'
            cat_html += '</div>'
            cat_html += '<span style="font-size:13px;">' + badge + '</span>'
            cat_html += '<input type="text" value="' + tg_display + '" id="tg-rename-' + cat + '-' + tg_id + '" class="mini-input" style="max-width:180px;font-weight:700;" placeholder="Nombre del &#237;tem">'
            cat_html += '<span style="font-size:10px;color:#94a3b8;">(' + str(len(items)) + ')</span>'
            cat_html += '</div>'
            cat_html += '<div style="display:flex;gap:4px;">'
            cat_html += '<button onclick="window.renombrarGrupo(\'' + cat + '\',\'' + tg.replace("'", "\\'") + '\',\'' + tg_id + '\')" class="btn-save-sm" title="Guardar nombre y orden">&#128190; Guardar</button>'
            cat_html += '<button onclick="window.showClonar(\'' + cat + '\',\'' + tg_id + '\')" class="btn-clone">&#128203; Clonar</button>'
            cat_html += '<button onclick="window.eliminarGrupo(\'' + cat + '\',\'' + tg.replace("'", "\\'") + '\',' + ids_json + ')" class="btn-del-sm">&#128465;</button>'
            cat_html += '</div></div>'
            cat_html += '<div id="clone-panel-' + cat + '-' + tg_id + '" style="display:none;background:#eff6ff;border:1px solid #93c5fd;border-radius:6px;padding:8px;margin:6px 0;">'
            cat_html += '<div style="font-size:11px;font-weight:700;color:#1e3a5f;margin-bottom:6px;">Clonar "' + tg_display + '" a categor&#237;a:</div>'
            cat_html += '<div style="display:flex;gap:6px;align-items:center;">'
            cat_html += '<select id="clone-dest-' + cat + '-' + tg_id + '" style="flex:1;padding:5px 8px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;">'
            for other_cat in all_cats:
                if other_cat != cat:
                    cat_html += '<option value="' + other_cat + '">' + other_cat + '</option>'
            cat_html += '</select>'
            cat_html += '<button onclick="window.confirmarClonar(\'' + cat + '\',\'' + tg.replace("'", "\\'") + '\',\'' + tg_id + '\')" class="btn-primary">&#9989; Clonar</button>'
            cat_html += '<button onclick="document.getElementById(\'clone-panel-' + cat + '-' + tg_id + '\').style.display=\'none\'" class="btn-cancel">&#10005;</button>'
            cat_html += '</div>'
            cat_html += '<div id="clone-st-' + cat + '-' + tg_id + '" style="font-size:11px;font-weight:600;margin-top:4px;"></div>'
            cat_html += '</div>'
            cat_html += '<div style="display:flex;flex-direction:column;gap:4px;margin-top:8px;">'
            for it in items:
                iid = str(it.get('id', ''))
                iurl = it.get('imagen_url') or ''
                ihex = it.get('hex') or ''
                if iurl:
                    thumb = '<img src="' + iurl + '" style="width:34px;height:34px;object-fit:cover;border-radius:4px;flex-shrink:0;">'
                elif ihex:
                    thumb = '<div style="width:34px;height:34px;background:' + ihex + ';border-radius:50%;border:1px solid #e2e8f0;flex-shrink:0;"></div>'
                else:
                    thumb = '<div style="width:34px;height:34px;background:#f1f5f9;border-radius:4px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:0.9rem;">&#128230;</div>'
                cat_html += '<div style="display:flex;align-items:center;gap:8px;background:white;border:1px solid #e2e8f0;border-radius:6px;padding:5px 8px;">'
                cat_html += thumb
                cat_html += '<input type="text" value="' + it.get('nombre', '').replace('"', '') + '" id="item-name-' + iid + '" class="mini-input" style="flex:1;">'
                cat_html += '<button onclick="window.renombrarItem(\'' + iid + '\')" class="btn-save-sm" title="Guardar nombre">&#128190;</button>'
                cat_html += '<button onclick="window.catEliminar(\'' + iid + '\',\'' + iurl + '\')" class="btn-del-xs">&#128465;</button>'
                cat_html += '</div>'
            cat_html += '</div>'
            cat_html += '</div>'
        cat_html += '<div style="margin-top:14px;border-top:1px solid #e2e8f0;padding-top:12px;">'
        cat_html += '<div style="font-weight:700;font-size:11px;color:#64748b;margin-bottom:8px;text-transform:uppercase;">Agregar nuevo &#237;tem a ' + cat + ':</div>'
        cat_html += '<div style="margin-bottom:8px;"><label class="field-label">T&#237;tulo del grupo</label>'
        cat_html += '<input id="new-tg-' + cat + '" type="text" placeholder="ej: Color de muros" class="mini-input"></div>'
        cat_html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">'
        cat_html += '<div><label class="field-label">Tipo</label>'
        cat_html += '<select id="new-tipo-' + cat + '" onchange="window.renderAddForm(\'' + cat + '\')" style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;">'
        cat_html += '<option value="imagen">&#128444; Imagen</option>'
        cat_html += '<option value="color">&#127912; Color</option>'
        cat_html += '<option value="select">&#128203; Lista</option>'
        cat_html += '<option value="si_no">&#9989; S&#237;/No</option>'
        cat_html += '</select></div>'
        cat_html += '<div id="new-cant-wrap-' + cat + '"><label class="field-label">Cantidad</label>'
        cat_html += '<input type="number" id="new-cantidad-' + cat + '" value="3" min="1" max="20" onchange="window.renderAddForm(\'' + cat + '\')" style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;"></div>'
        cat_html += '</div>'
        cat_html += '<div id="new-opts-wrap-' + cat + '"></div>'
        cat_html += '</div>'
        cat_html += '<div style="display:flex;gap:8px;margin-top:10px;">'
        cat_html += '<button onclick="window.agregarItemCompleto(\'' + cat + '\')" class="btn-success" style="flex:1;padding:9px;">+ Agregar &#237;tem</button>'
        cat_html += '<button onclick="window.toggleEdit(\'' + cat + '\')" class="btn-cancel" style="flex:1;padding:9px;">&#10005; Cancelar</button>'
        cat_html += '</div>'
        cat_html += '<div id="edit-status-' + cat + '" style="font-size:11px;font-weight:600;min-height:16px;margin-top:6px;"></div>'
        cat_html += '</div>'
        cat_html += '</div>'
        cat_html += '</div>'

    if not cat_html:
        cat_html = '<p style="color:#64748b;padding:8px 0;">El cat&#225;logo est&#225; vac&#237;o.</p>'

    css = '''
body{margin:0;padding:8px;font-family:Segoe UI,sans-serif;font-size:13px;background:#f8fafc;}
.cat-block{margin-bottom:14px;background:white;border:1px solid #e2e8f0;border-radius:10px;padding:12px;}
.cat-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;}
.cat-title{font-weight:900;font-size:14px;color:#0a1628;}
.btn-edit{background:#e8f0fe;color:#0f3460;border:none;border-radius:4px;padding:3px 9px;font-size:11px;cursor:pointer;font-weight:700;}
.btn-del-cat{background:#fee2e2;color:#dc2626;border:none;border-radius:4px;padding:3px 8px;font-size:11px;cursor:pointer;}
.btn-primary{background:#1e3a5f;color:white;border:none;border-radius:5px;padding:6px 12px;font-size:12px;cursor:pointer;font-weight:700;}
.btn-success{background:#16a34a;color:white;border:none;border-radius:5px;padding:7px 14px;font-size:12px;cursor:pointer;font-weight:700;}
.btn-clone{background:#f0fdf4;color:#15803d;border:1px solid #86efac;border-radius:4px;padding:3px 8px;font-size:11px;cursor:pointer;font-weight:700;}
.btn-del-sm{background:#fee2e2;color:#dc2626;border:none;border-radius:4px;padding:3px 8px;font-size:11px;cursor:pointer;font-weight:700;}
.btn-del-xs{background:#fee2e2;color:#dc2626;border:none;border-radius:4px;padding:2px 7px;font-size:11px;cursor:pointer;}
.btn-save-sm{background:#dbeafe;color:#1e3a5f;border:none;border-radius:4px;padding:3px 7px;font-size:12px;cursor:pointer;font-weight:700;}
.btn-cancel{background:#f1f5f9;color:#64748b;border:1px solid #e2e8f0;border-radius:5px;padding:6px 12px;font-size:12px;cursor:pointer;font-weight:700;}
.btn-save-cat{background:#0f3460;color:white;border:none;border-radius:7px;padding:10px 16px;font-size:13px;font-weight:700;cursor:pointer;}
.subgroup-block{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-bottom:8px;}
.subgroup-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:8px;}
.new-cat-box{background:white;border:2px solid #0f3460;border-radius:10px;padding:16px;margin-top:16px;}
.new-cat-title{font-weight:900;color:#0f172a;margin-bottom:12px;font-size:15px;}
.field-label{font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;margin-bottom:3px;display:block;}
.item-block{background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:12px;margin-bottom:10px;}
.opt-row{display:grid;gap:6px;margin-bottom:5px;align-items:center;}
.opt-row.color{grid-template-columns:1fr 44px 36px;}
.opt-row.imagen{grid-template-columns:1fr 1fr;}
.mini-input{padding:5px 8px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;width:100%;box-sizing:border-box;}
.mini-prev{width:32px;height:32px;border-radius:4px;object-fit:cover;flex-shrink:0;}
'''

    js = (
        'var S="' + supa_url + '",K="' + supa_key + '";\n'
        'var ALL_CATS=' + all_cats_json + ';\n'
        'var ALL_ITEMS=' + cat_items_json + ';\n'
        'var _items=[];\n'
        '''
function doRerun(){
  // Refresca el catálogo SIN recargar la página: clickeamos un botón nativo de
  // Streamlit oculto (.st-key-_cat_refresh_btn) que dispara un rerun y re-genera
  // este iframe con datos frescos. Recargar la página (lo que se hacía antes)
  // perdía la sesión y obligaba a re-loguear. Reintenta unos instantes por si el
  // botón aún no está montado en el DOM del parent.
  var tries=0;
  (function clickBtn(){
    try {
      var btn=window.parent.document.querySelector('.st-key-_cat_refresh_btn button');
      if(btn){ btn.click(); return; }
    } catch(e){}
    if(++tries<20){ setTimeout(clickBtn,80); return; }
    // Fallback (último recurso): reload con cache_buster.
    try {
      var u=new URL(window.parent.location.href);
      u.searchParams.set("_cat_ts", String(Date.now()));
      window.parent.location.replace(u.toString());
    } catch(e2){ try{ window.parent.location.reload(); }catch(e3){} }
  })();
}
window.toggleEdit=function(cat){
  var ep=document.getElementById("edit-"+cat);
  var pp=document.getElementById("preview-"+cat);
  var hidden=ep.style.display==="none";
  ep.style.display=hidden?"block":"none";
  pp.style.display=hidden?"none":"grid";
  document.getElementById("btn-edit-"+cat).textContent=hidden?"✕ Cerrar":"✏️ Editar";
  if(hidden){setTimeout(function(){window.renderAddForm(cat);},10);}
};
window.renombrarItem=async function(id){
  var el=document.getElementById("item-name-"+id);if(!el)return;
  var nuevo=el.value.trim();if(!nuevo)return;
  var r=await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({nombre:nuevo})});
  if(r.ok){el.style.borderColor="#16a34a";setTimeout(function(){el.style.borderColor="";},1200);}
  else alert("Error: "+r.status);
};
window.renombrarGrupo=async function(cat,tgOld,tgId){
  var el=document.getElementById("tg-rename-"+cat+"-"+tgId);if(!el)return;
  var nuevo=el.value.trim();if(!nuevo||nuevo===tgOld)return;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat&&(it.titulo_grupo||"(Sin grupo)")===tgOld;});
  var ids=items.map(function(it){return it.id;});if(!ids.length)return;
  var ordenEl=document.getElementById("tg-orden-"+cat+"-"+tgId);
  var orden=ordenEl?parseInt(ordenEl.value)||0:0;
  var r=await fetch(S+"/rest/v1/catalogo_materiales?id=in.("+ids.join(",")+")",{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({titulo_grupo:nuevo,orden_grupo:orden})});
  if(r.ok){el.style.borderColor="#16a34a";setTimeout(function(){doRerun();},800);}
  else alert("Error: "+r.status);
};
window.renombrarCategoria=async function(cat){
  var nuevo=document.getElementById("rename-"+cat).value.trim();
  var st=document.getElementById("rename-st-"+cat);
  if(!nuevo||nuevo===cat)return;
  st.textContent="...";st.style.color="#2563eb";
  var r=await fetch(S+"/rest/v1/catalogo_materiales?categoria=eq."+encodeURIComponent(cat),{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({categoria:nuevo})});
  if(r.ok){st.textContent="✅";st.style.color="#16a34a";setTimeout(doRerun,600);}
  else{st.textContent="Error";st.style.color="#dc2626";}
};
window.showClonar=function(cat,tgId){
  var p=document.getElementById("clone-panel-"+cat+"-"+tgId);
  if(p)p.style.display=p.style.display==="none"?"block":"none";
};
window.confirmarClonar=async function(cat,tg,tgId){
  var destEl=document.getElementById("clone-dest-"+cat+"-"+tgId);
  var stEl=document.getElementById("clone-st-"+cat+"-"+tgId);
  if(!destEl)return;
  var dest=destEl.value;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat&&(it.titulo_grupo||"(Sin grupo)")===tg;});
  if(!items.length){stEl.textContent="Sin ítems";stEl.style.color="#dc2626";return;}
  stEl.textContent="Clonando...";stEl.style.color="#2563eb";
  var ok=0;
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var body={categoria:dest,nombre:it.nombre,titulo_grupo:it.titulo_grupo||"",tipo:it.tipo||"imagen",imagen_url:it.imagen_url||"",hex:it.hex||"",activo:true};
    var r=await fetch(S+"/rest/v1/catalogo_materiales",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(body)});
    if(r.ok)ok++;
  }
  stEl.textContent="✅ "+ok+" clonados a "+dest;stEl.style.color="#16a34a";
  setTimeout(doRerun,800);
};
// Extrae el path del bucket ignorando query strings (?token=...) y hash
function extractStoragePath(url){
  if(!url) return "";
  var marker="/public/formulario-imagenes/";
  var idx=url.indexOf(marker);
  if(idx<0) return "";
  var rest=url.substring(idx+marker.length);
  // Cortar en ? o #
  var qIdx=rest.indexOf("?");
  if(qIdx>=0) rest=rest.substring(0,qIdx);
  var hIdx=rest.indexOf("#");
  if(hIdx>=0) rest=rest.substring(0,hIdx);
  return rest;
}
async function deleteStorageImg(url){
  var path=extractStoragePath(url);
  if(!path) return true;
  try {
    var r=await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"DELETE",headers:{"Authorization":"Bearer "+K,"apikey":K}});
    return r.ok;
  } catch(e){ return false; }
}
window.eliminarGrupo=async function(cat,tg,ids){
  if(!confirm("¿Eliminar todos los ítems del grupo \\""+tg+"\\"?"))return;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat&&(it.titulo_grupo||"(Sin grupo)")===tg;});
  for(var i=0;i<items.length;i++){
    await deleteStorageImg(items[i].imagen_url||"");
    await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+items[i].id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  }
  doRerun();
};
window.catEliminar=async function(id,url){
  if(!confirm("¿Eliminar este ítem?"))return;
  await deleteStorageImg(url);
  await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  doRerun();
};
window.eliminarCategoria=async function(cat){
  if(!confirm("¿Eliminar toda la categoría "+cat+"?"))return;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat;});
  for(var i=0;i<items.length;i++){
    await deleteStorageImg(items[i].imagen_url||"");
  }
  await fetch(S+"/rest/v1/catalogo_materiales?categoria=eq."+encodeURIComponent(cat),{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  doRerun();
};
window.renderAddForm=function(cat){
  var tipo=document.getElementById("new-tipo-"+cat).value;
  var n=parseInt(document.getElementById("new-cantidad-"+cat).value)||3;
  var cantWrap=document.getElementById("new-cant-wrap-"+cat);
  if(cantWrap)cantWrap.style.display=tipo==="si_no"?"none":"block";
  var wrap=document.getElementById("new-opts-wrap-"+cat);if(!wrap)return;
  var html="";
  if(tipo==="si_no"){
    html="<div style=\\"font-size:11px;color:#64748b;padding:6px;background:#f8fafc;border-radius:5px;\\">Solo tendrá Sí y No.</div>";
  } else {
    for(var i=0;i<n;i++){
      if(tipo==="color"){
        html+="<div style=\\"display:grid;grid-template-columns:1fr 44px 36px;gap:6px;margin-bottom:5px;align-items:center;\\">";
        html+="<input type=\\"text\\" id=\\"nadd-nom-"+cat+"-"+i+"\\" placeholder=\\"Nombre "+(i+1)+"\\" class=\\"mini-input\\">";
        html+="<input type=\\"color\\" id=\\"nadd-hex-"+cat+"-"+i+"\\" value=\\"#ffffff\\" style=\\"width:44px;height:34px;border-radius:4px;border:1px solid #cbd5e1;cursor:pointer;\\">";
        html+="<div id=\\"nadd-prev-"+cat+"-"+i+"\\" style=\\"width:32px;height:32px;border-radius:50%;background:#ffffff;border:1px solid #e2e8f0;\\"></div></div>";
      } else if(tipo==="imagen"){
        html+="<div style=\\"display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:5px;align-items:center;\\">";
        html+="<input type=\\"text\\" id=\\"nadd-nom-"+cat+"-"+i+"\\" placeholder=\\"Nombre "+(i+1)+"\\" class=\\"mini-input\\">";
        html+="<input type=\\"file\\" id=\\"nadd-file-"+cat+"-"+i+"\\" accept=\\"image/*\\" style=\\"font-size:11px;\\"></div>";
      } else {
        html+="<input type=\\"text\\" id=\\"nadd-nom-"+cat+"-"+i+"\\" placeholder=\\"Opción "+(i+1)+"\\" class=\\"mini-input\\" style=\\"margin-bottom:5px;\\">";
      }
    }
  }
  wrap.innerHTML=html;
};
window.agregarItemCompleto=async function(cat){
  var tg=document.getElementById("new-tg-"+cat).value.trim();
  var tipo=document.getElementById("new-tipo-"+cat).value;
  var n=parseInt(document.getElementById("new-cantidad-"+cat).value)||3;
  var st=document.getElementById("edit-status-"+cat);
  var items=[];
  if(tipo==="si_no"){items=[{nombre:"Sí",hex:"",url:""},{nombre:"No",hex:"",url:""}];}
  else {
    for(var i=0;i<n;i++){
      var nomEl=document.getElementById("nadd-nom-"+cat+"-"+i);
      if(!nomEl||!nomEl.value.trim())continue;
      var item={nombre:nomEl.value.trim(),hex:"",url:""};
      if(tipo==="color"){item.hex=document.getElementById("nadd-hex-"+cat+"-"+i).value;}
      else if(tipo==="imagen"){
        var fEl=document.getElementById("nadd-file-"+cat+"-"+i);
        if(fEl&&fEl.files[0]){
          st.textContent="Subiendo imagen "+(i+1)+"...";st.style.color="#2563eb";
          var file=fEl.files[0];
          var ext=(file.name.split(".").pop()||"png").toLowerCase().replace(/[^a-z0-9]/g,"");
          var path="catalogo/"+Date.now()+"_"+Math.random().toString(36).substring(2,7)+"."+ext;
          var ur=await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":file.type||"image/png","x-upsert":"true"},body:file});
          if(!ur.ok){
            var et=await ur.text();
            var msg=ur.status===403?"Sin permisos en bucket (403) — revisa policy INSERT con anon key"
                   :ur.status===413?"Imagen demasiado grande (413)"
                   :"Error "+ur.status;
            st.textContent=msg+": "+et.substring(0,80);st.style.color="#dc2626";return;
          }
          item.url=S+"/storage/v1/object/public/formulario-imagenes/"+path;
        }
      }
      items.push(item);
    }
  }
  if(!items.length){st.textContent="Agrega al menos una opción";st.style.color="#dc2626";return;}
  st.textContent="Guardando...";st.style.color="#2563eb";
  for(var j=0;j<items.length;j++){
    var it=items[j];
    var body={categoria:cat,nombre:it.nombre,titulo_grupo:tg,tipo:tipo,imagen_url:it.url||"",hex:it.hex||"",activo:true,orden_grupo:0};
    var r=await fetch(S+"/rest/v1/catalogo_materiales",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(body)});
    if(!r.ok){st.textContent="Error: "+r.status;st.style.color="#dc2626";return;}
  }
  st.textContent="✅ Ítem agregado";st.style.color="#16a34a";setTimeout(doRerun,700);
};
function renderNuevaCat(){
  var wrap=document.getElementById("items-list");if(!wrap)return;
  var html="";
  _items.forEach(function(item,idx){
    var tipos=[["imagen","\\ud83d\\uddbc\\ufe0f Imagen"],["color","\\ud83c\\udfa8 Color"],["select","\\ud83d\\udccb Lista"],["si_no","\\u2705 S\\u00ed/No"]];
    var tipoOpts="";
    tipos.forEach(function(t){
      tipoOpts+="<option value=\\""+t[0]+"\\""+(item.tipo===t[0]?" selected":"")+">"+t[1]+"</option>";
    });
    html+="<div class=\\"item-block\\">";
    html+="<div style=\\"display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;\\">";
    html+="<span style=\\"font-weight:700;font-size:12px;color:#1e3a5f;\\">\\u00cdTEM "+(idx+1)+"</span>";
    html+="<button onclick=\\"window.removeItem("+idx+")\\" class=\\"btn-del-sm\\">\\ud83d\\uddd1</button>";
    html+="</div>";
    html+="<div style=\\"margin-bottom:8px;\\"><label class=\\"field-label\\">T\\u00edtulo del grupo</label>";
    html+="<input type=\\"text\\" value=\\""+(item.titulo||"")+"\\" oninput=\\"window.updateItemTitulo("+idx+",this.value)\\" placeholder=\\"ej: Color de muros\\" class=\\"mini-input\\"></div>";
    html+="<div style=\\"display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;\\">";
    html+="<div><label class=\\"field-label\\">Tipo</label>";
    html+="<select onchange=\\"window.updateItemTipo("+idx+",this.value)\\" style=\\"width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;\\">"+tipoOpts+"</select></div>";
    if(item.tipo!=="si_no"){
      html+="<div><label class=\\"field-label\\">Cantidad</label>";
      html+="<input type=\\"number\\" value=\\""+item.cantidad+"\\" min=\\"1\\" max=\\"20\\" onchange=\\"window.updateItemCant("+idx+",parseInt(this.value)||1)\\" style=\\"width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;\\"></div>";
    }
    html+="</div>";
    if(item.tipo==="si_no"){
      html+="<div style=\\"font-size:11px;color:#64748b;padding:6px;background:#f8fafc;border-radius:5px;\\">Solo tendr\\u00e1 S\\u00ed y No.</div>";
    } else {
      for(var k=0;k<item.cantidad;k++){
        if(item.tipo==="color"){
          html+="<div style=\\"display:grid;grid-template-columns:1fr 44px 36px;gap:6px;margin-bottom:5px;align-items:center;\\">";
          html+="<input type=\\"text\\" id=\\"newcat-nom-"+idx+"-"+k+"\\" placeholder=\\"Nombre "+(k+1)+"\\" class=\\"mini-input\\">";
          html+="<input type=\\"color\\" id=\\"newcat-hex-"+idx+"-"+k+"\\" value=\\"#ffffff\\" style=\\"width:44px;height:34px;border-radius:4px;border:1px solid #cbd5e1;cursor:pointer;\\">";
          html+="<div style=\\"width:32px;height:32px;border-radius:50%;background:#ffffff;border:1px solid #e2e8f0;\\"></div></div>";
        } else if(item.tipo==="imagen"){
          html+="<div style=\\"display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:5px;align-items:center;\\">";
          html+="<input type=\\"text\\" id=\\"newcat-nom-"+idx+"-"+k+"\\" placeholder=\\"Nombre "+(k+1)+"\\" class=\\"mini-input\\">";
          html+="<input type=\\"file\\" id=\\"newcat-file-"+idx+"-"+k+"\\" accept=\\"image/*\\" style=\\"font-size:11px;\\"></div>";
        } else { // select
          html+="<input type=\\"text\\" id=\\"newcat-nom-"+idx+"-"+k+"\\" placeholder=\\"Opci\\u00f3n "+(k+1)+"\\" class=\\"mini-input\\" style=\\"margin-bottom:5px;\\">";
        }
      }
    }
    html+="</div>";
  });
  wrap.innerHTML=html;
}
function makeOpts(n){var o=[];for(var i=0;i<n;i++)o.push({nombre:"",hex:"#ffffff",file:null,previewUrl:"",url:""});return o;}
window.addItem=function(){_items.push({titulo:"",tipo:"imagen",cantidad:3,opciones:makeOpts(3)});renderNuevaCat();};
window.removeItem=function(idx){_items.splice(idx,1);renderNuevaCat();};
window.updateItemTitulo=function(idx,val){_items[idx].titulo=val;};
window.updateItemCant=function(idx,n){_items[idx].cantidad=Math.max(1,Math.min(20,n));renderNuevaCat();};
window.updateItemTipo=function(idx,val){_items[idx].tipo=val;_items[idx].opciones=makeOpts(_items[idx].cantidad);renderNuevaCat();};
window.guardarCategoria=async function(){
  var catNombre=document.getElementById("cat-nombre").value.trim();
  var st=document.getElementById("status");var btn=document.getElementById("save-btn");
  if(!catNombre){st.textContent="Escribe el nombre de la categor\\u00eda";st.style.color="#dc2626";return;}
  if(!_items.length){st.textContent="Agrega al menos un \\u00edtem";st.style.color="#dc2626";return;}
  btn.disabled=true;var total=0;
  try {
    for(var i=0;i<_items.length;i++){
      var item=_items[i];
      var titulo=(item.titulo||"").trim();
      if(!titulo){st.textContent="\\u00cdtem "+(i+1)+" necesita t\\u00edtulo de grupo";st.style.color="#dc2626";btn.disabled=false;return;}
      var opts=[];
      if(item.tipo==="si_no"){
        opts=[{nombre:"S\\u00ed",hex:"",url:""},{nombre:"No",hex:"",url:""}];
      } else {
        for(var j=0;j<item.cantidad;j++){
          var nomEl=document.getElementById("newcat-nom-"+i+"-"+j);
          if(!nomEl||!nomEl.value.trim())continue;
          var op={nombre:nomEl.value.trim(),hex:"",url:""};
          if(item.tipo==="color"){
            var hexEl=document.getElementById("newcat-hex-"+i+"-"+j);
            op.hex=hexEl?hexEl.value:"#ffffff";
          } else if(item.tipo==="imagen"){
            var fEl=document.getElementById("newcat-file-"+i+"-"+j);
            if(fEl&&fEl.files[0]){
              st.textContent="Subiendo imagen \\u00edtem "+(i+1)+", opci\\u00f3n "+(j+1)+"...";st.style.color="#2563eb";
              var file=fEl.files[0];
              var ext=(file.name.split(".").pop()||"png").toLowerCase().replace(/[^a-z0-9]/g,"");
              var path="catalogo/"+Date.now()+"_"+Math.random().toString(36).substring(2,7)+"."+ext;
              var ur=await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":file.type||"image/png","x-upsert":"true"},body:file});
              if(!ur.ok){var et1=await ur.text();st.textContent="Error subiendo imagen ("+ur.status+"): "+et1.substring(0,80);st.style.color="#dc2626";btn.disabled=false;return;}
              op.url=S+"/storage/v1/object/public/formulario-imagenes/"+path;
            }
          }
          opts.push(op);
        }
      }
      if(!opts.length){st.textContent="\\u00cdtem "+(i+1)+" sin opciones v\\u00e1lidas";st.style.color="#dc2626";btn.disabled=false;return;}
      for(var p=0;p<opts.length;p++){
        var o=opts[p];
        var body={categoria:catNombre,nombre:o.nombre,titulo_grupo:titulo,tipo:item.tipo,imagen_url:o.url||"",hex:o.hex||"",activo:true,orden_grupo:0};
        var r=await fetch(S+"/rest/v1/catalogo_materiales",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(body)});
        if(!r.ok){var et2=await r.text();st.textContent="Error guardando ("+r.status+"): "+et2.substring(0,80);st.style.color="#dc2626";btn.disabled=false;return;}total++;
      }
    }
    st.textContent="\\u2705 Categor\\u00eda creada con "+total+" \\u00edtems";st.style.color="#16a34a";setTimeout(doRerun,900);
  } catch(e){st.textContent="Error: "+e.message;st.style.color="#dc2626";btn.disabled=false;}
};
'''
    )

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>' + css + '</style></head><body>'
        + cat_html +
        '<div class="new-cat-box">'
        '<div class="new-cat-title">+ Agregar nueva categor&#237;a</div>'
        '<div style="margin-bottom:12px;">'
        '<label class="field-label">Nombre de la categor&#237;a</label>'
        '<input type="text" id="cat-nombre" placeholder="ej: Muros, Ba&#241;o, Pisos..." style="width:100%;padding:7px 10px;border:1.5px solid #0f3460;border-radius:6px;font-size:13px;box-sizing:border-box;">'
        '</div>'
        '<div id="items-list"></div>'
        '<div style="display:flex;gap:8px;margin-top:10px;">'
        '<button onclick="window.addItem()" class="btn-success" style="flex:1;padding:10px;">+ Agregar &#237;tem</button>'
        '<button id="save-btn" onclick="window.guardarCategoria()" class="btn-save-cat" style="flex:1;padding:10px;">&#128190; Guardar categor&#237;a</button>'
        '</div>'
        '<div id="status" style="margin-top:8px;font-size:12px;font-weight:600;min-height:18px;"></div>'
        '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html
