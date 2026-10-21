from abc import ABC, abstractmethod
from apps.politicas.dominio.models import PoliticaPrestamo


class IPoliticaServicio(ABC):

    @abstractmethod
    def configurar(self, dto):
        pass

    @abstractmethod
    def obtener_para(self, tipo_item, tipo_usuario):
        pass

    @abstractmethod
    def validar_plazo(self, tipo_item, tipo_usuario, fecha_entrega, fecha_devolucion):
        pass

class PoliticaServicioAplicacion(IPoliticaServicio):

    def __init__(self, repositorio):
        self.repositorio = repositorio

    def obtener_para(self, tipo_item, tipo_usuario):
        return self.repositorio.buscar_para(
            tipo_item,
            tipo_usuario
        )

    def configurar(self, dto):
        politica = self.repositorio.buscar_para(
            dto.tipo_item,
            dto.tipo_usuario
        )

        if politica is None:
            politica = PoliticaPrestamo(
                tipo_item=dto.tipo_item,
                tipo_usuario=dto.tipo_usuario
            )

        politica.duracion_maxima = dto.duracion_maxima
        politica.max_renovaciones = dto.max_renovaciones
        politica.antelacion_reserva = dto.antelacion_reserva
        politica.limite_simultaneo_global = dto.limite_simultaneo_global
        politica.limite_simultaneo_por_tipo = dto.limite_simultaneo_por_tipo

        politica.full_clean()
        return self.repositorio.guardar(politica)

    def validar_plazo(self, tipo_item, tipo_usuario, fecha_entrega, fecha_devolucion):
        politica = self.obtener_para(tipo_item, tipo_usuario)

        if politica is None:
            raise ValueError(
                "No existe una política para este tipo de ítem y usuario"
            )

        return politica.validar_plazo(fecha_entrega, fecha_devolucion)