"""Reglas de formato de los datos personales (RF-B1).

Viven en un solo lugar y se usan en el modelo, en el servicio y en el
formulario: si mañana se acepta, por ejemplo, carné de extranjería, se
cambia aquí y nada más.
"""
from django.core.validators import RegexValidator

validar_dni = RegexValidator(r"^\d{8}$", "El DNI debe tener exactamente 8 dígitos.")
validar_celular = RegexValidator(r"^9\d{8}$", "El celular debe tener 9 dígitos y empezar con 9.")
validar_cui = RegexValidator(r"^\d{8}$", "El CUI debe tener exactamente 8 dígitos.")


def error_de(validador, valor):
    """Devuelve el mensaje de error del validador, o None si el valor es válido.

    Así el servicio de aplicación junta todos los errores de una vez en vez de
    detenerse en el primero.
    """
    from django.core.exceptions import ValidationError

    try:
        validador(valor)
    except ValidationError as error:
        return error.messages[0]
    return None
