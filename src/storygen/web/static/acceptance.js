import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
export function acceptanceReason(state,ref){
  if(state.saving)return t("m_cbac60d6d919");
  if(state.dirty)return t("m_a4c2e86ecc1a");
  if(!state.scene)return t("m_f0f1417db6de");
  if(!ref?.complete||!['draft','edited','manual'].includes(ref.kind))return t("m_d6a28f9c4076");
  return '';
}
let closePreview=()=>{};
export function closeAcceptancePreview(){closePreview()}
const reasons={get review_basis_changed(){return t("review.basis_changed")},get selector_changed(){return t("m_8b91b89ae0c0")},get selector_unavailable(){return t("m_de55f106214d")},get source_baseline_changed(){return t("m_050f9db160c7")},get source_stale(){return t("m_f25bde6a2fc5")},get legacy_stale(){return t("m_9c6aa2eab83a")},get incomplete(){return t("m_9490802988fa")},get integrity_error(){return t("m_0c212402e872")},get source_unavailable(){return t("m_de55f106214d")},get dependency_cycle(){return t("m_29def73798da")}};
const value=v=>v==null?t("m_554e24318ede"):Array.isArray(v)?v.join(', '):String(v);
export async function openAcceptance({state,ref,api,json,panel,notice,onAccepted}){
  const reason=acceptanceReason(state,ref);if(reason)throw new Error(reason);
  closePreview();
  const sceneId=state.scene.id,epoch=state.bufferEpoch;
  const preview=await api(`/api/scenes/${sceneId}/acceptance-preview?version_id=${encodeURIComponent(ref.id)}`);
  if(state.scene?.id!==sceneId||state.bufferEpoch!==epoch||state.dirty)throw new Error(t("m_44e3922c2d3a"));
  const container=document.createElement('section');container.className='acceptance-preview';
  const title=document.createElement('h3');uiText(title,"textContent",()=>(t("m_b689fe961d15")));title.id='acceptance-title';container.setAttribute('aria-labelledby',title.id);
  const warning=document.createElement('p');uiText(warning,"textContent",()=>(t("m_04364d197a4e")));
  const text=document.createElement('pre');uiText(text,"textContent",()=>(preview.text));
  const changes=document.createElement('ul');
  for(const change of preview.changes){const item=document.createElement('li');uiText(item,"textContent",()=>(t("m_eb44a6ffaad5",{p0:(reasons[diagnostic(change.reason)]||diagnostic(change.reason)),p1:(change.selector?.field||change.version_id||ref.id),p2:(value(change.expected)),p3:(value(change.current))})));changes.append(item)}
  if(!preview.changes.length){const item=document.createElement('li');uiText(item,"textContent",()=>(t("m_44ad3b502cc5")));changes.append(item)}
  const commit=document.createElement('button');uiText(commit,"textContent",()=>(ref.kind==='draft'?t("m_2eaeb066a721"):t("m_ea020c200019")));
  const cancel=document.createElement('button');cancel.className='secondary';uiText(cancel,"textContent",()=>(t("m_3a0a2f657a53")));
  let busy=false,invalid=false;
  function update(){const reason=acceptanceReason(state,ref)||((state.scene?.id!==sceneId||state.bufferEpoch!==epoch)?t("m_8e19494e4a9d"):'');commit.disabled=busy||invalid||!!reason;uiText(commit,"title",()=>(diagnostic(reason)))}
  function close(){document.removeEventListener?.('editor-state-changed',update);container.replaceChildren();container.remove?.();closePreview=()=>{}}
  closePreview=close;cancel.onclick=close;
  commit.onclick=async()=>{
    update();if(commit.disabled)return;
    busy=true;update();uiText(commit,"textContent",()=>(t("m_899b666b7143")));
    try{
      const result=await api(`/api/scenes/${sceneId}/accept-version`,json('POST',{version_id:ref.id,expected_revision:preview.expected_revision,preview_fingerprint:preview.preview_fingerprint}));
      close();await onAccepted(result,{sceneId,epoch});notice(msg("m_3168b7c7d041"),'success');
    }catch(error){invalid=true;notice(error.message+t("m_f28d647d5a9e"),'error')}
    finally{busy=false;uiText(commit,"textContent",()=>(invalid?t("m_6fbd2274993c"):t("m_974213107ec3")));update()}
  };
  document.addEventListener('editor-state-changed',update);update();
  container.append(title,warning,text,changes,commit,cancel);panel.append(container);title.tabIndex=-1;title.focus();
  return {container,text,commit,cancel};
}


export function acceptedContinuation(run,attempts,scene,versions,acceptances){
  if(!run||!['alternative','needs_review'].includes(run.state))return null;
  const task=run.tasks[run.cursor],head={brief:'brief',draft:'draft',edit:'prose',memory:'memory'}[task?.stage];
  if(!head||task.scene_id!==scene?.id)return null;
  const attempt=[...attempts].reverse().find(a=>a.stage===task.stage&&a.scene_id===scene.id);
  const ref=versions.find(v=>v.id===attempt?.result_version_id);
  if(!ref||ref.stale||!ref.complete||scene.heads[head]!==ref.id)return null;
  const acceptance=acceptances.filter(a=>a.version_id===ref.id).at(-1);
  return {version_id:ref.id,expected_cursor:run.cursor,expected_scene_revision:scene.revision,acceptance_id:acceptance?.id||null};
}
