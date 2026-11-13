// MEMORY-MERGE-S04: the «Memory merge» section of the scene memory panel and the link to it from a run stopped before a
// merge point. Confirming is one PUT with CAS on the story revision and the head memory; a refused save re-reads the
// state and keeps every choice whose conflict did not change.
import {t,msg,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {mergeRows,keepChoices,decisionsPayload,confirmReason,headMemoryIds,mergeStopScene} from './memory-merge.js';

// The server's MergeRequired text (memory/previous.py::MERGE_REQUIRED); a stopped run keeps only this text.
const REQUIRED='Потрібне злиття пам’яті перед цією сценою';
let data=null,rows=[],epoch=0,saving=false,focusAfterLoad=false;

const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};

function box(create){
  const panel=document.querySelector('#memory-view');if(!panel)return null;
  let section=panel.querySelector('#memory-merge');
  if(!section&&create){
    section=document.createElement('section');section.id='memory-merge';section.className='memory-merge';section.tabIndex=-1;
    const summaries=panel.querySelector('#timeline-summaries');
    if(summaries)panel.insertBefore(section,summaries);else panel.append(section);
  }
  return section;
}

function radio(row,value,label,group){
  const item=node('label',null,'memory-merge-choice'),input=document.createElement('input');
  input.type='radio';input.name=group;input.value=value;input.checked=row.choice===value;
  input.onchange=()=>{  // a redraw replaces the inputs: keep keyboard focus on the chosen value
    row.choice=value;draw();
    [...(box(false)?.querySelectorAll('input[type=radio]')||[])].find(other=>other.name===group&&other.value===value)?.focus();
  };
  item.append(input,node('span',label));return item;
}

function conflictRow(row,index){
  const group=node('fieldset',null,'memory-merge-row');group.dataset.key=row.key;
  group.append(node('legend',()=>row.label));
  if(row.carried)group.append(node('p',()=>t('merge.carried'),'hint'));
  for(const value of row.values){
    const arcs=value.arcs.length?` (${value.arcs.join(', ')})`:'';
    group.append(radio(row,value.headId,()=>`${value.title}${arcs}: ${value.value??t('merge.value.none')}`,`merge-${index}`));
  }
  group.append(radio(row,'author',()=>t('merge.author'),`merge-${index}`));
  if(row.choice==='author'){
    const area=document.createElement('textarea');area.rows=2;area.maxLength=4000;area.value=row.text;area.className='memory-merge-author';
    area.setAttribute('aria-label',t('merge.author'));area.oninput=()=>{row.text=area.value};
    group.append(area);
  }
  return group;
}

function draw(){
  if(!data){box(false)?.remove();return}
  const section=box(true);
  section.replaceChildren(node('h3',()=>t(data.book_end?'merge.title_book_end':'merge.title')));
  const status=node('p',()=>t('merge.state.'+data.state),'memory-merge-state');status.setAttribute('role','status');section.append(status);
  if(data.reason)section.append(node('p',()=>diagnostic(data.reason),'hint'));
  const heads=node('ul',null,'memory-merge-heads');
  for(const head of data.heads||[]){
    const arcs=head.arc_titles?.length?` — ${head.arc_titles.join(', ')}`:'';
    heads.append(node('li',()=>`${head.number}. ${head.title}${arcs}`));
  }
  section.append(node('p',()=>t('merge.heads')),heads);
  if(data.state!=='blocked'){
    if(!rows.length)section.append(node('p',()=>t('merge.no_conflicts')));
    rows.forEach((row,index)=>section.append(conflictRow(row,index)));
  }
  const reason=confirmReason(data,rows);
  const actions=node('div',null,'actions');
  const confirm=node('button',()=>t('merge.confirm'));confirm.type='button';confirm.disabled=!!reason||saving;confirm.onclick=save;
  actions.append(confirm);
  if(reason)actions.append(node('span',()=>t(reason),'hint'));
  section.append(actions);
}

const lastActive=()=>{const active=(state.view?.scenes||[]).filter(scene=>!scene.trashed_at);return active.at(-1)};

async function fetchState(){
  const base=`/api/stories/${state.storyId}/memory-merges`;
  let found=await api(`${base}?scene_id=${encodeURIComponent(state.scene.id)}`);
  if(found.state==='not_needed'&&lastActive()?.id===state.scene.id)found=await api(`${base}?point=book_end`);
  return found.state==='not_needed'?null:found;
}

async function load(){
  const current=++epoch;
  if(!state.storyId||!state.scene||!state.view?.book_structure?.explicit||!document.querySelector('#memory-view')){data=null;rows=[];draw();return}
  try{
    const found=await fetchState();
    if(current!==epoch)return;
    const same=data&&found&&data.key===found.key;
    data=found;rows=found?(same?keepChoices(rows,mergeRows(found)):mergeRows(found)):[];
  }catch(e){if(current!==epoch)return;data=null;rows=[]}
  draw();
  if(focusAfterLoad&&data){focusAfterLoad=false;const section=box(false);section?.scrollIntoView({block:'start'});section?.focus({preventScroll:true})}
}

async function save(){
  if(!data||saving)return;
  saving=true;draw();
  try{
    await api(`/api/stories/${state.storyId}/memory-merges/${encodeURIComponent(data.key)}`,json('PUT',{
      decisions:decisionsPayload(rows),expected_revision:data.story_revision,expected_head_memory_ids:headMemoryIds(data)}));
    notice(msg('merge.saved'));
    saving=false;await refresh();
  }catch(e){
    notice(diagnostic(e.message),'error');saving=false;
    await load();  // keeps every choice whose conflict is the same
  }
}

// The link from a run stopped before a merge point (or a scene whose readiness names the merge).
function stopLink(){
  const row=document.querySelector('#workspace-status-row');if(!row)return;
  let link=document.querySelector('#memory-merge-open');
  const sceneId=mergeStopScene(state.workspaceRun,state.workspaceReadiness,state.scene?.id,REQUIRED);
  if(!sceneId){link?.remove();return}
  if(!link){
    link=node('button',()=>t('merge.open'),'secondary');link.id='memory-merge-open';link.type='button';row.append(link);
  }
  link.onclick=async()=>{
    const scene=(state.view?.scenes||[]).find(item=>item.id===sceneId);if(!scene)return;
    focusAfterLoad=true;
    if(state.scene?.id!==sceneId)await selectScene(scene);
    await invokeWorkspaceCommand('show','memory');
    await load();
  };
}

document.addEventListener('scene-selected',()=>{load();stopLink()});
document.addEventListener('story-refreshed',()=>{load();stopLink()});
document.addEventListener('workspace-readiness',stopLink);
document.addEventListener('workspace-run-state',stopLink);
