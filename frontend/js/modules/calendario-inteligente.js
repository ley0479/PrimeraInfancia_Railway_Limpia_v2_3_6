// Alpha15: Calendario Inteligente de Entregables y Alertas Operativas.
// Módulo aislado: no modifica plantillas oficiales ni impresión de formatos.
(function () {
    const apiBase = () => window.backendUrl || window.getBackendUrl?.() || window.getConfiguredBackendUrl?.() || window.location.origin;
    const API = `${apiBase()}/api/calendario-inteligente`;
    const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    const DIAS = ['Dom', 'Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb'];
    const state = {
        periodo: new Date().toISOString().slice(0, 7),
        anio: String(new Date().getFullYear()),
        vista: 'mes',
        dashboard: null,
        filtros: {},
        selectedDate: null,
        previewCronograma: null,
    };

    function api(path, options = {}) {
        return fetch(`${API}${path}`, options).then((resp) => {
            if (typeof manejarRespuestaJson === 'function') return manejarRespuestaJson(resp);
            return resp.json().then((json) => { if (!resp.ok) throw new Error(json.error || 'Error de calendario'); return json; });
        });
    }

    function apiJob(jobId) {
        const token = typeof authToken === 'function' ? authToken() : '';
        return fetch(`${apiBase()}/api/jobs/${encodeURIComponent(jobId)}`, {
            headers: {
                'Authorization': token ? `Bearer ${token}` : '',
                'X-Auth-Token': token || '',
                'X-Requested-With': 'XMLHttpRequest'
            }
        }).then((resp) => {
            if (typeof manejarRespuestaJson === 'function') return manejarRespuestaJson(resp);
            return resp.json().then((json) => { if (!resp.ok) throw new Error(json.error || 'Error consultando trabajo'); return json; });
        });
    }

    function esperarJobCalendario(jobId) {
        let intentos = 0;
        const maxIntentos = 180;
        const tick = async () => {
            intentos += 1;
            try {
                const data = await apiJob(jobId);
                const job = data.job || data;
                const progreso = Math.round(Number(job.progreso || 0));
                message(`${job.etapa || 'Procesando cronograma'} (${progreso}%)`);
                if (job.estado === 'completado') {
                    const r = job.resultado?.resultado || job.resultado || {};
                    message(`Cronograma procesado: ${r.creados || 0} creados, ${r.duplicados || 0} duplicados, ${r.errores?.length || 0} errores.`);
                    await cargarDashboard();
                    return;
                }
                if (job.estado === 'error') {
                    message(job.error || 'No se pudo procesar el cronograma.', 'error');
                    return;
                }
                if (intentos < maxIntentos) setTimeout(tick, 3000);
                else message('El cronograma sigue tardando demasiado. Revisa los logs del backend.', 'error');
            } catch (err) {
                if (intentos < maxIntentos) setTimeout(tick, 3000);
                else message(err.message || 'No se pudo consultar el avance del cronograma.', 'error');
            }
        };
        tick();
    }

    function esc(v) {
        return typeof escaparHtml === 'function' ? escaparHtml(v) : String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
    }

    function injectNavAndSection() {
        const nav = document.querySelector('aside nav');
        if (nav && !document.getElementById('nav-calendario-inteligente')) {
            const btn = document.createElement('button');
            btn.id = 'nav-calendario-inteligente';
            btn.onclick = () => window.mostrarSeccion ? mostrarSeccion('calendario-inteligente') : null;
            btn.className = 'w-full text-left flex items-center gap-3 px-4 py-3 text-slate-400 hover:bg-slate-900 hover:text-slate-200 rounded-xl transition';
            btn.innerHTML = '<i data-lucide="calendar-days"></i> Calendario Inteligente <span class="ml-auto rounded-full bg-rose-500/20 px-2 py-0.5 text-[10px] text-rose-300">Alertas</span>';
            const dashboard = document.getElementById('nav-dashboard');
            dashboard?.insertAdjacentElement('afterend', btn) || nav.prepend(btn);
        }
        const main = document.querySelector('main .p-8.space-y-8');
        if (main && !document.getElementById('calendario-inteligente')) {
            main.insertAdjacentHTML('beforeend', calendarSectionHtml());
        }
    }

    function calendarSectionHtml() {
        return `
        <section id="calendario-inteligente" class="hidden space-y-6">
            <div class="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
                <div class="flex items-start gap-4">
                    <div class="ci-title-icon"><i data-lucide="calendar-clock" class="w-8 h-8"></i></div>
                    <div>
                        <h2 class="text-3xl font-bold text-slate-100">Calendario Inteligente de Entregables</h2>
                        <p class="text-slate-400 mt-1">Control de actividades, fechas de entrega, evidencias y alertas operativas sincronizadas con la plataforma.</p>
                    </div>
                </div>
                <div class="flex flex-wrap gap-2">
                    <button onclick="ciAbrirModalNuevo()" class="ci-btn ci-btn-primary"><i data-lucide="plus" class="w-4 h-4"></i> Nuevo entregable</button>
                    <label class="ci-btn ci-btn-muted cursor-pointer"><i data-lucide="upload" class="w-4 h-4"></i> Cargar cronograma<input id="ci-cronograma-file" type="file" accept=".xlsx,.xls,.xlsm,.ods,.csv,.txt,.tsv,.tab,.dat,.docx,.pdf,.pptx,.png,.jpg,.jpeg,.webp,.bmp,.tif,.tiff" class="hidden" onchange="ciCargarCronograma()"></label><button onclick="ciExportarExcel()" class="ci-btn ci-btn-muted"><i data-lucide="file-spreadsheet" class="w-4 h-4"></i> Exportar Excel</button><button onclick="ciExportarPdf()" class="ci-btn ci-btn-muted"><i data-lucide="file-text" class="w-4 h-4"></i> Exportar PDF</button>
                </div>
            </div>
            <div id="ci-message" class="hidden rounded-xl px-4 py-3 text-sm"></div>
            <div class="ci-panel ci-help-panel">
                <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3">
                    <div>
                        <h3 class="font-semibold text-slate-100 flex items-center gap-2"><i data-lucide="scan-text" class="w-4 h-4 text-cyan-300"></i> Carga inteligente de cronograma mensual</h3>
                        <p class="text-sm text-slate-400 mt-1">Sube Excel, PDF, Word o imagen. El sistema detecta fechas y actividades, pero siempre muestra una vista previa editable antes de guardar.</p>
                    </div>
                    <span class="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-200">Revisar antes de guardar</span>
                </div>
            </div>
            <div class="grid gap-4 xl:grid-cols-5">
                <div class="ci-metric"><div class="flex items-center gap-3"><i data-lucide="calendar-check" class="text-blue-300"></i><p class="text-sm text-slate-400">Entregables del mes</p></div><p id="ci-stat-total" class="text-3xl font-bold mt-3">0</p><p class="text-xs text-slate-500 mt-1">Total programados</p></div>
                <div class="ci-metric"><div class="flex items-center gap-3"><i data-lucide="clock" class="text-yellow-300"></i><p class="text-sm text-yellow-200">Próximos a vencer</p></div><p id="ci-stat-proximos" class="text-3xl font-bold mt-3 text-yellow-300">0</p><p class="text-xs text-slate-500 mt-1">Amarillo/naranja</p></div>
                <div class="ci-metric"><div class="flex items-center gap-3"><i data-lucide="triangle-alert" class="text-red-300"></i><p class="text-sm text-red-200">Vencidos</p></div><p id="ci-stat-vencidos" class="text-3xl font-bold mt-3 text-red-300">0</p><p class="text-xs text-slate-500 mt-1">Requieren atención</p></div>
                <div class="ci-metric"><div class="flex items-center gap-3"><i data-lucide="circle-check" class="text-green-300"></i><p class="text-sm text-green-200">Entregados</p></div><p id="ci-stat-entregados" class="text-3xl font-bold mt-3 text-green-300">0</p><p class="text-xs text-slate-500 mt-1">Completados</p></div>
                <div class="ci-metric"><div class="flex items-center gap-3"><i data-lucide="percent" class="text-cyan-300"></i><p class="text-sm text-slate-400">Cumplimiento</p></div><p id="ci-stat-cumplimiento" class="text-3xl font-bold mt-3 text-cyan-300">0%</p><p class="text-xs text-slate-500 mt-1">Del mes</p></div>
            </div>
            <div class="ci-panel">
                <div class="grid gap-3 md:grid-cols-6">
                    <div><label class="text-xs text-slate-400">Mes</label><input id="ci-periodo" type="month" class="ci-input" onchange="ciSetPeriodo(this.value)"></div>
                    <div><label class="text-xs text-slate-400">Año</label><input id="ci-anio" type="number" min="2020" max="2100" class="ci-input" onchange="ciSetAnio(this.value)"></div>
                    <div><label class="text-xs text-slate-400">Coordinador</label><select id="ci-filtro-coordinador" class="ci-input" onchange="ciAplicarFiltros()"><option value="">Todos</option></select></div>
                    <div><label class="text-xs text-slate-400">Unidad/UDS</label><select id="ci-filtro-unidad" class="ci-input" onchange="ciAplicarFiltros()"><option value="">Todas</option></select></div>
                    <div><label class="text-xs text-slate-400">Módulo</label><select id="ci-filtro-modulo" class="ci-input" onchange="ciAplicarFiltros()"><option value="">Todos</option></select></div>
                    <div><label class="text-xs text-slate-400">Estado</label><select id="ci-filtro-estado" class="ci-input" onchange="ciAplicarFiltros()"><option value="">Todos</option></select></div>
                </div>
                <div class="mt-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                    <button onclick="ciLimpiarFiltros()" class="ci-btn ci-btn-muted"><i data-lucide="rotate-ccw" class="w-4 h-4"></i> Limpiar filtros</button>
                    <div class="ci-view-toggle">
                        <button id="ci-vista-mes" onclick="ciCambiarVista('mes')" class="ci-active">Mes</button>
                        <button id="ci-vista-anio" onclick="ciCambiarVista('anio')">Año</button>
                        <button id="ci-vista-lista" onclick="ciCambiarVista('lista')">Lista</button>
                    </div>
                </div>
            </div>
            <div class="grid gap-5 xl:grid-cols-[1fr_360px]">
                <div class="ci-panel">
                    <div class="flex items-center justify-between gap-3 mb-4">
                        <button onclick="ciMoverMes(-1)" class="ci-btn ci-btn-muted"><i data-lucide="chevron-left" class="w-4 h-4"></i></button>
                        <h3 id="ci-cal-title" class="text-2xl font-bold text-center">Mes</h3>
                        <button onclick="ciMoverMes(1)" class="ci-btn ci-btn-muted"><i data-lucide="chevron-right" class="w-4 h-4"></i></button>
                    </div>
                    <div id="ci-view-container"></div>
                </div>
                <aside class="space-y-4">
                    <div class="ci-panel">
                        <h3 class="font-semibold text-slate-100 flex items-center gap-2"><i data-lucide="bell-ring" class="w-4 h-4 text-amber-300"></i> Pendientes y alertas</h3>
                        <div id="ci-alertas-list" class="mt-3 space-y-2"></div>
                    </div>
                    <div class="ci-panel">
                        <h3 class="font-semibold text-slate-100 mb-3">Leyenda de estados</h3>
                        <div class="grid grid-cols-2 gap-2 text-xs text-slate-300">
                            ${legendItem('azul', 'Programado')}${legendItem('verde', 'Entregado')}${legendItem('amarillo', 'Próximo')}${legendItem('naranja', 'Vence pronto')}${legendItem('rojo', 'Vencido/Hoy')}${legendItem('gris', 'Cerrado')}
                        </div>
                    </div>
                    <div class="ci-panel">
                        <h3 class="font-semibold text-slate-100 mb-3">Cumplimiento por coordinador</h3>
                        <div id="ci-cumplimiento-coordinador" class="space-y-3"></div>
                    </div>
                </aside>
            </div>
        </section>`;
    }

    function legendItem(color, label) { return `<div class="flex items-center gap-2"><span class="ci-dot ci-${color}"></span>${label}</div>`; }

    function message(text, type = 'success') {
        const el = document.getElementById('ci-message');
        if (!el) return;
        el.className = `rounded-xl px-4 py-3 text-sm ${type === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
        el.textContent = text;
        el.classList.remove('hidden');
    }

    async function init() {
        injectNavAndSection();
        const periodo = document.getElementById('ci-periodo');
        const anio = document.getElementById('ci-anio');
        if (periodo && !periodo.value) periodo.value = state.periodo;
        if (anio && !anio.value) anio.value = state.anio;
        await cargarDashboard();
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    async function cargarDashboard() {
        const qs = new URLSearchParams({ periodo: state.periodo, anio: state.anio, ...state.filtros });
        const data = await api(`/dashboard?${qs.toString()}`);
        state.dashboard = data;
        renderStats(data.resumen || {});
        renderCatalogos(data.catalogos || {});
        renderVista();
        renderAlertas(data.alertas || []);
        renderCumplimiento(data.cumplimiento_coordinador || []);
        renderDashboardWidget(data.resumen || {}, data.alertas || []);
    }

    function renderStats(r) {
        setText('ci-stat-total', r.entregables_mes || 0);
        setText('ci-stat-proximos', r.proximos || 0);
        setText('ci-stat-vencidos', r.vencidos || 0);
        setText('ci-stat-entregados', r.entregados || 0);
        setText('ci-stat-cumplimiento', `${r.cumplimiento_general || 0}%`);
    }
    function setText(id, value) { const el = document.getElementById(id); if (el) el.textContent = value; }

    function renderCatalogos(c) {
        fillSelect('ci-filtro-modulo', c.modulos || [], 'Todos');
        fillSelect('ci-filtro-estado', c.estados || [], 'Todos');
        fillSelect('ci-filtro-coordinador', c.coordinadores || [], 'Todos');
        fillSelect('ci-filtro-unidad', c.unidades || [], 'Todas');
    }
    function fillSelect(id, items, first) {
        const el = document.getElementById(id); if (!el) return;
        const prev = el.value;
        el.innerHTML = `<option value="">${first}</option>` + (items || []).map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('');
        if ([...el.options].some(o => o.value === prev)) el.value = prev;
    }

    function eventos() { return state.dashboard?.eventos || []; }
    function annual() { return state.dashboard?.annual || []; }

    function renderVista() {
        document.querySelectorAll('#ci-vista-mes,#ci-vista-anio,#ci-vista-lista').forEach(b => b?.classList.remove('ci-active'));
        document.getElementById(`ci-vista-${state.vista}`)?.classList.add('ci-active');
        if (state.vista === 'mes') renderMes();
        if (state.vista === 'anio') renderAnio();
        if (state.vista === 'lista') renderLista();
    }

    function renderMes() {
        const [year, month] = state.periodo.split('-').map(Number);
        const first = new Date(year, month - 1, 1);
        const last = new Date(year, month, 0);
        setText('ci-cal-title', `${MESES[month - 1]} ${year}`);
        const byDate = groupBy(eventos(), e => e.fecha_limite);
        const cells = [];
        DIAS.forEach(d => cells.push(`<div class="ci-weekday">${d}</div>`));
        const prevLast = new Date(year, month - 1, 0).getDate();
        for (let i = 0; i < first.getDay(); i++) {
            cells.push(`<div class="ci-day ci-day-muted"><span class="ci-day-number">${prevLast - first.getDay() + i + 1}</span></div>`);
        }
        const today = new Date().toISOString().slice(0, 10);
        for (let d = 1; d <= last.getDate(); d++) {
            const iso = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const evs = byDate[iso] || [];
            cells.push(`<div class="ci-day ${today === iso ? 'ci-day-today' : ''}" onclick="ciAbrirDia('${iso}')">
                <div class="flex items-center justify-between"><span class="ci-day-number">${d}</span>${evs.length ? `<span class="text-xs text-slate-400">${evs.length}</span>` : ''}</div>
                ${evs.slice(0, 3).map(e => `<div class="ci-event-pill ci-${e.color || e.color_calculado || 'azul'}">${esc(e.titulo || e.modulo)}</div>`).join('')}
                ${evs.length > 3 ? `<div class="text-[11px] text-slate-500 mt-1">+${evs.length - 3} más</div>` : ''}
            </div>`);
        }
        const totalBody = first.getDay() + last.getDate();
        for (let i = 1; i <= (7 - (totalBody % 7 || 7)); i++) {
            cells.push(`<div class="ci-day ci-day-muted"><span class="ci-day-number">${i}</span></div>`);
        }
        document.getElementById('ci-view-container').innerHTML = `<div class="ci-calendar-grid">${cells.join('')}</div>`;
    }

    function renderAnio() {
        const year = Number(state.anio || new Date().getFullYear());
        setText('ci-cal-title', `Vista anual ${year}`);
        const byDate = groupBy(annual(), e => e.fecha_limite);
        let html = '<div class="ci-annual-grid">';
        for (let m = 1; m <= 12; m++) {
            const first = new Date(year, m - 1, 1), last = new Date(year, m, 0);
            let days = DIAS.map(d => `<div class="text-slate-500 font-bold">${d[0]}</div>`).join('');
            for (let i = 0; i < first.getDay(); i++) days += '<div></div>';
            for (let d = 1; d <= last.getDate(); d++) {
                const iso = `${year}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
                const evs = byDate[iso] || [];
                const color = evs.some(e => (e.color || e.color_calculado) === 'rojo') ? 'rojo' : evs.some(e => (e.color || e.color_calculado) === 'naranja') ? 'naranja' : evs.some(e => (e.color || e.color_calculado) === 'amarillo') ? 'amarillo' : evs.some(e => (e.color || e.color_calculado) === 'verde') ? 'verde' : evs.length ? 'azul' : '';
                days += `<button class="ci-mini-day ${evs.length ? `has-event ci-${color}` : ''}" onclick="ciAbrirDia('${iso}')">${d}</button>`;
            }
            html += `<div class="ci-mini-month"><div class="ci-mini-title">${MESES[m - 1]}</div><div class="ci-mini-grid">${days}</div></div>`;
        }
        html += '</div>';
        document.getElementById('ci-view-container').innerHTML = html;
    }

    function renderLista() {
        setText('ci-cal-title', `Pendientes ${state.periodo}`);
        const rows = eventos().map(e => `
            <tr class="hover:bg-slate-900/60">
                <td class="px-4 py-3">${esc(e.fecha_limite || '')}</td>
                <td class="px-4 py-3 font-semibold text-slate-200">${esc(e.titulo || '')}<p class="text-xs text-slate-500">${esc(e.descripcion || '')}</p></td>
                <td class="px-4 py-3">${esc(e.modulo || '')}</td>
                <td class="px-4 py-3">${esc(e.coordinador || '')}<p class="text-xs text-slate-500">${esc(e.unidad || '')}</p></td>
                <td class="px-4 py-3"><span class="ci-list-status ci-${e.color || e.color_calculado || 'azul'}">${esc(e.estado || '')}</span></td>
                <td class="px-4 py-3 text-right"><button onclick="ciAbrirEntregable(${Number(e.id)})" class="text-cyan-300 text-xs">Ver</button></td>
            </tr>`).join('') || '<tr><td colspan="6" class="px-4 py-8 text-center text-slate-500">Sin entregables para el filtro seleccionado.</td></tr>';
        document.getElementById('ci-view-container').innerHTML = `<div class="overflow-x-auto"><table class="w-full text-left text-sm text-slate-400"><thead class="bg-slate-950 text-xs uppercase text-slate-300"><tr><th class="px-4 py-3">Fecha</th><th class="px-4 py-3">Actividad</th><th class="px-4 py-3">Módulo</th><th class="px-4 py-3">Responsable</th><th class="px-4 py-3">Estado</th><th class="px-4 py-3"></th></tr></thead><tbody class="divide-y divide-slate-800">${rows}</tbody></table></div>`;
    }

    function renderAlertas(alertas) {
        const cont = document.getElementById('ci-alertas-list'); if (!cont) return;
        cont.innerHTML = alertas.length ? alertas.slice(0, 7).map(a => `<button onclick="ciAbrirEntregable(${Number(a.id)})" class="w-full text-left rounded-xl border ci-${a.nivel || 'azul'} p-3 text-xs"><strong>${esc(a.fecha_limite || '')}</strong><br>${esc(a.mensaje || '')}</button>`).join('') : '<p class="text-sm text-slate-500">Sin alertas críticas para el periodo.</p>';
    }

    function renderCumplimiento(rows) {
        const cont = document.getElementById('ci-cumplimiento-coordinador'); if (!cont) return;
        cont.innerHTML = rows.length ? rows.slice(0, 6).map(r => `<div><div class="flex justify-between text-xs mb-1"><span class="text-slate-300">${esc(r.nombre)}</span><span>${esc(r.porcentaje)}%</span></div><div class="ci-progress"><div class="ci-progress-bar" style="width:${Number(r.porcentaje || 0)}%"></div></div><p class="text-[11px] text-slate-500 mt-1">${r.entregados}/${r.total} entregados · ${r.vencidos} vencidos</p></div>`).join('') : '<p class="text-sm text-slate-500">Sin datos de cumplimiento.</p>';
    }

    function renderDashboardWidget(resumen, alertas) {
        const dash = document.getElementById('dashboard');
        if (!dash) return;
        let widget = document.getElementById('ci-dashboard-widget');
        if (!widget) {
            widget = document.createElement('div');
            widget.id = 'ci-dashboard-widget';
            widget.className = 'ci-dashboard-widget';
            const bar = dash.querySelector('.dashboard-current-datetime-bar');
            bar?.insertAdjacentElement('afterend', widget) || dash.prepend(widget);
        }
        widget.innerHTML = `<div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-3"><div><h3 class="font-bold text-slate-100 flex items-center gap-2"><i data-lucide="calendar-clock" class="w-5 h-5 text-blue-300"></i> Calendario inteligente del mes</h3><p class="text-sm text-slate-400">${resumen.entregables_mes || 0} entregables · ${resumen.proximos || 0} próximos · ${resumen.vencidos || 0} vencidos · ${resumen.entregados || 0} entregados.</p>${alertas?.length ? `<p class="text-xs text-amber-200 mt-1">${esc(alertas[0].mensaje)}</p>` : ''}</div><button onclick="mostrarSeccion('calendario-inteligente')" class="ci-btn ci-btn-primary">Abrir calendario</button></div>`;
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    function groupBy(arr, fn) {
        return (arr || []).reduce((acc, item) => { const key = fn(item); if (!key) return acc; (acc[key] ||= []).push(item); return acc; }, {});
    }

    async function abrirDia(iso) {
        state.selectedDate = iso;
        const sourceEvents = state.vista === 'anio' ? annual() : eventos();
        const dayEvents = (sourceEvents.length ? sourceEvents : annual()).filter(e => e.fecha_limite === iso);
        openModal(`Entregables del ${iso}`, dayEvents.length ? dayEvents.map(eventDetailHtml).join('') : '<p class="text-slate-500">No hay entregables en esta fecha.</p>');
    }

    async function abrirEntregable(id) {
        const data = await api(`/entregables/${encodeURIComponent(id)}`);
        openModal('Detalle del entregable', eventDetailHtml(data.entregable));
    }

    function eventDetailHtml(e) {
        const id = Number(e.id || 0);
        return `<div class="rounded-xl border border-slate-700 bg-slate-950/60 p-4 mb-3">
            <div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3">
                <div><h4 class="font-bold text-slate-100">${esc(e.titulo || '')}</h4><p class="text-sm text-slate-400">${esc(e.descripcion || '')}</p><p class="text-xs text-slate-500 mt-1">${esc(e.modulo || '')} · ${esc(e.unidad || '')} · ${esc(e.coordinador || '')}</p></div>
                <span class="ci-list-status ci-${e.color || e.color_calculado || 'azul'}">${esc(e.estado || '')}</span>
            </div>
            <div class="grid gap-2 md:grid-cols-3 mt-3 text-sm text-slate-300"><p><strong>Fecha:</strong> ${esc(e.fecha_limite || '')}</p><p><strong>Responsable:</strong> ${esc(e.responsable_nombre || '')}</p><p><strong>Prioridad:</strong> ${esc(e.prioridad || '')}</p></div>
            <div class="mt-3 flex flex-wrap gap-2"><button onclick="ciAbrirModulo('${esc(e.modulo || '')}')" class="ci-btn ci-btn-muted">Abrir módulo</button><button onclick="ciMarcarEntregado(${id})" class="ci-btn ci-btn-success">Marcar entregado</button><button onclick="ciEliminarEntregable(${id})" class="ci-btn ci-btn-danger">Eliminar</button></div>
            <div class="mt-3 grid gap-2 md:grid-cols-[1fr_auto]"><input id="ci-evidencia-${id}" type="file" class="ci-input"><button onclick="ciSubirEvidencia(${id})" class="ci-btn ci-btn-primary">Subir evidencia</button></div>
        </div>`;
    }

    function openModal(title, body) {
        closeModal();
        document.body.insertAdjacentHTML('beforeend', `<div id="ci-modal-backdrop" class="ci-modal-backdrop"><div class="ci-modal"><div class="flex items-start justify-between gap-3 mb-4"><h3 class="text-xl font-bold text-slate-100">${esc(title)}</h3><button onclick="ciCerrarModal()" class="ci-btn ci-btn-muted">Cerrar</button></div>${body}</div></div>`);
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }
    function closeModal() { document.getElementById('ci-modal-backdrop')?.remove(); }

    function abrirModalNuevo() {
        openModal('Nuevo entregable operativo', `<div class="grid gap-3 md:grid-cols-2">
            <input id="ci-new-titulo" class="ci-input" placeholder="Actividad o entregable">
            <input id="ci-new-fecha" type="date" class="ci-input" value="${new Date().toISOString().slice(0,10)}">
            <select id="ci-new-modulo" class="ci-input"><option>RPP</option><option>Bienestarina</option><option>RAM/RAN/Asistencia</option><option>Nutrición</option><option>Talento Humano</option><option>Planeación Pedagógica</option><option>Reportes Gerenciales</option><option>Cumplimiento ICBF</option></select>
            <input id="ci-new-formato" class="ci-input" placeholder="Formato">
            <input id="ci-new-coordinador" class="ci-input" placeholder="Coordinador">
            <input id="ci-new-unidad" class="ci-input" placeholder="Unidad/UDS">
            <input id="ci-new-responsable" class="ci-input" placeholder="Responsable">
            <select id="ci-new-prioridad" class="ci-input"><option>Alta</option><option selected>Media</option><option>Baja</option></select>
            <textarea id="ci-new-descripcion" class="ci-input md:col-span-2" placeholder="Descripción u observaciones"></textarea>
        </div><div class="mt-4"><button onclick="ciCrearEntregable()" class="ci-btn ci-btn-primary">Guardar entregable</button></div>`);
    }

    async function crearEntregable() {
        const payload = {
            titulo: document.getElementById('ci-new-titulo')?.value,
            fecha_limite: document.getElementById('ci-new-fecha')?.value,
            modulo: document.getElementById('ci-new-modulo')?.value,
            tipo_formato: document.getElementById('ci-new-formato')?.value,
            coordinador: document.getElementById('ci-new-coordinador')?.value,
            unidad: document.getElementById('ci-new-unidad')?.value,
            responsable_nombre: document.getElementById('ci-new-responsable')?.value,
            prioridad: document.getElementById('ci-new-prioridad')?.value,
            descripcion: document.getElementById('ci-new-descripcion')?.value,
            requiere_evidencia: true,
        };
        await api('/entregables', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        closeModal(); message('Entregable creado correctamente.'); await cargarDashboard();
    }

    async function cargarCronograma() {
        const input = document.getElementById('ci-cronograma-file');
        const file = input?.files?.[0];
        if (!file) return;
        const fd = new FormData(); fd.append('file', file);
        try {
            message('Leyendo cronograma. En unos segundos se abrirá la vista previa editable...');
            const data = await api('/cargar-cronograma', { method: 'POST', body: fd });
            if (data.job_id) {
                message('Cronograma recibido. Se está procesando en segundo plano para evitar error del túnel.');
                input.value = '';
                esperarJobCalendario(data.job_id);
                return;
            }
            if (data.preview) {
                state.previewCronograma = data.preview;
                abrirPreviewCronograma(data.preview);
                input.value = '';
                message(`Cronograma leído: ${data.preview.actividades?.length || 0} actividades detectadas. Revisa y guarda.`);
                return;
            }
            const r = data.resultado || {};
            message(`Cronograma procesado: ${r.creados || 0} creados, ${r.duplicados || 0} duplicados, ${r.errores?.length || 0} errores.`);
            input.value = ''; await cargarDashboard();
        } catch (err) {
            message(err?.message || 'No se pudo procesar el cronograma cargado.', 'error');
            input.value = '';
        }
    }

    function abrirPreviewCronograma(preview) {
        const actividades = preview.actividades || [];
        const rows = actividades.slice(0, 250).map((a, idx) => previewRowHtml(a, idx)).join('') || '<tr><td colspan="9" class="px-4 py-6 text-center text-slate-500">No se detectaron actividades válidas.</td></tr>';
        const warnings = [ ...(preview.advertencias || []), ...(preview.errores || []).slice(0, 5).map(e => `Fila ${e.fila}: ${e.error}`) ];
        const warnHtml = warnings.length ? `<div class="ci-preview-warning"><strong>Revisión requerida:</strong><ul>${warnings.map(w => `<li>${esc(w)}</li>`).join('')}</ul></div>` : '';
        openModal('Vista previa del cronograma', `
            <div class="ci-preview-summary">
                <div><strong>${Number(preview.actividades?.length || 0)}</strong><span>Detectadas</span></div>
                <div><strong>${Number(preview.validas || 0)}</strong><span>Válidas</span></div>
                <div><strong>${Number(preview.invalidas || 0)}</strong><span>Con error</span></div>
                <div><strong>${Number(preview.duplicados_en_archivo || 0)}</strong><span>Duplicadas</span></div>
            </div>
            ${warnHtml}
            <p class="text-sm text-slate-400 mb-3">Corrige fechas, títulos, responsables, unidad o módulo antes de guardar. Las filas marcadas como descartar no serán creadas.</p>
            <div class="ci-preview-table-wrap"><table class="ci-preview-table">
                <thead><tr><th>Guardar</th><th>Fecha</th><th>Actividad</th><th>Responsable</th><th>Coordinador</th><th>Unidad</th><th>Módulo</th><th>Estado</th><th>Observación</th></tr></thead>
                <tbody>${rows}</tbody>
            </table></div>
            ${actividades.length > 250 ? '<p class="text-xs text-amber-300 mt-2">Se muestran las primeras 250 actividades para proteger el rendimiento. Todas las actividades quedan disponibles en la vista previa interna.</p>' : ''}
            <div class="mt-4 flex flex-wrap gap-2">
                <button onclick="ciConfirmarCronograma()" class="ci-btn ci-btn-success"><i data-lucide="save" class="w-4 h-4"></i> Guardar en calendario</button>
                <button onclick="ciCerrarModal()" class="ci-btn ci-btn-muted">Cancelar</button>
            </div>
        `);
    }

    function previewRowHtml(a, idx) {
        const disabled = a.ok === false ? '' : 'checked';
        const err = (a.errores || []).length ? `<p class="text-[11px] text-rose-300">${esc(a.errores.join('; '))}</p>` : '';
        const warn = (a.advertencias || []).length ? `<p class="text-[11px] text-amber-300">${esc(a.advertencias.join('; '))}</p>` : '';
        return `<tr data-preview-index="${idx}">
            <td><input type="checkbox" class="ci-prev-guardar" ${disabled}></td>
            <td><input type="date" class="ci-input ci-prev-fecha" value="${esc(a.fecha_limite || a.fecha || '')}">${err}</td>
            <td><input class="ci-input ci-prev-titulo" value="${esc(a.titulo || '')}">${warn}</td>
            <td><input class="ci-input ci-prev-responsable" value="${esc(a.responsable_nombre || '')}"></td>
            <td><input class="ci-input ci-prev-coordinador" value="${esc(a.coordinador || '')}"></td>
            <td><input class="ci-input ci-prev-unidad" value="${esc(a.unidad || '')}"></td>
            <td><input class="ci-input ci-prev-modulo" value="${esc(a.modulo || 'General')}"></td>
            <td><select class="ci-input ci-prev-estado"><option value="programado" ${a.estado === 'programado' ? 'selected' : ''}>Programado</option><option value="pendiente" ${a.estado === 'pendiente' ? 'selected' : ''}>Pendiente</option><option value="entregado" ${a.estado === 'entregado' ? 'selected' : ''}>Entregado</option><option value="cerrado" ${a.estado === 'cerrado' ? 'selected' : ''}>Cerrado</option></select></td>
            <td><input class="ci-input ci-prev-observacion" value="${esc(a.observaciones || a.observacion || '')}"></td>
        </tr>`;
    }

    function recopilarPreviewActividades() {
        return [...document.querySelectorAll('[data-preview-index]')].map((tr) => ({
            descartar: !tr.querySelector('.ci-prev-guardar')?.checked,
            fecha_limite: tr.querySelector('.ci-prev-fecha')?.value || '',
            titulo: tr.querySelector('.ci-prev-titulo')?.value || '',
            responsable_nombre: tr.querySelector('.ci-prev-responsable')?.value || '',
            coordinador: tr.querySelector('.ci-prev-coordinador')?.value || '',
            unidad: tr.querySelector('.ci-prev-unidad')?.value || '',
            modulo: tr.querySelector('.ci-prev-modulo')?.value || 'General',
            estado: tr.querySelector('.ci-prev-estado')?.value || 'programado',
            observaciones: tr.querySelector('.ci-prev-observacion')?.value || '',
            prioridad: 'Media',
            requiere_evidencia: true,
        }));
    }

    async function confirmarCronograma() {
        const preview = state.previewCronograma;
        if (!preview?.cronograma_id) { message('No hay cronograma en vista previa.', 'error'); return; }
        const actividades = recopilarPreviewActividades();
        const seleccionadas = actividades.filter(a => !a.descartar);
        if (!seleccionadas.length) { message('Selecciona al menos una actividad para guardar.', 'error'); return; }
        const invalidas = seleccionadas.filter(a => !a.fecha_limite || !a.titulo);
        if (invalidas.length) { message('Hay actividades seleccionadas sin fecha o sin título. Corrígelas antes de guardar.', 'error'); return; }
        try {
            const data = await api('/confirmar-cronograma', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ cronograma_id: preview.cronograma_id, actividades })
            });
            const r = data.resultado || {};
            closeModal();
            state.previewCronograma = null;
            message(`Cronograma guardado: ${r.creados || 0} creados, ${r.duplicados || 0} duplicados, ${r.errores?.length || 0} errores.`);
            await cargarDashboard();
        } catch (err) {
            message(err?.message || 'No se pudo guardar el cronograma.', 'error');
        }
    }

    function exportarExcel() {
        const qs = new URLSearchParams({ periodo: state.periodo, anio: state.anio, ...state.filtros });
        window.descargarArchivoAutenticado(`${API}/exportar-excel?${qs.toString()}`).catch((error) => message(error.message, 'error'));
    }

    function exportarPdf() {
        const qs = new URLSearchParams({ periodo: state.periodo, anio: state.anio, ...state.filtros });
        window.descargarArchivoAutenticado(`${API}/exportar-pdf?${qs.toString()}`).catch((error) => message(error.message, 'error'));
    }

    async function subirEvidencia(id) {
        const input = document.getElementById(`ci-evidencia-${id}`);
        const file = input?.files?.[0];
        if (!file) { message('Selecciona un archivo de evidencia.', 'error'); return; }
        const fd = new FormData(); fd.append('file', file); fd.append('entregable_id', id); fd.append('marcar_entregado', '1');
        await api('/evidencias/upload', { method: 'POST', body: fd });
        closeModal(); message('Evidencia cargada y entregable marcado como entregado.'); await cargarDashboard();
    }

    async function marcarEntregado(id) { await api(`/entregables/${id}/entregar`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({}) }); closeModal(); message('Entregable marcado como entregado.'); await cargarDashboard(); }
    async function eliminarEntregable(id) { if (!confirm('¿Eliminar este entregable del calendario?')) return; await api(`/entregables/${id}`, { method: 'DELETE' }); closeModal(); message('Entregable eliminado.'); await cargarDashboard(); }

    function abrirModulo(modulo) {
        const m = String(modulo || '').toLowerCase(); closeModal();
        if (m.includes('nutric')) return mostrarSeccion('salud-nutricion');
        if (m.includes('talento')) return mostrarSeccion('talento');
        if (m.includes('plane')) return mostrarSeccion('planeacion-pedagogica');
        if (m.includes('reporte')) return mostrarSeccion('reportes-gerenciales');
        if (m.includes('cumplimiento')) return mostrarSeccion('cumplimiento');
        if (m.includes('coordinador')) return mostrarSeccion('gestion-coordinador');
        return mostrarSeccion('formatos');
    }

    function setPeriodo(value) { if (value) { state.periodo = value; state.anio = value.slice(0,4); const anio = document.getElementById('ci-anio'); if (anio) anio.value = state.anio; cargarDashboard(); } }
    function setAnio(value) { if (value) { state.anio = value; cargarDashboard(); } }
    function moverMes(delta) { const [y, m] = state.periodo.split('-').map(Number); const d = new Date(y, m - 1 + delta, 1); state.periodo = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; state.anio = String(d.getFullYear()); setText('ci-periodo', state.periodo); const p=document.getElementById('ci-periodo'); if(p)p.value=state.periodo; const a=document.getElementById('ci-anio'); if(a)a.value=state.anio; cargarDashboard(); }
    function cambiarVista(vista) { state.vista = vista; renderVista(); }
    function aplicarFiltros() { state.filtros = { coordinador: val('ci-filtro-coordinador'), unidad: val('ci-filtro-unidad'), modulo: val('ci-filtro-modulo'), estado: val('ci-filtro-estado') }; Object.keys(state.filtros).forEach(k => { if (!state.filtros[k]) delete state.filtros[k]; }); cargarDashboard(); }
    function limpiarFiltros() { ['ci-filtro-coordinador','ci-filtro-unidad','ci-filtro-modulo','ci-filtro-estado'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; }); state.filtros = {}; cargarDashboard(); }
    function val(id) { return document.getElementById(id)?.value || ''; }

    window.calendarioInteligenteInit = init;
    window.ciSetPeriodo = setPeriodo;
    window.ciSetAnio = setAnio;
    window.ciMoverMes = moverMes;
    window.ciCambiarVista = cambiarVista;
    window.ciAplicarFiltros = aplicarFiltros;
    window.ciLimpiarFiltros = limpiarFiltros;
    window.ciAbrirDia = abrirDia;
    window.ciAbrirEntregable = abrirEntregable;
    window.ciAbrirModalNuevo = abrirModalNuevo;
    window.ciCrearEntregable = crearEntregable;
    window.ciCargarCronograma = cargarCronograma;
    window.ciConfirmarCronograma = confirmarCronograma;
    window.ciExportarExcel = exportarExcel;
    window.ciExportarPdf = exportarPdf;
    window.ciSubirEvidencia = subirEvidencia;
    window.ciMarcarEntregado = marcarEntregado;
    window.ciEliminarEntregable = eliminarEntregable;
    window.ciCerrarModal = closeModal;
    window.ciAbrirModulo = abrirModulo;

    injectNavAndSection();
    document.addEventListener('DOMContentLoaded', injectNavAndSection);
})();
