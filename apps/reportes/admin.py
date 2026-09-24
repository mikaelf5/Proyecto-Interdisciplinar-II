from django.contrib import admin

from .models import Reporte


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("id", "tipo", "periodo_inicio", "periodo_fin", "generado_por_id", "creado_en")
    list_filter = ("tipo",)
    search_fields = ("generado_por_id",)
    readonly_fields = ("id", "creado_en", "actualizado_en")
    date_hierarchy = "creado_en"

