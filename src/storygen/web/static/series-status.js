// SERIES: the snapshot state of a series book in words, and «Оновити з попередньої книги» with its warning.
import {t} from './i18n.js';
import {api,json,notice} from './api.js';
import {confirmDialog} from './dialogs.js';

export function statusText(status){
  if(!status)return '';
  const number=status.source_number??'';
  const changed=status.changed_cards?.length?' '+t('series.status.cards',{p0:status.changed_cards.length}):'';
  const prequel=status.prequel?' '+t('series.status.prequel'):'';
  return ({
    fresh:t('series.status.fresh'),
    first:t('series.status.first'),
    no_summary:t('series.status.no_summary'),
    source_finished:t('series.status.source_finished'),
    source_changed:t('series.status.source_changed',{p0:number})+changed,
  }[status.state]||'')+prequel;
}

// The refresh stales the memory of the book's first scenes, so it asks first; returns whether the snapshot changed.
export async function refreshBook(storyId){
  if(!await confirmDialog(t('series.refresh_confirm'),{accept:t('series.refresh'),cancel:t('series.cancel')}))return false;
  try{
    const story=(await api(`/api/stories/${storyId}`)).story;
    const result=await api(`/api/stories/${storyId}/series/refresh`,json('POST',{expected_revision:story.revision,confirm:true}));
    notice(t('series.refreshed'));
    for(const warning of result.warnings||[])notice(warning,'error');
    return true;
  }catch(error){notice(error.message,'error');return false}
}
