# Informe de implementación — Expediente Operativo central por UCA 2.5.2

**Versión fuente:** PrimeraInfancia 2.5.1 — Autenticación y concurrencia SQLite estabilizadas  
**Versión resultante:** PrimeraInfancia 2.5.2 — Expediente Operativo central por UCA  
**Fecha:** 5 de agosto de 2026

## 1. Objetivo atendido

Convertir el Expediente Operativo por UCA en el centro de consulta y preparación para supervisión de la plataforma, integrando los módulos existentes sin crear una segunda Base Maestra ni duplicar participantes, valoraciones, planeaciones, entregables o archivos.

La implementación toma como referente el Manual Técnico de la Modalidad Propia e Intercultural, que organiza la atención alrededor de seis componentes de calidad y de una ruta operativa con fases preparatoria, implementación y cierre.

## 2. Arquitectura adoptada

Se implementó una arquitectura de **lectura integrada y referencias**:

```text
Módulos operativos existentes
        │
        ├── Base Maestra
        ├── Pedagogía
        ├── Salud y Nutrición
        ├── RAM / RPP / Bienestarina
        ├── Talento Humano
        ├── Calendario
        └── Reportes
        │
        ▼
UCAIntegrationEngine (consultas de solo lectura)
        │
        ├── Vista única por UCA
        ├── Indicadores derivados
        ├── Alertas consolidadas
        ├── Cronograma consolidado
        ├── Índice documental referencial
        └── Preparación para supervisión
```

Los registros originales continúan siendo administrados por sus módulos de origen. El Expediente central consulta esas fuentes y guarda únicamente:

- El expediente UCA y su ruta operativa.
- Los ocho planes.
- Referencias a documentos existentes.
- Historial de paquetes de supervisión.
- Auditoría de operaciones propias del expediente.

## 3. Funciones implementadas

### 3.1 Vista única por UCA

Se añadió el endpoint:

```text
GET /api/gestion-integral-uca/expedientes/<id>/vista-unica
```

La respuesta reúne:

- Identificación de la UCA.
- Ocho dominios integrados.
- Indicadores.
- Alertas.
- Cronograma.
- Documentos vinculados.
- Estado de fuentes.
- Porcentaje de preparación para supervisión.

### 3.2 Ocho dominios integrados

1. Base Maestra y población.
2. Proceso pedagógico.
3. Salud y Nutrición.
4. RAM, RPP y Bienestarina.
5. Talento Humano.
6. Documentos y evidencias.
7. Cronograma y calendario.
8. Reportes e indicadores.

Cada dominio informa sus fuentes, métricas y semáforo. La consulta se filtra por `fundacion_id` y por el nombre o código de la UCA.

### 3.3 Indicadores derivados

Se implementaron indicadores iniciales como:

- Participantes activos.
- Calidad de Base Maestra.
- Cobertura de valoración nutricional.
- Cumplimiento pedagógico.
- Talento humano activo.
- Alertas abiertas.
- Cumplimiento del cronograma.

Estos indicadores son derivados de los registros existentes y no modifican las tablas fuente.

### 3.4 Alertas consolidadas

La vista reúne inicialmente:

- Alertas abiertas de Salud y Nutrición.
- Inconsistencias de Base Maestra.
- Entregables o actividades vencidas del calendario.

La plataforma conserva el módulo de origen como responsable de resolver cada alerta.

### 3.5 Cronograma consolidado

Se consultan calendarios existentes y se muestran por UCA:

- Fecha.
- Título.
- Descripción.
- Estado.
- Prioridad.
- Responsable.
- Fuente.
- Condición de vencimiento.

El expediente no crea un calendario paralelo.

### 3.6 Índice documental único

Se creó la tabla:

```text
giu_vinculos_documentales
```

Esta tabla almacena referencias, no copias de archivos. Conserva:

- Módulo fuente.
- Tabla e identificador fuente.
- Categoría.
- Título.
- Estado.
- Fecha.
- Ruta autorizada.
- Nombre.
- Versión.
- Metadatos.

La sincronización es idempotente mediante una restricción única por fundación, expediente, tabla e identificador fuente.

La descarga solo se autoriza cuando el archivo está dentro de `DATA_DIR`.

### 3.7 Preparación para supervisión

Se calcula un porcentaje orientativo a partir de:

