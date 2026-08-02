console.info('[ALPHA73] app.js activo: fix mínimo Bienestarina frontend');
function getBackendUrl() {
    const localMode = window.PRIMERA_INFANCIA_CONFIG?.localMode === true;
    const override = localMode
        ? (localStorage.getItem('PRIMERA_INFANCIA_BACKEND_URL') || sessionStorage.getItem('PRIMERA_INFANCIA_BACKEND_URL'))
        : '';
    if (override && /^https?:\/\//i.test(override.trim())) {
        return override.trim().replace(/\/$/, '');
    }

    const configUrl = window.PRIMERA_INFANCIA_CONFIG?.backendUrl || document.querySelector('meta[name="primera-infancia-backend-url"]')?.content;
    if (configUrl && /^https?:\/\//i.test(configUrl.trim())) {
        return configUrl.trim().replace(/\/$/, '');
    }

    const host = window.location.hostname || '127.0.0.1';
    const protocol = window.location.protocol && window.location.protocol.startsWith('http') ? window.location.protocol : 'http:';
    const port = window.location.port || '';
    const origin = window.location.origin && window.location.origin !== 'null' ? window.location.origin : '';

    // Cuando la plataforma se abre desde archivo local, se conserva el modo tradicional.
    if (window.location.protocol === 'file:' || !window.location.hostname) {
        return 'http://127.0.0.1:5000';
    }

    // Modo túnel online: el backend sirve también el frontend por el mismo puerto.
    // Así Cloudflare/ngrok exponen un solo enlace y las llamadas /api no intentan ir a :5000 remoto.
    const tunnelHostPatterns = [
        'trycloudflare.com',
        'ngrok-free.app',
        'ngrok.io',
        'loca.lt',
        'localhost.run'
    ];
    const isKnownTunnelHost = tunnelHostPatterns.some((pattern) => host.endsWith(pattern));
    const isSameOriginBackend = window.PRIMERA_INFANCIA_CONFIG?.sameOriginApi === true ||
        isKnownTunnelHost ||
        port === '5000' ||
        (protocol === 'https:' && !port);

    if (origin && isSameOriginBackend) {
        return origin;
    }

    return `${protocol}//${host}:5000`;
}

const backendUrl = getBackendUrl();
window.backendUrl = backendUrl;
window.getBackendUrl = getBackendUrl;
const AUTH_TOKEN_KEY = 'primeraInfanciaAuthToken';
const AUTH_USER_KEY = 'primeraInfanciaAuthUser';
let usuarioActual = null;

const MENU_POR_ROL = {
    SUPERADMIN: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'manual-operativo', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento'],
    GERENTE: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'manual-operativo', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento'],
    COORDINADOR: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'ajustes', 'calidad-datos', 'base-maestra', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'formatos', 'relacion-mes', 'paquete-mensual', 'reportes-gerenciales', 'cumplimiento'],
    DOCENTE: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'ajustes', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'formatos'],
    NUTRICIONISTA: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'ajustes', 'calidad-datos', 'base-maestra', 'salud-nutricion', 'nutricion'],
    PSICOSOCIAL: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'ajustes', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador'],
    AUXILIAR_ADMINISTRATIVO: ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'ajustes', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes', 'formatos', 'talento', 'cumplimiento']
};

const allowedBaseExtensions = ['.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.tsv', '.tab', '.dat', '.ods', '.html', '.htm', '.json', '.docx', '.pdf'];
const allowedTemplateExtensions = ['.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.doc', '.docx', '.pdf', '.png', '.jpg', '.jpeg', '.zip', '.rar'];
const allowedNutritionExtensions = ['.xlsx', '.xls', '.xlsm', '.csv', '.txt'];
const allowedTalentExtensions = ['.xlsx', '.xls', '.xlsm', '.csv', '.txt', '.zip', '.docx'];
const allowedDocumentExtensions = ['.pdf', '.doc', '.docx', '.xlsx', '.xls', '.xlsm', '.csv', '.ppt', '.pptx', '.txt', '.png', '.jpg', '.jpeg', '.zip', '.rar'];

let estadoDiagnostico = {
    unidades: {},
    stats: {
        total_usuarios: 0,
        alertas_cobertura: 0,
        unidades_sin_cobertura: [],
        proximos_retiros: 0,
        proximos_retiros_lista: [],
        falta_nutricion: 0,
        grupos_edad_totales: {}
    }
};

window.estadoDiagnostico = estadoDiagnostico;
let plantillasRegistradas = [];
let talentoRegistrado = [];
let estadoSeleccionCuentame = {
    archivoToken: '',
    archivoNombre: '',
    totalUsuarios: 0,
    unidades: [],
    seleccionadas: new Set()
};
window.estadoSeleccionCuentame = estadoSeleccionCuentame;

const GRUPOS_EDAD_DASHBOARD = [
    { clave: '0 A 6 MESES Y GESTANTES', etiqueta: '0 a 6 meses y gestantes', statId: 'stat-edad-0-6-gestantes', formato: '0_6_GESTANTES' },
    { clave: '6 A 11 MESES 29 DIAS', etiqueta: '6 a 11 meses y 29 días', statId: 'stat-edad-6-11', formato: '6_11_MESES' },
    { clave: '1 A 2 ANOS 11 MESES', etiqueta: '1 a 2 años 11 meses', statId: 'stat-edad-1-2', formato: '1_2_ANOS' },
    { clave: '3 A 5 ANOS 11 MESES', etiqueta: '3 a 5 años 11 meses', statId: 'stat-edad-3-5', formato: '3_5_ANOS' }
];

const UNIDADES_OPERATIVAS_INVALIDAS = new Set(['', 'ACTIVO', 'ACTIVA', 'INACTIVO', 'INACTIVA', 'PENDIENTE', 'RETIRADO', 'RETIRADA', 'SIN UNIDAD']);



const AUTH_TOKEN_COMPAT_KEYS = [
    AUTH_TOKEN_KEY,
    'token',
    'authToken',
    'accessToken',
    'jwt',
    'primeraInfanciaToken',
    'primeraInfanciaAuthToken'
];

const AUTH_USER_COMPAT_KEYS = [
    AUTH_USER_KEY,
    'user',
    'usuario',
    'authUser',
    'primeraInfanciaUser',
    'primeraInfanciaAuthUser'
];

function leerStorageSeguro(storage, key) {
    try {
        return storage.getItem(key);
    } catch (_) {
        return null;
    }
}

function escribirStorageSeguro(storage, key, value) {
    try {
        storage.setItem(key, value);
    } catch (_) {}
}

function borrarStorageSeguro(storage, key) {
    try {
        storage.removeItem(key);
    } catch (_) {}
}

function authToken() {
    for (const storage of [sessionStorage, localStorage]) {
        for (const key of AUTH_TOKEN_COMPAT_KEYS) {
            const token = leerStorageSeguro(storage, key);
            if (token && token !== 'null' && token !== 'undefined') return token;
        }
    }

    const user = authUser();
    return user?.token || user?.accessToken || '';
}

function authUser() {
    for (const storage of [sessionStorage, localStorage]) {
        for (const key of AUTH_USER_COMPAT_KEYS) {
            const raw = leerStorageSeguro(storage, key);
            if (!raw || raw === 'null' || raw === 'undefined') continue;
            try {
                return JSON.parse(raw);
            } catch (_) {}
        }
    }
    return null;
}

function guardarSesion(token, usuario, recordar = false) {
    limpiarSesionLocal(false);

    const storage = recordar ? localStorage : sessionStorage;
    const userData = { ...(usuario || {}), token };

    escribirStorageSeguro(storage, AUTH_TOKEN_KEY, token || '');
    escribirStorageSeguro(storage, AUTH_USER_KEY, JSON.stringify(userData));

    // Compatibilidad con funciones antiguas o módulos nuevos que busquen otros nombres.
    escribirStorageSeguro(storage, 'token', token || '');
    escribirStorageSeguro(storage, 'authToken', token || '');
    escribirStorageSeguro(storage, 'accessToken', token || '');
    escribirStorageSeguro(storage, 'primeraInfanciaToken', token || '');
    escribirStorageSeguro(storage, 'usuario', JSON.stringify(userData));
    escribirStorageSeguro(storage, 'authUser', JSON.stringify(userData));

    usuarioActual = userData;
}

function limpiarSesionLocal(recargarUsuario = true) {
    for (const storage of [sessionStorage, localStorage]) {
        AUTH_TOKEN_COMPAT_KEYS.forEach((key) => borrarStorageSeguro(storage, key));
        AUTH_USER_COMPAT_KEYS.forEach((key) => borrarStorageSeguro(storage, key));
    }
    if (recargarUsuario) usuarioActual = null;
}

function limpiarAuth() {
    limpiarSesionLocal();
}

function esUrlBackend(url) {
    return url.startsWith(backendUrl) || url.startsWith('/api/');
}

function prepararHeadersAutenticados(init = {}) {
    const token = authToken();
    const headers = new Headers(init.headers || {});
    if (token) {
        if (!headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
        if (!headers.has('X-Auth-Token')) headers.set('X-Auth-Token', token);
    }
    return headers;
}

function appendAuthToken(url) {
    // Compatibilidad segura: los tokens se envían exclusivamente en encabezados HTTP.
    return String(url || '');
}
window.appendAuthToken = appendAuthToken;

const fetchOriginalPrimeraInfancia = window.fetch.bind(window);
window.fetch = function(input, init = {}) {
    const url = typeof input === 'string' ? input : input?.url || '';
    if (esUrlBackend(url)) {
        init = { ...init, headers: prepararHeadersAutenticados(init) };
    }
    return fetchOriginalPrimeraInfancia(input, init);
};


function nombreDescargaDesdeRespuesta(response, fallback = 'descarga') {
    const disposition = response.headers.get('Content-Disposition') || '';
    const utf8 = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8) {
        try { return decodeURIComponent(utf8[1].replace(/["']/g, '')); } catch (_) {}
    }
    const normal = disposition.match(/filename="?([^";]+)"?/i);
    return normal?.[1] || fallback;
}

async function descargarArchivoAutenticado(url, filename = '') {
    const response = await fetch(url, { method: 'GET' });
    if (!response.ok) {
        let message = `No se pudo descargar el archivo (${response.status}).`;
        try {
            const data = await response.json();
            message = data.error || data.message || message;
        } catch (_) {}
        throw new Error(message);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = filename || nombreDescargaDesdeRespuesta(response, 'descarga');
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(objectUrl), 60000);
    return true;
}

async function abrirArchivoAutenticado(url) {
    const response = await fetch(url, { method: 'GET' });
    if (!response.ok) {
        let message = `No se pudo abrir el archivo (${response.status}).`;
        try { message = (await response.json()).error || message; } catch (_) {}
        throw new Error(message);
    }
    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);
    const opened = window.open(objectUrl, '_blank', 'noopener');
    if (!opened) {
        URL.revokeObjectURL(objectUrl);
        throw new Error('El navegador bloqueó la nueva pestaña. Habilita ventanas emergentes para este sitio.');
    }
    setTimeout(() => URL.revokeObjectURL(objectUrl), 120000);
    return true;
}

window.descargarArchivoAutenticado = descargarArchivoAutenticado;
window.abrirArchivoAutenticado = abrirArchivoAutenticado;

function mostrarLogin(mensaje = '') {
    document.getElementById('login-screen')?.classList.remove('hidden');
    document.getElementById('app-shell')?.classList.add('hidden');
    const msg = document.getElementById('login-message');
    if (msg && mensaje) msg.textContent = mensaje;
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function mostrarAplicacion() {
    document.getElementById('login-screen')?.classList.add('hidden');
    document.getElementById('app-shell')?.classList.remove('hidden');
}

async function iniciarSesionDesdeToken() {
    const token = authToken();
    if (!token) {
        mostrarLogin();
        return false;
    }
    try {
        const resp = await fetch(`${backendUrl}/api/auth/me`);
        if (!resp.ok) throw new Error('Sesión inválida');
        const data = await resp.json();
        usuarioActual = data.usuario || authUser();
        if (usuarioActual) {
            sessionStorage.setItem(AUTH_USER_KEY, JSON.stringify(usuarioActual));
        }
        if (usuarioActual?.debe_cambiar_password) {
            mostrarCambioPasswordObligatorio();
            return false;
        }
        mostrarAplicacion();
        aplicarPermisosFrontend();
        if (window.ThemeManager && typeof ThemeManager.initSessionTheme === 'function') {
            try { await ThemeManager.initSessionTheme(); } catch (_) {}
        }
        return true;
    } catch (error) {
        limpiarSesionLocal();
        mostrarLogin();
        return false;
    }
}

function configurarFormularioLogin() {
    const form = document.getElementById('login-form');
    if (!form || form.dataset.bound === '1') return;
    form.dataset.bound = '1';
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const username = document.getElementById('login-username')?.value.trim();
        const password = document.getElementById('login-password')?.value || '';
        const recordar = document.getElementById('login-recordar')?.checked || false;
        const msg = document.getElementById('login-message');
        if (msg) msg.textContent = 'Validando credenciales...';
        try {
            limpiarSesionLocal();
            const resp = await fetchOriginalPrimeraInfancia(`${backendUrl}/api/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo iniciar sesión');
            guardarSesion(data.token, data.usuario, recordar);
            if (msg) msg.textContent = '';
            if (data.usuario?.debe_cambiar_password) {
                mostrarCambioPasswordObligatorio();
            } else {
                location.reload();
            }
        } catch (error) {
            if (msg) msg.textContent = error.message || 'Error de autenticación';
        }
    });
}

async function recuperarPassword() {
    const username = document.getElementById('login-username')?.value.trim();
    const msg = document.getElementById('login-message');
    if (!username) {
        if (msg) msg.textContent = 'Escribe el usuario o correo para generar recuperación.';
        return;
    }
    try {
        const resp = await fetchOriginalPrimeraInfancia(`${backendUrl}/api/auth/recuperar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username })
        });
        const data = await resp.json();
        if (msg) msg.textContent = data.message || 'Si la cuenta existe, recibirás las instrucciones de recuperación.';
    } catch (error) {
        if (msg) msg.textContent = 'No se pudo generar la recuperación.';
    }
}


function mostrarCambioPasswordObligatorio() {
    mostrarLogin();
    document.getElementById('login-form')?.classList.add('hidden');
    document.getElementById('password-reset-panel')?.classList.add('hidden');
    document.getElementById('forced-password-panel')?.classList.remove('hidden');
}

let passwordResetToken = '';

