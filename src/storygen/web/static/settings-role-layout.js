export function groupRoleFields(form,role){
  const main=document.createElement('div');main.className='settings-fields';
  const details=document.createElement('details');details.innerHTML='<summary>Додаткові параметри моделі</summary>';
  const prompts=document.createElement('details');prompts.innerHTML='<summary>Промпти та їхні призначення</summary>';
  form.append(main,details,prompts);
  const vendor=form.querySelector('.venice-options');
  const horizon=form.elements.future_plan_mode?.closest('fieldset');
  for(const name of ['provider','model','context_tokens','max_output_tokens','temperature','edit_mode','edit_review','memory_mode']){
    const el=form.elements[name];if(el)main.append(el.closest('label'));
  }
  const modelLabel=form.elements.model.closest('label');modelLabel.append(form.querySelector('datalist'),form.querySelector('.discover'));
  const reserve=document.createElement('p');reserve.className='settings-hint';
  function capacity(){const count=Number(form.elements.context_tokens.value)-Number(form.elements.max_output_tokens.value);reserve.textContent=count>0?`Після резерву відповіді: ${count.toLocaleString('uk-UA')} токенів, до службового запасу.`:'Резерв відповіді не залишає місця для входу.'}
  for(const name of ['context_tokens','max_output_tokens'])form.elements[name].addEventListener('input',capacity);capacity();
  for(const name of ['prompt_text','prepare_prompt_text','confirm_prompt_contract','confirm_prepare_prompt_contract']){
    const el=form.elements[name];if(el)prompts.append(el.closest('label'));
  }
  for(const node of form.querySelectorAll('[data-prompt-meta]'))prompts.append(node);
  const others=[...form.children].filter(node=>node!==main&&node!==details&&node!==prompts&&node!==horizon&&node.tagName!=='H2'&&node.tagName!=='DETAILS'&&!node.classList.contains('scope-submit'));
  for(const node of others)details.append(node);
  form.append(main,reserve);if(horizon)form.append(horizon);if(vendor)form.append(vendor);form.append(details,prompts);
  const shared=form.elements.shared_provider?.closest('label');if(shared){const group=document.createElement('details');group.innerHTML='<summary>Підключення для всіх чотирьох ролей</summary>';group.append(shared);const hint=document.createElement('p');hint.className='settings-hint';hint.textContent='Застосовується лише підключення. Чужі промпти, режими та ліміти зберігаються.';group.append(hint);form.append(group)}
  const extra=[...form.querySelectorAll(':scope > details')].filter(d=>d!==details&&d!==prompts);for(const d of extra)form.append(d);
  form.addEventListener('settings-reset',capacity);
}
