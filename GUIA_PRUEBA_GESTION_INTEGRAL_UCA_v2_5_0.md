# Guía de prueba — Gestión Integral por UCA 2.5.0

## 1. Preparación

1. Conserva la carpeta 2.4.3 como respaldo.
2. Extrae la versión 2.5.0 en una ruta corta, por ejemplo:

```text
C:\PI_V250
```

3. Para conservar datos de prueba, copia únicamente la carpeta `data` desde la instalación anterior.
4. No copies:

```text
backend\.venv
.runtime_windows
logs_tunel
tools\cloudflared
ENLACE_PUBLICO_TUNEL.txt
```

## 2. Inicio local

Ejecuta:

```text
INICIAR_PLATAFORMA_LOCAL.bat
```

Confirma:

```text
http://127.0.0.1:5000/api/health
```

La versión esperada es:

```text
2.5.0-gestion-integral-uca
```

## 3. Prueba del Expediente Operativo

1. Inicia sesión como `SUPERADMIN`, `GERENTE`, `COORDINADOR` o `AUXILIAR_ADMINISTRATIVO`.
2. Abre **Gestión Integral UCA → Expediente Operativo**.
3. Selecciona vigencia y contrato.
4. Pulsa **Sincronizar UCA**.
5. Confirma que se crea un expediente por UCA sin duplicados.
6. Repite la sincronización: el número de expedientes y actividades no debe aumentar.

## 4. Prueba de roles y UCA

Crea cuentas ficticias con roles:

- DOCENTE.
- NUTRICIONISTA.
- PSICOSOCIAL.
- COORDINADOR.

Asigna UCA diferentes. Verifica:

- el profesional consulta solamente sus UCA asignadas;
- el coordinador consulta toda la fundación;
- ningún usuario de una fundación puede consultar otra;
- un profesional operativo no puede aprobar ni cerrar actividades o planes.

## 5. Prueba de Ruta Operativa

1. Abre una actividad pendiente.
2. Asigna responsable y fecha límite.
3. Intenta aprobar sin evidencia: debe rechazarse.
4. Carga un archivo ficticio.
5. Envía a revisión.
6. Aprueba con un rol de coordinación.
7. Revisa que el progreso, la fase y el semáforo cambien.
8. Para “No aplica”, confirma que se exija justificación.

## 6. Prueba del Calendario

Al guardar una fecha límite, abre el Calendario Inteligente y verifica el entregable generado con origen `gestion_integral_uca`. Cambiar la fecha debe actualizar el mismo entregable, no crear otro.

## 7. Prueba de los ocho planes

1. Asigna responsable y progreso a cada plan.
2. Guarda objetivos, actividades e indicadores mediante la API o interfaz habilitada.
3. Envía un plan a revisión.
4. Intenta aprobar como profesional operativo: debe rechazarse.
5. Aprueba como coordinador.

## 8. Prueba de evidencias

Carga archivos ficticios permitidos. Comprueba:

- tamaño mayor que cero;
- versión consecutiva;
- SHA-256 registrado;
- descarga autenticada;
- rechazo al intentar descargar un archivo fuera del almacenamiento del tenant;
- evento de auditoría de carga y descarga.

## 9. Prueba de Biblioteca Oficial ICBF

1. Abre **Biblioteca Oficial ICBF**.
2. Registra un documento ficticio.
3. Carga versión 1 y versión 2.
4. Vincula el documento con un módulo.
5. Activa la versión 2 como `SUPERADMIN` o `GERENTE`.
6. Confirma que la anterior quede histórica.
7. Descarga el archivo y verifica el SHA-256.
8. Repite en otra fundación y confirma aislamiento.

No utilices esta prueba para extraer automáticamente archivos de una intranet o sistema que requiera credenciales.

## 10. Paquete de supervisión

Con un rol de coordinación:

1. Abre el expediente.
2. Pulsa **Paquete supervisión**.
3. Verifica que el ZIP incluya resumen, ruta, ocho planes, manifiesto de evidencias, trazabilidad y `LEEME.txt`.
4. Comprueba que no contenga archivos de otra fundación.

## 11. Prueba de persistencia en Railway

1. Monta el volumen en `/data`.
2. Crea expedientes, planes, biblioteca y evidencias ficticias.
3. Ejecuta un redeploy.
4. Confirma que todo permanezca.
5. Revisa que los paquetes se almacenen bajo `/data/tenants/<id>/`.

## 12. Criterios de aceptación

La prueba se aprueba cuando:

- no existen cruces entre fundaciones;
- la asignación de UCA se respeta;
- la sincronización es idempotente;
- no se aprueba sin evidencia obligatoria;
- los ocho planes existen una sola vez;
- la versión vigente de biblioteca es única por documento;
- el paquete de supervisión corresponde al tenant actual;
- los datos permanecen después del redeploy;
- los logs no contienen contraseñas, tokens ni archivos personales.

Utiliza solamente información ficticia hasta completar todos estos controles.
