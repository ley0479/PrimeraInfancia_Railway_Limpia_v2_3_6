# PrimeraInfancia 2.6.0 — Salud y Nutrición Integral + PostgreSQL

## Base de datos de producción

Use PostgreSQL en Railway mediante `DATABASE_URL`. La aplicación normaliza `postgresql://` al driver `postgresql+psycopg://`, usa pool con `pre_ping`, timeouts y rollback al devolver conexiones. El volumen `/data` continúa siendo necesario para documentos, evidencias, productos y respaldos; ya no es la base transaccional cuando PostgreSQL está activo.

Ejecute la migración primero en un servicio de prueba y conserve el respaldo SQLite.





## Novedad 2.5.4 — Supervisión, auditoría, calidad y gestión familiar

Esta versión incorpora dos módulos integrados con el Expediente UCA y el Motor de Gestión:

- **Supervisión y Calidad:** listas de verificación, hallazgos, planes, acciones, seguimientos, evidencias y productos PDF/XLSX/ZIP.
- **Familias, Comunidad y Redes:** expedientes familiares referenciales, actividades, asistencias, compromisos, redes, alertas, evidencias y borradores documentales.

Los cierres requieren revisión humana, los datos permanecen en sus módulos fuente y toda operación conserva aislamiento por fundación y alcance por UCA.

## Novedad 2.5.3 — Biblioteca controlada y Motor de Gestión

Esta versión amplía la Biblioteca Oficial ICBF con fuentes controladas, candidatos de actualización, aprobación manual, historial y notificaciones. La verificación remota queda deshabilitada por defecto y solo admite un catálogo JSON oficial, HTTPS y expresamente autorizado. También incorpora el Motor Inteligente de Gestión del Proyecto para consolidar tareas, responsables, entregables, recordatorios, productos operativos y cierres mensuales sin duplicar los datos de los módulos fuente. Todos los productos se generan como borradores y requieren revisión humana.


## Novedad 2.5.2 — Expediente Operativo central

La vista por UCA ahora integra en vivo Base Maestra, Pedagogía, Salud y Nutrición, RAM/RPP/Bienestarina, Talento Humano, documentos, cronograma, alertas, indicadores y preparación para supervisión. La integración usa referencias y consultas de solo lectura; no crea una segunda Base Maestra ni duplica archivos.

## Novedad 2.5.1

Esta versión conserva íntegramente la Gestión Integral UCA 2.5.0 y estabiliza el inicio de sesión bajo concurrencia SQLite. El login combina sus lecturas y escrituras en transacciones breves, aplica reintentos internos con presupuesto acotado, preserva sesiones activas de distintos dispositivos, evita que facturación ejecute mantenimiento durante el acceso y agrega tiempo límite/reintento controlado en el navegador. No cambia tablas, roles, permisos ni flujos funcionales.


## Novedad 2.5.0

Esta versión incorpora el Expediente Operativo por UCA, la Ruta Operativa por fases, los ocho planes integrados, la Biblioteca Oficial ICBF versionada y paquetes de supervisión con manifiesto de evidencias. Conserva las correcciones de túnel, autenticación, multifundación y Railway de las versiones anteriores.

Esta es la **versión candidata de trabajo** del proyecto PrimeraInfancia para habilitar varias fundaciones con aislamiento lógico y físico. Parte de la edición 2.3.7 Railway limpia operativa y conserva los scripts locales y de túnel de la línea SAAS Fase 1. La entrega está preparada para pruebas controladas con dos fundaciones y datos ficticios; todavía no está autorizada para información personal real.

La entrega no contiene bases de datos operativas, beneficiarios, usuarios históricos, cargas, resultados, respaldos, logs, archivos `.env`, contraseñas ni documentos diligenciados del proyecto privado.

> Use datos ficticios hasta comprobar roles, persistencia, respaldo, restauración y funcionamiento de cada formato en el dominio público.

## 1. Cambios acumulados y ajustes hasta la versión 2.5.1

