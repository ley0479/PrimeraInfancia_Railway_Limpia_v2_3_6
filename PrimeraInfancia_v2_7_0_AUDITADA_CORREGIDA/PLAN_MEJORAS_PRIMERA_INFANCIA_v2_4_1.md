# Plan de mejoras — PrimeraInfancia posterior a 2.4.1

## Fase inmediata: aceptación de 2.4.1

- Ejecutar la guía Windows de túnel en dos redes diferentes.
- Probar dos fundaciones y todos los roles con datos ficticios.
- Verificar eliminación lógica, restauración y auditoría.
- Configurar recuperación por correo en el entorno de pruebas de Railway.
- Respaldar y validar persistencia de `/data` después de redeploy.

## Fase de producción multi-fundación

- Completar pruebas de aislamiento en todas las tablas y archivos.
- Añadir pruebas end-to-end de navegador para cada rol.
- Migrar progresivamente de SQLite a PostgreSQL antes de aumentar réplicas o concurrencia.
- Implementar almacenamiento de objetos S3 compatible por tenant.
- Añadir cola persistente para procesos largos y generación masiva.
- Formalizar respaldo, restauración, retención y recuperación ante desastre.

## Túnel y acceso externo

- Mantener Quick Tunnel solamente para demostraciones temporales.
- Para URL estable, utilizar Railway o un túnel nombrado con dominio controlado.
- Añadir diagnóstico gráfico de conectividad, versión de `cloudflared` y puertos.
- Firmar o verificar el binario descargado antes de ejecución automática en entornos institucionales.

## Seguridad y cuentas

- Implementar segundo factor para `SUPERADMIN` y gerentes.
- Añadir historial visible de sesiones, cierre remoto y dispositivos.
- Notificar por correo cambios de contraseña, suspensiones y restablecimientos administrativos.
- Aplicar políticas de caducidad y reutilización de contraseña según la organización.
- Separar permisos administrativos finos: editar, suspender, eliminar y restablecer.

## Recuperación de contraseña

- Añadir proveedor de correo transaccional en Railway y plantillas institucionales.
- Registrar métricas sin información personal sobre entregas fallidas.
- Incorporar reenvío controlado, CAPTCHA adaptativo y detección de abuso.
- Permitir recuperación asistida con aprobación de dos administradores para cuentas críticas.

## Experiencia de usuario y accesibilidad

- Centro de ayuda por módulo y manuales por rol.
- Navegación por teclado, etiquetas ARIA, contraste y lectores de pantalla.
- Mensajes administrativos más claros y confirmaciones accesibles en lugar de `confirm()` nativo.
- Asistente de ayuda con lectura de pasos, dejando la voz como opción del usuario.

## Gobierno y cumplimiento

- Definir responsable de tratamiento de datos y matriz de acceso.
- Revisar base legal, consentimiento, retención y derechos de titulares.
- Ejecutar evaluación de impacto de privacidad antes de datos reales.
- Hacer pruebas de penetración y revisión independiente de aislamiento multi-tenant.
- Mantener inventario de versiones, hashes, dependencias y cambios aprobados.
