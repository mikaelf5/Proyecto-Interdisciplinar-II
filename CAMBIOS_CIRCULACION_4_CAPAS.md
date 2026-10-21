# Circulación reorganizada en cuatro capas

Esta copia conserva el proyecto recibido, excluyendo cachés y archivos locales sensibles.

## Cambios
- `dominio/models.py`: Solicitud y Prestamo con `Meta.app_label = "circulacion"` para conservar el registro Django y las tablas existentes.
- `dominio/servicios.py`: ServicioDeAprobacion (M4), sin alterar su lógica.
- `dominio/repositorio.py`: contratos ISolicitudRepositorio e IPrestamoRepositorio.
- `infraestructura/repositorio_django.py`: adaptadores Django ORM para ambos contratos.
- `aplicacion/servicios.py`: casos de uso pendientes, incluido M5 (sin implementación).
- `aplicacion/dtos.py`: DTO inicial para la entrega (a revisar al integrar contratos).
- `presentacion/views.py` y `presentacion/forms.py`: vistas y formulario actuales.
- Los archivos antiguos `models.py`, `services.py`, `views.py`, `forms.py` quedan como compatibilidad.
- Migraciones, tests, plantillas y URL no se alteran.

## Verificaciones pendientes en el equipo Windows con venv y PostgreSQL
```cmd
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.circulacion
```
No se pudieron ejecutar aquí: el entorno de análisis no tiene Django instalado ni acceso a la base PostgreSQL del proyecto.
No aplicar nuevas migraciones si el segundo comando reporta cambios; revisarlos primero.

## Integración pendiente
E3, N1 e I1: confirmar interfaces reales y ramas integradas antes de implementar M5.
La clase heredada `ServicioDeElegibilidad` sigue siendo un marcador, no un servicio E3 operativo.

## Cómo incorporar sin perder trabajo
Conservar copia de seguridad y preferir revisar los cambios con Git antes de copiar; no reemplazar a ciegas trabajo nuevo de compañeros.
