"""
Filtros de plantilla compartidos. Uso: {% load utilidades %}
  {{ dic|get_item:clave }}        busca en un diccionario
  {{ estado|estado_texto }}       "MANTENIMIENTO" -> "En mantenimiento"
  {{ estado|estado_color }}       color: verde, ambar, rojo, azul o gris
  {{ estado|estado_badge }}       clases de Bootstrap: "bg-success", "bg-danger"...
"""
from django import template

register = template.Library()

ESTADOS = {
    # ítems
    "DISPONIBLE": ("Disponible", "verde"), "RESERVADO": ("Reservado", "ambar"),
    "PRESTADO": ("Prestado", "rojo"), "MANTENIMIENTO": ("En mantenimiento", "ambar"),
    "BAJA": ("Dado de baja", "gris"),
    # reservas
    "ACTIVA": ("Activa", "verde"), "CONFIRMADA": ("Confirmada", "azul"),
    "EXPIRADA": ("Expirada", "gris"), "CANCELADA": ("Cancelada", "gris"),
    # lista de espera
    "EN_ESPERA": ("En espera", "azul"), "AVISADO": ("Avisado", "ambar"),
    "ATENDIDO": ("Atendido", "verde"), "CANCELADO": ("Cancelado", "gris"),
}


@register.filter
def get_item(diccionario, clave):
    return (diccionario or {}).get(clave, "")


@register.filter
def estado_texto(codigo):
    return ESTADOS.get(str(codigo), (str(codigo).replace("_", " ").capitalize(), ""))[0]


@register.filter
def estado_color(codigo):
    return ESTADOS.get(str(codigo), ("", "gris"))[1]


BADGES = {"verde": "bg-success", "ambar": "bg-warning text-dark", "rojo": "bg-danger",
          "azul": "bg-primary", "gris": "bg-secondary"}


@register.filter
def estado_badge(codigo):
    """Clases de Bootstrap para la etiqueta del estado: {{ item.estado|estado_badge }}"""
    return BADGES[estado_color(codigo)]
