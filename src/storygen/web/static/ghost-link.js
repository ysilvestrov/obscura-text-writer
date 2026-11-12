// MCP-BRIDGE-S23/S24: a link from the chat (?scene=..&material=draft&ghost=1[&draft=..]) opens Ghost Mode of the current draft.
// Pure: no DOM, no storage. ghost-mode.js wires it to the same open() the button uses.
const safeId=value=>typeof value==='string'&&/^[\p{L}\p{N}_-]{1,200}$/u.test(value);
// Read when the module loads: editor.js imports this module first, before its own refresh rewrites the address to material=plan.
const startSearch=(()=>{try{return globalThis.location?.search||'';}catch{return '';}})();

export function readGhostLink(search=''){
  const query=new URLSearchParams(search);
  if(query.get('ghost')!=='1'||query.get('material')!=='draft'||!safeId(query.get('scene')))return null;
  const draft=query.get('draft');
  if(draft!==null&&!safeId(draft))return null;
  return {sceneId:query.get('scene'),draftId:draft};
}

export const startGhostLink=()=>readGhostLink(startSearch);

// The button's own conditions first, then the link's: only the current draft head, never an older unfinished rewrite.
export function ghostLinkRefusal({hasDraft,history,dirty,saving,headDraft,expectedDraftId,resumeDraftId}){
  if(!hasDraft||!headDraft)return 'no_draft';
  if(history)return 'history';
  if(dirty||saving)return 'dirty';
  if(expectedDraftId&&expectedDraftId!==headDraft)return 'stale_link';
  if(resumeDraftId&&resumeDraftId!==headDraft)return 'old_session';
  return null;
}

// After an awaited request the buffer must still be this scene's clean current draft, or the mode opens over another scene.
export function sameDraftBuffer(sceneId,state){
  return !!state?.scene&&state.scene.id===sceneId&&state.mode==='draft'&&state.bufferOrigin!=='history'&&!state.dirty&&!state.saving;
}

// A reload or a bookmark must not open the mode again.
export function clearGhostLink(location=globalThis.location,history=globalThis.history){
  try{
    const url=new URL(location.href);
    if(!url.searchParams.has('ghost')&&!url.searchParams.has('draft'))return;
    url.searchParams.delete('ghost');url.searchParams.delete('draft');
    history.replaceState(history.state,'',url.href);
  }catch{/* A restricted browser still edits normally. */}
}
