# Informe de corrección del enlace Cloudflare Tunnel — PrimeraInfancia 2.4.3

**Fecha:** 4 de agosto de 2026  
**Versión fuente:** 2.4.2 — túnel, login y logs corregidos  
**Versión resultante:** 2.4.3 — Quick Tunnel Cloudflare corregido

## 1. Solicitud atendida

Se verificó el flujo de `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat` porque el enlace temporal no se generaba o no quedaba utilizable desde otros equipos.

## 2. Causa técnica comprobada

La versión 2.4.2 creaba un archivo de configuración vacío y arrancaba `cloudflared` pasando `--config` a un **Quick Tunnel**. Ese comportamiento no corresponde al contrato de Quick Tunnel: esta modalidad se inicia únicamente con `cloudflared tunnel --url <origen>` y no necesita una configuración de túnel nombrado.

Además, una configuración `config.yml` o `config.yaml` existente en el perfil personal del usuario puede impedir el funcionamiento de TryCloudflare. La corrección no borra ni renombra archivos personales: ejecuta `cloudflared` con un perfil `HOME/USERPROFILE` aislado y sin `--config`.

## 3. Correcciones aplicadas

### 3.1 Arranque compatible con Quick Tunnel

El comando efectivo conserva esta forma:

```text
cloudflared tunnel --url http://127.0.0.1:5000 --no-autoupdate --protocol <auto|http2> --loglevel info
```

No se crea ni se pasa ningún archivo `config.yml`, `config.yaml` o `--config`.

### 3.2 Aislamiento sin tocar la configuración del usuario

Se genera un perfil temporal dentro de:

```text
.runtime_windows/cloudflared_home_aislado
```

El proceso hijo recibe ese directorio como `HOME` y `USERPROFILE`. De este modo una configuración Cloudflare ajena al proyecto no modifica el Quick Tunnel, y el proyecto tampoco altera la configuración personal.

### 3.3 Compatibilidad de red

- Se fuerza TLS 1.2 para las solicitudes de PowerShell.
- La descarga de `cloudflared.exe` intenta primero `Invoke-WebRequest` y luego `curl.exe`.
- El primer intento usa protocolo `auto`.
- Si no produce un enlace verificado, se realiza un segundo intento explícito con `http2`, útil cuando una red o antivirus bloquea QUIC/UDP.
- El diagnóstico comprueba de forma orientativa la salida TCP al puerto 7844.

### 3.4 Verificación antes de entregar el enlace

El script no considera listo el túnel solamente porque apareció una URL. Antes de escribirla en `ENLACE_PUBLICO_TUNEL.txt` comprueba:

1. que `/api/health` responda `status=ok`;
2. que `project_instance_id` sea el de la carpeta actual;
3. que `public_tunnel_mode=true`;
4. que `/frontend/index.html` responda por el dominio público.

Así se evita compartir un enlace de una ejecución anterior, de otra carpeta o de un backend que no está preparado para proxy HTTPS.

### 3.5 Diagnóstico ampliado

Se mejoraron:

```text
DIAGNOSTICAR_LOGIN_TUNEL.bat
DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat
scripts_windows/diagnosticar_login_tunel.ps1
```

El reporte incluye:

- versión y ubicación de `cloudflared`;
- PID del túnel actual;
- estado local y público;
- coincidencia de instancia;
- prueba segura de la ruta de login;
- puerto 7844;
- configuración personal detectada, sin modificarla;
- logs no vacíos de `logs_tunel`;
- patrones de fallo de DNS, QUIC, origen local y configuración.

El comando efectivo, sin credenciales, se guarda en:

```text
.runtime_windows/ULTIMO_COMANDO_CLOUDFLARED.txt
```

## 4. Elementos preservados

No se alteraron:

- autenticación y contraseñas de usuarios;
- base SQLite;
- aislamiento multi-fundación;
- gestión de usuarios y fundaciones;
- recuperación de contraseña;
- plantillas, UDS, RPP, RAM o Bienestarina;
- configuración Railway/Docker.

La corrección se concentra en el arranque y diagnóstico del túnel local.

## 5. Seguridad

- El paquete no incluye `cloudflared.exe`; se descarga desde la distribución oficial al ejecutar el túnel.
- No incluye bases operativas, `.env`, contraseñas, logs ni datos personales.
- El Quick Tunnel sigue siendo temporal y debe usarse solo con datos ficticios.
- No debe compartirse una cuenta `SUPERADMIN`; se recomienda crear un usuario de prueba con permisos mínimos.

## 6. Validación

Se ejecutó el validador reproducible del paquete con el siguiente resultado:

| Control | Resultado |
|---|---:|
| Validaciones generales | **17 PASS / 0 FAIL / 0 SKIP** |
| Sintaxis Python | **150 archivos** |
| Sintaxis JavaScript | **32 archivos** |
| Sintaxis Bash | **2 scripts** |
| JSON | **14 archivos** |
| Rutas API revisadas | **318** |
| Familias de autorización | **55** |
| Prueba de regresión Quick Tunnel 2.4.3 | **Aprobada** |
| Aislamiento multi-fundación | **Aprobado** |
| Privacidad y ausencia de datos runtime | **Aprobadas** |

También pasaron las suites heredadas de multi-fundación 2.4.0, administración/recuperación 2.4.1 y login/logging 2.4.2.

No fue posible ejecutar `cloudflared.exe` ni PowerShell 5.1 dentro del entorno Linux de preparación. El contrato del comando y los scripts fueron revisados estáticamente y comparados con la documentación oficial; la prueba definitiva de red, antivirus y enlace público debe realizarse en Windows.
