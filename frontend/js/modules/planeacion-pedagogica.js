let ppEstado = {
    periodo: new Date().toISOString().slice(0, 7),
    planeaciones: [],
    plantillas: [],
    documentos: [],
    evidencias: [],
    proyectos: [],
    catalogos: { coordinadores: [], docentes: [], tipos_documento: [], tipos_actividad: [] },
    planeacionActual: null
};

function ppApi(path, options = {}) {
    return fetch(`${backendUrl}/api/planeacion-pedagogica${path}`, options).then(manejarRespuestaJson);
}

function ppHtml(valor) {
    return escaparHtml(valor ?? '');
}

function ppEstadoBadge(estado) {
    const e = String(estado || '').toUpperCase();
    const clases = {
        BORRADOR: 'border-slate-500/30 bg-slate-500/10 text-slate-300',
        CARGADA: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
        VALIDADA: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
        APROBADA: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
        RECHAZADA: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
        ANULADA: 'border-zinc-500/30 bg-zinc-500/10 text-zinc-300'
    };
    return `<span class="pp-badge ${clases[e] || clases.BORRADOR}">${ppHtml(e || 'SIN ESTADO')}</span>`;
}

function ppMostrarVista(vista) {
    document.querySelectorAll('.pp-view').forEach(el => el.classList.toggle('hidden', el.id !== `pp-view-${vista}`));
    document.querySelectorAll('.pp-tab').forEach(el => el.classList.toggle('activa', el.dataset.view === vista));
    if (vista === 'dashboard') ppCargarDashboard();
    if (vista === 'proyectos') ppCargarProyectos();
    if (vista === 'cargar') ppCargarCatalogos();
    if (vista === 'planeaciones') ppCargarPlaneaciones();
    if (vista === 'plantillas') ppCargarPlantillas();
    if (vista === 'documentos') ppCargarDocumentos();
    if (vista === 'evidencias') ppCargarEvidencias();
    if (vista === 'reportes') ppCargarReporte();
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

async function ppInit() {
    const periodoInput = document.getElementById('pp-periodo-global');
    if (periodoInput && !periodoInput.value) periodoInput.value = ppEstado.periodo;
    await ppCargarCatalogos();
    ppMostrarVista('dashboard');
}

async function ppCargarCatalogos() {
    try {
        const data = await ppApi('/catalogos');
        ppEstado.catalogos = data;
        ppPoblarSelects();
    } catch (error) {
        console.error('No se pudieron cargar catálogos de planeación', error);
    }
}

function ppPoblarSelects() {
    const coords = ppEstado.catalogos.coordinadores || [];
    const docentes = ppEstado.catalogos.docentes || [];
    const tiposDoc = ppEstado.catalogos.tipos_documento || [];
    const tiposAct = ppEstado.catalogos.tipos_actividad || [];
    const coordOptions = '<option value="">Sin coordinador</option>' + coords.map(c => `<option value="${c.id}">${ppHtml(c.nombre)}</option>`).join('');
    const docenteOptions = '<option value="">Sin agente educativo</option>' + docentes.map(d => `<option value="${d.id}">${ppHtml(d.nombre)}${d.unidad ? ' · ' + ppHtml(d.unidad) : ''}</option>`).join('');
    ['pp-coordinador', 'pp-manual-coordinador', 'pp-evidencia-coordinador'].forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = coordOptions; });
    ['pp-docente', 'pp-manual-docente'].forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = docenteOptions; });
    const proyectoCoord = document.getElementById('pp-proyecto-coordinador');
    if (proyectoCoord) proyectoCoord.innerHTML = coordOptions;
    const proyectoDocente = document.getElementById('pp-proyecto-docente');
    if (proyectoDocente) proyectoDocente.innerHTML = docenteOptions;
    const tipoDocSelect = document.getElementById('pp-plantilla-tipo');
    if (tipoDocSelect) tipoDocSelect.innerHTML = tiposDoc.map(t => `<option>${ppHtml(t)}</option>`).join('');
    const tipoActSelect = document.getElementById('pp-manual-tipo');
    if (tipoActSelect) tipoActSelect.innerHTML = tiposAct.map(t => `<option>${ppHtml(t.nombre)}</option>`).join('');
}

