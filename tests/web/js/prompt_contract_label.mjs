import assert from 'node:assert/strict';
import {expectedPromptContract} from '../../../src/storygen/web/static/settings-state.js';
const v2={stage:'memory',mode:'evidence_delta',schema_version:2},v3={...v2,schema_version:3};
// Mirrors configure_prompts: a custom memory/evidence_delta/2 prompt keeps /2 on edit and confirm.
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'Власний промпт'),'memory/evidence_delta/2');
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'Змінений власний промпт'),'memory/evidence_delta/2');
// Clearing the text returns the standard prompt, which is v3.
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'  '),'memory/evidence_delta/3');
assert.equal(expectedPromptContract('memory','evidence_delta',v3,true,'Власний'),'memory/evidence_delta/3');
assert.equal(expectedPromptContract('memory','evidence_delta',null,false,'Новий'),'memory/evidence_delta/3');
assert.equal(expectedPromptContract('memory','evidence_delta',v2,false,'Новий'),'memory/evidence_delta/3');
assert.equal(expectedPromptContract('memory','snapshot',v2,true,'Власний'),'memory/snapshot/1');
assert.equal(expectedPromptContract('edit','patches',null,false,''),'edit/patches/1');
// Opt-in upgrade moves a custom /2 prompt to /3 (upgrade_memory_wire); the default keeps /2.
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'текст',true),'memory/evidence_delta/3');
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'текст',false),'memory/evidence_delta/2');
assert.equal(expectedPromptContract('memory','evidence_delta',v2,true,'текст'),'memory/evidence_delta/2');
assert.equal(expectedPromptContract('memory','snapshot',v2,true,'текст',true),'memory/snapshot/1');
console.log('Prompt contract label regressions passed');
