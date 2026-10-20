"""Presentación (panel admin): las acciones pasan por el servicio de aplicación."""
from django.contrib import admin

from .aplicacion.servicios import NotificacionServicioAplicacion
from .dominio.models import Notificacion


@admin.action(description="Reintentar envío por correo")
def marcar_enviadas(modeladmin, request, queryset):
    servicio = NotificacionServicioAplicacion()
    for n in queryset.filter(fecha_envio__isnull=True):
        servicio.reintentar(n.id)


@admin.action(description="Marcar como leídas")
def marcar_leidas(modeladmin, request, queryset):
    servicio = NotificacionServicioAplicacion()
    for n in queryset:
        servicio.marcar_leida(n.id)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "destinatario_id", "canal", "fecha_envio", "leida")
    list_filter = ("tipo", "canal", "leida")
    search_fields = ("destinatario_id", "mensaje")
    readonly_fields = ("id",)
    actions = [marcar_enviadas, marcar_leidas]
