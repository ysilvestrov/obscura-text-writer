import {externalOriginLabel} from './external-origin.js';
import {confirmDialog} from './dialogs.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {acceptanceReason,openAcceptance,closeAcceptancePreview} from './acceptance.js';
import {api,json,notice} from './api.js';
import {state,textEditor,refresh,saveBuffer,loadBuffer} from './editor.js';
import {renderLanguageWarnings} from './copyedits.js';
import {installMemoryTable} from './memory-table.js';
import {confirmUnsaved} from './core-review.js';
import {registerWorkspaceCommand} from './workspace-commands.js';
import {loadBriefMaterial} from './brief-material.js';
import {activateStageTab,revealStageTab,setStageTabStops} from './workspace-tabs.js';
import {ghostStatsText} from './ghost-session.js';
import {newerScene,ghostOpen,cleanBuffer,externalNotice} from './scene-sync.js';
import {liveScene} from './workspace-status.js';
const memoryTable=installMemoryTable({state,api,json,notice,refresh,loadBuffer});
const editor=document.querySelector('#editor');
const labels={get plan(){return t("m_3146141c9367")},get brief(){return t("m_5a2ec5eaf0a1")},get draft(){return t("m_e9d875d4120b")},get review(){return t("m_c2320838b6df")},get prose(){return t("m_9c685577453c")},get memory(){return t("m_aa1cfb48cc30")}};
let versions=[],updateHistoryControls=()=>{};
document.addEventListener('editor-state-changed',()=>updateHistoryControls());
function updateTabs(){
  const buttons=[...document.querySelectorAll('#mode-tabs button')];
  for(const button of buttons){
    const active=button.dataset.mode===state.mode&&state.bufferOrigin!=='history';
    button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));activateStageTab(button,active);
  }
  setStageTabStops(buttons,state.mode);
}
document.addEventListener('editor-state-changed',updateTabs);
globalThis.addEventListener?.('resize',()=>{const active=document.querySelector('#mode-tabs [aria-selected="true"]');if(active)revealStageTab(active)});
async function show(mode,onlyIfChanged=false){
  if(state.saving)throw new Error(t("m_cbac60d6d919"));
  const before={id:state.scene?.id,epoch:state.bufferEpoch,mode:state.mode};
  if(!await confirmUnsaved(state,confirmDialog,t("m_768dad0572f4")))return;
  if(state.saving||state.scene?.id!==before.id||state.bufferEpoch!==before.epoch||state.mode!==before.mode)return;
  // #105: the brief loader may already have put a newer scene into the buffer than the loaded view holds.
  let scene=newerScene(state.view.scenes.find(s=>s.id===state.scene.id),state.scene);
  const epoch=state.bufferEpoch;
  let material;
  if(mode==='brief'){const result=await loadBriefMaterial(api,scene);scene=result.scene;material=result.material;}
  else material=!['review','plan'].includes(mode)&&scene.heads[mode]?await api('/api/versions/'+scene.heads[mode]):null;
  const text=mode==='review'?'':mode==='plan'?scene.beats:material?.text||'';
  if(epoch!==state.bufferEpoch)return;
  if(onlyIfChanged&&textEditor.identity().version_id===(material?.version.id??null))return;
  loadBuffer(scene,mode,text,'current',material?.version);
  uiText(document.querySelector('#current-kind'),"textContent",()=>(labels[mode].toUpperCase()));
  uiText(document.querySelector('#save-state'),"textContent",()=>(scene.heads[mode]?t("m_4fc1598084c2"):''));
}
registerWorkspaceCommand('show',show);
document.querySelector('#mode-tabs').addEventListener('keydown',async event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const buttons=[...document.querySelectorAll('#mode-tabs button')],index=buttons.indexOf(event.target);
  if(index<0)return;event.preventDefault();
  const next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(index+(event.key==='ArrowRight'?1:-1)+buttons.length)%buttons.length;
  try{await show(buttons[next].dataset.mode);if(state.mode===buttons[next].dataset.mode)document.querySelector(`#mode-tabs [data-mode="${state.mode}"]`)?.focus?.()}
  catch(error){notice(error.message,'error')}
});
registerWorkspaceCommand('save-material',async()=>{
  if(externalNotice(state)==='gone')throw new Error(t('sync.trashed'));
  if(memoryTable.active()){await memoryTable.save();if(state.dirty)throw new Error(t("m_e4eb188e3a6b"));return;}
  if(!['draft','prose','memory','brief'].includes(state.mode))throw new Error(t("m_9910fb588c99"));
  return saveBuffer(snapshot=>api(`/api/scenes/${snapshot.scene.id}/${snapshot.mode}`,json('POST',{text:snapshot.text,expected_revision:snapshot.scene.revision,...(snapshot.mode==='brief'?{source_brief_id:snapshot.source_version_id||null}:{}),...(['draft','prose'].includes(snapshot.mode)&&snapshot.content_format==='markdown'?{content_format:snapshot.content_format}:{}),...(snapshot.authoringFields||{})})));
});
async function render(){
  if(!state.scene)return;
  closeAcceptancePreview();
  const tabs=document.querySelector('#mode-tabs');tabs.replaceChildren();
  for(const [mode,label] of labelEntries(labels)){const button=document.createElement('button');button.className='secondary';button.dataset.mode=mode;button.dataset.label=label;uiText(button,"textContent",()=>(label));button.setAttribute('role','tab');button.onclick=()=>show(mode).catch(e=>notice(e.message,'error'));tabs.append(button)}
  updateTabs();
  const data=await api('/api/scenes/'+state.scene.id+'/versions');versions=data.versions;
  state.workspaceMaterials=Object.fromEntries(['plan','brief','draft','prose','memory'].map(kind=>[kind,versions.find(v=>v.id===liveScene(state.scene,state.view?.scenes).heads[kind])]));
  document.dispatchEvent(new CustomEvent('workspace-statistics'));
  const panel=document.querySelector('#version-panel');panel.replaceChildren();
  const title=document.createElement('h3');uiText(title,"textContent",()=>(t("m_ffb1638b3e7d")));panel.append(title);
  const list=document.createElement('select');list.id='history-version';uiAttr(list,'aria-label',()=>(t("m_f96dd4fff344")));
  for(const ref of [...versions].reverse()){const opt=document.createElement('option');opt.value=ref.id;uiText(opt,"textContent",()=>(`${ref.kind} · ${ref.created_at.slice(0,19)}${ref.stale?t("m_e9ed25b34a92"):''}${data.acceptances?.some(a=>a.version_id===ref.id)?t("m_96a5e12eeb4f"):''}${externalOriginLabel(ref)?' · '+externalOriginLabel(ref):''}`));list.append(opt)}
  const ghostStats=document.createElement('p');ghostStats.className='muted history-ghost-stats';
  panel.append(list,ghostStats);
  const historyActions=[];
  function updateHistory(){const ref=versions.find(v=>v.id===list.value);ghostStats.hidden=!ref?.ghost_rewrite;uiText(ghostStats,'textContent',()=>ghostStatsText(ref?.ghost_rewrite,t));for(const [b,kind]of historyActions){let reason=kind==='review-acceptance'?acceptanceReason(state,ref):!ref?t("m_718d25e12548"):state.saving?t("m_1322882bbef7"):kind==='select'&&(ref.stale||!ref.complete||!['edited','manual'].includes(ref.kind))?t("m_63721412ce4c"):kind==='accept'&&(ref.stale||!ref.complete||ref.kind!=='brief')?t("m_90486d14b4ce"):kind==='accept-draft'&&(ref.stale||!ref.complete||ref.kind!=='draft')?t("m_38422659d255"):kind==='language'&&(!['draft','edited','manual'].includes(ref.kind)||state.dirty)?t("m_a2fd74d27993"):kind==='compare'&&!state.scene?.heads.draft?t("m_446a5894c84d"):(['select','accept','accept-draft'].includes(kind)&&state.dirty)?t("m_185b792f5bf8"):'';b.disabled=!!reason;uiText(b,"title",()=>(diagnostic(reason)))}}
  list.onchange=updateHistory;updateHistoryControls=updateHistory;
  function action(label,handler,kind='view'){const b=document.createElement('button');b.className='secondary';uiText(b,"textContent",()=>(label));b.onclick=()=>handler().catch(e=>notice(e.message,'error'));historyActions.push([b,kind]);panel.append(b)}
  action(live(()=>(t("m_08ba5037418f"))),async()=>{if(state.saving)throw new Error(t("m_1322882bbef7"));const epoch=state.bufferEpoch,sceneId=state.scene?.id,previousMode=state.mode;if(!await confirmUnsaved(state,confirmDialog,t("m_1ab822828660")))return;if(state.saving||epoch!==state.bufferEpoch||sceneId!==state.scene?.id||previousMode!==state.mode)return;const v=await api('/api/versions/'+list.value);if(epoch!==state.bufferEpoch)return;const mode=v.version.kind==='memory'?'memory':v.version.kind==='brief'?'brief':v.version.kind==='scene_plan'?'plan':v.version.kind==='draft'?'draft':['edited','manual'].includes(v.version.kind)?'prose':'history';loadBuffer(state.scene,mode,v.text,'history',v.version);uiText(document.querySelector('#current-kind'),"textContent",()=>(t("m_19f94fbf1144")+v.version.kind))});
  const languageResult=document.createElement('section');languageResult.className='language-warnings';
  action(live(()=>(t("m_1ccbf3066eb3"))),async()=>{const ref=versions.find(v=>v.id===list.value);if(!ref||!['draft','edited','manual'].includes(ref.kind))throw new Error(t("m_83a9f717472d"));const id=ref.id;const result=await api(`/api/versions/${id}/language-warnings`);if(list.value!==id||!panel.contains(languageResult))return;renderLanguageWarnings(languageResult,result)},'language');
  panel.append(languageResult);
  action(live(()=>(t("m_72466c583aa4"))),async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/select-version`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('prose')},'select');
  action(live(()=>(t("m_26986720d655"))),async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/accept-brief`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('brief')},'accept');
  action(live(()=>(t("m_7d977f912681"))),async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/accept-draft`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('draft');notice(msg("m_ad04877c6fbd"))},'accept-draft');
  action(live(()=>(t("m_afa512a5ae9c"))),async()=>{
    const ref=versions.find(v=>v.id===list.value);
    await openAcceptance({state,ref,api,json,panel,notice,onAccepted:async(result,captured)=>{
      if(state.scene?.id===captured.sceneId&&!state.dirty&&!state.saving&&state.bufferEpoch===captured.epoch){state.scene=result.scene;await refresh();await show(ref.kind==='draft'?'draft':'prose')}
      else await refresh();
    }});
  },'review-acceptance');
  action(live(()=>(t("m_906d72c0ae4f"))),async()=>{if(!state.scene.heads.draft)throw new Error(t("m_446a5894c84d"));const pair=await api(`/api/versions/compare?left=${state.scene.heads.draft}&right=${list.value}`);const container=document.createElement('div');container.className='comparison';for(const text of [pair.left,pair.right,pair.diff]){const pre=document.createElement('pre');uiText(pre,"textContent",()=>(text));container.append(pre)}panel.append(container)},'compare');
  updateHistory();
}
document.addEventListener('scene-selected',()=>render().catch(e=>notice(e.message,'error')));
document.addEventListener('story-refreshed',async()=>{
  try{
    const latest=state.view.scenes.find(s=>s.id===state.scene?.id);
    // An open rewrite from memory works over the loaded draft; replacing it underneath would break that session.
    if(state.mode==='brief'&&!state.dirty&&!state.saving&&!ghostOpen()&&state.bufferOrigin!=='history')await show('brief',true);
    else if(['draft','prose','memory'].includes(state.mode)&&!state.dirty&&!state.saving&&!ghostOpen()&&state.bufferOrigin!=='history'&&latest?.heads[state.mode]&&latest.heads[state.mode]!==state.scene?.heads[state.mode])await show(state.mode);
    // #105: after a change made elsewhere a clean buffer is reloaded in every material, even when only another material moved.
    if(state.externalChange&&cleanBuffer(state,ghostOpen())&&['plan','brief','draft','review','prose','memory'].includes(state.mode)&&latest&&latest.revision!==state.scene?.revision)await show(state.mode);
    await render();
  }catch(e){notice(e.message,'error')}
});
document.addEventListener('save-prose',async()=>{try{
  if(externalNotice(state)==='gone')throw new Error(t('sync.trashed'));
  if(memoryTable.active()){await memoryTable.save();return;}
  if(!['draft','prose','memory','brief'].includes(state.mode))throw new Error(t("m_f89ef6f89e8a"));
  const result=await saveBuffer(snapshot=>api(`/api/scenes/${snapshot.scene.id}/${snapshot.mode==='prose'?'prose':snapshot.mode}`,json('POST',{text:snapshot.text,expected_revision:snapshot.scene.revision,...(snapshot.mode==='brief'?{source_brief_id:snapshot.source_version_id||null}:{}),...(['draft','prose'].includes(snapshot.mode)&&snapshot.content_format==='markdown'?{content_format:snapshot.content_format}:{}),...(snapshot.authoringFields||{})})));
  if(result)notice(result.needs_review?t("m_bb5c7d2fc991"):t("m_47d7dedd8913"));
}catch(e){notice(e.message,'error')}});
