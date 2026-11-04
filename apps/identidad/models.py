# Django busca los modelos en <app>/models.py: los reexportamos desde la capa de dominio.
from .dominio.models import (  # noqa: F401
    Cuenta,
    CuentaManager,
    EstadoRegistro,
    PerfilSolicitante,
    SolicitudRegistro,
    TipoDocumentoAcreditacion,
)
