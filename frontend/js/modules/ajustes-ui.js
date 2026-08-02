(function () {
    const STORAGE_KEY = 'PRIMERA_INFANCIA_UI_SETTINGS';
    const SCOPE_KEY = 'PRIMERA_INFANCIA_UI_SETTINGS_SCOPE';

    const DEFAULTS = {
        preset: 'oscuro-icbf',
        primaryColor: '#4f46e5',
        primaryHoverColor: '#4338ca',
        accentColor: '#06b6d4',
        backgroundColor: '#020617',
        surfaceColor: '#0f172a',
        surfaceSoftColor: '#1e293b',
        borderColor: '#334155',
        textColor: '#f8fafc',
        mutedTextColor: '#94a3b8',
        successColor: '#10b981',
        warningColor: '#f59e0b',
        dangerColor: '#ef4444',
        radius: '16px',
        density: 'comfortable',
        fontScale: '100',
        sidebarMode: 'normal',
        reduceMotion: false
    };

    const PRESETS = {
        'oscuro-icbf': DEFAULTS,
        'azul-profesional': { ...DEFAULTS, primaryColor: '#2563eb', primaryHoverColor: '#1d4ed8', accentColor: '#0891b2' },
        'verde-institucional': { ...DEFAULTS, primaryColor: '#059669', primaryHoverColor: '#047857', accentColor: '#65a30d' },
        'morado-ejecutivo': { ...DEFAULTS, primaryColor: '#7c3aed', primaryHoverColor: '#6d28d9', accentColor: '#d946ef' },
        'alto-contraste': { ...DEFAULTS, primaryColor: '#facc15', primaryHoverColor: '#eab308', accentColor: '#22d3ee', backgroundColor: '#000000', surfaceColor: '#0a0a0a', surfaceSoftColor: '#171717', borderColor: '#facc15', textColor: '#ffffff', mutedTextColor: '#e5e7eb' },
        'claro': { ...DEFAULTS, primaryColor: '#4f46e5', primaryHoverColor: '#4338ca', accentColor: '#0891b2', backgroundColor: '#f8fafc', surfaceColor: '#ffffff', surfaceSoftColor: '#e2e8f0', borderColor: '#cbd5e1', textColor: '#0f172a', mutedTextColor: '#475569' }
    };

    function usuarioActualSeguro() {
        try {
            if (window.usuarioActual) return window.usuarioActual;
            const raw = sessionStorage.getItem('primeraInfanciaAuthUser') || localStorage.getItem('primeraInfanciaAuthUser') || sessionStorage.getItem('authUser') || localStorage.getItem('authUser');
            return raw ? JSON.parse(raw) : {};
        } catch (_) {
            return {};
        }
    }

    function rolActual() {
        return String(usuarioActualSeguro()?.rol || '').trim().toUpperCase();
    }

    function puedeGuardarTemaInstitucional() {
        return ['SUPERADMIN', 'GERENTE'].includes(rolActual());
    }

    function tienePreferenciaPersonal() {
        try { return localStorage.getItem(SCOPE_KEY) === 'personal'; } catch (_) { return false; }
    }

    function marcarPreferenciaPersonal() {
        try { localStorage.setItem(SCOPE_KEY, 'personal'); } catch (_) {}
    }

    function marcarPreferenciaInstitucional() {
        try { localStorage.setItem(SCOPE_KEY, 'institucional'); } catch (_) {}
    }

    function limpiarPreferenciaPersonal() {
        try { localStorage.removeItem(SCOPE_KEY); } catch (_) {}
    }

    function mergeSettings(value) {
        return { ...DEFAULTS, ...(value || {}) };
    }

    function readLocal() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            return raw ? mergeSettings(JSON.parse(raw)) : { ...DEFAULTS };
        } catch (_) {
            return { ...DEFAULTS };
        }
    }

    function saveLocal(settings) {
        try { localStorage.setItem(STORAGE_KEY, JSON.stringify(mergeSettings(settings))); } catch (_) {}
    }

    function setVar(name, value) {
        document.documentElement.style.setProperty(name, value);
    }

    function apply(settings) {
        const s = mergeSettings(settings);
        const root = document.documentElement;
        root.classList.add('theme-pi');
        root.classList.toggle('reduce-motion', !!s.reduceMotion);
        root.dataset.density = s.density || 'comfortable';
        root.dataset.sidebar = s.sidebarMode || 'normal';
        root.style.fontSize = `${s.fontScale || '100'}%`;
        setVar('--pi-bg', s.backgroundColor);
        setVar('--pi-surface', s.surfaceColor);
        setVar('--pi-surface-soft', s.surfaceSoftColor);
        setVar('--pi-border', s.borderColor);
        setVar('--pi-text', s.textColor);
        setVar('--pi-muted', s.mutedTextColor);
        setVar('--pi-primary', s.primaryColor);
        setVar('--pi-primary-hover', s.primaryHoverColor || s.primaryColor);
        setVar('--pi-accent', s.accentColor);
        setVar('--pi-success', s.successColor);
        setVar('--pi-warning', s.warningColor);
        setVar('--pi-danger', s.dangerColor);
        setVar('--pi-radius', s.radius || '16px');
        saveLocal(s);
        updatePreview(s);
    }

    function updatePreview(settings) {
        const preview = document.getElementById('ajustes-preview');
        if (!preview) return;
        preview.innerHTML = `
            <div class="flex items-center justify-between gap-3">
                <div>
                    <p class="text-sm font-semibold">Vista previa institucional</p>
                    <p class="text-xs opacity-80">Tarjeta, botón, texto y borde usando el tema seleccionado.</p>
                </div>
                <button class="rounded-xl px-3 py-2 text-xs text-white" style="background:${settings.primaryColor}">Botón</button>
            </div>
            <div class="mt-3 grid grid-cols-3 gap-2 text-xs">
                <span class="rounded-lg border px-2 py-1" style="border-color:${settings.borderColor};color:${settings.textColor}">Texto</span>
                <span class="rounded-lg border px-2 py-1" style="border-color:${settings.accentColor};color:${settings.accentColor}">Acento</span>
                <span class="rounded-lg border px-2 py-1" style="border-color:${settings.warningColor};color:${settings.warningColor}">Alerta</span>
            </div>
        `;
    }

    function fillForm(settings) {
        const s = mergeSettings(settings);
        const set = (id, value) => { const el = document.getElementById(id); if (el) el.value = value; };
        set('ajustes-preset', s.preset);
        set('ajustes-primary', s.primaryColor);
        set('ajustes-primary-hover', s.primaryHoverColor);
        set('ajustes-accent', s.accentColor);
        set('ajustes-bg', s.backgroundColor);
        set('ajustes-surface', s.surfaceColor);
        set('ajustes-surface-soft', s.surfaceSoftColor);
        set('ajustes-border', s.borderColor);
        set('ajustes-text', s.textColor);
        set('ajustes-muted', s.mutedTextColor);
        set('ajustes-radius', s.radius);
        set('ajustes-density', s.density);
        set('ajustes-font-scale', s.fontScale);
        set('ajustes-sidebar-mode', s.sidebarMode);
        const reduce = document.getElementById('ajustes-reduce-motion');
        if (reduce) reduce.checked = !!s.reduceMotion;
        updatePreview(s);
    }

    function readForm() {
        const value = (id) => document.getElementById(id)?.value;
        return mergeSettings({
            preset: value('ajustes-preset') || 'personalizado',
            primaryColor: value('ajustes-primary'),
            primaryHoverColor: value('ajustes-primary-hover'),
            accentColor: value('ajustes-accent'),
            backgroundColor: value('ajustes-bg'),
            surfaceColor: value('ajustes-surface'),
            surfaceSoftColor: value('ajustes-surface-soft'),
            borderColor: value('ajustes-border'),
            textColor: value('ajustes-text'),
            mutedTextColor: value('ajustes-muted'),
            radius: value('ajustes-radius'),
            density: value('ajustes-density'),
            fontScale: value('ajustes-font-scale'),
            sidebarMode: value('ajustes-sidebar-mode'),
            reduceMotion: document.getElementById('ajustes-reduce-motion')?.checked || false
        });
    }

    function mensaje(texto, tipo = 'success') {
        const box = document.getElementById('ajustes-message');
        if (!box) return;
        box.className = `rounded-xl px-4 py-3 text-sm ${tipo === 'success' ? 'bg-emerald-500/10 text-emerald-300 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-300 border border-rose-500/20'}`;
        box.textContent = texto;
        box.classList.remove('hidden');
    }

    function applyPreset() {
        const preset = document.getElementById('ajustes-preset')?.value || 'oscuro-icbf';
        const settings = mergeSettings(PRESETS[preset] || DEFAULTS);
        settings.preset = preset;
        fillForm(settings);
        apply(settings);
    }

    async function loadRemote() {
        const localSettings = readLocal();

        // Los perfiles operativos pueden mantener un tema personal en su navegador.
        // Si existe preferencia personal, no se sobrescribe con el tema institucional.
        if (tienePreferenciaPersonal()) {
            fillForm(localSettings);
            apply(localSettings);
            actualizarAvisoAlcance();
            return;
        }

        try {
            const resp = await fetch(`${backendUrl}/api/ajustes-ui`);
            if (!resp.ok) throw new Error('No se pudieron consultar los ajustes');
            const data = await resp.json();
            const settings = mergeSettings(data.settings || localSettings);
            fillForm(settings);
            apply(settings);
            marcarPreferenciaInstitucional();
        } catch (_) {
            fillForm(localSettings);
            apply(localSettings);
        }
        actualizarAvisoAlcance();
    }

    async function saveRemote() {
        const settings = readForm();
        apply(settings);

        if (!puedeGuardarTemaInstitucional()) {
            marcarPreferenciaPersonal();
            mensaje('Ajustes guardados para tu perfil en este navegador. No afectan a otros usuarios de la fundación.', 'success');
            actualizarAvisoAlcance();
            return;
        }

        try {
            const resp = await fetch(`${backendUrl}/api/ajustes-ui`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudieron guardar los ajustes');
            apply(data.settings || settings);
            fillForm(data.settings || settings);
            marcarPreferenciaInstitucional();
            mensaje(data.message || 'Tema institucional guardado para la fundación.', 'success');
        } catch (error) {
            marcarPreferenciaPersonal();
            mensaje('No se pudo guardar en servidor. Se guardó como preferencia local en este navegador.', 'success');
        }
        actualizarAvisoAlcance();
    }

    async function resetRemote() {
        apply(DEFAULTS);
        fillForm(DEFAULTS);
        limpiarPreferenciaPersonal();

        if (!puedeGuardarTemaInstitucional()) {
            mensaje('Ajustes personales restablecidos en este navegador.', 'success');
            actualizarAvisoAlcance();
            return;
        }

        try {
            const resp = await fetch(`${backendUrl}/api/ajustes-ui/restablecer`, { method: 'POST' });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo restablecer');
            apply(data.settings || DEFAULTS);
            fillForm(data.settings || DEFAULTS);
            marcarPreferenciaInstitucional();
            mensaje(data.message || 'Tema institucional restablecido.', 'success');
        } catch (error) {
            mensaje('Ajustes locales restablecidos. No se pudo restablecer el tema institucional en servidor.', 'success');
        }
        actualizarAvisoAlcance();
    }

    function renderAudit(data) {
        const box = document.getElementById('ajustes-auditoria');
        if (!box) return;
        const totals = data?.totales || {};
        const rows = (data?.archivos || []).map((item) => `
            <tr class="border-b border-slate-800/70">
                <td class="px-3 py-2">${escapeHtml((item.archivo || '').replace(/^.*PrimeraInfancia\/?/, ''))}</td>
                <td class="px-3 py-2 text-right">${item.clases_color_quemadas || 0}</td>
                <td class="px-3 py-2 text-right">${item.onclick_inline || 0}</td>
                <td class="px-3 py-2 text-right">${item.ids_hardcoded || 0}</td>
            </tr>
        `).join('');
        const recs = (data?.recomendaciones || []).map((r) => `<li>${escapeHtml(r)}</li>`).join('');
        box.innerHTML = `
            <div class="grid gap-3 md:grid-cols-4">
                <div class="ajustes-preview"><p class="text-xs opacity-70">Archivos revisados</p><strong>${totals.archivos_revisados || 0}</strong></div>
                <div class="ajustes-preview"><p class="text-xs opacity-70">Colores quemados</p><strong>${totals.clases_color_quemadas || 0}</strong></div>
                <div class="ajustes-preview"><p class="text-xs opacity-70">onclick inline</p><strong>${totals.onclick_inline || 0}</strong></div>
                <div class="ajustes-preview"><p class="text-xs opacity-70">IDs directos</p><strong>${totals.ids_hardcoded || 0}</strong></div>
            </div>
            <div class="mt-4 overflow-x-auto"><table class="w-full text-left text-xs text-slate-400"><thead class="bg-slate-900 text-slate-300 uppercase"><tr><th class="px-3 py-2">Archivo</th><th class="px-3 py-2 text-right">Color</th><th class="px-3 py-2 text-right">onclick</th><th class="px-3 py-2 text-right">IDs</th></tr></thead><tbody>${rows}</tbody></table></div>
            <ul class="mt-4 list-disc pl-5 text-xs text-slate-400 space-y-1">${recs}</ul>
        `;
    }

    function escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    async function loadAudit() {
        const box = document.getElementById('ajustes-auditoria');
        if (!box) return;

        if (!puedeGuardarTemaInstitucional()) {
            box.innerHTML = `
                <div class="rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
                    <p class="font-medium text-slate-200">Auditoría técnica disponible para administración.</p>
                    <p class="mt-2">Tu perfil puede personalizar tema, colores, densidad y tamaño de texto sin afectar a otros usuarios.</p>
                </div>
            `;
            return;
        }

        box.innerHTML = '<p class="text-sm text-slate-400">Analizando componentes visuales...</p>';
        try {
            const resp = await fetch(`${backendUrl}/api/ajustes-ui/auditoria-ux`);
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || 'No se pudo cargar la auditoría');
            renderAudit(data);
        } catch (error) {
            box.innerHTML = `<p class="text-sm text-rose-300">${escapeHtml(error.message || 'No se pudo cargar auditoría UX/UI.')}</p>`;
        }
    }

    function bindInputs() {
        if (document.body.dataset.ajustesBound === '1') return;
        document.body.dataset.ajustesBound = '1';
        document.getElementById('ajustes-preset')?.addEventListener('change', applyPreset);
        ['ajustes-primary','ajustes-primary-hover','ajustes-accent','ajustes-bg','ajustes-surface','ajustes-surface-soft','ajustes-border','ajustes-text','ajustes-muted','ajustes-radius','ajustes-density','ajustes-font-scale','ajustes-sidebar-mode','ajustes-reduce-motion'].forEach((id) => {
            document.getElementById(id)?.addEventListener('input', () => apply(readForm()));
            document.getElementById(id)?.addEventListener('change', () => apply(readForm()));
        });
    }

    function actualizarAvisoAlcance() {
        const box = document.getElementById('ajustes-alcance');
        if (!box) return;
        if (puedeGuardarTemaInstitucional()) {
            box.innerHTML = '<strong class="text-slate-300">Alcance:</strong> puedes guardar el tema institucional para tu fundación. Los demás perfiles también pueden guardar preferencia local en su navegador.';
        } else {
            box.innerHTML = '<strong class="text-slate-300">Alcance:</strong> tus ajustes se guardan como preferencia personal en este navegador y no modifican la experiencia de otros usuarios.';
        }
    }

    async function init() {
        bindInputs();
        await loadRemote();
        await loadAudit();
        if (typeof lucide !== 'undefined') lucide.createIcons();
    }

    const initial = readLocal();
    if (document.documentElement) apply(initial);

    window.AjustesUI = {
        init,
        apply,
        applyPreset,
        save: saveRemote,
        reset: resetRemote,
        loadAudit,
        readLocal,
        defaults: DEFAULTS,
        presets: PRESETS
    };
    window.ajustesUIInit = init;
    window.ajustesGuardar = saveRemote;
    window.ajustesRestablecer = resetRemote;
    window.ajustesAplicarPreset = applyPreset;
    window.ajustesCargarAuditoria = loadAudit;

    document.addEventListener('DOMContentLoaded', () => apply(readLocal()));
})();
