import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
export const stages=[{mode:'plan',get label(){return t("m_3146141c9367")}},{mode:'brief',get label(){return t("m_5a2ec5eaf0a1")}},{mode:'draft',get label(){return t("m_e9d875d4120b")}},
  {mode:'review',get label(){return t("m_c2320838b6df")}},{mode:'prose',get label(){return t("m_9c685577453c")}},{mode:'memory',get label(){return t("m_aa1cfb48cc30")}}];
export function assertReadyDispatch(state,captured){
  if(state.scene?.id!==captured.sceneId||state.bufferEpoch!==captured.epoch||state.mode!==captured.mode||state.dirty||state.saving)
    throw new Error(t("m_8ce9184a0c6a"));
  if((state.workspaceRuns||[]).some(run=>['queued','running','pause_requested','cancellation_requested'].includes(run.state)))
    throw new Error(t("m_506ce9f6bdfa"));
}
export function primaryAction(state){
  const save=state.dirty?t("m_f83e2d5dbe77"):'';
  const definitions={plan:{mode:'stage',stage:'brief',target:'brief',get name(){return t("m_680822e95b88")},get label(){return t("m_ff65b517b118")}},
    brief:{mode:'stage',stage:'draft',target:'draft',get name(){return t("m_a94fb4b9179e")},get label(){return t("m_bd2f8a0a0fd1")}},
    draft:{mode:'edit_loop',target:'prose',get name(){return t("m_b1062b0054e5")},get label(){return t("m_71957284c5de")}},
    review:{action:'accept',get label(){return t("m_ae6ae32555fd")}},
    prose:{mode:'stage',stage:'memory',target:'memory',get name(){return t("m_d84ffc519180")},get label(){return t("m_a87ddd66760f")}},
    memory:{action:'next',get label(){return t("m_c37ec3213bd7")}}};
  const result={...definitions[state.mode]};
  if(result.target&&state.scene?.heads[result.target])result.label=save+(state.dirty?t("m_7375d1ec2b7c"):t("m_0a68d6b25fce"))+t("m_85718479f450")+result.name;
  return result;
}
export async function performPrimary({state,save,run,show,accept,next}){
  if(state.assistedReview)throw new Error(t('rewrite.resolve_first'));
  if(!state.scene||state.saving)throw new Error(t("m_4b79b55b4d28"));
  if(state.bufferOrigin==='history'||state.mode==='blueprint')throw new Error(t("m_2efd60917761"));
  const captured={id:state.scene.id,mode:state.mode,epoch:state.bufferEpoch};
  if(state.dirty)await save();
  if(state.dirty||state.saving||state.scene?.id!==captured.id||state.mode!==captured.mode||state.bufferEpoch!==captured.epoch)
    throw new Error(t("m_99828af8cba1"));
  if(state.mode==='brief'&&state.pendingBrief)throw new Error(t('brief.accept_first'));
  const action=primaryAction(state);
  if(action.action==='accept'){await accept();return;}
  if(action.action==='next'){await next();return;}
  if(!action.mode)throw new Error(t("m_a506e2217d64"));
  if(action.mode==='edit_loop'){
    action.editor_source_head='draft';action.editor_source_version_id=state.scene.heads.draft;
  }
  await run(action);
}
