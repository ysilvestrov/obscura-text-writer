// BOOK-STRUCTURE-S06: pure helpers for the grouped scene list, the arc picker and the «Book structure» panel buffer.
// Labels come through `label(key, n)` so the module stays free of the DOM and of the i18n catalog.

export const partTitle=(part,number,label)=>part.title||label('book.part.untitled',number);
export const arcTitle=(arc,number,label)=>arc.title||label('book.arc.untitled',number);

// Rows for the scene list: a part heading before the first scene of each part and an arc heading before the first scene
// of an arc when its part has several arcs or the arc has a title. A flat book gets scene rows only.
export function groupScenes(book,scenes,label){
  if(!book||book.kind!=='structured')return scenes.map(scene=>({type:'scene',scene}));
  const place=new Map();
  book.parts.forEach((part,p)=>part.arcs.forEach((arc,a)=>place.set(arc.id,{part,p,arc,a})));
  const rows=[];let lastPart=null,lastArc=null;
  for(const scene of scenes){
    const found=place.get(scene.arc_id);
    if(found&&found.part.id!==lastPart){rows.push({type:'part',id:found.part.id,title:partTitle(found.part,found.p+1,label)});lastPart=found.part.id;lastArc=null}
    if(found&&found.arc.id!==lastArc){
      if(found.part.arcs.length>1||found.arc.title)rows.push({type:'arc',id:found.arc.id,title:arcTitle(found.arc,found.a+1,label)});
      lastArc=found.arc.id;
    }
    rows.push({type:'scene',scene});
  }
  return rows;
}

// Options «Part › Arc» for the scene arc field, in structure order.
export function arcOptions(book,label){
  const options=[];
  (book?.parts||[]).forEach((part,p)=>part.arcs.forEach((arc,a)=>options.push({value:arc.id,label:partTitle(part,p+1,label)+' › '+arcTitle(arc,a+1,label)})));
  return options;
}

let counter=0;
const newId=prefix=>`${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`;

// The panel edits a copy; nothing reaches the server until save sends the whole structure in one PUT.
export function createBuffer(book,scenes){
  const parts=(book?.parts||[]).map(part=>({id:part.id,title:part.title||'',arcs:part.arcs.map(arc=>({id:arc.id,title:arc.title||'',protagonist_id:arc.protagonist_id||null}))}));
  // A meeting scene (several arc_ids) keeps every arc and counts in each of them; one arc stays a string.
  const arcsOf=scene=>scene.arc_ids?.length?scene.arc_ids:scene.arc_id?[scene.arc_id]:[];
  const used=new Map();for(const scene of scenes)for(const arc of arcsOf(scene))used.set(arc,(used.get(arc)||0)+1);
  return {parts,used,scene_arcs:Object.fromEntries(scenes.filter(s=>arcsOf(s).length).map(s=>[s.id,arcsOf(s).length===1?arcsOf(s)[0]:[...arcsOf(s)]]))};
}

const arcScenes=(buffer,arc)=>buffer.used.get(arc.id)||0;
const partScenes=(buffer,part)=>part.arcs.reduce((sum,arc)=>sum+arcScenes(buffer,arc),0);

export function addPart(buffer){buffer.parts.push({id:newId('part'),title:'',arcs:[{id:newId('arc'),title:''}]});return null}
export function addArc(buffer,p){buffer.parts[p].arcs.push({id:newId('arc'),title:''});return null}
// BOOK-LINEAGE-S04: '' or null means the book's inferred protagonist.
export function setProtagonist(buffer,p,a,id){buffer.parts[p].arcs[a].protagonist_id=id||null;return null}
export function rename(buffer,p,a,title){(a==null?buffer.parts[p]:buffer.parts[p].arcs[a]).title=title.slice(0,200);return null}

// Moving keeps scenes where they are; the server refuses an order that would mix arcs or parts.
export function move(buffer,p,a,delta){
  const list=a==null?buffer.parts:buffer.parts[p].arcs;const from=a==null?p:a;const to=from+delta;
  if(to<0||to>=list.length)return null;
  [list[from],list[to]]=[list[to],list[from]];return null;
}

// Errors are i18n keys: a part or arc with scenes, the last arc of a part, the last part.
export function remove(buffer,p,a){
  const part=buffer.parts[p];
  if(a==null){
    if(buffer.parts.length===1)return 'book.error.last_part';
    if(partScenes(buffer,part))return 'book.error.has_scenes';
    buffer.parts.splice(p,1);return null;
  }
  if(part.arcs.length===1)return 'book.error.last_arc';
  if(arcScenes(buffer,part.arcs[a]))return 'book.error.has_scenes';
  part.arcs.splice(a,1);return null;
}

export function payload(buffer,expected_revision){
  return {expected_revision,parts:buffer.parts.map(part=>({id:part.id,title:part.title,arcs:part.arcs.map(arc=>({id:arc.id,title:arc.title,protagonist_id:arc.protagonist_id||null}))})),scene_arcs:buffer.scene_arcs};
}
