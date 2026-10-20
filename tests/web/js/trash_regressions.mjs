import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const elements=new Map(),listeners=new Map();
class Element {dataset={};addEventListener(){}setAttribute(name,value){this[name]=value}children=[];textContent='';disabled=false;hidden=false;append(...items){this.children.push(...items)}replaceChildren(){this.children=[]}}
const element=id=>{if(!elements.has(id))elements.set(id,new Element());return elements.get(id)};
globalThis.document={querySelector:element,createElement:()=>new Element(),dispatchEvent:()=>{},addEventListener:(name,fn)=>listeners.set(name,fn)};
globalThis.confirm=()=>true;globalThis.CustomEvent=class{constructor(type){this.type=type}};
let calls=0,cleared=0,refreshed=0;
globalThis.fetch=async(url,options={})=>{if(options.method){assert.equal(state.saving,true,'trash blocks competing buffer operations');assert.equal(element('#editor').readOnly,true,'typing is blocked while trash is pending');calls++;return {ok:true,json:async()=>({})}}return {ok:true,json:async()=>({scenes:[]})}};
const {installSceneTrash}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/trash.js'));
const state={storyId:'s',scene:{id:'c',revision:3},dirty:true,saving:false};
installSceneTrash(state,async()=>{refreshed++},()=>{cleared++});
const button=element('.editor-toolbar').children[0];
await button.onclick();assert.equal(calls,0,'unsaved text blocks trash');
state.dirty=false;state.saving=true;await button.onclick();assert.equal(calls,0,'saving blocks trash');
state.saving=false;await button.onclick();assert.equal(calls,1);assert.equal(cleared,1);assert.equal(refreshed,1);
console.log('trash buffer guards passed');process.exit(0);
