// FASE 2: Gestión por Coordinador y Calendario Inteligente
// Módulo aislado. No modifica la lógica de los módulos existentes.

const gcApiBase = `${backendUrl}/api/gestion-coordinador`;

let gcState = {
    periodo: new Date().toISOString().slice(0, 7),
    vista: 'dashboard',
    coordinadores: [],
    actividades: [],
    asignaciones: [],
    alertas: [],
    panelActual: null
};

function gcPeriodoActual() {
    return new Date().toISOString().slice(0, 7);
}

function gcHoy() {
    return new Date().toISOString().slice(0, 10);
}

function gcApi(path, options = {}) {
    return fetch(`${gcApiBase}${path}`, options).then(manejarRespuestaJson);
}

function gcMessage(texto, tipo = 'success') {
    const box = document.getElementById('gc-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.textContent = texto;
    box.classList.remove('hidden');
}

function gcInit() {
    const periodo = document.getElementById('gc-periodo');
    if (periodo && !periodo.value) periodo.value = gcPeriodoActual();
    const fecha = document.getElementById('gc-actividad-fecha');
    if (fecha && !fecha.value) fecha.value = gcHoy();
    gcMostrarVista(gcState.vista || 'dashboard');
    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function gcMostrarVista(vista) {
    gcState.vista = vista;
    document.querySelectorAll('.gc-view').forEach(el => el.classList.add('hidden'));
    document.getElementById(`gc-view-${vista}`)?.classList.remove('hidden');
    document.querySelectorAll('.gc-tab').forEach(btn => btn.classList.remove('gc-tab-active'));
    document.getElementById(`gc-tab-${vista}`)?.classList.add('gc-tab-active');

    if (vista === 'dashboard') gcCargarDashboard();
    if (vista === 'coordinadores') gcCargarCoordinadores();
    if (vista === 'asignaciones') gcCargarAsignaciones();
    if (vista === 'calendario') gcCargarCalendario();
    if (vista === 'alertas') gcCargarAlertas();
    if (vista === 'reporte') gcCargarReporte();
}

function gcPeriodoSeleccionado() {
    return document.getElementById('gc-periodo')?.value || gcPeriodoActual();
}

function gcCargarDashboard() {
    const periodo = gcPeriodoSeleccionado();
    gcApi(`/dashboard?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            document.getElementById('gc-total-coordinadores').textContent = data.total_coordinadores || 0;
            document.getElementById('gc-total-actividades').textContent = data.total_actividades || 0;
            document.getElementById('gc-pendientes').textContent = data.actividades_pendientes || 0;
            document.getElementById('gc-vencidas').textContent = data.actividades_vencidas || 0;
            document.getElementById('gc-cumplimiento').textContent = `${data.cumplimiento_general || 0}%`;
            gcState.coordinadores = data.coordinadores || [];
            gcRenderCoordinadoresResumen();
            gcRenderAlertasDashboard(data.alertas || []);
            gcActualizarSelectsCoordinador();
        })
        .catch(err => gcMessage(err.message || 'No se pudo cargar Gestión por Coordinador.', 'error'));
}

function gcRenderCoordinadoresResumen() {
    const htmlVacio = '<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500">No hay coordinadores visibles para tu rol o fundación.</td></tr>';
    const htmlFilas = gcState.coordinadores.length ? gcState.coordinadores.map(c => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3 font-semibold text-slate-200">${escaparHtml(c.nombre || '')}</td>
            <td class="px-4 py-3">${escaparHtml(c.unidades_asignadas || 0)}</td>
            <td class="px-4 py-3">${escaparHtml(c.docentes_asignados || 0)}</td>
            <td class="px-4 py-3">${escaparHtml(c.pendientes_mes || 0)}</td>
            <td class="px-4 py-3"><span class="gc-semaforo gc-${String(c.estado_cumplimiento || 'GRIS').toLowerCase()}">${escaparHtml(c.estado_cumplimiento || 'GRIS')}</span></td>
            <td class="px-4 py-3">${escaparHtml(c.alertas_abiertas || 0)}</td>
            <td class="px-4 py-3"><button onclick="gcAbrirPanelCoordinador(${Number(c.id)})" class="text-cyan-300 hover:text-cyan-200 text-xs">Ver panel</button></td>
        </tr>
    `).join('') : htmlVacio;
    ['gc-coordinadores-resumen', 'gc-coordinadores-list'].forEach(id => {
        const body = document.getElementById(id);
        if (body) body.innerHTML = htmlFilas;
    });
}

function gcRenderAlertasDashboard(alertas) {
    const cont = document.getElementById('gc-alertas-dashboard');
    if (!cont) return;
    cont.innerHTML = alertas.length
        ? alertas.slice(0, 8).map(a => `<div class="rounded-xl border ${gcClaseEstado(a.nivel || a.tipo)} p-3 text-sm"><strong>${escaparHtml(a.nivel || '')}</strong> ${escaparHtml(a.mensaje || '')}</div>`).join('')
        : '<p class="text-slate-500 text-sm">Sin alertas críticas para el periodo.</p>';
}

function gcCargarCoordinadores() {
    const periodo = gcPeriodoSeleccionado();
    gcApi(`/coordinadores?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gcState.coordinadores = data.coordinadores || [];
            gcActualizarSelectsCoordinador();
            gcRenderCoordinadoresResumen();
        })
        .catch(err => gcMessage(err.message || 'No se pudieron cargar coordinadores.', 'error'));
}

function gcActualizarSelectsCoordinador() {
    const options = '<option value="">Todos / sin coordinador</option>' + gcState.coordinadores.map(c => `<option value="${Number(c.id)}">${escaparHtml(c.nombre || '')}</option>`).join('');
    ['gc-asignacion-filtro-coordinador', 'gc-cal-filtro-coordinador', 'gc-asig-coordinador', 'gc-actividad-coordinador'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        const prev = el.value;
        el.innerHTML = options;
        if ([...el.options].some(o => o.value === prev)) el.value = prev;
    });
}

function gcAbrirPanelCoordinador(id) {
    const periodo = gcPeriodoSeleccionado();
    gcMostrarVista('panel');
    gcApi(`/coordinadores/${encodeURIComponent(id)}/panel?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gcState.panelActual = data;
            gcRenderPanelCoordinador(data);
        })
        .catch(err => gcMessage(err.message || 'No se pudo abrir el panel del coordinador.', 'error'));
}

function gcRenderPanelCoordinador(data) {
    const cont = document.getElementById('gc-panel-coordinador');
    if (!cont) return;
    const c = data.coordinador || {};
    const cumplimiento = data.cumplimiento || {};
    cont.innerHTML = `
        <div class="gc-card">
            <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div>
                    <h3 class="text-xl font-bold text-slate-100">${escaparHtml(c.nombre || '')}</h3>
                    <p class="text-sm text-slate-400">Documento: ${escaparHtml(c.documento || '')} · Teléfono: ${escaparHtml(c.telefono || '')}</p>
                    <p class="text-sm text-slate-400">Contrato/Zona: ${escaparHtml(c.contrato || '')} ${escaparHtml(c.zona || '')}</p>
                </div>
                <div class="rounded-2xl border border-slate-700 bg-slate-950 p-4 text-center">
                    <p class="text-xs text-slate-400">Cumplimiento</p>
                    <p class="text-3xl font-bold text-cyan-300">${escaparHtml(cumplimiento.porcentaje || 0)}%</p>
                    <span class="gc-semaforo gc-${String(cumplimiento.semaforo || 'GRIS').toLowerCase()}">${escaparHtml(cumplimiento.semaforo || 'GRIS')}</span>
                </div>
            </div>
        </div>
        <div class="grid gap-4 lg:grid-cols-3">
            ${gcPanelBloque('Unidades asignadas', data.unidades || [])}
            ${gcPanelBloque('Agentes educativos asignados', (data.docentes || []).map(x => `${x.nombre || ''} · ${x.unidad || ''}`))}
            ${gcPanelBloque('Talento humano asignado', (data.talento_asignado || []).map(x => `${x.nombre || ''} · ${x.tipo_talento || x.rol || ''}`))}
        </div>
        <div class="grid gap-4 lg:grid-cols-2">
            ${gcTablaPanel('Pendientes', data.pendientes || [], ['tipo','titulo','fecha_limite','estado'])}
            ${gcTablaPanel('Cuentas de cobro', data.cuentas_cobro || [], ['tipo','titulo','fecha_limite','estado'])}
            ${gcTablaPanel('Planeaciones cargadas', data.planeaciones || [], ['periodo','tema','estado','fecha_creacion'])}
            ${gcTablaPanel('Evidencias cargadas', data.evidencias || [], ['tipo','titulo','estado','fecha_creacion'])}
        </div>
    `;
}

function gcPanelBloque(titulo, items) {
    const filas = (items || []).length ? items.map(x => `<li>${escaparHtml(typeof x === 'string' ? x : JSON.stringify(x))}</li>`).join('') : '<li class="text-slate-500">Sin registros.</li>';
    return `<div class="gc-card"><h4 class="font-semibold text-slate-200 mb-2">${escaparHtml(titulo)}</h4><ul class="list-disc pl-5 text-sm text-slate-400 space-y-1">${filas}</ul></div>`;
}

function gcTablaPanel(titulo, items, campos) {
    const filas = (items || []).length ? items.map(item => `<tr>${campos.map(c => `<td class="px-3 py-2">${escaparHtml(item[c] || '')}</td>`).join('')}</tr>`).join('') : `<tr><td colspan="${campos.length}" class="px-3 py-6 text-center text-slate-500">Sin registros.</td></tr>`;
    return `<div class="gc-card overflow-x-auto"><h4 class="font-semibold text-slate-200 mb-3">${escaparHtml(titulo)}</h4><table class="w-full text-left text-xs text-slate-400"><thead class="bg-slate-950 text-slate-300"><tr>${campos.map(c => `<th class="px-3 py-2">${escaparHtml(c)}</th>`).join('')}</tr></thead><tbody class="divide-y divide-slate-800">${filas}</tbody></table></div>`;
}

function gcCargarAsignaciones() {
    const coord = document.getElementById('gc-asignacion-filtro-coordinador', 'gc-cal-filtro-coordinador')?.value || '';
    const q = coord ? `?coordinador_id=${encodeURIComponent(coord)}` : '';
    gcApi(`/asignaciones${q}`)
        .then(data => {
            gcState.asignaciones = data.asignaciones || [];
            gcRenderAsignaciones();
            gcCargarCoordinadores();
        })
        .catch(err => gcMessage(err.message || 'No se pudieron cargar asignaciones.', 'error'));
}

function gcRenderAsignaciones() {
    const body = document.getElementById('gc-asignaciones-list');
    if (!body) return;
    if (!gcState.asignaciones.length) {
        body.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-slate-500">Sin asignaciones registradas.</td></tr>';
        return;
    }
    body.innerHTML = gcState.asignaciones.map(a => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3">${escaparHtml(a.coordinador_nombre || '')}</td>
            <td class="px-4 py-3">${escaparHtml(a.tipo_talento || '')}</td>
            <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(a.nombre || '')}</td>
            <td class="px-4 py-3">${escaparHtml(a.documento || '')}</td>
            <td class="px-4 py-3">${escaparHtml(a.cargo || a.rol || '')}</td>
            <td class="px-4 py-3">${escaparHtml(a.unidad || '')}</td>
            <td class="px-4 py-3"><span class="gc-state">${escaparHtml(a.estado || '')}</span></td>
            <td class="px-4 py-3"><button onclick="gcEditarAsignacion(${Number(a.id)})" class="text-cyan-300 text-xs mr-2">Editar</button><button onclick="gcEliminarAsignacion(${Number(a.id)})" class="text-rose-300 text-xs">Inactivar</button></td>
        </tr>
    `).join('');
}

function gcCrearAsignacion() {
    const payload = {
        coordinador_id: document.getElementById('gc-asig-coordinador')?.value || null,
        tipo_talento: document.getElementById('gc-asig-tipo')?.value || 'DOCENTE',
        nombre: document.getElementById('gc-asig-nombre')?.value || '',
        documento: document.getElementById('gc-asig-documento')?.value || '',
        cargo: document.getElementById('gc-asig-cargo')?.value || '',
        unidad: document.getElementById('gc-asig-unidad')?.value || '',
        telefono: document.getElementById('gc-asig-telefono')?.value || '',
        email: document.getElementById('gc-asig-email')?.value || '',
        observaciones: document.getElementById('gc-asig-observaciones')?.value || ''
    };
    if (!payload.coordinador_id || !payload.nombre.trim()) {
        gcMessage('Selecciona coordinador y escribe el nombre del talento humano.', 'error');
        return;
    }
    gcApi('/asignaciones', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .then(data => {
            gcMessage(data.message || 'Asignación guardada.');
            ['gc-asig-nombre','gc-asig-documento','gc-asig-cargo','gc-asig-unidad','gc-asig-telefono','gc-asig-email','gc-asig-observaciones'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            gcCargarAsignaciones();
        })
        .catch(err => gcMessage(err.message || 'No se pudo crear asignación.', 'error'));
}

function gcEditarAsignacion(id) {
    const a = gcState.asignaciones.find(x => Number(x.id) === Number(id));
    if (!a) return;
    const estado = prompt('Estado:', a.estado || 'ACTIVO');
    if (estado === null) return;
    const coord = prompt('Nuevo coordinador_id para reasignar:', a.coordinador_id || '');
    if (coord === null) return;
    gcApi(`/asignaciones/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...a, estado, coordinador_id: coord }) })
        .then(data => { gcMessage(data.message || 'Asignación actualizada.'); gcCargarAsignaciones(); })
        .catch(err => gcMessage(err.message || 'No se pudo actualizar asignación.', 'error'));
}

