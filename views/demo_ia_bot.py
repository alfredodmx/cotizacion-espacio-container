"""
Bot de IA — DEMO puramente visual (botón flotante + chat con respuestas
scripteadas). NO usa IA real, NO consulta la base de datos y NO toca la
lógica de cotización. Sirve solo para MOSTRAR el concepto (asistente de
presupuestos estilo RAG) en el sistema.

Todo se inyecta en el documento padre desde un components.html (height=0),
igual que los demás elementos flotantes de la app. Los handlers se re-atan
en cada run con propiedades onX (el iframe se recrea en los reruns).
"""
import streamlit as st
import streamlit.components.v1 as components


def render_demo_ia_bot():
    # No mostrar en el formulario público del cliente ni sin sesión.
    try:
        if st.query_params.get("cliente") == "1":
            return
    except Exception:
        pass
    if not st.session_state.get("auth_user"):
        return

    components.html("""<script>(function(){
var D=window.parent.document, W=window.parent, B=D.body;

/* ── CSS (siempre reemplazar) ─────────────────────────────────────── */
var oc=D.getElementById('_demo_ia_css'); if(oc) oc.remove();
var css=D.createElement('style'); css.id='_demo_ia_css';
css.textContent=`
#_demo_ia_fab{position:fixed;bottom:76px;right:24px;z-index:90000;width:62px;height:62px;border-radius:50%;
 background:linear-gradient(135deg,#334155,#0f172a);border:none;cursor:pointer;display:flex;align-items:center;
 justify-content:center;box-shadow:0 12px 30px rgba(15,23,42,.42);transition:transform .18s cubic-bezier(.22,1,.36,1);}
#_demo_ia_fab:hover{transform:scale(1.08) translateY(-2px);}
#_demo_ia_fab.hidden{display:none;}
#_demo_ia_fab svg{width:38px;height:38px;color:#fff;position:relative;z-index:2;}
#_demo_ia_fab::after{content:"";position:absolute;inset:0;border-radius:50%;border:2px solid rgba(51,65,85,.55);
 animation:diaPulse 2.1s ease-out infinite;}
@keyframes diaPulse{0%{transform:scale(1);opacity:.7}100%{transform:scale(1.5);opacity:0}}
#_demo_ia_fab .dia-fab-badge{position:absolute;top:-3px;right:-3px;background:#f59e0b;color:#fff;
 font:800 8px Montserrat,sans-serif;letter-spacing:.04em;padding:2px 5px;border-radius:6px;z-index:3;
 box-shadow:0 2px 6px rgba(0,0,0,.25);}

#_demo_ia_panel{position:fixed;bottom:76px;right:24px;z-index:90001;width:384px;max-width:calc(100vw - 32px);
 height:594px;max-height:calc(100vh - 104px);background:#fff;border-radius:20px;overflow:hidden;display:none;
 flex-direction:column;box-shadow:0 26px 72px rgba(15,23,42,.34);border:1px solid #e8ebf5;
 font-family:'Plus Jakarta Sans',system-ui,sans-serif;}
#_demo_ia_panel.on{display:flex;animation:diaIn .28s cubic-bezier(.22,1,.36,1);}
@keyframes diaIn{from{opacity:0;transform:translateY(18px) scale(.98)}to{opacity:1;transform:none}}
.dia-head{background:linear-gradient(135deg,#334155,#0f172a);padding:14px 15px;display:flex;align-items:center;gap:11px;color:#fff;}
.dia-avatar{width:38px;height:38px;border-radius:11px;background:rgba(255,255,255,.16);display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.dia-avatar svg{width:21px;height:21px;color:#fff;}
.dia-t{font:800 .95rem Montserrat,sans-serif;line-height:1.1;display:flex;align-items:center;gap:7px;}
.dia-pill{background:#f59e0b;color:#fff;font:800 8.5px Montserrat,sans-serif;letter-spacing:.06em;padding:2px 6px;border-radius:6px;}
.dia-s{font-size:.7rem;opacity:.9;font-weight:600;margin-top:3px;display:flex;align-items:center;gap:6px;}
.dia-dot{width:7px;height:7px;border-radius:50%;background:#4ade80;box-shadow:0 0 0 3px rgba(74,222,128,.3);}
.dia-x{margin-left:auto;background:rgba(255,255,255,.16);border:none;width:30px;height:30px;border-radius:9px;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;}
.dia-x:hover{background:rgba(255,255,255,.3);}
.dia-x svg{width:16px;height:16px;}
.dia-msgs{flex:1;overflow-y:auto;padding:16px;background:#f7f9fc;display:flex;flex-direction:column;gap:12px;}
.dia-msg{max-width:88%;font-size:.83rem;line-height:1.5;}
.dia-user{align-self:flex-end;background:linear-gradient(135deg,#334155,#0f172a);color:#fff;padding:9px 13px;
 border-radius:14px 14px 4px 14px;font-weight:500;box-shadow:0 3px 10px rgba(15,23,42,.18);}
.dia-bot{align-self:flex-start;background:#fff;color:#0f172a;padding:12px 14px;border-radius:14px 14px 14px 4px;
 border:1px solid #e8ebf5;box-shadow:0 3px 12px rgba(15,23,42,.05);}
.dia-chip{display:inline-flex;align-items:center;gap:7px;margin-top:11px;background:#1e293b;color:#e2e8f0;
 border:1px solid #334155;border-radius:99px;padding:8px 14px;font:700 .76rem 'Plus Jakarta Sans',sans-serif;cursor:pointer;transition:all .15s;}
.dia-chip:hover{background:#334155;transform:translateY(-1px);}
.dia-chip svg{width:14px;height:14px;}
.dia-dots{display:inline-flex;gap:4px;padding:3px 2px;}
.dia-dots i{width:7px;height:7px;border-radius:50%;background:#94a3b8;display:inline-block;animation:diaBounce 1.2s infinite;}
.dia-dots i:nth-child(2){animation-delay:.18s}.dia-dots i:nth-child(3){animation-delay:.36s}
@keyframes diaBounce{0%,60%,100%{transform:translateY(0);opacity:.5}30%{transform:translateY(-5px);opacity:1}}
.dia-bud-h{font:800 .92rem Montserrat,sans-serif;color:#0f172a;}
.dia-bud-sub{font-size:.72rem;color:#64748b;margin-top:2px;}
.dia-sec{font:800 .64rem Montserrat,sans-serif;letter-spacing:.06em;text-transform:uppercase;display:flex;align-items:center;gap:6px;margin:13px 0 6px;}
.dia-sec.inc{color:#15803d}.dia-sec.exc{color:#b45309}
.dia-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:.78rem;color:#334155;border-bottom:1px dashed #eef2f7;}
.dia-rn{flex:1;}.dia-rp{font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums;}
.dia-row.exc .dia-rn{color:#94a3b8;text-decoration:line-through;}
.dia-row svg{width:14px;height:14px;flex-shrink:0;}
.dia-total{margin-top:13px;background:#0f172a;border:1px solid #334155;border-radius:12px;padding:11px 13px;display:flex;align-items:center;justify-content:space-between;}
.dia-tl{font:800 .68rem Montserrat,sans-serif;text-transform:uppercase;letter-spacing:.05em;color:#cbd5e1;}
.dia-tl small{display:block;font:600 .62rem 'Plus Jakarta Sans',sans-serif;text-transform:none;letter-spacing:0;color:#94a3b8;margin-top:2px;}
.dia-tv{font:900 1.08rem Montserrat,sans-serif;color:#fff;}
.dia-note{margin-top:11px;font-size:.69rem;color:#94a3b8;line-height:1.45;display:flex;gap:6px;}
.dia-note svg{width:13px;height:13px;flex-shrink:0;margin-top:1px;color:#f59e0b;}
.dia-input{display:flex;gap:8px;padding:12px;border-top:1px solid #eef2f7;background:#fff;}
.dia-input input{flex:1;border:1px solid #e2e8f0;border-radius:11px;padding:10px 13px;font:500 .83rem 'Plus Jakarta Sans',sans-serif;outline:none;color:#0f172a;}
.dia-input input:focus{border-color:#94a3b8;box-shadow:0 0 0 3px rgba(15,23,42,.08);}
.dia-send{background:linear-gradient(135deg,#334155,#0f172a);border:none;width:42px;border-radius:11px;color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.dia-send:hover{filter:brightness(1.5);}.dia-send svg{width:18px;height:18px;}
@media (max-width:480px){#_demo_ia_panel{height:calc(100vh - 96px);right:16px;bottom:70px;}#_demo_ia_fab{right:16px;bottom:70px;}}
`;
D.head.appendChild(css);

/* ── Íconos ───────────────────────────────────────────────────────── */
var SPARK='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9.937 15.5A2 2 0 0 0 8.5 14.063l-6.135-1.582a.5.5 0 0 1 0-.962L8.5 9.936A2 2 0 0 0 9.937 8.5l1.582-6.135a.5.5 0 0 1 .963 0L14.063 8.5A2 2 0 0 0 15.5 9.937l6.135 1.581a.5.5 0 0 1 0 .964L15.5 14.063a2 2 0 0 0-1.437 1.437l-1.582 6.135a.5.5 0 0 1-.963 0z"/><path d="M20 3v4"/><path d="M22 5h-4"/></svg>';
var BOT='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8V4H8"/><rect width="16" height="12" x="4" y="8" rx="2"/><path d="M2 14h2"/><path d="M20 14h2"/><path d="M15 13v2"/><path d="M9 13v2"/></svg>';
/* Robot constructor: cara de robot con casco de obra + antena (cara grande) */
var ROBOT='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3.2V1.6"/><path d="M5 8a7 5 0 0 1 14 0"/><path d="M2.5 8h19"/><path d="M6 8v8.5a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V8"/><path d="M9.4 12.6h.01"/><path d="M14.6 12.6h.01"/><path d="M9.5 15.8h5"/></svg>';
var XI='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';
var SEND='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/></svg>';
var CK='<svg viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>';
var MN='<svg viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M8 12h8"/></svg>';
var INFO='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>';

/* ── Contenido scripteado ─────────────────────────────────────────── */
function irow(n,p){return '<div class="dia-row">'+CK+'<span class="dia-rn">'+n+'</span><span class="dia-rp">'+p+'</span></div>';}
function erow(n,p){return '<div class="dia-row exc">'+MN+'<span class="dia-rn">'+n+'</span><span class="dia-rp" style="color:#b45309;">'+p+'</span></div>';}
function budgetHTML(){
  return '<div class="dia-bud-h">Borrador de presupuesto — $10.000.000</div>'
    +'<div class="dia-bud-sub">Casa container · priorizado de lo esencial a lo opcional</div>'
    +'<div class="dia-sec inc">'+CK+'Incluye (esencial)</div>'
    +irow('Container 40\\' HC (estructura base)','$3.200.000')
    +irow('Perfiles estructurales y refuerzos','$1.150.000')
    +irow('Aislación térmica (piso/muro/cielo)','$980.000')
    +irow('Revestimiento interior (volcanita)','$870.000')
    +irow('Instalación eléctrica (canalización + tablero)','$760.000')
    +irow('Instalación de agua (red básica)','$540.000')
    +irow('Ventanas termopanel (x2)','$620.000')
    +irow('Puerta principal exterior','$340.000')
    +irow('Baño básico (WC + lavamanos)','$690.000')
    +irow('Terminaciones + mano de obra','$570.000')
    +'<div class="dia-sec exc">'+MN+'No incluye / ajustado para el monto</div>'
    +erow('Muebles de cocina','opcional')
    +erow('Luminarias (se deja la instalación lista)','opcional')
    +erow('Puertas interiores (solo la principal)','opcional')
    +erow('Aire acondicionado','opcional')
    +erow('Revestimiento exterior premium → estándar','ajustado')
    +'<div class="dia-total"><span class="dia-tl">Total estimado<small>de $10.000.000 · queda $280.000</small></span><span class="dia-tv">$9.720.000</span></div>'
    +'<div class="dia-note">'+INFO+'Borrador generado por IA (demo). Un ejecutivo debe revisarlo y ajustarlo antes de enviarlo al cliente.</div>';
}
var GREET='<b>Hola, soy el asistente de cotización.</b><br>Dime un presupuesto objetivo y te armo un borrador priorizando lo esencial de una casa container (sin dejar fuera lo importante).'
  +'<div><span class="dia-chip" data-q="Crea un presupuesto de 10 millones">'+SPARK+'Crea un presupuesto de $10.000.000</span></div>';
var FALLBACK='Esto es una <b>demostración</b> del asistente. Prueba pidiéndome, por ejemplo: «<b>un presupuesto de 10 millones</b>» y verás cómo armaría el borrador priorizando lo esencial.'
  +'<div><span class="dia-chip" data-q="Crea un presupuesto de 10 millones">'+SPARK+'Probar con $10.000.000</span></div>';

function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}

/* ── Estructura (se crea UNA vez, persiste en body) ───────────────── */
function getRoot(){
  var root=D.getElementById('_demo_ia_root');
  if(!root){
    root=D.createElement('div'); root.id='_demo_ia_root';
    root.innerHTML=
      '<button id="_demo_ia_fab" title="Asistente de Cotización IA (demo)"><span class="dia-fab-badge">DEMO</span>'+ROBOT+'</button>'
     +'<div id="_demo_ia_panel">'
     +'<div class="dia-head"><div class="dia-avatar">'+ROBOT+'</div>'
     +'<div><div class="dia-t">Cotizador IA <span class="dia-pill">DEMO</span></div>'
     +'<div class="dia-s"><span class="dia-dot"></span>Asistente de presupuestos</div></div>'
     +'<button class="dia-x" title="Cerrar">'+XI+'</button></div>'
     +'<div class="dia-msgs" id="_dia_msgs"></div>'
     +'<div class="dia-input"><input id="_dia_in" type="text" placeholder="Escribe un monto, ej: 10 millones…" autocomplete="off">'
     +'<button class="dia-send" id="_dia_send">'+SEND+'</button></div></div>';
    B.appendChild(root);
    var m=root.querySelector('#_dia_msgs');
    var g=D.createElement('div'); g.className='dia-msg dia-bot'; g.innerHTML=GREET; m.appendChild(g);
  }
  return root;
}

/* ── Bind de handlers (cada run; el iframe se recrea en los reruns) ─ */
function bind(){
  var root=getRoot();
  var fab=root.querySelector('#_demo_ia_fab');
  var panel=root.querySelector('#_demo_ia_panel');
  var xb=root.querySelector('.dia-x');
  var msgs=root.querySelector('#_dia_msgs');
  var inp=root.querySelector('#_dia_in');
  var snd=root.querySelector('#_dia_send');

  function add(html, who){ var d=D.createElement('div'); d.className='dia-msg dia-'+who; d.innerHTML=html; msgs.appendChild(d); msgs.scrollTop=msgs.scrollHeight; return d; }
  function respond(text){
    text=(text||'').trim(); if(!text) return;
    add(esc(text),'user');
    var t=add('<span class="dia-dots"><i></i><i></i><i></i></span>','bot');
    W.setTimeout(function(){
      t.remove();
      var isBudget = /\\d/.test(text) || /mill|presupuest|monto|millon/i.test(text);
      add(isBudget ? budgetHTML() : FALLBACK, 'bot');
      msgs.scrollTop=msgs.scrollHeight;
    }, 1500);
  }
  fab.onclick=function(){ panel.classList.add('on'); fab.classList.add('hidden'); W.setTimeout(function(){inp.focus();},60); };
  xb.onclick=function(){ panel.classList.remove('on'); fab.classList.remove('hidden'); };
  snd.onclick=function(){ var v=inp.value; inp.value=''; respond(v); };
  inp.onkeydown=function(e){ if(e.key==='Enter'){ e.preventDefault(); var v=inp.value; inp.value=''; respond(v); } };
  msgs.onclick=function(e){ var c=e.target.closest?e.target.closest('.dia-chip'):null; if(c) respond(c.getAttribute('data-q')||c.textContent); };
}
bind();
})();</script>""", height=0)
