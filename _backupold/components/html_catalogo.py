"""
Genera el HTML del panel de administracion del catalogo de materiales.
"""
import json


def _build_items_rows(tipo: str, cantidad: int) -> str:
    """Genera filas HTML de opciones para el formulario de nuevo item."""
    rows = ''
    if tipo == 'si_no':
        rows = '<p style="color:#64748b;font-size:12px;padding:6px;">Solo tendrá opciones Sí / No.</p>'
    elif tipo == 'select':
        rows = '<div style="font-weight:700;font-size:11px;color:#64748b;margin-bottom:6px;">OPCIONES</div>'
        for i in range(cantidad):
            rows += '<div style="margin-bottom:6px;"><input type="text" id="item-nombre-' + str(i) + '" placeholder="Opción ' + str(i+1) + '" style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;box-sizing:border-box;"></div>'
    elif tipo == 'color':
        rows = '<div style="font-weight:700;font-size:11px;color:#64748b;margin-bottom:6px;">COLORES</div>'
        for i in range(cantidad):
            rows += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px;padding:6px;background:#f8fafc;border-radius:7px;border:1px solid #e2e8f0;align-items:center;">'
            rows += '<input type="text" id="item-nombre-' + str(i) + '" placeholder="Nombre color ' + str(i+1) + '" style="padding:5px 7px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;">'
            rows += '<div style="display:flex;align-items:center;gap:8px;">'
            rows += '<input type="color" id="item-hex-' + str(i) + '" value="#ffffff" style="width:50px;height:36px;border-radius:6px;cursor:pointer;" oninput="document.getElementById(\'prev-' + str(i) + '\').style.background=this.value">'
            rows += '<div id="prev-' + str(i) + '" style="width:36px;height:36px;border-radius:50%;background:#fff;border:2px solid #e2e8f0;"></div>'
            rows += '</div></div>'
    else:
        rows = '<div style="font-weight:700;font-size:11px;color:#64748b;margin-bottom:8px;">IMÁGENES</div>'
        for i in range(cantidad):
            rows += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px;padding:8px;background:#f8fafc;border-radius:7px;border:1px solid #e2e8f0;">'
            rows += '<input type="text" id="item-nombre-' + str(i) + '" placeholder="Nombre opción ' + str(i+1) + '" style="padding:6px 8px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;width:100%;box-sizing:border-box;">'
            rows += '<div><input type="file" id="item-file-' + str(i) + '" accept="image/*" onchange="window.catPreview(' + str(i) + ')" style="font-size:11px;width:100%;"><div id="imgprev-' + str(i) + '" style="margin-top:4px;"></div></div>'
            rows += '</div>'
    return rows


