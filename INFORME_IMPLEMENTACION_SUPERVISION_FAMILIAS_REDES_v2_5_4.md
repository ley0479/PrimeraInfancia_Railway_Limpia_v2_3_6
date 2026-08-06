# Informe de implementación — PrimeraInfancia 2.5.4

## Centro Inteligente de Supervisión, Auditoría y Calidad + Gestión Integral de Familias, Comunidad y Redes

**Versión fuente:** 2.5.3 — Biblioteca Oficial ICBF y Motor Inteligente de Gestión  
**Versión resultante:** 2.5.4 — Supervisión, Familias, Comunidad y Redes  
**Fecha de preparación:** 5 de agosto de 2026

## 1. Propósito

Esta entrega implementa dos capacidades de la hoja de ruta funcional:

1. **Centro Inteligente de Supervisión, Auditoría y Calidad**, para consolidar verificaciones, hallazgos, planes de mejora, acciones, seguimientos, evidencias y productos por fundación, UCA, contrato y vigencia.
2. **Módulo de Gestión Integral de Familias, Comunidad y Redes de Apoyo**, como espacio especializado del equipo psicosocial para organizar expedientes familiares referenciales, actividades, asistencias, compromisos, seguimientos, redes territoriales, alertas, evidencias y productos documentales.

La solución parte del Manual Técnico Modalidad Propia e Intercultural para la Atención a la Primera Infancia, MT3.PP, versión 2 del 26 de diciembre de 2025. El manual exige soportar las condiciones de calidad para que puedan verificarse y organiza la modalidad en seis componentes. Para Familia, Comunidad y Redes Sociales plantea acompañamiento y fortalecimiento familiar, y movilización comunitaria alrededor de la protección integral.

## 2. Decisiones de arquitectura

- No se creó una segunda Base Maestra.
- Los participantes no se copian: `fcr_expedientes_familiares` conserva referencias al participante y a su UCA.
- Todas las tablas nuevas incluyen `fundacion_id`.
- Las operaciones consultan la fundación autenticada y, para roles operativos, aplican alcance por UCA en modo **fail-closed**.
- Los archivos se guardan dentro del almacenamiento del tenant y reciben huella SHA-256.
- Supervisión y Familias se enlazan con el Motor de Gestión mediante claves de fuente idempotentes.
- El Expediente Operativo por UCA integra métricas, alertas, cronograma y documentos de ambos módulos.
- Ningún hallazgo, plan, acción, compromiso o alerta se cierra automáticamente.
- Los documentos generados son borradores y requieren revisión humana.
- La implementación no crea historias clínicas, diagnósticos automáticos ni decisiones jurídicas.

## 3. Centro Inteligente de Supervisión, Auditoría y Calidad

### 3.1 Flujo funcional

```text
Programación de supervisión
        ↓
Lista de verificación configurable
        ↓
Evaluación por criterio
        ↓
Hallazgos explícitos
        ↓
Planes y acciones de mejora
        ↓
Seguimientos y evidencias
        ↓
Revisión y validación humana
        ↓
Productos PDF, Excel y ZIP
```

### 3.2 Catálogo inicial

Se incorporaron 14 criterios base relacionados con información, Ruta Operativa, familia y comunidad, salud y nutrición, pedagogía, talento humano, ambientes, obligaciones contractuales, control social, eventos críticos y mejora continua. El catálogo es una ayuda de verificación; no constituye certificación automática.

### 3.3 Supervisiones y verificaciones

Cada supervisión conserva:

- UCA y expediente operativo.
- Contrato, vigencia y modalidad de visita.
- Objetivo, alcance, responsables y fechas.
- Estado y porcentaje de cumplimiento.
- Verificaciones por criterio, resultado, observaciones, riesgo y evidencia.
- Historial de cambios.

Los resultados disponibles son `PENDIENTE`, `CUMPLE`, `PARCIAL`, `NO_CUMPLE` y `NO_APLICA`.

### 3.4 Hallazgos y planes de mejora

Un hallazgo se crea de forma explícita y no modifica el registro fuente. Puede contener código, componente, riesgo, responsable, fecha límite, resolución propuesta, planes, acciones, seguimientos y motivo de cierre.

Controles implementados:

- Un hallazgo no puede cerrarse sin plan de mejora.
- Todos sus planes deben estar cerrados y validados.
- Una acción configurada con evidencia obligatoria no puede validarse sin soporte.
- La aprobación y el cierre requieren un rol autorizado.
- Cada transición queda auditada.

### 3.5 Productos

Por supervisión se preparan:

- **MATRIZ_EXCEL** con verificaciones, hallazgos y acciones.
- **INFORME_PDF** en estado de borrador.
- **PAQUETE_ZIP** con matrices, informe, manifiestos y evidencias disponibles.

Los productos guardan tamaño, MIME, SHA-256, usuario y fecha de generación. No sustituyen la decisión del supervisor o interventor.

## 4. Gestión Integral de Familias, Comunidad y Redes

### 4.1 Expedientes familiares referenciales

La sincronización consulta la Base Maestra y crea o actualiza referencias familiares por fundación y UCA. Ejecutarla varias veces no duplica expedientes. Se conservan vínculos al participante, cuidador, contactos, territorio, estado y trazabilidad.

### 4.2 Actividades y asistencias

