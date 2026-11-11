// R20-WORKSPACE: the run line above the editor collapses into one summary line so it never pushes the editor down.
// Pure rules; runs.js only renders them.

// State, planned models when known, and a mark when a warning sits in the collapsed details.
export function runSummaryText(run,stateLabel){
  const plan=run?.planned_telemetry;
  const models=plan?[...new Set([...Object.values(plan.roles||{}),...(plan.evaluator?[plan.evaluator]:[])].map(v=>`${v.provider} / ${v.model}`))].join(', '):'';
  // A failed run shows its error expanded; any other run marks a hidden warning or error.
  return [stateLabel,models,(run?.warning||run?.error)&&run.state!=='failed'?'⚠':''].filter(Boolean).join(' · ');
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
