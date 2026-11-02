"""Reglas de formato de los datos personales (RF-B1).

Viven en un solo lugar y se usan en el modelo, en el servicio y en el
formulario: si mañana se acepta, por ejemplo, carné de extranjería, se
cambia aquí y nada más.
"""
from django.core.validators import RegexValidator

validar_dni = RegexValidator(r"^\d{8}$", "El DNI debe tener exactamente 8 dígitos.")
validar_celular = RegexValidator(r"^9\d{8}$", "El celular debe tener 9 dígitos y empezar con 9.")
validar_cui = RegexValidator(r"^\d{8}$", "El CUI debe tener exactamente 8 dígitos.")

# Solo correos de la universidad (requisito: la cuenta debe ser institucional).
DOMINIO_INSTITUCIONAL = "unsa.edu.pe"


def validar_correo_institucional(valor):
    """Acepta solo `algo@unsa.edu.pe` (sin importar mayúsculas).

    Rechaza subdominios y trampas como `x@unsa.edu.pe.com` o `x@gmail.com`:
    se compara la parte después de la ÚLTIMA arroba, completa.
    """
    from django.core.exceptions import ValidationError

    usuario, arroba, dominio = (valor or "").strip().rpartition("@")
    if not arroba or not usuario or dominio.lower() != DOMINIO_INSTITUCIONAL:
        raise ValidationError(
            f"Usa un correo institucional que termine en @{DOMINIO_INSTITUCIONAL}.",
            code="correo_no_institucional",
        )


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
