"""Genera el archivo del reporte: Excel con openpyxl, PDF con reportlab.

- Excel: cada celda lleva su valor real (número, fecha, porcentaje), con formato de celda.
- PDF: TODO texto se escapa antes de dárselo a reportlab, porque `Paragraph` interpreta
  etiquetas (<b>, <font>...). Sin escapar, un motivo como "Cable <roto>" perdía texto y
  uno como "usa <b>negrita" hacía fallar la descarga.
- Ambos llevan el sello "Generado el ... por ..." y el aviso de datos personales.
"""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.reportes.dominio.datos import AVISO_DATOS_PERSONALES, Porcentaje, Soles, como_texto
from apps.reportes.dominio.exportador import EXCEL, IExportador

COLORES_GRAFICO = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2", "#64748b"]

FORMATO_FECHA = "DD/MM/YYYY"
FORMATO_FECHA_HORA = "DD/MM/YYYY HH:MM"
FORMATO_PORCENTAJE = "0.0%"
FORMATO_SOLES = '"S/" #,##0.00'


# ---------------------------------------------------------------------------
# Excel
# ---------------------------------------------------------------------------
def _celda_excel(celda, valor):
    """Escribe el valor con su tipo real y el formato que le corresponde."""
    if valor is None or valor == "":
        celda.value = "—"
    elif isinstance(valor, Porcentaje):
        if valor.fraccion is None:
            celda.value = "—"
        else:
            celda.value = valor.fraccion
            celda.number_format = FORMATO_PORCENTAJE
    elif isinstance(valor, Soles):
        celda.value = float(valor.monto)
        celda.number_format = FORMATO_SOLES
    elif isinstance(valor, datetime):
        # openpyxl no acepta fechas con zona horaria: se pasan a la hora de Lima.
        celda.value = timezone.localtime(valor).replace(tzinfo=None) if timezone.is_aware(valor) else valor
        celda.number_format = FORMATO_FECHA_HORA
    elif isinstance(valor, date):
        celda.value = valor
        celda.number_format = FORMATO_FECHA
    elif isinstance(valor, Decimal):
        celda.value = float(valor)
    else:
        celda.value = valor
    return celda


def _tabla_excel(ws, fila, columnas, filas):
    """Escribe cabecera y filas desde `fila`; devuelve la última fila usada."""
    cabecera = PatternFill("solid", fgColor="343A40")
    for col, nombre in enumerate(columnas, start=1):
        celda = ws.cell(row=fila, column=col, value=nombre)
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = cabecera
    for datos_fila in filas:
        fila += 1
        for col, valor in enumerate(datos_fila, start=1):
            _celda_excel(ws.cell(row=fila, column=col), valor).alignment = Alignment(
                wrap_text=True, vertical="top"
            )
    return fila


