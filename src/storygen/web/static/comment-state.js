// Source positions are supplied by the editor bridge, never inferred from quotes.
export function notePayload(general,instructions,anchors){
  const comments=anchors.map(({id,anchor})=>({id,instruction:instructions.get(id)||'',anchor:{
    start:anchor.start,end:anchor.end,source_quote:anchor.source_quote,display_quote:anchor.display_quote,
    state:anchor.state,reason:anchor.reason||null,origin:anchor.origin||null,
    ...(anchor.origin_source?{origin_source:anchor.origin_source}:{})
  }}));
  comments.sort((a,b)=>a.anchor.start-b.anchor.start||a.id.localeCompare(b.id));
  return {general,comments};
}
export const notesFingerprint=payload=>JSON.stringify(payload);
export function instructionLimit(payload){
  const length=value=>[...value].length;
  if(payload.comments.length>100)return 'comments.limit_count';
  if(length(payload.general)>12000)return 'comments.limit_general';
  if(payload.comments.some(comment=>!comment.instruction.trim()||length(comment.instruction)>8000))return 'comments.limit_instruction';
  if(length(payload.general)+payload.comments.reduce((sum,comment)=>sum+length(comment.instruction),0)>50000)return 'comments.limit_total';
  return null;
}
