# Guía de prueba — login por túnel 2.4.2

## 1. Preparación segura

1. Conserva la carpeta 2.4.1 como respaldo.
2. Extrae la versión 2.4.2 en una ruta corta, por ejemplo:

```text
C:\PI_V242
```

3. Para conservar usuarios ficticios y configuraciones locales, copia únicamente
la carpeta `data` de la instalación anterior dentro de la nueva.
4. No copies:

```text
backend\.venv
.runtime_windows
logs_tunel
tools\cloudflared
ENLACE_PUBLICO_TUNEL.txt
```

La carpeta `.runtime_windows` debe regenerarse para esta copia.

## 2. Cerrar procesos anteriores

Ejecuta desde la carpeta nueva:

```text
DETENER_PLATAFORMA_LOCAL.bat
```

Esto libera el puerto 5000 y cierra el túnel registrado para el proyecto.

## 3. Prueba local

Ejecuta:

```text
INICIAR_PLATAFORMA_LOCAL.bat
```

El script mostrará una huella como:

```text
Instancia del proyecto: 1a2b3c4d5e6f7890
```

Abre:

```text
http://127.0.0.1:5000/api/health
```

Comprueba:

```json
{
  "status": "ok",
  "public_tunnel_mode": false,
  "project_instance_id": "1a2b3c4d5e6f7890"
}
```

Inicia sesión localmente. Si la base ya existía, usa la contraseña actual de esa
cuenta; las variables iniciales no restablecen usuarios existentes.

## 4. Iniciar el túnel

Cierra el backend local o permite que el script lo reinicie y ejecuta:

```text
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
```

La salida correcta debe indicar:

```text
Túnel listo, modo e instancia verificados.
```

El enlace queda en:

```text
ENLACE_PUBLICO_TUNEL.txt
```

Ese archivo también registra la huella y la versión expuestas.

## 5. Probar desde otro computador

1. Abre el enlace que termina en `/frontend/index.html`.
2. Utiliza un usuario ficticio de pruebas; el túnel no posee una clave propia.
3. Confirma que el usuario ve únicamente su fundación.
4. Cierra sesión y prueba un segundo usuario de otra fundación.

## 6. Si aparece “Error técnico del servidor”

No sigas intentando repetidamente. Ejecuta:

```text
DIAGNOSTICAR_LOGIN_TUNEL.bat
```

Luego ejecuta:

```text
ABRIR_LOGS_ERRORES.bat
```

Busca un archivo como:

```text
data\logs\error_api_2026080413314651541269.log
```

El navegador debe mostrar el mismo código. `backend\logs` no es el destino de
ejecución.

El diagnóstico se guarda en:

```text
.runtime_windows\DIAGNOSTICO_TUNEL_LOGIN_AAAAMMDD_HHMMSS.txt
```

## 7. Interpretación rápida

- **Instancia local distinta:** otra carpeta ocupa el puerto 5000.
- **Instancia pública distinta:** Cloudflare está publicando otra copia.
- **Modo público falso:** el backend no se reinició en modo túnel.
- **HTTP 400 en prueba segura de login:** correcto; la ruta está activa y rechazó
un cuerpo vacío sin lanzar un error técnico.
- **HTTP 500:** abre el `error_api_*.log` indicado.
- **HTTP 503 LOGIN_DATABASE_BUSY:** espera dos segundos y realiza un solo intento.
- **data/logs no escribible:** revisa permisos, antivirus o ubicación de la carpeta.

## 8. Finalizar

Ejecuta:

```text
DETENER_PLATAFORMA_LOCAL.bat
```

El enlace temporal dejará de responder.
