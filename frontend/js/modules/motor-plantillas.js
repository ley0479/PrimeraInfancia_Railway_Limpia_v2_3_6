let mpTemplates = [];
let mpSelectedTemplate = null;
let mpDetection = null;
let mpCampos = [];
let mpLastMapping = [];
let mpLastDownload = null;
let mpSelectedVersion = null;
let mpProducts = [];

function mpMsg(texto, tipo = 'info') {
    const el = document.getElementById('mp-message');
    if (!el) return;
    const cls = tipo === 'error'
        ? 'mp-risk'
        : tipo === 'ok'
            ? 'mp-ok'
            : 'mp-warning';
    el.className = `mt-3 ${cls}`;
    el.textContent = texto;
}

function mpFieldOptions(selected = '') {
    const base = ['<option value="ignorar">Ignorar / No mapear</option>'];
    (mpCampos || []).forEach((campo) => {
        base.push(`<option value="${escaparHtml(campo.id)}" ${campo.id === selected ? 'selected' : ''}>${escaparHtml(campo.label)}</option>`);
    });
    return base.join('');
}

function motorPlantillasInit() {
    mpCargarCampos();
    mpCargarPlantillas();
    if (typeof mpCargarMinutasRpp === 'function') mpCargarMinutasRpp();
    if (typeof mpCargarRamV3Estado === 'function') mpCargarRamV3Estado();
    if (typeof mpCargarInstruccionesRamV3 === 'function') mpCargarInstruccionesRamV3();
}

async function mpCargarCampos() {
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/campos`).then(manejarRespuestaJson);
        mpCampos = data.campos || [];
    } catch (error) {
        console.error('No se pudieron cargar campos del motor de plantillas', error);
    }
}

async function mpCargarPlantillas() {
    const lista = document.getElementById('mp-plantillas-list');
    if (lista) lista.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">Cargando plantillas...</td></tr>';
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas`).then(manejarRespuestaJson);
        mpTemplates = data.plantillas || [];
        mpRenderPlantillas();
        const dash = await fetch(`${backendUrl}/api/motor-plantillas/dashboard`).then(manejarRespuestaJson);
        mpRenderDashboard(dash);
    } catch (error) {
        if (lista) lista.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-rose-400">${escaparHtml(error.message || 'Error cargando plantillas')}</td></tr>`;
    }
}

function mpRenderDashboard(data = {}) {
    const container = document.getElementById('mp-dashboard');
    if (!container) return;
    container.innerHTML = `
        <div class="mp-card"><p class="text-xs text-slate-400">Plantillas</p><h3 class="text-2xl font-bold text-indigo-300">${Number(data.plantillas || 0)}</h3></div>
        <div class="mp-card"><p class="text-xs text-slate-400">Mapeadas</p><h3 class="text-2xl font-bold text-emerald-300">${Number(data.plantillas_mapeadas || 0)}</h3></div>
        <div class="mp-card"><p class="text-xs text-slate-400">Pruebas</p><h3 class="text-2xl font-bold text-cyan-300">${Number(data.pruebas || 0)}</h3></div>
        <div class="mp-card"><p class="text-xs text-slate-400">Errores prueba</p><h3 class="text-2xl font-bold text-rose-300">${Number(data.pruebas_error || 0)}</h3></div>
    `;
}

function mpRenderPlantillas() {
    const lista = document.getElementById('mp-plantillas-list');
    if (!lista) return;
    if (!mpTemplates.length) {
        lista.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">No hay plantillas registradas en el motor.</td></tr>';
        return;
    }
    lista.innerHTML = mpTemplates.map((item) => `
        <tr class="hover:bg-slate-900/60">
            <td class="px-4 py-3 font-medium text-slate-200">${escaparHtml(item.nombre || item.nombre_original || '')}</td>
            <td class="px-4 py-3">${escaparHtml(item.tipo || '')}</td>
            <td class="px-4 py-3">${escaparHtml(item.version || '1.0')}</td>
            <td class="px-4 py-3">${escaparHtml(item.hoja_principal || '')}</td>
            <td class="px-4 py-3"><span class="mp-state mp-state-${escaparHtml(String(item.estado || 'BORRADOR').toLowerCase())}">${escaparHtml(item.estado || 'BORRADOR')}</span></td>
            <td class="px-4 py-3">
                <div class="flex flex-wrap gap-1">
                    <button onclick="mpSeleccionarPlantilla(${Number(item.id)})" class="rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-xs text-white">Detectar / mapear</button>
                    ${['RPP', 'RAM', 'BIENESTARINA'].includes(String(item.tipo || '').toUpperCase()) && item.plantilla_oficial_version_id ? `<button onclick="mpMarcarVigente(${Number(item.plantilla_oficial_version_id)})" class="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-xs text-white">Activar versión</button>` : ''}
                </div>
            </td>
        </tr>
    `).join('');
}

