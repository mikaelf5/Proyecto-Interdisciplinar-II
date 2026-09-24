"""Enumeraciones del dominio (modelo_dominio_v5) usadas por Reservas y Notificaciones."""
from django.db import models


class EstadoReserva(models.TextChoices):
    ACTIVA = "ACTIVA", "Activa"
    CONFIRMADA = "CONFIRMADA", "Confirmada"
    EXPIRADA = "EXPIRADA", "Expirada"
    CANCELADA = "CANCELADA", "Cancelada"


class TipoNotificacion(models.TextChoices):
    RECORDATORIO_VENCIMIENTO = "RECORDATORIO_VENCIMIENTO", "Recordatorio de vencimiento"
    ALERTA_ATRASO = "ALERTA_ATRASO", "Alerta de atraso"
    DISPONIBILIDAD_RESERVA = "DISPONIBILIDAD_RESERVA", "Disponibilidad de reserva"
    INVENTARIO_BAJO = "INVENTARIO_BAJO", "Inventario bajo"
    ITEM_DANIADO = "ITEM_DANIADO", "Ítem dañado"


class CanalNotificacion(models.TextChoices):
    CORREO = "CORREO", "Correo"


class EstadoItem(models.TextChoices):
    DISPONIBLE = "DISPONIBLE", "Disponible"
    PRESTADO = "PRESTADO", "Prestado"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
    BAJA = "BAJA", "Baja"


class MomentoRegistro(models.TextChoices):
    ENTREGA = "ENTREGA", "Entrega"
    DEVOLUCION = "DEVOLUCION", "Devolución"


class TipoUsuario(models.TextChoices):
    ALUMNO = "ALUMNO", "Alumno"
    DOCENTE = "DOCENTE", "Docente"
    ADMINISTRATIVO = "ADMINISTRATIVO", "Administrativo"


class RolSistema(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    ENCARGADO = "ENCARGADO", "Encargado"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    SOLICITANTE = "SOLICITANTE", "Solicitante"


class EtiquetaEstado(models.TextChoices):
    NUEVO = "NUEVO", "Nuevo"
    FRECUENTE = "FRECUENTE", "Frecuente"
    SANCIONADO = "SANCIONADO", "Sancionado"
    BANEADO = "BANEADO", "Baneado"

class EstadoSolicitud(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    EN_ESPERA_SUPERVISOR = "EN_ESPERA_SUPERVISOR", "En espera de supervisor"
    APROBADA = "APROBADA", "Aprobada"
    RECHAZADA = "RECHAZADA", "Rechazada"
    CANCELADA = "CANCELADA", "Cancelada"


class EstadoPrestamo(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    VENCIDO = "VENCIDO", "Vencido"
    DEVUELTO = "DEVUELTO", "Devuelto"
    CERRADO_POR_PERDIDA = "CERRADO_POR_PERDIDA", "Cerrado por pérdida"


class TipoGarantia(models.TextChoices):
    DNI = "DNI", "DNI"
    CARNE_UNIVERSITARIO = "CARNE_UNIVERSITARIO", "Carné universitario"
    OTRO = "OTRO", "Otro"
