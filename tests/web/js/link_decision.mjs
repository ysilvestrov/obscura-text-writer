import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const {pendingLinks,sceneConsistency}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/link-actions.js'));

// VALID-LINKS-S08/S11: the panel of the open scene — one row per pending link, with the actions the server accepts.
const link=(status,reason=null,fingerprint='f-'+status)=>({status,source:null,reason,fingerprint});
const valid=link('valid');
const scenes=[{id:'s1',title:'Ранок',heads:{prose:'p1'}},{id:'s2',title:'Вечір',heads:{brief:'b2',prose:'p2'}}];
const view=(links,extra={})=>{const all={brief:valid,prose:valid,memory:valid,...links};
  return {s2:{links:all,validity:Object.values(all).every(l=>l.status==='valid')?'valid':'unchecked',...extra}};};
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

// A scene the stopped carry did not reach waits for the failed scene: a new memory or a rebuild of that scene.
assert.deepEqual(pendingLinks(view({memory:link('unavailable','carry_pending')},{carry_failed_scene_id:'s1'}),'s2',scenes),[
  {key:'memory',text:'link.carry_blocked',params:{p0:'Ранок'},actions:[memory('s1','link.new_memory'),{type:'rebuild',sceneId:'s1',label:'link.rebuild_memory'}]}]);

// Missing links and decided outcomes get no row; an unavailable link never offers an approval.
assert.deepEqual(pendingLinks(view({brief:link('missing'),prose:link('missing'),memory:link('missing')}),'s2',scenes),[]);
assert.deepEqual(pendingLinks(view({memory:link('unavailable','unknown_reason')}),'s2',scenes),[]);
for(const item of pendingLinks(view({...noPrevious,memory:link('unavailable','carry_failed')},{previous_scene_id:'s1'}),'s2',scenes))
  assert.ok(item.actions.every(action=>action.type!=='approve'),JSON.stringify(item));
// The auditor's discrepancy: a hint to reread, with its confidence, items and quotes, and the author's decisions of §8.
const items=[{text:'Місце не збігається',quote:'У студії тихо.'},{text:'Немає кроку з планом',quote:null}];
const discrepancy=(fingerprint,confidence=40)=>({status:'discrepancy',source:'auditor',reason:'Підсумок Ревізора',fingerprint,
  confidence,discrepancies:items,summary:'Підсумок Ревізора'});
const found=(key,text,fingerprint,actions,confidence=40)=>({key,text,params:{p0:confidence},discrepancies:items,
  summary:'Підсумок Ревізора',actions});
assert.deepEqual(pendingLinks(view({brief:discrepancy('fb')}),'s2',scenes),[
  found('brief','link.brief_discrepancy','fb',[approve('brief','fb','link.approve_brief')])]);
assert.deepEqual(pendingLinks(view({prose:discrepancy('fp',72)}),'s2',scenes),[
  found('prose','link.prose_discrepancy','fp',[approve('prose','fp','link.approve_prose')],72)]);
assert.deepEqual(pendingLinks(view({memory:discrepancy('fm')}),'s2',scenes),[
  found('memory','link.memory_discrepancy','fm',[approve('memory','fm','link.keep_memory'),memory('s2','link.new_memory')])]);
// A verdict without a stated confidence still shows its row.
assert.deepEqual(pendingLinks(view({brief:{...discrepancy('fb'),confidence:null,discrepancies:[],summary:null}}),'s2',scenes),[
  {key:'brief',text:'link.brief_discrepancy',params:{p0:'—'},discrepancies:[],summary:null,actions:[approve('brief','fb','link.approve_brief')]}]);

// The auditor could not check a link: the reason, and for an input over its limits the auditor's settings.
const overflow='Вхід перевірки перевищує ліміт Ревізора: 900000 символів із 400000';
const unavailable=(reason)=>({status:'unavailable',source:'auditor',reason,fingerprint:'fu'});
const settings={type:'settings',label:'link.open_auditor_settings'};
for(const link of ['brief','prose','memory'])
  assert.deepEqual(pendingLinks(view({[link]:unavailable(overflow)}),'s2',scenes),[
    {key:link,text:'link.audit_unavailable',params:{},reason:overflow,actions:[settings]}]);
assert.deepEqual(pendingLinks(view({prose:unavailable('Вхід перевірки перевищує ліміт Ревізора: приблизно 9000 токенів із 4000')}),'s2',scenes)[0].actions,[settings]);
// Another reason of the auditor (unreadable material): the explanation without a settings button, never an approval.
assert.deepEqual(pendingLinks(view({brief:unavailable('Матеріал перевірки не прочитано')}),'s2',scenes),[
  {key:'brief',text:'link.audit_unavailable',params:{},reason:'Матеріал перевірки не прочитано',actions:[]}]);

