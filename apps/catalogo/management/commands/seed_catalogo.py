"""
Carga datos de ejemplo del Catálogo.

Uso:
    python manage.py seed_catalogo           # crea/actualiza sin duplicar
    python manage.py seed_catalogo --limpiar # borra ítems y categorías antes
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalogo.models import Categoria, Item
from apps.common.choices import EstadoItem

CATEGORIAS = {
    "Libros": {
        "es_especial": False,
        "definicion_atributos": {
            "titulo": {"tipo": "texto", "requerido": True},
            "autor": {"tipo": "texto", "requerido": True},
            "isbn": {"tipo": "texto", "requerido": False},
            "editorial": {"tipo": "texto", "requerido": False},
            "anio": {"tipo": "entero", "requerido": False},
        },
    },
    "Equipos": {
        "es_especial": True,
        "definicion_atributos": {
            "nombre": {"tipo": "texto", "requerido": True},
            "marca": {"tipo": "texto", "requerido": True},
            "modelo": {"tipo": "texto", "requerido": False},
            "numero_serie": {"tipo": "texto", "requerido": True},
        },
    },
    "Indumentaria": {
        "es_especial": False,
        "definicion_atributos": {
            "prenda": {"tipo": "texto", "requerido": True},
            "talla": {"tipo": "opcion", "requerido": True, "opciones": ["XS", "S", "M", "L", "XL"]},
            "color": {"tipo": "texto", "requerido": False},
        },
    },
}

ITEMS = [
    ("LIB-001", "Libros", {"titulo": "Cien años de soledad", "autor": "Gabriel García Márquez", "anio": 1967}),
    ("LIB-002", "Libros", {"titulo": "Clean Code", "autor": "Robert C. Martin", "isbn": "9780132350884"}),
    ("LIB-003", "Libros", {"titulo": "Domain-Driven Design", "autor": "Eric Evans", "editorial": "Addison-Wesley"}),
    ("LIB-004", "Libros", {"titulo": "Cálculo", "autor": "James Stewart", "anio": 2012}),
    ("EQP-001", "Equipos", {"nombre": "Laptop", "marca": "Lenovo", "modelo": "ThinkPad E14", "numero_serie": "LNV-2026-001"}),
    ("EQP-002", "Equipos", {"nombre": "Proyector", "marca": "Epson", "modelo": "X49", "numero_serie": "EPS-2026-014"}),
    ("EQP-003", "Equipos", {"nombre": "Cámara", "marca": "Canon", "numero_serie": "CAN-2026-007"}),
    ("IND-001", "Indumentaria", {"prenda": "Mandil de laboratorio", "talla": "M", "color": "Blanco"}),
    ("IND-002", "Indumentaria", {"prenda": "Mandil de laboratorio", "talla": "L", "color": "Blanco"}),
    ("IND-003", "Indumentaria", {"prenda": "Casco de seguridad", "talla": "S", "color": "Amarillo"}),
]


class Command(BaseCommand):
    help = "Crea categorías e ítems de ejemplo para el Catálogo."

    def add_arguments(self, parser):
        parser.add_argument("--limpiar", action="store_true", help="Borra ítems y categorías antes de cargar.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if opciones["limpiar"]:
            Item.objects.all().delete()
            Categoria.objects.all().delete()
            self.stdout.write(self.style.WARNING("Catálogo limpiado."))

        categorias = {}
        for nombre, datos in CATEGORIAS.items():
            cat, _ = Categoria.objects.update_or_create(nombre=nombre, defaults=datos)
            cat.full_clean()
            categorias[nombre] = cat
        self.stdout.write(f"Categorías: {len(categorias)}")

        creados = 0
        for codigo, cat_nombre, atributos in ITEMS:
            item = Item.objects.filter(codigo=codigo).first() or Item(codigo=codigo)
            item.categoria = categorias[cat_nombre]
            item.atributos = atributos
            item.estado = EstadoItem.DISPONIBLE
            item.full_clean()  # aplica la validación de atributos
            item.save()
            creados += 1
        self.stdout.write(self.style.SUCCESS(f"Ítems cargados: {creados}"))
