from django.utils.dateparse import parse_date

from apps.auditoria.dominio.models import RegistroAuditoria
from apps.auditoria.dominio.repositorio import IRegistroAuditoriaRepositorio


class RegistroAuditoriaRepositorioImpl(IRegistroAuditoriaRepositorio):
    def guardar(self, registro):
        registro.save()
        return registro

    def buscar(self, filtros):
        qs = RegistroAuditoria.objects.all().order_by("-fecha_hora")
        if filtros.get("accion"):
            qs = qs.filter(accion=filtros["accion"])
        if filtros.get("entidad"):
            qs = qs.filter(entidad=filtros["entidad"])
        if filtros.get("actor"):
            qs = qs.filter(actor_id__icontains=filtros["actor"])
        desde = parse_date(filtros.get("desde", ""))
        hasta = parse_date(filtros.get("hasta", ""))
        if desde:
            qs = qs.filter(fecha_hora__date__gte=desde)
        if hasta:
            qs = qs.filter(fecha_hora__date__lte=hasta)
        return qs