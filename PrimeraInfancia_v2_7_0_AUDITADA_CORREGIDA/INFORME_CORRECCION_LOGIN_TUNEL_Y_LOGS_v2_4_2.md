# Informe técnico — corrección de login por túnel y logging

**Proyecto:** PrimeraInfancia  
**Versión:** 2.4.2 — túnel, login y logs corregidos  
**Fecha:** 4 de agosto de 2026  
**Base:** 2.4.1 Túnel, Administración y Recuperación Operativa

## 1. Objetivo

Investigar y corregir el fallo que, al iniciar sesión desde el enlace de
Cloudflare Tunnel, mostraba:

```text
Error técnico del servidor. Revisa logs. Error API.
```

También se solicitó reparar los reportes `error_api_*.log` que aparecían vacíos,
sin alterar módulos no relacionados ni reincorporar datos personales.

## 2. Límite de evidencia

No se recibió un traceback vigente del incidente. Los archivos revisados por el
usuario estaban en blanco o se estaban buscando en `backend/logs`, mientras la
configuración operativa utiliza `data/logs`.

Por esa razón, este informe **no atribuye el incidente a una excepción única no
demostrada**. Se identificaron y corrigieron cuatro defectos reproducibles que
podían producir exactamente esa experiencia.

## 3. Defectos encontrados

### 3.1 El túnel podía publicar otra copia del proyecto

La versión anterior aceptaba cualquier respuesta correcta de `/api/health` en el
puerto 5000. No comprobaba que ese proceso perteneciera a la misma carpeta que
se estaba ejecutando.

En un computador con varias copias de PrimeraInfancia, una versión antigua podía
quedar escuchando en el puerto 5000. El túnel entonces publicaba esa otra base y
esas otras credenciales. Los logs del error quedaban en la carpeta de la copia
antigua, no en la carpeta que el usuario estaba inspeccionando.

### 3.2 La ruta operativa de logs no era evidente

El destino de ejecución es:

```text
data/logs
```

La carpeta:

```text
backend/logs
```

es únicamente un marcador vacío del repositorio. El mensaje del frontend no
mostraba el `trace_id` ni la referencia real, y no existía una herramienta para
comprobar que el directorio fuera escribible.

### 3.3 Inicialización repetida de WAL en SQLite

Cada conexión ejecutaba `PRAGMA journal_mode=WAL`. Ese comando puede requerir un
bloqueo exclusivo. Con healthchecks, navegador y login concurrentes a través del
túnel, podía producir un `database is locked` intermitente y terminar en un 500
genérico.

### 3.4 El frontend perdía el contexto técnico

El formulario asumía que toda respuesta era JSON válida. Si el servidor o un
proxy devolvía una respuesta diferente, el propio parseo ocultaba el error
original. Tampoco enviaba un identificador de solicitud ni mostraba el archivo
de log relacionado.

## 4. Correcciones implementadas

### 4.1 Huella de instancia

Se añadió `project_instance_id`, una huella de 16 caracteres que no revela la
ruta del computador. Se publica en `/api/health` y se compara en:

- `INICIAR_PLATAFORMA_LOCAL.bat`;
- `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`;
- `scripts_windows/iniciar_tunel_cloudflare.ps1`;
- `DIAGNOSTICAR_LOGIN_TUNEL.bat`.

El túnel exige simultáneamente:

```text
status = ok
project_instance_id = huella de la carpeta actual
public_tunnel_mode = true
```

Si el puerto pertenece a otra copia o al modo local, se informa y se reinicia de
forma controlada antes de generar el enlace público.

### 4.2 Logging robusto

Se creó `backend/modules/seguridad/runtime_diagnostics.py` con:

- `RotatingFileHandler` para `data/logs/application.log`;
- reportes atómicos `error_api_<trace_id>.log`;
- `flush` y `fsync` antes del renombrado final;
- verificación de que el archivo tenga contenido;
- destino alterno `data/logs_fallback`;
- salida del traceback a la consola si el disco falla;
- ocultamiento de contraseñas, tokens, cookies y encabezados de autorización;
- metadatos seguros: etapa del login, versión, modo e instancia.

