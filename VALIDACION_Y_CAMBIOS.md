# Validación y cambios — PrimeraInfancia 2.6.0

## Salud y Nutrición Integral, PostgreSQL y scripts Windows

- Sistema Integral de Salud y Nutrición por participante y UCA, sin duplicar Base Maestra.
- Control documental de afiliación, vacunación, valoración integral, salud bucal, prenatal, tamizaje y discapacidad cuando aplique.
- Validación profesional versionada de valoraciones y CAPTURE XLSX/PDF en borrador controlado.
- Jornadas con actas, listados, informes, asistencia, evidencias y seguimiento.
- Canalizaciones y rutas con cierre humano y soporte obligatorio.
- Engine central SQLite/PostgreSQL, pool psycopg y capa de compatibilidad temporal.
- Herramienta no destructiva de migración SQLite → PostgreSQL con respaldo, SHA-256, lotes, secuencias y conteos.
- Respaldo/restauración PostgreSQL mediante pg_dump/pg_restore.
- BAT pequeños CRLF que delegan en PowerShell, corrigiendo fragmentación y truncamiento del script anterior.
- Diagnóstico de inicio Windows, puerto, Python, base, cloudflared y herramientas PostgreSQL.
- Pruebas específicas de compatibilidad, migración, scripts, Salud Integral y regresión.

# Validación y cambios — PrimeraInfancia 2.5.4


## Cambios de 2.5.4 — Supervisión, Auditoría, Calidad y Familias/Redes

- Centro de Supervisión por UCA con 14 criterios base, hallazgos, planes, acciones, seguimientos y evidencias.
- Productos de supervisión en Excel, PDF y ZIP, siempre en borrador y con validación humana.
- Módulo de Familias, Comunidad y Redes para el rol psicosocial, con sincronización idempotente desde Base Maestra.
- Generación de actas PDF, listados XLSX e informes PDF a partir de datos registrados, sin inventar resultados.
- Compromisos, alertas y redes territoriales integrados con el Motor de Gestión.
- Expediente UCA ampliado a diez dominios.
- Aislamiento multi-fundación y acceso por UCA en modo fail-closed.
- Prueba automatizada específica `test_supervision_familias_redes_v2_5_4.py`.

## Cambios de 2.5.3 — Biblioteca Oficial ICBF y Motor Inteligente de Gestión

- Fuentes documentales autorizadas con verificación remota deshabilitada por defecto.
- Contrato seguro de integración futura mediante catálogo JSON HTTPS y dominios permitidos.
- Detección de versiones candidatas sin activación automática.
- Aprobación, rechazo, historial, notificaciones y relación sugerida con módulos.
- Motor de tareas referenciales e idempotentes sobre Ruta Operativa, calendario y entregables existentes.
- Reglas de prioridad, dependencias, recordatorios y cierres mensuales.
- Preparación de Excel, PDF y ZIP únicamente con información registrada; todos quedan en BORRADOR.
- Revisión y aprobación humana obligatoria, trazabilidad y aislamiento multi-fundación.

# Validación y cambios — PrimeraInfancia 2.5.2

## Cambios de 2.5.2 — Expediente Operativo central por UCA

- Vista única de ocho dominios sin duplicar datos operativos.
- Motor de integración defensivo por fundación y UCA.
- Alertas, cronograma e indicadores consolidados.
- Índice documental referencial e idempotente.
- Descarga restringida a archivos bajo `DATA_DIR`.
- Paquete de supervisión ampliado con indicadores, alertas, cronograma, documentos, componentes y fuentes.
- Prueba específica con dos fundaciones y registros ficticios.

# Validación y cambios — PrimeraInfancia 2.5.1

**Fecha:** 5 de agosto de 2026  
**Base:** PrimeraInfancia 2.5.0 — Gestión Integral por UCA  
**Alcance:** estabilización del login, concurrencia SQLite, sesiones simultáneas, facturación de solo lectura durante autenticación y recuperación del frontend ante esperas.

## Cambios de 2.5.1 — autenticación y concurrencia

