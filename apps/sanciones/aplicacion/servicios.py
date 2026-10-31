from abc import ABC, abstractmethod
from datetime import date

from apps.sanciones.dominio.models import TipoSancion
from apps.sanciones.dominio.repositorio import ISancionRepositorio

# De mayor a menor gravedad (lo usa Identidad para la etiqueta del solicitante).
GRAVEDAD = (
    TipoSancion.BANEO,
    TipoSancion.SUSPENSION_TEMPORAL,
    TipoSancion.OBSERVACION,
)


class ISancionServicio(ABC):
    @abstractmethod
    def tiene_sancion_activa(self, cuenta_id, hoy=None) -> bool: ...

    @abstractmethod
    def sancion_mas_grave(self, cuenta_id, hoy=None): ...


class SancionServicioAplicacion(ISancionServicio):
    """Contrato de Sanciones para los demás contextos (RF-G2).

    `cuenta_id` es el id de la Cuenta (el mismo que `solicitante_id` en
    Circulación y `request.user.pk`).
    """

    def __init__(self, sancion_repositorio: ISancionRepositorio):
        self._repo = sancion_repositorio

    def _vigentes(self, cuenta_id, hoy=None):
        hoy = hoy or date.today()
        return [s for s in self._repo.activas_de(cuenta_id) if s.esta_vigente(hoy)]

    def tiene_sancion_activa(self, cuenta_id, hoy=None) -> bool:
        """True si la cuenta tiene al menos una sanción vigente (le quita la habilitación)."""
        return bool(self._vigentes(cuenta_id, hoy))

    def sancion_mas_grave(self, cuenta_id, hoy=None):
        """Tipo de la sanción vigente más grave (BANEO > SUSPENSION_TEMPORAL > OBSERVACION), o None.

        Identidad la usa para decidir la etiqueta: BANEO -> BANEADO, otro tipo -> SANCIONADO.
        """
        tipos = {s.tipo for s in self._vigentes(cuenta_id, hoy)}
        for tipo in GRAVEDAD:
            if tipo in tipos:
                return tipo
        return None

    def por_periodo(self, inicio, fin):
        return list(self._repo.por_periodo(inicio, fin))
