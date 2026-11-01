"""
Expira las reservas que no se recogieron a tiempo y pasa el turno al siguiente
de la lista de espera.

Uso:
    python manage.py expirar_reservas

Se puede programar para que corra solo cada 5 minutos (Programador de tareas
de Windows o cron en Linux). En la demo se ejecuta a mano.
"""
from django.core.management.base import BaseCommand

from apps.reservas.aplicacion.servicios import ReservaServicioAplicacion


class Command(BaseCommand):
    help = "Expira reservas no recogidas (tolerancia de 15 min) y avanza la lista de espera."

    def handle(self, *args, **opciones):
        expiradas = ReservaServicioAplicacion().expirar_reservas()
        for r in expiradas:
            self.stdout.write(f"  Expirada: {r.franja} (ítem {r.item_id})")
        self.stdout.write(self.style.SUCCESS(f"{len(expiradas)} reserva(s) expirada(s)."))
