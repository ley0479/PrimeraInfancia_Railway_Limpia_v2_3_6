# Informe de auditoría y ajustes — PrimeraInfancia 2.4.1

**Fecha:** 4 de agosto de 2026  
**Base técnica:** PrimeraInfancia 2.4.0 Multi-fundación Piloto Seguro  
**Nueva versión:** `2.4.1-operativa-tunel-admin-recuperacion`  
**Estado:** preparada para aceptación controlada con datos ficticios en Windows, Cloudflare Tunnel y Railway.

## 1. Objetivo de la intervención

La intervención cubre cuatro necesidades concretas:

1. corregir el inicio del túnel temporal para que genere, registre y verifique un enlace público utilizable desde otros equipos;
2. completar la administración de usuarios y fundaciones con edición, activación, suspensión, eliminación segura y restauración;
3. corregir el acceso de usuarios recién creados y reforzar el aislamiento entre fundaciones;
4. implementar recuperación de contraseña por enlace de correo, código estrictamente local o restablecimiento administrativo.

La base SQLite, el login y los módulos existentes se conservaron. Las modificaciones de esquema son aditivas e idempotentes y no sustituyen la base del usuario.

## 2. Hallazgo principal del túnel

El arranque anterior utilizaba `/api/acceso/ping` para decidir si el backend estaba disponible. Esa ruta requiere autenticación y responde `401` antes del login, por lo que el script podía interpretar un servidor saludable como si estuviera caído.

También existían puntos frágiles en la captura del enlace: dependencia de un único flujo de salida, interferencia posible de una configuración global de `cloudflared`, ausencia de validación pública completa y cierre indiscriminado de procesos.

### Corrección aplicada

- El chequeo local utiliza `/api/health`, ruta pública de salud.
- El túnel comprueba primero el backend y el frontend local.
- Si el backend está abierto en modo local, se reinicia en modo túnel para desactivar códigos locales de recuperación.
- `cloudflared` se busca en PATH o se descarga como ejecutable portable oficial para la arquitectura de Windows.
- Se usa una configuración aislada y vacía, sin modificar archivos personales de `.cloudflared`.
- Se capturan `stdout`, `stderr` y el archivo de log propio de `cloudflared`.
- Se extrae el subdominio `trycloudflare.com`, se guarda en `ENLACE_PUBLICO_TUNEL.txt` y se copia al portapapeles.
- Se validan públicamente `/api/health` y `/frontend/index.html` antes de anunciar éxito.
- Se guarda el PID del túnel y solo se detiene el proceso perteneciente a esta plataforma.
- Los errores muestran diagnóstico en español y las últimas líneas de los logs.

## 3. Inicio local y secretos

Se eliminó la credencial local fija y las claves de sesión predecibles del script de inicio.

Para una base local nueva:

- se genera una contraseña aleatoria fuerte para `admin.local`;
- se obliga a cambiarla en el primer ingreso;
- se guarda temporalmente en `.runtime_windows/CREDENCIALES_INICIALES_LOCAL.txt`;
- se generan `SECRET_KEY` y `JWT_SECRET_KEY` aleatorias, distintas y persistentes bajo `.runtime_windows/`;
- el runtime queda excluido de Git, Docker y del ZIP distribuible.

Cuando la base ya existe, el script no reemplaza ni afirma conocer la contraseña registrada.

## 4. Gestión de usuarios

La administración incorpora:

- creación con usuario y correo normalizados;
- detección de duplicados sin distinguir mayúsculas;
- validación de contraseña y del hash generado;
- edición de identidad, rol, fundación, estado y cambio obligatorio de contraseña;
- activación y desactivación;
- eliminación lógica con confirmación y resumen de dependencias;
- restauración;
- restablecimiento administrativo con contraseña temporal mostrada una sola vez;
- cierre de sesiones cuando cambia un dato de seguridad;
- protección de la propia cuenta y del último `SUPERADMIN` activo;
- denegación de acciones cruzadas para administradores sin alcance global.

La eliminación es lógica: se conserva trazabilidad y no se ejecuta un borrado en cascada de datos históricos.

## 5. Gestión de fundaciones

Se añadieron:

- edición controlada;
- activación y suspensión;
- consulta de dependencias antes de eliminar;
- eliminación lógica;
- restauración;
- cierre de sesiones y desactivación de usuarios cuando una fundación se suspende o elimina;
- protección de la fundación de la sesión actual y de la última fundación activa.

No se permite establecer directamente el estado `ELIMINADA` mediante una edición ordinaria; debe usarse la operación controlada de eliminación lógica.

## 6. Login de usuarios nuevos

El inicio de sesión ahora:

- acepta usuario o correo sin diferenciar mayúsculas;
- limpia bloqueos obsoletos asociados al usuario y al correo después de un acceso correcto;
- comprueba cuenta activa, estado de la fundación y hash de contraseña;
- actualiza la última conexión;
- conserva la política de bloqueo ante intentos fallidos.

La creación y edición de usuarios verifican inmediatamente que el hash corresponda a la contraseña suministrada.

## 7. Recuperación de contraseña

### Enlace por correo

