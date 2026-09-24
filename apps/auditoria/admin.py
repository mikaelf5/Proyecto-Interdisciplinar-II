from django.contrib import admin

from .models import RegistroAuditoria


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ("id", "fecha_hora", "actor_id", "accion", "entidad", "entidad_id")
    list_filter = ("accion", "entidad")
    search_fields = ("actor_id", "entidad", "entidad_id", "motivo")
    readonly_fields = ("id", "creado_en", "actualizado_en", "fecha_hora")
    date_hierarchy = "fecha_hora"

    def has_change_permission(self, request, obj=None):
        # Un registro de auditoría no debería poder editarse una vez creado.
        return False
