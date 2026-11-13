import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const m=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-merge.js'));

// MEMORY-MERGE-S04: rows of the merge window from GET /api/stories/{id}/memory-merges (neutral example).
const state={key:'heads:h1,h2',state:'none',story_revision:7,
  heads:[{scene_id:'h1',number:2,title:'Сцена 2',memory_id:'m1',arc_titles:['Дорога']},{scene_id:'h2',number:3,title:'Сцена 3',memory_id:'m2',arc_titles:['Місто']}],
  conflicts:[{key:'slot:c1:clothing',label:'Анна — clothing',values:{h1:'Анна в куртці',h2:'Анна в плащі'}},
             {key:'claim:x',label:'Ключ',values:{h1:'Ключ у кишені',h2:null}}],
  carried:{'claim:x':{choice:'author',text:'Ключ загублено'}}};

const rows=m.mergeRows(state);
assert.deepEqual(rows.map(r=>[r.key,r.choice,r.text,r.carried]),[['slot:c1:clothing',null,'',false],['claim:x','author','Ключ загублено',true]]);
assert.deepEqual(rows[0].values,[{headId:'h1',title:'2. Сцена 2',arcs:['Дорога'],value:'Анна в куртці'},{headId:'h2',title:'3. Сцена 3',arcs:['Місто'],value:'Анна в плащі'}]);
assert.equal(rows[1].values[1].value,null);

// Nothing to confirm while a conflict has no choice or the point is blocked.
assert.equal(m.confirmReason(state,rows),'merge.reason.undecided');
assert.equal(m.confirmReason({...state,state:'blocked'},[]),'merge.reason.blocked');
assert.equal(m.confirmReason(null,[]),'merge.reason.blocked');
const chosen=rows.map(r=>r.key==='slot:c1:clothing'?{...r,choice:'h2'}:r);
assert.equal(m.confirmReason(state,chosen),'');
assert.deepEqual(m.decisionsPayload(chosen),{'slot:c1:clothing':{choice:'h2'},'claim:x':{choice:'author',text:'Ключ загублено'}});

// After a refused save the window re-reads the state: a choice stays only for the same key and the same values.
const again=m.mergeRows({...state,carried:{}});
assert.deepEqual(m.keepChoices(chosen,again).map(r=>r.choice),['h2','author']);
const changed=m.mergeRows({...state,carried:{},conflicts:[{...state.conflicts[0],values:{h1:'Анна в куртці',h2:'Анна в шубі'}}]});
assert.deepEqual(m.keepChoices(chosen,changed).map(r=>r.choice),[null]);

// The heads the PUT expects, in the order of the state.
assert.deepEqual(m.headMemoryIds(state),['m1','m2']);

// The stop of a run before a merge point and the readiness of the current scene both lead to the merge window.
const REQUIRED='Потрібне злиття пам’яті перед цією сценою';
assert.equal(m.mergeStopScene({state:'needs_review',error:REQUIRED,cursor:1,tasks:[{scene_id:'a'},{scene_id:'m'}]},null,'x',REQUIRED),'m');
assert.equal(m.mergeStopScene({state:'needs_review',error:'Інше',cursor:0,tasks:[{scene_id:'a'}]},null,'x',REQUIRED),null);
assert.equal(m.mergeStopScene(null,{operations:{brief:{ready:false,reason_code:'memory_merge_required'}}},'x',REQUIRED),'x');
assert.equal(m.mergeStopScene(null,{operations:{brief:{ready:true}}},'x',REQUIRED),null);
