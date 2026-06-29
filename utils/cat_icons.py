"""
Iconos SVG (estilo Lucide) por categoría, detectados del título de la categoría
(sin acentos, case-insensitive). Compartido entre el formulario del cliente y la
pestaña de progreso para que los iconos sean idénticos en toda la app.
"""
import unicodedata as _ud

# (palabras_clave, path_svg). El primer match gana → ordenar de más específico a
# más genérico cuando haya solape.
_CAT_ICONS = [
    (('bano', 'ducha', 'tina', 'wc', 'sanitar', 'lavamanos', 'vanitor', 'inodoro', 'lavatorio'),
     '<path d="M9 6 6.5 3.5a1.5 1.5 0 0 0-1-.5C4.68 3 4 3.68 4 4.5V17a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/><line x1="2" x2="22" y1="12" y2="12"/><line x1="7" x2="7" y1="19" y2="21"/><line x1="17" x2="17" y1="19" y2="21"/>'),
    (('cocina', 'horno', 'encimera', 'campana'),
     '<path d="M3 2v7c0 1.1.9 2 2 2h4a2 2 0 0 0 2-2V2"/><path d="M7 2v20"/><path d="M21 15V2a5 5 0 0 0-5 5v6c0 1.1.9 2 2 2h3Zm0 0v7"/>'),
    (('piso', 'suelo', 'pavimento', 'ceramic', 'porcelan'),
     '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M9 3v18"/><path d="M15 3v18"/>'),
    (('ventana', 'marco'),
     '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 12h18"/><path d="M12 3v18"/>'),
    (('puerta',),
     '<path d="M3 21h18"/><path d="M5 21V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16"/><circle cx="15" cy="12" r="1"/>'),
    (('muro', 'pared', 'tabique', 'revesti', 'fachada'),
     '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M3 9h18"/><path d="M3 15h18"/><path d="M12 3v6"/><path d="M8 9v6"/><path d="M16 9v6"/><path d="M12 15v6"/>'),
    (('techo', 'cielo', 'cubierta', 'loza'),
     '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>'),
    (('dormitorio', 'cama', 'habitacion', 'pieza', 'recamara'),
     '<path d="M2 4v16"/><path d="M2 8h18a2 2 0 0 1 2 2v10"/><path d="M2 17h20"/><path d="M6 8v9"/>'),
    (('living', 'comedor', 'estar', 'sala', 'sillon', 'sofa'),
     '<path d="M20 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v3"/><path d="M2 11v5a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-5a2 2 0 0 0-4 0v2H6v-2a2 2 0 0 0-4 0Z"/><path d="M4 18v2"/><path d="M20 18v2"/>'),
    (('color', 'pintura', 'tono'),
     '<circle cx="13.5" cy="6.5" r=".5"/><circle cx="17.5" cy="10.5" r=".5"/><circle cx="8.5" cy="7.5" r=".5"/><circle cx="6.5" cy="12.5" r=".5"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.93 0 1.65-.75 1.65-1.69 0-.44-.18-.83-.44-1.12-.29-.29-.44-.65-.44-1.13a1.64 1.64 0 0 1 1.67-1.67h2c3.05 0 5.56-2.5 5.56-5.55C21.97 6.01 17.46 2 12 2z"/>'),
    (('luz', 'luces', 'iluminaci', 'lampara', 'foco', 'spot'),
     '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>'),
    (('cornisa', 'moldura', 'guardapolvo', 'zocalo', 'junquillo'),
     '<line x1="22" x2="2" y1="6" y2="6"/><line x1="22" x2="2" y1="18" y2="18"/><line x1="6" x2="6" y1="2" y2="22"/><line x1="18" x2="18" y1="2" y2="22"/>'),
    (('closet', 'armario', 'ropero', 'mueble', 'repisa', 'velador'),
     '<rect width="14" height="20" x="5" y="2" rx="2"/><path d="M12 2v20"/><path d="M9 8h.01"/><path d="M15 8h.01"/>'),
    (('calefacc', 'clima', 'aire', 'termo', 'estufa'),
     '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>'),
    (('exterior', 'terraza', 'jardin', 'patio', 'deck'),
     '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>'),
]
_CAT_ICON_DEFAULT = ('<path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/>'
                     '<path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>')


def cat_icon_path(nombre: str) -> str:
    """Devuelve SOLO el path SVG (sin <svg>) del icono para la categoría dada."""
    n = ''.join(c for c in _ud.normalize('NFD', (nombre or '').lower()) if _ud.category(c) != 'Mn')
    for keys, path in _CAT_ICONS:
        if any(k in n for k in keys):
            return path
    return _CAT_ICON_DEFAULT


def cat_icon_svg(nombre: str, size: int = 18, color: str = '#0f3460', sw: float = 2) -> str:
    """SVG inline completo del icono de la categoría (estilo Lucide)."""
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" '
            f'style="vertical-align:-3px;flex-shrink:0;">{cat_icon_path(nombre)}</svg>')
