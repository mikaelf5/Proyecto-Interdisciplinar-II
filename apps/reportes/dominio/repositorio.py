from abc import ABC, abstractmethod


class IReporteRepositorio(ABC):
    @abstractmethod
    def guardar(self, reporte): ...

    @abstractmethod
    def obtener(self, pk): ...

    @abstractmethod
    def listar(self): ...

    @abstractmethod
    def eliminar(self, reporte): ...