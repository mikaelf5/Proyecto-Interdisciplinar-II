"""Adaptador de IFuenteDeReportes: lee de Circulación, Auditoría, Identidad y Catálogo.

- Préstamos: TEMPORAL, lee el modelo de Circulación (sus campos estables). Cuando
  Marving exponga una consulta por periodo en `prestamo_servicio()`, se cambia aquí.
- Daños: son los registros de auditoría ITEM_DANIADO que NO son casos de pérdida
  (acuerdo pendiente con Marving: al devolver dañado, auditar ITEM_DANIADO sobre "Item").
- Nombres: `get_user_model()` (API pública de Django, no se importa Identidad).
- Ítems: servicio de aplicación de Catálogo.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model

from apps.auditoria.fabrica import auditoria_servicio
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.dominio.models import Prestamo
from apps.reportes.dominio.fuentes import FilaDanio, FilaPrestamo, IFuenteDeReportes

VENTANA_DANIO = timedelta(hours=1)    # el daño se registra al recibir el ítem
MARGEN_DANIO = timedelta(minutes=1)   # por si la devolución se guarda un instante después


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
            FilaDanio(fecha=r.fecha_hora, entidad=r.entidad, entidad_id=r.entidad_id, motivo=r.motivo,
                      solicitante_id=self._quien_lo_devolvio(r))
            for r in registros
            if r.entidad != "CasoPerdida"   # las pérdidas ya salen de Gestión de Pérdidas
        ]

    @staticmethod
    def _quien_lo_devolvio(registro):
        """Si el daño se registró al devolver el ítem, el responsable es quien lo devolvió.

        La auditoría no guarda el préstamo, así que se busca la devolución de ese ítem
        ocurrida hasta 1 hora antes del registro. Si el daño se marcó a mano desde el
        catálogo (sin devolución cerca), no se culpa a nadie: devuelve None.
        """
        if registro.entidad != "Item":
            return None
        prestamo = (
            Prestamo.objects.filter(
                item_id=registro.entidad_id,
                fecha_devolucion_real__lte=registro.fecha_hora + MARGEN_DANIO,
                fecha_devolucion_real__gte=registro.fecha_hora - VENTANA_DANIO,
            )
            .order_by("-fecha_devolucion_real")
            .first()
        )
        return prestamo.solicitante_id if prestamo else None

    def items_de_prestamos(self, prestamo_ids):
        filas = Prestamo.objects.filter(pk__in=set(prestamo_ids)).values_list("id", "item_id")
        return dict(filas)

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