import assert from 'node:assert/strict';
import {EvaluatorDraft} from '../../../src/storygen/web/static/evaluator-form-state.js';
const draft=new EvaluatorDraft({config:{provider:'codex_cli',max_input_chars:100000},context_tokens:128000,policy:'report'});
draft.setRaw('{');let calls=[];
const result=await draft.savePolicy('off',async policy=>{calls.push(policy);return {policy}});
assert.deepEqual(calls,['off']);assert.equal(result.policy,'off');assert.equal(draft.current.policy,'off');assert.equal(draft.rawText,'{');assert.equal(draft.rawPending,true);
await assert.rejects(()=>draft.savePolicy('report',async()=>{throw Error('network')}));assert.equal(draft.current.policy,'off');assert.equal(draft.rawText,'{');
console.log('Immediate policy update preserves unfinished JSON and failed request state');
