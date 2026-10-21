from abc import ABC, abstractmethod


class ISancionRepositorio(ABC):
    @abstractmethod
    def guardar(self, sancion): ...

    @abstractmethod
    def activas_de(self, solicitante_id): ...

    @abstractmethod
    def por_periodo(self, inicio, fin): ...