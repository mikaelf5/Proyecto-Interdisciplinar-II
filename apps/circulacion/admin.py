from django.contrib import admin

from .models import Solicitud, Prestamo


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "solicitante_id",
        "fecha_inicio",
        "fecha_fin",
        "estado",
    )

    list_filter = ("estado",)
    search_fields = ("solicitante_id",)
    readonly_fields = ("id", "creado_en", "actualizado_en")


@admin.register(Prestamo)
class PrestamoAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "item_id",
        "solicitante_id",
        "fecha_entrega",
        "fecha_vencimiento",
        "estado",
    )

    list_filter = ("estado", "garantia_tipo")
    search_fields = ("item_id", "solicitante_id")
    readonly_fields = ("id", "creado_en", "actualizado_en")