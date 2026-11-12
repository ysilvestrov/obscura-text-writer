import assert from 'node:assert/strict';
const root=new URL('../../../src/storygen/web/static/',import.meta.url);
const g=await import(new URL('ghost-link.js',root));

// MCP-BRIDGE-S23: the link is read only with material=draft and a valid scene; draft is a check, not a choice.
assert.deepEqual(g.readGhostLink('?scene=s1&material=draft&ghost=1&draft=d1'),{sceneId:'s1',draftId:'d1'});
assert.deepEqual(g.readGhostLink('?scene=s1&material=draft&ghost=1'),{sceneId:'s1',draftId:null});
assert.equal(g.readGhostLink('?scene=s1&material=plan&ghost=1'),null);
assert.equal(g.readGhostLink('?scene=s1&material=draft&ghost=0'),null);
assert.equal(g.readGhostLink('?scene=s1&material=draft'),null);
assert.equal(g.readGhostLink('?material=draft&ghost=1'),null);
assert.equal(g.readGhostLink('?scene=../x&material=draft&ghost=1'),null);
assert.equal(g.readGhostLink('?scene=s1&material=draft&ghost=1&draft=../x'),null);
assert.equal(g.readGhostLink(''),null);

const base={hasDraft:true,history:false,dirty:false,saving:false,headDraft:'d2',expectedDraftId:null,resumeDraftId:null};
assert.equal(g.ghostLinkRefusal(base),null);
assert.equal(g.ghostLinkRefusal({...base,expectedDraftId:'d2'}),null);
assert.equal(g.ghostLinkRefusal({...base,resumeDraftId:'d2'}),null,'an unfinished rewrite of the current draft is resumed');
assert.equal(g.ghostLinkRefusal({...base,hasDraft:false,headDraft:null}),'no_draft');
assert.equal(g.ghostLinkRefusal({...base,history:true}),'history');
assert.equal(g.ghostLinkRefusal({...base,dirty:true}),'dirty');
assert.equal(g.ghostLinkRefusal({...base,saving:true}),'dirty');
// MCP-BRIDGE-S24: a draft changed after the chat gave the link, or an older unfinished rewrite, never opens.
assert.equal(g.ghostLinkRefusal({...base,expectedDraftId:'d1'}),'stale_link');
assert.equal(g.ghostLinkRefusal({...base,resumeDraftId:'d1'}),'old_session');
assert.equal(g.ghostLinkRefusal({...base,expectedDraftId:'d1',resumeDraftId:'d1'}),'stale_link');

const calls=[];
const location={href:'http://127.0.0.1:8765/stories/st1?scene=s1&material=draft&ghost=1&draft=d1&x=1'};
g.clearGhostLink(location,{state:{keep:true},replaceState:(state,title,href)=>calls.push([state,href])});
assert.deepEqual(calls,[[{keep:true},'http://127.0.0.1:8765/stories/st1?scene=s1&material=draft&x=1']]);
g.clearGhostLink({href:'http://127.0.0.1:8765/stories/st1?scene=s1'},{replaceState:()=>calls.push('again')});
assert.equal(calls.length,1,'nothing to clear, no history entry');
g.clearGhostLink({href:'http://127.0.0.1:8765/stories/st1?ghost=1'},{replaceState(){throw new Error('restricted');}});
// Cross-review: the editor may rewrite the address to material=plan before ghost-mode.js runs; the link is read at module load.
globalThis.location={search:'?scene=s1&material=draft&ghost=1&draft=d1',href:'http://127.0.0.1:8765/stories/st1?scene=s1&material=draft&ghost=1&draft=d1'};
const fresh=await import(new URL('ghost-link.js?start',root));
globalThis.location={search:'?scene=s1&material=plan&ghost=1&draft=d1',href:'http://127.0.0.1:8765/stories/st1?scene=s1&material=plan&ghost=1&draft=d1'};
assert.deepEqual(fresh.startGhostLink(),{sceneId:'s1',draftId:'d1'});
delete globalThis.location;

// Cross-review: after the version request the buffer must still be the same scene's clean current draft.
const buffer={scene:{id:'s1'},mode:'draft',bufferOrigin:'live',dirty:false,saving:false};
assert.equal(g.sameDraftBuffer('s1',buffer),true);
assert.equal(g.sameDraftBuffer('s1',{...buffer,scene:{id:'s2'}}),false);
assert.equal(g.sameDraftBuffer('s1',{...buffer,mode:'plan'}),false);
assert.equal(g.sameDraftBuffer('s1',{...buffer,bufferOrigin:'history'}),false);
assert.equal(g.sameDraftBuffer('s1',{...buffer,dirty:true}),false);
assert.equal(g.sameDraftBuffer('s1',{...buffer,saving:true}),false);
assert.equal(g.sameDraftBuffer('s1',{...buffer,scene:null}),false);
console.log('ghost link ok');
