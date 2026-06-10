"""
Sistema de roles del sistema.

Roles definidos:
  root      → acceso total, puede eliminar cualquier cuenta
  admin     → ve todo, puede crear ejecutivos y admins
  operacion → vista operacional de proyectos
  ejecutivo → solo sus propias cotizaciones
"""
from config.settings import ROOTS


def get_rol(email: str, user_metadata: dict | None = None) -> str:
    """Retorna el rol del usuario: 'root', 'admin', 'operacion' o 'ejecutivo'."""
    email_l = (email or "").lower()
    if email_l in [r.lower() for r in ROOTS]:
        return "root"
    meta_rol = (user_metadata or {}).get("rol", "ejecutivo")
    if meta_rol in ("root",):
        return "root"
    if meta_rol in ("admin", "administrador"):
        return "admin"
    if meta_rol in ("operacion", "operaciones"):
        return "operacion"
    return "ejecutivo"


def es_rol_superior(email: str, user_metadata: dict | None = None) -> bool:
    """True si el usuario es root o admin (acceso amplio)."""
    return get_rol(email, user_metadata) in ("root", "admin")
