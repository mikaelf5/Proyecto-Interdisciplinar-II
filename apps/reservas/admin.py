"""Presentación (panel admin): las acciones pasan por el servicio de aplicación."""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .aplicacion.servicios import ReservaServicioAplicacion
from .dominio.models import Reserva


def _aplicar(modeladmin, request, queryset, metodo, etiqueta):
    servicio = ReservaServicioAplicacion()
    ok, errores = 0, 0
    for reserva in queryset:
        try:
            getattr(servicio, metodo)(reserva.id)
            ok += 1
        except ValidationError:
            errores += 1
    if ok:
        modeladmin.message_user(request, f"{ok} reserva(s) {etiqueta}.", messages.SUCCESS)
    if errores:
        modeladmin.message_user(
            request, f"{errores} reserva(s) no se pudieron cambiar por su estado actual.",
            messages.WARNING,
        )


@admin.action(description="Confirmar reservas seleccionadas")
def confirmar(modeladmin, request, queryset):
    _aplicar(modeladmin, request, queryset, "confirmar", "confirmada(s)")


@admin.action(description="Expirar reservas seleccionadas")
def expirar(modeladmin, request, queryset):
    _aplicar(modeladmin, request, queryset, "expirar", "expirada(s)")


@admin.action(description="Cancelar reservas seleccionadas")
def cancelar(modeladmin, request, queryset):
    _aplicar(modeladmin, request, queryset, "cancelar", "cancelada(s)")


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("item_id", "posicion_en_cola", "solicitante_id", "estado")
    list_filter = ("estado",)
    search_fields = ("item_id", "solicitante_id")
    readonly_fields = ("id",)
    actions = [confirmar, expirar, cancelar]

    def save_model(self, request, obj, form, change):
        # Si no se indicó posición, la calcula el AsignadorDeCola (al final de la cola).
        if obj.posicion_en_cola is None:
            obj.posicion_en_cola = ReservaServicioAplicacion().siguiente_posicion(obj.item_id)
        super().save_model(request, obj, form, change)
