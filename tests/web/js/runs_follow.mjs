import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const mode=process.argv[2],root=process.argv[3];
const created=[],listeners=new Map(),elements=new Map(),pendingEvents=[];
class Element{
  value='';textContent='';disabled=false;hidden=false;dataset={storyId:'s'};children=[];handlers={};classList={toggle(){}};
  setAttribute(name,value){this[name]=value}
  addEventListener(name,handler){this.handlers[name]=handler}
  trigger(name){this.handlers[name]?.()}
  replaceChildren(){this.children=[]}
  append(...items){this.children.push(...items)}
}
function element(id){if(!elements.has(id))elements.set(id,new Element());return elements.get(id)}
globalThis.document={querySelector:element,querySelectorAll:()=>[],createElement:()=>{const e=new Element();created.push(e);return e},addEventListener(name,handler){if(!listeners.has(name))listeners.set(name,[]);listeners.get(name).push(handler)},dispatchEvent(event){for(const handler of listeners.get(event.type)||[]){const result=handler(event);if(result?.then)pendingEvents.push(result)}}};
globalThis.CustomEvent=class {constructor(type){this.type=type}};
globalThis.confirm=()=>true;
const originalTimeout=globalThis.setTimeout;globalThis.setTimeout=(...args)=>{const timer=originalTimeout(...args);timer.unref();return timer};
globalThis.setInterval=()=>({unref(){}});
const store=new Map();
globalThis.sessionStorage={getItem:k=>store.has(k)?store.get(k):null,setItem:(k,v)=>store.set(k,String(v)),removeItem:k=>store.delete(k)};
const scene={id:'c',story_id:'s',position:0,revision:0,title:'Сцена',beats:'План',target_words:400,heads:{},character_ids:[]};
const mk=(id,reqMode,state,created_at)=>({id,story_id:'s',request_id:'q-'+id,state,created_at,request:{story_id:'s',mode:reqMode},impact:null});
const shortRuns=[mk('prep','prepare','completed','2026-01-01T00:00:00+00:00'),mk('drf','stage','completed','2026-01-02T00:00:00+00:00'),mk('r','stage','running','2026-01-03T00:00:00+00:00')];
const fullOf=short=>({...short,tasks:short.id==='imp'?[{},{}]:[],...(short.id==='imp'?{impact:{protocol:3,phase:'awaiting_author',scene_cursor:1,order:[]}}:{}),cursor:0,error:short.id==='r'?'Технічна причина':null,warning:null,planned_telemetry:{roles:{writer:{provider:'p',model:'m'}},calls:3},editor_loop:null,editor_loops:{},cancelled_before_enqueue:false});
if(mode==='review')shortRuns.splice(2,0,{...mk('imp','impact','needs_review','2026-01-02T12:00:00+00:00'),impact:{protocol:3,phase:'awaiting_author'}});
let release,fail=mode==='failure';const gate=new Promise(resolve=>{release=resolve});
const stale={on:false,state:'running',calls:0,gates:[]};
const log=[];
const response=data=>({ok:true,json:async()=>structuredClone(data)});
globalThis.fetch=async url=>{
 log.push(url);
 const detail=url.match(/^\/api\/runs\/([a-z]+)$/);
 if(detail&&stale.on){const snapshot=stale.state,run=shortRuns.find(r=>r.id===detail[1]);stale.calls++;await new Promise(r=>stale.gates.push(r));return response({run:{...fullOf(run),state:snapshot},attempts:[{result_version_id:'v1',created_at:run.created_at}],partial:''})}
 if(detail){await gate;if(fail)return {ok:false,status:500,json:async()=>({detail:'boom'})};const run=shortRuns.find(r=>r.id===detail[1]);return response({run:fullOf(run),attempts:[{result_version_id:'v1',created_at:run.created_at}],partial:''})}
 if(url==='/api/versions/v1')return response({text:'x'});
 if(url.endsWith('/runs'))return response({runs:shortRuns});
 if(url.includes('readiness'))return response({operations:{},ready:true,roles:{},calls:1});
 return response({story:{id:'s',revision:0},scenes:[scene],sources:[]});
};
globalThis.EventSource=class{constructor(){this.closed=false;globalThis.EventSource.last=this}close(){this.closed=true}};
if(mode==='review'){release();const host=element('#review-session');await import(pathToFileURL(root+'/src/storygen/web/static/review-session.js'));for(let i=0;i<8;i++)await new Promise(setImmediate);assert.ok(log.includes('/api/stories/s/review/imp'),'protocol-3 session chosen from the short list');assert.ok(log.includes('/api/runs/imp'),'full session run fetched');const {t:tr}=await import(pathToFileURL(root+'/src/storygen/web/static/i18n.js'));
const texts=host.children.map(c=>c.textContent);
assert.equal(texts[0],tr('review.title'),'session heading rendered');
assert.equal(texts[1],tr('review.scene_progress',{p0:2,p1:2}),'progress from session.tasks and impact.scene_cursor');
const actions=host.children.find(c=>c.className==='actions');assert.ok(actions,'actions container rendered');
assert.deepEqual(actions.children.map(c=>c.textContent),[tr('review.cancel')],'needs_review session offers exactly Cancel');
assert.equal(host.hidden,false,'session host is visible');console.log('review session loads on the short list');process.exit(0)}
if(mode==='recover'){store.set('storygen.tab','t1');store.set('storygen.primary.pending.s.t1',JSON.stringify({requestId:'q-r',request:{story_id:'s',mode:'stage'}}))}
await import(pathToFileURL(root+'/src/storygen/web/static/runs.js'));
const {state}=await import(pathToFileURL(root+'/src/storygen/web/static/editor.js'));
const {t}=await import(pathToFileURL(root+'/src/storygen/web/static/i18n.js'));
const tick=async()=>{for(let i=0;i<8;i++)await new Promise(setImmediate)};
const text=()=>element('#run-status').children.map(e=>e.textContent).join('|');
const byLabel=key=>{const b=created.find(e=>e.onclick&&e.textContent===t(key));assert.ok(b,'button '+key);return b};
const detailCalls=()=>log.filter(u=>/^\/api\/runs\/[a-z]+$/.test(u));
await tick();
const cancel=byLabel('m_8b4c2025378a'),pause=byLabel('m_03498e395a43');
if(mode==='stale'){
  release();await tick();
  const source=globalThis.EventSource.last;assert.ok(source,'follow opened the event stream');
  stale.on=true;log.length=0;
  const push=(seq)=>source.onmessage({data:JSON.stringify({seq,type:'state',data:{}})});
  // Подія 1: сервер уже cancelling; запит A залишається в польоті.
  stale.state='cancelling';push(1);await tick();
  // Подія 2: сервер уже cancelled; запит B не може приєднатися до A, бо A знято до цієї події.
  stale.state='cancelled';push(2);await tick();
  assert.equal(stale.calls,2,'the terminal event sends its own GET instead of joining the older one');
  while(stale.gates.length)stale.gates.shift()();await tick();
  assert.equal(state.workspaceRun.state,'cancelled','terminal state is drawn');
  assert.equal(source.closed,true,'terminal state closes the stream');
}else if(mode==='latest'){
  assert.deepEqual(detailCalls(),['/api/runs/r'],'open-story follow targets the last run');
  release();await tick();log.length=0;
  byLabel('m_e3b0d35990c3').onclick();await tick();
  assert.deepEqual(detailCalls(),['/api/runs/r'],'latest button follows the last short run');
  assert.equal(state.workspaceRun.planned_telemetry.calls,3);
  log.length=0;
  byLabel('m_e1cb5a4ec579').onclick();await tick();
  assert.deepEqual(detailCalls(),['/api/runs/prep'],'proposal opens the last completed prepare, not the last run');
  assert.ok(log.includes('/api/versions/v1'));
}else{
  assert.ok(detailCalls().includes('/api/runs/r'),'follow must fetch the full run');
  // Before the detail answers: short run only drives state/controls, no misleading plan or error text.
  assert.equal(state.workspaceRun.id,'r');assert.equal(state.workspaceRun.state,'running');
  assert.ok(!('planned_telemetry' in state.workspaceRun));
  assert.equal(cancel.disabled,false,'cancel stays enabled while the full run loads');
  assert.equal(pause.disabled,false,'pause stays enabled while the full run loads');
  assert.ok(!text().includes('план'),'no plan-unknown placeholder from a short run');
  assert.ok(!text().includes('Технічна причина'));
  release();await tick();
  if(fail){
    assert.equal(state.workspaceRun.state,'running','short state stays after a failed detail fetch');
    assert.equal(cancel.disabled,false);
  }else{
    assert.ok(state.workspaceRun.planned_telemetry);
    assert.ok(text().includes('Технічна причина'),'error from the full run is shown');
  }
}
console.log('follow regressions passed ('+mode+')');
