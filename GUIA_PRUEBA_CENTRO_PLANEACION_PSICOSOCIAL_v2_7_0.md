# Guía de prueba — PrimeraInfancia 2.7.0

## 1. Preparación

1. Conserve intacta la versión 2.6.1.
2. Extraiga 2.7.0 en una ruta corta, por ejemplo `C:\PI_V270`.
3. Copie únicamente la carpeta `data` cuando necesite conservar información ficticia.
4. No copie `.runtime_windows`, `backend\.venv`, `logs_tunel`, `tools\cloudflared` ni enlaces temporales anteriores.
5. Use datos completamente ficticios.

## 2. Inicio local

Ejecute:

```text
DETENER_PLATAFORMA_LOCAL.bat
INICIAR_PLATAFORMA_LOCAL.bat
```

Compruebe:

```text
http://127.0.0.1:5000/api/health
```

La respuesta debe indicar la versión 2.7.0 y el backend de base de datos esperado.

## 3. Prueba del Centro de Planeación

1. Abra **Gestión Integral UCA → Planeación Operativa**.
2. Pulse **Sincronizar fuentes** dos veces.
3. Compruebe que la segunda sincronización actualice y no duplique actividades.
4. Filtre por UCA, componente, estado y periodo.
5. Ingrese como un rol profesional y confirme que solo vea su agenda.
6. Ingrese como COORDINADOR y confirme la vista global.
7. Cree una dependencia entre dos actividades.
8. Verifique que la segunda quede bloqueada.
9. Finalice y apruebe la primera.
10. Verifique que la dependencia se libere.
11. Genere agenda, acta, listado e informe.
12. Confirme que todos queden en estado BORRADOR.
13. Genere el paquete mensual y compruebe el ZIP.

## 4. Prueba del Componente Psicosocial

1. Sincronice primero **Familias y Redes**.
2. Abra **Familia y Redes → Componente Psicosocial**.
3. Sincronice expedientes dos veces y confirme que no se dupliquen.
4. Ingrese como PSICOSOCIAL y compruebe que solo vea sus UCA y expedientes asignados.
5. Cree una caracterización inicial.
6. Cree una segunda caracterización y confirme que la primera se conserve como histórica.
7. Valide la versión actual con COORDINADOR.
8. Cree un plan de acompañamiento.
9. Cree una acción con evidencia obligatoria.
10. Intente validarla sin evidencia: debe ser rechazada.
11. Agregue la referencia de evidencia y valide.
12. Cierre el plan con coordinación.
13. Registre un seguimiento.
14. Genere el informe PDF y confirme que sea borrador restringido.

## 5. Prueba multi-fundación

1. Cree dos fundaciones ficticias.
2. Cree al menos una UCA en cada una.
3. Use documentos ficticios que puedan repetirse entre fundaciones.
4. Confirme que ninguna actividad, expediente, documento o informe cruce entre tenants.
5. Confirme que una cuenta PSICOSOCIAL de una fundación no consulte la otra.

## 6. Prueba en PostgreSQL

1. Ejecute la migración y verificación siguiendo la guía 2.6.1.
2. Inicie la aplicación con `DATABASE_URL` PostgreSQL.
3. Repita la sincronización, dependencias, caracterizaciones, acciones y documentos.
4. Reinicie el servicio y confirme persistencia.

## 7. Gate técnico

Ejecute:

```text
EJECUTAR_GATE_INTEGRIDAD.bat
```

El resultado esperado es `PASS`, con 19 pruebas críticas y sin SQL incompatible con PostgreSQL.

## 8. Túnel de prueba

Solo después de aprobar local y PostgreSQL:

```text
INICIAR_PLATAFORMA_TUNEL_ONLINE.bat
```

Mantenga abiertas las ventanas del backend y Cloudflare. Pruebe desde otro equipo o datos móviles. El túnel utiliza los mismos usuarios de la plataforma; no tiene contraseña propia.

## 9. Criterios de aceptación

- No existen duplicados tras repetir sincronizaciones.
- Todos los datos respetan `fundacion_id` y alcance por UCA.
- Los documentos se generan en BORRADOR.
- La evidencia obligatoria bloquea validaciones incompletas.
- Los roles profesionales no elevan su vista por parámetros.
- Los cierres dependen de revisión humana.
- El gate de integridad permanece aprobado.
