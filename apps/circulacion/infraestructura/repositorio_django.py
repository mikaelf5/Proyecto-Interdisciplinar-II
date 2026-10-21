"""Adaptadores Django ORM; sin claves foráneas entre bounded contexts."""
from django.utils import timezone
from apps.common.choices import EstadoPrestamo, EstadoSolicitud
from apps.circulacion.dominio.models import Solicitud, Prestamo
from apps.circulacion.dominio.repositorio import ISolicitudRepositorio, IPrestamoRepositorio

class SolicitudRepositorioImpl(ISolicitudRepositorio):
    def buscar_por_id(self, solicitud_id):
        return Solicitud.objects.filter(pk=solicitud_id).first()
    def guardar(self, solicitud):
        solicitud.save()
        return solicitud
    def pendientes(self):
        return Solicitud.objects.filter(estado__in=[EstadoSolicitud.PENDIENTE, EstadoSolicitud.EN_ESPERA_SUPERVISOR])

class PrestamoRepositorioImpl(IPrestamoRepositorio):
    def buscar_por_id(self, prestamo_id):
        return Prestamo.objects.filter(pk=prestamo_id).first()
    def guardar(self, prestamo):
        prestamo.save()
        return prestamo
    def vigentes_de(self, solicitante_id):
        return Prestamo.objects.filter(solicitante_id=solicitante_id, estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO])
    def vencidos(self):
        return Prestamo.objects.filter(estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO], fecha_vencimiento__lt=timezone.now())
    def existe_abierto_para_item(self, item_id):
        return Prestamo.objects.filter(item_id=item_id, estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO]).exists()
