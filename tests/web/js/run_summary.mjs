import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {runSummaryText,runNoticeMark,runExpanded,toggleRunExpansion,syncRunPrefs,usageUsd,addRunCost,runCostText}=await import(pathToFileURL(root+'/src/storygen/web/static/run-summary.js'));

// The one-line summary: state, the planned models when known, a warning mark when the run has a warning.
const plan={roles:{writer:{provider:'venice',model:'gemma'}},evaluator:{provider:'local',model:'judge'}};
assert.equal(runSummaryText({state:'completed',planned_telemetry:plan},'Завершено'),'Завершено · venice / gemma, local / judge');
assert.equal(runSummaryText({state:'completed',planned_telemetry:plan,warning:'Часову доступність не перевірено'},'Завершено'),'Завершено · venice / gemma, local / judge');
assert.equal(runNoticeMark({state:'completed',warning:'w'}),'⚠');
assert.equal(runNoticeMark({state:'completed'}),'');
assert.equal(runSummaryText({state:'running'},'Генерація'),'Генерація');
assert.equal(runSummaryText({state:'completed',planned_telemetry:{roles:{}}},'Завершено'),'Завершено');
// A failed run shows its error below, expanded; the mark is for warnings that would otherwise stay hidden.
assert.equal(runSummaryText({state:'failed',error:'boom',warning:'w'},'Помилка'),'Помилка');
assert.equal(runNoticeMark({state:'failed',error:'boom',warning:'w'}),'');

// Expansion: collapsed by default, a failed run opens by itself even after it was collapsed while running.
let prefs={expandedRun:null,collapsedFailure:null};
const running={id:'r1',state:'running'},failed={id:'r1',state:'failed'},next={id:'r2',state:'running'};
assert.equal(runExpanded(running,prefs),false);
prefs=toggleRunExpansion(running,prefs);assert.equal(runExpanded(running,prefs),true);
prefs=toggleRunExpansion(running,prefs);assert.equal(runExpanded(running,prefs),false);
assert.equal(runExpanded(failed,prefs),true,'entering failed discloses the error despite the earlier collapse');
prefs=toggleRunExpansion(failed,prefs);assert.equal(runExpanded(failed,prefs),false,'a shown error can be collapsed');
assert.equal(runExpanded(failed,prefs),false,'and stays collapsed for that run');
assert.equal(runExpanded({id:'r2',state:'failed'},prefs),true,'a new failed run opens again');
assert.equal(runExpanded(next,prefs),false,'a new run starts collapsed');
prefs=toggleRunExpansion(failed,prefs);assert.equal(runExpanded(failed,prefs),true,'collapsing again is undone by a second click');

// Review fix: one model used by several roles is named once, so the line stays short.
assert.equal(runSummaryText({state:'running',planned_telemetry:{roles:{writer:{provider:'v',model:'m'},editor:{provider:'v',model:'m'}}}},'Генерація'),'Генерація · v / m');
// Review fix: an error on a run that did not fail (cancelled, interrupted) is marked as well.
assert.equal(runNoticeMark({state:'cancelled',error:'boom'}),'⚠');
// Review fix: a resumed run keeps its id; when it fails again, the new error opens despite the earlier collapse.
let resumed={expandedRun:null,collapsedFailure:null};
resumed=toggleRunExpansion({id:'r9',state:'failed'},resumed);assert.equal(runExpanded({id:'r9',state:'failed'},resumed),false);
resumed=syncRunPrefs({id:'r9',state:'running'},resumed);
assert.equal(runExpanded({id:'r9',state:'failed'},resumed),true,'failing again after resume discloses the error');
assert.deepEqual(syncRunPrefs({id:'r9',state:'failed'},{expandedRun:null,collapsedFailure:'r9'}),{expandedRun:null,collapsedFailure:'r9'},'a failed run keeps its collapse');

// Owner request: the summary shows dollars spent (total / last call); raw provider usage goes to a tooltip.
assert.equal(usageUsd({cost:{usd:0.0021,diem:0}}),0.0021,'Venice reports cost.usd');
assert.equal(usageUsd({cost:0.5}),0.5,'OpenRouter reports a number');
assert.equal(usageUsd({prompt_tokens:3}),null);
let costs=null;
costs=addRunCost(costs,'r1','a1',{cost:{usd:0.0021}});
costs=addRunCost(costs,'r1','a2',{cost:{usd:0.0030}});
costs=addRunCost(costs,'r1','a2',{cost:{usd:0.0030}});
assert.equal(runCostText(costs,'r1'),'$0.0051 / $0.0030','a replayed event of the same attempt is counted once');
assert.deepEqual(costs.lastUsage,{cost:{usd:0.0030}});
assert.equal(runCostText(costs,'r2'),'','costs belong to their run');
assert.equal(runCostText(addRunCost(costs,'r2','b1',{cost:{usd:1.5}}),'r2'),'$1.50 / $1.50','a new run starts from zero');
assert.equal(runCostText(addRunCost(null,'r3','c1',{prompt_tokens:3}),'r3'),'$—','usage without a price stays reachable through the tooltip');
assert.equal(addRunCost(null,'r4','d1',{}),null,'no usage, nothing to show');
console.log('ok');
