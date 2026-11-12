// BOOK-STRUCTURE-S06 on the story page: the «Arc» field in scene parameters and, in an edition without long prose, the
// read-only banner for a structured book (BUILD-EDITION-001-S08). The server refuses writes either way.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
import {appInfo} from './app-info.js';
import {arcOptions} from './book-structure.js';

let longProse=null;
const label=(key,n)=>t(key,{p0:n});

function banner(){
  const workspace=document.querySelector('#workspace');if(!workspace)return;
  let box=document.querySelector('#book-readonly');
  const show=longProse===false&&state.view?.book_structure?.kind==='structured';
  if(!show){box?.remove();return}
  if(!box){box=document.createElement('p');box.id='book-readonly';box.className='notice warning';box.setAttribute('role','status');workspace.prepend(box)}
  uiText(box,'textContent',()=>t('book.readonly'));
  const save=document.querySelector('#save-text');if(save)save.disabled=true;
}

function arcField(){
  document.querySelector('#scene-arc')?.remove();
  const book=state.view?.book_structure,settings=document.querySelector('#scene-settings');
  if(!longProse||!book?.explicit||!state.scene||!settings)return;
  const current=state.view.scenes.find(scene=>scene.id===state.scene.id);
  const form=document.createElement('form');form.id='scene-arc';form.className='panel';
  const field=document.createElement('label'),caption=document.createElement('span'),select=document.createElement('select');
  select.name='arc_id';uiText(caption,'textContent',()=>t('book.scene_arc'));
  for(const option of arcOptions(book,label)){const item=document.createElement('option');item.value=option.value;item.textContent=option.label;select.append(item)}
  select.value=current?.arc_id||'';field.append(caption,select);form.append(field);
  // The change is saved at once: one PUT with the story revision; a refused change restores the shown value.
  select.onchange=async()=>{
    const previous=current?.arc_id||'';
    try{
      await api(`/api/stories/${state.storyId}/scenes/${state.scene.id}/arc`,json('PUT',{arc_id:select.value,expected_revision:state.view.story.revision}));
      await refresh();notice(msg('book.scene_arc_saved'));
    }catch(e){select.value=previous;notice(e.message,'error')}
  };
  settings.after(form);
}

function draw(){banner();arcField()}
document.addEventListener('scene-selected',draw);document.addEventListener('story-refreshed',draw);
appInfo().then(info=>{longProse=info.long_prose!==false;draw()});
