/*
Módulo independiente Salud y Nutrición Inteligente.
Depende únicamente de backendUrl y utilidades básicas existentes en app.js.
*/
let snEstado = {
    inicializado: false,
    dashboard: null,
    alertas: [],
    calendario: []
};

function snMensaje(texto, tipo = 'success') {
    const box = document.getElementById('sn-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.innerText = texto;
    box.classList.remove('hidden');
}

function snInit() {
    if (!snEstado.inicializado) {
        snEstado.inicializado = true;
        snCargarDashboard();
    }
    lucide.createIcons();
}

function snMostrarVista(vista) {
    ['dashboard', 'importar', 'cruce', 'historial', 'alertas', 'calendario', 'entregables'].forEach((id) => {
        const el = document.getElementById(`sn-view-${id}`);
        if (el) el.classList.toggle('hidden', id !== vista);
    });
    document.querySelectorAll('[data-sn-tab]').forEach((tab) => {
        tab.classList.toggle('active', tab.getAttribute('data-sn-tab') === vista);
    });
    if (vista === 'dashboard') snCargarDashboard();
    if (vista === 'alertas') snCargarAlertas();
    if (vista === 'calendario') snCargarCalendario();
    if (vista === 'entregables' && typeof snEntregablesInit === 'function') snEntregablesInit();
}

function snBadge(nivel, texto) {
    const n = String(nivel || '').toUpperCase();
    const clase = n === 'ROJO' ? 'sn-badge-rojo' : n === 'AMARILLO' ? 'sn-badge-amarillo' : 'sn-badge-verde';
    return `<span class="sn-badge ${clase}">${escaparHtml(texto || nivel || '')}</span>`;
}

function snRenderDistribucion(contenedorId, data) {
    const cont = document.getElementById(contenedorId);
    if (!cont) return;
    const items = Object.entries(data || {}).sort((a, b) => b[1] - a[1]);
    const total = items.reduce((sum, item) => sum + Number(item[1] || 0), 0);
    if (!items.length) {
        cont.innerHTML = '<p class="text-slate-500">Sin datos.</p>';
        return;
    }
    cont.innerHTML = items.map(([nombre, valor]) => {
        const pct = total ? Math.round((Number(valor) / total) * 100) : 0;
        return `
            <div>
                <div class="mb-1 flex items-center justify-between gap-3">
                    <span class="truncate text-slate-300">${escaparHtml(nombre)}</span>
                    <span class="text-xs text-slate-500">${valor} · ${pct}%</span>
                </div>
                <div class="sn-bar text-cyan-400"><span style="width:${pct}%"></span></div>
            </div>
        `;
    }).join('');
}

function snRenderCasos(rows) {
    const tbody = document.getElementById('sn-dashboard-casos');
    if (!tbody) return;
    const data = Array.isArray(rows) ? rows.slice(0, 120) : [];
    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-slate-500">Sin datos cargados.</td></tr>';
        return;
    }
    tbody.innerHTML = data.map((item) => `
        <tr>
            <td>${escaparHtml(item.unidad || '')}</td>
            <td class="font-medium text-slate-200">${escaparHtml(item.nombre_completo || '')}</td>
            <td>${escaparHtml(item.documento || '')}</td>
            <td>${escaparHtml(item.edad_texto || '')}</td>
            <td>${escaparHtml(item.peso_kg ?? '')}</td>
            <td>${escaparHtml(item.talla_cm ?? '')}</td>
            <td>${snBadge(item.nivel_alerta, item.diagnostico_global || 'Pendiente')}</td>
            <td>${escaparHtml(item.estado_control || '')}</td>
            <td>${escaparHtml(item.proximo_control || '')}</td>
        </tr>
    `).join('');
}

function snCargarDashboard() {
    fetch(`${backendUrl}/api/salud-nutricion/dashboard`)
        .then(manejarRespuestaJson)
        .then((data) => {
            snEstado.dashboard = data;
            document.getElementById('sn-stat-total').innerText = data.total_usuarios || 0;
            document.getElementById('sn-stat-valorados').innerText = data.total_valorados || 0;
            document.getElementById('sn-stat-pendientes').innerText = data.total_pendientes || 0;
            document.getElementById('sn-stat-criticos').innerText = data.casos_criticos || 0;
            document.getElementById('sn-stat-seguimiento').innerText = data.casos_seguimiento || 0;
            document.getElementById('sn-stat-cumplimiento').innerText = `${data.cumplimiento || 0}%`;
            snRenderDistribucion('sn-chart-diagnostico', data.por_diagnostico || {});
            snRenderDistribucion('sn-chart-control', data.por_estado_control || {});
            snRenderCasos(data.ultimos_casos || []);
            lucide.createIcons();
        })
        .catch((error) => snMensaje(error.message || 'No se pudo cargar dashboard nutricional.', 'error'));
}

