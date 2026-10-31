"""Adaptador: consultas de préstamos que necesita `revisar_vencimientos`.

TEMPORAL: Circulación todavía no expone estas 3 operaciones en `prestamo_servicio()`.
Cuando Marving las agregue, solo hay que cambiar esta clase (el revisor no cambia).
Solo usa campos estables del Prestamo: estado, fecha_vencimiento, solicitante_id, item_id.
"""
from datetime import timedelta

from django.utils import timezone

from apps.circulacion.aplicacion.dtos import PrestamoDTO
from apps.circulacion.dominio.models import Prestamo
from apps.common.choices import EstadoPrestamo


class PrestamosDeCirculacion:
    def por_vencer(self, ahora, minutos):
        """Activos que vencen entre ahora y dentro de `minutos` minutos."""
        qs = Prestamo.objects.filter(
            estado=EstadoPrestamo.ACTIVO,
            fecha_vencimiento__gt=ahora,
            fecha_vencimiento__lte=ahora + timedelta(minutes=minutos),
        ).order_by("fecha_vencimiento")
        return [PrestamoDTO.desde_modelo(p) for p in qs]

    def vencidos_abiertos(self, ahora):
        """Activos cuya hora de vencimiento ya pasó (todavía no marcados VENCIDO)."""
        qs = Prestamo.objects.filter(
            estado=EstadoPrestamo.ACTIVO, fecha_vencimiento__lt=ahora
        ).order_by("fecha_vencimiento")
        return [PrestamoDTO.desde_modelo(p) for p in qs]

    def marcar_vencido(self, prestamo_id):
        """ACTIVO -> VENCIDO. Devuelve False si ya no estaba ACTIVO."""
        cambiados = Prestamo.objects.filter(
            pk=prestamo_id, estado=EstadoPrestamo.ACTIVO
        ).update(estado=EstadoPrestamo.VENCIDO, actualizado_en=timezone.now())
        return cambiados == 1