function leerTokenRestablecimiento() {
    const queryToken = new URLSearchParams(window.location.search).get('reset_token') || '';
    const hash = String(window.location.hash || '').replace(/^#/, '');
    const hashQuery = hash.includes('?') ? hash.slice(hash.indexOf('?') + 1) : hash;
    const fragmentToken = new URLSearchParams(hashQuery).get('reset_token') || '';
    return fragmentToken || queryToken;
}

function prepararRestablecimientoDesdeUrl() {
    passwordResetToken = leerTokenRestablecimiento();
    if (!passwordResetToken) return false;
    // El fragmento no se envía al servidor. Además se retira de la barra de
    // direcciones para reducir exposición por capturas, historial o copiado.
    history.replaceState(null, '', `${window.location.pathname}#restablecer`);
    mostrarLogin();
    document.getElementById('login-form')?.classList.add('hidden');
    document.getElementById('forced-password-panel')?.classList.add('hidden');
    document.getElementById('password-reset-panel')?.classList.remove('hidden');
    return true;
}

async function restablecerPasswordDesdeEnlace() {
    const token = passwordResetToken;
    const password = document.getElementById('reset-password')?.value || '';
    const confirm = document.getElementById('reset-password-confirm')?.value || '';
    const msg = document.getElementById('reset-password-message');
    if (!token) { if (msg) msg.textContent = 'El enlace no contiene un token válido.'; return; }
    if (password !== confirm) { if (msg) msg.textContent = 'Las contraseñas no coinciden.'; return; }
    try {
        const response = await fetchOriginalPrimeraInfancia(`${backendUrl}/api/auth/restablecer`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token, password })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cambiar la contraseña.');
        passwordResetToken = '';
        history.replaceState(null, '', `${window.location.pathname}#login`);
        document.getElementById('password-reset-panel')?.classList.add('hidden');
        document.getElementById('login-form')?.classList.remove('hidden');
        if (msg) msg.textContent = '';
        const loginMsg = document.getElementById('login-message');
        if (loginMsg) loginMsg.textContent = data.message || 'Contraseña actualizada. Inicia sesión.';
    } catch (error) {
        if (msg) msg.textContent = error.message || 'No se pudo cambiar la contraseña.';
    }
}

async function cambiarPasswordObligatorio() {
    const current = document.getElementById('forced-current-password')?.value || '';
    const password = document.getElementById('forced-new-password')?.value || '';
    const confirm = document.getElementById('forced-new-password-confirm')?.value || '';
    const msg = document.getElementById('forced-password-message');
    if (password !== confirm) { if (msg) msg.textContent = 'Las contraseñas no coinciden.'; return; }
    try {
        const response = await fetch(`${backendUrl}/api/auth/cambiar-password`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password_actual: current, password_nueva: password })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'No se pudo cambiar la contraseña.');
        limpiarSesionLocal();
        document.getElementById('forced-password-panel')?.classList.add('hidden');
        document.getElementById('login-form')?.classList.remove('hidden');
        if (msg) msg.textContent = '';
        const loginMsg = document.getElementById('login-message');
        if (loginMsg) loginMsg.textContent = data.message || 'Contraseña cambiada. Inicia sesión nuevamente.';
    } catch (error) {
        if (msg) msg.textContent = error.message || 'No se pudo cambiar la contraseña.';
    }
}

window.restablecerPasswordDesdeEnlace = restablecerPasswordDesdeEnlace;
window.cambiarPasswordObligatorio = cambiarPasswordObligatorio;

async function cerrarSesion() {
    try { await fetch(`${backendUrl}/api/auth/logout`, { method: 'POST' }); } catch (_) {}
    limpiarSesionLocal();
    location.reload();
}

