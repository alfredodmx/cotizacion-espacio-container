"""
Pestaña CLIENTES (CRM) — maestro de clientes.

FASE 1 (esqueleto): SOLO-ROOT. Vistas Pipeline / Bandeja / Maestro. El Maestro
lista los clientes (con backfill de solo lectura desde cotizaciones) + búsqueda
client-side + alta manual. Pipeline y Bandeja llegan en la siguiente fase.

Condiciones duras: la pestaña es visible SOLO para root (doble llave: fuera de la
navegación de los demás roles en app.py + este guard). Es ADITIVA: solo lee lo
existente y escribe en las tablas nuevas. No toca el flujo actual.
"""
import html as _html

import streamlit as st
import streamlit.components.v1 as components

from views.layout import render_page_header
from repositories.clientes_repo import (
    listar_clientes, crear_cliente, registrar_actividad,
    backfill_desde_cotizaciones, dedup_key,
)

_ROL_OK = "root"


# ── Estilo del selector de vista (mismas reglas que las sub-pestañas de
#    OPERACIONES/CONTRATO: Plus Jakarta 0.88rem/700 uppercase, gris/azul) ───────
_CLI_SELECTOR_CSS = """
<style>
.st-key-_cli_view [role="radiogroup"]{gap:0!important;flex-wrap:wrap!important;
  border-bottom:2px solid #e2e6f3!important;margin-bottom:2px!important;padding:0!important;}
.st-key-_cli_view [role="radiogroup"] > label{background:transparent!important;border:none!important;
  border-bottom:3px solid transparent!important;border-radius:0!important;padding:0.85rem 1.6rem!important;
  margin:0 0 -2px 0!important;cursor:pointer!important;color:#7c85b3!important;
  transition:color .2s,border-color .2s!important;}
.st-key-_cli_view [role="radiogroup"] > label:hover{color:#5b7cfa!important;background:rgba(91,124,250,.05)!important;}
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked){color:#5b7cfa!important;
  border-bottom-color:#5b7cfa!important;background:rgba(91,124,250,.06)!important;}
.st-key-_cli_view [role="radiogroup"] > label > div:first-child{display:none!important;}
.st-key-_cli_view [role="radiogroup"] label [data-testid="stMarkdownContainer"] p{
  font-family:'Plus Jakarta Sans',sans-serif!important;font-size:0.88rem!important;font-weight:700!important;
  text-transform:uppercase!important;letter-spacing:0.05em!important;margin:0!important;}
.st-key-_cli_view [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p span{color:#7c85b3!important;}
.st-key-_cli_view [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label:hover [data-testid="stMarkdownContainer"] p span,
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p,
.st-key-_cli_view [role="radiogroup"] > label:has(input:checked) [data-testid="stMarkdownContainer"] p span{color:#5b7cfa!important;}
.st-key-_cli_view [role="radiogroup"] label span[role="img"][aria-label$=" icon"]{
  font-family:'Material Symbols Rounded'!important;font-weight:400!important;font-size:0.88rem!important;
  text-transform:none!important;letter-spacing:normal!important;}
</style>
"""

_CLI_CSS = """
<style>
.cli-tbl-wrap{overflow-x:auto;border-radius:14px;border:1px solid #e6e9f4;
  box-shadow:0 3px 16px rgba(30,36,71,.06);background:#fff;margin-top:10px;}
.cli-tbl-wrap table{width:100%;border-collapse:collapse;min-width:820px;white-space:nowrap;}
.cli-tbl-wrap thead th{background:linear-gradient(135deg,#1e2447 0%,#2a3060 100%);color:#fff;
  font-family:'Plus Jakarta Sans',sans-serif;font-weight:900;font-size:0.72rem;letter-spacing:.07em;
  text-transform:uppercase;padding:11px 14px;text-align:left;position:sticky;top:0;}
.cli-tbl-wrap tbody td{font-family:Montserrat,sans-serif;font-size:0.82rem;color:#0f172a;
  padding:9px 14px;border-bottom:1px solid #f0f2f8;}
.cli-tbl-wrap tbody tr:nth-child(even){background:#f8fafc;}
.cli-pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:0.68rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.03em;}
.cli-sbar{display:flex;align-items:center;gap:9px;background:#fff;border:1px solid #e6e9f4;
  border-radius:12px;padding:9px 13px;box-shadow:0 3px 16px rgba(30,36,71,.06);}
.cli-sbar input{flex:1 1 auto;border:none;outline:none;background:transparent;min-width:0;
  font-family:Montserrat,sans-serif;font-size:.86rem;font-weight:600;color:#0f172a;}
.cli-sbar input::placeholder{color:#94a3b8;font-weight:500;}
.cli-sbar .cli-sico{display:inline-flex;flex:0 0 auto;color:#94a3b8;}
.cli-empty-ph{text-align:center;color:#94a3b8;padding:40px;font-family:Montserrat,sans-serif;
  font-weight:600;border:1px dashed #d7ddf0;border-radius:14px;margin-top:10px;}
</style>
"""


