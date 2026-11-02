"""
Recalcula la etiqueta (NUEVO / FRECUENTE / SANCIONADO / BANEADO) de todos los solicitantes.

Uso:
    python manage.py actualizar_etiquetas

Las etiquetas también se recalculan solas cada vez que Circulación consulta
la habilitación y al abrir «Mi perfil»; este comando sirve para ponerlas al
día todas juntas (ej. una vez al día, junto con `revisar_vencimientos`).
"""
from django.core.management.base import BaseCommand

from apps.identidad.fabrica import cuenta_servicio


class Command(BaseCommand):
    help = "Recalcula las etiquetas automáticas de los solicitantes (RF-B6)."

    def handle(self, *args, **opciones):
        cambios = cuenta_servicio().actualizar_todas_las_etiquetas()
        self.stdout.write(self.style.SUCCESS(f"Etiquetas actualizadas: {cambios} cambio(s)."))
