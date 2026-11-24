import {confirmDialog} from './dialogs.js';
import {t,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,selectScene} from './editor.js';
import {auditConfirmationText,operationReason} from './run-readiness.js';
import {invalidSceneCount,bookMenuState,latestBookRun} from './book-validation-state.js';
import {stoppedAuditScene} from './run-summary.js';

// R-44 book validation, design §9/§12: the story menu item counts the invalid scenes of the story view; a press reads the
// preview (scenes, calls, the upper bound on cost and the plan fingerprint), and only the author's consent starts the run
// with that fingerprint. A plan that changed since the preview is refused by the server (409): the author reviews it
// again. A book run stopped for the author's decision leads from the status row to the scene of its stop.
const PLAN_CHANGED='План перевірки змінився. Перегляньте його ще раз';
const ACTIVE_RUN=new Set(['queued','running','pause_requested','cancellation_requested']);
const item=document.querySelector('#story-menu-validate'),jump=document.querySelector('#run-stop-scene');
let busy=false,lastRun=null;

// Visible run progress: a running book validation disables the item, a stopped one leads to its run row.
const bookRun=()=>latestBookRun(state.workspaceRuns,lastRun||state.workspaceRun);
const menuState=()=>bookMenuState(state.view?invalidSceneCount(state.view.material_status):null,bookRun());
function renderMenu(){
  if(!item)return;
  const menu=menuState();
  uiText(item,'textContent',()=>t(menu.key,menu.params));
  item.disabled=menu.disabled||busy||(!menu.show&&ACTIVE_RUN.has(state.workspaceRun?.state));
}
// The stop scene is the main action of a stopped book validation; after it opens, the focus goes to the scene's
// link panel (Р7: #link-attention until the coherence panel exists), else back to the run row.
async function openStopScene(scene){
  await selectScene(scene);
  const panel=document.querySelector('#link-attention'),target=panel&&!panel.hidden?panel:document.querySelector('#workspace-status-row');
  if(!target)return;
  if(!target.hasAttribute('tabindex'))target.tabIndex=-1;
  target.focus();
}
function renderJump(){
  if(!jump)return;
  const scene=stoppedAuditScene(lastRun,state.view?.scenes);
  jump.hidden=!scene;
  jump.classList.toggle('secondary',!scene);
  jump.onclick=scene?()=>void openStopScene(scene).catch(error=>notice(error.message,'error')):null;
  if(scene)uiText(jump,'textContent',()=>t('run.go_to_scene',{p0:scene.position+1}));
}
function render(){renderMenu();renderJump()}

async function validate(){
  if(busy)return;
  busy=true;renderMenu();
  try{
    for(;;){
      const preview=await api(`/api/stories/${state.storyId}/audit/preview`,json('POST',{scope:'story'}));
      const reason=operationReason(state,preview);
      if(reason){notice(reason,'warning');return}
      if(!await confirmDialog(auditConfirmationText(preview),{accept:t('book_validation.accept')}))return;
      const request={story_id:state.storyId,scene_id:null,mode:'audit',stage:null,audit_scope:'story',
        audit_plan_fingerprint:preview.plan_fingerprint,pause_after:[],budget_limit_usd:document.querySelector('#run-budget')?.value||null};
      try{
        const run=await api('/api/runs',json('POST',{request_id:crypto.randomUUID(),request}));
        document.dispatchEvent(new CustomEvent('run-reveal',{detail:run}));
        return;
      }catch(error){
        if(error.status!==409||error.message!==PLAN_CHANGED)throw error;
        if(!await confirmDialog(diagnostic(PLAN_CHANGED),{accept:t('book_validation.review_again')}))return;
      }
    }
  }catch(error){notice(error.message,'error')}
  finally{busy=false;renderMenu()}
}

if(item)item.onclick=()=>{
  const run=bookRun();
  if(bookMenuState(null,run).show){document.dispatchEvent(new CustomEvent('run-reveal',{detail:run}));return}
  void validate();
};
document.addEventListener('workspace-run-state',event=>{lastRun=event.detail;render()});
// A short run from the list has no checkpoint: keep the full run while it is the same run in the same state.
document.addEventListener('workspace-run-pending',event=>{
  const run=event.detail;if(lastRun?.id!==run?.id||lastRun?.state!==run?.state)lastRun=null;render();
});
document.addEventListener('story-refreshed',render);
document.addEventListener('workspace-readiness',renderMenu);
render();
