(function () {
    const state = { loaded: false, data: null };

    function $(id) { return document.getElementById(id); }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function number(value) {
        return Number(value || 0).toLocaleString('es-CO');
    }

    function money(value) {
        const n = Number(value || 0);
        try {
            return n.toLocaleString('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 });
        } catch (_) {
            return `$${number(n)}`;
        }
    }

    function percent(value) {
        const n = Number(value || 0);
        return `${Math.max(0, Math.min(100, n)).toLocaleString('es-CO', { maximumFractionDigits: 1 })}%`;
    }

    function periodNow() {
        return new Date().toISOString().slice(0, 7);
    }

    function currentPeriodParts() {
        const value = $('gg-periodo')?.value || periodNow();
        const [anio, mes] = value.split('-').map((v) => parseInt(v, 10));
        return { anio: anio || new Date().getFullYear(), mes: mes || new Date().getMonth() + 1, value };
    }

    function dateText(value) {
        if (!value) return 'Sin fecha';
        const text = String(value).slice(0, 10);
        const parsed = new Date(`${text}T00:00:00`);
        if (Number.isNaN(parsed.getTime())) return String(value);
        return parsed.toLocaleDateString('es-CO', { year: 'numeric', month: 'short', day: '2-digit' });
    }

    function badge(value) {
        const raw = String(value || 'SIN ESTADO').toUpperCase();
        let cls = 'gg-badge-muted';
        if (['ACTIVA', 'ACTIVO', 'AL_DIA', 'AL DIA', 'CUMPLIDO', 'OK', 'ENTREGADO', 'APROBADO'].includes(raw)) cls = 'gg-badge-ok';
        if (['POR_VENCER', 'PENDIENTE', 'EN_PROCESO', 'AMARILLO', 'PROXIMO_A_VENCER', 'PRÓXIMO A VENCER'].includes(raw)) cls = 'gg-badge-warn';
        if (['VENCIDA', 'SUSPENDIDA', 'CANCELADA', 'ROJO', 'CRITICO', 'CRÍTICO', 'VENCE_HOY', 'VENCE HOY'].includes(raw)) cls = 'gg-badge-danger';
        return `<span class="gg-badge ${cls}">${escapeHtml(raw.replace(/_/g, ' '))}</span>`;
    }

    function setText(id, value) {
        const el = $(id);
        if (el) el.textContent = value;
    }

    function message(text, type = 'info') {
        const el = $('gg-message');
        if (!el) return;
        el.textContent = text || '';
        el.className = `min-h-5 text-sm ${type === 'error' ? 'text-rose-300' : type === 'ok' ? 'text-emerald-300' : 'text-amber-300'}`;
    }

    async function apiGet(path) {
        const response = await fetch(`${backendUrl}${path}`);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || data.message || 'No se pudo consultar Gerencia General.');
        return data;
    }

    function renderResumenEjecutivo(data = {}) {
        const box = $('gg-resumen-ejecutivo');
        if (!box) return;
        const ind = data.indicadores || {};
        const raw = String(data.resumen_ejecutivo || '').trim();
        const sentences = raw
            ? raw.split(/(?<=[.!?])\s+/).filter(Boolean)
            : ['No hay resumen ejecutivo disponible para el periodo seleccionado.'];

        box.innerHTML = `
            <div class="gg-summary-metrics">
                <div class="gg-summary-metric"><span>Operación activa</span><strong>${number(ind.fundaciones_activas)} fundación(es)</strong></div>
                <div class="gg-summary-metric"><span>Ingresos del mes</span><strong>${money(ind.ingresos_mes)}</strong></div>
                <div class="gg-summary-metric"><span>Alertas críticas</span><strong>${number(ind.alertas_criticas)}</strong></div>
                <div class="gg-summary-metric"><span>Cobertura incompleta</span><strong>${number(ind.unidades_cobertura_incompleta)} unidad(es)</strong></div>
            </div>
            <ul class="gg-summary-list">
                ${sentences.map((sentence) => `<li>${escapeHtml(sentence)}</li>`).join('')}
            </ul>
        `;
    }

    function renderIndicadores(ind = {}) {
        setText('gg-stat-fundaciones-activas', number(ind.fundaciones_activas));
        setText('gg-stat-fundaciones-vencidas', number(ind.fundaciones_vencidas));
        setText('gg-stat-ingresos-mes', money(ind.ingresos_mes));
        setText('gg-stat-creditos-consumidos', number(ind.creditos_consumidos));
        setText('gg-stat-usuarios-activos', number(ind.usuarios_activos));
        setText('gg-stat-formatos-generados', number(ind.formatos_generados));
        setText('gg-stat-entregables-pendientes', number(ind.entregables_pendientes));
        setText('gg-stat-alertas-criticas', number(ind.alertas_criticas));
        setText('gg-stat-nutricion-riesgo', number(ind.casos_nutricionales_riesgo));
        setText('gg-stat-coordinadores-bajo', number(ind.coordinadores_bajo_cumplimiento));
        setText('gg-stat-cobertura-incompleta', number(ind.unidades_cobertura_incompleta));
        setText('gg-stat-tickets-abiertos', number(ind.tickets_abiertos));
    }

    function renderLicencias(rows = []) {
        const body = $('gg-licencias-list');
        if (!body) return;
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="9" class="gg-empty">Sin licencias registradas.</td></tr>';
            return;
        }
        body.innerHTML = rows.map((row) => {
            const mods = Array.isArray(row.modulos_habilitados_lista) ? row.modulos_habilitados_lista : [];
            const modsShort = mods.length > 4 ? `${mods.slice(0, 4).join(', ')} +${mods.length - 4}` : mods.join(', ');
            const plan = row.plan || row.plan_contratado || 'SIN PLAN';
            return `<tr>
                <td><strong>${escapeHtml(row.fundacion || '')}</strong><div class="text-[11px] text-slate-500">${escapeHtml(row.nit || '')}</div></td>
                <td>${escapeHtml(plan)}</td>
                <td>${badge(row.estado_pago || row.estado_suscripcion || row.estado_fundacion)}</td>
                <td>${escapeHtml(dateText(row.fecha_inicio))}</td>
                <td>${escapeHtml(dateText(row.fecha_vencimiento))}</td>
                <td>${escapeHtml(row.dias_gracia ?? 0)}</td>
                <td>${number(row.usuarios_activos)} / ${row.usuarios_permitidos || '∞'}</td>
                <td>${number(row.creditos_disponibles)}</td>
                <td><span title="${escapeHtml(mods.join(', '))}">${escapeHtml(modsShort || 'Sin módulos')}</span></td>
            </tr>`;
        }).join('');
    }

    function renderAlertasEn(id, rows = [], emptyText = 'Sin alertas registradas.') {
        const box = $(id);
        if (!box) return;
        if (!rows.length) {
            box.innerHTML = `<div class="gg-empty">${escapeHtml(emptyText)}</div>`;
            return;
        }
        box.innerHTML = rows.slice(0, 12).map((row) => `<div class="gg-alert">
            <div class="flex items-center justify-between gap-2"><strong>${escapeHtml(row.tipo || row.origen || 'Alerta')}</strong>${badge(row.nivel || row.estado_pago || 'AMARILLO')}</div>
            <div class="gg-alert-text">${escapeHtml(row.mensaje || row.fundacion || row.descripcion || '')}</div>
        </div>`).join('');
    }

    function renderCobertura(rows = []) {
        const body = $('gg-unidades-incompletas-list');
        if (!body) return;
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="4" class="gg-empty">Sin unidades con cobertura incompleta.</td></tr>';
            return;
        }
        body.innerHTML = rows.map((row) => `<tr>
            <td>${escapeHtml(row.unidad || '')}</td>
            <td>${number(row.total_usuarios)}</td>
            <td>${number(row.total_gestantes)}</td>
            <td>${escapeHtml(row.fundacion || '')}</td>
        </tr>`).join('');
    }

    function renderCumplimiento(rows = []) {
        const body = $('gg-coordinadores-bajo-list');
        if (!body) return;
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="4" class="gg-empty">Sin coordinadores con bajo cumplimiento.</td></tr>';
            return;
        }
        body.innerHTML = rows.map((row) => `<tr>
            <td>${escapeHtml(row.coordinador || row.coordinador_nombre || 'Sin coordinador')}<div class="text-[11px] text-slate-500">${escapeHtml(row.fundacion || '')}</div></td>
            <td>${number(row.pendientes)}</td>
            <td>${number(row.vencidos || row.vencidas)}</td>
            <td>${percent(row.cumplimiento || row.porcentaje)}</td>
        </tr>`).join('');
    }

    function renderNutricion(rows = []) {
        const body = $('gg-nutricion-riesgo-list');
        if (!body) return;
        if (!rows.length) {
            body.innerHTML = '<tr><td colspan="4" class="gg-empty">Sin casos nutricionales en riesgo.</td></tr>';
            return;
        }
        body.innerHTML = rows.map((row) => `<tr>
            <td>${escapeHtml(row.unidad || '')}</td>
            <td>${escapeHtml(row.nombre_completo || row.nombre || '')}</td>
            <td>${escapeHtml(row.diagnostico_global || row.diagnostico || '')}</td>
            <td>${badge(row.nivel_alerta || row.nivel)}</td>
        </tr>`).join('');
    }

    function renderTendencia(id, rows = [], dataKey = 'valor', formatter = number) {
        const box = $(id);
        if (!box) return;
        if (!rows.length) {
            box.innerHTML = '<div class="gg-empty">Sin datos de tendencia.</div>';
            return;
        }
        const max = Math.max(...rows.map((r) => Number(r[dataKey] || 0)), 1);
        box.innerHTML = rows.map((row) => {
            const raw = Number(row[dataKey] || 0);
            const width = Math.max(4, Math.round((raw / max) * 100));
            return `<div class="gg-bar-row">
                <span>${escapeHtml(row.periodo || row.mes || '')}</span>
                <div class="gg-bar-track"><div class="gg-bar-fill" style="width:${width}%"></div></div>
                <strong>${escapeHtml(formatter(raw))}</strong>
            </div>`;
        }).join('');
    }

    function render(data) {
        renderResumenEjecutivo(data || {});
        renderIndicadores(data.indicadores || {});
        renderLicencias(data.licencias || []);
        renderAlertasEn('gg-alertas-pago-list', data.alertas_pago || [], 'Sin alertas de pago o créditos.');
        renderAlertasEn('gg-alertas-criticas-list', data.alertas_criticas || [], 'Sin alertas críticas operativas.');
        renderCobertura(data.unidades_cobertura_incompleta || []);
        renderCumplimiento(data.coordinadores_bajo_cumplimiento || []);
        renderNutricion(data.nutricion_riesgo || data.casos_nutricionales_detalle || []);
        renderTendencia('gg-tendencia-ingresos', data.tendencias?.ingresos || [], 'ingresos', money);
        renderTendencia('gg-tendencia-creditos', data.tendencias?.creditos || [], 'creditos', number);
        renderInteligencia(data.inteligencia_negocio || {});
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    function renderInteligencia(bi = {}) {
        const indicators=$('gg-bi-indicadores'), lights=$('gg-bi-semaforos');
        if(indicators) indicators.innerHTML=Object.entries(bi.indicadores||{}).map(([key,value])=>`<div class="gg-card"><span class="gg-label">${escapeHtml(key.replaceAll('_',' '))}</span><strong class="gg-card-value">${escapeHtml(number(value))}</strong></div>`).join('');
        if(lights) lights.innerHTML=(bi.semaforos||[]).map(item=>`<div class="gg-alert"><div class="flex justify-between"><strong>${escapeHtml(item.componente)}</strong>${badge(item.estado)}</div><div class="gg-alert-text">${escapeHtml(item.valor)} ${escapeHtml(item.unidad)} · ${escapeHtml(item.explicacion)}</div></div>`).join('')||'<div class="gg-empty">Sin indicadores para los filtros.</div>';
    }

    async function cargarDashboard() {
        const periodo = $('gg-periodo')?.value || periodNow();
        const [anio, mes] = periodo.split('-');
        message('Cargando Gerencia General...', 'info');
        try {
            const extra=[['contrato','gg-filtro-contrato'],['unidad','gg-filtro-unidad'],['coordinador','gg-filtro-coordinador'],['componente','gg-filtro-componente']].map(([k,id])=>[$(id)?.value,k]).filter(x=>x[0]).map(([v,k])=>`&${k}=${encodeURIComponent(v)}`).join('');
            const data = await apiGet(`/api/gerencia-general/dashboard?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}${extra}`);
            state.data = data;
            state.loaded = true;
            render(data);
            message('Tablero de Gerencia General actualizado.', 'ok');
        } catch (error) {
            console.error(error);
            message(error.message || 'No se pudo cargar Gerencia General.', 'error');
        }
    }

    function exportarExcel() {
        const { anio, mes } = currentPeriodParts();
        window.descargarArchivoAutenticado(`${backendUrl}/api/gerencia-general/exportar/excel?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}`).catch((error) => message(error.message, 'error'));
    }

    function exportarPDF() {
        const { anio, mes } = currentPeriodParts();
        window.descargarArchivoAutenticado(`${backendUrl}/api/gerencia-general/exportar/pdf?anio=${encodeURIComponent(anio)}&mes=${encodeURIComponent(mes)}`).catch((error) => message(error.message, 'error'));
    }

    function exportar(tipo) {
        if (String(tipo).toLowerCase() === 'pdf') return exportarPDF();
        return exportarExcel();
    }

    function init() {
        const periodo = $('gg-periodo');
        if (periodo && !periodo.value) periodo.value = periodNow();
        if (!state.loaded) cargarDashboard();
    }

    window.GerenciaGeneral = { init, cargarDashboard, exportar, exportarExcel, exportarPDF };
    window.gerenciaGeneralInit = init;
})();