- Se combinó la lectura de bloqueo y usuario en una conexión breve.
- La búsqueda exacta utiliza los índices existentes de usuario/correo y conserva un fallback histórico sin distinguir mayúsculas.
- Fallo de credenciales, auditoría y bloqueo se registran en una única transacción.
- Creación de sesión, limpieza del bloqueo, fecha de conexión y auditoría se ejecutan en una única transacción `BEGIN IMMEDIATE`.
- Las sesiones activas de otros dispositivos se preservan; solo se limpian sesiones inactivas o vencidas del usuario actual.
- `SQLITE_BUSY/LOCKED` utiliza reintentos internos acotados, sin convertir la contención en intento fallido ni dejar el navegador esperando 30 segundos.
- Facturación inicializa esquema/semillas una vez por proceso y usa un snapshot de solo lectura en login y middleware.
- SQLAlchemy y el adaptador Core dejaron de renegociar `journal_mode=WAL` en cada conexión.
- El frontend incorpora bloqueo de doble envío, timeout, reintento único para `LOGIN_DATABASE_BUSY` y restauración garantizada del botón.
- Se añadieron métricas de duración y reintentos en cabeceras de respuesta y logs sanitizados.
- Se añadió una prueba de ocho sesiones concurrentes, bloqueo transitorio, bloqueo persistente sin falso rate limit y acceso desde dos dispositivos.

**Compatibilidad:** no se modificaron tablas, columnas, roles, permisos, rutas públicas ni estructura visual.

---

# Validación y cambios — PrimeraInfancia 2.5.0

**Fecha:** 5 de agosto de 2026  
**Base:** PrimeraInfancia 2.4.3 — Túnel Cloudflare corregido  
**Alcance:** Expediente Operativo por UCA, Ruta Operativa, ocho planes, Biblioteca Oficial ICBF, semáforos, evidencias y paquete de supervisión.

## Cambios de 2.5.0 — Gestión Integral por UCA

- Se añadió un Expediente Operativo único por fundación, UCA, vigencia y contrato.
- Se integran resúmenes y enlaces de Base Maestra, Pedagogía, Salud y Nutrición, Talento Humano, Calendario, RAM, RPP, Bienestarina y Reportes sin copiar sus datos.
- Se añadió una Ruta Operativa de 19 actividades: preparación, implementación, cierre y emergencia.
- Se exige evidencia antes de aprobar o cerrar actividades configuradas como documentales.
- Revisión, aprobación, cierre y “No aplica” quedan reservados a coordinación.
- Se sembraron los ocho planes operativos del Manual.
- Se implementaron avance por fase, porcentaje global, vencimientos y semáforo por UCA.
- Las fechas límite pueden sincronizarse de forma idempotente con el calendario existente.
- Se añadió Biblioteca Oficial ICBF con versiones, vigencias, estados, SHA-256, aprobación humana y relaciones con módulos.
- Se añadió generación de paquete ZIP de supervisión por UCA.
- Evidencias, documentos y paquetes se almacenan bajo `/data/tenants/<fundacion_id>/`.
- Las descargas verifican el almacenamiento autorizado y dejan auditoría.
- Los prefijos `giu_` y `biblioteca_` fueron incorporados al aislamiento multi-fundación.
- Se añadió una suite funcional SQLite con dos fundaciones y UCA ficticias.

**Límite:** el servidor Flask completo, el navegador, PowerShell, Cloudflare y Railway deben probarse en los entornos correspondientes antes de usar datos reales.

---

# Validación y cambios — PrimeraInfancia 2.4.3

**Fecha:** 4 de agosto de 2026  
**Base:** PrimeraInfancia 2.4.0 multi-fundación piloto seguro  
**Alcance:** túnel Cloudflare, gestión segura de usuarios/fundaciones, login de usuarios nuevos y recuperación de contraseña.


## Cambios de 2.4.3 — enlace Quick Tunnel Cloudflare

