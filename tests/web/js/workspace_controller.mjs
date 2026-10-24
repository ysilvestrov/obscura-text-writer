import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
const base=new URL('../../../src/storygen/web/static/',import.meta.url);
class Element{
  hidden=false;disabled=false;value='';dataset={};textContent='';children=[];attrs={};
  setAttribute(k,v){this.attrs[k]=v}querySelector(){return null}append(...nodes){this.children.push(...nodes)}
}
const nodes=new Map(),handlers=new Map();
const element=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id)};
globalThis.CustomEvent=class{constructor(type,options={}){this.type=type;this.detail=options.detail}};
const tab=new Element();tab.dataset={mode:'draft',label:'Чернетка'};
globalThis.document={querySelector:element,querySelectorAll:()=>[tab],createElement:()=>new Element(),
  addEventListener(name,fn){if(!handlers.has(name))handlers.set(name,[]);handlers.get(name).push(fn)},
  dispatchEvent(e){for(const fn of handlers.get(e.type)||[])fn(e)}};
const state={storyId:'s',scene:{id:'c',heads:{draft:'d'}},view:{scenes:[{id:'c'},{id:'next'}]},mode:'draft',dirty:true,bufferEpoch:0,
  workspaceReadiness:{operations:{edit_loop:{ready:true}}}};
let releaseSave,hold=false,runs=0,saves=0,accepts=0,errors=[];
globalThis.fixture={state,textEditor:{visible(){}},selectScene:async()=>{},refresh:async()=>{},api:async()=>{},json:()=>{},notice:message=>errors.push(message),
  invokeWorkspaceCommand:async(name,payload)=>{
    if(name==='save'){saves++;if(hold)await new Promise(r=>releaseSave=r);state.dirty=false}
    if(name==='run'){runs++;assert.equal(payload.editor_source_version_id,'d');return {id:'run',state:'running'}}
    if(name==='accept-review')accepts++;
  }};
let code=readFileSync(new URL('workspace-route.js',base),'utf8');
code=code.replace(/^import .* from '\.\/editor.js';$/m,'const {state,textEditor,selectScene,refresh}=globalThis.fixture;')
  .replace(/^import .* from '\.\/api.js';$/m,'const {api,json,notice}=globalThis.fixture;')
  .replace(/^import .* from '\.\/workspace-commands.js';$/m,'const {invokeWorkspaceCommand}=globalThis.fixture;')
  .replace("'./workspace-state.js'",JSON.stringify(new URL('workspace-state.js',base).href));
await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const primary=element('#workspace-primary');
assert.equal(primary.disabled,false);
state.workspaceRuns=[{state:'running',request:{mode:'stage',stage:'draft'}}];
assert.doesNotThrow(()=>document.dispatchEvent(new CustomEvent('workspace-readiness')));
assert.equal(primary.disabled,true);state.workspaceRuns=[];document.dispatchEvent(new CustomEvent('workspace-readiness'));
hold=true;const first=primary.onclick();await new Promise(setImmediate);await primary.onclick();
assert.equal(saves,1);releaseSave();await first;assert.equal(runs,1);
state.dirty=true;const second=primary.onclick();await new Promise(setImmediate);state.mode='prose';releaseSave();await second;
assert.equal(runs,1,'typing or navigation while saving must prevent dispatch');assert.ok(errors.some(s=>s.includes('зміни')));
state.mode='review';state.dirty=false;state.reviewAvailability={ready:true,reason:'',hasChanges:true};document.dispatchEvent(new CustomEvent('workspace-review-state'));
assert.equal(primary.disabled,false,'ready review must allow primary acceptance');await primary.onclick();assert.equal(accepts,1);
state.mode='memory';document.dispatchEvent(new CustomEvent('editor-state-changed'));assert.equal(primary.disabled,true,'no memory cannot complete the scene');
state.mode='draft';state.bufferOrigin='history';document.dispatchEvent(new CustomEvent('editor-state-changed'));assert.equal(primary.disabled,true);
console.log('Workspace controller double-click, async-save, review, missing-memory guards passed');
