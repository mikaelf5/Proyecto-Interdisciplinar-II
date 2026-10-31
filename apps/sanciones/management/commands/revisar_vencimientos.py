"""
Revisa los préstamos por vencer y los vencidos (RF-H1, RF-H2).

Uso:
    python manage.py revisar_vencimientos            # recordatorio 30 min antes
    python manage.py revisar_vencimientos --minutos 60

Para dejarlo automático (cada 5 minutos) en Linux:
    */5 * * * * cd /ruta/al/proyecto && venv/bin/python manage.py revisar_vencimientos
En la demo basta con ejecutarlo a mano.
"""
from django.core.management.base import BaseCommand

from apps.sanciones.fabrica import revisor_vencimientos


class Command(BaseCommand):
    help = "Avisa los préstamos por vencer y marca como VENCIDOS los que no se devolvieron."

    def add_arguments(self, parser):
        parser.add_argument(
            "--minutos", type=int, default=30,
            help="Cuántos minutos antes del vencimiento se envía el recordatorio (30).",
        )

    def handle(self, *args, **opciones):
        resultado = revisor_vencimientos().revisar(minutos_aviso=opciones["minutos"])
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios enviados: {resultado.recordatorios} · "
            f"Préstamos marcados como vencidos: {resultado.vencidos}"
        ))