def _svg(path, size=16, color="#0f172a", sw=2):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round" style="flex-shrink:0;vertical-align:-2px;">{path}</svg>')


def _titulo(texto, icon=""):
    st.markdown(
        '<div style="display:flex;align-items:center;gap:9px;margin:6px 0 10px;">'
        f'{icon}<span style="font-family:\'Montserrat\',sans-serif;font-weight:700;'
        'font-size:0.88rem;letter-spacing:0.05em;text-transform:uppercase;'
        f'color:#0f172a;">{texto}</span></div>',
        unsafe_allow_html=True)


def _esc(s):
    return _html.escape(str(s if s is not None else ""))


@st.cache_data(ttl=60, show_spinner=False)
def _cli_all() -> list:
    """Maestro de clientes (cacheado; se limpia al mutar/sincronizar)."""
    return listar_clientes(solo_activos=True)


def _kpi(label, valor, color="#0f172a"):
    return (
        '<div style="background:#f8fafc;border-radius:12px;padding:12px 14px;">'
        f'<div style="font-size:0.74rem;color:#64748b;font-weight:600;">{label}</div>'
        f'<div style="font-family:Montserrat,sans-serif;font-size:1.5rem;font-weight:800;'
        f'color:{color};line-height:1.2;">{valor}</div></div>')


_ORIGEN_COLORS = {
    "shopify": ("#ede9fe", "#6d28d9"),
    "web":     ("#e0f2fe", "#0369a1"),
    "manual":  ("#f1f5f9", "#475569"),
}


def _tabla_maestro_html(data: list) -> str:
    rows = ""
    for d in data:
        _asig = d.get("asignado_nombre") or d.get("asignado_email") or ""
        _org = str(d.get("origen") or "Manual")
        _obg, _ofg = _ORIGEN_COLORS.get(_org.split(" ")[0].lower(), _ORIGEN_COLORS["manual"])
        _lead = str(d.get("etapa_manual") or "") == "lead_nuevo"
        _s = _esc(f"{d.get('nombre','')} {d.get('rut','')} {d.get('email','')} "
                  f"{d.get('telefono','')} {_asig} {_org}".lower())
        _asig_cell = (_esc(_asig) if _asig
                      else '<span style="color:#ea580c;font-weight:700;font-size:0.72rem;">Sin asignar</span>')
        rows += (
            f'<tr data-s="{_s}">'
            f'<td style="font-weight:700;">{_esc(d.get("nombre","") or "—")}'
            + (' <span class="cli-pill" style="background:#fee2e2;color:#dc2626;">Lead</span>' if _lead else '')
            + '</td>'
            f'<td>{_esc(d.get("rut","")) or "—"}</td>'
            f'<td>{_esc(d.get("email","")) or "—"}</td>'
            f'<td>{_esc(d.get("telefono","")) or "—"}</td>'
            f'<td><span class="cli-pill" style="background:{_obg};color:{_ofg};">{_esc(_org)}</span></td>'
            f'<td>{_asig_cell}</td>'
            '</tr>')
    return (
        '<div class="cli-tbl-wrap"><table><thead><tr>'
        '<th>Cliente</th><th>RUT</th><th>Correo</th><th>Tel&eacute;fono</th>'
        '<th>Origen</th><th>Ejecutivo</th>'
        f'</tr></thead><tbody>{rows}</tbody></table></div>')


