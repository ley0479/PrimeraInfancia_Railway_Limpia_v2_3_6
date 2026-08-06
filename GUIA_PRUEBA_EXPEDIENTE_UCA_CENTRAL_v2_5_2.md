# Guía de prueba — Expediente Operativo central por UCA 2.5.2

## 1. Preparación

1. Conserva la versión anterior como respaldo.
2. Extrae esta versión en una ruta corta, por ejemplo:

```text
C:\PI_V252
```

3. Para conservar información ficticia, copia únicamente `data`.
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
DETENER_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_LOCAL.bat
```

Entra con una cuenta autorizada.

## 3. Sincronización

1. Abre `Gestión Integral UCA → Expediente Operativo`.
2. Define vigencia y contrato.
3. Pulsa `Sincronizar UCA`.
4. Confirma que se cree un expediente por UCA sin duplicarse al repetir.

## 4. Vista central

Selecciona una UCA y revisa:

- Centro operativo.
- Componentes.
- Documentos.
- Alertas.
- Cronograma.
- Indicadores.
- Ruta Operativa.
- Ocho planes.
- Biblioteca.

## 5. Prueba de no duplicidad

1. Anota la cantidad de participantes de Base Maestra.
2. Abre y actualiza varias veces el Expediente.
3. Confirma que la cantidad en Base Maestra no cambia.
4. Confirma que las valoraciones, planeaciones y alertas no se duplican.

## 6. Prueba documental

1. Carga una evidencia desde un módulo fuente.
2. Vuelve a `Documentos`.
3. Pulsa `Sincronizar vínculos`.
4. Confirma que aparece una referencia única.
5. Descárgala.
6. Repite la sincronización y confirma que no se duplica.

## 7. Prueba de aislamiento

Con dos fundaciones ficticias:

- Crea UCA de nombres parecidos.
- Carga participantes, alertas y documentos diferentes.
- Confirma que cada cuenta solo vea su fundación.
- Confirma que usuarios limitados por UCA solo vean sus unidades asignadas.

## 8. Paquete de supervisión

Genera el paquete y confirma que incluya los archivos `00` a `11`, el `LEEME.txt` y los documentos autorizados.

## 9. Railway

Antes de información real:

1. Despliega en una rama o servicio de prueba.
2. Mantén una réplica y un worker mientras se use SQLite.
3. Confirma volumen persistente en `/data`.
4. Crea un dato ficticio.
5. Ejecuta redeploy.
6. Confirma que el dato persiste.

## 10. Criterio de aceptación

La versión se acepta cuando:

- No cruza fundaciones o UCA.
- No duplica registros operativos.
- Descarga únicamente archivos autorizados.
- Los indicadores coinciden con los módulos fuente.
- El paquete de supervisión abre correctamente.
- Los datos persisten después del redeploy.
