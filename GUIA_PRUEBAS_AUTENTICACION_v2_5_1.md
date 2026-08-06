# Guía de pruebas de autenticación — PrimeraInfancia 2.5.1

## 1. Preparación

1. Conserva la carpeta 2.5.0 como respaldo.
2. Extrae la versión 2.5.1 en una ruta corta, por ejemplo:

```text
C:\PI_V251
```

3. Para mantener usuarios y datos ficticios, copia únicamente:

```text
data
```

4. No copies:

```text
backend\.venv
.runtime_windows
logs_tunel
tools\cloudflared
ENLACE_PUBLICO_TUNEL.txt
```

## 2. Prueba local básica

1. Ejecuta `DETENER_PLATAFORMA_LOCAL.bat` en las carpetas anteriores.
2. Ejecuta `INICIAR_PLATAFORMA_LOCAL.bat` en 2.5.1.
3. Abre el enlace local.
4. Inicia sesión con un administrador válido.
5. El botón debe pasar de `Validando...` al panel o volver a `Ingresar`; nunca debe quedar bloqueado indefinidamente.

## 3. Prueba en dos dispositivos

1. Mantén abierta la sesión en el primer navegador.
2. Abre una ventana privada u otro computador.
3. Inicia sesión con la misma cuenta, solo si la política de prueba lo permite.
4. Confirma que ambas sesiones continúan activas.
5. Cierra una sesión y comprueba que la otra permanece abierta.

## 4. Prueba con usuarios diferentes

1. Crea dos usuarios ficticios con roles autorizados.
2. Inicia sesión simultáneamente desde dos navegadores.
3. Confirma que cada usuario conserva su fundación y UCA.
4. Verifica que no aparezcan datos cruzados.

## 5. Prueba de doble clic

1. En el formulario de login, pulsa varias veces rápidamente el botón.
2. Debe enviarse una sola solicitud.
3. El botón permanece deshabilitado hasta terminar.

## 6. Prueba de recuperación ante espera

1. Con la aplicación de prueba, provoca temporalmente una carga de escritura o ejecuta dos acciones pesadas ficticias.
2. Inicia sesión.
3. El backend debe reintentar internamente.
4. Si responde `LOGIN_DATABASE_BUSY`, el navegador debe reintentar una sola vez.
5. No deben aparecer intentos fallidos por una contraseña correcta.

## 7. Diagnóstico

En las herramientas de desarrollo del navegador revisa la respuesta de `/api/auth/login`:

```text
X-Login-Duration-Ms
X-Login-DB-Retries
X-Client-Request-ID
```

Revisa además:

```text
data\logs\application.log
data\logs\error_api_*.log
```

No compartas contraseñas, tokens ni cookies.

## 8. Criterios de aceptación

- Login normal menor de dos segundos.
- Ninguna permanencia indefinida en `Validando credenciales`.
- Sesiones simultáneas permitidas sin invalidación accidental.
- Un bloqueo SQLite no incrementa el contador de contraseñas incorrectas.
- La interfaz recupera el botón después de cualquier error.
- Los roles y datos multi-fundación permanecen aislados.
- No hay errores 500 durante login con credenciales válidas.

## 9. Railway

Antes de probar en Railway confirma:

```text
1 réplica
1 worker Gunicorn
volumen montado en /data
```

Realiza la prueba con datos ficticios y dos navegadores. Registra duración, código HTTP y `request_id` de cualquier fallo.
