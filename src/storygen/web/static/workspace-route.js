import {sceneStatus} from "./workspace-status.js";
import {confirmDialog} from './dialogs.js';
import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {state,textEditor,selectScene,refresh} from './editor.js';
import {api,json,notice} from './api.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {performPrimary,primaryAction} from './workspace-state.js';
import {compactBudgetText} from './workspace-links.js';
import {editorLoopOperation} from './run-readiness.js';

const primary=document.querySelector('#workspace-primary'),hint=document.querySelector('#workspace-hint');
const primaryWrap=document.createElement('span');primaryWrap.className='workspace-primary-wrap';
primary.before(primaryWrap);primaryWrap.append(primary);
const telemetry=document.createElement('small');telemetry.id='workspace-telemetry';
telemetry.tabIndex=0;
const detailsCard=document.createElement('div');detailsCard.id='workspace-telemetry-details';detailsCard.className='workspace-telemetry-details';detailsCard.setAttribute('role','tooltip');
primaryWrap.append(telemetry,detailsCard);primary.setAttribute('aria-describedby','workspace-hint workspace-telemetry workspace-telemetry-details');
const activeKey=()=>`storygen.primary.active.${state.storyId}`;
function activeId(){try{return sessionStorage.getItem(activeKey())}catch{return null}}
function setActiveId(id){try{if(id)sessionStorage.setItem(activeKey(),id);else sessionStorage.removeItem(activeKey())}catch{}}
let busy=false,pending=null,primaryRun=activeId(),primaryController=null,cancelRequested=false;
const activeStates=new Set(['queued','running','pause_requested','cancellation_requested']);
const isActive=()=>activeStates.has(state.workspaceRun?.state)||(state.workspaceRuns||[]).some(run=>activeStates.has(run.state));
function render(){
  const meta=document.querySelector('#workspace-scene-meta');if(meta&&state.scene)uiText(meta,"textContent",()=>(t("m_2424d27e2118",{p0:(state.scene.position+1),p1:(state.view?.scenes.length||'—'),p2:(state.scene.target_words)})));
  const sceneStatusNode=document.querySelector('#workspace-scene-status');if(sceneStatusNode){sceneStatusNode.hidden=!state.scene;if(state.scene)uiText(sceneStatusNode,'textContent',()=>sceneStatus(state.scene,state.view?.impact_status).label)}
  const compact=document.querySelector('#workspace-compact-status');if(compact){const labels={get queued(){return t("m_eb3c78969040")},get running(){return t("m_b4232dd37ccb")},get needs_review(){return t("m_66d1a05343f7")},get completed(){return t("m_016bc923f7ff")},get failed(){return t("m_57467fc4b91f")},get paused(){return t("m_03498e395a43")},get cancelled(){return t("m_84b388351ede")},get alternative(){return t("m_e6d278323734")},get interrupted(){return t("m_54e9f1dc0cc0")}};uiText(compact,"textContent",()=>((labels[state.workspaceRun?.state]||t("m_a6150ea8a568"))+' · '+(compactBudgetText(state.workspaceBudgetData||document.querySelector('.budget-panel')?.budgetData))));}
  const activeRun=activeStates.has(state.workspaceRun?.state)?state.workspaceRun:(state.workspaceRuns||[]).find(run=>activeStates.has(run.state));
  const review=state.mode==='review';
  textEditor.visible(!review&&!state.memoryTableActive);
  const panel=document.querySelector('#copyedit-panel');panel.hidden=!review;
  const details=panel.querySelector('details');if(review&&details)details.open=true;
  const action=primaryAction(state);
  let reason=!state.scene?t("m_f0f1417db6de"):state.saving?t("m_51204171ac66"):busy?t("m_4f6a901d08c4"):isActive()?t("m_9fafcde1c64a"):state.characterDirty?t("m_c2fa0cfd122f"):state.bufferOrigin==='history'?t("m_33cea90c8873"):'';
  if(state.pendingBrief)reason=reason||t('brief.accept_first');
  if(review)reason=reason||(state.reviewAvailability?.ready?'':state.reviewAvailability?.reason||t("m_0dcb6302f894"));
  if(state.mode==='memory')reason=reason||(!state.scene?.heads.memory?t("m_4c7c76c265f9"):state.workspaceMaterials?.memory?.stale?t("m_a304be958559"):'');
  const operation=state.workspaceReadiness?.operations[action.stage||action.mode];
  const modelAction=['plan','brief','draft','prose'].includes(state.mode)&&!!action.mode;
  telemetry.hidden=detailsCard.hidden=!modelAction;
  if(modelAction){
    let info=operation;
    if(info&&action.mode==='edit_loop')try{info=editorLoopOperation(info,Number(document.querySelector('#edit-pass-limit')?.value||5))}catch{info=null}
    const roles=Object.entries(info?.roles||{}),warnings=[...new Set([...(operation?.warnings||[]),operation?.warning].filter(value=>value&&!['Джерело: чернетка.','Джерело: поточна проза.'].includes(value)))];
    const models=roles.map(([role,value])=>`${role}: ${value.provider} / ${value.model}`).join(', ');
    const summary=roles.map(([,value])=>`${value.provider} / ${value.model}`).join(', ');
    uiText(telemetry,'textContent',()=>summary?t('workspace.telemetry',{p0:summary,p1:info.calls})+(warnings.length?' ⚠':''):t('workspace.telemetry_unknown'));
    uiText(detailsCard,'textContent',()=>[t('workspace.model',{p0:models||t('workspace.unknown')}),t('workspace.volume',{p0:info?.calls??'—',p1:t(({plan:'m_3146141c9367',brief:'m_5a2ec5eaf0a1',draft:'m_e9d875d4120b',prose:'m_9c685577453c'})[state.mode])}),...(warnings.length?[t('workspace.warnings',{p0:warnings.map(diagnostic).join('; ')})]:[]),...(state.mode==='draft'?[t('workspace.copy_note')]:[])].join('\n'));
  }
  if(!reason&&!state.dirty&&action.mode)reason=operation?.ready||operation?.can_confirm?'':operation?.reason||t("m_a8900573fc3e");
  const canStop=!!primaryController||!!state.workspacePending||(primaryRun&&activeStates.has(state.workspaceRun?.state)&&state.workspaceRun?.id===primaryRun);
  uiText(primary,"textContent",()=>(canStop?t('workspace.stop'):(primaryAction(state).label||t("m_b31265827ca7"))));primary.disabled=canStop?cancelRequested:!!reason;
  const scenes=state.view?.scenes||[],last=scenes.at(-1)?.id===state.scene?.id;
  if(state.mode==='memory'&&!canStop)uiText(primary,"textContent",()=>(last?t("m_0471f5c4220f"):t("m_58a98c56a879")));
  uiText(hint,"textContent",()=>(diagnostic(reason)||(action.target&&state.scene?.heads[action.target]?t("m_44df09bb6ff6"):state.mode==='review'?t("m_34c3cc998162"):state.mode==='memory'?t("m_e310e34e8865"):t("m_93abd76dba4c"))));
  uiText(primary,"title",()=>(diagnostic(reason)));
  const repeat=document.querySelector('#workspace-edit-prose');repeat.hidden=state.mode!=='prose';repeat.disabled=busy||isActive()||state.saving;
  for(const b of document.querySelectorAll('#mode-tabs button')){
    const mode=b.dataset.mode,head=mode==='review'?'prose':mode;
    const material=state.workspaceMaterials?.[mode];
    let status=mode==='brief'&&state.pendingBrief?t('m_66d1a05343f7'):mode==='review'?(state.reviewAvailability?.pending?t("m_66d1a05343f7"):state.reviewAvailability?.hasChanges?t("m_a8cf00058976"):t("m_421a83bf60b6")):!state.scene?.heads[head]&&!(mode==='plan'&&state.scene?.beats)?t("m_8680be0998f5"):material?.stale?t("m_ac780daa8d8e"):t("m_3ee8deffed11");
    if(activeRun&&mode===(activeRun.request.mode==='edit_loop'?'review':{brief:'brief',draft:'draft',edit:'review',memory:'memory'}[activeRun.request.stage]))status=t("m_af4dd928935c");
    b.setAttribute('aria-selected',String(mode===state.mode&&state.bufferOrigin!=='history'));
    uiAttr(b,'aria-label',()=>(`${({plan:t('m_3146141c9367'),brief:t('m_5a2ec5eaf0a1'),draft:t('m_e9d875d4120b'),review:t('m_c2320838b6df'),prose:t('m_9c685577453c'),memory:t('m_aa1cfb48cc30')})[mode]||b.dataset.label}: ${diagnostic(status)}`));
    let small=b.querySelector('small');if(!small){small=document.createElement('small');b.append(small)}uiText(small,"textContent",()=>(diagnostic(status)));
  }
}
async function nextScene(){
  const scenes=state.view.scenes,index=scenes.findIndex(s=>s.id===state.scene.id);
  if(index<0)throw new Error(t("m_bfe9af0fc8e1"));
  if(index===scenes.length-1){location.assign(`/stories/${encodeURIComponent(state.storyId)}/publication`);return}
  await selectScene(scenes[index+1]);
}
async function launch(options,primaryAction=false){
  const capture={sceneId:state.scene.id,epoch:state.bufferEpoch,mode:state.mode};
  const run=await invokeWorkspaceCommand('run',{...options,primary:primaryAction,signal:primaryAction?primaryController?.signal:undefined,onCreated:primaryAction?async run=>{primaryRun=run.id;setActiveId(run.id);if(cancelRequested)await invokeWorkspaceCommand('cancel-run',run.id)}:undefined});
  if(run){pending={...capture,id:run.id,target:options.mode==='edit_loop'?'review':options.stage};await complete(run)}
  return run;
}
async function complete(run){
  if(!pending||pending.id!==run.id||!['completed','needs_review','alternative'].includes(run.state))return;
  const captured=pending;pending=null;
  if(run.editor_loop?.no_change_prose_version_id)captured.target='prose';
  await refresh();
  if(state.scene?.id===captured.sceneId&&state.mode===captured.mode&&!state.dirty&&!state.saving&&state.bufferOrigin!=='history'){
    // The material loader may have refreshed the same completed head; never replace newer typing.
    if(state.bufferEpoch===captured.epoch||state.mode===captured.target)await invokeWorkspaceCommand('show',captured.target);
  }
}
primary.onclick=async()=>{
  if(primaryController||state.workspacePending||primaryRun&&activeStates.has(state.workspaceRun?.state)&&state.workspaceRun?.id===primaryRun){
    cancelRequested=true;primaryController?.abort();render();
    if(state.workspacePending)try{await invokeWorkspaceCommand('cancel-pending')}catch(error){notice(error.message,'error');cancelRequested=false;render()}
    else if(primaryRun)try{await invokeWorkspaceCommand('cancel-run',primaryRun)}catch(error){notice(error.message,'error');cancelRequested=false;render()}
    return;
  }
  if(busy||primary.disabled)return;busy=true;render();
  primaryController=primaryAction(state).mode?new AbortController():null;cancelRequested=false;render();
  try{await performPrimary({state,save:async()=>{await invokeWorkspaceCommand('save');if(primaryController?.signal.aborted)throw new DOMException('Cancelled','AbortError')},run:options=>launch(options,true),
    show:mode=>invokeWorkspaceCommand('show',mode),accept:()=>invokeWorkspaceCommand('accept-review'),next:nextScene})}
  catch(error){if(error.name!=='AbortError')notice(error.message,'error')}finally{busy=false;primaryController=null;if(!primaryRun)cancelRequested=false;render()}
};
document.querySelector('#workspace-edit-prose').onclick=async()=>{
  if(busy)return;busy=true;render();
  const capture={id:state.scene?.id,epoch:state.bufferEpoch,mode:state.mode};
  try{
    if(state.dirty)await invokeWorkspaceCommand('save');
    if(state.dirty||state.saving||state.mode!=='prose'||state.scene?.id!==capture.id||state.bufferEpoch!==capture.epoch)throw new Error(t("m_6bb9c3d53d83"));
    await launch({mode:'edit_loop',editor_source_head:'prose',editor_source_version_id:state.scene.heads.prose});
  }catch(error){notice(error.message,'error')}finally{busy=false;render()}
};
document.querySelector('#workspace-use-draft').onclick=async()=>{
  if(state.dirty||state.saving||busy||isActive())return;
  const scene=state.scene,id=scene?.heads.draft,epoch=state.bufferEpoch;
  if(!id){notice(msg("m_a5921f6925b0"),'warning');return}
  if(!await confirmDialog(t("m_05e4fd1b757f")))return;
  busy=true;render();
  try{const source=await api('/api/versions/'+id);
    if(state.scene?.id!==scene.id||state.bufferEpoch!==epoch||state.dirty)throw new Error(t("m_7d8d43f3fed7"));
    await api(`/api/scenes/${scene.id}/prose`,json('POST',{text:source.text,expected_revision:scene.revision}));await refresh();await invokeWorkspaceCommand('show','prose');
  }catch(error){notice(error.message,'error')}finally{busy=false;render()}
};
for(const event of ['editor-state-changed','scene-selected','story-refreshed','workspace-readiness','workspace-review-state','workspace-statistics','brief-review-state','workspace-pending-state'])document.addEventListener(event,render);
document.addEventListener('input',event=>{if(event.target?.id==='edit-pass-limit')render()});
document.addEventListener('workspace-run-pending',()=>render());
document.addEventListener('workspace-run-state',event=>{if(event.detail.id===primaryRun&&!activeStates.has(event.detail.state)){primaryRun=null;setActiveId(null);cancelRequested=false}render();void complete(event.detail).catch(e=>notice(e.message,'error'))});
document.addEventListener('workspace-primary-recovered',event=>{if(activeStates.has(event.detail.state)){primaryRun=event.detail.id;setActiveId(primaryRun)}render()});
document.addEventListener('workspace-budget-updated',event=>{state.workspaceBudgetData=event.detail;render()});
render();
