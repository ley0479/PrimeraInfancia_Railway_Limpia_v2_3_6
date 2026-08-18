# Guía de prueba del enlace Cloudflare Tunnel — PrimeraInfancia 2.4.3

## Antes de comenzar

1. Conserva intacta la carpeta 2.4.2 como respaldo.
2. Extrae esta versión en una ruta corta, por ejemplo:

```text
C:\PI_V243
```

3. Para conservar usuarios y configuraciones ficticias, copia **únicamente** la carpeta `data` de la instalación anterior.
4. No copies estos elementos antiguos:

```text
.runtime_windows
backend\.venv
logs_tunel
tools\cloudflared
ENLACE_PUBLICO_TUNEL.txt
```

## Prueba principal

### Paso 1 — cerrar procesos anteriores

Ejecuta:

```text
DETENER_PLATAFORMA_LOCAL.bat
```

### Paso 2 — iniciar el túnel

Ejecuta directamente:

```text
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
```

No necesitas iniciar primero la modalidad local. El script arranca o reinicia la misma copia en modo túnel.

### Paso 3 — esperar la confirmación

La ejecución correcta debe terminar con un mensaje equivalente a:

```text
[5/5] Tunel listo, protocolo, modo e instancia verificados.
```

También mostrará:

```text
ENLACE PUBLICO: https://...trycloudflare.com/frontend/index.html
```

### Paso 4 — usar el enlace correcto

Abre o comparte el valor `Frontend` guardado en:

```text
ENLACE_PUBLICO_TUNEL.txt
```

No compartas:

```text
http://127.0.0.1:5000
```

### Paso 5 — probar desde otra red

Mantén abiertas las ventanas del backend y del túnel. Abre el enlace desde:

- otro computador;
- un teléfono usando datos móviles;
- una ventana privada del navegador.

El túnel utiliza los mismos usuarios y contraseñas de la base local; no tiene credenciales propias.

## Si no genera el enlace

Ejecuta:

```text
DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat
```

El reporte quedará en:

```text
.runtime_windows\DIAGNOSTICO_TUNEL_LOGIN_AAAAMMDD_HHMMSS.txt
```

Revisa también:

```text
logs_tunel
.runtime_windows\ULTIMO_COMANDO_CLOUDFLARED.txt
```

### Acciones según el diagnóstico

- **QUIC o UDP bloqueado:** el script reintenta automáticamente con HTTP/2/TCP.
- **Puerto 7844 bloqueado:** permite salida de `cloudflared.exe` en antivirus/firewall o prueba temporalmente otra red, por ejemplo un punto de acceso móvil.
- **DNS:** prueba otra red o revisa el DNS del equipo.
- **Origen rechazado:** confirma que la ventana del backend siga abierta y que `http://127.0.0.1:5000/api/health` responda.
- **Ejecutable dañado o antiguo:** elimina `tools\cloudflared\cloudflared.exe` y vuelve a ejecutar el túnel para descargarlo otra vez.
- **Otra copia ocupa el puerto 5000:** acepta cerrar el proceso solo después de verificar que no sea otro trabajo importante.

## Si genera enlace pero no abre

1. No reutilices un enlace de una ejecución anterior; cambia cada vez que reinicias Quick Tunnel.
2. Confirma que `ENLACE_PUBLICO_TUNEL.txt` diga `Estado: VERIFICADO`.
3. Ejecuta el diagnóstico mientras ambas ventanas continúan abiertas.
4. Comprueba el enlace de salud:

```text
https://...trycloudflare.com/api/health
```

Debe mostrar la misma `project_instance_id` que el reporte local.

## Cierre correcto

Para terminar:

```text
DETENER_PLATAFORMA_LOCAL.bat
```

Esto cierra el backend del puerto 5000 y el proceso `cloudflared` registrado para esta copia.
