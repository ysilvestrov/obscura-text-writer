import {acceptanceReason,openAcceptance,closeAcceptancePreview} from './acceptance.js';
import {api,json,notice} from './api.js';
import {state,refresh,saveBuffer,loadBuffer} from './editor.js';
import {renderLanguageWarnings} from './copyedits.js';
import {installMemoryTable} from './memory-table.js';
import {registerWorkspaceCommand} from './workspace-commands.js';
import {activateStageTab,revealStageTab,setStageTabStops} from './workspace-tabs.js';
const memoryTable=installMemoryTable({state,api,json,notice,refresh,loadBuffer});
const editor=document.querySelector('#editor');
const labels={plan:'План',brief:'Завдання',draft:'Чернетка',review:'Редактура',prose:'Проза',memory:'Пам’ять'};
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
async function show(mode){
  if(state.saving)throw new Error('Дочекайтеся завершення збереження');
  if(state.dirty&&!confirm('Є незбережені правки. Відкрити інший матеріал?'))return;
  const scene=state.view.scenes.find(s=>s.id===state.scene.id)||state.scene;
  const epoch=state.bufferEpoch;
  const text=mode==='review'?'':mode==='plan'?scene.beats:scene.heads[mode]?(await api('/api/versions/'+scene.heads[mode])).text:'';
  if(epoch!==state.bufferEpoch)return;
  loadBuffer(scene,mode,text);
  document.querySelector('#current-kind').textContent=labels[mode].toUpperCase();
  document.querySelector('#save-state').textContent=scene.heads[mode]?'Збережена версія':'';
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
  if(memoryTable.active()){await memoryTable.save();if(state.dirty)throw new Error('Не вдалося зберегти вибір пам’яті');return;}
  if(!['draft','prose','memory','brief'].includes(state.mode))throw new Error('Цей матеріал недоступний для збереження');
  return saveBuffer(snapshot=>api(`/api/scenes/${snapshot.scene.id}/${snapshot.mode}`,json('POST',{text:snapshot.text,expected_revision:snapshot.scene.revision})));
});
async function render(){
  if(!state.scene)return;
  closeAcceptancePreview();
  const tabs=document.querySelector('#mode-tabs');tabs.replaceChildren();
  for(const [mode,label] of Object.entries(labels)){const button=document.createElement('button');button.className='secondary';button.dataset.mode=mode;button.dataset.label=label;button.textContent=label;button.setAttribute('role','tab');button.onclick=()=>show(mode).catch(e=>notice(e.message,'error'));tabs.append(button)}
  updateTabs();
  const data=await api('/api/scenes/'+state.scene.id+'/versions');versions=data.versions;
  state.workspaceMaterials=Object.fromEntries(['plan','brief','draft','prose','memory'].map(kind=>[kind,versions.find(v=>v.id===state.scene.heads[kind])]));
  document.dispatchEvent(new CustomEvent('workspace-statistics'));
  const panel=document.querySelector('#version-panel');panel.replaceChildren();
  const title=document.createElement('h3');title.textContent='Історія версій';panel.append(title);
  const list=document.createElement('select');list.id='history-version';list.setAttribute('aria-label','Історична версія');
  for(const ref of [...versions].reverse()){const opt=document.createElement('option');opt.value=ref.id;opt.textContent=`${ref.kind} · ${ref.created_at.slice(0,19)}${ref.stale?' · застаріла':''}${data.acceptances?.some(a=>a.version_id===ref.id)?' · авторське прийняття':''}`;list.append(opt)}
  panel.append(list);
  const historyActions=[];
  function updateHistory(){const ref=versions.find(v=>v.id===list.value);for(const [b,kind]of historyActions){let reason=kind==='review-acceptance'?acceptanceReason(state,ref):!ref?'Немає версії':state.saving?'Дочекайтеся збереження':kind==='select'&&(ref.stale||!ref.complete||!['edited','manual'].includes(ref.kind))?'Оберіть завершену актуальну прозу':kind==='accept'&&(ref.stale||!ref.complete||ref.kind!=='brief')?'Оберіть актуальне завдання':kind==='accept-draft'&&(ref.stale||!ref.complete||ref.kind!=='draft')?'Оберіть завершену актуальну чернетку':kind==='language'&&(!['draft','edited','manual'].includes(ref.kind)||state.dirty)?'Оберіть збережену чернетку або прозу та збережіть ручні правки':kind==='compare'&&!state.scene?.heads.draft?'Немає чернетки':(['select','accept','accept-draft'].includes(kind)&&state.dirty)?'Спершу збережіть правки':'';b.disabled=!!reason;b.title=reason}}
  list.onchange=updateHistory;updateHistoryControls=updateHistory;
  function action(label,handler,kind='view'){const b=document.createElement('button');b.className='secondary';b.textContent=label;b.onclick=()=>handler().catch(e=>notice(e.message,'error'));historyActions.push([b,kind]);panel.append(b)}
  action('Переглянути версію',async()=>{if(state.saving)throw new Error('Дочекайтеся збереження');if(state.dirty&&!confirm('Є незбережені правки. Переглянути версію?'))return;const epoch=state.bufferEpoch;const v=await api('/api/versions/'+list.value);if(epoch!==state.bufferEpoch)return;const mode=v.version.kind==='memory'?'memory':v.version.kind==='brief'?'brief':v.version.kind==='scene_plan'?'plan':['edited','manual'].includes(v.version.kind)?'prose':'history';loadBuffer(state.scene,mode,v.text,'history');document.querySelector('#current-kind').textContent='ІСТОРИЧНА ВЕРСІЯ · '+v.version.kind});
  const languageResult=document.createElement('section');languageResult.className='language-warnings';
  action('Перевірити мову вибраної версії',async()=>{const ref=versions.find(v=>v.id===list.value);if(!ref||!['draft','edited','manual'].includes(ref.kind))throw new Error('Оберіть збережену чернетку або прозу');const id=ref.id;const result=await api(`/api/versions/${id}/language-warnings`);if(list.value!==id||!panel.contains(languageResult))return;renderLanguageWarnings(languageResult,result)},'language');
  panel.append(languageResult);
  action('Зробити поточною прозою',async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/select-version`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('prose')},'select');
  action('Прийняти завдання',async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/accept-brief`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('brief')},'accept');
  action('Прийняти чернетку',async()=>{state.scene=await api(`/api/scenes/${state.scene.id}/accept-draft`,json('POST',{version_id:list.value,expected_revision:state.scene.revision}));await refresh();await show('draft');notice('Чернетку прийнято')},'accept-draft');
  action('Переглянути й прийняти текст',async()=>{
    const ref=versions.find(v=>v.id===list.value);
    await openAcceptance({state,ref,api,json,panel,notice,onAccepted:async(result,captured)=>{
      if(state.scene?.id===captured.sceneId&&!state.dirty&&!state.saving&&state.bufferEpoch===captured.epoch){state.scene=result.scene;await refresh();await show(ref.kind==='draft'?'draft':'prose')}
      else await refresh();
    }});
  },'review-acceptance');
  action('Порівняти з чернеткою',async()=>{if(!state.scene.heads.draft)throw new Error('Немає чернетки');const pair=await api(`/api/versions/compare?left=${state.scene.heads.draft}&right=${list.value}`);const container=document.createElement('div');container.className='comparison';for(const text of [pair.left,pair.right,pair.diff]){const pre=document.createElement('pre');pre.textContent=text;container.append(pre)}panel.append(container)},'compare');
  updateHistory();
}
document.addEventListener('scene-selected',()=>render().catch(e=>notice(e.message,'error')));
document.addEventListener('story-refreshed',async()=>{
  try{
    const latest=state.view.scenes.find(s=>s.id===state.scene?.id);
    if(['brief','draft','prose','memory'].includes(state.mode)&&!state.dirty&&!state.saving&&state.bufferOrigin!=='history'&&latest?.heads[state.mode]&&latest.heads[state.mode]!==state.scene?.heads[state.mode])await show(state.mode);
    await render();
  }catch(e){notice(e.message,'error')}
});
document.addEventListener('save-prose',async()=>{try{
  if(memoryTable.active()){await memoryTable.save();return;}
  if(!['draft','prose','memory','brief'].includes(state.mode))throw new Error('Збереження доступне для плану, завдання, чернетки, прози й пам’яті');
  const result=await saveBuffer(snapshot=>api(`/api/scenes/${snapshot.scene.id}/${snapshot.mode==='prose'?'prose':snapshot.mode}`,json('POST',{text:snapshot.text,expected_revision:snapshot.scene.revision})));
  if(result)notice(result.needs_review?'Завдання з пропозиціями збережено. Прийміть його окремою дією.':'Нову версію збережено');
}catch(e){notice(e.message,'error')}});
