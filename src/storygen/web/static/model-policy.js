// Consent checkbox and refusal mark under the chosen model of a role (MODEL-003, MODEL-004).
// Both act at once through /api/model-policy for the role + endpoint + exact model shown in the form; the role form is not saved.
import {t,uiText,diagnostic} from './i18n.js';
import {api,json} from './api.js';

// Venice reports Uncensored in its catalog: until the list is loaded the mark is unknown, so nothing is shown (the gateway
// still enforces consent). OpenRouter and other cloud providers never report it, so their warning is always shown.
export const consentVisible=(option,provider,catalogLoaded)=>provider!=='local'&&(provider!=='venice'||catalogLoaded===true)&&option?.uncensored!==true;
export const refusalRatings=refusals=>refusals.map(({rating:[sexual,violence,themes]})=>t('rating.scene.summary',{p0:sexual,p1:violence,p2:themes})).join('; ');

function el(tag,props={},...children){const node=document.createElement(tag);for(const[k,v]of Object.entries(props))if(k in node&&!k.includes('-'))node[k]=v;else node.setAttribute(k,v);node.append(...children);return node}

export function mountModelPolicy({host,role,modelInput,providerInput,baseUrlInput,picker}){
  host.classList.add('model-policy');
  // The checkbox has no name: it is not part of the role form draft and never marks the form as changed.
  const consent=el('input',{type:'checkbox'}),consentText=el('span'),hint=el('p');
  const warn=el('div',{className:'model-policy-notice model-policy-warn','data-model-consent':'true'},hint,el('label',{className:'model-policy-consent'},consent,consentText));
  const refusedText=el('p'),clear=el('button',{type:'button',className:'secondary'}),choose=el('button',{type:'button',className:'secondary'});
  const refusal=el('div',{className:'model-policy-notice model-policy-refusal','data-model-refusal':'true'},refusedText,el('div',{className:'model-policy-actions'},clear,choose));
  const error=el('p',{className:'model-policy-error',role:'status','data-model-policy-error':'true'});
  host.replaceChildren(refusal,warn,error);
  uiText(hint,'textContent',()=>t('policy.consent_hint'));uiText(consentText,'textContent',()=>t('policy.consent_label'));
  uiText(clear,'textContent',()=>t('policy.clear_refusal'));uiText(choose,'textContent',()=>t('policy.choose_other'));
  let state=null,stateKey=null,failure=null,pending=null,busy=false,seq=0;
  const target=()=>{
    const model=modelInput.value.trim(),base_url=baseUrlInput.value.trim();
    return model?{role,provider:providerInput.value,model,...(base_url?{base_url}:{})}:null;
  };
  const keyOf=value=>value?JSON.stringify(value):null;
  const query=value=>new URLSearchParams(value).toString();
  // State fetched for another model is never shown: a changed field hides the old checkbox and mark until the new answer.
  const shown=()=>stateKey!==null&&stateKey===keyOf(target())?state:null;
  function render(){
    const value=target(),current=shown();
    warn.hidden=!value||!consentVisible(picker?.selected?.()??null,value.provider,Boolean(picker?.loaded?.()));
    consent.checked=pending??Boolean(current?.consent);consent.disabled=busy||!current||modelInput.disabled;
    const refusals=current?.refusals||[];refusal.hidden=!refusals.length;clear.disabled=busy||modelInput.disabled;
    uiText(refusedText,'textContent',()=>refusals.length?t('policy.refused',{p0:refusalRatings(refusals)}):'');
    uiText(error,'textContent',()=>failure?diagnostic(failure):'');error.hidden=!failure;
    host.hidden=warn.hidden&&refusal.hidden&&error.hidden;
  }
  async function refresh(){
    const value=target(),key=keyOf(value),mine=++seq;failure=null;
    if(key!==stateKey){state=null;stateKey=null}
    render();if(!value)return;
    try{const body=await api(`/api/model-policy?${query(value)}`);if(mine===seq&&key===keyOf(target())){state=body;stateKey=key}}
    catch(e){if(mine===seq)failure=e.message}
    render();
  }
  async function change(request,{checked=null}={}){
    const value=target(),key=keyOf(value);if(!value||key!==stateKey||busy)return;
    busy=true;pending=checked;failure=null;render();
    // On failure the checkbox returns to the stored state and the error stays in the block.
    try{const body=await api(...request(value));if(key===stateKey){state=body;seq++}}
    catch(e){failure=e.message}
    finally{busy=false;pending=null;render()}
  }
  consent.addEventListener('change',()=>change(consent.checked?value=>['/api/model-policy/consent',json('PUT',value)]:value=>[`/api/model-policy/consent?${query(value)}`,{method:'DELETE'}],{checked:consent.checked}));
  clear.onclick=()=>change(value=>[`/api/model-policy/refusal?${query(value)}`,{method:'DELETE'}]);
  choose.onclick=()=>picker?.open?.();
  // Other listeners update dependent fields (provider → base URL) first; read the pair after them.
  const later=()=>queueMicrotask(refresh);
  // A catalog change can follow a silent rewrite of the fields (shared provider applied to this role): re-read a changed pair.
  modelInput.addEventListener('model-catalog-changed',()=>{if(keyOf(target())!==stateKey)later();else render()});
  for(const field of [modelInput,providerInput,baseUrlInput]){field.addEventListener('input',render);field.addEventListener('change',later)}
  modelInput.form?.addEventListener('settings-reset',later);modelInput.form?.addEventListener('settings-unlocked',render);
  refresh();
  return {refresh};
}
