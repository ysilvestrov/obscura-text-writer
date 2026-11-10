// MEMORY-SELECT-S08: the memory table's Type column (auto / core / atmosphere), saved at once with story CAS.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {setImmediate as tick} from 'node:timers/promises';
class Element{
  constructor(tag=''){this.tag=tag;this.children=[];this.dataset={};this.value='';this.hidden=false;this.disabled=false;this.listeners={};}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this[k]=v;}
  addEventListener(name,fn){this.listeners[name]=fn}
  remove(){}
  focus(){}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
const nodes=Object.fromEntries(['memory-view','editor','save-text','save-state'].map(id=>['#'+id,new Element()]));
const events={};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
globalThis.document={body:new Element('body'),querySelector:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),dispatchEvent:event=>{for(const fn of events[event.type]||[])fn();}};
const state={scene:{id:'s',story_id:'st',position:1,heads:{memory:'m'},revision:0},view:{scenes:[{id:'s',position:1,title:'Друга'}]},mode:'memory',bufferOrigin:'current',bufferEpoch:1,dirty:false,saving:false};
const rows=()=>[
  {claim_id:'SLOT',text:'Синій халат',quote:'q',category:'character_states',category_label:'Стан персонажа',forward:true,source_scene:2,source_title:'Друга',kind:null,slot:true},
  {claim_id:'FACT',text:'Маяк на карті',quote:'q',category:'facts',category_label:'Факт',forward:true,source_scene:2,source_title:'Друга',kind:'atmosphere',slot:false}];
let revision=3,loads=0,sent=null,fail=false;const notices=[];
const api=async(url,options)=>{
  if(url.endsWith('/memory-kind')){
    sent={url,...JSON.parse(JSON.stringify(options.body))};
    if(fail)throw Error('Твір уже змінено');
    return {id:'st',revision:++revision};
  }
  if(url.endsWith('/memory-view'))loads++;return {scene:state.scene,expected_revision:0,fingerprint:'h',memory_id:'m',can_save:true,story_revision:revision,rows:rows()};
};
const {installMemoryTable}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-table.js'));
installMemoryTable({state,api,json:(method,body)=>({method,body}),notice:(text,kind)=>notices.push([String(text),kind]),refresh:async()=>{},loadBuffer:()=>{}});
document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();
const panel=nodes['#memory-view'],table=panel.children[5].children[0],body=table.children[2];
assert.equal(table.children[1].children[0].children.length,5,'Type is a fifth column');
const kindCell=row=>body.children[row].children[4];
assert.equal(kindCell(0).children[0].tag,'span','A core slot has no type control');
const select=kindCell(1).children[0];
assert.equal(select.tag,'select');assert.equal(select.value,'atmosphere');
assert.deepEqual(select.children.map(o=>o.value),['','core','atmosphere']);
select.value='core';await select.onchange();
assert.deepEqual({claim_id:sent.claim_id,kind:sent.kind,expected_revision:sent.expected_revision},{claim_id:'FACT',kind:'core',expected_revision:3});
assert.equal(sent.url,'/api/stories/st/memory-kind');
assert.equal(state.dirty,false,'A type change is saved at once, not left for Save');
assert.equal(kindCell(1).children[0].value,'core');
kindCell(1).children[0].value='';await kindCell(1).children[0].onchange();
assert.equal(sent.kind,null);assert.equal(sent.expected_revision,4,'The next change uses the new story revision');
fail=true;const before=loads;kindCell(1).children[0].value='atmosphere';await kindCell(1).children[0].onchange();await tick();
assert.equal(notices.at(-1)[1],'error');assert.equal(loads,before+1,'A failed change reloads the table');
assert.equal(JSON.stringify(panel).includes('"FACT"'),false,'Claim IDs are not visible DOM text');
console.log('memory kind column passed');
