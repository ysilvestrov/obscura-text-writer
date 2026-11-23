// VALID-LINKS rule (г): after a character card or location change the author decides whether the dependent scenes lose
// the validity of their brief and prose links. Only «Так» writes anything; saving alone changes no link.
import {t,msg,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {confirmDialog} from './dialogs.js';

export async function offerInvalidation(storyId,kind,ids,names,sceneIds){
  if(!ids?.length||!sceneIds?.length)return false;
  const key=kind==='character'?'link.cards_invalidate':'link.locations_invalidate';
  const accepted=await confirmDialog(t(key,{p0:names.filter(Boolean).join(', '),p1:sceneIds.length}),
    {accept:t('link.invalidate_yes'),cancel:t('link.invalidate_no')});
  if(!accepted)return false;
  try{
    await api(`/api/stories/${storyId}/links/invalidate`,json('POST',{scene_ids:sceneIds,reason:{kind,ids}}));
    notice(msg('link.invalidated'));
    return true;
  }catch(error){notice(diagnostic(error.message),'error');return false}
}
