// MEMORY-LOCATIONS-S07, S12: the «Locations» page of a story (/stories/{id}/locations, like the characters page; the
// scene's memory tab only links here). Cards come from «Локація:» lines of scene plans;
// the author merges look-alikes, splits them back, hides a suggestion, writes a description for the planner and the
// writer, removes a place a model gave a scene (R-51) and glues a name the parse cut into one (MEMORY-LOCATIONS-S11). Every change is CAS on the story revision; a refused save
// keeps the typed description.
import {t,msg,uiText,uiAttr,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {confirmDialog} from './dialogs.js';
import {offerInvalidation} from './link-invalidation.js';
import {returnLink} from './workspace-links.js';
import {glueOptions,glueRows,hasDrafts,locationRows,mergeTargets,suggestionRows} from './locations.js';

const page=document.querySelector('#locations-page');
const storyId=page?.dataset.storyId||null;
let data=null,choosing=null,gluing=null,busy=false;
const drafts=new Map();  // card id -> typed description not saved yet

const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};
function button(render,onclick,primary=false){const b=node('button',render,primary?'':'secondary');b.type='button';b.disabled=busy;b.onclick=onclick;return b}
function box(){
  return page?.querySelector('#story-locations')||null;
}

function description(row){
  const wrap=node('details',null,'location-description');
  if(drafts.has(row.id))wrap.open=true;
  const summary=node('summary',()=>t('locations.description'));
  if(row.description)summary.append(node('span',()=>': '+row.description,'location-preview'));  // hidden while open
  wrap.append(summary);
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

function glueChooser(row){
  const wrap=node('div',null,'actions location-glue');
  const select=document.createElement('select');uiAttr(select,'aria-label',()=>t('locations.glue_target',{p0:row.path}));
  const options=glueOptions(data,row.id);
  for(const option of options){const o=node('option',()=>option.phrase);o.value=option.key;select.append(o)}
  wrap.append(select,button(()=>t('locations.glue_do'),()=>glue(options.find(o=>o.key===select.value)),true),
    button(()=>t('locations.cancel'),()=>{gluing=null;draw()}));
  return wrap;
}

function glues(){
  const list=node('div',null,'location-glues');list.append(node('h2',()=>t('locations.glues')));
  for(const item of glueRows(data)){
    const entry=node('div',null,'location-glued');entry.dataset.key=item.key;
    const actions=node('div',null,'actions');actions.append(button(()=>t('locations.unglue'),()=>unglue(item)));
    entry.append(node('p',()=>item.phrase),actions);list.append(entry);
  }
  return list;
}

function draw(){
  const section=box();if(!section)return;
  section.replaceChildren(node('p',()=>t('locations.hint'),'hint'));
  if(!data)return;
  const rows=locationRows(data);
  if(!rows.length){
    const empty=node('p',()=>t('locations.page_empty'),'locations-empty');
    const link=node('a',()=>t('characters.nav'));link.href=`/stories/${encodeURIComponent(storyId)}/characters`;
    section.append(empty,node('p',null,'locations-empty-link'));section.lastChild.append(link);return;
  }
  const hints=suggestionRows(data);
  if(hints.length){
    const list=node('div',null,'location-suggestions');list.append(node('h2',()=>t('locations.suggestions')));
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
    if(row.modelScenes.length){
      const places=node('div',null,'actions location-model-scenes');
      for(const scene of row.modelScenes)places.append(button(()=>t('locations.remove_from_scene',{p0:scene.label}),()=>removeFromScene(row,scene)));
      item.append(places);
    }
    if(row.editable)item.append(description(row));
    if(choosing===row.id)item.append(chooser(row));
    else if(gluing===row.id)item.append(glueChooser(row));
    else{
      const actions=node('div',null,'actions');
      if(row.canMerge&&mergeTargets(data,row.id).length)actions.append(button(()=>t('locations.merge'),()=>{choosing=row.id;draw()}));
      if(!row.merged&&glueOptions(data,row.id).length)actions.append(button(()=>t('locations.glue'),()=>{gluing=row.id;draw()}));
      if(row.canSplit)actions.append(button(()=>t('locations.split'),()=>change(`/${row.id}/split`,'POST',{},'locations.split_notice',{ids:[row.id],names:[row.path]})));
      if(actions.children.length)item.append(actions);
    }
    section.append(item);
  }
  if(glueRows(data).length)section.append(glues());
}

async function load(){
  if(!storyId)return;
  try{data=await api(`/api/stories/${storyId}/locations`)}catch(e){data=null;notice(diagnostic(e.message),'error')}
  draw();
}

// subject {ids, names} (or a function of the new data giving it): the cards a change touches; the author then decides
// on the dependent scenes.
async function change(path,method,body,done,subject=null){
  if(busy||!data)return false;
  const before=data.story_revision,story=storyId;busy=true;draw();
  let dependent=[];
  try{
    data=await api(`/api/stories/${story}/locations${path}`,json(method,{...body,expected_revision:before}));
    dependent=data.dependent_scene_ids||[];
    notice(msg(done));
  }catch(e){notice(diagnostic(e.message),'error');await load();return false}  // drafts survive the reload
  finally{busy=false;draw()}
  if(typeof subject==='function')subject=subject(data);
  // The workspace notices the moved story revision when the author returns to it (MCP-BRIDGE).
  if(subject)await offerInvalidation(story,'location',subject.ids,subject.names,dependent);
  return true;
}

async function merge(id,path,into,intoPath){
  if(!into||!await confirmDialog(t('locations.merge_confirm',{p0:path,p1:intoPath||''}),{accept:t('locations.merge_do')}))return;
  choosing=null;
  await change(`/${id}/merge`,'POST',{into},'locations.merged_notice',{ids:[id,into],names:[path,intoPath||'']});
}

// R-51: a place a model gave the scene goes after a confirmation; then, as for any card change, the author decides on
// the dependent scenes.
async function removeFromScene(row,scene){
  if(!await confirmDialog(t('locations.remove_confirm',{p0:row.path,p1:scene.label}),{accept:t('locations.remove_do')}))return;
  await change(`/${row.id}/remove-from-scene`,'POST',{scene_id:scene.id},'locations.removed',{ids:[row.id],names:[row.path]});
}

// MEMORY-LOCATIONS-S11: the phrase becomes a glue of the story; plan scenes get the glued card at once.
async function glue(option){
  if(!option||!await confirmDialog(t('locations.glue_confirm',{p0:option.phrase,p1:option.scenes}),{accept:t('locations.glue_do')}))return;
  gluing=null;
  await change('/glue','POST',{phrase:option.phrase},'locations.glued',{ids:option.cardIds,names:[option.phrase]});
}

async function unglue(item){
  if(!await confirmDialog(t('locations.unglue_confirm',{p0:item.phrase}),{accept:t('locations.unglue')}))return;
  await change('/unglue','POST',{key:item.key},'locations.unglued',
    fresh=>({ids:(fresh?.glue_candidates||[]).find(c=>c.key===item.key)?.card_ids||['glue:'+item.key],names:[item.phrase]}));
}

async function save(row,text){
  if(await change(`/${row.id}`,'PUT',{description:text},'locations.saved',{ids:[row.id],names:[row.path]}))drafts.delete(row.id);
  draw();
}

if(page){
  const back=document.querySelector('#locations-return');
  if(back)back.href=returnLink(storyId,location.search);
  globalThis.addEventListener('beforeunload',event=>{if(hasDrafts(drafts)){event.preventDefault();event.returnValue=''}});
  void load();
}