def build_catalogo_html(cat_items, supa_url, supa_key, tipo='imagen', cantidad=4):
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

    all_cats       = sorted(grupos.keys())
    all_cats_json  = json.dumps(all_cats, ensure_ascii=False)
    cat_items_json = json.dumps(cat_items, ensure_ascii=True)

    cat_html = ''
    for cat in all_cats:
        subgrupos = grupos[cat]
        total     = sum(len(v) for v in subgrupos.values())

        cat_html += '<div class="cat-block" id="catblock-' + cat + '">'
        cat_html += '<div class="cat-header">'
        cat_html += '<span class="cat-title">' + cat + '</span>'
        cat_html += '<div style="display:flex;gap:6px;align-items:center;">'
        cat_html += '<span style="font-size:11px;opacity:0.7;">' + str(total) + ' ítems</span>'
        cat_html += '<button onclick="window.toggleEdit(\'' + cat + '\')" class="btn-edit" id="btn-edit-' + cat + '">✏️ Editar</button>'
        cat_html += '<button onclick="window.eliminarCategoria(\'' + cat + '\')" class="btn-del-cat">🗑</button>'
        cat_html += '</div></div>'

        cat_html += '<div id="preview-' + cat + '" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(80px,1fr));gap:4px;margin-top:6px;">'
        for tg, items in sorted(subgrupos.items()):
            for it in items:
                iurl  = it.get('imagen_url') or ''
                itipo = it.get('tipo','imagen')
                badge = {'imagen':'🖼','color':'🎨','select':'📋','si_no':'✅'}.get(itipo,'❓')
                if iurl:
                    preview = '<img src="' + iurl + '" style="width:100%;height:55px;object-fit:cover;display:block;">'
                elif it.get('hex'):
                    preview = '<div style="width:100%;height:55px;background:' + it['hex'] + ';"></div>'
                else:
                    preview = '<div style="width:100%;height:55px;background:#f1f5f9;display:flex;align-items:center;justify-content:center;font-size:1rem;">📦</div>'
                cat_html += '<div style="background:white;border:1px solid #e2e8f0;border-radius:6px;overflow:hidden;">'
                cat_html += preview
                cat_html += '<div style="font-size:9px;font-weight:700;padding:2px 4px;display:flex;justify-content:space-between;">'
                cat_html += '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + it.get('nombre','') + '</span>'
                cat_html += '<span>' + badge + '</span></div></div>'
        cat_html += '</div>'

        cat_html += '<div id="edit-' + cat + '" style="display:none;margin-top:10px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:14px;">'
        cat_html += '<div style="display:flex;gap:8px;margin-bottom:14px;align-items:flex-end;padding-bottom:12px;border-bottom:1px solid #e2e8f0;">'
        cat_html += '<div style="flex:1"><label class="field-label">Nombre de categoría</label>'
        cat_html += '<input id="rename-' + cat + '" type="text" value="' + cat + '" class="mini-input"></div>'
        cat_html += '<button onclick="window.renombrarCategoria(\'' + cat + '\')" class="btn-primary">Renombrar</button>'
        cat_html += '<div id="rename-st-' + cat + '" style="font-size:11px;font-weight:600;align-self:center;min-width:40px;"></div>'
        cat_html += '</div>'

        for tg, items in sorted(subgrupos.items(), key=lambda x: orden_grupos.get(cat, {}).get(x[0], 0)):
            tg_display = tg
            tg_id      = tg.replace(' ','_').replace("'","").replace('(','').replace(')','')[:30]
            itipo      = items[0].get('tipo','imagen') if items else 'imagen'
            badge      = {'imagen':'🖼','color':'🎨','select':'📋','si_no':'✅'}.get(itipo,'❓')
            ids_json   = json.dumps([str(it['id']) for it in items])

            cat_html += '<div class="subgroup-block" id="sg-' + cat + '-' + tg_id + '">'
            cat_html += '<div class="subgroup-header">'
            _orden_val = str(orden_grupos.get(cat, {}).get(tg, 0))
            cat_html += '<div style="display:flex;align-items:center;gap:8px;flex:1;">'
            cat_html += '<div style="display:flex;flex-direction:column;align-items:center;gap:1px;">'
            cat_html += '<span style="font-size:9px;color:#94a3b8;font-weight:700;">ORDEN</span>'
            cat_html += '<input type="number" value="' + _orden_val + '" id="tg-orden-' + cat + '-' + tg_id + '" min="0" max="99" style="width:48px;padding:3px 5px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;font-weight:700;text-align:center;">'
            cat_html += '</div>'
            cat_html += '<span style="font-size:13px;">' + badge + '</span>'
            cat_html += '<input type="text" value="' + tg_display + '" id="tg-rename-' + cat + '-' + tg_id + '" class="mini-input" style="max-width:180px;font-weight:700;" placeholder="Nombre del ítem">'
            cat_html += '<span style="font-size:10px;color:#94a3b8;">(' + str(len(items)) + ')</span>'
            cat_html += '</div>'
            cat_html += '<div style="display:flex;gap:4px;">'
            cat_html += '<button onclick="window.renombrarGrupo(\'' + cat + '\',\'' + tg.replace("'","\\'") + '\',\'' + tg_id + '\')" class="btn-save-sm" title="Guardar nombre y orden">💾 Guardar</button>'
            cat_html += '<button onclick="window.showClonar(\'' + cat + '\',\'' + tg_id + '\')" class="btn-clone">📋 Clonar</button>'
            cat_html += '<button onclick="window.eliminarGrupo(\'' + cat + '\',\'' + tg.replace("'","\\'") + '\',' + ids_json + ')" class="btn-del-sm">🗑</button>'
            cat_html += '</div></div>'

            cat_html += '<div id="clone-panel-' + cat + '-' + tg_id + '" style="display:none;background:#eff6ff;border:1px solid #93c5fd;border-radius:6px;padding:8px;margin:6px 0;">'
            cat_html += '<div style="font-size:11px;font-weight:700;color:#1e3a5f;margin-bottom:6px;">Clonar "' + tg_display + '" a categoría:</div>'
            cat_html += '<div style="display:flex;gap:6px;align-items:center;">'
            cat_html += '<select id="clone-dest-' + cat + '-' + tg_id + '" style="flex:1;padding:5px 8px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;">'
            for other_cat in all_cats:
                if other_cat != cat:
                    cat_html += '<option value="' + other_cat + '">' + other_cat + '</option>'
            cat_html += '</select>'
            cat_html += '<button onclick="window.confirmarClonar(\'' + cat + '\',\'' + tg.replace("'","\\'") + '\',\'' + tg_id + '\')" class="btn-primary">✅ Clonar</button>'
            cat_html += '<button onclick="document.getElementById(\'clone-panel-' + cat + '-' + tg_id + '\').style.display=\'none\'" class="btn-cancel">✕</button>'
            cat_html += '</div>'
            cat_html += '<div id="clone-st-' + cat + '-' + tg_id + '" style="font-size:11px;font-weight:600;margin-top:4px;"></div>'
            cat_html += '</div>'

            cat_html += '<div style="display:flex;flex-direction:column;gap:4px;margin-top:8px;">'
            for it in items:
                iid  = str(it.get('id',''))
                iurl = it.get('imagen_url') or ''
                ihex = it.get('hex') or ''
                if iurl:
                    thumb = '<img src="' + iurl + '" style="width:34px;height:34px;object-fit:cover;border-radius:4px;flex-shrink:0;">'
                elif ihex:
                    thumb = '<div style="width:34px;height:34px;background:' + ihex + ';border-radius:50%;border:1px solid #e2e8f0;flex-shrink:0;"></div>'
                else:
                    thumb = '<div style="width:34px;height:34px;background:#f1f5f9;border-radius:4px;display:flex;align-items:center;justify-content:center;flex-shrink:0;font-size:0.9rem;">📦</div>'
                cat_html += '<div style="display:flex;align-items:center;gap:8px;background:white;border:1px solid #e2e8f0;border-radius:6px;padding:5px 8px;">'
                cat_html += thumb
                cat_html += '<input type="text" value="' + it.get('nombre','').replace('"','') + '" id="item-name-' + iid + '" class="mini-input" style="flex:1;">'
                cat_html += '<button onclick="window.renombrarItem(\'' + iid + '\')" class="btn-save-sm" title="Guardar nombre">💾</button>'
                cat_html += '<button onclick="window.catEliminar(\'' + iid + '\',\'' + iurl + '\')" class="btn-del-xs">🗑</button>'
                cat_html += '</div>'
            cat_html += '</div>'
            cat_html += '</div>'

        cat_html += '<div style="margin-top:14px;border-top:1px solid #e2e8f0;padding-top:12px;">'
        cat_html += '<div style="font-weight:700;font-size:11px;color:#64748b;margin-bottom:8px;text-transform:uppercase;">Agregar nuevo ítem a ' + cat + ':</div>'
        cat_html += '<div style="margin-bottom:8px;"><label class="field-label">Título del grupo</label>'
        cat_html += '<input id="new-tg-' + cat + '" type="text" placeholder="ej: Color de muros" class="mini-input"></div>'
        cat_html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;">'
        cat_html += '<div><label class="field-label">Tipo</label>'
        cat_html += '<select id="new-tipo-' + cat + '" onchange="window.renderAddForm(\'' + cat + '\')" style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;">'
        cat_html += '<option value="imagen">🖼 Imagen</option>'
        cat_html += '<option value="color">🎨 Color</option>'
        cat_html += '<option value="select">📋 Lista</option>'
        cat_html += '<option value="si_no">✅ Sí/No</option>'
        cat_html += '</select></div>'
        cat_html += '<div id="new-cant-wrap-' + cat + '"><label class="field-label">Cantidad</label>'
        cat_html += '<input type="number" id="new-cantidad-' + cat + '" value="3" min="1" max="20" onchange="window.renderAddForm(\'' + cat + '\')" style="width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;"></div>'
        cat_html += '</div>'
        cat_html += '<div id="new-opts-wrap-' + cat + '"></div>'
        cat_html += '</div>'
        cat_html += '<div style="display:flex;gap:8px;margin-top:10px;">'
        cat_html += '<button onclick="window.agregarItemCompleto(\'' + cat + '\')" class="btn-success" style="flex:1;padding:9px;">+ Agregar ítem</button>'
        cat_html += '<button onclick="window.toggleEdit(\'' + cat + '\')" class="btn-cancel" style="flex:1;padding:9px;">✕ Cancelar</button>'
        cat_html += '</div>'
        cat_html += '</div>'
        cat_html += '<div id="edit-status-' + cat + '" style="font-size:11px;font-weight:600;min-height:16px;margin-top:6px;"></div>'
        cat_html += '</div>'
        cat_html += '</div>'
        cat_html += '</div>'

    if not cat_html:
        cat_html = '<p style="color:#64748b;padding:8px 0;">El catálogo está vacío.</p>'

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
.mini-input{padding:5px 8px;border:1px solid #cbd5e1;border-radius:4px;font-size:12px;width:100%;box-sizing:border-box;}
.mini-prev{width:32px;height:32px;border-radius:4px;object-fit:cover;flex-shrink:0;}
'''

    js = '''
var S="''' + supa_url + '''",K="''' + supa_key + '''";
var ALL_CATS=''' + all_cats_json + ''';
var ALL_ITEMS=''' + cat_items_json + ''';
var _items=[];

function doRerun(){
  var u=new URL(window.parent.location.href);
  u.searchParams.set("cat_ts",Date.now());
  window.parent.history.replaceState({},"",u);
  window.parent.dispatchEvent(new PopStateEvent("popstate"));
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
  var el=document.getElementById("item-name-"+id);
  if(!el)return;var nuevo=el.value.trim();if(!nuevo)return;
  var r=await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({nombre:nuevo})});
  if(r.ok){el.style.borderColor="#16a34a";setTimeout(function(){el.style.borderColor="";},1200);}
  else alert("Error: "+r.status);
};

