"""
Repositorio server-side del formulario del cliente (tabla formulario_respuestas).

Objetivo de seguridad: mover el guardado de respuestas del cliente del NAVEGADOR
(que hoy usa la clave anon → obliga a tener RLS apagado) al SERVIDOR (service key,
que bypassa RLS). Así se puede activar RLS "deny anon" en formulario_respuestas
sin romper el formulario público.

Estado: función lista y probada en cuanto a lógica; el cableado (que el
formulario del cliente llame a esto en vez de hacer fetch directo) se hace en un
paso aparte y se verifica en el beta ANTES de activar el RLS de la tabla.
"""
import streamlit as st

from config.supabase import supabase_admin
from utils.security import analizar_inputs


def guardar_respuestas_cliente(ep: str, picks: dict, email_cliente: str = "") -> tuple:
    """Guarda las selecciones del cliente en formulario_respuestas usando la
    service key (server-side).

    picks: dict {item_id(str): respuesta(str)}.

    Replica la lógica del guardado del navegador:
      - por cada grupo del formulario (item_ids en formulario_config), si el
        cliente eligió un item del grupo, borra las respuestas de los OTROS items
        del mismo grupo (para que no queden selecciones viejas) y guarda la elegida.
    Antes de guardar, escanea los valores (input del cliente = no confiable) y, si
    detecta inyección de severidad ALTA, aborta y registra el evento de seguridad.

    Devuelve (ok: bool, error: str|None)."""
    try:
        if not ep or not picks:
            return (True, None)

        # ── Blindaje: el cliente es un origen NO confiable ──────────────────
        _bloquear, _ = analizar_inputs(
            {f'resp_{k}': v for k, v in picks.items()},
            email=email_cliente or f'cliente:{ep}',
            contexto=f'formulario_cliente:{ep}')
        if _bloquear:
            return (False, "Contenido no permitido en la selección (posible inyección).")

        # Grupos del formulario (item_ids por grupo) para borrar hermanos.
        _cfg = (supabase_admin.table('formulario_config')
                .select('item_ids').eq('cotizacion_numero', ep).execute().data or [])
        grupos = [[str(i) for i in (c.get('item_ids') or [])] for c in _cfg]

        for _iid, _val in picks.items():
            iid = str(_iid)
            # Borrar respuestas de los hermanos del grupo que contiene a iid.
            for g in grupos:
                if iid in g:
                    hermanos = [x for x in g if x != iid]
                    if hermanos:
                        (supabase_admin.table('formulario_respuestas')
                         .delete().eq('cotizacion_numero', ep)
                         .in_('item_id', hermanos).execute())
            # Upsert manual (delete + insert) para no depender de un índice único.
            (supabase_admin.table('formulario_respuestas')
             .delete().eq('cotizacion_numero', ep).eq('item_id', iid).execute())
            (supabase_admin.table('formulario_respuestas').insert({
                'cotizacion_numero': ep,
                'item_id': iid,
                'respuesta': str(_val),
            }).execute())

        return (True, None)
    except Exception as e:
        return (False, str(e))
