
let plantillasOficialesCache = [];

function poMostrarMensaje(texto, tipo = 'success') {
    const box = document.getElementById('po-message');
    if (!box) return;
    box.className = `mt-4 rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.textContent = texto;
    box.classList.remove('hidden');
}

async function plantillasOficialesInit() {
    await poCargar();
}

async function poCargar() {
    const tbody = document.getElementById('po-list');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center text-slate-500">Cargando...</td></tr>';
    try {
        const resp = await fetch(`${backendUrl}/api/plantillas-oficiales`);
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'No se pudieron cargar las plantillas oficiales.');
        plantillasOficialesCache = data.plantillas || [];
        poRender();
    } catch (error) {
        if (tbody) tbody.innerHTML = `<tr><td colspan="7" class="px-4 py-6 text-center text-rose-300">${escaparHtml(error.message)}</td></tr>`;
    }
}

function poRender() {
    const tbody = document.getElementById('po-list');
    if (!tbody) return;
    if (!plantillasOficialesCache.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center text-slate-500">No hay plantillas oficiales registradas.</td></tr>';
        return;
    }
    tbody.innerHTML = plantillasOficialesCache.map((p) => `
        <tr>
            <td>${escaparHtml(p.nombre || p.codigo || '')}</td>
            <td>${escaparHtml(p.archivo || '')}</td>
            <td>${escaparHtml(p.hoja || '')}</td>
            <td>${escaparHtml(p.version || '')}</td>
            <td>${p.existe ? '<span class="text-emerald-300">Activa</span>' : '<span class="text-rose-300">Falta archivo</span>'}</td>
            <td>${escaparHtml(p.fecha_actualizacion || 'Sin fecha')}</td>
            <td>${p.preservar_estilos ? 'Solo valores · preserva impresión' : 'Revisar'}</td>
        </tr>
    `).join('');
    poRenderMapeoAsistencia(plantillasOficialesCache.find((item) => item.tipo_formato === 'listado_asistencia_usuarios'));
}

function poRenderMapeoAsistencia(plantilla) {
    const target = document.getElementById('po-asistencia-mapeo');
    if (!target) return;
    const mapping = plantilla?.mapeo;
    if (!mapping) {
        target.textContent = 'Carga la planilla para detectar y mostrar el mapeo de columnas.';
        return;
    }
    const fields = Object.entries(mapping.campos || {}).map(([field, col]) => `${escaparHtml(field)} → columna ${Number(col)}`).join(' · ');
    target.innerHTML = `<strong class="text-emerald-300">Mapeo detectado:</strong> hoja ${escaparHtml(mapping.hoja || '')}, encabezados en fila ${Number(mapping.fila_encabezado || 0)}.<br>${fields}`;
}

async function poSubir(tipo) {
    const inputs = { rpp: 'po-rpp-file', bienestarina: 'po-bienestarina-file', listado_usuarios: 'po-listado-usuarios-file', listado_asistencia_usuarios: 'po-listado-asistencia-file' };
    const input = document.getElementById(inputs[tipo]);
    const file = input?.files?.[0];
    if (!file) {
        poMostrarMensaje('Selecciona primero la plantilla oficial.', 'error');
        return;
    }
    const extensiones = tipo === 'listado_usuarios' ? ['.docx'] : ['.xlsx', '.xlsm'];
    const error = validarArchivo(file, extensiones, 50);
    if (error) {
        poMostrarMensaje(error, 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    try {
        const resp = await fetch(`${backendUrl}/api/plantillas-oficiales/${tipo}`, { method: 'POST', body: form });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'No se pudo actualizar la plantilla.');
        poMostrarMensaje(data.message || 'Plantilla oficial actualizada.');
        if (tipo === 'listado_asistencia_usuarios') poRenderMapeoAsistencia(data.plantilla);
        input.value = '';
        await poCargar();
    } catch (error) {
        poMostrarMensaje(error.message, 'error');
    }
}

function poDescargar(tipo) {
    window.descargarArchivoAutenticado(`${backendUrl}/api/plantillas-oficiales/${tipo}/descargar`).catch((error) => poMostrarMensaje(error.message, 'error'));
}

async function poRestaurar(tipo) {
    if (!confirm('¿Restaurar la copia anterior de esta plantilla oficial?')) return;
    try {
        const resp = await fetch(`${backendUrl}/api/plantillas-oficiales/${tipo}/restaurar`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'No se pudo restaurar la plantilla.');
        poMostrarMensaje(data.message || 'Plantilla oficial restaurada.');
        await poCargar();
    } catch (error) {
        poMostrarMensaje(error.message, 'error');
    }
}
