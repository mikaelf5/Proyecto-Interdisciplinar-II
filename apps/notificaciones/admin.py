from django.contrib import admin

from .models import Notificacion


@admin.action(description="Marcar como enviadas")
def marcar_enviadas(modeladmin, request, queryset):
    for n in queryset.filter(fecha_envio__isnull=True):
        n.marcar_enviada()


@admin.action(description="Marcar como leídas")
def marcar_leidas(modeladmin, request, queryset):
    queryset.update(leida=True)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "destinatario_id", "canal", "fecha_envio", "leida")
    list_filter = ("tipo", "canal", "leida")
    search_fields = ("destinatario_id", "mensaje")
    readonly_fields = ("id",)
    actions = [marcar_enviadas, marcar_leidas]
