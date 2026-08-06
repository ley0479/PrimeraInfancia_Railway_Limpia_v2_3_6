# Informe de implementación — PrimeraInfancia 2.7.0

## Centro Inteligente de Planeación y Componente Psicosocial

**Versión fuente:** 2.6.1 — PostgreSQL, Integridad y Estabilidad  
**Versión resultante:** 2.7.0 — Centro de Planeación y Componente Psicosocial  
**Fecha de preparación:** 6 de agosto de 2026

## 1. Alcance atendido

La versión 2.7.0 continúa sobre el estado técnico de 2.6.1. No reemplaza la autenticación, PostgreSQL, el aislamiento multi-fundación, el Motor de Integridad, Base Maestra, Gestión de Familias y Redes, Salud y Nutrición, Pedagogía, RAM, RAN, RPP, Bienestarina ni el Expediente Operativo por UCA.

Se implementaron dos capacidades nuevas:

1. **Centro Inteligente de Planeación y Calendario Operativo**, como capa transversal para consolidar actividades sin duplicarlas.
2. **Componente Psicosocial especializado**, como área de trabajo propia del rol PSICOSOCIAL, construida sobre referencias a los expedientes familiares existentes.

El desarrollo sigue la organización del Manual Técnico Modalidad Propia e Intercultural, MT3.PP, versión 2 del 26 de diciembre de 2025. El Manual establece seis componentes de calidad, exige soportes verificables y reconoce el acompañamiento familiar, la movilización comunitaria, la planeación, el seguimiento y la articulación entre componentes.

## 2. Decisiones de arquitectura

### 2.1 Una sola fuente de datos

El Centro de Planeación no crea un segundo calendario. La tabla histórica `calendario_entregables` continúa siendo la fuente canónica de fechas y estados. Las tablas `cpo_*` agregan únicamente reglas, metadatos, dependencias, notificaciones, documentos y auditoría.

El Componente Psicosocial no crea una segunda Base Maestra ni duplica participantes. `ps_expedientes` enlaza los expedientes de `fcr_expedientes_familiares`, los participantes fuente y el Expediente Operativo por UCA.

### 2.2 Separación por rol

- Cada profesional consulta su agenda, UCA y responsabilidades.
- El rol PSICOSOCIAL consulta los expedientes que tiene asignados.
- SUPERADMIN, GERENTE y COORDINADOR disponen de vistas globales autorizadas.
- Un parámetro del navegador no puede elevar una vista profesional a vista de coordinación.

### 2.3 Revisión humana

La plataforma prepara borradores y propone prioridades, pero no inventa hechos, no completa análisis profesionales y no cierra procesos automáticamente. Las aprobaciones y cierres se reservan a roles autorizados.

## 3. Centro Inteligente de Planeación

### 3.1 Fuentes integradas

La sincronización consulta, cuando existen:

- Motor Inteligente de Gestión del Proyecto.
- Salud y Nutrición integral.
- Gestión de Familias y Redes.
- Acciones del Componente Psicosocial.
- Calendario pedagógico.
- Planeación pedagógica.

Los registros espejo del Motor de Gestión se omiten cuando existe una fuente misional directa, evitando que una misma actividad aparezca dos veces.

### 3.2 Reglas configurables

Se incluyen reglas iniciales para:

- Actividad general.
- Jornada de Salud y Nutrición.
- Actividad psicosocial o familiar.
- Actividad pedagógica.

Cada regla puede definir componente, tipo, rol responsable, anticipación de recordatorios, documentos esperados, evidencias y prioridad. Las reglas pueden ampliarse por fundación sin cambiar el código.

### 3.3 Dependencias y semáforos

Una actividad puede depender de otra. Mientras la actividad precedente no esté completa, la dependiente se marca como bloqueada. El tablero calcula semáforos a partir de fechas, estado, bloqueos y pendientes.

### 3.4 Documentos preparados

Desde una actividad se pueden generar como borradores controlados:

- Agenda.
- Acta.
- Listado de asistencia XLSX.
- Informe PDF.

Cada producto conserva fundación, actividad, autor, fecha, tipo MIME, tamaño, SHA-256 y estado. La coordinación puede revisar, aprobar o devolver; la generación nunca equivale a aprobación.

### 3.5 Paquete mensual

El Centro puede producir un ZIP por periodo con:

- Resumen general.
- Resumen por componente.
- Resumen por UCA.
- Relación de actividades.
- Documentos preparados disponibles.
- Archivo de orientación.

## 4. Componente Psicosocial

### 4.1 Expediente referencial

El expediente psicosocial mantiene referencias a:

- Fundación y UCA.
- Expediente familiar.
- Participante original.
- Profesional referente.
- Nivel de acceso.
- Fecha y motivo de apertura.

No se implementó una historia clínica ni se replicaron datos de identidad.

### 4.2 Caracterización versionada

Cada nueva caracterización crea una versión y conserva las anteriores. Puede registrar, según criterio profesional:

- Composición y dinámicas familiares.
- Factores protectores.
- Situaciones a acompañar.
- Redes presentes.
- Barreras de acceso.
- Enfoque diferencial.
- Conclusión y recomendaciones.

Solo una versión queda activa. La coordinación valida o devuelve la versión; la plataforma no emite diagnóstico autónomo.

### 4.3 Planes y acciones

Cada expediente puede tener planes de acompañamiento con objetivo, fechas, prioridad, porcentaje y resultado final. Las acciones se integran al Motor de Gestión y pueden exigir evidencia.

Una acción no puede validarse cuando la evidencia obligatoria está ausente. Un plan no puede cerrarse hasta que sus acciones estén terminadas y exista validación humana.

### 4.4 Actividades y seguimientos

El módulo puede vincular actividades creadas en Gestión de Familias y Redes sin copiarlas. También registra seguimientos con fecha, descripción, resultado, próxima acción y referencia de evidencia.

### 4.5 Informe restringido

El informe psicosocial se genera como borrador PDF y puede limitar el contenido sensible según el rol. La descarga registra una auditoría de acceso.

## 5. Integración con el Expediente Operativo por UCA

La vista única por UCA incorpora dos dominios adicionales:

- `planeacion_operativa`
- `psicosocial`

Con ellos, el expediente presenta doce dominios integrados y agrega los indicadores:

- Cumplimiento de Planeación Operativa.
- Cobertura de caracterización psicosocial.

También incorpora bloqueos por dependencias de planeación y acciones psicosociales pendientes dentro de la preparación para supervisión.

## 6. Seguridad y privacidad

- Todas las tablas nuevas incluyen `fundacion_id`.
- Los prefijos `cpo_` y `ps_` se añadieron a la migración multi-tenant.
- Las rutas están declaradas en la matriz central de autorización.
- El acceso operativo es fail-closed por UCA.
- Los archivos se guardan dentro de `/data/tenants/<fundacion_id>/` en producción.
- Las descargas validan ruta, existencia, tamaño y SHA-256.
- Los informes psicosociales se consideran restringidos.
- No se registran contraseñas, tokens ni contenido sensible en logs.
- No se modifican datos históricos al generar documentos.

## 7. Compatibilidad PostgreSQL

Los repositorios utilizan la capa `modules.dbapi_compat`, de manera que la aplicación conserva SQLite para recuperación local y PostgreSQL para producción. La auditoría de SQL runtime revisó 1.602 literales SQL y no encontró construcciones incompatibles ni importaciones directas no autorizadas de `sqlite3`.

## 8. Pruebas ejecutadas

- Sincronización psicosocial idempotente.
- Aislamiento entre dos fundaciones.
- Asignación de expedientes por profesional y UCA.
- Versionado de caracterizaciones.
- Validación humana.
- Bloqueo de acciones sin evidencia.
- Cierre controlado de planes.
- Generación e integridad del informe PDF.
- Sincronización del Centro de Planeación sin duplicar fuentes espejo.
- Dependencias y desbloqueo.
- Generación de PDF, XLSX y ZIP.
- Protección contra elevación de vista por parámetro.
- Integración de los dos dominios al Expediente UCA.
- Gate de integridad: 19 pruebas críticas aprobadas.

## 9. Limitaciones de la entrega

La entrega está preparada como versión candidata. No se ejecutaron dentro del entorno de construcción:

- Navegador real sobre Windows con todos los flujos de interfaz.
- PowerShell real.
- Cloudflare Tunnel sobre la red del operador.
- PostgreSQL productivo con datos reales.
- Railway con tráfico real y varios dispositivos.

Debe probarse primero con datos ficticios, en local y después en un servicio de prueba.