# Buscador client-side (input HTML + data-s por fila): filtra en el navegador sin
# reruns. Mismo patrón que INVENTARIO.
_CLI_SEARCH_JS = r"""<script>
(function(){
  var W=window.parent, D=W&&W.document; if(!D) return;
  var q=D.getElementById('_cli_q');
  if(!q) return;
  if(W._cliQH){ try{ q.removeEventListener('input', W._cliQH); }catch(e){} }
  W._cliQH=function(){
    var v=(q.value||'').toLowerCase().trim();
    var trs=D.querySelectorAll('.cli-tbl-wrap tbody tr[data-s]'), n=0;
    for(var i=0;i<trs.length;i++){
      var ok=(!v)||(trs[i].getAttribute('data-s').indexOf(v)>=0);
      trs[i].style.display=ok?'':'none'; if(ok) n++;
    }
    var c=D.getElementById('_cli_count'); if(c) c.textContent=n;
    var em=D.getElementById('_cli_noresult'); if(em) em.style.display=(n||!trs.length)?'none':'block';
    W._cliQ=v;
  };
  q.addEventListener('input', W._cliQH);
  if(W._cliQ){ q.value=W._cliQ; W._cliQH(); }
})();
</script>"""


def _render_agregar_dialog():
    """Alta manual de un cliente (one-shot). Dedup por RUT>email>teléfono>nombre."""
    @st.dialog("Agregar cliente")
    def _dlg():
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre *", key="_cli_add_nombre")
            rut = st.text_input("RUT", key="_cli_add_rut")
            email = st.text_input("Correo", key="_cli_add_email")
        with c2:
            telefono = st.text_input("Teléfono", key="_cli_add_tel")
            tipo = st.selectbox("Tipo", ["natural", "empresa"], key="_cli_add_tipo")
            comuna = st.text_input("Comuna", key="_cli_add_comuna")
        empresa = rut_empresa = ""
        if tipo == "empresa":
            e1, e2 = st.columns(2)
            with e1:
                empresa = st.text_input("Empresa", key="_cli_add_empresa")
            with e2:
                rut_empresa = st.text_input("RUT empresa", key="_cli_add_rutemp")
        direccion = st.text_input("Dirección", key="_cli_add_dir")

        b1, b2 = st.columns(2)
        with b1:
            guardar = st.button("Guardar cliente", type="primary", use_container_width=True,
                                key="_cli_add_save")
        with b2:
            if st.button("Cancelar", use_container_width=True, key="_cli_add_cancel"):
                st.session_state.pop("_cli_add_open", None)
                st.rerun()
        if guardar:
            if not (nombre or "").strip():
                st.warning("El nombre es obligatorio.")
                return
            # Dedup: si ya existe un cliente con la misma identidad, no duplicar.
            k = dedup_key(rut, email, telefono, nombre)
            if k[1]:
                for c in _cli_all():
                    if dedup_key(c.get("rut"), c.get("email"), c.get("telefono"), c.get("nombre")) == k:
                        st.warning(f"Ya existe un cliente con esa identidad: "
                                   f"{c.get('nombre','')}. No se creó un duplicado.")
                        return
            _actor = st.session_state.get("auth_nombre") or st.session_state.get("auth_email", "")
            cid, err = crear_cliente({
                "nombre": nombre.strip(), "rut": (rut or "").strip(),
                "email": (email or "").strip(), "telefono": (telefono or "").strip(),
                "tipo": tipo, "empresa": (empresa or "").strip(),
                "rut_empresa": (rut_empresa or "").strip(),
                "direccion": (direccion or "").strip(), "comuna": (comuna or "").strip(),
                "origen": "Manual", "etapa_manual": "lead_nuevo",
            })
            if cid:
                registrar_actividad(cid, "nota", "Cliente creado manualmente", actor=_actor)
                _cli_all.clear()
                st.session_state.pop("_cli_add_open", None)
                st.session_state["_cli_toast"] = f"Cliente {nombre.strip()} agregado."
                st.rerun()
            else:
                st.error(f"No se pudo guardar: {err}")
    _dlg()