function aplicarPermisosFrontend() {
    const user = usuarioActual || authUser();
    if (!user) return;
    const rol = user.rol || 'DOCENTE';
    const permitidos = new Set([...(MENU_POR_ROL[rol] || []), ...((user.menus || []))]);
    document.querySelectorAll('[id^="nav-"]').forEach((btn) => {
        const seccion = btn.id.replace('nav-', '');
        btn.classList.toggle('hidden', !permitidos.has(seccion));
    });
    if (window.MenuInstitucionalLateral && typeof MenuInstitucionalLateral.aplicarPermisos === 'function') {
        MenuInstitucionalLateral.aplicarPermisos();
    }
    const info = document.getElementById('auth-user-info');
    if (info) {
        info.innerHTML = `<div class="text-right"><p class="text-sm font-semibold text-slate-200">${escaparHtml(user.nombre_completo || user.username || '')}</p><p class="text-[11px] text-slate-400">${escaparHtml(user.rol || '')} · ${escaparHtml(user.fundacion_nombre || 'Fundación')}</p></div>`;
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function initApp() {
    if (typeof lucide !== 'undefined') lucide.createIcons();
    configurarFormularioLogin();
    if (prepararRestablecimientoDesdeUrl()) return;
    const autorizado = await iniciarSesionDesdeToken();
    if (!autorizado) return;
    lucide.createIcons();
    if (window.MenuInstitucionalLateral && typeof MenuInstitucionalLateral.init === 'function') {
        MenuInstitucionalLateral.init();
    }
    const seccionInicial = (window.location.hash || '').replace('#', '') || 'dashboard';
    mostrarSeccion(['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'manual-operativo', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes'].includes(seccionInicial) ? seccionInicial : 'dashboard');

    const inputExcel = document.getElementById('input-excel');
    const dropZone = document.getElementById('drop-zone');

    inputExcel.addEventListener('change', (e) => {
        const nombre = e.target.files[0]?.name || 'Arrastra o selecciona la base de datos (.xlsx, .xls, .xlsm, .csv, .txt, .tsv, .json, .docx o .pdf)';
        document.getElementById('texto-archivo').innerText = nombre;
        resetSelectorUnidadesCuentame();
        limpiarMensajes();
    });

    dropZone.addEventListener('dragover', (event) => {
        event.preventDefault();
        dropZone.classList.add('border-indigo-500', 'bg-slate-900/70');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('border-indigo-500', 'bg-slate-900/70');
    });

    dropZone.addEventListener('drop', (event) => {
        event.preventDefault();
        dropZone.classList.remove('border-indigo-500', 'bg-slate-900/70');
        const file = event.dataTransfer.files[0];
        if (file) {
            document.getElementById('input-excel').files = event.dataTransfer.files;
            document.getElementById('texto-archivo').innerText = file.name;
            resetSelectorUnidadesCuentame();
            limpiarMensajes();
        }
    });

    fetchPlantillas();
    fetchTalento();
    inicializarPeriodoEntregable();
    document.getElementById('entregable-periodo')?.addEventListener('change', fetchEntregablesOperacion);
    fetchDocumentosInstitucionales();
    fetchEntregablesOperacion();
    evaluarOperacionICBF(false);
    if (typeof calendarioInteligenteInit === 'function') calendarioInteligenteInit(); // dashboard widget
    if (window.CruceBases) CruceBases.init();
    if (typeof cargarPanelPrincipalBaseMaestra === 'function') cargarPanelPrincipalBaseMaestra({ silent: true });
    if (typeof cargarConfiguracionInstitucional === 'function') cargarConfiguracionInstitucional(true);
}

function mostrarSeccion(seccion) {
    const user = usuarioActual || authUser();
    const rol = user?.rol || 'DOCENTE';
    const permitidos = new Set([...(MENU_POR_ROL[rol] || []), ...((user?.menus || []))]);
    if (permitidos.size && !permitidos.has(seccion)) {
        seccion = permitidos.has('dashboard') ? 'dashboard' : Array.from(permitidos)[0];
    }
    if (window.location.hash !== `#${seccion}`) {
        history.replaceState(null, '', `#${seccion}`);
    }
    ['dashboard', 'buscador-beneficiarios', 'calendario-inteligente', 'administracion', 'panel-comercial', 'gerencia-general', 'acceso-compartido', 'configuracion-institucional', 'manual-operativo', 'ajustes', 'administrador-disenos', 'backups', 'calidad-datos', 'base-maestra', 'motor-plantillas', 'plantillas-oficiales', 'paquete-mensual', 'reportes-gerenciales', 'facturacion', 'formatos', 'nutricion', 'salud-nutricion', 'talento', 'cumplimiento', 'planeacion-pedagogica', 'gestion-pedagogica', 'gestion-coordinador', 'cuentas-cobro', 'relacion-mes'].forEach(id => {
        const section = document.getElementById(id);
        if (section) section.classList.toggle('hidden', id !== seccion);
    });
    ['nav-dashboard', 'nav-buscador-beneficiarios', 'nav-calendario-inteligente', 'nav-administracion', 'nav-panel-comercial', 'nav-gerencia-general', 'nav-acceso-compartido', 'nav-configuracion-institucional', 'nav-manual-operativo', 'nav-ajustes', 'nav-administrador-disenos', 'nav-backups', 'nav-calidad-datos', 'nav-base-maestra', 'nav-motor-plantillas', 'nav-plantillas-oficiales', 'nav-paquete-mensual', 'nav-reportes-gerenciales', 'nav-facturacion', 'nav-formatos', 'nav-nutricion', 'nav-salud-nutricion', 'nav-talento', 'nav-cumplimiento', 'nav-planeacion-pedagogica', 'nav-gestion-pedagogica', 'nav-gestion-coordinador', 'nav-cuentas-cobro', 'nav-relacion-mes'].forEach(id => {
        const boton = document.getElementById(id);
        if (boton) {
            boton.classList.toggle('bg-indigo-600/10', id === `nav-${seccion}`);
            boton.classList.toggle('text-indigo-400', id === `nav-${seccion}`);
            boton.classList.toggle('text-slate-400', id !== `nav-${seccion}`);
        }
    });
    if (window.MenuInstitucionalLateral && typeof MenuInstitucionalLateral.marcarActivo === 'function') {
        MenuInstitucionalLateral.marcarActivo(seccion);
    }
    if (seccion === 'dashboard' && typeof cargarPanelPrincipalBaseMaestra === 'function') {
        cargarPanelPrincipalBaseMaestra({ silent: true });
    }
    if (seccion === 'buscador-beneficiarios' && window.BuscadorGlobalBeneficiarios && typeof BuscadorGlobalBeneficiarios.showPanel === 'function') {
        BuscadorGlobalBeneficiarios.showPanel();
    }
    if (seccion === 'calendario-inteligente' && typeof calendarioInteligenteInit === 'function') {
        calendarioInteligenteInit();
    }
    if (seccion === 'planeacion-pedagogica' && typeof ppInit === 'function') {
        ppInit();
    }
    if (seccion === 'gestion-pedagogica' && typeof gpMostrarVista === 'function') {
        gpMostrarVista('dashboard');
    }
    if (seccion === 'gestion-coordinador' && typeof gcInit === 'function') {
        gcInit();
    }
    if (seccion === 'salud-nutricion' && typeof snInit === 'function') {
        snInit();
    }
    if (seccion === 'administracion') {
        cargarAdministracion();
    }
    if (seccion === 'facturacion' && typeof facturacionInit === 'function') {
        facturacionInit();
    }
    if (seccion === 'panel-comercial' && typeof panelComercialInit === 'function') {
        panelComercialInit();
    }
    if (seccion === 'gerencia-general' && typeof gerenciaGeneralInit === 'function') {
        gerenciaGeneralInit();
    }
    if (seccion === 'acceso-compartido' && typeof accesoCompartidoInit === 'function') {
        accesoCompartidoInit();
    }
    if (seccion === 'ajustes' && typeof ajustesUIInit === 'function') {
        ajustesUIInit();
    }
    if (seccion === 'configuracion-institucional' && typeof configInstitucionalInit === 'function') {
        configInstitucionalInit();
    }
    if (seccion === 'manual-operativo' && typeof manualOperativoInit === 'function') {
        manualOperativoInit();
    }
    if (seccion === 'administrador-disenos' && window.ThemeManager && typeof ThemeManager.initAdmin === 'function') {
        ThemeManager.initAdmin();
        if (typeof ThemeManager.bindBuilderEvents === 'function') ThemeManager.bindBuilderEvents();
    }
    if (seccion === 'backups' && typeof backupsInit === 'function') {
        backupsInit();
    }
    if (seccion === 'calidad-datos' && typeof calidadDatosInit === 'function') {
        calidadDatosInit();
    }
    if (seccion === 'base-maestra' && typeof baseMaestraInit === 'function') {
        baseMaestraInit();
    }
    if (seccion === 'motor-plantillas' && typeof motorPlantillasInit === 'function') {
        motorPlantillasInit();
    }
    if (seccion === 'plantillas-oficiales' && typeof plantillasOficialesInit === 'function') {
        plantillasOficialesInit();
    }
    if (seccion === 'paquete-mensual' && typeof pmInit === 'function') {
        pmInit();
    }
    if (seccion === 'reportes-gerenciales' && typeof rgInit === 'function') {
        rgInit();
    }
    if (seccion === 'cuentas-cobro') {
        inicializarCuentasCobro();
    }
    if (seccion === 'relacion-mes') {
        inicializarRelacionMes();
    }
}

function limpiarMensajes() {
    const box = document.getElementById('message-box');
    box.className = 'mt-4 hidden rounded-xl px-4 py-3 text-sm';
    box.innerText = '';
}

function mostrarMensaje(id, texto, tipo = 'success') {
    const box = document.getElementById(id);
    if (!box) return;
    box.className = `mt-4 rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.innerText = texto;
    box.classList.remove('hidden');
}

function validarArchivo(file, allowedExtensions, tamanoMaxMB) {
    if (!file) {
        return 'No se seleccionó ningún archivo.';
    }
    const nombre = file.name.toLowerCase();
    const valido = allowedExtensions.some(ext => nombre.endsWith(ext));
    if (!valido) {
        return `Extensión no permitida. Utiliza ${allowedExtensions.join(', ')}.`;
    }
    const tamanoMb = file.size / 1024 / 1024;
    if (tamanoMb > tamanoMaxMB) {
        return `El archivo es demasiado grande. Tamaño máximo ${tamanoMaxMB} MB.`;
    }
    return null;
}

function actualizarBarraProgreso(valor) {
    const contenedor = document.getElementById('progress-container');
    const barra = document.getElementById('progress-bar');
    if (!contenedor || !barra) return;
    contenedor.classList.remove('hidden');
    barra.style.width = `${valor}%`;
}

function ocultarProgreso() {
    const contenedor = document.getElementById('progress-container');
    const barra = document.getElementById('progress-bar');
    if (!contenedor || !barra) return;
    barra.style.width = '0%';
    contenedor.classList.add('hidden');
}

function mostrarCargando(texto = 'Procesando base de datos y formatos oficiales...') {
    const overlay = document.getElementById('loading-overlay');
    const label = document.getElementById('loading-text');
    if (label) label.innerText = texto;
    if (overlay) overlay.classList.remove('hidden');
}

function ocultarCargando() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) overlay.classList.add('hidden');
}

function manejarRespuestaJson(respuesta) {
    if (!respuesta.ok) {
        if (respuesta.status === 401) {
            limpiarAuth();
            mostrarLogin('Sesión vencida. Ingrese nuevamente.');
        }
        return respuesta.json().then(json => {
            throw new Error(json.error || 'Error en el servidor');
        });
    }
    return respuesta.json();
}


function escaparHtml(valor) {
    return String(valor ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function normalizarFiltro(valor) {
    return String(valor || '')
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .trim()
        .toUpperCase()
        .replace(/\s+/g, ' ');
}

function normalizarGrupoEdad(valor, tipoBeneficiario = '') {
    const grupo = normalizarFiltro(valor);
    const tipo = normalizarFiltro(tipoBeneficiario);

    if (tipo.includes('GESTANTE') || grupo.includes('GESTANTE') || grupo.includes('0 A 5') || grupo.includes('0 A 6') || grupo.includes('MENOR DE SEIS')) {
        return '0 A 6 MESES Y GESTANTES';
    }
    if (grupo.includes('6 A 11')) {
        return '6 A 11 MESES 29 DIAS';
    }
    if (grupo.includes('1 A 2') || grupo.includes('1 ANO A 2') || grupo.includes('1 ANOS A 2')) {
        return '1 A 2 ANOS 11 MESES';
    }
    if (grupo.includes('3 A 5') || grupo.includes('3 ANOS A 5')) {
        return '3 A 5 ANOS 11 MESES';
    }
    if (grupo.includes('5 ANOS EN ADELANTE')) {
        return '5 ANOS EN ADELANTE';
    }
    return grupo;
}

function formatearEdadCompleta(edadMeses, tipoBeneficiario = '') {
    const tipo = normalizarFiltro(tipoBeneficiario);
    if (tipo.includes('GESTANTE')) return 'Gestante';

    const totalMeses = Math.max(0, parseInt(edadMeses || 0, 10) || 0);
    const anios = Math.floor(totalMeses / 12);
    const meses = totalMeses % 12;
    const partes = [];

    if (anios > 0) {
        partes.push(`${anios} año${anios === 1 ? '' : 's'}`);
    }
    if (meses > 0 || partes.length === 0) {
        partes.push(`${meses} mes${meses === 1 ? '' : 'es'}`);
    }

    return partes.join(' y ');
}

function fechaPlantillaLegible(fecha) {
    if (!fecha) return '';
    const parsed = new Date(fecha);
    return Number.isNaN(parsed.getTime()) ? String(fecha) : parsed.toLocaleString();
}

function unidadTieneUsuarios(data) {
    const total = Number(data?.total_usuarios || 0);
    const lista = Array.isArray(data?.datos_completos) ? data.datos_completos.length : 0;
    return total > 0 || lista > 0;
}

function obtenerUnidadesConDatos() {
    const unidades = estadoDiagnostico.unidades || {};
    return Object.keys(unidades)
        .filter((unidad) => !UNIDADES_OPERATIVAS_INVALIDAS.has(normalizarFiltro(unidad)))
        .filter((unidad) => unidadTieneUsuarios(unidades[unidad]))
        .sort((a, b) => a.localeCompare(b, 'es'));
}

function contarGrupo(grupos, claveNormalizada) {
    if (!grupos) return 0;
    return Object.keys(grupos).reduce((total, key) => {
        return total + (normalizarGrupoEdad(key) === claveNormalizada ? Number(grupos[key] || 0) : 0);
    }, 0);
}

function formatoRppPorGrupo(claveGrupo) {
    const grupoNormalizado = normalizarGrupoEdad(claveGrupo || '');
    const grupo = GRUPOS_EDAD_DASHBOARD.find((item) => item.clave === grupoNormalizado);
    return grupo?.formato || null;
}

function aplicarFiltroEdad(clave) {
    const filtro = document.getElementById('filtro-edad');
    if (filtro) {
        filtro.value = clave;
    }
    renderTablaUnidades();
}

function actualizarTarjetas(stats = {}) {
    document.getElementById('stat-total').innerText = stats.total_usuarios || 0;
    document.getElementById('stat-cobertura').innerText = stats.alertas_cobertura || 0;
    document.getElementById('stat-retiros').innerText = stats.proximos_retiros || 0;
    document.getElementById('stat-nutricion').innerText = stats.falta_nutricion || 0;

    const grupos = stats.grupos_edad_totales || {};
    GRUPOS_EDAD_DASHBOARD.forEach((grupo) => {
        const el = document.getElementById(grupo.statId);
        if (el) el.innerText = contarGrupo(grupos, grupo.clave);
    });

    const detalleCobertura = document.getElementById('detalle-cobertura');
    if (detalleCobertura) {
        const unidades = Array.isArray(stats.unidades_sin_cobertura) ? stats.unidades_sin_cobertura : [];
        detalleCobertura.innerHTML = unidades.length
            ? unidades.slice(0, 5).map((u) => `<span class="block truncate">${escaparHtml(u.unidad)}: ${escaparHtml(u.total)} / ${escaparHtml(u.meta || 20)}</span>`).join('')
            : '';
    }

    const detalleRetiros = document.getElementById('detalle-retiros');
    if (detalleRetiros) {
        const retiros = Array.isArray(stats.proximos_retiros_lista) ? stats.proximos_retiros_lista : [];
        detalleRetiros.innerHTML = retiros.length
            ? retiros.slice(0, 5).map((u) => `<span class="block truncate">${escaparHtml(u.nombre)} · ${escaparHtml(u.unidad)} · ${escaparHtml(u.edad_completa || formatearEdadCompleta(u.edad_meses))}</span>`).join('')
            : '';
    }
}


function fetchUnidadesRegistradas() {
    fetch(`${backendUrl}/api/unidades`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const unidades = data.unidades || [];
            unidades.forEach((item) => {
                const nombre = item.nombre;
                if (!nombre || UNIDADES_OPERATIVAS_INVALIDAS.has(normalizarFiltro(nombre))) return;
                if (!unidadTieneUsuarios(item)) return;
                if (!estadoDiagnostico.unidades[nombre]) {
                    estadoDiagnostico.unidades[nombre] = {
                        total_usuarios: item.total_usuarios || 0,
                        alerta_cobertura: (item.total_usuarios || 0) > 0 && (item.total_usuarios || 0) < 20,
                        usuarios_criticos: [],
                        nutricion_pendiente: 0,
                        grupos_edad: {},
                        datos_completos: []
                    };
                }
            });
            actualizarFiltrosUnidades();
            renderTablaUnidades();
        })
        .catch((error) => console.error('No se pudieron cargar unidades registradas', error));
}

function actualizarFiltrosUnidades() {
    const selectUnidad = document.getElementById('filtro-unidad');
    const selectAgregar = document.getElementById('nueva-unidad-nombre');
    const unidades = obtenerUnidadesConDatos();

    if (selectUnidad) {
        const seleccionado = selectUnidad.value;
        selectUnidad.innerHTML = '<option value="">Todas las unidades</option>' + unidades.map((unidad) => `
            <option value="${escaparHtml(unidad)}">${escaparHtml(unidad)}</option>
        `).join('');

        if (unidades.includes(seleccionado)) {
            selectUnidad.value = seleccionado;
        }
    }

    if (selectAgregar) {
        const seleccionadoAgregar = selectAgregar.value;
        selectAgregar.innerHTML = '<option value="">Selecciona una unidad detectada</option>' + unidades.map((unidad) => `
            <option value="${escaparHtml(unidad)}">${escaparHtml(unidad)}</option>
        `).join('');
        selectAgregar.disabled = unidades.length === 0;
        if (unidades.includes(seleccionadoAgregar)) {
            selectAgregar.value = seleccionadoAgregar;
        }
    }
}

function obtenerUsuariosFiltrados() {
    const filtroUnidad = normalizarFiltro(document.getElementById('filtro-unidad')?.value || '');
    const filtroEdad = normalizarGrupoEdad(document.getElementById('filtro-edad')?.value || '');
    const unidades = estadoDiagnostico.unidades || {};

    const resultado = [];
    obtenerUnidadesConDatos().forEach((unidad) => {
        if (filtroUnidad && normalizarFiltro(unidad) !== filtroUnidad) return;
        const data = unidades[unidad] || {};
        const usuarios = Array.isArray(data.datos_completos) ? data.datos_completos : [];
        usuarios.forEach((usuario) => {
            const grupo = normalizarGrupoEdad(usuario.GrupoEdad || usuario.grupo_edad || '', usuario.TipoBeneficiario || usuario.tipo_beneficiario || '');
            if (filtroEdad && grupo !== filtroEdad) return;
            resultado.push({ unidad, usuario: { ...usuario, GrupoEdadNormalizado: grupo } });
        });
    });
    return resultado;
}

function renderUsuariosFiltrados(usuarios) {
    const contenedor = document.getElementById('usuarios-filtrados');
    const resumen = document.getElementById('resumen-filtros');
    const unidadSeleccionada = document.getElementById('filtro-unidad')?.value || '';
    const edadSeleccionada = document.getElementById('filtro-edad')?.value || '';
    const filtroUnidadTexto = unidadSeleccionada || 'Todas las unidades';
    const filtroEdadTexto = edadSeleccionada || 'Todos los grupos';

    if (resumen) {
        resumen.innerText = `Filtro activo: ${filtroUnidadTexto} · ${filtroEdadTexto} · ${usuarios.length} usuario(s) encontrados.`;
    }

    if (!contenedor) return;

    const formatoSeleccionado = formatoRppPorGrupo(edadSeleccionada);
    const botonDescargaFiltro = unidadSeleccionada && formatoSeleccionado
        ? `<button onclick="descargar('${escaparHtml(unidadSeleccionada)}', '${escaparHtml(formatoSeleccionado)}')" class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition">
                Descargar RPP de este filtro
           </button>`
        : '';

    if (usuarios.length === 0) {
        contenedor.classList.remove('hidden');
        contenedor.innerHTML = `
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <p class="text-sm text-slate-500">No hay usuarios para el filtro seleccionado.</p>
                ${botonDescargaFiltro}
            </div>
        `;
        return;
    }

    contenedor.classList.remove('hidden');
    const filas = usuarios.slice(0, 80).map(({ unidad, usuario }) => `
        <tr class="border-b border-slate-800/70">
            <td class="px-3 py-2 text-slate-300">${escaparHtml(unidad)}</td>
            <td class="px-3 py-2 text-slate-200 font-medium">${escaparHtml(usuario.Nombre || '')}</td>
            <td class="px-3 py-2">${escaparHtml(usuario.Documento || usuario.NUI || '')}</td>
            <td class="px-3 py-2">${escaparHtml(usuario.EdadCompleta || usuario.edad_completa || formatearEdadCompleta(usuario.EdadMeses, usuario.TipoBeneficiario || usuario.tipo_beneficiario || ''))}</td>
            <td class="px-3 py-2">${escaparHtml(usuario.GrupoEdad || usuario.GrupoEdadNormalizado || '')}</td>
            <td class="px-3 py-2">${escaparHtml(usuario.Acudiente || '')}</td>
            <td class="px-3 py-2">${escaparHtml(usuario.Parentesco || '')}</td>
        </tr>
    `).join('');

    const aviso = usuarios.length > 80
        ? `<p class="mt-3 text-xs text-amber-400">Mostrando los primeros 80 de ${usuarios.length}. Usa los filtros para reducir la lista.</p>`
        : '';

    contenedor.innerHTML = `
        <div class="mb-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <h3 class="font-medium text-slate-200">Usuarios filtrados</h3>
            <div class="flex items-center gap-2">
                <span class="rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1 text-xs text-indigo-300">${usuarios.length} resultado(s)</span>
                ${botonDescargaFiltro}
            </div>
        </div>
        <div class="overflow-x-auto">
            <table class="w-full text-left text-xs text-slate-400">
                <thead class="bg-slate-950 text-slate-300 uppercase">
                    <tr>
                        <th class="px-3 py-2">Unidad</th>
                        <th class="px-3 py-2">Nombre</th>
                        <th class="px-3 py-2">Documento/NUI</th>
                        <th class="px-3 py-2">Edad y meses</th>
                        <th class="px-3 py-2">Grupo</th>
                        <th class="px-3 py-2">Acudiente</th>
                        <th class="px-3 py-2">Parentesco</th>
                    </tr>
                </thead>
                <tbody>${filas}</tbody>
            </table>
        </div>
        ${aviso}
    `;
}


function renderTablaUnidades() {
    const tablaCuerpo = document.getElementById('tabla-cuerpo');
    if (!tablaCuerpo) return;

    const unidades = estadoDiagnostico.unidades || {};
    const filtroUnidad = normalizarFiltro(document.getElementById('filtro-unidad')?.value || '');
    const filtroEdad = normalizarGrupoEdad(document.getElementById('filtro-edad')?.value || '');
    const usuariosFiltrados = obtenerUsuariosFiltrados();

    tablaCuerpo.innerHTML = '';
    const nombresUnidades = obtenerUnidadesConDatos();
    const unidadesVisibles = nombresUnidades.filter((unidad) => !filtroUnidad || normalizarFiltro(unidad) === filtroUnidad);

    if (unidadesVisibles.length === 0) {
        tablaCuerpo.innerHTML = `<tr><td colspan="6" class="px-6 py-8 text-center text-slate-500">No hay unidades con usuarios para mostrar en este filtro.</td></tr>`;
        renderUsuariosFiltrados([]);
        return;
    }

    unidadesVisibles.forEach(unidad => {
        const data = unidades[unidad] || {};
        const usuariosUnidad = Array.isArray(data.datos_completos) ? data.datos_completos : [];
        const usuariosUnidadFiltrados = usuariosUnidad.filter((usuario) => {
            const grupo = normalizarGrupoEdad(usuario.GrupoEdad || '', usuario.TipoBeneficiario || '');
            return !filtroEdad || grupo === filtroEdad;
        });
        const totalReal = Number(data.total_usuarios || usuariosUnidad.length || 0);
        const totalVisible = filtroEdad ? usuariosUnidadFiltrados.length : totalReal;

        let criticosHTML = `<span class="text-xs text-emerald-400 flex items-center gap-1"><i data-lucide="check-circle" class="w-3.5 h-3.5"></i> Sin novedades de gravedad</span>`;
        if (Array.isArray(data.usuarios_criticos) && data.usuarios_criticos.length > 0) {
            criticosHTML = data.usuarios_criticos.slice(0, 3).map(c => `
                <div class="text-xs text-rose-400 bg-rose-500/10 p-1.5 rounded border border-rose-500/20 mb-1">
                    <strong>${escaparHtml(c.nombre)}:</strong> ${escaparHtml(c.motivo)}
                </div>
            `).join('');
        }

        const alertaCobertura = totalReal > 0 && totalReal < 20 && !filtroEdad;
        const claseBadge = alertaCobertura
            ? 'bg-rose-500/10 text-rose-500 border-rose-500/30'
            : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
        const textoCobertura = filtroEdad
            ? `${totalVisible} usuario(s) en grupo`
            : `${totalReal} / 20 ${totalReal >= 20 ? '(Completo)' : '(Falta Cupo)'}`;

        const grupos = data.grupos_edad || {};
        const detalleGrupos = GRUPOS_EDAD_DASHBOARD
            .map((g) => ({ etiqueta: g.etiqueta, total: contarGrupo(grupos, g.clave) }))
            .filter((g) => g.total > 0)
            .map((g) => `${g.etiqueta}: ${g.total}`)
            .join(' · ');

        const docenteAsignado = data.docente_asignado || data.docente || (window.CruceBases ? CruceBases.docentePorUnidad(unidad) : '') || 'Sin agente educativo asignado';

        const rppLinks = GRUPOS_EDAD_DASHBOARD.map((g) => {
            const totalGrupo = contarGrupo(grupos, g.clave);
            return `
                <button onclick="descargarRppCategoria('${escaparHtml(unidad)}', '${escaparHtml(g.formato)}')" class="text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1">
                    <i data-lucide="download" class="w-3.5 h-3.5"></i> ${escaparHtml(g.etiqueta)} (${totalGrupo})
                </button>
            `;
        }).join('');

        tablaCuerpo.insertAdjacentHTML('beforeend', `
            <tr class="hover:bg-slate-900/50 transition">
                <td class="px-6 py-4 font-semibold text-slate-200">
                    ${escaparHtml(unidad)}
                    ${detalleGrupos ? `<div class="mt-1 text-[11px] font-normal text-slate-500">${escaparHtml(detalleGrupos)}</div>` : ''}
                </td>
                <td class="px-6 py-4">
                    <span class="px-2.5 py-1 rounded-lg border text-xs font-medium ${claseBadge}">${escaparHtml(textoCobertura)}</span>
                </td>
                <td class="px-6 py-4 text-xs text-slate-300">
                    <div class="font-medium text-slate-200">${escaparHtml(docenteAsignado)}</div>
                </td>
                <td class="px-6 py-4 max-w-xs">${criticosHTML}</td>
                <td class="px-6 py-4 text-xs ${data.nutricion_pendiente > 0 ? 'text-cyan-400 font-medium' : 'text-slate-500'}">
                    ${data.nutricion_pendiente > 0 ? `${data.nutricion_pendiente} Niños sin Peso/Talla` : 'Al día'}
                </td>
                <td class="px-6 py-4 space-y-1">
                    <button onclick="descargar('${escaparHtml(unidad)}', 'ram')" class="text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1"><i data-lucide="download" class="w-3.5 h-3.5"></i> Asistencia / RAM</button>
                    <button onclick="descargar('${escaparHtml(unidad)}', 'bienestarina')" class="text-indigo-400 hover:text-indigo-300 text-xs flex items-center gap-1"><i data-lucide="download" class="w-3.5 h-3.5"></i> Bienestarina</button>
                    <button onclick="CruceBases.descargarUsuariosUnidad('${escaparHtml(unidad)}', 'excel')" class="text-emerald-400 hover:text-emerald-300 text-xs flex items-center gap-1"><i data-lucide="file-down" class="w-3.5 h-3.5"></i> Descargar usuarios Excel</button>
                    <button onclick="CruceBases.descargarUsuariosUnidad('${escaparHtml(unidad)}', 'pdf')" class="text-rose-400 hover:text-rose-300 text-xs flex items-center gap-1"><i data-lucide="file-text" class="w-3.5 h-3.5"></i> Descargar usuarios PDF</button>
                    <button onclick="CruceBases.imprimirUsuariosUnidad('${escaparHtml(unidad)}')" class="text-amber-400 hover:text-amber-300 text-xs flex items-center gap-1"><i data-lucide="printer" class="w-3.5 h-3.5"></i> Imprimir usuarios</button>
                    <div class="pt-1 text-[10px] uppercase tracking-wide text-slate-500">RPP por categoría</div>
                    ${rppLinks}
                </td>
            </tr>
        `);
    });

    renderUsuariosFiltrados(usuariosFiltrados);
    lucide.createIcons();
}

function agregarUnidadManual() {
    const nombreInput = document.getElementById('nueva-unidad-nombre');
    const detalleInput = document.getElementById('nueva-unidad-detalle');
    const nombre = nombreInput?.value.trim();
    const detalle = detalleInput?.value.trim();

    if (!nombre) {
        mostrarMensaje('message-box', 'Selecciona una unidad detectada en el archivo.', 'error');
        return;
    }

    fetch(`${backendUrl}/api/unidades`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, direccion: detalle, telefono: '' })
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            const unidad = data.unidad?.nombre || nombre;
            if (unidad && estadoDiagnostico.unidades[unidad]) {
                document.getElementById('filtro-unidad').value = unidad;
                renderTablaUnidades();
            }
            if (detalleInput) detalleInput.value = '';
            mostrarMensaje('message-box', data.message || 'Unidad guardada correctamente.', 'success');
        })
        .catch((error) => {
            mostrarMensaje('message-box', error.message || 'No se pudo agregar la unidad.', 'error');
        });
}



function procesarResultadoBase(resultado) {
    actualizarTarjetas(resultado.stats || {});

    if ((resultado.stats?.alertas_cobertura || 0) > 0 || (resultado.stats?.proximos_retiros || 0) > 0) {
        document.getElementById('ping-alerta')?.classList.remove('hidden');
    }

    estadoDiagnostico = resultado;
    window.estadoDiagnostico = estadoDiagnostico;
    if (window.CruceBases) CruceBases.cargarUltimoCruce();
    actualizarFiltrosUnidades();
    renderTablaUnidades();
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const errores = Array.isArray(resultado.errores_formatos) && resultado.errores_formatos.length
        ? ` Algunos formatos tuvieron observaciones: ${resultado.errores_formatos.length}.`
        : '';
    const procesamiento = resultado.procesamiento || {};
    const unidadesProcesadas = procesamiento.total_unidades_formatos || resultado.stats?.unidades_procesadas || Object.keys(resultado.unidades || {}).length;
    const registrosFormatos = procesamiento.total_usuarios_formatos || resultado.stats?.total_usuarios_formatos || resultado.stats?.total_usuarios || 0;
    const registrosBase = procesamiento.total_usuarios_base_maestra || resultado.stats?.total_usuarios_base_maestra || registrosFormatos;
    const mensajeBase = procesamiento.modo === 'unidades_seleccionadas'
        ? `Base Maestra actualizada con ${registrosBase} registro(s). Formatos generados solo para ${unidadesProcesadas} unidad(es) seleccionada(s), ${registrosFormatos} registro(s).`
        : `Base procesada correctamente. Formatos generados para todas las unidades detectadas (${unidadesProcesadas}).`;
    mostrarMensaje('message-box', `${mensajeBase}${errores}`, 'success');
}


function aplicarPanelPrincipalBaseMaestra(resultado, opciones = {}) {
    if (!resultado || !resultado.fuente_activa) return false;
    actualizarTarjetas(resultado.stats || {});

    if ((resultado.stats?.alertas_cobertura || 0) > 0 || (resultado.stats?.proximos_retiros || 0) > 0) {
        document.getElementById('ping-alerta')?.classList.remove('hidden');
    }

    estadoDiagnostico = resultado;
    window.estadoDiagnostico = estadoDiagnostico;
    actualizarFiltrosUnidades();
    renderTablaUnidades();
    if (window.CruceBases && typeof CruceBases.cargarOpcionesInforme === 'function') {
        try { CruceBases.cargarOpcionesInforme(); } catch (_) {}
    }
    if (typeof lucide !== 'undefined') lucide.createIcons();

    const version = resultado.version_activa || {};
    const total = resultado.stats?.total_usuarios || 0;
    const status = document.getElementById('bmp-status-text');
    if (status) {
        status.textContent = `Panel alimentado desde Base Maestra v${version.version_numero || version.id || 'activa'} · ${total} usuario(s) activos.`;
    }
    if (!opciones.silent) {
        const mensaje = `Panel principal actualizado desde Base Maestra publicada: ${total} usuario(s), ${resultado.stats?.total_unidades || 0} unidad(es).`;
        if (typeof mostrarMensaje === 'function') mostrarMensaje('bmp-message', mensaje, 'success');
    }
    return true;
}
window.aplicarPanelPrincipalBaseMaestra = aplicarPanelPrincipalBaseMaestra;

function consultarJobOperativo(jobId) {
    const token = authToken();
    return fetch(`${backendUrl}/api/jobs/${encodeURIComponent(jobId)}`, {
        headers: {
            'Authorization': token ? `Bearer ${token}` : '',
            'X-Auth-Token': token || '',
            'X-Requested-With': 'XMLHttpRequest'
        }
    }).then(manejarRespuestaJson);
}

function esperarJobOperativo(jobId, onComplete, messageTarget = 'message-box') {
    let intentos = 0;
    const maxIntentos = 180; // hasta 9 minutos, útil para bases grandes por túnel

    const tick = () => {
        intentos += 1;
        consultarJobOperativo(jobId)
            .then((data) => {
                const job = data.job || data;
                const progreso = Number(job.progreso || 0);
                if (Number.isFinite(progreso)) actualizarBarraProgreso(Math.max(1, Math.min(100, progreso)));
                if (job.etapa) mostrarCargando(`${job.etapa} (${Math.round(progreso)}%)`);

                if (job.estado === 'completado') {
                    ocultarProgreso();
                    ocultarCargando();
                    try {
                        onComplete(job.resultado || {});
                    } catch (error) {
                        console.error(error);
                        mostrarMensaje(messageTarget, 'El proceso terminó, pero hubo un error actualizando el tablero.', 'error');
                    }
                    return;
                }

                if (job.estado === 'error') {
                    ocultarProgreso();
                    ocultarCargando();
                    const detalle = job.error || 'El proceso en segundo plano falló.';
                    mostrarMensaje(messageTarget, `Error procesando en segundo plano: ${detalle}`, 'error');
                    console.error('Job operativo fallido', job);
                    return;
                }

                if (intentos >= maxIntentos) {
                    ocultarProgreso();
                    ocultarCargando();
                    mostrarMensaje(messageTarget, 'El proceso sigue tardando demasiado. Revisa los logs del backend o intenta con una base más liviana.', 'error');
                    return;
                }

                setTimeout(tick, 3000);
            })
            .catch((error) => {
                if (intentos >= maxIntentos) {
                    ocultarProgreso();
                    ocultarCargando();
                    mostrarMensaje(messageTarget, error.message || 'No se pudo consultar el avance del proceso.', 'error');
                    return;
                }
                setTimeout(tick, 3000);
            });
    };

    mostrarMensaje(messageTarget, 'La base fue recibida. El sistema sigue procesando en segundo plano para evitar error 524 del túnel.', 'success');
    actualizarBarraProgreso(1);
    tick();
}

function resetSelectorUnidadesCuentame() {
    estadoSeleccionCuentame = {
        archivoToken: '',
        archivoNombre: '',
        totalUsuarios: 0,
        unidades: [],
        seleccionadas: new Set()
    };
    window.estadoSeleccionCuentame = estadoSeleccionCuentame;

    const contenedor = document.getElementById('selector-unidades-container');
    const lista = document.getElementById('selector-unidades-lista');
    const resumen = document.getElementById('selector-unidades-resumen');
    const contador = document.getElementById('selector-unidades-contador');
    const buscar = document.getElementById('selector-unidades-buscar');
    if (contenedor) contenedor.classList.add('hidden');
    if (lista) lista.innerHTML = '<div class="px-4 py-5 text-center text-sm text-slate-500">Sin unidades detectadas todavía.</div>';
    if (resumen) resumen.innerText = 'Carga una base para ver las unidades disponibles.';
    if (contador) contador.innerText = '0 seleccionadas';
    if (buscar) buscar.value = '';
}

function obtenerFormatosSeleccionadosAlpha68() {
    const checks = Array.from(document.querySelectorAll('[data-alpha68-formato]:checked'));
    const seleccion = checks.map((item) => String(item.value || item.dataset.alpha68Formato || '').trim()).filter(Boolean);
    if (seleccion.includes('paquete_completo')) {
        return ['paquete_completo'];
    }
    return Array.from(new Set(seleccion));
}
window.obtenerFormatosSeleccionadosAlpha68 = obtenerFormatosSeleccionadosAlpha68;

function actualizarResumenFormatosAlpha68() {
    const destino = document.getElementById('alpha68-formatos-resumen');
    if (!destino) return;
    const seleccion = obtenerFormatosSeleccionadosAlpha68();
    if (!seleccion.length) {
        destino.textContent = 'Sin selección: se conserva el comportamiento histórico y se generarán todos los formatos disponibles.';
        return;
    }
    const nombres = {
        rpp: 'RPP', bienestarina: 'Bienestarina', ram: 'RAM', ran: 'RAN', rran: 'RRAN',
        relacion_mensual: 'Relación mensual', listado_usuarios: 'Listado de usuarios',
        distribucion_alimentos: 'Distribución de alimentos', paquete_completo: 'Paquete completo'
    };
    destino.textContent = `Se procesará solo: ${seleccion.map((v) => nombres[v] || v).join(', ')}.`;
}
window.actualizarResumenFormatosAlpha68 = actualizarResumenFormatosAlpha68;

function seleccionarFormatosAlpha68(modo) {
    const checks = Array.from(document.querySelectorAll('[data-alpha68-formato]'));
    if (modo === 'todo') {
        checks.forEach((check) => { check.checked = check.value === 'paquete_completo'; });
    } else if (modo === 'limpiar') {
        checks.forEach((check) => { check.checked = false; });
    } else if (modo === 'basicos') {
        checks.forEach((check) => { check.checked = ['rpp','bienestarina','ram'].includes(check.value); });
    }
    actualizarResumenFormatosAlpha68();
}
window.seleccionarFormatosAlpha68 = seleccionarFormatosAlpha68;

document.addEventListener('change', (ev) => {
    if (ev.target && ev.target.matches('[data-alpha68-formato]')) {
        if (ev.target.value === 'paquete_completo' && ev.target.checked) {
            document.querySelectorAll('[data-alpha68-formato]').forEach((check) => {
                if (check !== ev.target) check.checked = false;
            });
        } else if (ev.target.checked) {
            const pack = document.querySelector('[data-alpha68-formato][value="paquete_completo"]');
            if (pack) pack.checked = false;
        }
        actualizarResumenFormatosAlpha68();
    }
});

function periodoFormatosSeleccionado() {
    const ahora = new Date();
    const mesInput = document.getElementById('periodo-formatos-mes');
    const anioInput = document.getElementById('periodo-formatos-anio');
    let mes = Number(mesInput?.value || (ahora.getMonth() + 1));
    let anio = Number(anioInput?.value || ahora.getFullYear());
    if (!Number.isInteger(mes) || mes < 1 || mes > 12) mes = ahora.getMonth() + 1;
    if (!Number.isInteger(anio) || anio < 2020 || anio > 2100) anio = ahora.getFullYear();
    return { mes, anio };
}
window.periodoFormatosSeleccionado = periodoFormatosSeleccionado;

function inicializarPeriodoFormatos() {
    const ahora = new Date();
    const mesInput = document.getElementById('periodo-formatos-mes');
    const anioInput = document.getElementById('periodo-formatos-anio');
    if (mesInput && !mesInput.value) mesInput.value = String(ahora.getMonth() + 1);
    if (mesInput) mesInput.value = mesInput.value || String(ahora.getMonth() + 1);
    if (anioInput && !anioInput.value) anioInput.value = String(ahora.getFullYear());
}
document.addEventListener('DOMContentLoaded', inicializarPeriodoFormatos);

function anexarOpcionesCuentame(formData) {
    const periodo = periodoFormatosSeleccionado();
    formData.append('mes', String(periodo.mes));
    formData.append('anio', String(periodo.anio));
    formData.append('año', String(periodo.anio));
    formData.append('max_usuarios_formato', document.getElementById('max-usuarios-formato')?.value || '20');
    formData.append('bienestarina_por_hoja', document.getElementById('bienestarina-por-hoja')?.value || '14');
    formData.append('fecha_entrega_bienestarina', document.getElementById('fecha-entrega-bienestarina')?.value || '');
    formData.append('lote_bienestarina', document.getElementById('lote-bienestarina')?.value || '');
    formData.append('cantidad_bienestarina', document.getElementById('cantidad-bienestarina')?.value || '');
    const formatosSeleccionados = obtenerFormatosSeleccionadosAlpha68();
    formData.append('formatos_seleccionados', formatosSeleccionados.join(','));
    return formData;
}

function actualizarContadorSelectorUnidades() {
    const contador = document.getElementById('selector-unidades-contador');
    if (!contador) return;
    const seleccionadas = estadoSeleccionCuentame.unidades.filter((u) => estadoSeleccionCuentame.seleccionadas.has(String(u.nombre || '')));
    const totalRegistros = seleccionadas.reduce((sum, u) => sum + Number(u.total || 0), 0);
    contador.innerText = `${seleccionadas.length} seleccionada(s) · ${totalRegistros} registro(s)`;
}

function unidadesSeleccionadasDesdeDOM() {
    const marcadas = Array.from(document.querySelectorAll('#selector-unidades-lista input[type="checkbox"]:checked'))
        .map((input) => input.value || input.dataset.unidad || '')
        .map((unidad) => String(unidad || '').trim())
        .filter(Boolean);
    return Array.from(new Set([...Array.from(estadoSeleccionCuentame.seleccionadas || []), ...marcadas]));
}

function toggleUnidadSeleccionada(input) {
    const unidad = String(input?.value || input?.dataset?.unidad || '').trim();
    if (!unidad) return;
    if (input.checked) {
        estadoSeleccionCuentame.seleccionadas.add(unidad);
    } else {
        estadoSeleccionCuentame.seleccionadas.delete(unidad);
    }
    window.estadoSeleccionCuentame = estadoSeleccionCuentame;
    actualizarContadorSelectorUnidades();
}

function renderSelectorUnidades() {
    const contenedor = document.getElementById('selector-unidades-container');
    const lista = document.getElementById('selector-unidades-lista');
    const resumen = document.getElementById('selector-unidades-resumen');
    if (!contenedor || !lista) return;

    const unidades = Array.isArray(estadoSeleccionCuentame.unidades) ? estadoSeleccionCuentame.unidades : [];
    contenedor.classList.toggle('hidden', unidades.length === 0);

    const filtro = (document.getElementById('selector-unidades-buscar')?.value || '').trim().toLowerCase();
    const visibles = unidades.filter((u) => String(u.nombre || '').toLowerCase().includes(filtro));

    if (resumen) {
        resumen.innerText = `${estadoSeleccionCuentame.totalUsuarios || 0} registro(s) en ${unidades.length} unidad(es). Archivo: ${estadoSeleccionCuentame.archivoNombre || 'base cargada'}.`;
    }

    if (!visibles.length) {
        lista.innerHTML = '<div class="px-4 py-5 text-center text-sm text-slate-500">No hay unidades que coincidan con la búsqueda.</div>';
        actualizarContadorSelectorUnidades();
        return;
    }

    lista.innerHTML = visibles.map((u) => {
        const nombre = String(u.nombre || 'SIN UNIDAD');
        const checked = estadoSeleccionCuentame.seleccionadas.has(nombre) ? 'checked' : '';
        return `
            <label class="flex items-center gap-3 px-4 py-3 hover:bg-slate-900/80 cursor-pointer transition">
                <input type="checkbox" value="${escaparHtml(nombre)}" data-unidad="${escaparHtml(nombre)}" onchange="toggleUnidadSeleccionada(this)" ${checked} class="h-4 w-4 rounded border-slate-600 bg-slate-950 text-indigo-500 focus:ring-indigo-500" />
                <span class="flex-1 min-w-0">
                    <span class="block text-sm font-medium text-slate-200 truncate">${escaparHtml(nombre)}</span>
                    <span class="block text-xs text-slate-500">${Number(u.total || 0)} registro(s) · ${Number(u.activos || 0)} activo(s) · ${Number(u.gestantes || 0)} gestante(s)</span>
                </span>
            </label>`;
    }).join('');

    actualizarContadorSelectorUnidades();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function seleccionarTodasUnidades(marcar = true) {
    const unidades = Array.isArray(estadoSeleccionCuentame.unidades) ? estadoSeleccionCuentame.unidades : [];
    if (!unidades.length) {
        mostrarMensaje('message-box', 'Primero analiza una base para detectar unidades.', 'error');
        return;
    }
    estadoSeleccionCuentame.seleccionadas = marcar
        ? new Set(unidades.map((u) => String(u.nombre || '')).filter(Boolean))
        : new Set();
    renderSelectorUnidades();
}

function manejarErrorAuthProcesamiento(xhr, resultado) {
    if (xhr.status === 401) {
        limpiarSesionLocal();
        mostrarLogin('Sesión expirada o token inválido. Inicia sesión nuevamente.');
        mostrarMensaje('message-box', resultado.error || 'Sesión expirada o token inválido. Inicia sesión nuevamente.', 'error');
        return true;
    }

    if (xhr.status === 403) {
        mostrarMensaje('message-box', resultado.error || 'No tienes permiso para cargar esta base de datos.', 'error');
        return true;
    }
    return false;
}

function enviarFormularioProcesamientoCuentame(formData, textoCargando) {
    const token = authToken();
    const tablaCuerpo = document.getElementById('tabla-cuerpo');
    if (tablaCuerpo) {
        tablaCuerpo.innerHTML = `<tr><td colspan="6" class="px-6 py-8 text-center text-indigo-400 animate-pulse">Procesando auditoría y generando formatos para las unidades seleccionadas...</td></tr>`;
    }
    limpiarMensajes();
    mostrarCargando(textoCargando || 'Procesando base de datos y formatos oficiales...');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${backendUrl}/api/procesar`, true);
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.setRequestHeader('X-Auth-Token', token);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

    xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
            const porcentaje = Math.round((event.loaded / event.total) * 100);
            actualizarBarraProgreso(Math.max(1, Math.min(95, porcentaje)));
        }
    };

    xhr.onload = function () {
        ocultarProgreso();
        ocultarCargando();

        let resultado = {};
        try {
            resultado = xhr.responseText ? JSON.parse(xhr.responseText) : {};
        } catch (_) {
            resultado = {};
        }

        if (manejarErrorAuthProcesamiento(xhr, resultado)) return;

        if (xhr.status === 202 && resultado.job_id) {
            esperarJobOperativo(resultado.job_id, procesarResultadoBase, 'message-box');
            return;
        }

        if (xhr.status >= 400) {
            const mensaje524 = xhr.status === 524
                ? 'El túnel agotó el tiempo de espera. La versión actual procesa la base en segundo plano; vuelve a intentar y espera el avance en pantalla.'
                : (resultado.error || `Error técnico del servidor (${xhr.status}). Revisa el archivo o intenta nuevamente.`);
            mostrarMensaje('message-box', mensaje524, 'error');
            return;
        }

        try {
            procesarResultadoBase(resultado);
        } catch (error) {
            mostrarMensaje('message-box', 'La base se procesó, pero hubo un error al actualizar el tablero.', 'error');
            console.error(error);
        }
    };

    xhr.onerror = function () {
        ocultarProgreso();
        ocultarCargando();
        mostrarMensaje('message-box', 'Ocurrió un error de conexión con el backend de Python.', 'error');
    };

    xhr.send(formData);
}

