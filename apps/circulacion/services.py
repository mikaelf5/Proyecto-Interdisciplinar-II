"""Compatibilidad con importaciones previas a las cuatro capas."""
from .dominio.servicios import ServicioDeAprobacion, ServicioDeElegibilidad
from .aplicacion.servicios import (
    AprobarYEntregarPrestamo, RegistrarDevolucion, RenovarPrestamo,
    SolicitudServicioAplicacion, PrestamoServicioAplicacion,
    ISolicitudServicio, IPrestamoServicio,
)
