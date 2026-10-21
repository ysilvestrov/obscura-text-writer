import {api,json,notice} from './api.js';
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
    if(role==='editor')form.insertAdjacentHTML('beforeend','<label>Режим редактора<select name="edit_mode"><option value="prose">Повна літературна версія</option><option value="patches">Точкові мовні правки</option></select></label>');
    if(role==='memory')form.insertAdjacentHTML('beforeend','<label>Режим пам’яті<select name="memory_mode"><option value="evidence_delta">Операції пам’яті v2 за доказами</option><option value="snapshot">Повний snapshot · застарілий, лише додавання</option></select></label>');
    if(role==='editor'||role==='memory'){const hint=document.createElement('p');hint.textContent='Після зміни режиму залиште поле промпту порожнім для відповідного стандартного завдання або адаптуйте власний промпт до нового формату відповіді.';form.append(hint);}
    form.insertAdjacentHTML('beforeend','<fieldset class="venice-options"><legend>Venice</legend><label><input type="checkbox" name="venice_include_system_prompt"> Додавати системний промпт Venice</label><label><input type="checkbox" name="venice_disable_thinking"> Вимкнути thinking (якщо модель підтримує)</label><p>Лише моделі з uncensored=true. Вебпошук вимкнено.</p></fieldset>');
    for(const key of ['venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=config.provider[key]||false;
    const vendorVisibility=()=>{form.querySelector('.venice-options').hidden=form.elements.provider.value!=='venice'};
    form.insertAdjacentHTML('beforeend','<label><input type="checkbox" name="shared_provider"> Застосувати цю модель та її підключення до всіх 4 ролей</label><p>Промпти, режими та ліміти інших ролей зберігаються.</p>');
    const save=document.createElement('button');save.textContent='Зберегти роль';form.append(save);
    form.querySelector('h2').textContent=name;
    if(role==='editor')form.elements.edit_mode.value=config.edit_mode||'prose';
    if(role==='memory')form.elements.memory_mode.value=config.memory_mode||'evidence_delta';
    for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])form.elements[field].value=config[field];
    for(const field of ['provider','base_url','model','timeout','response_mode'])form.elements[field].value=config.provider[field];
    form.elements.include_usage.checked=config.provider.include_usage; const stopLabel=document.createElement('label');stopLabel.textContent='Службові stop-послідовності (до 4, по одній у рядку)';const stopInput=document.createElement('textarea');stopInput.name='stop_sequences';stopInput.rows=2;stopInput.value=(config.stop_sequences||[]).join('\n');stopLabel.append(stopInput);form.insertBefore(stopLabel,save);
    const originalPrompt=snapshot.prompts[role]||'',originalPrepare=snapshot.prepare_prompt||'';
    form.elements.prompt_text.value=originalPrompt;if(role==='planner')form.elements.prepare_prompt_text.value=originalPrepare;
    form.applyProvider=value=>{config.provider=structuredClone(value);for(const key of ['provider','base_url','model','timeout','response_mode'])form.elements[key].value=value[key];for(const key of ['include_usage','venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=value[key]||false;vendorVisibility()};
    vendorVisibility();
    form.elements.provider.onchange=()=>{const selected=form.elements.provider.value;form.elements.base_url.value={local:'http://localhost:1235/v1',openrouter:'https://openrouter.ai/api/v1',venice:'https://api.venice.ai/api/v1'}[selected];form.elements.timeout.value=selected==='local'?3600:180;vendorVisibility()};
    const provider=()=>({...config.provider,provider:form.elements.provider.value,key_env:form.elements.provider.value===config.provider.provider?config.provider.key_env:(form.elements.provider.value==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY'),venice_include_system_prompt:form.elements.venice_include_system_prompt.checked,venice_disable_thinking:form.elements.venice_disable_thinking.checked,model:form.elements.model.value||'discovery-only',base_url:form.elements.base_url.value,timeout:Number(form.elements.timeout.value),response_mode:form.elements.response_mode.value,include_usage:form.elements.include_usage.checked});
    form.querySelector('.discover').onclick=async()=>{try{const result=await api('/api/providers/discover',json('POST',provider()));const list=form.querySelector('datalist');list.replaceChildren();for(const model of result.models){const option=document.createElement('option');option.value=model.id;option.textContent=model.context_tokens?`${model.context_tokens} токенів`:'Контекст невідомий';list.append(option)}notice(`Знайдено моделей: ${result.models.length}. Виберіть точний ID.`)}catch(e){notice(e.message,'error')}};
    form.onsubmit=async event=>{
      event.preventDefault();save.disabled=true;
      try{
        const settings={...config,provider:provider(),stop_sequences:form.elements.stop_sequences.value.split(/\r?\n/).filter(value=>value.length>0)};for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])settings[field]=Number(form.elements[field].value);
        if(role==='editor')settings.edit_mode=form.elements.edit_mode.value;
        if(role==='memory')settings.memory_mode=form.elements.memory_mode.value;
        const body={expected_revision:snapshot.story.revision,role,settings};
        if(form.elements.prompt_text.value!==originalPrompt)body.prompt_text=form.elements.prompt_text.value;
        if(role==='planner'&&form.elements.prepare_prompt_text.value!==originalPrepare)body.prepare_prompt_text=form.elements.prepare_prompt_text.value;
        if(form.elements.shared_provider.checked){body.provider=provider();snapshot.story=await api(`/api/stories/${id}/settings/shared-provider`,json('PUT',body));for(const other of target.querySelectorAll('form[data-role]'))if(other!==form)other.applyProvider(body.provider);await load(role);notice('Модель збережено для всіх 4 ролей')}else{snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',body));await load(role);notice('Роль збережено')};
      }catch(e){notice(e.message,'error')}finally{save.disabled=false}
    };
    const previous=target.querySelector(`[data-role="${role}"]`);if(previous)previous.replaceWith(form);else target.append(form);
  }
}
document.querySelector('#profile-form').onsubmit=async event=>{event.preventDefault();try{const profile=Object.fromEntries(new FormData(event.target));profile.previous_tail_chars=Number(profile.previous_tail_chars);snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',{expected_revision:snapshot.story.revision,profile}));notice('Профіль збережено')}catch(e){notice(e.message,'error')}};
load().catch(e=>notice(e.message,'error'));