function gcEliminarAsignacion(id) {
    if (!confirm('¿Inactivar esta asignación?')) return;
    gcApi(`/asignaciones/${id}`, { method: 'DELETE' })
        .then(data => { gcMessage(data.message || 'Asignación inactivada.'); gcCargarAsignaciones(); })
        .catch(err => gcMessage(err.message || 'No se pudo inactivar asignación.', 'error'));
}

function gcCargarCalendario() {
    const params = new URLSearchParams();
    params.set('periodo', gcPeriodoSeleccionado());
    params.set('vista', document.getElementById('gc-vista-calendario')?.value || 'mes');
    ['gc-asignacion-filtro-coordinador', 'gc-cal-filtro-coordinador','gc-filtro-unidad','gc-filtro-docente','gc-filtro-tipo','gc-filtro-estado'].forEach(id => {
        const el = document.getElementById(id);
        if (el && el.value) {
            let key = id.replace('gc-filtro-', '').replace('gc-cal-filtro-', '');
            key = key.replace('coordinador', 'coordinador_id').replace('docente', 'docente_id');
            params.set(key, el.value);
        }
    });
    gcApi(`/calendario?${params.toString()}`)
        .then(data => {
            gcState.actividades = data.actividades || [];
            gcRenderCalendario(data);
        })
        .catch(err => gcMessage(err.message || 'No se pudo cargar calendario.', 'error'));
}

