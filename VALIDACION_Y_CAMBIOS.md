# Validación y cambios — PrimeraInfancia 2.3.6 Railway

**Fecha de cierre:** 1 de agosto de 2026  
**Alcance:** instalación nueva y controlada en Railway, usando exclusivamente datos ficticios.  
**Estado:** lista para el primer despliegue técnico; no contiene la base ni los archivos operativos del paquete auditado.

## 1. Garantía de conservación del original

La transformación se realizó sobre una copia aislada. El archivo fuente no fue modificado y conserva este SHA-256:

```text
59ac1ca55fc74359c01102588bd1a8442828c03b36bc3bd79ec6dd329bd3f78b
```

## 2. Limpieza de información

Se excluyeron del paquete de entrega:

- bases SQLite y archivos auxiliares WAL/SHM;
- usuarios, beneficiarios, alertas y movimientos operativos;
- cargas, salidas generadas, respaldos, logs y estados de trabajos;
- cuentas de cobro diligenciadas;
- archivos `.env`, credenciales y configuraciones locales;
- automatizaciones de túnel y copias históricas que no pertenecen al despliegue Railway;
- plantillas históricas con información ya diligenciada.

Las plantillas requeridas por la plataforma se reconstruyeron como semillas sanitizadas. Sus hashes están en `backend/seed_data/templates_originales/seed_manifest.json` y se verifican antes de copiarlas al volumen.

### Comparación de privacidad

La comprobación estricta reunió 3.238 candidatos sensibles únicos del origen y los buscó como coincidencias exactas dentro de texto, código y XML interno de documentos Office de la entrega.

```text
Coincidencias exactas de datos sensibles: 0
Coincidencias exactas de secretos del origen: 0
```

Esta prueba reduce el riesgo de arrastrar información del archivo fuente; no sustituye las obligaciones de privacidad sobre datos que se carguen después del despliegue.

## 3. Correcciones funcionales para hosting

- Flask sirve correctamente `/`, `/css`, `/js` y `/assets` desde `frontend/`.
- El frontend resuelve la API mediante el mismo origen público; los fallbacks a `localhost` quedan limitados al modo local explícito.
- Se añadió `backend/init_hosting.py` para crear carpetas, verificar semillas, inicializar esquema, comprobar SQLite y crear el administrador inicial.
- Toda información persistente se deriva de `DATA_DIR=/data` o del volumen informado por Railway.
- Gunicorn escucha en `0.0.0.0:$PORT`, usa un worker con hilos y no recicla el proceso por conteo de peticiones mientras haya trabajos en memoria.
- Se añadieron `Dockerfile`, `start_hosting.sh`, `railway.json`, `.gitignore`, `.dockerignore` y `.env.example`.
- El contenedor prepara el volumen como root y ejecuta Flask/Gunicorn con un usuario sin privilegios.
- El healthcheck público `/api/health` devuelve estado técnico sin conteos personales.

## 4. Correcciones de seguridad

- No existe una credencial administrativa predeterminada utilizable.
- El primer SUPERADMIN se crea únicamente desde variables privadas, sin promover cuentas existentes ni restablecer contraseñas en reinicios.
- El primer ingreso exige cambio de contraseña y revoca sesiones anteriores.
- La recuperación devuelve un mensaje genérico; el token es de un solo uso, expira y no se devuelve en el JSON.
- El enlace de recuperación coloca el token en el fragmento del navegador y el frontend lo retira de la barra al cargar.
- Los tokens de sesión dejaron de construirse en direcciones de descarga o consulta; se envían en `Authorization`.
- Los archivos se descargan mediante `fetch` autenticado y `Blob`.
- Inicio de sesión y recuperación tienen límites persistentes de intentos.
- Las rutas `/api/` aplican autorización por roles con denegación por defecto.
- Producción falla de forma cerrada si la capa de seguridad no se registra.
- CORS no admite comodín en producción.
- HTTPS es obligatorio para accesos externos; el healthcheck interno queda exento para evitar bucles.
- CSP en producción restringe conexiones a `self`; localhost solo se permite en desarrollo.
- Se añadieron HSTS bajo HTTPS, `no-store` para API, anti-framing, `nosniff`, política de referencias y permisos.
- El paquete queda bloqueado en modo de una sola fundación mientras no se certifique el aislamiento multiempresa histórico.
- La dependencia Lucide del navegador quedó fijada a una versión concreta, evitando `@latest`.

## 5. Resultado de validaciones automatizadas

El validador incluido se ejecuta con:

```bash
python tools/validate_release.py
```

Resultado final de esta entrega:

| Control | Resultado |
|---|---:|
| Archivos obligatorios | PASS |
| Ausencia de enlaces simbólicos | PASS |
| Ausencia de bytecode y cachés | PASS |
| Ausencia de DB, `.env`, logs y respaldos operativos | PASS |
| Directorios runtime vacíos | PASS |
| Sintaxis Python, 137 archivos | PASS |
| JSON válido, 6 archivos antes del manifiesto final | PASS |
| Sintaxis Bash, 2 scripts | PASS |
| Sintaxis JavaScript, 32 archivos | PASS |
| Hashes de 8 semillas | PASS |
| Integridad Office y ausencia de relaciones externas | PASS |
| Cobertura de autorización, 312 rutas y 54 familias | PASS |
| Configuración productiva y bootstrap | PASS |
| Invariantes de privacidad y seguridad | PASS |
| Configuración Railway/Docker | PASS |

**Total: 15 PASS, 0 FAIL, 0 SKIP.**

## 6. Pruebas que sí se ejecutaron

- compilación sintáctica de todos los módulos Python sin generar bytecode;
- validación de todos los JavaScript con Node;
- validación Bash y JSON;
- creación repetible de una base SQLite temporal;
- creación idempotente del SUPERADMIN y rechazo de promoción indebida;
- verificación de integridad SQLite;
- verificación de manifiestos y SHA-256 de semillas;
- apertura estructural de XLSX y DOCX, incluida revisión de relaciones externas;
- extracción AST de rutas y cobertura por familia de autorización;
- comparación exacta contra candidatos sensibles del origen;
- validación del contenido y estructura del archivo ZIP final.

## 7. Límite de la validación local

Este entorno no dispone de Flask, Werkzeug, Gunicorn ni Docker y tampoco puede resolver el índice público de paquetes. Por eso no se afirmó una prueba de arranque integral del contenedor. El primer build en Railway instalará las dependencias y será la prueba de integración real de Flask/Gunicorn, OCR, PDF y sistema operativo.

El frontend heredado aún usa Tailwind Play CDN. Es adecuado para el ensayo controlado solicitado, pero Tailwind recomienda compilar CSS estático para una operación final. No deben cargarse datos reales hasta completar ese cambio, la prueba funcional por roles, persistencia, respaldo, restauración y revisión de logs.

## 8. Criterio de entrega

La carpeta queda preparada para:

1. subirse a un repositorio privado o mediante Railway CLI;
2. montarse con un único volumen `/data`;
3. recibir secretos y administrador inicial exclusivamente como variables;
4. iniciar una base vacía con plantillas sanitizadas;
5. probar la plataforma con registros completamente ficticios.

No se autoriza todavía el uso de información real de niños, acudientes, salud, nutrición, personal o contratos.
