import {api,json,notice} from './api.js';
import {mountHorizonControls} from './horizon-controls.js';
const root=document.querySelector('[data-story-id]'),id=root.dataset.storyId;
const names={planner:'Планувальник',writer:'Письменник',editor:'Літературний редактор',memory:'Пам’ять'};
const defaults={provider:{provider:'local',base_url:'http://localhost:1235/v1',model:'',timeout:3600,key_env:'OPENROUTER_API_KEY',include_usage:false,response_mode:'prompt_json'},context_tokens:8192,max_output_tokens:2048,max_input_chars:80000,temperature:0.7,prompt_version_id:null,prepare_prompt_version_id:null};
let snapshot;
async function load(onlyRole=null){
  snapshot=await api(`/api/stories/${id}/settings`);
  const profileForm=document.querySelector('#profile-form');if(!onlyRole)for(const[key,value]of Object.entries(snapshot.profile))profileForm.elements[key].value=value;
  const target=document.querySelector('#role-settings');if(!onlyRole)target.replaceChildren();
  for(const[role,name]of Object.entries(names)){
    if(onlyRole&&role!==onlyRole)continue;
    const config=snapshot.roles[role]||structuredClone(defaults),form=document.createElement('form');form.className='panel';form.dataset.role=role;
    form.innerHTML='<h2></h2><label>Провайдер<select name="provider"><option value="local">Локальний API</option><option value="openrouter">OpenRouter</option><option value="venice">Venice · uncensored=true</option></select></label><label>Base URL<input name="base_url" required></label><label>Model ID<input name="model" required list="models-'+role+'"></label><datalist id="models-'+role+'"></datalist><button type="button" class="secondary discover">Отримати список моделей</button><label>Перевірений контекст, токенів<input name="context_tokens" type="number" min="512" required></label><label>Резерв відповіді, токенів<input name="max_output_tokens" type="number" min="1" required></label><label>Операційний ліміт входу, символів<input name="max_input_chars" type="number" min="1" required></label><label>Температура<input name="temperature" type="number" min="0" max="2" step="0.05"></label><label>Timeout, секунд<input name="timeout" type="number" min="1"></label><label>Структуровані відповіді<select name="response_mode"><option value="prompt_json">JSON за промптом</option><option value="json_schema">JSON Schema (endpoint має підтримувати)</option></select></label><label><input name="include_usage" type="checkbox"> Запитувати usage потоку (якщо підтримується)</label><label>Промпт ролі<textarea name="prompt_text" rows="4" placeholder="Стандартний промпт, якщо поле порожнє"></textarea></label>';
    if(role==='planner')form.insertAdjacentHTML('beforeend','<label>Окремий промпт підготовки структури<textarea name="prepare_prompt_text" rows="4" placeholder="Стандартний промпт підготовки"></textarea></label>');
    if(role==='editor')form.insertAdjacentHTML('beforeend','<label>Режим редактора<select name="edit_mode"><option value="prose">Повна літературна версія</option><option value="patches">Точкові мовні правки</option><option value="diff">Редактура з переглядом змін</option></select></label><p>Режим перегляду повертає звичайний текст без JSON Schema. Програма виділяє зміни й завжди чекає авторського рішення.</p>');
    if(role==='editor')form.insertAdjacentHTML('beforeend','<label>Застосування точкових правок<select name="edit_review"><option value="auto">Автоматично після перевірки</option><option value="review">Спочатку перегляд автором</option></select></label><p>Перегляд стосується точкових правок. Workflow чекатиме на вибір і явне продовження.</p>');
    if(role==='memory')form.insertAdjacentHTML('beforeend','<label>Режим пам’яті<select name="memory_mode"><option value="evidence_delta">Операції пам’яті v2 за доказами</option><option value="snapshot">Повний snapshot · застарілий, лише додавання</option></select></label>');
    if(role==='editor'||role==='memory'){const hint=document.createElement('p');hint.textContent='Після зміни режиму залиште поле промпту порожнім для відповідного стандартного завдання або адаптуйте власний промпт до нового формату відповіді.';form.append(hint);}
    const horizonControls=mountHorizonControls(form,role,config);
    form.insertAdjacentHTML('beforeend','<fieldset class="venice-options"><legend>Venice</legend><label><input type="checkbox" name="venice_include_system_prompt"> Додавати системний промпт Venice</label><label><input type="checkbox" name="venice_disable_thinking"> Вимкнути thinking (якщо модель підтримує)</label><p>Лише моделі з uncensored=true. Вебпошук вимкнено.</p></fieldset>');
    form.querySelector('.venice-options').insertAdjacentHTML('beforeend','<label>Reasoning effort<select name="venice_reasoning_effort"><option value="">Типове для моделі</option><option value="none">none</option><option value="low">low</option><option value="medium">medium</option><option value="high">high</option><option value="xhigh">xhigh</option><option value="max">max</option></select></label><p>Залежить від моделі. Виберіть або effort, або вимкнення thinking.</p>');
    for(const key of ['venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=config.provider[key]||false;
    form.elements.venice_reasoning_effort.value=config.provider.venice_reasoning_effort||'';
    const updateEffort=()=>{form.elements.venice_reasoning_effort.disabled=form.elements.venice_disable_thinking.checked;if(form.elements.venice_disable_thinking.checked)form.elements.venice_reasoning_effort.value=''};
    form.elements.venice_disable_thinking.onchange=updateEffort;updateEffort();
    if(role==='editor'){
      const details=document.createElement('details'),heading=document.createElement('summary'),hint=document.createElement('p'),label=document.createElement('label'),input=document.createElement('textarea'),example=document.createElement('button');
      heading.textContent='Необов’язковий класифікатор змін';hint.textContent='Окремий модельний виклик лише кнопкою в перегляді правок. Порожнє поле вимикає його. Поради моделі не підтверджують правильності змін. Ключі задаються через key_env, не вставляйте секрети в JSON.';
      label.textContent='Профіль класифікатора (JSON)';input.name='classification_json';input.rows=10;input.spellcheck=false;input.value=config.classification?JSON.stringify(config.classification,null,2):'';label.append(input);
      example.type='button';example.className='secondary';example.textContent='Заповнити приклад Venice';example.onclick=()=>{input.value=JSON.stringify({provider:{provider:'venice',model:'qwen-3-8-27b',timeout:300,key_env:'VENICE_API_KEY',include_usage:true,response_mode:'json_schema',venice_disable_thinking:true},context_tokens:32768,max_output_tokens:4096,max_input_chars:80000,temperature:0.2},null,2)};
      details.append(heading,hint,label,example);form.append(details);
    }
    const vendorVisibility=()=>{form.querySelector('.venice-options').hidden=form.elements.provider.value!=='venice'};
    form.insertAdjacentHTML('beforeend','<label><input type="checkbox" name="shared_provider"> Застосувати цю модель та її підключення до всіх 4 ролей</label><p>Промпти, режими та ліміти інших ролей зберігаються.</p>');
    const save=document.createElement('button');save.textContent='Зберегти роль';form.append(save);
    form.querySelector('h2').textContent=name;
    if(role==='editor')form.elements.edit_mode.value=config.edit_mode||'prose';
    if(role==='editor')form.elements.edit_review.value=config.edit_review||'auto';
    if(role==='memory')form.elements.memory_mode.value=config.memory_mode||'evidence_delta';
    for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])form.elements[field].value=config[field];
    for(const field of ['provider','base_url','model','timeout','response_mode'])form.elements[field].value=config.provider[field];
    form.elements.include_usage.checked=config.provider.include_usage; const stopLabel=document.createElement('label');stopLabel.textContent='Службові stop-послідовності (до 4, по одній у рядку)';const stopInput=document.createElement('textarea');stopInput.name='stop_sequences';stopInput.rows=2;stopInput.value=(config.stop_sequences||[]).join('\n');stopLabel.append(stopInput);form.insertBefore(stopLabel,save);
    const originalPrompt=snapshot.prompts[role]||'',originalPrepare=snapshot.prepare_prompt||'';
    form.elements.prompt_text.value=originalPrompt;if(role==='planner')form.elements.prepare_prompt_text.value=originalPrepare;
    const contract=document.createElement('p');contract.className='muted';form.elements.prompt_text.parentElement.after(contract);
    const assignment=document.createElement('label');const assignInput=document.createElement('input');assignInput.type='checkbox';assignInput.name='confirm_prompt_contract';assignment.append(assignInput,document.createTextNode('Я адаптував власний промпт і призначаю його вибраному етапу та режиму'));contract.after(assignment);
    const reset=document.createElement('button');reset.type='button';reset.className='secondary';reset.textContent='Повернути стандартний промпт';assignment.after(reset);reset.onclick=()=>{form.elements.prompt_text.value='';assignInput.checked=false;updateContract()};
    const stage={planner:'brief',writer:'draft',editor:'edit',memory:'memory'}[role];
    function updateContract(){const mode=role==='editor'?form.elements.edit_mode.value:role==='memory'?form.elements.memory_mode.value:role==='planner'?'brief':'prose';const expected=`${stage}/${mode}/${mode==='evidence_delta'?2:1}`;const stored=snapshot.prompt_contracts?.[role];const saved=config.prompt_version_id?(stored?`${stored.stage}/${stored.mode}/${stored.schema_version}`:'не призначено'):'стандартний';contract.textContent=`Потрібне призначення: ${expected}. Збережений промпт: ${saved}. Новий текст призначається під час збереження.`}
    for(const field of ['edit_mode','memory_mode'])if(form.elements[field])form.elements[field].onchange=()=>{if(!config.prompt_version_id&&form.elements.prompt_text.value===originalPrompt)form.elements.prompt_text.value='';assignInput.checked=false;updateContract()};
    form.elements.prompt_text.addEventListener('input',updateContract);updateContract();
    if(role==='planner'){const prepareAssignment=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.name='confirm_prepare_prompt_contract';prepareAssignment.append(input,document.createTextNode('Призначити власний промпт підготовки контракту prepare/blueprint/1'));form.elements.prepare_prompt_text.parentElement.after(prepareAssignment)}
    form.applyProvider=value=>{config.provider=structuredClone(value);for(const key of ['provider','base_url','model','timeout','response_mode'])form.elements[key].value=value[key];for(const key of ['include_usage','venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=value[key]||false;form.elements.venice_reasoning_effort.value=value.venice_reasoning_effort||'';updateEffort();vendorVisibility()};
    if(role==='editor'){
      const updateReview=()=>{const manual=form.elements.edit_mode.value==='diff';form.elements.edit_review.disabled=manual;if(manual)form.elements.edit_review.value='review'};
      const previous=form.elements.edit_mode.onchange;form.elements.edit_mode.onchange=()=>{previous?.();updateReview()};updateReview();
    }
    vendorVisibility();
    form.elements.provider.onchange=()=>{const selected=form.elements.provider.value;form.elements.base_url.value={local:'http://localhost:1235/v1',openrouter:'https://openrouter.ai/api/v1',venice:'https://api.venice.ai/api/v1'}[selected];form.elements.timeout.value=selected==='local'?3600:180;vendorVisibility()};
    const provider=()=>({...config.provider,provider:form.elements.provider.value,key_env:form.elements.provider.value===config.provider.provider?config.provider.key_env:(form.elements.provider.value==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY'),venice_include_system_prompt:form.elements.venice_include_system_prompt.checked,venice_disable_thinking:form.elements.venice_disable_thinking.checked,venice_reasoning_effort:form.elements.venice_reasoning_effort.value||null,model:form.elements.model.value||'discovery-only',base_url:form.elements.base_url.value,timeout:Number(form.elements.timeout.value),response_mode:form.elements.response_mode.value,include_usage:form.elements.include_usage.checked});
    form.querySelector('.discover').onclick=async()=>{try{const result=await api('/api/providers/discover',json('POST',provider()));const list=form.querySelector('datalist');list.replaceChildren();for(const model of result.models){const option=document.createElement('option');option.value=model.id;option.textContent=model.context_tokens?`${model.context_tokens} токенів`:'Контекст невідомий';list.append(option)}notice(`Знайдено моделей: ${result.models.length}. Виберіть точний ID.`)}catch(e){notice(e.message,'error')}};
    form.onsubmit=async event=>{
      event.preventDefault();save.disabled=true;
      try{
        const settings={...config,...horizonControls.read(),provider:provider(),stop_sequences:form.elements.stop_sequences.value.split(/\r?\n/).filter(value=>value.length>0)};for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])settings[field]=Number(form.elements[field].value);
        if(role==='editor')settings.edit_mode=form.elements.edit_mode.value;
        if(role==='editor')settings.edit_review=form.elements.edit_review.value;
        if(role==='editor'){
          try{settings.classification=form.elements.classification_json.value.trim()?JSON.parse(form.elements.classification_json.value):null}
          catch{throw new Error('Профіль класифікатора: некоректний JSON')}
        }
        if(role==='memory')settings.memory_mode=form.elements.memory_mode.value;
        const body={expected_revision:snapshot.story.revision,role,settings};
        body.confirm_prompt_contract=form.elements.confirm_prompt_contract.checked;
        if(role==='planner')body.confirm_prepare_prompt_contract=form.elements.confirm_prepare_prompt_contract.checked;
        if(form.elements.prompt_text.value!==originalPrompt)body.prompt_text=form.elements.prompt_text.value;
        if(role==='planner'&&form.elements.prepare_prompt_text.value!==originalPrepare)body.prepare_prompt_text=form.elements.prepare_prompt_text.value;
        if(form.elements.shared_provider.checked){body.provider=provider();snapshot.story=await api(`/api/stories/${id}/settings/shared-provider`,json('PUT',body));for(const other of target.querySelectorAll('form[data-role]'))if(other!==form)other.applyProvider(body.provider);await load(role);notice('Модель збережено для всіх 4 ролей')}else{snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',body));await load(role);notice('Роль збережено')};
      }catch(e){notice(e.message,'error')}finally{save.disabled=false}
    };
    horizonControls.update();
    const previous=target.querySelector(`[data-role="${role}"]`);if(previous)previous.replaceWith(form);else target.append(form);
  }
}
document.querySelector('#profile-form').onsubmit=async event=>{event.preventDefault();try{const profile=Object.fromEntries(new FormData(event.target));profile.previous_tail_chars=Number(profile.previous_tail_chars);snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',{expected_revision:snapshot.story.revision,profile}));notice('Профіль збережено')}catch(e){notice(e.message,'error')}};
load().catch(e=>notice(e.message,'error'));
