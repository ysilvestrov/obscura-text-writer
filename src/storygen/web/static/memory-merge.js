// MEMORY-MERGE-S04: pure helpers of the «Memory merge» window over GET /api/stories/{id}/memory-merges.
// A row is one conflict: the value of every head that changed it, the author's choice (a head id or 'author') and own text.

export function mergeRows(state){
  const carried=state?.carried||{};
  const heads=state?.heads||[];
  return (state?.conflicts||[]).map(conflict=>{
    const decision=carried[conflict.key];
    return {
      key:conflict.key,label:conflict.label,
      values:heads.filter(head=>Object.hasOwn(conflict.values,head.scene_id))
        .map(head=>({headId:head.scene_id,title:`${head.number}. ${head.title}`,arcs:head.arc_titles||[],value:conflict.values[head.scene_id]})),
      choice:decision?.choice||null,text:decision?.text||'',carried:!!decision,
    };
  });
}

const sameValues=(a,b)=>JSON.stringify(a.values.map(v=>[v.headId,v.value]))===JSON.stringify(b.values.map(v=>[v.headId,v.value]));

// After a refused save the state is read again; a choice stays only where the conflict is the same.
export function keepChoices(oldRows,newRows){
  const old=new Map(oldRows.map(row=>[row.key,row]));
  return newRows.map(row=>{
    const before=old.get(row.key);
    return before?.choice&&sameValues(before,row)?{...row,choice:before.choice,text:before.text}:row;
  });
}

export function decisionsPayload(rows){
  return Object.fromEntries(rows.map(row=>[row.key,row.choice==='author'?{choice:'author',text:row.text}:{choice:row.choice}]));
}

// '' when the merge can be confirmed, otherwise the i18n key of the reason.
export function confirmReason(state,rows){
  if(!state||state.state==='blocked')return 'merge.reason.blocked';
  if(rows.some(row=>!row.choice))return 'merge.reason.undecided';
  return '';
}

export const headMemoryIds=state=>(state?.heads||[]).map(head=>head.memory_id);

// The scene the author should open to confirm a merge: the scene of a run stopped before a merge point, or the current
// scene when its readiness names the merge. `required` is the server's message (the run keeps only its text).
export function mergeStopScene(run,readiness,currentSceneId,required){
  if(run?.state==='needs_review'&&run.error===required)return run.tasks?.[run.cursor]?.scene_id||null;
  const operations=Object.values(readiness?.operations||{});
  return operations.some(operation=>operation?.reason_code==='memory_merge_required')?currentSceneId||null:null;
}
