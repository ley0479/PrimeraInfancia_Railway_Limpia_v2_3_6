# Prompt Maestro de Continuidad y No Regresión

Aplica obligatoriamente a **todos los formatos actuales y futuros** de Primera Infancia, incluidos Excel, PDF, Word, reportes, exportaciones, plantillas cargadas y formatos generados dinámicamente.

## Reglas obligatorias

1. Trabajar sobre la última carpeta y versión estable real. Nunca reconstruir el proyecto desde una copia anterior.
2. Antes de modificar, consultar `integrity/format_capabilities.json`, el historial disponible y las pruebas relacionadas.
3. Tratar cada formato y cada capacidad registrada como `PROTECTED`.
4. Aplicar cambios mínimos mediante parche diferencial. No reemplazar archivos centrales completos cuando el cambio pueda aislarse.
5. No editar un archivo generado esperando cambiar su plantilla. Las plantillas oficiales deben cargarse como versión, probarse, registrar su hash y publicarse como vigentes.
6. Toda mejora funcional debe agregar o actualizar una prueba permanente que falle si la mejora desaparece.
7. Un formato nuevo debe registrarse antes de publicarse. Los formatos desconocidos se consideran sin prueba y bloquean el despliegue.
8. Ejecutar el Motor de Integridad antes de declarar estable una versión. Cualquier pérdida de capacidad produce `BLOCKED`.
9. No actualizar la línea base para ocultar un fallo. Solo se actualiza después de verificar que el cambio es intencional, acumulativo y aprobado.
10. Entregar un resumen diferencial: versión estable de origen, archivos modificados, capacidades agregadas, capacidades preservadas, pruebas ejecutadas y resultado del gate.

## Condición de aceptación

Una mejora se acepta únicamente cuando conserva todas las capacidades protegidas, incorpora pruebas de la nueva conducta, mantiene trazabilidad de versión y hash cuando corresponda, y el Deployment Gate termina en `PASS`. En cualquier otro caso el resultado obligatorio es `BLOCKED`.
