from abc import ABC, abstractmethod


class ICasoPerdidaRepositorio(ABC):
    @abstractmethod
    def guardar(self, caso): ...

    @abstractmethod
    def obtener(self, pk): ...

    @abstractmethod
    def buscar(self, estado="", q=""): ...

    @abstractmethod
    def contar_abiertos(self): ...

    @abstractmethod
    def eliminar(self, caso): ...

    @abstractmethod
    def por_periodo(self, inicio, fin): ...