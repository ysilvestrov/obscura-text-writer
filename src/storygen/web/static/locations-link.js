// MEMORY-LOCATIONS-S12: the locations live on their own page; a scene's memory tab keeps one link to it, last in the
// tab (after «Timeline summaries», which other panels add later).
import {t,uiText} from './i18n.js';
import {state} from './editor.js';
import {memoryLinkHref} from './locations.js';

const panel=document.querySelector('#memory-view');
let line=null;

function place(){
  if(!panel||!state.storyId)return;
  if(!line){
    line=document.createElement('p');line.id='memory-locations-link';line.className='memory-locations-link';
    const link=document.createElement('a');uiText(link,'textContent',()=>t('locations.memory_link'));line.append(link);
  }
  line.firstChild.href=memoryLinkHref(state.storyId,state.scene?.id,state.mode);
  if(panel.lastElementChild!==line)panel.append(line);
}

if(panel){
  new MutationObserver(()=>{if(line&&panel.lastElementChild!==line)panel.append(line)}).observe(panel,{childList:true});
  for(const name of ['scene-selected','story-refreshed','editor-state-changed'])document.addEventListener(name,place);
  place();
}
