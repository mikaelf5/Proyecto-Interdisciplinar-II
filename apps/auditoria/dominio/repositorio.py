from abc import ABC, abstractmethod


class IRegistroAuditoriaRepositorio(ABC):
    @abstractmethod
    def guardar(self, registro): ...

    @abstractmethod
    def buscar(self, filtros): ...