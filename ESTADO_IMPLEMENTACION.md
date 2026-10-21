# Circulación — correspondencia con el diagrama de cuatro capas

## Implementado en esta entrega

- Dominio: Solicitud (aprobar, aprobar_como_supervisor, rechazar, cancelar, requiere_supervisor), Prestamo (renovar, registrar_devolucion, esta_vencido, cerrar_por_perdida), ServicioDeElegibilidad.evaluar (regla pura), ServicioDeAprobacion.decidir y el flujo M4.
- Puertos de dominio: ISolicitudRepositorio.guardar/buscar_por_id/pendientes, IPrestamoRepositorio.guardar/buscar_por_id/vigentes_de/vencidos, con alias de compatibilidad obtener_por_id y existe_abierto_para_item.
- Infraestructura: SolicitudRepositorioImpl, PrestamoRepositorioImpl usando Django ORM.
- Aplicación: DTOs, ISolicitudServicio y SolicitudServicioAplicacion (solicitar/aprobar/aprobar_como_supervisor/rechazar/cancelar); IPrestamoServicio y PrestamoServicioAplicacion (registrar_entrega/renovar/registrar_devolucion/listar_vencidos/cerrar_por_perdida); casos de uso delegadores.
- Pruebas nuevas para repositorios, reglas y servicios; conservadas las 19 pruebas existentes.
- Modelos con Meta.app_label="circulacion"; conservadas migraciones y compatibilidad de imports.

## Integraciones que requieren completar y verificar en el proyecto del equipo

- `registrar_entrega` usa dependencias inyectadas para Elegibilidad, Catálogo, Políticas, Condición Física y Auditoría. **No está conectado automáticamente** con las ramas N1/I1 ni con el E3 real. Sus contratos necesitan adaptadores y pruebas integradas antes de exponerlo en una vista. La atomicidad de `transaction.atomic` solo cubre operaciones en la misma base de datos.
- `renovar` requiere `resolver_politica(solicitante_id,item_id)` implementado con Identidad y Políticas. La regla del modelo está lista.
- `registrar_devolucion` registra condición física mediante contrato inyectado; **no libera automáticamente el ítem**: el equipo debe acordar el cambio de estado después de inspección.
- Los controladores `SolicitudController` y `PrestamoController` del diagrama no se han conectado a nuevas rutas web: las vistas Django existentes se conservaron. No afirmar que todas las acciones son accesibles desde la UI.
- `Solicitud.fecha_inicio` y `fecha_fin` son DateField. La precisión horaria del vencimiento se debe confirmar con el equipo antes de habilitar entregas reales.
- No se alteraron migraciones ni esquemas de base de datos.

## Verificación recomendada en Windows con el venv del proyecto

```
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.circulacion
```

**Advertencia:** en el entorno de generación no estaba instalado Django; se verificó compilación Python, no la ejecución de los tests con PostgreSQL.
