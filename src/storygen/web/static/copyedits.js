import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {mountChangeReview} from './change-review.js';
export const mountCopyeditReview=options=>mountChangeReview(options);

export function renderLanguageWarnings(host,result){
  host.replaceChildren();const title=document.createElement('h4');uiText(title,"textContent",()=>(t("m_4c6e10f9642e")));
  const hint=document.createElement('p');uiText(hint,"textContent",()=>(t("m_5c45944904c5")+(result.stale?t("m_17bd58515a66"):'')));host.append(title,hint);
  if(!result.warnings.length){const p=document.createElement('p');uiText(p,"textContent",()=>(t("m_7319dd129ac0")));host.append(p)}
  for(const warning of result.warnings){const p=document.createElement('p');uiText(p,"textContent",()=>(t("m_413d24dd21de",{p0:(warning.quote),p1:(diagnostic(warning.message)),p2:(warning.start+1),p3:(warning.end)})));host.append(p)}
}
