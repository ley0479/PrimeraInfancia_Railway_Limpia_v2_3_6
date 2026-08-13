# Sistema Integral del Componente Pedagógico — Prompt 10

## Decisión arquitectónica

El sistema amplía `planeacion_pedagogica` y no crea un tercer módulo ni una
fuente espejo. Las fuentes canónicas siguen siendo:

- `pp_planeaciones`: planeaciones pedagógicas.
- `pp_actividades`: ejecución programada y realizada.
- `pp_evidencias_planeacion`: referencias a evidencias, sin copiar archivos.
- `pp_documentos_generados`: borradores documentales derivados.
- `gp_calendario_eventos` / `gp_entregables`: integración histórica con el
  calendario y entregables operativos.
- `pp_proyectos_pedagogicos`: cabecera única por fundación, UCA y vigencia.
- `pp_proyecto_versiones`: versiones inmutables del proyecto.
- `pp_seguimientos_pedagogicos`: seguimiento vinculado por IDs a proyecto,
  planeación y actividad.

## Flujo del proyecto pedagógico

1. Una docente, coordinación o gerencia crea el proyecto por UCA y vigencia.
2. El sistema crea la versión 1 en estado `BORRADOR`.
3. Las planeaciones crean actividades y referencias de calendario mediante el
   flujo preexistente.
4. `actualizar-desde-ejecucion` lee actividades ejecutadas de la misma
   fundación y UCA, y crea una nueva versión en `BORRADOR_ACTUALIZACION`.
5. La generación automática conserva IDs de las fuentes utilizadas y nunca
   aprueba ni reemplaza silenciosamente una versión.
6. Solo la docente asignada puede ejecutar la validación final; el control es
   fail-closed cuando no existe asignación docente.

## API

- `GET|POST /api/planeacion-pedagogica/proyectos-pedagogicos`
- `GET /api/planeacion-pedagogica/proyectos-pedagogicos/<id>`
- `POST /api/planeacion-pedagogica/proyectos-pedagogicos/<id>/actualizar-desde-ejecucion`
- `POST /api/planeacion-pedagogica/proyectos-pedagogicos/<id>/validar-docente`

Las rutas reutilizan la autenticación opaca vigente, el contexto de fundación y
las asignaciones `gp_docentes` / `gp_coordinadores`. No almacenan diagnósticos
automáticos ni datos clínicos.

## Controles verificados

- Sintaxis Python y JavaScript.
- Auditoría SQL PostgreSQL: `PASS`, sin construcciones incompatibles.
- Tablas aprovisionadas en PostgreSQL local.
- Login y lecturas autenticadas: HTTP 200.
- Creación y actualización versionada: HTTP 201.
- SUPERADMIN intentando sustituir validación docente: HTTP 403.
- Datos QA retirados después de la prueba.

## Extensiones posteriores

Los formatos oficiales deben registrarse en `pp_plantillas_documento` y los
archivos generados siempre nacen como borradores. Una extensión posterior puede
incorporar edición estructurada de cada sección y más indicadores sin alterar
las fuentes canónicas definidas aquí.
