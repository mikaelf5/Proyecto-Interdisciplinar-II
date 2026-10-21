"""Reglas de presentación de las sanciones (no modifican la base de datos)."""
from datetime import date, timedelta

VIGENTE = "vigente"
CUMPLIDA = "cumplida"
LEVANTADA = "levantada"

ESTADOS = [
    (VIGENTE, "Vigente"),
    (CUMPLIDA, "Cumplida"),
    (LEVANTADA, "Levantada"),
]


def fecha_fin(sancion):
    """Último día de la sanción, o None si no tiene duración (ej. baneo)."""
    if sancion.duracion_dias:
        return sancion.fecha_inicio + timedelta(days=sancion.duracion_dias - 1)
    return None


def estado_de(sancion, hoy=None):
    """vigente / cumplida (se acabó el plazo) / levantada (cerrada a mano)."""
    hoy = hoy or date.today()
    if not sancion.activa:
        return LEVANTADA
    fin = fecha_fin(sancion)
    if fin is not None and hoy > fin:
        return CUMPLIDA
    return VIGENTE


def con_estado(sanciones, hoy=None):
    """Agrega .estado y .fecha_fin a cada sanción (atributos solo en memoria)."""
    hoy = hoy or date.today()
    resultado = list(sanciones)
    for s in resultado:
        s.estado = estado_de(s, hoy)
        s.fin = fecha_fin(s)
    return resultado