El endpoint `/api/health` informa si el destino de logs es escribible.

### 4.3 Login trazable y resistente

El login ahora:

- recibe y devuelve `X-Client-Request-ID`;
- registra la etapa segura en la que ocurrió el fallo;
- trata un hash antiguo o dañado como credencial inválida, no como error 500;
- no bloquea el acceso si el complemento de facturación no está disponible;
- devuelve `503 LOGIN_DATABASE_BUSY` cuando SQLite está ocupado;
- añade `Retry-After: 2`;
- conserva el límite de intentos y el aislamiento por fundación.

### 4.4 SQLite

`journal_mode=WAL` se configura una sola vez por base y proceso. Las conexiones
mantienen `busy_timeout`, claves foráneas y sincronización normal, evitando pedir
un cambio de journal en cada petición.

### 4.5 Mensaje útil en el navegador

El frontend:

- genera un ID de solicitud;
- interpreta de forma segura respuestas JSON o no JSON;
- muestra `trace_id` y la ruta relativa del reporte;
- explica el bloqueo temporal de SQLite;
- dirige a `DIAGNOSTICAR_LOGIN_TUNEL.bat` y `data/logs` cuando corresponde.

### 4.6 Diagnóstico Windows

Se añadieron:

```text
DIAGNOSTICAR_LOGIN_TUNEL.bat
ABRIR_LOGS_ERRORES.bat
scripts_windows/diagnosticar_login_tunel.ps1
```

El diagnóstico no solicita ni guarda credenciales. Comprueba la instancia local
y pública, el modo túnel, la ruta de login con un cuerpo vacío seguro, la
escritura de logs y los reportes no vacíos más recientes.

## 5. Contraseña del túnel

Cloudflare Tunnel **no tiene una contraseña independiente**. El enlace público
expone la misma aplicación y la misma base local. Se inicia sesión con cualquier
usuario válido de esa base.

Si el local acepta una cuenta pero el túnel no, primero debe comprobarse que el
túnel publique la misma `project_instance_id`.

## 6. Seguridad y privacidad

La entrega no contiene:

- bases SQLite operativas;
- archivos `.env` privados;
- contraseñas utilizables;
- tokens o cookies;
- logs de ejecución;
- beneficiarios o usuarios históricos.

Los nuevos reportes nunca guardan el cuerpo del login. Los valores con nombres
como `password`, `token`, `secret`, `authorization` o `cookie` se redactan.

## 7. Validaciones ejecutadas

- Todas las suites heredadas de 2.3.7, 2.4.0 y 2.4.1.
- Login correcto usando un Host `trycloudflare.com` ficticio.
- Hash de contraseña dañado tratado como 401.
- Escritura atómica y no vacía de reportes.
- Redacción de secretos en excepción y traceback.
- Huella de instancia explícita y calculada.
- Contratos estáticos de scripts, healthcheck, frontend y SQLite.
- Sintaxis Python, JavaScript, Bash y JSON.
- Integridad de plantillas Office y manifiestos SHA-256.

## 8. Validación aún necesaria en Windows

Este entorno no puede ejecutar PowerShell ni `cloudflared.exe`. La comprobación
final debe hacerse en Windows:

1. cerrar versiones anteriores;
2. iniciar localmente esta carpeta;
3. iniciar el túnel;
4. confirmar que local y público muestran la misma huella;
5. iniciar sesión desde otro computador con un usuario ficticio;
6. provocar únicamente un error controlado de prueba y confirmar que el reporte
aumente de cero bytes;
7. ejecutar `DIAGNOSTICAR_LOGIN_TUNEL.bat`.

Hasta completar esa prueba, el túnel debe utilizarse solo con datos ficticios.
