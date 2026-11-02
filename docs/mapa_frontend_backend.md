# Mapa Frontend → Backend (Catálogo, Reservas, Notificaciones)

Para la exposición: por cada **botón o pantalla**, qué código se ejecuta y en qué orden.
Rutas relativas a `apps/`. Los números de línea son los de esta versión.

**Cómo encontrarlo rápido en VS Code**
- `Ctrl + P` → escribe el archivo (ej. `reservas/aplicacion/servicios.py`) → `Ctrl + G` → número de línea.
- `Ctrl + Shift + F` → busca el **texto del botón** (ej. `Marcar dañado`) y llegas a la plantilla HTML;
  ahí el `action="{% url '...' %}"` te dice qué URL llama.
- `Ctrl + clic` sobre un nombre de función te lleva a donde está definida.

**El camino de SIEMPRE**
```
HTML (botón/form) → config/urls.py → <app>/urls.py → presentacion/urls.py → Vista (presentacion/views.py)
   → Servicio de aplicación (aplicacion/servicios.py) → Regla de dominio (dominio/models.py o dominio/servicios.py)
   → Repositorio (infraestructura/repositorios.py) → ORM de Django → PostgreSQL
```

---

## 1. CATÁLOGO

### 1.1 Buscar ítems — menú "Catálogo" + botón "Buscar"
| Capa | Dónde | Qué hace |
|---|---|---|
| HTML | `catalogo/templates/catalogo/item_list.html` | `<form method="get">` con texto, categoría y estado |
| URL | `catalogo/presentacion/urls.py:8` | `""` → `BuscarView` |
| Vista | `catalogo/presentacion/views.py:48` `BuscarView.get` | Lee el form `FiltroItemForm` (`presentacion/forms.py:6`) y arma `FiltrosItem` |
| Servicio | `catalogo/aplicacion/servicios.py:165` `buscar_items` | Pide los ítems al repositorio y los convierte en `ItemDTO` |
| Repositorio | `catalogo/infraestructura/repositorios.py:50` `buscar` | `Item.objects.select_related("categoria").filter(...)` |
| Tabla | `catalogo_item` JOIN `catalogo_categoria` | `SELECT ... WHERE codigo ILIKE ... OR atributos::text ILIKE ...` |

### 1.2 Ver detalle — botón "Ver"
| Capa | Dónde | Qué hace |
|---|---|---|
| URL | `catalogo/presentacion/urls.py:10` | `<uuid:pk>/` → `DetalleView` |
| Vista | `catalogo/presentacion/views.py:106` `DetalleView.get` | Junta ítem + horarios de hoy + historial |
| Servicio | `catalogo/aplicacion/servicios.py:170` `obtener_item` | Busca el ítem por id |
| Servicio | `catalogo/aplicacion/servicios.py:184` `historial_condicion` | Historial de condición física (RF-A5) |
| Otro módulo | `reservas/aplicacion/servicios.py:278` `agenda` | Horarios reservados y libres de hoy |
| Repositorio | `catalogo/infraestructura/repositorios.py:41` `buscar_por_id`, `:71` `de_item` | `Item.objects.get(pk=...)`, `CondicionFisica.objects.filter(item_id=...)` |

### 1.3 Registrar ítem — botón "+ Registrar ítem" (solo ADMINISTRADOR)
| Capa | Dónde | Qué hace |
|---|---|---|
| HTML | `catalogo/templates/catalogo/item_form.html` | Paso 1 elegir categoría (GET), paso 2 datos (POST) |
| URL | `catalogo/presentacion/urls.py:9` | `nuevo/` → `RegistrarItemView` |
| Permiso | `RolRequeridoMixin`, `roles_permitidos = [ADMINISTRADOR]` | Si no es admin → 403 |
| Vista | `catalogo/presentacion/views.py:65` `RegistrarItemView.post` | Valida el form y arma `NuevoItemDTO` |
| Form | `catalogo/presentacion/forms.py:58` `ItemNuevoForm` | Un campo por cada atributo de la categoría (tabla `CAMPOS_POR_TIPO`); `atributos()` (`:98`) arma el JSON |
| Servicio | `catalogo/aplicacion/servicios.py:101` `registrar_item` | Verifica código único (RF-A3), crea el `Item` |
| Dominio | `catalogo/dominio/models.py:77` `Item.clean` → `dominio/validadores.py:63` `validar_atributos` | Atributos obligatorios y tipos (tabla `VERIFICADORES`, `:47`) |
| Repositorio | `catalogo/infraestructura/repositorios.py:32` `guardar` | `full_clean()` + `save()` → **INSERT** en `catalogo_item` |

