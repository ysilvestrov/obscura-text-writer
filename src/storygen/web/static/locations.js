// MEMORY-LOCATIONS-S07: rows of the «Locations» panel from GET /api/stories/{id}/locations (pure).
// Nested cards follow their parent; a merged card is shown under its target and can only be split back.
export function locationRows(data){
  const cards=data?.locations||[],known=new Set(cards.map(c=>c.id)),rows=[],seen=new Set();
  const under=id=>[
    ...cards.filter(c=>!c.merged_into&&c.parent_id===id),
    ...cards.filter(c=>c.merged_into===id),
  ];
  const visit=(card,depth)=>{
    if(seen.has(card.id))return;seen.add(card.id);
    const merged=!!card.merged_into;
    rows.push({id:card.id,path:card.path,depth,merged,targetPath:card.target_path||null,description:card.description||'',
      scenes:(card.scenes||[]).map(s=>`${s.position+1}. ${s.title}`).join(', '),
      canMerge:!merged,canSplit:merged,editable:!merged});
    for(const child of under(card.id))visit(child,depth+1);
  };
  for(const card of cards)if(!card.merged_into&&(!card.parent_id||!known.has(card.parent_id)))visit(card,0);
  for(const card of cards)visit(card,0);  // anything a broken chain left out
  return rows;
}

export function mergeTargets(data,id){
  // In panel order: unmerged cards only (a merged card is split first), never the card itself.
  return locationRows(data).filter(r=>!r.merged&&r.id!==id).map(r=>({id:r.id,path:r.path}));
}

export function suggestionRows(data){
  return (data?.suggestions||[]).map(s=>({a:s.a,b:s.b,aPath:s.a_path,bPath:s.b_path}));
}
