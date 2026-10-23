export function mountHorizonControls(form,role,config){
  const initial={future_plan_mode:config.future_plan_mode??'all',future_plan_count:config.future_plan_count??2};
  if(role==='memory'){
    const hint=document.createElement('p');hint.textContent='Пам’ять використовує лише попередній журнал і поточну прозу; горизонт майбутніх планів тут не застосовується.';form.append(hint);
    return {read:()=>initial,update:()=>{}};
  }
  const group=document.createElement('fieldset'),legend=document.createElement('legend');legend.textContent='Горизонт майбутнього сюжету';group.append(legend);
  const label=document.createElement('label'),mode=document.createElement('select');mode.name='future_plan_mode';label.textContent='Які плани передавати цій ролі';
  for(const [value,text] of [['all','Поточна та всі наступні сцени'],['next_n','Поточна та N наступних сцен'],['current','Лише поточна сцена']]){
    const option=document.createElement('option');option.value=value;option.textContent=text;mode.append(option);
  }
  mode.value=initial.future_plan_mode;label.append(mode);group.append(label);
  const countLabel=document.createElement('label'),count=document.createElement('input');count.type='number';count.name='future_plan_count';count.min='0';count.max='1000';count.step='1';count.required=true;count.value=String(initial.future_plan_count);countLabel.textContent='Кількість наступних сцен N (без поточної)';countLabel.append(count);group.append(countLabel);
  const hint=document.createElement('p');group.append(hint);form.append(group);
  const update=()=>{
    const available=role!=='editor'||form.elements.edit_mode.value==='prose';
    mode.disabled=!available;count.disabled=!available||mode.value!=='next_n';
    hint.textContent=!available?'Цей режим редактора отримує лише чернетку. Горизонт не застосовується.':
      'Пам’ять минулих подій не змінюється. Бриф, канон і власний промпт можуть містити відомості про фінал.'+(role==='planner'?' Горизонт діє для завдання письменнику; підготовка структури використовує повний імпортований план.':'');
  };
  mode.addEventListener('change',update);
  if(role==='editor')form.elements.edit_mode.addEventListener('change',update);
  update();
  return {update,read:()=>({future_plan_mode:mode.value,future_plan_count:mode.value==='next_n'?Number(count.value):initial.future_plan_count})};
}