function gcRenderCalendario(data) {
    const cont = document.getElementById('gc-calendario-list');
    if (!cont) return;
    const actividades = data.actividades || [];
    if (!actividades.length) {
        cont.innerHTML = '<p class="text-slate-500 text-sm">No hay actividades para el filtro seleccionado.</p>';
        return;
    }
    const grupos = {};
    actividades.forEach(a => {
        const dia = String(a.fecha || '').slice(8, 10) || '--';
        if (!grupos[dia]) grupos[dia] = [];
        grupos[dia].push(a);
    });
    cont.innerHTML = Object.keys(grupos).sort().map(dia => `
        <div class="gc-day" onclick="gcToggleDia('${dia}')">
            <div class="flex items-center justify-between"><span class="text-3xl font-bold text-cyan-300">${Number(dia) || dia}</span><span class="text-xs text-slate-400">${grupos[dia].length} actividad(es)</span></div>
            <div class="mt-3 space-y-2">${grupos[dia].slice(0, 3).map(a => `<div class="rounded-lg border px-2 py-1 text-xs ${gcClaseEstado(a.estado)}">${escaparHtml(a.titulo || '')}</div>`).join('')}</div>
            <div id="gc-dia-${dia}" class="hidden mt-3 space-y-2 text-xs text-slate-400">${grupos[dia].map(a => `<div class="rounded-lg border border-slate-800 bg-slate-950/60 p-2"><p class="font-medium text-slate-200">${escaparHtml(a.titulo || '')}</p><p>${escaparHtml(a.tipo || '')} · ${escaparHtml(a.estado || '')} · ${escaparHtml(a.coordinador_nombre || '')}</p><p>${escaparHtml(a.descripcion || '')}</p><div class="mt-2"><button onclick="event.stopPropagation();gcEditarActividad(${Number(a.id)})" class="text-cyan-300 mr-2">Editar</button><button onclick="event.stopPropagation();gcEliminarActividad(${Number(a.id)})" class="text-rose-300">Anular</button></div></div>`).join('')}</div>
        </div>
    `).join('');
}

