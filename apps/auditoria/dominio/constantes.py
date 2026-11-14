"""Valores fijos de Auditoría que otros módulos también usan."""
import uuid

# Actor de las acciones automáticas (comandos, procesos del sistema).
SISTEMA_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Identidad usa su propio "actor sistema" (todo ceros): la pantalla trata a ambos igual.
ACTORES_SISTEMA = frozenset({SISTEMA_ID, uuid.UUID(int=0)})
ETIQUETA_SISTEMA = "Sistema (automático)"
