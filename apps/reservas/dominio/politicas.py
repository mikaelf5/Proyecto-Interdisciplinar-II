"""
Capa de DOMINIO — Políticas de reserva por defecto (Value Object).

Igual que horario.py, las reglas por categoría viven aquí en el código, así
el sistema funciona aunque nadie haya cargado políticas en la base de datos.

Si el administrador configura una política en /admin/ (tabla
politicas_politicaprestamo), manda esa: esta tabla es solo el respaldo.

  
"""
from dataclasses import dataclass

from apps.common.choices import TipoUsuario

MAXIMO_VIGENTES_EN_TOTAL = 4

ANTELACION_CORTA = {TipoUsuario.ALUMNO: 3, TipoUsuario.DOCENTE: 3, TipoUsuario.ADMINISTRATIVO: 3}
ANTELACION_LARGA = {TipoUsuario.ALUMNO: 7, TipoUsuario.DOCENTE: 7, TipoUsuario.ADMINISTRATIVO: 7}


@dataclass(frozen=True)
class ReglaDeCategoria:
    horas_maximas: int
    dias_de_antelacion: dict
    a_la_vez: int


POLITICAS_POR_CATEGORIA = {
    "equipos": ReglaDeCategoria(horas_maximas=3, dias_de_antelacion=ANTELACION_CORTA, a_la_vez=1),
    "libros": ReglaDeCategoria(horas_maximas=4, dias_de_antelacion=ANTELACION_LARGA, a_la_vez=4),
    "indumentaria": ReglaDeCategoria(horas_maximas=5, dias_de_antelacion=ANTELACION_CORTA, a_la_vez=4),
}

# Para una categoría nueva que no está en la tabla de arriba
REGLA_PARA_ESPECIAL = POLITICAS_POR_CATEGORIA["equipos"]
REGLA_PARA_NORMAL = ReglaDeCategoria(horas_maximas=4, dias_de_antelacion=ANTELACION_CORTA, a_la_vez=4)


@dataclass(frozen=True)
class PoliticaDeReserva:
    """Tiene los mismos campos que usa Reservas de la tabla de políticas."""
    duracion_maxima: int             # horas
    antelacion_reserva: int          # días
    limite_simultaneo_por_tipo: int
    limite_simultaneo_global: int = MAXIMO_VIGENTES_EN_TOTAL


def politica_por_defecto(nombre_categoria, es_especial, tipo_usuario):
    """La política del código para esa categoría y ese tipo de usuario (alumno, docente…)."""
    respaldo = REGLA_PARA_ESPECIAL if es_especial else REGLA_PARA_NORMAL
    regla = POLITICAS_POR_CATEGORIA.get((nombre_categoria or "").strip().lower(), respaldo)
    return PoliticaDeReserva(
        duracion_maxima=regla.horas_maximas,
        antelacion_reserva=regla.dias_de_antelacion[tipo_usuario],
        limite_simultaneo_por_tipo=regla.a_la_vez,
    )