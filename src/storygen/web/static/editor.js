import {externalOriginLabel} from './external-origin.js';
import {confirmDialog,promptDialog} from './dialogs.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {api,json,notice} from './api.js';
import {renderImportJournal} from './import-journal.js';
import {sceneStatus} from './workspace-status.js';
import {renderImportResults,showImportPending,showImportRefreshWarning} from './import-results.js';
import {installSceneTrash} from './trash.js';
import {createTextEditor} from './text-editor.js';
import {confirmUnsaved} from './core-review.js';
import {readWorkspacePosition,rememberWorkspacePosition,resolveWorkspacePosition,updateWorkspaceUrl} from './workspace-position.js';
import {registerWorkspaceCommand,invokeWorkspaceCommand} from './workspace-commands.js';

export const state={storyId:document.querySelector('#workspace')?.dataset.storyId,scene:null,view:null,mode:'plan',dirty:false,saving:false,bufferEpoch:0};
export const initialWorkspacePosition=readWorkspacePosition(state.storyId,globalThis.location?.search||'');
let authorComments=null;
export function registerAuthorComments(controller){authorComments=controller;}
export const getAuthorComments=()=>authorComments;
const editor=document.querySelector('#editor');
export const textEditor=createTextEditor(editor);
const placeholders={
  get plan(){return t("m_af47cedafa12")},
  get brief(){return t("m_d5bd1ca9098e")},
  get draft(){return t("m_f7662a3cd77a")},
  get prose(){return t("m_e7390f027430")},
  get memory(){return t("m_b17c1fbe1061")}
};
const saveButton=document.querySelector('#save-text');
const changed=()=>document.dispatchEvent(new CustomEvent('editor-state-changed'));

