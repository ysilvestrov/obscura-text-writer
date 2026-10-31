import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export function groupRoleFields(form,role){
  const main=document.createElement('div');main.className='settings-fields';
  const details=document.createElement('details');uiHTML(details,"<summary><span data-i18n=\"m_3cd7ef97584e\">Додаткові параметри моделі</span></summary>",{});
  const prompts=document.createElement('details');uiHTML(prompts,"<summary><span data-i18n=\"m_1175dbb6973f\">Промпти та їхні призначення</span></summary>",{});
  form.append(main,details,prompts);
  const vendor=form.querySelector('.venice-options');
  const horizon=form.elements.future_plan_mode?.closest('fieldset');
  for(const name of ['provider','model','context_tokens','max_output_tokens','temperature','edit_mode','edit_review','memory_mode']){
    const el=form.elements[name];if(el)main.append(el.closest('label'));
  }
  const modelLabel=form.elements.model.closest('label');modelLabel.append(form.querySelector('datalist'),form.querySelector('.discover'));
  const reserve=document.createElement('p');reserve.className='settings-hint';
  function capacity(){const count=Number(form.elements.context_tokens.value)-Number(form.elements.max_output_tokens.value);uiText(reserve,"textContent",()=>(count>0?t("m_4331bc0af9cd",{p0:(count.toLocaleString(getLocale()==='en'?'en-US':'uk-UA'))}):t("m_0d8b5b177c7c")))}
  for(const name of ['context_tokens','max_output_tokens'])form.elements[name].addEventListener('input',capacity);capacity();
  for(const name of ['prompt_text','prepare_prompt_text','confirm_prompt_contract','confirm_prepare_prompt_contract']){
    const el=form.elements[name];if(el)prompts.append(el.closest('label'));
  }
  for(const node of form.querySelectorAll('[data-prompt-meta]'))prompts.append(node);
  const others=[...form.children].filter(node=>node!==main&&node!==details&&node!==prompts&&node!==horizon&&node.tagName!=='H2'&&node.tagName!=='DETAILS'&&!node.classList.contains('scope-submit'));
  for(const node of others)details.append(node);
  form.append(main,reserve);if(horizon)form.append(horizon);if(vendor)form.append(vendor);form.append(details,prompts);
  const shared=form.elements.shared_provider?.closest('label');if(shared){const group=document.createElement('details');uiHTML(group,"<summary><span data-i18n=\"m_f92138dded91\">Підключення для всіх чотирьох ролей</span></summary>",{});group.append(shared);const hint=document.createElement('p');hint.className='settings-hint';uiText(hint,"textContent",()=>(t("m_4ead690f330a")));group.append(hint);form.append(group)}
  const extra=[...form.querySelectorAll(':scope > details')].filter(d=>d!==details&&d!==prompts);for(const d of extra)form.append(d);
  form.addEventListener('settings-reset',capacity);
}