async function ppCrearProyecto() {
    const message = document.getElementById('pp-proyecto-message');
    const data = {
        unidad: document.getElementById('pp-proyecto-unidad')?.value.trim() || '',
        vigencia: Number(document.getElementById('pp-proyecto-vigencia')?.value || new Date().getFullYear()),
        nombre: document.getElementById('pp-proyecto-nombre')?.value.trim() || '',
        docente_id: document.getElementById('pp-proyecto-docente')?.value || null,
        coordinador_id: document.getElementById('pp-proyecto-coordinador')?.value || null,
        diagnostico_contexto: document.getElementById('pp-proyecto-diagnostico')?.value || '',
        objetivos: document.getElementById('pp-proyecto-objetivos')?.value || '',
        estrategias: document.getElementById('pp-proyecto-estrategias')?.value || '',
        participacion_familias: document.getElementById('pp-proyecto-familias')?.value || '',
        enfoque_diferencial: document.getElementById('pp-proyecto-diferencial')?.value || ''
    };
    if (!data.unidad || !data.nombre) {
        if (message) message.textContent = 'UCA y nombre son obligatorios.';
        return;
    }
    try {
        const response = await ppApi('/proyectos-pedagogicos', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
        });
        if (message) message.textContent = response.message || 'Proyecto creado.';
        await ppCargarProyectos();
    } catch (error) {
        if (message) message.textContent = error.message || 'No se pudo crear el proyecto.';
    }
}

async function ppCargarProyectos() {
    const list = document.getElementById('pp-proyectos-list');
    const vigencia = Number(document.getElementById('pp-proyecto-vigencia')?.value || new Date().getFullYear());
    const vigenciaInput = document.getElementById('pp-proyecto-vigencia');
    if (vigenciaInput && !vigenciaInput.value) vigenciaInput.value = String(vigencia);
    try {
        const response = await ppApi(`/proyectos-pedagogicos?vigencia=${encodeURIComponent(vigencia)}`);
        ppEstado.proyectos = response.proyectos || [];
        if (!list) return;
        list.innerHTML = ppEstado.proyectos.length ? ppEstado.proyectos.map(project => `
            <article class="border-b border-slate-800 p-4 space-y-2">
                <div class="flex justify-between gap-3"><div><p class="font-semibold text-slate-100">${ppHtml(project.nombre)}</p><p class="text-xs text-slate-400">${ppHtml(project.unidad)} · ${project.vigencia} · versión ${project.version_actual || 0}</p></div>${ppEstadoBadge(project.estado)}</div>
                <div class="flex flex-wrap gap-2"><button onclick="ppActualizarProyecto(${project.id})" class="rounded-lg bg-indigo-600 px-3 py-1 text-xs text-white">Actualizar desde ejecución</button><button onclick="ppValidarProyectoDocente(${project.id})" class="rounded-lg bg-emerald-600 px-3 py-1 text-xs text-white">Validación docente</button></div>
            </article>`).join('') : '<div class="p-4 text-sm text-slate-500">No hay proyectos pedagógicos para esta vigencia.</div>';
    } catch (error) {
        if (list) list.innerHTML = `<div class="p-4 text-sm text-rose-300">${ppHtml(error.message)}</div>`;
    }
}

async function ppActualizarProyecto(id) {
    const resumen = prompt('Resumen de la actualización:', 'Actualización desde actividades ejecutadas') || '';
    try {
        const response = await ppApi(`/proyectos-pedagogicos/${id}/actualizar-desde-ejecucion`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({resumen_cambios: resumen})});
        alert(response.message || 'Borrador actualizado.');
        await ppCargarProyectos();
    } catch (error) { alert(error.message || 'No se pudo actualizar.'); }
}

async function ppValidarProyectoDocente(id) {
    const observacion = prompt('Observación de validación docente:', '') || '';
    try {
        const response = await ppApi(`/proyectos-pedagogicos/${id}/validar-docente`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({observacion})});
        alert(response.message || 'Proyecto validado.');
        await ppCargarProyectos();
    } catch (error) { alert(error.message || 'La validación requiere la docente asignada.'); }
}

