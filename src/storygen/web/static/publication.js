import {confirmDialog} from './dialogs.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {externalPublicationChange,withLibraryRevisions} from './publication-sync.js';

const page=document.querySelector('#publication-page');
const storyId=page.dataset.storyId;
const base=`/api/stories/${storyId}/publication`;
const form=document.querySelector('#publication-form');
const save=document.querySelector('#publication-save');
const status=document.querySelector('#publication-status');
const scalar=['title','language','annotation','cycle_title','publication_date','publisher','isbn','rights','source_language'];
let view=null,library=[],authors=[],translators=[],coverId=null,signatureRevisions={};
let dirty=false,busy=false,loading=false,edits=0;
let acceptance=null;
const touched=new Set();

function libraryDirty(){
  return [...document.querySelectorAll('.signature-row input')].some(input=>input.value!==input.dataset.saved)
    || !!document.querySelector('#publication-signature-create').elements.namedItem('display_name').value.trim();
}
function state(message){
  for(const control of form.elements)control.disabled=!view||loading;
  save.disabled=busy||!view||!dirty;
  document.querySelector('#publication-reload').disabled=busy;
  document.querySelector('#publication-cover-upload').disabled=busy||!view;
  document.querySelector('#publication-cover-remove').disabled=busy||!view||!coverId;
  for(const control of document.querySelectorAll('.publication-suggestion-apply'))control.disabled=busy||control.dataset.available!=='true';
  for(const role of ['author','translator']){
    const choice=document.querySelector(`#publication-${role}-choice`);
    document.querySelector(`#publication-${role}-add`).disabled=busy||!view||!choice.value;
  }
  if(message)uiText(status,"textContent",()=>(diagnostic(message)));
  else uiText(status,"textContent",()=>(busy?t("m_284972eb2a43"):dirty?t("m_ad6fd44ef27f"):t("m_0bfe9e67febe")));
}
function changed(event){if(event?.target?.name)touched.add(event.target.name);dirty=true;edits++;state();}
function button(text,handler){
  const node=document.createElement('button');node.type='button';node.className='secondary';
  uiText(node,"textContent",()=>(text));node.onclick=handler;return node;
}
function selected(role){return role==='author'?authors:translators;}
function renderPeople(){
  for(const role of ['author','translator']){
    const ids=selected(role),list=document.querySelector(role==='author'?'#publication-authors':'#publication-translators');
    list.replaceChildren();
    ids.forEach((id,index)=>{
      const person=library.find(item=>item.id===id);
      const row=document.createElement('li');const name=document.createElement('span');
      uiText(name,"textContent",()=>((person?.display_name||t("m_d8a1bc7307aa"))+(person?.archived_at?t("m_da4e124f1d85"):'')));
      const actions=document.createElement('div');actions.className='actions';
      const up=button(live(()=>(t("m_9dccba8c676e"))),()=>{[ids[index-1],ids[index]]=[ids[index],ids[index-1]];changed();renderPeople();});
      up.disabled=index===0||busy;
      const down=button(live(()=>(t("m_c6b677f0d732"))),()=>{[ids[index],ids[index+1]]=[ids[index+1],ids[index]];changed();renderPeople();});
      down.disabled=index===ids.length-1||busy;
      const remove=button(live(()=>(t("m_bf052e77eb36"))),()=>{ids.splice(index,1);changed();renderPeople();});remove.disabled=busy;
      actions.append(up,down,remove);row.append(name,actions);list.append(row);
    });
    if(!ids.length){const empty=document.createElement('li');uiText(empty,"textContent",()=>(role==='author'?t("m_d2e7bf10bef3"):t("m_21396e4d6de4")));list.append(empty);}
    const choice=document.querySelector(`#publication-${role}-choice`);
    const empty=new Option('','');uiText(empty,'textContent',()=>t("m_f3312f2e6965"));choice.replaceChildren(empty);
    for(const person of library.filter(item=>!item.archived_at&&!ids.includes(item.id)))choice.add(new Option(person.display_name,person.id));
  }
  state();
}
function renderCover(){
  const image=document.querySelector('#publication-cover');
  image.hidden=!coverId;
  if(coverId)image.src=`${base}/covers/${coverId}`;else image.removeAttribute('src');
  document.querySelector('#publication-cover-empty').hidden=!!coverId;
  state();
}
function fill(){
  for(const key of scalar)form.elements.namedItem(key).value=view.card[key]||'';
  form.elements.namedItem('cycle_number').value=view.card.cycle_number??'';
  form.elements.namedItem('keywords').value=view.card.keywords.join('\n');
  for(const option of form.elements.namedItem('genres').options)option.selected=view.card.genres.includes(option.value);
  authors=[...view.card.author_ids];translators=[...view.card.translator_ids];coverId=view.card.cover_id;
  signatureRevisions=Object.fromEntries([...view.authors,...view.translators].map(item=>[item.id,item.revision]));
  dirty=false;renderPeople();renderCover();
  touched.clear();acceptance=null;
}
function collect(){
  const result=Object.fromEntries(scalar.map(key=>[key,form.elements.namedItem(key).value]));
  result.genres=[...form.elements.namedItem('genres').selectedOptions].map(option=>option.value);
  result.keywords=form.elements.namedItem('keywords').value.split(/\r?\n/).map(item=>item.trim()).filter(Boolean);
  const number=form.elements.namedItem('cycle_number').value;
  result.cycle_number=number===''?null:Number(number);
  return {...result,author_ids:[...authors],translator_ids:[...translators],cover_id:coverId};
}
async function refreshLibrary(){
  const response=await api('/api/publication-signatures?include_archived=true');
  library=response.signatures;
  signatureRevisions=withLibraryRevisions(signatureRevisions,library);
  renderLibrary();renderPeople();
}
function renderLibrary(){
  const container=document.querySelector('#publication-signatures');
  const drafts=new Map([...container.querySelectorAll('input[data-id]')].filter(input=>input.value!==input.dataset.saved).map(input=>[input.dataset.id,input.value]));
  container.replaceChildren();
  for(const person of library){
    const row=document.createElement('form');row.className='signature-row';
    const label=document.createElement('label');uiText(label,"textContent",()=>(person.archived_at?t("m_921baf888332"):t("m_c842c27b9176")));
    const input=document.createElement('input');input.value=drafts.get(person.id)??person.display_name;
    input.dataset.saved=person.display_name;input.dataset.id=person.id;input.required=true;input.maxLength=300;
    label.append(input);
    const actions=document.createElement('div');actions.className='actions';
    const apply=button(live(()=>(t("m_f46b51eb6365"))),()=>row.requestSubmit());
    const archive=button(live(()=>person.archived_at?t("m_11b6e5a88fd6"):t("m_fba97decdd75")),()=>update({archived:!person.archived_at}));
    actions.append(apply,archive);row.append(label,actions);container.append(row);
    async function update(changes){
      if(busy)return;
      busy=true;state();apply.disabled=true;archive.disabled=true;
      try{
        await api('/api/publication-signatures/'+person.id,json('PATCH',{expected_revision:person.revision,...changes}));
        // This explicit edit is reflected in current choices; unrelated form fields survive.
        if(changes.display_name!==undefined)input.dataset.saved=changes.display_name;
        await refreshLibrary();notice(msg("m_45bdaac9a856"));
      }catch(error){notice(error.message,'error');}
      finally{busy=false;apply.disabled=false;archive.disabled=false;renderPeople();state();}
    }
    row.onsubmit=event=>{event.preventDefault();void update({display_name:input.value});};
  }
  if(!library.length){const empty=document.createElement('p');empty.className='muted';uiText(empty,"textContent",()=>(t("m_eb83a4f7f35d")));container.append(empty);}
}
async function load(){
  busy=true;loading=true;state(t("m_09fa21f2ecc7"));
  try{
    const [current,people]=await Promise.all([api(base),api('/api/publication-signatures?include_archived=true')]);
    view=current;library=people.signatures;renderLibrary();fill();
    void refreshSuggestions(true);
  }catch(error){notice(error.message,'error');state(t("m_2a71312f01a8"));}
  finally{busy=false;loading=false;renderPeople();state(view?undefined:t("m_300dfe2b0e8a"));}
}
form.addEventListener('input',changed);form.addEventListener('change',changed);
form.onsubmit=async event=>{
  event.preventDefault();if(busy||!view||!dirty)return;
  const sequence=edits;const data=collect();busy=true;state();
  const expected=Object.fromEntries([...new Set([...authors,...translators])].map(id=>[id,signatureRevisions[id]]));
  try{
    const suggestion=acceptance&&{...acceptance,fields:acceptance.fields.filter(key=>Array.isArray(data[key])?data[key].length:!!data[key]?.trim())};
    view=await api(base,json('PUT',{expected_revision:view.card.revision,data,expected_signature_revisions:expected,...(suggestion?.fields.length?{suggestion}:{})}));
    acceptance=null;
    if(sequence===edits)fill();
    void refreshSuggestions(true);
    notice(sequence===edits?t("m_aaf45dc4267a"):t("m_1c03b9a2dfb8"));
  }catch(error){notice(error.message,'error');}
  finally{busy=false;renderPeople();state();}
};
for(const role of ['author','translator']){
  const choice=document.querySelector(`#publication-${role}-choice`);
  choice.onchange=()=>state();
  document.querySelector(`#publication-${role}-add`).onclick=()=>{
    if(!view||busy||!choice.value)return;
    const ids=selected(role);if(ids.length>=20){notice(msg("m_79add8957f2f"),'error');return;}
    const person=library.find(item=>item.id===choice.value);
    ids.push(person.id);signatureRevisions[person.id]=person.revision;changed();renderPeople();
  };
}
document.querySelector('#publication-signature-create').onsubmit=async event=>{
  event.preventDefault();if(busy)return;const node=event.currentTarget;const input=node.elements.namedItem('display_name');const original=input.value;
  busy=true;node.querySelector('button').disabled=true;state();
  try{await api('/api/publication-signatures',json('POST',{display_name:original}));if(input.value===original)input.value='';await refreshLibrary();notice(msg("m_e12d57b9840b"));}
  catch(error){notice(error.message,'error');}
  finally{busy=false;node.querySelector('button').disabled=false;renderPeople();state();}
};
document.querySelector('#publication-cover-form').onsubmit=async event=>{
  event.preventDefault();if(busy||!view)return;
  const node=event.currentTarget,file=node.elements.namedItem('file').files[0];if(!file)return;
  if(file.size>10*1024*1024){notice(msg("m_2cade430c401"),'error');return;}
  const body=new FormData();body.append('file',file);busy=true;state(t("m_95349d307384"));
  try{const asset=await api(base+'/cover',{method:'POST',body});coverId=asset.id;changed();renderCover();notice(msg("m_f39b262d5cb5"));}
  catch(error){notice(error.message,'error');}
  finally{busy=false;renderPeople();state();}
};
document.querySelector('#publication-cover-remove').onclick=()=>{if(!busy){coverId=null;changed();renderCover();}};
document.querySelector('#publication-reload').onclick=async()=>{
  if(busy)return;
  const before=edits;
  if((dirty||libraryDirty())&&!await confirmDialog(t("m_365ad153ac12")))return;
  if(busy||edits!==before)return;
  // Explicit discard also clears drafts in the shared dictionary.
  document.querySelector('#publication-signatures').replaceChildren();void load();
};
window.addEventListener('beforeunload',event=>{if(dirty||libraryDirty()){event.preventDefault();event.returnValue='';}});

