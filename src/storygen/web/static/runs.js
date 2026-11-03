import {live as liveLabel,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {acceptedContinuation} from './acceptance.js';
import {api,json,notice} from './api.js';
import {state,refresh,loadBuffer,textEditor} from './editor.js';
import {registerWorkspaceCommand} from './workspace-commands.js';
import {assertReadyDispatch} from './workspace-state.js';
import {operationReason,confirmationText,runKind,controlReason,materialReason,editorLoopOperation} from './run-readiness.js';
const controls=document.querySelector('#generation-controls'),status=document.querySelector('#run-status'),live=document.querySelector('#live-text');
const terminal=new Set(['completed','failed','cancelled','interrupted','needs_review','alternative','paused']);
const names={get queued(){return t("m_eb3c78969040")},get running(){return t("m_b4232dd37ccb")},get pause_requested(){return t("m_7b3ff291c3da")},get paused(){return t("m_914a1d354f3b")},get cancellation_requested(){return t("m_4037d1b317aa")},get cancelled(){return t("m_7c3f9efa92f8")},get completed(){return t("m_016bc923f7ff")},get failed(){return t("m_57467fc4b91f")},get interrupted(){return t("m_e8bcb6c8f22e")},get needs_review(){return t("m_f2898eb5c9bf")},get alternative(){return t("m_ea160912aa6f")}};
let active=null,source=null,last=0,started=Date.now(),followEpoch=0;
let readiness=null,readinessEpoch=0,historyRuns=null,pendingReadiness=null,pendingEpoch=0;
let continuation=null;
const actions=[];
function updateControls(){for(const item of actions){let reason=item.operation?operationReason(state,readiness?.operations[item.operation]):['latest','proposal','apply'].includes(item.action)?materialReason(item.action,state,historyRuns):item.action==='accepted'?operationReason(state,{ready:!!continuation,reason:t("m_7795d03d9c33")}):item.action?controlReason(item.action,active):'';if(['resume','repeat'].includes(item.action))reason=reason||(active?.impact?.protocol===3&&['awaiting_author','author_editing'].includes(active.impact.phase)?t('review.author_required'):operationReason(state,pendingReadiness));if(item.busy)reason=t("m_08ee1e43995d");item.button.disabled=!!reason;uiText(item.button,"title",()=>(diagnostic(reason)));uiText(item.hint,"textContent",()=>(diagnostic(reason)));item.button.setAttribute('aria-describedby',item.hint.id);if(['pause','cancel','resume','repeat','accepted'].includes(item.action))item.wrapper.hidden=['resume','repeat'].includes(item.action)?!!controlReason(item.action,active):!!reason}}
async function loadPending(){
  const epoch=++pendingEpoch;pendingReadiness=null;continuation=null;updateControls();if(!active)return;
  const runId=active.id;
  try{
    const [result,details]=await Promise.all([api(`/api/runs/${runId}/readiness`),api(`/api/runs/${runId}`)]);
    const task=details.run.tasks[details.run.cursor];
    let candidate=null;
    if(['alternative','needs_review'].includes(details.run.state)&&task?.scene_id){
      const history=await api(`/api/scenes/${task.scene_id}/versions`);
      candidate=acceptedContinuation(details.run,details.attempts,history.scene,history.versions,history.acceptances||[]);
    }
    if(epoch===pendingEpoch){pendingReadiness=result;continuation=candidate;updateControls()}
  }catch(error){if(epoch===pendingEpoch){pendingReadiness={ready:false,reason:error.message};updateControls()}}
}
function selectedSource(options={}){
  if(options.editor_source_head)return {editor_source_head:options.editor_source_head,editor_source_version_id:options.editor_source_version_id};
  const head=['draft','prose'].includes(state.mode)?state.mode:null;
  return head&&state.scene?.heads[head]?{editor_source_head:head,editor_source_version_id:state.scene.heads[head]}:{};
}
async function loadReadiness(options={}){
  const epoch=++readinessEpoch;readiness=null;state.workspaceReadiness=null;updateControls();document.dispatchEvent(new CustomEvent('workspace-readiness'));
  try{
    const query=new URLSearchParams(state.scene?{scene_id:state.scene.id,...selectedSource(options)}:{});
    const [result,runs]=await Promise.all([api(`/api/stories/${state.storyId}/readiness?${query}`),api(`/api/stories/${state.storyId}/runs`)]);
    if(epoch===readinessEpoch){readiness=result;historyRuns=runs.runs;state.workspaceReadiness=result;state.workspaceRuns=historyRuns;updateControls();document.dispatchEvent(new CustomEvent('workspace-readiness'))}
  }catch(error){if(epoch===readinessEpoch){readiness={operations:Object.fromEntries(['prepare','brief','draft','edit','memory','scene','remaining','rebuild_memory','edit_loop'].map(key=>[key,{ready:false,reason:error.message}]))};state.workspaceReadiness=readiness;updateControls();notice(error.message,'error')}}
}
for(const event of ['story-refreshed','scene-selected','evaluation-policy-changed'])document.addEventListener(event,()=>{loadReadiness();if(active&&terminal.has(active.state))loadPending()});
document.addEventListener('editor-state-changed',()=>{updateControls();if(state.mode!==state.workspaceReadinessMode){state.workspaceReadinessMode=state.mode;void loadReadiness()}});
textEditor.onInput(updateControls);
const elapsed=document.createElement('p');
function draw(run){active=run;state.workspaceRun=run;document.dispatchEvent(new CustomEvent('workspace-run-state',{detail:run}));status.dataset.kind=run.warning&&run.state!=='failed'?'warning':runKind(run.state);status.setAttribute('role',run.state==='failed'?'alert':'status');status.replaceChildren();const p=document.createElement('p');uiText(p,"textContent",()=>(names[run.state]||run.state));status.append(p);for(const message of [...new Set([run.error,run.warning].filter(Boolean))]){const e=document.createElement('p');uiText(e,"textContent",()=>(diagnostic(message)));status.append(e)}uiText(elapsed,"textContent",()=>(terminal.has(run.state)?'':elapsed.textContent));status.append(elapsed);updateControls();if(terminal.has(run.state))loadPending()}
setInterval(()=>{if(active&&!terminal.has(active.state))uiText(elapsed,"textContent",()=>(t("m_61cb5f9a3bb9",{p0:(Math.floor((Date.now()-started)/1000))})))},1000);
async function follow(run){
  const epoch=++followEpoch;let stateFetch=0;
  source?.close();last=0;started=Date.parse(run.created_at);draw(run);live.hidden=false;
  const saved=await api('/api/runs/'+run.id);if(epoch!==followEpoch)return;draw(saved.run);uiText(live,"textContent",()=>(saved.partial));
  const attempt=saved.attempts?.at(-1);if(attempt?.created_at)started=Date.parse(attempt.created_at);
  if(terminal.has(saved.run.state)){await refresh();return}
  // Replay from the beginning once; reconnects use the saved event cursor.
  uiText(live,"textContent",()=>(''));
  source=new EventSource(`/api/runs/${run.id}/events`);
  const reader=source;
  source.onmessage=async message=>{try{if(epoch!==followEpoch)return;const event=JSON.parse(message.data);last=event.seq;
    if(event.type==='stage_started'){if(event.created_at)started=Date.parse(event.created_at);uiText(live,"textContent",()=>(''));const p=document.createElement('p');uiText(p,"textContent",()=>((event.data.edit_loop_pass?t("m_9a029cc4638c",{p0:(event.data.edit_loop_pass),p1:(event.data.edit_loop_limit)}):'')+`${event.data.stage} · ${event.data.model} · ${event.data.provider}`));status.append(p)}
    if(event.type==='delta')live.textContent+=event.data.text;
    if(event.type==='stage_finished'){const p=document.createElement('p');uiText(p,"textContent",()=>(Object.keys(event.data.usage||{}).length?t("m_15e66c683330")+JSON.stringify(event.data.usage):t("m_59303d743463")));status.append(p);await refresh()}
    if(event.type==='evaluation_warning'||event.type==='evaluation_skipped'){notice(event.data.failure?.message||event.data.reason||event.data.reasons?.join('; ')||t("m_8c627045acd1"),'warning');document.dispatchEvent(new CustomEvent('evaluation-policy-changed'))}
    if(event.type==='state'||event.type==='context_warning'){const stamp=++stateFetch,current=await api('/api/runs/'+run.id);if(epoch!==followEpoch||stamp!==stateFetch)return;draw(current.run);if(terminal.has(current.run.state)){uiText(live,"textContent",()=>(current.partial));reader.close();followEpoch++;notice(names[current.run.state]+(current.run.error||current.run.warning?': '+(current.run.error||current.run.warning):''),current.run.warning&&current.run.state!=='failed'?'warning':runKind(current.run.state));await refresh()}}
    }catch(error){notice(error.message,'error')}
  };
  source.onerror=()=>{if(epoch===followEpoch&&active&&!terminal.has(active.state))notice(msg("m_0907c7c982d4"),'warning')};
}
document.addEventListener('run-enqueued',event=>follow(event.detail).catch(error=>notice(error.message,'error')));
async function start(mode,stage,options={}){
  const captured={sceneId:state.scene?.id,epoch:state.bufferEpoch,mode:state.mode};
  if(!state.scene&&mode!=='prepare')throw new Error(t("m_f0f1417db6de"));
  if(state.dirty)throw new Error(t("m_a4c2e86ecc1a"));
  await loadReadiness(options);
  assertReadyDispatch(state,captured);
  let operation=readiness?.operations[stage||mode];
  const passLimit=Number(document.querySelector('#edit-pass-limit')?.value||5);
  const usesEditorLoop=['edit_loop','scene','remaining'].includes(mode);
  if(usesEditorLoop)operation=editorLoopOperation(operation,passLimit);
  const reason=operationReason(state,operation);
  if(reason)throw new Error(reason);
  if(!confirm(confirmationText(operation)))return;
  const request={story_id:state.storyId,scene_id:mode==='prepare'?null:state.scene.id,mode,stage:stage||null,pause_after:document.querySelector('#pause-each').checked?['brief','draft','edit','memory']:[]};
  if(mode==='stage'&&stage==='memory'&&operation.memory_review)request.memory_approval=operation.memory_review.fingerprint;
  if(usesEditorLoop){request.edit_pass_limit=passLimit;request.edit_workflow='loop'}
  if(mode==='edit_loop')Object.assign(request,selectedSource(options));
  request.budget_limit_usd=document.querySelector('#run-budget')?.value||null;
  const key='storygen.pending.'+JSON.stringify(request);let requestId=localStorage.getItem(key)||crypto.randomUUID();localStorage.setItem(key,requestId);
  const run=await api('/api/runs',json('POST',{request_id:requestId,request}));localStorage.removeItem(key);await follow(run);return active;
}
controls.hidden=false;
function button(label,fn,operation=null,action=null){const wrapper=document.createElement('span');wrapper.className='run-action';const b=document.createElement('button'),hint=document.createElement('small');hint.id='run-reason-'+actions.length;b.className='secondary';uiText(b,"textContent",()=>(label));const item={button:b,hint,wrapper,operation,action,busy:false};actions.push(item);b.onclick=async()=>{item.busy=true;updateControls();try{await fn()}catch(e){notice(e.message,'error')}finally{item.busy=false;updateControls()}};wrapper.append(b,hint);(document.querySelector('#run-actions')&&['pause','cancel','resume','repeat','accepted'].includes(action)?document.querySelector('#run-actions'):controls).append(wrapper);updateControls();return wrapper}
button(liveLabel(()=>(t("m_4c7f8d65f750"))),()=>start('prepare'),'prepare');
for(const [stage,label] of labelEntries({get brief(){return t("m_27e8e3278f1a")},get draft(){return t("m_a0503ed62ae7")},get edit(){return t("m_c542d0ba7da5")},get memory(){return t("m_05c4218abe15")}})){
  if(stage==='edit'){
    const editorAction=button(label,()=>start('edit_loop'),'edit_loop');
    const passLabel=document.createElement('label');uiHTML(passLabel,"<span data-i18n=\"m_6c1316f99476\">Максимум проходів редактури</span><input id=\"edit-pass-limit\" type=\"number\" min=\"1\" max=\"10\" step=\"1\" value=\"5\">",{});editorAction.append(passLabel);
  }
  else button(label,()=>start('stage',stage),stage);
}
button(liveLabel(()=>(t("m_3f2da413a47a"))),()=>start('scene'),'scene');button(liveLabel(()=>(t("m_9d2918521914"))),()=>start('remaining'),'remaining');
const pauseLabel=document.createElement('label');uiHTML(pauseLabel,"<input id=\"pause-each\" type=\"checkbox\"> <span data-i18n=\"m_991c0d0700bb\">Пауза після кожного етапу</span>",{});controls.append(pauseLabel);
button(liveLabel(()=>(t("m_03498e395a43"))),async()=>{if(active)draw(await api(`/api/runs/${active.id}/pause`,json('POST',{})))},null,'pause');
button(liveLabel(()=>(t("m_8b4c2025378a"))),async()=>{if(active)draw(await api(`/api/runs/${active.id}/cancel`,json('POST',{})))},null,'cancel');
async function resumeRun(repeat){if(!active)return;await loadPending();const reason=operationReason(state,pendingReadiness);if(reason)throw new Error(reason);if(!confirm((repeat?t("m_f126caaa8d97"):'')+confirmationText(pendingReadiness)))return;await follow(await api(`/api/runs/${active.id}/resume`,json('POST',{repeat_interrupted:repeat})))}
button(liveLabel(()=>(t("m_387c0a3209b9"))),async()=>{
  await loadPending();
  const reason=operationReason(state,{ready:!!continuation,reason:t("m_46e01b57161e")});if(reason)throw new Error(reason);
  const runId=active.id,body=continuation;
  if(!confirm(t("m_371741f40974")))return;
  await follow(await api(`/api/runs/${runId}/continue-after-acceptance`,json('POST',body)));
},null,'accepted');
button(liveLabel(()=>(t("m_a50d268827d2"))),()=>resumeRun(false),null,'resume');
button(liveLabel(()=>(t("m_7a9c5a57576c"))),()=>resumeRun(true),null,'repeat');
button(liveLabel(()=>(t("m_06461e7a38ad"))),()=>start('rebuild_memory'),'rebuild_memory');
button(liveLabel(()=>(t("m_e3b0d35990c3"))),async()=>{const runs=(await api(`/api/stories/${state.storyId}/runs`)).runs;if(runs.length)await follow(runs.at(-1))},null,'latest');
button(liveLabel(()=>(t("m_e1cb5a4ec579"))),async()=>{const runs=(await api(`/api/stories/${state.storyId}/runs`)).runs;const run=[...runs].reverse().find(r=>r.request.mode==='prepare'&&r.state==='completed');if(!run)throw new Error(t("m_f23e2e25e089"));const details=await api('/api/runs/'+run.id);const ref=details.attempts.at(-1).result_version_id;const proposal=(await api('/api/versions/'+ref)).text;const editor=document.querySelector('#editor');if(state.dirty)throw new Error(t("m_185b792f5bf8"));loadBuffer(state.scene,'blueprint',proposal);state.dirty=false;uiText(document.querySelector('#current-kind'),"textContent",()=>(t("m_01a4fc472a1d")));document.querySelector('#save-text').disabled=true;updateControls()},null,'proposal');
button(liveLabel(()=>(t("m_d2193b81e0c3"))),async()=>{if(state.mode!=='blueprint')throw new Error(t("m_01a5baeeaa81"));const proposal=JSON.parse(textEditor.read());if(!confirm(t("m_7f8d04e5c78c")))return;await api(`/api/stories/${state.storyId}/blueprint/apply`,json('POST',{proposal,expected_revision:state.view.story.revision}));state.dirty=false;await refresh();notice(msg("m_646d341468c4"))},null,'apply');
loadReadiness();
api(`/api/stories/${state.storyId}/runs`).then(result=>{if(result.runs.length)follow(result.runs.at(-1)).catch(e=>notice(e.message,'error'))}).catch(e=>notice(e.message,'error'));

registerWorkspaceCommand('run',async options=>{try{return await start(options.mode,options.stage,options)}catch(error){document.dispatchEvent(new CustomEvent('workspace-operation-error',{detail:{stage:options.mode==='edit_loop'?'edit':options.stage||options.mode,message:error.message}}));throw error}});
registerWorkspaceCommand('refresh-readiness',loadReadiness);
