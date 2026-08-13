# Integraciones, Configuración y Administración General

Centro maestro de lectura transversal y parametrización no sensible. Reutiliza Configuración Institucional, Seguridad, Plantillas Oficiales, Calendario, Backups e Integridad; no sustituye esas fuentes.

Los conectores nacen en `BORRADOR` y registrarlos no ejecuta tráfico externo. Las credenciales se conservan exclusivamente en variables de entorno o bóvedas; la tabla almacena referencias como `ENV:NOMBRE_VARIABLE`, nunca secretos.

Solo Superadmin puede cambiar parámetros o registrar conectores. Gerencia tiene consulta. Toda modificación deja auditoría multi-tenant.

API: `GET /api/integraciones-configuracion/dashboard`, POST `/parametros` y `/integraciones`.
