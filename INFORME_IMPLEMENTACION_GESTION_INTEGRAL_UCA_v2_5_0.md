# Informe de implementación — PrimeraInfancia 2.5.0 Gestión Integral por UCA

**Fecha de preparación:** 5 de agosto de 2026  
**Versión fuente:** 2.4.3 — Túnel Cloudflare corregido  
**Versión resultante:** 2.5.0 — Gestión Integral UCA  
**Base normativa funcional:** Manual Técnico Modalidad Propia e Intercultural para la Atención a la Primera Infancia, MT3.PP, versión 2, 26/12/2025.

## 1. Objetivo atendido

Evolucionar la plataforma sin reemplazar los módulos existentes, incorporando tres capacidades coordinadas:

1. **Expediente Operativo por UCA** como vista integradora.
2. **Ruta Operativa por fases** con checklist, evidencias, responsables y semáforos.
3. **Biblioteca Oficial ICBF** con control de versiones, vigencias, integridad y aprobación humana.

La implementación conserva Base Maestra, Gestión Pedagógica, Salud y Nutrición, RAM, RPP, Bienestarina, Talento Humano, Calendario, reportes, autenticación, multifundación, Railway y Quick Tunnel. El nuevo módulo consulta y resume esas fuentes; no crea una segunda Base Maestra ni copia los registros misionales.

## 2. Fundamento funcional del Manual

El Manual organiza la operación mediante seis componentes de calidad: Familia, Comunidad y Redes Sociales; Salud y Nutrición; Proceso Pedagógico; Talento Humano; Ambientes Educativos y Protectores; y Administrativo y de Gestión (página 56).

La ruta operativa se estructura en tres fases: preparatoria, implementación del servicio y cierre (página 72). La fase preparatoria incluye ocho actividades: concertación; talento humano e inducción; articulación interinstitucional; espacios y dotación; formalización de población; presupuesto; proveedores de alimentos; y contrapartida, cuando aplique (página 73).

La planeación de implementación incluye ocho planes articulados y una bitácora mensual por UCA (páginas 80 y 81). El cierre exige consolidación documental, custodia, transferencia, inventario y evidencia de los productos de la operación (páginas 81 y 82).

## 3. Arquitectura implementada

### 3.1 Nuevo dominio funcional

Se creó el módulo:

```text
backend/modules/gestion_integral_uca/
├── __init__.py
├── schema.py
├── services.py
├── repository.py
└── routes.py
```

Responsabilidades:

- `schema.py`: modelo de datos idempotente y ocho planes iniciales.
- `services.py`: catálogo de la ruta, estados, fases, roles, evidencias y cálculos.
- `repository.py`: persistencia SQLite, integración de fuentes, versionado y paquetes.
- `routes.py`: API, control de acceso, carga segura y descargas autenticadas.

### 3.2 Modelo de datos

Tablas añadidas:

```text
giu_expedientes_uca
giu_ruta_catalogo
giu_ruta_instancias
giu_ruta_evidencias
giu_planes_uca
giu_auditoria
giu_schema_version
biblioteca_icbf_documentos
biblioteca_icbf_versiones
biblioteca_icbf_relaciones
```

Todas las tablas operativas nuevas incluyen `fundacion_id`. Sus prefijos fueron incorporados a la migración y al control multi-tenant existente.

### 3.3 Interfaz

Se añadieron dos secciones:

- **Expediente Operativo**.
- **Biblioteca Oficial ICBF**.

Archivos principales:

```text
frontend/css/gestion-integral-uca.css
frontend/js/modules/gestion-integral-uca.js
```

La SPA inicializa cada sección desde `frontend/js/app.js` y aplica los menús autorizados por rol.

## 4. Fase 1 — Expediente Operativo por UCA

Cada expediente queda identificado por:

- fundación;
- UCA/UDS;
- vigencia;
- contrato;
- modalidad o servicio;
- fase actual;
- porcentaje global;
- semáforo;
- coordinador y trazabilidad.

### Integración sin duplicación

El expediente consulta dinámicamente las estructuras existentes y presenta resúmenes y enlaces de navegación para:

