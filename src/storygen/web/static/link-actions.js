// VALID-LINKS-S08/S11: the rows of the link panel of the open scene and the actions each row offers. Pure: the panel
// (link-decision.js) renders them. An approval goes only to an unchecked link (the server refuses Z3 `unavailable`);
// a memory action launches the memory stage of the named scene through the usual preview and consent; rebuild launches
// «Перебудувати пам’ять» from the scene; a carry action resumes or cancels the stalled carry run (MEMORY-CARRY).
const UNCHECKED={
  brief:{text:'link.brief_unchecked',approve:'link.approve_brief'},
  prose:{text:'link.prose_unchecked',approve:'link.approve_prose'},
  memory:{text:'link.memory_unchecked',approve:'link.keep_memory',memory:'link.new_memory'},
};
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
    const rule=state?.status==='unchecked'?UNCHECKED[link]:link==='memory'&&state?.status==='unavailable'?MEMORY_UNAVAILABLE[state.reason]:null;
    if(!rule)continue;
    const actions=[];
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
