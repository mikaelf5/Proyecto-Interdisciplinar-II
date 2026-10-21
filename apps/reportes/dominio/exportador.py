from abc import ABC, abstractmethod

EXCEL = "excel"
PDF = "pdf"
FORMATOS = (EXCEL, PDF)
CONTENT_TYPES = {
    EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    PDF: "application/pdf",
}
EXTENSIONES = {EXCEL: "xlsx", PDF: "pdf"}


class IExportador(ABC):
    @abstractmethod
    def exportar(self, datos, formato) -> bytes: ...