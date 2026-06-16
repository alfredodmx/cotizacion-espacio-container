"""
Servicio de geocodificacion via Nominatim (OpenStreetMap).
"""
import requests


_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "CotizadorEspacio/1.0"}


def buscar_direccion(query: str, pais: str = "Chile") -> list[dict]:
    """
    Busca una direccion usando Nominatim.
    Retorna lista de resultados con display_name, lat, lon.
    """
    if not query or len(query.strip()) < 3:
        return []
    try:
        params = {
            "q": f"{query}, {pais}",
            "format": "json",
            "addressdetails": 1,
            "limit": 5,
        }
        resp = requests.get(_NOMINATIM_URL, params=params, headers=_HEADERS, timeout=8)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            {
                "display_name": r.get("display_name", ""),
                "lat": float(r.get("lat", 0)),
                "lon": float(r.get("lon", 0)),
                "address": r.get("address", {}),
            }
            for r in data
        ]
    except Exception:
        return []
