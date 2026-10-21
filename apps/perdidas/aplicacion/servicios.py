from apps.auditoria.models import TipoAccion
from apps.perdidas.dominio.repositorio import ICasoPerdidaRepositorio


class CasoPerdidaServicioAplicacion:
    def __init__(self, repositorio: ICasoPerdidaRepositorio, auditoria):
        self._repo = repositorio
        self._auditoria = auditoria

    def listar(self, estado="", q=""):
        return self._repo.buscar(estado, q)

    def contar_abiertos(self):
        return self._repo.contar_abiertos()

    def obtener(self, pk):
        return self._repo.obtener(pk)

    def por_periodo(self, inicio, fin):
        return list(self._repo.por_periodo(inicio, fin))

    def registrar(self, caso, actor_id):
        self._repo.guardar(caso)
        self._auditoria.registrar(
            actor_id, TipoAccion.ITEM_DANIADO, "CasoPerdida", caso.pk,
            f"Pérdida registrada: {caso.observaciones or 'sin observaciones'}",
        )
        return caso

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