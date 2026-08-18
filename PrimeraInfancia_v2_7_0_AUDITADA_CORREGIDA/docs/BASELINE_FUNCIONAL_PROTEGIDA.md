# Baseline funcional protegida

Esta baseline aplica el Protocolo Maestro de Reglas de Oro a Primera Infancia.
Su registro ejecutable es `integrity/protected_functionality.json` y el gate que
la valida es `backend/tools/integrity_gate.py`.

## Flujo obligatorio de cambio

1. Registrar commit, rama y estado del repositorio. Si Git no está disponible,
   declarar explícitamente que no existe checkpoint Git y no inventar historial.
2. Ejecutar el gate previo y conservar su reporte como evidencia `before`.
3. Clasificar componentes como PROTEGIDO, RELACIONADO u OBJETIVO.
4. Inventariar ruta, método, consumidores, datos, tenant, archivos y pruebas.
5. Aplicar el parche mínimo. No modificar componentes protegidos sin necesidad
   técnica demostrada.
6. Ejecutar prueba específica, pruebas relacionadas y gate completo.
7. Comparar la matriz antes/después. Cualquier regresión rechaza el cambio.
8. Crear un commit pequeño y descriptivo únicamente cuando exista Git.

## Matriz mínima obligatoria

| Función | Antes | Después requerido | Regresión permitida |
| --- | --- | --- | --- |
| Login | PASS | PASS | NO |
| Panel y navegación | PASS | PASS | NO |
| PostgreSQL | PASS | PASS | NO |
| Base Maestra | PASS | PASS | NO |
| Filtros UDS | PASS | PASS | NO |
| RAM | PASS | PASS | NO |
| RAN | PASS | PASS | NO |
| RRAN | PASS | PASS | NO |
| Bienestarina | PASS | PASS | NO |
| RPP | PASS | PASS | NO |
| Multi-tenant | PASS | PASS | NO |

## Artefactos protegidos

- PostgreSQL y sus datos reales.
- Contratos HTTP existentes: URL, método, autenticación, payload y respuesta.
- Aislamiento por `fundacion_id` y almacenamiento `TenantPath`.
- Plantillas oficiales y sus hashes.
- Compatibilidad local y Railway.

Actualizar una baseline para ocultar un fallo está prohibido. Una ampliación de
baseline solo procede después de demostrar que la capacidad nueva funciona y
que todas las capacidades anteriores continúan en PASS.
