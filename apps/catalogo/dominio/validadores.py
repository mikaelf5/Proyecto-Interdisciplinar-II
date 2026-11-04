"""
Validación de los atributos dinámicos de un Item contra la definición
de su Categoría (Categoria.definicion_atributos).

Formato esperado de definicion_atributos:
{
    "autor":  {"tipo": "texto",  "requerido": true},
    "anio":   {"tipo": "entero", "requerido": false},
    "talla":  {"tipo": "opcion", "requerido": true, "opciones": ["S", "M", "L"]}
}
Tipos soportados: texto, entero, numero, booleano, fecha (AAAA-MM-DD), opcion.
"""
from datetime import date

from django.core.exceptions import ValidationError

def _es_texto(valor, regla):
    return isinstance(valor, str)


def _es_entero(valor, regla):
    return isinstance(valor, int) and not isinstance(valor, bool)


def _es_numero(valor, regla):
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _es_booleano(valor, regla):
    return isinstance(valor, bool)


def _es_fecha(valor, regla):
    try:
        date.fromisoformat(str(valor))
        return True
    except ValueError:
        return False


def _es_opcion(valor, regla):
    return valor in regla.get("opciones", [])


# Cada tipo de atributo tiene su verificador. Para agregar un tipo nuevo basta
# con agregar una línea aquí (sin tocar el resto del código).
VERIFICADORES = {
    "texto": _es_texto,
    "entero": _es_entero,
    "numero": _es_numero,
    "booleano": _es_booleano,
    "fecha": _es_fecha,
    "opcion": _es_opcion,
}
TIPOS = set(VERIFICADORES)


def _es_del_tipo(valor, regla):
    verificador = VERIFICADORES.get(regla.get("tipo", "texto"))
    return verificador is not None and verificador(valor, regla)


def validar_atributos(atributos, definicion):
    """Lanza ValidationError con todos los problemas encontrados."""
    atributos = atributos or {}
    definicion = definicion or {}
    errores = []

    if not isinstance(atributos, dict):
        raise ValidationError({"atributos": "Los atributos deben ser un objeto JSON."})

    for nombre, regla in definicion.items(): #por cada atributo que pide la categoría
        if nombre not in atributos or atributos[nombre] in (None, ""):
            if regla.get("requerido", False):
                errores.append(f"Falta el atributo obligatorio «{nombre}».") # ◄ anota el problema
            continue
        
        if not _es_del_tipo(atributos[nombre], regla):
            tipo = regla.get("tipo", "texto")
            extra = f" ({', '.join(regla.get('opciones', []))})" if tipo == "opcion" else ""
            errores.append(f"«{nombre}» debe ser de tipo {tipo}{extra}.")

    sobrantes = set(atributos) - set(definicion)
    for nombre in sorted(sobrantes):
        errores.append(f"«{nombre}» no está definido en la categoría.")

    if errores:
        raise ValidationError({"atributos": errores})


def validar_definicion(definicion):
    """Valida que la definición de una Categoría esté bien escrita."""
    if not isinstance(definicion, dict):
        raise ValidationError({"definicion_atributos": "Debe ser un objeto JSON."})
    errores = []
    for nombre, regla in definicion.items():
        if not isinstance(regla, dict):
            errores.append(f"La regla de «{nombre}» debe ser un objeto.")
            continue
        tipo = regla.get("tipo", "texto")
        if tipo not in TIPOS:
            errores.append(f"«{nombre}»: tipo «{tipo}» no válido. Usa: {', '.join(sorted(TIPOS))}.")
        if tipo == "opcion" and not regla.get("opciones"):
            errores.append(f"«{nombre}»: el tipo opcion necesita una lista «opciones».")
    if errores:
        raise ValidationError({"definicion_atributos": errores})