async function mpSubirPlantilla() {
    const file = document.getElementById('mp-file')?.files?.[0];
    const tipo = document.getElementById('mp-tipo')?.value || 'OTROS';
    const version = document.getElementById('mp-version')?.value || '1.0';
    const codigo = document.getElementById('mp-codigo')?.value || '';
    const fechaVigencia = document.getElementById('mp-fecha-vigencia')?.value || '';
    const observaciones = document.getElementById('mp-observaciones')?.value || '';
    if (!file) {
        mpMsg('Selecciona una plantilla oficial Excel.', 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    form.append('tipo', tipo);
    form.append('version', version);
    form.append('codigo', codigo);
    form.append('fecha_vigencia', fechaVigencia);
    form.append('observaciones', observaciones);
    try {
        mpMsg('Subiendo y detectando columnas...', 'warn');
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas`, { method: 'POST', body: form }).then(manejarRespuestaJson);
        mpMsg(data.message || 'Plantilla cargada.', 'ok');
        await mpCargarPlantillas();
        if (data.version_id) mpSelectedVersion = Number(data.version_id);
        if (data.plantilla_id) await mpSeleccionarPlantilla(data.plantilla_id);
    } catch (error) {
        mpMsg(error.message || 'No se pudo subir la plantilla.', 'error');
    }
}

async function mpSeleccionarPlantilla(id) {
    mpSelectedTemplate = id;
    mpLastDownload = null;
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${id}/detectar`).then(manejarRespuestaJson);
        mpDetection = data.deteccion || {};
        mpCampos = data.campos || mpCampos;
        document.getElementById('mp-selected-title').textContent = data.plantilla?.nombre || data.plantilla?.nombre_original || `Plantilla ${id}`;
        mpRenderDetection();
        const mapeo = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${id}/mapeo`).then(manejarRespuestaJson);
        if (mapeo?.mapeo?.mapeo?.length) {
            mpAplicarMapeoGuardado(mapeo.mapeo.mapeo);
        }
        await mpCargarVersionPlantilla(id);
    } catch (error) {
        mpMsg(error.message || 'No se pudo detectar la plantilla.', 'error');
    }
}


async function mpCargarVersionPlantilla(id) {
    mpSelectedVersion = null;
    mpProducts = [];
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${id}/versiones`).then(manejarRespuestaJson);
        const versiones = data.versiones || [];
        const propia = versiones.find(v => Number(v.mp_plantilla_id || 0) === Number(id)) || versiones[0];
        if (propia) {
            mpSelectedVersion = Number(propia.id);
            const prod = await fetch(`${backendUrl}/api/motor-plantillas/version/${mpSelectedVersion}/productos`).then(manejarRespuestaJson).catch(() => ({ productos: [] }));
            mpProducts = prod.productos || [];
        }
    } catch (error) {
        console.warn('No se pudo cargar versión ALPHA52', error);
    }
    mpRenderProducts();
}

function mpRenderProducts() {
    const panel = document.getElementById('mp-products-panel');
    if (!panel) return;
    if (!mpSelectedTemplate) {
        panel.innerHTML = '<div class="mp-warning">Selecciona una plantilla RPP para configurar productos.</div>';
        return;
    }
    const rows = (mpProducts.length ? mpProducts : []).map((item, idx) => mpProductRow(item, idx)).join('');
    panel.innerHTML = `
        <div class="overflow-x-auto">
            <table class="mp-table">
                <thead><tr><th>Producto</th><th>Columna</th><th>Unidad</th><th>Cantidad</th><th>Grupo etario</th><th>Orden</th><th></th></tr></thead>
                <tbody id="mp-products-list">${rows || '<tr><td colspan="7" class="text-center text-slate-500 py-4">Sin productos configurados para esta versión.</td></tr>'}</tbody>
            </table>
        </div>
    `;
}

