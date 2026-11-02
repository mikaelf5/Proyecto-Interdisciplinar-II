"""Backend de correo para DESARROLLO: imprime el correo legible en la consola.

El backend de consola de Django imprime el mensaje MIME tal cual; con tildes
(ñ, é) el cuerpo sale en "quoted-printable" y el enlace de recuperación queda
partido con "=" al final de cada línea, imposible de copiar en la demo.
Este backend imprime los encabezados y el cuerpo como texto normal.
"""
from django.core.mail.backends.console import EmailBackend as ConsolaDjango


class EmailBackend(ConsolaDjango):
    def write_message(self, message):
        self.stream.write(
            "\n" + "=" * 70 + "\n"
            f"De:     {message.from_email}\n"
            f"Para:   {', '.join(message.to)}\n"
            f"Asunto: {message.subject}\n"
            + "-" * 70 + "\n"
            f"{message.body}\n"
            + "=" * 70 + "\n"
        )
