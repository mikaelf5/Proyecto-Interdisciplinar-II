from django.contrib import admin

from .models import CasoPerdida


@admin.register(CasoPerdida)
class CasoPerdidaAdmin(admin.ModelAdmin):
    list_display = ("id", "prestamo_id", "solicitante_id", "fecha", "costo_estimado", "cerrado")
    list_filter = ("cerrado",)
    search_fields = ("prestamo_id", "solicitante_id", "observaciones")
    readonly_fields = ("id", "creado_en", "actualizado_en")
    date_hierarchy = "fecha"
