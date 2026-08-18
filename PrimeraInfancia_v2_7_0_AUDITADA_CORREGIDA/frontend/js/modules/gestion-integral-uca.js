(function(){
'use strict';
const API = () => `${window.backendUrl || window.getBackendUrl?.() || window.location.origin}/api/gestion-integral-uca`;
const state = {dashboard:null, expedientes:[], selected:null, integrated:null, tab:'centro', initialized:false, biblioteca:[], librarySources:[], libraryCandidates:[], libraryNotifications:[], libraryHistory:[]};
const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
const role = () => String(window.usuarioActual?.rol || window.authUser?.()?.rol || '').toUpperCase();
const canCoordinate = () => ['SUPERADMIN','GERENTE','COORDINADOR','AUXILIAR_ADMINISTRATIVO'].includes(role());
const canLibraryAdmin = () => ['SUPERADMIN','GERENTE','AUXILIAR_ADMINISTRATIVO'].includes(role());
const canLibraryApprove = () => ['SUPERADMIN','GERENTE'].includes(role());

async function request(path, options={}){
  const response = await fetch(`${API()}${path}`, options);
  const type = response.headers.get('content-type') || '';
  const data = type.includes('application/json') ? await response.json() : null;
  if(!response.ok) throw new Error(data?.error || data?.message || `Error HTTP ${response.status}`);
  return data;
}
function message(text='', type='info', target='giu-message'){
  const box=$(target); if(!box) return;
  const colors={info:'border-cyan-500/30 bg-cyan-500/10 text-cyan-100',success:'border-emerald-500/30 bg-emerald-500/10 text-emerald-100',error:'border-rose-500/30 bg-rose-500/10 text-rose-100',warning:'border-amber-500/30 bg-amber-500/10 text-amber-100'};
  box.className=`rounded-xl border px-4 py-3 text-sm ${colors[type]||colors.info}`; box.textContent=text; box.classList.toggle('hidden',!text);
}
function lightClass(value){ const v=String(value||'ROJO').toLowerCase(); return v==='verde'?'giu-green':v==='amarillo'?'giu-yellow':'giu-red'; }
function stateClass(value){ const v=String(value||'').toUpperCase(); return ['APROBADA','CERRADA','APROBADO'].includes(v)?'giu-green':v.includes('PENDIENTE')||v==='EN_PROCESO'?'giu-yellow':v==='NO_APLICA'?'giu-blue':'giu-red'; }
function formatBytes(bytes){ const n=Number(bytes||0); if(n<1024)return `${n} B`; if(n<1048576)return `${(n/1024).toFixed(1)} KB`; return `${(n/1048576).toFixed(1)} MB`; }

async function init(){
  const year=$('giu-vigencia'); if(year && !year.value) year.value=new Date().getFullYear();
  if(!state.initialized){ bindForms(); state.initialized=true; }
  await loadDashboard();
}
async function loadDashboard(){
  try{
    message('Consultando expedientes operativos…','info');
    const year=$('giu-vigencia')?.value || new Date().getFullYear();
    state.dashboard=await request(`/dashboard?vigencia=${encodeURIComponent(year)}`);
    state.expedientes=state.dashboard.expedientes||[];
    renderStats(); renderList();
    if(state.selected){
      const still=state.expedientes.find(x=>x.id===state.selected.id); if(still) await selectExpediente(still.id); else clearDetail();
    }
    message('', 'info');
  }catch(error){message(error.message,'error');}
}
function renderStats(){
  const r=state.dashboard?.resumen||{};
  const target=$('giu-stats'); if(!target)return;
  target.innerHTML=[['Expedientes',r.total||0],['Promedio',`${Number(r.promedio||0).toFixed(1)}%`],['En verde',r.verde||0],['En amarillo',r.amarillo||0],['Críticos',r.rojo||0]].map(([label,val])=>`<div class="giu-stat"><strong>${esc(val)}</strong><span>${esc(label)}</span></div>`).join('');
}
function renderList(){
  const target=$('giu-expedientes-list'); if(!target)return;
  if(!state.expedientes.length){ target.innerHTML='<div class="giu-empty">No hay expedientes. Usa “Sincronizar UCA” para crearlos desde la Base Maestra.</div>'; return; }
  target.innerHTML=state.expedientes.map(item=>`<button class="giu-expediente-card ${state.selected?.id===item.id?'is-active':''}" onclick="GIU.selectExpediente(${item.id})">
    <div class="flex items-start justify-between gap-3"><div><strong class="block text-sm text-slate-100">${esc(item.unidad_nombre)}</strong><span class="text-xs text-slate-500">${esc(item.contrato||'Sin contrato')} · ${esc(item.vigencia)}</span></div><span class="giu-badge ${lightClass(item.semaforo)}">${esc(item.semaforo)}</span></div>
    <div class="mt-3 giu-progress"><span style="width:${Math.max(0,Math.min(100,Number(item.porcentaje_global||0)))}%"></span></div>
    <div class="mt-2 flex items-center justify-between text-[11px] text-slate-400"><span>${esc(item.fase_actual)}</span><span>${Number(item.porcentaje_global||0).toFixed(1)}%</span></div>
  </button>`).join('');
}
async function syncUnits(){
  if(!canCoordinate()) return message('Tu rol puede consultar, pero no sincronizar expedientes.','warning');
  try{
    const payload={vigencia:$('giu-vigencia')?.value||new Date().getFullYear(), contrato:$('giu-contrato')?.value||''};
    message('Sincronizando UCA y creando checklists idempotentes…','info');
    const data=await request('/sincronizar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    message(data.message,'success'); await loadDashboard();
  }catch(error){message(error.message,'error');}
}
async function selectExpediente(id){
  try{
    const [data,integrated]=await Promise.all([request(`/expedientes/${id}`),request(`/expedientes/${id}/vista-unica`)]); state.selected=data.expediente; state.integrated=integrated.vista||null; renderList(); renderDetail();
  }catch(error){message(error.message,'error');}
}
function clearDetail(){ state.selected=null; state.integrated=null; const target=$('giu-detail'); if(target)target.innerHTML='<div class="giu-empty">Selecciona una UCA para consultar su expediente operativo.</div>'; renderList(); }
function renderDetail(){
  const target=$('giu-detail'); const e=state.selected, v=state.integrated; if(!target||!e)return;
  const readiness=v?.preparacion_supervision||{};
  const tabs=[['centro','Centro operativo'],['componentes','Componentes'],['documentos','Documentos'],['alertas','Alertas'],['cronograma','Cronograma'],['indicadores','Indicadores'],['ruta','Ruta operativa'],['planes','Ocho planes'],['biblioteca','Biblioteca']];
  target.innerHTML=`<div class="giu-card p-5">
    <div class="flex flex-col xl:flex-row xl:items-start xl:justify-between gap-4">
      <div><p class="text-xs uppercase tracking-[.18em] text-cyan-300">Expediente Operativo por UCA · Fuente única</p><h2 class="mt-1 text-xl font-semibold text-white">${esc(e.unidad_nombre)}</h2><p class="mt-1 text-sm text-slate-400">${esc(e.servicio_modalidad||'Modalidad por configurar')} · Vigencia ${esc(e.vigencia)} · ${esc(e.contrato||'Sin contrato')}</p></div>
      <div class="flex flex-wrap gap-2"><span class="giu-badge ${lightClass(e.semaforo)}">Ruta ${esc(e.semaforo)} · ${Number(e.porcentaje_global||0).toFixed(1)}%</span>${v?`<span class="giu-badge ${lightClass(readiness.semaforo)}">Supervisión ${esc(readiness.semaforo||'GRIS')} · ${Number(readiness.porcentaje||0).toFixed(1)}%</span>`:''}${canCoordinate()?`<button class="giu-btn giu-btn-secondary" onclick="GIU.refreshIntegrated()"><i data-lucide="refresh-cw"></i> Actualizar vista</button><button class="giu-btn giu-btn-primary" onclick="GIU.downloadPackage(${e.id})"><i data-lucide="archive"></i> Paquete supervisión</button>`:''}</div>
    </div>
    <div class="mt-5 flex flex-wrap gap-2">${tabs.map(([id,label])=>`<button class="giu-tab ${state.tab===id?'is-active':''}" onclick="GIU.setTab('${id}')">${label}</button>`).join('')}</div>
    <div id="giu-tab-content" class="mt-5"></div>
  </div>`;
  renderTab(); if(window.lucide)lucide.createIcons();
}
function setTab(tab){ state.tab=tab; renderDetail(); }
async function refreshIntegrated(){
  if(!state.selected)return;
  try{message('Actualizando la vista única y los vínculos documentales…','info');const data=await request(`/expedientes/${state.selected.id}/vista-unica`);state.integrated=data.vista;renderDetail();message('Vista integrada actualizada.','success');}
  catch(error){message(error.message,'error');}
}
function renderTab(){
  const target=$('giu-tab-content'); if(!target||!state.selected)return;
  if(state.tab==='componentes') return renderComponents(target);
  if(state.tab==='documentos') return renderDocuments(target);
  if(state.tab==='alertas') return renderAlerts(target);
  if(state.tab==='cronograma') return renderSchedule(target);
  if(state.tab==='indicadores') return renderIndicators(target);
  if(state.tab==='ruta') return renderRoute(target);
  if(state.tab==='planes') return renderPlans(target);
  if(state.tab==='biblioteca') return renderLinkedLibrary(target);
  return renderCenter(target);
}
function scalarMetrics(metrics={}){
  return Object.entries(metrics).filter(([,value])=>['string','number','boolean'].includes(typeof value)).slice(0,6);
}
function renderCenter(target){
  const e=state.selected,v=state.integrated;
  if(!v){target.innerHTML='<div class="giu-empty">La vista integrada todavía no está disponible.</div>';return;}
  const readiness=v.preparacion_supervision||{};
  const blockers=readiness.bloqueos||[];
  const phaseCards=(e.fases||[]).map(p=>`<div class="giu-panel p-3"><div class="flex justify-between gap-2"><strong class="text-xs text-slate-200">${esc(p.titulo)}</strong><span class="text-xs text-cyan-200">${Number(p.porcentaje||0).toFixed(1)}%</span></div><div class="mt-2 giu-progress"><span style="width:${p.porcentaje||0}%"></span></div><p class="mt-2 text-[11px] text-slate-500">${p.completas||0} completas de ${p.total||0}</p></div>`).join('');
  const componentCards=(v.componentes||[]).map(c=>`<button class="giu-integration text-left" onclick="GIU.openModule('${esc(c.seccion||'dashboard')}')"><div class="flex items-start justify-between gap-2"><strong class="text-sm text-slate-100">${esc(c.nombre)}</strong><span class="giu-badge ${lightClass(c.semaforo)}">${esc(c.semaforo)}</span></div><p class="mt-1 text-[11px] text-slate-500">${esc(c.descripcion||'')}</p><div class="mt-3 space-y-1">${scalarMetrics(c.metricas).map(([k,val])=>`<div class="flex justify-between gap-3 text-xs text-slate-400"><span>${esc(k.replaceAll('_',' '))}</span><b class="text-slate-200">${esc(val)}</b></div>`).join('')}</div></button>`).join('');
  target.innerHTML=`<div class="grid gap-4 xl:grid-cols-[1.35fr_.65fr]"><div><h3 class="text-sm font-semibold text-slate-200">Centro operativo</h3><div class="mt-3 giu-integration-grid">${componentCards}</div></div><aside class="giu-panel p-4"><p class="text-xs uppercase tracking-[.14em] text-cyan-300">Preparación para supervisión</p><div class="mt-2 flex items-end gap-2"><strong class="text-4xl text-white">${Number(readiness.porcentaje||0).toFixed(1)}%</strong><span class="giu-badge ${lightClass(readiness.semaforo)}">${esc(readiness.semaforo||'GRIS')}</span></div><div class="mt-3 giu-progress"><span style="width:${Number(readiness.porcentaje||0)}%"></span></div><div class="mt-4 space-y-2">${blockers.length?blockers.map(text=>`<div class="giu-warning-item">${esc(text)}</div>`).join(''):'<div class="giu-success-item">No se detectaron bloqueos críticos en la lectura integrada.</div>'}</div></aside></div><h3 class="mt-6 mb-3 text-sm font-semibold text-slate-200">Avance de la Ruta Operativa</h3><div class="grid gap-3 md:grid-cols-2">${phaseCards}</div><p class="mt-5 text-[11px] text-slate-500">${esc(v.principio||'')}</p>`;
}
function renderComponents(target){
  const components=state.integrated?.componentes||[];
  target.innerHTML=`<div class="grid gap-4 md:grid-cols-2">${components.map(c=>`<div class="giu-panel p-4"><div class="flex items-start justify-between gap-3"><div><h3 class="font-semibold text-slate-100">${esc(c.nombre)}</h3><p class="mt-1 text-xs text-slate-500">${esc(c.descripcion||'')}</p></div><span class="giu-badge ${lightClass(c.semaforo)}">${esc(c.semaforo)}</span></div><div class="mt-4 grid gap-2">${scalarMetrics(c.metricas).map(([k,v])=>`<div class="giu-metric-row"><span>${esc(k.replaceAll('_',' '))}</span><b>${esc(v)}</b></div>`).join('')}</div><button class="mt-4 giu-btn giu-btn-secondary" onclick="GIU.openModule('${esc(c.seccion||'dashboard')}')">Abrir módulo fuente</button></div>`).join('')}</div>`;
}
function renderDocuments(target){
  const docs=state.integrated?.documentos||[];
  target.innerHTML=`<div class="flex flex-wrap items-center justify-between gap-3 mb-4"><div><h3 class="font-semibold text-slate-100">Índice documental único</h3><p class="text-xs text-slate-500">Son referencias a archivos de los módulos; no se copian ni se duplican registros.</p></div><button class="giu-btn giu-btn-secondary" onclick="GIU.syncDocuments()"><i data-lucide="refresh-cw"></i> Sincronizar vínculos</button></div>${docs.length?`<div class="giu-table-wrap"><table class="giu-table"><thead><tr><th>Categoría</th><th>Documento</th><th>Fuente</th><th>Estado</th><th>Fecha</th><th></th></tr></thead><tbody>${docs.map(d=>`<tr><td>${esc(d.categoria||'Documento')}</td><td><strong>${esc(d.titulo)}</strong><small>${esc(d.file_name||'Sin archivo físico')}</small></td><td>${esc(d.source_module)}<small>${esc(d.source_table)} #${esc(d.source_id)}</small></td><td><span class="giu-badge ${stateClass(d.estado)}">${esc(d.estado||'REFERENCIA')}</span></td><td>${esc(d.fecha_documento||'—')}</td><td>${d.descargable?`<button class="giu-btn giu-btn-secondary" onclick="GIU.downloadLinkedDocument(${d.id},'${esc(d.file_name||d.titulo)}')">Descargar</button>`:'<span class="text-xs text-slate-600">Referencia</span>'}</td></tr>`).join('')}</tbody></table></div>`:'<div class="giu-empty">No se encontraron documentos vinculables. Sincroniza los módulos o carga evidencias.</div>'}`;
}
async function syncDocuments(){
  if(!state.selected)return;
  try{message('Sincronizando referencias documentales…','info');await request(`/expedientes/${state.selected.id}/documentos`,{method:'POST'});await refreshIntegrated();message('Índice documental actualizado sin duplicar archivos.','success');}
  catch(error){message(error.message,'error');}
}
function downloadLinkedDocument(id,name){window.descargarArchivoAutenticado?.(`${API()}/expedientes/${state.selected.id}/documentos/${id}/descargar`,name).catch(error=>message(error.message,'error'));}
function renderAlerts(target){
  const rows=state.integrated?.alertas||[];
  target.innerHTML=`<div class="flex items-center justify-between gap-3 mb-4"><div><h3 class="font-semibold text-slate-100">Alertas consolidadas</h3><p class="text-xs text-slate-500">Salud, calidad de datos y cronograma en una sola vista.</p></div><span class="giu-badge ${rows.length?'giu-red':'giu-green'}">${rows.length} abierta(s)</span></div>${rows.length?`<div class="space-y-3">${rows.map(a=>`<button class="giu-alert-row" onclick="GIU.openModule('${esc(a.seccion||'dashboard')}')"><span class="giu-badge ${lightClass(normalizeLight(a.nivel))}">${esc(a.nivel||'AMARILLO')}</span><div><strong>${esc(a.tipo||a.componente)}</strong><p>${esc(a.mensaje||'')}</p><small>${esc(a.componente||'')} · ${esc(a.fecha||'Sin fecha')}</small></div></button>`).join('')}</div>`:'<div class="giu-success-item">No hay alertas abiertas en las fuentes integradas.</div>'}`;
}
function normalizeLight(value){const v=String(value||'').toUpperCase();return v.includes('ROJ')||v.includes('CRIT')||v.includes('ALT')?'ROJO':v.includes('VERD')||v.includes('BAJ')?'VERDE':'AMARILLO';}
function renderSchedule(target){
  const rows=state.integrated?.cronograma||[];
  target.innerHTML=`<div class="flex items-center justify-between gap-3 mb-4"><div><h3 class="font-semibold text-slate-100">Cronograma consolidado</h3><p class="text-xs text-slate-500">Actividades y entregables de los calendarios existentes.</p></div><button class="giu-btn giu-btn-secondary" onclick="GIU.openModule('calendario-inteligente')">Abrir calendario</button></div>${rows.length?`<div class="space-y-2">${rows.map(r=>`<div class="giu-schedule-row ${r.vencida?'is-overdue':''}"><time>${esc(r.fecha||'Sin fecha')}</time><div><strong>${esc(r.titulo)}</strong><p>${esc(r.descripcion||'')}</p><small>${esc(r.responsable||'Sin responsable')} · ${esc(r.source_table)}</small></div><span class="giu-badge ${r.vencida?'giu-red':stateClass(r.estado)}">${r.vencida?'VENCIDA':esc(r.estado||'PROGRAMADA')}</span></div>`).join('')}</div>`:'<div class="giu-empty">No hay actividades programadas para esta UCA.</div>'}`;
}
function renderIndicators(target){
  const rows=state.integrated?.indicadores||[];
  target.innerHTML=`<div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">${rows.map(i=>`<div class="giu-indicator-card"><div class="flex items-start justify-between gap-3"><p class="text-xs text-slate-400">${esc(i.nombre)}</p><span class="giu-badge ${lightClass(i.semaforo)}">${esc(i.semaforo)}</span></div><strong>${esc(i.valor)} <small>${esc(i.unidad||'')}</small></strong><p>${esc(i.fuente||'')}</p></div>`).join('')}</div>`;
}
function moduleFor(key){return ({base_maestra:'base-maestra',pedagogico:'gestion-pedagogica',salud_nutricion:'salud-nutricion',ram_rpp_bienestarina:'formatos',talento_humano:'talento',documentos_evidencias:'expediente-operativo-uca',cronograma:'calendario-inteligente',reportes_indicadores:'reportes-gerenciales'})[key]||'dashboard';}
function openModule(section){ if(typeof window.mostrarSeccion==='function') window.mostrarSeccion(section); }
function renderRoute(target){
  const grouped={}; (state.selected.ruta||[]).forEach(item=>(grouped[item.fase]??=[]).push(item));
  const phaseOrder=['PREPARATORIA','IMPLEMENTACION','CIERRE','TRANSVERSAL'];
  target.innerHTML=phaseOrder.filter(code=>grouped[code]?.length).map(code=>{
    const items=grouped[code]; const title=state.selected.fases?.find(p=>p.codigo===code)?.titulo||code;
    const pct=state.selected.fases?.find(p=>p.codigo===code)?.porcentaje||0;
    return `<div class="giu-phase mb-4"><div class="giu-phase-header"><div><strong class="text-sm text-slate-100">${esc(title)}</strong><p class="text-[11px] text-slate-500">${items.length} actividades</p></div><span class="giu-badge giu-blue">${Number(pct).toFixed(1)}%</span></div>${items.map(item=>`<div class="giu-route-row"><div><strong class="text-sm text-slate-200">${esc(item.titulo)}</strong><p class="mt-1 text-xs text-slate-500">${esc(item.componente)}${item.obligatoria?' · Obligatoria':' · Cuando aplique'}</p></div><div><span class="giu-badge ${stateClass(item.estado)}">${esc(item.estado)}</span><p class="mt-1 text-[11px] text-slate-500">${item.evidencias_total||0} evidencia(s)</p></div><div class="text-xs text-slate-400"><span>${esc(item.responsable_nombre||'Sin responsable')}</span><br><span>${esc(item.fecha_limite||'Sin fecha límite')}</span></div><div class="giu-route-actions flex justify-end"><button class="giu-btn giu-btn-secondary" onclick="GIU.openActivity(${item.id})">Gestionar</button></div></div>`).join('')}</div>`;
  }).join('');
}
async function openActivity(id){
  const item=state.selected?.ruta?.find(x=>x.id===id); if(!item)return;
  $('giu-act-id').value=id; $('giu-act-title').textContent=item.titulo; $('giu-act-description').textContent=item.descripcion||'';
  const stateSelect=$('giu-act-state'); stateSelect.value=item.estado||'PENDIENTE'; [...stateSelect.options].forEach(option=>{ const review=['PENDIENTE_REVISION','DEVUELTA','APROBADA','CERRADA','NO_APLICA'].includes(option.value); option.disabled=!canCoordinate()&&review&&option.value!==item.estado; }); $('giu-act-responsible').value=item.responsable_nombre||''; $('giu-act-start').value=item.fecha_inicio||''; $('giu-act-due').value=item.fecha_limite||''; $('giu-act-progress').value=item.porcentaje||0; $('giu-act-observations').value=item.observaciones||''; $('giu-act-na').value=item.justificacion_no_aplica||'';
  $('giu-evidence-list').innerHTML='<p class="text-xs text-slate-500">Consultando evidencias…</p>'; $('giu-activity-modal').classList.remove('hidden');
  try{ const data=await request(`/expedientes/${state.selected.id}/ruta/${id}/evidencias`); renderEvidenceList(data.evidencias||[]); }catch(error){$('giu-evidence-list').innerHTML=`<p class="text-xs text-rose-300">${esc(error.message)}</p>`;}
}
function closeActivity(){ $('giu-activity-modal')?.classList.add('hidden'); }
async function saveActivity(){
  const id=Number($('giu-act-id').value); if(!id)return;
  const payload={estado:$('giu-act-state').value,responsable_nombre:$('giu-act-responsible').value,fecha_inicio:$('giu-act-start').value,fecha_limite:$('giu-act-due').value,porcentaje:Number($('giu-act-progress').value||0),observaciones:$('giu-act-observations').value,justificacion_no_aplica:$('giu-act-na').value};
  try{ await request(`/expedientes/${state.selected.id}/ruta/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); message('Actividad actualizada.','success'); closeActivity(); await selectExpediente(state.selected.id); }
  catch(error){message(error.message,'error','giu-act-message');}
}
async function uploadEvidence(){
  const id=Number($('giu-act-id').value), file=$('giu-evidence-file').files?.[0]; if(!file)return message('Selecciona un archivo de evidencia.','warning','giu-act-message');
  const form=new FormData(); form.append('file',file); form.append('observaciones',$('giu-evidence-note').value||'');
  try{await request(`/expedientes/${state.selected.id}/ruta/${id}/evidencias`,{method:'POST',body:form}); $('giu-evidence-file').value=''; $('giu-evidence-note').value=''; const data=await request(`/expedientes/${state.selected.id}/ruta/${id}/evidencias`); renderEvidenceList(data.evidencias||[]); message('Evidencia cargada.','success','giu-act-message');}
  catch(error){message(error.message,'error','giu-act-message');}
}
function renderEvidenceList(rows){ const target=$('giu-evidence-list'); if(!rows.length){target.innerHTML='<p class="text-xs text-slate-500">No hay evidencias cargadas.</p>';return;} target.innerHTML=rows.map(x=>`<div class="flex items-center justify-between gap-3 border-t border-slate-700/50 py-2 text-xs"><div><strong class="text-slate-200">v${x.version} · ${esc(x.nombre_original)}</strong><p class="text-slate-500">${formatBytes(x.tamano_bytes)} · ${esc(x.fecha_carga)}</p></div><button class="giu-btn giu-btn-secondary" onclick="GIU.downloadEvidence(${x.id},'${esc(x.nombre_original)}')">Descargar</button></div>`).join('');}
function downloadEvidence(id,name){ window.descargarArchivoAutenticado?.(`${API()}/evidencias/${id}/descargar`,name).catch(error=>message(error.message,'error','giu-act-message')); }
function renderPlans(target){
  const plans=state.selected.planes||[]; target.innerHTML=`<p class="mb-4 text-sm text-slate-400">Los ocho planes comparten el expediente de la UCA y conservan responsables, indicadores y trazabilidad.</p><div class="giu-plan-grid">${plans.map(p=>`<div class="giu-panel p-4"><strong class="text-sm text-slate-100">${esc(p.nombre)}</strong><div class="mt-3 grid gap-2"><input id="giu-plan-resp-${p.id}" class="giu-input" value="${esc(p.responsable_nombre||'')}" placeholder="Responsable"><select id="giu-plan-state-${p.id}" class="giu-input">${['BORRADOR','EN_EJECUCION','PENDIENTE_REVISION','APROBADO','CERRADO'].map(s=>`<option ${s===p.estado?'selected':''} ${!canCoordinate()&&['APROBADO','CERRADO'].includes(s)&&s!==p.estado?'disabled':''}>${s}</option>`).join('')}</select><label class="text-xs text-slate-400">Progreso <input id="giu-plan-progress-${p.id}" type="number" min="0" max="100" class="giu-input mt-1" value="${Number(p.progreso||0)}"></label><textarea id="giu-plan-note-${p.id}" class="giu-input" placeholder="Observaciones">${esc(p.observaciones||'')}</textarea><button class="giu-btn giu-btn-primary" onclick="GIU.savePlan(${p.id})">Guardar plan</button></div></div>`).join('')}</div>`;
}
async function savePlan(id){
  try{const payload={responsable_nombre:$(`giu-plan-resp-${id}`).value,estado:$(`giu-plan-state-${id}`).value,progreso:Number($(`giu-plan-progress-${id}`).value||0),observaciones:$(`giu-plan-note-${id}`).value}; await request(`/expedientes/${state.selected.id}/planes/${id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); message('Plan actualizado.','success'); await selectExpediente(state.selected.id);}catch(error){message(error.message,'error');}
}
function renderLinkedLibrary(target){
  const docs=state.selected.biblioteca||[]; target.innerHTML=`<div class="flex items-center justify-between gap-3 mb-3"><p class="text-sm text-slate-400">Documentos y formatos versionados disponibles para esta fundación.</p><button class="giu-btn giu-btn-secondary" onclick="GIU.openModule('biblioteca-icbf')">Administrar biblioteca</button></div><div class="grid gap-3 md:grid-cols-2">${docs.map(d=>`<div class="giu-library-card"><div class="flex items-start justify-between gap-3"><div><strong class="text-sm text-slate-100">${esc(d.codigo)} · ${esc(d.nombre)}</strong><p class="mt-1 text-xs text-slate-500">${esc(d.componente||'Transversal')}</p></div><span class="giu-badge ${d.version_vigente?'giu-green':'giu-yellow'}">${d.version_vigente?`v${esc(d.version_vigente.version)}`:'Sin vigente'}</span></div></div>`).join('')}</div>`;
}
function downloadPackage(id){window.descargarArchivoAutenticado?.(`${API()}/expedientes/${id}/paquete-supervision`).catch(error=>message(error.message,'error'));}

async function bibliotecaInit(){ if(!state.initialized){bindForms();state.initialized=true;} await loadLibrary(); }
async function loadLibrary(){
  try{const data=await request('/biblioteca/documentos');state.biblioteca=data.documentos||[];renderLibrary();await loadLibraryOperations();message('', 'info','bib-message');}
  catch(error){message(error.message,'error','bib-message');}
}
function renderLibrary(){
  const target=$('bib-list'); if(!target)return;
  $('bib-admin-panel')?.classList.toggle('hidden',!canLibraryAdmin());
  if(!state.biblioteca.length){target.innerHTML='<div class="giu-empty">No hay documentos registrados.</div>';return;}
  target.innerHTML=state.biblioteca.map(doc=>`<div class="giu-library-card"><div class="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-3"><div><p class="text-[11px] uppercase tracking-[.14em] text-cyan-300">${esc(doc.codigo)} · ${esc(doc.tipo_documento)}</p><h3 class="mt-1 font-semibold text-slate-100">${esc(doc.nombre)}</h3><p class="mt-1 text-xs text-slate-500">${esc(doc.componente||'Transversal')} · ${esc(doc.fuente_tipo||'Manual')}</p><p class="mt-2 text-xs text-slate-400">${esc(doc.descripcion||'')}</p></div>${canLibraryAdmin()?`<button class="giu-btn giu-btn-secondary" onclick="GIU.prepareVersion(${doc.id},'${esc(doc.codigo)}')">Nueva versión</button>`:''}</div><div class="mt-3">${(doc.versiones||[]).map(v=>`<div class="giu-version-row"><div><strong class="text-xs text-slate-200">Versión ${esc(v.version)}</strong><span class="ml-2 giu-badge ${v.estado==='VIGENTE'?'giu-green':'giu-blue'}">${esc(v.estado)}</span><p class="mt-1 text-[11px] text-slate-500">${esc(v.fecha_documento||'Sin fecha')} · ${v.sha256?`SHA ${esc(v.sha256.slice(0,12))}…`:'Sin archivo'}</p></div><div class="flex gap-2">${v.ruta_archivo?`<button class="giu-btn giu-btn-secondary" onclick="GIU.downloadLibraryVersion(${v.id},'${esc(v.nombre_original||doc.codigo)}')">Descargar</button>`:''}${canLibraryAdmin()&&v.estado!=='VIGENTE'?`<button class="giu-btn giu-btn-primary" onclick="GIU.activateVersion(${v.id})">Activar</button>`:''}</div></div>`).join('')||'<p class="text-xs text-slate-500">Sin versiones.</p>'}</div></div>`).join('');
  if(window.lucide)lucide.createIcons();
}
function prepareVersion(id,code){$('bib-version-document-id').value=id;$('bib-version-title').textContent=`Nueva versión · ${code}`;$('bib-version-form').classList.remove('hidden');$('bib-version-form').scrollIntoView({behavior:'smooth',block:'center'});}
async function createLibraryDocument(event){
  event.preventDefault(); const payload={codigo:$('bib-code').value,nombre:$('bib-name').value,tipo_documento:$('bib-type').value,modalidad:$('bib-modality').value,componente:$('bib-component').value,descripcion:$('bib-description').value,fuente_tipo:$('bib-source-type').value,fuente_url:$('bib-source-url').value,verificacion_automatica:false};
  try{await request('/biblioteca/documentos',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});event.target.reset();message('Documento registrado.','success','bib-message');await loadLibrary();}catch(error){message(error.message,'error','bib-message');}
}
async function uploadLibraryVersion(event){
  event.preventDefault(); const id=$('bib-version-document-id').value; if(!id)return message('Selecciona un documento.','warning','bib-message'); const form=new FormData(event.target); try{await request(`/biblioteca/documentos/${id}/versiones`,{method:'POST',body:form});event.target.reset();$('bib-version-document-id').value='';$('bib-version-form').classList.add('hidden');message('Versión registrada.','success','bib-message');await loadLibrary();}catch(error){message(error.message,'error','bib-message');}
}
async function activateVersion(id){try{await request(`/biblioteca/versiones/${id}/activar`,{method:'POST'});message('Versión vigente actualizada.','success','bib-message');await loadLibrary();}catch(error){message(error.message,'error','bib-message');}}
function downloadLibraryVersion(id,name){window.descargarArchivoAutenticado?.(`${API()}/biblioteca/versiones/${id}/descargar`,name).catch(error=>message(error.message,'error','bib-message'));}

async function loadLibraryOperations(){
  try{
    const [sources,candidates,notifications,history]=await Promise.all([
      request('/biblioteca/fuentes'),request('/biblioteca/candidatos'),request('/biblioteca/notificaciones'),request('/biblioteca/historial?limit=100')
    ]);
    state.librarySources=sources.fuentes||[]; state.libraryCandidates=candidates.candidatos||[];
    state.libraryNotifications=notifications.notificaciones||[]; state.libraryHistory=history.historial||[];
    renderLibraryOperations();
  }catch(error){message(error.message,'error','bib-message');}
}
function renderLibraryOperations(){
  const src=$('bib-sources'),can=canLibraryAdmin();
  ['bib-source-authorized','bib-source-enabled'].forEach(id=>{const el=$(id);if(el)el.disabled=!canLibraryApprove();});
  const mech=$('bib-source-mechanism');if(mech&& !canLibraryApprove())mech.value='MANUAL';
  if(src)src.innerHTML=state.librarySources.length?state.librarySources.map(x=>`<div class="giu-panel p-3"><div class="flex items-start justify-between gap-3"><div><strong class="text-xs text-slate-100">${esc(x.nombre)}</strong><p class="mt-1 text-[11px] text-slate-500">${esc(x.mecanismo)} · ${esc(x.url_base||'Sin URL')}</p><small class="text-[10px] text-slate-600">${esc(x.estado_ultima_revision||'SIN_REVISAR')} · ${esc(x.detalle_ultima_revision||'')}</small></div><span class="giu-badge ${x.habilitada&&x.autorizada?'giu-green':'giu-yellow'}">${x.habilitada&&x.autorizada?'ACTIVA':'CONTROLADA'}</span></div>${can&&x.habilitada&&x.autorizada?`<button class="giu-btn giu-btn-secondary mt-2" onclick="GIU.verifyLibrarySource(${x.id})">Verificar fuente</button>`:''}</div>`).join(''):'<div class="giu-empty">No hay fuentes registradas. La actualización remota permanece deshabilitada por seguridad.</div>';
  const c=$('bib-candidates'); if(c)c.innerHTML=state.libraryCandidates.length?state.libraryCandidates.map(x=>`<div class="giu-panel p-3"><strong class="text-xs text-slate-100">${esc(x.codigo_documento)} · v${esc(x.version_detectada)}</strong><p class="mt-1 text-[11px] text-slate-500">${esc(x.nombre_documento||'Documento detectado')} · ${esc(x.estado)}</p>${canLibraryApprove()&&x.estado==='DETECTADA'?`<div class="mt-2 flex gap-2"><button class="giu-btn giu-btn-primary" onclick="GIU.decideCandidate(${x.id},'aprobar')">Aprobar metadatos</button><button class="giu-btn giu-btn-danger" onclick="GIU.decideCandidate(${x.id},'rechazar')">Rechazar</button></div>`:''}</div>`).join(''):'<div class="giu-empty">No hay actualizaciones candidatas.</div>';
  const n=$('bib-notifications'); if(n)n.innerHTML=state.libraryNotifications.length?state.libraryNotifications.slice(0,20).map(x=>`<button class="giu-panel p-3 w-full text-left" onclick="GIU.readLibraryNotification(${x.id})"><strong class="text-xs text-slate-100">${esc(x.titulo)}</strong><p class="mt-1 text-[11px] text-slate-400">${esc(x.mensaje)}</p><small class="text-[10px] text-slate-600">${esc(x.creada_en)}</small></button>`).join(''):'<div class="giu-empty">No hay notificaciones.</div>';
  const h=$('bib-history'); if(h)h.innerHTML=state.libraryHistory.length?state.libraryHistory.slice(0,30).map(x=>`<div class="giu-panel p-3"><strong class="text-xs text-slate-100">${esc(x.accion)}</strong><p class="mt-1 text-[11px] text-slate-500">${esc(x.estado_anterior||'')} → ${esc(x.estado_nuevo||'')} · ${esc(x.usuario||'sistema')}</p><small class="text-[10px] text-slate-600">${esc(x.fecha)}</small></div>`).join(''):'<div class="giu-empty">Sin movimientos registrados.</div>';
}
async function verifyLibrarySource(id){try{message('Verificando únicamente la fuente autorizada…','info','bib-message');const d=await request(`/biblioteca/fuentes/${id}/verificar`,{method:'POST'});message(d.message,'success','bib-message');await loadLibraryOperations();}catch(e){message(e.message,'error','bib-message');}}
async function decideCandidate(id,action){try{await request(`/biblioteca/candidatos/${id}/${action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});message('Decisión registrada. La versión no se activa automáticamente.','success','bib-message');await loadLibrary();}catch(e){message(e.message,'error','bib-message');}}
async function readLibraryNotification(id){try{await request(`/biblioteca/notificaciones/${id}/leer`,{method:'POST'});await loadLibraryOperations();}catch(e){message(e.message,'error','bib-message');}}


async function saveLibrarySource(event){
  event.preventDefault(); if(!canLibraryAdmin())return;
  const payload={codigo:$('bib-source-code').value,nombre:$('bib-source-name').value,mecanismo:$('bib-source-mechanism').value,url_base:$('bib-source-url-base').value,dominio_permitido:$('bib-source-domain').value,autorizada:$('bib-source-authorized').checked,habilitada:$('bib-source-enabled').checked,configuracion:{items_path:'documents'}};
  try{await request('/biblioteca/fuentes',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});event.target.reset();message('Fuente guardada sin ejecutar consultas automáticas.','success','bib-message');await loadLibraryOperations();}catch(e){message(e.message,'error','bib-message');}
}
async function importManualCandidate(event){
  event.preventDefault(); if(!canLibraryAdmin())return;
  const document={codigo:$('bib-candidate-code').value,nombre:$('bib-candidate-name').value,version:$('bib-candidate-version').value,fuente_url:$('bib-candidate-url').value};
  try{await request('/biblioteca/candidatos/importar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({documentos:[document]})});event.target.reset();message('Candidato importado para revisión manual.','success','bib-message');await loadLibraryOperations();}catch(e){message(e.message,'error','bib-message');}
}

function bindForms(){ $('bib-document-form')?.addEventListener('submit',createLibraryDocument); $('bib-version-form')?.addEventListener('submit',uploadLibraryVersion); $('bib-source-form')?.addEventListener('submit',saveLibrarySource); $('bib-candidate-form')?.addEventListener('submit',importManualCandidate); }

window.GIU={init,loadDashboard,syncUnits,selectExpediente,setTab,refreshIntegrated,syncDocuments,downloadLinkedDocument,openActivity,closeActivity,saveActivity,uploadEvidence,downloadEvidence,savePlan,downloadPackage,openModule,bibliotecaInit,loadLibrary,loadLibraryOperations,prepareVersion,activateVersion,downloadLibraryVersion,verifyLibrarySource,decideCandidate,readLibraryNotification};
window.giuInit=init; window.bibliotecaIcbfInit=bibliotecaInit;
})();
