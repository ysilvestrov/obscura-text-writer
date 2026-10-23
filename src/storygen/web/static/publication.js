import {api,json,notice} from './api.js';

const page=document.querySelector('#publication-page');
const storyId=page.dataset.storyId;
const base=`/api/stories/${storyId}/publication`;
const form=document.querySelector('#publication-form');
const save=document.querySelector('#publication-save');
const status=document.querySelector('#publication-status');
const scalar=['title','language','annotation','cycle_title','publication_date','publisher','isbn','rights','source_language'];
let view=null,library=[],authors=[],translators=[],coverId=null,signatureRevisions={};
let dirty=false,busy=false,loading=false,edits=0;
let acceptance=null;
const touched=new Set();

function libraryDirty(){
  return [...document.querySelectorAll('.signature-row input')].some(input=>input.value!==input.dataset.saved)
    || !!document.querySelector('#publication-signature-create').elements.namedItem('display_name').value.trim();
}
function state(message){
  for(const control of form.elements)control.disabled=!view||loading;
  save.disabled=busy||!view||!dirty;
  document.querySelector('#publication-reload').disabled=busy;
  document.querySelector('#publication-cover-upload').disabled=busy||!view;
  document.querySelector('#publication-cover-remove').disabled=busy||!view||!coverId;
  for(const control of document.querySelectorAll('.publication-suggestion-apply'))control.disabled=busy||control.dataset.available!=='true';
  for(const role of ['author','translator']){
    const choice=document.querySelector(`#publication-${role}-choice`);
    document.querySelector(`#publication-${role}-add`).disabled=busy||!view||!choice.value;
  }
  if(message)status.textContent=message;
  else status.textContent=busy?'Зберігаємо…':dirty?'Незбережені зміни в картці':'Картку завантажено';
}
function changed(event){if(event?.target?.name)touched.add(event.target.name);dirty=true;edits++;state();}
function button(text,handler){
  const node=document.createElement('button');node.type='button';node.className='secondary';
  node.textContent=text;node.onclick=handler;return node;
}
function selected(role){return role==='author'?authors:translators;}
function renderPeople(){
  for(const role of ['author','translator']){
    const ids=selected(role),list=document.querySelector(role==='author'?'#publication-authors':'#publication-translators');
    list.replaceChildren();
    ids.forEach((id,index)=>{
      const person=library.find(item=>item.id===id);
      const row=document.createElement('li');const name=document.createElement('span');
      name.textContent=(person?.display_name||'Недоступний підпис')+(person?.archived_at?' (в архіві)':'');
      const actions=document.createElement('div');actions.className='actions';
      const up=button('Вище',()=>{[ids[index-1],ids[index]]=[ids[index],ids[index-1]];changed();renderPeople();});
      up.disabled=index===0||busy;
      const down=button('Нижче',()=>{[ids[index],ids[index+1]]=[ids[index+1],ids[index]];changed();renderPeople();});
      down.disabled=index===ids.length-1||busy;
      const remove=button('Прибрати',()=>{ids.splice(index,1);changed();renderPeople();});remove.disabled=busy;
      actions.append(up,down,remove);row.append(name,actions);list.append(row);
    });
    if(!ids.length){const empty=document.createElement('li');empty.textContent=role==='author'?'Авторів ще не обрано.':'Перекладачів ще не обрано.';list.append(empty);}
    const choice=document.querySelector(`#publication-${role}-choice`);
    choice.replaceChildren(new Option('Оберіть підпис із довідника',''));
    for(const person of library.filter(item=>!item.archived_at&&!ids.includes(item.id)))choice.add(new Option(person.display_name,person.id));
  }
  state();
}
function renderCover(){
  const image=document.querySelector('#publication-cover');
  image.hidden=!coverId;
  if(coverId)image.src=`${base}/covers/${coverId}`;else image.removeAttribute('src');
  document.querySelector('#publication-cover-empty').hidden=!!coverId;
  state();
}
function fill(){
  for(const key of scalar)form.elements.namedItem(key).value=view.card[key]||'';
  form.elements.namedItem('cycle_number').value=view.card.cycle_number??'';
  form.elements.namedItem('keywords').value=view.card.keywords.join('\n');
  for(const option of form.elements.namedItem('genres').options)option.selected=view.card.genres.includes(option.value);
  authors=[...view.card.author_ids];translators=[...view.card.translator_ids];coverId=view.card.cover_id;
  signatureRevisions=Object.fromEntries([...view.authors,...view.translators].map(item=>[item.id,item.revision]));
  dirty=false;renderPeople();renderCover();
  touched.clear();acceptance=null;
}
function collect(){
  const result=Object.fromEntries(scalar.map(key=>[key,form.elements.namedItem(key).value]));
  result.genres=[...form.elements.namedItem('genres').selectedOptions].map(option=>option.value);
  result.keywords=form.elements.namedItem('keywords').value.split(/\r?\n/).map(item=>item.trim()).filter(Boolean);
  const number=form.elements.namedItem('cycle_number').value;
  result.cycle_number=number===''?null:Number(number);
  return {...result,author_ids:[...authors],translator_ids:[...translators],cover_id:coverId};
}
async function refreshLibrary(){
  const response=await api('/api/publication-signatures?include_archived=true');
  library=response.signatures;
  for(const item of library)signatureRevisions[item.id]=item.revision;
  renderLibrary();renderPeople();
}
function renderLibrary(){
  const container=document.querySelector('#publication-signatures');
  const drafts=new Map([...container.querySelectorAll('input[data-id]')].filter(input=>input.value!==input.dataset.saved).map(input=>[input.dataset.id,input.value]));
  container.replaceChildren();
  for(const person of library){
    const row=document.createElement('form');row.className='signature-row';
    const label=document.createElement('label');label.textContent=person.archived_at?'Архівний підпис':'Публічний підпис';
    const input=document.createElement('input');input.value=drafts.get(person.id)??person.display_name;
    input.dataset.saved=person.display_name;input.dataset.id=person.id;input.required=true;input.maxLength=300;
    label.append(input);
    const actions=document.createElement('div');actions.className='actions';
    const apply=button('Зберегти підпис',()=>row.requestSubmit());
    const archive=button(person.archived_at?'Відновити':'В архів',()=>update({archived:!person.archived_at}));
    actions.append(apply,archive);row.append(label,actions);container.append(row);
    async function update(changes){
      if(busy)return;
      busy=true;state();apply.disabled=true;archive.disabled=true;
      try{
        await api('/api/publication-signatures/'+person.id,json('PATCH',{expected_revision:person.revision,...changes}));
        // This explicit edit is reflected in current choices; unrelated form fields survive.
        if(changes.display_name!==undefined)input.dataset.saved=changes.display_name;
        await refreshLibrary();notice('Довідник оновлено.');
      }catch(error){notice(error.message,'error');}
      finally{busy=false;apply.disabled=false;archive.disabled=false;renderPeople();state();}
    }
    row.onsubmit=event=>{event.preventDefault();void update({display_name:input.value});};
  }
  if(!library.length){const empty=document.createElement('p');empty.className='muted';empty.textContent='Додайте ім’я або псевдонім, щоб обрати його для твору.';container.append(empty);}
}
async function load(){
  busy=true;loading=true;state('Завантаження…');
  try{
    const [current,people]=await Promise.all([api(base),api('/api/publication-signatures?include_archived=true')]);
    view=current;library=people.signatures;renderLibrary();fill();
    void refreshSuggestions(true);
  }catch(error){notice(error.message,'error');state('Не вдалося завантажити картку. Спробуйте «Оновити дані».');}
  finally{busy=false;loading=false;renderPeople();state(view?undefined:'Картка недоступна. Спробуйте «Оновити дані».');}
}
form.addEventListener('input',changed);form.addEventListener('change',changed);
form.onsubmit=async event=>{
  event.preventDefault();if(busy||!view||!dirty)return;
  const sequence=edits;const data=collect();busy=true;state();
  const expected=Object.fromEntries([...new Set([...authors,...translators])].map(id=>[id,signatureRevisions[id]]));
  try{
    const suggestion=acceptance&&{...acceptance,fields:acceptance.fields.filter(key=>Array.isArray(data[key])?data[key].length:!!data[key]?.trim())};
    view=await api(base,json('PUT',{expected_revision:view.card.revision,data,expected_signature_revisions:expected,...(suggestion?.fields.length?{suggestion}:{})}));
    acceptance=null;
    if(sequence===edits)fill();
    void refreshSuggestions(true);
    notice(sequence===edits?'Картку публікації збережено.':'Попередні значення збережено; нові правки залишилися у формі.');
  }catch(error){notice(error.message,'error');}
  finally{busy=false;renderPeople();state();}
};
for(const role of ['author','translator']){
  const choice=document.querySelector(`#publication-${role}-choice`);
  choice.onchange=()=>state();
  document.querySelector(`#publication-${role}-add`).onclick=()=>{
    if(!view||busy||!choice.value)return;
    const ids=selected(role);if(ids.length>=20){notice('Можна обрати до 20 підписів.','error');return;}
    const person=library.find(item=>item.id===choice.value);
    ids.push(person.id);signatureRevisions[person.id]=person.revision;changed();renderPeople();
  };
}
document.querySelector('#publication-signature-create').onsubmit=async event=>{
  event.preventDefault();if(busy)return;const node=event.currentTarget;const input=node.elements.namedItem('display_name');const original=input.value;
  busy=true;node.querySelector('button').disabled=true;state();
  try{await api('/api/publication-signatures',json('POST',{display_name:original}));if(input.value===original)input.value='';await refreshLibrary();notice('Підпис додано. Тепер його можна обрати для твору.');}
  catch(error){notice(error.message,'error');}
  finally{busy=false;node.querySelector('button').disabled=false;renderPeople();state();}
};
document.querySelector('#publication-cover-form').onsubmit=async event=>{
  event.preventDefault();if(busy||!view)return;
  const node=event.currentTarget,file=node.elements.namedItem('file').files[0];if(!file)return;
  if(file.size>10*1024*1024){notice('Обкладинка має бути до 10 MiB.','error');return;}
  const body=new FormData();body.append('file',file);busy=true;state('Завантажуємо обкладинку…');
  try{const asset=await api(base+'/cover',{method:'POST',body});coverId=asset.id;changed();renderCover();notice('Обкладинку завантажено. Збережіть картку, щоб застосувати її.');}
  catch(error){notice(error.message,'error');}
  finally{busy=false;renderPeople();state();}
};
document.querySelector('#publication-cover-remove').onclick=()=>{if(!busy){coverId=null;changed();renderCover();}};
document.querySelector('#publication-reload').onclick=()=>{
  if(busy)return;
  if((dirty||libraryDirty())&&!confirm('Відкинути незбережені правки й завантажити актуальні дані?'))return;
  // Explicit discard also clears drafts in the shared dictionary.
  document.querySelector('#publication-signatures').replaceChildren();void load();
};
window.addEventListener('beforeunload',event=>{if(dirty||libraryDirty()){event.preventDefault();event.returnValue='';}});

