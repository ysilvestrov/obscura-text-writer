import {t,msg,uiText,uiAttr,formatDate,diagnostic} from './i18n.js';
// Author review of the protagonist core and threads under the scene memory. Edits stay a local draft until Confirm.
const editKey=item=>item.kind==='slot'?`slot:${item.character_id}:${item.slot}`:`thread:${item.claim_id}`;
const STATUS={changed:"m_c36221796c0b",unknown:"m_5f3c207c48c1",introduced:"m_64ca270e7933",author:"m_977e9d0f23a1",unchanged:"m_945c711369db",open:"m_bf02883817ec",closed:"m_2e4c6dc14e41"};

export function coreReviewModel(review,edits=[]){
  const drafts=new Map(edits.map(edit=>[editKey(edit),edit])),canKeep=!!review?.has_wire,changed=[],quiet=[];
  const place=(row,isQuiet)=>{
    row.key=editKey(row);row.edit=drafts.get(row.key)||null;
    // Keeping the previous state only means something for a change the model answered.
    row.keepable=canKeep&&!isQuiet;
    // Without a model answer a closed thread is gone from the journal and cannot be closed again.
    row.writable=!(row.kind==='thread'&&row.status==='closed'&&!canKeep);
    (isQuiet?quiet:changed).push(row);
  };
  for(const slot of review?.slots||[])place({...slot,kind:'slot'},slot.status==='unchanged');
  for(const thread of review?.threads||[])place({...thread,kind:'thread'},thread.status==='open');
  return {groups:[{kind:'changed',rows:changed},{kind:'quiet',rows:quiet}],canKeep,dirty:edits.length>0};
}

// Navigation guard shared with the workspace: unsaved table edits or a core review draft need the same confirmation.
export async function confirmUnsaved(state,ask,message){
  const core=!!state.coreReview?.dirty();
  if((state.dirty||core)&&!await ask(message))return false;
  if(core)state.coreReview.discard();
  return true;
}

