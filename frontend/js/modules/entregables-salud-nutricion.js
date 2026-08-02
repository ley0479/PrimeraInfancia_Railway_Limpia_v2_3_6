/* ALPHA51 - Entregables Salud y Nutrición.
   Extiende el módulo Salud/Nutrición sin tocar carga Cuéntame, CoreCursor ni formatos oficiales. */
let snEntEstado = {
    inicializado: false,
    entregables: [],
    resumen: {},
    anio: new Date().getFullYear(),
    mes: new Date().getMonth() + 1
};

function snEntMsg(texto, tipo = 'success') {
    const box = document.getElementById('sn-ent-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.innerText = texto;
    box.classList.remove('hidden');
}

function snEntregablesInit() {
    if (!snEntEstado.inicializado) {
        snEntEstado.inicializado = true;
        const mes = document.getElementById('sn-ent-mes');
        const anio = document.getElementById('sn-ent-anio');
        if (mes) mes.value = String(snEntEstado.mes);
        if (anio) anio.value = String(snEntEstado.anio);
    }
    snEntCargar();
    if (window.lucide) lucide.createIcons();
}

function snEntFiltros() {
    return {
        mes: document.getElementById('sn-ent-mes')?.value || String(new Date().getMonth() + 1),
        anio: document.getElementById('sn-ent-anio')?.value || String(new Date().getFullYear()),
        uds: document.getElementById('sn-ent-uds')?.value?.trim() || '',
        coordinador: document.getElementById('sn-ent-coordinador')?.value?.trim() || '',
        estado: document.getElementById('sn-ent-estado')?.value || ''
    };
}

function snEntQuery(filtros = snEntFiltros()) {
    const params = new URLSearchParams();
    Object.entries(filtros).forEach(([k, v]) => { if (v !== undefined && v !== null && String(v).trim() !== '') params.set(k, v); });
    return params.toString();
}

function snEntActualizarStats(resumen = {}) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
    set('sn-ent-stat-total', resumen.total || 0);
    set('sn-ent-stat-completos', resumen.completos || 0);
    set('sn-ent-stat-pendientes', resumen.pendientes || 0);
    set('sn-ent-stat-avance', `${resumen.porcentaje || 0}%`);
}

function snEntBadge(estado) {
    const e = String(estado || 'pendiente').toLowerCase();
    const cls = e === 'completo' ? 'sn-badge-verde' : e === 'observado' ? 'sn-badge-amarillo' : e === 'vencido' ? 'sn-badge-rojo' : 'sn-badge-amarillo';
    return `<span class="sn-badge ${cls}">${escaparHtml(estado || 'pendiente')}</span>`;
}

function snEntAcciones(row) {
    const id = Number(row.id);
    const acciones = [];
    if (Number(row.requiere_acta || 0)) acciones.push(`<button onclick="snEntGenerar(${id}, 'acta')" class="sn-ent-btn">Acta</button>`);
    if (Number(row.requiere_listado || 0)) acciones.push(`<button onclick="snEntGenerar(${id}, 'listado')" class="sn-ent-btn">Listado</button>`);
    if (Number(row.requiere_oficio || 0)) acciones.push(`<button onclick="snEntGenerar(${id}, 'oficio')" class="sn-ent-btn">Oficio</button>`);
    if (Number(row.requiere_formato_excel || 0)) acciones.push(`<button onclick="snEntGenerar(${id}, 'formato')" class="sn-ent-btn">Formato</button>`);
    if (Number(row.requiere_fotos || 0)) acciones.push(`<button onclick="snEntSubirEvidencia(${id})" class="sn-ent-btn sn-ent-btn-foto">Fotos</button>`);
    acciones.push(`<button onclick="snEntValidar(${id})" class="sn-ent-btn sn-ent-btn-validar">Validar</button>`);
    return `<div class="flex flex-wrap gap-1.5">${acciones.join('')}</div>`;
}

function snEntRender(rows = [], resumen = {}) {
    const body = document.getElementById('sn-ent-list');
    snEntActualizarStats(resumen);
    if (!body) return;
    if (!rows.length) {
        body.innerHTML = '<tr><td colspan="7" class="text-center text-slate-500">No hay entregables creados para los filtros seleccionados.</td></tr>';
        return;
    }
    body.innerHTML = rows.map((row, idx) => {
        const fotos = Number(row.fotos_cargadas || 0);
        const minimo = Number(row.requiere_fotos || 0) ? Number(row.minimo_fotos || 4) : 0;
        const fotoTxt = minimo ? `${fotos}/${minimo}` : 'No aplica';
        return `
            <tr>
                <td>${idx + 1}</td>
                <td><div class="font-semibold text-slate-100">${escaparHtml(row.nombre || '')}</div><div class="mt-1 text-[11px] text-slate-500">${escaparHtml(row.codigo || '')}</div></td>
                <td>${escaparHtml(row.uds || 'TODAS')}</td>
                <td>${snEntBadge(row.estado)}</td>
                <td class="${minimo && fotos < minimo ? 'text-amber-300' : 'text-emerald-300'}">${fotoTxt}</td>
                <td>${Number(row.archivos_generados || 0)}</td>
                <td>${snEntAcciones(row)}</td>
            </tr>`;
    }).join('');
}

