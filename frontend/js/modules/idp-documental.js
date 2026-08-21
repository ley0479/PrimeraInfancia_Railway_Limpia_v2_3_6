(function () {
    'use strict';
    const state = { documents: [], selected: null, initialized: false };
    const $ = (id) => document.getElementById(id);
    const esc = (value) => String(value ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;');

    async function api(path, options) {
        const response = await fetch(`${backendUrl}/api/idp${path}`, options);
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.error || `Error HTTP ${response.status}`);
        return data;
    }

    function message(text, type='info') {
        const box=$('idp-message'); if(!box)return;
        box.className=`idp-message ${type}`; box.textContent=text; box.classList.remove('hidden');
    }

    function badge(status) {
        const value=String(status||'RECIBIDO').toUpperCase();
        const tone=value==='APROBADO'?'green':value.includes('ERROR')?'red':value.includes('OCR')||value.includes('REVISION')?'yellow':'blue';
        return `<span class="idp-badge ${tone}">${esc(value.replaceAll('_',' '))}</span>`;
    }

    function renderList() {
        const target=$('idp-documents'); if(!target)return;
        if(!state.documents.length){target.innerHTML='<div class="idp-empty">No hay documentos cargados para esta fundación.</div>';return;}
        target.innerHTML=state.documents.map(doc=>`<button type="button" class="idp-document ${state.selected?.id===doc.id?'active':''}" onclick="IDPDocumental.select(${Number(doc.id)})"><div><strong>${esc(doc.nombre_original)}</strong><small>${esc(doc.tipo_documento)} · ${esc(doc.motor_lectura||'Pendiente')}</small></div><div>${badge(doc.estado)}<small>${Number(doc.progreso||0)}%</small></div></button>`).join('');
    }

    function confidence(field) {
        const value=Number(field.confianza||0);
        return value>=.9?'green':value>=.65?'yellow':'red';
    }

    function displayValue(value) {
        if(value===null||value===undefined||value==='')return '<em>No encontrado</em>';
        if(typeof value==='object')return esc(JSON.stringify(value));
        return esc(value);
    }

    function renderDetail() {
        const target=$('idp-detail'); if(!target)return;
        const doc=state.selected;
        if(!doc){target.innerHTML='<div class="idp-empty">Selecciona un documento para revisar sus resultados.</div>';return;}
        const fields=(doc.campos||[]).map(field=>`<div class="idp-field ${confidence(field)}"><div><small>${esc(field.ruta_canonica)}</small><strong>${displayValue(field.valor)}</strong><span>Original: ${esc(field.texto_original||'No encontrado')} · Confianza ${(Number(field.confianza||0)*100).toFixed(0)}%</span><span>Evidencia: ${esc(JSON.stringify(field.evidencia||{}))}</span></div><button type="button" class="idp-btn secondary" onclick="IDPDocumental.correct(${Number(field.id)})">Corregir</button></div>`).join('');
        const validations=(doc.validaciones||[]).map(item=>`<div class="idp-warning">${esc(item.mensaje||item.codigo)}</div>`).join('');
        target.innerHTML=`<div class="idp-card p-5"><div class="idp-detail-head"><div><p class="idp-eyebrow">${esc(doc.tipo_documento)}</p><h3>${esc(doc.nombre_original)}</h3><p>Motor: ${esc(doc.motor_lectura||'Pendiente')} · Clasificación ${(Number(doc.confianza_clasificacion||0)*100).toFixed(0)}%</p></div>${badge(doc.estado)}</div><div class="idp-progress"><span style="width:${Math.max(0,Math.min(100,Number(doc.progreso||0)))}%"></span></div><div class="idp-actions"><button class="idp-btn secondary" onclick="IDPDocumental.download(${Number(doc.id)})">Descargar original</button><button class="idp-btn primary" ${doc.estado==='REQUIERE_OCR'||doc.estado==='APROBADO'?'disabled':''} onclick="IDPDocumental.approve(${Number(doc.id)})">Aprobar sin importar</button></div>${validations}<div class="idp-fields">${fields||'<div class="idp-empty">No hay campos estructurados. Requiere mapeo u OCR.</div>'}</div></div>`;
    }

    async function load() {
        try { const data=await api('/documentos'); state.documents=data.documentos||[]; renderList(); }
        catch(error){message(error.message,'error');}
    }

    async function select(id) {
        try { const data=await api(`/documentos/${id}`); state.selected=data.documento; renderList(); renderDetail(); }
        catch(error){message(error.message,'error');}
    }

    async function upload() {
        const input=$('idp-file'); const file=input?.files?.[0];
        if(!file){message('Selecciona un archivo.','error');return;}
        if(file.size>50*1024*1024){message('El archivo supera 50 MB.','error');return;}
        const form=new FormData(); form.append('file',file);
        const button=$('idp-upload'); if(button)button.disabled=true;
        message('Validando, clasificando y extrayendo el documento...','info');
        try { const data=await api('/documentos',{method:'POST',body:form}); state.selected=data.documento; input.value=''; message(data.message,'success'); await load(); renderDetail(); }
        catch(error){message(error.message,'error');}
        finally{if(button)button.disabled=false;}
    }

    async function correct(fieldId) {
        const field=(state.selected?.campos||[]).find(item=>Number(item.id)===Number(fieldId)); if(!field)return;
        const raw=prompt(`Corregir ${field.ruta_canonica}`,field.valor??''); if(raw===null)return;
        const reason=prompt('Motivo de la corrección (opcional)','Revisión humana')??'';
        try { const data=await api(`/documentos/${state.selected.id}/campos/${fieldId}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({valor:raw,motivo:reason})}); state.selected=data.documento; message(data.message,'success'); renderDetail(); }
        catch(error){message(error.message,'error');}
    }

    async function approve(id) {
        if(!confirm('¿Aprobar el resultado revisado? Esta acción NO lo importará todavía a los módulos funcionales.'))return;
        try { const data=await api(`/documentos/${id}/aprobar`,{method:'POST'}); state.selected=data.documento; message(data.message,'success'); await load(); renderDetail(); }
        catch(error){message(error.message,'error');}
    }

    function download(id) {
        window.descargarArchivoAutenticado(`${backendUrl}/api/idp/documentos/${id}/original`).catch(error=>message(error.message,'error'));
    }

    function init() {
        if(!state.initialized){state.initialized=true;$('idp-upload')?.addEventListener('click',upload);}
        load();
    }
    window.IDPDocumental={init,load,select,upload,correct,approve,download};
    window.idpDocumentalInit=init;
})();