window.renombrarGrupo=async function(cat,tgOld,tgId){
  var el=document.getElementById("tg-rename-"+cat+"-"+tgId);
  if(!el)return;var nuevo=el.value.trim();if(!nuevo||nuevo===tgOld)return;
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

window.eliminarGrupo=async function(cat,tg,ids){
  if(!confirm("¿Eliminar todos los ítems del grupo \\""+tg+"\\"?"))return;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat&&(it.titulo_grupo||"(Sin grupo)")===tg;});
  for(var i=0;i<items.length;i++){
    var url=items[i].imagen_url||"";
    if(url){var path=url.split("/public/formulario-imagenes/")[1];if(path)await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"DELETE",headers:{"Authorization":"Bearer "+K,"apikey":K}});}
    await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+items[i].id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  }
  doRerun();
};

window.catEliminar=async function(id,url){
  if(!confirm("¿Eliminar este ítem?"))return;
  if(url){var path=url.split("/public/formulario-imagenes/")[1];if(path)await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"DELETE",headers:{"Authorization":"Bearer "+K,"apikey":K}});}
  await fetch(S+"/rest/v1/catalogo_materiales?id=eq."+id,{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  doRerun();
};

window.eliminarCategoria=async function(cat){
  if(!confirm("¿Eliminar toda la categoría "+cat+"?"))return;
  var items=ALL_ITEMS.filter(function(it){return it.categoria===cat;});
  for(var i=0;i<items.length;i++){
    var url=items[i].imagen_url||"";
    if(url){var path=url.split("/public/formulario-imagenes/")[1];if(path)await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"DELETE",headers:{"Authorization":"Bearer "+K,"apikey":K}});}
  }
  await fetch(S+"/rest/v1/catalogo_materiales?categoria=eq."+encodeURIComponent(cat),{method:"PATCH",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify({activo:false})});
  doRerun();
};

