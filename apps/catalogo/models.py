"""
Contexto: Catálogo e Inventario (Supporting).

- Categoria: tipo de ítem (Libros, Equipos...) y qué atributos deben tener sus ítems.
- Item: cada objeto físico que se presta.
- CondicionFisica: cómo estaba el ítem al entregarlo o devolverlo.

Referencias:
- Dentro del contexto (Item → Categoria, CondicionFisica → Item): ForeignKey.
- Hacia otros contextos (Préstamo, Personal): UUID sin FK.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.choices import EstadoItem, MomentoRegistro
from apps.common.models import BaseModel

from .validators import validar_atributos, validar_definicion


class Categoria(BaseModel):
    nombre = models.CharField(max_length=100, unique=True)
    es_especial = models.BooleanField(
        "es especial",
        default=False,
        help_text="Los ítems de categorías especiales requieren aprobación de supervisor.",
    )
    definicion_atributos = models.JSONField(
        "definición de atributos",
        default=dict,
        blank=True,
        help_text='Ejemplo: {"autor": {"tipo": "texto", "requerido": true}}',
    )

    class Meta:
        verbose_name = "categoría"
        verbose_name_plural = "categorías"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def clean(self):
        super().clean()
        validar_definicion(self.definicion_atributos)


class Item(BaseModel):
    # Transiciones de estado permitidas: estado actual → estados a los que puede pasar
    TRANSICIONES = {
        EstadoItem.DISPONIBLE: {EstadoItem.PRESTADO, EstadoItem.MANTENIMIENTO, EstadoItem.BAJA},
        EstadoItem.PRESTADO: {EstadoItem.DISPONIBLE, EstadoItem.MANTENIMIENTO, EstadoItem.BAJA},
        EstadoItem.MANTENIMIENTO: {EstadoItem.DISPONIBLE, EstadoItem.BAJA},
        EstadoItem.BAJA: set(),  # estado final: un ítem dado de baja ya no vuelve
    }

    codigo = models.CharField("código", max_length=50, unique=True)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="items")
    atributos = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=20, choices=EstadoItem.choices, default=EstadoItem.DISPONIBLE)
    motivo_fuera_servicio = models.CharField("motivo fuera de servicio", max_length=255, blank=True)

    class Meta:
        verbose_name = "ítem"
        verbose_name_plural = "ítems"
        ordering = ["codigo"]

    def __str__(self):
        return f"{self.codigo} ({self.categoria})"

    def clean(self):
        super().clean()
        if self.categoria_id:
            validar_atributos(self.atributos, self.categoria.definicion_atributos)

    # ---------- Métodos del dominio ----------
    def cambiar_estado(self, nuevo, motivo=""):
        """Cambia el estado solo si la transición está permitida."""
        if nuevo not in self.TRANSICIONES[self.estado]:
            raise ValidationError(
                f"No se puede pasar de {self.get_estado_display()} a {EstadoItem(nuevo).label}."
            )
        self.estado = nuevo
        # Si vuelve a estar disponible o prestado, ya no está fuera de servicio
        if nuevo in (EstadoItem.DISPONIBLE, EstadoItem.PRESTADO):
            self.motivo_fuera_servicio = ""
        elif motivo:
            self.motivo_fuera_servicio = motivo
        self.save(update_fields=["estado", "motivo_fuera_servicio"])

    def marcar_daniado(self, motivo):
        """El ítem está dañado: pasa a MANTENIMIENTO con su motivo."""
        if not motivo:
            raise ValidationError("Indica el motivo del daño.")
        self.cambiar_estado(EstadoItem.MANTENIMIENTO, motivo)

    def dar_de_baja(self, motivo):
        """Retira el ítem definitivamente del inventario."""
        if not motivo:
            raise ValidationError("Indica el motivo de la baja.")
        self.cambiar_estado(EstadoItem.BAJA, motivo)

    @property
    def esta_disponible(self):
        return self.estado == EstadoItem.DISPONIBLE


class CondicionFisica(BaseModel):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="condiciones")
    prestamo_id = models.UUIDField("préstamo", db_index=True)       # contexto Circulación
    responsable_id = models.UUIDField("responsable", db_index=True)  # contexto Identidad (Personal)
    momento = models.CharField(max_length=20, choices=MomentoRegistro.choices)
    fecha = models.DateField()
    foto = models.CharField(max_length=500, blank=True, help_text="Ruta o URL de la foto.")
    descripcion = models.TextField("descripción")

    class Meta:
        verbose_name = "condición física"
        verbose_name_plural = "condiciones físicas"
        ordering = ["-fecha"]
        constraints = [
            # Por cada préstamo solo hay un registro de ENTREGA y uno de DEVOLUCIÓN
            models.UniqueConstraint(
                fields=["prestamo_id", "momento"],
                name="condicion_unica_por_prestamo_y_momento",
            ),
        ]

    def __str__(self):
        return f"{self.item.codigo} · {self.get_momento_display()} · {self.fecha}"
