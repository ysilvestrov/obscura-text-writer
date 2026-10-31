// Browser navigation preference only; never store manuscript or version contents.
const materials=new Set(['plan','brief','draft','review','prose','memory']);
const safeId=value=>typeof value==='string'&&/^[\p{L}\p{N}_-]{1,200}$/u.test(value);
const valid=value=>value&&safeId(value.scene_id)&&materials.has(value.material)?{scene_id:value.scene_id,material:value.material}:null;
function browserStorage(){try{return globalThis.localStorage;}catch{return null;}}
const key=storyId=>'obscura.workspace.v1.'+storyId;
export function readWorkspacePosition(storyId,search='',storage=browserStorage()){
  if(!safeId(storyId))return null;
  const query=new URLSearchParams(search),explicit=valid({scene_id:query.get('scene'),material:query.get('material')});
  if(explicit)return explicit;
  try{return valid(JSON.parse(storage?.getItem(key(storyId))||'null'));}catch{return null;}
}
export function rememberWorkspacePosition(storyId,position,storage=browserStorage()){
  const value=valid(position);if(!safeId(storyId)||!value)return false;
  try{if(!storage)return false;storage.setItem(key(storyId),JSON.stringify(value));return true;}catch{return false;}
}
export function resolveWorkspacePosition(scenes,position){
  const value=valid(position),scene=value&&scenes.find(scene=>scene.id===value.scene_id);
  return scene?{scene,material:value.material}:scenes.length?{scene:scenes[0],material:'plan'}:null;
}
export function updateWorkspaceUrl(position,location=globalThis.location,history=globalThis.history){
  const value=valid(position);if(!value||!location?.href||!history?.replaceState)return;
  try{
    const url=new URL(location.href);url.searchParams.set('scene',value.scene_id);url.searchParams.set('material',value.material);
    history.replaceState(history.state,'',url.href);
  }catch{/* A restricted browser must still allow editing. */}
}