function mpProductRow(item = {}, idx = 0) {
    return `
        <tr data-product-idx="${idx}">
            <td><input class="mp-input mp-prod-name" value="${escaparHtml(item.nombre_producto || item.nombre || '')}" placeholder="Ej. Arroz" /></td>
            <td><input class="mp-input mp-prod-col" value="${escaparHtml(item.columna || '')}" placeholder="Ej. H" /></td>
            <td><input class="mp-input mp-prod-unit" value="${escaparHtml(item.unidad_medida || item.unidad || '')}" placeholder="Ej. libras" /></td>
            <td><input class="mp-input mp-prod-qty" value="${escaparHtml(item.cantidad || '')}" placeholder="Ej. 2" /></td>
            <td><input class="mp-input mp-prod-group" value="${escaparHtml(item.grupo_etario_aplica || 'todos')}" /></td>
            <td><input class="mp-input mp-prod-order" type="number" value="${Number(item.orden || idx + 1)}" /></td>
            <td><button onclick="mpEliminarProducto(${idx})" class="rounded-lg border border-rose-500/40 px-2 py-1 text-xs text-rose-200">Quitar</button></td>
        </tr>
    `;
}

function mpAgregarProducto() {
    mpProducts.push({ nombre_producto: '', columna: '', unidad_medida: '', cantidad: '', grupo_etario_aplica: 'todos', orden: mpProducts.length + 1, activo: 1 });
    mpRenderProducts();
}

function mpEliminarProducto(idx) {
    mpProducts.splice(idx, 1);
    mpRenderProducts();
}

function mpRecolectarProductos() {
    const rows = Array.from(document.querySelectorAll('#mp-products-list tr[data-product-idx]'));
    return rows.map((row, idx) => ({
        nombre_producto: row.querySelector('.mp-prod-name')?.value?.trim() || '',
        columna: row.querySelector('.mp-prod-col')?.value?.trim().toUpperCase() || '',
        unidad_medida: row.querySelector('.mp-prod-unit')?.value?.trim() || '',
        cantidad: row.querySelector('.mp-prod-qty')?.value?.trim() || '',
        grupo_etario_aplica: row.querySelector('.mp-prod-group')?.value?.trim() || 'todos',
        orden: Number(row.querySelector('.mp-prod-order')?.value || idx + 1),
        activo: 1
    })).filter(p => p.nombre_producto);
}

async function mpGuardarProductos() {
    if (!mpSelectedVersion) return mpMsg('Selecciona una versión de plantilla primero.', 'error');
    const productos = mpRecolectarProductos();
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/version/${mpSelectedVersion}/productos`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ productos })
        }).then(manejarRespuestaJson);
        mpProducts = data.productos || productos;
        mpRenderProducts();
        mpMsg(data.message || 'Productos guardados.', 'ok');
    } catch (error) {
        mpMsg(error.message || 'No se pudieron guardar productos.', 'error');
    }
}

async function mpMarcarVigente(versionId = null) {
    const id = Number(versionId || mpSelectedVersion || 0);
    if (!id) return mpMsg('Selecciona una versión probada para marcar vigente.', 'error');
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/version/${id}/vigente`, { method: 'POST' }).then(manejarRespuestaJson);
        mpMsg(data.message || 'Plantilla marcada como vigente.', 'ok');
        await mpCargarPlantillas();
    } catch (error) {
        mpMsg(error.message || 'No se pudo marcar vigente.', 'error');
    }
}

