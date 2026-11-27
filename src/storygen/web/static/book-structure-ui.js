// BOOK-STRUCTURE-S06 on the story page: the «Arc» field in scene parameters and, in an edition without long prose, the
// read-only banner for a structured book (BUILD-EDITION-001-S08). The server refuses writes either way.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
import {appInfo} from './app-info.js';
import {arcOptions,meetingOptions} from './book-structure.js';
import {confirmDialog} from './dialogs.js';
import {claimTrial,trialState,usedNotice} from './long-prose-trial.js';

let info=null;
// LONG-PROSE-TRIAL-S07: the book answers for itself (GET /api/stories/{id}), its trial included.
const longProse=()=>state.view?.long_prose!==false;
const label=(key,n)=>t(key,{p0:n});

function banner(){
  const workspace=document.querySelector('#workspace');if(!workspace)return;
  let box=document.querySelector('#book-readonly');
  const show=!!state.view&&!longProse()&&state.view.book_structure?.kind==='structured';
  if(!show){box?.remove();document.querySelector('#book-readonly-trial')?.remove();return}
  if(!box){box=document.createElement('p');box.id='book-readonly';box.className='notice warning';box.setAttribute('role','status');workspace.prepend(box)}
  uiText(box,'textContent',()=>t('book.readonly'));
  const save=document.querySelector('#save-text');if(save)save.disabled=true;
  trialOffer(box);
}

// Beside the banner, never inside it: the banner keeps its exact text. A series book is offered its series instead.
function trialOffer(box){
  let node=document.querySelector('#book-readonly-trial');
  const trial=trialState(info),story=state.view.story;
  const kind=trial.state==='available'&&!story.series_id?'offer':trial.state==='used'?'used':null;
  if(!kind){node?.remove();return}
  if(node?.dataset.kind===kind)return;
  if(!node){node=document.createElement('div');node.id='book-readonly-trial';node.className='trial-offer'}
  box.after(node);node.dataset.kind=kind;
  if(kind==='used'){node.replaceChildren(usedNotice(document,trial,info));return}
  const offer=document.createElement('button');offer.type='button';
  uiText(offer,'textContent',()=>t('trial.offer_book'));
  offer.onclick=()=>claimTrial({api,json,confirmDialog,notice,location},{story_id:state.storyId},story.title);
  node.replaceChildren(offer);
}

function arcField(){
  document.querySelector('#scene-arc')?.remove();
  const book=state.view?.book_structure,settings=document.querySelector('#scene-settings');
  if(!longProse()||!book?.explicit||!state.scene||!settings)return;
  const current=state.view.scenes.find(scene=>scene.id===state.scene.id);
  const form=document.createElement('form');form.id='scene-arc';form.className='panel';
  const field=document.createElement('label'),caption=document.createElement('span'),select=document.createElement('select');
  select.name='arc_id';uiText(caption,'textContent',()=>t('book.scene_arc'));
  for(const option of arcOptions(book,label)){const item=document.createElement('option');item.value=option.value;item.textContent=option.label;select.append(item)}
  const arcIds=current?.arc_ids?.length?current.arc_ids:current?.arc_id?[current.arc_id]:[];
  select.value=arcIds[0]||'';field.append(caption,select);form.append(field);
  // Every change is saved at once: one PUT with the story revision; a refused change restores the shown value.
  const save=async(body,restore)=>{
    try{
      await api(`/api/stories/${state.storyId}/scenes/${state.scene.id}/arc`,json('PUT',{...body,expected_revision:state.view.story.revision}));
      await refresh();notice(msg('book.scene_arc_saved'));
    }catch(e){restore();notice(e.message,'error')}
  };
  // A new main arc ends a meeting: the scene keeps one arc.
  select.onchange=()=>save({arc_id:select.value},()=>{select.value=arcIds[0]||''});
  // MEMORY-MERGE harness: the other arcs of the part make the scene a meeting scene.
  const options=meetingOptions(book,arcIds,label);
  if(options.length){
    const group=document.createElement('fieldset'),legend=document.createElement('legend');
    group.className='scene-meeting';uiText(legend,'textContent',()=>t('book.scene_meeting'));group.append(legend);
    const boxes=[];
    for(const option of options){
      const item=document.createElement('label'),box=document.createElement('input'),text=document.createElement('span');
      box.type='checkbox';box.value=option.value;box.checked=option.checked;text.textContent=option.label;
      box.onchange=()=>{
        const ids=[select.value,...boxes.filter(b=>b.checked).map(b=>b.value)];
        save(ids.length>1?{arc_ids:ids}:{arc_id:ids[0]},()=>{box.checked=!box.checked});
      };
      boxes.push(box);item.append(box,text);group.append(item);
    }
    form.append(group);
  }
  settings.after(form);
}

function draw(){banner();arcField()}
document.addEventListener('scene-selected',draw);document.addEventListener('story-refreshed',draw);
appInfo().then(value=>{info=value;draw()});
