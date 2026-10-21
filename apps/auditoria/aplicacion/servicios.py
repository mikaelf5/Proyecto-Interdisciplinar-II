from abc import ABC, abstractmethod

from apps.auditoria.dominio.models import RegistroAuditoria
from apps.auditoria.dominio.repositorio import IRegistroAuditoriaRepositorio


class IAuditoriaServicio(ABC):
    @abstractmethod
    def registrar(self, actor_id, accion, entidad, entidad_id, motivo=""): ...

    @abstractmethod
    def buscar(self, filtros): ...


class AuditoriaServicioAplicacion(IAuditoriaServicio):
    def __init__(self, auditoria_repositorio: IRegistroAuditoriaRepositorio):
        self._repo = auditoria_repositorio

    def registrar(self, actor_id, accion, entidad, entidad_id, motivo=""):
        registro = RegistroAuditoria(
            actor_id=actor_id, accion=accion, entidad=entidad,
            entidad_id=entidad_id, motivo=motivo,
        )
        self._repo.guardar(registro)
        return self._repo.guardar(registro)

    def buscar(self, filtros):
        return self._repo.buscar(filtros)