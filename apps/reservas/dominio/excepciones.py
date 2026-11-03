"""Errores del dominio de Reservas."""
from django.core.exceptions import ValidationError


class HorarioOcupado(ValidationError):
    """La franja pedida choca con otra reserva del mismo ítem.

    Además del mensaje trae lo necesario para que la pantalla ofrezca
    alternativas: los horarios libres de ese día .
    """

    def __init__(self, mensaje, ocupada=None, horarios_libres=(), alternativos=()):
        super().__init__(mensaje)
        self.ocupada = ocupada
        self.horarios_libres = list(horarios_libres)

