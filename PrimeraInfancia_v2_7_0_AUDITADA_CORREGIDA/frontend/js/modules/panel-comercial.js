const PanelComercial = (() => {
    let iniciado = false;
    let dataActual = null;

    const money = (value) => {
        const numero = Number(value || 0);
        return numero.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
    };

    const safe = (value) => escaparHtml(value ?? '');

    const badge = (value) => {
        const estado = String(value || '').toUpperCase();
        let cls = 'pc-badge-info';
        if (['ACTIVA', 'ACTIVO', 'RESUELTO', 'CERRADO'].includes(estado)) cls = 'pc-badge-ok';
        if (['POR_VENCER', 'EN_PROCESO', 'MEDIA', 'ALTA'].includes(estado)) cls = 'pc-badge-warn';
        if (['VENCIDA', 'SUSPENDIDA', 'CANCELADA', 'CRITICA', 'ROJO', 'ABIERTO'].includes(estado)) cls = 'pc-badge-danger';
        if (['ANULADO', 'INACTIVA'].includes(estado)) cls = '';
        return `<span class="pc-badge ${cls}">${safe(value || 'N/D')}</span>`;
    };

    async function api(path, options = {}) {
        const resp = await fetch(`${backendUrl}${path}`, options);
        const json = await resp.json().catch(() => ({}));
        if (!resp.ok) throw new Error(json.error || 'Error en Panel Comercial');
        return json;
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function renderStats(data) {
        const stats = data.stats || {};
        setText('pc-stat-fundaciones-activas', stats.fundaciones_activas || 0);
        setText('pc-stat-fundaciones-vencidas', stats.fundaciones_vencidas || 0);
        setText('pc-stat-ingresos-mes', money(stats.ingresos_mes || 0));
        setText('pc-stat-creditos-consumidos', stats.creditos_consumidos_mes || 0);
        setText('pc-stat-usuarios-activos', stats.usuarios_activos || 0);
        setText('pc-stat-tickets-abiertos', stats.tickets_abiertos || 0);
        const ultimo = data.ultimo_ingreso || {};
        setText('pc-stat-ultimo-ingreso', ultimo.username ? `${ultimo.username} · ${ultimo.fecha_ultima_conexion || ''}` : 'Sin registros');
        setText('pc-stat-alertas-pago', Array.isArray(data.alertas_pago) ? data.alertas_pago.length : 0);
    }

    function renderFundaciones(data) {
        const cont = document.getElementById('pc-fundaciones-list');
        if (!cont) return;
        const rows = data.fundaciones || [];
        if (!rows.length) {
            cont.innerHTML = `<tr><td colspan="9" class="pc-empty">No hay fundaciones para mostrar.</td></tr>`;
            return;
        }
        cont.innerHTML = rows.map(f => `
            <tr>
                <td class="font-semibold text-slate-200">${safe(f.nombre)}</td>
                <td>${safe(f.nit || '')}</td>
                <td>${badge(f.estado)}</td>
                <td>${badge(f.suscripcion_estado || 'Sin suscripción')}</td>
                <td>${safe(f.plan_nombre || '')}</td>
                <td>${safe(f.fecha_vencimiento || '')}</td>
                <td>${safe(f.creditos_disponibles ?? 0)}</td>
                <td>${safe(f.usuarios_activos ?? 0)}</td>
                <td>${safe(f.ultimo_ingreso || 'Sin ingreso')}</td>
            </tr>
        `).join('');
    }

    function renderAlertas(data) {
        const cont = document.getElementById('pc-alertas-list');
        if (!cont) return;
        const rows = data.alertas_pago || [];
        if (!rows.length) {
            cont.innerHTML = `<div class="pc-empty">Sin alertas comerciales o de pago.</div>`;
            return;
        }
        cont.innerHTML = rows.map(a => `
            <div class="pc-card-soft p-3 flex flex-col md:flex-row md:items-center md:justify-between gap-2">
                <div>
                    <div>${badge(a.nivel || 'INFO')} <span class="font-semibold text-slate-200 ml-2">${safe(a.fundacion_nombre || 'Fundación')}</span></div>
                    <p class="mt-1 text-sm text-slate-400">${safe(a.mensaje)}</p>
                </div>
                <div class="text-xs text-slate-500 text-right">${safe(a.tipo || '')}<br>${safe(a.fecha_vencimiento || '')}</div>
            </div>
        `).join('');
    }

    function renderTickets(data) {
        const cont = document.getElementById('pc-tickets-list');
        if (!cont) return;
        const rows = data.tickets || dataActual?.tickets || [];
        if (!rows.length) {
            cont.innerHTML = `<tr><td colspan="7" class="pc-empty">No hay tickets de soporte registrados.</td></tr>`;
            return;
        }
        cont.innerHTML = rows.map(t => `
            <tr>
                <td class="font-semibold text-slate-200">#${safe(t.id)} · ${safe(t.titulo)}</td>
                <td>${safe(t.fundacion_nombre || '')}</td>
                <td>${safe(t.categoria || '')}</td>
                <td>${badge(t.prioridad)}</td>
                <td>${badge(t.estado)}</td>
                <td>${safe(t.fecha_creacion || '')}</td>
                <td>
                    <div class="flex flex-wrap gap-2">
                        <button class="pc-btn-secondary" onclick="PanelComercial.cambiarEstadoTicket(${Number(t.id)}, 'EN_PROCESO')">En proceso</button>
                        <button class="pc-btn-secondary" onclick="PanelComercial.cambiarEstadoTicket(${Number(t.id)}, 'RESUELTO')">Resolver</button>
                        <button class="pc-btn-secondary" onclick="PanelComercial.comentarTicket(${Number(t.id)})">Comentar</button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    function renderIngresos(data) {
        const cont = document.getElementById('pc-ingresos-list');
        if (!cont) return;
        const rows = data.ingresos_recientes || [];
        if (!rows.length) {
            cont.innerHTML = `<tr><td colspan="6" class="pc-empty">No hay pagos recientes.</td></tr>`;
            return;
        }
        cont.innerHTML = rows.slice(0, 20).map(p => `
            <tr>
                <td>${safe(p.fecha_pago)}</td>
                <td class="font-semibold text-slate-200">${safe(p.fundacion_nombre || '')}</td>
                <td>${safe(p.plan_nombre || '')}</td>
                <td>${money(p.valor_pagado)}</td>
                <td>${safe(p.metodo_pago || '')}</td>
                <td>${safe(p.referencia_pago || '')}</td>
            </tr>
        `).join('');
    }

    function renderConsumo(data) {
        const cont = document.getElementById('pc-consumo-list');
        if (!cont) return;
        const rows = data.consumo_creditos || [];
        if (!rows.length) {
            cont.innerHTML = `<tr><td colspan="6" class="pc-empty">No hay movimientos de créditos.</td></tr>`;
            return;
        }
        cont.innerHTML = rows.slice(0, 30).map(m => `
            <tr>
                <td>${safe(m.fecha_movimiento)}</td>
                <td>${safe(m.fundacion_nombre || '')}</td>
                <td>${safe(m.tipo || '')}</td>
                <td>${safe(m.accion || '')}</td>
                <td>${safe(m.creditos || 0)}</td>
                <td>${safe(m.saldo_nuevo ?? '')}</td>
            </tr>
        `).join('');
    }

    async function cargarDashboard() {
        const msg = document.getElementById('pc-message');
        if (msg) msg.textContent = 'Cargando panel comercial...';
        try {
            const data = await api('/api/panel-comercial/dashboard');
            dataActual = data;
            renderStats(data);
            renderFundaciones(data);
            renderAlertas(data);
            renderIngresos(data);
            renderConsumo(data);
            const tickets = await api('/api/panel-comercial/tickets');
            dataActual.tickets = tickets.tickets || [];
            renderTickets(tickets);
            if (msg) msg.textContent = '';
            if (typeof lucide !== 'undefined') lucide.createIcons();
        } catch (error) {
            if (msg) msg.textContent = error.message || 'No se pudo cargar Panel Comercial.';
        }
    }

    async function crearTicket() {
        const payload = {
            titulo: document.getElementById('pc-ticket-titulo')?.value || '',
            categoria: document.getElementById('pc-ticket-categoria')?.value || 'Soporte general',
            prioridad: document.getElementById('pc-ticket-prioridad')?.value || 'MEDIA',
            descripcion: document.getElementById('pc-ticket-descripcion')?.value || '',
            modulo_origen: document.getElementById('pc-ticket-modulo')?.value || 'Panel Comercial'
        };
        try {
            await api('/api/panel-comercial/tickets', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            ['pc-ticket-titulo','pc-ticket-descripcion','pc-ticket-modulo'].forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
            await cargarDashboard();
        } catch (error) {
            alert(error.message || 'No se pudo crear el ticket.');
        }
    }

    async function cambiarEstadoTicket(id, estado) {
        try {
            const actual = (dataActual?.tickets || []).find(t => Number(t.id) === Number(id));
            await api(`/api/panel-comercial/tickets/${encodeURIComponent(id)}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    titulo: actual?.titulo || `Ticket ${id}`,
                    descripcion: actual?.descripcion || '',
                    categoria: actual?.categoria || 'Soporte general',
                    prioridad: actual?.prioridad || 'MEDIA',
                    estado
                })
            });
            await cargarDashboard();
        } catch (error) {
            alert(error.message || 'No se pudo actualizar el ticket.');
        }
    }

    async function comentarTicket(id) {
        const comentario = prompt('Comentario para el ticket:');
        if (!comentario) return;
        try {
            await api(`/api/panel-comercial/tickets/${encodeURIComponent(id)}/comentarios`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ comentario })
            });
            await cargarDashboard();
        } catch (error) {
            alert(error.message || 'No se pudo comentar el ticket.');
        }
    }

    function exportarExcel() {
        window.descargarArchivoAutenticado(`${backendUrl}/api/panel-comercial/exportar/excel`).catch((error) => alert(error.message || 'No se pudo exportar el panel comercial.'));
    }

    function init() {
        if (!iniciado) {
            iniciado = true;
            const cat = document.getElementById('pc-ticket-categoria');
            if (cat && !cat.options.length) {
                ['Soporte general','Pago y suscripción','Créditos','Error técnico','Capacitación','Solicitud comercial','Mejora'].forEach(v => cat.insertAdjacentHTML('beforeend', `<option value="${v}">${v}</option>`));
            }
        }
        cargarDashboard();
    }

    return { init, cargarDashboard, crearTicket, cambiarEstadoTicket, comentarTicket, exportarExcel };
})();

window.panelComercialInit = PanelComercial.init;
window.PanelComercial = PanelComercial;
