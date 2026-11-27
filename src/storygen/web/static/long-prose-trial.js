// LONG-PROSE-TRIAL-S07: the one trial of long prose in an edition without it. The window only offers and hides actions;
// the server keeps every limit. After a successful claim the page reloads: appInfo() keeps one answer per page.
import {t,uiText} from './i18n.js';

const NONE={state:'none',kind:null,id:null,title:null};

export function trialState(info){
  return info?.long_prose_trial?{...NONE,...info.long_prose_trial}:{...NONE};
}

// A deleted work or series leaves no title: then the text names no work.
export function usedText(state){
  return state?.title?t('trial.used',{p0:state.title}):t('trial.used_untitled');
}

export function claimBody(target){
  return target.series_id?{series_id:target.series_id,confirm:true}:{story_id:target.story_id,confirm:true};
}

export async function claimTrial({api,json,confirmDialog,notice,location},target,title){
  if(!await confirmDialog(t('trial.confirm',{p0:title})))return false;
  try{
    await api('/api/long-prose-trial',json('POST',claimBody(target)));
  }catch(error){
    notice(error.message,'error');
    return false;
  }
  location.reload();
  return true;
}

export function usedNotice(document,state,info){
  const box=document.createElement('p');
  box.className='muted trial-used';
  const text=document.createElement('span');
  uiText(text,'textContent',()=>usedText(state));
  box.append(text);
  if(info?.waitlist_url){
    const link=document.createElement('a');
    link.href=info.waitlist_url;link.target='_blank';link.rel='noopener noreferrer';
    link.dataset.i18n='app.link.waitlist';
    uiText(link,'textContent',()=>t('app.link.waitlist'));
    box.append(' ',link);
  }
  return box;
}
