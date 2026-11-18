"""Adaptador de IFuenteDeReportes: pide los datos a los servicios de los otros módulos.

- Préstamos: servicio de Circulación (`entregados_entre`, `items_de_prestamos`).
  Ya no se lee el modelo `Prestamo` directamente.
- Daños: registros de auditoría ITEM_DANIADO que NO son casos de pérdida. Si el daño se
  registró al recibir una devolución, se indica quién devolvió el ítem (idea de Micaela).
- Nombres: `get_user_model()` (API pública de Django, no se importa Identidad).
- Ítems: servicio de Catálogo, en UNA consulta para todos (`obtener_items`).
"""
from datetime import timedelta

from django.contrib.auth import get_user_model

from apps.auditoria.fabrica import auditoria_servicio
from apps.catalogo.aplicacion.servicios import CatalogoServicioAplicacion
from apps.circulacion.aplicacion.servicios import PrestamoServicioAplicacion
from apps.circulacion.infraestructura.repositorio_django import PrestamoRepositorioImpl
from apps.reportes.dominio.fuentes import FilaDanio, FilaPrestamo, IFuenteDeReportes

ITEM_NO_ENCONTRADO = "(ítem no encontrado)"
VENTANA_DANIO = timedelta(hours=1)    # el daño se registra al recibir el ítem
MARGEN_DANIO = timedelta(minutes=1)   # por si la devolución se guarda un instante después


class FuenteDeReportesDjango(IFuenteDeReportes):
    def __init__(self, prestamos=None, catalogo=None):
        # Para leer solo hace falta el repositorio: no se arman Reservas, Políticas, etc.
        self._prestamos = prestamos or PrestamoServicioAplicacion(PrestamoRepositorioImpl())
        self._catalogo = catalogo or CatalogoServicioAplicacion()

    def prestamos_del_periodo(self, inicio, fin):
        return [
            FilaPrestamo(
                id=p.id, item_id=p.item_id, solicitante_id=p.solicitante_id, estado=p.estado,
                fecha_entrega=p.fecha_entrega, fecha_vencimiento=p.fecha_vencimiento,
                fecha_devolucion_real=p.fecha_devolucion_real,
            )
            for p in self._prestamos.entregados_entre(inicio, fin)
        ]

    def items_de_prestamos(self, prestamo_ids):
        return self._prestamos.items_de_prestamos(prestamo_ids)

    def danios_del_periodo(self, inicio, fin):
        registros = [
            r for r in auditoria_servicio().buscar({
                "accion": "ITEM_DANIADO",
                "desde": inicio.isoformat(),
                "hasta": fin.isoformat(),
            })
            if r.entidad != "CasoPerdida"   # las pérdidas ya salen de Gestión de Pérdidas
        ]
        responsables = self._quien_lo_devolvio(registros)
        return [
            FilaDanio(fecha=r.fecha_hora, entidad=r.entidad, entidad_id=r.entidad_id, motivo=r.motivo,
                      solicitante_id=responsables.get(r.pk))
            for r in registros
        ]

    def _quien_lo_devolvio(self, registros):
        """{registro_id: solicitante_id} para los daños registrados al recibir una devolución.

        La auditoría no guarda el préstamo, así que se busca la devolución de ese ítem ocurrida
        hasta 1 hora antes del registro. Si el daño se marcó a mano desde el catálogo (sin una
        devolución cerca), no se culpa a nadie. Se resuelve con UNA consulta para todos los daños.
        """
        de_items = [r for r in registros if r.entidad == "Item"]
        if not de_items:
            return {}
        devueltos = self._prestamos.devueltos_entre(
            {r.entidad_id for r in de_items},
            min(r.fecha_hora for r in de_items) - VENTANA_DANIO,
            max(r.fecha_hora for r in de_items) + MARGEN_DANIO,
        )
        responsables = {}
        for r in de_items:
            candidatos = [
                p for p in devueltos
                if p.item_id == r.entidad_id
                and r.fecha_hora - VENTANA_DANIO <= p.fecha_devolucion_real <= r.fecha_hora + MARGEN_DANIO
            ]
            if candidatos:   # la devolución más cercana al registro del daño
                responsables[r.pk] = max(candidatos, key=lambda p: p.fecha_devolucion_real).solicitante_id
        return responsables

    def nombres_de_cuentas(self, ids):
        ids = {i for i in ids if i}
        if not ids:
            return {}
        cuentas = get_user_model().objects.filter(pk__in=ids)
        return {c.pk: c.nombres for c in cuentas}

    def datos_de_items(self, ids):
        ids = {i for i in ids if i}
        encontrados = self._catalogo.obtener_items(ids)
        datos = {}
        for item_id in ids:
            item = encontrados.get(item_id)
            if item is None:   # ítem borrado: el reporte sigue, mostrando solo el id
                datos[item_id] = (str(item_id)[:8], ITEM_NO_ENCONTRADO, "—")
            else:
                datos[item_id] = (item.codigo, item.nombre, item.categoria_nombre)
        return datos
