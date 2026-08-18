let facEstado = {
    catalogos: { planes: [], paquetes: [], modulos: [] },
    dashboard: {},
    planes: [],
    suscripciones: [],
    pagos: [],
    movimientos: [],
    fundaciones: []
};

function facApi(path, options = {}) {
    return fetch(`${backendUrl}/api/facturacion${path}`, options).then(manejarRespuestaJson);
}

function facMensaje(texto, tipo = 'success') {
    const box = document.getElementById('fac-message');
    if (!box) return;
    box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
    box.textContent = texto;
    box.classList.remove('hidden');
}

function facMoney(value) {
    const numero = Number(value || 0);
    return numero.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
}

function facEstadoClase(estado) {
    const e = String(estado || '').toUpperCase();
    if (e === 'ACTIVA') return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300';
    if (e === 'POR_VENCER') return 'border-amber-500/30 bg-amber-500/10 text-amber-300';
    if (e === 'VENCIDA' || e === 'SUSPENDIDA') return 'border-rose-500/30 bg-rose-500/10 text-rose-300';
    return 'border-slate-500/30 bg-slate-500/10 text-slate-300';
}

function facturacionMostrarVista(vista) {
    document.querySelectorAll('.fac-view').forEach((el) => el.classList.toggle('hidden', el.id !== `fac-view-${vista}`));
    document.querySelectorAll('.fac-tab').forEach((btn) => btn.classList.toggle('active', btn.dataset.facTab === vista));
    if (vista === 'dashboard') facCargarDashboard();
    if (vista === 'planes') facCargarPlanes();
    if (vista === 'suscripciones') facCargarSuscripciones();
    if (vista === 'pagos') facCargarPagos();
    if (vista === 'creditos') facCargarCreditos();
}

async function facturacionInit() {
    await facCargarCatalogos();
    await facCargarFundaciones();
    facPrepararFechas();
    facturacionMostrarVista('dashboard');
}

function facPrepararFechas() {
    const hoy = new Date().toISOString().slice(0, 10);
    const mesDespues = new Date();
    mesDespues.setMonth(mesDespues.getMonth() + 1);
    ['fac-pago-fecha', 'fac-sub-inicio'].forEach(id => { const el = document.getElementById(id); if (el && !el.value) el.value = hoy; });
    ['fac-pago-vencimiento', 'fac-sub-vencimiento'].forEach(id => { const el = document.getElementById(id); if (el && !el.value) el.value = mesDespues.toISOString().slice(0, 10); });
}

async function facCargarCatalogos() {
    try {
        const data = await facApi('/catalogos');
        facEstado.catalogos = data || { planes: [], paquetes: [], modulos: [] };
        facEstado.planes = data.planes || [];
        facPopularSelects();
    } catch (error) {
        facMensaje(error.message || 'No se pudieron cargar catálogos de facturación.', 'error');
    }
}

async function facCargarFundaciones() {
    try {
        const data = await fetch(`${backendUrl}/api/fundaciones`).then(manejarRespuestaJson);
        facEstado.fundaciones = data.fundaciones || [];
        facPopularSelects();
    } catch (error) {
        facEstado.fundaciones = [];
    }
}

function facPopularSelects() {
    const fundaciones = facEstado.fundaciones || [];
    const planes = facEstado.catalogos?.planes || facEstado.planes || [];
    const paquetes = facEstado.catalogos?.paquetes || [];
    ['fac-sub-fundacion', 'fac-pago-fundacion', 'fac-credito-fundacion'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = fundaciones.map(f => `<option value="${escaparHtml(f.id)}">${escaparHtml(f.nombre)}</option>`).join('');
    });
    ['fac-sub-plan', 'fac-pago-plan'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = planes.map(p => `<option value="${escaparHtml(p.id)}">${escaparHtml(p.nombre)} · ${facMoney(p.precio_mensual)}</option>`).join('');
    });
    const paqueteEl = document.getElementById('fac-credito-paquete');
    if (paqueteEl) paqueteEl.innerHTML = '<option value="">Personalizado</option>' + paquetes.map(p => `<option value="${escaparHtml(p.id)}">${escaparHtml(p.nombre)} · ${p.creditos} créditos</option>`).join('');
}

