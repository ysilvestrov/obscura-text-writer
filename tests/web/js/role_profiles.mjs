import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {setImmediate as tick} from 'node:timers/promises';
const root=process.argv[2];
class Element {
  constructor(){this.children=[];this.value='';this.checked=false;this.disabled=false;this.dataset={};this.files=[];this.elements={}}
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=items}
  setAttribute(){}
  contains(){return false}
  set innerHTML(value){throw new Error('Untrusted profile data may not use innerHTML')}
}
const selectors={};
for(const id of ['role-profile-select','role-profile-preview','role-profile-apply','role-profile-export','role-profile-summary'])selectors['#'+id]=new Element();
const form=new Element(),save=new Element(),file=new Element(),panel=new Element(),notice=new Element();
form.querySelector=()=>save;
for(const key of ['name','include_evaluator','new_version'])form.elements[key]=new Element();
selectors.form=form;selectors['input[type=file]']=file;panel.querySelector=key=>selectors[key];
const handlers={};
globalThis.document={querySelector:key=>key==='#role-profiles'?panel:key==='[data-story-id]'?{dataset:{storyId:'target'}}:key==='#notice'?notice:null,
  createElement:()=>new Element(),addEventListener:(key,fn)=>handlers[key]=fn};
globalThis.setTimeout=()=>0;globalThis.clearTimeout=()=>{};
let revision=4,applied=0,reloaded=0,confirmed=false,lastBody=null;
const confirmations=[];
globalThis.confirm=message=>{confirmations.push(message);return confirmed};
globalThis.location={reload:()=>reloaded++};
globalThis.fetch=async(url,options={})=>{
  const body=options.body?JSON.parse(options.body):null;lastBody=body;
  let data;
  if(url==='/api/role-profiles')data={profiles:[{id:'p',version:1,name:'Тест <img>',has_evaluator:false}]};
  else if(url.endsWith('/settings'))data={story:{revision}};
  else if(url.endsWith('/preview'))data={id:'p',version:1,name:'Тест <img>',expected_revision:revision,
    roles:{writer:{provider:{provider:'local',model:'model <img>'},context_tokens:8192,max_output_tokens:2048}},
    prompts:{writer:{prompt:{text:null}}},evaluator:null,warnings:[]};
  else if(url.endsWith('/apply')){
    if(body.expected_revision!==revision)return {ok:false,json:async()=>({detail:'Конфлікт ревізії'})};
    applied++;revision++;data={revision};
  } else throw new Error('Unexpected request '+url);
  return {ok:true,json:async()=>data};
};
await import(pathToFileURL(root+'/src/storygen/web/static/role-profiles.js'));
await tick();
const select=selectors['#role-profile-select'],preview=selectors['#role-profile-preview'],apply=selectors['#role-profile-apply'];
assert.equal(apply.disabled,true);
await apply.onclick();assert.equal(applied,0,'Programmatic apply cannot skip preview');
select.value='p:1';select.onchange();assert.equal(preview.disabled,false);assert.equal(apply.disabled,true);
await preview.onclick();assert.equal(apply.disabled,false);
assert.equal(select.children[1].textContent,'Тест <img> · версія 1');
handlers.input({target:{closest:()=>form}});assert.equal(apply.disabled,true);assert.deepEqual(selectors['#role-profile-summary'].children,[]);
await preview.onclick();confirmed=false;await apply.onclick();assert.equal(applied,0);assert.equal(reloaded,0);
assert.match(confirmations.at(-1),/незбережені зміни/i);
confirmed=true;revision=5;await apply.onclick();assert.equal(applied,0);assert.equal(reloaded,0);assert.equal(notice.dataset.kind,'error');
await preview.onclick();await apply.onclick();assert.equal(applied,1);assert.equal(reloaded,1);assert.equal(lastBody.expected_revision,5);
select.value='';select.onchange();assert.equal(apply.disabled,true);assert.equal(preview.disabled,true);
console.log('R-11 UI: preview, dirty reset, cancel, CAS error, apply/reload, safe text passed');
