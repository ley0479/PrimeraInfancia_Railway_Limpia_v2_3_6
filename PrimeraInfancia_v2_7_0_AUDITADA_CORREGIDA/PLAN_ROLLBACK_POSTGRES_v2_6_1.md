# Plan de rollback PostgreSQL — PrimeraInfancia 2.6.1

## 1. Principio

El rollback no consiste en copiar automáticamente datos nuevos de PostgreSQL hacia el SQLite antiguo. Tras el corte, ambos sistemas divergen. La decisión debe tomarse antes de reabrir escrituras productivas o mediante un plan explícito de reconciliación.

## 2. Puntos de restauración

Conservar:

1. SQLite original.
2. Snapshot consistente del corte.
3. Reporte y SHA-256.
4. `pg_dump` posterior a la migración.
5. Código de la versión estable 2.6.0.
6. Manifiesto de cutover.

## 3. Rollback antes de abrir producción

Si falla cualquier verificación:

- no active `DATABASE_URL`;
- descarte o limpie el PostgreSQL de pruebas;
- mantenga la plataforma en SQLite estable;
- corrija el defecto;
- repita sobre un PostgreSQL vacío.

## 4. Rollback inmediatamente después del corte

Si no se han aceptado escrituras nuevas:

1. Ponga el servicio en mantenimiento.
2. Retire `DATABASE_URL` PostgreSQL o apunte temporalmente al SQLite estable en un entorno controlado.
3. Despliegue la versión estable.
4. Verifique integridad y login.
5. Documente el incidente.

## 5. Si PostgreSQL ya recibió datos nuevos

No vuelva al SQLite sin reconciliación. Opciones:

- restaurar un `pg_dump` a otro PostgreSQL sano;
- corregir infraestructura y mantener PostgreSQL;
- construir una exportación inversa controlada y validada, que no forma parte de la autorreparación.

## 6. Restauración PostgreSQL

Use los scripts de respaldo/restauración o herramientas oficiales:

```text
RESPALDAR_POSTGRESQL.bat
RESTAURAR_POSTGRESQL.bat
```

El respaldo recomendado es formato custom para permitir `pg_restore` selectivo y validación previa.

## 7. Criterios para detener el despliegue

- discrepancia de filas;
- discrepancia de huellas;
- claves foráneas no validadas;
- gate bloqueado;
- login fallido;
- aislamiento entre fundaciones fallido;
- RAM/RAN/RPP/Bienestarina incorrectos;
- pérdida de documentos o evidencias;
- readiness inestable;
- restauración no comprobada.

## 8. Responsables y aprobación

La ejecución productiva debe registrar:

- responsable técnico;
- responsable funcional;
- aprobador del corte;
- hora de congelamiento;
- hora de migración;
- hora de verificación;
- decisión de apertura o rollback;
- rutas de los respaldos y reportes.
