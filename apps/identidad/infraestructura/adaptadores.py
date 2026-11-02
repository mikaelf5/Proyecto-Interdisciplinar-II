"""Adaptadores hacia otros contextos (implementan dominio/puertos.py).

- Sanciones: se usa SU servicio público (tiene_sancion_activa / sancion_mas_grave),
  acordado con Estrella (ehuarsam). Nunca leemos su tabla directamente.
- Circulación: todavía no publica "préstamos devueltos a tiempo de una cuenta",
  así que el adaptador hace esa consulta de solo lectura sobre su modelo.
  Si Marving publica un método en su servicio, solo se cambia esta clase.
"""
from django.db.models import F

from apps.identidad.dominio.puertos import IHistorialPrestamosPuerto, ISancionesPuerto


class SancionesAdaptador(ISancionesPuerto):
    def __init__(self):
        from apps.sanciones.fabrica import sancion_servicio
        self._servicio = sancion_servicio()

    def tiene_sancion_activa(self, cuenta_id):
        return self._servicio.tiene_sancion_activa(cuenta_id)

    def sancion_mas_grave(self, cuenta_id):
        tipo = self._servicio.sancion_mas_grave(cuenta_id)
        return str(tipo) if tipo else None


class HistorialPrestamosAdaptador(IHistorialPrestamosPuerto):
    def devueltos_a_tiempo(self, cuenta_id):
        from apps.circulacion.models import Prestamo
        from apps.common.choices import EstadoPrestamo

        return Prestamo.objects.filter(
            solicitante_id=cuenta_id,
            estado=EstadoPrestamo.DEVUELTO,
            fecha_devolucion_real__lte=F("fecha_vencimiento"),
        ).count()
