"""Revisión periódica de vencimientos (RF-H1 y RF-H2).

Qué hace cada vez que se ejecuta:
  1. Préstamos activos que vencen en los próximos N minutos (30 por defecto):
     un recordatorio por correo (una sola vez por préstamo).
  2. Préstamos activos cuya hora ya pasó: pasan a VENCIDO, se dejan en la
     auditoría y se envía la alerta de atraso.

Solo coordina: pide los préstamos a Circulación (puerto `prestamos`), avisa por el
servicio de Notificaciones, nombra el ítem con Catálogo y deja constancia en Auditoría.
"""
import uuid
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from apps.auditoria.models import TipoAccion
from apps.common.choices import TipoNotificacion

# Actor de las acciones automáticas (no las hace una persona).
SISTEMA_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass
class ResultadoRevision:
    recordatorios: int = 0
    vencidos: int = 0


class RevisorDeVencimientos:
    def __init__(self, prestamos, notificaciones, catalogo, auditoria):
        self._prestamos = prestamos            # por_vencer / vencidos_abiertos / marcar_vencido
        self._notificaciones = notificaciones  # NotificacionServicioAplicacion
        self._catalogo = catalogo              # CatalogoServicioAplicacion
        self._auditoria = auditoria            # AuditoriaServicioAplicacion

    # ------------------------------------------------------------------ #
    def revisar(self, ahora=None, minutos_aviso=30):
        ahora = ahora or timezone.now()
        resultado = ResultadoRevision()
        for prestamo in self._prestamos.por_vencer(ahora, minutos_aviso):
            if self._enviar_recordatorio(prestamo):
                resultado.recordatorios += 1
        for prestamo in self._prestamos.vencidos_abiertos(ahora):
            if self._marcar_vencido(prestamo):
                resultado.vencidos += 1
        return resultado

    # ------------------------------------------------------------------ #
    @staticmethod
    def _marca(prestamo):
        """Texto corto que identifica al préstamo en el mensaje (#ab12cd34)."""
        return f"#{str(prestamo.id)[:8]}"

    def _nombre_item(self, prestamo):
        try:
            item = self._catalogo.obtener_item(prestamo.item_id)
            return f"{item.codigo} · {item.nombre}"
        except Exception:  # el ítem ya no existe: no frena el aviso
            return str(prestamo.item_id)[:8]

    def _ya_avisado(self, prestamo, tipo):
        marca = self._marca(prestamo)
        return any(
            n.tipo == tipo and marca in n.mensaje
            for n in self._notificaciones.mis_notificaciones(prestamo.solicitante_id)
        )

    def _enviar_recordatorio(self, prestamo):
        tipo = TipoNotificacion.RECORDATORIO_VENCIMIENTO
        if self._ya_avisado(prestamo, tipo):
            return False
        hora = timezone.localtime(prestamo.fecha_vencimiento)
        self._notificaciones.enviar(
            prestamo.solicitante_id, tipo,
            f"Tu préstamo {self._marca(prestamo)} de «{self._nombre_item(prestamo)}» "
            f"vence hoy a las {hora:%H:%M}. Devuélvelo a tiempo para evitar una sanción.",
        )
        return True

    def _marcar_vencido(self, prestamo):
        with transaction.atomic():
            if not self._prestamos.marcar_vencido(prestamo.id):
                return False  # otro proceso ya lo había marcado
            self._auditoria.registrar(
                SISTEMA_ID, TipoAccion.CAMBIO_ESTADO, "Prestamo", prestamo.id,
                "Marcado como vencido automáticamente: no se devolvió a la hora pactada.",
            )
            hora = timezone.localtime(prestamo.fecha_vencimiento)
            self._notificaciones.enviar(
                prestamo.solicitante_id, TipoNotificacion.ALERTA_ATRASO,
                f"Tu préstamo {self._marca(prestamo)} de «{self._nombre_item(prestamo)}» "
                f"venció el {hora:%d/%m/%Y} a las {hora:%H:%M}. Devuélvelo lo antes posible.",
            )
        return True