- Se eliminó el archivo de configuración vacío y el argumento `--config` del Quick Tunnel.
- `cloudflared` se ejecuta con un `HOME/USERPROFILE` aislado para que un `config.yml` personal no interfiera, sin modificar los archivos del usuario.
- Se fuerza TLS 1.2 en PowerShell y se añadió descarga alternativa mediante `curl.exe`.
- Primer intento con protocolo `auto`; segundo intento explícito con `http2` cuando QUIC/UDP no funciona.
- Se capturan `stdout` y `stderr` por intento y se analiza DNS, conexión al origen, QUIC y configuración.
- El enlace no se entrega hasta comprobar `/api/health`, el frontend, la huella de la copia y `PUBLIC_TUNNEL_MODE=true`.
- Se añadió diagnóstico del proceso `cloudflared`, puerto TCP 7844, archivos de configuración personales y logs reales en `logs_tunel`.
- Se conserva el comando efectivo en `.runtime_windows/ULTIMO_COMANDO_CLOUDFLARED.txt` para facilitar soporte.

**Causa reproducible corregida:** la versión 2.4.2 pasaba una configuración explícita al Quick Tunnel. Cloudflare documenta que los Quick Tunnels no necesitan configuración y no son compatibles cuando existe una configuración activa.

---

## Cambios de 2.4.2 — login por túnel y logs

- `/api/health` informa una huella de copia `project_instance_id`.
- El inicio local exige que puerto, huella y modo correspondan a la carpeta actual.
- El túnel reinicia una copia antigua o en modo local antes de publicar.
- La validación pública compara la misma huella y `PUBLIC_TUNNEL_MODE=true`.
- Los errores globales se escriben atómicamente en `data/logs`; si ese destino falla, se intenta `data/logs_fallback` y se imprime el traceback en la consola.
- Los reportes incluyen un `trace_id`, versión, etapa segura del login y metadatos sanitizados, sin cuerpo JSON, cookies, contraseñas ni tokens.
- El frontend muestra el código del error y la referencia relativa del archivo real.
- El login diferencia una base SQLite ocupada y responde `503 LOGIN_DATABASE_BUSY` en lugar de un 500 genérico.
- `PRAGMA journal_mode=WAL` se configura una sola vez por proceso para evitar bloqueos exclusivos en cada petición.
- Se añadieron `DIAGNOSTICAR_LOGIN_TUNEL.bat` y `ABRIR_LOGS_ERRORES.bat`.

**Alcance del diagnóstico:** no se recibió un traceback vigente del fallo observado; los archivos revisados estaban vacíos o correspondían a otra carpeta. Por eso no se atribuye el incidente a una única excepción no demostrada. Se corrigieron los defectos reproducibles de selección de proceso, ubicación de logs, trazabilidad del login y concurrencia SQLite.

---

## Cambios de 2.4.1

- El arranque local y el túnel comprueban `/api/health`, no una ruta autenticada.
- El túnel analiza todos los canales de log de `cloudflared`, valida la URL pública y guarda su PID.
- Si el backend estaba en modo local, el túnel lo reinicia con controles adecuados para exposición temporal.
- Gestión de usuarios: crear, editar, activar, desactivar, eliminar lógicamente, restaurar y restablecer contraseña.
- Gestión de fundaciones: editar, suspender, activar, eliminar lógicamente y restaurar con revisión de dependencias.
- Usuarios nuevos: normalización, detección de duplicados sin distinguir mayúsculas, validación del hash y limpieza de bloqueos anteriores.
- Recuperación: enlace por correo de un solo uso, código exclusivamente local sin túnel y restablecimiento administrativo.
- Aislamiento por fundación aplicado a listados, edición, eliminación y restablecimiento.
- Protección del último `SUPERADMIN`, de la sesión propia y de la última fundación activa.
- El inicio local ya no contiene una contraseña administrativa ni claves de sesión fijas: genera secretos aleatorios persistentes y, para una base nueva, una contraseña inicial aleatoria de un solo arranque guardada temporalmente fuera de Git.
- El script no afirma que la credencial de arranque siga siendo válida cuando detecta una base existente y obliga a cambiar la contraseña de una instalación nueva.

## Estado de certificación

