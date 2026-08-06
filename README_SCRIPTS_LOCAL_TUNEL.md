# Scripts Windows — ejecución local y túnel Cloudflare

## Versión

**PrimeraInfancia 2.6.0 — Salud y Nutrición Integral, PostgreSQL, scripts Windows robustos y Quick Tunnel Cloudflare.**

Los scripts de esta carpeta sirven para dos escenarios distintos:

- **Local:** ejecutar la plataforma solamente en el computador de desarrollo.
- **Túnel de pruebas:** publicar temporalmente esa misma ejecución local mediante un enlace HTTPS aleatorio de `trycloudflare.com` para ensayarla desde otros computadores.

El túnel es una herramienta de demostración. Railway continúa siendo el entorno recomendado para un enlace estable.


## Inicio de sesión estable 2.5.1

- El navegador cancela una validación que exceda cinco segundos y recupera el botón de ingreso.
- Un `SQLITE_BUSY` transitorio se reintenta internamente en el backend y una sola vez en el cliente.
- El login conserva sesiones activas del mismo usuario en dispositivos distintos.
- La facturación se consulta en modo lectura durante el acceso y no ejecuta DDL ni actualizaciones de mantenimiento por cada petición.
- Las respuestas incluyen `X-Login-Duration-Ms`, `X-Login-DB-Retries` y un identificador de solicitud para diagnóstico.

## Scripts principales

| Archivo | Función |
|---|---|
| `INICIAR_PLATAFORMA_LOCAL.bat` | Detecta Python 3.11/3.12, prepara el entorno virtual, inicializa la base local, verifica `/api/health` y abre el frontend. |
| `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat` | Reinicia el backend en modo túnel seguro cuando es necesario, descarga/verifica `cloudflared`, genera y valida el enlace público. |
| `DETENER_PLATAFORMA_LOCAL.bat` | Cierra el backend del puerto 5000 y únicamente el proceso de túnel asociado a este proyecto. |
| `DIAGNOSTICAR_LOGIN_TUNEL.bat` | Compara la copia local y la pública, prueba `/api/health`, comprueba la ruta de login y analiza los logs de Cloudflare. |
| `DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat` | Alias claro del diagnóstico de red, proceso, instancia, puerto 7844 y enlace público. |
| `ABRIR_LOGS_ERRORES.bat` | Abre la carpeta operativa real `data\logs`. |


## Verificación de la copia correcta

Cada carpeta extraída recibe una huella estable de 16 caracteres. El endpoint
`/api/health` publica esa huella como `project_instance_id`, y los scripts la
comparan antes de abrir el navegador o generar un túnel.

Esto evita un fallo especialmente confuso: tener una versión antigua escuchando
en el puerto 5000 y publicar esa otra base mediante el túnel mientras se cree
estar probando la carpeta nueva. Si la huella o el modo no coinciden, el script
informa el conflicto y pide autorización antes de cerrar el proceso.

La huella no contiene la ruta del computador ni datos personales.

## Inicio local

1. Extraiga el proyecto en una ruta corta, por ejemplo:

```text
C:\PI\
```

2. Ejecute:

```text
INICIAR_PLATAFORMA_LOCAL.bat
```

3. El script debe abrir:

```text
http://127.0.0.1:5000/frontend/index.html
```

4. El estado técnico se comprueba mediante:

```text
http://127.0.0.1:5000/api/health
```

La ruta `/api/health` es pública y sirve para comprobar el arranque. La ruta `/api/acceso/ping` continúa autenticada y ya no se utiliza para decidir si Flask inició.

## Túnel Cloudflare de pruebas

1. Cierre cualquier túnel anterior de este proyecto o ejecute `DETENER_PLATAFORMA_LOCAL.bat`.
2. Ejecute:

```text
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
```

3. El proceso realiza automáticamente:

- comprobación de `/api/health` y del frontend local;
- reinicio en `PUBLIC_TUNNEL_MODE=true` cuando Flask estaba abierto solo en modo local;
- descarga del ejecutable oficial portable para `amd64` o `arm64`;
- perfil `HOME/USERPROFILE` aislado para que un `config.yml` personal no interfiera;
- ejecución del Quick Tunnel **sin `--config`**, como exige Cloudflare;
- intento automático y segundo intento explícito con HTTP/2/TCP si QUIC/UDP está bloqueado;
- TLS 1.2 y descarga alternativa mediante `curl.exe`;
- captura del enlace desde salida estándar y salida de errores;
- validación pública de `/api/health` y `/frontend/index.html`;
- guardado del PID para cerrar exclusivamente este túnel;
- copia del enlace al portapapeles y apertura del navegador.

El resultado queda en:

```text
ENLACE_PUBLICO_TUNEL.txt
```

El enlace que debe compartirse tiene esta forma:

```text
https://palabras-aleatorias.trycloudflare.com/frontend/index.html
```

