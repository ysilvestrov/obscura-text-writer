import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {setImmediate as tick} from 'node:timers/promises';
const root=new URL('../../../src/storygen/web/static/',import.meta.url);
const {coreReviewModel,installCoreReview,confirmUnsaved}=await import(new URL('core-review.js',root));
const catalog=JSON.parse(readFileSync(new URL('i18n.json',root),'utf8'));

const slot=(name,status,extra={})=>({character_id:'A',name:'Анна',slot:name,label:name,before:null,after:null,status,reason:null,reader_unknown:false,...extra});
const review=(hasWire,extra={})=>({scene_id:'s2',memory_version_id:'m2',revision:3,has_wire:hasWire,day_change:false,confirmation:null,
  slots:[slot('clothing','changed',{before:'Халат',after:'Пальто'}),slot('carried','unknown',{before:'Ключ',reason:'Не згадано'}),slot('location','unchanged'),slot('body','author',{after:'Втома',reader_unknown:true})],
  threads:[{claim_id:'T1',text:'Хто стукав?',status:'closed',resolution:'Сусід'},{claim_id:'T2',text:'Що в листі?',status:'open',resolution:null}],...extra});

// Grouping: unchanged slots and open threads are quiet, everything else is a change.
const model=coreReviewModel(review(true),[]);
assert.deepEqual(model.groups.map(g=>g.kind),['changed','quiet']);
const names=group=>group.rows.map(r=>r.kind==='slot'?r.slot:r.claim_id);
assert.deepEqual(names(model.groups[0]),['clothing','carried','body','T1']);
assert.deepEqual(names(model.groups[1]),['location','T2']);
assert.equal(model.canKeep,true);assert.equal(model.dirty,false);
assert.equal(model.groups[0].rows.every(r=>r.keepable),true,'Keep is offered on changes with a model answer');
assert.equal(model.groups[1].rows.some(r=>r.keepable),false,'Nothing to keep on quiet rows');
assert.equal(model.groups[0].rows.find(r=>r.claim_id==='T1').writable,true);

// Without a captured answer keep is unavailable, and a closed thread cannot be written in (UNKNOWN_TARGET).
const manual=coreReviewModel(review(false),[]);
assert.equal(manual.canKeep,false);
assert.equal(manual.groups.flatMap(g=>g.rows).some(r=>r.keepable),false);
assert.equal(manual.groups[0].rows.find(r=>r.claim_id==='T1').writable,false);
assert.equal(manual.groups[1].rows.find(r=>r.claim_id==='T2').writable,true);

// A draft entry makes the panel dirty and is attached to its row.
const entry={kind:'slot',character_id:'A',slot:'location',action:'set',text:'Кухня',quote:null,evidence_version_id:null};
const dirty=coreReviewModel(review(true),[entry]);
assert.equal(dirty.dirty,true);assert.deepEqual(dirty.groups[1].rows[0].edit,entry);
assert.deepEqual(coreReviewModel({scene_id:'s',memory_version_id:null,slots:[],threads:[]},[]).groups.map(g=>g.rows.length),[0,0]);

// Every panel label exists in both catalogs.
const keys=new Set();
for(const file of ['core-review.js','memory-table.js'])for(const match of readFileSync(new URL(file,root),'utf8').matchAll(/"(m_[0-9a-f]{12})"/g))keys.add(match[1]);
assert.ok(keys.size>=30,'Panel labels go through i18n keys');
for(const key of keys){assert.ok(catalog.uk[key],`uk ${key}`);assert.ok(catalog.en[key],`en ${key}`);}

