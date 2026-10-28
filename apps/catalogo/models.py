# Puente: Django busca los modelos en este archivo.
# Los agregados viven en la capa de dominio (dominio/models.py).
from .dominio.models import Categoria, CondicionFisica, Item  # noqa: F401
