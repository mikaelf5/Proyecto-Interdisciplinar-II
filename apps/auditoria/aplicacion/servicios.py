from abc import ABC, abstractmethod

from django.core.exceptions import ValidationError

from apps.auditoria.dominio.constantes import ACTORES_SISTEMA, ETIQUETA_SISTEMA
from apps.auditoria.dominio.models import ACCIONES_CON_MOTIVO, RegistroAuditoria
from apps.auditoria.dominio.repositorio import IRegistroAuditoriaRepositorio


class IAuditoriaServicio(ABC):
    @abstractmethod
    def registrar(self, actor_id, accion, entidad, entidad_id, motivo=""): ...

    @abstractmethod
    def buscar(self, filtros): ...

    @abstractmethod
    def entidades(self): ...

    @abstractmethod
    def nombres_de_actores(self, ids): ...


class AuditoriaServicioAplicacion(IAuditoriaServicio):
    def __init__(self, auditoria_repositorio: IRegistroAuditoriaRepositorio):
        self._repo = auditoria_repositorio

    def registrar(self, actor_id, accion, entidad, entidad_id, motivo=""):
        """Deja constancia de quién hizo qué. Rechazo, ítem dañado y sanción exigen motivo (RF-J1)."""
        if accion in ACCIONES_CON_MOTIVO and not (motivo or "").strip():
            raise ValidationError("Esta acción exige registrar el motivo en la auditoría.")
        registro = RegistroAuditoria(
            actor_id=actor_id, accion=accion, entidad=entidad,
            entidad_id=entidad_id, motivo=motivo,
        )
        return self._repo.guardar(registro)

    def buscar(self, filtros):
        return self._repo.buscar(filtros)

    def entidades(self):
        return self._repo.entidades()

    def nombres_de_actores(self, ids):
        """{actor_id: nombre a mostrar}. Los procesos automáticos salen como "Sistema"."""
        ids = set(ids)
        nombres = self._repo.nombres_de_actores(ids - ACTORES_SISTEMA)
        return {i: ETIQUETA_SISTEMA if i in ACTORES_SISTEMA else nombres.get(i, "") for i in ids}
