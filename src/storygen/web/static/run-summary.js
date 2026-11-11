// R20-WORKSPACE: the run line above the editor collapses into one summary line so it never pushes the editor down.
// Pure rules; runs.js only renders them.

// State and planned models when known. The ⚠ mark is separate (runNoticeMark) so truncating a long model list never hides it.
export function runSummaryText(run,stateLabel){
  const plan=run?.planned_telemetry;
  const models=plan?[...new Set([...Object.values(plan.roles||{}),...(plan.evaluator?[plan.evaluator]:[])].map(v=>`${v.provider} / ${v.model}`))].join(', '):'';
  return [stateLabel,models].filter(Boolean).join(' · ');
}

// A failed run shows its error expanded; any other run marks a hidden warning or error.
export function runNoticeMark(run){
  return (run?.warning||run?.error)&&run.state!=='failed'?'⚠':'';
}

// Collapsed by default. Entering failed discloses the error even if the author collapsed this run while it ran;
// only collapsing an error already shown is remembered (until another run).
export function runExpanded(run,{expandedRun,collapsedFailure}){
  if(!run)return false;
  return expandedRun===run.id||(run.state==='failed'&&collapsedFailure!==run.id);
}

// A resumed run keeps its id: once it leaves failed, a remembered collapse no longer applies, so failing again opens the new error.
export function syncRunPrefs(run,prefs){
  if(run&&run.state!=='failed'&&prefs.collapsedFailure===run.id)return {...prefs,collapsedFailure:null};
  return prefs;
}

export function toggleRunExpansion(run,prefs){
  if(!run)return prefs;
  if(run.state==='failed')return {...prefs,expandedRun:null,collapsedFailure:runExpanded(run,prefs)?run.id:null};
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

const dollars=value=>`$${value<0.01?value.toFixed(4):value.toFixed(2)}`;
export function runCostText(costs,runId){
  if(costs?.runId!==runId||!costs.lastUsage)return '';
  const known=Object.values(costs.byAttempt).filter(value=>value!==null),last=usageUsd(costs.lastUsage);
  if(!known.length)return '$—';
  return `${dollars(known.reduce((sum,value)=>sum+value,0))} / ${last===null?'$—':dollars(last)}`;
}
