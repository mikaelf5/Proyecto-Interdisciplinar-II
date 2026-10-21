"""Puerto (interfaz) para hashear contraseñas.

El dominio solo conoce este contrato. La implementación concreta
(DjangoPasswordHasher) vive en la capa de infraestructura, así el dominio
no depende de Django para algo tan delicado como las contraseñas (RNF-1).
"""
from abc import ABC, abstractmethod


class IPasswordHasher(ABC):
    @abstractmethod
    def hashear(self, password_plano: str) -> str: ...

    @abstractmethod
    def verificar(self, password_plano: str, password_hash: str) -> bool: ...
