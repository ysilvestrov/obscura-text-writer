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
  focus(){document.activeElement=this}
  contains(node){return node===this||this.children.some(child=>child.contains?.(node))}
  set innerHTML(_){throw Error('Untrusted text may not become HTML');}
}
const nodes=Object.fromEntries(['memory-view','editor','save-text','save-state'].map(id=>['#'+id,new Element()]));
const events={};
globalThis.CustomEvent=class{constructor(type){this.type=type;}};
globalThis.document={body:new Element('body'),activeElement:null,querySelector:id=>nodes[id],createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),removeEventListener:()=>{},addEventListener:(type,fn)=>(events[type]??=[]).push(fn),dispatchEvent:event=>{for(const fn of events[event.type]||[])fn();}};
const state={scene:{id:'s',story_id:'st',position:1,heads:{memory:'m'},revision:0},view:{scenes:[{id:'s',position:1,title:'Друга'}]},mode:'memory',bufferOrigin:'current',bufferEpoch:1,dirty:false,saving:false};
const rows=()=>[
  {claim_id:'SLOT',text:'Синій халат',quote:'q',category:'character_states',category_label:'Стан персонажа',forward:true,source_scene:2,source_title:'Друга',kind:null,slot:true},
  {claim_id:'FACT',text:'Маяк на карті',quote:'q',category:'facts',category_label:'Факт',forward:true,source_scene:2,source_title:'Друга',kind:'atmosphere',slot:false}];
let revision=3,loads=0,sent=null,fail=false,gate=null;const notices=[];
const api=async(url,options)=>{
  if(url.endsWith('/memory-kind')){
    sent={url,...JSON.parse(JSON.stringify(options.body))};
    if(gate)await gate;
    if(fail)throw Error('Твір уже змінено');
    return {id:'st',revision:++revision};
  }
  if(url.endsWith('/memory-view'))loads++;return {scene:state.scene,expected_revision:0,fingerprint:'h',memory_id:'m',can_save:true,story_revision:revision,rows:rows()};
};
const {installMemoryTable}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/memory-table.js'));
installMemoryTable({state,api,json:(method,body)=>({method,body}),notice:(text,kind)=>notices.push([String(text),kind]),refresh:async()=>{},loadBuffer:()=>{}});
document.dispatchEvent(new CustomEvent('editor-state-changed'));await tick();
const panel=nodes['#memory-view'],table=panel.children[6].children[0],body=table.children[2];
assert.ok(panel.children[5].className.includes('memory-kind-legend'),'An icon legend sits above the table');
assert.equal(table.children[1].children[0].children.length,5,'Type is a fifth column');
const kindCell=row=>body.children[row].children[4];
assert.equal(kindCell(0).children[0].tag,'span','A core slot has no type control');
const control=()=>{const box=kindCell(1).children[0];return {button:box.children[0],menu:box.children[1]};};
let {button,menu}=control();
assert.equal(button.tag,'button');assert.equal(button.dataset.kind,'atmosphere');
assert.equal(button['aria-haspopup'],'menu');assert.equal(button['aria-label'],'Тип запису «Маяк на карті»: Атмосфера');
assert.equal(menu.hidden,true,'The menu is closed until the button is pressed');
button.onclick();
assert.equal(menu.hidden,false);assert.equal(button['aria-expanded'],'true');
assert.deepEqual(menu.children.map(item=>item.dataset.kind),['','core','atmosphere']);
assert.deepEqual(menu.children.map(item=>item['aria-checked']),['false','false','true']);
assert.equal(document.activeElement,menu.children[2],'Focus starts on the checked item');
menu.onkeydown({key:'ArrowDown',preventDefault(){}});assert.equal(document.activeElement,menu.children[0],'Arrows wrap around');
menu.onkeydown({key:'Escape',preventDefault(){}});assert.equal(menu.hidden,true);assert.equal(document.activeElement,button,'Escape returns focus to the button');
button.onclick();await menu.children[1].onclick({stopPropagation(){}});await tick();
assert.deepEqual({claim_id:sent.claim_id,kind:sent.kind,expected_revision:sent.expected_revision},{claim_id:'FACT',kind:'core',expected_revision:3});
assert.equal(sent.url,'/api/stories/st/memory-kind');
assert.equal(state.dirty,false,'A type change is saved at once, not left for Save');
({button,menu}=control());assert.equal(button.dataset.kind,'core');
assert.equal(document.activeElement,button,'After saving, focus returns to the redrawn button');
button.onclick();await menu.children[0].onclick({stopPropagation(){}});await tick();
assert.equal(sent.kind,null);assert.equal(sent.expected_revision,4,'The next change uses the new story revision');
// The author moves to another field while the type is saving: the redraw does not take focus back.
let release;gate=new Promise(resolve=>{release=resolve;});
({button,menu}=control());button.onclick();const saving=menu.children[1].onclick({stopPropagation(){}});
const search={isConnected:true};document.activeElement=search;release();await saving;await tick();gate=null;
assert.equal(document.activeElement,search,'A save in flight does not steal focus from the field the author moved to');
fail=true;const before=loads;({button,menu}=control());button.onclick();await menu.children[2].onclick({stopPropagation(){}});await tick();
assert.equal(notices.at(-1)[1],'error');assert.equal(loads,before+1,'A failed change reloads the table');
assert.equal(JSON.stringify(panel).includes('"FACT"'),false,'Claim IDs are not visible DOM text');
console.log('memory kind column passed');
