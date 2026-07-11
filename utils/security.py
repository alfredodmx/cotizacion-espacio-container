"""
Núcleo de seguridad del sistema.

Responsabilidades:
  - Escapar HTML de datos del usuario (defensa XSS en el output).
  - Detectar patrones de ataque (XSS / SQLi / template injection) en los inputs
    ANTES de procesarlos/guardarlos, con severidad.
  - Registrar eventos de seguridad (a la tabla cotizacion_logs, numero='SEGURIDAD').
  - Rate limiting server-side del login (cuenta intentos fallidos por email en una
    ventana de tiempo — no dependiente de session_state, así no se evade abriendo
    otra pestaña).
  - Leer los eventos para la pestaña SEGURIDAD.

NOTA: reutiliza la tabla existente `cotizacion_logs` (columnas: numero, asesor,
tipo_cambio, detalle jsonb, fecha) para no requerir crear tablas nuevas en Supabase.
Los eventos de seguridad usan numero='SEGURIDAD' (o 'SISTEMA' para login_fallido,
que ya existía). Todo va en try/except y falla ABIERTO (nunca bloquea al usuario
legítimo por un error de logging).
"""
import re
import html as _html
from datetime import datetime, timezone, timedelta

import streamlit as st

from config.supabase import supabase_admin

# Tipos de evento de seguridad que muestra la pestaña SEGURIDAD.
TIPOS_SEGURIDAD = ['login_fallido', 'login_bloqueado', 'input_sospechoso', 'acceso_denegado', 'backup_bd']

# Orden de severidad para comparaciones/UX.
_SEV_RANK = {'baja': 1, 'media': 2, 'alta': 3}

# ── Patrones de ataque ────────────────────────────────────────────────────────
# (etiqueta, severidad, regex). Pensados para inputs de formularios (nombres,
# direcciones, observaciones, email): un valor legítimo NO debería contener nada
# de esto, así que un match es señal fuerte de intento de inyección.
_PATTERNS = [
    ('xss_script',    'alta',  re.compile(r'<\s*script', re.I)),
    ('xss_evento',    'alta',  re.compile(r'\bon(error|load|click|mouseover|focus|submit|toggle|animationstart)\s*=', re.I)),
    ('xss_js_uri',    'alta',  re.compile(r'javascript\s*:', re.I)),
    ('xss_svg_img',   'alta',  re.compile(r'<\s*(svg|img|iframe|video|audio|body)\b[^>]*\bon\w+\s*=', re.I)),
    ('xss_tag',       'media', re.compile(r'<\s*/?\s*(script|iframe|object|embed|link|meta|base|form|style)\b', re.I)),
    ('sqli_union',    'alta',  re.compile(r'\bunion\b[\s\S]{0,40}\bselect\b', re.I)),
    ('sqli_stmt',     'alta',  re.compile(r';\s*(drop|delete|truncate|alter|create|update|insert|grant)\s', re.I)),
    ('sqli_bool',     'media', re.compile(r"""('|")\s*(or|and)\s*('|")?\s*\d+\s*=\s*\d+""", re.I)),
    ('sqli_comment',  'baja',  re.compile(r'(--|#|/\*)[\s\S]{0,30}\b(drop|delete|insert|update|select|from|where)\b', re.I)),
    ('tpl_inject',    'media', re.compile(r'\{\{[\s\S]*?\}\}|\$\{[\s\S]*?\}|<%[\s\S]*?%>')),
    ('path_traversal','media', re.compile(r'(\.\./){2,}|/etc/passwd|\\windows\\system32', re.I)),
]


# ── Escape de output (defensa XSS al renderizar) ──────────────────────────────

def escape_html(value) -> str:
    """Escapa un valor para incrustarlo con seguridad en HTML (unsafe_allow_html).
    Convierte < > & " ' en entidades → un <script> del usuario se muestra como
    texto, no se ejecuta."""
    return _html.escape("" if value is None else str(value), quote=True)


# ── Detección de patrones de ataque en inputs ─────────────────────────────────

def scan_value(value) -> list:
    """Devuelve [(etiqueta, severidad), ...] de los patrones de ataque que
    matchean en `value`. Lista vacía si el valor es limpio."""
    if value is None:
        return []
    s = str(value)
    if not s:
        return []
    hits = []
    for etiqueta, sev, rx in _PATTERNS:
        if rx.search(s):
            hits.append((etiqueta, sev))
    return hits


