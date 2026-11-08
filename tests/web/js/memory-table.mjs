import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {setImmediate as tick} from 'node:timers/promises';
class Element{
  constructor(tag=''){this.tag=tag;this.children=[];this.dataset={};this.value='';this.hidden=false;this.disabled=false;}
  append(...items){this.children.push(...items);}
  replaceChildren(...items){this.children=items;}
  setAttribute(k,v){this[k]=v;}
  addEventListener(){}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
const nodes=Object.fromEntries(['memory-view','editor','save-text','save-state'].map(id=>['#'+id,new Element()]));
const events={};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
globalThis.document={querySelector:id=>nodes[id],createElement:tag=>new Element(tag),addEventListener:(type,fn)=>(events[type]??=[]).push(fn),dispatchEvent:event=>{for(const fn of events[event.type]||[])fn();}};
globalThis.confirm=()=>false;
const state={scene:{id:'s',position:0,heads:{memory:'m'},revision:0},view:{scenes:[{id:'s',position:0,title:'Початок'},{id:'s2',position:1,title:'Друга'}]},mode:'memory',bufferOrigin:'current',bufferEpoch:1,dirty:false,saving:false};
let release,hold=false,fail=false,sent;
const response={scene:state.scene,expected_revision:0,fingerprint:'hash',memory_id:'m',can_save:true,
  rows:[{claim_id:'HIDDEN_ID',text:'Факт <img>',quote:'Доказ',supporting_quotes:['Ще один','Третій'],category:'facts',category_label:'Факт',forward:true,source_scene:1,source_title:'Початок'},
  {claim_id:'NO_SUPPORT',text:'Другий',quote:'Без додаткових',category:'facts',category_label:'Факт',forward:true,source_scene:1,source_title:'Початок'},
  {claim_id:'OTHER',text:'Інша сцена',quote:'Цитата',category:'timeline',category_label:'Хронологія',forward:true,source_scene:2,source_title:'Друга'},
  {claim_id:'UNKNOWN',text:'Невідоме джерело',quote:'Цитата',category:'facts',category_label:'Факт',forward:true,source_scene:null,source_title:'Попереднє джерело'}]};
const api=async(url,options)=>{
  if(options){sent=options.body;if(hold)await new Promise(resolve=>release=resolve);if(fail)throw Error('Конфлікт');return {...response,rows:[{...response.rows[0],forward:false}]};}
  return response;
};
const {installMemoryTable}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-table.js'));
const memory=installMemoryTable({state,api,json:(method,body)=>({method,body}),notice:()=>{},refresh:async()=>{},loadBuffer:()=>{}});
document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();
const panel=nodes['#memory-view'],body=panel.children[4].children[0].children[2];
assert.equal(nodes['#editor'].hidden,true);assert.equal(memory.active(),true);
const sceneFilter=panel.children[3].children[2];
assert.equal(sceneFilter.value,'1','Current scene is selected by default');
assert.equal(body.children.length,2);
sceneFilter.value='2';sceneFilter.onchange();assert.equal(body.children.length,1);assert.equal(body.children[0].children[1].children[0].textContent,'Інша сцена');
sceneFilter.value='';sceneFilter.onchange();assert.equal(body.children.length,4,'All includes entries with unknown sources');
const search=panel.children[3].children[0],category=panel.children[3].children[1];
category.value='timeline';category.onchange();assert.equal(body.children.length,1);
search.value='Немає';search.oninput();assert.equal(body.children[0].children.length,1,'Filters combine and show empty state');
search.value='';category.value='';sceneFilter.value='1';sceneFilter.onchange();
const proofOf=row=>row.children[1].children[1];
const paragraphs=proofOf(body.children[0]).children.filter(c=>c.tag==='p').map(c=>String(c.textContent));
assert.deepEqual(paragraphs,['Доказ','Ще один','Третій'],'Supporting quotes follow the main quote');
assert.deepEqual(proofOf(body.children[1]).children.filter(c=>c.tag==='p').map(c=>String(c.textContent)),['Без додаткових'],'A row without supporting_quotes renders exactly the main quote');

assert.equal(JSON.stringify(panel).includes('HIDDEN_ID'),false,'Internal claim IDs are not visible DOM text');
const check=body.children[0].children[0].children[0];
check.checked=false;check.onchange();sceneFilter.value='2';sceneFilter.onchange();sceneFilter.value='1';sceneFilter.onchange();assert.equal(body.children[0].children[0].children[0].checked,false,'Filtering preserves unsaved choices');assert.equal(state.dirty,true);assert.equal(nodes['#save-text'].disabled,false);
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
state.dirty=false;state.mode='memory';state.bufferOrigin='current';state.scene={id:'s2',position:1,heads:{memory:'m'},revision:0};state.bufferEpoch++;document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();assert.equal(sceneFilter.value,'2','Changing scene resets the filter to the current scene');
state.mode='plan';document.dispatchEvent(new CustomEvent('editor-state-changed'));
assert.equal(panel.hidden,true);assert.equal(nodes['#editor'].hidden,false);
console.log('memory table selection, dirty switch, async save, conflict and hidden IDs passed');
