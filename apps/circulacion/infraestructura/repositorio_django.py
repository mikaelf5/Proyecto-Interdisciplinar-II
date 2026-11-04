"""Adaptadores Django ORM; sin claves foráneas entre bounded contexts."""
from django.utils import timezone

from apps.common.choices import EstadoPrestamo
from apps.circulacion.dominio.models import Prestamo
from apps.circulacion.dominio.repositorio import IPrestamoRepositorio


class PrestamoRepositorioImpl(IPrestamoRepositorio):
    def buscar_por_id(self, prestamo_id):
        return Prestamo.objects.filter(pk=prestamo_id).first()
    def guardar(self, prestamo):
        prestamo.save()
        return prestamo
    def vigentes_de(self, solicitante_id):
        return Prestamo.objects.filter(solicitante_id=solicitante_id, estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO])

    def historial_de(self, solicitante_id):
        return Prestamo.objects.filter(
            solicitante_id=solicitante_id
        ).order_by("-fecha_entrega")
    def vencidos(self):
        return Prestamo.objects.filter(estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO], fecha_vencimiento__lt=timezone.now())
    def buscar_vencidos(self, solicitante_id=None, item_id=None):
        prestamos = Prestamo.objects.filter(
            estado__in=[
                EstadoPrestamo.ACTIVO,
                EstadoPrestamo.VENCIDO
            ],
            fecha_vencimiento__lt=timezone.now()
        )

        if solicitante_id is not None:
            prestamos = prestamos.filter(
                solicitante_id=solicitante_id
            )

        if item_id is not None:
            prestamos = prestamos.filter(
                item_id=item_id
            )

        return prestamos
    def existe_abierto_para_item(self, item_id):
        return Prestamo.objects.filter(item_id=item_id, estado__in=[EstadoPrestamo.ACTIVO, EstadoPrestamo.VENCIDO]).exists()

    def entregados_hoy(self):
        hoy = timezone.localdate()

        return Prestamo.objects.filter(
            fecha_entrega__date=hoy,
            estado=EstadoPrestamo.ACTIVO
        ).order_by("-fecha_entrega")

    def abiertos(self):
        return Prestamo.objects.filter(
            estado__in=[
                EstadoPrestamo.ACTIVO,
                EstadoPrestamo.VENCIDO
            ]
        ).order_by("fecha_vencimiento")
