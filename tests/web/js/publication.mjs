import {installDialogFixture} from './dialog-fixture.mjs';
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
for(const key of ['page','form','save','status','reload','cover-upload','cover-remove','author-choice','author-add','translator-choice','translator-add','authors','translators','cover','cover-empty','signatures','signature-create','cover-form','cover-palette','cover-generate','suggest','suggest-cancel','suggest-status','suggestions','suggestion-history','suggestion-selection'])nodes['#publication-'+key]=new Element();
nodes['#publication-page'].dataset.storyId='story';
nodes['#publication-cover-palette'].value='ink';
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
installDialogFixture(globalThis.document);
globalThis.FormData=class{append(){}};
let revision=0,hold=false,release,uploadFailure=false,initialRelease;
let proposals=[],suggestionBody=null,runCalls=0,lastSave,readinessSelection=null,historyItems=[],refuseRun=false;
let putCalls=0,generateCalls=0,generateBody=null,generateFailure=false,holdGenerate=false,releaseGenerate;
const initialReady=new Promise(resolve=>initialRelease=resolve);
let card={title:'',language:'uk',annotation:'',cycle_title:'',publication_date:'',publisher:'',isbn:'',rights:'',source_language:'',cycle_number:null,keywords:[],genres:[],author_ids:[],translator_ids:[],cover_id:null,story_id:'story',revision};
const person={id:'person',display_name:'Тінь <img>',revision:0};
function current(){return{card:{...card,revision},effective_title:'Книга',authors:[],translators:[],cover:null};}
globalThis.fetch=async(url,options={})=>{
  if(!options.method)await initialReady;
  let data,ok=true;
  if(url.includes('publication-signatures'))data={signatures:[person]};
  else if(url.endsWith('/suggestions/readiness'))data={ready:true,roles:{writer:{model:'fake-writer'}},selection:readinessSelection};
  else if(url.endsWith('/suggestions'))data={proposals,history:historyItems,active_runs:[]};
  else if(url==='/api/runs'){runCalls++;suggestionBody=JSON.parse(options.body);if(refuseRun){ok=false;data={detail:'Відбір сцен змінився; перегляньте його знову'};}else data={id:'run'};}
  else if(url.endsWith('/cover/generate')){
    generateCalls++;generateBody=JSON.parse(options.body);
    if(holdGenerate)await new Promise(resolve=>releaseGenerate=resolve);
    ok=!generateFailure;data=ok?{id:'generated'+generateCalls}:{detail:'cycle_number: має бути ≥ 1'};
  }
  else if(url.endsWith('/cover')){ok=!uploadFailure;data=ok?{id:'cover'}:{detail:'Невірна обкладинка'};}
  else if(options.method==='PUT'){
    const body=JSON.parse(options.body);
    lastSave=body;putCalls++;
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
const {setLocale}=await import(pathToFileURL(root+'/src/storygen/web/static/i18n.js'));
const emptyAuthor=nodes['#publication-author-choice'].children[0];
setLocale('en');assert.equal(emptyAuthor.textContent,'Choose a credit from the directory');
setLocale('uk');assert.equal(emptyAuthor.textContent,'Оберіть підпис із довідника');
assert.equal(nodes['#publication-save'].disabled,true,'Locale switch must not dirty the card');
// R16-COVER-S04: generating from a clean card alone makes it dirty, and Save sends the generated cover_id.
await nodes['#publication-cover-generate'].onclick();
assert.equal(nodes['#publication-save'].disabled,false,'Generating from a clean card makes the form dirty');
await form.onsubmit({preventDefault(){}});
assert.equal(lastSave.data.cover_id,'generated1');assert.equal(nodes['#publication-save'].disabled,true);
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
await nodes['#publication-reload'].onclick();assert.equal(fields.title.value,'Не втратити');
let warned=false;windowEvents.beforeunload({preventDefault(){warned=true;}});assert.equal(warned,true);
await nodes['#publication-cover-form'].onsubmit({preventDefault(){},currentTarget:nodes['#publication-cover-form']});
assert.equal(nodes['#publication-cover'].hidden,false);
uploadFailure=true;
await nodes['#publication-cover-form'].onsubmit({preventDefault(){},currentTarget:nodes['#publication-cover-form']});
assert.equal(nodes['#publication-cover'].src,'/api/stories/story/publication/covers/cover');
assert.equal(fields.title.value,'Не втратити');
// R16-COVER-S04: the text cover takes unsaved form values, never saves the card, and busy blocks a second request.
const putsBefore=putCalls;
fields.title.value='Незбережена назва';form.handlers.input({target:{name:'title'}});
nodes['#publication-cover-palette'].value='wine';
const callsBefore=generateCalls;
holdGenerate=true;
const firstGenerate=nodes['#publication-cover-generate'].onclick();await tick();
assert.equal(nodes['#publication-cover-generate'].disabled,true,'Generate is disabled while busy');
await nodes['#publication-cover-generate'].onclick();
releaseGenerate();await firstGenerate;holdGenerate=false;
assert.equal(generateCalls,callsBefore+1,'Busy blocks a second generate');
assert.deepEqual(Object.keys(generateBody).sort(),['author_ids','cycle_number','cycle_title','language','palette','title']);
assert.equal(generateBody.title,'Незбережена назва');assert.equal(generateBody.palette,'wine');
const generatedSrc=`/api/stories/story/publication/covers/generated${generateCalls}`;
assert.equal(nodes['#publication-cover'].src,generatedSrc);
assert.equal(putCalls,putsBefore,'Generating never saves the card');
generateFailure=true;notice.dataset.kind='';
await nodes['#publication-cover-generate'].onclick();
assert.equal(nodes['#publication-cover'].src,generatedSrc);
assert.equal(notice.dataset.kind,'error');assert.equal(fields.title.value,'Незбережена назва');
// R16-SUGGEST-S07: a book that does not fit whole shows which scenes are read, and the run carries the shown selection.
assert.equal(nodes['#publication-suggestion-selection'].hidden,true,'A whole book shows no selection line');
assert.equal(suggestionBody.request.expected_selection,undefined,'A whole book sends no selection key');
const key='a'.repeat(64);
readinessSelection={included:14,total:31,last_scene_id:'s14',last_scene_title:'Шторм',idea:true,bound_by:'chars',key};
historyItems=[{created_at:'t1',state:'failed',error:null,warnings:[],selection:readinessSelection}];
proposals=[{...proposals[0],attempt_id:'long',selection:readinessSelection}];
await nodes['#publication-suggest'].onclick();
const selectionLine=nodes['#publication-suggestion-selection'];
assert.equal(selectionLine.hidden,false);
assert.equal(selectionLine.textContent,'Книжка не вміщається у вікно моделі повністю: модель прочитає ідею твору й сцени 1–14 із 31 (до «Шторм»). Межа — ліміт символів письменника; його можна підняти в налаштуваннях моделей.');
assert.ok(nodes['#publication-suggestion-history'].children[0].textContent.includes('Відібрано: ідея й сцени 1–14 із 31'),'History says selected, not read');
assert.ok(nodes['#publication-suggestions'].children[0].children.some(node=>node.textContent==='Прочитано: ідея й сцени 1–14 із 31'));
await nodes['#publication-suggest'].onclick();
assert.equal(suggestionBody.request.expected_selection,key,'The run carries the key of the selection shown');
setLocale('en');
assert.equal(selectionLine.textContent,'The book does not fit the model window whole: the model will read the story idea and scenes 1–14 of 31 (up to “Шторм”). The limit is the writer\'s character limit; you can raise it in the model settings.');
assert.ok(nodes['#publication-suggestions'].children[0].children.some(node=>node.textContent==='Read: the idea and scenes 1–14 of 31'));
setLocale('uk');
readinessSelection={...readinessSelection,idea:false,bound_by:'tokens'};
historyItems=[];proposals=[];
await nodes['#publication-suggest'].onclick();
assert.equal(selectionLine.textContent,'Книжка не вміщається у вікно моделі повністю: модель прочитає сцени 1–14 із 31 (до «Шторм»), без ідеї твору.');
// A refused run (the selection changed meanwhile) re-reads readiness: the line and the next key follow the new selection.
refuseRun=true;readinessSelection={...readinessSelection,included:12,last_scene_title:'Туман',key:'c'.repeat(64)};
await nodes['#publication-suggest'].onclick();
assert.equal(suggestionBody.request.expected_selection,key,'The refused click still sent the key it showed');
assert.ok(selectionLine.textContent.includes('сцени 1–12 із 31 (до «Туман»)'),'The line shows the new selection after a refusal');
assert.equal(nodes['#publication-suggest-status'].textContent,'Відбір сцен змінився; перегляньте його знову');
refuseRun=false;
await nodes['#publication-suggest'].onclick();
assert.equal(suggestionBody.request.expected_selection,'c'.repeat(64),'The next click sends the key of the selection shown now');
console.log('publication dirty/async save/CAS/upload/text cover/long book selection passed');
