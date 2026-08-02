// Módulo independiente: Gestión Pedagógica / Seguimiento Coordinadores
// No modifica la lógica existente de Panel Principal, Formatos, Nutrición, Talento ni Cumplimiento.

const gpApiBase = `${backendUrl}/api/gestion-pedagogica`;

let gpState = {
    currentView: 'dashboard',
    coordinadores: [],
    equipos: [],
    docentes: [],
    entregables: [],
    documentos: [],
    alertas: [],
    calendario: []
};

function gpPeriodoActual() {
    return new Date().toISOString().slice(0, 7);
}

function gpHoy() {
    return new Date().toISOString().slice(0, 10);
}

function gpSetDefaultDates() {
    ['gp-periodo', 'gp-entregable-periodo', 'gp-reporte-periodo', 'gp-importar-calendario-periodo', 'gp-planeacion-periodo'].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.value) el.value = gpPeriodoActual();
    });
    ['gp-entregable-fecha', 'gp-evento-fecha'].forEach(id => {
        const el = document.getElementById(id);
        if (el && !el.value) el.value = gpHoy();
    });
}

function gpMessage(texto, tipo = 'success') {
    const box = document.getElementById('gp-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.innerText = texto;
    box.classList.remove('hidden');
}

function gpApi(path, options = {}) {
    return fetch(`${gpApiBase}${path}`, options).then(manejarRespuestaJson);
}

function gpMostrarVista(view) {
    gpSetDefaultDates();
    gpState.currentView = view;

    document.querySelectorAll('.gp-view').forEach(el => el.classList.add('hidden'));
    const panel = document.getElementById(`gp-view-${view}`);
    if (panel) panel.classList.remove('hidden');

    document.querySelectorAll('.gp-tab').forEach(el => el.classList.remove('gp-tab-active'));
    const tab = document.getElementById(`gp-tab-${view}`);
    if (tab) tab.classList.add('gp-tab-active');

    if (view === 'dashboard') gpCargarDashboard();
    if (view === 'coordinadores') gpFetchCoordinadores();
    if (view === 'equipos') gpCargarEquiposYDocentes();
    if (view === 'entregables') gpFetchEntregables();
    if (view === 'calendario') gpFetchCalendario();
    if (view === 'planeacion') gpPrepararPlaneacion();
    if (view === 'documentos') gpFetchDocumentos();
    if (view === 'alertas') gpFetchAlertas();
    if (view === 'reportes') gpCargarReporteMensual(false);

    if (typeof lucide !== 'undefined') lucide.createIcons();
}

function gpCargarDashboard() {
    const periodo = document.getElementById('gp-periodo')?.value || gpPeriodoActual();
    gpApi(`/dashboard?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            document.getElementById('gp-total-coordinadores').innerText = data.total_coordinadores || 0;
            document.getElementById('gp-total-entregables').innerText = data.total_entregables_mes || 0;
            document.getElementById('gp-entregables-pendientes').innerText = data.entregables_pendientes || 0;
            document.getElementById('gp-entregables-vencidos').innerText = data.entregables_vencidos || 0;
            document.getElementById('gp-docs-revisar').innerText = data.documentos_por_revisar || 0;
            document.getElementById('gp-cumplimiento').innerText = `${data.cumplimiento_general || 0}%`;
            document.getElementById('gp-alertas-criticas').innerText = data.alertas_criticas || 0;

            const alertas = data.alertas || [];
            const cont = document.getElementById('gp-alertas-dashboard');
            if (cont) {
                cont.innerHTML = alertas.length
                    ? alertas.map(a => `<div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3"><span class="gp-state">${escaparHtml(a.nivel)}</span> ${escaparHtml(a.mensaje)}</div>`).join('')
                    : '<p class="text-slate-500">Sin alertas para el periodo.</p>';
            }
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar el dashboard pedagógico.', 'error'));

    gpFetchCoordinadores(false);
    gpFetchEntregables(false);
}

function gpActualizarSelectCoordinadores() {
    const options = '<option value="">Sin coordinador</option>' + gpState.coordinadores.map(c => `
        <option value="${Number(c.id)}">${escaparHtml(c.nombre || '')}</option>
    `).join('');

    [
        'gp-equipo-coordinador',
        'gp-docente-coordinador',
        'gp-entregable-coordinador',
        'gp-evento-coordinador',
        'gp-doc-coordinador',
        'gp-planeacion-coordinador'
    ].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            const prev = el.value;
            el.innerHTML = options;
            if ([...el.options].some(o => o.value === prev)) el.value = prev;
        }
    });
}

