import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
import {CharacterBuffer} from './characters-state.js';

const host=document.querySelector('#context-content');
if(host){
  const buffer=new CharacterBuffer(),panel=document.createElement('details');panel.className='character-editor';
  const summary=document.createElement('summary');summary.textContent='Доступність відомостей персонажів';panel.append(summary);host.after(panel);
  const help=document.createElement('p');help.textContent='Позначте, зі сцени якої письменник може бачити відомість. Непозначені описи дають попередження. Ці мітки не перевіряють канон, промпти та інші вказівки.';panel.append(help);
  const form=document.createElement('form'),list=document.createElement('div'),status=document.createElement('p');status.setAttribute('role','status');
  const tools=document.createElement('div');tools.className='actions';
  const button=(text,fn)=>{const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=text;b.onclick=fn;return b};
  const save=document.createElement('button');save.type='submit';save.textContent='Зберегти відомості';
  const add=button('Додати персонажа',()=>{buffer.cards.push({id:null,schema_version:2,name:'',entries:[]});changed();render()});
  const reload=button('Перезавантажити',()=>load(true));tools.append(save,add,reload);form.append(list,tools,status);panel.append(form);
  const source=document.createElement('details'),sourceTitle=document.createElement('summary'),sourceText=document.createElement('pre');sourceTitle.textContent='Вихідний опис для звірки';sourceText.className='character-preview';source.append(sourceTitle,sourceText);panel.append(source);
  const previewLabel=document.createElement('label');previewLabel.textContent='Перегляд для сцени';
  const previewScene=document.createElement('select');previewLabel.append(previewScene);
  const preview=button('Що побачить письменник',showPreview),previewInfo=document.createElement('p'),previewText=document.createElement('pre');previewText.className='character-preview';previewInfo.setAttribute('role','status');panel.append(previewLabel,preview,previewInfo,previewText);
  let metadata=null,previewBusy=false;
  const url=()=>`/api/stories/${state.storyId}/characters`;
  function update(){
    save.disabled=buffer.saving||!buffer.dirty||buffer.revision===null;add.disabled=buffer.saving||buffer.revision===null;
    reload.disabled=buffer.saving;preview.disabled=buffer.saving||previewBusy||!previewScene.value||buffer.revision===null;
    list.querySelectorAll('fieldset').forEach(field=>field.disabled=buffer.saving);
    state.characterDirty=buffer.dirty||buffer.saving;
    document.dispatchEvent(new CustomEvent('editor-state-changed'));
  }
  function changed(){buffer.changed();status.textContent='Незбережені відомості';previewInfo.textContent='Відомості змінено — оновіть перегляд.';previewText.textContent='';update()}
  function field(label,value,oninput,tag='input'){
    const wrapper=document.createElement('label');wrapper.textContent=label;
    const input=document.createElement(tag);input.value=value||'';input.required=true;
    if(tag==='textarea')input.rows=3;
    input.oninput=()=>{oninput(input.value);changed()};wrapper.append(input);return wrapper;
  }
  function render(){
    list.replaceChildren();
    if(!buffer.cards.length){const p=document.createElement('p');p.textContent='Карток ще немає. Додайте персонажа або застосуйте підготовлену структуру; старий вихідний опис лишається неперевіреним.';list.append(p)}
    buffer.cards.forEach((card,cardIndex)=>{
      const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent=card.name||'Новий персонаж';group.append(legend);
      group.append(field('Ім’я',card.name,value=>{card.name=value;legend.textContent=value||'Новий персонаж'}));
      if(card.id){const id=document.createElement('small');id.textContent='Ідентифікатор для складу сцен: '+card.id;group.append(id)}
      card.entries.forEach((entry,index)=>{
        const row=document.createElement('div');row.className='character-entry';
        row.append(field('Відомість',entry.text,value=>{entry.text=value;split.disabled=entry.text.split(/\n\s*\n/).filter(s=>s.trim()).length<2},'textarea'));
        const availability=document.createElement('label');availability.textContent='Коли можна передавати письменнику';const mode=document.createElement('select');
        for(const [value,text]of Object.entries({unclassified:'Час не перевірено',timeless:'Від самого початку',from_scene:'Починаючи зі сцени'})){const opt=document.createElement('option');opt.value=value;opt.textContent=text;mode.append(opt)}
        mode.value=entry.availability;availability.append(mode);row.append(availability);
        const sceneLabel=document.createElement('label');sceneLabel.textContent='Перша сцена доступності';const sceneSelect=document.createElement('select');
        const empty=document.createElement('option');empty.value='';empty.textContent='Оберіть сцену';sceneSelect.append(empty);
        for(const scene of metadata?.scenes||[]){const opt=document.createElement('option');opt.value=scene.id;opt.textContent=`${scene.position+1}. ${scene.title}`;sceneSelect.append(opt)}
        sceneSelect.value=entry.available_from_scene_id||'';sceneLabel.append(sceneSelect);row.append(sceneLabel);
        const scopeVisibility=()=>{sceneLabel.hidden=mode.value!=='from_scene';sceneSelect.disabled=sceneLabel.hidden;sceneSelect.required=!sceneLabel.hidden};scopeVisibility();
        mode.onchange=()=>{entry.availability=mode.value;entry.available_from_scene_id=mode.value==='from_scene'?(sceneSelect.value||null):null;scopeVisibility();changed()};
        sceneSelect.onchange=()=>{entry.available_from_scene_id=sceneSelect.value||null;changed()};
        const originLabel=document.createElement('label');originLabel.textContent='Походження';const origin=document.createElement('select');
        for(const [value,text]of Object.entries({author:'Авторське твердження',imported:'Імпортоване з джерелами'})){const opt=document.createElement('option');opt.value=value;opt.textContent=text;opt.disabled=value==='imported'&&!entry.sources?.length;origin.append(opt)}
        origin.value=entry.origin;origin.onchange=()=>{entry.origin=origin.value;changed()};originLabel.append(origin);row.append(originLabel);
        const evidence=document.createElement('small');evidence.textContent=entry.sources?.length?`Збережено джерел: ${entry.sources.length}.`:'Авторське твердження без документального підтвердження.';row.append(evidence);
        const actions=document.createElement('div');actions.className='actions';
        const split=button('Розділити за абзацами',()=>{const parts=entry.text.split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean);if(parts.length<2)return;card.entries.splice(index,1,...parts.map((text,i)=>({...structuredClone(entry),id:i===0?entry.id:null,text})));changed();render()});
        split.disabled=entry.text.split(/\n\s*\n/).filter(s=>s.trim()).length<2;
        actions.append(split,button('Прибрати відомість',()=>{card.entries.splice(index,1);changed();render()}));row.append(actions);group.append(row);
      });
      const actions=document.createElement('div');actions.className='actions';
      actions.append(button('Додати відомість',()=>{card.entries.push({id:null,text:'',availability:'unclassified',available_from_scene_id:null,origin:'author',sources:[]});changed();render()}),button('Прибрати картку',()=>{buffer.cards.splice(cardIndex,1);changed();render()}));group.append(actions);list.append(group);
    });update();
  }
  async function load(force=false){
    if(buffer.saving)return;
    if(buffer.dirty&&!force)return;
    if(buffer.dirty&&force&&!confirm('Скинути незбережені відомості й завантажити серверну версію?'))return;
    const epoch=buffer.epoch,token=buffer.beginLoad();
    try{
      const data=await api(url());
      if(force&&epoch===buffer.epoch)buffer.dirty=false;
      if(!buffer.loaded(data,token))return;
      metadata=data;status.textContent=data.warnings.join(' ')||'Збережені відомості';source.hidden=!data.source;sourceText.textContent=data.source?.text||'';
      const selected=previewScene.value;previewScene.replaceChildren();
      for(const scene of data.scenes){const opt=document.createElement('option');opt.value=scene.id;opt.textContent=`${scene.position+1}. ${scene.title}`;previewScene.append(opt)}
      if(data.scenes.some(s=>s.id===selected))previewScene.value=selected;else if(state.scene)previewScene.value=state.scene.id;
      render();
    }catch(error){status.textContent=error.message;notice(error.message,'error');update()}
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(!form.reportValidity()||buffer.saving)return;
    const snapshot=buffer.beginSave();update();
    try{
      const data=await api(url(),json('PUT',{cards:snapshot.cards,expected_revision:snapshot.expected_revision}));
      if(buffer.saved(data,snapshot)){metadata=data;status.textContent='Відомості збережено';render();notice('Доступність відомостей збережено')}
      else{status.textContent='Сервер зберіг попередню правку. Нові локальні зміни збережіть окремо перед перезавантаженням.';notice(status.textContent,'warning')}
      await refresh();
    }catch(error){buffer.failed();status.textContent=error.message;notice(error.message,'error')}
    finally{update()}
  };
  async function showPreview(){
    if(!form.reportValidity())return;
    const request=buffer.previewRequest(previewScene.value);previewBusy=true;previewInfo.textContent='Формуємо перегляд…';update();
    try{
      const result=await api(url()+'/preview',json('POST',{cards:structuredClone(buffer.cards),scene_id:request.scene_id}));
      if(!buffer.previewCurrent(request,previewScene.value))return;
      previewText.textContent=result.text||'Для цієї сцени немає доступних відомостей.';
      previewInfo.textContent=`Виключено майбутніх відомостей: ${result.excluded_count}. `+result.warnings.join(' ');
    }catch(error){if(buffer.previewCurrent(request,previewScene.value)){previewInfo.textContent=error.message;notice(error.message,'error')}}
    finally{previewBusy=false;update()}
  }
  previewScene.onchange=()=>{buffer.previewToken++;previewText.textContent='';previewInfo.textContent='Оновіть перегляд для вибраної сцени.'};
  document.addEventListener('story-refreshed',()=>load());
  document.addEventListener('scene-selected',()=>{if(state.scene&&[...previewScene.options].some(o=>o.value===state.scene.id))previewScene.value=state.scene.id;buffer.previewToken++;previewText.textContent=''});
  globalThis.addEventListener('beforeunload',event=>{if(buffer.dirty||buffer.saving){event.preventDefault();event.returnValue=''}});
  load();
}
