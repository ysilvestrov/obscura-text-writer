import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
import {setImmediate as tick} from 'node:timers/promises';
const root=process.argv[2];
class Element{
  constructor(tag=''){this.tag=tag;this.children=[];this.value='';this.dataset={};this.handlers={};this.files=[];this.disabled=false;this.className='';this.selected=false;}
  append(...items){this.children.push(...items);}
  add(item){this.append(item);}
  replaceChildren(...items){this.children=items;this.value='';}
  setAttribute(key,value){this[key]=value;}
  removeAttribute(key){delete this[key];}
  addEventListener(key,handler){this.handlers[key]=handler;}
  get options(){return this.children;}
  get selectedOptions(){return this.children.filter(item=>item.selected);}
  querySelectorAll(selector){let nodes=this.children.flatMap(child=>[child,...child.querySelectorAll(selector)]);return nodes.filter(node=>selector==='input[data-id]'?node.tag==='input'&&node.dataset.id:selector==='button'?node.tag==='button':false);}
  querySelector(selector){return this.querySelectorAll(selector)[0];}
  set innerHTML(value){throw Error('Untrusted publication data must not use innerHTML');}
}
const nodes={};
for(const key of ['page','form','save','status','reload','cover-upload','cover-remove','author-choice','author-add','translator-choice','translator-add','authors','translators','cover','cover-empty','signatures','signature-create','cover-form','suggest','suggest-cancel','suggest-status','suggestions','suggestion-history'])nodes['#publication-'+key]=new Element();
nodes['#publication-page'].dataset.storyId='story';
const form=nodes['#publication-form'];
const fields={};
for(const key of ['title','language','annotation','cycle_title','publication_date','publisher','isbn','rights','source_language','cycle_number','keywords','genres'])fields[key]=new Element();
form.elements=Object.assign(Object.values(fields),{namedItem:key=>fields[key]});
nodes['#publication-signature-create'].elements={namedItem:()=>new Element()};
nodes['#publication-cover-form'].elements={namedItem:()=>({files:[{size:100}]})};
const notice=new Element();const windowEvents={};
globalThis.document={querySelector:key=>key==='#notice'?notice:nodes[key]||null,querySelectorAll:selector=>selector==='.signature-row input'?nodes['#publication-signatures'].querySelectorAll('input[data-id]'):[],createElement:tag=>new Element(tag)};
globalThis.window={addEventListener:(key,handler)=>windowEvents[key]=handler};
globalThis.Option=class extends Element{constructor(label,value){super('option');this.textContent=label;this.value=value;}};
globalThis.setTimeout=()=>0;globalThis.clearTimeout=()=>{};
globalThis.confirm=()=>false;
globalThis.FormData=class{append(){}};
let revision=0,hold=false,release,uploadFailure=false,initialRelease;
let proposals=[],suggestionBody=null,runCalls=0,lastSave;
const initialReady=new Promise(resolve=>initialRelease=resolve);
let card={title:'',language:'uk',annotation:'',cycle_title:'',publication_date:'',publisher:'',isbn:'',rights:'',source_language:'',cycle_number:null,keywords:[],genres:[],author_ids:[],translator_ids:[],cover_id:null,story_id:'story',revision};
const person={id:'person',display_name:'Тінь <img>',revision:0};
function current(){return{card:{...card,revision},effective_title:'Книга',authors:[],translators:[],cover:null};}
globalThis.fetch=async(url,options={})=>{
  if(!options.method)await initialReady;
  let data,ok=true;
  if(url.includes('publication-signatures'))data={signatures:[person]};
  else if(url.endsWith('/suggestions/readiness'))data={ready:true,roles:{planner:{model:'fake-planner'}}};
  else if(url.endsWith('/suggestions'))data={proposals,history:[],active_runs:[]};
  else if(url==='/api/runs'){runCalls++;suggestionBody=JSON.parse(options.body);data={id:'run'};}
  else if(url.endsWith('/cover')){ok=!uploadFailure;data=ok?{id:'cover'}:{detail:'Невірна обкладинка'};}
  else if(options.method==='PUT'){
    const body=JSON.parse(options.body);
    lastSave=body;
    if(hold)await new Promise(resolve=>release=resolve);
    if(body.expected_revision!==revision){ok=false;data={detail:'Конфлікт картки'};}
    else{card={...card,...body.data};revision++;data=current();}
  }else data=current();
  return {ok,json:async()=>data};
};
await import(pathToFileURL(root+'/src/storygen/web/static/publication.js'));
assert.equal(fields.title.disabled,true,'Fields are protected until initial data is loaded');
initialRelease();
await tick();
await tick();
assert.equal(nodes['#publication-save'].disabled,true);
// Generation never fills the form. Review preserves a field edited during the request.
fields.genres.append(new Option('Оповідання','short_story'));
proposals=[{attempt_id:'attempt',fingerprint:'hash',model:'fake-planner',created_at:'now',can_apply:true,warnings:['Порожнє поле genres <img>: оберіть вручну.'],
  available_fields:['annotation','genres','keywords'],suggestions:{annotation:'Запропоновано',genres:['short_story'],keywords:['літо']}}];
