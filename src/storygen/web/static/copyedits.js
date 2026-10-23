// A reusable panel. Content is always text; publication is performed by the API.
export function mountCopyeditReview({host,state,api,json,notice,onApplied,onQueued=()=>{}}){
  const panel=document.createElement('details'),summary=document.createElement('summary');
  panel.className='copyedit-review';summary.textContent='Правки редактора';panel.append(summary);host.append(panel);
  const help=document.createElement('p');help.textContent='Зміни одного речення приймаються разом одним прапорцем. Порожній вибір збереже прозу без цих правок. Попередні версії залишаться в історії.';
  const label=document.createElement('label');label.textContent='Редакторська пропозиція';const select=document.createElement('select');select.setAttribute('aria-label','Редакторська пропозиція');label.append(select);
  const open=document.createElement('button');open.type='button';open.className='secondary';open.textContent='Оновити перегляд';
  const info=document.createElement('p');info.setAttribute('role','status');
  const edits=document.createElement('div');edits.className='copyedit-items';
  const apply=document.createElement('button');apply.type='button';apply.textContent='Застосувати вибрані правки';
  const showSelection=document.createElement('button');showSelection.type='button';showSelection.className='secondary';showSelection.textContent='Переглянути вибраний текст';
  const selectedText=document.createElement('pre');selectedText.className='copyedit-selected-text';selectedText.setAttribute('aria-label','Текст із вибраними правками');
  const warnings=document.createElement('p');warnings.className='muted';
  const classify=document.createElement('button');classify.type='button';classify.className='secondary';classify.textContent='Класифікувати зміни';
  const classificationInfo=document.createElement('p');classificationInfo.className='muted';
  panel.append(help,label,open,info,warnings,edits,showSelection,selectedText,apply,classify,classificationInfo);
  let current=null,choices=[],busy=false,previewLoading=false,sceneId=null,listEpoch=0,previewEpoch=0;
  let assembled=null,selectionLoading=false,selectionEpoch=0;
  function clearSelection(){assembled=null;selectionEpoch++;selectionLoading=false;selectedText.textContent='';warnings.textContent='';classificationInfo.textContent=''}
  const indices=()=>choices.flatMap(c=>c.checked?c.editIndices:[]).sort((a,b)=>a-b);
  const selectionKey=()=>JSON.stringify(indices());
  const unresolved=()=>choices.some(c=>c.indeterminate);
  const selectionReady=()=>!unresolved()&&(current?.protocol_version!==2||(assembled?.fingerprint===current.proposal_fingerprint&&assembled?.key===selectionKey()));
  const hasChanges=()=>!!current&&(current.has_changes??current.edits.some(e=>e.original!==e.replacement));
  function reason(){return busy?'Виконуємо запит…':previewLoading?'Завантажуємо вибрану пропозицію…':!state.scene?'Оберіть сцену':state.saving?'Дочекайтеся збереження':state.dirty?'Спершу збережіть ручні правки':state.characterDirty?'Спершу збережіть відомості персонажів':!current?'Немає пропозиції для перегляду':!hasChanges()?'Редактор не запропонував змін':!current.can_apply?(current.reason||'Пропозицію не можна застосувати'):''}
  function updateAvailability(){help.hidden=!!current&&!hasChanges();classificationInfo.hidden=!hasChanges();apply.hidden=!!current&&!hasChanges();showSelection.hidden=!!current&&!hasChanges();selectedText.hidden=!hasChanges();const message=reason().trim();apply.disabled=!!message||!selectionReady();apply.title=message||(unresolved()?'Оберіть або відхиліть речення цілком':!selectionReady()?'Спершу перегляньте текст із вибраними змінами':'');for(const input of choices)input.disabled=!!message;open.disabled=busy||!state.scene;select.disabled=busy||!state.scene;showSelection.disabled=!!message||selectionLoading||unresolved();classify.hidden=current?.protocol_version!==2||!hasChanges();classify.disabled=!!message||!current?.can_classify;classify.title=current?.classification_reason||message;info.textContent=message||`Вибрано ${choices.filter(c=>c.checked).length} із ${choices.length}. Рішень в історії: ${current.decisions.length}.`+(unresolved()?' Історичний вибір містить частину речення; оберіть або відхиліть його цілком.':!selectionReady()?' Перегляньте зібраний текст перед прийняттям.':'')}
  function render(data,preserved=null){
    if(!preserved)clearSelection();
    current=data;choices=[];edits.replaceChildren();
    const selected=preserved||new Set(data.decisions.length?data.decisions.at(-1).selected_indices:(data.default_selected_indices??data.edits.map((_,i)=>i)));
    warnings.textContent=(data.warnings||[]).join(' ');
    const history=data.classification_history||[],last=history.at(-1);
    const statuses={completed:'завершено',failed:'помилка',running:'виконується',cancelled:'скасовано',interrupted:'перервано'};
    classificationInfo.textContent=(data.classification_provider?`Класифікатор: ${data.classification_provider.model} · ${data.classification_provider.provider}. `:'')+(data.classification?`Поради моделі ${data.classification_advice_model||''} можуть бути помилковими. `:'')+(last?`Остання класифікація: ${statuses[last.state]||last.state}${last.error?' · '+last.error:''}`:(data.classification_reason||''));
    const rows=data.groups??data.edits.map((edit,index)=>({...edit,indices:[index]}));
    for(const edit of (hasChanges()?rows:[])){
      const item=document.createElement('label');item.className='copyedit-item';
      const input=document.createElement('input');input.type='checkbox';input.editIndices=edit.indices;input.checked=edit.indices.every(index=>selected.has(index));input.indeterminate=!input.checked&&edit.indices.some(index=>selected.has(index));input.onchange=()=>{input.indeterminate=false;selectionEpoch++;if(!selectionReady())selectedText.textContent='Вибір змінено. Натисніть «Переглянути вибраний текст».';updateAvailability()};choices.push(input);
      const content=document.createElement('span'),kind=document.createElement('strong');kind.textContent={grammar:'Граматика',spelling:'Орфографія',punctuation:'Пунктуація',wording:'Слововживання',unclassified:'Зміна для перегляду',mixed:'Зміни речення'}[edit.category]||edit.category;
      const original=document.createElement('del');original.textContent=edit.original;
      const replacement=document.createElement('ins');replacement.textContent=edit.replacement;
      content.append(kind);
      for(const [caption,change,parts,tag]of [['Було: ',original,edit.before_parts,'del'],['Стало: ',replacement,edit.after_parts,'ins']]){
        const sentence=document.createElement('p');sentence.className='copyedit-sentence';
        const label=document.createElement('span');label.className='copyedit-line-label';label.textContent=caption;
        const before=document.createElement('span');before.textContent=edit.context_before||'';
        const after=document.createElement('span');after.textContent=edit.context_after||'';
        if(parts){sentence.append(label);for(const part of parts){const span=document.createElement(part.changed?tag:'span');span.textContent=part.text;sentence.append(span)}}
        else sentence.append(label,before,change,after);
        content.append(sentence);
      }
      for(const index of edit.indices){
      const advice=data.classification?.changes.find(c=>c.index===index);
      if(advice){const hint=document.createElement('small');const categories={grammar:'Граматика',spelling:'Орфографія',punctuation:'Пунктуація',wording:'Слововживання',style:'Стиль',meaning:'Зміст',formatting:'Форматування',mixed:'Змішана зміна',uncertain:'Не визначено'},assessments={improvement:'ймовірне покращення',regression:'можливе погіршення',neutral:'нейтрально',uncertain:'не визначено'};hint.textContent=`Порада моделі: ${categories[advice.category]||advice.category} · ${assessments[advice.assessment]||advice.assessment}. ${advice.explanation}`;content.append(hint)}
      }
      item.append(input,content);edits.append(item);
    }
    if(!hasChanges())for(const option of select.children){if(option.value===data.attempt_id)option.textContent=option.textContent.replace(/ · (?:чекає рішення|без змін)$/,'')+' · без змін'}
    if(!hasChanges()){const empty=document.createElement('p');empty.textContent='Прийняття недоступне; поточний текст не змінено.';edits.append(empty)}
    if(!indices().length){assembled={fingerprint:data.proposal_fingerprint,key:selectionKey(),text:data.original,warnings:[]};selectedText.textContent=data.original}
    else selectedText.textContent=selectionReady()?assembled?.text||data.preview:'Перегляньте текст із вибраними змінами.';
    if(selectionReady()&&assembled)warnings.textContent=(assembled.warnings||[]).join(' ');
    updateAvailability();
  }
  async function loadPreview(){
    if(!state.scene||!select.value){current=null;choices=[];clearSelection();edits.replaceChildren();updateAvailability();return}
    const selectedId=select.value,scene=state.scene.id,epoch=++previewEpoch;
    const previousFingerprint=current?.proposal_fingerprint;
    const preserved=current?.attempt_id===selectedId&&!unresolved()?new Set(indices()):null;
    current=null;previewLoading=true;updateAvailability();
    try{
      const data=await api(`/api/scenes/${scene}/copyedits/${selectedId}`);
      if(epoch!==previewEpoch||state.scene?.id!==scene||select.value!==selectedId)return;
      render(data,previousFingerprint===data.proposal_fingerprint?preserved:null);
    }catch(error){if(epoch===previewEpoch){current=null;choices=[];edits.replaceChildren();notice(error.message,'error')}}
    finally{if(epoch===previewEpoch){previewLoading=false;updateAvailability()}}
  }
  async function reload(){
    const epoch=++listEpoch,scene=state.scene?.id;
    if(scene!==sceneId){sceneId=scene;current=null;choices=[];clearSelection();previewLoading=false;edits.replaceChildren();select.replaceChildren();previewEpoch++}
    if(!scene){updateAvailability();return}
    try{
      const data=await api(`/api/scenes/${scene}/copyedits`);
      if(epoch!==listEpoch||scene!==state.scene?.id)return;
      const previous=select.value;select.replaceChildren();
      for(const attempt of [...data.attempts].reverse()){const option=document.createElement('option');option.value=attempt.id;option.textContent=attempt.created_at.slice(0,19)+(attempt.state==='needs_review'?' · чекає рішення':'');select.append(option)}
      select.value=data.attempts.some(a=>a.id===previous)?previous:data.attempts.at(-1)?.id||'';
      await loadPreview();
    }catch(error){if(epoch===listEpoch){current=null;updateAvailability();info.textContent=error.message}}
  }
  select.onchange=()=>loadPreview();open.onclick=()=>loadPreview();
  showSelection.onclick=async()=>{
    if(reason().trim()||unresolved())return;
    const captured={sceneId:state.scene.id,attemptId:current.attempt_id,fingerprint:current.proposal_fingerprint,key:selectionKey(),epoch:++selectionEpoch};
    selectionLoading=true;updateAvailability();
    try{
      const result=await api(`/api/scenes/${captured.sceneId}/copyedits/${captured.attemptId}/selection-preview`,json('POST',{expected_revision:current.expected_revision,proposal_fingerprint:captured.fingerprint,selected_indices:indices()}));
      if(captured.epoch!==selectionEpoch||state.scene?.id!==captured.sceneId||current?.attempt_id!==captured.attemptId||selectionKey()!==captured.key)return;
      assembled={fingerprint:captured.fingerprint,key:captured.key,text:result.text,warnings:result.warnings||[]};selectedText.textContent=result.text;warnings.textContent=assembled.warnings.join(' ');
    }catch(error){notice(error.message,'error')}
    finally{selectionLoading=false;updateAvailability()}
  };
  classify.onclick=async()=>{
    if(reason().trim()||!current?.can_classify)return;
    busy=true;updateAvailability();
    try{
      const run=await api(`/api/scenes/${state.scene.id}/copyedits/${current.attempt_id}/classify`,json('POST',{request_id:crypto.randomUUID(),proposal_fingerprint:current.proposal_fingerprint}));
      onQueued(run);
      notice('Класифікацію поставлено в чергу. Поради можна оновити після завершення; вони не застосовують змін.');
      await reload();
    }catch(error){notice(error.message,'error')}
    finally{busy=false;updateAvailability()}
  };
  apply.onclick=async()=>{
    if(reason().trim()||!selectionReady())return;
    const captured={sceneId:state.scene.id,epoch:state.bufferEpoch};
    const body={expected_revision:current.expected_revision,proposal_fingerprint:current.proposal_fingerprint,selected_indices:indices()};
    const attemptId=current.attempt_id;busy=true;updateAvailability();
    try{
      const result=await api(`/api/scenes/${captured.sceneId}/copyedits/${attemptId}`,json('POST',body));
      current=null;await onApplied(result,captured);if(result.run)onQueued(result.run);await reload();notice(result.run?.request.mode==='edit_loop'?'Підсумкові правки збережено. Цикл редактури завершено.':'Вибрані правки збережено новою версією. Для зупиненого workflow використайте продовження після прийнятого етапу.');
    }catch(error){notice(error.message,'error');info.textContent=error.message}
    finally{busy=false;updateAvailability()}
  };
  updateAvailability();
  return {reload,updateAvailability};
}

export function renderLanguageWarnings(host,result){
  host.replaceChildren();const title=document.createElement('h4');title.textContent='Мовні попередження';
  const hint=document.createElement('p');hint.textContent='Перевірено збережену версію. Евристики можуть помилятися й не доводять літературної якості.'+(result.stale?' Версія застаріла.':'');host.append(title,hint);
  if(!result.warnings.length){const p=document.createElement('p');p.textContent='Підтримуваних мовних ознак не знайдено.';host.append(p)}
  for(const warning of result.warnings){const p=document.createElement('p');p.textContent=`«${warning.quote}» — ${warning.message} (символи ${warning.start+1}–${warning.end})`;host.append(p)}
}
