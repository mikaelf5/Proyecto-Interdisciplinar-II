# Auditoría y Reportes — qué hacen, dónde están y qué reglas cumplen

Estos dos módulos **solo observan**: Auditoría guarda la bitácora de lo que pasa en el sistema y Reportes
calcula estadísticas leyendo de los demás. Ninguno modifica datos de otro módulo.

---

## 1. Auditoría (`apps/auditoria`)

### Qué hace

Deja constancia de **quién hizo qué, cuándo y por qué** (RF-J1, RF-J2). Los registros solo se agregan:
no se editan ni se borran. Solo el **Administrador** ve la bitácora (`/auditoria/`).

### Reglas

| Regla | Dónde se cumple |
|---|---|
| Las acciones **rechazo, ítem dañado y sanción** siempre llevan motivo (RF-J1). Si falta, no se guarda nada y se lanza `ValidationError`. | `aplicacion/servicios.py` → `registrar()`; la lista está en `dominio/models.py` → `ACCIONES_CON_MOTIVO` |
| Un registro guarda **una sola vez** (antes hacía un `INSERT` y un `UPDATE` repetido). | `aplicacion/servicios.py` |
| Los procesos automáticos aparecen como **"Sistema (automático)"**. | `dominio/constantes.py` (`ACTORES_SISTEMA`) |
| La pantalla **no consulta la base de datos**: pide todo al servicio. | `views.py` → `auditoria_servicio()` |

### Vocabulario de acciones (`TipoAccion`)

| Acción | Quién la registra | Cuándo |
|---|---|---|
| `ENTREGA_PRESTAMO` | Circulación | Se entrega un ítem. |
| `RENOVACION_PRESTAMO` | Circulación | Se renueva un préstamo. |
| `DEVOLUCION_PRESTAMO` | Circulación | Se devuelve un ítem. |
| `SANCION` | Sanciones | Se aplica, modifica, levanta o elimina una sanción. |
| `ITEM_DANIADO` | Catálogo, Pérdidas | Un ítem se marca dañado o se registra una pérdida. |
| `CAMBIO_ESTADO` | Catálogo, Reservas, Pérdidas, Identidad, Sanciones (vencimientos) | Cambia el estado de un ítem, reserva, préstamo, caso o cuenta (poner disponible, dar de baja, anular una reserva, marcar vencido…). |
| `APROBACION` | Reservas | El supervisor aprueba una reserva de un ítem especial. |
| `RECHAZO` | Reservas, Identidad | Se rechaza una reserva o una solicitud de registro (con motivo). |
| `ENTREGA`, `DEVOLUCION` | (sin uso actual) | Se conservan por compatibilidad con el diseño original. |

Hay una **prueba que vigila el vocabulario**: si alguien audita con un nombre que no está en `TipoAccion`,
`test_todas_las_acciones_que_usa_el_codigo_existen_en_TipoAccion` falla.

### Cómo se audita desde otro módulo

```python
from apps.auditoria.fabrica import auditoria_servicio
auditoria_servicio().registrar(actor_id, "CAMBIO_ESTADO", "Reserva", reserva.id, "Motivo")
```

En Catálogo y Reservas el `actor_id` es **opcional** en los métodos (`marcar_daniado`, `dar_de_baja_item`,
`cambiar_estado_item`, `anular`): lo pasan las pantallas, y si lo dispara otro módulo no se duplica la
auditoría que ese módulo ya deja. **Excepción**: `marcar_daniado` siempre audita (si no hay actor, queda como
"Sistema"), porque así una devolución dañada de Préstamos también aparece en la bitácora y en los reportes.

### Archivos

| Capa | Archivo |
|---|---|
| Dominio | `dominio/models.py` (`RegistroAuditoria`, `TipoAccion`, `ACCIONES_CON_MOTIVO`), `dominio/constantes.py`, `dominio/repositorio.py` |
| Aplicación | `aplicacion/servicios.py` (`registrar`, `buscar`, `entidades`, `nombres_de_actores`) |
| Infraestructura | `infraestructura/repositorio_django.py` (las consultas) |
| Presentación | `views.py`, `templates/auditoria/registro_list.html`, `urls.py` |
| Armado | `fabrica.py` → `auditoria_servicio()` |

Tabla: `auditoria_registroauditoria` (`actor_id`, `accion`, `entidad`, `entidad_id`, `motivo`, `fecha_hora`).

### Pantalla

Filtros: acción, entidad, actor (ID), **texto del motivo**, rango de fechas. Muestra el **nombre** de quien hizo la
acción (con su ID abreviado), y la paginación conserva los filtros.

---

## 2. Reportes (`apps/reportes`)

### Qué hace

Cinco reportes por periodo (RF-I1), todos exportables a **Excel y PDF** (RF-I2). Solo el **Administrador**
los genera y los ve (`/reportes/`). Los datos se calculan al abrir el reporte, con la información actual.

| Reporte | Qué cuenta | Fuente |
|---|---|---|
| Ítems más prestados | Préstamos **entregados** en el periodo, por ítem (los 15 primeros). | Circulación |
| Usuarios más activos | Préstamos por solicitante, con cuántos devolvió a tiempo y con atraso. | Circulación + Identidad |
| Tasa de devolución a tiempo | *Devueltos a tiempo ÷ (a tiempo + con atraso)*. No cuentan los que siguen en curso ni los cerrados por pérdida. | Circulación |
| Ítems perdidos o dañados | Casos de pérdida **más** ítems dañados (registros `ITEM_DANIADO` sobre un `Item`), con código y nombre del ítem. | Pérdidas + Auditoría + Catálogo |
| Sanciones por periodo | Sanciones aplicadas, por tipo y cuántas siguen vigentes. | Sanciones |

### Archivos

| Capa | Archivo |
|---|---|
| Dominio | `dominio/models.py`, `dominio/datos.py`, `dominio/fuentes.py` (qué datos necesita de otros módulos) |
| Aplicación | `aplicacion/servicios.py` (el cálculo de los 5 reportes) |
| Infraestructura | `infraestructura/fuente_datos.py` (de dónde los lee), `exportador_excel_pdf.py` (openpyxl y reportlab) |
| Presentación | `views.py`, `templates/reportes/`, `urls.py` |

Tabla: `reportes_reporte` (`tipo`, `periodo_inicio`, `periodo_fin`, `generado_por_id`).

---

## 3. Pruebas

| Archivo | Qué comprueba |
|---|---|
| `auditoria/tests/test_auditoria.py` | Un solo `INSERT` por registro, permisos por rol, filtros. |
| `auditoria/tests/test_vocabulario_y_pantalla.py` | Vocabulario de acciones, motivo obligatorio, nombres de actores, filtros y paginación. |
| `auditoria/tests/test_cobertura.py` | Catálogo y Reservas dejan su auditoría; **devolución dañada → bitácora → reporte**. |
| `reportes/tests/test_reportes.py` | Los 5 reportes, Excel y PDF, permisos. |

Ejecutar: `python manage.py test apps.auditoria apps.reportes`

## 4. Límites conocidos

- La devolución dañada audita el **daño** como "Sistema" (lo dispara Catálogo sin saber quién devolvió); quien hizo la
  devolución sí queda en el registro `DEVOLUCION_PRESTAMO`. Para atribuirlo, Circulación podría pasar su `encargado_id`
  a `marcar_daniado(..., actor_id=...)` (hoy sus pruebas esperan la llamada sin ese parámetro).
- Los reportes de préstamos leen el modelo de Circulación (`fuente_datos.py`); si Circulación expone consultas por
  periodo en su servicio, solo hay que cambiar esa clase.
