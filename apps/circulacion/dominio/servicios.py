"""Servicios de dominio de Circulación."""

from django.core.exceptions import ValidationError


class ServicioDeElegibilidad:
    """Evalúa si un usuario cumple las condiciones para obtener un préstamo."""

    def evaluar(self, perfil, tiene_sancion, politica, vigentes):
        if perfil is None or politica is None or tiene_sancion:
            return False

        habilitado = getattr(perfil, "habilitado", None)

        if habilitado is None:
            metodo = getattr(perfil, "esta_habilitado", None)

            if not callable(metodo):
                raise ValidationError(
                    "No se puede determinar la habilitación del perfil."
                )

            habilitado = metodo()

        if not habilitado:
            return False

        return len(vigentes) < politica.limite_simultaneo_global