function gpActualizarSelectEntregables() {
    const options = '<option value="">Sin entregable</option>' + gpState.entregables.map(e => `
        <option value="${Number(e.id)}">${escaparHtml(e.titulo || e.tipo || '')}</option>
    `).join('');
    const el = document.getElementById('gp-doc-entregable');
    if (el) {
        const prev = el.value;
        el.innerHTML = options;
        if ([...el.options].some(o => o.value === prev)) el.value = prev;
    }
}

function gpFetchCoordinadores(render = true) {
    return gpApi('/coordinadores')
        .then(data => {
            gpState.coordinadores = data.coordinadores || [];
            gpActualizarSelectCoordinadores();
            if (render) gpRenderCoordinadores();
        })
        .catch(error => gpMessage(error.message || 'No se pudieron cargar coordinadores.', 'error'));
}

function gpRenderCoordinadores() {
    const body = document.getElementById('gp-coordinadores-list');
    if (!body) return;
    if (!gpState.coordinadores.length) {
        body.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">No hay coordinadores registrados.</td></tr>';
        return;
    }
    body.innerHTML = gpState.coordinadores.map(c => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(c.nombre || '')}</td>
            <td class="px-4 py-3">${escaparHtml(c.documento || '')}</td>
            <td class="px-4 py-3">${escaparHtml(c.telefono || '')}</td>
            <td class="px-4 py-3">${escaparHtml(c.contrato || '')}</td>
            <td class="px-4 py-3 text-xs">${escaparHtml(c.unidades_json || '')}</td>
            <td class="px-4 py-3">
                <button onclick="gpEditarCoordinador(${Number(c.id)})" class="text-cyan-300 hover:text-cyan-200 text-xs mr-2">Editar</button>
                <button onclick="gpEliminarCoordinador(${Number(c.id)})" class="text-rose-300 hover:text-rose-200 text-xs">Eliminar</button>
            </td>
        </tr>
    `).join('');
}

function gpCrearCoordinador() {
    const unidades = (document.getElementById('gp-coord-unidades')?.value || '')
        .split(',')
        .map(x => x.trim())
        .filter(Boolean);

    const payload = {
        nombre: document.getElementById('gp-coord-nombre')?.value || '',
        documento: document.getElementById('gp-coord-documento')?.value || '',
        telefono: document.getElementById('gp-coord-telefono')?.value || '',
        email: document.getElementById('gp-coord-email')?.value || '',
        contrato: document.getElementById('gp-coord-contrato')?.value || '',
        unidades
    };

    if (!payload.nombre.trim()) {
        gpMessage('El nombre del coordinador es obligatorio.', 'error');
        return;
    }

    gpApi('/coordinadores', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(data => {
            gpMessage(data.message || 'Coordinador guardado.');
            ['gp-coord-nombre', 'gp-coord-documento', 'gp-coord-telefono', 'gp-coord-email', 'gp-coord-contrato', 'gp-coord-unidades'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            gpFetchCoordinadores();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo guardar el coordinador.', 'error'));
}

function gpEditarCoordinador(id) {
    const c = gpState.coordinadores.find(x => Number(x.id) === Number(id));
    if (!c) return;
    const nombre = prompt('Nombre del coordinador:', c.nombre || '');
    if (nombre === null) return;
    const documento = prompt('Documento:', c.documento || '');
    if (documento === null) return;
    const telefono = prompt('Teléfono:', c.telefono || '');
    if (telefono === null) return;
    const contrato = prompt('Contrato:', c.contrato || '');
    if (contrato === null) return;
    const unidades = prompt('Unidades separadas por coma:', c.unidades_json || '');
    if (unidades === null) return;

    gpApi(`/coordinadores/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...c, nombre, documento, telefono, contrato, unidades_json: unidades })
    })
        .then(data => {
            gpMessage(data.message || 'Coordinador actualizado.');
            gpFetchCoordinadores();
        })
        .catch(error => gpMessage(error.message || 'No se pudo actualizar el coordinador.', 'error'));
}

