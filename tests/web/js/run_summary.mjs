import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
const root=process.argv[2];
const {runSummaryText,runExpanded,toggleRunExpansion,syncRunPrefs}=await import(pathToFileURL(root+'/src/storygen/web/static/run-summary.js'));

// The one-line summary: state, the planned models when known, a warning mark when the run has a warning.
const plan={roles:{writer:{provider:'venice',model:'gemma'}},evaluator:{provider:'local',model:'judge'}};
assert.equal(runSummaryText({state:'completed',planned_telemetry:plan},'Завершено'),'Завершено · venice / gemma, local / judge');
assert.equal(runSummaryText({state:'completed',planned_telemetry:plan,warning:'Часову доступність не перевірено'},'Завершено'),'Завершено · venice / gemma, local / judge · ⚠');
assert.equal(runSummaryText({state:'running'},'Генерація'),'Генерація');
assert.equal(runSummaryText({state:'completed',planned_telemetry:{roles:{}}},'Завершено'),'Завершено');
// A failed run shows its error below, expanded; the mark is for warnings that would otherwise stay hidden.
assert.equal(runSummaryText({state:'failed',error:'boom',warning:'w'},'Помилка'),'Помилка');

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
assert.equal(runSummaryText({state:'cancelled',error:'boom'},'Скасовано'),'Скасовано · ⚠');
// Review fix: a resumed run keeps its id; when it fails again, the new error opens despite the earlier collapse.
let resumed={expandedRun:null,collapsedFailure:null};
resumed=toggleRunExpansion({id:'r9',state:'failed'},resumed);assert.equal(runExpanded({id:'r9',state:'failed'},resumed),false);
resumed=syncRunPrefs({id:'r9',state:'running'},resumed);
assert.equal(runExpanded({id:'r9',state:'failed'},resumed),true,'failing again after resume discloses the error');
assert.deepEqual(syncRunPrefs({id:'r9',state:'failed'},{expandedRun:null,collapsedFailure:'r9'}),{expandedRun:null,collapsedFailure:'r9'},'a failed run keeps its collapse');
console.log('ok');
