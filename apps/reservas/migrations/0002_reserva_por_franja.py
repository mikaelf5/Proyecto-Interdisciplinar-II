"""
Reserva pasa a ser "por franja": un día + hora de inicio + hora de fin.

Las reservas antiguas (solo cola, sin fecha ni horas) eran datos de demo y no
se pueden convertir, así que se borran antes de cambiar la tabla.
Después de migrar, vuelve a cargar la demo con:  python manage.py seed_demo
"""
import datetime

from django.db import migrations, models


def borrar_reservas_antiguas(apps, schema_editor):
    apps.get_model("reservas", "Reserva").objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("reservas", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(borrar_reservas_antiguas, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="reserva",
            name="reserva_unica_activa_por_solicitante_item",
        ),
        migrations.AddField(
            model_name="reserva",
            name="categoria_id",
            field=models.UUIDField(blank=True, db_index=True, null=True, verbose_name="categoría"),
        ),
        migrations.AddField(
            model_name="reserva",
            name="fecha",
            field=models.DateField(default=datetime.date(2026, 1, 1), verbose_name="fecha de uso"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reserva",
            name="hora_inicio",
            field=models.TimeField(default=datetime.time(8, 0), verbose_name="desde"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reserva",
            name="hora_fin",
            field=models.TimeField(default=datetime.time(9, 0), verbose_name="hasta"),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="reserva",
            name="finalidad",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="reserva",
            name="aprobado_por_supervisor_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reserva",
            name="motivo",
            field=models.TextField(blank=True, help_text="Motivo de rechazo o anulación."),
        ),
        migrations.AlterField(
            model_name="reserva",
            name="posicion_en_cola",
            field=models.PositiveIntegerField(
                blank=True, null=True, help_text="Solo para reservas ACTIVAS (en lista de espera).",
                verbose_name="posición en lista de espera",
            ),
        ),
        migrations.AlterField(
            model_name="reserva",
            name="estado",
            field=models.CharField(
                choices=[
                    ("ACTIVA", "Activa (en lista de espera)"),
                    ("EN_ESPERA_SUPERVISOR", "En espera de supervisor"),
                    ("CONFIRMADA", "Confirmada"),
                    ("ATENDIDA", "Atendida (ítem entregado)"),
                    ("FINALIZADA", "Finalizada (ítem devuelto)"),
                    ("EXPIRADA", "Expirada"),
                    ("CANCELADA", "Cancelada"),
                    ("RECHAZADA", "Rechazada por supervisor"),
                    ("ANULADA", "Anulada por encargado"),
                ],
                default="CONFIRMADA",
                max_length=25,
            ),
        ),
        migrations.AlterModelOptions(
            name="reserva",
            options={"ordering": ["fecha", "hora_inicio"], "verbose_name": "reserva",
                     "verbose_name_plural": "reservas"},
        ),
        migrations.AddIndex(
            model_name="reserva",
            index=models.Index(fields=["item_id", "fecha"], name="reserva_item_fecha_idx"),
        ),
        migrations.AddConstraint(
            model_name="reserva",
            constraint=models.CheckConstraint(
                condition=models.Q(("hora_fin__gt", models.F("hora_inicio"))),
                name="reserva_hora_fin_mayor_que_inicio",
            ),
        ),
    ]