function detectarUnidadesBase() {
    const fileInput = document.getElementById('input-excel');
    const file = fileInput?.files?.[0];
    const error = validarArchivo(file, allowedBaseExtensions, 30);
    if (error) {
        mostrarMensaje('message-box', error, 'error');
        return;
    }

    const token = authToken();
    if (!token) {
        limpiarSesionLocal();
        mostrarLogin('Debe iniciar sesión para cargar la base de datos.');
        mostrarMensaje('message-box', 'Debe iniciar sesión para cargar la base de datos.', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('solo_detectar_unidades', '1');
    anexarOpcionesCuentame(formData);

    limpiarMensajes();
    mostrarCargando('Analizando la base Cuéntame y detectando unidades de atención...');

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${backendUrl}/api/procesar`, true);
    xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.setRequestHeader('X-Auth-Token', token);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');

    xhr.upload.onprogress = function (event) {
        if (event.lengthComputable) {
            const porcentaje = Math.round((event.loaded / event.total) * 100);
            actualizarBarraProgreso(Math.max(1, Math.min(95, porcentaje)));
        }
    };

    xhr.onload = function () {
        ocultarProgreso();
        ocultarCargando();

        let resultado = {};
        try {
            resultado = xhr.responseText ? JSON.parse(xhr.responseText) : {};
        } catch (_) {
            resultado = {};
        }

        if (manejarErrorAuthProcesamiento(xhr, resultado)) return;

        if (xhr.status >= 400) {
            mostrarMensaje('message-box', resultado.error || `No se pudieron detectar unidades (${xhr.status}).`, 'error');
            return;
        }

        estadoSeleccionCuentame.archivoToken = resultado.archivo_token || '';
        estadoSeleccionCuentame.archivoNombre = resultado.archivo || file.name;
        estadoSeleccionCuentame.totalUsuarios = Number(resultado.total_usuarios || 0);
        estadoSeleccionCuentame.unidades = Array.isArray(resultado.unidades) ? resultado.unidades : [];
        estadoSeleccionCuentame.seleccionadas = new Set();
        window.estadoSeleccionCuentame = estadoSeleccionCuentame;
        renderSelectorUnidades();
        mostrarMensaje('message-box', resultado.mensaje || 'Unidades detectadas. Selecciona cuáles deseas procesar.', 'success');
    };

    xhr.onerror = function () {
        ocultarProgreso();
        ocultarCargando();
        mostrarMensaje('message-box', 'Ocurrió un error de conexión con el backend de Python.', 'error');
    };

    xhr.send(formData);
}

function procesarUnidadesSeleccionadas(procesarTodo = false) {
    const token = authToken();
    if (!token) {
        limpiarSesionLocal();
        mostrarLogin('Debe iniciar sesión para procesar la base de datos.');
        mostrarMensaje('message-box', 'Debe iniciar sesión para procesar la base de datos.', 'error');
        return;
    }

    const seleccionadas = unidadesSeleccionadasDesdeDOM();
    estadoSeleccionCuentame.seleccionadas = new Set(seleccionadas);
    window.estadoSeleccionCuentame = estadoSeleccionCuentame;
    actualizarContadorSelectorUnidades();
    if (!procesarTodo && seleccionadas.length === 0) {
        mostrarMensaje('message-box', 'Selecciona al menos una unidad o usa la opción Procesar todo.', 'error');
        return;
    }

    const formData = new FormData();
    anexarOpcionesCuentame(formData);

    if (estadoSeleccionCuentame.archivoToken) {
        formData.append('archivo_token', estadoSeleccionCuentame.archivoToken);
    } else {
        const file = document.getElementById('input-excel')?.files?.[0];
        const error = validarArchivo(file, allowedBaseExtensions, 30);
        if (error) {
            mostrarMensaje('message-box', 'Primero analiza la base para detectar unidades.', 'error');
            return;
        }
        formData.append('file', file);
    }

    if (procesarTodo) {
        formData.append('procesar_todo', '1');
    } else {
        formData.append('unidades_seleccionadas', JSON.stringify(seleccionadas));
        formData.append('unidades_seleccionadas_csv', seleccionadas.join('|'));
        seleccionadas.forEach((unidad) => {
            formData.append('unidad_seleccionada', unidad);
            formData.append('unidades_seleccionadas[]', unidad);
        });
    }

    const texto = procesarTodo
        ? 'Procesando todas las unidades de la base Cuéntame...'
        : `Procesando ${seleccionadas.length} unidad(es) seleccionada(s)...`;
    enviarFormularioProcesamientoCuentame(formData, texto);
}

function subirYProcesar() {
    detectarUnidadesBase();
}

function esGrupoRppDescargaAlpha61(fmt) {
    const normalizado = String(fmt || '').trim().toUpperCase();
    return ['0_6_GESTANTES', '6_11_MESES', '1_2_ANOS', '3_5_ANOS'].includes(normalizado)
        || String(fmt || '').toLowerCase().startsWith('rpp_');
}

function descargar(unidad, formato) {
    const fmtOriginal = String(formato || '').trim();
    const fmt = fmtOriginal.toLowerCase();
    if (fmt.includes('bienestarina')) {
        // ALPHA73: fix mínimo diferencial. Bienestarina solo usa su endpoint específico por UDS.
        const urlBienestarina = `${backendUrl}/api/bienestarina/descargar?unidad=${encodeURIComponent(unidad)}`;
        console.info('[ALPHA73] Descarga Bienestarina por endpoint específico:', { unidad, url: urlBienestarina });
        descargarArchivoFormatoAlpha63({
            url: urlBienestarina,
            unidad,
            formato: 'Bienestarina',
            nombreBase: `BIENESTARINA_${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}.xlsx`
        });
        return;
    }
    if (esGrupoRppDescargaAlpha61(fmtOriginal)) {
        descargarArchivoFormatoAlpha63({
            url: `${backendUrl}/api/rpp/descargar?unidad=${encodeURIComponent(unidad)}&grupo=${encodeURIComponent(fmtOriginal)}`,
            unidad,
            formato: `RPP ${fmtOriginal}`,
            nombreBase: `RPP_${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}_${fmtOriginal}.xlsx`
        });
        return;
    }
    const periodo = periodoFormatosSeleccionado();
    const queryPeriodo = `mes=${encodeURIComponent(periodo.mes)}&anio=${encodeURIComponent(periodo.anio)}`;
    descargarArchivoFormatoAlpha63({
        url: `${backendUrl}/api/descargar/${encodeURIComponent(unidad)}/${encodeURIComponent(formato)}?${queryPeriodo}`,
        unidad,
        formato,
        nombreBase: `${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}_${String(formato).replace(/[^A-Za-z0-9]+/g, '_')}_${periodo.anio}_${String(periodo.mes).padStart(2, '0')}.xlsx`
    });
}

async function descargarArchivoFormatoAlpha63({ url, unidad, formato, nombreBase }) {
    try {
        const response = await fetch(url, { method: 'GET', credentials: 'same-origin' });
        const contentType = (response.headers.get('content-type') || '').toLowerCase();

        if (!response.ok || contentType.includes('application/json')) {
            let data = {};
            try {
                data = await response.json();
            } catch (error) {
                data = {};
            }
            const msg = data.mensaje || data.error || `No se pudo descargar ${formato} para esta UDS.`;
            if (typeof mostrarMensaje === 'function') {
                mostrarMensaje('message-box', msg, 'error');
            } else {
                alert(msg);
            }
            console.warn('Descarga de formato no realizada:', { unidad, formato, data });
            return;
        }

        const blob = await response.blob();
        if (!blob || blob.size === 0) {
            throw new Error(`El archivo de ${formato} llegó vacío.`);
        }

        let filename = nombreBase || `FORMATO_${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}.xlsx`;
        const disposition = response.headers.get('content-disposition') || '';
        const match = disposition.match(/filename\*?=(?:UTF-8''|")?([^";]+)/i);
        if (match && match[1]) {
            filename = decodeURIComponent(match[1].replace(/"/g, '').trim());
        }

        const blobUrl = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = blobUrl;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => window.URL.revokeObjectURL(blobUrl), 1500);

        if (typeof mostrarMensaje === 'function') {
            mostrarMensaje('message-box', `${formato} descargado para ${unidad}.`, 'success');
        }
    } catch (error) {
        const msg = `No se pudo descargar ${formato} para ${unidad}: ${error.message || error}`;
        if (typeof mostrarMensaje === 'function') {
            mostrarMensaje('message-box', msg, 'error');
        } else {
            alert(msg);
        }
        console.error('Error descargando formato:', { unidad, formato, error });
    }
}

async function descargarBienestarinaAlpha62(unidad) {
    if (!unidad) {
        alert('Debe seleccionar una UDS antes de descargar Bienestarina.');
        return;
    }
    const url = `${backendUrl}/api/bienestarina/descargar?unidad=${encodeURIComponent(unidad)}`;
    return descargarArchivoFormatoAlpha63({
        url,
        unidad,
        formato: 'Bienestarina',
        nombreBase: `BIENESTARINA_${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}.xlsx`
    });
}

function descargarRppCategoria(unidad, grupo) {
    if (!unidad || !grupo) {
        alert('Debe seleccionar una unidad y un grupo etario para descargar RPP.');
        return;
    }
    const url = `${backendUrl}/api/rpp/descargar?unidad=${encodeURIComponent(unidad)}&grupo=${encodeURIComponent(grupo)}`;
    descargarArchivoFormatoAlpha63({
        url,
        unidad,
        formato: `RPP ${grupo}`,
        nombreBase: `RPP_${String(unidad).replace(/[^A-Za-z0-9]+/g, '_')}_${grupo}.xlsx`
    });
}

function subirPlantilla() {
    const input = document.getElementById('input-template');
    const tipo = document.getElementById('template-type').value;
    const version = document.getElementById('template-version').value.trim() || '1.0';
    const file = input.files[0];
    const error = validarArchivo(file, allowedTemplateExtensions, 20);
    if (error) {
        mostrarMensaje('template-message', error, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('tipo', tipo);
    formData.append('version', version);

    fetch(`${backendUrl}/api/plantillas`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('template-message', data.message, 'success');
            input.value = '';
            fetchPlantillas();
        })
        .catch((error) => {
            mostrarMensaje('template-message', error.message || 'Error al subir plantilla.', 'error');
        });
}

function fetchPlantillas() {
    fetch(`${backendUrl}/api/plantillas`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const lista = document.getElementById('plantillas-list');
            plantillasRegistradas = Array.isArray(data.plantillas) ? data.plantillas : [];

            if (!lista) return;

            if (plantillasRegistradas.length === 0) {
                lista.innerHTML = `<tr><td colspan="6" class="px-6 py-8 text-center text-slate-500">No hay plantillas registradas aún.</td></tr>`;
                return;
            }

            lista.innerHTML = plantillasRegistradas.map((item) => {
                const estado = String(item.estado || (item.activa ? 'activo' : 'inactivo')).toLowerCase();
                const estadoClase = estado === 'activo'
                    ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30'
                    : 'bg-slate-500/10 text-slate-300 border-slate-500/30';

                return `
                    <tr class="hover:bg-slate-900/50 transition">
                        <td class="px-6 py-4">${escaparHtml(item.nombre_original || item.nombre || '')}</td>
                        <td class="px-6 py-4">${escaparHtml(item.tipo || '')}</td>
                        <td class="px-6 py-4">${escaparHtml(item.version || item['versión'] || '1.0')}</td>
                        <td class="px-6 py-4">${escaparHtml(fechaPlantillaLegible(item.fecha_carga || item.fecha_ultima_actualizacion))}</td>
                        <td class="px-6 py-4">
                            <span class="rounded-lg border px-2.5 py-1 text-xs ${estadoClase}">${escaparHtml(estado)}</span>
                        </td>
                        <td class="px-6 py-4">
                            <div class="flex flex-wrap gap-2">
                                <button onclick="editarPlantilla(${Number(item.id)})" class="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs text-cyan-300 hover:bg-cyan-500/20 transition">Editar</button>
                                <button onclick="eliminarPlantilla(${Number(item.id)}, false)" class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs text-amber-300 hover:bg-amber-500/20 transition">Eliminar</button>
                                <button onclick="eliminarPlantilla(${Number(item.id)}, true)" class="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/20 transition">Borrar</button>
                            </div>
                        </td>
                    </tr>
                `;
            }).join('');
        })
        .catch((error) => {
            console.error('Error al cargar plantillas', error);
        });
}

function editarPlantilla(id) {
    const plantilla = plantillasRegistradas.find((item) => Number(item.id) === Number(id));
    if (!plantilla) {
        mostrarMensaje('template-message', 'No se encontró la plantilla seleccionada.', 'error');
        return;
    }

    const tipo = prompt('Tipo de plantilla:', plantilla.tipo || 'Otros');
    if (tipo === null) return;

    const version = prompt('Versión:', plantilla.version || plantilla['versión'] || '1.0');
    if (version === null) return;

    const estadoActual = plantilla.estado || (plantilla.activa ? 'activo' : 'inactivo');
    const estado = prompt('Estado: activo o inactivo', estadoActual);
    if (estado === null) return;

    fetch(`${backendUrl}/api/plantillas/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tipo: tipo.trim() || plantilla.tipo || 'Otros',
            version: version.trim() || '1.0',
            estado: estado.trim() || estadoActual || 'activo'
        })
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('template-message', data.message || 'Plantilla actualizada.', 'success');
            fetchPlantillas();
        })
        .catch((error) => {
            mostrarMensaje('template-message', error.message || 'No se pudo actualizar la plantilla.', 'error');
        });
}

