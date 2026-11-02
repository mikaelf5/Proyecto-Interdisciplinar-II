"""
Capa de DOMINIO — servicios de dominio (lógica pura, sin base de datos).

- AsignadorDeCola: orden FIFO de la lista de espera.
- ReglasDeReserva: valida una franja contra el horario y la política.
- CalculadoraDeHorarios: calcula los huecos libres de un día.
"""
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError

from .horario import MINUTOS_POR_HORA, hora_desde_minutos, minutos_del_dia



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
            + self._errores_de_duracion(desde, hasta)
            + self._errores_de_anticipacion(fecha, desde, ahora)
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
        if not (self.horario.en_bloque(desde) and self.horario.en_bloque(hasta)):
            return [f"Elige horas en bloques de {self.horario.bloque_min} minutos (ej. 10:00, 10:15, 10:30)."]
        return []

    def _errores_de_duracion(self, desde, hasta):
        duracion = minutos_del_dia(hasta) - minutos_del_dia(desde)
        if 0 < duracion < self.horario.duracion_minima_min:
            return [f"La reserva debe durar al menos {self.horario.duracion_minima_min} minutos."]
        return []

    def _errores_de_anticipacion(self, fecha, desde, ahora):
        """Se reserva con un mínimo de anticipación (30 min) para que el encargado prepare el ítem."""
        inicio = datetime.combine(fecha, desde)
        lo_mas_pronto = ahora.replace(tzinfo=None, second=0, microsecond=0) + timedelta(
            minutes=self.horario.anticipacion_minima_min)
        if inicio >= lo_mas_pronto:
            return []
        if inicio < ahora.replace(tzinfo=None):
            return ["No puedes reservar en un horario que ya pasó."]
        return [f"Debes reservar con al menos {self.horario.anticipacion_minima_min} minutos de "
                f"anticipación (lo más pronto: {lo_mas_pronto:%H:%M})."]

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
    def validar_limites(politica, vigentes_total, vigentes_mismo_tipo, es_especial):
        """
        RF-C2: cuántas reservas vigentes puede tener una persona (pendientes, confirmadas o en uso).
            limite_simultaneo_global  → en total (ej. 4)
            limite_simultaneo_por_tipo → de esa clase de ítem (ej. ítems especiales: 1)
        """
        if vigentes_total >= politica.limite_simultaneo_global:
            raise ValidationError(
                f"Ya tienes {vigentes_total} reservas vigentes: el máximo es "
                f"{politica.limite_simultaneo_global}. Cancela alguna para hacer otra."
            )
        if vigentes_mismo_tipo >= politica.limite_simultaneo_por_tipo:
            if es_especial:
                raise ValidationError(
                    f"Ya tienes una reserva de un ítem especial: solo se permite "
                    f"{politica.limite_simultaneo_por_tipo} a la vez."
                )
            raise ValidationError(
                f"Ya tienes {vigentes_mismo_tipo} reservas de esta categoría: el máximo es "
                f"{politica.limite_simultaneo_por_tipo}."
            )


class CalculadoraDeHorarios:
    def __init__(self, horario):
        self.horario = horario

    def libres(self, fecha, ocupadas, ahora):
        """Huecos libres del día como lista de (desde, hasta). `ocupadas` = reservas que ocupan."""
        if not self.horario.atiende(fecha) or fecha < ahora.date():
            return []
        cursor = self._primer_minuto_disponible(fecha, ahora)
        huecos = []
        margen = self.horario.margen_entre_reservas_min
        for reserva in sorted(ocupadas, key=lambda r: r.hora_inicio):
            self._agregar_hueco(huecos, cursor, minutos_del_dia(reserva.hora_inicio) - margen)
            cursor = max(cursor, minutos_del_dia(reserva.hora_fin) + margen)
        self._agregar_hueco(huecos, cursor, minutos_del_dia(self.horario.cierre))
        return huecos

    def _primer_minuto_disponible(self, fecha, ahora):
        apertura = minutos_del_dia(self.horario.apertura)
        if fecha != ahora.date():
            return apertura
        lo_mas_pronto = minutos_del_dia(ahora.time()) + self.horario.anticipacion_minima_min
        return max(apertura, self._redondear_al_siguiente_bloque(lo_mas_pronto))

    def _redondear_al_siguiente_bloque(self, minutos):
        return minutos + (-minutos) % self.horario.bloque_min

    def _agregar_hueco(self, huecos, desde, hasta):
        """Solo se ofrecen huecos donde cabe la reserva más corta permitida (15 min)."""
        if hasta - desde >= self.horario.duracion_minima_min:
            huecos.append((hora_desde_minutos(desde), hora_desde_minutos(hasta)))
