(function () {
    const api = () => `${window.backendUrl || backendUrl}/api/reportes-gerenciales`;

    function el(id) { return document.getElementById(id); }

    function htmlEscape(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function periodoActual() {
        const input = el('rg-periodo');
        const now = new Date();
        if (input && !input.value) input.value = now.toISOString().slice(0, 7);
        return input?.value || now.toISOString().slice(0, 7);
    }

    function periodoMesAnio() {
        const periodo = periodoActual();
        const [anio, mes] = periodo.split('-').map(Number);
        return { anio, mes };
    }

    function setMessage(texto, tipo = 'success') {
        const box = el('rg-message');
        if (!box) return;
        box.className = `mt-4 rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300' : 'bg-rose-500/10 border border-rose-500/20 text-rose-300'}`;
        box.textContent = texto;
        box.classList.remove('hidden');
    }

    function renderCards(indicadores = {}) {
        const box = el('rg-indicadores');
        if (!box) return;
        const principales = [
            ['Beneficiarios activos', 'users'],
            ['Unidades con participantes', 'building-2'],
            ['Entregables pendientes', 'clock'],
            ['Entregables vencidos', 'triangle-alert'],
            ['Casos nutricionales críticos', 'heart-pulse'],
            ['Alertas abiertas', 'bell'],
        ];
        box.innerHTML = principales.map(([key, icon]) => `
            <div class="rg-card">
                <div class="flex items-center justify-between gap-3">
                    <p class="text-xs text-slate-400">${htmlEscape(key)}</p>
                    <i data-lucide="${icon}" class="w-4 h-4 text-indigo-300"></i>
                </div>
                <h3 class="mt-2 text-2xl font-bold text-slate-100">${htmlEscape(indicadores[key] ?? 0)}</h3>
            </div>
        `).join('');
    }

    function renderList(id, items, empty, template) {
        const box = el(id);
        if (!box) return;
        if (!Array.isArray(items) || !items.length) {
            box.innerHTML = `<div class="rg-empty">${htmlEscape(empty)}</div>`;
            return;
        }
        box.innerHTML = items.map(template).join('');
    }

    function renderDashboard(data = {}) {
        renderCards(data.indicadores || {});
        renderList('rg-hallazgos', data.hallazgos || [], 'Sin hallazgos críticos registrados.', (h) => `
            <div class="rg-item"><span class="rg-badge">${htmlEscape(h.nivel || '')}</span><strong>${htmlEscape(h.titulo || '')}</strong><p>${htmlEscape(h.detalle || '')}</p></div>
        `);
        renderList('rg-alertas', data.alertas || [], 'Sin alertas abiertas.', (a) => `
            <div class="rg-item"><span class="rg-badge rg-badge-warn">${htmlEscape(a.nivel || '')}</span><strong>${htmlEscape(a.tipo || 'Alerta')}</strong><p>${htmlEscape(a.mensaje || '')}</p></div>
        `);
        renderList('rg-pendientes', data.pendientes || [], 'Sin pendientes registrados.', (p) => `
            <div class="rg-item"><strong>${htmlEscape(p.titulo || p.tipo || '')}</strong><p>${htmlEscape(p.unidad || '')} · ${htmlEscape(p.responsable || '')} · ${htmlEscape(p.estado || '')}</p></div>
        `);
        renderList('rg-recomendaciones', data.recomendaciones || [], 'Sin recomendaciones automáticas.', (r) => `
            <div class="rg-item"><span class="rg-badge rg-badge-ok">${htmlEscape(r.prioridad || '')}</span><p>${htmlEscape(r.recomendacion || '')}</p></div>
        `);
        renderHistorial(data.historial || []);
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    function renderHistorial(reportes = []) {
        const body = el('rg-historial');
        if (!body) return;
        if (!reportes.length) {
            body.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center text-slate-500">Sin reportes generados.</td></tr>';
            return;
        }
        body.innerHTML = reportes.map((r) => `
            <tr class="hover:bg-slate-900/50">
                <td class="px-4 py-3">${htmlEscape(r.periodo || '')}</td>
                <td class="px-4 py-3">${htmlEscape(r.titulo || 'Reporte gerencial')}</td>
                <td class="px-4 py-3">${htmlEscape(r.total_hallazgos || 0)}</td>
                <td class="px-4 py-3">${htmlEscape(r.total_alertas || 0)}</td>
                <td class="px-4 py-3">${htmlEscape((r.fecha_generacion || '').replace('T', ' '))}</td>
                <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-2">
                        <button onclick="rgDescargar(${Number(r.id)}, 'pdf')" class="rg-btn rg-btn-outline">PDF</button>
                        <button onclick="rgDescargar(${Number(r.id)}, 'excel')" class="rg-btn rg-btn-outline">Excel</button>
                    </div>
                </td>
            </tr>
        `).join('');
    }

    async function rgInit() {
        periodoActual();
        try {
            const resp = await fetch(`${api()}/dashboard`);
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo cargar el dashboard de reportes.');
            renderDashboard(data);
        } catch (error) {
            setMessage(error.message || 'No se pudo cargar Reportes Gerenciales.', 'error');
        }
    }

    async function rgGenerar() {
        const { mes, anio } = periodoMesAnio();
        setMessage('Generando reporte ejecutivo con indicadores, hallazgos, alertas, recomendaciones y tablas...', 'success');
        try {
            const resp = await fetch(`${api()}/generar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mes, anio })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo generar el reporte.');
            setMessage(data.message || 'Reporte generado correctamente.', 'success');
            renderDashboard({
                indicadores: data.indicadores,
                hallazgos: data.hallazgos,
                alertas: data.alertas,
                pendientes: data.pendientes,
                recomendaciones: data.recomendaciones,
                historial: []
            });
            await rgCargarHistorial();
        } catch (error) {
            setMessage(error.message || 'Error al generar reporte gerencial.', 'error');
        }
    }

    async function rgCargarHistorial() {
        try {
            const resp = await fetch(`${api()}/historial`);
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo cargar historial.');
            renderHistorial(data.reportes || []);
        } catch (error) {
            setMessage(error.message || 'Error al cargar historial.', 'error');
        }
    }

    function rgDescargar(id, tipo) {
        window.descargarArchivoAutenticado(`${api()}/${encodeURIComponent(id)}/descargar/${encodeURIComponent(tipo)}`).catch((error) => setMessage(error.message || 'No se pudo descargar el reporte.', 'error'));
    }

    window.rgInit = rgInit;
    window.rgGenerar = rgGenerar;
    window.rgCargarHistorial = rgCargarHistorial;
    window.rgDescargar = rgDescargar;
})();
