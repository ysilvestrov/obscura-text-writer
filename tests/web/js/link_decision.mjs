import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {pendingLinks}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/link-actions.js'));

// VALID-LINKS-S08/S11: the panel of the open scene — one row per pending link, with the actions the server accepts.
const link=(status,reason=null,fingerprint='f-'+status)=>({status,source:null,reason,fingerprint});
const valid=link('valid');
const scenes=[{id:'s1',title:'Ранок',heads:{prose:'p1'}},{id:'s2',title:'Вечір',heads:{brief:'b2',prose:'p2'}}];
const view=(links,extra={})=>({s2:{links:{brief:valid,prose:valid,memory:valid,...links},...extra}});
const approve=(link,fingerprint,label)=>({type:'approve',link,fingerprint,label});
const memory=(sceneId,label)=>({type:'memory',sceneId,label});

assert.deepEqual(pendingLinks(view({}),'s2',scenes),[]);
assert.deepEqual(pendingLinks({},'s2',scenes),[]);
assert.deepEqual(pendingLinks(undefined,'s2',scenes),[]);

// Brief and prose: the author's approval.
assert.deepEqual(pendingLinks(view({brief:link('unchecked',null,'fb'),prose:link('unchecked',null,'fp')}),'s2',scenes),[
  {key:'brief',text:'link.brief_unchecked',params:{},actions:[approve('brief','fb','link.approve_brief')]},
  {key:'prose',text:'link.prose_unchecked',params:{},actions:[approve('prose','fp','link.approve_prose')]}]);

// Z3 unchecked: keep the earlier memory (the author's decision) or create a new one for this scene.
assert.deepEqual(pendingLinks(view({memory:link('unchecked',null,'fm')}),'s2',scenes),[
  {key:'memory',text:'link.memory_unchecked',params:{},actions:[approve('memory','fm','link.keep_memory'),memory('s2','link.new_memory')]}]);

// No memory of this scene: only creating it helps.
assert.deepEqual(pendingLinks(view({memory:{status:'unavailable',source:null,reason:'no_memory',fingerprint:null}}),'s2',scenes),[
  {key:'memory',text:'link.no_memory',params:{},actions:[memory('s2','link.create_memory')]}]);

// No memory of the previous scene: one row for brief and prose, naming the previous scene and creating its memory.
const noPrevious={brief:link('unavailable','no_previous_memory'),prose:link('unavailable','no_previous_memory')};
assert.deepEqual(pendingLinks(view(noPrevious,{previous_scene_id:'s1'}),'s2',scenes),[
  {key:'previous',text:'link.no_previous_memory',params:{p0:'Ранок'},actions:[memory('s1','link.create_memory')]}]);
// A merge to confirm or a series start has no plain previous scene: the explanation without a button.
assert.deepEqual(pendingLinks(view(noPrevious),'s2',scenes),[
  {key:'previous',text:'link.no_previous_memory_other',params:{},actions:[]}]);
assert.deepEqual(pendingLinks(view(noPrevious,{previous_scene_id:'gone'}),'s2',scenes),[
  {key:'previous',text:'link.no_previous_memory_other',params:{},actions:[]}]);

// The carry: pending has no action; failed asks for a new memory of this scene.
assert.deepEqual(pendingLinks(view({memory:link('unavailable','carry_pending')}),'s2',scenes),[
  {key:'memory',text:'link.carry_pending',params:{},actions:[]}]);
// Failed: a new memory of this scene, or rebuilding the memory from this scene onwards (MEMORY-CARRY).
assert.deepEqual(pendingLinks(view({memory:link('unavailable','carry_failed')}),'s2',scenes),[
  {key:'memory',text:'link.carry_failed',params:{},actions:[memory('s2','link.new_memory'),{type:'rebuild',sceneId:'s2',label:'link.rebuild_memory'}]}]);
// A stalled carry (paused, failed, interrupted) is the latest carry run: resume it or cancel it from the row.
for(const state of ['paused','failed','interrupted'])
  assert.deepEqual(pendingLinks(view({memory:link('unavailable','carry_pending')},{carry_run:{id:'r1',state}}),'s2',scenes),[
    {key:'memory',text:'link.carry_stalled',params:{},actions:[
      {type:'carry',runId:'r1',command:'resume',label:'link.carry_resume'},
      {type:'carry',runId:'r1',command:'cancel',label:'link.carry_cancel'}]}]);

// Missing links and decided outcomes get no row; an unavailable link never offers an approval.
assert.deepEqual(pendingLinks(view({brief:link('missing'),prose:link('missing'),memory:link('missing')}),'s2',scenes),[]);
assert.deepEqual(pendingLinks(view({memory:link('unavailable','unknown_reason')}),'s2',scenes),[]);
for(const item of pendingLinks(view({...noPrevious,memory:link('unavailable','carry_failed')},{previous_scene_id:'s1'}),'s2',scenes))
  assert.ok(item.actions.every(action=>action.type!=='approve'),JSON.stringify(item));
console.log('Link panel actions passed');