- Base Maestra y participantes.
- Gestión Pedagógica.
- Salud y Nutrición.
- Talento Humano.
- Calendario inteligente.
- RAM, RPP y Bienestarina.
- Reportes y supervisión.

La sincronización de UCA es idempotente. La llave única es:

```text
fundacion_id + unidad_clave + vigencia + contrato
```

Un usuario operativo solo recibe las UCA que tenga asignadas cuando esa asignación existe. Una lista de asignación vacía no se interpreta como acceso global.

## 5. Fase 2 — Ruta Operativa

Se implementó un catálogo inicial de **19 actividades**:

- 8 preparatorias.
- 6 de implementación y seguimiento.
- 4 de cierre.
- 1 transversal para flexibilización por emergencia o desastre.

Cada actividad conserva:

- fase y orden;
- componente;
- obligatoriedad;
- roles responsables;
- evidencia esperada;
- responsable;
- fechas;
- estado;
- porcentaje;
- observaciones;
- justificación de “No aplica”;
- revisión y aprobación;
- historial de auditoría.

### Estados y controles

Estados soportados:

```text
PENDIENTE
EN_PROCESO
PENDIENTE_EVIDENCIA
PENDIENTE_REVISION
DEVUELTA
APROBADA
CERRADA
NO_APLICA
```

Reglas relevantes:

- No se aprueba o cierra una actividad que exige evidencia si no existe al menos un archivo válido.
- “No aplica” exige justificación.
- Revisión, devolución, aprobación, cierre y “No aplica” están reservados a roles de coordinación.
- Los archivos se versionan, se pesan nuevamente y se calcula SHA-256 desde el archivo realmente guardado.
- Las descargas verifican que el archivo esté dentro del almacenamiento del tenant.
- Cada descarga queda auditada.

### Avance y semáforos

El expediente calcula:

- progreso ponderado;
- actividades vencidas;
- actividades devueltas o bloqueadas;
- avance por fase;
- fase actual;
- semáforo verde, amarillo o rojo.

Cuando la tabla de calendario existente lo permite, las actividades con fecha límite generan o actualizan un entregable con clave idempotente.

## 6. Ocho planes integrados

Cada expediente crea una sola vez:

1. Plan de articulación interinstitucional y comunitaria.
2. Plan de formación y acompañamiento a las familias.
3. Proyecto pedagógico.
4. Plan de saneamiento básico.
5. Plan de gestión de riesgos de accidentes.
6. Plan de gestión de riesgos de desastres.
7. Plan de cualificación del talento humano intercultural.
8. Plan de gestión de calidad de la atención.

Cada plan maneja responsable, estado, periodo, progreso, objetivos, actividades, indicadores y observaciones. La aprobación y el cierre corresponden a coordinación.

## 7. Fase 3 — Biblioteca Oficial ICBF

La biblioteca implementa:

- catálogo por código, modalidad y componente;
- versiones históricas;
- fechas de documento y vigencia;
- estados borrador, aprobada, vigente, histórica o retirada;
- archivo controlado o URL oficial de referencia;
- tamaño, MIME y SHA-256;
- notas de cambio;
- aprobación y activación de versión vigente;
- relación de cada documento con módulos de la plataforma.

La versión no realiza extracción automática de una intranet ni navegación autenticada. Queda preparada para conectores futuros únicamente cuando exista un mecanismo oficial, documentado y autorizado. La activación de una nueva versión siempre requiere decisión humana.

## 8. Paquete de supervisión

Los roles de coordinación pueden generar un ZIP por expediente con:

```text
00_RESUMEN_EXPEDIENTE.json
01_RUTA_OPERATIVA.csv
02_OCHO_PLANES.csv
03_MANIFIESTO_EVIDENCIAS.csv
04_TRAZABILIDAD.csv
LEEME.txt
```

El paquete se almacena en:

```text
/data/tenants/<fundacion_id>/archivos_actualizados/gestion_integral_uca/
```

Incluye las evidencias disponibles, pero no sustituye la revisión del supervisor o interventor.

## 9. Roles y seguridad

Acceso de consulta:

