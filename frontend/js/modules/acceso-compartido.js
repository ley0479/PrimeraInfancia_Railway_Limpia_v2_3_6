// Módulo ligero: Configuración de Acceso Compartido
// No modifica módulos operativos. Solo consulta estado y muestra URLs para compartir.

let accesoEstado = {
    cargado: false,
    config: null
};

function accesoMensaje(texto, tipo = 'success') {
    const box = document.getElementById('acceso-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.textContent = texto;
    box.classList.remove('hidden');
}

function accesoSetValue(id, value) {
    const el = document.getElementById(id);
    if (!el) return;
    if ('value' in el) el.value = value || '';
    else el.textContent = value || '-';
}

function accesoCompartidoInit() {
    accesoSetValue('acceso-backend-actual', backendUrl);
    const override = localStorage.getItem('PRIMERA_INFANCIA_BACKEND_URL') || sessionStorage.getItem('PRIMERA_INFANCIA_BACKEND_URL') || '';
    accesoSetValue('acceso-backend-override', override);
    accesoCargarConfiguracion();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function accesoCargarConfiguracion() {
    try {
        const data = await fetch(`${backendUrl}/api/acceso/config`).then(manejarRespuestaJson);
        accesoEstado.config = data;
        accesoEstado.cargado = true;
        accesoSetValue('acceso-modo', data.modo || '-');
        accesoSetValue('acceso-ip', data.ipLocal || '-');
        accesoSetValue('acceso-backend-estado', 'Online');
        accesoSetValue('acceso-login-estado', data.login?.estado || 'Autenticado');
        accesoSetValue('acceso-url-local', data.frontendUrlLocal || '');
        accesoSetValue('acceso-url-red', data.urlCompartirWifi || data.frontendUrlRedLocal || '');
        accesoSetValue('acceso-url-tunel-publico', data.urlTunelPublico || '');
        accesoSetValue('acceso-backend-local', data.backendUrlLocal || '');
        accesoSetValue('acceso-backend-red', data.backendUrlRedLocal || '');
        accesoSetValue('acceso-backend-actual', backendUrl);

        const instrucciones = document.getElementById('acceso-instrucciones');
        if (instrucciones) {
            instrucciones.innerHTML = (data.instruccionesRapidas || []).map(item => `<li>${escaparHtml(item)}</li>`).join('');
        }
        accesoMensaje('Configuración de acceso actualizada.', 'success');
    } catch (error) {
        accesoSetValue('acceso-backend-estado', 'No responde');
        accesoMensaje(error.message || 'No se pudo cargar la configuración de acceso.', 'error');
    }
}

async function accesoProbarBackend() {
    try {
        const resp = await fetch(`${backendUrl}/api/health`);
        if (!resp.ok) throw new Error(`Backend respondió ${resp.status}`);
        accesoSetValue('acceso-backend-estado', 'Online');
        accesoMensaje('Backend respondiendo correctamente.', 'success');
    } catch (error) {
        accesoSetValue('acceso-backend-estado', 'No responde');
        accesoMensaje('Backend no responde. Verifica que app.py esté ejecutándose y que el firewall permita el puerto 5000.', 'error');
    }
}

function accesoCopiar(inputId) {
    const input = document.getElementById(inputId);
    if (!input || !input.value) {
        accesoMensaje('No hay URL para copiar.', 'error');
        return;
    }
    navigator.clipboard?.writeText(input.value).then(() => {
        accesoMensaje('URL copiada al portapapeles.', 'success');
    }).catch(() => {
        input.select();
        document.execCommand('copy');
        accesoMensaje('URL copiada.', 'success');
    });
}

function accesoGuardarBackendOverride() {
    const input = document.getElementById('acceso-backend-override');
    const value = (input?.value || '').trim().replace(/\/$/, '');
    if (!value || !/^https?:\/\//i.test(value)) {
        accesoMensaje('Escribe una URL válida. Ejemplo: http://192.168.1.35:5000', 'error');
        return;
    }
    localStorage.setItem('PRIMERA_INFANCIA_BACKEND_URL', value);
    accesoMensaje('URL guardada. Recarga la página con Ctrl + F5 para aplicar el cambio.', 'success');
}

function accesoLimpiarBackendOverride() {
    localStorage.removeItem('PRIMERA_INFANCIA_BACKEND_URL');
    sessionStorage.removeItem('PRIMERA_INFANCIA_BACKEND_URL');
    accesoSetValue('acceso-backend-override', '');
    accesoMensaje('Override eliminado. Recarga la página con Ctrl + F5 para usar detección automática.', 'success');
}
