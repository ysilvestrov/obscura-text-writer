import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
class Element{
  constructor(tag){this.tagName=tag;this.children=[];this.dataset={};this.value='';this.textContent='';this.disabled=false;this.checked=false;this.hidden=false}
  append(...items){this.children.push(...items)}
  replaceChildren(...items){this.children=items}
  setAttribute(key,value){this[key]=value}
  set innerHTML(_){throw new Error('Untrusted editor content must never be HTML')}
}
globalThis.document={createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text})};
const {mountCopyeditReview}=await import(pathToFileURL(root+'/src/storygen/web/static/copyedits.js'));
const host=new Element('div'),state={scene:{id:'s'},dirty:false,saving:false,bufferEpoch:0};
let body,applied=0,refreshed=0;const messages=[];
const preview={attempt_id:'a',original:'<script>old</script>',edits:[{original:'old',replacement:'new',category:'grammar',context_before:'<script>',context_after:'</script>'}],
  preview:'<script>new</script>',proposal_fingerprint:'hash',expected_revision:7,decisions:[],can_apply:true,reason:null};
const api=async(url,options)=>{
  if(options?.method==='POST'){body=JSON.parse(options.body);return {version:{id:'v'},scene:{id:'s',revision:8}}}
  if(url.endsWith('/copyedits'))return {attempts:[{id:'a',created_at:'2026-10-21',state:'needs_review'}]};
  return preview;
};
const component=mountCopyeditReview({host,state,api,json:(method,value)=>({method,body:JSON.stringify(value)}),notice:(...m)=>messages.push(m),onApplied:async()=>{applied++}});
await component.reload();
const all=()=>{const result=[];function walk(e){result.push(e);for(const c of e.children||[])walk(c)}walk(host);return result};
const apply=()=>all().find(e=>e.tagName==='button'&&e.textContent==='Застосувати вибрані правки');
assert.equal(apply().disabled,false);
assert.ok(all().some(e=>e.textContent==='old'));
const sentenceRows=all().filter(e=>e.className==='copyedit-sentence');
assert.equal(sentenceRows.length,2);
assert.deepEqual(sentenceRows[0].children.map(e=>e.textContent),['Було: ','<script>','old','</script>']);
assert.deepEqual(sentenceRows[1].children.map(e=>e.textContent),['Стало: ','<script>','new','</script>']);
assert.equal(sentenceRows[0].children[2].tagName,'del');
assert.equal(sentenceRows[1].children[2].tagName,'ins');
all().find(e=>e.tagName==='input').checked=false;
await apply().onclick();
assert.deepEqual(body,{expected_revision:7,proposal_fingerprint:'hash',selected_indices:[]});
assert.equal(applied,1);
state.dirty=true;component.updateAvailability();assert.equal(apply().disabled,true);
await apply().onclick();assert.equal(applied,1,'Programmatic click may not bypass dirty guard');
state.dirty=false;state.characterDirty=true;component.updateAvailability();assert.equal(apply().disabled,true);
state.characterDirty=false;component.updateAvailability();
preview.can_apply=false;preview.reason='Джерела змінилися';await component.reload();
assert.equal(apply().disabled,true);
assert.ok(all().some(e=>e.textContent==='Джерела змінилися'));
state.scene=null;await component.reload();assert.equal(apply().disabled,true);

// Changing the proposal must disable publication immediately, before B arrives.
const secondHost=new Element('div'),secondState={scene:{id:'s'},dirty:false,saving:false,bufferEpoch:0};
let resolveB,postCount=0;
const pendingB=new Promise(resolve=>{resolveB=resolve});
const secondApi=async(url,options)=>{
  if(options){postCount++;return {version:{id:'v'},scene:{id:'s'}}}
  if(url.endsWith('/copyedits'))return {attempts:[{id:'b',created_at:'2026-10-20',state:'completed'},{id:'a',created_at:'2026-10-21',state:'completed'}]};
  if(url.endsWith('/b'))return pendingB;
  return {...preview,attempt_id:'a',can_apply:true};
};
const second=mountCopyeditReview({host:secondHost,state:secondState,api:secondApi,json:(method,value)=>({method,body:JSON.stringify(value)}),notice:()=>{},onApplied:async()=>{}});
await second.reload();
function descendants(node){return [node,...(node.children||[]).flatMap(descendants)]}
const secondSelect=descendants(secondHost).find(e=>e.tagName==='select');
const secondApply=descendants(secondHost).find(e=>e.tagName==='button'&&e.textContent==='Застосувати вибрані правки');
assert.equal(secondApply.disabled,false);
secondSelect.value='b';const loading=secondSelect.onchange();
assert.equal(secondApply.disabled,true,'Selection change must block old proposal publication before fetch resolves');
await secondApply.onclick();assert.equal(postCount,0);
resolveB({...preview,attempt_id:'b',can_apply:true,proposal_fingerprint:'hash-b'});
await loading;assert.equal(secondApply.disabled,false);

