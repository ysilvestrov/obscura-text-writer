import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {usd} from './budget-format.js';
const roles=new Set(['planner','writer','editor','memory']);
const modes=new Set(['plan','brief','draft','review','prose','memory']);
const safeId=value=>typeof value==='string'&&/^[\p{L}\p{N}_-]{1,200}$/u.test(value);
export function settingsLink(story,scene,mode,role){
  if(!roles.has(role)||!modes.has(mode)||!safeId(scene))return null;
  const query=new URLSearchParams({scene,material:mode,role});
  return `/stories/${encodeURIComponent(story)}/settings?${query}#role-${role}`;
}
export function returnLink(story,search){
  const query=new URLSearchParams(search),scene=query.get('scene'),mode=query.get('material');
  const base=`/stories/${encodeURIComponent(story)}`;
  return safeId(scene)&&modes.has(mode)?base+'?'+new URLSearchParams({scene,material:mode}):base;
}
export function usageText(usage){
  const number=(...keys)=>{for(const key of keys){const value=usage?.[key];if(Number.isInteger(value)&&value>=0)return String(value)}return t("m_e3b740479858")};
  return t("m_1cb565018878",{p0:(number('prompt_tokens','input_tokens')),p1:(number('completion_tokens','output_tokens'))});
}
export function compactBudgetText(data){
  if(!data)return t("m_e297ebd8c120");
  const call=data.last_call;
  const last=!call?t("m_5523510adcba"):call.cost_source==='unpriced'?t("m_94e7a99d269e"):
    call.cost_source==='provider'?usd(call.counted_nanos)+t("m_6d6e68499791"):
    call.cost_source==='priced_usage_estimate'?usd(call.counted_nanos)+t("m_5896dd668cd3"):t("m_349e00a5bff6")+usd(call.counted_nanos);
  return t("m_012c2b154290",{p0:(usd(data.exposure_nanos)),p1:(data.limit_nanos==null?t("m_983d16aa1ad2"):usd(data.limit_nanos)),p2:(last)});
}