### 1.4 Marcar dañado / Poner disponible / Dar de baja — "Acciones del encargado"
| Capa | Dónde | Qué hace |
|---|---|---|
| HTML | `catalogo/templates/catalogo/item_detail.html` | 3 `<form method="post">` con `{% csrf_token %}` |
| URL | `catalogo/presentacion/urls.py:11-13` | `disponible/`, `daniado/`, `baja/` |
| Permiso | `catalogo/presentacion/views.py:140` `_AccionEncargadoView` | ENCARGADO o ADMINISTRADOR; si no → 403 |
| Vista | `views.py:157` `PonerDisponibleView`, `:165` `MarcarDaniadoView`, `:173` `DarDeBajaView` | Cada una solo implementa `ejecutar()` |
| Servicio | `servicios.py:111` `cambiar_estado_item`, `:119` `marcar_daniado`, `:128` `dar_de_baja_item` | Buscar → regla → guardar → DTO |
| Dominio | `catalogo/dominio/models.py:55` `TRANSICIONES`, `:83` `cambiar_estado` | Máquina de estados: ej. de BAJA no se sale |
| Repositorio | `catalogo/infraestructura/repositorios.py:36` `guardar_estado` | **UPDATE** `catalogo_item SET estado=...` (solo el estado) |
| Reservas | `catalogo/aplicacion/servicios.py:136` `_anular_reservas_futuras` → `reservas/aplicacion/servicios.py:210` | Dañado o baja: **anula las reservas futuras** del ítem y avisa a cada solicitante |

---

## 2. RESERVAS

### 2.1 Reservar — botón "Reservar este ítem" → formulario → botón "Reservar"
| Capa | Dónde | Qué hace |
|---|---|---|
| HTML | `reservas/templates/reservas/reservar.html` | Form día + desde + hasta + finalidad |
| URL | `reservas/presentacion/urls.py:10` | `item/<uuid>/reservar/` → `ReservarView` |
| Permiso | `ReservarView.roles_permitidos = [SOLICITANTE]` | Si no es solicitante → 403 |
| Vista | `reservas/presentacion/views.py:78` `ReservarView.post` | Form `ReservaForm` → `NuevaReservaDTO` → `servicio.crear` |
| Servicio | `reservas/aplicacion/servicios.py:117` **`crear`** | Se lee como receta (ver abajo) |
| Repositorio | `reservas/infraestructura/repositorios.py:12` `guardar` | **INSERT** en `reservas_reserva` |

**`crear()` paso a paso** (`reservas/aplicacion/servicios.py`)
0. `expirar_reservas` (`:193`) — primero libera las franjas de quien no vino (15 min de tolerancia).
1. `_item_solicitado` (`:290`) → `_item_reservable` (`:297`) — el ítem existe y no está en mantenimiento/baja.
2. `_validar_reglas` (`:314`) →
   - `_verificar_habilitacion` (`:321`) → Identidad (`infraestructura/adaptadores.py:19`): ¿habilitado?
   - `_politica_de` (`:326`) → Políticas (`adaptadores.py:38`): duración, antelación, límites.
   - `ReglasDeReserva.validar` (`dominio/servicios.py:40`): horario, bloques de 15 min, duración mínima (15 min) y máxima (política), anticipación mínima (30 min) y máxima (política).
3. `repositorio.bloquear_item` (`repositorios.py:23`) — candado para que dos personas no reserven a la vez.
4. `_verificar_franja_libre` (`:334`) — si choca (o no deja **15 min de margen** con otra reserva) lanza `HorarioOcupado` con horarios libres y otros ítems. La regla de choque está en un solo lugar: `_choca` (`:417`) → `Reserva.choca_con` (`dominio/models.py:93`).
5. `_verificar_limites` (`:353`) → `ReglasDeReserva.validar_limites` (`dominio/servicios.py:95`): máximo 4 vigentes y 1 especial a la vez.
6. `_nueva_reserva` (`:380`) + `_aprobar_automaticamente` (`:388`) — CONFIRMADA o EN_ESPERA_SUPERVISOR.
7. `repositorio.guardar` → INSERT.

