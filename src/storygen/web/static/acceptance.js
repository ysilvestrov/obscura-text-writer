export function acceptanceReason(state,ref){
  if(state.saving)return 'Дочекайтеся завершення збереження';
  if(state.dirty)return 'Спершу збережіть ручні правки';
  if(!state.scene)return 'Оберіть сцену';
  if(!ref?.complete||!['draft','edited','manual'].includes(ref.kind))return 'Оберіть завершену чернетку або прозу';
  return '';
}
let closePreview=()=>{};
export function closeAcceptancePreview(){closePreview()}
const reasons={selector_changed:'Змінено джерело',selector_unavailable:'Джерело недоступне',source_baseline_changed:'Змінено авторське рішення',source_stale:'Застаріле джерело',legacy_stale:'Застаріла версія без перевіреного знімка',incomplete:'Незавершена версія',integrity_error:'Порушена цілісність',source_unavailable:'Джерело недоступне',dependency_cycle:'Цикл залежностей'};
const value=v=>v==null?'відсутнє':Array.isArray(v)?v.join(', '):String(v);
export async function openAcceptance({state,ref,api,json,panel,notice,onAccepted}){
  const reason=acceptanceReason(state,ref);if(reason)throw new Error(reason);
  closePreview();
  const sceneId=state.scene.id,epoch=state.bufferEpoch;
  const preview=await api(`/api/scenes/${sceneId}/acceptance-preview?version_id=${encodeURIComponent(ref.id)}`);
  if(state.scene?.id!==sceneId||state.bufferEpoch!==epoch||state.dirty)throw new Error('Редактор змінився. Відкрийте перегляд прийняття заново');
  const container=document.createElement('section');container.className='acceptance-preview';
  const title=document.createElement('h3');title.textContent='Перегляд авторського прийняття';title.id='acceptance-title';container.setAttribute('aria-labelledby',title.id);
  const warning=document.createElement('p');warning.textContent='Прийняття зробить цей текст поточним за новою базою залежностей. Пам’ять і оцінювання потребуватимуть окремого оновлення.';
  const text=document.createElement('pre');text.textContent=preview.text;
  const changes=document.createElement('ul');
  for(const change of preview.changes){const item=document.createElement('li');item.textContent=`${reasons[change.reason]||change.reason}: ${change.selector?.field||change.version_id||ref.id} · було: ${value(change.expected)}; тепер: ${value(change.current)}`;changes.append(item)}
  if(!preview.changes.length){const item=document.createElement('li');item.textContent='Змін залежностей не виявлено.';changes.append(item)}
  const commit=document.createElement('button');commit.textContent=ref.kind==='draft'?'Підтверджую прийняття чернетки':'Підтверджую прийняття прози';
  const cancel=document.createElement('button');cancel.className='secondary';cancel.textContent='Закрити перегляд';
  let busy=false,invalid=false;
  function update(){const reason=acceptanceReason(state,ref)||((state.scene?.id!==sceneId||state.bufferEpoch!==epoch)?'Редактор змінився. Перегляньте заново':'');commit.disabled=busy||invalid||!!reason;commit.title=reason}
  function close(){document.removeEventListener?.('editor-state-changed',update);container.replaceChildren();container.remove?.();closePreview=()=>{}}
  closePreview=close;cancel.onclick=close;
  commit.onclick=async()=>{
    update();if(commit.disabled)return;
    busy=true;update();commit.textContent='Зберігаємо рішення…';
    try{
      const result=await api(`/api/scenes/${sceneId}/accept-version`,json('POST',{version_id:ref.id,expected_revision:preview.expected_revision,preview_fingerprint:preview.preview_fingerprint}));
      close();await onAccepted(result,{sceneId,epoch});notice('Авторське прийняття збережено','success');
    }catch(error){invalid=true;notice(error.message+' Відкрийте перегляд заново.','error')}
    finally{busy=false;commit.textContent=invalid?'Потрібен новий перегляд':'Прийнято';update()}
  };
  document.addEventListener('editor-state-changed',update);update();
  container.append(title,warning,text,changes,commit,cancel);panel.append(container);title.tabIndex=-1;title.focus();
  return {container,text,commit,cancel};
}


export function acceptedContinuation(run,attempts,scene,versions,acceptances){
  if(!run||!['alternative','needs_review'].includes(run.state))return null;
  const task=run.tasks[run.cursor],head={brief:'brief',draft:'draft',edit:'prose',memory:'memory'}[task?.stage];
  if(!head||task.scene_id!==scene?.id)return null;
  const attempt=[...attempts].reverse().find(a=>a.stage===task.stage&&a.scene_id===scene.id);
  const ref=versions.find(v=>v.id===attempt?.result_version_id);
  if(!ref||ref.stale||!ref.complete||scene.heads[head]!==ref.id)return null;
  const acceptance=acceptances.filter(a=>a.version_id===ref.id).at(-1);
  return {version_id:ref.id,expected_cursor:run.cursor,expected_scene_revision:scene.revision,acceptance_id:acceptance?.id||null};
}