- SUPERADMIN.
- GERENTE.
- COORDINADOR.
- AUXILIAR_ADMINISTRATIVO.
- DOCENTE.
- NUTRICIONISTA.
- PSICOSOCIAL.

Capacidades de coordinación:

- crear y sincronizar expedientes;
- revisar, devolver, aprobar y cerrar actividades;
- aprobar o cerrar planes;
- generar paquetes de supervisión.

Administración de biblioteca:

- SUPERADMIN y GERENTE;
- AUXILIAR_ADMINISTRATIVO para catálogo y carga;
- activación de versión vigente reservada a SUPERADMIN y GERENTE.

Controles preservados:

- token obligatorio;
- autorización por ruta;
- aislamiento por fundación;
- almacenamiento por tenant;
- protección de descargas;
- auditoría;
- no exposición de secretos en archivos nuevos.

## 10. API añadida

Prefijo:

```text
/api/gestion-integral-uca
```

Principales recursos:

```text
GET  /salud
GET  /unidades
GET  /dashboard
POST /sincronizar
GET|POST /expedientes
GET  /expedientes/<id>
PATCH /expedientes/<id>/ruta/<actividad>
GET|POST /expedientes/<id>/ruta/<actividad>/evidencias
GET  /evidencias/<id>/descargar
PATCH /expedientes/<id>/planes/<plan>
GET  /expedientes/<id>/paquete-supervision
GET|POST /biblioteca/documentos
GET|PUT /biblioteca/documentos/<id>/relaciones
POST /biblioteca/documentos/<id>/versiones
POST /biblioteca/versiones/<id>/activar
GET  /biblioteca/versiones/<id>/descargar
```

## 11. Pruebas realizadas

Se construyó una suite funcional con SQLite temporal y datos ficticios que valida:

- dos fundaciones;
- una UCA con el mismo nombre en ambos tenants;
- filtrado por UCA asignada;
- sincronización idempotente;
- 19 actividades;
- ocho planes;
- evidencia obligatoria;
- calendario;
- biblioteca versionada;
- relaciones biblioteca-módulo;
- paquete de supervisión;
- integración estática de backend, frontend, menús y seguridad.

También se ejecutaron las suites heredadas de multifundación 2.4.0, administración y recuperación 2.4.1, login y logging 2.4.2, y túnel 2.4.3.

## 12. Limitaciones reales

- El entorno de preparación no dispone de Flask instalado; no se levantó el servidor HTTP completo ni se ejecutó una sesión real de navegador.
- PowerShell, `cloudflared.exe`, Docker y Railway no pueden ejecutarse directamente en este entorno Linux.
- Los resúmenes de integración dependen de las tablas realmente existentes en cada instalación y fueron diseñados para tolerar esquemas históricos.
- La Biblioteca ICBF no descarga automáticamente archivos oficiales ni accede a una intranet.
- La implementación no sustituye las guías operativas específicas de cada servicio ni una auditoría jurídica o de protección de datos.

## 13. Pruebas finales obligatorias

Antes de utilizar información real:

1. Respaldar el volumen `/data`.
2. Probar en una rama y servicio Railway separados.
3. Crear dos fundaciones ficticias.
4. Asignar diferentes UCA a usuarios operativos.
5. Confirmar que cada usuario solo vea su fundación y sus UCA autorizadas.
6. Sincronizar expedientes.
7. Cargar y descargar evidencias.
8. Aprobar actividades y planes con un coordinador.
9. Generar el paquete de supervisión.
10. Cargar dos versiones ficticias de un formato y activar una.
11. Reiniciar y desplegar nuevamente para comprobar persistencia.
12. Revisar logs, respaldos y restauración.

## 14. Conclusión

La versión 2.5.0 entrega la arquitectura funcional de las tres primeras fases solicitadas. Convierte los módulos existentes en una vista operativa común por UCA, incorpora la ruta del Manual con evidencia y control de avance, y agrega gobierno documental versionado. La plataforma continúa siendo una candidata para pruebas controladas; la autorización para datos personales requiere completar la matriz de aceptación en Windows, navegador y Railway.
