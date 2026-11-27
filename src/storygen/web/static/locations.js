// MEMORY-LOCATIONS-S07: rows of the «Locations» panel from GET /api/stories/{id}/locations (pure).
// Nested cards follow their parent; a merged card is shown under its final target and can only be split back.
// Parents and targets are followed through merges, so a chain А→Б→В or a parent merged into its own child keeps the tree.
const label=scene=>`${scene.position+1}. ${scene.title}`;

export function locationRows(data){
  const cards=data?.locations||[],byId=new Map(cards.map(c=>[c.id,c])),rows=[],seen=new Set();
  const canonical=id=>{const chain=new Set();while(id&&byId.get(id)?.merged_into&&!chain.has(id)){chain.add(id);id=byId.get(id).merged_into}return id};
  // Where a card hangs: a merged card under its final target, an unmerged one under its parent's final target.
  const home=card=>{
    const place=card.merged_into?canonical(card.id):card.parent_id?canonical(card.parent_id):null;
    return place&&place!==card.id&&byId.has(place)?place:null;
  };
  const under=id=>[
    ...cards.filter(c=>!c.merged_into&&home(c)===id),
    ...cards.filter(c=>c.merged_into&&home(c)===id),
  ];
  const visit=(card,depth)=>{
    if(seen.has(card.id))return;seen.add(card.id);
    const merged=!!card.merged_into;
    rows.push({id:card.id,path:card.path,depth,merged,targetPath:card.target_path||null,description:card.description||'',
      scenes:(card.scenes||[]).map(label).join(', '),
      // R-51: places a model gave a scene can be removed here; a plan's place is changed in the plan.
      modelScenes:merged?[]:(card.scenes||[]).filter(s=>s.source==='model').map(s=>({id:s.id,label:label(s)})),
      canMerge:!merged,canSplit:merged,editable:!merged});
    for(const child of under(card.id))visit(child,depth+1);
  };
  for(const card of cards)if(!card.merged_into&&!home(card))visit(card,0);
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

// MEMORY-LOCATIONS-S11: phrases a card can be glued into (candidates whose cards include it; 3–200 characters, the
// server's bounds) and the glues of the story.
export function glueOptions(data,id){
  return (data?.glue_candidates||[]).filter(c=>(c.card_ids||[]).includes(id)&&c.phrase.length>=3&&c.phrase.length<=200)
    .map(c=>({key:c.key,phrase:c.phrase,cardIds:c.card_ids,scenes:(c.scene_ids||[]).length}));
}

export function glueRows(data){
  return (data?.glues||[]).map(g=>({key:g.key,phrase:g.phrase}));
}

// MEMORY-LOCATIONS-S12: typed descriptions not saved yet keep the author on the page («beforeunload»).
export function hasDrafts(drafts){return !!drafts&&drafts.size>0}

// The «Story locations →» link of a scene's memory tab: the page returns to the same scene and material.
export function memoryLinkHref(storyId,sceneId,mode){
  const base=`/stories/${encodeURIComponent(storyId)}/locations`;
  return sceneId&&mode?base+'?'+new URLSearchParams({scene:sceneId,material:mode}):base;
}

// Typed descriptions still worth keeping after a change: of an unmerged card that exists and differs from the saved
// text (a merge or glue can take the card away, and a stale draft would keep the page asking before leaving).
export function liveDrafts(drafts,data){
  if(!data?.locations)return new Map(drafts);
  const cards=new Map(data.locations.map(card=>[card.id,card]));
  return new Map([...drafts].filter(([id,text])=>{const card=cards.get(id);return card&&!card.merged_into&&text!==card.description}));
}
