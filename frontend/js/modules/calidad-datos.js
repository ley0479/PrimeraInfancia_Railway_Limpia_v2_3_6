let calidadDatosEstado = {
    ultimo: null,
    resumen: {},
    hallazgos: [],
    historial: [],
    tipoActivo: 'todos'
};

const CD_TIPOS = [
    ['DOCUMENTO_VACIO', 'Documentos vacíos'],
    ['DOCUMENTO_DUPLICADO', 'Documentos duplicados'],
    ['NINO_SIN_UNIDAD', 'Niños sin unidad'],
    ['NINO_SIN_ACUDIENTE', 'Niños sin acudiente'],
    ['NINO_SIN_TELEFONO', 'Niños sin teléfono'],
    ['NINO_SIN_FECHA_NACIMIENTO', 'Sin fecha nacimiento'],
    ['UNIDAD_SIN_DOCENTE', 'Unidades sin agente educativo'],
    ['DOCENTE_SIN_UNIDAD', 'Agentes educativos sin unidad'],
    ['TALENTO_DUPLICADO', 'Talento duplicado'],
    ['EDAD_INCONSISTENTE', 'Edad inconsistente'],
    ['BENEFICIARIO_FUERA_RANGO', 'Fuera de rango']
];

function cdConteoTipo(tipo) {
    const conteos = calidadDatosEstado.resumen?.conteos_tipo || calidadDatosEstado.conteos_tipo || {};
    return Number(conteos[tipo] || 0);
}

function calidadDatosInit() {
    cdCargarDashboard();
    cdCargarHistorial();
}

