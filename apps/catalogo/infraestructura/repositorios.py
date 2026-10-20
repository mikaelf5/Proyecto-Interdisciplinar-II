"""
Capa de INFRAESTRUCTURA — implementaciones de repositorio
(«RepositoryImpl» del PDF) con Django ORM + PostgreSQL.
"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q

from ..dominio.models import Categoria, CondicionFisica, Item
from ..dominio.repositorios import (
    ICategoriaRepositorio,
    ICondicionFisicaRepositorio,
    IItemRepositorio,
)


class CategoriaRepositorioImpl(ICategoriaRepositorio):
    def guardar(self, categoria):
        categoria.full_clean()  # valida definicion_atributos
        categoria.save()

    def buscar_por_id(self, categoria_id):
        try:
            return Categoria.objects.get(pk=categoria_id)
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise ValidationError("La categoría no existe.")

    def todas(self):
        return list(Categoria.objects.all())


class ItemRepositorioImpl(IItemRepositorio):
    def guardar(self, item):
        item.full_clean()  # valida atributos dinámicos contra la categoría
        item.save()

    def buscar_por_id(self, item_id):
        try:
            return Item.objects.select_related("categoria").get(pk=item_id)
        except (ObjectDoesNotExist, ValidationError, ValueError):
            raise ValidationError("El ítem no existe.")

    def buscar_por_codigo(self, codigo):
        return Item.objects.select_related("categoria").filter(codigo=codigo).first()

    def buscar(self, filtros):
        """filtros: FiltrosItem (texto, categoria_id, estado, solo_disponibles)."""
        qs = Item.objects.select_related("categoria")
        if filtros.texto:
            # Busca en el código y dentro de los atributos dinámicos (JSONB)
            qs = qs.filter(
                Q(codigo__icontains=filtros.texto)
                | Q(atributos__icontains=filtros.texto)
            )
        if filtros.categoria_id:
            qs = qs.filter(categoria_id=filtros.categoria_id)
        if filtros.estado:
            qs = qs.filter(estado=filtros.estado)
        return list(qs)


class CondicionFisicaRepositorioImpl(ICondicionFisicaRepositorio):
    def guardar(self, condicion):
        condicion.full_clean()
        condicion.save()

    def de_item(self, item_id):
        return list(CondicionFisica.objects.filter(item_id=item_id))
