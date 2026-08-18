# Guía de aplicación y despliegue — Primera Infancia v2.7.0 auditada

## Opción recomendada: versión completa

1. Crea copia de seguridad de la carpeta actual y de PostgreSQL.
2. Crea una rama Git: `release/v2-7-0-auditada-corregida`.
3. Extrae el ZIP completo en una carpeta nueva.
4. No copies `.env`, bases locales, `.venv`, logs ni archivos de usuarios desde la entrega anterior.
5. Configura en Railway las variables ya existentes; no cambies `DATABASE_URL` si ya referencia `${{Postgres.DATABASE_URL}}`.
6. Haz commit y push.
7. Comprueba `/api/system/version`, `/health`, login, calendario, Base Maestra y RAM.

## Opción patch

1. Abre la carpeta exacta del repositorio con GitHub Desktop → Repository → Show in Explorer.
2. Crea una rama y un backup.
3. Extrae el patch sobre la raíz, conservando rutas.
4. Confirma que GitHub Desktop muestre los archivos del manifiesto de cambios.
5. Commit sugerido: `fix: estabilizar PostgreSQL, calendario y formato RAM oficial`.
6. Push origin y verifica el SHA en Railway.

## No hacer

- No borrar PostgreSQL.
- No reemplazar `DATABASE_URL` por localhost.
- No copiar `.env` dentro de GitHub.
- No desplegar desde una carpeta distinta al repositorio conectado.
- No aceptar el despliegue si `/api/system/version` no coincide con el commit subido.
