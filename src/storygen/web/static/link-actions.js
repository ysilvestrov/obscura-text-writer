// VALID-LINKS-S08/S11: the rows of the link panel of the open scene and the actions each row offers. Pure: the panel
// (link-decision.js) renders them. An approval goes only to an unchecked link (the server refuses Z3 `unavailable`);
// a memory action launches the memory stage of the named scene through the usual preview and consent; rebuild launches
// «Перебудувати пам’ять» from the scene; a carry action resumes or cancels the stalled carry run (MEMORY-CARRY).
import {dollars} from "./run-summary.js";

const UNCHECKED={
  brief:{text:'link.brief_unchecked',approve:'link.approve_brief'},
  prose:{text:'link.prose_unchecked',approve:'link.approve_prose'},
  memory:{text:'link.memory_unchecked',approve:'link.keep_memory',memory:'link.new_memory'},
};
// VALID-LINKS: the auditor's discrepancy is a hint to reread the scene (its stated reasons are often imprecise); the
// author approves the link or, for Z3, creates a new memory, as for an unchecked link.
const DISCREPANCY={brief:'link.brief_discrepancy',prose:'link.prose_discrepancy',memory:'link.memory_discrepancy'};
// The auditor's own `unavailable` verdict: its reason (a server text); an input over its limits offers its settings.
const OVERFLOW='Вхід перевірки перевищує ліміт Ревізора';
const MEMORY_UNAVAILABLE={
  no_memory:{text:'link.no_memory',memory:'link.create_memory'},
  carry_pending:{text:'link.carry_pending'},
  carry_failed:{text:'link.carry_failed',memory:'link.new_memory',rebuild:'link.rebuild_memory'},
};

export function pendingLinks(materialStatus,sceneId,scenes=[]){
  const row=(materialStatus||{})[sceneId];
  const links=row?.links||{};
  const items=[];
  // Brief and prose share one reason: the scene they continue has no memory. The previous scene is named only when it
  // is a plain earlier scene (server: previous_scene_id); a merge to confirm or a series start gets the explanation.
  if(['brief','prose'].some(link=>links[link]?.status==='unavailable'&&links[link].reason==='no_previous_memory')){
    const previous=row.previous_scene_id&&scenes.find(scene=>scene.id===row.previous_scene_id);
    items.push(previous
      ?{key:'previous',text:'link.no_previous_memory',params:{p0:previous.title},actions:[{type:'memory',sceneId:previous.id,label:'link.create_memory'}]}
      :{key:'previous',text:'link.no_previous_memory_other',params:{},actions:[]});
  }
  for(const link of ['brief','prose','memory']){
    const state=links[link];
    if(state?.status==='discrepancy'){
      const actions=[{type:'approve',link,fingerprint:state.fingerprint,label:UNCHECKED[link].approve}];
      if(UNCHECKED[link].memory)actions.push({type:'memory',sceneId,label:UNCHECKED[link].memory});
      items.push({key:link,text:DISCREPANCY[link],params:{p0:state.confidence??'—'},discrepancies:state.discrepancies||[],
        summary:state.summary??null,actions});
      continue;
    }
    if(state?.status==='unavailable'&&state.source==='auditor'){
      const reason=state.reason||'';
      items.push({key:link,text:'link.audit_unavailable',params:{},reason,
        actions:reason.startsWith(OVERFLOW)?[{type:'settings',label:'link.open_auditor_settings'}]:[]});
      continue;
    }
    const rule=state?.status==='unchecked'?UNCHECKED[link]:link==='memory'&&state?.status==='unavailable'?MEMORY_UNAVAILABLE[state.reason]:null;
    if(!rule)continue;
    const actions=[];
    const failed=state.reason==='carry_pending'&&row.carry_failed_scene_id&&scenes.find(scene=>scene.id===row.carry_failed_scene_id);
    if(failed){
      items.push({key:link,text:'link.carry_blocked',params:{p0:failed.title},actions:[
        {type:'memory',sceneId:failed.id,label:'link.new_memory'},{type:'rebuild',sceneId:failed.id,label:'link.rebuild_memory'}]});
      continue;
    }
    if(state.reason==='carry_pending'&&row.carry_run){
      const runId=row.carry_run.id;
      items.push({key:link,text:'link.carry_stalled',params:{},actions:[
        {type:'carry',runId,command:'resume',label:'link.carry_resume'},
        {type:'carry',runId,command:'cancel',label:'link.carry_cancel'}]});
      continue;
    }
    if(rule.approve)actions.push({type:'approve',link,fingerprint:state.fingerprint,label:rule.approve});
    if(rule.memory)actions.push({type:'memory',sceneId,label:rule.memory});
    if(rule.rebuild)actions.push({type:'rebuild',sceneId,label:rule.rebuild});
    items.push({key:link,text:rule.text,params:{},actions});
  }
  return items;
}

