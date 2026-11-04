"""DTOs: datos simples que entran a los casos de uso.

El servicio no recibe el `request` ni el formulario de Django, solo estos
objetos. Así se puede llamar igual desde una vista, un comando o una prueba.
"""
from dataclasses import dataclass, field


@dataclass
class PerfilSolicitanteDTO:
    tipo: str = ""
    cui: str = ""
    habilitado_institucional: bool = False
    acta_aceptada: bool = False


@dataclass
class RegistroCuentaDTO:
    nombres: str
    dni: str
    correo: str
    password: str
    celular: str = ""
    direccion: str = ""
    roles: list = field(default_factory=list)
    consentimiento_aceptado: bool = False
    perfil: PerfilSolicitanteDTO = None   # obligatorio si roles incluye SOLICITANTE


@dataclass
class SolicitudRegistroDTO:
    """Lo que llena la persona en el formulario público de registro."""
    nombres: str
    dni: str
    correo: str
    password: str
    celular: str
    direccion: str
    tipo: str
    tipo_documento: str
    documento: object            # archivo subido (UploadedFile)
    cui: str = ""
    acta_aceptada: bool = False
    consentimiento_aceptado: bool = False


@dataclass
class AprobacionRegistroDTO:
    """Lo que decide el administrador al aprobar."""
    roles: list = field(default_factory=list)
    tipo: str = ""               # puede corregir el tipo que declaró la persona