function cdMostrarMensaje(texto, tipo = 'success') {
    const box = document.getElementById('cd-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.innerText = texto;
    box.classList.remove('hidden');
}

function cdCargarDashboard() {
    fetch(`${backendUrl}/api/calidad-datos/dashboard`)
        .then(manejarRespuestaJson)
        .then((data) => {
            calidadDatosEstado.ultimo = data.ultimo;
            calidadDatosEstado.resumen = data.resumen || {};
            calidadDatosEstado.conteos_tipo = data.conteos_tipo || {};
            cdRenderDashboard();
            if (data.ultimo?.id) cdCargarHallazgos(data.ultimo.id, 'todos');
        })
        .catch((error) => {
            console.error(error);
            cdMostrarMensaje(error.message || 'No se pudo cargar Calidad de Datos.', 'error');
        });
}

function cdRenderDashboard() {
    const cards = document.getElementById('cd-cards');
    if (!cards) return;
    const resumen = calidadDatosEstado.resumen || {};
    const totalRegistros = resumen.total_registros || calidadDatosEstado.ultimo?.total_registros || 0;
    const totalHallazgos = resumen.total_hallazgos || calidadDatosEstado.ultimo?.total_hallazgos || 0;
    const severidad = resumen.conteos || {};

    const principales = [
        ['REGISTROS', 'Registros analizados', totalRegistros, 'text-indigo-300'],
        ['HALLAZGOS', 'Hallazgos totales', totalHallazgos, 'text-amber-300'],
        ['CRITICA', 'Críticos', severidad.CRITICA || 0, 'text-rose-300'],
        ['ALTA', 'Altos', severidad.ALTA || 0, 'text-orange-300'],
        ['MEDIA', 'Medios', severidad.MEDIA || 0, 'text-sky-300'],
        ['BAJA', 'Bajos', severidad.BAJA || 0, 'text-emerald-300']
    ];

    cards.innerHTML = principales.map(([tipo, label, total, color]) => `
        <button type="button" onclick="cdSeleccionarTipo('${tipo === 'REGISTROS' || tipo === 'HALLAZGOS' ? 'todos' : tipo}')" class="cd-card text-left">
            <p class="text-xs uppercase tracking-wide text-slate-500">${label}</p>
            <p class="mt-2 text-3xl font-bold ${color}">${total}</p>
        </button>
    `).join('');

    const issues = document.getElementById('cd-issues');
    if (issues) {
        issues.innerHTML = CD_TIPOS.map(([tipo, label]) => {
            const total = cdConteoTipo(tipo);
            const clase = total > 0 ? 'border-amber-500/30 bg-amber-500/10 text-amber-200' : 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300';
            return `
                <button onclick="cdSeleccionarTipo('${tipo}')" class="rounded-xl border ${clase} px-3 py-2 text-left text-xs transition hover:bg-slate-800">
                    <span class="block font-semibold">${total}</span>
                    <span>${label}</span>
                </button>
            `;
        }).join('');
    }

    const ultimo = document.getElementById('cd-ultimo');
    if (ultimo) {
        if (calidadDatosEstado.ultimo) {
            ultimo.innerHTML = `
                <span class="text-slate-400">Último análisis:</span>
                <span class="text-slate-200 font-medium">#${calidadDatosEstado.ultimo.id}</span>
                <span class="text-slate-500">· ${escaparHtml(calidadDatosEstado.ultimo.nombre_archivo || calidadDatosEstado.ultimo.tipo_fuente || '')}</span>
                <span class="text-slate-500">· ${escaparHtml(fechaPlantillaLegible(calidadDatosEstado.ultimo.fecha_analisis))}</span>
            `;
        } else {
            ultimo.innerHTML = '<span class="text-slate-500">Aún no hay análisis de calidad.</span>';
        }
    }

    const actions = document.getElementById('cd-download-actions');
    if (actions) {
        const id = calidadDatosEstado.ultimo?.id;
        actions.innerHTML = id ? `
            <button onclick="cdDescargar(${id}, 'xlsx')" class="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium text-white">Descargar Excel</button>
            <button onclick="cdDescargar(${id}, 'pdf')" class="rounded-xl bg-rose-600 hover:bg-rose-500 px-4 py-2 text-sm font-medium text-white">Descargar PDF</button>
        ` : '';
    }
}

function cdSeleccionarTipo(tipo) {
    calidadDatosEstado.tipoActivo = tipo || 'todos';
    const id = calidadDatosEstado.ultimo?.id;
    if (id) cdCargarHallazgos(id, calidadDatosEstado.tipoActivo);
}

function cdCargarHallazgos(id, tipo = 'todos') {
    fetch(`${backendUrl}/api/calidad-datos/${encodeURIComponent(id)}/hallazgos/${encodeURIComponent(tipo)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            calidadDatosEstado.hallazgos = data.items || [];
            cdRenderHallazgos();
        })
        .catch((error) => {
            console.error(error);
            cdMostrarMensaje(error.message || 'No se pudieron cargar hallazgos.', 'error');
        });
}

function cdRenderHallazgos() {
    const tbody = document.getElementById('cd-hallazgos-list');
    if (!tbody) return;
    const items = calidadDatosEstado.hallazgos || [];
    if (!items.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-slate-500">Sin hallazgos para este filtro.</td></tr>';
        return;
    }
    tbody.innerHTML = items.slice(0, 500).map((item) => {
        const sev = String(item.severidad || 'MEDIA');
        const sevClass = sev === 'CRITICA' ? 'text-rose-300' : sev === 'ALTA' ? 'text-orange-300' : sev === 'MEDIA' ? 'text-amber-300' : 'text-emerald-300';
        return `
            <tr class="hover:bg-slate-900/50">
                <td class="px-4 py-3 font-medium ${sevClass}">${escaparHtml(sev)}</td>
                <td class="px-4 py-3">${escaparHtml(item.categoria || item.tipo || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.documento || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.nombre || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.unidad || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.docente || '')}</td>
                <td class="px-4 py-3">${escaparHtml(item.campo || '')}</td>
                <td class="px-4 py-3 max-w-sm">${escaparHtml(item.descripcion || '')}</td>
            </tr>
        `;
    }).join('');
}

function cdCargarHistorial() {
    fetch(`${backendUrl}/api/calidad-datos/historial`)
        .then(manejarRespuestaJson)
        .then((data) => {
            calidadDatosEstado.historial = data.historial || [];
            cdRenderHistorial();
        })
        .catch((error) => console.error(error));
}

function cdRenderHistorial() {
    const tbody = document.getElementById('cd-historial-list');
    if (!tbody) return;
    const rows = calidadDatosEstado.historial || [];
    if (!rows.length) {
        tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-8 text-center text-slate-500">Sin historial de análisis.</td></tr>';
        return;
    }
    tbody.innerHTML = rows.map((row) => `
        <tr class="hover:bg-slate-900/50">
            <td class="px-4 py-3">#${row.id}</td>
            <td class="px-4 py-3">${escaparHtml(row.nombre_archivo || row.tipo_fuente || '')}</td>
            <td class="px-4 py-3">${escaparHtml(row.total_registros || 0)}</td>
            <td class="px-4 py-3">${escaparHtml(row.total_hallazgos || 0)}</td>
            <td class="px-4 py-3">${escaparHtml(fechaPlantillaLegible(row.fecha_analisis))}</td>
            <td class="px-4 py-3">${escaparHtml(row.usuario || '')}</td>
            <td class="px-4 py-3 flex gap-2">
                <button onclick="cdAbrirAnalisis(${row.id})" class="rounded-lg border border-indigo-500/30 px-3 py-1 text-xs text-indigo-300">Ver</button>
                <button onclick="cdDescargar(${row.id}, 'xlsx')" class="rounded-lg border border-emerald-500/30 px-3 py-1 text-xs text-emerald-300">Excel</button>
                <button onclick="cdDescargar(${row.id}, 'pdf')" class="rounded-lg border border-rose-500/30 px-3 py-1 text-xs text-rose-300">PDF</button>
            </td>
        </tr>
    `).join('');
}

function cdAbrirAnalisis(id) {
    fetch(`${backendUrl}/api/calidad-datos/${encodeURIComponent(id)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            calidadDatosEstado.ultimo = data.analisis;
            calidadDatosEstado.resumen = data.analisis?.resumen || {};
            calidadDatosEstado.hallazgos = data.hallazgos || [];
            cdRenderDashboard();
            cdRenderHallazgos();
            document.getElementById('cd-hallazgos-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
        })
        .catch((error) => cdMostrarMensaje(error.message || 'No se pudo abrir el análisis.', 'error'));
}

function cdAnalizarArchivo() {
    const input = document.getElementById('cd-input-file');
    const file = input?.files?.[0];
    if (!file) {
        cdMostrarMensaje('Selecciona un archivo para analizar.', 'error');
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    formData.append('tipo', document.getElementById('cd-tipo')?.value || 'auto');
    formData.append('mes', document.getElementById('cd-mes')?.value || new Date().getMonth() + 1);
    formData.append('anio', document.getElementById('cd-anio')?.value || new Date().getFullYear());

    cdMostrarMensaje('Analizando calidad de datos...', 'success');
    fetch(`${backendUrl}/api/calidad-datos/analizar`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            cdMostrarMensaje(data.message || 'Análisis generado correctamente.', 'success');
            input.value = '';
            calidadDatosEstado.ultimo = { id: data.analisis_id, total_registros: data.resumen?.total_registros, total_hallazgos: data.resumen?.total_hallazgos };
            calidadDatosEstado.resumen = data.resumen || {};
            calidadDatosEstado.hallazgos = data.hallazgos || [];
            cdRenderDashboard();
            cdRenderHallazgos();
            cdCargarHistorial();
        })
        .catch((error) => cdMostrarMensaje(error.message || 'No se pudo analizar el archivo.', 'error'));
}

function cdAnalizarBaseActual() {
    const formData = new FormData();
    formData.append('fuente', 'base_actual');
    formData.append('tipo', 'base_actual');
    formData.append('mes', document.getElementById('cd-mes')?.value || new Date().getMonth() + 1);
    formData.append('anio', document.getElementById('cd-anio')?.value || new Date().getFullYear());

    cdMostrarMensaje('Analizando base actual del sistema...', 'success');
    fetch(`${backendUrl}/api/calidad-datos/analizar`, { method: 'POST', body: formData })
        .then(manejarRespuestaJson)
        .then((data) => {
            cdMostrarMensaje(data.message || 'Análisis generado correctamente.', 'success');
            calidadDatosEstado.ultimo = { id: data.analisis_id, total_registros: data.resumen?.total_registros, total_hallazgos: data.resumen?.total_hallazgos };
            calidadDatosEstado.resumen = data.resumen || {};
            calidadDatosEstado.hallazgos = data.hallazgos || [];
            cdRenderDashboard();
            cdRenderHallazgos();
            cdCargarHistorial();
        })
        .catch((error) => cdMostrarMensaje(error.message || 'No se pudo analizar la base actual.', 'error'));
}

function cdDescargar(id, formato) {
    if (!id) return;
    window.descargarArchivoAutenticado(`${backendUrl}/api/calidad-datos/${encodeURIComponent(id)}/descargar/${encodeURIComponent(formato)}`).catch((error) => cdMostrarMensaje(error.message, 'error'));
}

window.calidadDatosInit = calidadDatosInit;