// VALID-LINKS-S15: the rows of the «Узгодженість сцени» panel. Always three rows (brief → prose → memory) built from the
// links of the scene and the items of pendingLinks; the render (link-decision.js) draws them.
const LINKS=['brief','prose','memory'];
const STATE={valid:'ok',unchecked:'pending',discrepancy:'discrepancy',unavailable:'unavailable'};
const ICON={ok:'✓',pending:'○',discrepancy:'!',unavailable:'—',missing:'·'};
const key=(name,params={})=>({key:name,params});

function isBookStop(run,sceneId){
  return run?.request?.mode==='audit'&&run.request.audit_scope==='story'&&run.state==='needs_review'&&run.checkpoint?.scene_id===sceneId;
}

// Г4: the approval of a brief or prose link is worded by the state it decides; the memory keeps its own labels.
function relabel(actions,link,label){
  return (actions||[]).map(action=>action.type==='approve'&&link!=='memory'?{...action,label}:action);
}

function consistencyRow(link,state,item){
  const kind=STATE[state?.status]||'missing';
  const row={link,title:`consistency.row_${link}`,state:kind,icon:ICON[kind],status:null,actions:[]};
  if(kind==='ok'){
    const suffix=state.source==='auditor'?'_auditor':state.source==='author'?'_author':'';
    row.status=key('consistency.state_ok'+suffix);
  }else if(kind==='missing')row.status=key('consistency.state_missing');
  else if(kind==='pending'){
    row.status=key(link==='memory'?'link.memory_unchecked':'consistency.state_pending');
    row.actions=relabel(item?.actions,link,'consistency.approve_self');
  }else if(kind==='discrepancy'){
    row.status=key('consistency.state_discrepancy',{p0:state.confidence??'—'});
    row.confidence=state.confidence??null;
    row.summary=state.summary??null;
    row.discrepancies=state.discrepancies||[];
    row.actions=relabel(item?.actions,link,'consistency.no_discrepancy');
  }else if(state.source==='auditor'){
    row.status=key('link.audit_unavailable');
    row.reason=state.reason||'';
    row.actions=item?.actions||[];
  }else if(item){
    row.status=key(item.text,item.params);
    row.actions=item.actions;
  }else row.status=key('consistency.state_pending');
  return row;
}

export function sceneConsistency(materialStatus,sceneId,scenes=[],run=null,preview=null,blocked=''){
  const scene=(materialStatus||{})[sceneId];
  const links=scene?.links||{};
  const items=pendingLinks(materialStatus,sceneId,scenes);
  const previousItem=items.find(item=>item.key==='previous');
  // Г3: the previous scene's memory sits once, on the brief row when the brief is unavailable for it, otherwise on prose.
  const needsPrevious=link=>links[link]?.status==='unavailable'&&links[link].reason==='no_previous_memory';
  const previousOwner=previousItem?(needsPrevious('brief')?'brief':'prose'):null;
  const rows=LINKS.map(link=>{
    if(needsPrevious(link)&&link!==previousOwner){
      return {...consistencyRow(link,links[link],null),status:key('consistency.state_needs_previous')};
    }
    return consistencyRow(link,links[link],link===previousOwner?previousItem:items.find(entry=>entry.key===link));
  });
  const pendingCount=rows.filter(row=>['pending','discrepancy','unavailable'].includes(row.state)).length;
  const total=rows.filter(row=>row.state!=='missing').length;
  const stop=isBookStop(run,sceneId);
  const view=stop?'full':scene?.validity==='valid'?'valid':pendingCount===0?'none':'full';
  let primary;
  if(stop){
    const checkpoint=run.checkpoint;
    // Г6: ready when the stop link was decided (its status left the outcome) or the Auditor itself was unavailable.
    const ready=links[checkpoint.link]?.status!==checkpoint.outcome||checkpoint.outcome==='unavailable';
    const reason=blocked?{text:blocked}:ready?null:key('consistency.resolve_first');
    primary={action:'resume',runId:run.id,label:'consistency.resume',disabled:reason!==null,reason};
  }else{
    let reason=null;
    if(blocked)reason={text:blocked};
    else if(preview&&!preview.ready)reason={text:preview.reason};
    else if(preview&&preview.calls===0)reason=key('consistency.nothing_to_audit');
    let detail=null;
    if(preview?.ready){
      const usd=preview.cost?.total_usd;
      detail=usd==null?key('consistency.audit_calls',{p0:preview.calls}):key('consistency.audit_cost',{p0:preview.calls,p1:dollars(Number(usd))});
    }
    primary={action:'audit',label:'consistency.audit',detail,disabled:!preview||reason!==null,reason};
  }
  return {view,pendingCount,total,rows,primary,resume:primary.action==='resume'};
}
