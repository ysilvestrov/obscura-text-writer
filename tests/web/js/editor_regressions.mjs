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
const initial={id:'c',story_id:'s',position:0,revision:0,title:'Сцена',beats:'План A',target_words:400,character_ids:[],heads:{prose:'a'},needs_review:false};
let server=structuredClone(initial),release,calls=0,lastRequest;
const response=data=>({ok:true,json:async()=>structuredClone(data)});
globalThis.fetch=async(url,options={})=>{
  if(options.method==='PATCH'||options.method==='POST'){
    calls++;const body=JSON.parse(options.body);lastRequest={url,body};return new Promise(resolve=>{release=()=>{server={...server,revision:1,beats:body.beats??server.beats,heads:{prose:'b',...(url.endsWith('/draft')?{draft:'d'}:{})}};resolve(response(url.endsWith('/prose')||url.endsWith('/draft')?{scene:server,version:{id:'b'}}:server))}});
  }
  if(url.startsWith('/api/versions/'))return response({text:mode.startsWith('draft-')?'Нова чернетка':'Нова пам’ять',version:{id:'m-new',kind:'memory'}});
  if(url.includes('/versions'))return response({scene:server,versions:[]});
  return response({story:{id:'s',revision:1},scenes:[server],sources:[]});
};
const module=await import(pathToFileURL(root+'/src/storygen/web/static/editor.js'));
await new Promise(setImmediate);
if(mode==='prose'||mode.startsWith('draft')||mode.startsWith('memory'))await import(pathToFileURL(root+'/src/storygen/web/static/versions.js'));
const {state,refresh}=module,editor=element('#editor'),save=element('#save-text');
state.scene=structuredClone(initial);state.mode=mode==='refresh'?'prose':mode;state.dirty=false;editor.value='Текст A';
if(mode==='titles'){
  const title='### **Локація**: __Фотостудія__';
  server={...server,title,beats:'### **Авторський текст**: __без змін__'};
  await module.selectScene(server);
  await refresh();
  assert.equal(element('#scene-title').textContent,'Локація: Фотостудія');
  assert.equal(element('#scene-list').children[0].textContent,'1. Локація: Фотостудія');
  assert.equal(editor.value,server.beats,'display formatting must not alter author text');
  assert.equal(server.title,title,'stored title must remain verbatim');
  assert.equal(module.displaySceneTitle('C# та snake_case, _текст_'),'C# та snake_case, _текст_');
  assert.equal(module.displaySceneTitle('Звичайна назва'),'Звичайна назва');
}else if(mode.startsWith('memory')||mode.startsWith('draft-')){
  const kind=mode.startsWith('memory')?'memory':'draft',before=kind==='memory'?'Стара пам’ять':'Стара чернетка',after=kind==='memory'?'Нова пам’ять':'Нова чернетка';
  state.mode=kind;state.scene.heads[kind]='m-old';state.bufferOrigin=mode.endsWith('-history')?'history':'current';editor.value=before;state.dirty=mode.endsWith('-dirty');server={...server,revision:1,heads:{prose:'a',[kind]:'m-new'}};
  await refresh();await Promise.all(pendingEvents);
  assert.equal(editor.value,mode.endsWith('-clean')?after:before);
  assert.equal(state.scene.revision,mode.endsWith('-clean')?1:0);
}else if(mode==='refresh'){
  server={...server,revision:1,heads:{prose:'b'}};
  await refresh();
  assert.equal(editor.value,'Текст A');
  assert.equal(state.scene.revision,0,'a displayed old buffer must retain its original CAS revision');
}else{
  if(mode==='draft'){
    document.dispatchEvent(new CustomEvent('scene-selected'));await Promise.all(pendingEvents);
    await element('#mode-tabs').children.find(tab=>tab.textContent==='Чернетка').onclick();
    assert.equal(editor.value,'','an absent draft opens an empty buffer for manual text');
    assert.equal(save.disabled,false,'manual draft text must be saveable');
  }
  editor.value='Надісланий текст';editor.trigger('input');
  const saving=save.onclick();await Promise.resolve();
  if(mode==='draft'){
    assert.equal(lastRequest?.url,'/api/scenes/c/draft');
    assert.deepEqual(lastRequest.body,{text:'Надісланий текст',expected_revision:0});
  }
  editor.value='Правка під час очікування';editor.trigger('input');
  release();await saving;await Promise.all(pendingEvents);
  assert.equal(editor.value,'Правка під час очікування');
  assert.equal(state.dirty,true,'typing during a save must remain unsaved');
  if(mode==='draft'){
    assert.equal(state.scene.heads.draft,'d');
    assert.equal(save.disabled,false,'save must stay available after a draft save');
  }
}
console.log('buffer regression passed: '+mode);
process.exit(0);
