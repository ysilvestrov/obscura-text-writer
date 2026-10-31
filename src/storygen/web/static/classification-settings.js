import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {mountConnection} from './settings-connection.js';
export function mountClassification(form,initial){
  const original=structuredClone(initial)||{provider:{provider:'venice',model:'',base_url:'https://api.venice.ai/api/v1',key_env:'VENICE_API_KEY',timeout:300,include_usage:true,response_mode:'json_schema',venice_disable_thinking:true},context_tokens:32768,max_output_tokens:4096,max_input_chars:80000,temperature:0.2};
  const details=document.createElement('details');uiHTML(details,"<summary><span data-i18n=\"m_35b95f1a33d3\">Необов’язковий класифікатор змін</span></summary><p><span data-i18n=\"m_45d30a22598a\">Окремий модельний виклик лише кнопкою «Класифікувати зміни» у перегляді правок.</span></p><label class=\"checkbox\"><input type=\"checkbox\" name=\"classification_enabled\"> <span data-i18n=\"m_637368184a26\">Увімкнути класифікатор</span></label><fieldset class=\"classification-fields\"><legend><span data-i18n=\"m_b3ef781fc1aa\">Налаштування класифікатора</span></legend></fieldset>",{});form.append(details);
  const toggle=form.elements.classification_enabled,body=details.querySelector('fieldset');toggle.checked=!!initial;
  const connection=mountConnection(body,{value:original.provider,prefix:'classification_',kind:'role'});
  const numeric=document.createElement('div');numeric.className='settings-fields';
  for(const[name,label,min]of [['context_tokens',msg("m_526a85b7766b"),512],['max_output_tokens',msg("m_11de327806c2"),1],['max_input_chars',msg("m_a1adc1cec8e7"),1],['temperature',msg("m_56f7653b8834"),0]]){
    const l=document.createElement('label'),input=document.createElement('input');uiText(l,"textContent",()=>(label));input.name='classification_'+name;input.type='number';input.min=String(min);input.step=name==='temperature'?'any':'1';input.required=true;input.value=String(original[name]);l.append(input);numeric.append(l);
  }body.append(numeric);
  const usageLabel=document.createElement('label');usageLabel.className='checkbox';uiHTML(usageLabel,"<input type=\"checkbox\" name=\"classification_include_usage\"> <span data-i18n=\"m_ad56436592fd\">Запитувати usage</span>",{});body.append(usageLabel);form.elements.classification_include_usage.checked=!!original.provider.include_usage;
  function update(){body.hidden=!toggle.checked;body.disabled=!toggle.checked;connection.update()}
  toggle.addEventListener('change',update);form.addEventListener('settings-reset',update);update();
  return {read(){if(!toggle.checked)return null;const result={...original,provider:{...connection.read(),include_usage:form.elements.classification_include_usage.checked}};for(const name of ['context_tokens','max_output_tokens','max_input_chars','temperature'])result[name]=Number(form.elements['classification_'+name].value);if(result.max_output_tokens>=result.context_tokens)throw new Error(t("m_da61ca0b1811"));return result}};
}