def analizar_inputs(datos: dict, email: str = "", contexto: str = "") -> tuple:
    """Escanea todos los valores string de `datos`. Si hay patrones sospechosos,
    registra un evento 'input_sospechoso' y devuelve (bloquear, amenazas).

    bloquear=True si alguna amenaza es de severidad ALTA (XSS/SQLi claros) → el
    caller debe abortar la operación. Severidades media/baja se registran pero no
    bloquean (para no frustrar falsos positivos)."""
    amenazas = []
    for campo, val in (datos or {}).items():
        for etiqueta, sev in scan_value(val):
            amenazas.append({
                'campo': str(campo),
                'tipo': etiqueta,
                'severidad': sev,
                'muestra': str(val)[:160],
            })
    if not amenazas:
        return (False, [])
    bloquear = any(a['severidad'] == 'alta' for a in amenazas)
    _sev_max = max((a['severidad'] for a in amenazas), key=lambda s: _SEV_RANK.get(s, 0))
    log_evento_seguridad('input_sospechoso', email, {
        'contexto': contexto,
        'bloqueado': bloquear,
        'amenazas': amenazas,
    }, severidad=_sev_max)
    return (bloquear, amenazas)


# ── Registro de eventos de seguridad ──────────────────────────────────────────

def log_evento_seguridad(tipo: str, email: str, detalle: dict = None, severidad: str = 'media') -> None:
    """Inserta un evento de seguridad en cotizacion_logs (numero='SEGURIDAD').
    Nunca lanza: si falla el logging, no interrumpe el flujo del usuario."""
    try:
        _det = dict(detalle or {})
        _det.setdefault('severidad', severidad)
        supabase_admin.table('cotizacion_logs').insert({
            'numero': 'SEGURIDAD',
            'asesor': (str(email or 'anónimo').strip().lower())[:150],
            'tipo_cambio': tipo,
            'detalle': _det,
        }).execute()
    except Exception:
        pass


def registrar_login_fallido(email: str, intentos_sesion: int = 0) -> None:
    """Registra un intento de login fallido (para rate limiting + auditoría)."""
    log_evento_seguridad('login_fallido', email, {
        'intentos_sesion': intentos_sesion,
    }, severidad='baja')


def registrar_login_bloqueado(email: str, intentos: int) -> None:
    log_evento_seguridad('login_bloqueado', email, {
        'intentos_recientes': intentos,
    }, severidad='alta')


# ── Rate limiting server-side del login ───────────────────────────────────────

def login_rate_limit(email: str, ventana_min: int = 15, max_intentos: int = 8) -> tuple:
    """Cuenta los login_fallido de este email en los últimos `ventana_min` minutos
    (a nivel de servidor, no de sesión). Devuelve (bloqueado, intentos).

    Falla ABIERTO: si hay error de consulta, devuelve (False, 0) para no dejar
    fuera a usuarios legítimos por un problema de infraestructura."""
    _em = (email or "").strip().lower()
    if not _em:
        return (False, 0)
    try:
        _desde = (datetime.now(timezone.utc) - timedelta(minutes=ventana_min)).isoformat()
        r = (supabase_admin.table('cotizacion_logs')
             .select('id', count='exact')
             .eq('tipo_cambio', 'login_fallido')
             .eq('asesor', _em)
             .gte('fecha', _desde)
             .execute())
        n = r.count if r.count is not None else len(r.data or [])
        return (n >= max_intentos, n)
    except Exception:
        return (False, 0)


# ── Lectura de eventos para la pestaña SEGURIDAD ──────────────────────────────

@st.cache_data(ttl=20, show_spinner=False)
def fetch_eventos_seguridad(horas: int = 168, limite: int = 800) -> list:
    """Eventos de seguridad de las últimas `horas` (por defecto 7 días), más
    recientes primero. Cacheado 20s."""
    try:
        _desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
        r = (supabase_admin.table('cotizacion_logs')
             .select('*')
             .in_('tipo_cambio', TIPOS_SEGURIDAD)
             .gte('fecha', _desde)
             .order('fecha', desc=True)
             .limit(limite)
             .execute())
        return r.data or []
    except Exception:
        return []