function snEntCargar() {
    const filtros = snEntFiltros();
    fetch(`${backendUrl}/api/salud-nutricion/entregables?${snEntQuery(filtros)}`)
        .then(manejarRespuestaJson)
        .then((data) => {
            snEntEstado.entregables = data.entregables || [];
            snEntEstado.resumen = data.resumen || {};
            snEntRender(snEntEstado.entregables, snEntEstado.resumen);
        })
        .catch((error) => snEntMsg(error.message || 'No se pudieron cargar entregables.', 'error'));
}

function snEntCrearMes() {
    const payload = snEntFiltros();
    payload.uds = payload.uds || 'TODAS';
    mostrarCargando('Creando entregables de Salud y Nutrición...');
    fetch(`${backendUrl}/api/salud-nutricion/entregables/crear-mes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snEntMsg(data.message || 'Entregables creados.', 'success');
            snEntCargar();
        })
        .catch((error) => {
            ocultarCargando();
            snEntMsg(error.message || 'No se pudieron crear entregables.', 'error');
        });
}

function snEntGenerar(id, tipo) {
    mostrarCargando(`Generando ${tipo}...`);
    fetch(`${backendUrl}/api/salud-nutricion/entregables/${id}/${tipo}`, { method: 'POST' })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snEntMsg(data.message || 'Archivo generado.', 'success');
            if (data.archivo?.download_url) {
                setTimeout(() => { window.descargarArchivoAutenticado(`${backendUrl}${data.archivo.download_url}`).catch((error) => snEntMsg(error.message, 'error')); }, 250);
            }
            snEntCargar();
        })
        .catch((error) => {
            ocultarCargando();
            snEntMsg(error.message || `No se pudo generar ${tipo}.`, 'error');
        });
}

function snEntSubirEvidencia(id) {
    const input = document.createElement('input');
    input.type = 'file';
    input.multiple = true;
    input.accept = '.png,.jpg,.jpeg,.webp,.pdf,.doc,.docx,.xlsx,.xls';
    input.onchange = () => {
        const files = Array.from(input.files || []);
        if (!files.length) return;
        const filtros = snEntFiltros();
        const fd = new FormData();
        files.forEach((f) => fd.append('files', f));
        fd.append('uds', filtros.uds || 'TODAS');
        fd.append('actividad', 'ENTREGABLE_SALUD_NUTRICION');
        fd.append('fecha', new Date().toISOString().slice(0, 10));
        mostrarCargando('Subiendo evidencias...');
        fetch(`${backendUrl}/api/salud-nutricion/entregables/${id}/evidencias`, { method: 'POST', body: fd })
            .then(manejarRespuestaJson)
            .then((data) => {
                ocultarCargando();
                snEntMsg(data.message || 'Evidencias cargadas.', 'success');
                snEntCargar();
            })
            .catch((error) => {
                ocultarCargando();
                snEntMsg(error.message || 'No se pudieron subir evidencias.', 'error');
            });
    };
    input.click();
}

function snEntValidar(id) {
    fetch(`${backendUrl}/api/salud-nutricion/entregables/${id}/validar`, { method: 'POST' })
        .then((response) => response.json().then((data) => ({ ok: response.ok, status: response.status, data })))
        .then(({ ok, data }) => {
            if (ok) {
                snEntMsg(data.message || 'Entregable validado.', 'success');
            } else {
                const pendientes = (data.pendientes || []).join(' · ');
                snEntMsg(pendientes || data.message || data.error || 'Entregable con pendientes.', 'error');
            }
            snEntCargar();
        })
        .catch((error) => snEntMsg(error.message || 'No se pudo validar.', 'error'));
}

function snEntPostArchivo(endpoint, mensaje) {
    const payload = snEntFiltros();
    mostrarCargando(mensaje);
    fetch(`${backendUrl}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
        .then(manejarRespuestaJson)
        .then((data) => {
            ocultarCargando();
            snEntMsg(data.message || 'Archivo generado.', 'success');
            if (data.archivo?.download_url) {
                setTimeout(() => { window.descargarArchivoAutenticado(`${backendUrl}${data.archivo.download_url}`).catch((error) => snEntMsg(error.message, 'error')); }, 250);
            }
        })
        .catch((error) => {
            ocultarCargando();
            snEntMsg(error.message || 'No se pudo generar archivo.', 'error');
        });
}

function snEntGenerarMatriz() { snEntPostArchivo('/api/salud-nutricion/entregables/matriz', 'Generando matriz de control...'); }
function snEntGenerarInforme() { snEntPostArchivo('/api/salud-nutricion/entregables/informe', 'Generando informe Word...'); }
function snEntGenerarZip() { snEntPostArchivo('/api/salud-nutricion/entregables/zip', 'Generando paquete ZIP...'); }

window.snEntregablesInit = snEntregablesInit;
window.snEntCrearMes = snEntCrearMes;
window.snEntCargar = snEntCargar;
window.snEntGenerar = snEntGenerar;
window.snEntSubirEvidencia = snEntSubirEvidencia;
window.snEntValidar = snEntValidar;
window.snEntGenerarMatriz = snEntGenerarMatriz;
window.snEntGenerarInforme = snEntGenerarInforme;
window.snEntGenerarZip = snEntGenerarZip;
