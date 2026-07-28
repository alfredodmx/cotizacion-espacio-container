"""
Página PÚBLICA de desuscripción (baja de correos). Se abre desde el link de baja
que llevan los correos masivos: `…/?baja=<cliente_id>`. Marca al cliente como
`no_email=true` y muestra una confirmación simple. No requiere login.
"""
import streamlit as st


def render_baja_view(token: str):
    from repositories.clientes_repo import marcar_no_email, obtener_cliente

    _cli = obtener_cliente(token) or {}
    _nombre = str(_cli.get("nombre") or "").strip()
    _ok = marcar_no_email(token, True) if _cli else False

    _msg = ("Listo, te diste de baja." if _ok
            else "No pudimos procesar la baja. Escríbenos a ventas@espaciocontainerhouse.cl y lo hacemos manualmente.")
    _sub = ("Ya no recibirás más correos de Espacio Container House."
            if _ok else "Disculpa la molestia.")
    _hola = f"Hola{(' ' + _nombre) if _nombre else ''},"

    st.markdown(
        f"""
        <div style="max-width:520px;margin:8vh auto 0;padding:36px 32px;border-radius:18px;
             border:1px solid #e6e9f4;background:#fff;box-shadow:0 8px 32px rgba(30,36,71,.08);
             font-family:Montserrat,Arial,sans-serif;text-align:center;">
          <div style="width:64px;height:64px;border-radius:50%;margin:0 auto 18px;
               background:{'#dcfce7' if _ok else '#fee2e2'};display:flex;align-items:center;justify-content:center;">
            <span style="font-size:30px;">{'✅' if _ok else '⚠️'}</span>
          </div>
          <div style="font-size:0.78rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;
               color:#94a3b8;">Espacio Container House</div>
          <h2 style="margin:10px 0 6px;font-size:1.25rem;color:#0f172a;">{_msg}</h2>
          <p style="color:#64748b;font-size:0.95rem;margin:0;">{_hola} {_sub}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()
