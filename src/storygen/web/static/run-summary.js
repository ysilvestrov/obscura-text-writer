// R20-WORKSPACE: the run line above the editor collapses into one summary line so it never pushes the editor down.
// Pure rules; runs.js only renders them.

// State and planned models when known. The ⚠ mark is separate (runNoticeMark) so truncating a long model list never hides it.
// modeLabel names a run that is not a model stage the author started (MEMORY-CARRY: the model-free carry).
export function runSummaryText(run,stateLabel,modeLabel=''){
  const plan=run?.planned_telemetry;
  const models=plan?[...new Set([...Object.values(plan.roles||{}),...(plan.evaluator?[plan.evaluator]:[])].map(v=>`${v.provider} / ${v.model}`))].join(', '):'';
  return [modeLabel,stateLabel,models].filter(Boolean).join(' · ');
}

// The catalog key of a run's own label, or null for the usual model runs (VALID-LINKS: the auditor's scene check).
const MODE_KEYS={memory_carry:'run.mode_memory_carry',audit:'run.mode_audit'};
export function runModeKey(run){
  if(run?.request?.mode==='audit'&&run.request.audit_scope==='story')return 'run.mode_audit_book';
  return MODE_KEYS[run?.request?.mode]||null;
}

// R-44 book validation: a book run stopped for the author's decision names the scene of its stop (checkpoint.scene_id);
// the summary leads there. A scene no longer in the story view gives no link.
export function stoppedAuditScene(run,scenes){
  if(run?.state!=='needs_review'||run.request?.mode!=='audit'||run.request.audit_scope!=='story')return null;
  const id=run.checkpoint?.scene_id;
  return (id&&(scenes||[]).find(scene=>scene.id===id))||null;
}

// A failed run shows its error expanded; any other run marks a hidden warning or error.
export function runNoticeMark(run){
  return (run?.warning||run?.error)&&run.state!=='failed'?'⚠':'';
}

// A failed run and a run stopped for review (needs_review) share one disclosure rule.
const DISCLOSED=new Set(['failed','needs_review']);

// Collapsed by default. Entering failed or needs_review discloses the error even if the author collapsed this run while it ran;
// only collapsing an error already shown is remembered (until another run).
export function runExpanded(run,{expandedRun,collapsedFailure}){
  if(!run)return false;
  return expandedRun===run.id||(DISCLOSED.has(run.state)&&collapsedFailure!==run.id);
}

// A resumed run keeps its id: once it leaves failed or needs_review, a remembered collapse no longer applies, so failing again opens the new error.
export function syncRunPrefs(run,prefs){
  if(run&&!DISCLOSED.has(run.state)&&prefs.collapsedFailure===run.id)return {...prefs,collapsedFailure:null};
  return prefs;
}

export function toggleRunExpansion(run,prefs){
  if(!run)return prefs;
  if(DISCLOSED.has(run.state))return {...prefs,expandedRun:null,collapsedFailure:runExpanded(run,prefs)?run.id:null};
  return {...prefs,expandedRun:prefs.expandedRun===run.id?null:run.id};
}

// Dollars spent by the run: the summary shows total / last call, the raw provider usage goes to a tooltip.
// Venice reports cost.usd, OpenRouter a number in cost; other providers give no price.
export function usageUsd(usage){
  const cost=usage?.cost,value=typeof cost==='number'?cost:cost?.usd;
  return typeof value==='number'&&Number.isFinite(value)?value:null;
}

// Keyed by attempt so the replayed event stream (reload, reconnect) counts each call once.
export function addRunCost(costs,runId,attemptId,usage){
  if(!usage||!Object.keys(usage).length)return costs;
  const base=costs?.runId===runId?costs:{runId,byAttempt:{},lastUsage:null};
  const key=attemptId??`call-${Object.keys(base.byAttempt).length}`;
  return {runId,byAttempt:{...base.byAttempt,[key]:usageUsd(usage)},lastUsage:usage};
}

export const dollars=value=>`$${value<0.01?value.toFixed(4):value.toFixed(2)}`;
export function runCostText(costs,runId){
  if(costs?.runId!==runId||!costs.lastUsage)return '';
  const known=Object.values(costs.byAttempt).filter(value=>value!==null),last=usageUsd(costs.lastUsage);
  if(!known.length)return '$—';
  return `${dollars(known.reduce((sum,value)=>sum+value,0))} / ${last===null?'$—':dollars(last)}`;
}

// Г8: revealing a run moves the focus to its row, but never out of a field the author is typing in.
export function revealTakesFocus(element){
  return !element?.matches?.('textarea, input, select, [contenteditable]:not([contenteditable="false"])');
}
