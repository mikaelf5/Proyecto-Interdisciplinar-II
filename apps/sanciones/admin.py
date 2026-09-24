from django.contrib import admin

from .models import Sancion


@admin.register(Sancion)
class SancionAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "solicitante_id", "fecha_inicio", "duracion_dias", "activa")
    list_filter = ("tipo", "activa")
    search_fields = ("solicitante_id", "aplicada_por_id", "prestamo_id", "motivo")
    readonly_fields = ("id", "created_at", "updated_at")
    date_hierarchy = "fecha_inicio"
