from django.db import models
from apps.common.models import BaseModel

class TipoReporte(models.TextChoices):
    ITEMS_MAS_PRESTADOS = "ITEMS_MAS_PRESTADOS", "Ítems más prestados"
    USUARIOS_MAS_ACTIVOS = "USUARIOS_MAS_ACTIVOS", "Usuarios más activos"
    TASA_DEVOLUCION_A_TIEMPO = "TASA_DEVOLUCION_A_TIEMPO", "Tasa de devolución a tiempo"
    ITEMS_PERDIDOS_DANIADOS = "ITEMS_PERDIDOS_DANIADOS", "Ítems perdidos o dañados"
    SANCIONES_POR_PERIODO = "SANCIONES_POR_PERIODO", "Sanciones por periodo"


class FormatoExport(models.TextChoices):
    EXCEL = "EXCEL", "Excel"
    PDF = "PDF", "PDF"


class Reporte(BaseModel):
    tipo = models.CharField(max_length=40, choices=TipoReporte.choices)
    periodo_inicio = models.DateField()
    periodo_fin = models.DateField()
    generado_por_id = models.UUIDField(
        help_text="Personal (Administrador) que generó el reporte (contexto Identidad)."
    )

    class Meta:
        verbose_name = "Reporte"
        verbose_name_plural = "Reportes"
        ordering = ["-creado_en"]

    def __str__(self):
        return f"{self.get_tipo_display()} ({self.periodo_inicio} – {self.periodo_fin})"

    def exportar(self, formato: str):
        """
        Stub (fase de lógica de negocio). Deberá generar el archivo
        (Excel con openpyxl/pandas, PDF con reportlab/weasyprint) según
        `formato` y devolver la ruta o el binario resultante.
        """
        if formato not in FormatoExport.values:
            raise ValueError(f"Formato no soportado: {formato}")
        raise NotImplementedError("Exportación pendiente de implementar en la fase de lógica de negocio.")
