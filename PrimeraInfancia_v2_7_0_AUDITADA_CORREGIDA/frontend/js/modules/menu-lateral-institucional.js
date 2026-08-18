// ALPHA49 — Comportamiento del menú lateral institucional.
// Capa de navegación visual: no modifica procesamiento, formatos, Base Maestra ni rutas backend.
(function () {
    const STORAGE_KEY = 'primeraInfanciaMenuInstitucionalAlpha49';
    const DEFAULT_OPEN = new Set(['panel-principal', 'base-maestra', 'operacion-icbf', 'gestion-pedagogica']);

    function leerEstado() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            const parsed = raw ? JSON.parse(raw) : null;
            return Array.isArray(parsed) ? new Set(parsed) : new Set(DEFAULT_OPEN);
        } catch (_) {
            return new Set(DEFAULT_OPEN);
        }
    }

    function guardarEstado() {
        try {
            const abiertos = Array.from(document.querySelectorAll('.pi-menu-group[data-open="true"]'))
                .map((group) => group.getAttribute('data-menu-group'))
                .filter(Boolean);
            localStorage.setItem(STORAGE_KEY, JSON.stringify(abiertos));
        } catch (_) {}
    }

    function setGrupoAbierto(group, abierto, persistir = true) {
        if (!group) return;
        group.setAttribute('data-open', abierto ? 'true' : 'false');
        const toggle = group.querySelector('.pi-menu-group-toggle');
        if (toggle) toggle.setAttribute('aria-expanded', abierto ? 'true' : 'false');
        if (persistir) guardarEstado();
    }

    function init() {
        const nav = document.getElementById('menu-lateral-institucional');
        if (!nav || nav.dataset.alpha49Ready === '1') return;
        nav.dataset.alpha49Ready = '1';

        const abiertos = leerEstado();
        document.querySelectorAll('.pi-menu-group').forEach((group) => {
            const key = group.getAttribute('data-menu-group');
            setGrupoAbierto(group, abiertos.has(key), false);
        });

        nav.querySelectorAll('.pi-menu-group-toggle').forEach((toggle) => {
            toggle.addEventListener('click', () => {
                const key = toggle.getAttribute('data-menu-toggle');
                const group = document.querySelector(`.pi-menu-group[data-menu-group="${CSS.escape(key)}"]`);
                const abierto = group?.getAttribute('data-open') === 'true';
                setGrupoAbierto(group, !abierto);
            });
        });

        aplicarPermisos();
        const seccion = (window.location.hash || '').replace('#', '') || 'dashboard';
        marcarActivo(seccion);
        if (typeof lucide !== 'undefined') {
            try { lucide.createIcons(); } catch (_) {}
        }
    }

    function aplicarPermisos() {
        document.querySelectorAll('.pi-menu-group').forEach((group) => {
            const botones = Array.from(group.querySelectorAll('[id^="nav-"]'));
            const visibles = botones.filter((btn) => !btn.classList.contains('hidden'));
            const placeholders = group.querySelectorAll('[data-menu-placeholder]');
            // Los grupos con placeholder representan componentes del Manual Operativo que aún no tienen módulo pesado.
            group.classList.toggle('hidden', visibles.length === 0 && placeholders.length === 0);
        });
    }

    function marcarActivo(seccion) {
        const nav = document.getElementById('menu-lateral-institucional');
        if (!nav) return;
        nav.querySelectorAll('.pi-menu-item').forEach((btn) => btn.classList.remove('pi-menu-item-active'));
        nav.querySelectorAll('.pi-menu-group').forEach((group) => group.classList.remove('pi-menu-group-active'));

        const activo = document.getElementById(`nav-${seccion}`);
        if (activo) {
            activo.classList.add('pi-menu-item-active');
            const groupKey = activo.getAttribute('data-menu-group');
            const group = groupKey ? document.querySelector(`.pi-menu-group[data-menu-group="${CSS.escape(groupKey)}"]`) : null;
            if (group) {
                group.classList.add('pi-menu-group-active');
                setGrupoAbierto(group, true);
            }
        }

        aplicarPermisos();
    }

    window.MenuInstitucionalLateral = {
        init,
        aplicarPermisos,
        marcarActivo
    };

    document.addEventListener('DOMContentLoaded', init);
})();
