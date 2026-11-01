"""
Presentación (panel admin) — solo CONSULTA.

Las reservas se crean y cambian desde las pantallas, porque ahí se aplican las
reglas (horario, política, choques, supervisor). Si el admin las editara a mano
se saltaría esas reglas, por eso aquí todo es de solo lectura.
"""
from django.contrib import admin

from .dominio.models import Reserva


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("fecha", "hora_inicio", "hora_fin", "item_id", "solicitante_id", "estado", "posicion_en_cola")
    list_filter = ("estado", "fecha")
    search_fields = ("=item_id", "=solicitante_id")
    date_hierarchy = "fecha"

    def get_readonly_fields(self, request, obj=None):
        return [f.name for f in self.model._meta.fields]

    def has_add_permission(self, request):
        return False
