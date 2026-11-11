import {confirmDialog} from './dialogs.js';
import {t,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';

const host=document.querySelector('#review-session');
let current=null,session=null,busy=false,epoch=0,opened=null,policies=null;
const drafts=new Map();
const node=(tag,text,cls)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(cls)e.className=cls;return e;};
const blocked=()=>busy||state.dirty||state.saving||(state.workspaceRuns||[]).some(r=>{
  const live=r.id===state.workspaceRun?.id?state.workspaceRun:r.id===session?.id?session:r;
  return ['queued','running','pause_requested','cancellation_requested'].includes(live.state);
});
function button(label,fn,primary=false){const b=node('button',t(label),primary?'':'secondary');b.type='button';b.disabled=blocked();b.onclick=async()=>{if(blocked())return;const hadFocus=document.activeElement===b;busy=true;render();if(hadFocus){host.tabIndex=-1;host.focus()}try{await fn();}catch(e){notice(e.message,'error');}finally{busy=false;await load();}};return b;}
async function command(action,choices={}){
  const result=await api(`/api/stories/${state.storyId}/review/${session.id}/${action}`,json('POST',{operation_id:crypto.randomUUID(),fingerprint:current.fingerprint,choices}));
  await refresh();
  if(result.state==='queued'){const data=await api(`/api/runs/${session.id}`);document.dispatchEvent(new CustomEvent('run-enqueued',{detail:data.run}));}
}
async function openScene(){const scene=state.view.scenes.find(s=>s.id===current.scene_id);if(!scene)return;await selectScene(scene);if(state.scene?.id===scene.id&&!state.dirty)await invokeWorkspaceCommand('show',scene.heads.prose?'prose':'brief');}
async function priority(material,preferred,superseded,revokeId=null){
  const sceneId=current?.scene_id,revision=policies?.authority_revisions[material],fingerprint=current?.fingerprint;
  if(!await confirmDialog(t(revokeId?'review4.revoke_confirm':'review4.priority_confirm')))return;
  if(current?.scene_id!==sceneId||current?.fingerprint!==fingerprint||policies?.authority_revisions[material]!==revision||state.dirty||state.saving)return;
  await api(`/api/stories/${state.storyId}/review/priorities/${sceneId}`,json('POST',{
    material,expected_revision:revision,operation_id:crypto.randomUUID(),
    preferred,superseded,revoke_id:revokeId
  }));
  await refresh();
}
// #89: in the workspace the card shows only while the session waits for the author; the revision page shows it always.
const attentionOnly=host?.dataset?.scope==='attention';
const waiting=run=>['queued','running','paused','needs_review','pause_requested','cancellation_requested','interrupted','alternative','failed'].includes(run?.state);
function render(){
  host.replaceChildren();host.hidden=!session||(attentionOnly&&!waiting(session));
  if(attentionOnly){const box=host.closest?.('#review-attention');if(box)box.hidden=host.hidden}
  if(host.hidden)return;
  host.append(node('h3',t('review.title')));
  host.append(node('p',t('review.scene_progress',{p0:Math.min(session.impact.scene_cursor+1,session.tasks.length),p1:session.tasks.length})));
  if(session.error)host.append(node('p',diagnostic(session.error)));
  if(session.state==='alternative')host.append(node('p',t('review.changed')));
  const runActions=node('div',null,'actions');host.append(runActions);
  if(['paused','failed','interrupted'].includes(session.state))runActions.append(button('review.retry',async()=>{
    const runId=session.id,runState=session.state;
    if(!await confirmDialog(t('review.retry_confirm')))return;
    if(session?.id!==runId||session?.state!==runState||state.dirty||state.saving)return;
    const run=await api(`/api/runs/${runId}/resume`,json('POST',{repeat_interrupted:runState!=='paused'}));
    document.dispatchEvent(new CustomEvent('run-enqueued',{detail:run}));
  }));
  if(['queued','running','paused','needs_review','interrupted','alternative'].includes(session.state)){
    const cancel=node('button',t('review.cancel'),'secondary');cancel.type='button';cancel.disabled=busy;
    cancel.onclick=async()=>{busy=true;render();try{await api(`/api/runs/${session.id}/cancel`,json('POST',{}));await refresh();}catch(e){notice(e.message,'error');}finally{busy=false;await load();}};
    runActions.append(cancel);
  }
  if(!current?.report){host.append(node('p',t(session.state==='completed'?'review.completed':'review.working')));return;}
  const reviewing=session.state==='needs_review'&&['awaiting_author','author_editing'].includes(current.phase)&&!current.changed_while_waiting;
  const evidence=current.report.schema_version===4;
  if(evidence){
    host.append(node('p',t(current.report.execution_state==='complete'?'review4.complete':'review4.partial')));
    if(current.report.execution_state==='complete'&&!current.report.concerns.length)host.append(node('p',t('review4.author_clean'),'muted'));
    if(current.report.diagnostics.length)host.append(node('p',t('review4.diagnostics',{p0:current.report.diagnostics.length}),'muted'));
    if(current.report.unresolved_task_ids?.length){
      const details=node('details');details.open=true;details.append(node('summary',t('review4.unfinished_parts')));
      const list=node('ul');
      for(const id of current.report.unresolved_task_ids){const spec=current.report.part_specs[id];if(spec)list.append(node('li',t('review4.phase.'+spec.phase)+(spec.material?' · '+t('impact.'+spec.material):'')));}
      details.append(list);host.append(details);
    }
    if(policies?.priorities.length){
      const details=node('details');details.append(node('summary',t('review4.priorities')));
      for(const decision of policies.priorities){
        details.append(node('p',t('impact.'+decision.material)),node('blockquote',policies.statements[decision.preferred_statement_id].quote));
        details.append(button('review4.revoke',()=>priority(decision.material,null,null,decision.id)));
      }host.append(details);
    }
  }
  host.append(node('h4',current.report.targets[0]?.scene_title||''));
  const modes=current.report.coverage?.plan?.basis_modes||{};
  for(const target of current.report.targets){
    const mode=modes[target.version_id]||'historical_delta';
    host.append(node('p',t('impact.'+target.material)+' · '+t('review.basis.'+mode),'muted'));
  }
  if(Object.values(modes).includes('current_consistency'))host.append(node('p',t('review.current_basis_notice'),'muted'));
  if(current.phase!=='partial_result')host.append(node('p',t('review.phase.'+current.phase)));
  if(current.changed_while_waiting)host.append(node('p',t('review.changed')));
  const actions=node('div',null,'actions');actions.append(button('review.open',openScene));host.append(actions);
  const choices=drafts.get(current.report.id)||{...current.dispositions};drafts.set(current.report.id,choices);
  for(const concern of current.report.concerns){
    const item=node('article',null,'review-concern');item.dataset.concern=concern.id;
    if(evidence)item.append(node('h4',t('review4.'+concern.subtype)));
    item.append(node('p',concern.message,'review-concern-message'));
    if(evidence){
      const statements=concern.statement_ids.map(id=>current.report.statements[id]);
      for(const statement of statements)item.append(node('p',t(statement.role==='source'?'review.source':'review.target'),'muted'),node('blockquote',statement.quote));
      if(concern.subtype==='premise_conflict'&&statements.length===2&&statements.every(s=>s.role==='source')&&!current.changed_while_waiting){
        const actions=node('div',null,'actions');
        for(let index=0;index<2;index++){
          const b=button(index===0?'review4.prefer_first':'review4.prefer_second',()=>priority(concern.material,statements[index],statements[1-index]));
          b.dataset.priorityChoice=String(index);actions.append(b);
        }item.append(actions);
      }
    }
    for(const [ids,label] of evidence?[]:[[concern.target_refs,'review.target'],[concern.source_refs,'review.source']]){
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
    const listed=[...sessions].reverse().find(r=>['queued','running','paused','needs_review','pause_requested','cancellation_requested'].includes(r.state))||sessions.at(-1);
    const run=listed?(await api(`/api/runs/${listed.id}`)).run:null;
    const p=run?await api(`/api/stories/${state.storyId}/review/${run.id}`):null;
    const policy=p?.report?.schema_version===4?await api(`/api/stories/${state.storyId}/review/priorities/${p.scene_id}`):null;
    if(ticket!==epoch)return;session=run;current=p;policies=policy;render();
    const attention=run&&['needs_review','failed','interrupted','paused','alternative'].includes(run.state);
    const marker=p?.report?.id||run?.id+':'+run?.state;
    if(attention&&opened!==marker&&!state.dirty&&!state.saving){opened=marker;const panel=document.querySelector('#impact-panel');if(panel)panel.open=true;}
  }catch(e){if(ticket===epoch)notice(diagnostic(e.message),'error');}
}
document.addEventListener('story-refreshed',()=>void load());
document.addEventListener('workspace-run-state',event=>{if(event.detail.impact?.protocol===3)void load();});
document.addEventListener('editor-state-changed',render);
document.addEventListener('workspace-readiness',render);
document.addEventListener('ui-locale-changed',render);
void load();