async function facCargarDashboard() {
    try {
        const data = await facApi('/dashboard');
        facEstado.dashboard = data || {};
        facRenderDashboard(data);
    } catch (error) {
        facMensaje(error.message || 'No se pudo cargar dashboard de facturación.', 'error');
    }
}

function facRenderDashboard(data = {}) {
    const cards = document.getElementById('fac-dashboard-cards');
    const user = usuarioActual || authUser() || {};
    if (cards) {
        if (user.rol === 'SUPERADMIN') {
            const s = data.stats || {};
            cards.innerHTML = [
                ['Fundaciones', s.fundaciones_total || 0], ['Activas', s.activas || 0], ['Por vencer', s.por_vencer || 0],
                ['Vencidas', s.vencidas || 0], ['Ingresos mes', facMoney(s.ingresos_mes || 0)], ['Créditos mes', s.creditos_consumidos_mes || 0]
            ].map(([t,v]) => `<div class="fac-card"><p class="text-xs text-slate-400">${t}</p><h3 class="mt-2 text-2xl font-bold text-amber-300">${v}</h3></div>`).join('');
        } else {
            const sub = data.suscripcion || {};
            cards.innerHTML = [
                ['Plan', sub.plan_nombre || 'Sin plan'], ['Estado', sub.estado || ''], ['Vence', sub.fecha_vencimiento || ''],
                ['Días restantes', sub.dias_restantes ?? 0], ['Créditos', sub.creditos_disponibles || 0], ['Gracia', sub.fecha_fin_gracia || '']
            ].map(([t,v]) => `<div class="fac-card"><p class="text-xs text-slate-400">${t}</p><h3 class="mt-2 text-2xl font-bold text-amber-300">${escaparHtml(v)}</h3></div>`).join('');
        }
    }
    const alertas = document.getElementById('fac-alertas-list');
    if (alertas) {
        const list = data.alertas || [];
        alertas.innerHTML = list.length ? list.map(a => `<div class="rounded-xl border ${facEstadoClase(a.estado)} p-3"><strong>${escaparHtml(a.fundacion_nombre || 'Fundación')}</strong><br><span>Estado: ${escaparHtml(a.estado)} · Vence: ${escaparHtml(a.fecha_vencimiento)}</span></div>`).join('') : '<p class="text-slate-500">Sin alertas de suscripción.</p>';
    }
    const pagos = document.getElementById('fac-pagos-recientes');
    if (pagos) {
        const list = data.pagos_recientes || data.pagos || [];
        pagos.innerHTML = list.length ? list.slice(0, 10).map(p => `<div class="rounded-xl border border-slate-800 bg-slate-900/60 p-3"><strong>${escaparHtml(p.fundacion_nombre || 'Fundación')}</strong><br><span>${facMoney(p.valor_pagado)} · ${escaparHtml(p.metodo_pago)} · ${escaparHtml(p.fecha_pago)}</span></div>`).join('') : '<p class="text-slate-500">Sin pagos registrados.</p>';
    }
}

async function facCargarPlanes() {
    const data = await facApi('/planes');
    facEstado.planes = data.planes || [];
    facEstado.catalogos.planes = facEstado.planes;
    facPopularSelects();
    const tbody = document.getElementById('fac-planes-list');
    if (!tbody) return;
    tbody.innerHTML = facEstado.planes.map(p => `<tr class="hover:bg-slate-900/50"><td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(p.nombre)}</td><td class="px-3 py-2">${facMoney(p.precio_mensual)}</td><td class="px-3 py-2">${p.creditos_incluidos || 0}</td><td class="px-3 py-2">U:${p.limite_usuarios || 0} C:${p.limite_coordinadores || 0} Unid:${p.limite_unidades || 0}</td><td class="px-3 py-2"><span class="fac-badge ${facEstadoClase(p.estado)}">${escaparHtml(p.estado)}</span></td><td class="px-3 py-2"><button onclick='facEditarPlan(${JSON.stringify(p).replace(/'/g, "&#39;")})' class="text-cyan-300 text-xs">Editar</button></td></tr>`).join('');
}