// Presentation only: never rewrite the title in storage or the editor buffer.
export function displaySceneTitle(title){
  return title.replace(/^\s*#{1,6}\s+/, '').replace(/\*\*|__/g, '').trim();
}

// MCP-BRIDGE: the status row names the external client of the version in the buffer; an author save replaces the ref.
function renderOrigin(ref){const node=document.querySelector('#workspace-origin');if(node){node.hidden=!externalOriginLabel(ref);uiText(node,'textContent',()=>externalOriginLabel(ref))}}
export function loadBuffer(scene,mode,text,origin='current',ref=null){
  textEditor.write(text,{material:mode,content_format:ref?.content_format||'plain',version_id:ref?.id,source_ref:ref});
  state.scene=scene;state.mode=mode;state.dirty=false;state.bufferEpoch++;
  if(origin==='current'&&['plan','brief','draft','review','prose','memory'].includes(mode)){
    const position={scene_id:scene.id,material:mode};rememberWorkspacePosition(state.storyId,position);updateWorkspaceUrl(position);
  }
    state.bufferOrigin=origin;
  renderOrigin(ref);
  textEditor.placeholder(live(()=>placeholders[mode]||''));
  textEditor.readOnly(origin==='history'||['review','blueprint'].includes(mode));
  uiText(document.querySelector('#save-state'),"textContent",()=>(t("m_4fc1598084c2")));
  saveButton.disabled=['history','blueprint','review'].includes(mode);changed();
}

export async function saveBuffer(send){
  if(state.saving)return null;
  if(!state.scene)throw new Error(t("m_f0f1417db6de"));
  const material=textEditor.snapshot();
  const authoring=state.mode==='draft'&&state.bufferOrigin!=='history'?authorComments:null;
  const authoringFields=authoring?.capture();
  const snapshot={scene:state.scene,mode:state.mode,text:material.source,content_format:material.content_format,source_version_id:material.version_id,authoringFields};
  authoring?.lock(true);
  state.saving=true;saveButton.disabled=true;changed();
  try{
    const result=await send(snapshot);
    if(state.scene?.id===snapshot.scene.id&&state.mode===snapshot.mode){
      state.scene=result.scene||result;
      const current=textEditor.snapshot();
      state.dirty=current.source!==snapshot.text||current.content_format!==snapshot.content_format;
      const savedAcceptedBrief=snapshot.mode==='brief'&&!result.needs_review&&result.version?.id&&
        result.scene?.heads?.brief===result.version.id&&textEditor.identity().version_id===snapshot.source_version_id;
      if(!state.dirty||savedAcceptedBrief)textEditor.markSaved({...material,version_id:result.version?.id,source_ref:result.version});
      renderOrigin(result.version);
      authoring?.saved(result);
      state.dirty=state.dirty||!!authoring?.isDirty();
      uiText(document.querySelector('#save-state'),"textContent",()=>(state.dirty?t("m_5da9339e255c"):t("m_7f00ac2a170a")));
    }
    await refresh();
    return result;
  }finally{
    state.saving=false;authoring?.lock(false);saveButton.disabled=['history','blueprint','review'].includes(state.mode);changed();
  }
}

export async function refresh(options){
  state.view=await api('/api/stories/'+state.storyId,options?.fresh===true?{fresh:true}:undefined);
  // The loaded buffer keeps its own revision until text and revision are explicitly reloaded together.
  const latest=state.view.scenes.find(s=>s.id===state.scene?.id);
  if(state.scene)uiText(document.querySelector('#scene-title'),"textContent",()=>(displaySceneTitle(state.scene.title)));
  if(latest&&latest.revision!==state.scene.revision&&!state.dirty)uiText(document.querySelector('#save-state'),"textContent",()=>(t("m_51e65512078d")));
  const list=document.querySelector('#scene-list');list.replaceChildren();
  uiText(document.querySelector('#scene-count'),"textContent",()=>(state.view.scenes.length));
  const picker=document.querySelector('#scene-select-mobile');
  if(picker){picker.replaceChildren();for(const scene of state.view.scenes){const option=document.createElement('option');option.value=scene.id;uiText(option,"textContent",()=>((scene.position+1)+'. '+displaySceneTitle(scene.title)));picker.append(option)}picker.value=state.scene?.id||'';picker.onchange=()=>{const scene=state.view.scenes.find(s=>s.id===picker.value);if(scene)void selectScene(scene)}}
  for(const scene of state.view.scenes){
    const button=document.createElement('button');button.className='scene-item'+(state.scene?.id===scene.id?' active':'');uiText(button,"textContent",()=>((scene.position+1)+'. '+displaySceneTitle(scene.title)));
    button.setAttribute('aria-current',state.scene?.id===scene.id?'true':'false');
    const small=document.createElement('small');uiText(small,"textContent",()=>sceneStatus(scene,state.view.impact_status).label);button.append(small);button.onclick=()=>selectScene(scene);list.append(button);
  }
  if(!state.scene&&state.view.scenes.length)await selectScene(resolveWorkspacePosition(state.view.scenes,initialWorkspacePosition).scene);
  renderImportJournal(document.querySelector('#import-journal')||document.querySelector('#context-content'),state.view.source_files||[],state.view.active_sources||{});
  const importer=document.querySelector('.importer');if(importer&&!importer.dataset.userOpened)importer.open=!(state.view.source_files?.length||state.view.sources?.length)&&state.view.scenes.length===0;
  document.dispatchEvent(new CustomEvent('story-refreshed'));
}

export async function selectScene(scene){
  if(state.saving){notice(msg("m_cbac60d6d919"));return}
  const captured={id:state.scene?.id,epoch:state.bufferEpoch,mode:state.mode};
  if(!await confirmUnsaved(state,confirmDialog,t("m_98091834913e")))return;
  if(state.saving||state.scene?.id!==captured.id||state.bufferEpoch!==captured.epoch||state.mode!==captured.mode)return;
  loadBuffer(scene,'plan',scene.beats);
  uiText(document.querySelector('#current-kind'),"textContent",()=>(t("m_9ecb77f7d846")));
  uiText(document.querySelector('#scene-title'),"textContent",()=>(displaySceneTitle(scene.title)));
  const picker=document.querySelector('#scene-select-mobile');if(picker)picker.value=scene.id;
  document.dispatchEvent(new CustomEvent('scene-selected'));
  for(const button of document.querySelectorAll('.scene-item')){const active=button.textContent.startsWith((scene.position+1)+'.');button.classList.toggle('active',active);button.setAttribute('aria-current',active?'true':'false')}
}

textEditor.onInput(()=>{state.dirty=textEditor.isDirty()||!!authorComments?.isDirty();state.bufferEpoch++;uiText(document.querySelector('#save-state'),"textContent",()=>(state.dirty?t("m_ee929a68273c"):t("m_4fc1598084c2")));changed()});
globalThis.addEventListener?.('beforeunload',event=>{if(state.dirty||state.saving||state.coreReview?.dirty()){event.preventDefault();event.returnValue=''}});

export async function saveCurrentMaterial(){
  if(state.bufferOrigin==='history'||['history','blueprint','review'].includes(state.mode))throw new Error(t("m_b51f0fcfbfe2"));
  if(state.mode!=='plan')return invokeWorkspaceCommand('save-material');
  return saveBuffer(snapshot=>api('/api/scenes/'+snapshot.scene.id,json('PATCH',{story_id:state.storyId,expected_revision:snapshot.scene.revision,beats:snapshot.text})));
}
registerWorkspaceCommand('save',saveCurrentMaterial);
saveButton.onclick=async()=>{
  if(state.saving)return;
  try{
    if(state.mode!=='plan'){document.dispatchEvent(new CustomEvent('save-prose'));return}
    const saved=await saveBuffer(snapshot=>api('/api/scenes/'+snapshot.scene.id,json('PATCH',{story_id:state.storyId,expected_revision:snapshot.scene.revision,beats:snapshot.text})));
    if(saved)notice(msg("m_2833156c05b9"));
  }catch(error){notice(error.message,'error')}
};

let importBusy=false;
document.querySelector('#import-sources').onsubmit=async event=>{
  event.preventDefault();if(importBusy)return;
  const formElement=event.target,host=document.querySelector('#import-results');
  const charactersHref=()=>document.querySelector('#workspace-characters')?.href||`/stories/${encodeURIComponent(state.storyId)}/characters`;
  let previous=[],sent=false;
  try{
    if(state.dirty||state.saving)throw new Error(t("m_a4c2e86ecc1a"));
    const form=new FormData(formElement);for(const[key,value]of[...form])if(!value.size)form.delete(key);
    importBusy=true;formElement.setAttribute('aria-busy','true');
    previous=[...formElement.elements].map(e=>[e,e.disabled]);previous.forEach(([e])=>e.disabled=true);
    const importer=formElement.closest('details');importer.dataset.userOpened='true';importer.open=true;
    showImportPending(host);
    sent=true;
    const result=await api('/api/stories/'+state.storyId+'/sources',{method:'POST',body:form});
    if(!Array.isArray(result.files))throw new Error(t('imports.unknown'));
    renderImportResults(host,result,{charactersHref:charactersHref()});
    for(const file of result.files||[])if(file.status==='imported'){
      const input=formElement.elements[file.kind==='source_plan'?'plan':'characters'];if(input)input.value='';
    }
    try{await refresh();}catch{showImportRefreshWarning(host,refresh);}
  }catch(error){
    const uncertain=sent&&!Array.isArray(error.data?.files)&&(!error.status||error.status>=500);
    if(uncertain)for(const name of ['plan','characters'])formElement.elements[name].value='';
    renderImportResults(host,error.data||{},{failed:true,uncertain,onRefresh:refresh,error,charactersHref:charactersHref()});
    notice(error.message,'error');
  }finally{
    previous.forEach(([e,disabled])=>e.disabled=disabled);importBusy=false;formElement.setAttribute('aria-busy','false');importAvailability();
  }
};
document.querySelector('#add-scene').onclick=async()=>{const title=await promptDialog(t("m_dd7bf0189af8"));if(!title)return;try{await api('/api/stories/'+state.storyId+'/scenes',json('POST',{title}));await refresh()}catch(error){notice(error.message,'error')}};
installSceneTrash(state,refresh,()=>{state.scene=null;state.dirty=false;state.bufferEpoch++;textEditor.write('');renderOrigin(null);textEditor.placeholder(live(()=>placeholders.plan));document.querySelector('#mode-tabs').replaceChildren();document.querySelector('#version-panel').replaceChildren();document.querySelector('#scene-settings')?.remove?.();uiText(document.querySelector('#scene-title'),"textContent",()=>(t("m_f0f1417db6de")));uiText(document.querySelector('#save-state'),"textContent",()=>(''));saveButton.disabled=true;document.dispatchEvent(new CustomEvent('scene-selected'));changed()});
refresh().catch(error=>notice(error.message,'error'));

const importForm=document.querySelector('#import-sources'),importButton=importForm.querySelector?.('button');
function importAvailability(){if(importButton){importButton.disabled=!(importForm.elements?.plan?.files?.length||importForm.elements?.characters?.files?.length)||state.saving||state.dirty||importBusy;uiText(importButton,"title",()=>(importButton.disabled?t("m_4b050af78972"):''))}}
document.querySelector('.importer > summary')?.addEventListener('click',()=>{document.querySelector('.importer').dataset.userOpened='true'});
importForm.addEventListener('change',importAvailability);document.addEventListener('editor-state-changed',importAvailability);importAvailability();
