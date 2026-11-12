import {t} from './i18n.js';

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