// The entry panel: Cancel keeps the draft, Apply adds a set edit with the chosen prefix quote, Confirm posts it.
class Element{
  constructor(tag){this.tag=tag;this.children=[];this.attributes={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.className='';}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this.attributes[k]=String(v);}
  getAttribute(k){return this.attributes[k]??null;}
  addEventListener(){}
  focus(){}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
globalThis.document={createElement:tag=>new Element(tag)};
const all=(node,out=[])=>{out.push(node);for(const c of node.children||[])all(c,out);return out;};
const text=node=>all(node).map(n=>String(n.textContent)).join(' ');
const button=(node,label)=>all(node).find(n=>n.tag==='button'&&String(n.textContent)===label);
const prefix=[{scene_id:'s1',scene_number:1,title:'Ранок',version_id:'p1'},{scene_id:'s2',scene_number:2,title:'Гість',version_id:'p2'}];
const fragments={s1:[{version_id:'p1',scene_id:'s1',scene_number:1,fragment_id:'f000001',text:'Анна в халаті.'}],s2:[]};
let posted=null,queries=[],head='m2';const notices=[];
const api=async(url,options)=>{
  if(options){posted=JSON.parse(options.body);return {...review(false),revision:4,memory_version_id:'m3',confirmation:{by:'author',confirmed_at:'2026-11-09T10:00:00Z'}};}
  if(url.endsWith('/core-review'))return {...review(true),memory_version_id:head};
  if(url.endsWith('/core-review/scenes'))return prefix;
  const params=new URL(url,'http://x').searchParams;queries.push([params.get('scene_id'),params.get('q')]);
  return fragments[params.get('scene_id')].filter(f=>f.text.includes(params.get('q')||''));
};
let refreshed=0;
const container=new Element('section');
const panel=installCoreReview({container,api,json:(method,body)=>({method,body:JSON.stringify(body)}),notice:(text,kind)=>notices.push([String(text),kind]),refresh:async()=>{refreshed++;}});
await panel.load('s2');
const confirmLabel=()=>String(all(container).find(n=>n.tag==='button'&&n.className.includes('core-review-confirm')).textContent);
assert.equal(confirmLabel(),catalog.uk.m_6842aa7e5803);
const enter=catalog.uk.m_6ffe74d9820d;
const openEntry=async()=>{button(container,enter).onclick();await tick();await tick();return all(container).find(n=>n.className==='core-review-entry');};
let form=await openEntry();
assert.ok(form,'Write in opens the entry panel');
assert.deepEqual(queries.at(-1),['s2',''],'The current scene is chosen by default');
button(form,catalog.uk.m_8b4c2025378a).onclick();
assert.equal(all(container).some(n=>n.className==='core-review-entry'),false);
assert.equal(confirmLabel(),catalog.uk.m_6842aa7e5803,'Cancel leaves the draft unchanged');
form=await openEntry();
const sceneSelect=all(form).find(n=>n.tag==='select');sceneSelect.value='s1';await sceneSelect.onchange();
const radio=all(form).find(n=>n.tag==='input'&&n.type==='radio'&&n.value==='f000001');radio.checked=true;radio.onchange();
all(form).find(n=>n.tag==='textarea').value='Халат під пальтом';
button(form,catalog.uk.m_387b53c52751).onclick();
assert.equal(confirmLabel(),catalog.uk.m_02d42f8c1439.replace('{p0}','1'),'Apply adds the entry to the draft');
assert.ok(text(container).includes('Халат під пальтом'));
assert.equal(posted,null,'Apply sends nothing to the server');
assert.equal(panel.dirty(),true,'An applied entry is an unsaved draft');
await panel.load('s2');
assert.equal(confirmLabel(),catalog.uk.m_02d42f8c1439.replace('{p0}','1'),'Reloading the same memory head keeps the draft');
assert.equal(notices.length,0);
await button(container,confirmLabel()).onclick();
assert.deepEqual(posted,{expected_revision:3,memory_version_id:'m2',edits:[{kind:'slot',character_id:'A',slot:'clothing',action:'set',text:'Халат під пальтом',quote:'Анна в халаті.',evidence_version_id:'p1'}]});
assert.equal(refreshed,1);assert.equal(confirmLabel(),catalog.uk.m_6842aa7e5803,'The draft is cleared after saving');
assert.equal(panel.dirty(),false);
// A typed value in an open entry counts as unsaved; a head change drops the draft with a notice.
head='m3';await panel.load('s2');notices.length=0;
form=await openEntry();
assert.equal(panel.dirty(),false,'An untouched entry is not a draft');
all(form).find(n=>n.tag==='textarea').value='Шарф';
assert.equal(panel.dirty(),true,'A typed value in the entry is unsaved');
head='m9';await panel.load('s2');
assert.equal(panel.dirty(),false);assert.equal(all(container).some(n=>n.className==='core-review-entry'),false);
assert.deepEqual(notices,[[catalog.uk.m_7016d90fae72,'error']],'A changed memory head discards the draft with a notice');
form=await openEntry();all(form).find(n=>n.tag==='textarea').value='Шарф';button(form,catalog.uk.m_387b53c52751).onclick();
assert.equal(panel.dirty(),true);panel.discard();assert.equal(panel.dirty(),false);
assert.equal(confirmLabel(),catalog.uk.m_6842aa7e5803,'Discard clears the draft');
// The shared navigation guard asks for a core draft too; cancelling keeps it, confirming discards it.
{
  let draft=true,asked=0;const guarded={dirty:false,coreReview:{dirty:()=>draft,discard:()=>{draft=false;}}};
  assert.equal(await confirmUnsaved(guarded,async()=>{asked++;return false;},'?'),false);assert.equal(draft,true);
  assert.equal(await confirmUnsaved(guarded,async()=>{asked++;return true;},'?'),true);assert.equal(draft,false);
  assert.equal(await confirmUnsaved(guarded,async()=>{asked++;return false;},'?'),true,'Nothing unsaved: no question');assert.equal(asked,2);
  assert.equal(await confirmUnsaved({dirty:false},async()=>false,'?'),true,'Works before the panel is installed');
}
// Refreshing the table while the confirmation is still in flight must not leave Confirm disabled for good.
{
  let release,calls=0;
  const slow=new Element('section');
  const slowApi=async(url,options)=>{
    if(options){calls++;await new Promise(r=>{release=r;});return {...review(false),revision:4,memory_version_id:'m3'};}
    return {...review(true),memory_version_id:'m2'};
  };
  const slowPanel=installCoreReview({container:slow,api:slowApi,json:(method,body)=>({method,body:JSON.stringify(body)}),notice(){},refresh:async()=>{}});
  await slowPanel.load('s2');
  const confirm=()=>all(slow).find(n=>n.tag==='button'&&n.className.includes('core-review-confirm'));
  const pending=confirm().onclick();await tick();
  assert.equal(confirm().disabled,true,'Confirm is disabled while the request runs');
  await slowPanel.load('s2');
  release();await pending;await tick();
  assert.equal(confirm().disabled,false,'Confirm is enabled again after a superseded request finishes');
  assert.equal(calls,1);
}
// Switching the interface language reloads the panel, because slot labels come from the server in the request locale.
{
  const listeners={};
  const savedDoc=globalThis.document;
  globalThis.document={createElement:savedDoc.createElement,addEventListener:(name,fn)=>{listeners[name]=fn;}};
  let label='Одяг',gets=0;
  const localized=new Element('section');
  const localeApi=async()=>{gets++;return {...review(true),slots:[slot('clothing','changed',{label,before:'Халат',after:'Пальто'})]};};
  const localePanel=installCoreReview({container:localized,api:localeApi,json:()=>({}),notice(){},refresh:async()=>{}});
  await localePanel.load('s2');
  assert.ok(text(localized).includes('Одяг'));
  label='Clothing';listeners['ui-locale-changed']();await tick();await tick();
  assert.equal(gets,2);assert.ok(text(localized).includes('Clothing'),'Slot headings follow the new language');
  globalThis.document=savedDoc;
}
console.log('core review grouping, keep availability, draft entry, labels and confirm passed');
