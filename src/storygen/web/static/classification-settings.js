import {mountConnection} from './settings-connection.js';
export function mountClassification(form,initial){
  const original=structuredClone(initial)||{provider:{provider:'venice',model:'',base_url:'https://api.venice.ai/api/v1',key_env:'VENICE_API_KEY',timeout:300,include_usage:true,response_mode:'json_schema',venice_disable_thinking:true},context_tokens:32768,max_output_tokens:4096,max_input_chars:80000,temperature:0.2};
  const details=document.createElement('details');details.innerHTML='<summary>Необов’язковий класифікатор змін</summary><p>Окремий модельний виклик лише кнопкою «Класифікувати зміни» у перегляді правок.</p><label class="checkbox"><input type="checkbox" name="classification_enabled"> Увімкнути класифікатор</label><fieldset class="classification-fields"><legend>Налаштування класифікатора</legend></fieldset>';form.append(details);
  const toggle=form.elements.classification_enabled,body=details.querySelector('fieldset');toggle.checked=!!initial;
  const connection=mountConnection(body,{value:original.provider,prefix:'classification_',kind:'role'});
  const numeric=document.createElement('div');numeric.className='settings-fields';
  for(const[name,label,min]of [['context_tokens','Контекст, токенів',512],['max_output_tokens','Резерв відповіді, токенів',1],['max_input_chars','Ліміт входу, символів',1],['temperature','Температура',0]]){
    const l=document.createElement('label'),input=document.createElement('input');l.textContent=label;input.name='classification_'+name;input.type='number';input.min=String(min);input.step=name==='temperature'?'any':'1';input.required=true;input.value=String(original[name]);l.append(input);numeric.append(l);
  }body.append(numeric);
  const usageLabel=document.createElement('label');usageLabel.className='checkbox';usageLabel.innerHTML='<input type="checkbox" name="classification_include_usage"> Запитувати usage';body.append(usageLabel);form.elements.classification_include_usage.checked=!!original.provider.include_usage;
  function update(){body.hidden=!toggle.checked;body.disabled=!toggle.checked;connection.update()}
  toggle.addEventListener('change',update);form.addEventListener('settings-reset',update);update();
  return {read(){if(!toggle.checked)return null;const result={...original,provider:{...connection.read(),include_usage:form.elements.classification_include_usage.checked}};for(const name of ['context_tokens','max_output_tokens','max_input_chars','temperature'])result[name]=Number(form.elements['classification_'+name].value);if(result.max_output_tokens>=result.context_tokens)throw new Error('Резерв класифікатора має залишати місце для входу');return result}};
}
