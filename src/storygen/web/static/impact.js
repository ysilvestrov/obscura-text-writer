import {t,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh,selectScene} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {usd} from './budget-format.js';
import {compactBudgetText,settingsLink} from './workspace-links.js';

const panel=document.querySelector('#impact-panel'),previewButton=document.querySelector('#impact-preview');
const previewPanel=document.querySelector('#impact-preview-panel'),start=document.querySelector('#impact-start');
const reportBox=document.querySelector('#impact-reports'),limit=document.querySelector('#impact-limit');
let cached=null,preview=null,busy=false,loadEpoch=0,previewController=null;
const PREVIEW_TIMEOUT_MS=120000;
const activeStates=new Set(['queued','running','pause_requested','cancellation_requested']);
const isOpen=r=>r&&(activeStates.has(r.state)||(r.impact?.protocol===3&&['paused','needs_review'].includes(r.state)));
const active=()=>isOpen(state.workspaceRun)||(state.workspaceRuns||[]).some(isOpen);
const node=(tag,text,className)=>{const e=document.createElement(tag);if(text!=null)e.textContent=text;if(className)e.className=className;return e};
const contractLabel=node('label');contractLabel.hidden=true;
const contractName=node('span');uiText(contractName,'textContent',()=>t('review4.method'));
const contractSelect=node('select');contractSelect.id='review-contract-version';
for(const [value,key] of [['3','review4.classic'],['4','review4.evidence']]){const option=node('option');option.value=value;uiText(option,'textContent',()=>t(key));contractSelect.append(option);}
contractLabel.append(contractName,contractSelect);previewButton.before(contractLabel);
contractSelect.onchange=()=>{preview=null;previewPanel.hidden=true;controls();};
function controls(){contractSelect.disabled=busy||state.saving||active();previewButton.disabled=busy||state.saving||active();start.disabled=busy||state.saving||state.dirty||active()||!preview?.ready;}
function renderReports(){
  if(!cached)return;
  uiText(document.querySelector('#impact-count'),'textContent',()=>t('impact.pending_count',{p0:cached.pending.length}));
  reportBox.replaceChildren();
  for(const target of cached.pending.filter(target=>target.blockers.length))reportBox.append(node('p',target.scene_title+' · '+t('impact.'+target.material)+' — '+target.blockers.map(diagnostic).join('; '),'muted'));
  const latest=new Map();for(const report of cached.reports)latest.set(report.scene_id+':'+report.material,report);
  if(!latest.size)return;
  reportBox.append(node('h3',t('impact.history')));
  for(const report of [...latest.values()].reverse()){
    const article=node('article',null,'impact-report');article.dataset.current=String(report.current);article.dataset.verdict=report.verdict;
    article.append(node('h4',report.scene_title+' · '+t('impact.'+report.material)),node('p',report.current?t('impact.'+report.verdict):t('impact.outdated'),'impact-verdict'),node('p',report.explanation));
    if(report.protocol===2)article.append(node('p',t('impact.proof_parts',{p0:report.proof_count}),'muted'));
    if(report.delta){const details=node('details');details.append(node('summary',t('impact.delta')));if(!report.delta.items.length)details.append(node('p',t('impact.delta_empty')));for(const item of report.delta.items){details.append(node('p',item.explanation));for(const evidence of item.evidence){const source=report.sources[evidence.source_id];details.append(node('p',(source?.label?(source.author_label?source.label:diagnostic(source.label))+' · ':'')+t(source?.side==='old'?'impact.old':'impact.new'),'muted'),node('blockquote',evidence.quote));}}article.append(details);}
    for(const finding of report.findings){
      const item=node('div',null,'impact-finding');item.append(node('blockquote',finding.target_quote),node('p',finding.explanation));
      for(const evidence of finding.evidence){const source=report.sources[evidence.source_id];item.append(node('p',(source?.label?(source.author_label?source.label:diagnostic(source.label))+' · ':'')+t(source?.side==='old'?'impact.old':'impact.new'),'muted'),node('blockquote',evidence.quote));}
      article.append(item);
    }
    if(report.memory_check_current&&report.memory_semantic_impact!=='unchecked')article.append(node('p',t('impact.memory_'+report.memory_semantic_impact)),node('p',report.memory_explanation));
    if(report.memory_evidence_status==='invalid')article.append(node('p',t('impact.memory_invalid'),'muted'));
    if(report.memory_evidence_status==='historical')article.append(node('p',t('impact.memory_historical'),'muted'));
    article.append(node('p',t(report.memory_needs_update?'impact.memory_update':'impact.memory'),'muted'));
    const actions=node('div',null,'actions'),open=node('button',t('impact.open'),'secondary');open.type='button';
    open.onclick=async()=>{try{const scene=state.view.scenes.find(s=>s.id===report.scene_id);if(!scene)return;await selectScene(scene);if(state.scene?.id===scene.id&&!state.dirty)await invokeWorkspaceCommand('show',report.material);}catch(error){notice(error.message,'error')}};actions.append(open);
    if(report.current){const reject=node('button',t('impact.reject'),'secondary');reject.type='button';reject.dataset.rejectImpact=report.id;reject.onclick=async()=>{try{await api(`/api/stories/${state.storyId}/impact/${report.id}/reject`,json('POST',{}));await refresh();await load();}catch(error){notice(error.message,'error')}};actions.append(reject);}
    article.append(actions);reportBox.append(article);
  }
}
async function load(){
  const epoch=++loadEpoch;
  try{const data=await api(`/api/stories/${state.storyId}/impact`);if(epoch!==loadEpoch)return;cached=data;const capable=data.review_protocols?.includes(3);contractLabel.hidden=!data.review_contract_versions?.includes(4);panel.dataset.reviewProtocol=capable?'3':'unsupported';panel.hidden=!capable;renderReports();controls();}
  catch(error){if(epoch===loadEpoch&&panel.open)notice(error.message,'error');}
}
previewButton.onclick=async()=>{
  if(busy)return;
  if(state.dirty){if(!confirm(t('impact.save_first')))return;try{await invokeWorkspaceCommand('save');}catch(error){notice(error.message,'error');return;}if(state.dirty||state.saving)return;}
  const link=document.querySelector('#impact-settings');link.hidden=false;link.href=settingsLink(state.storyId,state.scene?.id,state.mode,'planner')||`/stories/${state.storyId}/settings?role=planner#role-planner`;
  busy=true;preview=null;controls();
  const controller=new AbortController();previewController=controller;
  const began=Date.now();let timedOut=false;
  previewPanel.hidden=false;previewPanel.setAttribute('aria-busy','true');start.hidden=true;
  document.querySelector('#impact-targets').replaceChildren();document.querySelector('#impact-warnings').replaceChildren();
  document.querySelector('#impact-limit-label').hidden=true;document.querySelector('#impact-cost').textContent='';
  uiText(document.querySelector('#impact-progress'),'textContent',()=>t('impact.loading_help'));
  const elapsed=()=>uiText(document.querySelector('#impact-preview-info'),'textContent',()=>t('impact.loading_elapsed',{p0:Math.floor((Date.now()-began)/1000)}));
  elapsed();const ticker=setInterval(elapsed,1000);
  const timeout=setTimeout(()=>{timedOut=true;controller.abort();},PREVIEW_TIMEOUT_MS);
  try{
    preview=await api(`/api/stories/${state.storyId}/review/preview`,{...json('POST',cached?.review_contract_versions?.includes(4)?{review_contract_version:Number(contractSelect.value)}:{}),signal:controller.signal});
    if(controller.signal.aborted)throw new DOMException('Aborted','AbortError');
    if(!preview.ready)throw new Error(preview.reason||t('impact.none'));
    const prepared=preview;
    uiText(document.querySelector('#impact-preview-info'),'textContent',()=>(prepared.protocol===3?t('review.preview',{p0:prepared.model,p1:prepared.calls}):t('impact.calls',{p0:prepared.model,p1:prepared.calls}))+(prepared.protocol===2?' · '+t('impact.wire',{p0:prepared.wire_schema_version||1})+' · '+t('impact.parts',{p0:prepared.part_counts.delta+prepared.part_counts.check,p1:prepared.part_counts.reduce_delta+prepared.part_counts.reduce_check+prepared.part_counts.reduce_memory}):''));
    const targets=document.querySelector('#impact-targets');targets.replaceChildren();for(const target of preview.plan.targets){const item=node('li');uiText(item,'textContent',()=>target.scene_title+' · '+t('impact.'+target.material)+(prepared.basis_modes?.[target.version_id]?' · '+t('review.basis.'+prepared.basis_modes[target.version_id]):'')+(target.blockers.length?' — '+target.blockers.map(diagnostic).join('; '):''));targets.append(item);}
    const warnings=document.querySelector('#impact-warnings');warnings.replaceChildren();for(const warning of preview.warnings||[]){const item=node('li');uiText(item,'textContent',()=>diagnostic(warning));warnings.append(item);}
    const paid=!!preview.paid||preview.upper_cost_nanos!=null;document.querySelector('#impact-limit-label').hidden=!paid;
    if(paid)limit.value=preview.upper_cost_nanos==null?'':(preview.upper_cost_nanos/1e9).toFixed(9);
    uiText(document.querySelector('#impact-cost'),'textContent',()=>paid?(prepared.upper_cost_nanos==null?t('review.paid_help'):t('impact.upper',{p0:usd(prepared.upper_cost_nanos)})):t('impact.local'));
    if(prepared.contract_version===4&&prepared.initial_search_upper_cost_nanos!=null)uiText(document.querySelector('#impact-cost'),'textContent',()=>t('review4.initial_upper',{p0:usd(prepared.initial_search_upper_cost_nanos)})+' '+t('review.paid_help'));
    previewPanel.hidden=false;start.hidden=false;
    document.querySelector('#impact-progress').textContent='';
  }catch(error){
    preview=null;previewPanel.hidden=true;
    if(controller.signal.aborted){
      const key=timedOut?'impact.preview_timeout':'impact.preview_cancelled';
      uiText(document.querySelector('#impact-progress'),'textContent',()=>t(key));
      if(timedOut)notice(t(key),'error');
    }else{
      uiText(document.querySelector('#impact-progress'),'textContent',()=>diagnostic(error.message));notice(error.message,'error');
    }
  }finally{
    clearInterval(ticker);clearTimeout(timeout);previewController=null;previewPanel.setAttribute('aria-busy','false');busy=false;controls();
  }
};
start.onclick=async()=>{
  if(!preview||busy)return;if(state.dirty||state.saving){notice(t('impact.unsaved'),'warning');return;}
  busy=true;controls();
  try{const run=await api(`/api/stories/${state.storyId}/review`,json('POST',{request_id:crypto.randomUUID(),fingerprint:preview.plan.fingerprint,...(preview.contract_version===4?{review_contract_version:4}:{}),budget_limit_usd:preview.paid||preview.upper_cost_nanos!=null?limit.value||null:null}));previewPanel.hidden=true;preview=null;document.dispatchEvent(new CustomEvent('run-enqueued',{detail:run}));notice(t('impact.queued'));}
  catch(error){notice(error.message,'error');}finally{busy=false;controls();}
};
document.querySelector('#impact-cancel-preview').onclick=()=>{if(previewController){previewController.abort();return;}preview=null;previewPanel.hidden=true;controls();};
panel.addEventListener('toggle',()=>{if(panel.open)void load();});
document.addEventListener('story-refreshed',()=>{if(panel.open)void load();else if(state.view?.impact_status){const count=Object.values(state.view.impact_status).filter(s=>s.prose==='pending'||s.prose==='changes_required'||s.brief==='pending'||s.brief==='changes_required').length;uiText(document.querySelector('#impact-count'),'textContent',()=>t('impact.pending_count',{p0:count}));}controls();});
document.addEventListener('workspace-run-state',event=>{const run=event.detail;if(run.request?.mode==='impact'){uiText(document.querySelector('#impact-progress'),'textContent',()=>(run.impact?.protocol===3?t('review.progress',{p0:run.impact.scene_cursor,p1:run.tasks.length,p2:run.impact.order.length}):t('impact.progress',{p0:run.cursor,p1:run.tasks.length}))+(run.impact?.protocol===2&&run.tasks[run.cursor]?' · '+t('impact.phase.'+run.tasks[run.cursor].phase):'')+' · '+compactBudgetText(state.workspaceBudgetData));if(!activeStates.has(run.state))void load();}controls();});
document.addEventListener('editor-state-changed',controls);
document.addEventListener('ui-locale-changed',()=>{renderReports();controls();});
controls();

void load();