function eliminarPlantilla(id, permanente = false) {
    const plantilla = plantillasRegistradas.find((item) => Number(item.id) === Number(id));
    const nombre = plantilla?.nombre_original || plantilla?.nombre || 'esta plantilla';

    const mensaje = permanente
        ? `Vas a BORRAR permanentemente ${nombre}. Se eliminará de la lista y se intentará borrar el archivo físico. ¿Continuar?`
        : `Vas a ELIMINAR/DESACTIVAR ${nombre}. Se conserva el historial y el archivo. ¿Continuar?`;

    if (!confirm(mensaje)) return;

    const url = `${backendUrl}/api/plantillas/${encodeURIComponent(id)}${permanente ? '?hard=1' : ''}`;
    fetch(url, { method: 'DELETE' })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('template-message', data.message || 'Operación realizada.', 'success');
            fetchPlantillas();
        })
        .catch((error) => {
            mostrarMensaje('template-message', error.message || 'No se pudo eliminar la plantilla.', 'error');
        });
}

function subirNutricion() {
    const input = document.getElementById('input-nutricion');
    const file = input.files[0];
    const error = validarArchivo(file, allowedNutritionExtensions, 20);
    if (error) {
        mostrarMensaje('nutricion-message', error, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch(`${backendUrl}/api/nutricion`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('nutricion-message', data.message, 'success');
            document.getElementById('nutri-al-dia').innerText = data.status.al_dia || 0;
            document.getElementById('nutri-proximo').innerText = data.status.proximo_vencer || 0;
            document.getElementById('nutri-vencido').innerText = data.status.vencido || 0;
            input.value = '';
            renderBoaNutricion(data.boa || {});
            fetchBoaNutricion();
        })
        .catch((error) => {
            mostrarMensaje('nutricion-message', error.message || 'Error al procesar nutrición.', 'error');
        });
}


function estadoNutricionClase(valor) {
    const v = normalizarFiltro(valor);
    if (v.includes('DESNUTRICION') || v.includes('RIESGO') || v.includes('VENCIDO')) return 'text-rose-300';
    if (v.includes('PENDIENTE') || v.includes('PROXIMO')) return 'text-amber-300';
    if (v.includes('ADECUADO') || v.includes('AL DIA')) return 'text-emerald-300';
    return 'text-slate-300';
}

function renderBoaNutricion(boa = {}) {
    const resumenBox = document.getElementById('nutricion-boa-resumen');
    const body = document.getElementById('nutricion-boa-list');
    if (!resumenBox || !body) return;
    const resumen = boa.resumen || {};
    const detalles = Array.isArray(boa.detalles) ? boa.detalles : [];
    const cards = [
        ['Adecuado', resumen.ADECUADO || 0],
        ['Riesgo', resumen.RIESGO || 0],
        ['Desnutrición', resumen.DESNUTRICION || 0],
        ['Pendiente', resumen.PENDIENTE || 0]
    ];
    resumenBox.innerHTML = cards.map(([label, value]) => `
        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <p class="text-xs text-slate-400">${escaparHtml(label)}</p>
            <p class="mt-1 text-2xl font-bold ${estadoNutricionClase(label)}">${escaparHtml(value)}</p>
        </div>
    `).join('');
    if (!detalles.length) {
        body.innerHTML = '<tr><td colspan="9" class="px-3 py-8 text-center text-slate-500">No hay registros de peso y talla todavía.</td></tr>';
        return;
    }
    body.innerHTML = detalles.slice(0, 250).map(item => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-3 py-2">${escaparHtml(item.unidad || '')}</td>
            <td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(item.nombre || '')}</td>
            <td class="px-3 py-2">${escaparHtml(item.documento || '')}</td>
            <td class="px-3 py-2">${escaparHtml(item.peso || '')}</td>
            <td class="px-3 py-2">${escaparHtml(item.talla || '')}</td>
            <td class="px-3 py-2 ${estadoNutricionClase(item.estado_nutricional)}">${escaparHtml(item.estado_nutricional || '')}</td>
            <td class="px-3 py-2 ${estadoNutricionClase(item.estado_control)}">${escaparHtml(item.estado_control || '')}</td>
            <td class="px-3 py-2">${escaparHtml(item.trimestre || '')}</td>
            <td class="px-3 py-2">${escaparHtml(item.fecha_proximo_control || '')}</td>
        </tr>
    `).join('');
}

function fetchBoaNutricion() {
    fetch(`${backendUrl}/api/nutricion/boa`)
        .then(manejarRespuestaJson)
        .then((data) => renderBoaNutricion(data.boa || {}))
        .catch((error) => console.error('No se pudo cargar BOA nutrición', error));
}

function subirTalento() {
    const input = document.getElementById('input-talento');
    const file = input.files[0];
    const error = validarArchivo(file, allowedTalentExtensions, 20);
    if (error) {
        mostrarMensaje('talento-message', error, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    fetch(`${backendUrl}/api/talento`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('talento-message', data.message, 'success');
            if (data.integracion) renderTalentoIntegracion(data.integracion);
            input.value = '';
            fetchTalento();
        })
        .catch((error) => {
            mostrarMensaje('talento-message', error.message || 'Error al procesar talento humano.', 'error');
        });
}

function fetchTalento() {
    const contenedor = document.getElementById('talento-list');
    if (!contenedor) return;

    fetch(`${backendUrl}/api/talento`)
        .then(manejarRespuestaJson)
        .then((data) => {
            talentoRegistrado = Array.isArray(data.talento) ? data.talento : [];
            renderTalento();
            if (data.integracion) {
                renderTalentoIntegracion(data.integracion);
            } else {
                fetchTalentoIntegracion();
            }
        })
        .catch((error) => {
            console.error('No se pudo cargar talento humano', error);
            contenedor.innerHTML = '<tr><td colspan="10" class="px-6 py-8 text-center text-rose-400">No se pudo cargar talento humano.</td></tr>';
        });
}

function renderTalentoIntegracion(integracion = {}) {
    const contenedor = document.getElementById('talento-integracion-resumen');
    if (!contenedor) return;
    contenedor.querySelectorAll('[data-ti]').forEach((el) => {
        const key = el.getAttribute('data-ti');
        el.textContent = integracion[key] ?? 0;
    });
    const estado = document.getElementById('talento-integracion-estado');
    if (estado) {
        const ultimo = integracion.ultimo_evento;
        estado.textContent = ultimo?.fecha_accion
            ? `Última sincronización: ${fechaPlantillaLegible(ultimo.fecha_accion)} por ${ultimo.usuario || 'sistema'}`
            : 'Aún no hay sincronización registrada.';
    }
}

function fetchTalentoIntegracion() {
    const contenedor = document.getElementById('talento-integracion-resumen');
    if (!contenedor) return;
    fetch(`${backendUrl}/api/talento/integracion`)
        .then(manejarRespuestaJson)
        .then((data) => renderTalentoIntegracion(data.integracion || {}))
        .catch((error) => console.error('No se pudo cargar integración de talento humano', error));
}

function sincronizarTalentoGlobal() {
    mostrarMensaje('talento-message', 'Sincronizando talento humano con todos los módulos...', 'success');
    fetch(`${backendUrl}/api/talento/sincronizar-global`, { method: 'POST' })
        .then(manejarRespuestaJson)
        .then((data) => {
            renderTalentoIntegracion(data.integracion || {});
            mostrarMensaje('talento-message', data.message || 'Talento Humano sincronizado con toda la plataforma.', 'success');
            fetchTalento();
            if (typeof gpCargarDashboard === 'function') {
                try { gpCargarDashboard(); } catch (_) {}
            }
            if (typeof gcCargarDashboard === 'function') {
                try { gcCargarDashboard(); } catch (_) {}
            }
        })
        .catch((error) => {
            mostrarMensaje('talento-message', error.message || 'No se pudo sincronizar talento humano.', 'error');
        });
}


function talentoTipoTexto(item = {}) {
    return normalizarFiltro([item.tipo_equipo, item.cargo, item.perfil, item.rol_normalizado].filter(Boolean).join(' '));
}

function talentoEsCoordinador(item = {}) {
    return talentoTipoTexto(item).includes('COORDINADOR');
}

function talentoEtiquetaTipo(item = {}) {
    const tipo = talentoTipoTexto(item);
    if (tipo.includes('DOCENTE') || tipo.includes('AGENTE')) return 'AGENTE EDUCATIVO';
    if (tipo.includes('COORDINADOR')) return 'COORDINADOR';
    if (tipo.includes('NUTRIC')) return 'NUTRICIONISTA';
    if (tipo.includes('ENFERMER') || tipo.includes('SALUD')) return 'ENFERMERÍA';
    if (tipo.includes('PSICOSOCIAL') || tipo.includes('PSICOLOG')) return 'PSICOSOCIAL';
    if (tipo.includes('PEDAGOG')) return 'PEDAGOGÍA';
    if (tipo.includes('ADMINISTR')) return 'ADMINISTRATIVO';
    if (tipo.includes('SABEDOR') || tipo.includes('ARTISTA')) return 'APOYO CULTURAL';
    return item.tipo_equipo || item.cargo || 'APOYO';
}

function talentoCoordinadorPorUnidad(items = talentoRegistrado) {
    const mapa = {};
    (items || []).forEach((item) => {
        if (!talentoEsCoordinador(item)) return;
        const unidadKey = normalizarFiltro(item.unidad || '');
        if (unidadKey && item.nombre) mapa[unidadKey] = item.nombre;
        try {
            const unidades = JSON.parse(item.unidades || '[]');
            if (Array.isArray(unidades)) {
                unidades.forEach((unidad) => {
                    const key = normalizarFiltro(unidad || '');
                    if (key && item.nombre) mapa[key] = item.nombre;
                });
            }
        } catch (_) {}
    });
    return mapa;
}

function talentoCoordinadorVisible(item = {}, mapa = {}) {
    if (item.coordinador) return item.coordinador;
    if (talentoEsCoordinador(item)) return item.nombre || 'Coordinador sin nombre';
    const key = normalizarFiltro(item.unidad || '');
    return mapa[key] || '';
}

function renderEquipoCoordinadores() {
    const contenedor = document.getElementById('equipo-coordinadores');
    if (!contenedor) return;

    const activos = (talentoRegistrado || []).filter((item) => String(item.estado || (item.activo ? 'activo' : 'inactivo')).toLowerCase() === 'activo');
    const coordinadorPorUnidad = talentoCoordinadorPorUnidad(activos);
    const grupos = {};

    activos.forEach((item) => {
        const coordinador = talentoCoordinadorVisible(item, coordinadorPorUnidad) || 'Sin coordinador asignado';
        if (!grupos[coordinador]) {
            grupos[coordinador] = { total: 0, agentes: 0, psicosocial: 0, enfermeria: 0, nutricion: 0, pedagogia: 0, administrativo: 0, apoyo: 0, unidades: new Set() };
        }
        const g = grupos[coordinador];
        g.total += 1;
        if (item.unidad) g.unidades.add(item.unidad);
        const tipo = talentoTipoTexto(item);
        if (tipo.includes('DOCENTE') || tipo.includes('AGENTE')) g.agentes += 1;
        else if (tipo.includes('PSICOSOCIAL') || tipo.includes('PSICOLOG')) g.psicosocial += 1;
        else if (tipo.includes('NUTRIC')) g.nutricion += 1;
        else if (tipo.includes('ENFERMER') || tipo.includes('SALUD')) g.enfermeria += 1;
        else if (tipo.includes('PEDAGOG')) g.pedagogia += 1;
        else if (tipo.includes('ADMINISTR')) g.administrativo += 1;
        else g.apoyo += 1;
    });

    const nombres = Object.keys(grupos).sort((a, b) => a.localeCompare(b, 'es'));
    if (nombres.length === 0) {
        contenedor.innerHTML = '<p class="text-slate-500">No hay equipos registrados todavía.</p>';
        return;
    }

    contenedor.innerHTML = nombres.map((nombre) => {
        const g = grupos[nombre];
        return `
            <div class="rounded-2xl border border-slate-800 bg-slate-900/60 p-4">
                <p class="font-semibold text-slate-100">${escaparHtml(nombre)}</p>
                <p class="mt-1 text-xs text-slate-500">${g.unidades.size} unidad(es) asociada(s) · ${g.total} persona(s)</p>
                <div class="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <span>Agentes educativos: <strong class="text-slate-200">${g.agentes}</strong></span>
                    <span>Psicosocial: <strong class="text-slate-200">${g.psicosocial}</strong></span>
                    <span>Enfermería: <strong class="text-slate-200">${g.enfermeria}</strong></span>
                    <span>Nutrición: <strong class="text-slate-200">${g.nutricion}</strong></span>
                    <span>Pedagogía: <strong class="text-slate-200">${g.pedagogia}</strong></span>
                    <span>Administrativo: <strong class="text-slate-200">${g.administrativo}</strong></span>
                    <span>Apoyo/Sabedor: <strong class="text-slate-200">${g.apoyo}</strong></span>
                </div>
            </div>
        `;
    }).join('');
}

function renderTalento() {
    const contenedor = document.getElementById('talento-list');
    if (!contenedor) return;

    if (!Array.isArray(talentoRegistrado) || talentoRegistrado.length === 0) {
        contenedor.innerHTML = '<tr><td colspan="10" class="px-6 py-8 text-center text-slate-500">No hay talento humano registrado todavía.</td></tr>';
        renderEquipoCoordinadores();
        return;
    }

    const coordinadorPorUnidad = talentoCoordinadorPorUnidad(talentoRegistrado);
    contenedor.innerHTML = talentoRegistrado.map((item) => {
        const estado = String(item.estado || (item.activo ? 'activo' : 'inactivo')).toLowerCase();
        const tipoVisible = talentoEtiquetaTipo(item);
        const coordinadorVisible = talentoCoordinadorVisible(item, coordinadorPorUnidad);
        return `
            <tr class="hover:bg-slate-900/50 transition">
                <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(item.unidad || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.nombre || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.documento || '')}</td>
                <td class="px-4 py-3">${escaparHtml(tipoVisible)}</td>
                <td class="px-4 py-3">${escaparHtml(item.cargo || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.direccion || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.telefono || '')}</td>
                <td class="px-4 py-3">${escaparHtml(coordinadorVisible || '')}<div class="text-[11px] text-slate-500">${escaparHtml(estado)}</div></td>
                <td class="px-4 py-3">${escaparHtml(item.contrato || '')}</td>
                <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-2">
                        <button onclick="editarTalento(${Number(item.id)})" class="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-1 text-xs text-cyan-300 hover:bg-cyan-500/20">Editar</button>
                        <button onclick="eliminarTalento(${Number(item.id)}, false)" class="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-300 hover:bg-amber-500/20">Eliminar</button>
                        <button onclick="eliminarTalento(${Number(item.id)}, true)" class="rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1 text-xs text-rose-300 hover:bg-rose-500/20">Borrar</button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
    renderEquipoCoordinadores();
}

