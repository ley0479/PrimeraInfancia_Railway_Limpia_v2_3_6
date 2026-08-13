# Motor Central de Integridad, Autorreparación y Actualización Inteligente

Extiende el Gate transversal existente sin crear una fuente paralela. Opera en cuatro modos:

1. **Monitor permanente:** sonda externa de `/api/ready`, historial JSONL y métricas.
2. **Diagnóstico manual:** autenticación/JWT, matriz RBAC, estructura mínima de base y análisis agregado de logs.
3. **Gate rápido o completo:** contratos, formatos, plantillas oficiales, sintaxis, PostgreSQL y regresión automática.
4. **Autorreparación segura:** primero genera un plan y solo con autorización elimina cachés/temporales obsoletos o rota logs.

## Límites inviolables

El motor no modifica usuarios, hashes, roles, permisos, fundaciones, participantes, Base Maestra, tablas de negocio, migraciones productivas ni plantillas/formatos oficiales. Los diagnósticos de logs solo entregan conteos y nombres de archivo; nunca cuerpos de solicitudes, credenciales, cookies o JWT.

## API

- `GET /api/integrity/status`, `/architecture`, `/monitor`, `/metrics`
- `POST /api/integrity/diagnostic` con modo `MANUAL`, `QUICK` o `FULL`
- `POST /api/integrity/run`
- `POST /api/integrity/safe-repair` (`apply=false` por defecto)

Los reportes auditables se escriben en `data/integrity/`.
