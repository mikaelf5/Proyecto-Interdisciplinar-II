"""Adaptador de IFuenteDeReportes: lee de Circulación, Auditoría, Identidad y Catálogo.

- Préstamos: TEMPORAL, lee el modelo de Circulación (sus campos estables). Cuando
  Marving exponga una consulta por periodo en `prestamo_servicio()`, se cambia aquí.
- Daños: son los registros de auditoría ITEM_DANIADO que NO son casos de pérdida
  (acuerdo pendiente con Marving: al devolver dañado, auditar ITEM_DANIADO sobre "Item").
- Nombres: `get_user_model()` (API pública de Django, no se importa Identidad).
- Ítems: servicio de aplicación de Catálogo.
"""
from django.contrib.auth import get_user_model

from apps.auditoria.fabrica import auditoria_servicio
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.dominio.models import Prestamo
from apps.reportes.dominio.fuentes import FilaDanio, FilaPrestamo, IFuenteDeReportes


class FuenteDeReportesDjango(IFuenteDeReportes):
    def prestamos_del_periodo(self, inicio, fin):
        qs = Prestamo.objects.filter(fecha_entrega__date__range=(inicio, fin)).order_by("fecha_entrega")
        return [
            FilaPrestamo(
                id=p.id, item_id=p.item_id, solicitante_id=p.solicitante_id, estado=p.estado,
                fecha_entrega=p.fecha_entrega, fecha_vencimiento=p.fecha_vencimiento,
                fecha_devolucion_real=p.fecha_devolucion_real,
            )
            for p in qs
        ]

    def danios_del_periodo(self, inicio, fin):
        registros = auditoria_servicio().buscar({
            "accion": "ITEM_DANIADO",
            "desde": inicio.isoformat(),
            "hasta": fin.isoformat(),
        })
        return [
            FilaDanio(fecha=r.fecha_hora, entidad=r.entidad, entidad_id=r.entidad_id, motivo=r.motivo)
            for r in registros
            if r.entidad != "CasoPerdida"   # las pérdidas ya salen de Gestión de Pérdidas
        ]

    def nombres_de_cuentas(self, ids):
        cuentas = get_user_model().objects.filter(pk__in=set(ids))
        return {c.pk: c.nombres for c in cuentas}

    def datos_de_items(self, ids):
        catalogo = CatalogoServicioAplicacion()
        datos = {}
        for item_id in set(ids):
            try:
                item = catalogo.obtener_item(item_id)
                datos[item_id] = (item.codigo, item.nombre, item.categoria_nombre)
            except Exception:  # ítem borrado: el reporte sigue, mostrando solo el id
                datos[item_id] = (str(item_id)[:8], "(ítem no encontrado)", "—")
        return datos
