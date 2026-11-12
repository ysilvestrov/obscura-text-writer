// MEMORY-SUMMARY-S07: rows of the «Timeline summaries» panel from GET /api/stories/{id}/timeline-summaries (pure).
export function blockLabel(block){
  return block.part?{key:'summaries.part',params:{p0:block.title,p1:block.first_number,p2:block.last_number}}
    :{key:'summaries.range',params:{p0:block.first_number,p1:block.last_number}};
}

export function summaryRows(blocks){
  return (blocks||[]).map(block=>({
    key:block.key,label:blockLabel(block),state:block.state,versionId:block.version_id,text:block.text||'',
    action:block.ready?(block.state==='none'?'create':'rebuild'):null,
    highlighted:!!block.recommended,editable:!!block.version_id,
    reason:block.ready?(block.state==='stale'?`summaries.reason.${block.reason}`:null):block.ready_reason,
  }));
}
