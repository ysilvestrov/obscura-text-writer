export const usd=n=>n===null?'не задано':'$'+(n/1e9).toLocaleString('uk-UA',{maximumFractionDigits:6});

export function lastCallText(call){
  if(!call)return 'Останній виклик: відправлених викликів ще немає.';
  const model=`${call.provider} · ${call.model}`;
  if(call.cost_source==='unpriced')return `Останній виклик: ${model} — без токенної USD-ціни.`;
  const amount=usd(call.counted_nanos);
  if(call.cost_source==='provider')return `Останній виклик: ${amount} · підтверджено · ${model}.`;
  if(call.cost_source==='priced_usage_estimate')return `Останній виклик: ${amount} · розраховано за токенами · ${model}.`;
  return `Останній виклик: вартість ще не підтверджена; резерв ${amount} · ${call.state==='unresolved'?'потребує звірки':'виконується'} · ${model}.`;
}
