"""Errores del dominio de Identidad (la capa de presentación decide cómo mostrarlos)."""


class IdentidadError(Exception):
    """Error base del contexto Identidad."""


class CredencialesInvalidas(IdentidadError):
    """Correo o contraseña incorrectos (mensaje genérico a propósito)."""


class CuentaInactiva(IdentidadError):
    """La cuenta existe y la contraseña es correcta, pero está desactivada."""


class CuentaNoEncontrada(IdentidadError):
    pass


class RolInvalido(IdentidadError, ValueError):
    pass


class DatosInvalidos(IdentidadError):
    """Uno o más datos no cumplen las reglas. Lleva un error POR CAMPO.

    `errores` es un dict {campo: mensaje}; la pantalla lo usa para mostrar
    cada error junto a su campo.
    """

    def __init__(self, errores):
        self.errores = dict(errores)
        super().__init__(" ".join(self.errores.values()))


class ActaYaFirmada(IdentidadError):
    """El acta de responsabilidad se firma una sola vez (RF-B2)."""


class OperacionNoPermitida(IdentidadError):
    """La acción rompería una regla (ej. dejar el sistema sin administradores)."""


class MotivoRequerido(IdentidadError):
    """Las acciones sensibles exigen motivo (RF-J1)."""
