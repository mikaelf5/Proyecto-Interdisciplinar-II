"""Documentos que el usuario acepta al registrarse (RF-B2, RNF-2).

La VERSIÓN es un dato del negocio: si el texto cambia, se sube la versión
(v1 -> v2) y en la base queda qué versión aceptó cada persona y cuándo.
"""

VERSION_ACTA = "v1"
VERSION_CONSENTIMIENTO = "v1"

ACTA_RESPONSABILIDAD = (
    "El solicitante se compromete a: (1) usar los recursos prestados solo para fines "
    "académicos o institucionales; (2) devolverlos en la fecha indicada y en el mismo "
    "estado en que los recibió; (3) comunicar de inmediato cualquier daño, pérdida o robo; "
    "(4) dejar la garantía que se le solicite (DNI, carné u otro documento); y (5) aceptar "
    "las sanciones de acceso (observación, suspensión o baneo) que la escuela aplique "
    "por incumplimiento."
)

CONSENTIMIENTO_DATOS = (
    "De acuerdo con la Ley N.° 29733, Ley de Protección de Datos Personales, y su "
    "reglamento, autorizo a la escuela a tratar mis datos (nombres, DNI, CUI, correo, "
    "celular y dirección) con la única finalidad de gestionar los préstamos, reservas, "
    "notificaciones y sanciones del Sistema de Préstamos. Solo accede a ellos el personal "
    "autorizado. Puedo ejercer mis derechos de acceso, rectificación, cancelación y "
    "oposición (ARCO) ante la administración de la escuela."
)
