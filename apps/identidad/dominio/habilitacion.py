"""Value Object con la respuesta de `consultar_habilitacion`.

Se devuelve un objeto (y no solo True/False) para que Circulación pueda
mostrar POR QUÉ un solicitante no puede pedir un préstamo y dejarlo en la
auditoría si rechaza la solicitud (RF-D2, RF-J1).
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResultadoHabilitacion:
    solicitante_id: object
    habilitado: bool
    motivos: tuple = field(default_factory=tuple)

    def __bool__(self):
        return self.habilitado

    @property
    def mensaje(self):
        return "Habilitado." if self.habilitado else " ".join(self.motivos)

    @classmethod
    def si(cls, solicitante_id):
        return cls(solicitante_id, True, ())

    @classmethod
    def no(cls, solicitante_id, *motivos):
        return cls(solicitante_id, False, tuple(motivos))
