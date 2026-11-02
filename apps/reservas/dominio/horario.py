"""
Capa de DOMINIO — Horario de atención (Value Object).

Todo préstamo ocurre dentro de UN día y dentro de este horario: los ítems
no se llevan fuera de la universidad. Se puede cambiar sin tocar el código
agregando en config/settings.py, por ejemplo:

    RESERVAS_HORARIO = {"dias": [0, 1, 2, 3, 4, 5], "apertura": "08:00",
                        "cierre": "14:00", "tolerancia_min": 15}

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
    nombres: tuple = field(default=tuple(NOMBRES_DIAS), repr=False)

    @classmethod
    def desde_settings(cls):
        conf = getattr(settings, "RESERVAS_HORARIO", {}) or {}
        return cls(
            dias=tuple(conf.get("dias", cls.dias)),
            apertura=_hora(conf.get("apertura", cls.apertura)),
            cierre=_hora(conf.get("cierre", cls.cierre)),
            tolerancia_min=int(conf.get("tolerancia_min", cls.tolerancia_min)),
        )

    def atiende(self, fecha):
        return fecha.weekday() in self.dias

    def dentro(self, desde, hasta):
        return self.apertura <= desde < hasta <= self.cierre

    def describir(self):
        dias = ", ".join(self.nombres[d] for d in self.dias)
        return f"{dias} de {self.apertura:%H:%M} a {self.cierre:%H:%M}"
