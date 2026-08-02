# PrimeraInfancia 2.3.6 — versión limpia y segura para Railway

Esta entrega fue construida desde una **copia aislada** del proyecto. No contiene la base SQLite original, beneficiarios, usuarios, cargas, resultados, respaldos, logs, cuentas de cobro diligenciadas ni archivos `.env` del paquete auditado.

> Esta versión es para una instalación nueva de prueba. Use exclusivamente información ficticia hasta terminar la validación funcional y de privacidad en el dominio público.

## 1. Qué incluye

- `Dockerfile`: imagen Python 3.12 con Gunicorn y dependencias de Excel, PDF, DOCX y OCR.
- `start_hosting.sh`: inicializa el volumen y arranca un único worker Gunicorn.
- `backend/init_hosting.py`: verifica las semillas por SHA-256, crea el esquema, comprueba SQLite y crea el SUPERADMIN inicial.
- `backend/seed_data/templates_originales/`: plantillas sanitizadas; conservan estructura y formato, sin registros operativos reales.
- `railway.json`: comando de arranque, healthcheck y reinicio por fallo.
- `.env.example`: inventario de variables sin secretos reales.
- `tools/validate_release.py`: validación local del contenido del paquete.
- `VALIDACION_Y_CAMBIOS.md`: alcance de las correcciones y pruebas realizadas.

## 2. Controles de seguridad aplicados

- No existe una credencial administrativa predeterminada utilizable dentro del código.
- Las credenciales iniciales se reciben mediante variables privadas y nunca se sobrescriben en reinicios posteriores.
- El primer ingreso obliga a cambiar la contraseña; todas las sesiones de esa cuenta se invalidan al cambiarla.
- Recuperación de contraseña con mensaje genérico, token de un solo uso, caducidad e invalidación de sesiones.
- El token de recuperación nuevo viaja en el fragmento de la URL, que el navegador no envía al servidor; el frontend lo retira de la barra de direcciones al abrir el enlace.
- Tokens de sesión únicamente en encabezados; la compatibilidad con tokens en query/form queda desactivada.
- Límite persistente de intentos para inicio de sesión y recuperación.
- Autorización por roles con política **denegar por defecto** para toda ruta `/api/`.
- Respuestas API con `Cache-Control: no-store`, encabezados de seguridad y HSTS bajo HTTPS.
- La capa de autenticación falla de forma cerrada: producción no arranca si no puede registrarla.
- El frontend usa el mismo origen público y no redirige accidentalmente a `127.0.0.1` en Railway.

## 3. Alcance multiempresa

Esta entrega se configura expresamente con:

```env
SINGLE_TENANT_MODE=true
ALLOW_EXPERIMENTAL_MULTI_TENANT=false
```

Eso limita la instalación a **una sola fundación**. Aunque existe estructura histórica multiempresa, todavía no se certificó el aislamiento de todas las consultas heredadas. No cambie esas dos variables para una prueba con datos personales.

## 4. Publicar mediante repositorio privado

1. Descomprima el ZIP.
2. Cree un repositorio **privado** en GitHub.
3. Suba el contenido de la carpeta `PrimeraInfancia_Railway_Limpia_v2_3_6`; no suba el ZIP original auditado.
4. En Railway seleccione `New Project` y después el repositorio de GitHub.
5. En `Settings → Networking`, seleccione `Generate Domain`.
6. Añada un volumen al servicio y configure el punto de montaje exacto `/data`.
7. Abra `Variables` y agregue los valores de la sección 6.
8. Confirme que `PUBLIC_APP_URL`, `FRONTEND_ORIGIN` y `PASSWORD_RESET_PUBLIC_URL` referencian `RAILWAY_PUBLIC_DOMAIN`.
9. Despliegue de nuevo y revise los logs de inicialización.

Railway detecta el `Dockerfile` de la raíz. El volumen existe solamente en tiempo de ejecución, por eso la inicialización se ejecuta desde `start_hosting.sh` y no durante la compilación de la imagen.

## 5. Publicar sin GitHub mediante Railway CLI

Desde la carpeta descomprimida:

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Después añada el volumen `/data`, las variables y el dominio desde el panel. Para este proyecto se recomienda GitHub privado porque facilita conservar historial y desplegar correcciones controladas.

## 6. Variables obligatorias del primer despliegue