window.renderAddForm=function(cat){
  var tipo=document.getElementById("new-tipo-"+cat).value;
  var n=parseInt(document.getElementById("new-cantidad-"+cat).value)||3;
  var cantWrap=document.getElementById("new-cant-wrap-"+cat);
  if(cantWrap)cantWrap.style.display=tipo==="si_no"?"none":"block";
  var wrap=document.getElementById("new-opts-wrap-"+cat);
  if(!wrap)return;
  var html="";
  if(tipo==="si_no"){
    html="<div style='font-size:11px;color:#64748b;padding:6px;background:#f8fafc;border-radius:5px;'>Solo tendrá Sí y No.</div>";
  } else {
    for(var i=0;i<n;i++){
      if(tipo==="color"){
        html+="<div style='display:grid;grid-template-columns:1fr 44px 36px;gap:6px;margin-bottom:5px;align-items:center;'>";
        html+="<input type='text' id='nadd-nom-"+cat+"-"+i+"' placeholder='Nombre "+(i+1)+"' class='mini-input'>";
        html+="<input type='color' id='nadd-hex-"+cat+"-"+i+"' value='#ffffff' style='width:44px;height:34px;border-radius:4px;border:1px solid #cbd5e1;cursor:pointer;' oninput=\"var p=document.getElementById('nadd-prev-"+cat+"-"+i+"');if(p)p.style.background=this.value\">";
        html+="<div id='nadd-prev-"+cat+"-"+i+"' style='width:32px;height:32px;border-radius:50%;background:#ffffff;border:1px solid #e2e8f0;'></div>";
        html+="</div>";
      } else if(tipo==="imagen"){
        html+="<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:5px;align-items:center;'>";
        html+="<input type='text' id='nadd-nom-"+cat+"-"+i+"' placeholder='Nombre "+(i+1)+"' class='mini-input'>";
        html+="<input type='file' id='nadd-file-"+cat+"-"+i+"' accept='image/*' style='font-size:11px;'>";
        html+="</div>";
      } else {
        html+="<input type='text' id='nadd-nom-"+cat+"-"+i+"' placeholder='Opción "+(i+1)+"' class='mini-input' style='margin-bottom:5px;'>";
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
  if(tipo==="si_no"){
    items=[{nombre:"Sí",hex:"",url:""},{nombre:"No",hex:"",url:""}];
  } else {
    for(var i=0;i<n;i++){
      var nomEl=document.getElementById("nadd-nom-"+cat+"-"+i);
      if(!nomEl||!nomEl.value.trim())continue;
      var item={nombre:nomEl.value.trim(),hex:"",url:""};
      if(tipo==="color"){item.hex=document.getElementById("nadd-hex-"+cat+"-"+i).value;}
      else if(tipo==="imagen"){
        var fEl=document.getElementById("nadd-file-"+cat+"-"+i);
        if(fEl&&fEl.files[0]){
          st.textContent="Subiendo imagen "+(i+1)+"...";st.style.color="#2563eb";
          var file=fEl.files[0],ext=file.name.split(".").pop();
          var path="catalogo/"+Date.now()+"_"+Math.random().toString(36).substr(2,5)+"."+ext;
          var ur=await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":file.type,"x-upsert":"true"},body:file});
          if(!ur.ok){st.textContent="Error subiendo";st.style.color="#dc2626";return;}
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
  st.textContent="✅ Ítem agregado";st.style.color="#16a34a";
  setTimeout(doRerun,700);
};

function makeOpts(n){var o=[];for(var i=0;i<n;i++)o.push({nombre:"",hex:"#ffffff",file:null,previewUrl:"",url:""});return o;}
window.addItem=function(){_items.push({titulo:"",tipo:"imagen",cantidad:3,opciones:makeOpts(3)});renderNuevaCat();};
window.removeItem=function(idx){_items.splice(idx,1);renderNuevaCat();};
window.updateItemTitulo=function(idx,val){_items[idx].titulo=val;};
window.updateItemTipo=function(idx,val){_items[idx].tipo=val;_items[idx].opciones=makeOpts(_items[idx].cantidad);renderNuevaCat();};
window.updateItemCantidad=function(idx,val){
  var n=Math.max(1,Math.min(20,parseInt(val)||1));_items[idx].cantidad=n;
  var o=[];for(var i=0;i<n;i++){var e=_items[idx].opciones[i]||{};o.push({nombre:e.nombre||"",hex:e.hex||"#ffffff",file:e.file||null,previewUrl:e.previewUrl||"",url:e.url||""});}
  _items[idx].opciones=o;renderNuevaCat();
};
window.updateOptNombre=function(idx,oi,val){_items[idx].opciones[oi].nombre=val;};
window.updateOptHex=function(idx,oi,val){_items[idx].opciones[oi].hex=val;var el=document.getElementById("clrprev-"+idx+"-"+oi);if(el)el.style.background=val;};
window.updateOptFile=function(idx,oi,input){
  if(!input.files[0])return;_items[idx].opciones[oi].file=input.files[0];
  var r=new FileReader();r.onload=function(e){_items[idx].opciones[oi].previewUrl=e.target.result;renderNuevaCat();};r.readAsDataURL(input.files[0]);
};

function renderNuevaCat(){
  var wrap=document.getElementById("items-list");
  if(!wrap)return;
  var html="";
  _items.forEach(function(item,idx){
    html+="<div class='item-block'><div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>";
    html+="<span style='font-weight:700;font-size:12px;color:#1e3a5f;'>ÍTEM "+(idx+1)+"</span>";
    html+="<button onclick='window.removeItem("+idx+")' class='btn-del-sm'>🗑</button></div>";
    html+="<div style='margin-bottom:8px;'><label class='field-label'>Título del grupo</label>";
    html+="<input type='text' value='"+item.titulo+"' onchange='window.updateItemTitulo("+idx+",this.value)' placeholder='ej: Color de muros' class='mini-input'></div>";
    html+="<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px;'><div><label class='field-label'>Tipo</label>";
    html+="<select onchange='window.updateItemTipo("+idx+",this.value)' style='width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;'>";
    [["imagen","🖼 Imagen"],["color","🎨 Color"],["select","📋 Lista"],["si_no","✅ Sí/No"]].forEach(function(t){
      html+="<option value='"+t[0]+"'"+(item.tipo===t[0]?" selected":"")+">"+t[1]+"</option>";
    });
    html+="</select></div>";
    if(item.tipo!=="si_no"){
      html+="<div><label class='field-label'>Cantidad</label><input type='number' value='"+item.cantidad+"' min='1' max='20' onchange='window.updateItemCantidad("+idx+",this.value)' style='width:100%;padding:6px 9px;border:1px solid #cbd5e1;border-radius:5px;font-size:12px;'></div>";
    }
    html+="</div>";
    if(item.tipo==="si_no"){
      html+="<div style='font-size:11px;color:#64748b;padding:4px 0;background:#f8fafc;border-radius:5px;padding:6px;'>Solo tendrá Sí y No.</div>";
    } else {
      item.opciones.forEach(function(opt,oi){
        if(item.tipo==="color"){
          html+="<div style='display:grid;grid-template-columns:1fr 44px 36px;gap:6px;margin-bottom:5px;align-items:center;'>";
          html+="<input type='text' value='"+opt.nombre+"' onchange='window.updateOptNombre("+idx+","+oi+",this.value)' placeholder='Nombre "+(oi+1)+"' class='mini-input'>";
          html+="<input type='color' value='"+(opt.hex||"#ffffff")+"' onchange='window.updateOptHex("+idx+","+oi+",this.value)' style='width:44px;height:34px;border-radius:4px;border:1px solid #cbd5e1;cursor:pointer;'>";
          html+="<div style='width:32px;height:32px;border-radius:50%;background:"+(opt.hex||"#ffffff")+";border:1px solid #e2e8f0;' id='clrprev-"+idx+"-"+oi+"'></div></div>";
        } else if(item.tipo==="imagen"){
          html+="<div style='display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:5px;align-items:center;'>";
          html+="<input type='text' value='"+opt.nombre+"' onchange='window.updateOptNombre("+idx+","+oi+",this.value)' placeholder='Nombre "+(oi+1)+"' class='mini-input'>";
          html+="<div style='display:flex;align-items:center;gap:4px;'><input type='file' accept='image/*' onchange='window.updateOptFile("+idx+","+oi+",this)' style='font-size:10px;max-width:150px;'>";
          if(opt.previewUrl)html+="<img src='"+opt.previewUrl+"' class='mini-prev'>";
          html+="</div></div>";
        } else {
          html+="<input type='text' value='"+opt.nombre+"' onchange='window.updateOptNombre("+idx+","+oi+",this.value)' placeholder='Opción "+(oi+1)+"' class='mini-input' style='margin-bottom:5px;'>";
        }
      });
    }
    html+="</div>";
  });
  wrap.innerHTML=html;
}

window.guardarCategoria=async function(){
  var catNombre=document.getElementById("cat-nombre").value.trim();
  var st=document.getElementById("status");var btn=document.getElementById("save-btn");
  if(!catNombre){st.textContent="Escribe el nombre";st.style.color="#dc2626";return;}
  if(!_items.length){st.textContent="Agrega al menos un ítem";st.style.color="#dc2626";return;}
  btn.disabled=true;var total=0;
  for(var i=0;i<_items.length;i++){
    var item=_items[i];
    if(item.tipo==="si_no"){
      for(var sv of["Sí","No"]){
        var body={categoria:catNombre,nombre:sv,titulo_grupo:item.titulo,tipo:"si_no",imagen_url:"",hex:"",activo:true};
        var r=await fetch(S+"/rest/v1/catalogo_materiales",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(body)});
        if(!r.ok){st.textContent="Error guardando";st.style.color="#dc2626";btn.disabled=false;return;}total++;
      }
    } else {
      for(var oi=0;oi<item.opciones.length;oi++){
        var opt=item.opciones[oi];if(!opt.nombre.trim())continue;
        var body={categoria:catNombre,nombre:opt.nombre.trim(),titulo_grupo:item.titulo,tipo:item.tipo,imagen_url:"",hex:"",activo:true};
        if(item.tipo==="color")body.hex=opt.hex;
        else if(item.tipo==="imagen"&&opt.file){
          st.textContent="Subiendo "+(total+1)+"...";st.style.color="#2563eb";
          var ext=opt.file.name.split(".").pop();
          var path="catalogo/"+Date.now()+"_"+Math.random().toString(36).substr(2,5)+"."+ext;
          var ur=await fetch(S+"/storage/v1/object/formulario-imagenes/"+path,{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":opt.file.type,"x-upsert":"true"},body:opt.file});
          if(!ur.ok){st.textContent="Error subiendo";st.style.color="#dc2626";btn.disabled=false;return;}
          body.imagen_url=S+"/storage/v1/object/public/formulario-imagenes/"+path;
        }
        var r=await fetch(S+"/rest/v1/catalogo_materiales",{method:"POST",headers:{"Authorization":"Bearer "+K,"apikey":K,"Content-Type":"application/json","Prefer":"return=minimal"},body:JSON.stringify(body)});
        if(!r.ok){st.textContent="Error guardando";st.style.color="#dc2626";btn.disabled=false;return;}total++;
      }
    }
  }
  st.textContent="✅ Guardado con "+total+" ítems";st.style.color="#16a34a";setTimeout(doRerun,900);
};
'''

    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<style>' + css + '</style></head><body>'
        + cat_html +
        '<div class="new-cat-box">'
        '<div class="new-cat-title">+ Agregar nueva categoría</div>'
        '<div style="margin-bottom:12px;">'
        '<label class="field-label">Nombre de la categoría</label>'
        '<input type="text" id="cat-nombre" placeholder="ej: Muros, Baño, Pisos..." style="width:100%;padding:7px 10px;border:1.5px solid #0f3460;border-radius:6px;font-size:13px;box-sizing:border-box;">'
        '</div>'
        '<div id="items-list"></div>'
        '<div style="display:flex;gap:8px;margin-top:10px;">'
        '<button onclick="window.addItem()" class="btn-success" style="flex:1;padding:10px;">+ Agregar ítem</button>'
        '<button id="save-btn" onclick="window.guardarCategoria()" class="btn-save-cat" style="flex:1;padding:10px;">💾 Guardar categoría</button>'
        '</div>'
        '<div id="status" style="margin-top:8px;font-size:12px;font-weight:600;min-height:18px;"></div>'
        '</div>'
        '<script>' + js + '</script>'
        '</body></html>'
    )
    return html