- Calidad de datos.
- Cobertura de valoración.
- Cumplimiento pedagógico.
- Talento activo.
- Cronograma.
- Documentos vinculados.

También se muestran bloqueos concretos. Este cálculo facilita la preparación, pero no reemplaza la decisión del supervisor o interventor.

### 3.8 Paquete de supervisión ampliado

El ZIP de supervisión incorpora ahora:

```text
00_RESUMEN_EXPEDIENTE.json
01_RUTA_OPERATIVA.csv
02_OCHO_PLANES.csv
03_MANIFIESTO_EVIDENCIAS.csv
04_TRAZABILIDAD.csv
05_INDICADORES_UCA.csv
06_ALERTAS_UCA.csv
07_CRONOGRAMA_UCA.csv
08_DOCUMENTOS_VINCULADOS.csv
09_ESTADO_COMPONENTES.json
10_PREPARACION_SUPERVISION.json
11_FUENTES_INTEGRADAS.json
LEEME.txt
```

Cuando un documento referenciado está dentro del almacenamiento autorizado, se incluye en `documentos_vinculados/`.

El historial de paquetes queda en:

```text
giu_paquetes_supervision
```

### 3.9 Interfaz

El Expediente dispone de las pestañas:

- Centro operativo.
- Componentes.
- Documentos.
- Alertas.
- Cronograma.
- Indicadores.
- Ruta operativa.
- Ocho planes.
- Biblioteca.

El listado de UCA permanece ligero: la integración completa se calcula únicamente al abrir un expediente.

## 4. Seguridad y aislamiento

- Todas las consultas que disponen de `fundacion_id` se filtran por la fundación autenticada.
- Las consultas por UCA comparan nombre y código normalizados.
- Los documentos solo se descargan desde `DATA_DIR`.
- La vista no expone rutas físicas al navegador.
- No se crean copias de participantes, valoraciones o planeaciones.
- Los paquetes se almacenan en el directorio tenant correspondiente.
- Se conservan los permisos y el aislamiento multi-fundación existentes.

## 5. Cambios de esquema

La versión del esquema GIU pasó a `2` y añadió únicamente tablas del propio expediente:

```text
giu_vinculos_documentales
giu_paquetes_supervision
```

No se alteraron columnas de Base Maestra, Salud, Pedagogía, Talento Humano, RAM, RPP o Bienestarina.

## 6. Pruebas ejecutadas

Se creó la suite:

```text
backend/tests/test_expediente_uca_central_v2_5_2.py
```

La prueba utiliza dos fundaciones y UCA ficticias y verifica:

- Vista única con ocho dominios.
- Aislamiento por fundación y UCA.
- Participantes y valoraciones filtrados correctamente.
- RAM, RPP y Bienestarina integrados.
- Alertas sin cruces de tenant.
- Cronograma por UCA.
- Índice documental idempotente.
- Descarga autorizada desde `DATA_DIR`.
- No duplicación de registros operativos.
- Paquete de supervisión ampliado.
- Contrato estático de frontend y API.

También se ejecutaron las suites heredadas desde 2.3.7 hasta 2.5.1.

## 7. Compatibilidad

Se conservaron:

- Autenticación estable 2.5.1.
- Multi-fundación.
- Base Maestra.
- RAM/RPP/Bienestarina.
- Gestión Pedagógica.
- Salud y Nutrición.
- Talento Humano.
- Biblioteca Oficial ICBF.
- Túnel Cloudflare.
- Railway/Docker.

## 8. Limitaciones reales

La integración se basa en las tablas y columnas presentes. Cuando un módulo no está instalado, no posee datos o utiliza nombres de columnas no reconocidos, la fuente aparece como no disponible o sin registros.

No se ejecutó en este entorno:

- Navegador completo contra Flask.
- PowerShell.
- Cloudflare real.
- Docker completo.
- Railway con volumen y tráfico real.

Por tanto, la versión debe validarse con datos ficticios en Windows y luego en un entorno de prueba de Railway antes de utilizar información personal real.

## 9. Próximos pasos recomendados

1. Probar dos fundaciones y dos UCA por fundación.
2. Confirmar los nombres reales de tablas y campos de cada módulo.
3. Crear adaptadores adicionales para fuentes no reconocidas.
4. Añadir reglas parametrizables de indicadores por contrato y modalidad.
5. Añadir firma/aprobación del paquete de supervisión.
6. Ejecutar prueba de persistencia mediante redeploy de Railway.
