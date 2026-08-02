(function () {
    const api = () => `${window.backendUrl || window.getBackendUrl?.() || window.getConfiguredBackendUrl?.() || window.location.origin}/api/base-maestra`;
    const tipos = {
        cuentame: {
            input: 'bmp-file-cuentame',
            label: 'Niños / Cuéntame',
            status: 'bmp-status-cuentame'
        },
        talento_humano: {
            input: 'bmp-file-talento',
            label: 'Talento humano',
            status: 'bmp-status-talento'
        },
        salud_nutricion: {
            input: 'bmp-file-salud',
            label: 'Salud, nutrición, peso y talla',
            status: 'bmp-status-salud'
        }
    };

    function el(id) { return document.getElementById(id); }

    function esc(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function mensaje(texto, tipo = 'info') {
        if (typeof mostrarMensaje === 'function') {
            mostrarMensaje('bmp-message', texto, tipo === 'error' ? 'error' : tipo === 'warning' ? 'error' : 'success');
            return;
        }
        const box = el('bmp-message');
        if (!box) return;
        const styles = {
            success: 'border-emerald-500/20 bg-emerald-500/10 text-emerald-200',
            error: 'border-rose-500/20 bg-rose-500/10 text-rose-200',
            warning: 'border-amber-500/20 bg-amber-500/10 text-amber-200',
            info: 'border-cyan-500/20 bg-cyan-500/10 text-cyan-200'
        };
        box.className = `mt-4 rounded-xl border px-4 py-3 text-sm ${styles[tipo] || styles.info}`;
        box.textContent = texto;
        box.classList.remove('hidden');
    }

    async function fetchJson(url, options = {}) {
        const res = await fetch(url, options);
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || data.message || 'Error consultando Base Maestra');
        return data;
    }

    function setStatus(id, text, ok = false) {
        const node = el(id);
        if (!node) return;
        node.textContent = text;
        node.classList.toggle('text-emerald-300', ok);
        node.classList.toggle('text-slate-400', !ok);
    }

    async function cargarEstadoFuentes() {
        try {
            const data = await fetchJson(`${api()}/fuentes-estado`);
            const map = new Map((data.fuentes || []).map(f => [f.tipo_fuente, f]));
            Object.keys(tipos).forEach((tipo) => {
                const cfg = tipos[tipo];
                const fuente = map.get(tipo);
                if (fuente?.cargada) {
                    setStatus(cfg.status, `${fuente.estado || 'cargado'} · ${fuente.total_registros || 0} registros`, true);
                } else {
                    setStatus(cfg.status, 'Sin cargar', false);
                }
            });
            const versionLabel = el('bmp-version-label');
            if (versionLabel) {
                versionLabel.textContent = data.version_activa
                    ? `Base Maestra activa v${data.version_activa.version_numero || data.version_activa.id}`
                    : 'Sin Base Maestra publicada';
            }
            return data;
        } catch (error) {
            const status = el('bmp-status-text');
            if (status) status.textContent = error.message || 'No se pudo consultar el estado de la Base Maestra.';
            return null;
        }
    }

    async function cargarFuente(tipo) {
        const cfg = tipos[tipo];
        if (!cfg) return;
        const file = el(cfg.input)?.files?.[0];
        if (!file) {
            mensaje(`Selecciona primero el archivo de ${cfg.label}.`, 'warning');
            return;
        }
        const fd = new FormData();
        fd.append('file', file);
        fd.append('tipo_fuente', tipo);
        try {
            if (typeof mostrarCargando === 'function') mostrarCargando(`Cargando fuente: ${cfg.label}...`);
            const data = await fetchJson(`${api()}/cargar-fuente`, { method: 'POST', body: fd });
            if (el(cfg.input)) el(cfg.input).value = '';
            mensaje(`${cfg.label}: carga #${data.carga_id} registrada con ${data.registros_cargados || data.total_registros || 0} registro(s).`, 'success');
            await cargarEstadoFuentes();
        } catch (error) {
            mensaje(error.message || `No se pudo cargar ${cfg.label}.`, 'error');
        } finally {
            if (typeof ocultarCargando === 'function') ocultarCargando();
        }
    }

    async function validarPendientes() {
        try {
            if (typeof mostrarCargando === 'function') mostrarCargando('Validando las fuentes pendientes de Base Maestra...');
            const data = await fetchJson(`${api()}/validar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            mensaje(`Validación terminada: ${data.total_validaciones || 0} carga(s) revisada(s).`, 'success');
            await cargarEstadoFuentes();
        } catch (error) {
            mensaje(error.message || 'No se pudieron validar las fuentes.', 'error');
        } finally {
            if (typeof ocultarCargando === 'function') ocultarCargando();
        }
    }

    async function consolidar() {
        try {
            if (typeof mostrarCargando === 'function') mostrarCargando('Normalizando y uniendo por documento del niño...');
            const data = await fetchJson(`${api()}/consolidar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ observaciones: 'Consolidación desde Panel Principal ALPHA31' })
            });
            mensaje(`${data.message || 'Base Maestra consolidada.'} Versión borrador #${data.version_id}. ${data.puede_publicar ? 'Lista para publicar.' : 'Tiene críticos por revisar.'}`, data.puede_publicar ? 'success' : 'warning');
            await cargarEstadoFuentes();
            return data;
        } catch (error) {
            mensaje(error.message || 'No se pudo consolidar la Base Maestra.', 'error');
            return null;
        } finally {
            if (typeof ocultarCargando === 'function') ocultarCargando();
        }
    }

    async function publicarUltimoBorrador() {
        try {
            const dashboard = await fetchJson(`${api()}/resumen`);
            const borrador = (dashboard.borradores || [])[0];
            if (!borrador?.id) {
                mensaje('No hay versión borrador para publicar. Primero consolida la Base Maestra.', 'warning');
                return;
            }
            if (!confirm(`¿Publicar la Base Maestra borrador v${borrador.version_numero || borrador.id} como versión oficial activa?`)) return;
            if (typeof mostrarCargando === 'function') mostrarCargando('Publicando Base Maestra oficial...');
            const data = await fetchJson(`${api()}/publicar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ version_id: Number(borrador.id), observaciones: 'Publicación desde Panel Principal ALPHA31' })
            });
            mensaje(data.message || 'Base Maestra publicada correctamente.', 'success');
            await cargarEstadoFuentes();
            await cargarPanelPrincipalBaseMaestra({ silent: false });
        } catch (error) {
            mensaje(error.message || 'No se pudo publicar la Base Maestra.', 'error');
        } finally {
            if (typeof ocultarCargando === 'function') ocultarCargando();
        }
    }

    async function cargarPanelPrincipalBaseMaestra(options = {}) {
        try {
            const data = await fetchJson(`${api()}/resumen-panel`);
            if (!data.fuente_activa) {
                if (!options.silent) mensaje(data.message || 'No hay Base Maestra publicada todavía.', 'warning');
                await cargarEstadoFuentes();
                return data;
            }
            if (typeof window.aplicarPanelPrincipalBaseMaestra === 'function') {
                window.aplicarPanelPrincipalBaseMaestra(data, options);
            }
            await cargarEstadoFuentes();
            return data;
        } catch (error) {
            if (!options.silent) mensaje(error.message || 'No se pudo alimentar el panel desde Base Maestra.', 'error');
            return null;
        }
    }

    async function flujoCompleto() {
        await validarPendientes();
        const borrador = await consolidar();
        if (borrador?.puede_publicar) {
            await publicarUltimoBorrador();
        }
    }

    window.BMP = {
        cargarFuente,
        validarPendientes,
        consolidar,
        publicarUltimoBorrador,
        cargarEstadoFuentes,
        cargarPanelPrincipalBaseMaestra,
        flujoCompleto
    };
    window.cargarPanelPrincipalBaseMaestra = cargarPanelPrincipalBaseMaestra;

    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => cargarEstadoFuentes(), 1200);
    });
})();
