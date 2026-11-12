// MODEL-001: the writer's optional model for scenes rated 0–1. The prompt and the response mode stay shared with the main model.
import {t,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {mountModelPicker} from './model-picker.js';
import {mountModelPolicy} from './model-policy.js';
import {providerEndpoints} from './settings-connection.js';

const NUMBERS=['context_tokens','max_output_tokens','max_input_chars','temperature'];

// null when the toggle is off: the writer save then clears the stored variant (low_rating_variant: null).
export function variantPayload(form){
  const f=form.elements;if(!f.variant_enabled?.checked)return null;
  const provider=f.variant_provider.value,timeout=f.variant_timeout.value===''?null:Number(f.variant_timeout.value);
  // Options stored for the same provider (key name, vendor flags) survive a save; another provider starts from its defaults.
  const base=form.writerVariantBase?.provider?.provider===provider?form.writerVariantBase.provider:{key_env:null,include_usage:false};
  const result={provider:{...base,provider,model:f.variant_model.value.trim(),base_url:f.variant_base_url.value,timeout,response_mode:f.response_mode.value}};
  for(const name of NUMBERS)result[name]=Number(f[`variant_${name}`].value);
  result.timeout=timeout;
  return result;
}

function el(tag,props={},...children){const node=document.createElement(tag);for(const[k,v]of Object.entries(props))if(k in node&&!k.includes('-'))node[k]=v;else node.setAttribute(k,v);node.append(...children);return node}
const text=key=>{const span=el('span');uiText(span,'textContent',()=>t(key));return span};

// Options a variant of the same provider starts from: its own stored ones, else the main connection's (key name, vendor flags).
export const variantBase=config=>config.low_rating_variant||{provider:config.provider};

export function mountWriterVariant(form,config){
  const stored=config.low_rating_variant||null;form.writerVariantBase=variantBase(config);
  // A new variant starts from the main model's connection and limits; the author picks the model.
  const start=stored||{provider:{...config.provider,model:''},context_tokens:config.context_tokens,max_output_tokens:config.max_output_tokens,max_input_chars:config.max_input_chars,temperature:config.temperature,timeout:null};
  const toggle=el('input',{type:'checkbox',name:'variant_enabled'}),strong=el('b',{},text('writer.variant.toggle'));
  const hint=el('p',{className:'settings-hint'},text('writer.variant.hint'));
  const provider=el('select',{name:'variant_provider'},el('option',{value:'local'},text('m_63156f17fb93')),el('option',{value:'openrouter'},'OpenRouter'),el('option',{value:'venice'},'Venice · uncensored=true'));
  const baseUrl=el('input',{name:'variant_base_url',required:true}),model=el('input',{name:'variant_model',required:true,maxLength:300});
  const discover=el('button',{type:'button',className:'secondary'},text('m_bb570a85efbc'));
  const pickerHost=el('div'),policyHost=el('div');
  const number=(name,attrs)=>el('input',{name:`variant_${name}`,type:'number',required:name!=='timeout',...attrs});
  const inputs={context_tokens:number('context_tokens',{min:'512'}),max_output_tokens:number('max_output_tokens',{min:'1'}),max_input_chars:number('max_input_chars',{min:'1'}),temperature:number('temperature',{min:'0',max:'2',step:'any'}),timeout:number('timeout',{min:'0.001',step:'any'})};
  const captions={context_tokens:'m_a5e1bed8c89a',max_output_tokens:'m_11de327806c2',max_input_chars:'m_c8f9fea4d67c',temperature:'m_56f7653b8834',timeout:'m_ae883a01f59f'};
  const grid=el('div',{className:'settings-fields'},el('label',{},text('m_2d385af6d69b'),provider),el('label',{},'Base URL',baseUrl),el('label',{},'Model ID',model,discover),pickerHost,
    ...Object.entries(inputs).map(([name,input])=>el('label',{},text(captions[name]),input)));
  const fields=el('fieldset',{className:'writer-variant-fields'},grid);
  const block=el('div',{className:'writer-variant','data-writer-variant':'true'},el('label',{className:'checkbox writer-variant-toggle'},toggle,' ',strong),hint,fields);
  toggle.checked=Boolean(stored);provider.value=start.provider.provider;baseUrl.value=start.provider.base_url||providerEndpoints[start.provider.provider];model.value=start.provider.model||'';
  for(const name of NUMBERS)inputs[name].value=String(start[name]);
  inputs.timeout.value=String(start.timeout??start.provider.timeout??'');
  const picker=mountModelPicker({host:pickerHost,modelInput:model,providerInput:provider,baseUrlInput:baseUrl,responseModeInput:form.elements.response_mode});
  // Consent and the refusal mark are keyed by role writer + the variant's endpoint and model (MODEL-003, MODEL-004).
  pickerHost.append(policyHost);
  mountModelPolicy({host:policyHost,role:'writer',modelInput:model,providerInput:provider,baseUrlInput:baseUrl,picker});
  provider.addEventListener('change',()=>{baseUrl.value=providerEndpoints[provider.value];inputs.timeout.value=provider.value==='local'?3600:180});
  discover.onclick=async()=>{
    const captured=picker.capture();discover.disabled=true;
    try{
      const request={provider:provider.value,model:model.value||'discovery-only',base_url:baseUrl.value,key_env:form.writerVariantBase?.provider?.provider===provider.value?form.writerVariantBase.provider.key_env:null,timeout:inputs.timeout.value===''?null:Number(inputs.timeout.value),response_mode:form.elements.response_mode.value};
      const result=await api('/api/providers/discover',json('POST',request));if(!picker.setModels(result.models,captured))throw new Error(t('m_b6361b46aced'));notice(t('m_8d511fd9fc01',{p0:result.models.length}));
    }catch(e){notice(e.message,'error')}finally{discover.disabled=false}
  };
  // Hidden and disabled while off: its required fields do not block the writer save.
  function update(){fields.hidden=fields.disabled=!toggle.checked}
  toggle.addEventListener('change',update);form.addEventListener('settings-reset',update);form.addEventListener('settings-unlocked',update);update();
  return {block,read(){const blocked=toggle.checked?picker.validate():null;if(blocked)throw new Error(t(blocked));return variantPayload(form)}};
}