// Program-built diffs start with nothing selected; advice refresh cannot accept edits.
const diffHost=new Element('div');
const diffData={...preview,protocol_version:2,attempt_id:'d',can_apply:true,proposal_fingerprint:'diff',default_selected_indices:[],decisions:[],can_classify:true,classification_history:[],warnings:['full-warning']};
let selectedBody,delayPreview=false,resolvePreview;
const delayedPreview=new Promise(resolve=>{resolvePreview=resolve});
const diffApi=async(url,options)=>{
  if(url.includes('/new/')&&url.endsWith('/copyedits'))return {attempts:[]};
  if(url.endsWith('/selection-preview')){selectedBody=JSON.parse(options.body);return delayPreview?delayedPreview:{text:'assembled',warnings:['selected-warning']}}
  if(url.endsWith('/copyedits'))return {attempts:[{id:'d',created_at:'2026-10-21',state:'needs_review'}]};
  return diffData;
};
const diffState={scene:{id:'s'},dirty:false,saving:false};
const diffPanel=mountCopyeditReview({host:diffHost,state:diffState,api:diffApi,json:(method,value)=>({method,body:JSON.stringify(value)}),notice:()=>{},onApplied:async()=>{}});
await diffPanel.reload();
const diffNodes=()=>descendants(diffHost);
const diffCheck=()=>diffNodes().find(e=>e.tagName==='input');
const diffApply=()=>diffNodes().find(e=>e.tagName==='button'&&e.textContent==='Застосувати вибрані правки');
assert.equal(diffCheck().checked,false);
diffCheck().checked=true;diffCheck().onchange();assert.equal(diffApply().disabled,true);
await diffNodes().find(e=>e.tagName==='button'&&e.textContent==='Переглянути вибраний текст').onclick();
assert.deepEqual(selectedBody.selected_indices,[0]);assert.equal(diffApply().disabled,false);
diffData.classification={changes:[{index:0,category:'meaning',assessment:'uncertain',explanation:'<script>advice</script>'}]};
await diffPanel.reload();assert.equal(diffCheck().checked,true);
assert.ok(diffNodes().some(e=>e.textContent.includes('<script>advice</script>')));
assert.ok(diffNodes().some(e=>e.textContent==='selected-warning'));
delayPreview=true;
const late=diffNodes().find(e=>e.tagName==='button'&&e.textContent==='Переглянути вибраний текст').onclick();
diffState.scene={id:'new'};await diffPanel.reload();
resolvePreview({text:'STALE TEXT FROM PREVIOUS SCENE',warnings:[]});await late;
assert.ok(!diffNodes().some(e=>e.textContent.includes('STALE TEXT FROM PREVIOUS SCENE')));
assert.ok(!diffNodes().some(e=>e.tagName==='pre'&&e.textContent==='assembled'));
assert.equal(diffApply().disabled,true);