Permite programar escuelas de familias, encuentros, acompañamientos y otras actividades autorizadas. Cada actividad maneja objetivo, metodología, fechas, lugar, profesional, resultados, conclusiones, compromisos y asistentes.

Al crear una actividad, la plataforma prepara automáticamente como **BORRADOR**:

- Acta en PDF.
- Listado de asistencia en XLSX.

También puede preparar un informe en PDF. Los campos profesionales faltantes permanecen explícitamente pendientes; el sistema no inventa resultados.

### 4.3 Compromisos y seguimientos

Los compromisos conservan responsable, prioridad, fecha límite, avance, seguimientos y estado. Se enlazan con el Motor de Gestión. El cierre requiere 100 % de avance reportado y validación humana de coordinación.

### 4.4 Redes de apoyo

Se pueden registrar actores territoriales, tipo, territorio, contacto, servicios y rutas. La verificación de la red queda separada del simple registro y solo la realiza coordinación.

### 4.5 Alertas

Las alertas conservan familia, actividad, UCA, tipo, nivel, descripción, entidad de ruta, responsable, próximo seguimiento y estado. No pueden cerrarse mediante una edición genérica. El cierre exige un resultado profesional y una referencia de evidencia.

### 4.6 Evidencias y productos

Las evidencias se guardan por tenant con huella SHA-256. El módulo puede preparar un paquete ZIP de seguimiento con resumen, actividades, compromisos, alertas, redes, documentos y manifiesto.

**Decisión de privacidad:** esta entrega no incorpora una tabla de notas clínicas o historias psicosociales reservadas. Los acompañamientos operativos se representan mediante actividad, compromiso, seguimiento, alerta y evidencia. Una futura historia psicosocial requerirá un diseño adicional de confidencialidad, retención y acceso reforzado.

## 5. Roles y alcance

### Supervisión y Calidad

- Consulta: `SUPERADMIN`, `GERENTE`, `COORDINADOR`, `AUXILIAR_ADMINISTRATIVO`, `DOCENTE`, `NUTRICIONISTA`, `PSICOSOCIAL` dentro de su alcance.
- Gestión: coordinación y apoyo administrativo según la operación.
- Aprobación/cierre: `SUPERADMIN`, `GERENTE`, `COORDINADOR`.
- Roles operativos sin UCA asignada reciben cero resultados.

### Familias, Comunidad y Redes

- Consulta y operación: `SUPERADMIN`, `GERENTE`, `COORDINADOR`, `PSICOSOCIAL`.
- Validación/cierre: `SUPERADMIN`, `GERENTE`, `COORDINADOR`.
- El rol psicosocial sin UCA explícitamente asignada no obtiene acceso global.

## 6. Integraciones

Se preservan y reutilizan:

- Autenticación concurrente 2.5.1.
- Expediente UCA central 2.5.2.
- Biblioteca y Motor de Gestión 2.5.3.
- Base Maestra.
- Pedagogía.
- Salud y Nutrición.
- RAM, RPP y Bienestarina.
- Talento Humano.
- Calendario.
- Railway, Docker y scripts locales/túnel.

El Expediente Operativo ahora presenta diez dominios e incorpora `familias_redes` y `supervision_calidad`, con métricas, alertas, cronograma y vínculos documentales.

## 7. Modelo de datos nuevo

### Supervisión

`csc_checklist_catalogo`, `csc_supervisiones`, `csc_verificaciones`, `csc_hallazgos`, `csc_planes_mejora`, `csc_acciones_mejora`, `csc_seguimientos`, `csc_evidencias`, `csc_productos`, `csc_auditoria`, `csc_schema_version`.

### Familias y Redes

`fcr_expedientes_familiares`, `fcr_actividades`, `fcr_asistencias`, `fcr_compromisos`, `fcr_seguimientos`, `fcr_redes_apoyo`, `fcr_alertas`, `fcr_evidencias`, `fcr_documentos_generados`, `fcr_auditoria`, `fcr_schema_version`.

Las migraciones son idempotentes mediante `CREATE TABLE IF NOT EXISTS` y versión de esquema propia.

## 8. Pruebas automatizadas

Se probaron con datos ficticios:

- Dos fundaciones y UCA independientes.
- Sincronización familiar idempotente.
- Acta y listado automáticos en borrador.
- Registro de asistencia.
- Compromisos con seguimiento y cierre humano.
- Redes verificadas.
- Alertas con resultado y evidencia de cierre.
- Evidencias con SHA-256.
- Paquete familiar ZIP.
- Checklist de 14 criterios.
- Hallazgos, planes, acciones y seguimientos.
- Reglas de cierre humano.
- Productos XLSX, PDF y ZIP.
- Sincronización del Motor sin duplicados.
- Expediente UCA con diez dominios.
- Aislamiento entre fundaciones.
- Alcance por UCA en modo fail-closed.

## 9. Limitaciones honestas

No se ejecutaron desde el entorno de preparación:

- Navegador completo contra Flask en Windows.
- PowerShell real.
- Cloudflare Tunnel real.
- Docker completo.
- Railway con volumen y tráfico simultáneo.

La entrega es una **candidata para pruebas controladas con información ficticia**. Antes de utilizar datos personales reales se requiere prueba funcional, revisión de permisos, evaluación de privacidad y aprobación institucional.
