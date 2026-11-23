import {t,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {pendingLinks} from './link-actions.js';
// VALID-LINKS-S08/S11: the pending links of the open scene with the author's actions (link-actions.js). The panel
// reads the story view's material_status; the server checks the fingerprint, so a stale panel gets 409 and refreshes.
const host=document.querySelector('#link-attention');
const CARRY_POLL_MS=3000,CARRY_POLLS=40;
let busy=false,carryTimer=null,carryPolls=0;
function render(){
  if(!host)return;
  host.replaceChildren();
  const items=state.scene?pendingLinks(state.view?.material_status,state.scene.id,state.view?.scenes||[]):[];
  host.hidden=!items.length;
  for(const item of items){
    const row=document.createElement('p');row.className='link-attention-row';row.dataset.link=item.key;
    const text=document.createElement('span');uiText(text,'textContent',()=>t(item.text,item.params));
    row.append(text);
    for(const action of item.actions){
      const button=document.createElement('button');button.type='button';button.className='secondary';button.disabled=busy;
      uiText(button,'textContent',()=>t(action.label));
      button.onclick=()=>void(action.type==='approve'?decide(action):action.type==='carry'?carry(action)
        :createMemory(action.sceneId,action.type==='rebuild'?{mode:'rebuild_memory'}:{mode:'stage',stage:'memory'}));
      row.append(' ',button);
    }
    host.append(row);
  }
  // MEMORY-CARRY: the carry runs in the background without a followed run; the view is read again until it reaches
  // this scene, so «Пам’ять переноситься…» clears by itself. A paused or failed carry keeps the scene pending, so the
  // polling stops after about two minutes per opened scene (the next refresh or scene switch shows the state again).
  clearTimeout(carryTimer);carryTimer=null;
  const pending=items.some(item=>item.text==='link.carry_pending');
  if(!pending)carryPolls=0;
  else if(carryPolls<CARRY_POLLS)carryTimer=setTimeout(()=>{
    carryTimer=null;carryPolls++;
    if(!busy&&!state.dirty&&!state.saving)refresh({fresh:true}).catch(()=>{}).finally(render);else render();
  },CARRY_POLL_MS);
}
async function decide(action){
  if(busy)return;
  busy=true;render();
  try{
    await api(`/api/scenes/${state.scene.id}/links/${action.link}/decision`,json('POST',{action:'approve',fingerprint:action.fingerprint}));
    notice(t('link.approved'),'success');
  }catch(error){notice(error.message,'error')}
  finally{busy=false;await refresh();render()}
}
// MEMORY-CARRY: a stalled carry is resumed (no model, no cost) or cancelled; the scenes it covers stop waiting either way.
async function carry(action){
  if(busy)return;
  busy=true;render();
  try{
    await api(`/api/runs/${action.runId}/${action.command}`,json('POST',action.command==='resume'?{repeat_interrupted:true}:{}));
  }catch(error){notice(error.message,'error')}
  finally{busy=false;carryPolls=0;await refresh();render()}
}
// The memory stage (or «Перебудувати пам’ять») of the named scene through the usual run preview and consent. The run
// command works on the open scene, so another scene (the previous one) is opened first; a cancelled switch (unsaved
// text) launches nothing.
async function createMemory(sceneId,options){
  if(busy)return;
  try{
    if(state.scene?.id!==sceneId){
      const target=state.view?.scenes?.find(scene=>scene.id===sceneId);
      if(!target)return;
      await selectScene(target);
      if(state.scene?.id!==sceneId)return;
    }
    await invokeWorkspaceCommand('run',options);
  }catch(error){if(error.name!=='AbortError')notice(error.message,'error')}
}
document.addEventListener('story-refreshed',render);
document.addEventListener('scene-selected',()=>{carryPolls=0;render()});
render();
