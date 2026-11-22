// MEMORY-LOCATIONS-S07: the «Locations» section of the story side panel. Cards come from «Локація:» lines of scene plans;
// the author merges look-alikes, splits them back, hides a suggestion and writes a description for the planner and the
// writer. Every change is CAS on the story revision; a refused save keeps the typed description.
import {t,msg,uiText,uiAttr,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state} from './editor.js';
import {confirmDialog} from './dialogs.js';
import {locationRows,mergeTargets,suggestionRows} from './locations.js';
import {announceRevision,followRevision} from './story-revision.js';

let data=null,storyId=null,choosing=null,busy=false;
const drafts=new Map();  // card id -> typed description not saved yet

const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};
function button(render,onclick,primary=false){const b=node('button',render,primary?'':'secondary');b.type='button';b.disabled=busy;b.onclick=onclick;return b}
const box=()=>document.querySelector('#story-locations');

function description(row){
  const wrap=node('details',null,'location-description');
  if(drafts.has(row.id))wrap.open=true;
  wrap.append(node('summary',()=>t('locations.description')+(row.description&&!drafts.has(row.id)?': '+row.description:'')));
  const area=document.createElement('textarea');area.rows=3;area.maxLength=2000;area.value=drafts.get(row.id)??row.description;
  uiAttr(area,'aria-label',()=>t('locations.description')+' — '+row.path);
  const counter=node('p',()=>t('locations.counter',{p0:area.value.length}),'hint');
  area.oninput=()=>{if(area.value===row.description)drafts.delete(row.id);else drafts.set(row.id,area.value);counter.textContent=t('locations.counter',{p0:area.value.length})};
  const actions=node('div',null,'actions');actions.append(button(()=>t('locations.save'),()=>save(row,area.value),true));
  wrap.append(area,counter,actions);
  return wrap;
}

function chooser(row){
  const wrap=node('div',null,'actions location-merge');
  const select=document.createElement('select');uiAttr(select,'aria-label',()=>t('locations.merge_target',{p0:row.path}));
  for(const target of mergeTargets(data,row.id)){const o=node('option',()=>target.path);o.value=target.id;select.append(o)}
  wrap.append(select,button(()=>t('locations.merge_do'),()=>merge(row.id,row.path,select.value,select.selectedOptions?.[0]?.textContent),true),
    button(()=>t('locations.cancel'),()=>{choosing=null;draw()}));
  return wrap;
}

function draw(){
  const section=box();if(!section)return;
  section.replaceChildren(node('p',()=>t('locations.hint'),'hint'));
  const rows=locationRows(data);
  if(!rows.length){section.append(node('p',()=>t('locations.empty')));return}
  const hints=suggestionRows(data);
  if(hints.length){
    const list=node('div',null,'location-suggestions');list.append(node('h4',()=>t('locations.suggestions')));
    for(const hint of hints){
      const item=node('div',null,'location-suggestion');item.dataset.a=hint.a;item.dataset.b=hint.b;
      item.append(node('p',()=>t('locations.suggestion',{p0:hint.bPath,p1:hint.aPath})));
      const actions=node('div',null,'actions');
      // The later card goes into the one that appeared first.
      actions.append(button(()=>t('locations.merge_do'),()=>merge(hint.b,hint.bPath,hint.a,hint.aPath),true),
        button(()=>t('locations.dismiss'),()=>change(`/dismiss`,'POST',{a:hint.a,b:hint.b},'locations.dismissed')));
      item.append(actions);list.append(item);
    }
    section.append(list);
  }
  for(const row of rows){
    const item=node('div',null,'location-row');item.dataset.id=row.id;item.style.marginInlineStart=`${row.depth}rem`;
    const head=node('p');head.append(node('strong',()=>row.path));
    if(row.merged)head.append(document.createTextNode(' '),node('span',()=>t('locations.merged',{p0:row.targetPath}),'hint'));
    item.append(head,node('p',()=>row.scenes?t('locations.scenes',{p0:row.scenes}):t('locations.no_scenes'),'hint'));
    if(row.editable)item.append(description(row));
    if(choosing===row.id)item.append(chooser(row));
    else{
      const actions=node('div',null,'actions');
      if(row.canMerge&&mergeTargets(data,row.id).length)actions.append(button(()=>t('locations.merge'),()=>{choosing=row.id;draw()}));
      if(row.canSplit)actions.append(button(()=>t('locations.split'),()=>change(`/${row.id}/split`,'POST',{},'locations.split_notice')));
      if(actions.children.length)item.append(actions);
    }
    section.append(item);
  }
}

async function load(){
  if(!state.storyId||!box())return;
  if(storyId!==state.storyId){drafts.clear();choosing=null;storyId=state.storyId}
  try{data=await api(`/api/stories/${state.storyId}/locations`)}catch(e){data=null}
  draw();
}

async function change(path,method,body,done){
  if(busy||!data)return false;
  const before=data.story_revision;busy=true;draw();
  try{
    data=await api(`/api/stories/${state.storyId}/locations${path}`,json(method,{...body,expected_revision:before}));
    announceRevision(state.storyId,data.story_revision);
    notice(msg(done));return true;
  }catch(e){notice(diagnostic(e.message),'error');await load();return false}  // drafts survive the reload
  finally{busy=false;draw()}
}

async function merge(id,path,into,intoPath){
  if(!into||!await confirmDialog(t('locations.merge_confirm',{p0:path,p1:intoPath||''}),{accept:t('locations.merge_do')}))return;
  choosing=null;
  await change(`/${id}/merge`,'POST',{into},'locations.merged_notice');
}

async function save(row,text){
  if(await change(`/${row.id}`,'PUT',{description:text},'locations.saved'))drafts.delete(row.id);
  draw();
}

followRevision(()=>data&&storyId===state.storyId?{storyId,get:()=>data.story_revision,set:value=>{data.story_revision=value}}:null);
document.addEventListener('scene-selected',load);
document.addEventListener('story-refreshed',load);
