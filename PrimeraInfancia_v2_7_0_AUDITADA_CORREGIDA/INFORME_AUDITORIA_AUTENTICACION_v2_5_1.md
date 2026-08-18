# Informe de auditoría y corrección de autenticación — PrimeraInfancia 2.5.1

**Fecha:** 5 de agosto de 2026  
**Versión fuente:** PrimeraInfancia 2.5.0 — Gestión Integral por UCA  
**Versión resultante:** PrimeraInfancia 2.5.1 — Autenticación y concurrencia SQLite estabilizadas

## 1. Objetivo

Corregir el inicio de sesión intermitente del administrador y los síntomas:

- permanencia indefinida en `Validando credenciales`;
- respuesta `Base local ocupada temporalmente`;
- falsos bloqueos por intentos;
- dificultad para abrir sesiones simultáneas en dispositivos distintos;
- tiempos de espera incompatibles con un login interactivo;
- poca trazabilidad para distinguir una contraseña incorrecta de una contención SQLite.

La intervención conserva la estructura funcional, las tablas, las columnas, los roles, los permisos, los módulos y la interfaz general.

## 2. Alcance auditado

Se revisaron:

- `POST /api/auth/login`;
- lectura de usuarios y bloqueos de acceso;
- verificación de contraseñas;
- creación y validación de sesiones;
- auditoría de accesos;
- middleware de seguridad;
- middleware y servicios de facturación;
- conexiones SQLite directas;
- conexiones SQLAlchemy Core;
- configuración WAL y `busy_timeout`;
- cliente web del formulario de login;
- scripts de inicio local y túnel;
- pruebas de regresión multi-fundación.

## 3. Causa raíz

El problema no provenía de una única línea. Era el resultado acumulado de varias ventanas de escritura sobre SQLite durante y justo después del login.

### 3.1 Demasiadas transacciones de escritura por login

El flujo anterior utilizaba conexiones separadas para:

1. consultar el límite de intentos;
2. consultar el usuario;
3. limpiar distintas claves del rate limit;
4. insertar la sesión;
5. actualizar la última conexión;
6. registrar auditoría;
7. inicializar o refrescar facturación.

Cada `commit` abría una nueva oportunidad para competir con otras solicitudes del navegador, healthchecks, tareas de fondo o un segundo dispositivo.

### 3.2 Facturación escribía durante el acceso y en solicitudes autenticadas

El servicio de facturación inicializaba esquema, semillas y estados de suscripción con demasiada frecuencia. Después del login, el navegador carga varios endpoints casi al mismo tiempo; esos endpoints podían iniciar escrituras adicionales mientras el login aún estaba terminando.

### 3.3 Negociación repetida de WAL

Tres caminos de conexión podían ejecutar `PRAGMA journal_mode=WAL`:

- conexión de seguridad;
- conexión SQLAlchemy;
- adaptador SQLAlchemy Core.

Cambiar o comprobar el modo de journal puede requerir un bloqueo exclusivo. Hacerlo en cada conexión incrementaba la probabilidad de `SQLITE_BUSY` o `database is locked`.

### 3.4 Tiempo genérico de SQLite demasiado largo para autenticación

Los módulos operativos usan un timeout amplio para cargas y generación de documentos. El login heredaba ese comportamiento, de modo que una contención podía mantener el navegador esperando muchos segundos. El mensaje `Validando credenciales` no tenía límite propio.

### 3.5 Consulta de usuario poco eficiente

La búsqueda utilizaba `lower(username)` y `lower(email)` siempre. Esa expresión impide aprovechar directamente los índices únicos existentes en el caso habitual.

### 3.6 Frontend sin control de solicitud en curso

El formulario no tenía:

- bloqueo contra doble envío;
- `AbortController`;
- timeout;
- reintento controlado;
- restauración garantizada del botón.

Una conexión que no terminara podía dejar visualmente el formulario en `Validando credenciales`.

### 3.7 El bloqueo de credenciales podía confundirse con contención

El rate limit debía escribirse en la misma base que estaba ocupada. Si no se diferenciaba claramente la contención de una contraseña inválida, el usuario podía interpretar el problema como un bloqueo manual o insistir varias veces, activando entonces un bloqueo real.

## 4. Solución aplicada

### 4.1 Política de reintentos exclusiva para login

Se añadieron parámetros independientes:

```env
LOGIN_DB_RETRY_ATTEMPTS=4
LOGIN_DB_BUSY_TIMEOUT_MS=150
LOGIN_DB_RETRY_BASE_MS=50
LOGIN_DB_RETRY_BUDGET_MS=1200
LOGIN_SLOW_THRESHOLD_MS=1500
```

El login usa esperas breves y reintentos acotados. Los módulos que procesan archivos conservan `SQLITE_TIMEOUT_SECONDS`.

### 4.2 Lectura inicial combinada

Bloqueo y usuario se consultan en una sola conexión corta.

La búsqueda usa primero:

```sql
WHERE username=? OR email=?
```

para aprovechar los índices existentes. Solo si no existe coincidencia se aplica el fallback histórico sin distinción de mayúsculas.

No se añadieron índices ni se alteró el esquema.

### 4.3 Fallo de credenciales atómico

Cuando la contraseña es incorrecta, en una sola transacción se registran:

- contador de intentos;
- ventana de bloqueo;
- auditoría de login fallido.

Si SQLite está ocupado y se agota el presupuesto, la transacción se revierte y no se crea un intento falso.

### 4.4 Inicio de sesión exitoso atómico

En una sola transacción `BEGIN IMMEDIATE` se ejecutan:

