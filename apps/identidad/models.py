# Django busca los modelos en <app>/models.py: los reexportamos desde la capa de dominio.
from .dominio.models import Cuenta, CuentaManager, PerfilSolicitante  # noqa: F401
