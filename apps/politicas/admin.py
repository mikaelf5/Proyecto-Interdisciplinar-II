from django.contrib import admin

from .models import PoliticaPrestamo


@admin.register(PoliticaPrestamo)
class PoliticaPrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "categoria_id",
        "tipo_item",
        "tipo_usuario",
        "duracion_maxima",
        "max_renovaciones",
        "limite_simultaneo_global",
        "limite_simultaneo_por_tipo",
    )

    list_filter = ("tipo_usuario",)

    search_fields = (
        "tipo_item",
        "=categoria_id",
    )

    readonly_fields = (
        "id",
        "creado_en",
        "actualizado_en",
    )