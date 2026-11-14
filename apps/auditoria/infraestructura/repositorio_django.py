from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_date

from apps.auditoria.dominio.models import RegistroAuditoria
from apps.auditoria.dominio.repositorio import IRegistroAuditoriaRepositorio


class RegistroAuditoriaRepositorioImpl(IRegistroAuditoriaRepositorio):
    def guardar(self, registro):
        registro.save()
        return registro

    def buscar(self, filtros):
        """Filtros (todos opcionales): accion, entidad, actor (ID), q (texto del motivo), desde, hasta."""
        qs = RegistroAuditoria.objects.all().order_by("-fecha_hora")
        if filtros.get("accion"):
            qs = qs.filter(accion=filtros["accion"])
        if filtros.get("entidad"):
            qs = qs.filter(entidad=filtros["entidad"])
        if filtros.get("actor"):
            qs = qs.filter(actor_id__icontains=filtros["actor"])
        if filtros.get("q"):
            qs = qs.filter(motivo__icontains=filtros["q"])
        desde = parse_date(filtros.get("desde", ""))
        hasta = parse_date(filtros.get("hasta", ""))
        if desde:
            qs = qs.filter(fecha_hora__date__gte=desde)
        if hasta:
            qs = qs.filter(fecha_hora__date__lte=hasta)
        return qs

    def entidades(self):
        return list(
            RegistroAuditoria.objects.order_by("entidad")
            .values_list("entidad", flat=True).distinct()
        )

    def nombres_de_actores(self, ids):
        cuentas = get_user_model().objects.filter(pk__in=set(ids))
        return {c.pk: c.nombres for c in cuentas}
