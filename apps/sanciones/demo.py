"""Datos de demo de Sanciones (los usa `seed_demo` de Micaela).

Uso, dentro de seed_demo:
    from apps.sanciones.demo import cargar_demo
    cargar_demo(encargado, ana, diego)

Crea 2 sanciones de ejemplo SIN duplicar si se ejecuta dos veces. Ninguna queda
vigente, así no bloquean a Ana ni a Diego en el recorrido de la demo, pero el
historial y los reportes de sanciones sí muestran datos.
"""
from datetime import date, timedelta

from apps.sanciones.dominio.models import Sancion, TipoSancion


def cargar_demo(encargado, ana, diego, hoy=None):
    """Devuelve cuántas sanciones nuevas creó (0 si ya existían)."""
    hoy = hoy or date.today()
    ejemplos = [
        # Cumplida: suspensión de 3 días que terminó hace más de una semana.
        dict(solicitante_id=diego.pk, tipo=TipoSancion.SUSPENSION_TEMPORAL, duracion_dias=3,
             fecha_inicio=hoy - timedelta(days=20), activa=True,
             motivo="Devolvió la laptop con 2 días de atraso."),
        # Levantada a mano por el encargado.
        dict(solicitante_id=ana.pk, tipo=TipoSancion.OBSERVACION, duracion_dias=None,
             fecha_inicio=hoy - timedelta(days=30), activa=False,
             motivo="Observación por no avisar la cancelación de una reserva."),
    ]
    creadas = 0
    for datos in ejemplos:
        _, nueva = Sancion.objects.get_or_create(
            solicitante_id=datos["solicitante_id"], motivo=datos["motivo"],
            defaults={**datos, "aplicada_por_id": encargado.pk},
        )
        creadas += nueva
    return creadas
