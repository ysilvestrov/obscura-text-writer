import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {settingsSignature} from './settings-state.js';
import {providerEndpoints} from './settings-connection.js';
export const criterionLabels={get ukrainian(){return t("m_4820959238a5")},get style(){return t("m_f6a2879f703d")},get voice(){return t("m_cb93df94875c")},get plan_fidelity(){return t("m_0c69e7182274")},get continuity(){return t("m_476973cfe93d")},get editorial_preservation(){return t("m_01cf7d93f5cf")}};
const clone=value=>structuredClone(value);
function validateShape(s){
  const c=s.config,p=s.profile,finite=v=>typeof v==='number'&&Number.isFinite(v);
  if(!['off','report','pause_on_failure'].includes(s.policy)||!['local','venice','openrouter','codex_cli'].includes(c.provider)||!['json_schema','prompt_json'].includes(c.response_mode))throw new Error(t("m_22b9eca4b863"));
  if(!Number.isInteger(s.context_tokens)||s.context_tokens<1024||!Number.isInteger(c.max_output_tokens)||c.max_output_tokens<1||c.max_output_tokens>=s.context_tokens)throw new Error(t("m_073491154388"));
  if(c.model!==null&&typeof c.model!=='string'||c.provider!=='codex_cli'&&(typeof c.model!=='string'||!c.model.trim()))throw new Error(t("m_42cedff702a0"));
  if(!Number.isInteger(c.max_input_chars)||c.max_input_chars<1||c.temperature!==null&&(!finite(c.temperature)||c.temperature<0||c.temperature>2)||c.timeout_seconds!==null&&(!finite(c.timeout_seconds)||c.timeout_seconds<=0))throw new Error(t("m_eb28e73c758d"));
  if(typeof c.local_disable_thinking!=='boolean'||typeof c.venice_disable_thinking!=='boolean'||typeof c.venice_include_system_prompt!=='boolean'||typeof c.codex_command!=='string'||typeof c.base_url!=='string'||typeof c.api_key_env!=='string')throw new Error(t("m_69015bd6ff33"));
  if(!p.minimum_scores||typeof p.minimum_scores!=='object'||Array.isArray(p.minimum_scores)||!Array.isArray(p.blocking_severities)||p.blocking_severities.some(v=>!['minor','major','critical'].includes(v))||typeof p.calibrated!=='boolean'||typeof p.version!=='string'||!Number.isInteger(p.min_quote_chars)||p.min_quote_chars<1)throw new Error(t("m_d536810079af"));
  for(const[k,v]of Object.entries(p.minimum_scores))if(!Object.hasOwn(criterionLabels,k)||!Number.isInteger(v)||v<0||v>4)throw new Error(t("m_58f681213f32"));
}
export function normalizeEvaluator(data){
  const config={provider:'codex_cli',base_url:null,model:null,api_key_env:null,timeout_seconds:null,max_output_tokens:6000,temperature:null,response_mode:'json_schema',max_input_chars:100000,codex_command:'codex',local_disable_thinking:false,venice_include_system_prompt:false,venice_disable_thinking:false,...data.config};
  config.base_url??=providerEndpoints[config.provider];config.api_key_env??=config.provider==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY';
  const profile={version:'candidate-v1',calibrated:false,minimum_scores:Object.fromEntries(Object.keys(criterionLabels).map(k=>[k,3])),blocking_severities:['major','critical'],min_quote_chars:12,evaluator_fingerprint:null,calibration_fingerprint:null,...data.profile};
  return {config,context_tokens:data.context_tokens??32768,profile,policy:data.policy??'off'};
}
export class EvaluatorDraft{
  constructor(saved){this.baseline=normalizeEvaluator(saved);this.current=clone(this.baseline);this.rawText=JSON.stringify(this.current,null,2);this.rawPending=false;this.policyOverride=null;this.candidateCreated=false}
  patch(fields){if(this.rawPending)throw new Error(t("m_cb20a570da63"));if(fields.profile&&this.current.profile.calibrated&&settingsSignature(fields.profile)!==settingsSignature(this.current.profile))throw new Error(t("m_7f25d1d0f520"));Object.assign(this.current,clone(fields));this.rawText=JSON.stringify(this.current,null,2)}
  setRaw(text){this.rawText=text;this.rawPending=true}
  discardRaw(){this.rawText=JSON.stringify(this.current,null,2);this.rawPending=false}
  applyRaw(){
    let parsed;try{parsed=JSON.parse(this.rawText)}catch{throw new Error(t("m_127dc3a4de92"))}
    const valid=(obj,keys)=>obj&&typeof obj==='object'&&!Array.isArray(obj)&&Object.keys(obj).every(k=>keys.includes(k));
    if(!valid(parsed,['config','context_tokens','profile','policy'])||!valid(parsed.config,Object.keys(this.baseline.config))||parsed.profile&&!valid(parsed.profile,Object.keys(this.baseline.profile)))throw new Error(t("m_33527a2a19f9"));
    if(!Object.hasOwn(parsed.config,'provider')||!Object.hasOwn(parsed.config,'max_input_chars')||!Object.hasOwn(parsed,'context_tokens')||!Object.hasOwn(parsed,'policy'))throw new Error(t("m_fd785f8d2234"));
    const next=normalizeEvaluator(parsed);
    validateShape(next);
    if(!valid(next.profile.minimum_scores,Object.keys(criterionLabels))||!Array.isArray(next.profile.blocking_severities)||next.profile.blocking_severities.some(s=>!['minor','major','critical'].includes(s))||typeof next.profile.calibrated!=='boolean'||typeof next.profile.version!=='string'||!Number.isInteger(next.profile.min_quote_chars)||next.profile.min_quote_chars<1)throw new Error(t("m_61f507b833cf"));
    if(next.profile.calibrated&&settingsSignature(next.profile)!==settingsSignature(this.baseline.profile))throw new Error(t("m_92bf1aff7fdc"));
    if(!next.profile.calibrated&&(next.profile.calibration_fingerprint!==this.baseline.profile.calibration_fingerprint||next.profile.evaluator_fingerprint!==this.baseline.profile.evaluator_fingerprint)&&(next.profile.calibration_fingerprint!==null||next.profile.evaluator_fingerprint!==null))throw new Error(t("m_92bf1aff7fdc"));
    if(this.policyOverride!==null)next.policy=this.policyOverride;
    this.current=next;this.rawPending=false;this.rawText=JSON.stringify(next,null,2);this.candidateCreated=!next.profile.calibrated;
  }
  policySaved(policy){this.current.policy=policy;this.baseline.policy=policy;this.policyOverride=policy;if(!this.rawPending)this.rawText=JSON.stringify(this.current,null,2)}
  async savePolicy(policy,send){const result=await send(policy);this.policySaved(result.policy);return result}
  calibrationLost(){return this.baseline.profile.calibrated&&(!this.current.profile.calibrated||settingsSignature(this.current.config)!==settingsSignature(this.baseline.config))}
  makeCandidate(){if(this.rawPending)throw new Error(t("m_cb20a570da63"));this.current.profile={...this.current.profile,version:this.current.profile.version+'-candidate',calibrated:false,evaluator_fingerprint:null,calibration_fingerprint:null};this.candidateCreated=true;this.rawText=JSON.stringify(this.current,null,2)}
  read(){
    if(this.rawPending)throw new Error(t("m_cb20a570da63"));
    const s=this.current;
    validateShape(s);
    if(s.policy==='pause_on_failure'&&(!s.profile.calibrated||this.calibrationLost()))throw new Error(t("m_ba0cca650318"));
    return clone(s);
  }
}
