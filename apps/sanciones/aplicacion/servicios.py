from abc import ABC, abstractmethod
from datetime import date

from apps.sanciones.dominio.repositorio import ISancionRepositorio


class ISancionServicio(ABC):
    @abstractmethod
    def tiene_sancion_activa(self, solicitante_id) -> bool: ...


class SancionServicioAplicacion(ISancionServicio):
    def __init__(self, sancion_repositorio: ISancionRepositorio):
        self._repo = sancion_repositorio

    def tiene_sancion_activa(self, solicitante_id, hoy=None) -> bool:
        hoy = hoy or date.today()
        return any(s.esta_vigente(hoy) for s in self._repo.activas_de(solicitante_id))
    
    def por_periodo(self, inicio, fin):
        return list(self._repo.por_periodo(inicio, fin))