function guardarTalentoManual() {
    const data = {
        nombre: document.getElementById('talento-nombre')?.value.trim() || '',
        documento: document.getElementById('talento-documento')?.value.trim() || '',
        tipo_equipo: document.getElementById('talento-tipo-equipo')?.value.trim() || 'DOCENTE',
        cargo: document.getElementById('talento-cargo')?.value.trim() || 'AGENTE EDUCATIVO',
        unidad: document.getElementById('talento-unidad')?.value.trim() || '',
        direccion: document.getElementById('talento-direccion')?.value.trim() || '',
        telefono: document.getElementById('talento-telefono')?.value.trim() || '',
        coordinador: document.getElementById('talento-coordinador')?.value.trim() || '',
        contrato: document.getElementById('talento-contrato')?.value.trim() || '',
        estado: 'activo'
    };

    if (!data.nombre || !data.documento) {
        mostrarMensaje('talento-message', 'Nombre y documento son obligatorios.', 'error');
        return;
    }

    fetch(`${backendUrl}/api/talento`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
        .then(manejarRespuestaJson)
        .then((resp) => {
            mostrarMensaje('talento-message', resp.message || 'Talento humano guardado.', 'success');
            if (resp.integracion) renderTalentoIntegracion(resp.integracion);
            ['talento-nombre', 'talento-documento', 'talento-cargo', 'talento-unidad', 'talento-direccion', 'talento-telefono', 'talento-coordinador', 'talento-contrato'].forEach((id) => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            fetchTalento();
        })
        .catch((error) => mostrarMensaje('talento-message', error.message || 'No se pudo guardar talento humano.', 'error'));
}

function editarTalento(id) {
    const item = talentoRegistrado.find((row) => Number(row.id) === Number(id));
    if (!item) return;

    const nombre = prompt('Nombre completo:', item.nombre || '');
    if (nombre === null) return;
    const documento = prompt('Documento:', item.documento || '');
    if (documento === null) return;
    const tipo_equipo = prompt('Tipo equipo: DOCENTE, COORDINADOR, PSICOSOCIAL, ENFERMERIA, PEDAGOGIA, ADMINISTRATIVO', item.tipo_equipo || 'DOCENTE');
    if (tipo_equipo === null) return;
    const cargo = prompt('Cargo:', item.cargo || 'AGENTE EDUCATIVO');
    if (cargo === null) return;
    const unidad = prompt('Unidad / comunidad:', item.unidad || '');
    if (unidad === null) return;
    const direccion = prompt('Dirección:', item.direccion || '');
    if (direccion === null) return;
    const telefono = prompt('Teléfono:', item.telefono || '');
    if (telefono === null) return;
    const coordinador = prompt('Coordinador responsable:', item.coordinador || '');
    if (coordinador === null) return;
    const contrato = prompt('Contrato / equipo:', item.contrato || '');
    if (contrato === null) return;
    const estado = prompt('Estado: activo o inactivo', item.estado || 'activo');
    if (estado === null) return;

    fetch(`${backendUrl}/api/talento/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nombre, documento, tipo_equipo, cargo, unidad, direccion, telefono, coordinador, contrato, estado })
    })
        .then(manejarRespuestaJson)
        .then((resp) => {
            mostrarMensaje('talento-message', resp.message || 'Talento humano actualizado.', 'success');
            if (resp.integracion) renderTalentoIntegracion(resp.integracion);
            fetchTalento();
        })
        .catch((error) => mostrarMensaje('talento-message', error.message || 'No se pudo actualizar talento humano.', 'error'));
}

function eliminarTalento(id, permanente = false) {
    const item = talentoRegistrado.find((row) => Number(row.id) === Number(id));
    const nombre = item?.nombre || 'este registro';
    const pregunta = permanente
        ? `Vas a borrar permanentemente ${nombre}. ¿Continuar?`
        : `Vas a desactivar ${nombre}. ¿Continuar?`;
    if (!confirm(pregunta)) return;

    fetch(`${backendUrl}/api/talento/${encodeURIComponent(id)}${permanente ? '?hard=1' : ''}`, { method: 'DELETE' })
        .then(manejarRespuestaJson)
        .then((resp) => {
            mostrarMensaje('talento-message', resp.message || 'Operación realizada.', 'success');
            if (resp.integracion) renderTalentoIntegracion(resp.integracion);
            fetchTalento();
        })
        .catch((error) => mostrarMensaje('talento-message', error.message || 'No se pudo eliminar talento humano.', 'error'));
}

function subirDocumentoInstitucional() {
    const input = document.getElementById('input-documento');
    const file = input.files[0];
    const error = validarArchivo(file, allowedDocumentExtensions, 50);
    if (error) {
        mostrarMensaje('documento-message', error, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('tipo', document.getElementById('doc-type').value);
    formData.append('titulo', document.getElementById('doc-title').value.trim() || file.name);
    formData.append('version', document.getElementById('doc-version').value.trim() || '1.0');

    fetch(`${backendUrl}/api/documentos-institucionales`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            const reglas = data.reglas_inferidas ? ` Reglas creadas: ${data.reglas_inferidas}.` : '';
            const detalle = data.indexado ? ` Indexado para busqueda y asistente.${reglas}` : ' Guardado; este formato no permite extraccion local de texto.';
            mostrarMensaje('documento-message', `${data.message}${detalle}`, 'success');
            input.value = '';
            fetchDocumentosInstitucionales();
            evaluarOperacionICBF(false);
        })
        .catch((error) => {
            mostrarMensaje('documento-message', error.message || 'Error al cargar documento.', 'error');
        });
}

function inicializarPeriodoEntregable() {
    const input = document.getElementById('entregable-periodo');
    if (!input) return;
    input.value = new Date().toISOString().slice(0, 7);
}

function fetchDocumentosInstitucionales() {
    const contenedor = document.getElementById('documentos-list');
    if (!contenedor) return;
    fetch(`${backendUrl}/api/documentos-institucionales`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const documentos = data.documentos || [];
            if (documentos.length === 0) {
                contenedor.innerHTML = '<p>No hay documentos institucionales cargados.</p>';
                return;
            }
            contenedor.innerHTML = documentos.slice(0, 5).map((doc) => `
                <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                    <p class="text-slate-200">${doc.tipo}: ${doc.titulo}</p>
                    <p class="text-xs">Versión ${doc.version} · ${doc.estado}</p>
                </div>
            `).join('');
        })
        .catch(() => {
            contenedor.innerHTML = '<p>No se pudo cargar el centro documental.</p>';
        });
}

function estadoEntregableClase(estado) {
    const e = normalizarFiltro(estado);
    if (e === 'CARGADO') return 'text-emerald-400';
    if (e === 'VENCIDO') return 'text-rose-400';
    if (e === 'PROXIMO') return 'text-amber-400';
    return 'text-slate-400';
}

function fetchEntregablesOperacion() {
    const contenedor = document.getElementById('entregables-list');
    if (!contenedor) return;
    const periodo = document.getElementById('entregable-periodo')?.value || new Date().toISOString().slice(0, 7);
    fetch(`${backendUrl}/api/entregables-operacion?periodo=${encodeURIComponent(periodo)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const tablero = data.tablero || [];
            const resumen = data.resumen || {};

            ['total', 'cargados', 'pendientes', 'proximos', 'vencidos'].forEach((key) => {
                const el = document.getElementById(`entregables-${key}`);
                if (el) el.innerText = resumen[key] ?? 0;
            });

            if (tablero.length === 0) {
                contenedor.innerHTML = '<p class="text-slate-500">No hay entregables configurados para este periodo.</p>';
                return;
            }

            contenedor.innerHTML = `
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-400">
                        <thead class="bg-slate-900 text-slate-300 uppercase">
                            <tr>
                                <th class="px-3 py-2">Entregable</th>
                                <th class="px-3 py-2">Categoría</th>
                                <th class="px-3 py-2">Fecha límite</th>
                                <th class="px-3 py-2">Responsable</th>
                                <th class="px-3 py-2">Estado</th>
                                <th class="px-3 py-2">Observaciones</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${tablero.map((item) => `
                                <tr class="border-b border-slate-800/70">
                                    <td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(item.tipo || '')}</td>
                                    <td class="px-3 py-2">${escaparHtml(item.categoria || '')}</td>
                                    <td class="px-3 py-2">${escaparHtml(item.fecha_limite || '')}</td>
                                    <td class="px-3 py-2">${escaparHtml(item.responsable || '')}</td>
                                    <td class="px-3 py-2 ${estadoEntregableClase(item.estado)}">${escaparHtml(item.estado || '')}</td>
                                    <td class="px-3 py-2">${escaparHtml(item.observaciones || '')}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
        })
        .catch(() => {
            contenedor.innerHTML = '<p>No se pudieron cargar los entregables.</p>';
        });
}

function subirEntregableOperacion() {
    const input = document.getElementById('input-entregable');
    const file = input.files[0];
    const error = validarArchivo(file, allowedDocumentExtensions, 50);
    if (error) {
        mostrarMensaje('entregable-message', error, 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('tipo', document.getElementById('entregable-tipo').value);
    formData.append('periodo', document.getElementById('entregable-periodo').value || new Date().toISOString().slice(0, 7));
    formData.append('unidad', document.getElementById('entregable-unidad').value.trim());
    formData.append('fecha_limite', document.getElementById('entregable-fecha-limite')?.value || '');
    formData.append('responsable', document.getElementById('entregable-responsable')?.value.trim() || '');
    formData.append('categoria', document.getElementById('entregable-categoria')?.value.trim() || '');
    formData.append('observaciones', document.getElementById('entregable-observaciones')?.value.trim() || '');

    fetch(`${backendUrl}/api/entregables-operacion`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            mostrarMensaje('entregable-message', data.message, 'success');
            input.value = '';
            fetchEntregablesOperacion();
            evaluarOperacionICBF(false);
        })
        .catch((error) => {
            mostrarMensaje('entregable-message', error.message || 'Error al cargar entregable.', 'error');
        });
}

function renderCumplimiento(data) {
    if (!data) return;
    document.getElementById('cumplimiento-general').innerText = `${data.cumplimiento_general || 0}%`;
    document.getElementById('cumplimiento-beneficiarios').innerText = data.indicadores?.beneficiarios_activos || 0;
    document.getElementById('cumplimiento-retiro').innerText = data.indicadores?.edad_retiro || 0;
    document.getElementById('cumplimiento-nutricion').innerText = data.indicadores?.peso_talla_vencido || 0;

    const componentes = document.getElementById('componentes-cumplimiento');
    componentes.innerHTML = Object.entries(data.componentes || {}).map(([nombre, valor]) => `
        <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
            <p class="text-xs text-slate-400">${nombre}</p>
            <p class="mt-2 text-2xl font-bold ${valor >= 80 ? 'text-emerald-400' : valor >= 50 ? 'text-amber-400' : 'text-rose-400'}">${valor}%</p>
        </div>
    `).join('');

    const matriz = document.getElementById('matriz-estandares');
    matriz.innerHTML = (data.matriz_estandares || []).map((item) => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3 text-slate-200">${item.estandar}</td>
            <td class="px-4 py-3">${item.cumple ? '<span class="text-emerald-400">Si</span>' : '<span class="text-rose-400">No</span>'}</td>
            <td class="px-4 py-3">${item.evidencia}</td>
        </tr>
    `).join('');

    const incumplimientos = document.getElementById('lista-incumplimientos');
    if (!Array.isArray(data.incumplimientos) || data.incumplimientos.length === 0) {
        incumplimientos.innerHTML = '<p class="text-emerald-400">Sin incumplimientos detectados.</p>';
        return;
    }
    incumplimientos.innerHTML = data.incumplimientos.map((item) => `
        <div class="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3">
            <p class="font-medium text-rose-300">${item.tipo}</p>
            <p class="text-slate-300">${item.detalle}</p>
        </div>
    `).join('');
}

function evaluarOperacionICBF(guardar = true) {
    fetch(`${backendUrl}/api/cumplimiento/evaluar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    })
        .then(manejarRespuestaJson)
        .then(renderCumplimiento)
        .catch((error) => {
            console.error('Error al evaluar cumplimiento', error);
            if (guardar) {
                alert(error.message || 'Error al evaluar la operacion.');
            }
        });
}

function preguntarAsistenteICBF() {
    const pregunta = document.getElementById('asistente-pregunta').value.trim();
    if (!pregunta) return;
    const respuesta = document.getElementById('asistente-respuesta');
    respuesta.innerText = 'Consultando documentos institucionales...';

    fetch(`${backendUrl}/api/asistente-icbf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pregunta })
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            const fuentes = (data.fuentes || []).map(f => `${f.tipo}: ${f.titulo} v${f.version}`).join(' | ');
            respuesta.innerText = fuentes ? `${data.respuesta}\n\nFuente: ${fuentes}` : data.respuesta;
        })
        .catch((error) => {
            respuesta.innerText = error.message || 'Error al consultar asistente.';
        });
}

function generarInformeICBF() {
    fetch(`${backendUrl}/api/informes/supervision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            evaluarOperacionICBF(false);
            descargarArchivoAutenticado(`${backendUrl}${data.url}`)
                .catch((error) => alert(error.message || 'No se pudo descargar el informe ICBF.'));
        })
        .catch((error) => {
            alert(error.message || 'Error al generar informe ICBF.');
        });
}


