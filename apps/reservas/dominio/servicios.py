"""
Capa de DOMINIO — servicios de dominio (lógica pura, sin base de datos).

- AsignadorDeCola: orden FIFO de la lista de espera.
- ReglasDeReserva: valida una franja contra el horario y la política.
- CalculadoraDeHorarios: calcula los huecos libres de un día.
"""
from datetime import timedelta

from django.core.exceptions import ValidationError

from .horario import MINUTOS_POR_HORA, hora_desde_minutos, minutos_del_dia

CUARTO_DE_HORA = 15


class AsignadorDeCola:
    @staticmethod
    def en_orden(cola):
        """Reservas ACTIVAS de la lista de espera, de la primera en llegar a la última."""
        return sorted((r for r in cola if r.estado == "ACTIVA"), key=lambda r: r.posicion_en_cola)

    @classmethod
    def siguiente(cls, cola):
        """La primera en llegar, o None si la lista está vacía."""
        en_orden = cls.en_orden(cola)
        return en_orden[0] if en_orden else None

    @staticmethod
    def posicion_para_nueva(cola):
        """La nueva va al final de la lista de espera."""
        return max((r.posicion_en_cola or 0 for r in cola), default=0) + 1


class ReglasDeReserva:
    """Reglas que toda reserva debe cumplir (RF-C3: la política se aplica sola)."""

    def __init__(self, horario):
        self.horario = horario

    def validar(self, fecha, desde, hasta, ahora, politica):
        """Lanza ValidationError con TODOS los problemas encontrados, no solo el primero."""
        errores = (
            self._errores_de_horario(fecha, desde, hasta)
            + self._errores_de_momento(fecha, desde, ahora)
            + self._errores_de_politica(fecha, desde, hasta, ahora, politica)
        )
        if errores:
            raise ValidationError(errores)

    def _errores_de_horario(self, fecha, desde, hasta):
        if hasta <= desde:
            return ["La hora de fin debe ser posterior a la hora de inicio."]
        if not self.horario.atiende(fecha):
            return [f"Ese día no hay atención. Horario: {self.horario.describir()}."]
        if not self.horario.dentro(desde, hasta):
            return [f"La reserva debe estar dentro del horario: {self.horario.describir()}."]
        return []

    @staticmethod
    def _errores_de_momento(fecha, desde, ahora):
        hora_actual = ahora.time().replace(second=0, microsecond=0)
        ya_paso = fecha < ahora.date() or (fecha == ahora.date() and desde < hora_actual)
        return ["No puedes reservar en un horario que ya pasó."] if ya_paso else []

    @staticmethod
    def _errores_de_politica(fecha, desde, hasta, ahora, politica):
        errores = []
        fecha_maxima = ahora.date() + timedelta(days=politica.antelacion_reserva)
        if fecha > fecha_maxima:
            errores.append(
                f"Solo puedes reservar con hasta {politica.antelacion_reserva} día(s) de antelación "
                f"(como máximo el {fecha_maxima:%d/%m/%Y})."
            )
        duracion = minutos_del_dia(hasta) - minutos_del_dia(desde)
        if duracion > politica.duracion_maxima * MINUTOS_POR_HORA:
            errores.append(f"La reserva no puede durar más de {politica.duracion_maxima} hora(s).")
        return errores

    @staticmethod
    def validar_limites(politica, simultaneas_total, simultaneas_categoria):
        """RF-C2: cuántos ítems puede tener a la vez (en total y de una misma categoría)."""
        if simultaneas_total >= politica.limite_simultaneo_global:
            raise ValidationError(
                f"Ya tienes {simultaneas_total} reserva(s) en ese horario: el máximo es "
                f"{politica.limite_simultaneo_global} a la vez."
            )
        if simultaneas_categoria >= politica.limite_simultaneo_por_tipo:
            raise ValidationError(
                f"Ya tienes {simultaneas_categoria} ítem(s) de esta categoría en ese horario: "
                f"el máximo es {politica.limite_simultaneo_por_tipo} a la vez."
            )


class CalculadoraDeHorarios:
    HUECO_MINIMO = CUARTO_DE_HORA  # no se ofrecen huecos de menos de 15 minutos

    def __init__(self, horario):
        self.horario = horario

    def libres(self, fecha, ocupadas, ahora):
        """Huecos libres del día como lista de (desde, hasta). `ocupadas` = reservas que ocupan."""
        if not self.horario.atiende(fecha) or fecha < ahora.date():
            return []
        cursor = self._primer_minuto_disponible(fecha, ahora)
        huecos = []
        for reserva in sorted(ocupadas, key=lambda r: r.hora_inicio):
            self._agregar_hueco(huecos, cursor, minutos_del_dia(reserva.hora_inicio))
            cursor = max(cursor, minutos_del_dia(reserva.hora_fin))
        self._agregar_hueco(huecos, cursor, minutos_del_dia(self.horario.cierre))
        return huecos

    def _primer_minuto_disponible(self, fecha, ahora):
        apertura = minutos_del_dia(self.horario.apertura)
        if fecha != ahora.date():
            return apertura
        ahora_redondeado = self._redondear_al_siguiente_cuarto(minutos_del_dia(ahora.time()))
        return max(apertura, ahora_redondeado)

    @staticmethod
    def _redondear_al_siguiente_cuarto(minutos):
        return minutos + (-minutos) % CUARTO_DE_HORA

    def _agregar_hueco(self, huecos, desde, hasta):
        if hasta - desde >= self.HUECO_MINIMO:
            huecos.append((hora_desde_minutos(desde), hora_desde_minutos(hasta)))
