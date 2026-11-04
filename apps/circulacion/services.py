"""Compatibilidad con importaciones previas a las cuatro capas."""

from .dominio.servicios import ServicioDeElegibilidad

from .aplicacion.servicios import (
    PrestamoServicioAplicacion,
    IPrestamoServicio,
    AprobarYEntregarPrestamo,
    RegistrarDevolucion,
    RenovarPrestamo,
)