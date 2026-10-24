import {api,json,notice} from './api.js';
import {installSceneTrash} from './trash.js';
import {createTextEditor} from './text-editor.js';
import {registerWorkspaceCommand,invokeWorkspaceCommand} from './workspace-commands.js';

export const state={storyId:document.querySelector('#workspace')?.dataset.storyId,scene:null,view:null,mode:'plan',dirty:false,saving:false,bufferEpoch:0};
const editor=document.querySelector('#editor');
export const textEditor=createTextEditor(editor);
const placeholders={
  plan:'Імпортуйте план або створіть сцену вручну.',
  brief:'Створіть завдання за планом сцени або вставте його у форматі JSON.',
  draft:'Напишіть чернетку вручну або натисніть «Написати».',
  prose:'Тут буде проза після прийняття редактури. Також можна вставити текст вручну.',
  memory:'Натисніть «Оновити пам’ять» після створення прози. Розширене редагування — у форматі JSON.'
};
const saveButton=document.querySelector('#save-text');
const changed=()=>document.dispatchEvent(new CustomEvent('editor-state-changed'));

// Presentation only: never rewrite the title in storage or the editor buffer.
export function displaySceneTitle(title){
  return title.replace(/^\s*#{1,6}\s+/, '').replace(/\*\*|__/g, '').trim();
}

export function loadBuffer(scene,mode,text,origin='current'){
  state.scene=scene;state.mode=mode;state.dirty=false;state.bufferEpoch++;
    state.bufferOrigin=origin;
  textEditor.write(text);
  textEditor.placeholder(placeholders[mode]||'');
  textEditor.readOnly(mode==='review');
  document.querySelector('#save-state').textContent='Збережена версія';
  saveButton.disabled=['history','blueprint','review'].includes(mode);changed();
}

export async function saveBuffer(send){
  if(state.saving)return null;
  if(!state.scene)throw new Error('Оберіть сцену');
  const snapshot={scene:state.scene,mode:state.mode,text:textEditor.read()};
  state.saving=true;saveButton.disabled=true;changed();
  try{
    const result=await send(snapshot);
    if(state.scene?.id===snapshot.scene.id&&state.mode===snapshot.mode){
      state.scene=result.scene||result;
      state.dirty=textEditor.read()!==snapshot.text;
      document.querySelector('#save-state').textContent=state.dirty?'Попередню правку збережено; є нові незбережені зміни':'Збережено';
    }
    await refresh();
    return result;
  }finally{
    state.saving=false;saveButton.disabled=['history','blueprint','review'].includes(state.mode);changed();
  }
}

export async function refresh(){
  state.view=await api('/api/stories/'+state.storyId);
  // The loaded buffer keeps its own revision until text and revision are explicitly reloaded together.
  const latest=state.view.scenes.find(s=>s.id===state.scene?.id);
  if(state.scene)document.querySelector('#scene-title').textContent=displaySceneTitle(state.scene.title);
  if(latest&&latest.revision!==state.scene.revision&&!state.dirty)document.querySelector('#save-state').textContent='Є новіша версія на сервері. Відкрийте її перед збереженням.';
  const list=document.querySelector('#scene-list');list.replaceChildren();
  document.querySelector('#scene-count').textContent=state.view.scenes.length;
  const picker=document.querySelector('#scene-select-mobile');
  if(picker){picker.replaceChildren();for(const scene of state.view.scenes){const option=document.createElement('option');option.value=scene.id;option.textContent=(scene.position+1)+'. '+displaySceneTitle(scene.title);picker.append(option)}picker.value=state.scene?.id||'';picker.onchange=()=>{const scene=state.view.scenes.find(s=>s.id===picker.value);if(scene)void selectScene(scene)}}
  for(const scene of state.view.scenes){
    const button=document.createElement('button');button.className='scene-item'+(state.scene?.id===scene.id?' active':'');button.textContent=(scene.position+1)+'. '+displaySceneTitle(scene.title);
    button.setAttribute('aria-current',state.scene?.id===scene.id?'true':'false');
    const small=document.createElement('small');small.textContent=!scene.heads.prose&&!scene.heads.draft?(scene.heads.brief?'Немає тексту':'Не почато'):scene.needs_review?'Потребує перегляду':scene.heads.prose?'Текст створено':'Є чернетка';button.append(small);button.onclick=()=>selectScene(scene);list.append(button);
  }
  if(!state.scene&&state.view.scenes.length)await selectScene(state.view.scenes[0]);
  const context=document.querySelector('#context-content');context.replaceChildren();
  for(const source of state.view.sources){const p=document.createElement('p');p.textContent=source.kind==='source_plan'?'✓ Авторський план':'✓ Описи персонажів';context.append(p)}
  const importer=document.querySelector('.importer');if(importer&&!importer.dataset.userOpened)importer.open=state.view.sources.length===0&&state.view.scenes.length===0;
  document.dispatchEvent(new CustomEvent('story-refreshed'));
}

export async function selectScene(scene){
  if(state.saving){notice('Дочекайтеся завершення збереження');return}
  if(state.dirty&&!confirm('Є незбережені правки. Змінити сцену без збереження?'))return;
  loadBuffer(scene,'plan',scene.beats);
  document.querySelector('#current-kind').textContent='ПЛАН СЦЕНИ';
  document.querySelector('#scene-title').textContent=displaySceneTitle(scene.title);
  const picker=document.querySelector('#scene-select-mobile');if(picker)picker.value=scene.id;
  document.dispatchEvent(new CustomEvent('scene-selected'));
  for(const button of document.querySelectorAll('.scene-item')){const active=button.textContent.startsWith((scene.position+1)+'.');button.classList.toggle('active',active);button.setAttribute('aria-current',active?'true':'false')}
}

editor.addEventListener('input',()=>{state.dirty=true;state.bufferEpoch++;document.querySelector('#save-state').textContent='Незбережені зміни';changed()});
globalThis.addEventListener?.('beforeunload',event=>{if(state.dirty||state.saving){event.preventDefault();event.returnValue=''}});

export async function saveCurrentMaterial(){
  if(state.bufferOrigin==='history'||['history','blueprint','review'].includes(state.mode))throw new Error('Історію або перегляд редактури не можна зберегти як матеріал');
  if(state.mode!=='plan')return invokeWorkspaceCommand('save-material');
  return saveBuffer(snapshot=>api('/api/scenes/'+snapshot.scene.id,json('PATCH',{story_id:state.storyId,expected_revision:snapshot.scene.revision,beats:snapshot.text})));
}
registerWorkspaceCommand('save',saveCurrentMaterial);
saveButton.onclick=async()=>{
  if(state.saving)return;
  try{
    if(state.mode!=='plan'){document.dispatchEvent(new CustomEvent('save-prose'));return}
    const saved=await saveBuffer(snapshot=>api('/api/scenes/'+snapshot.scene.id,json('PATCH',{story_id:state.storyId,expected_revision:snapshot.scene.revision,beats:snapshot.text})));
    if(saved)notice('План сцени збережено');
  }catch(error){notice(error.message,'error')}
};

document.querySelector('#import-sources').onsubmit=async event=>{
  event.preventDefault();
  try{
    if(state.dirty||state.saving)throw new Error('Спершу збережіть ручні правки');
    const form=new FormData(event.target);for(const[key,value]of[...form])if(!value.size)form.delete(key);
    const result=await api('/api/stories/'+state.storyId+'/sources',{method:'POST',body:form});
    notice(result.warnings.join(' ')||'Матеріали імпортовано');state.scene=null;await refresh();
  }catch(error){notice(error.message,'error')}
};
document.querySelector('#add-scene').onclick=async()=>{const title=prompt('Назва нової сцени');if(!title)return;try{await api('/api/stories/'+state.storyId+'/scenes',json('POST',{title}));await refresh()}catch(error){notice(error.message,'error')}};
installSceneTrash(state,refresh,()=>{state.scene=null;state.dirty=false;state.bufferEpoch++;editor.value='';editor.placeholder=placeholders.plan;document.querySelector('#mode-tabs').replaceChildren();document.querySelector('#version-panel').replaceChildren();document.querySelector('#scene-settings')?.remove?.();document.querySelector('#scene-title').textContent='Оберіть сцену';document.querySelector('#save-state').textContent='';saveButton.disabled=true;document.dispatchEvent(new CustomEvent('scene-selected'));changed()});
refresh().catch(error=>notice(error.message,'error'));

const importForm=document.querySelector('#import-sources'),importButton=importForm.querySelector?.('button');
function importAvailability(){if(importButton){importButton.disabled=!(importForm.elements?.plan?.files?.length||importForm.elements?.characters?.files?.length)||state.saving;importButton.title=importButton.disabled?'Виберіть файл плану або персонажів':''}}
importForm.addEventListener('change',importAvailability);document.addEventListener('editor-state-changed',importAvailability);importAvailability();
