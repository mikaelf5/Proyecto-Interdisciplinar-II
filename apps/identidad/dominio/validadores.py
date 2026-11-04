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


# ---------- Registro por autoservicio ----------
DOMINIO_INSTITUCIONAL = "@unsa.edu.pe"


def validar_correo_institucional(correo):
    """Solo se aceptan correos que terminan en @unsa.edu.pe (requisito del sistema)."""
    from django.core.exceptions import ValidationError

    if not (correo or "").strip().lower().endswith(DOMINIO_INSTITUCIONAL):
        raise ValidationError(f"Usa tu correo institucional (termina en {DOMINIO_INSTITUCIONAL}).")


EXTENSIONES_DOCUMENTO = ("pdf", "jpg", "jpeg", "png")
TAMANIO_MAXIMO_DOCUMENTO = 5 * 1024 * 1024  # 5 MB


def validar_documento(archivo):
    """El documento que acredita la condición institucional: PDF o imagen, máx. 5 MB."""
    from django.core.exceptions import ValidationError

    nombre = getattr(archivo, "name", "") or ""
    extension = nombre.rsplit(".", 1)[-1].lower() if "." in nombre else ""
    if extension not in EXTENSIONES_DOCUMENTO:
        raise ValidationError("Sube el documento en PDF, JPG o PNG.")
    if (getattr(archivo, "size", 0) or 0) > TAMANIO_MAXIMO_DOCUMENTO:
        raise ValidationError("El documento no debe pesar más de 5 MB.")
