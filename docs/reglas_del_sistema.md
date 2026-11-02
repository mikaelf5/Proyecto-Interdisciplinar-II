# ¿Dónde están las reglas del sistema?

Las reglas viven en **3 lugares distintos** según su tipo:

1. **Valores configurables** (números que el administrador puede cambiar) → **Políticas** (tabla `politicas_politicaprestamo`).
2. **Reglas del negocio** (la lógica que usa esos valores) → la capa de **dominio** de cada módulo.
3. **Garantías de la base de datos** (lo que nunca puede romperse, aunque falle el código) → **restricciones** en PostgreSQL.

Encima de eso, los **formularios** revisan la forma de los datos y las **vistas** revisan los permisos por rol.
Rutas relativas a `apps/`.

---

## 1. Políticas: los VALORES (se configuran, no se programan)

Tabla `politicas_politicaprestamo` · modelo `politicas/dominio/models.py:9` · se edita en `/admin/` · `seed_demo` carga los de ejemplo.
Hay una política por **categoría × tipo de usuario** (alumno, docente, administrativo).

| Valor | Qué controla | Valor actual | Lo usa |
|---|---|---|---|
| `duracion_maxima` (horas) | Cuánto puede durar una reserva | Equipos 3 h · Libros 4 h · Indumentaria 5 h | Reservas (`ReglasDeReserva._errores_de_politica`) |
| `antelacion_reserva` (días) | Hasta cuántos días adelante se puede reservar | 3 o 7 días según categoría y usuario | Reservas (`_errores_de_politica`) |
| `limite_simultaneo_global` | Máximo de **reservas vigentes en total** (en espera, confirmadas o en uso) | **4** para todos | Reservas (`validar_limites`) |
| `limite_simultaneo_por_tipo` | Máximo de **esa clase de ítem** | **Especiales (Equipos): 1** · Libros 4 · Indumentaria 4 | Reservas (`validar_limites`) |
| `max_renovaciones` | Cuántas veces se puede renovar | 1 o 2 | Préstamos (`circulacion/dominio/models.py:221` `renovar`) |

Validación de la propia política (que no tenga valores absurdos): `politicas/dominio/models.py:62` `clean()`.

**Cómo llegan a Reservas:** `reservas/infraestructura/adaptadores.py:38` `politica_para()` → `reservas/aplicacion/servicios.py:326` `_politica_de()`.

---

## 2. Horario de atención: reglas fijas para TODOS

`reservas/dominio/horario.py:38` `HorarioAtencion` · se puede cambiar en `config/settings.py` con `RESERVAS_HORARIO`.

| Regla | Valor | Dónde se valida |
|---|---|---|
| Días de atención | Lunes a viernes | `reservas/dominio/servicios.py:51` `_errores_de_horario` |
| Horario | 08:00 a 20:00 (todo dentro del mismo día) | `:51` `_errores_de_horario` |
| Bloques de horas | De 15 en 15 (10:00, 10:15…) | `:51` `_errores_de_horario` |
| Duración mínima | 15 minutos | `:62` `_errores_de_duracion` |
| Anticipación mínima | 30 minutos antes del inicio | `:68` `_errores_de_anticipacion` |
| Margen entre reservas del mismo ítem | 15 minutos (para recibir y revisar el ítem) | `reservas/dominio/models.py:93` `choca_con` ← `aplicacion/servicios.py:417` `_choca` |
| Tolerancia para recoger | 15 minutos; si no, expira | `reservas/aplicacion/servicios.py:427` `_debe_expirar` |

---

## 3. Reglas del negocio (dominio y servicios)

