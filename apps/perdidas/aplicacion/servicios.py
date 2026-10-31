from django.core.exceptions import ValidationError
from django.db import transaction

from apps.auditoria.models import TipoAccion
from apps.perdidas.dominio.repositorio import ICasoPerdidaRepositorio


class CasoPerdidaServicioAplicacion:
    """Casos de uso de Gestión de Pérdidas.

    Al registrar un caso (RF-G3) coordina otros dos contextos, siempre por sus
    servicios de aplicación (nunca por sus modelos):
      - Circulación: `cerrar_por_perdida(prestamo_id)` -> el préstamo queda CERRADO_POR_PERDIDA.
      - Catálogo: `dar_de_baja_item(item_id, motivo)` -> el ítem sale del inventario.
    Si alguno falla, no se guarda nada (transacción).
    """

    def __init__(self, repositorio: ICasoPerdidaRepositorio, auditoria,
                 circulacion=None, catalogo=None):
        self._repo = repositorio
        self._auditoria = auditoria
        self._circulacion = circulacion   # IPrestamoServicio (Marving)
        self._catalogo = catalogo         # ICatalogoServicio (Micaela)

    def listar(self, estado="", q=""):
        return self._repo.buscar(estado, q)

    def contar_abiertos(self):
        return self._repo.contar_abiertos()

    def obtener(self, pk):
        return self._repo.obtener(pk)

    def por_periodo(self, inicio, fin):
        return list(self._repo.por_periodo(inicio, fin))

    def registrar(self, caso, actor_id):
        """Registra la pérdida, cierra el préstamo y da de baja el ítem.

        Lanza ValidationError si el préstamo no existe o no está abierto, o si
        el solicitante no es el del préstamo (no queda nada a medias).
        """
        with transaction.atomic():
            prestamo = None
            if self._circulacion is not None:
                prestamo = self._circulacion.cerrar_por_perdida(caso.prestamo_id)
                if not caso.solicitante_id:
                    caso.solicitante_id = prestamo.solicitante_id
                elif caso.solicitante_id != prestamo.solicitante_id:
                    raise ValidationError("El solicitante no coincide con el del préstamo.")
            elif not caso.solicitante_id:
                raise ValidationError("Indica el solicitante responsable.")

            self._repo.guardar(caso)
            motivo = caso.observaciones or "sin observaciones"
            self._auditoria.registrar(
                actor_id, TipoAccion.ITEM_DANIADO, "CasoPerdida", caso.pk,
                f"Pérdida registrada: {motivo}",
            )
            if prestamo is not None:
                self._auditoria.registrar(
                    actor_id, TipoAccion.CAMBIO_ESTADO, "Prestamo", prestamo.pk,
                    "Préstamo cerrado por pérdida",
                )
                self._dar_de_baja(prestamo.item_id, motivo, actor_id)
        return caso

    def _dar_de_baja(self, item_id, motivo, actor_id):
        if self._catalogo is None:
            return
        if self._catalogo.obtener_item(item_id).estado == "BAJA":
            return  # ya estaba dado de baja: no hay nada más que hacer
        self._catalogo.dar_de_baja_item(item_id, f"Pérdida: {motivo}"[:255])
        self._auditoria.registrar(
            actor_id, TipoAccion.CAMBIO_ESTADO, "Item", item_id,
            f"Dado de baja por pérdida: {motivo}",
        )

    def actualizar(self, caso):
        return self._repo.guardar(caso)

    def cerrar(self, caso, actor_id):
        """Devuelve False si ya estaba cerrado."""
        if caso.cerrado:
            return False
        caso.cerrar_prestamo()
        self._auditoria.registrar(
            actor_id, TipoAccion.CAMBIO_ESTADO, "CasoPerdida", caso.pk,
            "Caso de pérdida cerrado",
        )
        return True

    def eliminar(self, caso, actor_id):
        pk, prestamo = caso.pk, caso.prestamo_id
        self._repo.eliminar(caso)
        self._auditoria.registrar(
            actor_id, TipoAccion.CAMBIO_ESTADO, "CasoPerdida", pk,
            f"Caso de pérdida eliminado (préstamo {prestamo})",
        )
