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
| `EXPORTACION_REPORTE` | Reportes | Alguien descarga un reporte en Excel o PDF (los archivos llevan datos personales). |
| `ELIMINACION_REPORTE` | Reportes | Alguien elimina un reporte generado. |
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

| Reporte | Qué cuenta | Fuente | Gráfico |
|---|---|---|---|
| Ítems más prestados | Préstamos **entregados** en el periodo, por ítem. | Circulación + Catálogo | Barras |
| Usuarios más activos | Préstamos por solicitante, con cuántos devolvió a tiempo y con atraso. | Circulación + Identidad | Barras |
| Tasa de devolución a tiempo | *Devueltos a tiempo ÷ (a tiempo + con atraso)*. No cuentan los que siguen en curso ni los cerrados por pérdida. | Circulación | Dona |
| Ítems perdidos o dañados | Casos de pérdida (con el **ítem** perdido) **más** ítems dañados (registros `ITEM_DANIADO` sobre un `Item`). | Pérdidas + Circulación + Auditoría + Catálogo | Dona |
| Sanciones por periodo | Sanciones aplicadas, por tipo, cuántas siguen vigentes, con el **nombre** del sancionado y de quien la aplicó. | Sanciones + Identidad | Dona |

### Reglas

| Regla | Dónde se cumple |
|---|---|
| Un reporte **no se edita**: es la constancia de qué se pidió, quién y cuándo. Para otro periodo se genera uno nuevo. | `urls.py` (no hay `editar/`), `aplicacion/servicios.py` |
| El periodo no puede empezar ni terminar después de hoy, ni durar más de **366 días**, ni estar al revés. | `forms.py` (`MAX_DIAS_PERIODO`) |
| En pantalla los rankings muestran los **15 primeros**; las **descargas traen la lista completa**. | `aplicacion/servicios.py` (`TOP`, `generar_datos(limite=...)`) |
| Descargar o eliminar un reporte queda en la **auditoría** (`EXPORTACION_REPORTE`, `ELIMINACION_REPORTE`). | `aplicacion/servicios.py` → `exportar()`, `eliminar()` |
| Los archivos llevan **"Generado el … por …"** (quien descarga) y el aviso de **datos personales (Ley 29733)**. | `infraestructura/exportador_excel_pdf.py` |
| En el PDF, todo texto se **escapa** antes de pasarlo a reportlab: un motivo como `Cable <roto>` ya no pierde texto ni rompe la descarga. | `exportador_excel_pdf.py` → `_p()` |
| En el Excel las celdas guardan **números, fechas, porcentajes y soles** con su formato (se pueden sumar y graficar). | `exportador_excel_pdf.py` → `_celda_excel()`; tipos en `dominio/datos.py` (`Porcentaje`, `Soles`) |
| En los daños registrados al recibir una devolución, la columna "Persona" dice **quién devolvió el ítem** (la devolución de ese ítem hasta 1 h antes del registro). Si el daño se marcó a mano desde el catálogo, queda vacía: no se culpa a nadie. | `infraestructura/fuente_datos.py` → `_quien_lo_devolvio()` (una consulta para todos) |
| Para ver los reportes con datos: `python manage.py seed_demo` y luego `python manage.py shell -c "exec(open('datos_reportes.py', encoding='utf-8').read())"`. **Borra** préstamos, sanciones, pérdidas y reportes: solo en local (se niega con `DEBUG=False`). | `datos_reportes.py` |
| Los ítems se piden a Catálogo **en una sola consulta** (`obtener_items`), no uno por uno. | `infraestructura/fuente_datos.py` |
| Reportes ya **no lee el modelo de Circulación**: usa `entregados_entre()` e `items_de_prestamos()` de su servicio. | `infraestructura/fuente_datos.py` |

### Archivos

| Capa | Archivo |
|---|---|
| Dominio | `dominio/models.py`, `dominio/datos.py` (`DatosReporte`, `Porcentaje`, `Soles`, `Grafico`, `como_texto`), `dominio/fuentes.py` (qué datos necesita de otros módulos) |
| Aplicación | `aplicacion/servicios.py` (el cálculo de los 5 reportes, auditoría de descargas) |
| Infraestructura | `infraestructura/fuente_datos.py` (de dónde los lee), `exportador_excel_pdf.py` (openpyxl y reportlab, con gráfico) |
| Presentación | `views.py`, `templates/reportes/` (gráfico con Chart.js y atajos de periodo), `urls.py` |

Tabla: `reportes_reporte` (`tipo`, `periodo_inicio`, `periodo_fin`, `generado_por_id`). **No guarda resultados.**

Consulta equivalente a "Ítems más prestados" (para mostrar en pgAdmin):

```sql
SELECT i.codigo, COUNT(*) AS prestamos
FROM circulacion_prestamo p
JOIN catalogo_item i ON i.id = p.item_id
WHERE (p.fecha_entrega AT TIME ZONE 'America/Lima')::date BETWEEN '2026-11-01' AND '2026-11-30'
GROUP BY i.codigo
ORDER BY prestamos DESC
LIMIT 15;
```

---

## 3. Pruebas

| Archivo | Qué comprueba |
|---|---|
| `auditoria/tests/test_auditoria.py` | Un solo `INSERT` por registro, permisos por rol, filtros. |
| `auditoria/tests/test_vocabulario_y_pantalla.py` | Vocabulario de acciones, motivo obligatorio, nombres de actores, filtros y paginación. |
| `auditoria/tests/test_cobertura.py` | Catálogo y Reservas dejan su auditoría; **devolución dañada → bitácora → reporte**. |
| `reportes/tests/test_reportes.py` | Los 5 reportes, Excel y PDF (tipos de celda, escape del PDF, sello), lista completa, una sola consulta de ítems, auditoría de descargas y eliminación, validación del periodo, gráfico, permisos. |

Ejecutar: `python manage.py test apps.auditoria apps.reportes`

## 4. Límites conocidos

- La devolución dañada audita el **daño** como "Sistema" (lo dispara Catálogo sin saber quién devolvió); quien hizo la
  devolución sí queda en el registro `DEVOLUCION_PRESTAMO`. Para atribuirlo, Circulación podría pasar su `encargado_id`
  a `marcar_daniado(..., actor_id=...)` (hoy sus pruebas esperan la llamada sin ese parámetro).
- El gráfico de la pantalla usa Chart.js desde un CDN: sin internet no se dibuja, pero la tabla y las descargas
  (que llevan su propio gráfico hecho con reportlab) siguen funcionando.
