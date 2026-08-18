(function () {
    'use strict';

    const VERSION = '2.3.0-alpha.47-panel-pack35';
    const numberFmt = new Intl.NumberFormat('es-CO');
    let initialized = false;
    let lastLogText = '';

    function n(value) {
        const parsed = Number(String(value ?? '').replace(/[^0-9.-]/g, ''));
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function text(id, fallback = '') {
        const el = document.getElementById(id);
        return (el?.textContent || fallback || '').trim();
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function setWidth(id, value) {
        const el = document.getElementById(id);
        if (el) el.style.width = `${Math.max(0, Math.min(100, Number(value) || 0))}%`;
    }

    function copyImage(sourceId, targetId, fallbackId) {
        const source = document.getElementById(sourceId);
        const target = document.getElementById(targetId);
        const fallback = document.getElementById(fallbackId);
        if (!target) return;
        const src = source?.getAttribute('src');
        const visible = src && !source.classList.contains('hidden');
        if (visible) {
            target.src = src;
            target.classList.remove('hidden');
            fallback?.classList.add('hidden');
        } else {
            target.classList.add('hidden');
            fallback?.classList.remove('hidden');
        }
    }

    function updateInstitution() {
        setText('alpha47-institucion-nombre', text('institucional-nombre-sidebar', 'PrimeraInfancia'));
        setText('alpha47-institucion-sigla', text('institucional-sigla-sidebar', 'Plataforma integral'));
        setText('alpha47-admin-nombre', text('institucional-admin-nombre-header', 'Administrador'));
        setText('alpha47-admin-cargo', text('institucional-admin-cargo-header', 'Administrador Plataforma'));
        copyImage('institucional-logo-sidebar', 'alpha47-logo', 'alpha47-logo-fallback');
        copyImage('institucional-foto-admin-header', 'alpha47-admin-foto', 'alpha47-admin-fallback');
    }

    function getSelectedUnitsCount() {
        const state = window.estadoSeleccionCuentame;
        if (state?.seleccionadas && typeof state.seleccionadas.size === 'number') return state.seleccionadas.size;
        return document.querySelectorAll('#selector-unidades-lista input[type="checkbox"]:checked').length;
    }

    function getTotalUnits() {
        const state = window.estadoDiagnostico;
        const unidades = state?.unidades || {};
        const count = Object.keys(unidades).filter(Boolean).length;
        return count || n(text('bmp-status-text').match(/(\d+)\s*unidad/i)?.[1] || 0) || (window.estadoSeleccionCuentame?.unidades?.length || 0);
    }

    function updateStats() {
        const total = n(text('stat-total'));
        const unidades = getTotalUnits();
        const alertas = n(text('stat-cobertura')) + n(text('stat-retiros')) + n(text('stat-nutricion'));
        setText('alpha47-total-users', numberFmt.format(total));
        setText('alpha47-total-units', numberFmt.format(unidades));
        setText('alpha47-selected-count', numberFmt.format(getSelectedUnitsCount()));
        setText('alpha47-alert-count', numberFmt.format(alertas));

        const values = [
            n(text('stat-edad-0-6-gestantes')),
            n(text('stat-edad-6-11')),
            n(text('stat-edad-1-2')),
            n(text('stat-edad-3-5'))
        ];
        const max = Math.max(...values, 1);
        values.forEach((value, index) => {
            setText(`alpha47-bar-${index}-label`, numberFmt.format(value));
            setWidth(`alpha47-bar-${index}`, Math.max(8, (value / max) * 100));
        });
    }

    function currentProgress() {
        const bar = document.getElementById('progress-bar');
        const style = bar?.style?.width || '';
        const match = style.match(/([0-9.]+)%/);
        return match ? Number(match[1]) : 0;
    }

    function updateProgress() {
        const pct = currentProgress();
        setWidth('alpha47-progress-fill', pct);
        setText('alpha47-progress-percent', `${Math.round(pct)}%`);
        const loadingText = text('loading-text', 'Listo para cargar base');
        const progressVisible = !document.getElementById('progress-container')?.classList.contains('hidden');
        setText('alpha47-current-stage', progressVisible || pct > 0 ? loadingText : 'Listo para cargar base');
        setText('alpha47-job-state', pct >= 100 ? 'Completado' : (pct > 0 ? 'En proceso' : 'En espera'));
    }

    function pushLog(title, description) {
        const log = document.getElementById('alpha47-activity-log');
        if (!log || !description || description === lastLogText) return;
        lastLogText = description;
        const row = document.createElement('div');
        row.innerHTML = `<b>${title}</b><span>${description}</span>`;
        log.prepend(row);
        while (log.children.length > 6) log.removeChild(log.lastElementChild);
    }

    function updateLogs() {
        const bmpMessage = document.getElementById('bmp-message');
        if (bmpMessage && !bmpMessage.classList.contains('hidden') && bmpMessage.textContent.trim()) {
            pushLog('Base Maestra', bmpMessage.textContent.trim());
        }
        const message = document.getElementById('message-box');
        if (message && !message.classList.contains('hidden') && message.textContent.trim()) {
            pushLog('Procesamiento Cuéntame', message.textContent.trim());
        }
    }

    function refresh() {
        if (!document.getElementById('alpha47-dashboard-operativo')) return;
        updateInstitution();
        updateStats();
        updateProgress();
        updateLogs();
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            try { window.lucide.createIcons(); } catch (_) {}
        }
    }

    function observeTargets() {
        const ids = [
            'stat-total', 'stat-cobertura', 'stat-retiros', 'stat-nutricion',
            'stat-edad-0-6-gestantes', 'stat-edad-6-11', 'stat-edad-1-2', 'stat-edad-3-5',
            'progress-bar', 'loading-text', 'bmp-message', 'message-box',
            'institucional-nombre-sidebar', 'institucional-sigla-sidebar',
            'institucional-admin-nombre-header', 'institucional-admin-cargo-header'
        ];
        const observer = new MutationObserver(refresh);
        ids.forEach((id) => {
            const el = document.getElementById(id);
            if (el) observer.observe(el, { childList: true, subtree: true, characterData: true, attributes: true });
        });
        const selector = document.getElementById('selector-unidades-lista');
        if (selector) observer.observe(selector, { childList: true, subtree: true, attributes: true });
    }

    function init() {
        if (initialized) return;
        initialized = true;
        refresh();
        observeTargets();
        setInterval(refresh, 5000);
        document.addEventListener('change', (ev) => {
            if (ev.target?.closest?.('#selector-unidades-lista')) refresh();
        });
        console.info(`[ALPHA47] Panel Principal Institucional activo (${VERSION}). Motor Pack35 sin modificar.`);
    }

    window.Alpha47PanelPrincipal = { refresh, version: VERSION };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
