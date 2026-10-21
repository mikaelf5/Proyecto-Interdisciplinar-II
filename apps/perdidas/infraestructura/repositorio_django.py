from django.db.models import Q

from apps.perdidas.dominio.models import CasoPerdida
from apps.perdidas.dominio.repositorio import ICasoPerdidaRepositorio


class CasoPerdidaRepositorioImpl(ICasoPerdidaRepositorio):
    def guardar(self, caso):
        caso.save()
        return caso

    def obtener(self, pk):
        return CasoPerdida.objects.filter(pk=pk).first()

    def buscar(self, estado="", q=""):
        qs = CasoPerdida.objects.all().order_by("cerrado", "-fecha", "-creado_en")
        if estado == "abierto":
            qs = qs.filter(cerrado=False)
        elif estado == "cerrado":
            qs = qs.filter(cerrado=True)
        q = q.strip()
        if q:
            qs = qs.filter(
                Q(prestamo_id__icontains=q)
                | Q(solicitante_id__icontains=q)
                | Q(observaciones__icontains=q)
            )
        return qs

    def contar_abiertos(self):
        return CasoPerdida.objects.filter(cerrado=False).count()

    def eliminar(self, caso):
        caso.delete()

    def por_periodo(self, inicio, fin):
        return CasoPerdida.objects.filter(fecha__range=(inicio, fin)).order_by("fecha", "creado_en")