def a_excel(datos):
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws["A1"] = datos.titulo
    ws["A1"].font = Font(bold=True, size=14)
    ws["A2"] = datos.subtitulo
    ws["A3"] = datos.sello
    ws["A3"].font = Font(italic=True, color="666666")
    fila = 5
    for etiqueta, valor in datos.resumen:
        ws.cell(row=fila, column=1, value=etiqueta).font = Font(bold=True)
        _celda_excel(ws.cell(row=fila, column=2), valor).alignment = Alignment(horizontal="right")
        fila += 1
    fila += 1
    if datos.secciones:
        # Historiales: una tabla con título por sección (préstamos, sanciones, pérdidas...).
        for seccion in datos.secciones:
            ws.cell(row=fila, column=1, value=seccion.titulo).font = Font(bold=True, size=12)
            fila = _tabla_excel(ws, fila + 1, seccion.columnas, seccion.filas)
            if not seccion.filas:
                fila += 1
                ws.cell(row=fila, column=1, value=seccion.vacio).font = Font(italic=True, color="666666")
            fila += 2
        anchas = max(len(s.columnas) for s in datos.secciones)
    else:
        ws.freeze_panes = ws.cell(row=fila + 1, column=1)   # la cabecera queda fija al bajar
        fila = _tabla_excel(ws, fila, datos.columnas, datos.filas) + 2
        anchas = len(datos.columnas)
    ws.cell(row=fila, column=1, value=AVISO_DATOS_PERSONALES).font = Font(italic=True, color="666666")
    for col in range(1, max(anchas, 2) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 38 if col in (2, 3, 4) else 22
    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
def _p(valor, estilo):
    """Paragraph con el texto escapado: nunca se interpreta como etiqueta."""
    return Paragraph(escape(como_texto(valor)), estilo)


def _grafico_pdf(grafico, ancho):
    """Dibujo de reportlab para el gráfico del reporte (o None si no hay datos)."""
    if grafico is None or not grafico.valores or not any(grafico.valores):
        return None
    alto = 6 * cm
    dibujo = Drawing(ancho, alto + 0.8 * cm)
    dibujo.add(String(0, alto + 0.3 * cm, grafico.titulo, fontName="Helvetica-Bold", fontSize=10))
    if grafico.tipo == "doughnut":
        lado = alto - 0.4 * cm
        torta = Pie()
        torta.x, torta.y, torta.width, torta.height = 0.5 * cm, 0.2 * cm, lado, lado
        torta.data = [v or 0 for v in grafico.valores]
        torta.slices.strokeColor = colors.white
        torta.slices.strokeWidth = 1.5
        leyenda = Legend()
        leyenda.x, leyenda.y = lado + 1.5 * cm, alto - 0.8 * cm
        leyenda.fontName, leyenda.fontSize = "Helvetica", 8
        leyenda.alignment = "right"
        leyenda.columnMaximum = 10   # una sola columna
        pares = []
        for i, (etiqueta, valor) in enumerate(zip(grafico.etiquetas, grafico.valores)):
            color = colors.HexColor(COLORES_GRAFICO[i % len(COLORES_GRAFICO)])
            torta.slices[i].fillColor = color
            pares.append((color, f"{etiqueta}: {valor}"))
        leyenda.colorNamePairs = pares
        dibujo.add(torta)
        dibujo.add(leyenda)
    else:
        barras = HorizontalBarChart()
        etiquetas = [e[:32] for e in grafico.etiquetas][::-1]   # el mayor arriba
        barras.x, barras.y = 5.5 * cm, 0.2 * cm
        barras.width, barras.height = ancho - 7 * cm, alto - 0.4 * cm
        barras.data = [list(grafico.valores)[::-1]]
        barras.categoryAxis.categoryNames = etiquetas
        barras.categoryAxis.labels.fontName = "Helvetica"
        barras.categoryAxis.labels.fontSize = 7
        barras.valueAxis.valueMin = 0
        barras.valueAxis.labels.fontName = "Helvetica"
        barras.valueAxis.labels.fontSize = 7
        barras.bars[0].fillColor = colors.HexColor(COLORES_GRAFICO[0])
        barras.bars[0].strokeColor = None
        barras.barLabelFormat = "%d"
        barras.barLabels.fontName = "Helvetica"
        barras.barLabels.fontSize = 7
        barras.barLabels.nudge = 8
        dibujo.add(barras)
    return dibujo


def _tabla_pdf(columnas, filas, celda, cabecera, ancho_util):
    datos_tabla = [[_p(c, cabecera) for c in columnas]]
    datos_tabla += [[_p(v, celda) for v in f] for f in filas]
    ancho = ancho_util / len(columnas)
    tabla = Table(datos_tabla, colWidths=[ancho] * len(columnas), repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#343a40")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f4f6")]),
    ]))
    return tabla


def a_pdf(datos):
    estilos = getSampleStyleSheet()
    celda = ParagraphStyle("celda", parent=estilos["BodyText"], fontSize=7.5, leading=9)
    cabecera = ParagraphStyle("cab", parent=celda, textColor=colors.white, fontName="Helvetica-Bold")
    pagina = landscape(A4)

    def pie(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.grey)
        canvas.drawString(1.5 * cm, 0.8 * cm, f"{datos.sello} · {AVISO_DATOS_PERSONALES}")
        canvas.drawRightString(pagina[0] - 1.5 * cm, 0.8 * cm, f"Página {doc.page}")
        canvas.restoreState()

    salida = BytesIO()
    doc = SimpleDocTemplate(
        salida, pagesize=pagina,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        title=datos.titulo,
    )
    elementos = [
        _p(datos.titulo, estilos["Title"]),
        _p(datos.subtitulo, estilos["Normal"]),
        _p(datos.sello, ParagraphStyle("sello", parent=estilos["Normal"], textColor=colors.grey)),
        Spacer(1, 0.5 * cm),
    ]
    resumen = Table(
        [[_p(e, ParagraphStyle("res", parent=celda, fontName="Helvetica-Bold")), _p(v, celda)]
         for e, v in datos.resumen],
        colWidths=[6 * cm, 4 * cm], hAlign="LEFT",
    )
    resumen.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey)]))
    elementos += [resumen, Spacer(1, 0.6 * cm)]

    dibujo = _grafico_pdf(datos.grafico, pagina[0] - 3 * cm)
    if dibujo is not None:
        elementos += [dibujo, Spacer(1, 0.6 * cm)]

    ancho_util = pagina[0] - 3 * cm
    if datos.secciones:
        # Historiales: una tabla con título por sección.
        for seccion in datos.secciones:
            elementos.append(_p(seccion.titulo, estilos["Heading3"]))
            if seccion.filas:
                elementos.append(_tabla_pdf(seccion.columnas, seccion.filas, celda, cabecera, ancho_util))
            else:
                elementos.append(_p(seccion.vacio, estilos["Normal"]))
            elementos.append(Spacer(1, 0.5 * cm))
    elif datos.filas:
        elementos.append(_tabla_pdf(datos.columnas, datos.filas, celda, cabecera, ancho_util))
    else:
        elementos.append(Paragraph("No hay registros en este periodo.", estilos["Normal"]))
    doc.build(elementos, onFirstPage=pie, onLaterPages=pie)
    return salida.getvalue()


class ExportadorExcelPDF(IExportador):
    def exportar(self, datos, formato):
        return a_excel(datos) if formato == EXCEL else a_pdf(datos)
