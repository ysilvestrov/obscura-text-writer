import {confirmDialog} from './dialogs.js';
import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {SettingsDrafts,settingsRoute} from './settings-state.js';
import {api,notice} from './api.js';
import {settingsContentKey,externalSettingsChange} from './settings-sync.js';

export const settingsDrafts=new SettingsDrafts();
const forms=new Map(),root=document.querySelector('.settings-page');
const labels={get writing(){return t("m_88f778367baf")},get models(){return t("m_9d43f6fcda82")},get evaluator(){return t("m_04c7075b6943")},get budget(){return t("m_0773ed49428f")},get profiles(){return t("m_bd94099c1720")}};
const roles={get planner(){return t("m_38c94c25c4af")},get writer(){return t("m_75515c07207a")},get editor(){return t("m_65d42cf1679c")},get memory(){return t("m_aa1cfb48cc30")}};
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
export async function confirmSettingsReplacement(keys,names=null){
  keys.forEach(sync);
  const affected=keys.filter(k=>names?settingsDrafts.changedFields(k,names):settingsDrafts.dirty(k));
  return !affected.length||await confirmDialog(t("m_4a83b83f52ac")+affected.map(k=>forms.get(k)?.label||k).join(', ')+t("m_24e0783e85ed"));
}
export async function withSettingsSave(key,work){
  if(settingsDrafts.anyBusy())throw new Error(t("m_cbac60d6d919"));
  const entry=forms.get(key);if(!entry)throw new Error(t("m_041152c8523b"));
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
    uiText(button,"textContent",()=>(labels[key]+(dirty?t("m_5837eb667064"):'')));button.classList.toggle('active',key===route.section);button.setAttribute('aria-current',key===route.section?'page':'false');
  }
  for(const button of root.querySelectorAll('[data-settings-role]')){
    const role=button.dataset.settingsRole;uiText(button,"textContent",()=>(roles[role]+(settingsDrafts.dirty(role)?t("m_5837eb667064"):'')));button.classList.toggle('active',role===route.role);button.setAttribute('aria-pressed',String(role===route.role));
  }
  for(const form of root.querySelectorAll('form[data-role]'))form.hidden=route.section!=='models'||form.dataset.role!==route.role;
  const key=selectedKey(),entry=forms.get(key),record=settingsDrafts.get(key),save=root.querySelector('#settings-save'),reset=root.querySelector('#settings-reset');
  uiText(root.querySelector('#settings-section-title'),"textContent",()=>(labels[route.section]));root.querySelector('#settings-section-mobile').value=route.section;
  uiText(save,"textContent",()=>(entry?t("m_5612089c6bba")+entry.label:t("m_bf610d493cb4")));save.hidden=!entry;reset.hidden=!entry;
  save.disabled=!entry||settingsDrafts.anyBusy()||!settingsDrafts.dirty(key)||entry.form.dataset.saveBlocked==='true';reset.disabled=!entry||settingsDrafts.anyBusy()||!settingsDrafts.dirty(key);
  uiText(root.querySelector('#settings-save-status'),"textContent",()=>(record?.busy?t("m_284972eb2a43"):diagnostic(record?.error)||(!entry?t("m_90ff64df1843"):settingsDrafts.dirty(key)?t("m_ee929a68273c"):t("m_0117849a201e"))));
}
if(root){
  for(const button of root.querySelectorAll('[data-settings-nav]'))button.onclick=()=>{route.section=button.dataset.settingsNav;draw()};
  for(const button of root.querySelectorAll('[data-settings-role]'))button.onclick=()=>showSettingsRole(button.dataset.settingsRole);
  root.querySelector('#settings-section-mobile').onchange=event=>{route.section=event.target.value;draw()};
  root.querySelector('#settings-save').onclick=()=>forms.get(selectedKey())?.form.requestSubmit();
  root.querySelector('#settings-reset').onclick=async()=>{
    const key=selectedKey(),entry=forms.get(key);if(!entry||settingsDrafts.anyBusy()||!await confirmDialog(t("m_6fd8e12ff721")+entry.label+'?'))return;
    try{await resetSettingsForm(key)}catch(error){settingsDrafts.setError(key,error.message);draw()}
  };
  document.addEventListener('settings-show-role',event=>showSettingsRole(event.detail));
  globalThis.addEventListener('beforeunload',event=>{if(!navigationAllowed&&hasUnsavedSettings()){event.preventDefault();event.returnValue=''}});
  draw();
  watchOutsideChanges();
}
// MCP-BRIDGE-S37: on return to the page, pick up settings changed elsewhere (a chat, another window) without touching edits.
function watchOutsideChanges(){
  const storyId=document.querySelector('[data-story-id]')?.dataset.storyId;
  if(!storyId)return;
  let loadedKey=null,lastSync=0,syncing=false;
  const readKey=async()=>{
    const [settings,evaluator]=await Promise.all([api(`/api/stories/${storyId}/settings`),api(`/api/stories/${storyId}/evaluator`)]);
    return settingsContentKey(settings,evaluator);
  };
  // What the page now shows: after loading and after every own save (the language select saves outside withSettingsSave).
  const rebase=async()=>{try{loadedKey=await readKey()}catch{/* the next own action rebases again */}};
  document.addEventListener?.('workspace-settings-loaded',()=>void rebase());
  document.addEventListener?.('story-language-changed',()=>void rebase());
  document.addEventListener?.('settings-save-state',()=>{if(!settingsBusy())void rebase()});
  const sync=async()=>{
    if(loadedKey===null||syncing||Date.now()-lastSync<2000)return;
    syncing=true;lastSync=Date.now();
    try{
      const decision=externalSettingsChange({loadedKey,freshKey:await readKey(),unsaved:hasUnsavedSettings(),busy:settingsBusy()});
      if(decision.reload){allowSettingsNavigation();globalThis.location.reload();}
      else if(decision.warn)notice(t('settings.changed_elsewhere'),'error');
    }catch{/* A failed check stays quiet; the next return tries again. */}
    finally{syncing=false}
  };
  document.addEventListener?.('visibilitychange',()=>{if(!document.hidden)void sync()});
  globalThis.addEventListener?.('focus',()=>void sync());
}