def render_tab_clientes(**kwargs):
    _rol = st.session_state.get("rol_usuario", "ejecutivo")
    # DOBLE LLAVE: aunque no está en la navegación de otros roles, se re-valida acá.
    if _rol != _ROL_OK:
        render_page_header("clientes", "Clientes", "CRM")
        st.warning("Esta sección aún no está disponible.")
        return

    render_page_header("clientes", "Clientes",
                       "CRM · maestro de clientes (en construcción)")
    st.markdown(_CLI_CSS, unsafe_allow_html=True)

    _t = st.session_state.pop("_cli_toast", None)
    if _t:
        st.toast(_t)

    data = _cli_all()

    # KPIs
    _n_total = len(data)
    _n_sinasig = sum(1 for d in data if not str(d.get("asignado_email") or "").strip())
    _n_leads = sum(1 for d in data if str(d.get("etapa_manual") or "") == "lead_nuevo")
    _n_shopify = sum(1 for d in data if "shopify" in str(d.get("origen") or "").lower())
    st.markdown(
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:6px 0 14px;">'
        + _kpi("Total clientes", _n_total)
        + _kpi("Sin asignar", _n_sinasig, "#ea580c" if _n_sinasig else "#0f172a")
        + _kpi("Leads nuevos", _n_leads, "#dc2626" if _n_leads else "#0f172a")
        + _kpi("Desde Shopify", _n_shopify)
        + '</div>', unsafe_allow_html=True)

    # Barra de acciones: Sincronizar (backfill) + Agregar cliente
    a1, a2, _a3 = st.columns([1, 1, 2])
    with a1:
        if st.button("Sincronizar", icon=":material/sync:", use_container_width=True,
                     key="_cli_sync", help="Re-lee las cotizaciones y crea las fichas que falten (solo lectura)"):
            with st.spinner("Sincronizando con cotizaciones…"):
                res = backfill_desde_cotizaciones()
            _cli_all.clear()
            st.session_state["_cli_toast"] = (
                f"Sincronizado: {res['creados']} nuevo(s), {res['existentes']} ya estaban.")
            st.rerun()
    with a2:
        if st.button("Agregar cliente", icon=":material/person_add:", type="primary",
                     use_container_width=True, key="_cli_add_btn"):
            st.session_state["_cli_add_open"] = True

    # Selector de vista
    st.markdown(_CLI_SELECTOR_CSS, unsafe_allow_html=True)
    _views = ["Pipeline", "Bandeja", "Maestro"]
    _icons = {"Pipeline": ":material/view_kanban:", "Bandeja": ":material/inbox:",
              "Maestro": ":material/table_rows:"}
    _view = st.radio("Vista", _views, index=2, key="_cli_view", horizontal=True,
                     label_visibility="collapsed",
                     format_func=lambda v: f"{_icons.get(v,'')} {v}")

    if _view == "Maestro":
        _titulo(f'Maestro · <span id="_cli_count">{_n_total}</span> cliente(s)',
                _svg('<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>'
                     '<path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', 16))
        st.markdown(
            '<div class="cli-sbar"><span class="cli-sico">'
            + _svg('<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>', 16, "currentColor")
            + '</span><input id="_cli_q" type="text" autocomplete="off" '
            'placeholder="Buscar por nombre, RUT, correo, teléfono o ejecutivo…"></div>',
            unsafe_allow_html=True)
        if not data:
            st.markdown('<div class="cli-empty-ph">Aún no hay clientes. Pulsa '
                        '<b>Sincronizar</b> para importar desde tus cotizaciones, o '
                        '<b>Agregar cliente</b>.</div>', unsafe_allow_html=True)
        else:
            st.markdown(_tabla_maestro_html(data), unsafe_allow_html=True)
            st.markdown('<div id="_cli_noresult" class="cli-empty-ph" style="display:none;">'
                        'Ningún cliente coincide con tu búsqueda.</div>',
                        unsafe_allow_html=True)
            components.html(_CLI_SEARCH_JS, height=0)
    else:
        _lbl = "El pipeline de oportunidades" if _view == "Pipeline" else "La bandeja de leads"
        st.markdown(
            '<div style="border:1.5px dashed #d7ddf0;border-radius:14px;padding:42px 24px;'
            'text-align:center;margin-top:12px;background:#fbfcff;">'
            + _svg('<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
                   30, "#94a3b8", 1.6)
            + f'<div style="font-family:Montserrat,sans-serif;font-weight:700;color:#334155;'
            f'font-size:0.95rem;margin-top:12px;">{_lbl} llega en la próxima fase</div>'
            '<div style="color:#94a3b8;font-size:0.82rem;margin-top:4px;">'
            'Por ahora usá el <b>Maestro</b> para ver e ingresar clientes.</div></div>',
            unsafe_allow_html=True)

    # Diálogo de alta (one-shot)
    if st.session_state.get("_cli_add_open"):
        st.session_state.pop("_cli_add_open", None)
        _render_agregar_dialog()