function snImportarValoraciones() {
    const input = document.getElementById('sn-input-valoraciones');
    const file = input?.files?.[0];
    if (!file) {
        snMensaje('Selecciona un archivo de salud y nutrición.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('usuario', document.getElementById('sn-import-usuario')?.value || 'sistema');
    mostrarCargando('Importando salud y nutrición...');
    fetch(`${backendUrl}/api/salud-nutricion/importar`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snMensaje(data.message || 'Importación realizada.', 'success');
            if (input) input.value = '';
            snCargarDashboard();
        })
        .catch((error) => {
            ocultarCargando();
            snMensaje(error.message || 'No se pudo importar.', 'error');
        });
}

function snImportarReferencias() {
    const input = document.getElementById('sn-input-referencias');
    const file = input?.files?.[0];
    if (!file) {
        snMensaje('Selecciona un archivo de referencias OMS/ICBF.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    mostrarCargando('Importando referencias OMS/ICBF...');
    fetch(`${backendUrl}/api/salud-nutricion/referencias/importar`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snMensaje(data.message || 'Referencias importadas.', 'success');
            input.value = '';
        })
        .catch((error) => {
            ocultarCargando();
            snMensaje(error.message || 'No se pudieron importar referencias.', 'error');
        });
}

function snCompararBases() {
    const anterior = document.getElementById('sn-base-anterior')?.files?.[0];
    const actual = document.getElementById('sn-base-actual')?.files?.[0];
    if (!anterior || !actual) {
        snMensaje('Carga base anterior y base actual.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('base_anterior', anterior);
    formData.append('base_actual', actual);
    mostrarCargando('Comparando bases de datos...');
    fetch(`${backendUrl}/api/salud-nutricion/comparar`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snMensaje(data.message || 'Comparación generada.', 'success');
            snRenderComparacion(data);
        })
        .catch((error) => {
            ocultarCargando();
            snMensaje(error.message || 'No se pudo comparar.', 'error');
        });
}

function snRenderComparacion(data) {
    const cont = document.getElementById('sn-comparacion-resultado');
    if (!cont) return;
    const r = data.resumen || {};
    cont.classList.remove('hidden');
    cont.innerHTML = `
        <h3 class="font-semibold mb-3">Resultado de comparación</h3>
        <div class="grid gap-3 md:grid-cols-6 mb-4">
            <div class="sn-card"><p class="text-xs text-slate-500">Anterior</p><p class="text-2xl font-bold">${r.total_anterior || 0}</p></div>
            <div class="sn-card"><p class="text-xs text-slate-500">Actual</p><p class="text-2xl font-bold">${r.total_actual || 0}</p></div>
            <div class="sn-card"><p class="text-xs text-slate-500">Nuevos</p><p class="text-2xl font-bold">${r.nuevos || 0}</p></div>
            <div class="sn-card"><p class="text-xs text-slate-500">Retirados</p><p class="text-2xl font-bold">${r.retirados || 0}</p></div>
            <div class="sn-card"><p class="text-xs text-slate-500">Traslados</p><p class="text-2xl font-bold">${r.trasladados || 0}</p></div>
            <div class="sn-card"><p class="text-xs text-slate-500">Cambios</p><p class="text-2xl font-bold">${r.cambios || 0}</p></div>
        </div>
        <div class="flex flex-wrap gap-2">
            ${data.reporte_excel ? `<button onclick="snDescargarReporte('${escaparHtml(data.reporte_excel)}')" class="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium text-white">Descargar Excel</button>` : ''}
            ${data.reporte_pdf ? `<button onclick="snDescargarReporte('${escaparHtml(data.reporte_pdf)}')" class="rounded-xl bg-rose-600 hover:bg-rose-500 px-4 py-2 text-sm font-medium text-white">Descargar PDF</button>` : ''}
        </div>
    `;
}

function snBuscarFicha() {
    const doc = document.getElementById('sn-ficha-documento')?.value?.trim();
    const cont = document.getElementById('sn-ficha-resultado');
    if (!doc) {
        snMensaje('Escribe un documento/NUI.', 'error');
        return;
    }
    fetch(`${backendUrl}/api/salud-nutricion/ficha/${encodeURIComponent(doc)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            if (!cont) return;
            cont.classList.remove('hidden');
            const b = data.beneficiario || {};
            const historial = data.historial || [];
            cont.innerHTML = `
                <h3 class="font-semibold mb-2">${escaparHtml(b.nombre_completo || '')}</h3>
                <p class="text-sm text-slate-400 mb-4">${escaparHtml(b.documento || '')} · ${escaparHtml(b.unidad || '')} · ${escaparHtml(b.edad_texto || '')}</p>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs sn-table text-slate-400">
                        <thead><tr><th>Fecha</th><th>Peso</th><th>Talla</th><th>IMC</th><th>PB</th><th>Diagnóstico</th><th>Control</th><th>Próximo</th></tr></thead>
                        <tbody>${historial.map((h) => `
                            <tr>
                                <td>${escaparHtml(h.fecha_valoracion || '')}</td>
                                <td>${escaparHtml(h.peso_kg ?? '')}</td>
                                <td>${escaparHtml(h.talla_cm ?? '')}</td>
                                <td>${escaparHtml(h.imc ?? '')}</td>
                                <td>${escaparHtml(h.perimetro_braquial_cm ?? '')}</td>
                                <td>${snBadge(h.nivel_alerta, h.diagnostico_global || 'Pendiente')}</td>
                                <td>${escaparHtml(h.estado_control || '')}</td>
                                <td>${escaparHtml(h.proximo_control || '')}</td>
                            </tr>
                        `).join('')}</tbody>
                    </table>
                </div>
            `;
        })
        .catch((error) => snMensaje(error.message || 'No se encontró ficha.', 'error'));
}

function snCargarAlertas() {
    fetch(`${backendUrl}/api/salud-nutricion/alertas?atendida=0`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const tbody = document.getElementById('sn-alertas-list');
            const alertas = data.alertas || [];
            if (!tbody) return;
            if (!alertas.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="text-center text-slate-500">Sin alertas pendientes.</td></tr>';
                return;
            }
            tbody.innerHTML = alertas.map((a) => `
                <tr>
                    <td>${snBadge(a.nivel, a.nivel)}</td>
                    <td>${escaparHtml(a.tipo || '')}</td>
                    <td>${escaparHtml(a.documento || '')}</td>
                    <td>${escaparHtml(a.unidad || '')}</td>
                    <td>${escaparHtml(a.mensaje || '')}</td>
                    <td>${escaparHtml(a.fecha_creacion || '')}</td>
                    <td><button onclick="snAtenderAlerta(${Number(a.id)})" class="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-2 py-1 text-xs text-white">Atender</button></td>
                </tr>
            `).join('');
        })
        .catch((error) => snMensaje(error.message || 'No se pudieron cargar alertas.', 'error'));
}

function snAtenderAlerta(id) {
    fetch(`${backendUrl}/api/salud-nutricion/alertas/${encodeURIComponent(id)}/atender`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ observaciones: 'Atendida desde dashboard' })
    })
        .then(manejarRespuestaJson)
        .then(() => snCargarAlertas())
        .catch((error) => snMensaje(error.message || 'No se pudo atender alerta.', 'error'));
}

function snCargarCalendario() {
    fetch(`${backendUrl}/api/salud-nutricion/calendario`)
        .then(manejarRespuestaJson)
        .then((data) => {
            const cont = document.getElementById('sn-calendario-list');
            const eventos = data.eventos || [];
            if (!cont) return;
            if (!eventos.length) {
                cont.innerHTML = '<p class="text-slate-500">Sin eventos nutricionales programados.</p>';
                return;
            }
            cont.innerHTML = eventos.slice(0, 200).map((e) => `
                <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
                    <div class="flex items-start justify-between gap-3">
                        <div>
                            <p class="text-sm font-semibold text-slate-200">${escaparHtml(e.fecha || '')}</p>
                            <p class="mt-1 text-xs text-slate-400">${escaparHtml(e.tipo || '')}</p>
                        </div>
                        ${snBadge(e.nivel, e.nivel)}
                    </div>
                    <p class="mt-3 text-sm text-slate-300">${escaparHtml(e.nombre || '')}</p>
                    <p class="mt-1 text-xs text-slate-500">${escaparHtml(e.unidad || '')}</p>
                    <p class="mt-2 text-xs text-slate-400">${escaparHtml(e.descripcion || '')}</p>
                </div>
            `).join('');
        })
        .catch((error) => snMensaje(error.message || 'No se pudo cargar calendario nutricional.', 'error'));
}

function snGenerarReporte(formato = 'excel') {
    fetch(`${backendUrl}/api/salud-nutricion/reportes/dashboard?formato=${encodeURIComponent(formato)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            snMensaje(data.message || 'Reporte generado.', 'success');
            if (data.archivo) snDescargarReporte(data.archivo);
        })
        .catch((error) => snMensaje(error.message || 'No se pudo generar reporte.', 'error'));
}

function snDescargarReporte(nombre) {
    window.descargarArchivoAutenticado(`${backendUrl}/api/salud-nutricion/reportes/${encodeURIComponent(nombre)}`).catch((error) => snMensaje(error.message, 'error'));
}
