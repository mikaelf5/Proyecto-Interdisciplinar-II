"""Regla de las etiquetas automáticas del solicitante (RF-B6).

Función pura: recibe hechos (sanciones vigentes, préstamos devueltos a
tiempo) y decide la etiqueta. No consulta la base de datos, así se prueba
con una sola línea por caso.

Prioridad (de más a menos grave):
    1. BANEADO     -> tiene un baneo vigente.
    2. SANCIONADO  -> tiene otra sanción vigente (observación o suspensión).
    3. FRECUENTE   -> devolvió a tiempo al menos `umbral_frecuente` préstamos.
    4. NUEVO       -> todo lo demás.
"""
from apps.common.choices import EtiquetaEstado

TIPO_BANEO = "BANEO"  # valor de TipoSancion.BANEO (contexto Sanciones)


def calcular_etiqueta(tiene_sancion_activa, sancion_mas_grave, devueltos_a_tiempo, umbral_frecuente):
    if tiene_sancion_activa and sancion_mas_grave == TIPO_BANEO:
        return EtiquetaEstado.BANEADO
    if tiene_sancion_activa:
        return EtiquetaEstado.SANCIONADO
    if umbral_frecuente > 0 and devueltos_a_tiempo >= umbral_frecuente:
        return EtiquetaEstado.FRECUENTE
    return EtiquetaEstado.NUEVO
