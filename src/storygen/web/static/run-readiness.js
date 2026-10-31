import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export function operationReason(state,operation){
  if(state.assistedReview)return t("rewrite.resolve_first");
  if(state.saving)return t("m_cbac60d6d919");
  if(state.dirty)return t("m_a4c2e86ecc1a");
  if(state.characterDirty)return t("m_5c4ff1c13cbb");
  if(!operation)return t("m_a8900573fc3e");
  return operation.ready||operation.can_confirm?'':operation.reason||t("m_1ff0aee46b1d");
}
export function editorLoopOperation(operation,limit){
  if(!Number.isInteger(limit)||limit<1||limit>10)throw new Error(t("m_7a3edd75b937"));
  const calls=operation?.edit_loop_scenes?operation.calls+(limit-operation.edit_pass_limit)*operation.edit_loop_scenes:limit;
  return {...operation,calls,warnings:[...(operation?.warnings||[]),msg("m_61c8ee57393c")]};
}
export function confirmationText(operation){
  const roles=Object.entries(operation.roles).map(([role,c])=>`${role}: ${c.provider} / ${c.model}`);
  if(operation.evaluator)roles.push(t("m_9336bc87f2cb",{p0:(operation.evaluator.provider),p1:(operation.evaluator.model||t("m_a83642f7025e"))}));
  const warnings=[...new Set([...(operation.warnings||[]),operation.warning].filter(Boolean))];
  const review=operation.memory_review;
  const consent=review?t('memory.confirm',{p0:review.memory_scene_number,p1:review.changed_version_count,p2:review.changed_text_count})+'\n\n'+(review.risk?t('memory.confirm_risk'):t('memory.confirm_identical'))+'\n\n':'';
  return consent+t("m_03d8a244e7c2",{p0:(operation.calls),p1:(roles.join('\n')),p2:(warnings.length?t("m_82ee1cb44ed7")+warnings.join('\n')+'\n':'')});
}
export function runKind(state){return state==='completed'?'success':state==='failed'?'error':['interrupted','needs_review','alternative','cancelled','paused'].includes(state)?'warning':'info'}
export function controlReason(action,run){
  if(!run)return t("m_35691ee7bea3");
  const allowed={pause:['queued','running'],cancel:['queued','running','pause_requested','paused','interrupted','needs_review','alternative'],resume:['paused','needs_review','alternative'],repeat:['failed','interrupted','cancelled']};
  return allowed[action]?.includes(run.state)?'':t("m_aa885dcd2fb6");
}
export function materialReason(action,state,runs){
  if(action==='latest')return runs?.length?'':t("m_974cb3942167");
  if(state.saving)return t("m_cbac60d6d919");
  if(action==='proposal'){
    if(state.dirty)return t("m_a4c2e86ecc1a");
    return runs?.some(run=>run.request.mode==='prepare'&&run.state==='completed')?'':t("m_17e4cda95563");
  }
  if(action==='apply')return state.mode==='blueprint'?'':t("m_70f9878478a2");
  return '';
}
