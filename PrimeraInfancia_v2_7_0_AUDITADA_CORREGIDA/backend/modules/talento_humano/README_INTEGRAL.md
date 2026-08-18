# Sistema Integral de Talento Humano

Amplía `th_personas` y `th_asignaciones` sin copiar colaboradores. Agrega documentos y vencimientos, formación, evaluaciones de acompañamiento y mapa de capacidades.

- Todo registro incluye `fundacion_id` y referencia `th_personas.id`.
- Las evaluaciones nacen como `BORRADOR`; no califican automáticamente.
- El mapa de capacidades no crea rankings ni decisiones laborales.
- Las asignaciones UCA existentes siguen siendo la fuente canónica.

API: `/api/talento-core/integral/dashboard`, `/personas/<id>` y POST para `documentos`, `formaciones`, `evaluaciones` y `capacidades`.
