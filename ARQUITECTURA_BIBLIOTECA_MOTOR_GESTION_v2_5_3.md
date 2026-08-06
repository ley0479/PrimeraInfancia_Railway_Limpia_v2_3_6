# Arquitectura — Biblioteca Oficial ICBF y Motor de Gestión 2.5.3

## Vista general

```text
Módulos misionales existentes
(Base Maestra, GIU, Pedagogía, Salud, Calendario, entregables)
                         │
                         │ referencias, no copias
                         ▼
             MotorGestionRepository
                         │
          ┌──────────────┼───────────────┐
          ▼              ▼               ▼
       Tareas       Recordatorios     Productos/cierres
          │                              │
          └──────── revisión humana ─────┘

Fuentes oficiales/autorizadas
             │
             ▼
     Candidato documental
             │ revisión
             ▼
      Versión aprobada
             │ archivo/fuente verificada + activación explícita
             ▼
       Versión vigente
             │
             ▼
Relaciones y notificaciones a módulos
```

## Capas

### Dominio

- `motor_gestion_proyecto/services.py`: normalización, estados, prioridad y utilidades puras.
- `gestion_integral_uca/library_updates.py`: validación segura de fuentes remotas.

### Persistencia

- `motor_gestion_proyecto/repository.py`.
- `gestion_integral_uca/repository.py`.

Las escrituras son breves y usan SQLite con claves únicas para evitar duplicados.

### API

- `/api/motor-gestion-proyecto/*`.
- `/api/gestion-integral-uca/biblioteca/*`.

### Presentación

- `frontend/js/modules/motor-gestion-proyecto.js`.
- Ampliaciones de `gestion-integral-uca.js`.

## Identidad de tareas

```text
fundacion_id + fuente_tabla + fuente_clave
```

Esto permite actualizar una referencia existente cuando cambia el registro fuente, sin crear una tarea nueva.

## Estados de productos

```text
BORRADOR → PENDIENTE_APROBACION → APROBADO
                  ↘ DEVUELTO
```

## Estados documentales

```text
BORRADOR / APROBADA / VIGENTE / HISTORICA / RETIRADA
```

Un candidato se mantiene separado de la versión vigente para evitar actualizaciones automáticas no revisadas.

## Seguridad de conectores

- Interruptor global desactivado por defecto.
- Lista de dominios.
- HTTPS obligatorio.
- Sin redirecciones automáticas.
- Bloqueo de IP privadas, loopback, link-local, reservadas y multicast.
- Límite de tamaño lógico del catálogo.
- No se incluyen credenciales en URL.
- No se descarga ni activa automáticamente el archivo documental.

## Compatibilidad

No se eliminan tablas ni rutas anteriores. El esquema GIU avanza de 2 a 3 mediante `CREATE TABLE IF NOT EXISTS`. El Motor utiliza un esquema independiente con prefijo `mgp_`.
