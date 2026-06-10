"""
Calculadora de dias habiles con feriados chilenos.
"""
from datetime import date, timedelta


def _feriados_chile(anio: int) -> set[date]:
    """Retorna conjunto de feriados fijos + moviles de Chile para el anio dado."""
    feriados = {
        date(anio, 1, 1),   # Año Nuevo
        date(anio, 5, 1),   # Dia del Trabajo
        date(anio, 5, 21),  # Glorias Navales
        date(anio, 6, 29),  # San Pedro y San Pablo
        date(anio, 7, 16),  # Virgen del Carmen
        date(anio, 8, 15),  # Asuncion de la Virgen
        date(anio, 9, 18),  # Primera Junta Nacional de Gobierno
        date(anio, 9, 19),  # Glorias del Ejercito
        date(anio, 10, 12), # Encuentro de dos Mundos
        date(anio, 10, 31), # Dia de las Iglesias Evangelicas
        date(anio, 11, 1),  # Dia de todos los Santos
        date(anio, 11, 2),  # Dia de los Fieles Difuntos
        date(anio, 12, 8),  # Inmaculada Concepcion
        date(anio, 12, 25), # Navidad
    }

    # Viernes Santo y Sabado Santo (moviles — dependen de Semana Santa)
    # Algoritmo de Butcher para calcular Pascua
    a = anio % 19
    b = anio // 100
    c = anio % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes_pascua = (h + l - 7 * m + 114) // 31
    dia_pascua = ((h + l - 7 * m + 114) % 31) + 1
    pascua = date(anio, mes_pascua, dia_pascua)

    feriados.add(pascua - timedelta(days=2))  # Viernes Santo
    feriados.add(pascua - timedelta(days=1))  # Sabado Santo

    return feriados


def sumar_dias_habiles(fecha_inicio: date, dias: int) -> date:
    """Suma N dias habiles (lunes-viernes, excluye feriados) a fecha_inicio."""
    feriados = _feriados_chile(fecha_inicio.year)
    fecha = fecha_inicio
    sumados = 0
    while sumados < dias:
        fecha += timedelta(days=1)
        if fecha.year != fecha_inicio.year:
            feriados = feriados | _feriados_chile(fecha.year)
        if fecha.weekday() < 5 and fecha not in feriados:
            sumados += 1
    return fecha


def dias_habiles_entre(fecha_inicio: date, fecha_fin: date) -> int:
    """Cuenta dias habiles entre dos fechas (excluye inicio, incluye fin)."""
    if fecha_fin <= fecha_inicio:
        return 0
    feriados: set[date] = set()
    for anio in range(fecha_inicio.year, fecha_fin.year + 1):
        feriados |= _feriados_chile(anio)

    cuenta = 0
    fecha = fecha_inicio
    while fecha < fecha_fin:
        fecha += timedelta(days=1)
        if fecha.weekday() < 5 and fecha not in feriados:
            cuenta += 1
    return cuenta
