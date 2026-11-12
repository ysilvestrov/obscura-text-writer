import assert from 'node:assert/strict';
const root=new URL('../../../src/storygen/web/static/',import.meta.url);
const {externalPublicationChange:decide}=await import(new URL('publication-sync.js',root));

const library=[{id:'a',revision:0,archived_at:null},{id:'b',revision:2,archived_at:null}];
const base={loadedRevision:3,freshRevision:3,formDirty:false,busy:false,loadedLibrary:library,freshLibrary:library.map(x=>({...x})),libraryDirty:false};
const none={reloadCard:false,warnCard:false,reloadLibrary:false};
assert.deepEqual(decide(base),none,'nothing changed');
assert.deepEqual(decide({...base,freshRevision:4}),{...none,reloadCard:true},'clean form reloads the card');
assert.deepEqual(decide({...base,freshRevision:4,formDirty:true}),{...none,warnCard:true},'author edits are never overwritten');
assert.deepEqual(decide({...base,freshRevision:4,busy:true}),{...none,warnCard:true},'a save in progress is not interrupted');
// MCP-BRIDGE-S31: a signature from the chat changes only the library, not the card revision.
const added=[...library,{id:'c',revision:0,archived_at:null}];
assert.deepEqual(decide({...base,freshLibrary:added}),{...none,reloadLibrary:true});
assert.deepEqual(decide({...base,freshLibrary:[library[0],{...library[1],revision:3}]}),{...none,reloadLibrary:true},'renamed signature');
assert.deepEqual(decide({...base,freshLibrary:[library[0],{...library[1],archived_at:'x'}]}),{...none,reloadLibrary:true},'archived signature');
assert.deepEqual(decide({...base,freshLibrary:[...library].reverse()}),none,'order alone is no change');
assert.deepEqual(decide({...base,freshLibrary:added,libraryDirty:true}),none,'an edited library row is kept');
assert.deepEqual(decide({...base,freshRevision:4,freshLibrary:added}),{...none,reloadCard:true},'a card reload also reloads the library');
assert.deepEqual(decide({...base,freshRevision:4,formDirty:true,freshLibrary:added}),{...none,warnCard:true,reloadLibrary:true});
console.log('publication sync ok');
