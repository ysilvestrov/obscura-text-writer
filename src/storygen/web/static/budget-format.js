import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export const usd=n=>n==null?t("m_c50d8ea8a872"):'$'+(n/1e9).toLocaleString(getLocale()==='en'?'en-US':'uk-UA',{maximumFractionDigits:6});

export function lastCallText(call){
  if(!call)return t("m_da9e24b6ee8d");
  const model=`${call.provider} · ${call.model}`;
  if(call.cost_source==='unpriced')return t("m_3df478e862f2",{p0:(model)});
  const amount=usd(call.counted_nanos);
  if(call.cost_source==='provider')return t("m_da5bdbf5861d",{p0:(amount),p1:(model)});
  if(call.cost_source==='priced_usage_estimate')return t("m_e1941e63821f",{p0:(amount),p1:(model)});
  return t("m_ecf4be1dc682",{p0:(amount),p1:(call.state==='unresolved'?t("m_37664d4d324f"):t("m_e36f5ec8b962")),p2:(model)});
}