### Reservas
| Regla | Dónde |
|---|---|
| **Todas las reglas de una reserva juntas** (horario, bloques, duración mín/máx, anticipación mín/máx) | `reservas/dominio/servicios.py:40` `ReglasDeReserva.validar` |
| **Máximo 4 reservas vigentes y 1 especial a la vez** (la lista de espera también cuenta) | `reservas/dominio/servicios.py:95` `validar_limites` ← `aplicacion/servicios.py:353` `_verificar_limites` |
| El usuario debe estar **habilitado** (perfil, acta firmada, sin sanción) | `reservas/aplicacion/servicios.py:321` → Identidad `identidad/dominio/models.py:144` `motivos_de_inhabilitacion` |
| No se reserva un ítem en mantenimiento o de baja | `reservas/aplicacion/servicios.py:297` `_item_reservable` |
| **Franja exclusiva**: no se reserva encima de otro, y se deja un margen de 15 min | `reservas/aplicacion/servicios.py:334` `_verificar_franja_libre` (usa `_choca`) |
| La lista de espera también respeta el margen | `reservas/aplicacion/servicios.py:397` `_pasar_turno_en` |
| Aprobación automática; ítem especial → supervisor | `reservas/aplicacion/servicios.py:388` `_aprobar_automaticamente` |
| **Nadie aprueba su propia reserva** | `reservas/dominio/models.py:123` `aprobar_por_supervisor` |
| El supervisor no aprueba una reserva cuyo horario ya empezó | `reservas/aplicacion/servicios.py:162` `aprobar_supervisor` |
| Rechazar o anular exige **motivo** | `reservas/dominio/models.py:129` `rechazar_por_supervisor`, `:143` `anular` |
| Qué cambios de estado se permiten | `reservas/dominio/models.py:106` `_pasar` (cada método dice desde qué estados) |
| Solo el dueño cancela su reserva | `reservas/aplicacion/servicios.py:147` `cancelar` |
| Lista de espera FIFO | `reservas/dominio/servicios.py:18` `en_orden`, `:29` `posicion_para_nueva` |
| Quien no recoge en 15 min pierde la reserva (se revisa sola al reservar) | `reservas/aplicacion/servicios.py:193` `expirar_reservas` |
| Renovar sin pasar el cierre y sin pisar al siguiente | `reservas/aplicacion/servicios.py:240` `extender` |

### Catálogo
| Regla | Dónde |
|---|---|
| Estados del ítem permitidos (de BAJA no se vuelve) | `catalogo/dominio/models.py:55` `TRANSICIONES`, `:83` `cambiar_estado` |
| Dañado o baja exigen motivo | `catalogo/dominio/models.py:96` `marcar_daniado`, `:102` `dar_de_baja` |
| Dañado o baja **anulan las reservas futuras** del ítem y avisan | `catalogo/aplicacion/servicios.py:136` `_anular_reservas_futuras` |
| Atributos según la categoría (obligatorios, tipos, sin sobrantes) | `catalogo/dominio/validadores.py:63` `validar_atributos` (tabla `VERIFICADORES`, `:47`) |
| Cambiar de estado no revalida atributos (un cambio de categoría no bloquea ítems viejos) | `catalogo/infraestructura/repositorios.py:36` `guardar_estado` |
| Código único | `catalogo/aplicacion/servicios.py:101` `registrar_item` (+ `UNIQUE` en la BD) |

### Usuarios y permisos
| Regla | Dónde |
|---|---|
| Quién entra a cada pantalla (rol) | `identidad/presentacion/permisos.py:14` `RolRequeridoMixin` + `roles_permitidos` en cada vista |
| Habilitación para reservar | `identidad/aplicacion/servicios.py:107` `consultar_habilitacion` |

---

## 4. Garantías en la base de datos (PostgreSQL)

Aunque el código fallara, la base de datos **rechaza** esto:

| Restricción | Tabla | Definida en |
|---|---|---|
| Código de ítem único | `catalogo_item` | `catalogo/dominio/models.py:62` (`unique=True`) |
| Una condición física de ENTREGA y una de DEVOLUCIÓN por préstamo | `catalogo_condicionfisica` | `catalogo/dominio/models.py:129` |
| No borrar una categoría que tiene ítems | `catalogo_item` → `catalogo_categoria` | `on_delete=PROTECT` (llave foránea) |
| Hora de fin mayor que hora de inicio | `reservas_reserva` | `reservas/dominio/models.py:68` (`CheckConstraint`) |
| Dos personas no pueden tener la misma posición en la lista de espera | `reservas_reserva` | `reservas/dominio/models.py:68` (`UniqueConstraint`) |
| Un ítem no puede tener dos préstamos abiertos | `circulacion_prestamo` | `circulacion/dominio/models.py:199` |
| Correo y DNI únicos por cuenta | `identidad_cuenta` | `identidad/dominio/models.py` (`unique=True`) |

---

## 5. Primer filtro: los formularios (solo la FORMA de los datos)

| Formulario | Qué revisa |
|---|---|
| `reservas/presentacion/forms.py` `ReservaForm` | Que haya fecha y horas válidas y que el fin sea posterior al inicio |
| `catalogo/presentacion/forms.py` `ItemNuevoForm` | Tipo de cada atributo (número, fecha, opción) y obligatorios |
| `identidad/presentacion/forms.py` `LoginForm` | Que el correo tenga forma de correo |

El formulario **no** decide reglas del negocio: eso lo hacen el dominio y los servicios.
