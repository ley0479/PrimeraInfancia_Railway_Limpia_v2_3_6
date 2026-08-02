const PM_CATEGORIAS = [
    ['01_Bienestarina', 'Bienestarina'],
    ['02_RPP', 'RPP'],
    ['03_RAM_RAN_RRAN', 'RAM / RAN / RRAN'],
    ['04_Relacion_Mes', 'Relación del mes'],
    ['05_Cuentas_Cobro', 'Cuentas de cobro'],
    ['06_Informe_Nutricional', 'Informe nutricional'],
    ['07_Informe_Novedades', 'Informe de novedades'],
    ['08_Talento_Humano', 'Talento Humano'],
    ['09_Reporte_Gerencial', 'Reporte gerencial'],
    ['10_Auditoria_Mensual', 'Auditoría mensual']
];

function pmPeriodoActual() {
    const d = new Date();
    return {
        mes: d.getMonth() + 1,
        anio: d.getFullYear()
    };
}

function pmPeriodoForm() {
    const periodo = document.getElementById('pm-periodo')?.value;
    if (periodo && periodo.includes('-')) {
        const [anio, mes] = periodo.split('-').map(Number);
        return { mes, anio };
    }
    const actual = pmPeriodoActual();
    return actual;
}

function pmSetPeriodoActual() {
    const input = document.getElementById('pm-periodo');
    if (!input || input.value) return;
    const { mes, anio } = pmPeriodoActual();
    input.value = `${anio}-${String(mes).padStart(2, '0')}`;
}

async function pmInit() {
    pmSetPeriodoActual();
    pmRenderCategorias();
    await pmCargarDashboard();
    await pmCargarHistorial();
}

function pmRenderCategorias() {
    const cont = document.getElementById('pm-categorias');
    if (!cont) return;
    cont.innerHTML = PM_CATEGORIAS.map(([folder, label]) => `
        <div class="pm-folder">
            <div class="flex items-center gap-2 text-slate-200">
                <i data-lucide="folder-check" class="w-4 h-4 text-cyan-300"></i>
                <span class="font-medium">${escaparHtml(label)}</span>
            </div>
            <div class="mt-1 text-[11px] text-slate-500">${escaparHtml(folder)}</div>
        </div>
    `).join('');
    lucide.createIcons();
}

async function pmCargarDashboard() {
    const box = document.getElementById('pm-resumen');
    if (!box) return;
    try {
        const resp = await fetch(`${backendUrl}/api/paquete-mensual/dashboard`);
        const data = await manejarRespuestaJson(resp);
        box.innerHTML = `
            <div class="pm-kpi">
                <p class="text-xs text-slate-400">Paquetes generados</p>
                <p class="text-2xl font-bold text-indigo-300">${data.total_paquetes || 0}</p>
            </div>
            <div class="pm-kpi">
                <p class="text-xs text-slate-400">Costo por generación</p>
                <p class="text-2xl font-bold text-cyan-300">${data.costo_creditos || 10} créditos</p>
            </div>
            <div class="pm-kpi">
                <p class="text-xs text-slate-400">Último paquete</p>
                <p class="text-sm font-semibold text-slate-200">${data.ultimo ? escaparHtml(data.ultimo.periodo || '') : 'Sin paquetes'}</p>
            </div>
        `;
    } catch (error) {
        box.innerHTML = `<div class="rounded-xl border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-300">${escaparHtml(error.message || 'No se pudo cargar el dashboard del paquete mensual.')}</div>`;
    }
}

