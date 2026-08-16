# Patch regenerado: Calendario, Entregables y Listados

Este paquete fue regenerado porque el enlace anterior apuntaba a un archivo que no quedó físicamente creado.

## Alcance real incluido

- Módulo `calendario_inteligente` existente en la baseline v2.7.0.
- Módulo `centro_planeacion` existente en la baseline v2.7.0.
- Lectura de cronogramas Word, Excel, PowerPoint y PDF conforme al código incluido.
- Carga de evidencias y panel/calendario existentes.
- Migraciones del calendario inteligente.
- Servicio y migración RAM oficial v3.
- Formato oficial RAM suministrado por el usuario, conservado como plantilla fuente.
- Lista de chequeo mensual suministrada por el usuario como documento fuente.
- Archivos frontend correspondientes.

## Regla de oro

El instalador crea una copia de seguridad de cada archivo que vaya a reemplazar. No modifica `app.py`, `frontend/index.html` ni `frontend/js/app.js` automáticamente. Al finalizar verifica si las referencias de registro ya existen y muestra cualquier integración faltante.

## Uso

Desde la raíz de este paquete:

```bash
python aplicar_patch.py "RUTA_AL_REPOSITORIO"
```

Ejemplo Windows:

```powershell
python aplicar_patch.py "C:\Users\kioskUser0\Documents\PrimeraInfancia_v2_7_0_CENTRO_PLANEACION_PSICOSOCIAL"
```

Después revise `REPORTE_APLICACION_PATCH.txt` en la raíz del repositorio y ejecute las pruebas del proyecto antes de desplegar.
