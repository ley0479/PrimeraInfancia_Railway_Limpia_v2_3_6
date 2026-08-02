/**
 * CurrentDateTime
 * Componente reutilizable para mostrar fecha y reloj en tiempo real.
 * Uso:
 *   <div data-current-datetime></div>
 * Opcionales:
 *   data-hour-format="12" | "24"
 *   data-show-icons="true" | "false"
 */
(function () {
    class CurrentDateTime {
        constructor(element, options = {}) {
            if (!element) {
                throw new Error('CurrentDateTime requiere un elemento contenedor.');
            }
            this.element = element;
            this.options = {
                hourFormat: options.hourFormat || element.dataset.hourFormat || '12',
                showIcons: options.showIcons ?? element.dataset.showIcons !== 'false',
                locale: options.locale || element.dataset.locale || 'es-CO'
            };
            this.timer = null;
            this.render();
            this.start();
        }

        start() {
            this.stop();
            this.update();
            this.timer = window.setInterval(() => this.update(), 1000);
        }

        stop() {
            if (this.timer) {
                window.clearInterval(this.timer);
                this.timer = null;
            }
        }

        formatDate(now) {
            const formatted = new Intl.DateTimeFormat(this.options.locale, {
                weekday: 'long',
                day: 'numeric',
                month: 'long',
                year: 'numeric'
            }).format(now);

            return formatted.charAt(0).toUpperCase() + formatted.slice(1);
        }

        formatTime(now) {
            const hour12 = String(this.options.hourFormat) !== '24';
            return new Intl.DateTimeFormat(this.options.locale, {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12
            }).format(now);
        }

        render() {
            this.element.classList.add('current-datetime-card');
            const dateIcon = this.options.showIcons
                ? '<i data-lucide="calendar-days" class="current-datetime-icon"></i>'
                : '';
            const timeIcon = this.options.showIcons
                ? '<i data-lucide="clock-3" class="current-datetime-icon"></i>'
                : '';

            this.element.innerHTML = `
                <div class="current-datetime-row">
                    ${dateIcon}
                    <span class="current-datetime-date" data-current-datetime-date>---</span>
                </div>
                <div class="current-datetime-row current-datetime-time-row">
                    ${timeIcon}
                    <span class="current-datetime-time" data-current-datetime-time>--:--:--</span>
                </div>
            `;
        }

        update() {
            const now = new Date();
            const dateNode = this.element.querySelector('[data-current-datetime-date]');
            const timeNode = this.element.querySelector('[data-current-datetime-time]');
            if (dateNode) dateNode.textContent = this.formatDate(now);
            if (timeNode) timeNode.textContent = this.formatTime(now);
            this.element.dataset.currentIso = now.toISOString();
        }

        static mount(target, options = {}) {
            const element = typeof target === 'string' ? document.querySelector(target) : target;
            if (!element) return null;

            if (element.__currentDateTimeInstance) {
                element.__currentDateTimeInstance.stop();
            }
            element.__currentDateTimeInstance = new CurrentDateTime(element, options);
            return element.__currentDateTimeInstance;
        }

        static mountAll() {
            document.querySelectorAll('[data-current-datetime]').forEach((element) => {
                CurrentDateTime.mount(element);
            });
            if (window.lucide) {
                window.lucide.createIcons();
            }
        }
    }

    window.CurrentDateTime = CurrentDateTime;

    document.addEventListener('DOMContentLoaded', () => {
        CurrentDateTime.mountAll();
    });
})();