La entrega pasa validación estática y pruebas SQLite con dos fundaciones ficticias. El script PowerShell debe probarse en Windows con acceso real a Cloudflare. Railway y el túnel deben utilizarse con datos ficticios hasta superar la matriz de aceptación.

---

## Historial heredado de 2.4.0


**Fecha:** 3 de agosto de 2026  
**Base oficial:** versión 2.3.7 Railway limpia operativa  
**Fuente local complementaria:** versión 2.3.6 SAAS Fase 1 con scripts local/túnel  
**Estado:** piloto multi-fundación preparado para pruebas con dos tenants y datos ficticios; no autorizado todavía para información personal real.

## 1. Criterio de construcción

La versión 2.3.7 limpia operativa se mantuvo como base funcional. La entrega local SAAS Fase 1 se utilizó para conservar los scripts de inicio local y túnel. No se copió la base SQLite, usuarios, beneficiarios, cargas, resultados, respaldos, logs, archivos `.env`, contraseñas ni documentos diligenciados.

Proveniencia verificada:

```text
Base funcional 2.3.7: ee9ca7046ac41e610c12397737152b27533bf2075ae6162e9f6fc16dd7b2eb54
Fuente local/túnel aportada: 328800974685d4c0a16ad7914f236fa7e9f5a43c881c718f1d8f59c7e8ac9a44
```

Se reincorporaron solamente:

- nombres, códigos internos y alias de UDS;
- estructura no personal de la minuta RPP;
- una plantilla RAM histórica sanitizada;
- vigencias y reglas necesarias para seleccionar formatos.

## 2. Activos restaurados

### 2.1 Catálogo UDS

- 32 UDS canónicas.
- Códigos internos `UDS-01` a `UDS-32`.
- Alias ortográficos y equivalencias de unidades de demostración.
- Servicio central de normalización.
- Migración SQLite idempotente.
- Siembra de unidades faltantes sin tocar datos personales.

### 2.2 RPP

- Semilla de mayo de 2026.
- 4 grupos.
- 49 productos.
- 17 equivalencias de productos.
- Creación solo cuando no existe una minuta previa.
- Protección contra sobrescritura de minutas operativas.
- Selección estricta por mes y año para impedir reutilizar una minuta de otro periodo.

### 2.3 RAM

- RAM V2 histórica sanitizada hasta el 31 de julio de 2026.
- RAM V3 desde el 1 de agosto de 2026.
- Selección automática por periodo.
- Generación paginada de la versión histórica.
- Preservación de estilos, combinaciones, áreas de impresión y estructura de la plantilla.

## 3. Correcciones Railway

- Resolución de URL pública mediante `PUBLIC_APP_URL`, `FRONTEND_ORIGIN` y `RAILWAY_PUBLIC_DOMAIN`.
- Acceso Compartido muestra el dominio Railway como enlace principal.
- En producción no presenta localhost, puerto 5000 ni enlaces WiFi.
- Diagnóstico autenticado de almacenamiento bajo `/data`.
- Sincronización de semillas hacia el volumen por SHA-256.
- Respaldo automático antes de actualizar una semilla administrada.
- Preservación de plantillas personalizadas en el volumen.
- Marcadores de inicialización y sincronización bajo `/data`.

## 4. Diagnóstico funcional añadido

Se añadió:

```text
GET /api/formatos/diagnostico
```

El endpoint y su botón de interfaz permiten comprobar por UDS y periodo:

- coincidencia de la UDS;
- conteo de participantes sin datos identificables;
- disponibilidad y versión de RPP, Bienestarina y RAM;
- minuta RPP y su periodo;
- motivos que impiden generar;
- ubicación básica de la base y volumen.

También se añadió:

```text
GET /api/acceso/storage-health
```

para comprobar rutas y permisos de escritura. La persistencia real continúa exigiendo una prueba mediante redeploy.

## 5. Seguridad preservada

