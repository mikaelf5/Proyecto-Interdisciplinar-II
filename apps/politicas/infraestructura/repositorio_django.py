from apps.politicas.dominio.models import PoliticaPrestamo
from apps.politicas.dominio.repositorio import IPoliticaRepositorio


class PoliticaRepositorioImpl(IPoliticaRepositorio):

    def buscar_para(self, tipo_item, tipo_usuario):
        return PoliticaPrestamo.objects.filter(
            tipo_item=tipo_item,
            tipo_usuario=tipo_usuario
        ).first()

    def guardar(self, politica):
        politica.save()
        return politica

    def buscar_por_categoria(self, categoria_id, tipo_usuario):
        return PoliticaPrestamo.objects.filter(
            categoria_id=categoria_id,
            tipo_usuario=tipo_usuario
        ).first()