import {t,uiText,uiAttr,getLocale} from './i18n.js';

export function modelMetadataLabel(model,now=Date.now()){
  const tariff=model?.tariff;
  let label=t('models.tariff_unknown');
  if(tariff){
    const expiry=Date.parse(tariff.expires_at);
    if(Number.isFinite(expiry))label=(expiry<=now?t('models.tariff_expired')+' ':'')+t(tariff.kind==='manual'?'models.tariff_manual':'models.tariff_official')+' '+t('models.tariff_rates',{p0:tariff.input_per_million,p1:tariff.output_per_million,p2:tariff.request_usd});
  }
  if(Number.isInteger(model?.context_tokens)&&model.context_tokens>0)label+=' '+t('models.context_cap',{p0:model.context_tokens});
  if(Number.isInteger(model?.max_output_tokens)&&model.max_output_tokens>0)label+=' '+t('models.output_cap',{p0:model.max_output_tokens});
  return label;
}

export function mountModelCatalog({list,modelInput,providerInput,baseUrlInput}){
  const info=document.createElement('small');info.dataset.modelInfo='true';info.className='settings-hint';
  const caption=modelInput.parentElement.firstChild;
  uiAttr(modelInput,'aria-label',()=>{getLocale();return caption?.textContent||t('m_f1f1eed62cda');});
  info.id=list.id+'-metadata';modelInput.parentElement.append(info);
  modelInput.setAttribute('aria-describedby',[modelInput.getAttribute('aria-describedby'),info.id].filter(Boolean).join(' '));
  let catalog=new Map(),binding=null;
  const identity=()=>JSON.stringify([providerInput.value,baseUrlInput.value.replace(/\/$/,'')]);
  function update(){uiText(info,'textContent',()=>modelMetadataLabel(binding===identity()?catalog.get(modelInput.value):null));}
  function clear(){catalog=new Map();binding=null;list.replaceChildren();update();}
  for(const event of ['input','change'])modelInput.addEventListener(event,update);
  providerInput.addEventListener('change',clear);baseUrlInput.addEventListener('input',clear);baseUrlInput.addEventListener('change',clear);
  update();
  return {capture:identity,clear,update,setModels(models,captured){
    if(captured!==identity())return false;
    catalog=new Map(models.map(model=>[model.id,model]));binding=captured;list.replaceChildren();
    for(const model of models){const option=document.createElement('option');option.value=model.id;uiText(option,'textContent',()=>modelMetadataLabel(model));list.append(option);}
    update();return true;
  }};
}
