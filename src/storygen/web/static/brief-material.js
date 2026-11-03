// A proposal is visible for review without becoming the selected writer input.
export function hasBriefChanges(text){
  try{const changes=JSON.parse(text).proposed_changes;return Array.isArray(changes)&&changes.length>0;}
  catch{return false;}
}
export async function loadBriefMaterial(api,scene){
  const data=await api(`/api/scenes/${scene.id}/versions`),current=data.scene||scene;
  const head=current.heads.brief,headIndex=data.versions.findIndex(ref=>ref.id===head);
  const candidates=data.versions.slice(headIndex+1).filter(ref=>ref.kind==='brief'&&ref.complete&&!ref.stale).reverse();
  for(const ref of candidates){
    const material=await api('/api/versions/'+ref.id);
    if(hasBriefChanges(material.text))return {scene:current,material};
  }
  return {scene:current,material:head?await api('/api/versions/'+head):null};
}