async function mpRollback(tipo = 'RPP') {
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/${encodeURIComponent(tipo)}/rollback`, { method: 'POST' }).then(manejarRespuestaJson);
        mpMsg(data.message || 'Rollback realizado.', 'ok');
        await mpCargarPlantillas();
    } catch (error) {
        mpMsg(error.message || 'No se pudo hacer rollback.', 'error');
    }
}

function mpRenderDetection() {
    const panel = document.getElementById('mp-detection-panel');
    if (!panel) return;
    const columnas = mpDetection?.columnas || [];
    const riesgos = mpDetection?.riesgos || [];
    if (!columnas.length) {
        panel.innerHTML = '<div class="mp-warning">No se detectaron columnas reconocibles. Revisa que la plantilla tenga encabezados legibles.</div>';
        return;
    }
    const rows = columnas.map((col, idx) => `
        <tr data-mp-row="${idx}">
            <td>${escaparHtml(col.sheet)}</td>
            <td>${escaparHtml(col.cell)}</td>
            <td class="text-slate-200">${escaparHtml(col.label)}</td>
            <td><select class="mp-input mp-field-select" data-idx="${idx}">${mpFieldOptions(col.suggested_field || 'ignorar')}</select></td>
            <td><input class="mp-input mp-start-row" type="number" min="${Number(col.row)+1}" value="${Number(col.data_start_row || col.row + 1)}" data-idx="${idx}" /></td>
        </tr>
    `).join('');
    panel.innerHTML = `
        <div class="grid gap-3 md:grid-cols-3 mb-4">
            <div class="mp-ok">Columnas detectadas: ${columnas.length}</div>
            <div class="mp-warning">Riesgos de alimento/cantidad: ${riesgos.length}</div>
            <div class="mp-panel p-3 text-xs text-slate-400">Regla: no se insertan filas, no se mueven hojas y no se tocan encabezados oficiales.</div>
        </div>
        <div class="overflow-x-auto mp-panel">
            <table class="mp-table">
                <thead><tr><th>Hoja</th><th>Celda encabezado</th><th>Texto detectado</th><th>Campo dinámico</th><th>Fila inicial de datos</th></tr></thead>
                <tbody>${rows}</tbody>
            </table>
        </div>
        <div class="mt-4 flex flex-wrap gap-2">
            <button onclick="mpValidarMapeo()" class="rounded-xl bg-cyan-600 hover:bg-cyan-500 px-4 py-2 text-sm text-white">Validar antes de guardar</button>
            <button onclick="mpGuardarMapeo()" class="rounded-xl bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm text-white">Guardar configuración</button>
        </div>
    `;
}

function mpRecolectarMapeo() {
    const columnas = mpDetection?.columnas || [];
    return columnas.map((col, idx) => {
        const field = document.querySelector(`.mp-field-select[data-idx="${idx}"]`)?.value || 'ignorar';
        const dataStart = Number(document.querySelector(`.mp-start-row[data-idx="${idx}"]`)?.value || (Number(col.row) + 1));
        return {
            field,
            sheet: col.sheet,
            row: Number(col.row),
            col: Number(col.col),
            col_letter: col.col_letter,
            cell: col.cell,
            label: col.label,
            data_start_row: dataStart
        };
    }).filter((item) => item.field && item.field !== 'ignorar');
}

function mpAplicarMapeoGuardado(mapping) {
    const columnas = mpDetection?.columnas || [];
    mapping.forEach((saved) => {
        const idx = columnas.findIndex((col) => col.sheet === saved.sheet && Number(col.row) === Number(saved.row) && Number(col.col) === Number(saved.col));
        if (idx >= 0) {
            const sel = document.querySelector(`.mp-field-select[data-idx="${idx}"]`);
            const start = document.querySelector(`.mp-start-row[data-idx="${idx}"]`);
            if (sel) sel.value = saved.field || 'ignorar';
            if (start) start.value = saved.data_start_row || saved.dataStartRow || Number(saved.row) + 1;
        }
    });
}

function mpRenderValidacion(validacion) {
    const out = document.getElementById('mp-validation-result');
    if (!out) return;
    const errores = validacion?.errores || [];
    const advertencias = validacion?.advertencias || [];
    if (!errores.length && !advertencias.length) {
        out.innerHTML = '<div class="mp-ok">Validación correcta. No se detectaron riesgos críticos.</div>';
        return;
    }
    out.innerHTML = `
        ${errores.map((e) => `<div class="mp-risk mb-2"><strong>${escaparHtml(e.code || 'ERROR')}:</strong> ${escaparHtml(e.message || '')}</div>`).join('')}
        ${advertencias.map((e) => `<div class="mp-warning mb-2"><strong>${escaparHtml(e.code || 'ADVERTENCIA')}:</strong> ${escaparHtml(e.message || '')}</div>`).join('')}
    `;
}

async function mpValidarMapeo() {
    if (!mpSelectedTemplate) return mpMsg('Selecciona una plantilla primero.', 'error');
    const mapping = mpRecolectarMapeo();
    mpLastMapping = mapping;
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${mpSelectedTemplate}/validar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping, strict: true })
        }).then(manejarRespuestaJson);
        mpRenderValidacion(data.validacion);
    } catch (error) {
        mpMsg(error.message || 'No se pudo validar.', 'error');
    }
}

async function mpGuardarMapeo() {
    if (!mpSelectedTemplate) return mpMsg('Selecciona una plantilla primero.', 'error');
    const mapping = mpRecolectarMapeo();
    mpLastMapping = mapping;
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${mpSelectedTemplate}/mapeo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping, nombre: 'Mapeo principal', version: '1.0' })
        }).then(manejarRespuestaJson);
        mpRenderValidacion(data.validacion);
        mpMsg(data.message || 'Mapeo guardado.', 'ok');
    } catch (error) {
        mpMsg(error.message || 'No se pudo guardar el mapeo.', 'error');
        try {
            const detail = JSON.parse(error.message);
            mpRenderValidacion(detail.validacion);
        } catch (_) {}
    }
}

async function mpProbarUnidad() {
    if (!mpSelectedTemplate) return mpMsg('Selecciona una plantilla primero.', 'error');
    const unidad = document.getElementById('mp-unidad-prueba')?.value?.trim();
    const limite = Number(document.getElementById('mp-limite-prueba')?.value || 20);
    if (!unidad) return mpMsg('Escribe una unidad para probar.', 'error');
    const mapping = mpRecolectarMapeo();
    const productos = mpRecolectarProductos();
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/plantillas/${mpSelectedTemplate}/probar-unidad`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ unidad, limite, mapping, productos })
        }).then(manejarRespuestaJson);
        const out = document.getElementById('mp-test-result');
        mpLastDownload = data.download_url ? `${backendUrl}${data.download_url}` : null;
        if (out) {
            out.innerHTML = `
                <div class="${data.resultado?.ok ? 'mp-ok' : 'mp-risk'}">
                    ${escaparHtml(data.message || '')}<br>
                    Usuarios usados: ${Number(data.resultado?.total_usuarios || 0)}
                    ${data.download_url ? `<br><button onclick="mpDescargarPrueba()" class="mt-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 px-3 py-1.5 text-xs text-white">Descargar prueba generada</button>` : ''}
                </div>
            `;
        }
    } catch (error) {
        mpMsg(error.message || 'No se pudo probar con la unidad.', 'error');
    }
}