- Catálogo central de **32 UDS**, con códigos internos y alias de escritura.
- Migración idempotente de valores `UNIDAD DEMO 01..32` hacia las UDS operativas.
- Semilla sanitizada de la minuta RPP de mayo de 2026: **4 grupos, 49 productos y 17 equivalencias**.
- Plantilla RAM V2 histórica sanitizada para periodos hasta julio de 2026.
- Plantilla RAM V3 para agosto de 2026 en adelante.
- Selección automática de RAM según mes y año.
- Sincronización de plantillas administradas por hash, con respaldo y sin sobrescribir personalizaciones del usuario.
- Acceso Compartido orientado primero al dominio público de Railway.
- Diagnóstico del volumen `/data`.
- Diagnóstico previo de RPP, Bienestarina y RAM sin mostrar datos personales.
- Interfaz para ejecutar el diagnóstico previo por UDS antes de procesar la base.
- Seguridad, autorización por roles, límites de intentos y secretos de la versión limpia preservados.
- Creación administrada de varias fundaciones por `SUPERADMIN`.
- Esquema multi-fundación v3 con migración idempotente y claves únicas compuestas por `fundacion_id`.
- Cortafuegos SQL para SQLite y SQLAlchemy Core con validación de parámetros explícitos.
- Carpetas independientes bajo `/data/tenants/<fundacion_id>/`.
- Inicialización independiente de suscripción, corporación, UDS, reglas y minuta RPP para cada nueva fundación.
- Invalida sesiones cuando una fundación o un usuario se suspende.
- Gestión de usuarios con edición, activación, desactivación, eliminación lógica y diagnóstico de dependencias.
- Gestión de fundaciones con edición, suspensión, restauración y eliminación lógica segura.
- Restablecimiento administrativo con contraseña temporal de un solo uso visual y cambio obligatorio.
- Recuperación pública por correo con token hash, expiración, uso único y respuesta genérica.
- Código local alternativo únicamente en desarrollo, desde loopback y sin túnel activo.
- Quick Tunnel Cloudflare corregido y verificado mediante `/api/health`; no se usa como hosting estable.
- Huella `project_instance_id` para impedir que el túnel publique otra copia que ocupe el puerto 5000.
- Logging global rotativo y reportes atómicos no vacíos bajo `data/logs`, con ocultamiento de secretos.
- Login con identificador de solicitud, contexto por etapas y respuesta 503 cuando SQLite está temporalmente ocupado.
- Diagnóstico Windows para comparar instancia local/pública y localizar el log correcto.

## 2. Estructura relevante

```text
backend/
├── config/uds_catalog.json
├── seed_data/
│   ├── config/rpp_minuta_base_2026_05.json
│   └── templates_originales/
│       ├── seed_manifest.json
│       └── oficiales/
│           ├── plantilla_rpp_oficial.xlsx
│           ├── plantilla_bienestarina_oficial.xlsx
│           ├── plantilla_ram_oficial_v2_historica.xlsx
│           ├── plantilla_ram_oficial_v3.xlsx
│           └── templates_manifest.json
├── services/
│   ├── uds_catalog.py
│   ├── seed_sync.py
│   ├── rpp_minutas_service.py
│   └── ram_historical_service.py
└── init_hosting.py
```

Los archivos de `backend/seed_data/` son semillas sanitizadas. En Railway se sincronizan hacia el volumen persistente en el primer arranque y cuando cambia una semilla administrada.

## 3. Requisitos obligatorios en Railway

La aplicación utiliza SQLite y genera archivos. Por eso necesita:

1. Un único servicio conectado al repositorio privado de GitHub.
2. Un volumen persistente montado exactamente en:

```text
/data
```

3. Una sola réplica mientras se utilice SQLite.
4. Un solo worker Gunicorn; `start_hosting.sh` ya lo configura.
5. Un dominio público HTTPS generado en Railway.
6. Variables privadas configuradas desde el panel, nunca dentro del repositorio.

## 4. Variables recomendadas

Use `.env.example` únicamente como inventario. En Railway configure, como mínimo:

```env
APP_ENV=production
APP_VERSION=2.5.2-expediente-uca-central
DATA_DIR=/data
PROJECT_INSTANCE_ID=
SYNC_MANAGED_TEMPLATES=true

SINGLE_TENANT_MODE=false
ALLOW_EXPERIMENTAL_MULTI_TENANT=true
MULTI_TENANT_STRICT=true
TENANT_STORAGE_ISOLATION=true
MULTI_TENANT_SCHEMA_VERSION=3

SECRET_KEY=<secreto aleatorio de 64+ caracteres>
JWT_SECRET_KEY=<otro secreto diferente de 64+ caracteres>

INITIAL_ADMIN_USERNAME=<usuario inicial>
INITIAL_ADMIN_EMAIL=<correo administrativo válido>
INITIAL_ADMIN_PASSWORD=<contraseña inicial fuerte>
INITIAL_ADMIN_NAME=<nombre administrativo>
INITIAL_ADMIN_FORCE_PASSWORD_CHANGE=true
INITIAL_FOUNDATION_NAME=Fundación piloto inicial

RAILWAY_PUBLIC_DOMAIN=<dominio generado por Railway>
PUBLIC_APP_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
FRONTEND_ORIGIN=https://${{ RAILWAY_PUBLIC_DOMAIN }}
PASSWORD_RESET_PUBLIC_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
TRUSTED_PROXY_COUNT=1
FORCE_HTTPS=true

ALLOW_LEGACY_QUERY_TOKENS=false
ALLOW_PASSWORD_RESET_TOKEN_RESPONSE=false
ALLOW_LOCAL_RECOVERY_CODE=false
LOCAL_RECOVERY_CODE_LENGTH=10
RESET_MAX_ATTEMPTS=8
RESET_WINDOW_SECONDS=900
RESET_LOCK_SECONDS=900
ENABLE_LEGACY_TENANT_BACKFILL=false
```