export function installCoreReview({container,api,json,notice,refresh}){
  const node=(tag,render,className)=>{const n=document.createElement(tag);if(render)uiText(n,'textContent',render);if(className)n.className=className;return n;};
  const plain=(tag,text,className)=>{const n=document.createElement(tag);n.textContent=text;if(className)n.className=className;return n;};
  const action=(render,onclick,className='secondary')=>{const b=node('button',render,className);b.type='button';b.onclick=onclick;return b;};
  container.className='core-review';
  let sceneId=null,review=null,edits=[],quoteScenes=new Map(),busy=false,token=0,quietOpen=false,entry=null,scenes=null,message=null;
  const setEdit=edit=>{edits=[...edits.filter(e=>editKey(e)!==editKey(edit)),edit];};
  const dropEdit=key=>{edits=edits.filter(e=>editKey(e)!==key);quoteScenes.delete(key);};

  function draftLine(row){
    const edit=row.edit;if(!edit)return null;
    if(edit.action==='keep')return node('p',()=>t("m_9d19ce0f56f9"),'core-review-draft');
    if(edit.quote)return node('p',()=>t("m_aef1db24dd30",{p0:edit.text,p1:quoteScenes.get(row.key)??'',p2:edit.quote}),'core-review-draft');
    return node('p',()=>t("m_66aa12a8d829",{p0:edit.text}),'core-review-draft');
  }

  function drawRow(row){
    const item=node('div',null,'core-review-row');
    const head=node('div',null,'core-review-row-head');
    head.append(row.kind==='slot'?plain('strong',`${row.name} · ${row.label}`):node('strong',()=>t("m_55efe6827e59")),node('span',()=>t(STATUS[row.status]||"m_945c711369db"),'core-review-status'));
    if(row.reader_unknown)head.append(node('span',()=>t("m_4b5d628f8944"),'core-review-reader-unknown'));
    item.append(head);
    if(row.kind==='slot'){
      item.append(node('p',()=>t("m_8d7af7d5d97e",{p0:row.before??'—'})),node('p',()=>t("m_26760a5cbc8a",{p0:row.after??'—'})));
      if(row.reason)item.append(node('p',()=>t("m_c34f25b3688f",{p0:row.reason}),'core-review-reason'));
    }else{
      item.append(plain('p',row.text));
      if(row.resolution)item.append(node('p',()=>t("m_3383cf04c303",{p0:row.resolution})));
    }
    const draft=draftLine(row);if(draft)item.append(draft);
    const actions=node('div',null,'actions core-review-actions');
    const accept=action(()=>t("m_21a176209a54"),()=>{dropEdit(row.key);if(entry?.row.key===row.key)entry=null;render();});
    accept.setAttribute('aria-pressed',String(!row.edit));
    const keep=action(()=>t("m_6b51735eba72"),()=>{
      if(!row.keepable)return;
      setEdit(row.kind==='slot'?{kind:'slot',character_id:row.character_id,slot:row.slot,action:'keep'}:{kind:'thread',claim_id:row.claim_id,action:'keep'});
      quoteScenes.delete(row.key);if(entry?.row.key===row.key)entry=null;render();
    });
    keep.disabled=busy||!row.keepable;keep.setAttribute('aria-pressed',String(row.edit?.action==='keep'));
    if(!review.has_wire)uiAttr(keep,'title',()=>t("m_cbac23a1bbac"));
    accept.disabled=busy;actions.append(accept,keep);
    if(row.writable){const write=action(()=>t("m_6ffe74d9820d"),()=>void openEntry(row));write.disabled=busy;write.setAttribute('aria-expanded',String(entry?.row.key===row.key));actions.append(write);}
    item.append(actions);
    if(entry?.row.key===row.key)item.append(entry.form);
    return item;
  }

  async function loadFragments(){
    if(!entry)return;
    const current=entry,mine=++current.requests;
    const params=new URLSearchParams({scene_id:current.scene.value,q:current.search.value.trim()});
    try{
      const found=await api(`/api/scenes/${sceneId}/core-review/fragments?${params}`);
      if(entry!==current||mine!==current.requests)return;
      current.fragments=found;drawFragments(current);
    }catch(error){if(entry===current)uiText(current.error,'textContent',()=>diagnostic(error.message));}
  }

  function drawFragments(current){
    const name=`core-quote-${current.id}`,options=[];
    const choice=(value,label,checked,onPick)=>{
      const wrap=node('label',null,'core-review-fragment'),input=document.createElement('input');
      input.type='radio';input.name=name;input.value=value;input.checked=checked;input.onchange=()=>{if(input.checked){onPick();hint();}};
      wrap.append(input,label);options.push(wrap);
    };
    const hint=()=>{current.hint.hidden=current.quote!==null;};
    choice('',node('span',()=>t("m_1479e5c2cb3d")),current.quote===null,()=>{current.quote=null;});
    for(const fragment of current.fragments)choice(fragment.fragment_id,plain('span',fragment.text),current.quote?.version_id===fragment.version_id&&current.quote?.fragment_id===fragment.fragment_id,()=>{current.quote=fragment;});
    if(!current.fragments.length)options.push(node('p',()=>t("m_828594f9e3f6"),'core-review-empty'));
    current.list.replaceChildren(...options);hint();
  }

  async function openEntry(row){
    if(busy)return;
    const id=(entry?.id||0)+1;
    const form=node('div',null,'core-review-entry');
    const valueLabel=node('label',()=>t(row.kind==='slot'?"m_2178c46a2715":"m_50916ca6edb7"));
    const value=document.createElement('textarea');value.rows=2;
    value.value=row.edit&&row.edit.action!=='keep'?row.edit.text:(row.kind==='slot'?row.after:row.resolution)||'';
    valueLabel.append(value);
    const sceneLabel=node('label',()=>t("m_2ad164570ac4")),scene=document.createElement('select');sceneLabel.append(scene);
    const search=document.createElement('input');search.type='search';
    uiAttr(search,'aria-label',()=>t("m_06ea5237c029"));uiText(search,'placeholder',()=>t("m_06ea5237c029"));
    const fieldset=node('fieldset'),legend=node('legend',()=>t("m_91789239325d")),list=node('div',null,'core-review-fragments');
    fieldset.append(legend,list);
    const hint=node('p',()=>t("m_78a08c916f39"),'core-review-hint'),error=node('p',null,'core-review-error');error.setAttribute('role','alert');
    const buttons=node('div',null,'actions');
    const current={id,row,form,value,initial:value.value,scene,search,list,hint,error,fragments:[],quote:null,requests:0};
    const apply=action(()=>t("m_387b53c52751"),()=>{
      const text=value.value.trim();
      if(!text){uiText(error,'textContent',()=>t("m_b75b76095819"));return;}
      const quote=current.quote;
      setEdit(row.kind==='slot'
        ?{kind:'slot',character_id:row.character_id,slot:row.slot,action:'set',text,quote:quote?.text??null,evidence_version_id:quote?.version_id??null}
        :{kind:'thread',claim_id:row.claim_id,action:'close',text,quote:quote?.text??null,evidence_version_id:quote?.version_id??null});
      if(quote)quoteScenes.set(row.key,quote.scene_number);else quoteScenes.delete(row.key);
      entry=null;render();
    },'');
    const cancel=action(()=>t("m_8b4c2025378a"),()=>{entry=null;render();});
    buttons.append(apply,cancel);
    form.append(valueLabel,sceneLabel,search,fieldset,hint,error,buttons);
    scene.onchange=()=>{current.quote=null;return loadFragments();};
    search.oninput=()=>void loadFragments();
    entry=current;render();
    try{
      scenes??=await api(`/api/scenes/${sceneId}/core-review/scenes`);
      if(entry!==current)return;
      for(const item of scenes){const option=plain('option',`${item.scene_number}. ${item.title}`);option.value=item.scene_id;scene.append(option);}
      scene.value=scenes.some(item=>item.scene_id===review.scene_id)?review.scene_id:scenes.at(-1)?.scene_id||'';
      await loadFragments();
    }catch(error){if(entry===current)uiText(current.error,'textContent',()=>diagnostic(error.message));}
    value.focus?.();
  }

  async function submitReview(){
    if(busy||!review?.memory_version_id)return;
    busy=true;render();
    const body={expected_revision:review.revision,memory_version_id:review.memory_version_id,edits:edits.map(edit=>({...edit}))};
    const mine=token;
    try{
      const result=await api(`/api/scenes/${sceneId}/core-review`,json('POST',body));
      if(mine!==token)return;
      review=result;edits=[];quoteScenes=new Map();entry=null;busy=false;render();
      notice(msg("m_87fd861aed45"));
      await refresh?.();
    }catch(error){
      notice(error.message,'error');
      // A conflict means the memory head moved (or the edits were saved but not confirmed): show the current state.
      if(error.status===409&&mine===token){busy=false;edits=[];quoteScenes=new Map();entry=null;await load(sceneId);try{await refresh?.();}catch{}}
    }finally{if(mine===token&&busy){busy=false;render();}}
  }

  function render(){
    container.replaceChildren();
    container.append(node('h3',()=>t("m_4ed5b1fa6c48")));
    if(message){container.append(message);return;}
    if(!review)return;
    const status=node('p',null,'core-review-state');status.setAttribute('role','status');
    if(review.memory_version_id){
      const confirmed=review.confirmation;
      uiText(status,'textContent',()=>confirmed?t("m_be008b8fe036",{p0:formatDate(confirmed.confirmed_at)}):t("m_3d2a1535c4bf"));
      status.setAttribute("data-confirmed",String(!!confirmed));
      container.append(status);
    }
    if(!review.slots?.length)container.append(node('p',()=>t("m_023750a5d0ec"),'core-review-empty'));
    const model=coreReviewModel(review,edits);
    const [changed,quiet]=model.groups;
    if(changed.rows.length){
      const section=node('section',null,'core-review-group');
      section.append(node('h4',()=>t("m_8c18450d0141",{p0:changed.rows.length})),...changed.rows.map(drawRow));
      container.append(section);
    }
    if(quiet.rows.length){
      const details=node('details',null,'core-review-group core-review-quiet');details.open=quietOpen;
      details.ontoggle=()=>{quietOpen=details.open;};
      details.append(node('summary',()=>t("m_a83ab9a72df2",{p0:quiet.rows.length})),...quiet.rows.map(drawRow));
      container.append(details);
    }
    if(review.memory_version_id){
      const footer=node('div',null,'actions');
      const submit=action(()=>edits.length?t("m_02d42f8c1439",{p0:edits.length}):t("m_6842aa7e5803"),()=>submitReview(),'core-review-confirm');
      submit.disabled=busy;footer.append(submit);container.append(footer);
    }
  }

  const dirty=()=>edits.length>0||!!(entry&&(entry.quote!==null||entry.value.value.trim()!==String(entry.initial).trim()));
  function discard(){edits=[];quoteScenes=new Map();entry=null;render();}

  async function load(id){
    // A reload of the same scene keeps the draft while the memory head it was made for is still current.
    const mine=++token,same=id===sceneId&&!!review,previous=same?review.memory_version_id:undefined;
    sceneId=id;scenes=null;
    if(!same){review=null;edits=[];quoteScenes=new Map();entry=null;busy=false;message=node('p',()=>t("m_6c90869b1735"),'core-review-state');render();}
    try{
      const result=await api(`/api/scenes/${id}/core-review`);
      if(mine!==token)return;
      if(same&&result.memory_version_id!==previous){
        if(dirty())notice(msg("m_7016d90fae72"),'error');
        edits=[];quoteScenes=new Map();entry=null;
      }
      review=result;message=null;render();
    }catch(error){
      if(mine!==token)return;
      message=node('p',()=>diagnostic(error.message),'core-review-error');render();
    }
  }
  return {load,dirty,discard};
}
