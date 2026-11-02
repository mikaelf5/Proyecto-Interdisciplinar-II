"""
Capa de DOMINIO — Horario de atención (Value Object).

Todo préstamo ocurre dentro de UN día y dentro de este horario: los ítems
no se llevan fuera de la universidad. Se puede cambiar sin tocar el código
agregando en config/settings.py, por ejemplo:

    RESERVAS_HORARIO = {"dias": [0, 1, 2, 3, 4, 5], "apertura": "08:00", "cierre": "14:00",
                        "tolerancia_min": 15, "anticipacion_minima_min": 30,
                        "duracion_minima_min": 15, "bloque_min": 15, "margen_entre_reservas_min": 15}

(0 = lunes ... 6 = domingo)
"""
from dataclasses import dataclass, field
from datetime import time

from django.conf import settings

NOMBRES_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MINUTOS_POR_HORA = 60


def minutos_del_dia(hora):
    """10:30 → 630. Permite restar y comparar horas como números."""
    return hora.hour * MINUTOS_POR_HORA + hora.minute


def hora_desde_minutos(minutos):
    """630 → 10:30."""
    return time(minutos // MINUTOS_POR_HORA, minutos % MINUTOS_POR_HORA)


def _hora(valor):
    return valor if isinstance(valor, time) else time.fromisoformat(valor)


@dataclass(frozen=True)
class HorarioAtencion:
    dias: tuple = (0, 1, 2, 3, 4)          # lunes a viernes
    apertura: time = time(8, 0)
    cierre: time = time(20, 0)
    tolerancia_min: int = 15               # minutos para recoger antes de que expire
    anticipacion_minima_min: int = 30      # reservar al menos 30 min antes de la hora de inicio
    duracion_minima_min: int = 15          # una reserva dura como mínimo 15 min
    bloque_min: int = 15                   # las horas van de 15 en 15 (10:00, 10:15, 10:30…)
    margen_entre_reservas_min: int = 15    # tiempo libre entre dos reservas para recibir y revisar el ítem
    nombres: tuple = field(default=tuple(NOMBRES_DIAS), repr=False)

    @classmethod
    def desde_settings(cls):
        conf = getattr(settings, "RESERVAS_HORARIO", {}) or {}
        return cls(
            dias=tuple(conf.get("dias", cls.dias)),
            apertura=_hora(conf.get("apertura", cls.apertura)),
            cierre=_hora(conf.get("cierre", cls.cierre)),
            tolerancia_min=int(conf.get("tolerancia_min", cls.tolerancia_min)),
            anticipacion_minima_min=int(conf.get("anticipacion_minima_min", cls.anticipacion_minima_min)),
            duracion_minima_min=int(conf.get("duracion_minima_min", cls.duracion_minima_min)),
            bloque_min=int(conf.get("bloque_min", cls.bloque_min)),
            margen_entre_reservas_min=int(conf.get("margen_entre_reservas_min", cls.margen_entre_reservas_min)),
        )

    def atiende(self, fecha):
        return fecha.weekday() in self.dias

    def en_bloque(self, hora):
        """¿La hora cae en un bloque? Con bloques de 15: 10:00 y 10:15 sí, 10:04 no."""
        return minutos_del_dia(hora) % self.bloque_min == 0

    def dentro(self, desde, hasta):
        return self.apertura <= desde < hasta <= self.cierre

    def describir(self):
        dias = ", ".join(self.nombres[d] for d in self.dias)
        return f"{dias} de {self.apertura:%H:%M} a {self.cierre:%H:%M}"
