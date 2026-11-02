"""Puertos hacia OTROS contextos que Identidad necesita para las etiquetas (RF-B6).

Identidad no lee las tablas de Sanciones ni de Circulación desde su lógica:
pide la información a través de estas interfaces. Las implementaciones
viven en infraestructura/adaptadores.py.
"""
from abc import ABC, abstractmethod


class ISancionesPuerto(ABC):
    @abstractmethod
    def tiene_sancion_activa(self, cuenta_id) -> bool: ...

    @abstractmethod
    def sancion_mas_grave(self, cuenta_id):
        """Tipo de la sanción vigente más grave (ej. "BANEO"), o None."""


class IHistorialPrestamosPuerto(ABC):
    @abstractmethod
    def devueltos_a_tiempo(self, cuenta_id) -> int:
        """Cuántos préstamos devolvió la cuenta en o antes de su vencimiento."""