function mpDescargarPrueba() {
    if (mpLastDownload) window.descargarArchivoAutenticado(mpLastDownload).catch((error) => mpMsg(error.message, 'error'));
}
// ===== ALPHA53 — Minutas RPP Versionadas =====
async function mpCargarMinutasRpp() {
    const panel = document.getElementById('mp-minutas-panel');
    if (panel) panel.innerHTML = '<div class="p-4 text-sm text-slate-500">Cargando minutas RPP...</div>';
    const mes = document.getElementById('mp-minuta-mes')?.value || '';
    const anio = document.getElementById('mp-minuta-anio')?.value || '';
    const qs = new URLSearchParams();
    if (mes) qs.set('mes', mes);
    if (anio) qs.set('anio', anio);
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/minutas-rpp?${qs.toString()}`).then(manejarRespuestaJson);
        const minutas = data.minutas || [];
        if (!panel) return;
        if (!minutas.length) {
            panel.innerHTML = '<div class="p-4 text-sm text-slate-500">No hay minutas RPP registradas para el filtro seleccionado.</div>';
            return;
        }
        panel.innerHTML = `
            <table class="mp-table">
                <thead><tr><th>Nombre</th><th>Mes/Año</th><th>Versión</th><th>Estado</th><th>Fecha elaboración</th><th>Acciones</th></tr></thead>
                <tbody>${minutas.map(m => `
                    <tr>
                        <td>${escaparHtml(m.nombre || m.nombre_minuta || 'Minuta RPP')}</td>
                        <td>${Number(m.mes || 0).toString().padStart(2, '0')}/${escaparHtml(m.anio || '')}</td>
                        <td>${escaparHtml(m.version || '')}</td>
                        <td><span class="mp-state mp-state-${escaparHtml(String(m.estado || 'borrador').toLowerCase())}">${escaparHtml(m.estado || 'borrador')}</span></td>
                        <td>${escaparHtml(m.fecha_elaboracion || '')}</td>
                        <td><button onclick="mpMarcarMinutaVigente(${Number(m.id)})" class="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3 py-1.5 text-xs text-white">Marcar vigente</button></td>
                    </tr>`).join('')}</tbody>
            </table>`;
    } catch (error) {
        if (panel) panel.innerHTML = `<div class="p-4 text-sm text-rose-400">${escaparHtml(error.message || 'No se pudieron cargar minutas RPP')}</div>`;
    }
}

async function mpSubirMinutaRpp() {
    const file = document.getElementById('mp-minuta-file')?.files?.[0];
    if (!file) return mpMsg('Selecciona una minuta RPP en PDF o Excel.', 'error');
    const form = new FormData();
    form.append('file', file);
    form.append('mes', document.getElementById('mp-minuta-mes')?.value || new Date().getMonth() + 1);
    form.append('anio', document.getElementById('mp-minuta-anio')?.value || new Date().getFullYear());
    form.append('version', document.getElementById('mp-minuta-version')?.value || '1.0');
    form.append('fecha_elaboracion', document.getElementById('mp-minuta-fecha')?.value || '');
    try {
        mpMsg('Subiendo y extrayendo productos de la minuta...', 'warn');
        const data = await fetch(`${backendUrl}/api/motor-plantillas/minutas-rpp/cargar`, { method: 'POST', body: form }).then(manejarRespuestaJson);
        const grupos = data?.extraccion?.grupos?.length || 0;
        mpMsg(`${data.message || 'Minuta cargada.'} Grupos detectados: ${grupos}.`, 'ok');
        await mpCargarMinutasRpp();
    } catch (error) {
        mpMsg(error.message || 'No se pudo cargar la minuta RPP.', 'error');
    }
}

async function mpMarcarMinutaVigente(versionId) {
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/minutas-rpp/${Number(versionId)}/vigente`, { method: 'POST' }).then(manejarRespuestaJson);
        mpMsg(data.message || 'Minuta RPP marcada como vigente.', 'ok');
        await mpCargarMinutasRpp();
    } catch (error) {
        mpMsg(error.message || 'No se pudo marcar la minuta como vigente.', 'error');
    }
}


