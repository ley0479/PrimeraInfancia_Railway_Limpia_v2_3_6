# Guía de prueba — PrimeraInfancia 2.5.4

## Preparación

1. Conserva la versión 2.5.3 como respaldo.
2. Extrae la versión 2.5.4 en una ruta corta, por ejemplo `C:\PI_V254`.
3. Para conservar pruebas anteriores, copia únicamente la carpeta `data`.
4. No copies `.runtime_windows`, `backend\.venv`, `logs_tunel`, `tools\cloudflared` ni `ENLACE_PUBLICO_TUNEL.txt`.
5. Ejecuta `DETENER_PLATAFORMA_LOCAL.bat` y luego `INICIAR_PLATAFORMA_LOCAL.bat`.
6. Usa únicamente participantes, familias y evidencias ficticias.

## Supervisión y Calidad

1. Abre **Gestión Integral UCA → Supervisión y Calidad**.
2. Selecciona una UCA y crea una supervisión.
3. Confirma que se carguen 14 criterios.
4. Marca un criterio como `NO_CUMPLE`.
5. Crea un hallazgo.
6. Intenta cerrarlo sin plan y confirma que el sistema lo impida.
7. Crea un plan y una acción.
8. Si la acción exige evidencia, intenta validarla sin archivo y comprueba el bloqueo.
9. Registra seguimiento y evidencia.
10. Completa la acción, cierra el plan y valida el hallazgo.
11. Completa los criterios y cierra la supervisión con un rol de coordinación.
12. Genera Excel, PDF y ZIP.
13. Descarga los productos y confirma que no estén vacíos.

## Familias, Comunidad y Redes

1. Abre **Gestión Integral UCA → Familias y Redes**.
2. Selecciona una UCA y pulsa **Sincronizar familias**.
3. Repite la sincronización y confirma que no se creen duplicados.
4. Abre un expediente familiar y revisa que sea una referencia al participante existente.
5. Registra una red de apoyo y verifícala con coordinación.
6. Programa una escuela de familias o encuentro.
7. Confirma la generación de:
   - acta PDF en borrador;
   - listado de asistencia XLSX en borrador.
8. Registra asistencia.
9. Registra un compromiso y verifica su aparición en el Motor de Gestión.
10. Añade seguimiento; intenta cerrar antes del 100 % y confirma el bloqueo.
11. Registra una alerta ficticia.
12. Intenta cerrarla sin evidencia y confirma el bloqueo.
13. Añade resultado y referencia de evidencia, y valida el cierre.
14. Carga una evidencia ficticia y comprueba su descarga.
15. Genera el paquete de seguimiento y revisa `00_RESUMEN.json` y `LEEME.txt`.

## Aislamiento por fundación y UCA

1. Crea dos fundaciones ficticias.
2. Usa una UCA diferente en cada una.
3. Verifica que ninguna familia, alerta, documento, supervisión o producto sea visible desde la otra fundación.
4. Prueba un usuario `PSICOSOCIAL` sin UCA asignada: debe ver cero expedientes/actividades.
5. Asigna una UCA y confirma que solo pueda operar sobre ella.

## Integración con Expediente UCA

1. Abre una UCA en el Expediente Operativo.
2. Confirma que aparezcan los dominios `familias_redes` y `supervision_calidad`.
3. Comprueba alertas familiares, cronograma de supervisión y documentos vinculados.
4. Genera nuevamente el paquete de supervisión UCA.

## Motor de Gestión

1. Ejecuta **Sincronizar fuentes**.
2. Repite la operación.
3. Confirma que no se dupliquen tareas `fcr_*` o `csc_*`.

## Railway

Solo después de aprobar las pruebas locales:

1. Despliega en una rama o servicio de prueba.
2. Mantén una réplica y un worker mientras utilices SQLite.
3. Configura volumen persistente `/data`.
4. Ejecuta redeploy y comprueba persistencia.
5. Prueba dos sesiones y dos fundaciones con datos ficticios.
