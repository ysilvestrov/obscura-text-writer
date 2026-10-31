import {t,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';

const host=document.querySelector('#review-session');
let current=null,session=null,busy=false,epoch=0,opened=null;
const drafts=new Map();
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const blocked=()=>busy||state.dirty||state.saving||(state.workspaceRuns||[]).some(r=>{
  const live=r.id===state.workspaceRun?.id?state.workspaceRun:r.id===session?.id?session:r;
  return ['queued','running','pause_requested','cancellation_requested'].includes(live.state);
});
function button(label,fn,primary=false){const b=node('button',t(label),primary?'':'secondary');b.type='button';b.disabled=blocked();b.onclick=async()=>{if(blocked())return;busy=true;render();try{await fn();}catch(e){notice(e.message,'error');}finally{busy=false;await load();}};return b;}
async function command(action,choices={}){
  const result=await api(`/api/stories/${state.storyId}/review/${session.id}/${action}`,json('POST',{operation_id:crypto.randomUUID(),fingerprint:current.fingerprint,choices}));
  await refresh();
  if(result.state==='queued'){const data=await api(`/api/runs/${session.id}`);document.dispatchEvent(new CustomEvent('run-enqueued',{detail:data.run}));}
}
async function openScene(){const scene=state.view.scenes.find(s=>s.id===current.scene_id);if(!scene)return;await selectScene(scene);if(state.scene?.id===scene.id&&!state.dirty)await invokeWorkspaceCommand('show',scene.heads.prose?'prose':'brief');}
function render(){
  host.replaceChildren();host.hidden=!session;if(!session)return;
  host.append(node('h3',t('review.title')));
  host.append(node('p',t('review.scene_progress',{p0:Math.min(session.impact.scene_cursor+1,session.tasks.length),p1:session.tasks.length})));
  if(session.error)host.append(node('p',diagnostic(session.error)));
  if(session.state==='alternative')host.append(node('p',t('review.changed')));
  const runActions=node('div',null,'actions');host.append(runActions);
  if(['paused','failed','interrupted'].includes(session.state))runActions.append(button('review.retry',async()=>{
    if(!confirm(t('review.retry_confirm')))return;
    const run=await api(`/api/runs/${session.id}/resume`,json('POST',{repeat_interrupted:session.state!=='paused'}));
    document.dispatchEvent(new CustomEvent('run-enqueued',{detail:run}));
  }));
  if(['queued','running','paused','needs_review','interrupted','alternative'].includes(session.state)){
    const cancel=node('button',t('review.cancel'),'secondary');cancel.type='button';cancel.disabled=busy;
    cancel.onclick=async()=>{busy=true;render();try{await api(`/api/runs/${session.id}/cancel`,json('POST',{}));await refresh();}catch(e){notice(e.message,'error');}finally{busy=false;await load();}};
    runActions.append(cancel);
  }
  if(!current?.report){host.append(node('p',t(session.state==='completed'?'review.completed':'review.working')));return;}
  const reviewing=session.state==='needs_review'&&['awaiting_author','author_editing'].includes(current.phase)&&!current.changed_while_waiting;
  host.append(node('h4',current.report.targets[0]?.scene_title||''));
  const modes=current.report.coverage?.plan?.basis_modes||{};
  for(const target of current.report.targets){
    const mode=modes[target.version_id]||'historical_delta';
    host.append(node('p',t('impact.'+target.material)+' · '+t('review.basis.'+mode),'muted'));
  }
  if(Object.values(modes).includes('current_consistency'))host.append(node('p',t('review.current_basis_notice'),'muted'));
  host.append(node('p',t('review.phase.'+current.phase)));
  if(current.changed_while_waiting)host.append(node('p',t('review.changed')));
  const actions=node('div',null,'actions');actions.append(button('review.open',openScene));host.append(actions);
  const choices=drafts.get(current.report.id)||{...current.dispositions};drafts.set(current.report.id,choices);
  for(const concern of current.report.concerns){
    const item=node('article',null,'review-concern');item.dataset.concern=concern.id;
    item.append(node('p',concern.message,'review-concern-message'));
    for(const [ids,label] of [[concern.target_refs,'review.target'],[concern.source_refs,'review.source']]){
      if(!ids.length)continue;
      const details=node('details');details.open=true;details.append(node('summary',t(label)));
      for(const id of ids){const row=current.report.registry[id];if(row){if(row.kind==='source')details.append(node('p',(row.author_label?row.label:diagnostic(row.label))+' · '+t(row.side==='old'?'impact.old':'impact.new'),'muted'));details.append(node('blockquote',row.text==='null'?t('review.no_value'):row.text));}}item.append(details);
    }
    if(reviewing&&current.phase==='awaiting_author'){
      const label=node('label',t('review.decision')),select=node('select');select.dataset.decision=concern.id;
      for(const [value,key] of [['','review.choose'],['reject','review.reject'],['fix','review.fix']]){const option=node('option',t(key));option.value=value;select.append(option);}
      select.value=choices[concern.id]||'';select.disabled=blocked();
      select.onchange=()=>{choices[concern.id]=select.value;apply.disabled=blocked()||current.report.concerns.some(c=>!choices[c.id]);};label.append(select);item.append(label);
    }else if(current.dispositions[concern.id])item.append(node('p',t('review.'+current.dispositions[concern.id]),'muted'));
    host.append(item);
  }
  if(state.dirty||state.saving)host.append(node('p',t('review.save_first'),'muted'));
  if(!reviewing)return;
  const footer=node('div',null,'actions');host.append(footer);
  const apply=button('review.apply',()=>command('decide',choices),true);
  if(current.phase==='awaiting_author'){
    apply.disabled=blocked()||current.report.concerns.some(c=>!choices[c.id]);footer.append(apply);
    footer.append(button('review.reject_all',()=>command('decide',Object.fromEntries(current.report.concerns.map(c=>[c.id,'reject'])))));
  }else{
    host.append(node('p',t('review.edit_help')));
    footer.append(button('review.finish',()=>command('finish'),true));
  }
}
export async function load(){
  const ticket=++epoch;
  try{
    const data=await api(`/api/stories/${state.storyId}/runs`);
    const sessions=data.runs.filter(r=>r.impact?.protocol===3);
    const run=[...sessions].reverse().find(r=>['queued','running','paused','needs_review','pause_requested','cancellation_requested'].includes(r.state))||sessions.at(-1);
    const p=run?await api(`/api/stories/${state.storyId}/review/${run.id}`):null;
    if(ticket!==epoch)return;session=run;current=p;render();
    const attention=run&&['needs_review','failed','interrupted','paused','alternative'].includes(run.state);
    const marker=p?.report?.id||run?.id+':'+run?.state;
    if(attention&&opened!==marker&&!state.dirty&&!state.saving){opened=marker;document.querySelector('#impact-panel').open=true;}
  }catch(e){if(ticket===epoch)notice(diagnostic(e.message),'error');}
}
document.addEventListener('story-refreshed',()=>void load());
document.addEventListener('workspace-run-state',event=>{if(event.detail.impact?.protocol===3)void load();});
document.addEventListener('editor-state-changed',render);
document.addEventListener('workspace-readiness',render);
document.addEventListener('ui-locale-changed',render);
void load();