function periodoMesActual() {
    return new Date().toISOString().slice(0, 7);
}

function inicializarCuentasCobro() {
    const mes = document.getElementById('cuenta-mes');
    if (mes && !mes.value) mes.value = periodoMesActual();
    cargarCuentasCobro();
}

function cargarCuentasCobro() {
    const plantillasBody = document.getElementById('cuentas-plantillas-list');
    const generadasBody = document.getElementById('cuentas-generadas-list');
    if (!plantillasBody && !generadasBody) return;

    fetch(`${backendUrl}/api/cuentas-cobro/plantillas`)
        .then(manejarRespuestaJson)
        .then(data => {
            const plantillas = data.plantillas || [];
            if (plantillasBody) {
                plantillasBody.innerHTML = plantillas.length ? plantillas.map(p => `
                    <tr class="hover:bg-slate-900/50">
                        <td class="px-4 py-3 text-slate-200">${escaparHtml(p.docente_nombre || '')}</td>
                        <td class="px-4 py-3">${escaparHtml(p.unidad || '')}</td>
                        <td class="px-4 py-3 text-xs">${escaparHtml(p.nombre_original || '')}</td>
                    </tr>
                `).join('') : '<tr><td colspan="3" class="px-4 py-8 text-center text-slate-500">No hay plantillas cargadas.</td></tr>';
            }
        })
        .catch(error => mostrarMensaje('cuentas-message', error.message || 'No se pudieron cargar plantillas.', 'error'));

    const periodo = document.getElementById('cuenta-mes')?.value || '';
    fetch(`${backendUrl}/api/cuentas-cobro?periodo=${encodeURIComponent(periodo)}`)
        .then(manejarRespuestaJson)
        .then(data => {
            const generadas = data.generadas || [];
            if (generadasBody) {
                generadasBody.innerHTML = generadas.length ? generadas.map(g => `
                    <tr class="hover:bg-slate-900/50">
                        <td class="px-4 py-3 text-slate-200">${escaparHtml(g.docente_nombre || '')}</td>
                        <td class="px-4 py-3">${escaparHtml(g.periodo || '')}</td>
                        <td class="px-4 py-3">${escaparHtml(g.numero_cuenta || '')}</td>
                        <td class="px-4 py-3"><button onclick="descargarArchivoGenerado('${escaparHtml(g.nombre_archivo || '')}')" class="text-cyan-300 hover:text-cyan-200 text-xs">Descargar</button></td>
                    </tr>
                `).join('') : '<tr><td colspan="4" class="px-4 py-8 text-center text-slate-500">No hay cuentas generadas para el periodo.</td></tr>';
            }
        })
        .catch(error => mostrarMensaje('cuentas-message', error.message || 'No se pudieron cargar cuentas generadas.', 'error'));
}

