"""Historial de una persona y de un ítem (solo consulta, nunca modifica otros módulos).

Usan las mismas reglas que los reportes (`_clasificar`, `_duracion`), para que "a tiempo"
y "con atraso" signifiquen lo mismo en todas las pantallas.
"""
from collections import Counter

from django.utils import timezone

from apps.auditoria.models import TipoAccion
from apps.reportes.dominio.datos import DatosReporte, Grafico, Seccion, Soles
from apps.reportes.dominio.exportador import CONTENT_TYPES, EXTENSIONES, FORMATOS
from apps.sanciones.servicios import estado_de, fecha_fin

from .servicios import _clasificar, _corto, _duracion

RESULTADOS = {
    "a_tiempo": "Devuelto a tiempo",
    "con_atraso": "Con atraso",
    "en_curso": "En curso",
    "perdido": "Cerrado por pérdida",
}


class HistorialNoEncontrado(Exception):
    """La persona o el ítem no existen."""


def _resultado(p, ahora):
    """Texto del resultado de un préstamo: "Con atraso (40 min)", "En curso"..."""
    clase = _clasificar(p, ahora)
    if clase == "con_atraso":
        if p.fecha_devolucion_real:
            return f"Devuelto con atraso ({_duracion(p.fecha_devolucion_real - p.fecha_vencimiento)})"
        return f"Sin devolver (atrasado {_duracion(ahora - p.fecha_vencimiento)})"
    return RESULTADOS[clase]


def _grafico_prestamos(cuenta):
    return Grafico(
        "doughnut", "Resultado de los préstamos",
        ["A tiempo", "Con atraso", "En curso", "Cerrados por pérdida"],
        [cuenta["a_tiempo"], cuenta["con_atraso"], cuenta["en_curso"], cuenta["perdido"]],
    )


def _sello(datos, ahora, nombre):
    datos.generado_en = ahora
    datos.generado_por = nombre
    return datos