```env
APP_ENV=production
DATA_DIR=/data
SINGLE_TENANT_MODE=true
ALLOW_EXPERIMENTAL_MULTI_TENANT=false

SECRET_KEY=<secreto aleatorio de 64+ caracteres>
JWT_SECRET_KEY=<otro secreto aleatorio de 64+ caracteres>

INITIAL_ADMIN_USERNAME=<usuario no predecible>
INITIAL_ADMIN_EMAIL=<correo real del administrador>
INITIAL_ADMIN_PASSWORD=<12+ caracteres, mayúscula, minúscula, número y símbolo>
INITIAL_ADMIN_NAME=<nombre administrativo>
INITIAL_ADMIN_FORCE_PASSWORD_CHANGE=true
INITIAL_FOUNDATION_NAME=Entorno de pruebas

PUBLIC_APP_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
FRONTEND_ORIGIN=https://${{ RAILWAY_PUBLIC_DOMAIN }}
PASSWORD_RESET_PUBLIC_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
TRUSTED_PROXY_COUNT=1

ALLOW_LEGACY_QUERY_TOKENS=false
ALLOW_PASSWORD_RESET_TOKEN_RESPONSE=false
ENABLE_LEGACY_TENANT_BACKFILL=false
```

Genere cada secreto por separado:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Selle en Railway `SECRET_KEY`, `JWT_SECRET_KEY`, `INITIAL_ADMIN_PASSWORD` y `RESEND_API_KEY` cuando esta última exista. Nunca las coloque en GitHub, capturas, mensajes o archivos del proyecto.

## 7. Primer ingreso y retiro de la contraseña de arranque

1. Inicie sesión con el usuario configurado en `INITIAL_ADMIN_USERNAME`.
2. La plataforma exigirá cambiar la contraseña inicial antes de abrir módulos.
3. Inicie sesión otra vez con la contraseña nueva.
4. Confirme que el volumen `/data` contiene `database.sqlite3` y `.primera_infancia_initialized.json`.
5. En Railway elimine `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_EMAIL` e `INITIAL_ADMIN_PASSWORD` y vuelva a desplegar.

Con la base y el marcador persistentes, el servicio seguirá arrancando con el SUPERADMIN existente. Si el volumen se pierde o se monta incorrectamente, la aplicación fallará en lugar de crear una cuenta silenciosa.

## 8. Recuperación de contraseña

En producción la API nunca devuelve el token al navegador. Para enviar el enlace configure una cuenta de correo transaccional por HTTPS:

```env
RESEND_API_KEY=<clave privada>
PASSWORD_RESET_FROM_EMAIL=Plataforma <no-reply@dominio-verificado.com>
PASSWORD_RESET_PUBLIC_URL=https://${{ RAILWAY_PUBLIC_DOMAIN }}
```

Sin proveedor configurado, la respuesta continúa siendo genérica y el token generado se invalida. Un SUPERADMIN puede establecer una contraseña temporal fuerte desde Administración.

## 9. Persistencia, capacidad y concurrencia

SQLite, cargas, salidas, respaldos, plantillas y logs se escriben bajo `/data`. Mantenga:

- una sola réplica de Railway;
- un solo worker Gunicorn;
- el volumen montado en `/data`;
- copias de seguridad fuera del repositorio.

Los planes Trial y Free tienen límites reducidos de memoria y volumen. Procesamientos grandes con pandas, OpenPyXL, Matplotlib, OCR o generación de PDF pueden superar los recursos del plan gratuito. Mida con datos ficticios antes de utilizar la plataforma en operación.

## 10. Comprobaciones después del despliegue

1. Abra `/api/health`; debe responder HTTP 200 con `status: ok` sin conteos personales.
2. Abra el dominio raíz y confirme CSS, JavaScript, iconos e imágenes.
3. En herramientas del navegador verifique que ninguna petición pública apunte a `127.0.0.1`.
4. Pruebe el cambio obligatorio de contraseña.
5. Haga cinco intentos fallidos controlados y confirme el bloqueo temporal.
6. Pruebe roles con usuarios ficticios y confirme que cada menú/API deniega lo no autorizado.
7. Cargue un archivo pequeño ficticio, genere un formato y descárguelo.
8. Reinicie el servicio y compruebe que usuario, plantillas y archivo de prueba persisten.
9. Pruebe crear y validar un respaldo; descárguelo a un lugar privado.
10. Revise logs: no deben mostrar contraseñas ni tokens de sesión.

## 11. Validación local del paquete

Sin instalar Flask puede ejecutar las comprobaciones estructurales:

```bash
python tools/validate_release.py
```

La prueba integral de Flask/Gunicorn debe hacerse durante el primer despliegue porque requiere instalar todas las dependencias de producción y ejecutar el contenedor real.

## 12. Regla de seguridad para los ensayos

No use datos reales de niños, niñas, acudientes, salud, nutrición, empleados o contratos hasta completar pruebas de acceso, permisos, persistencia, respaldo, restauración y manejo de incidentes. Este ZIP está limpio; la privacidad futura dependerá también de los archivos que se carguen después del despliegue.