- limpieza de las claves de bloqueo asociadas a usuario/correo;
- eliminación únicamente de sesiones inactivas o vencidas del usuario actual;
- inserción de la sesión nueva;
- actualización de `fecha_ultima_conexion`;
- auditoría de login exitoso;
- lectura del payload final.

### 4.5 Sesiones simultáneas preservadas

Una sesión nueva no invalida sesiones activas del mismo usuario. Esto permite que el administrador entre desde dos o más dispositivos cuando la política institucional lo autorice.

Las sesiones sí continúan invalidándose cuando:

- el usuario se suspende o elimina;
- la fundación se suspende o elimina;
- se cambia o restablece la contraseña;
- el usuario cierra sesión;
- la sesión expira.

### 4.6 Facturación de solo lectura durante login

El login consulta una instantánea de suscripción sin:

- crear tablas;
- sembrar catálogos;
- refrescar estados en la base;
- modificar `flask.g` antes de terminar la autenticación.

La inicialización de facturación se ejecuta una vez por base y proceso. El middleware autenticado utiliza snapshots de lectura.

### 4.7 WAL inicializado una sola vez

El modo WAL se activa una vez por base/proceso. Las conexiones posteriores configuran solamente:

- `foreign_keys`;
- `busy_timeout`;
- `synchronous`.

El adaptador SQLAlchemy Core dejó de ejecutar `journal_mode` por cada conexión.

### 4.8 Frontend recuperable

El formulario ahora:

- evita envíos dobles;
- desactiva el botón mientras hay una petición;
- cancela la petición después de cinco segundos;
- reintenta una sola vez únicamente ante `503 LOGIN_DATABASE_BUSY`;
- conserva la sesión anterior hasta que el nuevo login sea válido;
- restaura siempre el botón y el estado visual;
- muestra el identificador de solicitud para diagnóstico.

### 4.9 Telemetría segura

Las respuestas exitosas incluyen:

```text
X-Login-Duration-Ms
X-Login-DB-Retries
X-Client-Request-ID
Server-Timing
```

Los logs registran duración, etapa y cantidad de reintentos sin almacenar la contraseña.

## 5. Compatibilidad

No se modificaron:

- tablas ni columnas;
- roles;
- permisos;
- usuarios existentes;
- hashes de contraseña;
- Base Maestra;
- Gestión Integral UCA;
- RAM, RPP o Bienestarina;
- aislamiento multi-fundación;
- rutas públicas existentes;
- estructura visual del login.

## 6. Resultados de pruebas

Pruebas ejecutadas con una base SQLite temporal y datos ficticios:

| Escenario | Resultado |
|---|---:|
| Sesiones solicitadas en paralelo | 8 |
| Sesiones activas preservadas | 8 |
| Tokens únicos | 8 |
| Mayor duración en paralelo | 0,0232 s |
| Duración media en paralelo | 0,0104 s |
| Bloqueo transitorio simulado | 0,35 s |
| Login después del bloqueo | 0,3726 s |
| Reintentos internos observados | 2 |
| Bloqueo persistente simulado | 1,1 s |
| Respuesta acotada ante bloqueo persistente | 0,4116 s |
| Filas falsas de rate limit | 0 |
| Dispositivos probados por la ruta de login | 2 |
| Tokens distintos para esos dispositivos | 2 |

También pasaron las suites heredadas de:

- operación 2.3.7;
- multi-fundación fase 3;
- multi-fundación 2.4.0;
- administración y recuperación 2.4.1;
- login/logging 2.4.2;
- túnel 2.4.3;
- Gestión Integral UCA 2.5.0;
- RAM histórica y RAM V3.

## 7. Respuesta esperada

En condiciones normales, el login devuelve `200` y los encabezados de duración.

Cuando la base está ocupada brevemente, el backend reintenta sin intervención del usuario.

Si la contención supera el presupuesto:

```json
{
  "code": "LOGIN_DATABASE_BUSY",
  "retry_after": 1,
  "request_id": "..."
}
```

La interfaz realiza un solo reintento. No se registra como contraseña inválida.

## 8. Recomendaciones operativas

Mientras se utilice SQLite:

1. Mantener una sola réplica y un solo worker Gunicorn.
2. Mantener el volumen `/data` persistente.
3. No abrir la misma base desde programas externos mientras la plataforma está funcionando.
4. No copiar archivos `database.sqlite3-wal` o `database.sqlite3-shm` por separado.
5. Realizar respaldos mediante el módulo o con la aplicación detenida.
6. Para crecimiento real de múltiples fundaciones y alta concurrencia, planificar PostgreSQL en una fase posterior; no es requisito para esta corrección.

## 9. Plan de reversión

Si la prueba controlada detecta una regresión:

1. detener la plataforma;
2. conservar una copia de `data`;
3. volver a la carpeta 2.5.0;
4. copiar únicamente la misma carpeta `data`;
5. no copiar `.runtime_windows`, `.venv`, logs ni ejecutables de túnel;
6. iniciar la versión anterior.

No hay migración de esquema que revertir.

## 10. Limitaciones de validación

Las pruebas de SQLite, sesiones, rutas mediante dobles de Flask, sintaxis y regresiones se ejecutaron en el entorno de preparación.

No se ejecutaron aquí:

- interfaz real en un navegador Windows;
- PowerShell;
- `cloudflared.exe`;
- contenedor Docker completo;
- Railway con tráfico simultáneo real.

Estas comprobaciones deben realizarse en una copia de prueba antes de usar datos personales reales.