// ===== RAM V3 — lector oficial de instrucciones (solo lectura) =====
async function mpCargarRamV3Estado() {
    const out = document.getElementById('mp-ram-v3-status');
    if (!out) return;
    const fecha = document.getElementById('mp-fecha-vigencia')?.value || '';
    const base = fecha ? new Date(`${fecha}T00:00:00`) : new Date();
    const qs = new URLSearchParams({ mes: String(base.getMonth() + 1), anio: String(base.getFullYear()) });
    try {
        const data = await fetch(`${backendUrl}/api/motor-plantillas/ram-v3/estado?${qs.toString()}`).then(manejarRespuestaJson);
        const version = data.version_aplicable || {};
        out.innerHTML = `
            <div class="${data.integridad_ok ? 'mp-ok' : 'mp-warning'}">
                <strong>RAM ${escaparHtml(version.version || 'V3')}</strong> · periodo ${escaparHtml(data.periodo || '')}<br>
                Plantilla: ${data.plantilla_existe ? 'disponible' : 'no encontrada'} ·
                instrucciones: ${data.instrucciones_existen ? 'disponibles' : 'no encontradas'} ·
                integridad: ${data.integridad_ok ? 'verificada' : 'pendiente'}
                ${version.fecha_vigencia ? `<br>Vigencia inicial: ${escaparHtml(version.fecha_vigencia)}` : ''}
            </div>`;
    } catch (error) {
        out.innerHTML = `<div class="mp-risk">${escaparHtml(error.message || 'No se pudo consultar el estado RAM V3.')}</div>`;
    }
}

async function mpCargarInstruccionesRamV3(campo = '') {
    const out = document.getElementById('mp-ram-v3-instructions');
    if (!out) return;
    const query = campo || document.getElementById('mp-ram-v3-field')?.value || '';
    try {
        const url = query
            ? `${backendUrl}/api/motor-plantillas/ram-v3/instrucciones?campo=${encodeURIComponent(query)}`
            : `${backendUrl}/api/motor-plantillas/ram-v3/instrucciones`;
        const data = await fetch(url).then(manejarRespuestaJson);
        const items = data.instruccion ? [data.instruccion] : (data.campos || []);
        out.innerHTML = items.map((item) => `
            <article class="mp-panel p-4 mb-3">
                <h4 class="font-semibold text-cyan-200">${escaparHtml(item.titulo || item.id || '')}</h4>
                ${(item.valores_permitidos || []).length ? `<p class="mt-1 text-xs text-slate-400">Valores permitidos: ${item.valores_permitidos.map(escaparHtml).join(', ')}</p>` : ''}
                <ul class="mt-2 list-disc pl-5 text-sm text-slate-300 space-y-1">
                    ${(item.reglas || []).map((rule) => `<li>${escaparHtml(rule)}</li>`).join('')}
                </ul>
            </article>`).join('') || '<div class="mp-warning">No se encontraron instrucciones.</div>';
    } catch (error) {
        out.innerHTML = `<div class="mp-risk">${escaparHtml(error.message || 'No se pudo consultar el manual RAM V3.')}</div>`;
    }
}
