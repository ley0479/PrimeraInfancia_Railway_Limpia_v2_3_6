# Gerencia General e Inteligencia de Negocio

El tablero consulta en tiempo real las fuentes canónicas de la plataforma. No crea una bodega espejo ni modifica datos operativos.

La capa BI agrega indicadores de presupuesto y ejecución (`af_*`), talento y vencimientos (`th_*`), condiciones de ambientes (`aep_*`) y hallazgos (`csc_*`). Los semáforos incluyen una explicación visible y son descriptivos; nunca emiten diagnósticos ni decisiones automáticas.

Filtros disponibles: periodo, contrato, UCA, coordinador y componente. Los filtros se aplican únicamente donde la fuente contiene el atributo correspondiente.

API adicional: `GET /api/gerencia-general/inteligencia-negocio`.
