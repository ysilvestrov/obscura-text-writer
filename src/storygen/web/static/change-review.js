import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
// A reusable panel. Content is always text; publication is performed by the API.
export function mountChangeReview({host,state,api,json,notice,onApplied,onQueued=()=>{},onAvailability=()=>{},adapter={}}){
  const rewrite=adapter.kind==='rewrite';
  const url=(scene,attempt='',suffix='')=>`/api/scenes/${scene}/${rewrite?'rewrites':'copyedits'}${attempt?'/'+attempt:''}${suffix}`;
  const extra=()=>adapter.extraBody?.(current)||{};
  const panel=document.createElement('details'),summary=document.createElement('summary');
  panel.className='copyedit-review';uiText(summary,"textContent",()=>(t(rewrite?'rewrite.review':'m_bffeda2756af')));panel.append(summary);host.append(panel);
  const help=document.createElement('p');uiText(help,"textContent",()=>(t(rewrite?'rewrite.review_help':'m_57d964c1b1d5')));
  const label=document.createElement('label');uiText(label,"textContent",()=>(t(rewrite?'rewrite.proposal':'m_7d99bd9b5f5c')));const select=document.createElement('select');uiAttr(select,'aria-label',()=>(t(rewrite?'rewrite.proposal':'m_7d99bd9b5f5c')));label.append(select);
  const open=document.createElement('button');open.type='button';open.className='secondary';uiText(open,"textContent",()=>(t("m_36054168b4b9")));
  const info=document.createElement('p');info.setAttribute('role','status');
  const edits=document.createElement('div');edits.className='copyedit-items';
  const apply=document.createElement('button');apply.type='button';uiText(apply,"textContent",()=>(t(rewrite?'rewrite.apply':'m_fe2b5dd6eb18')));
  apply.setAttribute('data-review-accept','');
  const showSelection=document.createElement('button');showSelection.type='button';showSelection.className='secondary';uiText(showSelection,"textContent",()=>(t("m_2a4b06799113")));
  const selectedText=document.createElement('pre');selectedText.className='copyedit-selected-text';uiAttr(selectedText,'aria-label',()=>(t("m_a55579f6a944")));
  const warnings=document.createElement('p');warnings.className='muted';
  const classify=document.createElement('button');classify.type='button';classify.className='secondary';uiText(classify,"textContent",()=>(t("m_ea091064bccc")));
  const classificationInfo=document.createElement('p');classificationInfo.className='muted';
  panel.append(help,label,open,info,warnings,edits,showSelection,selectedText,apply,classify,classificationInfo);
  let current=null,choices=[],busy=false,previewLoading=false,sceneId=null,listEpoch=0,previewEpoch=0;
  let assembled=null,selectionLoading=false,selectionEpoch=0;
  function clearSelection(){assembled=null;selectionEpoch++;selectionLoading=false;uiText(selectedText,"textContent",()=>(''));uiText(warnings,"textContent",()=>(''));uiText(classificationInfo,"textContent",()=>(''))}
  const indices=()=>choices.flatMap(c=>c.checked?c.editIndices:[]).sort((a,b)=>a-b);
  const selectionKey=()=>JSON.stringify(indices());
  const unresolved=()=>choices.some(c=>c.indeterminate);
  const selectionReady=()=>!unresolved()&&(current?.protocol_version!==2||(assembled?.fingerprint===current.proposal_fingerprint&&assembled?.key===selectionKey()));
  const hasChanges=()=>!!current&&(current.has_changes??current.edits.some(e=>e.original!==e.replacement));
  function reason(){return busy?t("m_08ee1e43995d"):previewLoading?t("m_e1dafad3f121"):!state.scene?t("m_f0f1417db6de"):state.saving?t("m_1322882bbef7"):state.dirty?t("m_a4c2e86ecc1a"):state.characterDirty?t("m_c2fa0cfd122f"):!current?t("m_7e42688654c2"):!hasChanges()?t("m_c0b819b5b279"):!current.can_apply?(current.reason||t("m_1f54fb7a81a9")):''}
  function updateAvailability(){onAvailability({ready:!reason().trim()&&selectionReady(),reason:reason().trim()||(!selectionReady()?t("m_0cd4e9e1948c"):''),hasChanges:hasChanges(),pending:hasChanges()&&!current?.decisions?.length&&!!current?.can_apply});help.hidden=!!current&&!hasChanges();classificationInfo.hidden=!hasChanges();apply.hidden=!!current&&!hasChanges();showSelection.hidden=!!current&&!hasChanges();selectedText.hidden=!hasChanges();const message=reason().trim();apply.disabled=!!message||!selectionReady();uiText(apply,"title",()=>(diagnostic(message)||(unresolved()?t("m_f5ad568e5569"):!selectionReady()?t("m_7c6afe03778e"):'')));for(const input of choices)input.disabled=!!message;open.disabled=busy||!state.scene;select.disabled=busy||!state.scene;showSelection.disabled=!!message||selectionLoading||unresolved();classify.hidden=rewrite||current?.protocol_version!==2||!hasChanges();classify.disabled=!!message||!current?.can_classify;uiText(classify,"title",()=>(diagnostic(current?.classification_reason)||diagnostic(message)));uiText(info,"textContent",()=>(diagnostic(message)||t("m_9ac04dc56df6",{p0:(choices.filter(c=>c.checked).length),p1:(choices.length),p2:(current.decisions.length)})+(unresolved()?t("m_521285129056"):!selectionReady()?t("m_f821edf97ae7"):'')))}
  function render(data,preserved=null){
    if(!preserved)clearSelection();
    adapter.onReview?.(data);
    current=data;choices=[];edits.replaceChildren();
    const selected=preserved||new Set(data.decisions.length?data.decisions.at(-1).selected_indices:(data.default_selected_indices??data.edits.map((_,i)=>i)));
    uiText(warnings,"textContent",()=>((data.warnings||[]).join(' ')));
    const history=data.classification_history||[],last=history.at(-1);
    const statuses={get completed(){return t("m_71fb1279f355")},get failed(){return t("m_5d7bd00d31cf")},get running(){return t("m_e36f5ec8b962")},get cancelled(){return t("m_7b52c9f5fa73")},get interrupted(){return t("m_df6c9d11fd91")}};
    uiText(classificationInfo,"textContent",()=>((data.classification_provider?t("m_9012a3510d66",{p0:(data.classification_provider.model),p1:(data.classification_provider.provider)}):'')+(data.classification?t("m_791e2bfe3efc",{p0:(data.classification_advice_model||'')}):'')+(last?t("m_c3b35dc36426",{p0:(statuses[last.state]||last.state),p1:(diagnostic(last.error)?' · '+diagnostic(last.error):'')}):(diagnostic(data.classification_reason)||''))));
    const rows=data.groups??data.edits.map((edit,index)=>({...edit,indices:[index]}));
    for(const edit of (hasChanges()?rows:[])){
      const item=document.createElement('label');item.className='copyedit-item';
      const input=document.createElement('input');input.type='checkbox';input.editIndices=edit.indices;input.checked=edit.indices.every(index=>selected.has(index));input.indeterminate=!input.checked&&edit.indices.some(index=>selected.has(index));input.onchange=()=>{input.indeterminate=false;selectionEpoch++;if(!selectionReady())uiText(selectedText,"textContent",()=>(t("m_94bbf9a6cf09")));updateAvailability()};choices.push(input);
      const content=document.createElement('span'),kind=document.createElement('strong');uiText(kind,"textContent",()=>({get grammar(){return t("m_47cc828f5912")},get spelling(){return t("m_d24ca9b3179c")},get punctuation(){return t("m_50d0f64a2654")},get wording(){return t("m_a668090555ad")},get unclassified(){return t("m_8537b35c8b70")},get mixed(){return t("m_263fd5722361")}}[edit.category]||edit.category));
      const original=document.createElement('del');uiText(original,"textContent",()=>(edit.original));
      const replacement=document.createElement('ins');uiText(replacement,"textContent",()=>(edit.replacement));
      content.append(kind);
      for(const [caption,change,parts,tag]of [[msg("m_d3481e5cb0ae"),original,edit.before_parts,'del'],[msg("m_729db2d9951b"),replacement,edit.after_parts,'ins']]){
        const sentence=document.createElement('p');sentence.className='copyedit-sentence';
        const label=document.createElement('span');label.className='copyedit-line-label';uiText(label,"textContent",()=>(caption));
        const before=document.createElement('span');uiText(before,"textContent",()=>(edit.context_before||''));
        const after=document.createElement('span');uiText(after,"textContent",()=>(edit.context_after||''));
        if(parts){sentence.append(label);for(const part of parts){const span=document.createElement(part.changed?tag:'span');uiText(span,"textContent",()=>(part.text));sentence.append(span)}}
        else sentence.append(label,before,change,after);
        content.append(sentence);
      }
      if(rewrite){const location=document.createElement('small');uiText(location,'textContent',()=>t('rewrite.location.'+edit.location));content.append(location);}
      for(const index of edit.indices){
      const advice=data.classification?.changes.find(c=>c.index===index);
      if(advice){const hint=document.createElement('small');const categories={get grammar(){return t("m_47cc828f5912")},get spelling(){return t("m_d24ca9b3179c")},get punctuation(){return t("m_50d0f64a2654")},get wording(){return t("m_a668090555ad")},get style(){return t("m_f6a2879f703d")},get meaning(){return t("m_b27ca992c5f6")},get formatting(){return t("m_ec4994865a1d")},get mixed(){return t("m_1c3a73c9781a")},get uncertain(){return t("m_f6894ee2b8e7")}},assessments={get improvement(){return t("m_1fbe594daa88")},get regression(){return t("m_08e7332a4fd3")},get neutral(){return t("m_7213794ddfa8")},get uncertain(){return t("m_d35f25d1cbc6")}};uiText(hint,"textContent",()=>(t("m_9bc97c4b9891",{p0:(categories[advice.category]||advice.category),p1:(assessments[advice.assessment]||advice.assessment),p2:(advice.explanation)})));content.append(hint)}
      }
      item.append(input,content);edits.append(item);
    }
    if(!hasChanges())for(const option of select.children){if(option.value===data.attempt_id)uiText(option,"textContent",()=>option.dataset.createdAt+t("m_d0e75138d549"))}
    if(!hasChanges()){const empty=document.createElement('p');uiText(empty,"textContent",()=>(t("m_9dff3d6086f5")));edits.append(empty)}
    if(!indices().length){assembled={fingerprint:data.proposal_fingerprint,key:selectionKey(),text:data.original,warnings:[]};uiText(selectedText,"textContent",()=>(data.original))}
    else uiText(selectedText,"textContent",()=>(selectionReady()?assembled?.text||data.preview:t("m_3470cfbe73cc")));
    if(selectionReady()&&assembled)uiText(warnings,"textContent",()=>((assembled.warnings||[]).join(' ')));
    updateAvailability();
  }
  async function loadPreview(){
    if(!state.scene||!select.value){adapter.onReview?.(null);current=null;choices=[];clearSelection();edits.replaceChildren();updateAvailability();return}
    const selectedId=select.value,scene=state.scene.id,epoch=++previewEpoch;
    const previousFingerprint=current?.proposal_fingerprint;
    const preserved=current?.attempt_id===selectedId&&!unresolved()?new Set(indices()):null;
    current=null;previewLoading=true;updateAvailability();
    try{
      const data=await api(url(scene,selectedId));
      if(epoch!==previewEpoch||state.scene?.id!==scene||select.value!==selectedId)return;
      render(data,previousFingerprint===data.proposal_fingerprint?preserved:null);
    }catch(error){if(epoch===previewEpoch){current=null;choices=[];edits.replaceChildren();notice(error.message,'error')}}
    finally{if(epoch===previewEpoch){previewLoading=false;updateAvailability()}}
  }
  async function reload(){
    const epoch=++listEpoch,scene=state.scene?.id;
    if(scene!==sceneId){adapter.onReview?.(null);sceneId=scene;current=null;choices=[];clearSelection();previewLoading=false;edits.replaceChildren();select.replaceChildren();previewEpoch++}
    if(!scene){updateAvailability();return}
    try{
      const data=await api(url(scene));
      if(epoch!==listEpoch||scene!==state.scene?.id)return;
      const previous=select.value;select.replaceChildren();
      for(const attempt of [...data.attempts].reverse()){const option=document.createElement('option');option.value=attempt.id;option.dataset.createdAt=attempt.created_at.slice(0,19);uiText(option,"textContent",()=>(attempt.created_at.slice(0,19)+(attempt.state==='needs_review'?t("m_3e50d5900f81"):'')));select.append(option)}
      select.value=data.attempts.some(a=>a.id===previous)?previous:data.attempts.at(-1)?.id||'';
      await loadPreview();
    }catch(error){if(epoch===listEpoch){current=null;updateAvailability();uiText(info,"textContent",()=>(diagnostic(error.message)))}}
  }
  select.onchange=()=>loadPreview();open.onclick=()=>loadPreview();
  showSelection.onclick=async()=>{
    if(reason().trim()||unresolved())return;
    const captured={sceneId:state.scene.id,attemptId:current.attempt_id,fingerprint:current.proposal_fingerprint,key:selectionKey(),epoch:++selectionEpoch};
    selectionLoading=true;updateAvailability();
    try{
      const result=await api(url(captured.sceneId,captured.attemptId,'/selection-preview'),json('POST',{expected_revision:current.expected_revision,proposal_fingerprint:captured.fingerprint,selected_indices:indices(),...extra()}));
      if(captured.epoch!==selectionEpoch||state.scene?.id!==captured.sceneId||current?.attempt_id!==captured.attemptId||selectionKey()!==captured.key)return;
      assembled={fingerprint:captured.fingerprint,key:captured.key,text:result.text,warnings:result.warnings||[]};uiText(selectedText,"textContent",()=>(result.text));uiText(warnings,"textContent",()=>(assembled.warnings.join(' ')));
    }catch(error){notice(error.message,'error')}
    finally{selectionLoading=false;updateAvailability()}
  };
  classify.onclick=async()=>{
    if(reason().trim()||!current?.can_classify)return;
    busy=true;updateAvailability();
    try{
      const run=await api(`/api/scenes/${state.scene.id}/copyedits/${current.attempt_id}/classify`,json('POST',{request_id:crypto.randomUUID(),proposal_fingerprint:current.proposal_fingerprint}));
      onQueued(run);
      notice(msg("m_88f76dd58257"));
      await reload();
    }catch(error){notice(error.message,'error')}
    finally{busy=false;updateAvailability()}
  };
  apply.onclick=async()=>{
    if(reason().trim()||!selectionReady())return;
    const captured={sceneId:state.scene.id,epoch:state.bufferEpoch};
    const body={expected_revision:current.expected_revision,proposal_fingerprint:current.proposal_fingerprint,selected_indices:indices(),...extra()};
    const attemptId=current.attempt_id;busy=true;updateAvailability();
    try{
      const result=await api(url(captured.sceneId,attemptId,rewrite?'/apply':''),json('POST',body));
      current=null;await onApplied(result,captured);if(result.run)onQueued(result.run);await reload();notice(result.run?.request.mode==='edit_loop'?t("m_24c5f6514ee7"):t("m_99a2b5aeacca"));
    }catch(error){notice(error.message,'error');uiText(info,"textContent",()=>(diagnostic(error.message)))}
    finally{busy=false;updateAvailability()}
  };
  adapter.panel?.(panel);
  updateAvailability();
  return {reload,updateAvailability,accept:async()=>{
    if(apply.hidden||apply.disabled)throw new Error(apply.title||reason()||t("m_7c6afe03778e"));
    return apply.onclick();
  }};
}

