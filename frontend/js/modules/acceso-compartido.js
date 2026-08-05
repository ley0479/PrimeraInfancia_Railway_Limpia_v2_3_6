// Configuración de Acceso Compartido — Railway-first.
// Conserva diagnóstico local en desarrollo y evita mostrar localhost en producción.

let accesoEstado = { cargado: false, config: null };

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

function accesoToggle(id, visible) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('hidden', !visible);
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
        const esProduccion = Boolean(data.esProduccion);
        const urlPublica = data.urlPrincipalCompartir || data.publicAppUrl || data.urlTunelPublico || '';

        accesoSetValue('acceso-modo', data.modo || '-');
        accesoSetValue('acceso-ip', esProduccion ? 'No aplica' : (data.ipLocal || '-'));
        accesoSetValue('acceso-backend-estado', 'Online');
        accesoSetValue('acceso-login-estado', data.login?.estado || 'Autenticado');
        accesoSetValue('acceso-url-tunel-publico', urlPublica);
        accesoSetValue('acceso-url-local', data.frontendUrlLocal || '');
        accesoSetValue('acceso-url-red', data.urlCompartirWifi || data.frontendUrlRedLocal || '');
        accesoSetValue('acceso-backend-local', data.backendUrlLocal || '');
        accesoSetValue('acceso-backend-red', data.backendUrlRedLocal || '');
        accesoSetValue('acceso-backend-actual', data.backendUrlPublico || backendUrl);

        accesoToggle('acceso-local-diagnostics', !esProduccion);
        accesoToggle('acceso-backend-override-panel', !esProduccion);
        accesoToggle('acceso-public-note', true);

        const instrucciones = document.getElementById('acceso-instrucciones');
        if (instrucciones) {
            instrucciones.innerHTML = (data.instruccionesRapidas || []).map(item => `<li>${escaparHtml(item)}</li>`).join('');
        }
        accesoMensaje(
            esProduccion && urlPublica
                ? 'Dominio público de Railway detectado y listo para compartir.'
                : (data.tunnelActive && urlPublica
                    ? 'Túnel Cloudflare activo y verificado. Mantén abiertas las ventanas del backend y del túnel.'
                    : 'Configuración de acceso local actualizada.'),
            'success'
        );
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
        accesoMensaje('Backend y base de datos respondiendo correctamente.', 'success');
    } catch (error) {
        accesoSetValue('acceso-backend-estado', 'No responde');
        const esProduccion = Boolean(accesoEstado.config?.esProduccion);
        accesoMensaje(
            esProduccion
                ? 'El servicio no responde. Revisa Deployments y View logs en Railway.'
                : 'El backend no responde. Verifica el proceso local y el puerto configurado.',
            'error'
        );
    }
}

async function accesoProbarAlmacenamiento() {
    accesoSetValue('acceso-storage-estado', 'Comprobando...');
    try {
        const data = await fetch(`${backendUrl}/api/acceso/storage-health`).then(manejarRespuestaJson);
        const storage = data.storage || {};
        const rutasOk = Boolean(storage.databaseInsideDataDir && storage.allRequiredDirectoriesWritable);
        const volumenDetectado = Boolean(storage.persistentVolumeDeclared);
        const estado = volumenDetectado
            ? (rutasOk ? 'Detectado y escribible' : 'Detectado con observaciones')
            : (rutasOk ? 'Ruta /data escribible; persistencia por probar' : 'Configuración incompleta');
        accesoSetValue('acceso-storage-estado', estado);
        accesoMensaje(
            volumenDetectado && rutasOk
                ? 'Railway reporta el montaje y las carpetas requeridas son escribibles. Completa la prueba creando un registro ficticio y haciendo redeploy.'
                : (storage.nota || 'Revisa el volumen /data y completa una prueba de persistencia mediante redeploy.'),
            rutasOk ? 'success' : 'error'
        );
    } catch (error) {
        accesoSetValue('acceso-storage-estado', 'No disponible');
        accesoMensaje(error.message || 'No se pudo comprobar el almacenamiento.', 'error');
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
    if (accesoEstado.config?.esProduccion) {
        accesoMensaje('En Railway el backend se detecta automáticamente; no se admite override local.', 'error');
        return;
    }
    const input = document.getElementById('acceso-backend-override');
    const value = (input?.value || '').trim().replace(/\/$/, '');
    if (!value || !/^https?:\/\//i.test(value)) {
        accesoMensaje('Escribe una URL HTTP/HTTPS válida.', 'error');
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