Genere cada secreto por separado:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

No copie secretos en GitHub, capturas, chats ni archivos del proyecto.

## 5. Primer despliegue

1. Cree o abra el repositorio privado conectado a Railway.
2. Reemplace su copia local por esta versión o integre sus cambios mediante Git.
3. Confirme que el volumen exista y esté montado en `/data`.
4. Configure las variables anteriores.
5. Haga `commit` y `push` a la rama conectada.
6. Railway construirá y desplegará automáticamente.
7. Revise los logs de inicialización.
8. Abra `/api/health`; debe responder `status: ok`.
9. Abra el dominio raíz e inicie sesión con el administrador inicial.
10. Cambie la contraseña cuando la plataforma lo solicite.

El inicializador:

- verifica SHA-256 de las semillas;
- crea las carpetas persistentes;
- inicializa y migra el esquema SQLite;
- migra nombres `UNIDAD DEMO` hacia el catálogo central;
- registra las 32 UDS que no existan;
- carga la minuta RPP solamente si no hay una minuta previa;
- sincroniza plantillas administradas sin sobrescribir una plantilla personalizada;
- crea el SUPERADMIN solamente en una instalación vacía.

## 6. Confirmar el volumen `/data`

La ruta autenticada:

```text
GET /api/acceso/storage-health
```

comprueba que:

- la base esté dentro de `DATA_DIR`;
- las carpetas requeridas sean escribibles;
- existan los marcadores de inicialización y sincronización;
- Railway haya declarado la ruta del volumen cuando esté disponible.

La misma comprobación está disponible en **Acceso Compartido → Comprobar /data**.

La comprobación automática no puede demostrar por sí sola que el almacenamiento sobreviva a un redeploy. Haga esta prueba controlada:

1. Cree un registro completamente ficticio.
2. Anote un identificador no personal.
3. Ejecute un redeploy.
4. Confirme que el registro permanezca.
5. Elimine el registro ficticio.

No cargue información real antes de superar esta prueba.

## 7. Catálogo central de UDS

El archivo:

```text
backend/config/uds_catalog.json
```

contiene nombres operativos, códigos internos y alias. No contiene beneficiarios, documentos, teléfonos, direcciones, funcionarios ni credenciales.

Todos los módulos deben usar `backend/services/uds_catalog.py`. No vuelva a crear listas de UDS dentro de archivos Python o JavaScript.

Para agregar o corregir una UDS:

1. Edite solo `uds_catalog.json`.
2. Mantenga único el `codigo_interno`.
3. Añada variantes al arreglo `alias`.
4. Ejecute las pruebas.
5. Haga commit y push.

La migración es idempotente: puede ejecutarse en cada arranque sin duplicar unidades ni alterar campos personales.

## 8. RPP

La semilla de configuración se encuentra en:

```text
backend/seed_data/config/rpp_minuta_base_2026_05.json
```

Incluye únicamente configuración de grupos, productos y cantidades. No incluye participantes ni datos institucionales.

El esquema también instala 17 equivalencias de nombres de producto para reconocer variantes como pasta/pastas, plátano/platano, lácteo/leche y otros encabezados de la plantilla.

Comportamiento:

- se crea solo cuando la base no tiene ninguna minuta RPP;
- no reemplaza una minuta cargada posteriormente por un usuario;
- la generación exige plantilla, UDS reconocida, participantes y una minuta del mismo mes y año;
- no reutiliza silenciosamente una minuta de otro periodo;
- el diagnóstico previo informa por qué no está listo el RPP.

Cuando exista una nueva minuta oficial, cárguela desde el módulo administrativo y verifique su periodo. No reemplace la base SQLite desde GitHub.

## 9. RAM histórico y RAM V3

La selección se hace por periodo:

| Periodo | Plantilla |
|---|---|
| Hasta julio de 2026 | RAM V2 histórica sanitizada |
| Desde agosto de 2026 | RAM V3 |

Los rangos se declaran en:

```text
backend/seed_data/templates_originales/oficiales/templates_manifest.json
```

No modifique artificialmente la vigencia de RAM V3 para procesar meses anteriores. Añada una versión nueva con su rango correcto cuando cambie el formato oficial.

## 10. Sincronización segura de plantillas

`backend/services/seed_sync.py` mantiene un estado en:

```text
/data/.primera_infancia_seed_state.json
```

Reglas:

- copia semillas nuevas;
- actualiza una semilla administrada cuando cambió en GitHub y el archivo desplegado seguía intacto;
- crea una copia anterior bajo `/data/backups/seed_sync_*`;
- preserva un archivo modificado por el usuario;
- registra hashes de origen y desplegados;
- puede ejecutarse repetidamente.

Si se necesita forzar una revisión, primero descargue y conserve la plantilla del volumen. No borre `/data` para actualizar una sola plantilla.

## 11. Diagnóstico previo de formatos

En la sección de procesamiento aparece el botón:

```text
Diagnóstico previo de formatos
```

Después de detectar o seleccionar una UDS, informa:

- coincidencia con el catálogo central;
- número de participantes, sin nombres ni documentos;
- plantilla y versión aplicable de RPP, Bienestarina y RAM;
- estado de la minuta RPP;
- causas que impedirían la generación;
- situación básica del volumen `/data`.

La API correspondiente es:

```text
GET /api/formatos/diagnostico?unidad=<UDS>&mes=<1-12>&anio=<AAAA>
```

Está protegida por autenticación y devuelve solamente conteos y configuración técnica.

## 12. Acceso Compartido

En producción, el módulo utiliza este orden:

1. `PUBLIC_APP_URL`
2. `FRONTEND_ORIGIN`
3. `RAILWAY_PUBLIC_DOMAIN`
4. origen HTTPS de la petición

El panel muestra el dominio público de Railway y oculta instrucciones de localhost, puerto 5000 y red WiFi. Los campos históricos de túnel se conservan únicamente para compatibilidad con el frontend anterior.

## 13. Flujo para actualizar la plataforma

Trabaje siempre sobre una sola copia local conectada al repositorio oficial:

1. Abra GitHub Desktop.
2. Seleccione el repositorio de PrimeraInfancia.
3. Use `Fetch origin` y luego `Pull origin` antes de editar.
4. Cree una rama para el módulo, por ejemplo:

```text
mejora/rpp-diagnostico
```

5. Realice y pruebe un cambio pequeño.
6. Ejecute:

```bash
python tools/validate_release.py
```

7. Revise la lista de cambios.
8. Haga commit con un mensaje concreto.
9. Publique la rama o haga push a la rama acordada.
10. Revise el despliegue de Railway y los logs.
11. Pruebe el módulo desde el dominio público.
12. Conserve el último commit estable para poder revertir.

Nunca edite archivos dentro de Railway ni copie una versión completa encima de `/data`.

## 14. Pruebas incluidas

```bash
python tools/validate_release.py
PYTHONPATH=backend python backend/tests/test_operational_release_v2_3_7.py
PYTHONPATH=backend python backend/tests/test_ram_download_period_wiring.py
PYTHONPATH=backend python backend/tests/test_ram_v3_integration.py
PYTHONPATH=backend python backend/tests/test_multitenant_phase3.py
PYTHONPATH=backend python backend/tests/test_multitenant_release_v2_4_0.py
```

Las pruebas cubren estructura, sintaxis, manifiestos, seguridad, catálogo UDS, migración, minuta RPP, RAM V2/V3, sincronización de semillas y conexión de los diagnósticos.

## 15. Piloto multi-fundación

Esta entrega incorpora aislamiento lógico y físico con configuración explícita:

```env
SINGLE_TENANT_MODE=false
ALLOW_EXPERIMENTAL_MULTI_TENANT=true
MULTI_TENANT_STRICT=true
TENANT_STORAGE_ISOLATION=true
MULTI_TENANT_SCHEMA_VERSION=3
```

El modo multi-fundación no depende del plan de Railway. La aplicación exige las cinco variables anteriores y falla cerrada cuando falta alguna protección. Cada fundación debe contar con usuarios propios, datos filtrados por `fundacion_id` y carpetas separadas bajo `/data/tenants/<id>/`.

Antes de datos reales, ejecute la prueba de aceptación con dos fundaciones descrita en `GUIA_PRUEBAS_MULTIFUNDACION_RAILWAY_v2_4_0.md`. Esta entrega es un piloto técnico, no una certificación definitiva de privacidad.

## 16. Límites y operación responsable

- El contenedor completo debe validarse en Railway con Flask, Gunicorn, OCR, PDF y las dependencias de producción.
- SQLite requiere una sola réplica y un solo worker.
- Procesamientos grandes pueden exceder memoria o tiempo del plan de ensayo.
- El frontend heredado todavía utiliza Tailwind Play CDN; para una operación final debe compilarse CSS estático.
- La entrega está sanitizada, pero la privacidad futura depende de los archivos y datos que los usuarios carguen.
- Antes de información real, pruebe roles, bloqueo, respaldos, restauración, persistencia, descarga y manejo de incidentes.