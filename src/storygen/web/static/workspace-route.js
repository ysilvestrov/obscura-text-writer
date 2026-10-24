import {state,textEditor,selectScene,refresh} from './editor.js';
import {api,json,notice} from './api.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {performPrimary,primaryAction} from './workspace-state.js';

const primary=document.querySelector('#workspace-primary'),hint=document.querySelector('#workspace-hint');
let busy=false,pending=null;
const activeStates=new Set(['queued','running','pause_requested','cancellation_requested']);
const isActive=()=>activeStates.has(state.workspaceRun?.state)||(state.workspaceRuns||[]).some(run=>activeStates.has(run.state));
function render(){
  const meta=document.querySelector('#workspace-scene-meta');if(meta&&state.scene)meta.textContent=`Сцена ${state.scene.position+1} із ${state.view?.scenes.length||'—'} · орієнтир ${state.scene.target_words} слів`;
  const compact=document.querySelector('#workspace-compact-status');if(compact){const labels={queued:'У черзі',running:'Генерація',needs_review:'Очікує рішення',completed:'Завершено',failed:'Помилка',paused:'Пауза',cancelled:'Скасовано',alternative:'Альтернатива',interrupted:'Перервано'};compact.textContent=(labels[state.workspaceRun?.state]||'Готово до роботи')+' · '+(state.workspaceBudgetText||document.querySelector('.budget-panel')?.dataset.compactBudget||'Завантажуємо облік…');}
  const activeRun=activeStates.has(state.workspaceRun?.state)?state.workspaceRun:(state.workspaceRuns||[]).find(run=>activeStates.has(run.state));
  const review=state.mode==='review';
  textEditor.visible(!review&&!state.memoryTableActive);
  const panel=document.querySelector('#copyedit-panel');panel.hidden=!review;
  const details=panel.querySelector('details');if(review&&details)details.open=true;
  const action=primaryAction(state);
  let reason=!state.scene?'Оберіть сцену':state.saving?'Триває збереження':busy?'Виконуємо дію…':isActive()?'Дочекайтеся поточного запуску':state.characterDirty?'Спершу збережіть відомості персонажів':state.bufferOrigin==='history'?'Відкрито історичну версію: поверніться до поточного матеріалу':'';
  if(review)reason=reason||(state.reviewAvailability?.ready?'':state.reviewAvailability?.reason||'Перегляньте пропозиції та зібраний текст перед прийняттям');
  if(state.mode==='memory')reason=reason||(!state.scene?.heads.memory?'Спершу створіть пам’ять зі вкладки «Проза»':state.workspaceMaterials?.memory?.stale?'Пам’ять потребує оновлення перед переходом':'');
  const operation=state.workspaceReadiness?.operations[action.stage||action.mode];
  if(!reason&&!state.dirty&&action.mode)reason=operation?.ready?'':operation?.reason||'Перевіряємо передумови…';
  primary.textContent=action.label||'Оберіть етап';primary.disabled=!!reason;
  const scenes=state.view?.scenes||[],last=scenes.at(-1)?.id===state.scene?.id;
  if(state.mode==='memory')primary.textContent=last?'Зберегти вибір і перейти до публікації':'Зберегти вибір і перейти до наступної сцени';
  hint.textContent=reason||(action.target&&state.scene?.heads[action.target]?'Попередній результат залишиться в історії. Новий модельний виклик запускається лише цією дією.':state.mode==='review'?'Прийняття збереже нову прозу. Модельний виклик не потрібен.':state.mode==='memory'?'Перехід не запускає генерацію наступної сцени.':'Збережемо ручні правки й перевіримо передумови перед запуском.');
  primary.title=reason;
  const repeat=document.querySelector('#workspace-edit-prose');repeat.hidden=state.mode!=='prose';repeat.disabled=busy||isActive()||state.saving;
  for(const b of document.querySelectorAll('#mode-tabs button')){
    const mode=b.dataset.mode,head=mode==='review'?'prose':mode;
    const material=state.workspaceMaterials?.[mode];
    let status=mode==='review'?(state.reviewAvailability?.pending?'Очікує рішення':state.reviewAvailability?.hasChanges?'Є правки':'Перегляд правок'):!state.scene?.heads[head]&&!(mode==='plan'&&state.scene?.beats)?'Немає матеріалу':material?.stale?'Потребує оновлення':'Є матеріал';
    if(activeRun&&mode===(activeRun.request.mode==='edit_loop'?'review':{brief:'brief',draft:'draft',edit:'review',memory:'memory'}[activeRun.request.stage]))status='Виконується';
    b.setAttribute('aria-selected',String(mode===state.mode&&state.bufferOrigin!=='history'));
    b.setAttribute('aria-label',`${b.dataset.label||b.textContent.split('\n')[0]}: ${status}`);
    let small=b.querySelector('small');if(!small){small=document.createElement('small');b.append(small)}small.textContent=status;
  }
}
async function nextScene(){
  const scenes=state.view.scenes,index=scenes.findIndex(s=>s.id===state.scene.id);
  if(index<0)throw new Error('Оновіть список сцен');
  if(index===scenes.length-1){location.assign(`/stories/${encodeURIComponent(state.storyId)}/publication`);return}
  await selectScene(scenes[index+1]);
}
async function launch(options){
  const capture={sceneId:state.scene.id,epoch:state.bufferEpoch,mode:state.mode};
  const run=await invokeWorkspaceCommand('run',options);
  if(run){pending={...capture,id:run.id,target:options.mode==='edit_loop'?'review':options.stage};await complete(run)}
  return run;
}
async function complete(run){
  if(!pending||pending.id!==run.id||!['completed','needs_review','alternative'].includes(run.state))return;
  const captured=pending;pending=null;
  await refresh();
  if(state.scene?.id===captured.sceneId&&state.mode===captured.mode&&!state.dirty&&!state.saving&&state.bufferOrigin!=='history'){
    // The material loader may have refreshed the same completed head; never replace newer typing.
    if(state.bufferEpoch===captured.epoch||state.mode===captured.target)await invokeWorkspaceCommand('show',captured.target);
  }
}
primary.onclick=async()=>{
  if(busy||primary.disabled)return;busy=true;render();
  try{await performPrimary({state,save:()=>invokeWorkspaceCommand('save'),run:launch,
    show:mode=>invokeWorkspaceCommand('show',mode),accept:()=>invokeWorkspaceCommand('accept-review'),next:nextScene})}
  catch(error){notice(error.message,'error')}finally{busy=false;render()}
};
document.querySelector('#workspace-edit-prose').onclick=async()=>{
  if(busy)return;busy=true;render();
  const capture={id:state.scene?.id,epoch:state.bufferEpoch,mode:state.mode};
  try{
    if(state.dirty)await invokeWorkspaceCommand('save');
    if(state.dirty||state.saving||state.mode!=='prose'||state.scene?.id!==capture.id||state.bufferEpoch!==capture.epoch)throw new Error('Матеріал змінився під час збереження');
    await launch({mode:'edit_loop',editor_source_head:'prose',editor_source_version_id:state.scene.heads.prose});
  }catch(error){notice(error.message,'error')}finally{busy=false;render()}
};
document.querySelector('#workspace-use-draft').onclick=async()=>{
  if(state.dirty||state.saving||busy||isActive())return;
  const scene=state.scene,id=scene?.heads.draft,epoch=state.bufferEpoch;
  if(!id){notice('Немає поточної чернетки','warning');return}
  if(!confirm('Зберегти поточну чернетку як авторську прозу без прийняття редакторських правок?'))return;
  busy=true;render();
  try{const source=await api('/api/versions/'+id);
    if(state.scene?.id!==scene.id||state.bufferEpoch!==epoch||state.dirty)throw new Error('Матеріал змінився');
    await api(`/api/scenes/${scene.id}/prose`,json('POST',{text:source.text,expected_revision:scene.revision}));await refresh();await invokeWorkspaceCommand('show','prose');
  }catch(error){notice(error.message,'error')}finally{busy=false;render()}
};
for(const event of ['editor-state-changed','scene-selected','story-refreshed','workspace-readiness','workspace-review-state','workspace-statistics'])document.addEventListener(event,render);
document.addEventListener('workspace-run-state',event=>{render();void complete(event.detail).catch(e=>notice(e.message,'error'))});
document.addEventListener('workspace-budget-updated',event=>{state.workspaceBudgetText=event.detail;render()});
render();
