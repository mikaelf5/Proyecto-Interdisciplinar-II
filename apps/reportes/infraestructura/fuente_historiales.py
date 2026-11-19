"""Adaptador de IFuenteDeHistoriales: pide los datos a los servicios de los otros módulos.

Hereda de FuenteDeReportesDjango para reutilizar préstamos, nombres, ítems y la regla de
"quién devolvió el ítem dañado". Nada aquí modifica datos.
"""
from apps.auditoria.fabrica import auditoria_servicio
from apps.catalogo.aplicacion.dtos import FiltrosItem
from apps.common.choices import RolSistema
from apps.reportes.dominio.fuentes import (
    FichaItem, FichaPersona, FilaDanio, FilaPrestamo, IFuenteDeHistoriales,
)

from .fuente_datos import FuenteDeReportesDjango

ROLES = dict(RolSistema.choices)


def _fila(p):
    return FilaPrestamo(
        id=p.id, item_id=p.item_id, solicitante_id=p.solicitante_id, estado=p.estado,
        fecha_entrega=p.fecha_entrega, fecha_vencimiento=p.fecha_vencimiento,
        fecha_devolucion_real=p.fecha_devolucion_real,
    )


def _ficha_item(item):
    return FichaItem(
        id=item.id, codigo=item.codigo, nombre=item.nombre, categoria=item.categoria_nombre,
        estado=item.estado_display, motivo_fuera_servicio=item.motivo_fuera_servicio or "",
    )


class FuenteDeHistorialesDjango(FuenteDeReportesDjango, IFuenteDeHistoriales):
    def __init__(self, prestamos=None, catalogo=None, cuentas=None, sanciones=None, perdidas=None):
        super().__init__(prestamos, catalogo)
        self._cuentas_srv = cuentas
        self._sanciones_srv = sanciones
        self._perdidas_srv = perdidas

    # Los servicios se arman al primer uso: así no se cargan módulos que no hacen falta.
    @property
    def _cuentas(self):
        if self._cuentas_srv is None:
            from apps.identidad.fabrica import cuenta_servicio
            self._cuentas_srv = cuenta_servicio()
        return self._cuentas_srv

    @property
    def _sanciones(self):
        if self._sanciones_srv is None:
            from apps.sanciones.fabrica import sancion_servicio
            self._sanciones_srv = sancion_servicio()
        return self._sanciones_srv

    @property
    def _perdidas(self):
        if self._perdidas_srv is None:
            from apps.perdidas.fabrica import caso_perdida_servicio
            self._perdidas_srv = caso_perdida_servicio()
        return self._perdidas_srv

    # --- personas ---
    def _ficha(self, cuenta):
        perfil = self._cuentas.perfil_de(cuenta.pk)
        return FichaPersona(
            id=cuenta.pk, nombres=cuenta.nombres, dni=cuenta.dni, correo=cuenta.correo,
            roles=tuple(ROLES.get(r, r) for r in cuenta.roles),
            tipo=perfil.get_tipo_display() if perfil else "",
            cui=(perfil.cui or "") if perfil else "",
            etiqueta=perfil.get_etiqueta_display() if perfil and perfil.etiqueta else "",
        )

    def persona(self, cuenta_id):
        try:
            cuenta = self._cuentas.obtener_cuenta(cuenta_id)
        except Exception:   # CuentaNoEncontrada
            return None
        return self._ficha(cuenta)

    def buscar_personas(self, q):
        return [self._ficha(c) for c in self._cuentas.listar_cuentas(q)]

    def dni_de_cuentas(self, ids):
        from django.contrib.auth import get_user_model   # API pública de Django
        ids = {i for i in ids if i}
        if not ids:
            return {}
        return dict(get_user_model().objects.filter(pk__in=ids).values_list("pk", "dni"))

    # --- ítems ---
    def item(self, item_id):
        item = self._catalogo.obtener_items({item_id}).get(item_id)
        return _ficha_item(item) if item else None

    def buscar_items(self, q):
        return [_ficha_item(i) for i in self._catalogo.buscar_items(FiltrosItem(texto=q))]

    # --- préstamos, sanciones, pérdidas y daños ---
    def prestamos_de_persona(self, cuenta_id):
        return [_fila(p) for p in self._prestamos.historial_de(cuenta_id)]

    def prestamos_de_item(self, item_id):
        return [_fila(p) for p in self._prestamos.historial_de_item(item_id)]

    def sanciones_de(self, cuenta_id):
        return self._sanciones.de_solicitante(cuenta_id)

    def perdidas_de_persona(self, cuenta_id):
        return self._perdidas.de_solicitante(cuenta_id)

    def perdidas_de_prestamos(self, prestamo_ids):
        return self._perdidas.de_prestamos(prestamo_ids)

    def danios_de_item(self, item_id):
        registros = [
            r for r in auditoria_servicio().buscar({"accion": "ITEM_DANIADO", "entidad": "Item"})
            if r.entidad_id == item_id
        ]
        responsables = self._quien_lo_devolvio(registros)
        return [
            FilaDanio(fecha=r.fecha_hora, entidad=r.entidad, entidad_id=r.entidad_id, motivo=r.motivo,
                      solicitante_id=responsables.get(r.pk))
            for r in registros
        ]
