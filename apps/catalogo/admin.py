"""
Presentación (panel admin). Las acciones del admin también pasan por el
servicio de aplicación, igual que las vistas web.
"""
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from apps.common.choices import EstadoItem

from .aplicacion.servicios import CatalogoServicioAplicacion
from .dominio.models import Categoria, CondicionFisica, Item

catalogo = CatalogoServicioAplicacion()


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "es_especial", "cantidad_items")
    list_filter = ("es_especial",)
    search_fields = ("nombre",)
    readonly_fields = ("id",)

    @admin.display(description="N.º de ítems")
    def cantidad_items(self, obj):
        return obj.items.count()


def _cambiar(modeladmin, request, queryset, accion, etiqueta):
    ok, errores = 0, 0
    for item in queryset:
        try:
            accion(item.id)
            ok += 1
        except ValidationError:
            errores += 1
    if ok:
        modeladmin.message_user(request, f"{ok} ítem(s) {etiqueta}.", messages.SUCCESS)
    if errores:
        modeladmin.message_user(
            request, f"{errores} ítem(s) no se pudieron cambiar por su estado actual.", messages.WARNING
        )


@admin.action(description="Poner como disponible")
def poner_disponible(modeladmin, request, queryset):
    _cambiar(modeladmin, request, queryset,
             lambda pk: catalogo.cambiar_estado_item(pk, EstadoItem.DISPONIBLE), "puesto(s) como disponible(s)")


@admin.action(description="Marcar como dañado (a mantenimiento)")
def marcar_daniado(modeladmin, request, queryset):
    _cambiar(modeladmin, request, queryset,
             lambda pk: catalogo.marcar_daniado(pk, "Marcado como dañado desde el admin"),
             "enviado(s) a mantenimiento")


@admin.action(description="Dar de baja")
def dar_de_baja(modeladmin, request, queryset):
    _cambiar(modeladmin, request, queryset,
             lambda pk: catalogo.dar_de_baja_item(pk, "Dado de baja desde el admin"), "dado(s) de baja")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("codigo", "categoria", "estado", "motivo_fuera_servicio")
    list_filter = ("categoria", "estado")
    search_fields = ("codigo",)
    readonly_fields = ("id",)
    actions = [poner_disponible, marcar_daniado, dar_de_baja]


@admin.register(CondicionFisica)
class CondicionFisicaAdmin(admin.ModelAdmin):
    list_display = ("item", "momento", "fecha", "prestamo_id", "responsable_id")
    list_filter = ("momento", "fecha")
    search_fields = ("item__codigo", "prestamo_id", "descripcion")
    autocomplete_fields = ("item",)
    readonly_fields = ("id",)
