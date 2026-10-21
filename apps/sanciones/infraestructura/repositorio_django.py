from apps.sanciones.dominio.models import Sancion
from apps.sanciones.dominio.repositorio import ISancionRepositorio


class SancionRepositorioImpl(ISancionRepositorio):
    def guardar(self, sancion):
        sancion.save()
        return sancion

    def activas_de(self, solicitante_id):
        return Sancion.objects.filter(solicitante_id=solicitante_id, activa=True)
    
    def por_periodo(self, inicio, fin):
        return Sancion.objects.filter(
            fecha_inicio__range=(inicio, fin)
        ).order_by("fecha_inicio", "creado_en")