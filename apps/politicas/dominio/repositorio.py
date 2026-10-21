from abc import ABC, abstractmethod


class IPoliticaRepositorio(ABC):

    @abstractmethod
    def buscar_para(self, tipo_item, tipo_usuario):
        pass

    @abstractmethod
    def guardar(self, politica):
        pass