class HistorialServicio:
    def __init__(self, fuente, exportador, auditoria=None):
        self._fuente = fuente          # IFuenteDeHistoriales
        self._exportador = exportador
        self._auditoria = auditoria

    # --- búsquedas ---
    def buscar_personas(self, q):
        q = (q or "").strip()
        return self._fuente.buscar_personas(q) if q else []

    def buscar_items(self, q):
        q = (q or "").strip()
        return self._fuente.buscar_items(q) if q else []

    def persona(self, cuenta_id):
        return self._fuente.persona(cuenta_id)

    # --- historial de una persona ---
    def de_persona(self, cuenta_id, ahora=None, pedido_por_id=None):
        ahora = ahora or timezone.now()
        persona = self._fuente.persona(cuenta_id)
        if persona is None or not persona.es_solicitante:
            # El historial es de quien pide prestado: el personal (admin, encargado...) no tiene.
            raise HistorialNoEncontrado("Solo hay historial de cuentas con rol Solicitante.")

        prestamos = self._fuente.prestamos_de_persona(cuenta_id)
        sanciones = self._fuente.sanciones_de(cuenta_id)
        perdidas = self._fuente.perdidas_de_persona(cuenta_id)

        ids_items = {p.item_id for p in prestamos}
        item_de_prestamo = self._fuente.items_de_prestamos({c.prestamo_id for c in perdidas})
        items = self._fuente.datos_de_items(ids_items | set(item_de_prestamo.values()))
        aplicadores = self._fuente.nombres_de_cuentas({s.aplicada_por_id for s in sanciones})

        def item_texto(item_id):
            codigo, nombre, _ = items.get(item_id, (_corto(item_id), "", ""))
            return f"{codigo} · {nombre}" if nombre else codigo

        cuenta = Counter(_clasificar(p, ahora) for p in prestamos)
        estados = [estado_de(s) for s in sanciones]

        filas_prestamos = [
            [p.fecha_entrega, p.fecha_vencimiento, p.fecha_devolucion_real, item_texto(p.item_id),
             _resultado(p, ahora)]
            for p in prestamos
        ]
        filas_sanciones = [
            [s.fecha_inicio, fecha_fin(s) or "sin plazo", s.get_tipo_display(), s.motivo,
             estado.capitalize(), aplicadores.get(s.aplicada_por_id, _corto(s.aplicada_por_id))]
            for s, estado in zip(sanciones, estados)
        ]
        filas_perdidas = [
            [c.fecha,
             item_texto(item_de_prestamo[c.prestamo_id]) if c.prestamo_id in item_de_prestamo
             else f"Préstamo {_corto(c.prestamo_id)}",
             c.observaciones or None,
             Soles(c.costo_estimado) if c.costo_estimado is not None else None,
             "Cerrado" if c.cerrado else "Abierto"]
            for c in perdidas
        ]

        detalles = [f"DNI {persona.dni}"]
        if persona.cui:
            detalles.append(f"CUI {persona.cui}")
        if persona.tipo:
            detalles.append(persona.tipo)
        detalles.append(persona.correo)
        if persona.etiqueta:
            detalles.append(f"Etiqueta: {persona.etiqueta}")

        datos = DatosReporte(
            titulo=f"Historial de {persona.nombres}",
            subtitulo=" · ".join(detalles),
            resumen=[
                ("Préstamos", len(prestamos)),
                ("Devueltos a tiempo", cuenta["a_tiempo"]),
                ("Con atraso", cuenta["con_atraso"]),
                ("En curso", cuenta["en_curso"]),
                ("Cerrados por pérdida", cuenta["perdido"]),
                ("Sanciones", len(sanciones)),
                ("Sanciones vigentes", estados.count("vigente")),
                ("Casos de pérdida", len(perdidas)),
            ],
            grafico=_grafico_prestamos(cuenta),
            secciones=[
                Seccion("Préstamos", ["Entrega", "Vencimiento", "Devolución", "Ítem", "Resultado"],
                        filas_prestamos, "No tiene préstamos."),
                Seccion("Sanciones", ["Desde", "Hasta", "Tipo", "Motivo", "Estado", "Aplicada por"],
                        filas_sanciones, "No tiene sanciones."),
                Seccion("Pérdidas", ["Fecha", "Ítem", "Detalle", "Costo estimado", "Caso"],
                        filas_perdidas, "No tiene casos de pérdida."),
            ],
        )
        return _sello(datos, ahora, self._nombre(pedido_por_id))

    # --- historial de un ítem ---
    def de_item(self, item_id, ahora=None, pedido_por_id=None):
        ahora = ahora or timezone.now()
        item = self._fuente.item(item_id)
        if item is None:
            raise HistorialNoEncontrado("El ítem no existe.")

        prestamos = self._fuente.prestamos_de_item(item_id)
        perdidas = self._fuente.perdidas_de_prestamos({p.id for p in prestamos})
        danios = self._fuente.danios_de_item(item_id)
        personas = {p.solicitante_id for p in prestamos} | {c.solicitante_id for c in perdidas} \
            | {d.solicitante_id for d in danios if d.solicitante_id}
        nombres = self._fuente.nombres_de_cuentas(personas)
        dnis = self._fuente.dni_de_cuentas(personas)

        def nombre(cuenta_id):
            return nombres.get(cuenta_id, _corto(cuenta_id)) if cuenta_id else None

        cuenta = Counter(_clasificar(p, ahora) for p in prestamos)
        filas_prestamos = [
            [p.fecha_entrega, p.fecha_vencimiento, p.fecha_devolucion_real, nombre(p.solicitante_id),
             dnis.get(p.solicitante_id), _resultado(p, ahora)]
            for p in prestamos
        ]
        eventos = [
            (c.fecha, [c.fecha, "Pérdida", nombre(c.solicitante_id), dnis.get(c.solicitante_id),
                       c.observaciones or None])
            for c in perdidas
        ] + [
            (timezone.localtime(d.fecha).date(),
             [timezone.localtime(d.fecha).date(), "Daño", nombre(d.solicitante_id),
              dnis.get(d.solicitante_id), d.motivo or None])
            for d in danios
        ]
        filas_eventos = [fila for _, fila in sorted(eventos, key=lambda e: e[0], reverse=True)]

        subtitulo = f"{item.categoria} · Estado actual: {item.estado}"
        if item.motivo_fuera_servicio:
            subtitulo += f" ({item.motivo_fuera_servicio})"
        datos = DatosReporte(
            titulo=f"Historial del ítem {item.codigo} · {item.nombre}",
            subtitulo=subtitulo,
            resumen=[
                ("Estado actual", item.estado),
                ("Préstamos", len(prestamos)),
                ("Personas distintas", len({p.solicitante_id for p in prestamos})),
                ("Devueltos a tiempo", cuenta["a_tiempo"]),
                ("Con atraso", cuenta["con_atraso"]),
                ("Pérdidas", len(perdidas)),
                ("Daños registrados", len(danios)),
            ],
            grafico=_grafico_prestamos(cuenta),
            secciones=[
                Seccion("Préstamos", ["Entrega", "Vencimiento", "Devolución", "Solicitante", "DNI",
                                      "Resultado"], filas_prestamos, "Este ítem no se ha prestado."),
                Seccion("Pérdidas y daños", ["Fecha", "Tipo", "Persona", "DNI", "Detalle"],
                        filas_eventos, "No tiene pérdidas ni daños registrados."),
            ],
        )
        return _sello(datos, ahora, self._nombre(pedido_por_id))

    # --- descargas ---
    def exportar_persona(self, cuenta_id, formato, actor_id=None):
        datos = self.de_persona(cuenta_id, pedido_por_id=actor_id)
        dni = self._fuente.persona(cuenta_id).dni
        return self._exportar(datos, formato, actor_id, "Cuenta", cuenta_id, f"historial_persona_{dni}")

    def exportar_item(self, item_id, formato, actor_id=None):
        datos = self.de_item(item_id, pedido_por_id=actor_id)
        codigo = self._fuente.item(item_id).codigo
        return self._exportar(datos, formato, actor_id, "Item", item_id, f"historial_item_{codigo}")

    def _exportar(self, datos, formato, actor_id, entidad, entidad_id, base):
        if formato not in FORMATOS:
            raise ValueError(f"Formato no soportado: {formato}")
        contenido = self._exportador.exportar(datos, formato)
        if self._auditoria and actor_id:
            self._auditoria.registrar(
                actor_id, TipoAccion.EXPORTACION_REPORTE, entidad, entidad_id,
                f"{datos.titulo} en {EXTENSIONES[formato].upper()}",
            )
        nombre = f"{base}_{timezone.localdate():%Y%m%d}.{EXTENSIONES[formato]}"
        return contenido, CONTENT_TYPES[formato], nombre.replace(" ", "_")

    def _nombre(self, cuenta_id):
        if not cuenta_id:
            return ""
        return self._fuente.nombres_de_cuentas({cuenta_id}).get(cuenta_id, _corto(cuenta_id))
