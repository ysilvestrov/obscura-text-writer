import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {textStatistics}=await import(pathToFileURL(root+'/src/storygen/web/static/text-statistics.js'));
assert.deepEqual(textStatistics("П’ять п'єс, пʼять. Синьо-жовтий — пів‐аркуша і пів‑слова! 😀"),{characters:59,words:7});
assert.deepEqual(textStatistics('і\u0308жа'),{characters:4,words:1});
class Node{
  children=[];textContent='';value='';handlers={};open=false;
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=items}
  addEventListener(name,handler){this.handlers[name]=handler}
  setAttribute(){}
  set innerHTML(_){throw Error('No raw HTML')}
}
const nodes=new Map(['#scene-statistics','#editor','#current-kind'].map(id=>[id,new Node()]));
const handlers={};
const document={querySelector:id=>nodes.get(id),createElement:()=>new Node(),addEventListener:(name,fn)=>handlers[name]=fn};
const state={scene:{id:'a'},mode:'draft',dirty:false,bufferOrigin:'current'};
let release,calls=0;
const api=()=>{calls++;return new Promise(resolve=>release=resolve)};
const {installSceneStatistics}=await import(pathToFileURL(root+'/src/storygen/web/static/scene-statistics.js'));
const ui=installSceneStatistics({state,api,document});
nodes.get('#editor').value='Ручна правка';state.dirty=true;handlers['editor-state-changed']();
assert.equal(calls,0);assert.match(ui.compact.textContent,/Незбережений/);
state.saving=true;handlers['editor-state-changed']();assert.match(ui.compact.textContent,/під час збереження/);state.saving=false;
ui.details.open=true;const pending=ui.load();state.scene={id:'b'};
release({scene_id:'a',materials:{},memory:{},context:{},target_words:800});await pending;
assert.equal(ui.body.children.length,0,'late response for another scene must not render');
state.bufferOrigin='history';handlers['editor-state-changed']();assert.match(ui.compact.textContent,/Історична/);
const success=ui.load();release({scene_id:'b',scene_revision:1,materials:{prose:{words:1,characters:3,complete:true,stale:false,version_id:'v'}},memory:{previous:{available:false,reason:'Немає пам’яті'},through_scene:{available:false,reason:'Немає пам’яті'}},context:{available:false,reason:'Немає завдання'},target_words:800,last_usage:null});await success;
assert.ok(ui.body.children.length>0,'current response must render');
// MEMORY-SELECT-S08: the selection line names chosen, total and dropped entries with the dropped layers.
const context={available:true,provider:'p',model:'m',estimated_input_tokens:1,input_budget:2,output_reserve:1,context_tokens:3,method:'x',parts:[],
  memory_selection:{selected:4,total:9,dropped:5,layers:{core:1,facts:3},dropped_layers:{fts:3,timeline:2}}};
const selected=ui.load();release({scene_id:'b',scene_revision:2,materials:{},memory:{previous:{available:false},through_scene:{available:false}},context,target_words:800,last_usage:null});await selected;
const texts=ui.body.children.map(n=>String(n.textContent));
assert.ok(texts.some(t=>/Відбір пам’яті: вибрано 4 з 9, відкинуто 5 \(пошук за планом: 3, хронологія: 2\)/.test(t)),texts.join('|'));
const narrowed=ui.load();release({scene_id:'b',scene_revision:3,materials:{},memory:{previous:{available:false},through_scene:{available:false}},context:{...context,memory_selection:undefined,memory_narrow:{hidden:7}},target_words:800,last_usage:null});await narrowed;
assert.ok(ui.body.children.some(n=>/Каталог пам’яті звужено: не показано моделі 7/.test(String(n.textContent))));
console.log('statistics UI guards passed');