async function ppCargarDashboard() {
    const periodo = document.getElementById('pp-periodo-global')?.value || ppEstado.periodo;
    ppEstado.periodo = periodo;
    try {
        const data = await ppApi(`/dashboard?periodo=${encodeURIComponent(periodo)}`);
        const cards = document.getElementById('pp-dashboard-cards');
        if (cards) {
            const estados = data.estados || {};
            const actividades = data.actividades || {};
            cards.innerHTML = `
                <div class="pp-card"><p class="text-xs text-slate-400">Planeaciones</p><h3 class="mt-2 text-3xl font-bold text-fuchsia-300">${data.planeaciones_total || 0}</h3></div>
                <div class="pp-card"><p class="text-xs text-slate-400">Aprobadas</p><h3 class="mt-2 text-3xl font-bold text-emerald-300">${estados.APROBADA || 0}</h3></div>
                <div class="pp-card"><p class="text-xs text-slate-400">Pendientes / cargadas</p><h3 class="mt-2 text-3xl font-bold text-amber-300">${(estados.CARGADA || 0) + (estados.VALIDADA || 0) + (estados.BORRADOR || 0)}</h3></div>
                <div class="pp-card"><p class="text-xs text-slate-400">Actividades pendientes</p><h3 class="mt-2 text-3xl font-bold text-sky-300">${actividades.PENDIENTE || 0}</h3></div>
            `;
        }
        const resumen = document.getElementById('pp-dashboard-resumen');
        if (resumen) resumen.textContent = `Periodo ${data.periodo}. Documentos generados: ${Object.values(data.documentos_generados || {}).reduce((a,b)=>a+Number(b||0),0)}.`;
    } catch (error) {
        const resumen = document.getElementById('pp-dashboard-resumen');
        if (resumen) resumen.textContent = error.message || 'No se pudo cargar dashboard.';
    }
}

async function ppSubirPlaneacion() {
    const file = document.getElementById('pp-file')?.files?.[0];
    const msg = document.getElementById('pp-message');
    if (!file) { if (msg) msg.textContent = 'Selecciona un archivo de planeación.'; return; }
    const fd = new FormData();
    fd.append('file', file);
    ['pp-periodo-global','pp-coordinador','pp-docente','pp-unidad','pp-tema','pp-objetivo','pp-fecha','pp-tipo','pp-observaciones'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const key = {
            'pp-periodo-global':'periodo', 'pp-coordinador':'coordinador_id', 'pp-docente':'docente_id', 'pp-unidad':'unidad',
            'pp-tema':'tema', 'pp-objetivo':'objetivo', 'pp-fecha':'fecha_programada', 'pp-tipo':'tipo_encuentro', 'pp-observaciones':'observaciones'
        }[id];
        fd.append(key, el.value || '');
    });
    if (msg) msg.textContent = 'Cargando planeación y creando actividades...';
    try {
        const data = await ppApi('/planeaciones', { method: 'POST', body: fd });
        if (msg) msg.textContent = data.message || 'Planeación cargada.';
        document.getElementById('pp-file').value = '';
        ppEstado.planeacionActual = data.planeacion;
        await ppCargarPlaneaciones();
    } catch (error) {
        if (msg) msg.textContent = error.message || 'Error al cargar planeación.';
    }
}

