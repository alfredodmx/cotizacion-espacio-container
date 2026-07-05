"""
Funciones de operaciones: tabla RC, balance Excel/PDF, HTML builder.
Extraídas de app.py para la arquitectura modular.
"""

# ── Iconos SVG inline para el iframe del formulario (reemplazan emoticones) ──
_RC_ICONS = {
    "paperclip": '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
    "store":     '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M2 7h20"/><path d="M18 12v.01"/><path d="M6 12v.01"/>',
    "cart":      '<circle cx="8" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12"/>',
    "calendar":  '<rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/>',
    "clipboard": '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>',
    "note":      '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"/>',
    "save":      '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "x":         '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "check":     '<path d="M20 6 9 17l-5-5"/>',
    "file":      '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
    "user":      '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "trend-up":  '<polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/>',
    "trend-down":'<polyline points="22 17 13.5 8.5 8.5 13.5 2 7"/><polyline points="16 17 22 17 22 11"/>',
    "edit":      '<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4Z"/>',
    "trash":     '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    "chevron":   '<polyline points="6 9 12 15 18 9"/>',
    "alert":     '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" x2="12" y1="9" y2="13"/><line x1="12" x2="12.01" y1="17" y2="17"/>',
}


def _svg_rc(name, color="currentColor", size=14, mr=6, valign=-2, sw=2):
    """SVG inline para el iframe del formulario RC."""
    inner = _RC_ICONS.get(name, "")
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
        f'stroke-linejoin="round" style="vertical-align:{valign}px;margin-right:{mr}px;flex-shrink:0;">'
        f'{inner}</svg>'
    )


def build_historial_rc_html(regs, ep='', supa_url='', supa_key=''):
    """Historial de compras interactivo (iframe): tarjetas con la tabla en HTML
    que entra en modo edición IN-PLACE (las celdas se vuelven inputs, sin crear
    otra tabla). Editar/Eliminar del REGISTRO van SERVER-SIDE vía query param +
    popstate: ?rc_edit=<json> / ?rc_delete=<id>; Python aplica con la service key
    (RLS-safe) y recalcula los totales. La ÚNICA operación con la anon key es
    reemplazar el archivo de factura (subida al bucket de storage 'facturas',
    igual que el formulario de nueva compra); la URL resultante va en el payload
    server-side y Python valida que pertenezca a ese bucket."""
    import json as _json
    regs_json = _json.dumps(regs or [], ensure_ascii=False).replace('<', '\\u003c')
    IC_STORE = _svg_rc('store', color='#475569', size=17, mr=0)
    IC_CAL   = _svg_rc('calendar', color='#94a3b8', size=12, mr=5)
    IC_USER  = _svg_rc('user', color='#94a3b8', size=12, mr=5)
    IC_CART  = _svg_rc('cart', color='#94a3b8', size=12, mr=5)
    IC_FILE  = _svg_rc('file', color='#1d4ed8', size=15, mr=0)
    IC_EDIT  = _svg_rc('edit', color='#1d4ed8', size=14, mr=6)
    IC_TRASH = _svg_rc('trash', color='#dc2626', size=14, mr=6)
    IC_SAVE  = _svg_rc('save', color='#ffffff', size=14, mr=7)
    IC_X     = _svg_rc('x', color='#475569', size=13, mr=6)
    IC_CHEV  = _svg_rc('chevron', color='#94a3b8', size=16, mr=0)
    IC_UP    = _svg_rc('trend-up', color='#dc2626', size=13, mr=5)
    IC_DOWN  = _svg_rc('trend-down', color='#16a34a', size=13, mr=5)
    IC_ALERT = _svg_rc('alert', color='#dc2626', size=14, mr=7)
    IC_CLIP  = _svg_rc('paperclip', color='#1d4ed8', size=14, mr=7)

    return f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800&display=swap');