// Empty model proposals are distinct from the author's empty subset selection.
for(const protocol_version of [1,2]){
  const emptyHost=new Element('div');let emptyPosts=0;
  const emptyApi=async(url,options)=>{
    if(options){emptyPosts++;throw new Error('Must not publish empty model response')}
    if(url.endsWith('/copyedits'))return {attempts:[{id:'empty',created_at:'2026-10-21',state:'needs_review'}]};
    return {...preview,attempt_id:'empty',protocol_version,edits:[],has_changes:false,can_apply:false,reason:'Редактор не запропонував змін',decisions:[]};
  };
  const emptyPanel=mountCopyeditReview({host:emptyHost,state:{scene:{id:'s'}},api:emptyApi,json:()=>({}),notice:()=>{},onApplied:async()=>{}});
  await emptyPanel.reload();
  const nodes=descendants(emptyHost),accept=nodes.find(e=>e.textContent==='Застосувати вибрані правки');
  assert.equal(accept.hidden,true);assert.equal(accept.disabled,true);
  assert.ok(nodes.some(e=>e.textContent==='Прийняття недоступне; поточний текст не змінено.'));
  await accept.onclick();assert.equal(emptyPosts,0);
}

// One sentence may contain distant dependent changes: one checkbox, raw indices preserved.
const groupedHost=new Element('div'),groupedState={scene:{id:'s'},dirty:false};
let groupedBody,groupedApplied=0;
const groupedPreview={...preview,protocol_version:2,can_apply:true,reason:null,decisions:[],default_selected_indices:[],
  original:'Вона йшов до дома.',preview:'Вона йшла додому.',
  edits:[{original:'йшов',replacement:'йшла',category:'grammar'},{original:'до дома',replacement:'додому',category:'wording'}],
  groups:[{indices:[0,1],category:'mixed',before_parts:[{text:'Вона ',changed:false},{text:'йшов',changed:true},{text:' ',changed:false},{text:'до дома',changed:true},{text:'.',changed:false}],after_parts:[{text:'Вона ',changed:false},{text:'йшла',changed:true},{text:' ',changed:false},{text:'додому',changed:true},{text:'.',changed:false}]}]};
const groupedApi=async(url,options)=>{
  if(options){groupedBody=JSON.parse(options.body);return url.endsWith('/selection-preview')?{text:groupedPreview.preview,warnings:[]}:{version:{id:'v'},scene:{id:'s'}}}
  if(url.endsWith('/copyedits'))return {attempts:[{id:'a',created_at:'2026-10-22',state:'needs_review'}]};
  return groupedPreview;
};
const groupedPanel=mountCopyeditReview({host:groupedHost,state:groupedState,api:groupedApi,json:(method,value)=>({method,body:JSON.stringify(value)}),notice:()=>{},onApplied:async()=>{groupedApplied++}});
await groupedPanel.reload();
let groupNodes=descendants(groupedHost),groupInputs=groupNodes.filter(e=>e.tagName==='input');
assert.equal(groupInputs.length,1);
const groupedLines=groupNodes.filter(e=>e.className==='copyedit-sentence');
assert.equal(groupedLines[0].children.filter(e=>e.tagName==='del').length,2);
assert.equal(groupedLines[1].children.filter(e=>e.tagName==='ins').length,2);
assert.ok(groupedLines[0].children.some(e=>e.tagName==='span'&&e.textContent==='Вона '));
groupInputs[0].checked=true;groupInputs[0].onchange();
await groupNodes.find(e=>e.textContent==='Переглянути вибраний текст').onclick();
assert.deepEqual(groupedBody.selected_indices,[0,1]);
await groupNodes.find(e=>e.textContent==='Застосувати вибрані правки').onclick();
assert.deepEqual(groupedBody.selected_indices,[0,1]);assert.equal(groupedApplied,1);

// Historical partial acceptance stays visible but cannot be silently expanded or republished.
groupedPreview.decisions=[{selected_indices:[0]}];
const historicalHost=new Element('div'),historicalPanel=mountCopyeditReview({host:historicalHost,state:groupedState,api:groupedApi,json:(method,value)=>({method,body:JSON.stringify(value)}),notice:()=>{},onApplied:async()=>{}});
await historicalPanel.reload();
groupNodes=descendants(historicalHost);groupInputs=groupNodes.filter(e=>e.tagName==='input');
assert.equal(groupInputs[0].indeterminate,true);
assert.equal(groupNodes.find(e=>e.textContent==='Застосувати вибрані правки').disabled,true);
await historicalPanel.reload();
assert.equal(descendants(historicalHost).find(e=>e.tagName==='input').indeterminate,true);
