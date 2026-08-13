/*
 * Tabla maestra de impresión — PrimeraInfancia v2.3.0-alpha.13
 * Mantiene una sola fuente de verdad para imprimir RPP, Bienestarina y RAM.
 */
const PRINT_MASTER_CONFIG = Object.freeze({
    rpp: Object.freeze({
        label: 'Formato RPP',
        pageSize: 'A4',
        cssPageSize: 'A4 landscape',
        excelPaperSize: 'A4',
        orientation: 'landscape',
        scale: 35,
        fitToWidth: 1,
        fitToHeight: 0,
        margins: Object.freeze({
            top: 1.91,
            bottom: 1.91,
            left: 0.76,
            right: 0.64,
            header: 0.76,
            footer: 0.76
        })
    }),

    bienestarina: Object.freeze({
        label: 'Formato Bienestarina',
        pageSize: 'Legal',
        cssPageSize: 'Legal landscape',
        excelPaperSize: 'LEGAL',
        orientation: 'landscape',
        scale: 55,
        fitToWidth: 1,
        fitToHeight: 0,
        margins: Object.freeze({
            top: 1.91,
            bottom: 1.91,
            left: 0.64,
            right: 0.64,
            header: 0.76,
            footer: 0.76
        })
    }),

    ram: Object.freeze({
        label: 'Formato RAM / Asistencia',
        pageSize: '8.5x13',
        cssPageSize: '13in 8.5in',
        excelPaperSize: 'FOLIO',
        orientation: 'landscape',
        scale: 60,
        fitToWidth: 1,
        fitToHeight: 0,
        preserveTemplateMargins: true,
        margins: null
    })
});

window.PRINT_MASTER_CONFIG = PRINT_MASTER_CONFIG;
