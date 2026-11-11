import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {revisionsChanged,newerScene,externalNotice,cleanBuffer,createSceneSync}=await import(pathToFileURL(root+'/src/storygen/web/static/scene-sync.js'));

// revisionsChanged: the set of scenes and each revision against the loaded view; the current scene against the buffer.
const view=[{id:'a',revision:2},{id:'b',revision:1}];
assert.deepEqual(revisionsChanged(view,{a:2,b:1},{id:'a',revision:2}),{changed:false,currentChanged:false,currentGone:false});
assert.deepEqual(revisionsChanged(view,{a:3,b:1},{id:'a',revision:2}),{changed:true,currentChanged:true,currentGone:false});
assert.deepEqual(revisionsChanged(view,{a:2,b:4},{id:'a',revision:2}),{changed:true,currentChanged:false,currentGone:false});
assert.deepEqual(revisionsChanged(view,{a:2,b:1,c:1},{id:'a',revision:2}),{changed:true,currentChanged:false,currentGone:false});
assert.deepEqual(revisionsChanged(view,{b:1},{id:'a',revision:2}),{changed:true,currentChanged:false,currentGone:true});
assert.deepEqual(revisionsChanged(view,{a:2,b:1},null),{changed:false,currentChanged:false,currentGone:false});
// A buffer kept stale by the author's own unsaved edits still counts as the current scene being behind.
assert.deepEqual(revisionsChanged([{id:'a',revision:3}],{a:3},{id:'a',revision:2}),{changed:false,currentChanged:true,currentGone:false});

// newerScene: the scene with the higher revision; either side may be missing.
const older={id:'a',revision:1,heads:{}},newer={id:'a',revision:2,heads:{draft:'v'}};
assert.equal(newerScene(older,newer),newer);
assert.equal(newerScene(newer,older),newer);
assert.equal(newerScene(undefined,older),older);
assert.equal(newerScene(newer,null),newer);
assert.equal(newerScene(older,{...older}).revision,1);

// externalNotice: only after a change made elsewhere was detected, and only while the buffer is behind.
const base={externalChange:true,scene:{id:'a',revision:1},view:{scenes:[{id:'a',revision:2}]}};
assert.equal(externalNotice(base),'changed');
assert.equal(externalNotice({...base,externalChange:false}),null);
assert.equal(externalNotice({...base,scene:{id:'a',revision:2}}),null);
assert.equal(externalNotice({...base,view:{scenes:[]}}),'gone');
assert.equal(externalNotice({...base,scene:null}),null);
assert.equal(externalNotice({...base,view:null}),null);

// cleanBuffer: nothing unsaved, no save running, no rewrite-from-memory open, the current material in the buffer.
const clean={dirty:false,saving:false,bufferOrigin:'current'};
assert.equal(cleanBuffer(clean,false),true);
assert.equal(cleanBuffer({...clean,dirty:true},false),false);
assert.equal(cleanBuffer({...clean,saving:true},false),false);
assert.equal(cleanBuffer({...clean,bufferOrigin:'history'},false),false);
assert.equal(cleanBuffer(clean,true),false);

// createSceneSync: throttled to 2 s; a trigger while busy is kept and run once the operation settles.
let time=10_000,busy=false,calls=0,fail=false;
const sync=createSceneSync({check:async()=>{calls++;if(fail)throw new Error('offline')},busy:()=>busy,now:()=>time});
await sync.trigger();assert.equal(calls,1);
time+=1999;await sync.trigger();assert.equal(calls,1);
time+=1;await sync.trigger();assert.equal(calls,2);
time+=5000;busy=true;await sync.trigger();assert.equal(calls,2);
await sync.settle();assert.equal(calls,2,'still busy: the deferred check waits');
busy=false;await sync.settle();assert.equal(calls,3,'the deferred check runs once the operation ends');
await sync.settle();assert.equal(calls,3,'a deferred check runs once');
time+=5000;fail=true;await sync.trigger();assert.equal(calls,4);
time+=5000;fail=false;await sync.trigger();assert.equal(calls,5,'a failed check does not block later ones');
// A trigger during a running check is deferred until that check ends.
let release;const slow=createSceneSync({check:()=>{calls++;return new Promise(r=>release=r)},busy:()=>false,now:()=>time});
calls=0;const first=slow.trigger();time+=5000;await slow.trigger();assert.equal(calls,1);
release();await new Promise(r=>setTimeout(r,0));assert.equal(calls,2);release();await first;
console.log('ok');
