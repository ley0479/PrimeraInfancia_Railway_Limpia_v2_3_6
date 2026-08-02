/* Configuración unificada: producción usa siempre el mismo dominio que sirve el frontend. */
(function () {
    const host = (window.location.hostname || '').toLowerCase();
    const protocol = window.location.protocol || '';
    const isFile = protocol === 'file:' || host === '';
    const isLocalHost = host === '127.0.0.1' || host === 'localhost';
    const isSeparateLocalFrontend = isFile || (isLocalHost && window.location.port && window.location.port !== '5000');

    let backendUrl = window.location.origin && window.location.origin !== 'null'
        ? window.location.origin
        : 'http://127.0.0.1:5000';

    if (isSeparateLocalFrontend) {
        backendUrl = 'http://127.0.0.1:5000';
        try {
            const localOverride = localStorage.getItem('PRIMERA_INFANCIA_BACKEND_URL') || '';
            if (/^https?:\/\//i.test(localOverride.trim())) backendUrl = localOverride.trim();
        } catch (_) {}
    } else {
        // Evita que un valor antiguo de desarrollo redirija usuarios de producción a localhost.
        try {
            localStorage.removeItem('PRIMERA_INFANCIA_BACKEND_URL');
            sessionStorage.removeItem('PRIMERA_INFANCIA_BACKEND_URL');
        } catch (_) {}
    }

    const normalizedBackendUrl = backendUrl.replace(/\/$/, '');

    window.PRIMERA_INFANCIA_CONFIG = {
        backendUrl: normalizedBackendUrl,
        sameOriginApi: !isSeparateLocalFrontend,
        localMode: isFile || isLocalHost
    };

    // Punto único de resolución para módulos que se carguen antes o después de app.js.
    // En producción nunca cae accidentalmente en localhost: usa el mismo origen público.
    window.getConfiguredBackendUrl = function () {
        const configured = window.PRIMERA_INFANCIA_CONFIG?.backendUrl;
        if (configured) return String(configured).replace(/\/$/, '');
        const origin = window.location.origin;
        if (origin && origin !== 'null') return String(origin).replace(/\/$/, '');
        return 'http://127.0.0.1:5000';
    };
})();