async function ppCrearPlaneacionManual() {
    const payload = {
        periodo: document.getElementById('pp-periodo-global')?.value || ppEstado.periodo,
        coordinador_id: document.getElementById('pp-manual-coordinador')?.value || null,
        docente_id: document.getElementById('pp-manual-docente')?.value || null,
        unidad: document.getElementById('pp-manual-unidad')?.value || '',
        tema: document.getElementById('pp-manual-tema')?.value || '',
        objetivo: document.getElementById('pp-manual-objetivo')?.value || '',
        actividad: document.getElementById('pp-manual-actividad')?.value || '',
        fecha_programada: document.getElementById('pp-manual-fecha')?.value || '',
        tipo_encuentro: document.getElementById('pp-manual-tipo')?.value || 'Actividad pedagógica',
        evidencia_requerida: document.getElementById('pp-manual-evidencia')?.value || '',
        observaciones: document.getElementById('pp-manual-observaciones')?.value || ''
    };
    const msg = document.getElementById('pp-manual-message');
    if (!payload.tema) { if (msg) msg.textContent = 'El tema es obligatorio.'; return; }
    try {
        const data = await ppApi('/planeaciones/manual', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (msg) msg.textContent = data.message || 'Planeación creada.';
        await ppCargarPlaneaciones();
    } catch (error) {
        if (msg) msg.textContent = error.message || 'No se pudo crear planeación.';
    }
}

async function ppCargarPlaneaciones() {
    const periodo = document.getElementById('pp-periodo-global')?.value || ppEstado.periodo;
    try {
        const data = await ppApi(`/planeaciones?periodo=${encodeURIComponent(periodo)}`);
        ppEstado.planeaciones = data.planeaciones || [];
        const cont = document.getElementById('pp-planeaciones-list');
        if (!cont) return;
        if (ppEstado.planeaciones.length === 0) {
            cont.innerHTML = '<div class="p-4 text-sm text-slate-500">No hay planeaciones cargadas para el periodo.</div>';
            return;
        }
        cont.innerHTML = ppEstado.planeaciones.map(p => `
            <div class="border-b border-slate-800 p-4 hover:bg-slate-900/50">
                <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div><p class="font-semibold text-slate-200">${ppHtml(p.tema)}</p><p class="text-xs text-slate-400">${ppHtml(p.periodo)} · ${ppHtml(p.coordinador_nombre || 'Sin coordinador')} · ${ppHtml(p.docente_nombre || 'Sin agente educativo')} · ${ppHtml(p.unidad || '')}</p></div>
                    <div class="flex flex-wrap gap-2">${ppEstadoBadge(p.estado)}<button onclick="ppVerPlaneacion(${p.id})" class="rounded-lg border border-fuchsia-500/30 px-3 py-1 text-xs text-fuchsia-200">Ver</button><button onclick="ppGenerarDocumentos(${p.id})" class="rounded-lg bg-fuchsia-600 px-3 py-1 text-xs text-white">Generar documentos</button></div>
                </div>
            </div>
        `).join('');
    } catch (error) {
        const cont = document.getElementById('pp-planeaciones-list');
        if (cont) cont.innerHTML = `<div class="p-4 text-sm text-rose-300">${ppHtml(error.message)}</div>`;
    }
}

function ppDescargarDocumento(id) {
    window.descargarArchivoAutenticado(`${backendUrl}/api/planeacion-pedagogica/documentos-generados/${encodeURIComponent(id)}/download`)
        .catch((error) => alert(error.message || 'No se pudo descargar el documento.'));
}

async function ppVerPlaneacion(id) {
    try {
        const data = await ppApi(`/planeaciones/${id}`);
        ppEstado.planeacionActual = data.planeacion;
        const p = data.planeacion;
        const cont = document.getElementById('pp-planeacion-detalle');
        if (!cont) return;
        cont.classList.remove('hidden');
        cont.innerHTML = `
            <div class="pp-panel">
                <div class="p-4 border-b border-slate-800 flex flex-col lg:flex-row lg:justify-between gap-3">
                    <div><h3 class="font-semibold text-slate-100">${ppHtml(p.tema)}</h3><p class="text-xs text-slate-400">${ppHtml(p.periodo)} · ${ppHtml(p.tipo_encuentro)} · ${ppHtml(p.fecha_programada)}</p></div>
                    <div class="flex flex-wrap gap-2">${ppEstadoBadge(p.estado)}<button onclick="ppCambiarEstado(${p.id}, 'aprobar')" class="rounded-lg bg-emerald-600 px-3 py-1 text-xs text-white">Aprobar</button><button onclick="ppCambiarEstado(${p.id}, 'rechazar')" class="rounded-lg bg-rose-600 px-3 py-1 text-xs text-white">Rechazar</button><button onclick="ppCambiarEstado(${p.id}, 'corregir')" class="rounded-lg bg-amber-600 px-3 py-1 text-xs text-white">Corregir</button><button onclick="ppAnularPlaneacion(${p.id})" class="rounded-lg border border-slate-600 px-3 py-1 text-xs text-slate-300">Anular</button></div>
                </div>
                <div class="grid gap-4 lg:grid-cols-2 p-4 text-sm text-slate-300"><div><strong>Objetivo:</strong><br>${ppHtml(p.objetivo)}</div><div><strong>Actividad:</strong><br>${ppHtml(p.actividad)}</div><div><strong>Población:</strong><br>${ppHtml(p.poblacion_objetivo)}</div><div><strong>Evidencia:</strong><br>${ppHtml(p.evidencia_requerida)}</div></div>
                <div class="p-4 border-t border-slate-800"><h4 class="font-medium text-slate-200 mb-2">Actividades creadas en calendario</h4>${(p.actividades || []).map(a => `<div class="rounded-xl border border-slate-800 p-3 mb-2"><p class="text-slate-200">${ppHtml(a.titulo || a.tipo_actividad)}</p><p class="text-xs text-slate-400">${ppHtml(a.fecha_programada)} · ${ppHtml(a.estado)} · ${ppHtml(a.evidencia_requerida)}</p></div>`).join('') || '<p class="text-slate-500">Sin actividades.</p>'}</div>
                <div class="p-4 border-t border-slate-800"><h4 class="font-medium text-slate-200 mb-2">Documentos generados</h4>${(p.documentos_generados || []).map(d => `<button type="button" class="inline-flex mr-2 mb-2 rounded-lg border border-indigo-500/30 px-3 py-1 text-xs text-indigo-300" onclick="ppDescargarDocumento(${Number(d.id)})">${ppHtml(d.tipo_documento)} (${ppHtml(d.formato)})</button>`).join('') || '<p class="text-slate-500">Sin documentos generados.</p>'}</div>
            </div>`;
    } catch (error) { alert(error.message || 'No se pudo abrir detalle.'); }
}

async function ppCambiarEstado(id, accion) {
    const observacion = prompt('Observación:', '') || '';
    try {
        const data = await ppApi(`/planeaciones/${id}/${accion}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ observacion }) });
        await ppVerPlaneacion(id); await ppCargarPlaneaciones();
        alert(data.message || 'Estado actualizado.');
    } catch (error) { alert(error.message || 'No se pudo cambiar estado.'); }
}

async function ppAnularPlaneacion(id) {
    if (!confirm('¿Anular esta planeación?')) return;
    try { await ppApi(`/planeaciones/${id}`, { method: 'DELETE' }); await ppCargarPlaneaciones(); document.getElementById('pp-planeacion-detalle')?.classList.add('hidden'); } catch (error) { alert(error.message); }
}

async function ppGenerarDocumentos(id) {
    try {
        const tipos = Array.from(document.querySelectorAll('.pp-doc-check:checked')).map(ch => ch.value);
        const data = await ppApi(`/planeaciones/${id}/generar-documentos`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ tipos: tipos.length ? tipos : undefined }) });
        alert(data.message || 'Documentos generados.');
        await ppVerPlaneacion(id);
        await ppCargarDocumentos();
    } catch (error) { alert(error.message || 'No se pudieron generar documentos.'); }
}

async function ppSubirPlantilla() {
    const file = document.getElementById('pp-plantilla-file')?.files?.[0];
    const msg = document.getElementById('pp-plantilla-message');
    if (!file) { if (msg) msg.textContent = 'Selecciona una plantilla.'; return; }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('nombre', document.getElementById('pp-plantilla-nombre')?.value || file.name);
    fd.append('tipo_documento', document.getElementById('pp-plantilla-tipo')?.value || 'Informe pedagógico mensual');
    fd.append('version', document.getElementById('pp-plantilla-version')?.value || '1.0');
    try {
        const data = await ppApi('/plantillas', { method: 'POST', body: fd });
        if (msg) msg.textContent = data.message || 'Plantilla subida.';
        document.getElementById('pp-plantilla-file').value = '';
        ppCargarPlantillas();
    } catch (error) { if (msg) msg.textContent = error.message || 'Error al subir plantilla.'; }
}

async function ppCargarPlantillas() {
    try {
        const data = await ppApi('/plantillas');
        ppEstado.plantillas = data.plantillas || [];
        const cont = document.getElementById('pp-plantillas-list');
        if (!cont) return;
        cont.innerHTML = ppEstado.plantillas.length ? ppEstado.plantillas.map(t => `<div class="border-b border-slate-800 p-3"><p class="font-medium text-slate-200">${ppHtml(t.nombre)}</p><p class="text-xs text-slate-400">${ppHtml(t.tipo_documento)} · v${ppHtml(t.version)} · ${ppHtml(t.estado)}</p></div>`).join('') : '<div class="p-4 text-sm text-slate-500">No hay plantillas registradas.</div>';
    } catch (error) { console.error(error); }
}

async function ppCargarDocumentos() {
    try {
        const data = await ppApi('/documentos-generados');
        ppEstado.documentos = data.documentos || [];
        const cont = document.getElementById('pp-documentos-list');
        if (!cont) return;
        cont.innerHTML = ppEstado.documentos.length ? ppEstado.documentos.map(d => `<div class="border-b border-slate-800 p-3 flex justify-between gap-2"><div><p class="font-medium text-slate-200">${ppHtml(d.tipo_documento)}</p><p class="text-xs text-slate-400">${ppHtml(d.nombre)} · ${ppHtml(d.fecha_generacion)}</p></div><button type="button" class="rounded-lg border border-indigo-500/30 px-3 py-1 text-xs text-indigo-300" onclick="ppDescargarDocumento(${Number(d.id)})">Descargar</button></div>`).join('') : '<div class="p-4 text-sm text-slate-500">No hay documentos generados.</div>';
    } catch (error) { console.error(error); }
}

async function ppSubirEvidencia() {
    const file = document.getElementById('pp-evidencia-file')?.files?.[0];
    const msg = document.getElementById('pp-evidencia-message');
    if (!file) { if (msg) msg.textContent = 'Selecciona una evidencia.'; return; }
    const fd = new FormData();
    fd.append('file', file);
    fd.append('planeacion_id', document.getElementById('pp-evidencia-planeacion')?.value || '');
    fd.append('titulo', document.getElementById('pp-evidencia-titulo')?.value || file.name);
    fd.append('descripcion', document.getElementById('pp-evidencia-descripcion')?.value || '');
    try {
        const data = await ppApi('/evidencias/upload', { method: 'POST', body: fd });
        if (msg) msg.textContent = data.message || 'Evidencia cargada.';
        document.getElementById('pp-evidencia-file').value = '';
        ppCargarEvidencias();
    } catch (error) { if (msg) msg.textContent = error.message || 'Error al cargar evidencia.'; }
}

async function ppCargarEvidencias() {
    try {
        const data = await ppApi('/evidencias');
        ppEstado.evidencias = data.evidencias || [];
        const select = document.getElementById('pp-evidencia-planeacion');
        if (select) select.innerHTML = '<option value="">Sin planeación</option>' + (ppEstado.planeaciones || []).map(p => `<option value="${p.id}">${ppHtml(p.tema)}</option>`).join('');
        const cont = document.getElementById('pp-evidencias-list');
        if (cont) cont.innerHTML = ppEstado.evidencias.length ? ppEstado.evidencias.map(e => `<div class="border-b border-slate-800 p-3"><p class="font-medium text-slate-200">${ppHtml(e.titulo)}</p><p class="text-xs text-slate-400">${ppHtml(e.nombre_original)} · ${ppHtml(e.fecha_creacion)}</p></div>`).join('') : '<div class="p-4 text-sm text-slate-500">No hay evidencias.</div>';
    } catch (error) { console.error(error); }
}

async function ppCargarReporte() {
    const periodo = document.getElementById('pp-periodo-global')?.value || ppEstado.periodo;
    try {
        const data = await ppApi(`/reportes/mensual?periodo=${encodeURIComponent(periodo)}`);
        const cont = document.getElementById('pp-reporte-contenido');
        if (!cont) return;
        cont.innerHTML = `<div class="grid gap-3 md:grid-cols-3"><div class="pp-card"><p class="text-xs text-slate-400">Planeaciones</p><h3 class="text-2xl font-bold text-fuchsia-300">${data.total_planeaciones || 0}</h3></div><div class="pp-card"><p class="text-xs text-slate-400">Estados</p><p class="text-sm text-slate-300">${Object.entries(data.estado_planeaciones || {}).map(([k,v]) => `${ppHtml(k)}: ${v}`).join(' · ') || 'Sin datos'}</p></div><div class="pp-card"><p class="text-xs text-slate-400">Documentos</p><p class="text-sm text-slate-300">${(data.documentos_generados || []).map(d => `${ppHtml(d.tipo_documento)}: ${d.total}`).join(' · ') || 'Sin documentos'}</p></div></div>`;
    } catch (error) { console.error(error); }
}
