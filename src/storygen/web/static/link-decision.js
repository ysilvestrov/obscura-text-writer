import {t,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
// VALID-LINKS-S08: an unchecked brief or prose link of the open scene offers the author's approval. The panel reads
// the story view's material_status; the server checks the fingerprint, so a stale panel gets 409 and refreshes.
const host=document.querySelector('#link-attention');
const LINKS={brief:{text:'link.brief_unchecked',action:'link.approve_brief'},prose:{text:'link.prose_unchecked',action:'link.approve_prose'}};
let busy=false;
export function pendingLinks(materialStatus,sceneId){
  const links=(materialStatus||{})[sceneId]?.links||{};
  return Object.keys(LINKS).filter(link=>links[link]?.status==='unchecked').map(link=>({link,fingerprint:links[link].fingerprint}));
}
function render(){
  if(!host)return;
  host.replaceChildren();
  const items=state.scene?pendingLinks(state.view?.material_status,state.scene.id):[];
  host.hidden=!items.length;
  for(const item of items){
    const row=document.createElement('p');row.className='link-attention-row';row.dataset.link=item.link;
    const text=document.createElement('span');uiText(text,'textContent',()=>t(LINKS[item.link].text));
    const button=document.createElement('button');button.type='button';button.className='secondary';button.disabled=busy;
    uiText(button,'textContent',()=>t(LINKS[item.link].action));
    button.onclick=()=>void decide(item);
    row.append(text,' ',button);host.append(row);
  }
}
async function decide(item){
  if(busy)return;
  busy=true;render();
  try{
    await api(`/api/scenes/${state.scene.id}/links/${item.link}/decision`,json('POST',{action:'approve',fingerprint:item.fingerprint}));
    notice(t('link.approved'),'success');
  }catch(error){notice(error.message,'error')}
  finally{busy=false;await refresh();render()}
}
document.addEventListener('story-refreshed',render);
document.addEventListener('scene-selected',render);
render();
