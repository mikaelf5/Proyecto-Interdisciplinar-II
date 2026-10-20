"""
Capa de DOMINIO — servicio de dominio AsignadorDeCola (PDF).

Lógica pura de la cola FIFO: no toca la base de datos, recibe la cola
(lista de reservas ACTIVAS del ítem) y decide.
"""


class AsignadorDeCola:
    @staticmethod
    def siguiente(cola):
        """Devuelve la reserva que debe atenderse primero (o None si no hay cola)."""
        activas = [r for r in cola if r.estado == "ACTIVA"]
        return min(activas, key=lambda r: r.posicion_en_cola) if activas else None

    @staticmethod
    def posicion_para_nueva(cola):
        """Una reserva nueva va al final de la cola."""
        return max((r.posicion_en_cola for r in cola), default=0) + 1
