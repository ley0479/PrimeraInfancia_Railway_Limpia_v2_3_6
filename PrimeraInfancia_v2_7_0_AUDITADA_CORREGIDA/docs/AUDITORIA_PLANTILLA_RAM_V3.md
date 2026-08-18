# Plantilla oficial RAM V3

- Código: `F27.MT1.PP`
- Versión: `3`
- Archivo activo: `backend/seed_data/templates_originales/oficiales/plantilla_ram_oficial_v3.xlsx`
- SHA-256 activo: `a6b4c9412f7c72a19b9d5e842fa5ffd4b876c7d0f0c3d5c8e140b5287d700753`
- Origen: archivo oficial suministrado por el usuario en la auditoría de agosto de 2026.
- Validación ejecutada: apertura, código/hojas y generación con 21 participantes (2 hojas RAM).
- Regla: la plantilla maestra no se modifica durante la generación; se llena una copia.

## Mapa aprobado desde la plantilla real

| Fuente canónica | Hoja / celda o rango | Regla |
|---|---|---|
| Fundación / EAS-PDS | `FORMATO RAM!A4` | Conserva el rótulo oficial |
| NIT | `A5` | Se escribe sin puntos, guiones ni espacios |
| Número de contrato | `D5` | No se inventa cuando falta |
| Regional | `F5` | Fundación/contrato |
| Centro Zonal | `H5` | Fundación/contrato |
| Municipio | `U5` | UDS/contrato |
| Mes | `A6` | Periodo solicitado |
| Año | `D6` | Periodo solicitado |
| Agente educativo | `F6` | Talento Humano de la UDS |
| Documento del agente | `I6` | Talento Humano de la UDS |
| Modalidad | `A7` | UDS |
| Código CUÉNTAME UDS | `F7` | UDS; nunca el consecutivo interno |
| Nombre UDS/UCA | `K7` | UDS estable seleccionada |
| Servicio de atención | `A8` | UDS/contrato |
| Dirección UDS | `F8` | UDS |
| Teléfono UDS | `T8` | UDS, no teléfono del participante |
| Orden | `A15:A34` | 20 participantes por página; acumulada en páginas adicionales |
| Tipo documento | `B15:B34` | Solo catálogo oficial |
| Número documento | `C15:C34` | Texto para preservar ceros |
| Primer/segundo nombre | `D15:E34` | Base Maestra |
| Primer/segundo apellido | `F15:G34` | Base Maestra |
| Edad años/meses | `H15:I34` | Calculada al primer día del periodo RAM |
| Asistencia diaria | `J:AH`, filas `15:34` | Solo registro electrónico explícito; sin fuente válida queda vacía |
| Total asistencias/inasistencias | `AI:AJ`, filas `15:34` | Derivado únicamente de marcas válidas |
| Causa de retiro | `AK15:AK34` | Catálogo oficial cuando existe retiro |
| Totales de página | `AI35`, `AJ35` | Suma de filas de la página |

La plantilla conserva combinaciones, dimensiones, fórmulas, estilos, área de
impresión e instrucciones. Para más de 20 participantes se copia la hoja RAM y
se conserva la hoja de instrucciones. La generación se bloquea si el SHA-256
activo no coincide con el archivo registrado.