const suggest=document.querySelector('#publication-suggest');
const suggestCancel=document.querySelector('#publication-suggest-cancel');
const suggestStatus=document.querySelector('#publication-suggest-status');
let suggestionBusy=false,activeSuggestion=null,readiness=null,pollTimer=null;
const fieldLabels={title:'Назва',annotation:'Анотація',genres:'Жанри',keywords:'Ключові слова'};
function suggestionControls(){
  suggest.disabled=suggestionBusy||!!activeSuggestion||!readiness?.ready;
  suggestCancel.hidden=!activeSuggestion;
  suggestCancel.disabled=suggestionBusy;
}
async function refreshSuggestions(checkReady=false){
  if(!suggest)return;
  try{
    const response=await api(base+'/suggestions');
    activeSuggestion=response.active_runs[0]||null;
    if(checkReady||!activeSuggestion)readiness=await api(base+'/suggestions/readiness');
    const history=document.querySelector('#publication-suggestion-history');history.replaceChildren();
    for(const item of response.history){const line=document.createElement('p');line.textContent=`${item.created_at} · ${item.state}${item.error?' · '+item.error:''}${item.warnings?.length?' · '+item.warnings.join(' '):''}`;history.append(line);}
    if(!response.history.length)history.textContent='Пропозицій ще не було.';
    const container=document.querySelector('#publication-suggestions');container.replaceChildren();
    for(const proposal of response.proposals){
      const details=document.createElement('details');
      const summary=document.createElement('summary');summary.textContent=`${proposal.created_at} · ${proposal.model}`;details.append(summary);
      for(const message of proposal.warnings||[]){const warning=document.createElement('p');warning.className='muted';warning.textContent=message;details.append(warning);}
      for(const [key,value] of Object.entries(proposal.suggestions)){
        const line=document.createElement('p');
        const label=document.createElement('strong');label.textContent=fieldLabels[key]+': ';
        const text=document.createElement('span');
        text.textContent=key==='genres'?value.map(code=>[...form.elements.namedItem('genres').options].find(o=>o.value===code)?.textContent||code).join(', '):Array.isArray(value)?value.join(', '):value;
        line.append(label,text);details.append(line);
      }
      const apply=button('Заповнити порожні поля',()=>{
        if(busy||suggestionBusy)return;
        const current=collect(),applied=[];
        if(acceptance&&acceptance.attempt_id!==proposal.attempt_id){notice('Спочатку збережіть попередню пропозицію або відкиньте її через «Оновити дані».','error');return;}
        for(const key of proposal.available_fields){
          if(touched.has(key)||(Array.isArray(current[key])?current[key].length:current[key]?.trim())||(key==='title'&&view.effective_title.trim()))continue;
          const value=proposal.suggestions[key];
          if(key==='genres'){for(const option of form.elements.namedItem(key).options)option.selected=value.includes(option.value);}
          else form.elements.namedItem(key).value=Array.isArray(value)?value.join('\n'):value;
          applied.push(key);touched.add(key);
        }
        if(!applied.length){notice('Порожніх незмінених полів для цієї пропозиції немає.');return;}
        acceptance={attempt_id:proposal.attempt_id,fingerprint:proposal.fingerprint,fields:[...new Set([...(acceptance?.fields||[]),...applied])]};
        changed();notice('Поля заповнено у формі. Перевірте їх і збережіть картку.');
      });
      apply.className+=' publication-suggestion-apply';apply.dataset.available=String(proposal.can_apply&&!suggestionBusy);
      apply.disabled=busy||!proposal.can_apply||suggestionBusy;details.append(apply);
      if(proposal.reason){const warning=document.createElement('p');warning.textContent=proposal.reason;details.append(warning);}
      container.append(details);
    }
    const last=response.history[0];
    suggestStatus.textContent=activeSuggestion?`Запуск: ${activeSuggestion.state}${activeSuggestion.error?' · '+activeSuggestion.error:''}`:
      last?.state==='failed'?`Помилка: ${last.error}`:last?.warnings?.length?`Пропозицію збережено з попередженням: ${last.warnings.join(' ')}`:readiness?.ready?`Готово · ${readiness.roles.planner.model} · один виклик` :readiness?.reason||'Немає готового тексту';
    clearTimeout(pollTimer);
    if(activeSuggestion&&['queued','running','pause_requested','cancellation_requested'].includes(activeSuggestion.state))pollTimer=setTimeout(()=>void refreshSuggestions(),1500);
  }catch(error){suggestStatus.textContent=error.message;readiness=null;}
  finally{suggestionControls();}
}
if(suggest){
  suggest.onclick=async()=>{
    if(suggest.disabled)return;suggestionBusy=true;suggestionControls();
    try{await api('/api/runs',json('POST',{request:{story_id:storyId,mode:'publication_suggest'},request_id:crypto.randomUUID()}));await refreshSuggestions(true);}
    catch(error){suggestStatus.textContent=error.message;notice(error.message,'error');}
    finally{suggestionBusy=false;suggestionControls();}
  };
  suggestCancel.onclick=async()=>{
    if(!activeSuggestion||suggestionBusy)return;suggestionBusy=true;suggestionControls();
    try{await api(`/api/runs/${activeSuggestion.id}/cancel`,json('POST',{}));await refreshSuggestions(true);}
    catch(error){notice(error.message,'error');}
    finally{suggestionBusy=false;suggestionControls();}
  };
}
void load();
