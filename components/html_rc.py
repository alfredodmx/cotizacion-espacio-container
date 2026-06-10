"""
Genera el HTML del panel de registro de compras (RC).
"""


def build_rc_html(rc_prods, rc_cat_json, rc_prev, items_comprados=None, es_admin=False,
                  supa_url='', supa_key='', ep='', usuario='',
                  items_ya_comprados_json='[]', total_items_presupuesto=0, cats_cards_html=''):
    rows = ""
    items_comprados = items_comprados or {}

    for ri, prod in enumerate(rc_prods):
        cat   = str(prod.get('Categoria', ''))
        item  = str(prod.get('Item', ''))
        cant  = round(float(prod.get('Cantidad', 1) or 1))
        pu    = round(float(prod.get('Precio Unitario', 0) or 0))
        _es_adicional = bool(prod.get('_adicional', False))
        _es_sin_reg   = bool(prod.get('_sin_registro', False))
        _ic           = items_comprados.get(item, {})
        _ya_comprado  = bool(_ic and float(_ic.get('real', 0) or 0) > 0) or _es_adicional
        _readonly     = _ya_comprado and not es_admin

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

        pu_fmt   = '$' + f'{pu:,}'.replace(',', '.')
        pv       = rc_prev.get(str(ri), {})
        vreal    = float(_ic.get('real', 0)) if _ya_comprado else (pv.get('real', 0) or 0)
        vadic    = int(_ic.get('adicional', 0)) if _ya_comprado else (pv.get('adic', 0) or 0)
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
      <th>Categoría</th><th>Ítem</th><th class="r">Cant.</th>
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
      <div style="font-size:11px;margin-top:4px" id="b-icon">&#x2705; Ahorro</div><div style="font-size:17px;font-weight:900" id="b-t">$0</div>
    </div>
    <div style="border-left:2px solid #fed7aa;padding-left:10px;background:#fff7ed;border-radius:8px;">
      <div style="font-size:10px;font-weight:700;color:#f97316;letter-spacing:.05em;text-transform:uppercase;margin-bottom:2px">➕ Adicionales</div>
      <div style="font-size:9px;color:#f97316;margin-bottom:6px;font-weight:600">Con registro</div>
      <div style="font-size:11px;color:#f97316">Subtotal neto</div><div style="font-size:14px;font-weight:700;color:#f97316" id="ta-n">$0</div>
      <div style="font-size:11px;color:#f97316;margin-top:4px">IVA (19%)</div><div style="font-size:12px;font-weight:600;color:#f97316" id="ta-i">$0</div>
      <div style="font-size:11px;color:#f97316;margin-top:4px">Total con IVA</div><div style="font-size:16px;font-weight:900;color:#f97316" id="ta-t">$0</div>
    </div>
    <div style="border-left:2px solid #fbcfe8;padding-left:10px;background:#fdf2f8;border-radius:8px;">
      <div style="font-size:10px;font-weight:700;color:#ec4899;letter-spacing:.05em;text-transform:uppercase;margin-bottom:2px">➕ Adicionales</div>
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
      <button onclick="window.switchAddTab('reg')" id="tab-reg" style="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #f97316;background:#fff7ed;color:#f97316;cursor:pointer"><span style="color:#f97316;font-size:24px;line-height:1;vertical-align:middle;">●</span> Con registro</button>
      <button onclick="window.switchAddTab('sin')" id="tab-sin" style="font-size:11px;font-weight:700;padding:4px 12px;border-radius:6px;border:1.5px solid #e2e8f0;background:#fff;color:#94a3b8;cursor:pointer"><span style="color:#ec4899;font-size:24px;line-height:1;vertical-align:middle;">●</span> Sin registro</button>
    </div>
    <div id="add-con-reg" style="display:grid;grid-template-columns:1.5fr 3fr 0.8fr 1.2fr auto;gap:6px;align-items:end">
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Categoría</div>
        <select id="add-cat" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px"><option value="">Seleccionar...</option></select></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Ítem</div>
        <select id="add-item" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px"><option value="">Seleccionar categoría primero</option></select></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Cant.</div>
        <input id="add-cant" type="number" min="1" value="1" style="width:100%;border:1px solid #cbd5e1;border-radius:6px;padding:5px;font-size:12px;text-align:right"/></div>
      <div><div style="font-size:10px;color:#64748b;margin-bottom:3px">Presup. unit.</div>
        <div id="add-precio" style="border:1px solid #e2e8f0;border-radius:6px;padding:5px 8px;font-size:12px;font-weight:600;background:#f8fafc;text-align:right">$0</div></div>
      <div style="padding-bottom:1px">
        <button onclick="window.addRow()" style="background:#f97316;color:#fff;border:none;border-radius:6px;padding:6px 16px;font-size:12px;font-weight:700;cursor:pointer">+ Agregar</button></div>
    </div>
    <div id="add-sin-reg" style="display:none;grid-template-columns:1.5fr 3fr 0.8fr 1.2fr auto;gap:6px;align-items:end">
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Categoría *</div>
        <input id="sin-cat" type="text" placeholder="Ej: Herramientas" style="width:100%;border:1px solid #fbcfe8;border-radius:6px;padding:5px;font-size:12px;background:#fdf2f8;box-sizing:border-box"/></div>
      <div style="padding-right:2px"><div style="font-size:10px;color:#ec4899;margin-bottom:3px">Nombre del ítem *</div>
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
    <div style="font-size:11px;font-weight:700;color:#fff;letter-spacing:.05em;text-transform:uppercase;margin-bottom:8px">📎 Adjuntar Factura y Guardar</div>
    <style>
    .rc-field{{margin-bottom:8px}}
    .rc-lbl{{font-size:11px;color:rgba(255,255,255,0.6);margin-bottom:3px}}
    .rc-inp{{width:100%;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:7px 10px;font-size:13px;background:rgba(255,255,255,0.08);color:#fff;box-sizing:border-box;outline:none}}
    .rc-inp::placeholder{{color:rgba(255,255,255,0.35)}}
    .rc-sel{{width:100%;border:1px solid rgba(255,255,255,0.3);border-radius:6px;padding:7px 10px;font-size:13px;background:#1e2447;color:#fff;box-sizing:border-box;outline:none;cursor:pointer}}
    .rc-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
    .rc-hidden{{display:none}}
    </style>
    <div class="rc-grid">
      <div class="rc-field">
        <div class="rc-lbl">🏪 ¿Dónde compraste? *</div>
        <input id="lugar-compra" type="text" class="rc-inp" placeholder="Ej: Ferretería López" oninput="window.checkSaveBtn()"/>
      </div>
      <div class="rc-field">
        <div class="rc-lbl">🛒 Tipo de compra *</div>
        <select id="tipo-compra" class="rc-sel" onchange="window.onTipoChange()">
          <option value="">Seleccionar...</option>
          <option value="online">Compra Online</option>
          <option value="presencial">Compra Presencial</option>
        </select>
      </div>
    </div>
    <div id="subtipo-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl" id="subtipo-lbl">Modalidad *</div>
      <select id="subtipo-compra" class="rc-sel" onchange="window.onSubtipoChange()"></select>
    </div>
    <div id="fecha-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl" id="fecha-lbl">📅 ¿Para cuándo? *</div>
      <input id="fecha-compra" type="date" class="rc-inp" oninput="window.checkSaveBtn()" onchange="window.checkSaveBtn()"/>
    </div>
    <div id="faltó-wrap" class="rc-field rc-hidden">
      <div class="rc-lbl">📋 ¿Qué faltó por retirar? *</div>
      <textarea id="falto-texto" class="rc-inp" rows="2" placeholder="Describe los ítems que faltaron..." oninput="window.checkSaveBtn()" style="resize:vertical"></textarea>
    </div>
    <div class="rc-field">
      <div class="rc-lbl">📝 Observaciones adicionales (opcional)</div>
      <textarea id="obs-compra" class="rc-inp" rows="2" placeholder="Notas, motivos u observaciones de esta compra..." style="resize:vertical"></textarea>
    </div>
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
      <label id="factura-label" style="background:rgba(255,255,255,0.1);color:#fff;border:1px dashed rgba(255,255,255,0.4);border-radius:6px;padding:6px 14px;font-size:12px;cursor:pointer;white-space:nowrap">📎 Seleccionar factura PDF
        <input id="factura-input" type="file" accept=".pdf" style="display:none"/>
      </label>
      <button id="factura-clear" onclick="window.clearFactura()" style="display:none;background:rgba(220,38,38,0.7);color:#fff;border:none;border-radius:6px;padding:6px 10px;font-size:12px;cursor:pointer;white-space:nowrap">✕ Quitar</button>
      <div id="save-status" style="font-size:12px;color:rgba(255,255,255,0.7);flex:1"></div>
      <button id="save-btn" onclick="window.guardarRegistro()" disabled style="background:#10b981;color:#fff;border:none;border-radius:8px;padding:8px 24px;font-size:13px;font-weight:700;cursor:pointer;opacity:0.5;white-space:nowrap">💾 Guardar compra</button>
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
    +'<td style="padding:3px 6px;text-align:center"><button onclick="window.removeRow(this)" style="background:none;border:none;color:#ef4444;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1;" title="Eliminar">✕</button></td>';
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
  if(bi)bi.textContent=b>=0?"✅ Ahorro":"❌ Sobrecosto";
  var comprados=vals.filter(function(v){{return v.real>0&&v.idx<10000;}}).length;
  var pct=TOTAL_ITEMS>0?Math.round(comprados/TOTAL_ITEMS*1000)/10:0;
  var pctCol=pct>=100?"#3b82f6":pct>=66.6?"#16a34a":pct>=33.3?"#eab308":"#dc2626";
  var pctLbl=pct>=100?"🔵 Compra finalizada":pct>0?(pct.toFixed(1)+"% comprado"):"Sin compras";
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
    +'<td style="padding:3px 6px;text-align:center"><button onclick="window.removeRow(this)" style="background:none;border:none;color:#ef4444;font-size:14px;cursor:pointer;padding:2px 4px;line-height:1;" title="Eliminar">✕</button></td>';
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
  sw.className="rc-field"+(tipo?"":" rc-hidden");
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
    fl.textContent="📅 ¿Para cuándo llega lo que faltó? *";
    pw.className="rc-field";
  }}else{{
    fl.textContent="📅 ¿Para cuándo? *";
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
    if(lbl)lbl.innerHTML="📎 "+_facturaFile.name+'<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
    if(clr)clr.style.display="inline-block";
  }}else{{
    if(lbl)lbl.innerHTML='📎 Seleccionar factura PDF<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
    if(clr)clr.style.display="none";
  }}
  checkSaveBtn();
}});
window.clearFactura=function(){{
  _facturaFile=null;
  var lbl=document.getElementById("factura-label");
  var clr=document.getElementById("factura-clear");
  if(lbl)lbl.innerHTML='📎 Seleccionar factura PDF<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
  if(clr)clr.style.display="none";
  var ni=document.getElementById("factura-input");
  if(ni)ni.addEventListener("change",function(){{
    _facturaFile=this.files[0]||null;
    var l2=document.getElementById("factura-label");
    var c2=document.getElementById("factura-clear");
    if(_facturaFile){{
      if(l2)l2.innerHTML="📎 "+_facturaFile.name+'<input id="factura-input" type="file" accept=".pdf" style="display:none"/>';
      if(c2)c2.style.display="inline-block";
    }}
    checkSaveBtn();
  }});
  checkSaveBtn();
}};
window.guardarRegistro=async function(){{
  var btn=document.getElementById("save-btn");
  var status=document.getElementById("save-status");
  if(!_facturaFile){{status.textContent="⚠️ Debes subir una factura primero";status.style.color="#dc2626";return;}}
  btn.disabled=true;btn.textContent="⏳ Verificando compras previas...";
  var yaCompradosResp=await fetch(SUPA_URL+"/rest/v1/registro_compras?cotizacion_numero=eq."+EP_NUM+"&select=items",{{
    headers:{{"Authorization":"Bearer "+SUPA_KEY,"apikey":SUPA_KEY}}
  }});
  var yaCompradosData=await yaCompradosResp.json();
  var itemsYaComprados=[];
  (yaCompradosData||[]).forEach(function(reg){{
    (reg.items||[]).forEach(function(it){{if(it.item)itemsYaComprados.push(it.item);}});
  }});
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
  if(items.length===0){{status.textContent="⚠️ Ingresa al menos un precio real";status.style.color="#dc2626";return;}}
  btn.disabled=true;btn.textContent="⏳ Subiendo factura...";status.textContent="";
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
    btn.textContent="⏳ Guardando registro...";
    var lugarEl=document.getElementById("lugar-compra");
    var lugarVal=lugarEl?lugarEl.value.trim():"";
    var tipoVal=document.getElementById("tipo-compra")?document.getElementById("tipo-compra").value:"";
    var subtipoVal=document.getElementById("subtipo-compra")?document.getElementById("subtipo-compra").value:"";
    var fechaVal=document.getElementById("fecha-compra")?document.getElementById("fecha-compra").value:"";
    var faltóVal=document.getElementById("falto-texto")?document.getElementById("falto-texto").value.trim():"";
    var obsVal=document.getElementById("obs-compra")?document.getElementById("obs-compra").value.trim():"";
    var saveResp=await fetch(SUPA_URL+"/rest/v1/registro_compras",{{
      method:"POST",
      headers:{{
        "Authorization":"Bearer "+SUPA_KEY,"apikey":SUPA_KEY,
        "Content-Type":"application/json","Prefer":"return=minimal"
      }},
      body:JSON.stringify({{
        cotizacion_numero:EP_NUM,usuario_registro:USUARIO,
        lugar_compra:lugarVal,tipo_compra:tipoVal,subtipo_compra:subtipoVal,
        fecha_entrega_compra:fechaVal,falto_retirar:faltóVal,observaciones:obsVal,
        factura_url:_facturaUrl,factura_nombre:_facturaNom,
        items:items,total_presupuestado:tP,total_real:tR,balance:tP-tR
      }})
    }});
    if(!saveResp.ok) throw new Error("Error guardando registro: "+saveResp.status);
    btn.textContent="✅ Guardado";btn.style.background="#16a34a";
    status.textContent="✅ Guardado correctamente. Actualizando...";status.style.color="#16a34a";
    setTimeout(function(){{
      var url=new URL(window.parent.location.href);
      url.searchParams.set("rc_saved",Date.now());
      window.parent.history.replaceState({{}},"",url);
      window.parent.dispatchEvent(new PopStateEvent("popstate"));
    }},1000);
    items.forEach(function(it){{
      document.querySelectorAll("tr[data-idx]").forEach(function(r){{
        if(r.cells[1]&&r.cells[1].textContent.trim()===it.item){{
          r.style.background="#f0fdf4";
          r.querySelectorAll("input").forEach(function(inp){{inp.setAttribute("readonly","");inp.style.background="#f0fdf4";}});
        }}
      }});
    }});
  }}catch(e){{
    btn.disabled=false;btn.textContent="💾 Guardar compra";
    status.textContent="❌ Error: "+e.message;status.style.color="#dc2626";
  }}
}};
calc();
}})();</script>"""
    return html
