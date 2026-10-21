"""Ayudantes para dejar constancia en la bitácora desde las vistas."""
import uuid

from .models import RegistroAuditoria


def actor_id_de(request):
    """UUID de quien hace la acción (la cuenta con sesión iniciada).

    Con la `Cuenta` del equipo (pk UUID) devuelve su id tal cual. Si la
    cuenta tuviera un pk que no es UUID (ej. el User por defecto de Django
    en una prueba local), deriva un UUID estable a partir de él.
    """
    pk = request.user.pk
    if isinstance(pk, uuid.UUID):
        return pk
    try:
        return uuid.UUID(str(pk))
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_OID, f"cuenta-{pk}")


def auditar(request, accion, entidad, entidad_id, motivo=""):
    """Crea un RegistroAuditoria con la cuenta actual como actor."""
    return RegistroAuditoria.registrar(
        actor_id=actor_id_de(request),
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        motivo=motivo,
    )