function gpEliminarCoordinador(id) {
    if (!confirm('¿Eliminar/desactivar este coordinador?')) return;
    gpApi(`/coordinadores/${id}`, { method: 'DELETE' })
        .then(data => {
            gpMessage(data.message || 'Coordinador eliminado.');
            gpFetchCoordinadores();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo eliminar.', 'error'));
}

function gpCargarEquiposYDocentes() {
    gpFetchCoordinadores(false)
        .then(() => {
            gpFetchEquipos();
            gpFetchDocentes();
        });
}

function gpFetchEquipos() {
    gpApi('/equipos')
        .then(data => {
            gpState.equipos = data.equipos || [];
            const body = document.getElementById('gp-equipos-list');
            if (!body) return;
            body.innerHTML = gpState.equipos.length ? gpState.equipos.map(e => `
                <tr class="hover:bg-slate-900/50">
                    <td class="px-4 py-3"><span class="font-medium text-slate-200">${escaparHtml(e.nombre || '')}</span><br><span class="text-xs">${escaparHtml(e.coordinador_nombre || '')}</span></td>
                    <td class="px-4 py-3">${escaparHtml(e.rol || '')}</td>
                    <td class="px-4 py-3">${escaparHtml(e.telefono || '')}</td>
                    <td class="px-4 py-3"><button onclick="gpEliminarEquipo(${Number(e.id)})" class="text-rose-300 text-xs">Eliminar</button></td>
                </tr>
            `).join('') : '<tr><td class="px-4 py-8 text-center text-slate-500">Sin integrantes registrados.</td></tr>';
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar el equipo.', 'error'));
}

function gpCrearEquipo() {
    const payload = {
        coordinador_id: document.getElementById('gp-equipo-coordinador')?.value || null,
        nombre: document.getElementById('gp-equipo-nombre')?.value || '',
        documento: document.getElementById('gp-equipo-documento')?.value || '',
        rol: document.getElementById('gp-equipo-rol')?.value || '',
        profesion: document.getElementById('gp-equipo-profesion')?.value || '',
        telefono: document.getElementById('gp-equipo-telefono')?.value || ''
    };
    if (!payload.nombre.trim()) {
        gpMessage('El nombre del integrante es obligatorio.', 'error');
        return;
    }
    gpApi('/equipos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(data => {
        gpMessage(data.message || 'Integrante guardado.');
        ['gp-equipo-nombre','gp-equipo-documento','gp-equipo-profesion','gp-equipo-telefono'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        gpFetchEquipos();
    }).catch(error => gpMessage(error.message || 'No se pudo guardar integrante.', 'error'));
}

function gpEliminarEquipo(id) {
    if (!confirm('¿Eliminar/desactivar este integrante?')) return;
    gpApi(`/equipos/${id}`, { method: 'DELETE' })
        .then(data => { gpMessage(data.message || 'Integrante eliminado.'); gpFetchEquipos(); })
        .catch(error => gpMessage(error.message || 'No se pudo eliminar integrante.', 'error'));
}

function gpFetchDocentes() {
    gpApi('/docentes')
        .then(data => {
            gpState.docentes = data.docentes || [];
            const body = document.getElementById('gp-docentes-list');
            if (!body) return;
            body.innerHTML = gpState.docentes.length ? gpState.docentes.map(d => `
                <tr class="hover:bg-slate-900/50">
                    <td class="px-4 py-3"><span class="font-medium text-slate-200">${escaparHtml(d.nombre || '')}</span><br><span class="text-xs">${escaparHtml(d.coordinador_nombre || '')}</span></td>
                    <td class="px-4 py-3">${escaparHtml(d.unidad || '')}</td>
                    <td class="px-4 py-3">${escaparHtml(d.telefono || '')}</td>
                    <td class="px-4 py-3"><button onclick="gpEliminarDocente(${Number(d.id)})" class="text-rose-300 text-xs">Eliminar</button></td>
                </tr>
            `).join('') : '<tr><td class="px-4 py-8 text-center text-slate-500">Sin agentes educativos registrados.</td></tr>';
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar agentes educativos.', 'error'));
}

function gpCrearDocente() {
    const payload = {
        coordinador_id: document.getElementById('gp-docente-coordinador')?.value || null,
        nombre: document.getElementById('gp-docente-nombre')?.value || '',
        documento: document.getElementById('gp-docente-documento')?.value || '',
        unidad: document.getElementById('gp-docente-unidad')?.value || '',
        telefono: document.getElementById('gp-docente-telefono')?.value || '',
        email: document.getElementById('gp-docente-email')?.value || ''
    };
    if (!payload.nombre.trim()) {
        gpMessage('El nombre del agente educativo es obligatorio.', 'error');
        return;
    }
    gpApi('/docentes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(data => {
        gpMessage(data.message || 'Agente educativo guardado.');
        ['gp-docente-nombre','gp-docente-documento','gp-docente-unidad','gp-docente-telefono','gp-docente-email'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        gpFetchDocentes();
    }).catch(error => gpMessage(error.message || 'No se pudo guardar agente educativo.', 'error'));
}

function gpEliminarDocente(id) {
    if (!confirm('¿Eliminar/desactivar este agente educativo?')) return;
    gpApi(`/docentes/${id}`, { method: 'DELETE' })
        .then(data => { gpMessage(data.message || 'Agente educativo eliminado.'); gpFetchDocentes(); })
        .catch(error => gpMessage(error.message || 'No se pudo eliminar agente educativo.', 'error'));
}

function gpFetchEntregables(render = true) {
    const periodo = document.getElementById('gp-entregable-periodo')?.value || document.getElementById('gp-periodo')?.value || gpPeriodoActual();
    return gpApi(`/entregables?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gpState.entregables = data.entregables || [];
            gpActualizarSelectEntregables();
            if (render) gpRenderEntregables();
        })
        .catch(error => gpMessage(error.message || 'No se pudieron cargar entregables.', 'error'));
}

function gpRenderEntregables() {
    const body = document.getElementById('gp-entregables-list');
    if (!body) return;
    if (!gpState.entregables.length) {
        body.innerHTML = '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">No hay entregables para el periodo.</td></tr>';
        return;
    }
    body.innerHTML = gpState.entregables.map(e => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3">${escaparHtml(e.tipo || '')}</td>
            <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(e.titulo || '')}</td>
            <td class="px-4 py-3">${escaparHtml(e.coordinador_nombre || '')}</td>
            <td class="px-4 py-3">${escaparHtml(e.fecha_limite || '')}</td>
            <td class="px-4 py-3"><span class="gp-state">${escaparHtml(e.estado || '')}</span></td>
            <td class="px-4 py-3"><button onclick="gpEditarEntregable(${Number(e.id)})" class="text-cyan-300 text-xs mr-2">Editar</button><button onclick="gpEliminarEntregable(${Number(e.id)})" class="text-rose-300 text-xs">Eliminar</button></td>
        </tr>
    `).join('');
}

function gpCrearEntregable() {
    const payload = {
        coordinador_id: document.getElementById('gp-entregable-coordinador')?.value || null,
        tipo: document.getElementById('gp-entregable-tipo')?.value || '',
        titulo: document.getElementById('gp-entregable-titulo')?.value || '',
        periodo: document.getElementById('gp-entregable-periodo')?.value || gpPeriodoActual(),
        fecha_limite: document.getElementById('gp-entregable-fecha')?.value || '',
        prioridad: document.getElementById('gp-entregable-prioridad')?.value || 'media',
        estado: document.getElementById('gp-entregable-estado')?.value || 'Pendiente',
        unidad: document.getElementById('gp-entregable-unidad')?.value || '',
        responsable: document.getElementById('gp-entregable-responsable')?.value || '',
        descripcion: document.getElementById('gp-entregable-descripcion')?.value || ''
    };
    if (!payload.tipo.trim()) {
        gpMessage('El tipo de entregable es obligatorio.', 'error');
        return;
    }
    if (!payload.titulo.trim()) payload.titulo = payload.tipo;
    gpApi('/entregables', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(data => {
        const entregable = data.entregable || {};
        const file = document.getElementById('gp-entregable-file')?.files?.[0];
        const afterSave = () => {
            gpMessage(data.message || 'Entregable guardado.');
            ['gp-entregable-tipo','gp-entregable-titulo','gp-entregable-unidad','gp-entregable-responsable','gp-entregable-descripcion'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            const input = document.getElementById('gp-entregable-file');
            if (input) input.value = '';
            gpFetchEntregables();
            gpCargarDashboard();
        };
        if (file && entregable.id) {
            const form = new FormData();
            form.append('file', file);
            form.append('entregable_id', entregable.id);
            form.append('coordinador_id', payload.coordinador_id || '');
            form.append('version', '1.0');
            form.append('observaciones', 'Documento cargado desde el entregable.');
            gpApi('/documentos/upload', { method: 'POST', body: form }).then(afterSave).catch(afterSave);
        } else {
            afterSave();
        }
    }).catch(error => gpMessage(error.message || 'No se pudo guardar entregable.', 'error'));
}

function gpEditarEntregable(id) {
    const e = gpState.entregables.find(x => Number(x.id) === Number(id));
    if (!e) return;
    const estado = prompt('Estado del entregable:', e.estado || 'Pendiente');
    if (estado === null) return;
    const observaciones = prompt('Observaciones:', e.observaciones || '');
    if (observaciones === null) return;
    gpApi(`/entregables/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...e, estado, observaciones })
    }).then(data => {
        gpMessage(data.message || 'Entregable actualizado.');
        gpFetchEntregables();
        gpCargarDashboard();
    }).catch(error => gpMessage(error.message || 'No se pudo actualizar entregable.', 'error'));
}

function gpEliminarEntregable(id) {
    if (!confirm('¿Eliminar/desactivar este entregable?')) return;
    gpApi(`/entregables/${id}`, { method: 'DELETE' })
        .then(data => { gpMessage(data.message || 'Entregable eliminado.'); gpFetchEntregables(); gpCargarDashboard(); })
        .catch(error => gpMessage(error.message || 'No se pudo eliminar entregable.', 'error'));
}

function gpColorEstado(estado) {
    const e = normalizarFiltro(estado);
    if (e.includes('APROBADO')) return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    if (e.includes('CARGADO') || e.includes('REVISION')) return 'border-sky-500/30 bg-sky-500/10 text-sky-300';
    if (e.includes('DEVUELTO')) return 'border-orange-500/30 bg-orange-500/10 text-orange-300';
    if (e.includes('VENCIDO')) return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    return 'border-slate-700 bg-slate-900/60 text-slate-300';
}

function gpFetchCalendario() {
    const periodo = document.getElementById('gp-periodo')?.value || document.getElementById('gp-importar-calendario-periodo')?.value || gpPeriodoActual();
    gpApi(`/calendario?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gpState.calendario = data.eventos || [];
            const entregables = data.entregables || [];
            const cont = document.getElementById('gp-calendario-list');
            if (!cont) return;
            const items = [
                ...gpState.calendario.map(e => ({ ...e, origen: 'Evento' })),
                ...entregables.map(e => ({ id: e.id, titulo: e.titulo, tipo: e.tipo, fecha: e.fecha_limite, estado: e.estado, descripcion: e.descripcion, coordinador_nombre: e.coordinador_nombre, origen: 'Entregable' }))
            ].filter(x => x.fecha).sort((a, b) => String(a.fecha).localeCompare(String(b.fecha)));
            if (!items.length) {
                cont.innerHTML = '<p class="text-slate-500">No hay eventos ni entregables fechados para el periodo.</p>';
                return;
            }
            const grupos = {};
            items.forEach(item => {
                const dia = String(item.fecha || '').slice(8, 10) || '--';
                if (!grupos[dia]) grupos[dia] = [];
                grupos[dia].push(item);
            });
            cont.innerHTML = Object.keys(grupos).sort().map(dia => `
                <div class="gp-card cursor-pointer hover:border-cyan-500/50" onclick="gpMostrarDetalleDia('${dia}')">
                    <div class="flex items-center justify-between gap-2">
                        <span class="text-3xl font-bold text-cyan-300">${escaparHtml(Number(dia) || dia)}</span>
                        <span class="rounded-lg border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-300">${grupos[dia].length} actividad(es)</span>
                    </div>
                    <div class="mt-3 space-y-2">
                        ${grupos[dia].slice(0, 3).map(item => `<div class="rounded-lg border px-2 py-1 text-xs ${gpColorEstado(item.estado)}">${escaparHtml(item.titulo || item.tipo || '')}</div>`).join('')}
                    </div>
                    <div id="gp-dia-detalle-${dia}" class="hidden mt-3 space-y-2 text-xs text-slate-400">
                        ${grupos[dia].map(item => `<div class="rounded-lg border border-slate-800 bg-slate-950/60 p-2"><p class="font-medium text-slate-200">${escaparHtml(item.titulo || '')}</p><p>${escaparHtml(item.fecha || '')} ${escaparHtml(item.hora || '')}</p><p>${escaparHtml(item.descripcion || '')}</p><p>${escaparHtml(item.coordinador_nombre || '')}</p></div>`).join('')}
                    </div>
                </div>
            `).join('');
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar calendario.', 'error'));
}

function gpMostrarDetalleDia(dia) {
    const el = document.getElementById(`gp-dia-detalle-${dia}`);
    if (el) el.classList.toggle('hidden');
}

function gpGenerarCalendarioMensual() {
    const periodo = document.getElementById('gp-importar-calendario-periodo')?.value || document.getElementById('gp-periodo')?.value || gpPeriodoActual();
    gpApi('/calendario/generar-mensual', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ periodo })
    }).then(data => {
        gpMessage(data.message || 'Calendario generado.');
        gpFetchCalendario();
        gpCargarDashboard();
    }).catch(error => gpMessage(error.message || 'No se pudo generar calendario.', 'error'));
}

function gpCrearEvento() {
    const payload = {
        coordinador_id: document.getElementById('gp-evento-coordinador')?.value || null,
        titulo: document.getElementById('gp-evento-titulo')?.value || '',
        fecha: document.getElementById('gp-evento-fecha')?.value || '',
        hora: document.getElementById('gp-evento-hora')?.value || '',
        tipo: document.getElementById('gp-evento-tipo')?.value || 'Evento',
        estado: document.getElementById('gp-evento-estado')?.value || 'Pendiente',
        descripcion: document.getElementById('gp-evento-descripcion')?.value || ''
    };
    if (!payload.titulo.trim() || !payload.fecha) {
        gpMessage('Título y fecha son obligatorios.', 'error');
        return;
    }
    gpApi('/calendario/eventos', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    }).then(data => {
        gpMessage(data.message || 'Evento guardado.');
        ['gp-evento-titulo','gp-evento-hora','gp-evento-descripcion'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        gpFetchCalendario();
    }).catch(error => gpMessage(error.message || 'No se pudo guardar evento.', 'error'));
}

function gpFetchDocumentos() {
    gpFetchCoordinadores(false);
    gpFetchEntregables(false);
    gpApi('/documentos')
        .then(data => {
            gpState.documentos = data.documentos || [];
            const body = document.getElementById('gp-documentos-list');
            if (!body) return;
            body.innerHTML = gpState.documentos.length ? gpState.documentos.map(d => `
                <tr class="hover:bg-slate-900/50">
                    <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(d.nombre_original || '')}<br><span class="text-xs text-slate-500">v${escaparHtml(d.version || '1.0')}</span></td>
                    <td class="px-4 py-3">${escaparHtml(d.entregable_titulo || '')}</td>
                    <td class="px-4 py-3">${escaparHtml(d.coordinador_nombre || '')}</td>
                    <td class="px-4 py-3"><span class="gp-state">${escaparHtml(d.estado || '')}</span></td>
                    <td class="px-4 py-3 space-x-2">
                        <button onclick="gpAprobarDocumento(${Number(d.id)})" class="text-emerald-300 text-xs">Aprobar</button>
                        <button onclick="gpDevolverDocumento(${Number(d.id)})" class="text-amber-300 text-xs">Devolver</button>
                        <button type="button" onclick="gpDescargarDocumento(${Number(d.id)})" class="text-cyan-300 text-xs">Descargar</button>
                    </td>
                </tr>
            `).join('') : '<tr><td colspan="5" class="px-4 py-8 text-center text-slate-500">No hay documentos cargados.</td></tr>';
        })
        .catch(error => gpMessage(error.message || 'No se pudieron cargar documentos.', 'error'));
}

function gpSubirDocumento() {
    const file = document.getElementById('gp-doc-file')?.files?.[0];
    if (!file) {
        gpMessage('Selecciona un documento.', 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    form.append('coordinador_id', document.getElementById('gp-doc-coordinador')?.value || '');
    form.append('entregable_id', document.getElementById('gp-doc-entregable')?.value || '');
    form.append('version', document.getElementById('gp-doc-version')?.value || '1.0');
    form.append('observaciones', document.getElementById('gp-doc-observaciones')?.value || '');

    gpApi('/documentos/upload', { method: 'POST', body: form })
        .then(data => {
            gpMessage(data.message || 'Documento cargado.');
            const input = document.getElementById('gp-doc-file');
            if (input) input.value = '';
            document.getElementById('gp-doc-observaciones').value = '';
            gpFetchDocumentos();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar documento.', 'error'));
}

function gpDescargarDocumento(id) {
    window.descargarArchivoAutenticado(`${gpApiBase}/documentos/${encodeURIComponent(id)}/download`)
        .catch((error) => gpMessage(error.message || 'No se pudo descargar el documento.', 'error'));
}

function gpAprobarDocumento(id) {
    gpApi(`/documentos/${id}/aprobar`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario: 'sistema', observaciones: 'Aprobado desde plataforma.' })
    }).then(data => {
        gpMessage(data.message || 'Documento aprobado.');
        gpFetchDocumentos();
        gpCargarDashboard();
    }).catch(error => gpMessage(error.message || 'No se pudo aprobar documento.', 'error'));
}

function gpDevolverDocumento(id) {
    const observaciones = prompt('Observación de devolución:', 'Requiere corrección.');
    if (observaciones === null) return;
    gpApi(`/documentos/${id}/devolver`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ usuario: 'sistema', observaciones })
    }).then(data => {
        gpMessage(data.message || 'Documento devuelto.');
        gpFetchDocumentos();
        gpCargarDashboard();
    }).catch(error => gpMessage(error.message || 'No se pudo devolver documento.', 'error'));
}

function gpFetchAlertas() {
    const periodo = document.getElementById('gp-periodo')?.value || gpPeriodoActual();
    gpApi(`/alertas?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            gpState.alertas = data.alertas || [];
            const cont = document.getElementById('gp-alertas-list');
            if (!cont) return;
            cont.innerHTML = gpState.alertas.length ? gpState.alertas.map(a => `
                <div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                    <span class="gp-state">${escaparHtml(a.nivel || '')}</span>
                    <span class="font-medium text-slate-200">${escaparHtml(a.tipo || '')}</span>
                    <p class="mt-1 text-slate-400">${escaparHtml(a.mensaje || '')}</p>
                </div>
            `).join('') : '<p class="text-slate-500">Sin alertas para este periodo.</p>';
        })
        .catch(error => gpMessage(error.message || 'No se pudieron cargar alertas.', 'error'));
}

function gpCargarReporteMensual(mostrarMensajeReporte = true) {
    const periodo = document.getElementById('gp-reporte-periodo')?.value || document.getElementById('gp-periodo')?.value || gpPeriodoActual();
    const cont = document.getElementById('gp-reporte-contenido');
    if (!cont) return;
    gpApi(`/reportes/mensual?periodo=${encodeURIComponent(periodo)}`)
        .then(data => {
            const coord = data.por_coordinador || [];
            cont.innerHTML = `
                <h3 class="font-medium text-slate-200">Reporte ${escaparHtml(periodo)}</h3>
                <div class="mt-3 grid gap-3 md:grid-cols-4">
                    <div class="gp-card"><p class="text-xs text-slate-400">Cumplimiento</p><h4 class="text-2xl font-bold">${escaparHtml(data.dashboard?.cumplimiento_general || 0)}%</h4></div>
                    <div class="gp-card"><p class="text-xs text-slate-400">Entregables</p><h4 class="text-2xl font-bold">${escaparHtml(data.dashboard?.total_entregables_mes || 0)}</h4></div>
                    <div class="gp-card"><p class="text-xs text-slate-400">Vencidos</p><h4 class="text-2xl font-bold">${escaparHtml(data.dashboard?.entregables_vencidos || 0)}</h4></div>
                    <div class="gp-card"><p class="text-xs text-slate-400">Alertas</p><h4 class="text-2xl font-bold">${escaparHtml((data.alertas || []).length)}</h4></div>
                </div>
                <div class="mt-4 overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-400">
                        <thead class="bg-slate-900 text-slate-300 uppercase"><tr><th class="px-3 py-2">Coordinador</th><th class="px-3 py-2">Total</th><th class="px-3 py-2">Aprobados</th><th class="px-3 py-2">Pendientes</th><th class="px-3 py-2">Vencidos</th><th class="px-3 py-2">Cumplimiento</th></tr></thead>
                        <tbody>${coord.map(c => `<tr class="border-b border-slate-800"><td class="px-3 py-2">${escaparHtml(c.coordinador || '')}</td><td class="px-3 py-2">${c.total_entregables}</td><td class="px-3 py-2">${c.aprobados}</td><td class="px-3 py-2">${c.pendientes}</td><td class="px-3 py-2 text-rose-300">${c.vencidos}</td><td class="px-3 py-2">${c.cumplimiento}%</td></tr>`).join('')}</tbody>
                    </table>
                </div>
                <div class="mt-4 grid gap-4 lg:grid-cols-2">
                    <div class="gp-card"><h4 class="font-medium text-slate-200 mb-2">Resumen por tipo de entregable</h4><div class="space-y-2 text-xs">${(data.por_tipo || []).map(t => `<div class="rounded-lg border border-slate-800 p-2"><b>${escaparHtml(t.tipo)}</b><br>Total: ${t.total} · Pendientes: ${t.pendientes} · Vencidos: ${t.vencidos} · Aprobados: ${t.aprobados}</div>`).join('') || '<p class="text-slate-500">Sin tipos registrados.</p>'}</div></div>
                    <div class="gp-card"><h4 class="font-medium text-slate-200 mb-2">Entregables vencidos / críticos</h4><div class="space-y-2 text-xs">${(data.entregables_vencidos || []).map(e => `<div class="rounded-lg border border-rose-500/30 bg-rose-500/10 p-2"><b>${escaparHtml(e.titulo || e.tipo)}</b><br>${escaparHtml(e.coordinador_nombre || '')} · ${escaparHtml(e.fecha_limite || '')}</div>`).join('') || '<p class="text-slate-500">Sin vencidos.</p>'}</div></div>
                </div>
            `;
            if (mostrarMensajeReporte) gpMessage('Reporte mensual generado.');
        })
        .catch(error => {
            cont.innerHTML = `<p class="text-rose-400">${escaparHtml(error.message || 'No se pudo generar el reporte.')}</p>`;
        });
}

function gpImportarCalendario() {
    const fileInput = document.getElementById('gp-importar-calendario-file');
    const periodo = document.getElementById('gp-importar-calendario-periodo')?.value || gpPeriodoActual();
    const texto = document.getElementById('gp-importar-calendario-texto')?.value || '';
    const formData = new FormData();
    if (fileInput?.files?.[0]) formData.append('file', fileInput.files[0]);
    formData.append('periodo', periodo);
    formData.append('texto', texto);

    if (!fileInput?.files?.[0] && !texto.trim()) {
        gpMessage('Sube un archivo o pega el texto del comunicado mensual.', 'error');
        return;
    }

    gpApi('/calendario/importar', { method: 'POST', body: formData })
        .then(data => {
            gpMessage(data.message || 'Calendario importado.');
            if (fileInput) fileInput.value = '';
            const txt = document.getElementById('gp-importar-calendario-texto');
            if (txt) txt.value = '';
            gpFetchCalendario();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo importar el calendario.', 'error'));
}


function gpSincronizarTalento() {
    fetch(`${backendUrl}/api/talento/sincronizar-global`, { method: 'POST' })
        .then(manejarRespuestaJson)
        .then(data => {
            gpMessage(data.message || 'Sincronizado con Talento Humano.');
            gpCargarEquiposYDocentes();
            gpCargarDashboard();
            if (typeof fetchTalentoIntegracion === 'function') {
                try { fetchTalentoIntegracion(); } catch (_) {}
            }
        })
        .catch(error => gpMessage(error.message || 'No se pudo sincronizar talento humano.', 'error'));
}

function gpImportarTalento() {
    const file = document.getElementById('gp-talento-import-file')?.files?.[0];
    if (!file) {
        gpMessage('Selecciona un archivo de talento humano, agentes educativos o equipo interdisciplinario.', 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    gpApi('/talento/importar', { method: 'POST', body: form })
        .then(data => {
            gpMessage(data.message || 'Talento importado.');
            const input = document.getElementById('gp-talento-import-file');
            if (input) input.value = '';
            gpCargarEquiposYDocentes();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo importar talento.', 'error'));
}

function gpPrepararPlaneacion() {
    gpSetDefaultDates();
    gpFetchCoordinadores(false);
}

function gpSubirPlaneacion() {
    const file = document.getElementById('gp-planeacion-file')?.files?.[0];
    if (!file) {
        gpMessage('Selecciona la planeación pedagógica del mes.', 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    form.append('coordinador_id', document.getElementById('gp-planeacion-coordinador')?.value || '');
    form.append('periodo', document.getElementById('gp-planeacion-periodo')?.value || gpPeriodoActual());
    form.append('tema', document.getElementById('gp-planeacion-tema')?.value || 'Planeación mensual');
    form.append('docente', document.getElementById('gp-planeacion-docente')?.value || '');
    gpApi('/planeacion/upload', { method: 'POST', body: form })
        .then(data => {
            gpMessage(data.message || 'Planeación cargada.');
            ['gp-planeacion-tema','gp-planeacion-docente'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            const input = document.getElementById('gp-planeacion-file');
            if (input) input.value = '';
            gpFetchEntregables();
            gpCargarDashboard();
        })
        .catch(error => gpMessage(error.message || 'No se pudo cargar planeación.', 'error'));
}