Nunca comparta `127.0.0.1`; esa dirección solo funciona en el computador donde se ejecuta Flask.

## Protección durante el túnel

Mientras `PUBLIC_TUNNEL_MODE=true`:

- no se entrega ningún código local de recuperación de contraseña;
- el enlace de recuperación por correo utiliza el dominio temporal si está disponible;
- el panel Acceso Compartido muestra el enlace de `trycloudflare.com`;
- se recomienda crear un usuario individual de prueba y no compartir el `SUPERADMIN`;
- la ventana del backend y la del túnel deben permanecer abiertas.

## Recuperación de contraseña

- **Local sin túnel:** si no existe proveedor de correo, la plataforma puede mostrar un código temporal de un solo uso.
- **Túnel o Railway:** nunca muestra el código local; debe utilizar correo configurado o restablecimiento administrativo.
- **Administración:** un gerente autorizado o `SUPERADMIN` puede crear una contraseña temporal para un usuario de su fundación. El usuario debe cambiarla al ingresar.

## Diagnóstico cuando no aparece el enlace o falla el login

Ejecute primero:

```text
DIAGNOSTICAR_LOGIN_TUNEL.bat
```

El reporte se guarda en `.runtime_windows/` y confirma:

- que el puerto 5000 pertenece a esta carpeta;
- que el backend está en `PUBLIC_TUNNEL_MODE=true`;
- que el dominio público expone la misma huella;
- que la ruta de login responde sin provocar un error técnico;
- que `data\logs` es escribible;
- cuáles reportes `error_api_*.log` tienen contenido.

Los errores de Flask se guardan en:

```text
data\logs
```

`backend\logs` es únicamente un marcador vacío del repositorio. Para abrir la
carpeta correcta puede ejecutar `ABRIR_LOGS_ERRORES.bat`.

Para problemas propios de Cloudflare, revise `logs_tunel/`. La versión 2.5.0 conserva y amplía la corrección 2.4.3; guarda además el comando efectivo —sin secretos— en `.runtime_windows/ULTIMO_COMANDO_CLOUDFLARED.txt`. El script muestra las últimas líneas si detecta un fallo. Las causas más habituales son:

- internet intermitente;
- antivirus o firewall bloqueando `cloudflared.exe`;
- fecha/hora de Windows incorrecta;
- una red institucional que bloquea la salida a Cloudflare;
- descarga incompleta del ejecutable;
- puerto 5000 ocupado por otra aplicación.

También puede eliminar:

```text
tools\cloudflared\cloudflared.exe
```

para forzar una descarga nueva en el próximo inicio.

## Credenciales y secretos locales

En una base completamente nueva, el usuario inicial conserva el nombre:

```text
admin.local
```

La contraseña **ya no está fija en el código**. El script genera una clave aleatoria fuerte y la guarda únicamente en:

```text
.runtime_windows/CREDENCIALES_INICIALES_LOCAL.txt
```

El primer ingreso obliga a cambiarla. Después de hacerlo, elimine ese archivo. Si `data/database.sqlite3` ya existe, las variables de arranque no reemplazan la contraseña guardada y el script no presenta la contraseña temporal como si fuera válida.

`SECRET_KEY` y `JWT_SECRET_KEY` también se generan de forma aleatoria por instalación y se conservan en `.runtime_windows/`, una carpeta excluida de Git. No reutilice ninguna credencial local en Railway.

## Prueba mínima desde otro computador

1. Mantenga abiertas las dos ventanas.
2. Abra el enlace `trycloudflare.com` desde otro equipo o desde un celular con otra red.
3. Inicie sesión con un usuario ficticio no administrativo.
4. Compruebe navegación, carga y descarga de un archivo ficticio.
5. Cierre el túnel con `Ctrl+C` o `DETENER_PLATAFORMA_LOCAL.bat`.
6. Confirme que el enlace dejó de responder.

No utilice información personal real durante estas pruebas.


## Lanzadores 2.6.0

Los archivos BAT de raíz son envoltorios mínimos CRLF. Toda la lógica está en PowerShell para evitar fragmentación de comandos por codificación o saltos de línea.

- `INICIAR_PLATAFORMA_LOCAL.bat`: inicia SQLite o PostgreSQL según `DATABASE_URL`.
- `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`: inicia la misma copia en modo túnel y luego Quick Tunnel.
- `CONFIGURAR_POSTGRESQL_LOCAL.bat`: comprueba y guarda de forma local la URL.
- `MIGRAR_SQLITE_A_POSTGRESQL.bat`: respalda SQLite, migra y valida conteos.
- `RESPALDAR_POSTGRESQL.bat` / `RESTAURAR_POSTGRESQL.bat`: usan `pg_dump` y `pg_restore`.
- `DETENER_PLATAFORMA_LOCAL.bat`: cierra solo procesos confirmados de esta carpeta.
