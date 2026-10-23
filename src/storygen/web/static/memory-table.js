export function installMemoryTable({state,api,json,notice,refresh,loadBuffer}){
  const panel=document.querySelector('#memory-view');
  if(!panel)return {active:()=>false,save:async()=>{}};
  const editor=document.querySelector('#editor'),saveButton=document.querySelector('#save-text');
  const node=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
  const help=node('p','Прапорці діють з наступної сцени. Записи й докази залишаються в журналі; прихований запис лишається прихованим після оновлення.');
  const actions=node('div');actions.className='actions';
  const toggle=node('button','JSON для розширеного редагування');toggle.type='button';toggle.className='secondary';
  const reload=node('button','Оновити таблицю');reload.type='button';reload.className='secondary';actions.append(toggle,reload);
  const info=node('p');info.setAttribute('role','status');
  const tools=node('div');tools.className='memory-filters';
  const search=node('input');search.type='search';search.placeholder='Пошук у пам’яті';search.setAttribute('aria-label','Пошук у пам’яті');
  const filter=node('select');filter.setAttribute('aria-label','Категорія пам’яті');
  for(const [value,label] of [['','Усі категорії'],['facts','Факти'],['character_states','Стани персонажів'],['open_threads','Сюжетні лінії'],['timeline','Хронологія']]){const o=node('option',label);o.value=value;filter.append(o);}
  tools.append(search,filter);
  const wrap=node('div');wrap.className='memory-table-wrap';
  const table=node('table');table.className='memory-table';
  const caption=node('caption','Пам’ять після цієї сцени');const head=node('thead'),header=node('tr');
  for(const title of ['Передавати далі','Запис','Категорія','Джерело']){const th=node('th',title);th.scope='col';header.append(th);}
  head.append(header);const body=node('tbody');table.append(caption,head,body);wrap.append(table);
  panel.append(help,actions,info,tools,wrap);
  let key=null,data=null,pending={},advanced=false,loading=false,rawText='',loadedSceneId=null,loadedMemoryId=null;
  const currentKey=()=>`${state.scene?.id}:${state.scene?.heads.memory||''}:${state.bufferEpoch}`;
  const emit=()=>document.dispatchEvent(new CustomEvent('editor-state-changed'));
  const active=()=>state.mode==='memory'&&state.bufferOrigin!=='history'&&!advanced;
  function counts(shown){
    const enabled=data.rows.filter(row=>pending[row.claim_id]??row.forward).length;
    info.textContent=data.reason||`Передаватимуться далі: ${enabled} із ${data.rows.length}. Показано: ${shown}.`;
    if(!data.rows.length&&!data.reason)info.textContent='Пам’ять поки не містить записів.';
  }
  function controls(){
    const visible=state.mode==='memory'&&state.bufferOrigin!=='history';panel.hidden=!visible;
    state.memoryTableActive=visible&&!advanced;editor.hidden=visible&&!advanced;
    tools.hidden=advanced;wrap.hidden=advanced;
    toggle.textContent=advanced?'Таблиця пам’яті':'JSON для розширеного редагування';
    toggle.disabled=state.saving||loading;reload.disabled=state.saving||loading;
    if(visible&&!advanced)saveButton.disabled=loading||state.saving||!data?.can_save||!state.dirty;
    else if(visible&&advanced)saveButton.disabled=loading||state.saving;
  }
  function draw(){
    body.replaceChildren();if(!data){controls();return;}
    const rows=data.rows.filter(row=>(!filter.value||row.category===filter.value)&&`${row.text} ${row.source_title}`.toLocaleLowerCase('uk').includes(search.value.toLocaleLowerCase('uk')));
    counts(rows.length);
    if(!rows.length&&data.rows.length){const tr=node('tr'),td=node('td','За цим пошуком записів немає.');td.colSpan=4;tr.append(td);body.append(tr);}
    for(const row of rows){
      const tr=node('tr'),choice=node('td'),content=node('td'),category=node('td',row.category_label+(row.closed?' · закрито':'')),source=node('td',row.source_scene?`Сцена ${row.source_scene}: ${row.source_title}`:row.source_title);
      const check=node('input');check.type='checkbox';check.checked=pending[row.claim_id]??row.forward;
      check.setAttribute('aria-label',`Передавати далі: ${row.text}`);check.disabled=state.saving||!data.can_save;
      check.onchange=()=>{
        if(state.saving||!data.can_save)return;
        if(check.checked===row.forward)delete pending[row.claim_id];else pending[row.claim_id]=check.checked;
        state.dirty=Object.keys(pending).length>0;
        document.querySelector('#save-state').textContent=state.dirty?'Незбережений вибір пам’яті':'Збережений вибір пам’яті';
        emit();counts(rows.length);controls();
      };
      choice.append(check);content.append(node('p',row.text));
      const proof=node('details');proof.append(node('summary','Показати доказ'),node('p',row.quote));content.append(proof);
      [choice,content,category,source].forEach((td,i)=>td.dataset.label=['Передавати далі','Запис','Категорія','Джерело'][i]);
      tr.append(choice,content,category,source);body.append(tr);
    }
    controls();
  }
  async function load(){
    const captured=currentKey();key=captured;loadedSceneId=state.scene.id;loadedMemoryId=state.scene.heads.memory;data=null;pending={};advanced=false;rawText=editor.value;loading=true;info.textContent='Завантаження пам’яті…';draw();
    try{
      const result=await api(`/api/scenes/${state.scene.id}/memory-view`);
      if(currentKey()!==captured||state.mode!=='memory')return;
      data=result;
      if(result.memory_id!==(state.scene.heads.memory||null))data={...result,can_save:false,reason:'Пам’ять змінилася на сервері. Натисніть «Оновити таблицю».'};
      else if(!state.dirty)state.scene=result.scene;
      draw();
    }catch(error){if(currentKey()===captured)info.textContent=error.message;}
    finally{if(currentKey()===captured){loading=false;controls();}}
  }
  function update(){
    if(state.mode!=='memory'||state.bufferOrigin==='history'){advanced=false;key=null;controls();return;}
    controls();
    const editingSameJson=advanced&&state.scene.id===loadedSceneId&&state.scene.heads.memory===loadedMemoryId;
    if(currentKey()!==key&&!editingSameJson)void load();
  }
  toggle.onclick=()=>{
    if(state.saving||loading)return;
    if(state.dirty&&!confirm('Відкинути незбережені зміни перед перемиканням режиму пам’яті?'))return;
    if(state.dirty){pending={};editor.value=rawText;state.dirty=false;}
    advanced=!advanced;emit();draw();
  };
  reload.onclick=async()=>{
    if(state.saving||loading)return;
    if(state.dirty&&!confirm('Відкинути незбережені зміни та оновити пам’ять?'))return;
    const captured=currentKey();loading=true;controls();
    try{
      const latest=await api(`/api/scenes/${state.scene.id}/memory-view`);
      const text=latest.memory_id?(await api(`/api/versions/${latest.memory_id}`)).text:'';
      if(currentKey()===captured){loading=false;loadBuffer(latest.scene,'memory',text);}
    }catch(error){notice(error.message,'error');}
    finally{loading=false;controls();}
  };
  search.oninput=filter.onchange=draw;
  document.addEventListener('editor-state-changed',update);document.addEventListener('story-refreshed',update);
  return {active,save:async()=>{
    if(state.saving||loading||!state.dirty||!data?.can_save)return;
    const captured=currentKey(),snapshot=data,choices={...pending};state.saving=true;emit();draw();
    try{
      const result=await api(`/api/scenes/${snapshot.scene.id}/memory-view`,json('PUT',{expected_revision:snapshot.expected_revision,fingerprint:snapshot.fingerprint,choices}));
      if(currentKey()===captured){data=result;state.scene=result.scene;pending={};state.dirty=false;document.querySelector('#save-state').textContent='Вибір пам’яті збережено';}
      await refresh();notice('Вибір збережено. Він діятиме з наступної сцени; готові тексти не переписано.');
    }catch(error){notice(error.message,'error');}
    finally{state.saving=false;emit();draw();}
  }};
}
