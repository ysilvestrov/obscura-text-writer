// OPENROUTER-REASONING-S04: the role form offers only what the model's catalog row allows.
import assert from 'node:assert/strict';
import {pathToFileURL} from 'node:url';
globalThis.document={querySelector:()=>null,addEventListener:()=>{}};
const {reasoningChoices,providerReasoning}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/openrouter-reasoning.js'));
const {setLocale}=await import(pathToFileURL(process.argv[2]+'/src/storygen/web/static/i18n.js'));
const values=choices=>choices.map(c=>c.value);
const glm={mandatory:true,default_enabled:true,efforts:['max','high','low'],default_effort:'max'};
// Mandatory reasoning: no "off", only the listed levels, lowest first.
assert.deepEqual(values(reasoningChoices(glm,'')),['','low','high','max']);
// Disableable without a level choice (qwen3.7-plus): default and off only.
assert.deepEqual(values(reasoningChoices({mandatory:false,default_enabled:true,efforts:[]},'')),['','none']);
// efforts null: every level.
assert.deepEqual(values(reasoningChoices({mandatory:false,efforts:null},'')),['','none','minimal','low','medium','high','xhigh','max']);
// A saved value the model does not allow stays visible and marked, never silently dropped.
const kept=reasoningChoices(glm,'none');
assert.deepEqual(values(kept),['','low','high','max','none']);
assert.equal(kept.at(-1).unsupported,true);
assert.ok(!kept.slice(0,-1).some(c=>c.unsupported));
// Catalog not loaded: default plus the saved value, unmarked (nothing is known yet).
assert.deepEqual(reasoningChoices(undefined,'low').map(c=>[c.value,!!c.unsupported]),[['',false],['low',false]]);
assert.deepEqual(values(reasoningChoices(undefined,'')),['']);
// A model without reasoning: only the default; a saved level is marked.
assert.deepEqual(reasoningChoices(null,'low').map(c=>[c.value,!!c.unsupported]),[['',false],['low',true]]);
// Labels follow the locale.
setLocale('en');
assert.equal(reasoningChoices(glm,'')[0].label,'Model default');
assert.equal(reasoningChoices({mandatory:false,efforts:[]},'')[1].label,'Off');
assert.equal(reasoningChoices(glm,'none').at(-1).label,'Off — not supported by the model');
setLocale('uk');
assert.equal(reasoningChoices({mandatory:false,efforts:[]},'')[1].label,'Вимкнено');
// Payload: the value only for OpenRouter; any other provider sends null so the server never sees a stale level.
assert.equal(providerReasoning('openrouter','low'),'low');
assert.equal(providerReasoning('openrouter',''),null);
assert.equal(providerReasoning('venice','low'),null);
assert.equal(providerReasoning('local','none'),null);
console.log('openrouter reasoning check passed');