### 2.2 Choque de horario → "Avisarme si se libera"
| Capa | Dónde |
|---|---|
| Vista | `ReservarView.post` captura `HorarioOcupado` y vuelve a mostrar el form con el mensaje |
| Servicio | `reservas/aplicacion/servicios.py:131` `anotarse_en_espera` → `_verificar_que_puede_esperar` (`:367`) |
| Dominio | `dominio/servicios.py:29` `AsignadorDeCola.posicion_para_nueva` (va al final de la fila) |

### 2.3 Cancelar — botón "Cancelar" de Mis reservas
| Capa | Dónde | Qué hace |
|---|---|---|
| URL | `reservas/presentacion/urls.py:11` | `<uuid>/cancelar/` → `CancelarView` (`views.py:178`) |
| Servicio | `servicios.py:147` `cancelar` | Solo el dueño; si liberó la franja → `_pasar_turno_en` |
| Lista de espera | `servicios.py:397` `_pasar_turno_en` | En orden FIFO (`dominio/servicios.py:18` `en_orden`) confirma al primero que entra y le **notifica** |
| Notificación | `notificaciones/aplicacion/servicios.py:36` `enviar` | INSERT en `notificaciones_notificacion` + correo (consola) |

### 2.4 Bandeja del supervisor — Aprobar / Rechazar
| Capa | Dónde |
|---|---|
| URL | `reservas/presentacion/urls.py:17-19` |
| Vistas | `views.py:239` `BandejaSupervisorView`, `:254` `AprobarSupervisorView`, `:267` `RechazarSupervisorView` |
| Servicio | `servicios.py:162` `aprobar_supervisor` (no si el horario ya empezó), `:173` `rechazar_supervisor` |
| Dominio | `reservas/dominio/models.py:123` `aprobar_por_supervisor` → **"No puedes aprobar tu propia reserva"** |

### 2.5 Agenda y Anular (encargado)
| Capa | Dónde |
|---|---|
| Vistas | `views.py:190` `AgendaView`, `:222` `AnularView` |
| Servicio | `servicios.py:278` `agenda`, `:183` `anular` |
| Dominio | `dominio/servicios.py:122` `CalculadoraDeHorarios.libres` (huecos libres del día) |

### 2.6 Expirar reservas no recogidas
Se ejecuta **solo** cada vez que alguien reserva, y también a mano con `python manage.py expirar_reservas`.
→ `servicios.py:193` `expirar_reservas` → `_debe_expirar` (`:427`, 15 min de tolerancia) → `_pasar_turno_en`.

### 2.7 Contrato con Préstamos (lo llama Marving)
`servicios.py:221` `confirmadas_de_hoy` · `:226` `marcar_atendida` (entrega) · `:240` `extender` (renovar) · `:254` `liberar` (devolución).

---

## 3. NOTIFICACIONES

| Botón | URL | Vista | Servicio |
|---|---|---|---|
| Menú "Notificaciones" | `/notificaciones/` | `notificaciones/presentacion/views.py:20` `mis_notificaciones` | `aplicacion/servicios.py:66` `mis_notificaciones` |
| "Marcar como leída" | `/notificaciones/<id>/leida/` | `views.py:31` `marcar_leida` | `servicios.py:58` `marcar_leida` |
| (automático) avisos de reservas | — | — | `servicios.py:36` `enviar` → `infraestructura/emisores.py` (correo) |

---

## 4. Tablas que usan estos módulos
| Tabla | Modelo | Archivo |
|---|---|---|
| `catalogo_categoria` | `Categoria` | `catalogo/dominio/models.py` |
| `catalogo_item` | `Item` | `catalogo/dominio/models.py` |
| `catalogo_condicionfisica` | `CondicionFisica` | `catalogo/dominio/models.py` |
| `reservas_reserva` | `Reserva` | `reservas/dominio/models.py` |
| `notificaciones_notificacion` | `Notificacion` | `notificaciones/dominio/models.py` |
