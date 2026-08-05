# Guía de aceptación — PrimeraInfancia 2.4.0 multi-fundación

Use esta guía **antes de cargar información real**. La prueba requiere un `SUPERADMIN`, dos fundaciones ficticias y dos usuarios ficticios.

## 1. Preparación y respaldo

1. Confirme que el servicio actual está `Online`.
2. Descargue un respaldo de la base y de las carpetas del volumen `/data`.
3. Anote el commit estable actual de GitHub.
4. Confirme un solo worker y una sola réplica.
5. Confirme que el volumen esté montado exactamente en `/data`.

## 2. Variables Railway

Configure y aplique:

```env
APP_VERSION=2.4.0-multifundacion-piloto
SINGLE_TENANT_MODE=false
ALLOW_EXPERIMENTAL_MULTI_TENANT=true
MULTI_TENANT_STRICT=true
TENANT_STORAGE_ISOLATION=true
MULTI_TENANT_SCHEMA_VERSION=3
```

Conserve los secretos actuales. No copie contraseñas en GitHub. Después del deploy, `/api/health` debe responder correctamente.

## 3. Crear tenants ficticios

Desde Administración, como `SUPERADMIN`:

1. Mantenga la fundación inicial como **Fundación Piloto A**.
2. Cree **Fundación Piloto B**.
3. Verifique que B quede `ACTIVA`, no `CONFIGURACION_PENDIENTE`.
4. Compruebe que B recibe UDS, suscripción, reglas y minuta de inicio.
5. Cree `usuario_a_prueba` asignado a A.
6. Cree `usuario_b_prueba` asignado a B.
7. No asigne datos, correos ni documentos de personas reales.

## 4. Matriz mínima de aislamiento

Ejecute cada prueba y marque resultado:

| Prueba | Usuario A | Usuario B | Resultado esperado |
|---|---|---|---|
| Ver fundaciones | Solo A | Solo B | No ve la otra fundación |
| Ver usuarios | Solo usuarios autorizados de A | Solo usuarios autorizados de B | Sin cruce |
| Crear beneficiario ficticio con documento `TEST-0001` | Sí | Sí | El mismo código puede existir en ambos tenants |
| Consultar beneficiarios | Solo A | Solo B | Sin cruce |
| Crear UDS con mismo nombre | En A | En B | Independientes |
| Subir archivo `evidencia-a.txt` / `evidencia-b.txt` | A | B | Cada usuario descarga únicamente el suyo |
| Generar RPP/RAM/Bienestarina | Datos de A | Datos de B | Formatos separados |
| Consultar trabajos | Solo trabajos A | Solo trabajos B | Sin cruce |
| Reporte gerencial | Solo datos A | Solo datos B | Sin cruce |
| Plantilla personalizada | Solo A | Solo B | Versiones independientes |

Una sola aparición de datos de la otra fundación es un **fallo crítico**: detenga la prueba, regrese al commit estable y conserve los logs.

## 5. Prueba de archivos

En Railway, mediante una consola o un diagnóstico administrativo, confirme que existan carpetas distintas:

```text
/data/tenants/1/
/data/tenants/2/
```

Suba un archivo ficticio desde cada usuario. Verifique que no termine en la misma carpeta física ni pueda descargarse usando la sesión del otro tenant.

## 6. Prueba de suspensión

1. Inicie sesión con el usuario B.
2. En otra ventana, el `SUPERADMIN` suspende Fundación B.
3. La sesión B debe dejar de funcionar.
4. Un nuevo login B debe responder que la fundación está suspendida.
5. Reactive B y compruebe que se requiere iniciar sesión de nuevo.

## 7. Persistencia

1. Cree un registro ficticio en A y otro en B.
2. Ejecute un redeploy sin borrar el volumen.
3. Confirme que ambos registros continúan.
4. Confirme que cada usuario sigue viendo únicamente el suyo.
5. Elimine todos los datos ficticios al terminar.

## 8. Regresión funcional

Pruebe al menos:

- login y cambio de contraseña;
- UDS y base maestra;
- RPP de un periodo con minuta válida;
- RAM histórica y RAM V3;
- Bienestarina;
- cronograma y evidencias;
- reportes y paquete mensual;
- carga y descarga institucional;
- copia de seguridad y restauración controlada.

## 9. Criterio para continuar

Solo avanzar hacia datos reales cuando:

- todas las filas de la matriz pasen;
- el volumen sobreviva al redeploy;
- no haya secretos ni datos personales en logs;
- exista respaldo verificable;
- se haya probado restauración;
- roles y suspensión funcionen;
- el responsable de protección de datos autorice el entorno.

## 10. Reversión

Ante un fallo crítico:

1. no borre el volumen;
2. detenga nuevos accesos;
3. vuelva al commit estable anterior;
4. configure `SINGLE_TENANT_MODE=true` si necesita cerrar la creación de fundaciones;
5. redeploy;
6. revise logs y determine si hubo exposición;
7. restaure desde el respaldo si fue necesario.