// Task 1: the panel rules of «Узгодженість сцени».
const disc={...link('discrepancy',null,'fp'),source:'auditor',confidence:72,summary:'Можлива розбіжність',discrepancies:[{text:'Інший порт',quote:'Герой іде до порту'}]};
const pv=(calls,total='0.0123',ready=true,reason=null)=>({ready,reason,calls,cost:{total_usd:total}});
let c=sceneConsistency(view({brief:link('unchecked',null,'fb'),prose:disc,memory:{...valid,source:'auditor'}}),'s2',scenes,null,pv(1));
assert.deepEqual(c.rows.map(r=>[r.link,r.state,r.icon]),[['brief','pending','○'],['prose','discrepancy','!'],['memory','ok','✓']]);
assert.deepEqual([c.view,c.pendingCount,c.total,c.resume],['full',2,3,false]);
assert.deepEqual(c.rows[0].actions,[{type:'approve',link:'brief',fingerprint:'fb',label:'consistency.approve_self'}]);
assert.deepEqual(c.rows[1].actions,[{type:'approve',link:'prose',fingerprint:'fp',label:'consistency.no_discrepancy'}]);
assert.deepEqual([c.rows[1].status,c.rows[1].summary,c.rows[1].discrepancies],[{key:'consistency.state_discrepancy',params:{p0:72}},'Можлива розбіжність',disc.discrepancies]);
assert.deepEqual(c.rows[2].status,{key:'consistency.state_ok_auditor',params:{}});
assert.deepEqual(c.primary,{action:'audit',label:'consistency.audit',detail:{key:'consistency.audit_cost',params:{p0:1,p1:'$0.01'}},disabled:false,reason:null});
// preview: loading, not ready, nothing to call, no price, blocked
assert.deepEqual([sceneConsistency(view({brief:link('unchecked')}),'s2',scenes).primary.disabled,sceneConsistency(view({brief:link('unchecked')}),'s2',scenes).primary.reason],[true,null]);
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(0,null,false,'Роль не налаштовано: Ревізор')).primary.reason,{text:'Роль не налаштовано: Ревізор'});
assert.deepEqual(sceneConsistency(view({prose:disc}),'s2',scenes,null,pv(0,'0.0000')).primary.reason,{key:'consistency.nothing_to_audit',params:{}});  // every {key} reason carries params, {} when none
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(2,null)).primary.detail,{key:'consistency.audit_calls',params:{p0:2}});
assert.deepEqual(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,null,pv(1),'Збережіть зміни').primary,{action:'audit',label:'consistency.audit',detail:{key:'consistency.audit_cost',params:{p0:1,p1:'$0.01'}},disabled:true,reason:{text:'Збережіть зміни'}});
// visibility (Г2): valid line, nothing at all, brief-only scene with nothing to decide
assert.equal(sceneConsistency(view({}),'s2',scenes,null,pv(0)).view,'valid');
assert.equal(sceneConsistency({s2:{links:{brief:link('missing'),prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes).view,'none');
assert.equal(sceneConsistency({s2:{links:{brief:valid,prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes).view,'none');
const briefOnly=sceneConsistency({s2:{links:{brief:link('unchecked'),prose:link('missing'),memory:link('missing')},validity:'incomplete'}},'s2',scenes,null,pv(1));
assert.deepEqual([briefOnly.view,briefOnly.total,briefOnly.rows[1].status],['full',1,{key:'consistency.state_missing',params:{}}]);
// Г3: the previous scene's memory sits on the brief row once
const prev={s2:{links:{brief:link('unavailable','no_previous_memory'),prose:link('unavailable','no_previous_memory'),memory:valid},previous_scene_id:'s1',validity:'unchecked'}};
c=sceneConsistency(prev,'s2',scenes,null,pv(0));
assert.deepEqual(c.rows[0].status,{key:'link.no_previous_memory',params:{p0:'Ранок'}});
assert.deepEqual(c.rows[0].actions,[memory('s1','link.create_memory')]);
assert.deepEqual([c.rows[1].state,c.rows[1].status,c.rows[1].actions],['unavailable',{key:'consistency.state_needs_previous',params:{}},[]]);
// auditor overflow keeps the settings link
const over={status:'unavailable',source:'auditor',reason:'Вхід перевірки перевищує ліміт Ревізора: 9 > 8',fingerprint:'fo'};
c=sceneConsistency(view({prose:over},{validity:'unchecked'}),'s2',scenes,null,pv(0));
assert.deepEqual([c.rows[1].icon,c.rows[1].reason,c.rows[1].actions],['—',over.reason,[{type:'settings',label:'link.open_auditor_settings'}]]);
// resume on the stop scene (Г6)
const book=(cp,state='needs_review')=>({id:'r1',state,request:{mode:'audit',audit_scope:'story'},checkpoint:{phase:'awaiting_author',...cp}});
c=sceneConsistency(view({brief:{...disc,fingerprint:'fb'}},{validity:'discrepancy'}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'}),pv(1));
assert.deepEqual([c.view,c.resume,c.primary],['full',true,{action:'resume',runId:'r1',label:'consistency.resume',disabled:true,reason:{key:'consistency.resolve_first',params:{}}}]);
assert.equal(sceneConsistency(view({},{validity:'valid'}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'})).primary.disabled,false);  // decided: shown in full though valid
assert.equal(sceneConsistency(view({prose:over},{validity:'unchecked'}),'s2',scenes,book({scene_id:'s2',link:'prose',outcome:'unavailable'})).primary.disabled,false);
assert.equal(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,book({scene_id:'s1',link:'brief',outcome:'discrepancy'}),pv(1)).primary.action,'audit');
assert.equal(sceneConsistency(view({brief:link('unchecked')}),'s2',scenes,book({scene_id:'s2',link:'brief',outcome:'discrepancy'},'completed'),pv(1)).primary.action,'audit');
console.log('Link panel actions passed');
