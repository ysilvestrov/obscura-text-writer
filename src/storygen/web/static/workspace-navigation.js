import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {settingsLink,returnLink} from './workspace-links.js';

const settings=document.querySelector('.settings-page');
if(settings){
  const link=document.querySelector('#settings-return')||document.createElement('a');uiText(link,"textContent",()=>(t("m_b38276cdf9d4")));
  link.href=returnLink(settings.dataset.storyId,location.search);if(!link.parentElement)settings.prepend(link);
  const role=new URLSearchParams(location.search).get('role');
  let roleFocused=false;
  function focusRole(){if(roleFocused)return;if(!['planner','writer','editor','memory'].includes(role))return;document.dispatchEvent(new CustomEvent('settings-show-role',{detail:role}));const form=settings.querySelector(`[data-role="${role}"]`);if(form){roleFocused=true;form.id='role-'+role;form.querySelector('[name=context_tokens]')?.focus()}}
  document.addEventListener('workspace-settings-loaded',focusRole);
  focusRole();
}
const workspace=document.querySelector('#workspace');
if(workspace){
  const {state,initialWorkspacePosition}=await import('./editor.js');
  const charactersLink=document.querySelector('#workspace-characters');
  const updateCharactersLink=()=>{
    if(!charactersLink)return;
    const query=new URLSearchParams();
    if(state.scene){query.set('scene',state.scene.id);query.set('material',state.mode);}
    charactersLink.href=`/stories/${encodeURIComponent(state.storyId)}/characters`+(query.size?'?'+query:'');
  };
  document.addEventListener('editor-state-changed',updateCharactersLink);
  updateCharactersLink();
  const {resolveWorkspacePosition}=await import('./workspace-position.js');
  await import('./versions.js');
  const {invokeWorkspaceCommand}=await import('./workspace-commands.js');
  const link=document.querySelector('#workspace-error-settings');
  function show(role){
    const href=state.scene&&settingsLink(state.storyId,state.scene.id,state.mode,role);
    link.hidden=!href;if(href){link.href=href;uiText(link,"textContent",()=>(t("m_1a02bd37b311")+({get planner(){return t("m_1e464d8b93dd")},get writer(){return t("m_496366aa31cf")},get editor(){return t("m_15d82eb3de76")},get memory(){return t("m_de7953232eda")}}[role])))}
  }
  link.onclick=event=>{if(state.dirty||state.saving){event.preventDefault();document.dispatchEvent(new CustomEvent('workspace-navigation-blocked'));void import('./api.js').then(({notice})=>notice(msg("m_df05df152938"),'warning'))}};
  document.addEventListener('workspace-operation-error',event=>show({brief:'planner',draft:'writer',edit:'editor',memory:'memory',prepare:'planner'}[event.detail.stage]));
  document.addEventListener('workspace-readiness',()=>{
    const operation={plan:'brief',brief:'draft',draft:'edit_loop',prose:'memory'}[state.mode];
    const result=state.workspaceReadiness?.operations[operation];
    if(result&&!result.ready&&/контекст|reasoning|токен|налашт|модель|timeout/i.test(result.reason||''))show({brief:'planner',draft:'writer',edit_loop:'editor',memory:'memory'}[operation]);
    else if(state.workspaceRun?.state!=='failed')link.hidden=true;
  });
  document.addEventListener('workspace-run-state',event=>{
    const run=event.detail,task=run.tasks?.[run.cursor];
    if(run.state==='failed'||run.warning)show(run.impact?.protocol===3?(run.impact.phase==='memory_refresh'||run.impact.phase==='prepare'?'memory':'planner'):run.request.mode==='edit_loop'?'editor':{brief:'planner',draft:'writer',edit:'editor',memory:'memory',prepare:'planner'}[task?.stage||run.request.stage||run.request.mode]);
    else link.hidden=true;
  });
  document.addEventListener('scene-selected',()=>{link.hidden=true});
  let restored=false;
  async function restorePosition(){
    if(restored||!state.view||!state.scene)return;restored=true;
    const target=resolveWorkspacePosition(state.view.scenes,initialWorkspacePosition);
    // Only the initial automatic buffer can be restored; never replace newer input/navigation.
    if(!target||state.scene.id!==target.scene.id||state.bufferEpoch!==1||state.mode!=='plan'||state.dirty||state.saving)return;
    if(target.material!=='plan')await invokeWorkspaceCommand('show',target.material);
  }
  const restore=()=>restorePosition().catch(error=>import('./api.js').then(({notice})=>notice(error.message,'error')));
  document.addEventListener('story-refreshed',restore);
  void restore();
}
