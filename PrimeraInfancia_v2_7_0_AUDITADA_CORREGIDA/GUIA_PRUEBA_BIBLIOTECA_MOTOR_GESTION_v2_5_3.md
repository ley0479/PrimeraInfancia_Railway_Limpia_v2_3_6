# Guía de prueba — Biblioteca Oficial ICBF y Motor de Gestión 2.5.3

## Preparación

1. Conserva la versión 2.5.2.
2. Extrae esta versión en `C:\PI_V253`.
3. Copia únicamente `data` si deseas conservar datos ficticios.
4. No copies `.runtime_windows`, `backend\.venv`, `logs_tunel`, `tools\cloudflared` ni enlaces antiguos.
5. Ejecuta `DETENER_PLATAFORMA_LOCAL.bat`.
6. Ejecuta `INICIAR_PLATAFORMA_LOCAL.bat`.

## Prueba del Motor de Gestión

1. Entra a **Gestión Integral UCA → Motor de Gestión**.
2. Selecciona un periodo.
3. Pulsa **Sincronizar fuentes**.
4. Repite la sincronización y confirma que no duplique tareas.
5. Revisa prioridades, vencimientos y recordatorios.
6. Crea una tarea manual ficticia.
7. Pulsa **Preparar productos**.
8. Confirma que Excel, PDF y ZIP queden en `BORRADOR`.
9. Descarga los productos y verifica que abran correctamente.
10. Revisa y aprueba solamente después de comprobar el contenido.
11. Prepara un cierre mensual y confirma que no se cierre automáticamente.

## Prueba de Biblioteca

1. Entra a **Biblioteca Oficial ICBF**.
2. Registra un documento ficticio.
3. Carga una versión ficticia.
4. Consulta fuentes: el portal público inicial debe estar controlado y no habilitado para actualización automática.
5. Importa un candidato manual ficticio.
6. Aprueba sus metadatos.
7. Confirma que la versión quede `APROBADA`, no `VIGENTE`.
8. Carga o verifica el archivo oficial antes de activarla.
9. Revisa las relaciones sugeridas.
10. Comprueba notificaciones e historial.

## Prueba de aislamiento

Repite con dos fundaciones. Ninguna debe ver tareas, candidatos, versiones, notificaciones, productos o cierres de la otra.

## Integración remota futura

No habilites `BIBLIOTECA_REMOTE_CHECKS_ENABLED` hasta contar con:

- API o catálogo JSON oficial.
- Autorización de uso.
- Esquema de datos documentado.
- Dominio institucional permitido.
- Prueba en entorno no productivo.

## Railway

Mantén una réplica y un worker mientras se utilice SQLite. Comprueba persistencia del volumen `/data` después de un redeploy.
