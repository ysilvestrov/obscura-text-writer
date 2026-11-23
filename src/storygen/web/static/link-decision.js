import {t,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {pendingLinks} from './link-actions.js';
import {settingsLink} from './workspace-links.js';
// VALID-LINKS-S08/S11: the pending links of the open scene with the author's actions (link-actions.js). The panel
// reads the story view's material_status; the server checks the fingerprint, so a stale panel gets 409 and refreshes.
const host=document.querySelector('#link-attention');
const auditButton=document.querySelector('#audit-scene');
const ACTIVE_RUN=new Set(['queued','running','pause_requested','cancellation_requested']);
const CARRY_POLL_MS=3000,CARRY_POLLS=40;
let busy=false,carryTimer=null,carryPolls=0;
// VALID-LINKS: «Перевірити сцену» is offered while the open scene is not valid (its brief and prose exist, a link is
// unchecked or in discrepancy) and no run of the workspace is active; it runs the auditor through the usual preview and
// consent, and the run stops on a link that needs the author's decision.
function renderAudit(){
  if(!auditButton)return;
  const validity=state.scene&&state.view?.material_status?.[state.scene.id]?.validity;
  auditButton.hidden=!['unchecked','discrepancy'].includes(validity);
  auditButton.disabled=busy||ACTIVE_RUN.has(state.workspaceRun?.state);
}
async function audit(){
  if(busy)return;
  try{await invokeWorkspaceCommand('run',{mode:'audit',audit_scope:'scene'})}
  catch(error){if(error.name!=='AbortError')notice(error.message,'error')}
}
if(auditButton)auditButton.onclick=()=>void audit();
function render(){
  renderAudit();
  if(!host)return;
  host.replaceChildren();
  const items=state.scene?pendingLinks(state.view?.material_status,state.scene.id,state.view?.scenes||[]):[];
  host.hidden=!items.length;
  for(const item of items){
    const row=document.createElement(item.discrepancies||item.reason!==undefined?'div':'p');row.className='link-attention-row';row.dataset.link=item.key;
    // The auditor's reason is a server text (translated); its summary, items and quotes are the model's words, shown as is.
    const text=document.createElement('span');
    uiText(text,'textContent',()=>t(item.text,item.reason!==undefined?{...item.params,p0:diagnostic(item.reason)}:item.params));
    row.append(text);
    if(item.summary){const summary=document.createElement('p');summary.className='muted link-audit-summary';summary.textContent=item.summary;row.append(summary)}
    if(item.discrepancies?.length){
      const list=document.createElement('ul');list.className='link-discrepancies';
      for(const entry of item.discrepancies){
        const li=document.createElement('li');li.className='link-discrepancy';
        const what=document.createElement('span');what.textContent=entry.text;li.append(what);
        if(entry.quote){const quote=document.createElement('blockquote');quote.textContent=entry.quote;li.append(quote)}
        list.append(li);
      }
      row.append(list);
    }
    const buttons=item.discrepancies||item.reason!==undefined?document.createElement('p'):row;
    for(const action of item.actions){
      const button=document.createElement('button');button.type='button';button.className='secondary';button.disabled=busy;
      uiText(button,'textContent',()=>t(action.label));
      button.onclick=()=>void(action.type==='approve'?decide(action):action.type==='carry'?carry(action)
        :action.type==='settings'?openSettings()
        :createMemory(action.sceneId,action.type==='rebuild'?{mode:'rebuild_memory'}:{mode:'stage',stage:'memory'}));
      buttons.append(' ',button);
    }
    if(buttons!==row&&buttons.childNodes.length){buttons.className='link-attention-actions';row.append(buttons)}
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
// The auditor's settings, with the same guard as the settings link of a failed run: unsaved text stays in the editor.
function openSettings(){
  const href=state.scene&&settingsLink(state.storyId,state.scene.id,state.mode,'auditor');
  if(!href)return;
  if(state.dirty||state.saving){document.dispatchEvent(new CustomEvent('workspace-navigation-blocked'));notice(t('m_df05df152938'),'warning');return}
  location.href=href;
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
for(const event of ['workspace-run-state','workspace-run-pending'])document.addEventListener(event,renderAudit);
document.addEventListener('scene-selected',()=>{carryPolls=0;render()});
render();