*{{box-sizing:border-box}}
html,body{{margin:0;padding:0;font-family:Montserrat,'Segoe UI',sans-serif;background:transparent}}
.hc-wrap{{display:flex;flex-direction:column;gap:9px;}}
.hc{{border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;background:#fff;box-shadow:0 1px 3px rgba(15,23,42,0.06);}}
.hc.editing{{border-color:#93c5fd;box-shadow:0 4px 16px rgba(37,99,235,0.16);}}
.hc>summary{{list-style:none;cursor:pointer;display:flex;align-items:center;padding:12px 15px;background:#f8fafc;}}
.hc.editing>summary{{background:#eff6ff;}}
.hc>summary::-webkit-details-marker{{display:none}}
.hc[open]>summary{{border-bottom:1px solid #e2e8f0;}}
.hc-lugar{{font-weight:700;font-size:0.84rem;color:#0f172a;margin-left:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:45%;}}
.hc-badge{{margin-left:auto;display:inline-flex;align-items:center;font-weight:700;font-size:0.75rem;padding:4px 12px;border-radius:99px;white-space:nowrap;}}
.hc-chev{{margin-left:12px;transition:transform .2s;flex-shrink:0;}}
.hc[open] .hc-chev{{transform:rotate(180deg);}}
.hc-body{{padding:13px 15px;}}
.hc-meta{{display:flex;flex-wrap:wrap;gap:16px;font-size:0.72rem;color:#64748b;margin-bottom:11px;}}
.hc-meta span{{display:inline-flex;align-items:center;}}
.hc-tblwrap{{overflow-x:auto;border-radius:9px;border:1px solid #eef2f7;}}
.hc-tbl{{width:100%;border-collapse:collapse;font-size:0.79rem;min-width:520px;}}
.hc-tbl th{{background:#1e2447;color:#fff;text-align:left;padding:7px 11px;font-size:0.62rem;letter-spacing:.05em;text-transform:uppercase;font-weight:700;white-space:nowrap;}}
.hc-tbl th.r,.hc-tbl td.r{{text-align:right;}}
.hc-tbl th.c,.hc-tbl td.c{{text-align:center;}}
.hc-tbl td{{padding:7px 11px;border-bottom:1px solid #eef2f7;color:#475569;white-space:nowrap;}}
.hc-tbl tbody tr:last-child td{{border-bottom:none;}}
.hc-tbl tbody tr:nth-child(even){{background:#f8fafc;}}
.hc-tbl .it{{font-weight:600;color:#0f172a;white-space:normal;}}
.hc-inp{{width:92px;border:1.5px solid #cbd5e1;border-radius:6px;padding:5px 7px;font-size:0.78rem;text-align:right;font-family:inherit;outline:none;background:#fff;}}
.hc-inp:focus{{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.18);}}
.hc-rm{{width:17px;height:17px;cursor:pointer;accent-color:#dc2626;}}
tr.rm-on td{{background:#fef2f2 !important;text-decoration:line-through;color:#b91c1c;opacity:.65;}}
.hc-tots{{display:flex;flex-wrap:wrap;gap:18px;margin-top:12px;font-size:0.75rem;color:#64748b;}}
.hc-tots b{{color:#0f172a;font-weight:700;margin-left:4px;}}
.hc-obs{{display:flex;align-items:flex-start;margin-top:10px;font-size:0.74rem;color:#64748b;background:#f8fafc;border-radius:8px;padding:8px 11px;}}
.hc-fac{{display:inline-flex;align-items:center;gap:2px;margin-top:11px;padding:7px 14px;background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;border-radius:8px;text-decoration:none;font-size:0.78rem;font-weight:600;}}
.hc-nofac{{display:inline-flex;align-items:center;margin-top:11px;font-size:0.74rem;color:#94a3b8;}}
.hc-editfields{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:9px;margin-bottom:12px;}}
.hc-fld label{{display:block;font-size:0.62rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#64748b;margin-bottom:4px;}}
.hc-fld input{{width:100%;border:1.5px solid #cbd5e1;border-radius:7px;padding:7px 10px;font-size:0.8rem;font-family:inherit;outline:none;}}
.hc-fld input:focus{{border-color:#2563eb;box-shadow:0 0 0 2px rgba(37,99,235,.18);}}
.hc-hint{{font-size:0.72rem;color:#475569;margin-top:10px;background:#eff6ff;border-left:3px solid #93c5fd;border-radius:0 6px 6px 0;padding:8px 11px;}}
.hc-actions{{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;}}
.hc-btn{{display:inline-flex;align-items:center;justify-content:center;border:none;border-radius:8px;padding:8px 16px;font-size:0.78rem;font-weight:700;font-family:inherit;cursor:pointer;transition:filter .12s;}}
.hc-btn:hover{{filter:brightness(0.96);}}
.hc-edit{{background:#eff6ff;color:#1d4ed8;border:1px solid #bfdbfe;}}
.hc-del{{background:#fef2f2;color:#dc2626;border:1px solid #fecaca;}}
.hc-save{{background:#2563eb;color:#fff;}}
.hc-cancel{{background:#f1f5f9;color:#475569;border:1px solid #e2e8f0;}}
.hc-confirm{{margin-top:11px;background:#fef2f2;border:1px solid #fecaca;border-left:4px solid #dc2626;border-radius:8px;padding:10px 13px;font-size:0.78rem;color:#991b1b;display:flex;align-items:center;flex-wrap:wrap;gap:10px;}}
.hc-facedit{{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:11px;}}
.hc-facbtn{{display:inline-flex;align-items:center;background:#eff6ff;color:#1d4ed8;border:1px dashed #93c5fd;border-radius:8px;padding:7px 14px;font-size:0.78rem;font-weight:600;cursor:pointer;}}
.hc-facbtn:hover{{background:#dbeafe;}}
.hc-tipo{{display:inline-flex;align-items:center;margin-left:10px;font-weight:700;font-size:0.64rem;letter-spacing:.02em;text-transform:uppercase;padding:3px 10px;border-radius:99px;white-space:nowrap;}}
.hc-tipodot{{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:6px;flex-shrink:0;}}
.hc-inp-c{{width:74px;}}
.hc-filters{{display:flex;flex-wrap:wrap;align-items:center;gap:7px;margin-bottom:11px;}}
.hc-flabel{{font-size:0.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:#94a3b8;margin-right:2px;}}
.hc-fbadge{{display:inline-flex;align-items:center;font-size:0.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.02em;padding:5px 12px;border-radius:99px;border:1.5px solid #e2e8f0;background:#fff;color:#64748b;cursor:pointer;transition:all .12s;white-space:nowrap;}}
.hc-fbadge:hover{{border-color:#cbd5e1;background:#f8fafc;}}
.hc-fbadge.active{{border-color:#1e2447;background:#1e2447;color:#fff;}}
</style>
<div class="hc-filters" id="hc-filters"></div>
<div class="hc-wrap" id="hc-wrap"></div>
<script>
var REGS={regs_json};
var IC={{store:'{IC_STORE}',cal:'{IC_CAL}',user:'{IC_USER}',cart:'{IC_CART}',file:'{IC_FILE}',edit:'{IC_EDIT}',trash:'{IC_TRASH}',save:'{IC_SAVE}',x:'{IC_X}',chev:'{IC_CHEV}',up:'{IC_UP}',down:'{IC_DOWN}',alert:'{IC_ALERT}',clip:'{IC_CLIP}'}};
var EP="{ep}";var SUPA_URL="{supa_url}";var SUPA_KEY="{supa_key}";
var editing=-1, confirming=-1, _facFile=null, filter="";
function f(n){{return "$"+Math.round(Math.abs(+n||0)).toLocaleString("de-DE");}}
function esc(s){{return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}}
function nav(param,val){{
  var url=new URL(window.parent.location.href);
  url.searchParams.set(param,val);
  window.parent.history.replaceState({{}},"",url);
  window.parent.dispatchEvent(new PopStateEvent("popstate"));
}}
window.hcEdit=function(i){{_facFile=null;editing=(editing===i?-1:i);confirming=-1;render();}};
window.hcCancel=function(){{_facFile=null;editing=-1;render();}};
window.hcFilter=function(lbl){{filter=lbl;editing=-1;confirming=-1;_facFile=null;render();}};
window.hcAskDel=function(i){{confirming=i;editing=-1;render();}};
window.hcNoDel=function(){{confirming=-1;render();}};
window.hcDoDel=function(i){{nav("rc_delete",REGS[i].id);}};
window.hcToggleRm=function(i,j){{
  var tr=document.getElementById("row-"+i+"-"+j);
  var cb=document.getElementById("rm-"+i+"-"+j);
  if(tr)tr.classList.toggle("rm-on",cb.checked);
}};
window.hcFmt=function(el){{var raw=el.value.replace(/[^0-9]/g,"");el.value=raw?("$"+parseInt(raw).toLocaleString("de-DE")):"";}};
window.hcPickFac=function(i,inp){{_facFile=inp.files[0]||null;var l=document.getElementById("facname-"+i);if(l)l.textContent=_facFile?_facFile.name:"Reemplazar factura…";}};
window.hcSave=async function(i){{
  var r=REGS[i];var items=[];
  r.items.forEach(function(it,j){{
    var p=document.getElementById("p-"+i+"-"+j);
    var c=document.getElementById("c-"+i+"-"+j);
    var rm=document.getElementById("rm-"+i+"-"+j);
    var praw=p?parseInt((p.value+"").replace(/[^0-9]/g,"")):0;
    var cval=c?(parseInt(c.value)||0):(Math.round(it.cant)||0);
    items.push({{i:j,c:cval,p:praw||0,rm:rm?rm.checked:false}});
  }});
  var g=function(id){{var e=document.getElementById(id);return e?e.value:"";}};
  var payload={{id:r.id,lugar:g("lugar-"+i),obs:g("obs-"+i),fent:g("fent-"+i),items:items}};
  var btn=document.getElementById("savebtn-"+i);
  if(_facFile){{
    if(btn){{btn.disabled=true;btn.style.opacity="0.6";btn.textContent="Subiendo factura...";}}
    try{{
      var ext=(_facFile.name.split(".").pop()||"pdf");
      var path="cotizacion-"+encodeURIComponent(EP)+"/"+Date.now()+"."+ext;
      var up=await fetch(SUPA_URL+"/storage/v1/object/facturas/"+path,{{method:"POST",headers:{{"Authorization":"Bearer "+SUPA_KEY,"apikey":SUPA_KEY,"Content-Type":_facFile.type||"application/octet-stream","x-upsert":"true"}},body:_facFile}});
      if(!up.ok) throw new Error("HTTP "+up.status);
      payload.factura_url=SUPA_URL+"/storage/v1/object/public/facturas/"+path;
      payload.factura_nom=_facFile.name;
    }}catch(e){{
      if(btn){{btn.disabled=false;btn.style.opacity="1";btn.innerHTML=IC.save+"Guardar cambios";}}
      alert("No se pudo subir la factura: "+e.message);return;
    }}
  }}
  nav("rc_edit",JSON.stringify(payload));
}};
function badge(r){{
  var ah=(+r.balance||0)>=0;
  var col=ah?"#16a34a":"#dc2626";var bg=ah?"#f0fdf4":"#fef2f2";
  var lbl=ah?"Ahorro":"Sobrecosto";var ic=ah?IC.down:IC.up;
  return '<span class="hc-badge" style="background:'+bg+';color:'+col+';">'+ic+lbl+' '+f(r.balance)+'</span>';
}}
function viewRows(r){{
  if(!r.items.length)return '<tr><td colspan="5" style="text-align:center;color:#94a3b8;">Sin ítems.</td></tr>';
  return r.items.map(function(it){{
    return '<tr><td>'+esc(it.cat)+'</td><td class="it">'+esc(it.item)+'</td>'
      +'<td class="r">'+esc(it.cant)+'</td><td class="r">'+f(it.pp)+'</td>'
      +'<td class="r" style="font-weight:700;">'+f(it.pr)+'</td></tr>';
  }}).join("");
}}
function editRows(i,r){{
  return r.items.map(function(it,j){{
    var cantCell=it.sin
      ?'<td class="r"><input class="hc-inp hc-inp-c" id="c-'+i+'-'+j+'" type="number" min="0" step="1" value="'+(Math.round(it.cant)||0)+'" title="Adicional sin registro — cantidad editable"/></td>'
      :'<td class="r">'+esc(it.cant)+'</td>';
    return '<tr id="row-'+i+'-'+j+'"><td>'+esc(it.cat)+'</td><td class="it">'+esc(it.item)+'</td>'
      +cantCell
      +'<td class="r">'+f(it.pp)+'</td>'
      +'<td class="r"><input class="hc-inp" id="p-'+i+'-'+j+'" type="text" inputmode="numeric" value="'+f(it.pr)+'" oninput="hcFmt(this)"/></td>'
      +'<td class="c"><input class="hc-rm" id="rm-'+i+'-'+j+'" type="checkbox" onchange="hcToggleRm('+i+','+j+')" title="Quitar este ítem"/></td></tr>';
  }}).join("");
}}
function renderFilters(){{
  var order=["Normal","Adicional con registro","Adicional sin registro","Mixto"];
  var seen={{}};
  REGS.forEach(function(r){{if(r.tipo_lbl){{if(!seen[r.tipo_lbl])seen[r.tipo_lbl]={{n:0,bg:r.tipo_bg,fg:r.tipo_fg}};seen[r.tipo_lbl].n++;}}}});
  var keys=order.filter(function(k){{return seen[k];}});
  Object.keys(seen).forEach(function(k){{if(keys.indexOf(k)<0)keys.push(k);}});
  var el=document.getElementById("hc-filters");if(!el)return;
  if(keys.length<2){{el.innerHTML="";return;}}
  var html='<span class="hc-flabel">Filtrar por tipo:</span>';
  html+='<span class="hc-fbadge'+(filter===""?" active":"")+'" onclick="hcFilter(\'\')">Todas ('+REGS.length+')</span>';
  keys.forEach(function(k){{
    var s=seen[k];var act=(filter===k);
    var sty=act?('background:'+s.bg+';color:'+s.fg+';border-color:'+s.fg+';'):'';
    html+='<span class="hc-fbadge" style="'+sty+'" onclick="hcFilter(\''+k+'\')"><span class="hc-tipodot" style="background:'+s.fg+';"></span>'+k+' ('+s.n+')</span>';
  }});
  el.innerHTML=html;
}}
function fit(){{
  try{{
    // scrollHeight = altura REAL del contenido (no recortada al iframe); usar
    // getBoundingClientRect colapsaría el iframe (círculo viewport->altura).
    var h=Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 120)+2;
    var fe=window.frameElement;
    if(fe){{fe.style.height=h+"px";fe.setAttribute("height",h);}}
  }}catch(e){{}}
}}
function render(){{
  renderFilters();
  var w=document.getElementById("hc-wrap");w.innerHTML="";
  REGS.forEach(function(r,i){{
    if(filter&&r.tipo_lbl!==filter)return;
    var ed=(editing===i);
    var d=document.createElement("details");d.className="hc"+(ed?" editing":"");d.open=ed||(confirming===i);
    d.addEventListener("toggle",fit);
    var meta='<div class="hc-meta"><span>'+IC.cal+esc(r.fecha)+'</span><span>'+IC.user+esc(r.usuario)+'</span><span>'+IC.cart+esc(r.tipo)+'</span></div>';
    var fac=r.factura_url
      ?'<a class="hc-fac" href="'+esc(r.factura_url)+'" target="_blank" rel="noopener noreferrer">'+IC.file+'<span style="margin-left:2px;">Ver factura: '+esc(r.factura_nom)+'</span></a>'
      :'<div class="hc-nofac">'+IC.alert+'<span style="margin-left:4px;">Sin factura adjunta</span></div>';
    var obs=(r.obs&&!ed)?'<div class="hc-obs">'+esc(r.obs)+'</div>':'';
    var tipoB=r.tipo_lbl?('<span class="hc-tipo" style="background:'+(r.tipo_bg||"#e2e8f0")+';color:'+(r.tipo_fg||"#334155")+';"><span class="hc-tipodot" style="background:'+(r.tipo_fg||"#334155")+';"></span>'+esc(r.tipo_lbl)+'</span>'):'';
    var head='<summary>'+IC.store+'<span class="hc-lugar">'+esc(r.lugar||"Compra")+'</span>'+tipoB+badge(r)+IC.chev+'</summary>';
    var body;
    if(ed){{
      body='<div class="hc-body">'
        +'<div class="hc-editfields">'
        +'<div class="hc-fld"><label>Lugar de compra</label><input id="lugar-'+i+'" value="'+esc(r.lugar)+'"/></div>'
        +'<div class="hc-fld"><label>Fecha de entrega</label><input id="fent-'+i+'" value="'+esc(r.fent)+'"/></div>'
        +'<div class="hc-fld"><label>Observaciones</label><input id="obs-'+i+'" value="'+esc(r.obs)+'"/></div>'
        +'</div>'
        +'<div class="hc-tblwrap"><table class="hc-tbl"><thead><tr><th>Categoría</th><th>Ítem</th><th class="r">Cantidad</th><th class="r">Presupuestado</th><th class="r">Precio real</th><th class="c">Quitar</th></tr></thead><tbody>'+editRows(i,r)+'</tbody></table></div>'
        +'<div class="hc-hint">Corrige el <b>precio real</b> mal digitado, o marca <b>Quitar</b> para eliminar un ítem. El balance se recalcula al guardar.</div>'
        +'<div class="hc-facedit">'
        +(r.factura_url?'<a class="hc-fac" style="margin-top:0;" href="'+esc(r.factura_url)+'" target="_blank" rel="noopener noreferrer">'+IC.file+'<span style="margin-left:2px;">Factura actual: '+esc(r.factura_nom)+'</span></a>':'<span class="hc-nofac" style="margin-top:0;">'+IC.alert+'<span style="margin-left:4px;">Sin factura adjunta</span></span>')
        +'<label class="hc-facbtn">'+IC.clip+'<span id="facname-'+i+'">'+(r.factura_url?"Reemplazar factura…":"Adjuntar factura…")+'</span><input type="file" accept=".pdf,image/*" style="display:none" onchange="hcPickFac('+i+',this)"/></label>'
        +'</div>'
        +'<div class="hc-actions"><button id="savebtn-'+i+'" class="hc-btn hc-save" onclick="hcSave('+i+')">'+IC.save+'Guardar cambios</button><button class="hc-btn hc-cancel" onclick="hcCancel()">'+IC.x+'Cancelar</button></div>'
        +'</div>';
    }} else {{
      var conf=(confirming===i)
        ?'<div class="hc-confirm">'+IC.alert+'<span><b>¿Eliminar esta compra por completo?</b> Sus ítems volverán a quedar pendientes.</span><span style="margin-left:auto;display:flex;gap:8px;"><button class="hc-btn hc-del" onclick="hcDoDel('+i+')">Sí, eliminar</button><button class="hc-btn hc-cancel" onclick="hcNoDel()">Cancelar</button></span></div>'
        :'';
      body='<div class="hc-body">'+meta
        +'<div class="hc-tblwrap"><table class="hc-tbl"><thead><tr><th>Categoría</th><th>Ítem</th><th class="r">Cantidad</th><th class="r">Presupuestado</th><th class="r">Precio real</th></tr></thead><tbody>'+viewRows(r)+'</tbody></table></div>'
        +'<div class="hc-tots"><span>Presupuestado <b>'+f(r.tp)+'</b></span><span>Real <b>'+f(r.tr)+'</b></span><span>Balance <b style="color:'+((+r.balance||0)>=0?"#16a34a":"#dc2626")+';">'+((+r.balance||0)>=0?"Ahorro":"Sobrecosto")+' '+f(r.balance)+'</b></span></div>'
        +obs+fac
        +'<div class="hc-actions"><button class="hc-btn hc-edit" onclick="hcEdit('+i+')">'+IC.edit+'Editar</button><button class="hc-btn hc-del" onclick="hcAskDel('+i+')">'+IC.trash+'Eliminar</button></div>'
        +conf
        +'</div>';
    }}
    d.innerHTML=head+body;
    w.appendChild(d);
  }});
  fit();
}}
render();
window.addEventListener("load",fit);
try{{new ResizeObserver(function(){{fit();}}).observe(document.body);}}catch(e){{}}
setTimeout(fit,60);setTimeout(fit,350);
</script>"""


# ── CÁLCULO DE TOTALES ────────────────────────────────────────────────────────

def calcular_totales_rc(productos_presupuesto, registros, incluir_varios=False):
    """
    Calcula totales igual al JS calc() de la tabla RC.
    tP: precio presupuesto * cantidad para ítems normales
    tR: precio real * cantidad + adicional * precio real para TODOS los ítems
    tA: precio real * cantidad para adicionales con registro
    tS: precio real * cantidad para adicionales sin registro
    """
    import json as _jct
    _todos = list(productos_presupuesto or [])
    _pn = {str(p.get('Item', '')) for p in _todos}
    _pu_map = {str(p.get('Item', '')): round(float(p.get('Precio Unitario', 0) or 0))
               for p in _todos}

    if incluir_varios:
        prods = _todos
    else:
        prods = [p for p in _todos
                 if str(p.get('Categoria', '')).strip().lower() != 'varios']

    _comprados = {}
    for reg in (registros or []):
        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = _jct.loads(items_r)
            except Exception:
                items_r = []
        for it in items_r:
            nombre = str(it.get('item', ''))
            pr = float(it.get('precio_real', 0) or 0)
            if pr > 0 and nombre:
                _comprados[nombre] = {
                    'real': pr,
                    'cant': float(it.get('cantidad', 1) or 1),
                    'adic': int(it.get('adicional', 0) or 0),
                    'es_adicional': it.get('es_adicional', False),
                    'sin_registro': it.get('sin_registro', False),
                }

    tP = 0; tR = 0; tA = 0; tS = 0

    for nombre, data in _comprados.items():
        re = data['real']
        c = data['cant']
        ad = data['adic']
        isSinReg = data['sin_registro']
        isAdic = (nombre not in _pn) and not isSinReg

        if isSinReg:
            tS += re * c
        elif isAdic:
            tA += re * c
        else:
            pu = _pu_map.get(nombre, 0)
            tR += re * c + ad * re
            if nombre in _pn:
                tP += pu * c
            continue
        tR += re * c + ad * re

    for p in prods:
        nombre = str(p.get('Item', ''))
        if nombre not in _comprados:
            pu = round(float(p.get('Precio Unitario', 0) or 0))
            c = round(float(p.get('Cantidad', 1) or 1))
            tP += pu * c

    return {'tP': tP, 'tR': tR, 'tA': tA, 'tS': tS}


# ── EXCEL BALANCE ─────────────────────────────────────────────────────────────

def generar_excel_balance(cotizacion_numero, registros, productos_presupuesto, incluir_varios=False):
    """Genera Excel con precios reales consolidados por ítem para nutrir BD."""
    import io, json
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return None

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance de Precios"

    azul_oscuro = "1E2447"
    verde = "16A34A"
    rojo = "DC2626"
    gris_claro = "F8FAFC"
    borde_gris = "E2E8F0"

    hdr_font = Font(name='Calibri', bold=True, color="FFFFFF", size=10)
    hdr_fill = PatternFill("solid", fgColor=azul_oscuro)
    hdr_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
    thin = Side(style='thin', color=borde_gris)
    borde = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.merge_cells('A1:E1')
    ws['A1'] = f'Balance de Precios — {cotizacion_numero}'
    ws['A1'].font = Font(name='Calibri', bold=True, size=13, color=azul_oscuro)
    ws['A1'].alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 28

    headers = ['Categoría', 'Ítem', 'Precio Unitario (Presupuestado)', 'Precio Real (Compra)', 'Diferencia']
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font = hdr_font
        cell.fill = hdr_fill
        cell.alignment = hdr_align
        cell.border = borde
    ws.row_dimensions[2].height = 32

    if incluir_varios:
        prods_valid = list(productos_presupuesto or [])
    else:
        prods_valid = [p for p in (productos_presupuesto or [])
                       if str(p.get('Categoria', '')).strip().lower() != 'varios']

    precios_reales = {}
    for reg in registros:
        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = json.loads(items_r)
            except Exception:
                items_r = []
        for it in items_r:
            nombre = str(it.get('item', ''))
            real = float(it.get('precio_real', 0) or 0)
            if real > 0:
                precios_reales[nombre] = {
                    'real': real,
                    'categoria': it.get('categoria', ''),
                    'presup': float(it.get('precio_presupuestado', 0) or 0)
                }

    row = 3
    alt = False
    for prod in prods_valid:
        item_nombre = str(prod.get('Item', ''))
        if item_nombre not in precios_reales:
            continue
        datos = precios_reales[item_nombre]
        cat = datos['categoria'] or str(prod.get('Categoria', ''))
        pp = datos['presup'] or round(float(prod.get('Precio Unitario', 0) or 0))
        pr = datos['real']
        dif = pp - pr

        bg = PatternFill("solid", fgColor="FFFFFF" if not alt else gris_claro)
        alt = not alt

        vals = [cat, item_nombre, pp, pr, dif]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.fill = bg
            cell.border = borde
            cell.font = Font(name='Calibri', size=9)
            if col in (3, 4, 5):
                cell.number_format = '"$"#,##0'
                cell.alignment = Alignment(horizontal='right')
            else:
                cell.alignment = Alignment(horizontal='left', vertical='center')
            if col == 5:
                cell.font = Font(name='Calibri', size=9, bold=True,
                                 color=verde if dif >= 0 else rojo)
        ws.row_dimensions[row].height = 18
        row += 1

    ws.column_dimensions['A'].width = 18
    ws.column_dimensions['B'].width = 42
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 18
    ws.column_dimensions['E'].width = 18

    if row > 3:
        ws.cell(row=row, column=1, value='').border = borde
        ws.cell(row=row, column=2, value='TOTAL ÍTEMS COMPRADOS').font = Font(bold=True, name='Calibri', size=9)
        ws.cell(row=row, column=2).border = borde
        ws.cell(row=row, column=3, value=f'{row - 3} de {len(prods_valid)} ítems').font = Font(name='Calibri', size=9, color="64748B")
        ws.cell(row=row, column=3).border = borde
        ws.cell(row=row, column=4).border = borde
        ws.cell(row=row, column=5).border = borde
        ws.row_dimensions[row].height = 18

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


# ── PDF BALANCE ───────────────────────────────────────────────────────────────

def generar_pdf_balance(cotizacion_numero, datos_cliente, datos_asesor, registros,
                        productos_presupuesto, incluir_varios=False):
    """Genera PDF de balance de compras consolidando todos los registros."""
    import io, json
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from datetime import datetime, timezone, timedelta

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    elements = []
    styles = getSampleStyleSheet()
    tz_cl = timezone(timedelta(hours=-3))

    def _sty(name, **kw):
        try:
            styles.add(ParagraphStyle(name=name, parent=styles['Normal'], **kw))
        except Exception:
            pass
        return styles[name]

    _sty('BTitle', fontSize=18, fontName='Helvetica-Bold', spaceAfter=4, textColor=colors.HexColor('#1e2447'))
    _sty('BSubtitle', fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=2)
    _sty('BSection', fontSize=11, fontName='Helvetica-Bold', spaceAfter=4, textColor=colors.HexColor('#1e2447'), spaceBefore=10)
    _sty('BLabel', fontSize=9, textColor=colors.HexColor('#64748b'))
    _sty('BValue', fontSize=9, fontName='Helvetica-Bold')
    _sty('BSmall', fontSize=8, textColor=colors.HexColor('#64748b'))
    _sty('BRegHeader', fontSize=9, fontName='Helvetica-Bold', textColor=colors.HexColor('#1e2447'), spaceBefore=8, spaceAfter=2)

    now_str = datetime.now(tz_cl).strftime('%d/%m/%Y %H:%M')

    _logo_cell = ""
    try:
        from reportlab.platypus import Image as _RLImage
        _logo = _RLImage("logo.png")
        _logo_w = 4 * cm
        _logo_aspect = _logo.imageHeight / float(_logo.imageWidth)
        _logo.drawWidth = _logo_w
        _logo.drawHeight = _logo_w * _logo_aspect
        _logo_cell = _logo
    except Exception:
        pass

    header_data = [[
        _logo_cell,
        Paragraph("<b>BALANCE DE COMPRAS" + (" (CON VARIOS)" if incluir_varios else "") + "</b>", styles['BTitle']),
        Paragraph(f"Generado: {now_str}", styles['BSmall'])
    ]]
    header_tbl = Table(header_data, colWidths=[4.5 * cm, 9 * cm, 4 * cm])
    header_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
    ]))
    elements.append(header_tbl)
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#1e2447'), spaceBefore=4, spaceAfter=8))

    _nombre = datos_cliente.get('Nombre', '')
    _rut = datos_cliente.get('RUT', '')
    _asesor = datos_asesor.get('Nombre Ejecutivo', '')
    info_data = [
        [Paragraph('<b>N° Presupuesto</b>', styles['BLabel']), Paragraph(cotizacion_numero, styles['BValue']),
         Paragraph('<b>Cliente</b>', styles['BLabel']), Paragraph(_nombre, styles['BValue'])],
        [Paragraph('<b>RUT</b>', styles['BLabel']), Paragraph(_rut, styles['BValue']),
         Paragraph('<b>Ejecutivo</b>', styles['BLabel']), Paragraph(_asesor, styles['BValue'])],
    ]
    info_tbl = Table(info_data, colWidths=[3 * cm, 6 * cm, 3 * cm, 5.5 * cm])
    info_tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_tbl)
    elements.append(Spacer(1, 0.3 * cm))

    if incluir_varios:
        prods_valid = list(productos_presupuesto or [])
    else:
        prods_valid = [p for p in (productos_presupuesto or [])
                       if str(p.get('Categoria', '')).strip().lower() != 'varios']
    total_items = len(prods_valid)
    items_en_registros = set()
    for reg in registros:
        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = json.loads(items_r)
            except Exception:
                items_r = []
        for it in items_r:
            if float(it.get('precio_real', 0) or 0) > 0:
                items_en_registros.add(str(it.get('item', '')))
    comprados = sum(1 for p in prods_valid if str(p.get('Item', '')) in items_en_registros)
    pct = round(comprados / total_items * 1000) / 10 if total_items > 0 else 0
    pct_col = colors.HexColor('#3b82f6') if pct >= 100 else (
              colors.HexColor('#16a34a') if pct >= 66.6 else (
              colors.HexColor('#eab308') if pct >= 33.3 else colors.HexColor('#dc2626')))
    pct_lbl = 'Compra finalizada' if pct >= 100 else f'{pct}% comprado'

    prog_data = [[
        Paragraph('<b>Progreso de compra</b>', styles['BLabel']),
        Paragraph(f'<b>{pct_lbl}</b>', ParagraphStyle('_pc', parent=styles['Normal'],
            fontSize=11, fontName='Helvetica-Bold', textColor=pct_col)),
        Paragraph(f'{comprados} de {total_items} ítems', styles['BSmall']),
    ]]
    prog_tbl = Table(prog_data, colWidths=[3.5 * cm, 6 * cm, 3 * cm])
    prog_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (0, -1), 8),
    ]))
    elements.append(prog_tbl)
    elements.append(Spacer(1, 0.4 * cm))

    elements.append(Paragraph('Detalle de Registros de Compra', styles['BSection']))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=6))

    _tipo_labels = {'online': 'Compra Online', 'presencial': 'Compra Presencial'}
    _subtipo_labels = {'retiro': 'Retiro', 'despacho': 'Despacho',
                       'completo': 'Retiro Completo', 'parcial': 'Retiro Parcial'}
    col_azul = colors.HexColor('#1e2447')
    col_gris = colors.HexColor('#64748b')
    col_verde = colors.HexColor('#16a34a')
    col_rojo = colors.HexColor('#dc2626')

    tbl_header = ['Categoría', 'Ítem', 'Cant.', 'Presup.', 'Real', 'Adic.', 'Diferencia']
    col_ws = [2.5 * cm, 5.5 * cm, 1.2 * cm, 2.2 * cm, 2.2 * cm, 1.2 * cm, 2.7 * cm]

    for idx_r, reg in enumerate(registros):
        try:
            fecha_reg = datetime.fromisoformat(reg['fecha_registro'].replace('Z', '+00:00')).astimezone(tz_cl).strftime('%d/%m/%Y %H:%M')
        except Exception:
            fecha_reg = '—'
        lugar = reg.get('lugar_compra', '') or '—'
        tipo = _tipo_labels.get(reg.get('tipo_compra', ''), reg.get('tipo_compra', '') or '—')
        subtipo = _subtipo_labels.get(reg.get('subtipo_compra', ''), reg.get('subtipo_compra', '') or '')
        tipo_full = f"{tipo} — {subtipo}" if subtipo else tipo
        fecha_ent = reg.get('fecha_entrega_compra', '') or ''
        falto = reg.get('falto_retirar', '') or ''
        obs = reg.get('observaciones', '') or 'Sin observaciones'
        factura = reg.get('factura_nombre', '') or '—'

        reg_info = f"Registro #{idx_r + 1} — {fecha_reg} | {lugar} | {tipo_full}"
        if fecha_ent:
            reg_info += f" | Para: {fecha_ent}"
        elements.append(Paragraph(reg_info, styles['BRegHeader']))

        if falto:
            elements.append(Paragraph(f"Faltó retirar: {falto}", styles['BSmall']))
        elements.append(Paragraph(f"Observación: {obs}", styles['BSmall']))
        _factura_url = reg.get('factura_url', '') or ''
        if _factura_url:
            elements.append(Paragraph(
                f'Factura: <link href="{_factura_url}"><u><font color="#3b82f6">{factura}</font></u></link>',
                styles['BSmall']
            ))
        else:
            elements.append(Paragraph(f"Factura: {factura}", styles['BSmall']))
        elements.append(Spacer(1, 0.2 * cm))

        items_r = reg.get('items') or []
        if isinstance(items_r, str):
            try:
                items_r = json.loads(items_r)
            except Exception:
                items_r = []

        if items_r:
            rows = [tbl_header]
            row_types = ['header']
            sub_p = 0; sub_r = 0; sub_a = 0; sub_s = 0
            _pn_pdf = {str(p.get('Item', '')) for p in (productos_presupuesto or [])}
            _pp_map = {str(p.get('Item', '')): round(float(p.get('Precio Unitario', 0) or 0)) for p in (productos_presupuesto or [])}
            for it in items_r:
                pp = float(it.get('precio_presupuestado', 0) or 0)
                pr = float(it.get('precio_real', 0) or 0)
                cant = float(it.get('cantidad', 1) or 1)
                adic = int(it.get('adicional', 0) or 0)
                dif = (pp - pr) * cant - (adic * pr)
                _is_sin = it.get('sin_registro', False)
                _is_con = (it.get('es_adicional', False) or str(it.get('item', '')) not in _pn_pdf) and not _is_sin
                pp_real = _pp_map.get(str(it.get('item', '')), pp) if not _is_con and not _is_sin else pp
                if _is_sin:
                    sub_s += pr * cant
                elif _is_con:
                    sub_a += pr * cant
                else:
                    sub_p += pp_real * cant; sub_r += pr * cant + adic * pr
                dif_str = f"${abs(dif):,.0f} {'▼' if dif >= 0 else '▲'}".replace(',', '.')
                rows.append([it.get('categoria', ''), it.get('item', ''), str(int(cant)),
                    f"${pp_real:,.0f}".replace(',', '.'), f"${pr:,.0f}".replace(',', '.'),
                    str(adic), dif_str])
                row_types.append('sin' if _is_sin else ('con' if _is_con else 'normal'))
            bal_r = sub_p - sub_r
            rows.append(['', 'SUBTOTAL PRESUPUESTO', '', f"${sub_p:,.0f}".replace(',', '.'),
                         f"${sub_r:,.0f}".replace(',', '.'), '',
                         f"${abs(bal_r):,.0f} {'▼' if bal_r >= 0 else '▲'}".replace(',', '.')])
            row_types.append('subtotal')
            if sub_a > 0:
                rows.append(['', 'ADICIONALES CON REGISTRO', '', '—', f"${sub_a:,.0f}".replace(',', '.'), '', ''])
                row_types.append('subtotal_con')
            if sub_s > 0:
                rows.append(['', 'ADICIONALES SIN REGISTRO', '', '—', f"${sub_s:,.0f}".replace(',', '.'), '', ''])
                row_types.append('subtotal_sin')
            tbl = Table(rows, colWidths=col_ws, repeatRows=1)
            tbl_style = [
                ('BACKGROUND', (0, 0), (-1, 0), col_azul),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 7),
                ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
                ('ALIGN', (0, 0), (1, -1), 'LEFT'),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ]
            for ri, rtype in enumerate(row_types):
                if rtype == 'con':
                    tbl_style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fff7ed')))
                    tbl_style.append(('TEXTCOLOR', (0, ri), (1, ri), colors.HexColor('#c2410c')))
                elif rtype == 'sin':
                    tbl_style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fdf2f8')))
                    tbl_style.append(('TEXTCOLOR', (0, ri), (1, ri), colors.HexColor('#9d174d')))
                elif rtype == 'subtotal':
                    tbl_style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#f1f5f9')))
                    tbl_style.append(('FONTNAME', (0, ri), (-1, ri), 'Helvetica-Bold'))
                elif rtype == 'subtotal_con':
                    tbl_style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fff3e0')))
                    tbl_style.append(('FONTNAME', (0, ri), (-1, ri), 'Helvetica-Bold'))
                    tbl_style.append(('TEXTCOLOR', (0, ri), (-1, ri), colors.HexColor('#c2410c')))
                elif rtype == 'subtotal_sin':
                    tbl_style.append(('BACKGROUND', (0, ri), (-1, ri), colors.HexColor('#fdf2f8')))
                    tbl_style.append(('FONTNAME', (0, ri), (-1, ri), 'Helvetica-Bold'))
                    tbl_style.append(('TEXTCOLOR', (0, ri), (-1, ri), colors.HexColor('#9d174d')))
                if ri > 0 and row_types[ri] not in ('subtotal', 'subtotal_con', 'subtotal_sin') and len(rows[ri]) > 6 and rows[ri][6]:
                    is_ahorro = '▼' in rows[ri][6]
                    tbl_style.append(('TEXTCOLOR', (6, ri), (6, ri), col_verde if is_ahorro else col_rojo))
            tbl.setStyle(TableStyle(tbl_style))
            elements.append(tbl)

        elements.append(Spacer(1, 0.4 * cm))
        if idx_r < len(registros) - 1:
            elements.append(HRFlowable(width='100%', thickness=0.3, color=colors.HexColor('#e2e8f0'), spaceAfter=4))

    elements.append(Paragraph('Resumen Final Consolidado', styles['BSection']))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=8))

    _tots = calcular_totales_rc(productos_presupuesto, registros, incluir_varios=incluir_varios)
    total_p = _tots['tP']; total_r = _tots['tR']
    total_adic_con = _tots['tA']; total_adic_sin = _tots['tS']

    iva_p = total_p * 0.19; iva_r = total_r * 0.19
    bal = total_p - total_r; iva_bal = iva_p - iva_r
    bal_col = col_verde if bal >= 0 else col_rojo
    bal_lbl = 'AHORRO' if bal >= 0 else 'SOBRECOSTO'

    def _fmt(v): return f"${abs(v):,.0f}".replace(',', '.')

    iva_adic_con = total_adic_con * 0.19; iva_adic_sin = total_adic_sin * 0.19

    resumen_rows = [
        ['', 'PRESUPUESTADO', 'REAL', 'BALANCE', 'ADIC. C/REG.', 'ADIC. S/REG.'],
        ['Subtotal neto', _fmt(total_p), _fmt(total_r), _fmt(bal), _fmt(total_adic_con), _fmt(total_adic_sin)],
        ['IVA (19%)', _fmt(iva_p), _fmt(iva_r), _fmt(iva_bal), _fmt(iva_adic_con), _fmt(iva_adic_sin)],
        ['Total con IVA', _fmt(total_p + iva_p), _fmt(total_r + iva_r), _fmt(bal + iva_bal),
         _fmt(total_adic_con + iva_adic_con), _fmt(total_adic_sin + iva_adic_sin)],
    ]
    res_tbl = Table(resumen_rows, colWidths=[3 * cm, 2.8 * cm, 2.8 * cm, 2.8 * cm, 2.5 * cm, 2.5 * cm])
    res_style = [
        ('BACKGROUND', (0, 0), (-1, 0), col_azul),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TEXTCOLOR', (3, 1), (3, -1), bal_col),
        ('TEXTCOLOR', (4, 1), (4, -1), colors.HexColor('#c2410c')),
        ('BACKGROUND', (4, 0), (4, 0), colors.HexColor('#ea580c')),
        ('BACKGROUND', (4, 1), (4, -1), colors.HexColor('#fff7ed')),
        ('TEXTCOLOR', (4, 0), (4, 0), colors.white),
        ('TEXTCOLOR', (5, 1), (5, -1), colors.HexColor('#9d174d')),
        ('BACKGROUND', (5, 0), (5, 0), colors.HexColor('#db2777')),
        ('BACKGROUND', (5, 1), (5, -1), colors.HexColor('#fdf2f8')),
        ('TEXTCOLOR', (5, 0), (5, 0), colors.white),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    res_tbl.setStyle(TableStyle(res_style))
    elements.append(res_tbl)
    elements.append(Spacer(1, 0.3 * cm))

    badge_data = [[Paragraph(
        f"<b>{bal_lbl}: {_fmt(bal + iva_bal)} (con IVA)</b>",
        ParagraphStyle('_badge', parent=styles['Normal'], fontSize=12,
            fontName='Helvetica-Bold', textColor=bal_col, alignment=1)
    )]]
    badge_tbl = Table(badge_data, colWidths=[16 * cm])
    badge_tbl.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f0fdf4') if bal >= 0 else colors.HexColor('#fef2f2')),
        ('BOX', (0, 0), (-1, -1), 1, bal_col),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(badge_tbl)

    doc.build(elements)
    buf.seek(0)
    return buf.read()


# ── HTML BUILDER REGISTRO DE COMPRAS ─────────────────────────────────────────

def build_rc_html(rc_prods, rc_cat_json, rc_prev, items_comprados=None, es_admin=False,
                  supa_url='', supa_key='', ep='', usuario='', items_ya_comprados_json='[]',
                  total_items_presupuesto=0, cats_cards_html=''):
    rows = ""
    items_comprados = items_comprados or {}
    for ri, prod in enumerate(rc_prods):
        cat = str(prod.get('Categoria', ''))
        item = str(prod.get('Item', ''))
        cant = round(float(prod.get('Cantidad', 1) or 1))
        pu = round(float(prod.get('Precio Unitario', 0) or 0))
        _es_adicional = bool(prod.get('_adicional', False))
        _es_sin_reg = bool(prod.get('_sin_registro', False))
        _ic = items_comprados.get(item, {})
        _ya_comprado = bool(_ic and float(_ic.get('real', 0) or 0) > 0) or _es_adicional
        _readonly = _ya_comprado and not es_admin

        if _es_sin_reg:
            bg = '#fdf2f8'
        elif _es_adicional:
            bg = '#fff3e0'
        elif _ya_comprado:
            bg = '#f0fdf4'
        elif ri % 2 == 0:
            bg = '#ffffff'
        else:
            bg = '#f8fafc'

        pu_fmt = '$' + f'{pu:,}'.replace(',', '.')
        pv = rc_prev.get(str(ri), {})
        vreal = float(_ic.get('real', 0)) if _ya_comprado else (pv.get('real', 0) or 0)
        vadic = int(_ic.get('adicional', 0)) if _ya_comprado else (pv.get('adic', 0) or 0)
        vreal_fmt = ('$' + f'{int(vreal):,}'.replace(',', '.')) if vreal else ''

        _dc_attr = 'data-comprado="1"' if _ya_comprado else ""
        _da_attr = 'data-adicional="1"' if _es_adicional else ""
        _ds_attr = 'data-sin-registro="1"' if _es_sin_reg else ""
        rows += f"""<tr style="background:{bg};border-bottom:1px solid #eef0f6" data-idx="{ri}" data-pu="{pu}" data-cant="{cant}" {_dc_attr} {_da_attr} {_ds_attr}>
<td style="padding:5px 8px;font-size:.85rem;color:#334155;font-weight:700;font-family:Montserrat,'Segoe UI',sans-serif">{cat}</td>
<td style="padding:5px 8px;font-size:.95rem;color:#0f172a;font-weight:700;font-family:Montserrat,'Segoe UI',sans-serif">{item}</td>
<td style="padding:5px 8px;text-align:right;font-weight:700;font-family:Montserrat,'Segoe UI',sans-serif">{cant}</td>
<td style="padding:5px 8px;text-align:right;font-weight:700;font-family:Montserrat,'Segoe UI',sans-serif">{pu_fmt}</td>
<td style="padding:3px 4px"><input type="text" inputmode="numeric" value="{vreal_fmt}" class="rc-real" data-idx="{ri}" data-val="{vreal}" {"readonly" if _readonly else ""} style="width:100%;border:1px solid {"#86efac" if _ya_comprado else "#cbd5e1"};border-radius:6px;padding:5px;font-size:13px;text-align:right;box-sizing:border-box;{"background:#f0fdf4;color:#15803d;cursor:default" if _ya_comprado else ""}"/></td>
<td style="padding:3px 4px"><input type="number" min="0" step="1" value="{vadic}" class="rc-adic" data-idx="{ri}" {"readonly" if _readonly else ""} style="width:100%;border:1px solid {"#86efac" if _ya_comprado else "#fca5a5"};border-radius:6px;padding:5px;font-size:13px;text-align:right;background:{"#f0fdf4" if _ya_comprado else "#fff5f5"};box-sizing:border-box{"pointer-events:none" if _readonly else ""}"/></td>
<td class="rc-dif" data-idx="{ri}" style="padding:5px 8px;text-align:right;font-weight:700;color:#16a34a;white-space:nowrap;font-family:Montserrat,'Segoe UI',sans-serif">-</td>
<td></td>
</tr>"""

    html = f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700&display=swap');
html,body{{margin:0;padding:0;font-family:Montserrat,'Segoe UI',sans-serif;font-size:13px;height:100%;overflow:hidden}}
body{{display:flex;flex-direction:column}}
table{{width:100%;border-collapse:collapse}}
th{{background:#1e2447;color:#fff;padding:7px 8px;font-size:11px;letter-spacing:.05em;text-transform:uppercase;white-space:nowrap;position:sticky;top:0;z-index:1}}
th.r,td.r{{text-align:right}}
input[type=number]{{border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:13px;text-align:right;box-sizing:border-box}}
input[type=number]:focus{{outline:none;border-color:#5b7cfa;box-shadow:0 0 0 2px rgba(91,124,250,.2)}}
input[type=number]::-webkit-inner-spin-button{{opacity:.4}}
</style>
<input id="rc-search" type="text" placeholder="Buscar item..." oninput="window.filterRows(this.value)" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:7px 10px;font-size:13px;box-sizing:border-box;margin-bottom:6px"/>
{cats_cards_html}
<div style="border:1px solid #e2e8f0;border-radius:8px;display:flex;flex-direction:column;flex:1;overflow:hidden;min-height:0">
  <div id="tbl-wrap" style="overflow:auto;flex:1;min-height:0"><table>
    <thead><tr>
      <th>Categor&#237;a</th><th>&#205;tem</th><th class="r">Cant.</th>
      <th class="r">Presup. unit.</th><th class="r">Real unit.</th>
      <th class="r">Adicional</th><th class="r">Diferencia</th><th></th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  <div id="tots" style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr 1fr 1fr;gap:10px;padding:16px;background:#f8fafc;border-top:2px solid #e2e8f0;flex-shrink:0">
    <div>
      <div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px">Presupuestado</div>
      <div style="font-size:11px;color:#64748b">Subtotal neto</div><div style="font-size:15px;font-weight:700" id="tp-n">$0</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">IVA (19%)</div><div style="font-size:13px;font-weight:600" id="tp-i">$0</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">Total con IVA</div><div style="font-size:17px;font-weight:900" id="tp-t">$0</div>
    </div>
    <div>
      <div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px">Real</div>
      <div style="font-size:11px;color:#64748b">Subtotal neto</div><div style="font-size:15px;font-weight:700" id="tr-n">$0</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">IVA (19%)</div><div style="font-size:13px;font-weight:600" id="tr-i">$0</div>
      <div style="font-size:11px;color:#64748b;margin-top:4px">Total con IVA</div><div style="font-size:17px;font-weight:900" id="tr-t">$0</div>
    </div>
    <div>
      <div style="font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px" id="b-hdr">Balance</div>
      <div style="font-size:11px" id="b-lbl1">Neto</div><div style="font-size:15px;font-weight:700" id="b-n">$0</div>
      <div style="font-size:11px;margin-top:4px" id="b-lbl2">IVA</div><div style="font-size:13px;font-weight:600" id="b-i">$0</div>
      <div style="font-size:11px;margin-top:4px" id="b-icon">Ahorro</div><div style="font-size:17px;font-weight:900" id="b-t">$0</div>
    </div>
    <div style="border-left:2px solid #fed7aa;padding-left:10px;background:#fff7ed;border-radius:8px;">
      <div style="font-size:10px;font-weight:700;color:#f97316;letter-spacing:.05em;text-transform:uppercase;margin-bottom:2px">Adicionales</div>
      <div style="font-size:9px;color:#f97316;margin-bottom:6px;font-weight:600">Con registro</div>
      <div style="font-size:11px;color:#f97316">Subtotal neto</div><div style="font-size:14px;font-weight:700;color:#f97316" id="ta-n">$0</div>
      <div style="font-size:11px;color:#f97316;margin-top:4px">IVA (19%)</div><div style="font-size:12px;font-weight:600;color:#f97316" id="ta-i">$0</div>
      <div style="font-size:11px;color:#f97316;margin-top:4px">Total con IVA</div><div style="font-size:16px;font-weight:900;color:#f97316" id="ta-t">$0</div>
    </div>
    <div style="border-left:2px solid #fbcfe8;padding-left:10px;background:#fdf2f8;border-radius:8px;">
      <div style="font-size:10px;font-weight:700;color:#ec4899;letter-spacing:.05em;text-transform:uppercase;margin-bottom:2px">Adicionales</div>
      <div style="font-size:9px;color:#ec4899;margin-bottom:6px;font-weight:600">Sin registro</div>
      <div style="font-size:11px;color:#ec4899">Subtotal neto</div><div style="font-size:14px;font-weight:700;color:#ec4899" id="ts-n">$0</div>
      <div style="font-size:11px;color:#ec4899;margin-top:4px">IVA (19%)</div><div style="font-size:12px;font-weight:600;color:#ec4899" id="ts-i">$0</div>
      <div style="font-size:11px;color:#ec4899;margin-top:4px">Total con IVA</div><div style="font-size:16px;font-weight:900;color:#ec4899" id="ts-t">$0</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;border-left:2px solid #e2e8f0;padding-left:12px">
      <div style="font-size:11px;font-weight:700;color:#64748b;letter-spacing:.05em;text-transform:uppercase;margin-bottom:12px;text-align:center">Progreso de compra</div>
      <div id="prog-pct" style="font-size:42px;font-weight:900;line-height:1;color:#dc2626;text-align:center">0%</div>
      <div id="prog-lbl" style="font-size:12px;font-weight:600;color:#dc2626;margin-top:6px;text-align:center">Sin compras</div>
      <div style="width:100%;background:#e2e8f0;border-radius:99px;height:6px;margin-top:10px;overflow:hidden">
        <div id="prog-bar" style="height:100%;width:0%;border-radius:99px;background:#dc2626;transition:width .4s ease,background .4s ease"></div>
      </div>
    </div>
  </div>
  <div id="add-section" style="padding:12px 16px;background:#fff;border-top:1px solid #e2e8f0;flex-shrink:0">
    <div style="display:flex;gap:8px;margin-bottom:8px;">
      <button onclick="window.switchAddTab('reg')" id="tab-reg" style="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #f97316;background:#fff7ed;color:#f97316;cursor:pointer"><span style="color:#f97316;font-size:24px;line-height:1;vertical-align:middle;">&#9679;</span> Con registro</button>
      <button onclick="window.switchAddTab('sin')" id="tab-sin" style="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #e2e8f0;background:#fff;color:#94a3b8;cursor:pointer"><span style="color:#ec4899;font-size:24px;line-height:1;vertical-align:middle;">&#9679;</span> Sin registro</button>
    </div>
    <div id="add-con-reg" style="display:grid;grid-template-columns:1.5fr 3fr 0.8fr 1.2fr auto;gap:6px;align-items:end">
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Categor&#237;a</div>
        <select id="add-cat" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px"><option value="">Seleccionar...</option></select></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">&#205;tem</div>
        <select id="add-item" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px"><option value="">Seleccionar categor&#237;a primero</option></select></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Cant.</div>
        <input id="add-cant" type="number" min="1" value="1" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px;text-align:right"/></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Presup. unit.</div>
        <div id="add-precio" style="border:1px solid #e2e8f0;border-radius:6px;padding:5px 8px;font-size:12px;font-weight:600;background:#f8fafc;text-align:right">$0</div></div>
      <div style="padding-bottom:1px">
        <button onclick="window.addRow()" style="background:#f97316;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:700;cursor:pointer">+ Agregar</button></div>
    </div>
    <div id="add-sin-reg" style="display:none;grid-template-columns:1.5fr 3fr 0.8fr 1.2fr auto;gap:6px;align-items:end">
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Categor&#237;a *</div>
        <input id="sin-cat" type="text" placeholder="Ej: Herramientas" style="width:100%;border:1px solid #fbcfe8;border-radius:6px;padding:5px;font-size:12px;background:#fdf2f8;box-sizing:border-box"/></div>
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Nombre del &#237;tem *</div>
        <input id="sin-item" type="text" placeholder="Ej: Taladro percutor" style="width:100%;border:1px solid #fbcfe8;border-radius:6px;padding:5px;font-size:12px;background:#fdf2f8;box-sizing:border-box"/></div>
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Cant.</div>
        <input id="sin-cant" type="number" min="1" value="1" style="width:100%;border:1px solid #fbcfe8;border-radius:6px;padding:5px;font-size:12px;text-align:right;background:#fdf2f8;box-sizing:border-box"/></div>
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Precio real *</div>
        <input id="sin-precio" type="text" inputmode="numeric" placeholder="$0" style="width:100%;border:1px solid #fbcfe8;border-radius:6px;padding:5px;font-size:12px;text-align:right;background:#fdf2f8;box-sizing:border-box"/></div>
      <div style="padding-bottom:1px">
        <button onclick="window.addRowSinReg()" style="background:#ec4899;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:700;cursor:pointer">+ Agregar</button></div>
    </div>
  </div>
  <div id="save-section" style="padding:12px 16px;background:#1e2447;border-top:2px solid #e2e8f0;flex-shrink:0">
    <div style="font-size:11px;font-weight:700;color:#fff;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px;display:flex;align-items:center">{_svg_rc('paperclip', color='#fff', size=14, mr=8)}Adjuntar Factura y Guardar</div>
    <style>
    .rc-field{{margin-bottom:8px}}
    .rc-lbl{{font-size:11px;color:rgba(255,255,255,0.6);margin-bottom:3px;display:flex;align-items:center}}
    .rc-inp{{width:100%;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:7px 10px;font-size:13px;background:rgba(255,255,255,0.08);color:#fff;box-sizing:border-box;outline:none}}
    .rc-inp::placeholder{{color:rgba(255,255,255,0.35)}}
    .rc-sel{{width:100%;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:7px 10px;font-size:13px;background:#1e2447;color:#fff;box-sizing:border-box;outline:none;cursor:pointer}}
    .rc-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    .rc-hidden{{display:none}}
    </style>
    <div class="rc-grid">
      <div class="rc-field">
        <div class="rc-lbl">{_svg_rc('store', color='rgba(255,255,255,0.7)', size=13)}&#191;D&#243;nde compraste? *</div>
        <input id="lugar-compra" type="text" class="rc-inp" placeholder="Ej: Ferretera L&#243;pez" oninput="window.checkSaveBtn()"/>
      </div>
      <div class="rc-field">
        <div class="rc-lbl">{_svg_rc('cart', color='rgba(255,255,255,0.7)', size=13)}Tipo de compra *</div>
        <select id="tipo-compra" class="rc-sel" onchange="window.onTipoChange()">
          <option value="">Seleccionar...</option>
          <option value="online">Compra Online</option>
          <option value="presencial">Compra Presencial</option>
        </select>
      </div>
    </div>
    <div id="subtipo-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl" id="subtipo-lbl">Modalidad *</div>
      <select id="subtipo-compra" class="rc-sel" onchange="window.onSubtipoChange()">
      </select>
    </div>
    <div id="fecha-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl" id="fecha-lbl">{_svg_rc('calendar', color='rgba(255,255,255,0.7)', size=13)}&#191;Para cu&#225;ndo? *</div>
      <input id="fecha-compra" type="date" class="rc-inp" oninput="window.checkSaveBtn()" onchange="window.checkSaveBtn()"/>
    </div>
    <div id="falt&#243;-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl">{_svg_rc('clipboard', color='rgba(255,255,255,0.7)', size=13)}&#191;Qu&#233; falt&#243; por retirar? *</div>
      <textarea id="falto-texto" class="rc-inp" rows="2" placeholder="Describe los &#237;tems que faltaron..." oninput="window.checkSaveBtn()" style="resize:vertical"></textarea>
    </div>
    <div class="rc-field">
      <div class="rc-lbl">{_svg_rc('note', color='rgba(255,255,255,0.7)', size=13)}Observaciones adicionales (opcional)</div>
      <textarea id="obs-compra" class="rc-inp" rows="2" placeholder="Notas, motivos u observaciones de esta compra..." style="resize:vertical"></textarea>
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <label id="factura-label" style="background:rgba(255,255,255,0.1);color:#fff;border:1px dashed rgba(255,255,255,0.4);border-radius:6px;padding:6px 14px;font-size:12px;cursor:pointer;white-space:nowrap;display:inline-flex;align-items:center">{_svg_rc('paperclip', color='#fff', size=13)}Seleccionar factura PDF
        <input id="factura-input" type="file" accept=".pdf" style="display:none"/>
      </label>
      <button id="factura-clear" onclick="window.clearFactura()" style="display:none;background:rgba(220,38,38,0.7);color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px;cursor:pointer;white-space:nowrap;align-items:center">{_svg_rc('x', color='#fff', size=12, mr=4)}Quitar</button>
      <div id="save-status" style="font-size:12px;color:rgba(255,255,255,0.7);flex:1"></div>
      <button id="save-btn" onclick="window.guardarRegistro()" disabled style="background:#10b981;color:#fff;border:none;border-radius:8px;padding:8px 24px;font-size:13px;font-weight:700;cursor:pointer;opacity:0.5;white-space:nowrap;display:inline-flex;align-items:center;justify-content:center">{_svg_rc('save', color='#fff', size=14, mr=7)}Guardar compra</button>
    </div>
  </div>
    </div>
  </div>
</div>
<script>(function(){{
var SUPA_URL="{supa_url}";
var SUPA_KEY="{supa_key}";
var EP_NUM="{ep}";
var USUARIO="{usuario}";
var ITEMS_YA_COMPRADOS={items_ya_comprados_json};
var TOTAL_ITEMS={total_items_presupuesto};
var _facturaFile=null;
var _facturaUrl="";
var _facturaNom="";
var ICO_CAL='{_svg_rc('calendar', color='rgba(255,255,255,0.7)', size=13)}';
var ICO_CLIP='{_svg_rc('paperclip', color='#ffffff', size=13)}';
var CAT={rc_cat_json};
var addCat=document.getElementById("add-cat");
Object.keys(CAT).sort().forEach(function(c){{var o=document.createElement("option");o.value=c;o.textContent=c;addCat.appendChild(o);}});
addCat.addEventListener("change",function(){{
  var sel=document.getElementById("add-item");
  sel.innerHTML='<option value="">Seleccionar item...</option>';
  document.getElementById("add-precio").textContent="$0";
  var items=CAT[this.value]||[];
  items.forEach(function(it){{var o=document.createElement("option");o.value=JSON.stringify(it);o.textContent=it.item;sel.appendChild(o);}});
}});
document.getElementById("add-item").addEventListener("change",function(){{
  try{{var it=JSON.parse(this.value);document.getElementById("add-precio").textContent=f(it.precio);}}catch(e){{}}
}});
var _addIdx=10000;
window.addRow=function(){{
  var catEl=document.getElementById("add-cat");
  var itemEl=document.getElementById("add-item");
  var cantEl=document.getElementById("add-cant");
  if(!catEl.value||!itemEl.value)return;
  var it=JSON.parse(itemEl.value);
  var cant=parseInt(cantEl.value)||1;
  var pu=it.precio;
  var tr=document.createElement("tr");
  tr.style.cssText="background:#fff3e0;border-bottom:1px solid #eef0f6;border-left:3px solid #f97316";
  tr.dataset.idx=String(_addIdx);tr.dataset.pu=String(pu);tr.dataset.cant=String(cant);
  tr.dataset.adicional="1";
  tr.innerHTML="<td style='padding:5px 8px;font-size:.75rem;color:#64748b'>"+catEl.value+"</td>"
    +"<td style='padding:5px 8px;font-size:.82rem'>"+it.item+"</td>"
    +"<td style='padding:5px 8px;text-align:right'>"+cant+"</td>"
    +"<td style='padding:5px 8px;text-align:right;font-weight:600'>"+f(pu)+"</td>"
    +'<td style="padding:3px 4px"><input type="text" inputmode="numeric" value="" class="rc-real" data-idx="'+_addIdx+'" data-val="0" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:13px;text-align:right;box-sizing:border-box"/></td>'
    +'<td style="padding:3px 4px"><input type="number" min="0" step="1" value="0" class="rc-adic" data-idx="'+_addIdx+'" style="width:100%;border:1px solid #fca5a5;border-radius:6px;padding:5px;font-size:13px;text-align:right;background:#fff5f5;box-sizing:border-box"/></td>'
    +'<td class="rc-dif" style="padding:5px 8px;text-align:right;font-weight:700;color:#16a34a;white-space:nowrap">-</td>'
    +'<td style="padding:3px 6px;text-align:center"><button onclick="window.removeRow(this)" style="background:none;border:none;color:#ef4444;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1;" title="Eliminar">&#10005;</button></td>';
  document.querySelector("tbody").appendChild(tr);
  attachListeners(tr.querySelector(".rc-real"), tr.querySelector(".rc-adic"));
  _addIdx++;cantEl.value="1";itemEl.selectedIndex=0;
  document.getElementById("add-precio").textContent="$0";calc();
}};
function attachListeners(inp, adic){{
  inp.addEventListener("input",function(){{
    var raw=this.value.replace(/[^0-9]/g,"");
    this.dataset.val=raw||"0";
    if(!raw){{this.value="";calc();return;}}
    this.value="$"+parseInt(raw).toLocaleString("de-DE");calc();checkSaveBtn();
  }});
  inp.addEventListener("focus",function(){{
    var r=this.dataset.val||"0";
    this.value=r==="0"?"":r;
  }});
  inp.addEventListener("blur",function(){{
    var n=parseInt(this.dataset.val)||0;
    this.dataset.val=String(n);
    this.value=n>0?"$"+n.toLocaleString("de-DE"):"";calc();checkSaveBtn();
  }});
  adic.addEventListener("input",function(){{calc();checkSaveBtn();}});
}}
function f(n){{return "$"+Math.round(Math.abs(n)).toLocaleString("de-DE");}}
function calc(){{
  var tP=0,tR=0,tA=0,tS=0,vals=[];
  document.querySelectorAll("tr[data-idx]").forEach(function(r){{
    var idx=parseInt(r.dataset.idx)||0;
    var pu=+r.dataset.pu||0,c=+r.dataset.cant||1;
    var re=parseFloat(r.querySelector(".rc-real").dataset.val)||0;
    var ad=+r.querySelector(".rc-adic").value||0;
    var d=(pu-re)*c-(ad*re);
    var td=r.querySelector(".rc-dif");
    td.textContent=f(d)+(d>=0?" ▼":" ▲");
    td.style.color=d>=0?"#16a34a":"#dc2626";
    var isSinReg=r.getAttribute("data-sin-registro")==="1";
    var isAdic=r.dataset.adicional==="1"&&!isSinReg;
    if(isSinReg){{tS+=re*c;}}
    else if(isAdic){{tA+=re*c;}}
    else{{tP+=pu*c;}}
    tR+=re*c+ad*re;
    vals.push({{idx:+r.dataset.idx,real:re,adic:ad,dif:d}});
  }});
  var iP=tP*.19,iR=tR*.19,b=tP-tR,ib=iP-iR;
  var col=b>=0?"#16a34a":"#dc2626";
  var iA=tA*.19,iS=tS*.19;
  var ids=["tp-n","tp-i","tp-t","tr-n","tr-i","tr-t","b-n","b-i","b-t","ta-n","ta-i","ta-t","ts-n","ts-i","ts-t"];
  var v=[tP,iP,tP+iP,tR,iR,tR+iR,b,ib,b+ib,tA,iA,tA+iA,tS,iS,tS+iS];
  ids.forEach(function(id,i){{var el=document.getElementById(id);if(el)el.textContent=f(v[i]);}});
  ["b-hdr","b-n","b-i","b-lbl1","b-lbl2","b-icon","b-t"].forEach(function(id){{var el=document.getElementById(id);if(el)el.style.color=col;}});
  var bi=document.getElementById("b-icon");
  if(bi)bi.textContent=b>=0?"Ahorro":"Sobrecosto";
  var comprados=vals.filter(function(v){{return v.real>0&&v.idx<10000;}}).length;
  var pct=TOTAL_ITEMS>0?Math.round(comprados/TOTAL_ITEMS*1000)/10:0;
  var pctCol=pct>=100?"#3b82f6":pct>=66.6?"#16a34a":pct>=33.3?"#eab308":"#dc2626";
  var pctLbl=pct>=100?"Compra finalizada":pct>0?(pct.toFixed(1)+"% comprado"):"Sin compras";
  var pp=document.getElementById("prog-pct");
  var pl=document.getElementById("prog-lbl");
  var pb=document.getElementById("prog-bar");
  if(pp){{pp.textContent=pct>=100?"100%":(pct.toFixed(1)+"%");pp.style.color=pctCol;}}
  if(pl){{pl.textContent=pctLbl;pl.style.color=pctCol;}}
  if(pb){{pb.style.width=Math.min(pct,100)+"%";pb.style.background=pctCol;}}
  window.parent.postMessage({{type:"rc_vals",vals:vals,tP:tP,tR:tR}},"*");
}}
var _rcCatFiltro='';
window.applyFilters=function(catOverride){{
  if(catOverride!==undefined) _rcCatFiltro=catOverride;
  var q=document.getElementById('rc-search')?document.getElementById('rc-search').value.toLowerCase():'';
  document.querySelectorAll("tbody tr").forEach(function(r){{
    var txt=r.cells[1]?r.cells[1].textContent.toLowerCase():"";
    var cat=r.cells[0]?r.cells[0].textContent.trim():"";
    var matchTxt=!q||txt.indexOf(q)>-1;
    var matchCat=!_rcCatFiltro||cat===_rcCatFiltro;
    r.style.display=(matchTxt&&matchCat)?"":"none";
  }});
}}
window.filterRows=function(q){{applyFilters();}};
function _rcRgba(h,a){{h=h.replace('#','');return 'rgba('+parseInt(h.substr(0,2),16)+','+parseInt(h.substr(2,2),16)+','+parseInt(h.substr(4,2),16)+','+a+')';}}
window.rcFilterCat=function(el){{
  var cat=el.getAttribute('data-cat')||'';
  _rcCatFiltro=(_rcCatFiltro===cat)?'':cat;
  document.querySelectorAll('.rc-cat-card').forEach(function(c){{
    var cc=c.getAttribute('data-color')||'#6366f1';
    var nm=c.getAttribute('data-name')||'';
    var active=(_rcCatFiltro!==''&&c.getAttribute('data-cat')===_rcCatFiltro);
    c.style.background=active?_rcRgba(cc,0.15):'#fff';
    c.style.border=active?('2px solid '+cc):('1.5px solid '+_rcRgba(cc,0.3));
    c.style.borderLeft='4px solid '+cc;
    var cn=c.querySelector('.rc-cname');
    if(cn)cn.textContent=nm+(active?' \\u2713':'');
  }});
  applyFilters(_rcCatFiltro);
}};
document.querySelectorAll(".rc-real").forEach(function(inp){{
  attachListeners(inp, inp.closest("tr").querySelector(".rc-adic"));
}});
window.addEventListener("load",function(){{calc();}});
var sinPrecioEl=document.getElementById("sin-precio");
if(sinPrecioEl){{
  sinPrecioEl.addEventListener("input",function(){{
    var raw=this.value.replace(/[^0-9]/g,"");
    this.value=raw?"$"+parseInt(raw).toLocaleString("de-DE"):"";
  }});
  sinPrecioEl.addEventListener("blur",function(){{
    var raw=this.value.replace(/[^0-9]/g,"");
    this.value=raw?"$"+parseInt(raw).toLocaleString("de-DE"):"";
  }});
}}
window.switchAddTab=function(tab){{
  var reg=document.getElementById("add-con-reg");
  var sin=document.getElementById("add-sin-reg");
  var tbReg=document.getElementById("tab-reg");
  var tbSin=document.getElementById("tab-sin");
  if(tab==="reg"){{
    reg.style.display="grid";sin.style.display="none";
    tbReg.style.cssText="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #f97316;background:#fff7ed;color:#f97316;cursor:pointer";
    tbSin.style.cssText="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #e2e8f0;background:#fff;color:#94a3b8;cursor:pointer";
  }}else{{
    reg.style.display="none";sin.style.display="grid";
    tbSin.style.cssText="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #ec4899;background:#fdf2f8;color:#ec4899;cursor:pointer";
    tbReg.style.cssText="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #e2e8f0;background:#fff;color:#94a3b8;cursor:pointer";
  }}
}};
window.addRowSinReg=function(){{
  var catEl=document.getElementById("sin-cat");
  var itemEl=document.getElementById("sin-item");
  var cantEl=document.getElementById("sin-cant");
  var precioEl=document.getElementById("sin-precio");
  if(!catEl.value.trim()||!itemEl.value.trim()){{alert("Ingresa categoría y nombre del ítem");return;}}
  var rawPrecio=precioEl.value.replace(/[^0-9]/g,"");
  var precio=parseInt(rawPrecio)||0;
  var cant=parseInt(cantEl.value)||1;
  var tr=document.createElement("tr");
  tr.style.cssText="background:#fdf2f8;border-bottom:1px solid #eef0f6;border-left:3px solid #ec4899";
  tr.dataset.idx=String(_addIdx);tr.dataset.pu="0";tr.dataset.cant=String(cant);
  tr.dataset.adicional="1";tr.setAttribute("data-sin-registro","1");
  tr.innerHTML="<td style='padding:5px 8px;font-size:.75rem;color:#ec4899'>"+catEl.value.trim()+"</td>"
    +"<td style='padding:5px 8px;font-size:.82rem'>"+itemEl.value.trim()+"</td>"
    +"<td style='padding:5px 8px;text-align:right'>"+cant+"</td>"
    +"<td style='padding:5px 8px;text-align:right;font-weight:600'>—</td>"
    +'<td style="padding:3px 4px"><input type="text" inputmode="numeric" value="'+("$"+precio.toLocaleString("de-DE"))+'" class="rc-real" data-idx="'+_addIdx+'" data-val="'+precio+'" style="width:100%;border:1.5px solid #fbcfe8;border-radius:6px;padding:5px;font-size:13px;text-align:right;background:#fdf2f8;box-sizing:border-box"/></td>'
    +'<td style="padding:3px 4px"><input type="number" min="0" step="1" value="0" class="rc-adic" data-idx="'+_addIdx+'" style="width:100%;border:1.5px solid #fbcfe8;border-radius:6px;padding:5px;font-size:13px;text-align:right;background:#fdf2f8;box-sizing:border-box"/></td>'
    +'<td class="rc-dif" style="padding:5px 8px;text-align:right;font-weight:700;color:#ec4899;white-space:nowrap">—</td>'
    +'<td style="padding:3px 6px;text-align:center"><button onclick="window.removeRow(this)" style="background:none;border:none;color:#ef4444;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1;" title="Eliminar">&#10005;</button></td>';
  document.querySelector("tbody").appendChild(tr);
  attachListeners(tr.querySelector(".rc-real"),tr.querySelector(".rc-adic"));
  _addIdx++;
  catEl.value="";itemEl.value="";cantEl.value="1";precioEl.value="";
  calc();checkSaveBtn();
}};
window.onTipoChange=function(){{
  var tipo=document.getElementById("tipo-compra").value;
  var sw=document.getElementById("subtipo-wrap");
  var ss=document.getElementById("subtipo-compra");
  sw.className="rc-field"+(tipo?"" : " rc-hidden");
  ss.innerHTML="";
  if(tipo==="online"){{
    [["retiro","Retiro"],["despacho","Despacho"]].forEach(function(o){{
      var opt=document.createElement("option");opt.value=o[0];opt.textContent=o[1];ss.appendChild(opt);
    }});
  }}else if(tipo==="presencial"){{
    [["completo","Retiro Completo"],["parcial","Retiro Parcial"],["despacho","Despacho"]].forEach(function(o){{
      var opt=document.createElement("option");opt.value=o[0];opt.textContent=o[1];ss.appendChild(opt);
    }});
  }}
  window.onSubtipoChange();
}};
window.onSubtipoChange=function(){{
  var tipo=document.getElementById("tipo-compra").value;
  var sub=document.getElementById("subtipo-compra").value;
  var fw=document.getElementById("fecha-wrap");
  var fl=document.getElementById("fecha-lbl");
  var pw=document.getElementById("faltó-wrap");
  var needFecha=(tipo==="online")||(tipo==="presencial"&&sub!=="completo");
  fw.className="rc-field"+(needFecha?"":" rc-hidden");
  if(tipo==="presencial"&&sub==="parcial"){{
    fl.innerHTML=ICO_CAL+"¿Para cuándo llega lo que faltó? *";
    pw.className="rc-field";
  }}else{{
    fl.innerHTML=ICO_CAL+"¿Para cuándo? *";
    pw.className="rc-field rc-hidden";
  }}
  window.checkSaveBtn();
}};
window.removeRow=function(btn){{
  var tr=btn.parentElement;
  while(tr&&tr.tagName!=="TR")tr=tr.parentElement;
  if(tr)tr.remove();
  calc();checkSaveBtn();
}};
function checkSaveBtn(){{
  var hasVals=false;
  document.querySelectorAll("tr[data-idx]").forEach(function(r){{
    var re=parseFloat(r.querySelector(".rc-real").dataset.val)||0;
    if(re>0) hasVals=true;
  }});
  var lugar=document.getElementById("lugar-compra");
  var hasLugar=lugar&&lugar.value.trim().length>0;
  var hasFactura=_facturaFile!==null;
  var tipo=document.getElementById("tipo-compra");
  var hasTipo=tipo&&tipo.value.length>0;
  var fw=document.getElementById("fecha-wrap");
  var fechaOk=!fw||fw.className.indexOf("rc-hidden")>-1||(document.getElementById("fecha-compra")&&document.getElementById("fecha-compra").value.length>0);
  var pw=document.getElementById("faltó-wrap");
  var faltóOk=!pw||pw.className.indexOf("rc-hidden")>-1||(document.getElementById("falto-texto")&&document.getElementById("falto-texto").value.trim().length>0);
  var ok=hasVals&&hasLugar&&hasFactura&&hasTipo&&fechaOk&&faltóOk;
  var btn=document.getElementById("save-btn");
  if(btn){{btn.disabled=!ok;btn.style.opacity=ok?"1":"0.5";}}
}}
window.checkSaveBtn=checkSaveBtn;
document.getElementById("factura-input") && document.getElementById("factura-input").addEventListener("change",function(){{
  _facturaFile=this.files[0]||null;
  var lbl=document.getElementById("factura-label");
  var clr=document.getElementById("factura-clear");
  if(_facturaFile){{
    if(lbl)lbl.innerHTML=ICO_CLIP+_facturaFile.name+'<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
    if(clr)clr.style.display="inline-flex";
  }}else{{
    if(lbl)lbl.innerHTML=ICO_CLIP+'Seleccionar factura PDF<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
    if(clr)clr.style.display="none";
  }}
  checkSaveBtn();
}});
window.clearFactura=function(){{
  _facturaFile=null;
  var lbl=document.getElementById("factura-label");
  var clr=document.getElementById("factura-clear");
  if(lbl)lbl.innerHTML=ICO_CLIP+'Seleccionar factura PDF<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
  if(clr)clr.style.display="none";
  var ni=document.getElementById("factura-input");
  if(ni)ni.addEventListener("change",function(){{
    _facturaFile=this.files[0]||null;
    var l2=document.getElementById("factura-label");
    var c2=document.getElementById("factura-clear");
    if(_facturaFile){{
      if(l2)l2.innerHTML=ICO_CLIP+_facturaFile.name+'<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
      if(c2)c2.style.display="inline-block";
    }}
    checkSaveBtn();
  }});
  checkSaveBtn();
}};
window.guardarRegistro=async function(){{
  var btn=document.getElementById("save-btn");
  var status=document.getElementById("save-status");
  if(!_facturaFile){{status.textContent="Debes subir una factura primero";status.style.color="#dc2626";return;}}
  btn.disabled=true;btn.textContent="Verificando compras previas...";
  // Ya comprados: Python ya lo pasa server-side (service key) en ITEMS_YA_COMPRADOS
  // → evitamos el fetch desde el navegador (que RLS bloquearía).
  var itemsYaComprados=(ITEMS_YA_COMPRADOS||[]).slice();
  var items=[];
  document.querySelectorAll("tr[data-idx]").forEach(function(r){{
    var idx=parseInt(r.dataset.idx)||0;
    var inp=r.querySelector(".rc-real");
    var re=parseFloat(inp.dataset.val)||0;
    if(re<=0) return;
    if(idx >= 10000) {{
    }} else {{
      if(r.dataset.comprado==="1") return;
      if(!inp.value||inp.value.trim()==="") return;
      var itemNombre=r.cells[1]?r.cells[1].textContent.trim():"";
      if(itemsYaComprados.indexOf(itemNombre)>-1) return;
    }}
    var pu=+r.dataset.pu||0;
    var c=+r.dataset.cant||1;
    var ad=+r.querySelector(".rc-adic").value||0;
    var dif=(pu-re)*c-(ad*re);
    items.push({{
      categoria:r.cells[0]?r.cells[0].textContent.trim():"",
      item:r.cells[1]?r.cells[1].textContent.trim():"",
      cantidad:c,
      precio_presupuestado:pu,
      precio_real:re,
      adicional:ad,
      diferencia:dif,
      es_adicional:idx>=10000||r.dataset.adicional==="1",
      sin_registro:r.getAttribute("data-sin-registro")==="1"
    }});
  }});
  if(items.length===0){{status.textContent="Ingresa al menos un precio real";status.style.color="#dc2626";btn.disabled=false;btn.textContent="Guardar compra";return;}}
  btn.disabled=true;btn.textContent="Subiendo factura...";status.textContent="";
  try{{
    var ext=_facturaFile.name.split(".").pop();
    var path="cotizacion-"+EP_NUM+"/"+Date.now()+"."+ext;
    var uploadResp=await fetch(SUPA_URL+"/storage/v1/object/facturas/"+path,{{
      method:"POST",
      headers:{{"Authorization":"Bearer "+SUPA_KEY,"apikey":SUPA_KEY,"Content-Type":_facturaFile.type,"x-upsert":"true"}},
      body:_facturaFile
    }});
    if(!uploadResp.ok) throw new Error("Error subiendo factura: "+uploadResp.status);
    _facturaUrl=SUPA_URL+"/storage/v1/object/public/facturas/"+path;
    _facturaNom=_facturaFile.name;
    var tP=0,tR=0;
    items.forEach(function(it){{tP+=it.precio_presupuestado*it.cantidad;tR+=(it.precio_real*it.cantidad)+(it.adicional*it.precio_real);}});
    btn.textContent="Guardando registro...";
    var lugarEl=document.getElementById("lugar-compra");
    var lugarVal=lugarEl?lugarEl.value.trim():"";
    var tipoVal=document.getElementById("tipo-compra")?document.getElementById("tipo-compra").value:"";
    var subtipoVal=document.getElementById("subtipo-compra")?document.getElementById("subtipo-compra").value:"";
    var fechaVal=document.getElementById("fecha-compra")?document.getElementById("fecha-compra").value:"";
    var faltóVal=document.getElementById("falto-texto")?document.getElementById("falto-texto").value.trim():"";
    var obsVal=document.getElementById("obs-compra")?document.getElementById("obs-compra").value.trim():"";
    // Guardado SERVER-SIDE: en vez de POST a registro_compras (clave anon, que RLS
    // bloquearía), mandamos el registro a Python via query param + popstate (rerun
    // SIN recargar → NO desloguea al usuario de la app). Python inserta con la
    // service key. El balance lo recalcula el servidor (no se confía en el cliente).
    var _rcPayload={{
      cotizacion_numero:EP_NUM,
      usuario_registro:USUARIO,
      lugar_compra:lugarVal,
      tipo_compra:tipoVal,
      subtipo_compra:subtipoVal,
      fecha_entrega_compra:fechaVal,
      falto_retirar:faltóVal,
      observaciones:obsVal,
      factura_url:_facturaUrl,
      factura_nombre:_facturaNom,
      items:items,
      total_presupuestado:tP,
      total_real:tR
    }};
    btn.textContent="Guardado";btn.style.background="#16a34a";
    status.textContent="Guardado. Actualizando...";
    status.style.color="#16a34a";
    setTimeout(function(){{
      var url=new URL(window.parent.location.href);
      url.searchParams.set("rc_save", JSON.stringify(_rcPayload));
      window.parent.history.replaceState({{}},"",url);
      window.parent.dispatchEvent(new PopStateEvent("popstate"));
    }},600);
  }}catch(e){{
    btn.disabled=false;btn.textContent="Guardar compra";
    status.textContent="Error: "+e.message;status.style.color="#dc2626";
  }}
}};
calc();
}})();</script>"""
    return html