const suggest=document.querySelector('#publication-suggest');
const suggestCancel=document.querySelector('#publication-suggest-cancel');
const suggestStatus=document.querySelector('#publication-suggest-status');
let suggestionBusy=false,activeSuggestion=null,readiness=null,pollTimer=null;
const fieldLabels={get title(){return t("m_382c87f95f48")},get annotation(){return t("m_68c7c9c9e256")},get genres(){return t("m_8fc22bc825df")},get keywords(){return t("m_919849ae2f0f")}};
function suggestionControls(){
  suggest.disabled=suggestionBusy||!!activeSuggestion||!readiness?.ready;
  suggestCancel.hidden=!activeSuggestion;
  suggestCancel.disabled=suggestionBusy;
}
async function refreshSuggestions(checkReady=false){
  if(!suggest)return;
  try{
    const response=await api(base+'/suggestions');
    activeSuggestion=response.active_runs[0]||null;
    if(checkReady||!activeSuggestion)readiness=await api(base+'/suggestions/readiness');
    const history=document.querySelector('#publication-suggestion-history');history.replaceChildren();
    for(const item of response.history){const line=document.createElement('p');uiText(line,"textContent",()=>(`${item.created_at} · ${item.state}${diagnostic(item.error)?' · '+diagnostic(item.error):''}${item.warnings?.length?' · '+item.warnings.join(' '):''}`));history.append(line);}
    if(!response.history.length)uiText(history,"textContent",()=>(t("m_6c77004041e5")));
    const container=document.querySelector('#publication-suggestions');container.replaceChildren();
    for(const proposal of response.proposals){
      const details=document.createElement('details');
      const summary=document.createElement('summary');uiText(summary,"textContent",()=>(`${proposal.created_at} · ${proposal.model}`));details.append(summary);
      for(const message of proposal.warnings||[]){const warning=document.createElement('p');warning.className='muted';uiText(warning,"textContent",()=>(diagnostic(message)));details.append(warning);}
      for(const [key,value] of Object.entries(proposal.suggestions)){
        const line=document.createElement('p');
        const label=document.createElement('strong');uiText(label,"textContent",()=>(fieldLabels[key]+': '));
        const text=document.createElement('span');
        uiText(text,"textContent",()=>(key==='genres'?value.map(code=>[...form.elements.namedItem('genres').options].find(o=>o.value===code)?.textContent||code).join(', '):Array.isArray(value)?value.join(', '):value));
        line.append(label,text);details.append(line);
      }
      const apply=button(live(()=>(t("m_a39fde891195"))),()=>{
        if(busy||suggestionBusy)return;
        const current=collect(),applied=[];
        if(acceptance&&acceptance.attempt_id!==proposal.attempt_id){notice(msg("m_d9afead4c192"),'error');return;}
        for(const key of proposal.available_fields){
          if(touched.has(key)||(Array.isArray(current[key])?current[key].length:current[key]?.trim())||(key==='title'&&view.effective_title.trim()))continue;
          const value=proposal.suggestions[key];
          if(key==='genres'){for(const option of form.elements.namedItem(key).options)option.selected=value.includes(option.value);}
          else form.elements.namedItem(key).value=Array.isArray(value)?value.join('\n'):value;
          applied.push(key);touched.add(key);
        }
        if(!applied.length){notice(msg("m_d0513f180401"));return;}
        acceptance={attempt_id:proposal.attempt_id,fingerprint:proposal.fingerprint,fields:[...new Set([...(acceptance?.fields||[]),...applied])]};
        changed();notice(msg("m_3d9517f8d51f"));
      });
      apply.className+=' publication-suggestion-apply';apply.dataset.available=String(proposal.can_apply&&!suggestionBusy);
      apply.disabled=busy||!proposal.can_apply||suggestionBusy;details.append(apply);
      if(proposal.reason){const warning=document.createElement('p');uiText(warning,"textContent",()=>(diagnostic(proposal.reason)));details.append(warning);}
      container.append(details);
    }
    const last=response.history[0];
    uiText(suggestStatus,"textContent",()=>(activeSuggestion?t("m_f39da1dcdc43",{p0:(activeSuggestion.state),p1:(diagnostic(activeSuggestion.error)?' · '+diagnostic(activeSuggestion.error):'')}):
      last?.state==='failed'?t("m_7affa0531b8a",{p0:(diagnostic(last.error))}):last?.warnings?.length?t("m_4e5ea3207ea6",{p0:(last.warnings.join(' '))}):readiness?.ready?t("m_e0df58ccf3dd",{p0:(readiness.roles.planner.model)}) :diagnostic(readiness?.reason)||t("m_6e27f6bb226a")));
    clearTimeout(pollTimer);
    if(activeSuggestion&&['queued','running','pause_requested','cancellation_requested'].includes(activeSuggestion.state))pollTimer=setTimeout(()=>void refreshSuggestions(),1500);
  }catch(error){uiText(suggestStatus,"textContent",()=>(diagnostic(error.message)));readiness=null;}
  finally{suggestionControls();}
}
if(suggest){
  suggest.onclick=async()=>{
    if(suggest.disabled)return;suggestionBusy=true;suggestionControls();
    try{await api('/api/runs',json('POST',{request:{story_id:storyId,mode:'publication_suggest'},request_id:crypto.randomUUID()}));await refreshSuggestions(true);}
    catch(error){uiText(suggestStatus,"textContent",()=>(diagnostic(error.message)));notice(error.message,'error');}
    finally{suggestionBusy=false;suggestionControls();}
  };
  suggestCancel.onclick=async()=>{
    if(!activeSuggestion||suggestionBusy)return;suggestionBusy=true;suggestionControls();
    try{await api(`/api/runs/${activeSuggestion.id}/cancel`,json('POST',{}));await refreshSuggestions(true);}
    catch(error){notice(error.message,'error');}
    finally{suggestionBusy=false;suggestionControls();}
  };
}
// MCP-BRIDGE-S31: on return to the page, pick up changes made elsewhere (a chat, another window) without touching edits.
let lastSync=0,syncing=false;
async function syncFromOutside(){
  if(!view||syncing||loading||Date.now()-lastSync<2000)return;
  syncing=true;lastSync=Date.now();
  try{
    const [current,people]=await Promise.all([api(base),api('/api/publication-signatures?include_archived=true')]);
    if(!view)return;
    const decision=externalPublicationChange({loadedRevision:view.card.revision,freshRevision:current.card.revision,formDirty:dirty,busy,
      loadedLibrary:library,freshLibrary:people.signatures,libraryDirty:libraryDirty()});
    if(decision.reloadCard){await load();return;}
    if(decision.reloadLibrary){library=people.signatures;signatureRevisions=withLibraryRevisions(signatureRevisions,library);renderLibrary();renderPeople();}
    if(decision.warnCard)notice(t('publication.changed_elsewhere'),'error');
  }catch{/* A failed check stays quiet; the next return tries again. */}
  finally{syncing=false;}
}
document.addEventListener?.('visibilitychange',()=>{if(!document.hidden)void syncFromOutside();});
window.addEventListener?.('focus',()=>void syncFromOutside());
void load();
