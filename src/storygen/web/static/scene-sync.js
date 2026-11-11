// MCP-BRIDGE (#105): rules for noticing scene changes made elsewhere while the workspace was in the background.
// Pure functions only, so the page wiring (scene-sync-workspace.js) stays thin and these stay testable in Node.

// The loaded view against fresh revisions; the current scene against the revision of the buffer it protects.
export function revisionsChanged(viewScenes,revisions,bufferScene){
  const loaded=new Map((viewScenes||[]).map(s=>[s.id,s.revision])),fresh=Object.entries(revisions||{});
  const changed=loaded.size!==fresh.length||fresh.some(([id,revision])=>loaded.get(id)!==revision);
  const present=!!bufferScene&&Object.hasOwn(revisions||{},bufferScene.id);
  return {changed,currentChanged:present&&revisions[bufferScene.id]!==bufferScene.revision,currentGone:!!bufferScene&&!present};
}

// One source of truth for the scene a material is loaded from: the newer of the view's copy and the buffer's.
export function newerScene(a,b){
  if(!a)return b||null;
  if(!b)return a;
  return (b.revision??0)>(a.revision??0)?b:a;
}

// What the page tells the author: only after a change made elsewhere was detected, and only while the buffer is behind.
export function externalNotice(state){
  if(!state?.externalChange||!state.scene||!state.view)return null;
  const latest=(state.view.scenes||[]).find(s=>s.id===state.scene.id);
  if(!latest)return 'gone';
  return latest.revision!==state.scene.revision?'changed':null;
}

// The buffer may be replaced only when nothing in it or around it belongs to the author's unfinished work.
export function cleanBuffer(state,ghostOpen){
  return !state.dirty&&!state.saving&&!ghostOpen&&state.bufferOrigin==='current';
}

// Throttled check on return to the page. A trigger during a busy moment (own save or refresh, or a running check)
// is kept and run once that moment ends, so a request started before the external change cannot hide it.
export function createSceneSync({check,busy,now=()=>Date.now(),interval=2000}){
  let last=-Infinity,pending=false,running=false;
  async function run(){
    pending=false;running=true;last=now();
    try{await check()}catch{/* a failed check stays silent; the next return to the page tries again */}
    finally{running=false}
    if(pending)await settle();
  }
  async function trigger(){
    if(running||busy()){pending=true;return}
    if(now()-last<interval)return;
    await run();
  }
  async function settle(){
    if(!pending||running||busy())return;
    await run();
  }
  return {trigger,settle};
}
