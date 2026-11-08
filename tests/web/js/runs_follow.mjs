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
const interval=globalThis.setInterval;globalThis.setInterval=()=>({unref(){}});
const scene={id:'c',story_id:'s',position:0,revision:0,title:'Сцена',beats:'План',target_words:400,heads:{},character_ids:[]};
const request={story_id:'s',mode:'prepare'};
const shortRun={id:'r',story_id:'s',request_id:'q',state:'failed',created_at:new Date().toISOString(),request,impact:null};
const fullRun={...shortRun,tasks:[],cursor:0,error:'Технічна причина',warning:null,planned_telemetry:{roles:{writer:{provider:'p',model:'m'}},calls:3},editor_loop:null,editor_loops:{},cancelled_before_enqueue:false};
let release,detailRequests=0;const gate=new Promise(resolve=>{release=resolve});
const response=data=>({ok:true,json:async()=>structuredClone(data)});
globalThis.fetch=async url=>{
 if(url==='/api/runs/r'){detailRequests++;await gate;return response({run:fullRun,attempts:[],partial:''})}
 if(url.endsWith('/runs'))return response({runs:[shortRun]});
 if(url.includes('readiness'))return response({operations:{},ready:true,roles:{},calls:1});
 return response({story:{id:'s',revision:0},scenes:[scene],sources:[]});
};
globalThis.EventSource=class{constructor(){this.closed=false}close(){this.closed=true}};
await import(pathToFileURL(root+'/src/storygen/web/static/runs.js'));
const {state}=await import(pathToFileURL(root+'/src/storygen/web/static/editor.js'));
const text=()=>element('#run-status').children.map(e=>e.textContent).join('|');
for(let i=0;i<5;i++)await new Promise(setImmediate);
assert.equal(detailRequests,1,'open-story follow must fetch the full run');
assert.equal(state.workspaceRun,undefined,'short run must not be drawn before /api/runs/{id} answers');
assert.ok(!text().includes('план'),'no "plan unknown" placeholder from a short run');
release();
for(let i=0;i<5;i++)await new Promise(setImmediate);
assert.equal(state.workspaceRun.id,'r');assert.ok(state.workspaceRun.planned_telemetry);
assert.ok(text().includes('Технічна причина'),'error from the full run is shown');
console.log('follow draws only the full run');process.exit(0);
