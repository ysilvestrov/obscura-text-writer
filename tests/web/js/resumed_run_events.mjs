import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const mode=process.argv[2],root=process.argv[3];
const listeners=new Map(),elements=new Map(),pendingEvents=[];
class Element{
  value='';textContent='';disabled=false;hidden=false;dataset={storyId:'s'};children=[];handlers={};classList={toggle(){}};
  setAttribute(name,value){this[name]=value}
  addEventListener(name,handler){this.handlers[name]=handler}
  trigger(name){this.handlers[name]?.()}
  replaceChildren(){this.children=[]}
  append(...items){this.children.push(...items)}
}
function element(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}
globalThis.document={querySelector:element,querySelectorAll:()=>[],createElement:()=>new Element(),addEventListener(name,handler){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(handler)},dispatchEvent(event){for(const handler of listeners.get(event.type)||[]){const result=handler(event);if(result?.then)pendingEvents.push(result)}}};
globalThis.CustomEvent=class {constructor(type){this.type=type}};
globalThis.confirm=()=>true;
const originalTimeout=globalThis.setTimeout;globalThis.setTimeout=(...args)=>{const timer=originalTimeout(...args);timer.unref();return timer};
const scene={id:'c',story_id:'s',position:0,revision:0,title:'Сцена',beats:'План',target_words:400,heads:{},character_ids:[]};
let serverState=mode==='terminal'?'failed':'running',timer;const sources=[];
const interval=globalThis.setInterval;globalThis.setInterval=handler=>{timer=handler;return {unref(){}}};
const run=()=>({id:'r',state:serverState,error:mode==='terminal'?'Технічна причина':null,warning:mode==='terminal'?'Попередження контексту':null,created_at:new Date(Date.now()-140000).toISOString(),request:{mode:'stage',stage:'memory'}});
const response=data=>({ok:true,json:async()=>structuredClone(data)});
globalThis.fetch=async url=>{
 if(url==='/api/runs/r')return response({run:run(),attempts:[],partial:'Часткова пам’ять'});
 if(url.endsWith('/runs'))return response({runs:[run()]});
 if(url.includes('readiness'))return response({operations:{},ready:true,roles:{},calls:1});
 return response({story:{id:'s',revision:0},scenes:[scene],sources:[]});
};
globalThis.EventSource=class{constructor(){sources.push(this);this.closed=false}close(){this.closed=true}};
await import(pathToFileURL(root+'/src/storygen/web/static/runs.js'));
for(let i=0;i<5;i++)await new Promise(setImmediate);
if(mode==='terminal'){assert.equal(sources.length,0);assert.equal(element('#live-text').textContent,'Часткова пам’ять');assert.equal(element('#run-status').dataset.kind,'error');assert.ok(element('#run-status').children.some(e=>e.textContent==='Попередження контексту'));assert.ok(element('#run-status').children.some(e=>e.textContent==='Технічна причина'));process.exit(0)}
const source=sources.at(-1);assert.ok(source);
await source.onmessage({data:JSON.stringify({seq:1,type:'state',data:{state:'failed'}})});
assert.equal(source.closed,false,'Historical failure must not close a currently running stream');
await source.onmessage({data:JSON.stringify({seq:2,type:'stage_started',created_at:new Date(Date.now()-5000).toISOString(),data:{stage:'memory',model:'fake',provider:'local'}})});
timer();
assert.ok(element('#run-status').children.some(e=>e.textContent==='Минуло 5 с'),'Timer must use current attempt, not original run');
serverState='failed';
await source.onmessage({data:JSON.stringify({seq:3,type:'state',data:{state:'failed'}})});
assert.equal(source.closed,true);
assert.equal(element('#live-text').textContent,'Часткова пам’ять','Terminal snapshot must restore complete partial even before SSE replay catches up');
assert.equal(element('#run-status').dataset.kind,'error');
console.log('resumed event stream regression passed');process.exit(0);
