import {confirmDialog} from './dialogs.js';
import {t} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';

// DATA-010-S02: the story menu accepts all waiting prose as the author's in one server transaction.
// The server list is the only criterion for showing the menu item.
const button=document.querySelector('#story-menu-accept-prose');
let busy=false,epoch=0;
const preview=()=>api(`/api/stories/${state.storyId}/prose-acceptance`);
async function load(){
  const mine=++epoch;
  try{const data=await preview();if(mine===epoch)button.hidden=!data.scenes.length}
  catch(error){if(mine===epoch)button.hidden=true}
  controls();
}
function controls(){button.disabled=busy}
button.onclick=async()=>{
  if(busy)return;
  busy=true;controls();
  try{
    const data=await preview();
    if(!data.scenes.length){notice(t('prose_accept.none'),'warning');button.hidden=true;return}
    const titles=data.scenes.map(scene=>'«'+scene.title+'»').join(', ');
    if(!await confirmDialog(t('prose_accept.confirm',{p0:data.scenes.length,p1:titles}),{accept:t('prose_accept.accept')}))return;
    const result=await api(`/api/stories/${state.storyId}/prose-acceptance`,json('POST',{fingerprint:data.fingerprint}));
    notice(t('prose_accept.done',{p0:result.accepted.length}),'success');
    const open=state.scene?.id;
    await refresh();
    // Acceptance bumps the scene revision without changing any text: the open buffer, saved or not, takes the new
    // revision so its next save does not conflict.
    const latest=state.view?.scenes?.find(scene=>scene.id===open);
    if(latest&&state.scene?.id===open&&result.accepted.some(a=>a.scene_id===open))
      state.scene={...state.scene,revision:latest.revision,needs_review:latest.needs_review};
  }catch(error){notice(error.message,'error')}
  finally{busy=false;await load()}
};
document.addEventListener('story-refreshed',()=>void load());
void load();
