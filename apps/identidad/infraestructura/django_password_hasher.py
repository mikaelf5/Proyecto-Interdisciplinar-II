"""Adaptador: implementa IPasswordHasher con el sistema de hash de Django.

Django usa PBKDF2-SHA256 con sal aleatoria e iteraciones (configurable en
PASSWORD_HASHERS), así cumplimos RNF-1 sin inventar criptografía propia.
"""
from django.contrib.auth.hashers import check_password, make_password

from apps.identidad.dominio.hasher import IPasswordHasher


class DjangoPasswordHasher(IPasswordHasher):
    def hashear(self, password_plano: str) -> str:
        return make_password(password_plano)

    def verificar(self, password_plano: str, password_hash: str) -> bool:
        return check_password(password_plano, password_hash)
