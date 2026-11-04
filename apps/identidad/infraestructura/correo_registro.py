"""Adaptador de correo para el resultado del registro (implementa ICorreoRegistroPuerto).

Usa el EMAIL_BACKEND configurado: en desarrollo el correo sale en la consola.
"""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.common.choices import RolSistema
from apps.identidad.dominio.puertos import ICorreoRegistroPuerto


class CorreoRegistroDjango(ICorreoRegistroPuerto):
    def __init__(self, url_login=""):
        self._url_login = url_login

    def avisar_aprobacion(self, solicitud, roles):
        self._enviar(
            solicitud, "Tu solicitud de registro fue aprobada",
            "identidad/correo/registro_aprobado.txt",
            {"roles": [RolSistema(r).label for r in roles]},
        )

    def avisar_rechazo(self, solicitud):
        self._enviar(
            solicitud, "Tu solicitud de registro fue rechazada",
            "identidad/correo/registro_rechazado.txt", {},
        )

    def _enviar(self, solicitud, asunto, plantilla, extra):
        cuerpo = render_to_string(plantilla, {
            "solicitud": solicitud, "url_login": self._url_login, **extra,
        })
        send_mail(asunto, cuerpo, settings.DEFAULT_FROM_EMAIL, [solicitud.correo])
