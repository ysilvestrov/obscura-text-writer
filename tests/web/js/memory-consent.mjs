import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const base=new URL('../../../src/storygen/web/static/',import.meta.url);
class Element{
  constructor(){this.children=[];this.dataset={};this.disabled=false;this.value='';this.checked=false;this.textContent='';}
  append(...items){this.children.push(...items)}
  setAttribute(){} addEventListener(){} replaceChildren(...items){this.children=items}
  closest(){return null} querySelectorAll(){return []}
}
const elements=new Map();
globalThis.document={querySelector:key=>{if(!elements.has(key))elements.set(key,new Element());return elements.get(key)},querySelectorAll:()=>[],createElement:()=>new Element(),addEventListener(){},dispatchEvent(){}};
globalThis.setInterval=()=>0;
globalThis.CustomEvent=class{constructor(type,options){this.type=type;this.detail=options?.detail}};
let accepted=false,prompt='',posts=[];
globalThis.confirm=text=>{prompt=text;return accepted};
const storage=new Map();globalThis.localStorage={getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
const token='a'.repeat(64);
const state={storyId:'s',scene:{id:'c',heads:{prose:'p'}},mode:'prose',bufferEpoch:1,dirty:false,saving:false,workspaceRuns:[]};
globalThis.fixture={state,refresh:async()=>{},loadBuffer(){},textEditor:{onInput(){}},notice(){},json:(method,body)=>({method,body}),api:async(url,options)=>{
  if(url.includes('/readiness'))return {operations:{memory:{ready:false,can_confirm:true,calls:1,roles:{memory:{provider:'local',model:'fake'}},memory_review:{fingerprint:token,memory_scene_number:8,changed_version_count:6,changed_text_count:0,risk:false}}}};
  if(url.endsWith('/runs')&&!options)return {runs:[]};
  if(url==='/api/runs'&&options){posts.push(options.body);return {id:'r',state:'queued'}};
  throw Error('Unexpected test request: '+url);
}};
let source=readFileSync(new URL('runs.js',base),'utf8')
 .replace("import {state,refresh,loadBuffer,textEditor} from './editor.js';","const {state,refresh,loadBuffer,textEditor}=globalThis.fixture;")
 .replace("import {api,json,notice} from './api.js';","const {api,json,notice}=globalThis.fixture;")
 .replace("import {acceptedContinuation} from './acceptance.js';","const acceptedContinuation=()=>null;")
 .replace('await follow(run);return active;','return run;');
source=source.replace(/from '(\.\/[^']+)'/g,(_,path)=>'from '+JSON.stringify(new URL(path,base).href));
await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const {invokeWorkspaceCommand}=await import(new URL('workspace-commands.js',base));
await invokeWorkspaceCommand('run',{mode:'stage',stage:'memory'});
assert.equal(posts.length,0,'Declining consent must not enqueue a run');
assert.match(prompt,/дослівно збігаються/);
accepted=true;
await invokeWorkspaceCommand('run',{mode:'stage',stage:'memory'});
assert.equal(posts.length,1);assert.equal(posts[0].request.memory_approval,token);
assert.equal(posts[0].request.stage,'memory');
console.log('Memory consent decline/confirm and request binding passed');
