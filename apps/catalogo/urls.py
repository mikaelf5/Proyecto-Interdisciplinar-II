# Puente: config/urls.py incluye "apps.catalogo.urls".
# Las rutas viven en la capa de presentación (presentacion/urls.py).
from .presentacion.urls import app_name, urlpatterns  # noqa: F401
