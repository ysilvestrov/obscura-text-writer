import {t,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {sceneConsistency} from './link-actions.js';
import {operationReason} from './run-readiness.js';
import {panelBookRun,revealBlocked} from './book-validation-state.js';
import {settingsLink} from './workspace-links.js';
// VALID-LINKS-S15: the «Узгодженість сцени» panel of the open scene. The rows and the main action come from
// link-actions.js::sceneConsistency; the panel reads the story view's material_status and, for «Перевірити Ревізором»,
// the scene's audit preview (calls and the upper bound on cost). The server checks the fingerprint of every approval,
// so a stale panel gets 409 and refreshes.
const host=document.querySelector('#scene-consistency');
const ACTIVE_RUN=new Set(['queued','running','pause_requested','cancellation_requested']);
const CARRY_POLL_MS=3000,CARRY_POLLS=40;
let busy=false,carryTimer=null,carryPolls=0;
// Г7: the preview is read once per scene and state of its links; a refresh that leaves the links as they were reuses it.
let previewKeyValue=null,previewValue=null;
// Task 3: the full book validation run (the run line may hold a short list entry of it) for «Продовжити валідацію».
let bookRun=null;
const isBook=run=>run?.request?.mode==='audit'&&run.request.audit_scope==='story';
const currentRun=()=>panelBookRun(bookRun,state.workspaceRuns,state.workspaceRun);

// Why the main action cannot run now: unsaved edits and the like, another active run, a request of this panel.
export function blockedReason(){
  return operationReason(state,{ready:true})||(ACTIVE_RUN.has(state.workspaceRun?.state)?t('m_506ce9f6bdfa'):'')||(busy?t('m_08ee1e43995d'):'');
}
function previewKey(){
  const sceneId=state.scene?.id;
  if(!sceneId)return null;
  const links=state.view?.material_status?.[sceneId]?.links||{};
  return [sceneId,...['brief','prose','memory'].map(link=>`${link}:${links[link]?.status??''}:${links[link]?.fingerprint??''}`)].join('|');
}
const previewFor=key=>key!==null&&key===previewKeyValue?previewValue:null;
async function loadPreview(key,sceneId){
  previewKeyValue=key;previewValue=null;
  let result;
  try{result=await api(`/api/stories/${state.storyId}/audit/preview`,json('POST',{scope:'scene',scene_id:sceneId}))}
  catch(error){result={ready:false,reason:error.message,failed:true}}  // M3: read again on the next refresh
  // Review Focus 2: a late answer for another scene or another state of the links is dropped.
  if(previewKey()!==key||previewKeyValue!==key)return;
  previewValue=result;render();
}

const label=(element,value)=>uiText(element,'textContent',()=>value?(value.text!==undefined?diagnostic(value.text):t(value.key,value.params)):'');
function actionButton(action,focusKey){
  const button=document.createElement('button');button.type='button';button.className='link-button';button.disabled=busy;
  button.dataset.focusKey=focusKey;
  uiText(button,'textContent',()=>t(action.label));
  button.onclick=()=>{
    // Review Focus 4: the focus waits on the panel while the row redraws (as runs.js keeps it on the run row).
    host.focus({preventScroll:true});
    void(action.type==='approve'?decide(action):action.type==='carry'?carry(action)
      :action.type==='settings'?openSettings()
      :createMemory(action.sceneId,action.type==='rebuild'?{mode:'rebuild_memory'}:{mode:'stage',stage:'memory'}));
  };
  return button;
}
function renderRow(row){
  const li=document.createElement('li');li.dataset.link=row.link;li.dataset.state=row.state;
  const icon=document.createElement('span');icon.className='consistency-icon';icon.setAttribute('aria-hidden','true');icon.textContent=row.icon;
  const body=document.createElement('div');body.className='consistency-body';
  const title=document.createElement('span');title.className='consistency-title';uiText(title,'textContent',()=>t(row.title));
  body.append(title);
  if(row.state==='discrepancy'){
    // The summary, items and quotes are the model's words, shown as is.
    const block=document.createElement('div');block.className='consistency-discrepancy';
    const status=document.createElement('p');status.className='consistency-status';label(status,row.status);block.append(status);
    if(row.summary){const summary=document.createElement('p');summary.className='muted link-audit-summary';summary.textContent=row.summary;block.append(summary)}
    if(row.discrepancies?.length){
      const list=document.createElement('ul');list.className='link-discrepancies';
      for(const entry of row.discrepancies){
        const item=document.createElement('li');item.className='link-discrepancy';
        const what=document.createElement('span');what.textContent=entry.text;item.append(what);
        if(entry.quote){const quote=document.createElement('blockquote');quote.textContent=entry.quote;item.append(quote)}
        list.append(item);
      }
      block.append(list);
    }
    const hint=document.createElement('p');hint.className='muted consistency-hint';uiText(hint,'textContent',()=>t('consistency.discrepancy_hint'));
    block.append(hint);body.append(block);
  }else{
    const status=document.createElement('span');status.className='consistency-status muted';
    // The auditor's own reason is a server text (translated).
    if(row.reason!==undefined)uiText(status,'textContent',()=>t(row.status.key,{...row.status.params,p0:diagnostic(row.reason)}));
    else label(status,row.status);
    body.append(status);
  }
  li.append(icon,body);
  if(row.actions.length){
    const actions=document.createElement('span');actions.className='consistency-actions';
    row.actions.forEach((action,index)=>actions.append(actionButton(action,`${row.link}:${index}`)));
    li.append(actions);
  }
  return li;
}
function renderPrimary(primary){
  const wrap=document.createElement('p');wrap.className='consistency-primary';
  const button=document.createElement('button');button.id='scene-consistency-primary';button.type='button';
  button.dataset.focusKey='primary';
  button.setAttribute('aria-describedby','scene-consistency-reason');
  const cost=document.createElement('small');cost.className='consistency-cost muted';
  // The reason is the panel's only live text: it changes when an edit, a run or the preview blocks the action.
  const reason=document.createElement('small');reason.id='scene-consistency-reason';reason.className='consistency-reason muted';
  reason.setAttribute('aria-live','polite');
  wrap.append(button,' ',cost,' ',reason);
  updatePrimary(wrap,primary);
  return wrap;
}
// The main action follows the editor, the runs and the preview in place: typing never rebuilds the rows (I1).
function updatePrimary(wrap,primary){
  const button=wrap.querySelector('#scene-consistency-primary'),cost=wrap.querySelector('.consistency-cost'),reason=wrap.querySelector('#scene-consistency-reason');
  button.disabled=busy||primary.disabled;
  uiText(button,'textContent',()=>t(primary.label));
  button.onclick=()=>{if(primary.action==='audit')void audit();else if(primary.action==='resume'){const run=currentRun();if(run)void resume(run)}};
  label(cost,primary.detail);cost.hidden=!primary.detail;
  label(reason,primary.reason);reason.hidden=!primary.reason;
}
let shown=null;
function render(){
  if(!host)return;
  const key=previewKey();
  const run=currentRun();
  const panel=state.scene?sceneConsistency(state.view?.material_status,state.scene.id,state.view?.scenes||[],run,previewFor(key),
    run&&revealBlocked(state.workspaceRun,run)?t('book_validation.other_run_active'):blockedReason()):null;
  // Only the main action changed (an edit, a run, the preview): update it in place and keep the rows and the focus.
  const signature=panel&&JSON.stringify([state.scene.id,busy,panel.view,panel.pendingCount,panel.total,panel.rows,panel.primary.action,run?.id,run?.state]);
  const wrap=host.querySelector('.consistency-primary');
  if(signature&&signature===shown&&(panel.view!=='full'||wrap)){
    if(panel.view==='full'){
      updatePrimary(wrap,panel.primary);
      if(!panel.resume&&key!==previewKeyValue)void loadPreview(key,state.scene.id);
    }
    scheduleCarry(panel);
    return;
  }
  shown=signature;
  // Review Focus 4: a focused control of the panel keeps the focus across the redraw.
  const active=document.activeElement;
  const focusKey=host.contains(active)?(active===host?'host':active.dataset?.focusKey||'host'):null;
  host.replaceChildren();
  host.hidden=!panel||panel.view==='none';
  if(panel?.view==='valid'){
    const valid=document.createElement('p');valid.className='consistency-valid';valid.id='scene-consistency-title';uiText(valid,'textContent',()=>t('consistency.valid'));
    host.append(valid);
  }else if(panel?.view==='full'){
    const head=document.createElement('div');head.className='consistency-head';
    const title=document.createElement('h3');title.id='scene-consistency-title';uiText(title,'textContent',()=>t('consistency.title'));
    const badge=document.createElement('span');badge.className='consistency-badge';badge.hidden=!panel.pendingCount;
    uiText(badge,'textContent',()=>t('consistency.pending_count',{p0:panel.pendingCount,p1:panel.total}));
    head.append(title,badge);
    const list=document.createElement('ul');list.className='consistency-rows';
    for(const row of panel.rows)list.append(renderRow(row));
    host.append(head,list,renderPrimary(panel.primary));
    if(!panel.resume&&key!==previewKeyValue)void loadPreview(key,state.scene.id);
  }
  if(focusKey){
    const target=focusKey==='host'?null:host.querySelector(`[data-focus-key="${focusKey}"]`);
    // M2: a panel that hid itself hands the focus to the status row (as openStopScene does), never to the page.
    const row=document.querySelector('#workspace-status-row');
    if(host.hidden&&row&&!row.hasAttribute('tabindex'))row.tabIndex=-1;
    (host.hidden?row:target&&!target.disabled?target:host)?.focus({preventScroll:true});
  }
  scheduleCarry(panel);
}
// MEMORY-CARRY: the carry runs in the background without a followed run; the view is read again until it reaches
// this scene, so «Пам’ять переноситься…» clears by itself. A paused or failed carry keeps the scene pending, so the
// polling stops after about two minutes per opened scene (the next refresh or scene switch shows the state again).
function scheduleCarry(panel){
  clearTimeout(carryTimer);carryTimer=null;
  const pending=!!panel?.rows.some(row=>row.link==='memory'&&row.status?.key==='link.carry_pending');
  if(!pending)carryPolls=0;
  else if(carryPolls<CARRY_POLLS)carryTimer=setTimeout(()=>{
    carryTimer=null;carryPolls++;
    if(!busy&&!state.dirty&&!state.saving)refresh({fresh:true}).catch(()=>{}).finally(render);else render();
  },CARRY_POLL_MS);
}
// VALID-LINKS: «Перевірити Ревізором» runs the auditor through the usual preview and consent; the run stops on a link
// that needs the author's decision.
async function audit(){
  if(busy)return;
  try{await invokeWorkspaceCommand('run',{mode:'audit',audit_scope:'scene'})}
  catch(error){if(error.name!=='AbortError')notice(error.message,'error')}
}
async function resume(run){
  if(busy)return;
  try{await invokeWorkspaceCommand('resume-run',run)}
  catch(error){if(error.name!=='AbortError')notice(error.message,'error')}
}
async function decide(action){
  if(busy)return;
  busy=true;render();
  try{
    await api(`/api/scenes/${state.scene.id}/links/${action.link}/decision`,json('POST',{action:'approve',fingerprint:action.fingerprint}));
    notice(t('link.approved'),'success');
  }catch(error){notice(error.message,'error')}
  finally{busy=false;await refresh();render()}
}
// The auditor's settings, with the same guard as the settings link of a failed run: unsaved text stays in the editor.
function openSettings(){
  const href=state.scene&&settingsLink(state.storyId,state.scene.id,state.mode,'auditor');
  if(!href)return;
  if(state.dirty||state.saving){document.dispatchEvent(new CustomEvent('workspace-navigation-blocked'));notice(t('m_df05df152938'),'warning');return}
  location.href=href;
}
// MEMORY-CARRY: a stalled carry is resumed (no model, no cost) or cancelled; the scenes it covers stop waiting either way.
async function carry(action){
  if(busy)return;
  busy=true;render();
  try{
    await api(`/api/runs/${action.runId}/${action.command}`,json('POST',action.command==='resume'?{repeat_interrupted:true}:{}));
  }catch(error){notice(error.message,'error')}
  finally{busy=false;carryPolls=0;await refresh();render()}
}
// The memory stage (or «Перебудувати пам’ять») of the named scene through the usual run preview and consent. The run
// command works on the open scene, so another scene (the previous one) is opened first; a cancelled switch (unsaved
// text) launches nothing.
async function createMemory(sceneId,options){
  if(busy)return;
  try{
    if(state.scene?.id!==sceneId){
      const target=state.view?.scenes?.find(scene=>scene.id===sceneId);
      if(!target)return;
      await selectScene(target);
      if(state.scene?.id!==sceneId)return;
    }
    await invokeWorkspaceCommand('run',options);
  }catch(error){if(error.name!=='AbortError')notice(error.message,'error')}
}
if(host)document.addEventListener('story-refreshed',()=>{if(previewValue?.failed){previewKeyValue=null;previewValue=null}render()});
// Registered before the render listener so a render sees the run it was told about.
document.addEventListener('workspace-run-state',event=>{if(isBook(event.detail))bookRun=event.detail});
if(host)for(const event of ['workspace-run-state','workspace-run-pending','workspace-readiness','editor-state-changed'])document.addEventListener(event,render);
document.addEventListener('scene-selected',()=>{carryPolls=0;previewKeyValue=null;previewValue=null;render()});
render();
