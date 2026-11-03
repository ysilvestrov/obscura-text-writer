import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export function mountHorizonControls(form,role,config){
  const initial={future_plan_mode:config.future_plan_mode??'all',future_plan_count:config.future_plan_count??2};
  if(role==='memory'){
    const hint=document.createElement('p');uiText(hint,"textContent",()=>(t("m_cf30860c82c5")));form.append(hint);
    return {read:()=>initial,update:()=>{}};
  }
  const group=document.createElement('fieldset'),legend=document.createElement('legend');uiText(legend,"textContent",()=>(t("m_6046324eb951")));group.append(legend);
  const label=document.createElement('label'),mode=document.createElement('select');mode.name='future_plan_mode';uiText(label,"textContent",()=>(t("m_b7d741b588f8")));
  for(const [value,text] of [['all',msg("m_6793515ebea6")],['next_n',msg("m_4c5e1b65820e")],['current',msg("m_76f1f00623eb")]]){
    const option=document.createElement('option');option.value=value;uiText(option,"textContent",()=>(text));mode.append(option);
  }
  mode.value=initial.future_plan_mode;label.append(mode);group.append(label);
  const countLabel=document.createElement('label'),count=document.createElement('input');count.type='number';count.name='future_plan_count';count.min='0';count.max='1000';count.step='1';count.required=true;count.value=String(initial.future_plan_count);uiText(countLabel,"textContent",()=>(t("m_5e252e160a4b")));countLabel.append(count);group.append(countLabel);
  const hint=document.createElement('p');group.append(hint);form.append(group);
  const update=()=>{
    const available=role!=='editor'||form.elements.edit_mode.value==='prose';
    mode.disabled=!available;count.disabled=!available||mode.value!=='next_n';
    uiText(hint,"textContent",()=>(!available?t("m_41ee3bbf94e5"):
      t("m_7bb500a572fa")+(role==='planner'?t("m_b23f8942e0f3"):'')));
  };
  mode.addEventListener('change',update);
  if(role==='editor')form.elements.edit_mode.addEventListener('change',update);
  update();
  return {update,read:()=>({future_plan_mode:mode.value,future_plan_count:mode.value==='next_n'?Number(count.value):initial.future_plan_count})};
}