async function pmCargarHistorial() {
    const tbody = document.getElementById('pm-historial');
    if (!tbody) return;
    tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">Cargando historial...</td></tr>`;
    try {
        const resp = await fetch(`${backendUrl}/api/paquete-mensual/historial`);
        const data = await manejarRespuestaJson(resp);
        const paquetes = data.paquetes || [];
        if (!paquetes.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">No hay paquetes generados todavía.</td></tr>`;
            return;
        }
        tbody.innerHTML = paquetes.map((p) => `
            <tr class="border-b border-slate-800/70 hover:bg-slate-900/50">
                <td class="px-4 py-3">${escaparHtml(p.periodo || '')}</td>
                <td class="px-4 py-3">${escaparHtml(p.estado || '')}</td>
                <td class="px-4 py-3">${Number(p.total_archivos || 0)}</td>
                <td class="px-4 py-3">${pmFormatoTamano(p.tamano_bytes || 0)}</td>
                <td class="px-4 py-3">${escaparHtml(fechaPlantillaLegible(p.fecha_creacion || ''))}</td>
                <td class="px-4 py-3">
                    ${p.ruta_zip ? `<button onclick="pmDescargar(${Number(p.id)})" class="pm-btn pm-btn-outline py-1.5 text-xs"><i data-lucide="download" class="w-3.5 h-3.5"></i> Descargar</button>` : '<span class="text-slate-500">No disponible</span>'}
                </td>
            </tr>
        `).join('');
        lucide.createIcons();
    } catch (error) {
        tbody.innerHTML = `<tr><td colspan="6" class="px-4 py-6 text-center text-rose-300">${escaparHtml(error.message || 'Error al cargar historial.')}</td></tr>`;
    }
}

function pmFormatoTamano(bytes) {
    const b = Number(bytes || 0);
    if (b < 1024) return `${b} B`;
    if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
    return `${(b / 1024 / 1024).toFixed(1)} MB`;
}

async function pmGenerar() {
    const { mes, anio } = pmPeriodoForm();
    const msg = document.getElementById('pm-message');
    if (msg) {
        msg.className = 'mt-4 rounded-xl border border-indigo-500/20 bg-indigo-500/10 px-4 py-3 text-sm text-indigo-200';
        msg.textContent = 'Generando paquete mensual completo. Esto puede tardar varios minutos...';
    }
    mostrarCargando('Generando paquete mensual completo: formatos, reportes, auditoría y ZIP final...');
    try {
        const resp = await fetch(`${backendUrl}/api/paquete-mensual/generar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mes, anio })
        });
        const data = await manejarRespuestaJson(resp);
        if (msg) {
            const estado = data.paquete?.estado || 'GENERADO';
            const total = Number(data.paquete?.total_archivos || 0);
            const alertas = Array.isArray(data.paquete?.errores) ? data.paquete.errores.length : 0;
            msg.className = alertas
                ? 'mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-200'
                : 'mt-4 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300';
            msg.innerHTML = `
                <div class="font-semibold">${escaparHtml(data.message || 'Paquete generado.')}</div>
                <div class="mt-1 text-xs opacity-90">Estado: ${escaparHtml(estado)} · Archivos incluidos: ${total}${alertas ? ` · Alertas: ${alertas}` : ''}</div>
                <div class="mt-3 flex flex-wrap gap-2">
                    <button onclick="pmDescargar(${Number(data.paquete?.id)})" class="pm-btn pm-btn-primary py-1.5 text-xs"><i data-lucide="download" class="w-3.5 h-3.5"></i> Descargar ZIP actualizado</button>
                    <button onclick="pmCargarHistorial()" class="pm-btn pm-btn-outline py-1.5 text-xs"><i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Actualizar historial</button>
                </div>
            `;
            lucide.createIcons();
        }
        await pmCargarDashboard();
        await pmCargarHistorial();
    } catch (error) {
        if (msg) {
            msg.className = 'mt-4 rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300';
            msg.textContent = error.message || 'No se pudo generar el paquete mensual.';
        }
    } finally {
        ocultarCargando();
    }
}

function pmDescargar(id) {
    if (!id) return;
    window.descargarArchivoAutenticado(`${backendUrl}/api/paquete-mensual/${encodeURIComponent(id)}/descargar`).catch((error) => pmMensaje(error.message || 'No se pudo descargar el paquete.', 'error'));
}

function pmGenerarDesdePanel() {
    mostrarSeccion('paquete-mensual');
    setTimeout(() => pmGenerar(), 300);
}