import {SettingsDrafts,settingsRoute} from './settings-state.js';

export const settingsDrafts=new SettingsDrafts();
const forms=new Map(),root=document.querySelector('.settings-page');
const labels={writing:'Письмо',models:'Моделі',evaluator:'Оцінювач',budget:'Бюджет',profiles:'Комплекти'};
const roles={planner:'Планувальник',writer:'Письменник',editor:'Редактор',memory:'Пам’ять'};
let route=settingsRoute(globalThis.location?.search||''),navigationAllowed=false;
const fields=form=>Object.fromEntries([...form.elements].filter(e=>e.name&&!['submit','button','file'].includes(e.type)&&!(e.dataset.derived==='true'&&form.dataset.rawPending!=='true')).map(e=>[e.name,e.type==='checkbox'?e.checked:e.value]));
const selectedKey=()=>route.section==='models'?route.role:route.section;
function sync(key){const entry=forms.get(key);if(entry)settingsDrafts.change(key,fields(entry.form))}
export function hasUnsavedSettings(except=[]){for(const k of forms.keys())sync(k);return [...settingsDrafts.records].some(([k,r])=>!except.includes(k)&&(settingsDrafts.dirty(k)||r.busy))}
export function allowSettingsNavigation(){navigationAllowed=true}
export function settingsBusy(){return settingsDrafts.anyBusy()}
export function settingsChanged(key){sync(key);draw();document.dispatchEvent(new CustomEvent('settings-draft-changed'))}
export function settingsFormError(key,error){settingsDrafts.setError(key,error?.message||String(error));draw()}
export function registerSettingsForm(key,{form,label,section,reset=null}){
  form.dataset.settingsScope=key;forms.set(key,{form,label,section,reset});settingsDrafts.register(key,fields(form));
  if(form.dataset.settingsTracked!==key){
    for(const name of ['input','change'])form.addEventListener(name,()=>settingsChanged(key));
    form.addEventListener('invalid',event=>{for(let p=event.target.parentElement;p&&p!==form;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true},true);
    form.dataset.settingsTracked=key;
  }
  draw();
}
export function settingsSaved(key){sync(key);settingsDrafts.saved(key);draw();document.dispatchEvent(new CustomEvent('settings-saved',{detail:{key}}))}
export function settingsRebaseFields(key,names){sync(key);const value=settingsDrafts.get(key)?.current;if(value)settingsDrafts.rebase(key,Object.fromEntries(names.filter(n=>Object.hasOwn(value,n)).map(n=>[n,value[n]])));draw()}
export function confirmSettingsReplacement(keys,names=null){
  keys.forEach(sync);
  const affected=keys.filter(k=>names?settingsDrafts.changedFields(k,names):settingsDrafts.dirty(k));
  return !affected.length||confirm('Є незбережені правки: '+affected.map(k=>forms.get(k)?.label||k).join(', ')+'. Замінити відповідні налаштування?');
}
export async function withSettingsSave(key,work){
  if(settingsDrafts.anyBusy())throw new Error('Дочекайтеся завершення збереження');
  const entry=forms.get(key);if(!entry)throw new Error('Форму ще не завантажено');
  sync(key);settingsDrafts.setBusy(key,true);settingsDrafts.setError(key,null);
  document.dispatchEvent(new CustomEvent('settings-save-state'));
  const previous=[...new Set([...forms.values()].flatMap(v=>[...v.form.elements]))].map(e=>[e,e.disabled]);previous.forEach(([e])=>e.disabled=true);draw();
  try{return await work()}catch(error){settingsDrafts.setError(key,error.message);throw error}
  finally{previous.forEach(([e,disabled])=>{if(e.isConnected)e.disabled=disabled});settingsDrafts.setBusy(key,false);for(const v of forms.values())v.form.dispatchEvent(new Event('settings-unlocked'));draw();document.dispatchEvent(new CustomEvent('settings-save-state'))}
}
export async function resetSettingsForm(key){
  const entry=forms.get(key);if(!entry)return;
  return withSettingsSave(key,async()=>{
    if(entry.reset)await entry.reset();
    else{const baseline=settingsDrafts.reset(key);for(const e of entry.form.elements)if(Object.hasOwn(baseline,e.name)){if(e.type==='checkbox')e.checked=baseline[e.name];else e.value=baseline[e.name]}entry.form.dispatchEvent(new Event('settings-reset'));settingsChanged(key)}
  });
}
export function showSettingsRole(role){if(!Object.hasOwn(roles,role))return;route={section:'models',role};draw()}
function draw(){
  if(!root)return;
  for(const pane of root.querySelectorAll('[data-settings-section]'))pane.hidden=pane.dataset.settingsSection!==route.section;
  for(const button of root.querySelectorAll('[data-settings-nav]')){
    const key=button.dataset.settingsNav,dirty=[...forms].some(([k,v])=>v.section===key&&settingsDrafts.dirty(k));
    button.textContent=labels[key]+(dirty?' · незбережено':'');button.classList.toggle('active',key===route.section);button.setAttribute('aria-current',key===route.section?'page':'false');
  }
  for(const button of root.querySelectorAll('[data-settings-role]')){
    const role=button.dataset.settingsRole;button.textContent=roles[role]+(settingsDrafts.dirty(role)?' · незбережено':'');button.classList.toggle('active',role===route.role);button.setAttribute('aria-pressed',String(role===route.role));
  }
  for(const form of root.querySelectorAll('form[data-role]'))form.hidden=route.section!=='models'||form.dataset.role!==route.role;
  const key=selectedKey(),entry=forms.get(key),record=settingsDrafts.get(key),save=root.querySelector('#settings-save'),reset=root.querySelector('#settings-reset');
  root.querySelector('#settings-section-title').textContent=labels[route.section];root.querySelector('#settings-section-mobile').value=route.section;
  save.textContent=entry?'Зберегти: '+entry.label:'Зберегти';save.hidden=!entry;reset.hidden=!entry;
  save.disabled=!entry||settingsDrafts.anyBusy()||!settingsDrafts.dirty(key)||entry.form.dataset.saveBlocked==='true';reset.disabled=!entry||settingsDrafts.anyBusy()||!settingsDrafts.dirty(key);
  root.querySelector('#settings-save-status').textContent=record?.busy?'Зберігаємо…':record?.error||(!entry?'Оберіть потрібну дію в розділі':settingsDrafts.dirty(key)?'Незбережені зміни':'Без змін');
}
if(root){
  for(const button of root.querySelectorAll('[data-settings-nav]'))button.onclick=()=>{route.section=button.dataset.settingsNav;draw()};
  for(const button of root.querySelectorAll('[data-settings-role]'))button.onclick=()=>showSettingsRole(button.dataset.settingsRole);
  root.querySelector('#settings-section-mobile').onchange=event=>{route.section=event.target.value;draw()};
  root.querySelector('#settings-save').onclick=()=>forms.get(selectedKey())?.form.requestSubmit();
  root.querySelector('#settings-reset').onclick=async()=>{
    const key=selectedKey(),entry=forms.get(key);if(!entry||settingsDrafts.anyBusy()||!confirm('Відкинути ручні правки: '+entry.label+'?'))return;
    try{await resetSettingsForm(key)}catch(error){settingsDrafts.setError(key,error.message);draw()}
  };
  document.addEventListener('settings-show-role',event=>showSettingsRole(event.detail));
  globalThis.addEventListener('beforeunload',event=>{if(!navigationAllowed&&hasUnsavedSettings()){event.preventDefault();event.returnValue=''}});
  draw();
}
