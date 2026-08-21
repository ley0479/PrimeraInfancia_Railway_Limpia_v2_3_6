# Worker persistente del Motor Documental

La aplicación web conserva el procesamiento síncrono mientras `IDP_ASYNC_ENABLED` no esté activo. Esto permite desplegar la cola sin interrumpir el flujo vigente.

## Activación controlada en Railway

1. Crear un segundo servicio desde el mismo repositorio y Dockerfile.
2. Compartir con el servicio web la misma variable `DATABASE_URL` de PostgreSQL.
3. Montar el mismo volumen privado y la misma ruta de datos usada por el servicio web; el worker necesita leer los originales privados.
4. Configurar como comando de inicio: `./backend/start_idp_worker.sh`.
5. No configurar healthcheck HTTP para el worker; es un consumidor continuo sin servidor web.
6. Definir `IDP_WORKER_POLL_SECONDS=2` en el worker.
7. Confirmar que el worker está activo y después definir `IDP_ASYNC_ENABLED=1` en el servicio web.

## Reversión segura

Definir `IDP_ASYNC_ENABLED=0` o eliminar la variable en el servicio web. Las cargas nuevas volverán al procesamiento síncrono y los trabajos ya persistidos permanecerán auditables en `idp_trabajos_cola`.

No deben ejecutarse dos servicios con rutas de almacenamiento distintas: PostgreSQL conservaría el trabajo, pero el worker no podría abrir el archivo original.
