"""
Capa de INFRAESTRUCTURA — adaptador EmisorCorreoSMTP (PDF: django.core.mail).

En desarrollo conviene que settings tenga:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
así los correos se imprimen en la consola de runserver en vez de enviarse.
"""
import logging

from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from ..dominio.puertos import IEmisorNotificacion

log = logging.getLogger(__name__)


class EmisorCorreoSMTP(IEmisorNotificacion):
    asunto_por_tipo = {
        "RECORDATORIO_VENCIMIENTO": "Recordatorio: tu préstamo vence pronto",
        "ALERTA_ATRASO": "Alerta: tienes un préstamo atrasado",
        "DISPONIBILIDAD_RESERVA": "Tu reserva ya está disponible",
        "INVENTARIO_BAJO": "Aviso de inventario bajo",
        "ITEM_DANIADO": "Aviso: ítem dañado",
    }

    def _correo_de(self, destinatario_id):
        # El destinatario es una Cuenta (AUTH_USER_MODEL). Se usa la API pública de
        # Django get_user_model() para no importar los modelos del contexto Identidad.
        cuenta = get_user_model().objects.filter(pk=destinatario_id).first()
        return getattr(cuenta, "correo", None)

    def enviar(self, notificacion):
        correo = self._correo_de(notificacion.destinatario_id)
        if not correo:
            log.warning("Notificación %s sin correo de destino.", notificacion.id)
            return False
        try:
            send_mail(
                subject=self.asunto_por_tipo.get(notificacion.tipo, "Sistema de Préstamos"),
                message=notificacion.mensaje,
                from_email=None,  # usa DEFAULT_FROM_EMAIL
                recipient_list=[correo],
            )
            return True
        except Exception as e:  # sin servidor SMTP: queda registrada pero sin enviar
            log.warning("No se pudo enviar la notificación %s por correo: %s", notificacion.id, e)
            return False
