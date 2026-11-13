// MEMORY-SUMMARY-S07: the «Timeline summaries» section of the scene memory panel. Creating or rebuilding a summary is
// a paid memory-role call: the author sees readiness and the model first. A correction is saved with CAS on the block head
// and the story revision; a refused save keeps the typed text.
import {t,msg,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state} from './editor.js';
import {confirmDialog} from './dialogs.js';
import {summaryRows} from './timeline-summaries.js';

const FINISHED=new Set(['completed','failed','cancelled','needs_review','alternative']);
let data=null,editing=null,storyId=null;
const busy=new Set();

function box(){
  const panel=document.querySelector('#memory-view');if(!panel)return null;
  let section=panel.querySelector('#timeline-summaries');
  if(!section){section=document.createElement('section');section.id='timeline-summaries';section.className='timeline-summaries';panel.append(section)}
  return section;
}

const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};

function button(render,onclick,primary=false){
  const b=node('button',render,primary?'':'secondary');b.type='button';b.onclick=onclick;return b;
}

function draw(){
  const section=box();if(!section)return;
  section.replaceChildren(node('h3',()=>t('summaries.title')));
  const rows=summaryRows(data?.blocks);
  if(!rows.length){section.append(node('p',()=>t('summaries.empty')));return}
  for(const row of rows){
    const item=node('div',null,'timeline-summary-row');item.dataset.key=row.key;item.dataset.state=row.state;
    const head=node('p');head.append(node('strong',()=>t(row.label.key,row.label.params)),document.createTextNode(' '),
      node('span',()=>t('summaries.state.'+row.state),'timeline-summary-state'));
    item.append(head);
    if(row.reason)item.append(node('p',()=>row.reason.startsWith('summaries.')?t(row.reason):diagnostic(row.reason),'hint'));
    if(row.text&&editing?.key!==row.key)item.append(node('p',()=>row.text,'timeline-summary-text'));
    const actions=node('div',null,'actions');
    if(row.action){
      const run=button(()=>t(row.action==='create'?'summaries.create':'summaries.rebuild'),()=>start(row),row.highlighted);
      run.disabled=busy.has(row.key);if(row.highlighted)run.classList.add('recommended');actions.append(run);
    }
    if(row.editable&&editing?.key!==row.key)actions.append(button(()=>t('summaries.edit'),()=>{editing={key:row.key,text:row.text,versionId:row.versionId};draw()}));
    if(editing?.key===row.key){
      const area=document.createElement('textarea');area.value=editing.text;area.rows=5;area.className='timeline-summary-editor';
      area.oninput=()=>{editing.text=area.value};
      item.append(area);
      actions.append(button(()=>t('summaries.save'),()=>save(row),true),button(()=>t('summaries.cancel'),()=>{editing=null;draw()}));
    }
    item.append(actions);section.append(item);
  }
}

async function load(){
  if(!state.storyId||!document.querySelector('#memory-view'))return;
  if(storyId!==state.storyId){editing=null;storyId=state.storyId}
  try{data=await api(`/api/stories/${state.storyId}/timeline-summaries`)}catch(e){data=null}
  draw();
}

async function waitRun(id){
  for(let i=0;i<400;i++){
    const run=await api(`/api/runs/${id}`);
    if(FINISHED.has(run.state))return run;
    await new Promise(resolve=>setTimeout(resolve,1500));
  }
  return null;
}

async function start(row){
  const base=`/api/stories/${state.storyId}/timeline-summaries`;
  try{
    const ready=await api(`${base}/readiness?block_key=${encodeURIComponent(row.key)}`);
    if(!ready.ready){notice(diagnostic(ready.reason),'error');return}
    if(!await confirmDialog(t('summaries.confirm',{p0:ready.roles.memory.model,p1:ready.estimated_tokens})))return;
    busy.add(row.key);draw();
    const run=await api('/api/runs',json('POST',{request:{story_id:state.storyId,mode:'timeline_summary',summary_block_key:row.key},request_id:crypto.randomUUID()}));
    const done=await waitRun(run.id);
    if(done?.state==='completed')notice(msg('summaries.created'));
    else if(done)notice(diagnostic(done.error)||t('summaries.failed'),'error');
  }catch(e){notice(diagnostic(e.message),'error')}
  finally{busy.delete(row.key);await load()}
}

async function save(row){
  try{
    data=await api(`/api/stories/${state.storyId}/timeline-summaries/${encodeURIComponent(row.key)}`,
      json('PUT',{text:editing.text,expected_version_id:editing.versionId,expected_revision:data.story_revision}));
    editing=null;notice(msg('summaries.saved'));draw();
  }catch(e){notice(diagnostic(e.message),'error')}  // the buffer stays in `editing`
}

document.addEventListener('scene-selected',load);
document.addEventListener('story-refreshed',load);