function subirPlantillasCuentaCobro() {
    const input = document.getElementById('cuenta-template-file');
    const file = input?.files?.[0];
    if (!file) {
        mostrarMensaje('cuentas-message', 'Selecciona un DOCX o ZIP con cuentas de cobro.', 'error');
        return;
    }
    const nombre = file.name.toLowerCase();
    if (!nombre.endsWith('.docx') && !nombre.endsWith('.zip')) {
        mostrarMensaje('cuentas-message', 'Solo se aceptan .docx o .zip para cuentas de cobro.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    mostrarCargando('Subiendo plantillas de cuenta de cobro...');
    fetch(`${backendUrl}/api/cuentas-cobro/plantillas`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then(data => {
            ocultarCargando();
            mostrarMensaje('cuentas-message', data.message || 'Plantillas cargadas.', 'success');
            input.value = '';
            cargarCuentasCobro();
        })
        .catch(error => {
            ocultarCargando();
            mostrarMensaje('cuentas-message', error.message || 'No se pudieron subir las plantillas.', 'error');
        });
}

function generarCuentasCobro() {
    const periodo = document.getElementById('cuenta-mes')?.value || periodoMesActual();
    const [anio, mes] = periodo.split('-');
    const payload = {
        anio: Number(anio),
        mes: Number(mes),
        ciudad: document.getElementById('cuenta-ciudad')?.value || 'Ciudad de prueba',
        numero_inicial: document.getElementById('cuenta-numero-inicial')?.value || ''
    };
    mostrarCargando('Generando cuentas de cobro del mes...');
    fetch(`${backendUrl}/api/cuentas-cobro/generar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(manejarRespuestaJson)
        .then(data => {
            ocultarCargando();
            mostrarMensaje('cuentas-message', data.message || 'Cuentas generadas.', 'success');
            cargarCuentasCobro();
        })
        .catch(error => {
            ocultarCargando();
            mostrarMensaje('cuentas-message', error.message || 'No se pudieron generar las cuentas.', 'error');
        });
}

function descargarArchivoGenerado(nombre) {
    if (!nombre) return;
    descargarArchivoAutenticado(`${backendUrl}/api/descargar-archivo/${encodeURIComponent(nombre)}`).catch(error => alert(error.message));
}

function inicializarRelacionMes() {
    const periodo = document.getElementById('relacion-periodo');
    if (periodo && !periodo.value) periodo.value = periodoMesActual();
}

function generarRelacionMes() {
    const periodo = document.getElementById('relacion-periodo')?.value || periodoMesActual();
    const [anio, mes] = periodo.split('-');
    mostrarCargando('Generando relación del mes...');
    fetch(`${backendUrl}/api/relacion-mes/generar?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}`)
        .then(manejarRespuestaJson)
        .then(data => {
            ocultarCargando();
            mostrarMensaje('relacion-message', data.message || 'Relación generada.', 'success');
            const cont = document.getElementById('relacion-descarga');
            if (cont && data.archivo) {
                cont.innerHTML = `<button onclick="descargarArchivoGenerado('${escaparHtml(data.archivo)}')" class="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium text-white">Descargar ${escaparHtml(data.archivo)}</button>`;
            }
        })
        .catch(error => {
            ocultarCargando();
            mostrarMensaje('relacion-message', error.message || 'No se pudo generar la relación del mes.', 'error');
        });
}


async function cargarAdministracion() {
    try {
        const [fundResp, userResp] = await Promise.all([
            fetch(`${backendUrl}/api/fundaciones`).then(manejarRespuestaJson),
            fetch(`${backendUrl}/api/usuarios`).then(manejarRespuestaJson)
        ]);
        renderFundaciones(fundResp.fundaciones || []);
        renderUsuarios(userResp.usuarios || [], fundResp.fundaciones || [], userResp.roles || []);
    } catch (error) {
        mostrarMensaje('admin-message', error.message || 'No se pudo cargar administración.', 'error');
    }
}

function renderFundaciones(fundaciones) {
    const tbody = document.getElementById('fundaciones-list');
    const select = document.getElementById('usuario-fundacion');
    if (select) {
        select.innerHTML = fundaciones.map(f => `<option value="${f.id}">${escaparHtml(f.nombre)}</option>`).join('');
    }
    if (!tbody) return;
    tbody.innerHTML = fundaciones.length ? fundaciones.map(f => `
        <tr class="border-b border-slate-800">
            <td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(f.nombre)}</td>
            <td class="px-3 py-2">${escaparHtml(f.nit || '')}</td>
            <td class="px-3 py-2">${escaparHtml(f.plan || '')}</td>
            <td class="px-3 py-2">${escaparHtml(f.estado || '')}</td>
            <td class="px-3 py-2">${escaparHtml(f.fecha_vencimiento || '')}</td>
            <td class="px-3 py-2 space-x-2">
                <button onclick="cambiarEstadoFundacion(${f.id}, 'ACTIVA')" class="text-emerald-300 text-xs">Activar</button>
                <button onclick="cambiarEstadoFundacion(${f.id}, 'SUSPENDIDA')" class="text-rose-300 text-xs">Suspender</button>
            </td>
        </tr>`).join('') : '<tr><td colspan="6" class="px-3 py-6 text-center text-slate-500">Sin fundaciones.</td></tr>';
}

function renderUsuarios(usuarios, fundaciones, roles) {
    const tbody = document.getElementById('usuarios-list');
    const rolSelect = document.getElementById('usuario-rol');
    if (rolSelect) rolSelect.innerHTML = roles.map(r => `<option value="${r}">${r}</option>`).join('');
    if (!tbody) return;
    tbody.innerHTML = usuarios.length ? usuarios.map(u => `
        <tr class="border-b border-slate-800">
            <td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(u.username)}</td>
            <td class="px-3 py-2">${escaparHtml(u.email)}</td>
            <td class="px-3 py-2">${escaparHtml(u.rol)}</td>
            <td class="px-3 py-2">${escaparHtml(u.fundacion_nombre || '')}</td>
            <td class="px-3 py-2">${escaparHtml(u.estado || (u.activo ? 'ACTIVO' : 'INACTIVO'))}</td>
            <td class="px-3 py-2">
                <button onclick="desactivarUsuario(${u.id})" class="text-rose-300 text-xs">Desactivar</button>
            </td>
        </tr>`).join('') : '<tr><td colspan="6" class="px-3 py-6 text-center text-slate-500">Sin usuarios.</td></tr>';
}

async function crearFundacion() {
    const data = {
        nombre: document.getElementById('fundacion-nombre')?.value.trim(),
        nit: document.getElementById('fundacion-nit')?.value.trim(),
        representante: document.getElementById('fundacion-representante')?.value.trim(),
        email: document.getElementById('fundacion-email')?.value.trim(),
        telefono: document.getElementById('fundacion-telefono')?.value.trim(),
        plan: document.getElementById('fundacion-plan')?.value,
        fecha_vencimiento: document.getElementById('fundacion-vencimiento')?.value,
        estado: 'ACTIVA'
    };
    try {
        const resp = await fetch(`${backendUrl}/api/fundaciones`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const json = await manejarRespuestaJson(resp);
        mostrarMensaje('admin-message', json.message || 'Fundación creada.', 'success');
        cargarAdministracion();
    } catch (error) {
        mostrarMensaje('admin-message', error.message || 'No se pudo crear fundación.', 'error');
    }
}

async function cambiarEstadoFundacion(id, estado) {
    try {
        const resp = await fetch(`${backendUrl}/api/fundaciones/${id}?estado=${encodeURIComponent(estado)}`, { method: 'DELETE' });
        const json = await manejarRespuestaJson(resp);
        mostrarMensaje('admin-message', json.message || 'Estado actualizado.', 'success');
        cargarAdministracion();
    } catch (error) { mostrarMensaje('admin-message', error.message || 'No se pudo cambiar estado.', 'error'); }
}

async function crearUsuario() {
    const data = {
        username: document.getElementById('usuario-username')?.value.trim(),
        email: document.getElementById('usuario-email')?.value.trim(),
        password: document.getElementById('usuario-password')?.value,
        rol: document.getElementById('usuario-rol')?.value,
        fundacion_id: Number(document.getElementById('usuario-fundacion')?.value || 0),
        nombre_completo: document.getElementById('usuario-nombre')?.value.trim(),
        telefono: document.getElementById('usuario-telefono')?.value.trim()
    };
    try {
        const resp = await fetch(`${backendUrl}/api/usuarios`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        const json = await manejarRespuestaJson(resp);
        mostrarMensaje('admin-message', json.message || 'Usuario creado.', 'success');
        cargarAdministracion();
    } catch (error) {
        mostrarMensaje('admin-message', error.message || 'No se pudo crear usuario.', 'error');
    }
}

async function desactivarUsuario(id) {
    try {
        const resp = await fetch(`${backendUrl}/api/usuarios/${id}`, { method: 'DELETE' });
        const json = await manejarRespuestaJson(resp);
        mostrarMensaje('admin-message', json.message || 'Usuario desactivado.', 'success');
        cargarAdministracion();
    } catch (error) { mostrarMensaje('admin-message', error.message || 'No se pudo desactivar usuario.', 'error'); }
}

window.addEventListener('DOMContentLoaded', initApp);
