import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {setImmediate as tick} from 'node:timers/promises';
class Element{
  constructor(tag=''){this.tag=tag;this.children=[];this.dataset={};this.value='';this.hidden=false;this.disabled=false;}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this[k]=v;}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
const nodes=Object.fromEntries(['memory-view','editor','save-text','save-state'].map(id=>['#'+id,new Element()]));
const events={};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
globalThis.document={querySelector:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),dispatchEvent:event=>{for(const fn of events[event.type]||[])fn();}};
globalThis.confirm=()=>false;
const state={scene:{id:'s',heads:{memory:'m'},revision:0},mode:'memory',bufferOrigin:'current',bufferEpoch:1,dirty:false,saving:false};
let release,hold=false,fail=false,sent;
const response={scene:state.scene,expected_revision:0,fingerprint:'hash',memory_id:'m',can_save:true,
  rows:[{claim_id:'HIDDEN_ID',text:'Факт <img>',quote:'Доказ',category:'facts',category_label:'Факт',forward:true,source_scene:1,source_title:'Початок'}]};
const api=async(url,options)=>{
  if(options){sent=options.body;if(hold)await new Promise(resolve=>release=resolve);if(fail)throw Error('Конфлікт');return {...response,rows:[{...response.rows[0],forward:false}]};}
  return response;
};
const {installMemoryTable}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-table.js'));
const memory=installMemoryTable({state,api,json:(method,body)=>({method,body}),notice:()=>{},refresh:async()=>{},loadBuffer:()=>{}});
document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();
const panel=nodes['#memory-view'],body=panel.children[4].children[0].children[2];
assert.equal(nodes['#editor'].hidden,true);assert.equal(memory.active(),true);
assert.equal(JSON.stringify(panel).includes('HIDDEN_ID'),false,'Internal claim IDs are not visible DOM text');
const check=body.children[0].children[0].children[0];
check.checked=false;check.onchange();assert.equal(state.dirty,true);assert.equal(nodes['#save-text'].disabled,false);
panel.children[1].children[0].onclick();assert.equal(memory.active(),true,'Dirty switch requires explicit discard');
fail=true;await memory.save();assert.equal(state.dirty,true,'Conflict preserves the selection');
fail=false;hold=true;const saving=memory.save();await tick();assert.equal(state.saving,true);
assert.equal(body.children[0].children[0].children[0].disabled,true);release();await saving;
assert.deepEqual(sent.choices,{HIDDEN_ID:false});assert.equal(state.dirty,false);
panel.children[1].children[0].onclick();assert.equal(memory.active(),false);
assert.equal(nodes['#save-text'].disabled,false,'Advanced JSON restores the ordinary Save button');
nodes['#editor'].value='{"author_edit":true}';state.bufferEpoch++;state.dirty=true;
document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();
assert.equal(memory.active(),false,'Typing JSON must not reload the table');
assert.equal(nodes['#editor'].hidden,false);assert.equal(nodes['#editor'].value,'{"author_edit":true}');
assert.equal(state.dirty,true);
state.mode='plan';document.dispatchEvent(new CustomEvent('editor-state-changed'));
assert.equal(panel.hidden,true);assert.equal(nodes['#editor'].hidden,false);
console.log('memory table selection, dirty switch, async save, conflict and hidden IDs passed');
