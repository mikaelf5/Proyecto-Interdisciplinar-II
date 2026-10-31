"""Estados de presentación de las sanciones (no modifican la base de datos).

Usa las reglas del dominio (`Sancion.fecha_fin()` y `Sancion.esta_vigente()`), para que
la lista, los reportes y `tiene_sancion_activa()` siempre digan lo mismo.
"""
from datetime import date

VIGENTE = "vigente"
CUMPLIDA = "cumplida"
LEVANTADA = "levantada"

ESTADOS = [
    (VIGENTE, "Vigente"),
    (CUMPLIDA, "Cumplida"),
    (LEVANTADA, "Levantada"),
]


def fecha_fin(sancion):
    """Último día de la sanción (inclusive), o None si no tiene plazo (ej. baneo)."""
    return sancion.fecha_fin()


def estado_de(sancion, hoy=None):
    """vigente / cumplida (se acabó el plazo) / levantada (cerrada a mano)."""
    hoy = hoy or date.today()
    if not sancion.activa:
        return LEVANTADA
    return VIGENTE if sancion.esta_vigente(hoy) else CUMPLIDA


def con_estado(sanciones, hoy=None):
    """Agrega .estado y .fin a cada sanción (atributos solo en memoria)."""
    hoy = hoy or date.today()
    resultado = list(sanciones)
    for s in resultado:
        s.estado = estado_de(s, hoy)
        s.fin = fecha_fin(s)
    return resultado
