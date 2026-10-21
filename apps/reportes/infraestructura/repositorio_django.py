from apps.reportes.dominio.models import Reporte
from apps.reportes.dominio.repositorio import IReporteRepositorio


class ReporteRepositorioImpl(IReporteRepositorio):
    def guardar(self, reporte):
        reporte.save()
        return reporte

    def obtener(self, pk):
        return Reporte.objects.filter(pk=pk).first()

    def listar(self):
        return Reporte.objects.all().order_by("-creado_en")

    def eliminar(self, reporte):
        reporte.delete()