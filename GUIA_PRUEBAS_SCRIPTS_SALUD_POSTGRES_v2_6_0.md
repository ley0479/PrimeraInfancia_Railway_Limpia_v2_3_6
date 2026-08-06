# Guía de pruebas — PrimeraInfancia 2.6.0

## A. Scripts Windows

1. Extrae en una ruta corta, por ejemplo `C:\PI_V260`.
2. No copies `.runtime_windows`, `.venv`, `logs_tunel` ni `tools/cloudflared` de otra versión.
3. Ejecuta `DIAGNOSTICAR_INICIO_WINDOWS.bat`.
4. Ejecuta `INICIAR_PLATAFORMA_LOCAL.bat`.
5. Comprueba que no aparezcan comandos fragmentados como `t`, `not`, `r` o `et`.
6. Confirma que la ventana muestre la ruta correcta y que `/api/health` responda.
7. Ejecuta `DETENER_PLATAFORMA_LOCAL.bat` y verifica que solo cierre procesos de esta copia.

## B. Túnel

1. Inicia directamente `INICIAR_PLATAFORMA_TUNEL_ONLINE.bat`.
2. Mantén abiertas las ventanas.
3. Confirma la misma `project_instance_id` local y pública.
4. Prueba desde datos móviles.
5. Usa la misma cuenta de la base; el túnel no tiene contraseña propia.
6. Si falla, ejecuta `DIAGNOSTICAR_TUNEL_CLOUDFLARE.bat` y `DIAGNOSTICAR_INICIO_WINDOWS.bat`.

## C. Salud y Nutrición

Con dos fundaciones ficticias y al menos dos UCA por fundación:

1. Sincroniza expedientes dos veces y verifica que no se dupliquen.
2. Revisa estado de afiliación, vacunación, valoración, salud bucal y controles aplicables.
3. Registra mediciones antropométricas en el flujo existente.
4. Valida profesionalmente una valoración.
5. Genera CAPTURE XLSX/PDF.
6. Verifica que una valoración no validada no se presente como validada.
7. Crea una jornada de Educación para la Salud Alimentaria.
8. Genera acta, listado e informe en borrador.
9. Carga evidencia y comprueba SHA-256.
10. Crea una canalización, seguimiento y prueba el bloqueo de cierre sin evidencia.
11. Comprueba tableros del profesional y coordinación.
12. Confirma que una fundación no vea la otra.

## D. PostgreSQL

1. Migra una copia SQLite.
2. Compara conteos de todas las tablas.
3. Prueba login simultáneo.
4. Crea y edita información en cada módulo.
5. Reinicia backend.
6. Ejecuta respaldo `pg_dump` y valida con `pg_restore --list`.
7. Haz redeploy en Railway y confirma persistencia.

## E. Criterio de aprobación

La versión solo puede pasar a producción cuando:

- no existan errores de migración;
- todos los conteos coincidan;
- login y sesiones sean estables;
- aislamiento multi-fundación esté verificado;
- productos y evidencias persistan;
- respaldo y restauración hayan sido ensayados;
- exista autorización para tratar datos reales.
