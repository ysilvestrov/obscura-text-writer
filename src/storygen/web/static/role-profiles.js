import {confirmDialog} from './dialogs.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {hasUnsavedSettings,allowSettingsNavigation,registerSettingsForm,settingsSaved,withSettingsSave,settingsBusy} from './settings-workspace.js';
import {api,json,notice} from './api.js';

const panel=document.querySelector('#role-profiles');
const storyId=document.querySelector('[data-story-id]').dataset.storyId;
const select=panel.querySelector('#role-profile-select');
const previewButton=panel.querySelector('#role-profile-preview');
const applyButton=panel.querySelector('#role-profile-apply');
const exportButton=panel.querySelector('#role-profile-export');
const summary=panel.querySelector('#role-profile-summary');
const form=panel.querySelector('form');
const file=panel.querySelector('input[type=file]');
const labels={get planner(){return t("m_38c94c25c4af")},get writer(){return t("m_75515c07207a")},get editor(){return t("m_65d42cf1679c")},get memory(){return t("m_aa1cfb48cc30")}};
let items=[],preview=null,busy=false,dirty=false,selectionEpoch=0;

function selected(){return items.find(item=>`${item.id}:${item.version}`===select.value)}
function controls(){const item=selected();if(settingsBusy()){for(const el of [previewButton,applyButton,exportButton,file,select,form.querySelector('button')])el.disabled=true;return}previewButton.disabled=busy||!item;exportButton.disabled=busy||!item;applyButton.disabled=busy||!preview;form.querySelector('button').disabled=busy;file.disabled=busy;select.disabled=busy;form.elements.new_version.disabled=busy||!item}
function reset(){selectionEpoch++;preview=null;summary.replaceChildren();controls()}
select.onchange=()=>{reset();const item=selected();if(item)form.elements.name.value=item.name};
document.addEventListener('input',event=>{if(event.target.closest('form')&&!panel.contains(event.target)){dirty=true;reset()}});

async function load(preferred=null){
  const result=await api('/api/role-profiles');items=result.profiles;select.replaceChildren();
  const empty=document.createElement('option');empty.value='';uiText(empty,"textContent",()=>(items.length?t("m_767da841164d"):t("m_7dc4d8da1351")));select.append(empty);
  for(const item of items){const option=document.createElement('option');option.value=`${item.id}:${item.version}`;uiText(option,"textContent",()=>(t("m_c9790401d305",{p0:(item.name),p1:(item.version),p2:(item.has_evaluator?t("m_a2c773e16a40"):'')})));select.append(option)}
  if(preferred){select.value=`${preferred.id}:${preferred.version}`;form.elements.name.value=preferred.document.name}
  reset();
}

async function action(work){if(busy||settingsBusy())return;busy=true;controls();try{await work()}catch(error){notice(error.message,'error')}finally{busy=false;controls()}}
async function revision(){return (await api(`/api/stories/${storyId}/settings`)).story.revision}

previewButton.onclick=()=>action(async()=>{
  const item=selected(),epoch=selectionEpoch;
  preview=null;
  const data=await api(`/api/stories/${storyId}/role-profiles/preview`,json('POST',{profile_id:item.id,version:item.version,expected_revision:await revision()}));
  if(epoch!==selectionEpoch)return;
  preview=data;summary.replaceChildren();
  const title=document.createElement('h3');uiText(title,"textContent",()=>(t("m_6b47a412c317",{p0:(data.name),p1:(data.version)})));summary.append(title);
  const list=document.createElement('dl');
  for(const [role,config] of Object.entries(data.roles)){
    const name=document.createElement('dt');uiText(name,"textContent",()=>(labels[role]));
    const value=document.createElement('dd');uiText(value,"textContent",()=>(t("m_689ffb844b38",{p0:(config.provider.provider),p1:(config.provider.model),p2:(config.context_tokens),p3:(config.max_output_tokens),p4:(data.prompts[role].prompt.text===null?t("m_fcedf84d6354"):t("m_8bfbbad3632b"))})));
    list.append(name,value);
  }
  summary.append(list);
  const evaluator=document.createElement('p');uiText(evaluator,"textContent",()=>(data.evaluator?t("m_c809605baab4",{p0:(data.evaluator.config.provider),p1:(data.evaluator.config.model||t("m_eff175374c74")),p2:(data.evaluator.policy)}):t("m_836364365ba3")));summary.append(evaluator);
  for(const text of data.warnings){const warning=document.createElement('p');uiText(warning,"textContent",()=>(diagnostic(text)));summary.append(warning)}
  const details=document.createElement('details'),caption=document.createElement('summary'),raw=document.createElement('pre');uiText(caption,"textContent",()=>(t("m_edc6ecf1fe8c")));uiText(raw,"textContent",()=>(JSON.stringify(data,null,2)));details.append(caption,raw);summary.append(details);
});

applyButton.onclick=()=>action(()=>withSettingsSave('profiles',async()=>{
  if(!preview)return;
  const warning=hasUnsavedSettings()?t("m_1b71a8026745"):t("m_ddc1ef1e58c7");
  if(!await confirmDialog(warning+t("m_3ac2c4d48372",{p0:(preview.name),p1:(preview.version)})))return;
  await api(`/api/stories/${storyId}/role-profiles/apply`,json('POST',{profile_id:preview.id,version:preview.version,expected_revision:preview.expected_revision}));
  allowSettingsNavigation();location.reload();
}));

exportButton.onclick=()=>{const item=selected();if(item)location.href=`/api/role-profiles/${encodeURIComponent(item.id)}/versions/${item.version}/export`};
form.onsubmit=event=>{event.preventDefault();action(()=>withSettingsSave('profiles',async()=>{
  if(hasUnsavedSettings(['profiles'])&&!await confirmDialog(t("m_d2cbce67c72d")))return;
  const body={name:form.elements.name.value,include_evaluator:form.elements.include_evaluator.checked,expected_revision:await revision()};
  if(form.elements.new_version.checked){const item=selected();if(!item)throw new Error(t("m_a7068ca31456"));body.profile_id=item.id;body.expected_version=item.version}
  const saved=await api(`/api/stories/${storyId}/role-profiles/capture`,json('POST',body));await load(saved);settingsSaved('profiles');notice(msg("m_ff6b04a6519d"));
}))};
file.onchange=()=>action(async()=>{
  const source=file.files[0];if(!source)return;
  try{
    if(source.size>2*1024*1024)throw new Error(t("m_c769e0811142"));
    const saved=await api('/api/role-profiles/import',{method:'POST',headers:{'Content-Type':'application/json'},body:await source.text()});
    await load(saved);notice(msg("m_a2c15495d1ff"));
  }finally{file.value=''}
});
registerSettingsForm('profiles',{form,label:live(()=>(t("m_143bb204433b"))),section:'profiles'});
document.addEventListener('settings-save-state',controls);
document.addEventListener('settings-saved',reset);
document.addEventListener('settings-draft-changed',reset);
load().catch(error=>notice(error.message,'error'));
