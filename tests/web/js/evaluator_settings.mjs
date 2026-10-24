import assert from 'node:assert/strict';
import {EvaluatorDraft,normalizeEvaluator} from '../../../src/storygen/web/static/evaluator-form-state.js';
import {readConnection} from '../../../src/storygen/web/static/settings-connection.js';
const saved=normalizeEvaluator({config:{provider:'codex_cli',model:null,max_input_chars:100000,temperature:null,timeout_seconds:null},context_tokens:128000,policy:'off'});
let d=new EvaluatorDraft(saved);assert.deepEqual(d.read(),saved);
const connection=readConnection(saved.config,{provider:'codex_cli',model:'',base_url:saved.config.base_url,timeout:'',key_env:saved.config.api_key_env,response_mode:'json_schema',venice_include_system_prompt:false,venice_disable_thinking:false},'evaluator');
assert.equal(connection.model,null);assert.equal(connection.timeout_seconds,null);assert.ok(!Object.hasOwn(connection,'timeout'));
d.setRaw('{bad');assert.equal(d.rawPending,true);assert.throws(()=>d.read(),/JSON/);assert.throws(()=>d.patch({context_tokens:4000}),/JSON/);
d.policySaved('off');assert.equal(d.rawText,'{bad');assert.throws(()=>d.applyRaw());assert.equal(d.current.policy,'off');d.discardRaw();
d.setRaw(JSON.stringify({...saved,policy:'report'}));d.applyRaw();assert.equal(d.current.policy,'off','immediate off must survive later JSON apply');
const calibrated=normalizeEvaluator({...saved,policy:'pause_on_failure',profile:{...saved.profile,calibrated:true,evaluator_fingerprint:'e',calibration_fingerprint:'c'}});
d=new EvaluatorDraft(calibrated);d.patch({config:{...d.current.config,max_output_tokens:7000}});assert.equal(d.calibrationLost(),true);assert.throws(()=>d.read(),/режим/);
d.patch({policy:'report'});assert.equal(d.read().profile.calibrated,true,'server owns downgrade for changed config');
d=new EvaluatorDraft(calibrated);assert.throws(()=>d.patch({profile:{...d.current.profile,min_quote_chars:15}}),/кандидат/);
d.makeCandidate();assert.throws(()=>d.read(),/режим/);d.patch({policy:'report'});d.patch({profile:{...d.current.profile,min_quote_chars:15}});assert.equal(d.read().profile.calibrated,false);
d=new EvaluatorDraft(saved);d.setRaw(JSON.stringify({...saved,profile:{...saved.profile,calibrated:true,evaluator_fingerprint:'fake'}}));assert.throws(()=>d.applyRaw(),/калібрування/);
d=new EvaluatorDraft(saved);d.patch({config:{...d.current.config,temperature:0,timeout_seconds:1}});assert.equal(d.read().config.temperature,0);
assert.throws(()=>new EvaluatorDraft({...saved,context_tokens:1024}).read(),/контекст/);
for(const fields of [{temperature:'0.1'},{venice_disable_thinking:'false'},{model:123}]){
 d=new EvaluatorDraft(saved);d.setRaw(JSON.stringify({...saved,config:{...saved.config,...fields}}));
 assert.throws(()=>d.applyRaw(),'raw types must not be coerced by form controls');assert.deepEqual(d.current,saved);
}
d=new EvaluatorDraft(saved);d.setRaw(JSON.stringify({...saved,profile:{...saved.profile,evaluator_fingerprint:'fake'}}));assert.throws(()=>d.applyRaw(),/калібрування/);
console.log('Evaluator draft, JSON and calibration regressions passed');
