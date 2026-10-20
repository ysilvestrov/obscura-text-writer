export function operationReason(state,operation){
  if(state.saving)return 'Дочекайтеся завершення збереження';
  if(state.dirty)return 'Спершу збережіть ручні правки';
  if(!operation)return 'Перевіряємо передумови…';
  return operation.ready?'':operation.reason||'Немає потрібних матеріалів';
}
export function confirmationText(operation){
  const roles=Object.entries(operation.roles).map(([role,c])=>`${role}: ${c.provider} / ${c.model}`);
  if(operation.evaluator)roles.push(`Оцінювач після сцени: ${operation.evaluator.provider} / ${operation.evaluator.model||'типова модель CLI'}`);
  return `Заплановано до ${operation.calls} модельних викликів.\n${roles.join('\n')}\nВартість визначається провайдером; оцінки ціни немає. Запустити?`;
}
export function runKind(state){return state==='completed'?'success':state==='failed'?'error':['interrupted','needs_review','alternative','cancelled','paused'].includes(state)?'warning':'info'}
export function controlReason(action,run){
  if(!run)return 'Спершу оберіть запуск';
  const allowed={pause:['queued','running'],cancel:['queued','running','pause_requested','paused','interrupted','needs_review','alternative'],resume:['paused','needs_review','alternative'],repeat:['failed','interrupted','cancelled']};
  return allowed[action]?.includes(run.state)?'':'Недоступно в поточному стані запуску';
}
export function materialReason(action,state,runs){
  if(action==='latest')return runs?.length?'':'Немає збережених запусків';
  if(state.saving)return 'Дочекайтеся завершення збереження';
  if(action==='proposal'){
    if(state.dirty)return 'Спершу збережіть ручні правки';
    return runs?.some(run=>run.request.mode==='prepare'&&run.state==='completed')?'':'Немає завершеної пропозиції структури';
  }
  if(action==='apply')return state.mode==='blueprint'?'':'Спершу перегляньте пропозицію структури';
  return '';
}