fields.keywords.value='Ручний тег';form.handlers.input({target:{name:'keywords'}});
await nodes['#publication-suggest'].onclick();
assert.equal(runCalls,1);assert.equal(suggestionBody.request.mode,'publication_suggest');
assert.equal(fields.annotation.value,'');
assert.ok(nodes['#publication-suggestions'].children[0].children.some(node=>node.textContent==='Порожнє поле genres <img>: оберіть вручну.'));
const apply=nodes['#publication-suggestions'].children[0].children.find(node=>node.tag==='button');
hold=true;const initialSaving=form.onsubmit({preventDefault(){}});await tick();
apply.onclick();assert.equal(fields.annotation.value,'','A delayed Save blocks proposal application and preserves provenance');
release();await initialSaving;hold=false;
apply.onclick();assert.equal(fields.annotation.value,'Запропоновано');assert.equal(fields.keywords.value,'Ручний тег');
proposals=[{...proposals[0],attempt_id:'different',suggestions:{keywords:['новий тег']},available_fields:['keywords']}];
await nodes['#publication-suggest'].onclick();
nodes['#publication-suggestions'].children[0].children.find(node=>node.tag==='button').onclick();
assert.equal(fields.keywords.value,'Ручний тег');assert.equal(notice.dataset.kind,'error');
await form.onsubmit({preventDefault(){}});
assert.deepEqual(lastSave.suggestion.fields,['annotation','genres']);
assert.equal(card.annotation,'Запропоновано');
fields.title.value='Перша назва';form.handlers.input();
hold=true;const saving=form.onsubmit({preventDefault(){}});await tick();
nodes['#publication-suggestions'].children[0].children.find(node=>node.tag==='button').onclick();
assert.equal(fields.keywords.value,'Ручний тег','An in-flight Save must block applying another proposal');
fields.annotation.value='Нова правка під час збереження';form.handlers.input();release();await saving;hold=false;
assert.equal(fields.annotation.value,'Нова правка під час збереження');
assert.equal(nodes['#publication-save'].disabled,false);
await form.onsubmit({preventDefault(){}});
assert.equal(card.annotation,'Нова правка під час збереження');
assert.equal(nodes['#publication-save'].disabled,true);
fields.title.value='Не втратити';form.handlers.input();revision++;
await form.onsubmit({preventDefault(){}});
assert.equal(fields.title.value,'Не втратити');assert.equal(notice.dataset.kind,'error');
nodes['#publication-reload'].onclick();assert.equal(fields.title.value,'Не втратити');
let warned=false;windowEvents.beforeunload({preventDefault(){warned=true;}});assert.equal(warned,true);
await nodes['#publication-cover-form'].onsubmit({preventDefault(){},currentTarget:nodes['#publication-cover-form']});
assert.equal(nodes['#publication-cover'].hidden,false);
uploadFailure=true;
await nodes['#publication-cover-form'].onsubmit({preventDefault(){},currentTarget:nodes['#publication-cover-form']});
assert.equal(nodes['#publication-cover'].src,'/api/stories/story/publication/covers/cover');
assert.equal(fields.title.value,'Не втратити');
console.log('publication dirty/async save/CAS/upload passed');
