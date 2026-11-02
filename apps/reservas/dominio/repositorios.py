"""Capa de DOMINIO — interfaz IReservaRepositorio (qué se guarda/busca, no cómo)."""
from abc import ABC, abstractmethod


class IReservaRepositorio(ABC):
    @abstractmethod
    def guardar(self, reserva): ...

    @abstractmethod
    def buscar_por_id(self, reserva_id): ...

    @abstractmethod
    def bloquear_item(self, item_id):
        """Evita que dos personas reserven el mismo ítem al mismo tiempo (dentro de la transacción)."""

    @abstractmethod
    def ocupadas_de(self, item_id, fecha, excluir_id=None):
        """Reservas que ocupan franja (EN_ESPERA_SUPERVISOR, CONFIRMADA, ATENDIDA) del ítem ese día."""

    @abstractmethod
    def cola_de(self, item_id, fecha=None):
        """Lista de espera (ACTIVAS) del ítem, ordenada por posición."""

    @abstractmethod
    def de_solicitante(self, solicitante_id): ...

    @abstractmethod
    def simultaneas_de(self, solicitante_id, fecha, desde, hasta, categoria_id=None):
        """Cuántas reservas del solicitante ocupan una franja que se cruza con [desde, hasta)."""

    @abstractmethod
    def en_espera_supervisor(self): ...

    @abstractmethod
    def confirmadas_del_dia(self, fecha): ...

    @abstractmethod
    def pendientes_hasta(self, fecha):
        """ACTIVAS / EN_ESPERA_SUPERVISOR / CONFIRMADAS con fecha <= `fecha` (para expirar)."""
