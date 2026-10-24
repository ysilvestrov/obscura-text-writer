export const providerEndpoints={local:'http://localhost:1235/v1',openrouter:'https://openrouter.ai/api/v1',venice:'https://api.venice.ai/api/v1',codex_cli:'http://localhost:1235/v1'};
export function readConnection(original,values,kind='role'){
  const result={...original},evaluator=kind==='evaluator',provider=values.provider;
  Object.assign(result,{provider,model:evaluator&&provider==='codex_cli'&&!values.model?null:values.model,
    base_url:values.base_url||providerEndpoints[provider],response_mode:values.response_mode,
    [evaluator?'api_key_env':'key_env']:values.key_env||(provider==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY'),
    [evaluator?'timeout_seconds':'timeout']:values.timeout===''?null:Number(values.timeout),
    venice_include_system_prompt:!!values.venice_include_system_prompt,venice_disable_thinking:!!values.venice_disable_thinking});
  if(!evaluator)result.venice_reasoning_effort=values.venice_disable_thinking?null:values.venice_reasoning_effort||null;
  return result;
}
export function mountConnection(host,{value,kind='role',prefix='',onChange=()=>{}}){
  let original=structuredClone(value);
  const group=document.createElement('div');group.className='connection-fields';
  group.innerHTML=`<div class="settings-fields"><label>Провайдер<select name="${prefix}provider"><option value="local">Локальний API</option><option value="openrouter">OpenRouter</option><option value="venice">Venice · uncensored=true</option>${kind==='evaluator'?'<option value="codex_cli">Codex CLI</option>':''}</select></label><label>Модель<input name="${prefix}model" maxlength="300"><small>Точний ID; для Codex можна залишити порожнім.</small></label></div><details><summary>Параметри підключення</summary><div class="settings-fields"><label>Base URL<input name="${prefix}base_url"></label><label>Timeout, секунд<input name="${prefix}timeout" type="number" min="0.001" step="any"></label><label>Змінна середовища з ключем<input name="${prefix}key_env"><small>Лише назва змінної, без значення секрету.</small></label><label>Структурована відповідь<select name="${prefix}response_mode"><option value="prompt_json">JSON за промптом</option><option value="json_schema">JSON Schema</option></select></label></div></details><fieldset class="connection-venice"><legend>Venice</legend><label class="checkbox"><input name="${prefix}venice_disable_thinking" type="checkbox"> Вимкнути thinking</label><label class="checkbox"><input name="${prefix}venice_include_system_prompt" type="checkbox"> Додавати системний промпт Venice</label>${kind==='role'?`<label>Reasoning effort<select name="${prefix}venice_reasoning_effort"><option value="">Типове для моделі</option><option>none</option><option>low</option><option>medium</option><option>high</option><option>xhigh</option><option>max</option></select></label>`:''}</fieldset>`;
  host.append(group);
  const field=name=>group.querySelector(`[name="${prefix+name}"]`),names=['provider','model','base_url','timeout','key_env','response_mode','venice_disable_thinking','venice_include_system_prompt',...(kind==='role'?['venice_reasoning_effort']:[])];
  const discover=document.createElement('button'),list=document.createElement('datalist'),status=document.createElement('p');
  discover.type='button';discover.className='secondary';discover.textContent='Отримати список моделей';list.id=prefix+'connection-models';field('model').setAttribute('list',list.id);field('model').parentElement.append(list,discover);status.className='settings-hint';status.setAttribute('role','status');group.append(status);
  discover.onclick=async()=>{
    discover.disabled=true;status.textContent='Завантажуємо каталог…';
    try{
      const {api,json}=await import('./api.js'),values=readConnection(original,Object.fromEntries(names.map(n=>[n,field(n).type==='checkbox'?field(n).checked:field(n).value])),kind);
      const request={provider:values.provider,model:values.model||'discovery-only',base_url:values.base_url,key_env:values.api_key_env??values.key_env,timeout:values.timeout_seconds??values.timeout,response_mode:values.response_mode,venice_include_system_prompt:values.venice_include_system_prompt,venice_disable_thinking:values.venice_disable_thinking};
      const result=await api('/api/providers/discover',json('POST',request));if(values.provider!==field('provider').value||values.base_url!==field('base_url').value){status.textContent='Підключення змінено; завантажте каталог для поточного провайдера.';return}list.replaceChildren();for(const model of result.models){const option=document.createElement('option');option.value=model.id;option.textContent=model.context_tokens?model.context_tokens+' токенів':'Контекст невідомий';list.append(option)}status.textContent=`Знайдено моделей: ${result.models.length}. Оберіть точний ID; ліміти не змінюються автоматично.`;
    }catch(error){status.textContent=error.message}finally{discover.disabled=false}
  };
  function update(){const provider=field('provider').value;group.querySelector('.connection-venice').hidden=provider!=='venice';field('model').required=provider!=='codex_cli';field('base_url').readOnly=provider!=='local';field('key_env').parentElement.hidden=provider==='codex_cli';discover.hidden=provider==='codex_cli';if(kind==='role'){field('venice_reasoning_effort').disabled=field('venice_disable_thinking').checked;if(field('venice_disable_thinking').checked)field('venice_reasoning_effort').value=''}}
  function write(next){original=structuredClone(next);const values={...next,timeout:next[kind==='evaluator'?'timeout_seconds':'timeout'],key_env:next[kind==='evaluator'?'api_key_env':'key_env']};for(const name of names){const el=field(name);if(el.type==='checkbox')el.checked=!!values[name];else el.value=values[name]??(name==='base_url'?providerEndpoints[next.provider]:'')}update()}
  field('provider').addEventListener('change',()=>{const p=field('provider').value;field('base_url').value=providerEndpoints[p];field('timeout').value=p==='local'?3600:180;field('key_env').value=p==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY';list.replaceChildren();update();onChange()});
  group.addEventListener('input',()=>{update();onChange()});group.addEventListener('change',()=>{update();onChange()});write(value);
  return {group,read:()=>readConnection(original,Object.fromEntries(names.map(n=>[n,field(n).type==='checkbox'?field(n).checked:field(n).value])),kind),write,update};
}
