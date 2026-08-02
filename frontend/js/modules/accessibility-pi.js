/* =========================================================
   Primera Infancia — Módulo desacoplado de accesibilidad UX
   Release piloto SQLite/local files · WCAG 2.2 AA básico
   Fuente conceptual auditada: accessibility.js + enhancements.css
   Este archivo NO toca backend, rutas, login ni lógica de formatos.
========================================================= */
(function () {
    'use strict';

    const MODULE_VERSION = '2.3.0-release-a11y-ux';
    const STORAGE_PREFIX = 'primeraInfancia.a11y.preferences';
    const LEGACY_SOURCE_KEY = 'mn-accessibility';
    const PANEL_ID = 'pi-a11y-panel';
    const TOGGLE_ID = 'pi-a11y-toggle';
    const STATUS_ID = 'pi-a11y-status';
    const SKIP_ID = 'pi-a11y-skip-link';

    const defaults = Object.freeze({
        mode: 'current',
        fontScale: 100,
        highContrast: false,
        reduceMotion: false,
        visibleFocus: true,
        keyboardHelp: false
    });

    let settings = { ...defaults };
    let lastStorageKey = '';
    let lastFocusedElement = null;

    const qs = (selector, root = document) => root.querySelector(selector);
    const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));

    function safeJsonParse(value, fallback) {
        try {
            return JSON.parse(value || '');
        } catch (_) {
            return fallback;
        }
    }

    function normalizeIdentifier(value) {
        return String(value || '')
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-zA-Z0-9_.@-]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .slice(0, 80) || 'local';
    }

    function readUserFromStorage() {
        const candidates = ['usuario', 'user', 'currentUser', 'primeraInfanciaUser'];
        for (const storage of [window.localStorage, window.sessionStorage]) {
            for (const key of candidates) {
                const raw = storage.getItem(key);
                if (!raw) continue;
                const parsed = safeJsonParse(raw, null);
                if (parsed && typeof parsed === 'object') return parsed;
                if (typeof raw === 'string' && raw.length > 1) return { usuario: raw };
            }
        }
        return null;
    }

    function userScope() {
        const user = readUserFromStorage();
        const value = user?.id || user?.usuario || user?.username || user?.email || user?.correo || user?.documento || 'local';
        return normalizeIdentifier(value);
    }

    function storageKey() {
        return `${STORAGE_PREFIX}:${userScope()}`;
    }

    function migrateLegacySettings(base) {
        const legacy = safeJsonParse(localStorage.getItem(LEGACY_SOURCE_KEY), null);
        if (!legacy || typeof legacy !== 'object') return base;
        return {
            ...base,
            fontScale: Number(legacy.fontScale || base.fontScale),
            highContrast: Boolean(legacy.contrast ?? base.highContrast),
            reduceMotion: Boolean(legacy.reduceMotion ?? base.reduceMotion)
        };
    }

    function readSettings() {
        const key = storageKey();
        lastStorageKey = key;
        const stored = safeJsonParse(localStorage.getItem(key), null);
        if (stored && typeof stored === 'object') return { ...defaults, ...stored };
        return migrateLegacySettings({ ...defaults });
    }

    function saveSettings() {
        const key = storageKey();
        lastStorageKey = key;
        try {
            localStorage.setItem(key, JSON.stringify(settings));
        } catch (_) {}
    }

    function clampFontScale(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return defaults.fontScale;
        return Math.min(135, Math.max(90, Math.round(number / 5) * 5));
    }

    function ensureMainTarget() {
        let main = qs('main');
        if (!main) main = qs('#app, #dashboard, .app-shell, body');
        if (main && !main.id) main.id = 'contenido-principal';
        return main;
    }

    function ensureSkipLink() {
        if (document.getElementById(SKIP_ID)) return;
        const target = ensureMainTarget();
        const link = document.createElement('a');
        link.id = SKIP_ID;
        link.className = 'pi-a11y-skip-link';
        link.href = `#${target?.id || 'contenido-principal'}`;
        link.textContent = 'Saltar al contenido principal';
        document.body.insertBefore(link, document.body.firstChild);
    }

    function ensureStatusRegion() {
        if (document.getElementById(STATUS_ID)) return;
        const status = document.createElement('div');
        status.id = STATUS_ID;
        status.className = 'pi-a11y-sr-only';
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        document.body.appendChild(status);
    }

    function announce(message) {
        const status = document.getElementById(STATUS_ID);
        if (!status) return;
        status.textContent = '';
        window.setTimeout(() => { status.textContent = message; }, 35);
    }

    function setHidden(element, hidden) {
        if (!element) return;
        element.hidden = hidden;
        element.setAttribute('aria-hidden', String(hidden));
    }

    function createWidget() {
        if (document.getElementById('pi-a11y-widget')) return;
        const widget = document.createElement('aside');
        widget.id = 'pi-a11y-widget';
        widget.className = 'pi-a11y-widget';
        widget.setAttribute('aria-label', 'Herramientas de accesibilidad');
        widget.innerHTML = `
            <button id="${TOGGLE_ID}" class="pi-a11y-toggle" type="button" aria-expanded="false" aria-controls="${PANEL_ID}">
                <span class="pi-a11y-toggle-icon" aria-hidden="true">Aa</span>
                <span class="pi-a11y-toggle-text">Accesibilidad</span>
            </button>
            <section id="${PANEL_ID}" class="pi-a11y-panel" hidden aria-hidden="true" aria-label="Opciones de accesibilidad" tabindex="-1">
                <div class="pi-a11y-panel-head">
                    <div>
                        <strong>Accesibilidad</strong>
                        <small>Preferencias locales por usuario</small>
                    </div>
                    <button id="pi-a11y-close" class="pi-a11y-icon-btn" type="button" aria-label="Cerrar panel de accesibilidad">×</button>
                </div>

                <fieldset class="pi-a11y-fieldset">
                    <legend>Modo visual</legend>
                    <div class="pi-a11y-segmented" role="group" aria-label="Seleccionar modo visual">
                        <button type="button" data-mode="current">Actual</button>
                        <button type="button" data-mode="light">Claro</button>
                        <button type="button" data-mode="dark">Oscuro</button>
                    </div>
                </fieldset>

                <div class="pi-a11y-control">
                    <label for="pi-a11y-font-range">Tamaño de texto</label>
                    <div class="pi-a11y-font-row">
                        <button id="pi-a11y-font-down" type="button" aria-label="Reducir tamaño de texto">A−</button>
                        <input id="pi-a11y-font-range" type="range" min="90" max="135" step="5" value="100" aria-describedby="pi-a11y-font-value">
                        <button id="pi-a11y-font-up" type="button" aria-label="Aumentar tamaño de texto">A+</button>
                        <output id="pi-a11y-font-value" for="pi-a11y-font-range">100%</output>
                    </div>
                </div>

                <label class="pi-a11y-switch"><input id="pi-a11y-contrast" type="checkbox"><span>Alto contraste</span></label>
                <label class="pi-a11y-switch"><input id="pi-a11y-motion" type="checkbox"><span>Reducir animaciones</span></label>
                <label class="pi-a11y-switch"><input id="pi-a11y-focus" type="checkbox"><span>Foco visible reforzado</span></label>
                <label class="pi-a11y-switch"><input id="pi-a11y-keyboard-help" type="checkbox"><span>Mostrar guía de teclado</span></label>

                <div id="pi-a11y-keyboard-card" class="pi-a11y-keyboard-card" hidden>
                    <strong>Atajos útiles</strong>
                    <ul>
                        <li><kbd>Alt</kbd> + <kbd>A</kbd>: abrir/cerrar este panel.</li>
                        <li><kbd>Tab</kbd>: avanzar por controles.</li>
                        <li><kbd>Shift</kbd> + <kbd>Tab</kbd>: retroceder.</li>
                        <li><kbd>Esc</kbd>: cerrar paneles emergentes.</li>
                    </ul>
                </div>

                <div class="pi-a11y-read-actions" aria-label="Lectura por voz opcional">
                    <button id="pi-a11y-read" type="button">▶ Leer vista</button>
                    <button id="pi-a11y-stop" type="button">■ Detener</button>
                </div>

                <button id="pi-a11y-branding" class="pi-a11y-branding" type="button">🏛 Identidad visual</button>
                <button id="pi-a11y-reset" class="pi-a11y-reset" type="button">Restablecer</button>
                <small class="pi-a11y-note">No modifica datos, formatos, rutas ni backend. Guarda preferencias en este navegador.</small>
            </section>`;
        document.body.appendChild(widget);
    }

    function getControls() {
        const panel = document.getElementById(PANEL_ID);
        return {
            panel,
            toggle: document.getElementById(TOGGLE_ID),
            close: document.getElementById('pi-a11y-close'),
            modeButtons: qsa('[data-mode]', panel || document),
            fontRange: document.getElementById('pi-a11y-font-range'),
            fontValue: document.getElementById('pi-a11y-font-value'),
            contrast: document.getElementById('pi-a11y-contrast'),
            motion: document.getElementById('pi-a11y-motion'),
            focus: document.getElementById('pi-a11y-focus'),
            keyboardHelp: document.getElementById('pi-a11y-keyboard-help'),
            keyboardCard: document.getElementById('pi-a11y-keyboard-card'),
            read: document.getElementById('pi-a11y-read'),
            stop: document.getElementById('pi-a11y-stop'),
            branding: document.getElementById('pi-a11y-branding'),
            reset: document.getElementById('pi-a11y-reset'),
            fontDown: document.getElementById('pi-a11y-font-down'),
            fontUp: document.getElementById('pi-a11y-font-up')
        };
    }

    function applySettings({ persist = true, announceChange = false } = {}) {
        settings.fontScale = clampFontScale(settings.fontScale);
        const root = document.documentElement;

        root.classList.add('pi-a11y-enabled');
        root.classList.toggle('pi-a11y-light', settings.mode === 'light');
        root.classList.toggle('pi-a11y-dark', settings.mode === 'dark');
        root.classList.toggle('pi-a11y-high-contrast', Boolean(settings.highContrast));
        root.classList.toggle('pi-a11y-reduce-motion', Boolean(settings.reduceMotion));
        root.classList.toggle('pi-a11y-focus', Boolean(settings.visibleFocus));
        root.dataset.piA11yMode = settings.mode;
        root.style.setProperty('--pi-a11y-font-scale', String(settings.fontScale / 100));
        root.style.fontSize = `${settings.fontScale}%`;

        const controls = getControls();
        controls.modeButtons.forEach((button) => {
            const active = button.dataset.mode === settings.mode;
            button.classList.toggle('is-active', active);
            button.setAttribute('aria-pressed', String(active));
        });
        if (controls.fontRange) controls.fontRange.value = String(settings.fontScale);
        if (controls.fontValue) controls.fontValue.textContent = `${settings.fontScale}%`;
        if (controls.contrast) controls.contrast.checked = Boolean(settings.highContrast);
        if (controls.motion) controls.motion.checked = Boolean(settings.reduceMotion);
        if (controls.focus) controls.focus.checked = Boolean(settings.visibleFocus);
        if (controls.keyboardHelp) controls.keyboardHelp.checked = Boolean(settings.keyboardHelp);
        if (controls.keyboardCard) setHidden(controls.keyboardCard, !settings.keyboardHelp);

        if (persist) saveSettings();
        if (announceChange) announce('Preferencia de accesibilidad actualizada.');
    }

    function openPanel() {
        const { panel, toggle, close } = getControls();
        if (!panel || !toggle) return;
        lastFocusedElement = document.activeElement;
        setHidden(panel, false);
        toggle.setAttribute('aria-expanded', 'true');
        window.setTimeout(() => (close || panel).focus(), 20);
    }

    function closePanel() {
        const { panel, toggle } = getControls();
        if (!panel || !toggle) return;
        setHidden(panel, true);
        toggle.setAttribute('aria-expanded', 'false');
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        } else {
            toggle.focus();
        }
    }

    function togglePanel() {
        const panel = document.getElementById(PANEL_ID);
        if (!panel || panel.hidden) openPanel(); else closePanel();
    }

    function readableSource() {
        return qs('main:not([hidden])') || qs('[data-active-section]:not(.hidden)') || qs('#app') || document.body;
    }

    function getReadableText() {
        const source = readableSource();
        if (!source) return '';
        const clone = source.cloneNode(true);
        clone.querySelectorAll([
            'script', 'style', 'noscript', 'svg', 'canvas', 'iframe',
            'button', 'input', 'select', 'textarea', '[hidden]', '[aria-hidden="true"]',
            '.hidden', '.modal', '.pi-a11y-widget', '.pi-a11y-skip-link', 'nav', 'aside'
        ].join(',')).forEach((el) => el.remove());
        return String(clone.innerText || clone.textContent || '')
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, 12000);
    }

    function readPage() {
        if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
            window.alert('Tu navegador no admite lectura en voz alta.');
            return;
        }
        window.speechSynthesis.cancel();
        const text = getReadableText();
        if (!text) {
            window.alert('No se encontró contenido principal para leer en esta vista.');
            return;
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'es-CO';
        utterance.rate = 0.95;
        utterance.pitch = 1;
        window.speechSynthesis.speak(utterance);
        announce('Lectura por voz iniciada.');
    }

    function stopReading() {
        if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        announce('Lectura por voz detenida.');
    }

    function resetSettings() {
        stopReading();
        settings = { ...defaults };
        applySettings({ announceChange: true });
    }

    function bindEvents() {
        const controls = getControls();
        controls.toggle?.addEventListener('click', togglePanel);
        controls.close?.addEventListener('click', closePanel);
        controls.modeButtons.forEach((button) => {
            button.addEventListener('click', () => {
                settings.mode = button.dataset.mode || 'current';
                applySettings({ announceChange: true });
            });
        });
        controls.fontRange?.addEventListener('input', (event) => {
            settings.fontScale = clampFontScale(event.target.value);
            applySettings({ announceChange: false });
        });
        controls.fontRange?.addEventListener('change', () => announce('Tamaño de texto actualizado.'));
        controls.fontDown?.addEventListener('click', () => {
            settings.fontScale = clampFontScale(settings.fontScale - 5);
            applySettings({ announceChange: true });
        });
        controls.fontUp?.addEventListener('click', () => {
            settings.fontScale = clampFontScale(settings.fontScale + 5);
            applySettings({ announceChange: true });
        });
        controls.contrast?.addEventListener('change', (event) => {
            settings.highContrast = Boolean(event.target.checked);
            applySettings({ announceChange: true });
        });
        controls.motion?.addEventListener('change', (event) => {
            settings.reduceMotion = Boolean(event.target.checked);
            applySettings({ announceChange: true });
        });
        controls.focus?.addEventListener('change', (event) => {
            settings.visibleFocus = Boolean(event.target.checked);
            applySettings({ announceChange: true });
        });
        controls.keyboardHelp?.addEventListener('change', (event) => {
            settings.keyboardHelp = Boolean(event.target.checked);
            applySettings({ announceChange: true });
        });
        controls.read?.addEventListener('click', readPage);
        controls.stop?.addEventListener('click', stopReading);
        controls.branding?.addEventListener('click', () => {
            closePanel();
            if (typeof window.mostrarSeccion === 'function') window.mostrarSeccion('configuracion-institucional');
            if (typeof window.configInstitucionalInit === 'function') window.configInstitucionalInit();
            announce('Módulo de identidad visual abierto.');
        });
        controls.reset?.addEventListener('click', resetSettings);

        document.addEventListener('keydown', (event) => {
            if (event.altKey && event.key.toLowerCase() === 'a') {
                event.preventDefault();
                togglePanel();
                return;
            }
            if (event.key === 'Escape') {
                const panel = document.getElementById(PANEL_ID);
                if (panel && !panel.hidden) closePanel();
            }
        });

        document.addEventListener('keydown', (event) => {
            if (event.key === 'Tab') document.documentElement.classList.add('pi-a11y-keyboard-user');
        }, { once: true });

        window.addEventListener('storage', () => {
            const key = storageKey();
            if (key !== lastStorageKey) {
                settings = readSettings();
                applySettings({ persist: false });
            }
        });
    }

    function improveAriaLabels() {
        qsa('button').forEach((button, index) => {
            if (button.getAttribute('aria-label') || button.textContent.trim()) return;
            const icon = button.querySelector('[data-lucide]')?.getAttribute('data-lucide') || '';
            const title = button.getAttribute('title') || button.dataset.label || button.dataset.action || icon || `acción ${index + 1}`;
            button.setAttribute('aria-label', title.replace(/[-_]+/g, ' '));
        });
        qsa('input, select, textarea').forEach((field) => {
            if (field.id && document.querySelector(`label[for="${CSS.escape(field.id)}"]`)) return;
            if (field.getAttribute('aria-label') || field.getAttribute('aria-labelledby')) return;
            const placeholder = field.getAttribute('placeholder');
            const name = field.getAttribute('name') || field.id || '';
            if (placeholder || name) field.setAttribute('aria-label', placeholder || name.replace(/[-_]+/g, ' '));
        });
        qsa('table').forEach((table) => {
            if (!table.getAttribute('role')) table.setAttribute('role', 'table');
        });
    }

    function exposeApi() {
        window.PrimeraInfanciaAccessibility = Object.freeze({
            version: MODULE_VERSION,
            open: openPanel,
            close: closePanel,
            toggle: togglePanel,
            read: readPage,
            stop: stopReading,
            reset: resetSettings,
            getSettings: () => ({ ...settings }),
            setMode: (mode) => {
                settings.mode = ['current', 'light', 'dark'].includes(mode) ? mode : 'current';
                applySettings({ announceChange: true });
            }
        });
    }

    function init() {
        if (!document.body) return;
        ensureMainTarget();
        ensureSkipLink();
        ensureStatusRegion();
        createWidget();
        settings = readSettings();
        bindEvents();
        improveAriaLabels();
        applySettings({ persist: false });
        exposeApi();
        console.info(`[A11Y] Primera Infancia accesibilidad activa (${MODULE_VERSION}).`);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init, { once: true });
    } else {
        init();
    }
})();
