# Plan de reversión y contingencia — PrimeraInfancia 2.6.0

## Antes del cambio

- conservar ZIP de la versión 2.5.4;
- copiar la carpeta `data`;
- calcular SHA-256 de `database.sqlite3`;
- generar reporte de conteos;
- crear respaldo PostgreSQL si el destino no está vacío;
- documentar variables y hora de corte sin exponer secretos.

## Reversión antes del corte

Si la migración falla, no modifiques la instancia operativa. Corrige el error, crea una base PostgreSQL nueva y repite desde el respaldo SQLite.

## Reversión local

- detener procesos;
- retirar `.runtime_windows/database_url.local.txt`;
- restaurar `data/database.sqlite3` verificado;
- iniciar la versión anterior o la 2.6.0 en modo SQLite;
- validar login y conteos.

## Reversión Railway

- detener escrituras;
- guardar logs y respaldo del estado fallido;
- restaurar la variable `DATABASE_URL` y la imagen anteriores;
- restaurar el respaldo correspondiente;
- ejecutar healthcheck y smoke tests;
- reabrir tráfico.

## Prevención de pérdida

Nunca permitas escrituras simultáneas en SQLite y PostgreSQL después de iniciar el corte. La reconciliación automática entre dos bases divergentes no forma parte de esta entrega.
