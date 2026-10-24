import {settingsLink,returnLink} from './workspace-links.js';

const settings=document.querySelector('.settings-page');
if(settings){
  const link=document.querySelector('#settings-return')||document.createElement('a');link.textContent='← Повернутися до сцени';
  link.href=returnLink(settings.dataset.storyId,location.search);if(!link.parentElement)settings.prepend(link);
  const role=new URLSearchParams(location.search).get('role');
  let roleFocused=false;
  function focusRole(){if(roleFocused)return;if(!['planner','writer','editor','memory'].includes(role))return;document.dispatchEvent(new CustomEvent('settings-show-role',{detail:role}));const form=settings.querySelector(`[data-role="${role}"]`);if(form){roleFocused=true;form.id='role-'+role;form.querySelector('[name=context_tokens]')?.focus()}}
  document.addEventListener('workspace-settings-loaded',focusRole);
  focusRole();
}
const workspace=document.querySelector('#workspace');
if(workspace){
  const {state}=await import('./editor.js');
  const {invokeWorkspaceCommand}=await import('./workspace-commands.js');
  const link=document.querySelector('#workspace-error-settings');
  function show(role){
    const href=state.scene&&settingsLink(state.storyId,state.scene.id,state.mode,role);
    link.hidden=!href;if(href){link.href=href;link.textContent='Налаштувати '+({planner:'планувальника',writer:'письменника',editor:'редактора',memory:'пам’ять'}[role])}
  }
  link.onclick=event=>{if(state.dirty||state.saving){event.preventDefault();document.dispatchEvent(new CustomEvent('workspace-navigation-blocked'));void import('./api.js').then(({notice})=>notice('Спершу збережіть ручні правки перед налаштуваннями','warning'))}};
  document.addEventListener('workspace-operation-error',event=>show({brief:'planner',draft:'writer',edit:'editor',memory:'memory',prepare:'planner'}[event.detail.stage]));
  document.addEventListener('workspace-readiness',()=>{
    const operation={plan:'brief',brief:'draft',draft:'edit_loop',prose:'memory'}[state.mode];
    const result=state.workspaceReadiness?.operations[operation];
    if(result&&!result.ready&&/контекст|reasoning|токен|налашт|модель|timeout/i.test(result.reason||''))show({brief:'planner',draft:'writer',edit_loop:'editor',memory:'memory'}[operation]);
    else if(state.workspaceRun?.state!=='failed')link.hidden=true;
  });
  document.addEventListener('workspace-run-state',event=>{
    const run=event.detail,task=run.tasks?.[run.cursor];
    if(run.state==='failed'||run.warning)show(run.request.mode==='edit_loop'?'editor':{brief:'planner',draft:'writer',edit:'editor',memory:'memory',prepare:'planner'}[task?.stage||run.request.stage||run.request.mode]);
    else link.hidden=true;
  });
  document.addEventListener('scene-selected',()=>{link.hidden=true});
  let returned=false;
  document.addEventListener('story-refreshed',async()=>{
    if(returned||!state.view)return;returned=true;
    const query=new URLSearchParams(location.search),scene=state.view.scenes.find(s=>s.id===query.get('scene'));
    if(!scene)return;
    const {selectScene}=await import('./editor.js');
    if(state.dirty||state.saving)return;
    await selectScene(scene);
    const mode=query.get('material');if(['plan','brief','draft','review','prose','memory'].includes(mode))await invokeWorkspaceCommand('show',mode);
  });
}
