from apps.perdidas.fabrica import caso_perdida_servicio
from apps.sanciones.fabrica import sancion_servicio

from .aplicacion.servicios import ReporteServicioAplicacion
from .infraestructura.exportador_excel_pdf import ExportadorExcelPDF
from .infraestructura.repositorio_django import ReporteRepositorioImpl


def reporte_servicio():
    return ReporteServicioAplicacion(
        ReporteRepositorioImpl(),
        sancion_servicio(),
        caso_perdida_servicio(),
        ExportadorExcelPDF(),
    )