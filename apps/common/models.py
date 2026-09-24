import uuid

from django.db import models


class BaseModel(models.Model):
    """Base de todos los modelos: PK UUID + timestamps."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
