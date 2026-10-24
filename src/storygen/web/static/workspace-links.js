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
  const number=(...keys)=>{for(const key of keys){const value=usage?.[key];if(Number.isInteger(value)&&value>=0)return String(value)}return 'Немає даних'};
  return `Токени останнього виклику: вхід ${number('prompt_tokens','input_tokens')}; вихід ${number('completion_tokens','output_tokens')}.`;
}
export function compactBudgetText(data){
  if(!data)return 'Завантажуємо облік…';
  const call=data.last_call;
  const last=!call?'ще немає':call.cost_source==='unpriced'?'без USD-ціни':
    call.cost_source==='provider'?usd(call.counted_nanos)+' підтверджено':
    call.cost_source==='priced_usage_estimate'?usd(call.counted_nanos)+' за токенами':'резерв '+usd(call.counted_nanos);
  return `Облік ${usd(data.exposure_nanos)} / ${data.limit_nanos==null?'без ліміту':usd(data.limit_nanos)} · останній: ${last}`;
}