- No existe contraseña administrativa utilizable dentro del repositorio.
- Los secretos se reciben por variables privadas.
- El administrador inicial solo se crea en una instalación vacía.
- Las variables de arranque no promueven ni restablecen cuentas existentes.
- El primer ingreso obliga a cambiar la contraseña.
- Recuperación con mensaje genérico y token no expuesto en producción.
- Tokens de sesión en encabezados, no en direcciones.
- Límites persistentes de intentos.
- Autorización por roles con denegación por defecto.
- HTTPS, HSTS, CSP, `no-store`, anti-framing y `nosniff` conservados.
- Multifundación habilitada de forma explícita con guard SQL fail-closed, esquema v3 y almacenamiento por tenant.

## 6. Archivos nuevos principales

```text
backend/config/uds_catalog.json
backend/seed_data/config/rpp_minuta_base_2026_05.json
backend/seed_data/templates_originales/oficiales/plantilla_ram_oficial_v2_historica.xlsx
backend/services/uds_catalog.py
backend/services/seed_sync.py
backend/services/ram_historical_service.py
backend/tests/test_operational_release_v2_3_7.py
```

La lista completa se entrega en el informe externo de archivos modificados.

## 7. Pruebas automatizadas ejecutadas

Se ejecutaron satisfactoriamente:

```bash
python -m compileall -q backend
node --check frontend/js/modules/acceso-compartido.js
PYTHONPATH=backend python backend/tests/test_operational_release_v2_3_7.py
PYTHONPATH=backend python backend/tests/test_ram_download_period_wiring.py
PYTHONPATH=backend python backend/tests/test_ram_v3_integration.py
```

Cobertura funcional comprobada:

- 32 UDS y alias críticos;
- migración desde unidades demo;
- siembra idempotente de UDS;
- semilla RPP idempotente;
- 4 grupos y 49 productos RPP;
- 17 equivalencias RPP activas;
- RAM V2 para julio de 2026;
- RAM V3 para agosto de 2026;
- generación sintética de ambos formatos;
- paginación RAM V3 con 21 participantes ficticios;
- preservación de plantilla maestra;
- sincronización, respaldo y preservación de una plantilla personalizada;
- presencia de URL Railway, diagnóstico `/data` y preflight de formatos.

El resultado reproducible final de `tools/validate_release.py` queda consignado en el JSON externo de validación y en el informe de auditoría.

## 8. Privacidad

La plantilla RAM V2 fue sanitizada antes de incorporarla. Se eliminaron:

- datos institucionales de origen;
- NIT y contrato;
- agente educativo;
- UDS, dirección y teléfono;
- nombres, documentos y asistencia de participantes.

El catálogo UDS se considera información operativa, no personal. No se reincorporaron nombres de niños, acudientes, funcionarios, documentos, teléfonos ni credenciales.

## 9. Elementos intencionalmente no restaurados

- Base SQLite privada.
- Usuarios y contraseñas históricas.
- Beneficiarios.
- Cargas y resultados anteriores.
- Respaldos y logs.
- Cuentas de cobro diligenciadas.
- Plantillas con información personal o institucional ya escrita.
- Automatizaciones de túnel como mecanismo principal.
- Datos o archivos personales de otras fundaciones.

## 10. Validaciones todavía obligatorias en Railway y multifundación

1. Confirmar volumen montado en `/data`.
2. Ejecutar prueba de persistencia mediante redeploy.
3. Probar inicio de sesión y cambio de contraseña.
4. Probar RPP, Bienestarina y RAM con una UDS y datos ficticios.
5. Probar un periodo anterior y uno posterior a agosto de 2026.
6. Verificar descargas autenticadas.
7. Probar permisos con cada rol.
8. Revisar logs sin secretos ni datos personales.
9. Probar respaldo y restauración.
10. Medir memoria y tiempo con cargas representativas ficticias.
11. Crear dos fundaciones y comprobar aislamiento total de usuarios, datos, archivos, plantillas, trabajos y descargas.
12. Suspender una fundación y verificar la invalidación inmediata de sus sesiones.

## 11. Límite de certificación

La validación local comprueba código, manifiestos, hojas Office y comportamiento de servicios con datos sintéticos. No reemplaza la prueba integral del contenedor en Railway ni una auditoría legal de tratamiento de datos.

Hasta completar la lista anterior, la versión debe usarse solamente para ensayos controlados con información ficticia.
