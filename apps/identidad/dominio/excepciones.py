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