function gcToggleDia(dia) {
    document.getElementById(`gc-dia-${dia}`)?.classList.toggle('hidden');
}

function gcClaseEstado(estado) {
    const e = normalizarFiltro(estado || '');
    if (e.includes('CUMPLIDO') || e.includes('VERDE')) return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    if (e.includes('PENDIENTE') || e.includes('AMARILLO')) return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
    if (e.includes('VENCIDO') || e.includes('ROJO')) return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    if (e.includes('PROGRAMADO') || e.includes('REPROGRAMADO') || e.includes('AZUL')) return 'border-sky-500/30 bg-sky-500/10 text-sky-300';
    return 'border-slate-700 bg-slate-900/60 text-slate-300';
}

function gcCrearActividad() {
    const payload = {
        coordinador_id: document.getElementById('gc-actividad-coordinador')?.value || null,
        titulo: document.getElementById('gc-actividad-titulo')?.value || '',
        tipo: document.getElementById('gc-actividad-tipo')?.value || 'Entregables ICBF',
        fecha: document.getElementById('gc-actividad-fecha')?.value || '',
        hora: document.getElementById('gc-actividad-hora')?.value || '',
        estado: document.getElementById('gc-actividad-estado')?.value || 'PROGRAMADO',
        unidad: document.getElementById('gc-actividad-unidad')?.value || '',
        responsable: document.getElementById('gc-actividad-responsable')?.value || '',
        descripcion: document.getElementById('gc-actividad-descripcion')?.value || '',
        evidencia_requerida: document.getElementById('gc-actividad-evidencia')?.checked || false
    };
    if (!payload.titulo.trim() || !payload.fecha) {
        gcMessage('Título y fecha son obligatorios.', 'error');
        return;
    }
    gcApi('/calendario/actividades', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
        .then(data => {
            gcMessage(data.message || 'Actividad creada.');
            ['gc-actividad-titulo','gc-actividad-unidad','gc-actividad-responsable','gc-actividad-descripcion'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            gcCargarCalendario();
            gcCargarDashboard();
        })
        .catch(err => gcMessage(err.message || 'No se pudo crear actividad.', 'error'));
}

function gcEditarActividad(id) {
    const a = gcState.actividades.find(x => Number(x.id) === Number(id));
    if (!a) return;
    const estado = prompt('Estado: PROGRAMADO, PENDIENTE, CUMPLIDO, VENCIDO, REPROGRAMADO, ANULADO', a.estado || 'PROGRAMADO');
    if (estado === null) return;
    const descripcion = prompt('Descripción:', a.descripcion || '');
    if (descripcion === null) return;
    gcApi(`/calendario/actividades/${id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...a, estado, descripcion }) })
        .then(data => { gcMessage(data.message || 'Actividad actualizada.'); gcCargarCalendario(); gcCargarDashboard(); })
        .catch(err => gcMessage(err.message || 'No se pudo actualizar actividad.', 'error'));
}

function gcEliminarActividad(id) {
    if (!confirm('¿Anular esta actividad?')) return;
    gcApi(`/calendario/actividades/${id}`, { method: 'DELETE' })
        .then(data => { gcMessage(data.message || 'Actividad anulada.'); gcCargarCalendario(); gcCargarDashboard(); })
        .catch(err => gcMessage(err.message || 'No se pudo anular actividad.', 'error'));
}

function gcCargarAlertas() {
    const periodo = gcPeriodoSeleccionado();
    gcApi(`/alertas?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gcState.alertas = data.alertas || [];
            const cont = document.getElementById('gc-alertas-list');
            if (!cont) return;
            cont.innerHTML = gcState.alertas.length
                ? gcState.alertas.map(a => `<div class="rounded-xl border ${gcClaseEstado(a.nivel || a.tipo)} p-3 text-sm"><p class="font-semibold">${escaparHtml(a.tipo || a.nivel || '')}</p><p>${escaparHtml(a.mensaje || '')}</p><p class="text-xs opacity-80">${escaparHtml(a.fecha_alerta || '')}</p></div>`).join('')
                : '<p class="text-slate-500 text-sm">No hay alertas para el periodo.</p>';
        })
        .catch(err => gcMessage(err.message || 'No se pudieron cargar alertas.', 'error'));
}

function gcCargarReporte() {
    const periodo = gcPeriodoSeleccionado();
    gcApi(`/reportes/mensual?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            const cont = document.getElementById('gc-reporte-contenido');
            if (!cont) return;
            const coords = data.coordinadores || [];
            const porTipo = data.por_tipo || {};
            cont.innerHTML = `
                <div class="grid gap-4 md:grid-cols-4">
                    <div class="gc-card"><p class="text-xs text-slate-400">Cumplimiento</p><p class="text-3xl font-bold text-cyan-300">${escaparHtml(data.cumplimiento_general || 0)}%</p></div>
                    <div class="gc-card"><p class="text-xs text-slate-400">Actividades</p><p class="text-3xl font-bold">${escaparHtml(data.total_actividades || 0)}</p></div>
                    <div class="gc-card"><p class="text-xs text-slate-400">Pendientes</p><p class="text-3xl font-bold text-amber-300">${escaparHtml(data.actividades_pendientes || 0)}</p></div>
                    <div class="gc-card"><p class="text-xs text-slate-400">Vencidas</p><p class="text-3xl font-bold text-rose-300">${escaparHtml(data.actividades_vencidas || 0)}</p></div>
                </div>
                <div class="grid gap-4 lg:grid-cols-2 mt-4">
                    <div class="gc-card"><h4 class="font-semibold mb-3">Cumplimiento por coordinador</h4>${coords.map(c => `<p class="text-sm text-slate-300 mb-1">${escaparHtml(c.nombre || '')}: ${escaparHtml(c.cumplimiento?.porcentaje || 0)}% · ${escaparHtml(c.estado_cumplimiento || '')}</p>`).join('') || '<p class="text-slate-500">Sin coordinadores.</p>'}</div>
                    <div class="gc-card"><h4 class="font-semibold mb-3">Resumen por tipo</h4>${Object.entries(porTipo).map(([tipo, v]) => `<p class="text-sm text-slate-300 mb-1">${escaparHtml(tipo)}: ${escaparHtml(v.total)} total, ${escaparHtml(v.vencidas)} vencidas</p>`).join('') || '<p class="text-slate-500">Sin actividades.</p>'}</div>
                </div>
            `;
        })
        .catch(err => gcMessage(err.message || 'No se pudo generar reporte.', 'error'));
}
