// OPENROUTER-REASONING: the role's reasoning control for OpenRouter, offered from the model's catalog row.
import {t} from './i18n.js';

// Lowest first, as the form shows them; the catalog lists supported_efforts highest first.
export const OPENROUTER_EFFORTS=['minimal','low','medium','high','xhigh','max'];

function label(value){return value==='none'?t('openrouter.reasoning.off'):value}

// capability: undefined — catalog not loaded (or the model is not in it); null — the model has no reasoning;
// otherwise {mandatory, efforts}: efforts null = every level, [] = no level choice.
export function reasoningChoices(capability,saved){
  const choices=[{value:'',label:t('openrouter.reasoning.default')}];
  let allowed;
  if(capability===undefined)allowed=null;
  else if(capability===null)allowed=[];
  else{
    allowed=capability.mandatory?[]:['none'];
    const efforts=capability.efforts;
    allowed.push(...OPENROUTER_EFFORTS.filter(level=>efforts===null||efforts===undefined||efforts.includes(level)));
  }
  for(const value of allowed||[])choices.push({value,label:label(value)});
  if(saved&&!choices.some(choice=>choice.value===saved)){
    const unsupported=allowed!==null;
    choices.push({value:saved,unsupported,label:unsupported?t('openrouter.reasoning.unsupported',{p0:label(saved)}):label(saved)});
  }
  return choices;
}

// The payload value: only OpenRouter carries it; the server rejects it for any other provider.
export const providerReasoning=(provider,value)=>provider==='openrouter'&&value?value:null;

// select: the <select>; picker: the model picker (selected(), loaded()); modelInput: its model field.
export function mountOpenrouterReasoning({select,picker,modelInput}){
  const capability=()=>{if(!picker.loaded())return undefined;const model=picker.selected();return model?model.reasoning??null:undefined};
  function render(saved=select.value){
    const options=reasoningChoices(capability(),saved).map(choice=>{const option=document.createElement('option');option.value=choice.value;option.textContent=choice.label;if(choice.unsupported)option.dataset.unsupported='true';return option});
    select.replaceChildren(...options);select.value=saved||'';
  }
  for(const type of ['input','change','model-catalog-changed'])modelInput.addEventListener(type,()=>render());
  document.addEventListener('ui-locale-changed',()=>{if(select.isConnected)render()});
  render();
  return {render,write:value=>render(value||'')};
}