- Solicita usuario o correo sin revelar si la cuenta existe.
- Genera un token aleatorio, almacenado únicamente como hash.
- El token expira, es de un solo uso y queda asociado a usuario y fundación.
- Invalida solicitudes anteriores pendientes.
- Envía el enlace mediante la API HTTPS de Resend cuando está configurada.
- El enlace usa Railway o, durante una prueba, el subdominio actual del túnel.
- Al restablecer, invalida sesiones anteriores y elimina bloqueos de login.

### Alternativa local segura

Solo se habilita cuando simultáneamente:

- la aplicación no está en producción;
- no está en modo túnel;
- la solicitud proviene de `127.0.0.1` o `localhost`;
- `ALLOW_LOCAL_RECOVERY_CODE=true`.

El código es aleatorio, se guarda como hash, expira y solo funciona una vez. Nunca se devuelve mediante Railway o el túnel.

### Restablecimiento administrativo

Un administrador autorizado puede generar una contraseña temporal para un usuario de su alcance. La contraseña se muestra una sola vez, obliga a cambiarla y cierra todas las sesiones anteriores.

## 8. Aislamiento multi-fundación

Se conserva el modelo multi-tenant estricto de la versión 2.4.0. Las nuevas acciones verifican `fundacion_id`, rol y alcance antes de leer o modificar cuentas. Las pruebas con dos fundaciones ficticias comprueban que un gerente no puede administrar usuarios de otra fundación.

## 9. Privacidad

El paquete no contiene:

- bases SQLite operativas;
- archivos `.env` privados;
- usuarios, beneficiarios o formularios diligenciados;
- logs o respaldos de ejecución;
- contraseñas iniciales fijas;
- binarios descargados de `cloudflared`;
- archivos de runtime de Windows.

Las plantillas Office mantienen las banderas de sanitización y ausencia de datos reales. El control automatizado de privacidad quedó en `PRIVACIDAD_PRIMERA_INFANCIA_v2_4_1.json`.

## 10. Validación ejecutada

El validador reproducible terminó con **17 PASS, 0 FAIL y 0 SKIP**.

| Control | Resultado |
|---|---:|
| Sintaxis Python | 147 archivos aprobados |
| Sintaxis JavaScript | 32 archivos aprobados |
| Sintaxis Bash | 2 scripts aprobados |
| JSON | 10 archivos aprobados |
| Rutas API revisadas | 318 |
| Familias de autorización | 55 |
| Plantillas sanitizadas | 9 |
| Archivos Office íntegros | 7 |
| Configuración Railway/Docker | Aprobada |
| Aislamiento multi-fundación fail-closed | Aprobado |
| Privacidad y secretos | Aprobado |

Pruebas funcionales ejecutadas:

- migración y aislamiento multi-fundación;
- regresión de la versión 2.4.0;
- activos operativos UDS/RPP/RAM;
- cableado de descarga RAM por periodo;
- integración RAM V3;
- administración, login, eliminación lógica, restauración, recuperación local y túnel 2.4.1.

## 11. Archivos principales de la corrección

- `scripts_windows/iniciar_tunel_cloudflare.ps1`
- `INICIAR_PLATAFORMA_LOCAL.bat`
- `DETENER_PLATAFORMA_LOCAL.bat`
- `backend/modules/seguridad/routes.py`
- `backend/modules/seguridad/schema.py`
- `backend/modules/seguridad/services.py`
- `backend/config.py`
- `backend/app.py`
- `frontend/index.html`
- `frontend/js/app.js`
- `frontend/js/modules/acceso-compartido.js`
- `backend/tests/test_tunnel_admin_recovery_v2_4_1.py`

El inventario completo se encuentra en `ARCHIVOS_MODIFICADOS_PRIMERA_INFANCIA_v2_4_1.md`.

## 12. Configuración de Railway

Mantener como mínimo:

```env
APP_VERSION=2.4.1-operativa-tunel-admin-recuperacion
SINGLE_TENANT_MODE=false
ALLOW_EXPERIMENTAL_MULTI_TENANT=true
MULTI_TENANT_STRICT=true
TENANT_STORAGE_ISOLATION=true
MULTI_TENANT_SCHEMA_VERSION=3
ALLOW_LOCAL_RECOVERY_CODE=false
ALLOW_PASSWORD_RESET_TOKEN_RESPONSE=false
```

Para recuperación por correo:

```env
RESEND_API_KEY=<secreto>
PASSWORD_RESET_FROM_EMAIL=<remitente-verificado>
PASSWORD_RESET_PUBLIC_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
```

## 13. Límites de la entrega

No se realizó una prueba viva de PowerShell y `cloudflared` en Windows desde este entorno Linux. Tampoco se levantó aquí el contenedor completo con Flask, Gunicorn, OCR y las dependencias de producción. Por tanto, la aceptación final exige ejecutar la guía incluida en un computador Windows y repetir la matriz en una rama de prueba de Railway.

El Quick Tunnel es únicamente para ensayos temporales. No sustituye Railway ni un túnel administrado con dominio estable.

## 14. Criterio de promoción

La versión puede reemplazar la publicada después de confirmar:

1. generación y validación del enlace `trycloudflare.com` en Windows;
2. login de usuarios nuevos en dos fundaciones ficticias;
3. edición, activación, suspensión, eliminación lógica y restauración;
4. recuperación local, administrativa y por correo según el entorno;
5. aislamiento total entre las dos fundaciones;
6. persistencia del volumen `/data` después de un redeploy;
7. ausencia de secretos o códigos locales en respuestas públicas.
