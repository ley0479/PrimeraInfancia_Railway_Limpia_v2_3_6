/* Motor maestro de impresión para vistas HTML imprimibles — v2.3.0-alpha.13. */
(function () {
    const STYLE_ID = 'print-manager-dynamic-style';
    const BODY_CLASS = 'pi-printing';

    function getConfig(tipoFormato) {
        const key = String(tipoFormato || '').trim().toLowerCase();
        return window.PRINT_MASTER_CONFIG?.[key] || null;
    }

    function marginRule(cfg) {
        if (!cfg?.margins) return '';
        const m = cfg.margins;
        return `margin: ${m.top}cm ${m.right}cm ${m.bottom}cm ${m.left}cm;`;
    }

    function scaleRule(cfg) {
        const scale = Number(cfg?.scale || 100) / 100;
        if (!scale || scale === 1) return '';
        const width = (100 / scale).toFixed(4).replace(/\.0+$/, '');
        return `
            transform: scale(${scale});
            transform-origin: top left;
            width: ${width}%;
        `;
    }

    function ensureStyle(cfg, tipoFormato) {
        let style = document.getElementById(STYLE_ID);
        if (!style) {
            style = document.createElement('style');
            style.id = STYLE_ID;
            document.head.appendChild(style);
        }

        style.innerHTML = `
            @page {
                size: ${cfg.cssPageSize};
                ${marginRule(cfg)}
            }

            @media print {
                html[data-print-format="${tipoFormato}"],
                html[data-print-format="${tipoFormato}"] body {
                    background: #fff !important;
                    color: #000 !important;
                    margin: 0 !important;
                    padding: 0 !important;
                }

                body.${BODY_CLASS} .print-area,
                body.${BODY_CLASS} .formato-${tipoFormato.replace('_', '-')},
                body.${BODY_CLASS} [data-print-format="${tipoFormato}"] {
                    ${scaleRule(cfg)}
                }
            }
        `;
    }

    function cleanup() {
        document.body.classList.remove(BODY_CLASS);
        document.documentElement.removeAttribute('data-print-format');
        document.querySelectorAll('.print-target-active').forEach((el) => el.classList.remove('print-target-active'));
    }

    window.imprimirFormato = function imprimirFormato(tipoFormato, options = {}) {
        const cfg = getConfig(tipoFormato);
        if (!cfg) {
            alert(`No existe configuración de impresión para: ${tipoFormato}`);
            return false;
        }

        ensureStyle(cfg, tipoFormato);
        document.documentElement.setAttribute('data-print-format', tipoFormato);
        document.body.classList.add(BODY_CLASS);

        const targetSelector = options.targetSelector || options.selector || null;
        if (targetSelector) {
            const target = document.querySelector(targetSelector);
            if (target) target.classList.add('print-target-active');
        }

        setTimeout(() => window.print(), 150);
        return true;
    };

    window.addEventListener('afterprint', cleanup);
    window.PrintManager = {
        config: window.PRINT_MASTER_CONFIG,
        imprimirFormato: window.imprimirFormato,
        cleanup
    };
})();
