import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
import {operationReason,confirmationText,runKind,controlReason,materialReason} from './run-readiness.js';
const controls=document.querySelector('#generation-controls'),status=document.querySelector('#run-status'),live=document.querySelector('#live-text');
const terminal=new Set(['completed','failed','cancelled','interrupted','needs_review','alternative','paused']);
const names={queued:'У черзі',running:'Генерація',pause_requested:'Пауза після етапу',paused:'На паузі',cancellation_requested:'Скасування запитано; очікуємо виходу клієнта',cancelled:'Клієнт завершив скасування',completed:'Завершено',failed:'Помилка',interrupted:'Перервано попередню сесію',needs_review:'Потрібне рішення автора',alternative:'Збережено альтернативу після конфлікту'};
let active=null,source=null,last=0,started=Date.now(),followEpoch=0;
let readiness=null,readinessEpoch=0,historyRuns=null,pendingReadiness=null,pendingEpoch=0;
const actions=[];
function updateControls(){for(const item of actions){let reason=item.operation?operationReason(state,readiness?.operations[item.operation]):['latest','proposal','apply'].includes(item.action)?materialReason(item.action,state,historyRuns):item.action?controlReason(item.action,active):'';if(['resume','repeat'].includes(item.action))reason=reason||operationReason(state,pendingReadiness);if(item.busy)reason='Виконуємо запит…';item.button.disabled=!!reason;item.button.title=reason;item.hint.textContent=reason;item.button.setAttribute('aria-describedby',item.hint.id)}}
async function loadPending(){const epoch=++pendingEpoch;pendingReadiness=null;updateControls();if(!active)return;try{const result=await api(`/api/runs/${active.id}/readiness`);if(epoch===pendingEpoch){pendingReadiness=result;updateControls()}}catch(error){if(epoch===pendingEpoch){pendingReadiness={ready:false,reason:error.message};updateControls()}}}
async function loadReadiness(){const epoch=++readinessEpoch;readiness=null;updateControls();try{const [result,runs]=await Promise.all([api(`/api/stories/${state.storyId}/readiness${state.scene?'?scene_id='+encodeURIComponent(state.scene.id):''}`),api(`/api/stories/${state.storyId}/runs`)]);if(epoch===readinessEpoch){readiness=result;historyRuns=runs.runs;updateControls()}}catch(error){if(epoch===readinessEpoch){readiness={operations:Object.fromEntries(['prepare','brief','draft','edit','memory','scene','remaining','rebuild_memory'].map(key=>[key,{ready:false,reason:error.message}]))};updateControls();notice(error.message,'error')}}}
for(const event of ['story-refreshed','scene-selected','evaluation-policy-changed'])document.addEventListener(event,()=>{loadReadiness();if(active&&terminal.has(active.state))loadPending()});
document.addEventListener('editor-state-changed',updateControls);
document.querySelector('#editor').addEventListener('input',updateControls);
const elapsed=document.createElement('p');
function draw(run){active=run;status.dataset.kind=runKind(run.state);status.setAttribute('role',run.state==='failed'?'alert':'status');status.replaceChildren();const p=document.createElement('p');p.textContent=names[run.state]||run.state;status.append(p);if(run.error){const e=document.createElement('p');e.textContent=run.error;status.append(e)}elapsed.textContent=terminal.has(run.state)?'':elapsed.textContent;status.append(elapsed);updateControls();if(terminal.has(run.state))loadPending()}
setInterval(()=>{if(active&&!terminal.has(active.state))elapsed.textContent=`Минуло ${Math.floor((Date.now()-started)/1000)} с`},1000);
async function follow(run){
  const epoch=++followEpoch;let stateFetch=0;
  source?.close();last=0;started=Date.parse(run.created_at);draw(run);live.hidden=false;
  const saved=await api('/api/runs/'+run.id);if(epoch!==followEpoch)return;draw(saved.run);live.textContent=saved.partial;
  const attempt=saved.attempts?.at(-1);if(attempt?.created_at)started=Date.parse(attempt.created_at);
  if(terminal.has(saved.run.state)){await refresh();return}
  // Replay from the beginning once; reconnects use the saved event cursor.
  live.textContent='';
  source=new EventSource(`/api/runs/${run.id}/events`);
  const reader=source;
  source.onmessage=async message=>{try{if(epoch!==followEpoch)return;const event=JSON.parse(message.data);last=event.seq;
    if(event.type==='stage_started'){if(event.created_at)started=Date.parse(event.created_at);live.textContent='';const p=document.createElement('p');p.textContent=`${event.data.stage} · ${event.data.model} · ${event.data.provider}`;status.append(p)}
    if(event.type==='delta')live.textContent+=event.data.text;
    if(event.type==='stage_finished'){const p=document.createElement('p');p.textContent=Object.keys(event.data.usage||{}).length?'Usage провайдера: '+JSON.stringify(event.data.usage):'Usage і вартість: невідомі';status.append(p);await refresh()}
    if(event.type==='state'){const stamp=++stateFetch,current=await api('/api/runs/'+run.id);if(epoch!==followEpoch||stamp!==stateFetch)return;draw(current.run);if(terminal.has(current.run.state)){live.textContent=current.partial;reader.close();followEpoch++;notice(names[current.run.state]+(current.run.error?': '+current.run.error:''),runKind(current.run.state));await refresh()}}
    }catch(error){notice(error.message,'error')}
  };
  source.onerror=()=>{if(epoch===followEpoch&&active&&!terminal.has(active.state))notice('Зв’язок із подіями перервано; браузер перепідключиться. Стан запуску уточнюється на сервері.','warning')};
}
async function start(mode,stage){
  if(!state.scene&&mode!=='prepare')throw new Error('Оберіть сцену');
  if(state.dirty)throw new Error('Спершу збережіть ручні правки');
  await loadReadiness();
  const operation=readiness?.operations[stage||mode],reason=operationReason(state,operation);
  if(reason)throw new Error(reason);
  if(!confirm(confirmationText(operation)))return;
  const request={story_id:state.storyId,scene_id:mode==='prepare'?null:state.scene.id,mode,stage:stage||null,pause_after:document.querySelector('#pause-each').checked?['brief','draft','edit','memory']:[]};
  const key='storygen.pending.'+JSON.stringify(request);let requestId=localStorage.getItem(key)||crypto.randomUUID();localStorage.setItem(key,requestId);
  const run=await api('/api/runs',json('POST',{request_id:requestId,request}));localStorage.removeItem(key);await follow(run);
}
controls.hidden=false;
function button(label,fn,operation=null,action=null){const wrapper=document.createElement('span');wrapper.className='run-action';const b=document.createElement('button'),hint=document.createElement('small');hint.id='run-reason-'+actions.length;b.className='secondary';b.textContent=label;const item={button:b,hint,operation,action,busy:false};actions.push(item);b.onclick=async()=>{item.busy=true;updateControls();try{await fn()}catch(e){notice(e.message,'error')}finally{item.busy=false;updateControls()}};wrapper.append(b,hint);controls.append(wrapper);updateControls()}
button('Підготувати структуру',()=>start('prepare'),'prepare');
for(const [stage,label] of Object.entries({brief:'Створити завдання',draft:'Написати',edit:'Редагувати',memory:'Оновити пам’ять'}))button(label,()=>start('stage',stage),stage);
button('Уся сцена',()=>start('scene'),'scene');button('Пройти решту',()=>start('remaining'),'remaining');
const pauseLabel=document.createElement('label');pauseLabel.innerHTML='<input id="pause-each" type="checkbox"> Пауза після кожного етапу';controls.append(pauseLabel);
button('Пауза',async()=>{if(active)draw(await api(`/api/runs/${active.id}/pause`,json('POST',{})))},null,'pause');
button('Скасувати',async()=>{if(active)draw(await api(`/api/runs/${active.id}/cancel`,json('POST',{})))},null,'cancel');
async function resumeRun(repeat){if(!active)return;await loadPending();const reason=operationReason(state,pendingReadiness);if(reason)throw new Error(reason);if(!confirm((repeat?'Повторний виклик може повторно спожити ресурси.\n':'')+confirmationText(pendingReadiness)))return;await follow(await api(`/api/runs/${active.id}/resume`,json('POST',{repeat_interrupted:repeat})))}
button('Продовжити',()=>resumeRun(false),null,'resume');
button('Повторити перерваний етап',()=>resumeRun(true),null,'repeat');
button('Перебудувати пам’ять далі',()=>start('rebuild_memory'),'rebuild_memory');
button('Переглянути останній запуск',async()=>{const runs=(await api(`/api/stories/${state.storyId}/runs`)).runs;if(runs.length)await follow(runs.at(-1))},null,'latest');
button('Переглянути пропозицію структури',async()=>{const runs=(await api(`/api/stories/${state.storyId}/runs`)).runs;const run=[...runs].reverse().find(r=>r.request.mode==='prepare'&&r.state==='completed');if(!run)throw new Error('Немає завершеної пропозиції');const details=await api('/api/runs/'+run.id);const ref=details.attempts.at(-1).result_version_id;const proposal=(await api('/api/versions/'+ref)).text;const editor=document.querySelector('#editor');if(state.dirty)throw new Error('Спершу збережіть правки');editor.value=proposal;state.mode='blueprint';state.dirty=false;document.querySelector('#current-kind').textContent='ПРОПОЗИЦІЯ СТРУКТУРИ (JSON)';document.querySelector('#save-text').disabled=true;updateControls()},null,'proposal');
button('Застосувати пропозицію структури',async()=>{if(state.mode!=='blueprint')throw new Error('Спершу перегляньте пропозицію');const proposal=JSON.parse(document.querySelector('#editor').value);if(!confirm('Застосувати відредаговану пропозицію канону й персонажів? Наявні сцени залишаться під вашим контролем.'))return;await api(`/api/stories/${state.storyId}/blueprint/apply`,json('POST',{proposal,expected_revision:state.view.story.revision}));state.dirty=false;await refresh();notice('Канон і персонажів застосовано')},null,'apply');
loadReadiness();
api(`/api/stories/${state.storyId}/runs`).then(result=>{if(result.runs.length)follow(result.runs.at(-1)).catch(e=>notice(e.message,'error'))}).catch(e=>notice(e.message,'error'));
