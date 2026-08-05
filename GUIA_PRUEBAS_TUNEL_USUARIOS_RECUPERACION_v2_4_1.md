# Guía de aceptación — túnel, usuarios, fundaciones y recuperación 2.4.1

Use únicamente datos ficticios. La prueba debe ejecutarse primero en local y después, de manera temporal, mediante Cloudflare Tunnel.

## 1. Preparación

1. Conserve intacto el ZIP recibido.
2. Extraiga la versión en una ruta corta, por ejemplo `C:\PI_V241\`.
3. Confirme Python 3.11 o 3.12.
4. Si ya existe una instalación local, copie la carpeta `data` como respaldo.
5. Ejecute `DETENER_PLATAFORMA_LOCAL.bat` para evitar procesos antiguos.

## 2. Arranque local y credenciales iniciales

1. Ejecute `INICIAR_PLATAFORMA_LOCAL.bat`.
2. Confirme que el script utiliza `/api/health` y abre:

```text
http://127.0.0.1:5000/frontend/index.html
```

3. Compruebe que `/api/health` devuelve `status: ok`.
4. Si `data/database.sqlite3` no existía, el inicio crea una cuenta `admin.local` con contraseña aleatoria y obliga a cambiarla. Las credenciales se guardan temporalmente en:

```text
.runtime_windows/CREDENCIALES_INICIALES_LOCAL.txt
```

5. Entre una sola vez, cambie la contraseña y elimine ese archivo de credenciales. No reutilice esa clave en Railway ni para una demostración por túnel.
6. Si la base ya existía, use la cuenta registrada; el script no reemplaza contraseñas existentes.
7. Confirme que el menú Administración carga fundaciones y usuarios.

Las claves internas `SECRET_KEY` y `JWT_SECRET_KEY` también se generan de forma aleatoria y quedan únicamente en `.runtime_windows/`, carpeta excluida de Git y del ZIP operativo.

## 3. Usuarios nuevos

Cree dos fundaciones ficticias: **Prueba A** y **Prueba B**. Cree al menos:

- un gerente en A;
- un docente en A;
- un gerente en B;
- un docente en B.

Para cada cuenta:

1. use un usuario y correo ficticios únicos;
2. asigne una contraseña que cumpla la política;
3. cierre la sesión administrativa;
4. inicie sesión una sola vez con el usuario recién creado;
5. si está marcado “cambio obligatorio”, cambie la contraseña;
6. confirme que el acceso posterior funciona.

Resultado esperado: ningún usuario nuevo debe responder “credenciales inválidas” cuando se emplean exactamente los datos creados.

## 4. Gestión de usuarios

Como administrador autorizado:

| Acción | Resultado esperado |
|---|---|
| Editar nombre, correo, usuario o rol | Guarda y cierra sesiones antiguas cuando cambia seguridad |
| Desactivar | Bloquea nuevos inicios y cierra sesiones activas |
| Activar | Permite login si la fundación está activa |
| Restablecer clave | Muestra una contraseña temporal una sola vez y exige cambio |
| Eliminar | Realiza eliminación lógica y conserva trazabilidad |
| Restaurar | Devuelve estado ACTIVO; la contraseña puede restablecerse después |
| Modificar usuario de otro tenant como GERENTE | Responde 403 |
| Eliminar la propia cuenta | Se bloquea |
| Eliminar el último SUPERADMIN | Se bloquea |

Antes de eliminar, la interfaz debe mostrar la cantidad de registros relacionados.

## 5. Gestión de fundaciones

| Acción | Resultado esperado |
|---|---|
| Editar | Actualiza información sin alterar datos de otras fundaciones |
| Suspender | Cierra sesiones de sus usuarios y bloquea login |
| Activar | Restaura la fundación; los usuarios se reactivan individualmente |
| Eliminar | Eliminación lógica, sesiones cerradas y usuarios desactivados |
| Restaurar | Estado ACTIVA sin borrar trazabilidad |
| Eliminar fundación actual | Se bloquea |
| Eliminar última fundación activa | Se bloquea |

Confirme que Prueba A nunca vea usuarios, archivos o registros de Prueba B.

## 6. Recuperación de contraseña local

Sin túnel activo:

1. cierre sesión;
2. escriba el usuario o correo;
3. pulse **Recuperar contraseña**;
4. cuando no exista proveedor de correo, debe mostrarse un código temporal local;
5. escriba una contraseña nueva;
6. use el código una vez;
7. confirme que el segundo uso del mismo código falla;
8. inicie sesión con la nueva contraseña.

El código local solo debe aparecer desde `127.0.0.1` o `localhost` y en desarrollo.

## 7. Túnel Cloudflare

1. Ejecute `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`.
2. Si el backend estaba abierto en modo local, el script debe reiniciarlo en modo túnel.
3. Confirme cinco pasos exitosos y el mensaje **Túnel listo y verificado**.
4. Abra `ENLACE_PUBLICO_TUNEL.txt`.
5. Pruebe el enlace desde otro computador o una red móvil.
6. Confirme que el panel Acceso Compartido muestra el mismo enlace.
7. No utilice `admin.local`; cree un usuario ficticio con permisos mínimos.
8. Mantenga abiertas las ventanas del backend y del túnel.

Resultado esperado:

```text
https://<subdominio-aleatorio>.trycloudflare.com/frontend/index.html
```

## 8. Recuperación durante el túnel

Con el túnel activo:

- la API nunca debe devolver `local_recovery_code`;
- si Resend está configurado, debe enviarse un enlace que use el dominio `trycloudflare.com` vigente;
- sin correo configurado, debe mostrarse solamente el mensaje genérico;
- un administrador puede restablecer la cuenta desde Gestión de Usuarios.

## 9. Cierre y logs

1. Ejecute `DETENER_PLATAFORMA_LOCAL.bat`.
2. Confirme que el enlace público deje de responder.
3. Confirme que no se cerraron otros procesos `cloudflared` ajenos al proyecto.
4. Revise `logs_tunel/` y verifique que no contengan contraseñas, tokens de sesión ni datos personales.

## 10. Railway

Antes de actualizar producción:

1. respalde `/data`;
2. haga commit en una rama de prueba;
3. configure `APP_VERSION=2.4.1-operativa-tunel-admin-recuperacion`;
4. mantenga `ALLOW_LOCAL_RECOVERY_CODE=false`;
5. configure Resend para recuperación pública o defina un procedimiento administrativo;
6. haga deploy;
7. repita la matriz con dos fundaciones ficticias;
8. haga un redeploy y confirme persistencia.

## Criterio de aprobación

La versión puede avanzar cuando:

- el túnel genera y valida el enlace en Windows;
- los usuarios nuevos inician sesión;
- todas las acciones administrativas respetan tenant y dependencias;
- recuperación local, correo y recuperación administrativa funcionan según su entorno;
- no hay códigos locales ni secretos expuestos por túnel o Railway;
- todas las pruebas multi-fundación anteriores continúan aprobadas.