function facEditarPlan(p) {
    document.getElementById('fac-plan-id').value = p.id || '';
    document.getElementById('fac-plan-nombre').value = p.nombre || '';
    document.getElementById('fac-plan-precio').value = p.precio_mensual || 0;
    document.getElementById('fac-plan-creditos').value = p.creditos_incluidos || 0;
    document.getElementById('fac-plan-usuarios').value = p.limite_usuarios || 0;
    document.getElementById('fac-plan-coordinadores').value = p.limite_coordinadores || 0;
    document.getElementById('fac-plan-unidades').value = p.limite_unidades || 0;
    document.getElementById('fac-plan-descripcion').value = p.descripcion || '';
    document.getElementById('fac-plan-modulos').value = Array.isArray(p.modulos_habilitados) ? p.modulos_habilitados.join(',') : (p.modulos_habilitados || '');
    facMensaje('Plan cargado para edición.', 'success');
}

async function facGuardarPlan() {
    const id = document.getElementById('fac-plan-id').value;
    const body = {
        nombre: document.getElementById('fac-plan-nombre').value,
        precio_mensual: Number(document.getElementById('fac-plan-precio').value || 0),
        creditos_incluidos: Number(document.getElementById('fac-plan-creditos').value || 0),
        limite_usuarios: Number(document.getElementById('fac-plan-usuarios').value || 0),
        limite_coordinadores: Number(document.getElementById('fac-plan-coordinadores').value || 0),
        limite_unidades: Number(document.getElementById('fac-plan-unidades').value || 0),
        descripcion: document.getElementById('fac-plan-descripcion').value,
        modulos_habilitados: document.getElementById('fac-plan-modulos').value.split(',').map(x => x.trim()).filter(Boolean),
        estado: 'ACTIVO'
    };
    try {
        await facApi(id ? `/planes/${id}` : '/planes', { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        facMensaje('Plan guardado correctamente.');
        document.getElementById('fac-plan-id').value = '';
        await facCargarCatalogos();
        await facCargarPlanes();
    } catch (error) { facMensaje(error.message || 'No se pudo guardar el plan.', 'error'); }
}

async function facCargarSuscripciones() {
    const data = await facApi('/suscripciones');
    facEstado.suscripciones = data.suscripciones || (data.suscripcion ? [data.suscripcion] : []);
    const tbody = document.getElementById('fac-suscripciones-list');
    if (!tbody) return;
    tbody.innerHTML = facEstado.suscripciones.map(s => `<tr class="hover:bg-slate-900/50"><td class="px-3 py-2 font-medium text-slate-200">${escaparHtml(s.fundacion_nombre || s.fundacion_id)}</td><td class="px-3 py-2">${escaparHtml(s.plan_nombre || s.plan_id)}</td><td class="px-3 py-2"><span class="fac-badge ${facEstadoClase(s.estado)}">${escaparHtml(s.estado)}</span></td><td class="px-3 py-2">${escaparHtml(s.fecha_vencimiento || '')}</td><td class="px-3 py-2">${escaparHtml(s.fecha_fin_gracia || '')}</td><td class="px-3 py-2">${s.creditos_disponibles || 0}</td><td class="px-3 py-2"><button onclick='facEditarSuscripcion(${JSON.stringify(s).replace(/'/g, "&#39;")})' class="text-cyan-300 text-xs">Editar</button></td></tr>`).join('');
}

function facEditarSuscripcion(s) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
    set('fac-sub-fundacion', s.fundacion_id); set('fac-sub-plan', s.plan_id); set('fac-sub-inicio', s.fecha_inicio); set('fac-sub-vencimiento', s.fecha_vencimiento); set('fac-sub-gracia', s.dias_gracia || 5); set('fac-sub-creditos', s.creditos_disponibles || 0); set('fac-sub-estado', s.estado || 'ACTIVA'); set('fac-sub-observaciones', s.observaciones || '');
}

async function facGuardarSuscripcion() {
    const body = {
        fundacion_id: document.getElementById('fac-sub-fundacion').value,
        plan_id: document.getElementById('fac-sub-plan').value,
        fecha_inicio: document.getElementById('fac-sub-inicio').value,
        fecha_vencimiento: document.getElementById('fac-sub-vencimiento').value,
        dias_gracia: document.getElementById('fac-sub-gracia').value,
        creditos_disponibles: document.getElementById('fac-sub-creditos').value,
        estado: document.getElementById('fac-sub-estado').value,
        observaciones: document.getElementById('fac-sub-observaciones').value
    };
    try { await facApi('/suscripciones', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); facMensaje('Suscripción guardada.'); await facCargarSuscripciones(); } catch (error) { facMensaje(error.message, 'error'); }
}

async function facCargarPagos() {
    const data = await facApi('/pagos');
    facEstado.pagos = data.pagos || [];
    const tbody = document.getElementById('fac-pagos-list');
    if (!tbody) return;
    tbody.innerHTML = facEstado.pagos.map(p => `<tr class="hover:bg-slate-900/50"><td class="px-3 py-2">${escaparHtml(p.fundacion_nombre || p.fundacion_id)}</td><td class="px-3 py-2">${escaparHtml(p.plan_nombre || p.plan_id)}</td><td class="px-3 py-2">${facMoney(p.valor_pagado)}</td><td class="px-3 py-2">${escaparHtml(p.metodo_pago)}</td><td class="px-3 py-2">${escaparHtml(p.fecha_pago)}</td><td class="px-3 py-2">${escaparHtml(p.fecha_vencimiento)}</td><td class="px-3 py-2">${escaparHtml(p.referencia_pago || '')}</td></tr>`).join('') || '<tr><td colspan="7" class="px-3 py-8 text-center text-slate-500">Sin pagos.</td></tr>';
}

async function facRegistrarPago() {
    const formData = new FormData();
    formData.append('fundacion_id', document.getElementById('fac-pago-fundacion').value);
    formData.append('plan_id', document.getElementById('fac-pago-plan').value);
    formData.append('valor_pagado', document.getElementById('fac-pago-valor').value);
    formData.append('metodo_pago', document.getElementById('fac-pago-metodo').value);
    formData.append('fecha_pago', document.getElementById('fac-pago-fecha').value);
    formData.append('fecha_vencimiento', document.getElementById('fac-pago-vencimiento').value);
    formData.append('referencia_pago', document.getElementById('fac-pago-referencia').value);
    formData.append('observaciones', document.getElementById('fac-pago-observaciones').value);
    const file = document.getElementById('fac-pago-comprobante').files[0];
    if (file) formData.append('comprobante', file);
    try { await facApi('/pagos', { method: 'POST', body: formData }); facMensaje('Pago registrado y suscripción actualizada.'); await facCargarPagos(); await facCargarSuscripciones(); await facCargarDashboard(); } catch (error) { facMensaje(error.message, 'error'); }
}

async function facCargarCreditos() {
    const mov = await facApi('/creditos/movimientos');
    facEstado.movimientos = mov.movimientos || [];
    const tbody = document.getElementById('fac-creditos-list');
    if (!tbody) return;
    tbody.innerHTML = facEstado.movimientos.map(m => `<tr class="hover:bg-slate-900/50"><td class="px-3 py-2">${escaparHtml(m.fecha_movimiento)}</td><td class="px-3 py-2">${escaparHtml(m.fundacion_nombre || m.fundacion_id)}</td><td class="px-3 py-2">${escaparHtml(m.tipo)}</td><td class="px-3 py-2">${escaparHtml(m.accion || '')}</td><td class="px-3 py-2">${m.creditos}</td><td class="px-3 py-2">${m.saldo_nuevo}</td><td class="px-3 py-2">${escaparHtml(m.descripcion || '')}</td></tr>`).join('') || '<tr><td colspan="7" class="px-3 py-8 text-center text-slate-500">Sin movimientos.</td></tr>';
}

async function facAsignarCreditos() {
    const body = {
        fundacion_id: document.getElementById('fac-credito-fundacion').value,
        paquete_id: document.getElementById('fac-credito-paquete').value,
        creditos: document.getElementById('fac-credito-cantidad').value,
        descripcion: document.getElementById('fac-credito-descripcion').value || 'Asignación manual de créditos'
    };
    try { await facApi('/creditos/asignar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }); facMensaje('Créditos asignados.'); await facCargarCreditos(); await facCargarSuscripciones(); await facCargarDashboard(); } catch (error) { facMensaje(error.message, 'error'); }
}
