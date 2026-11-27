// SERIES: the series of a book on its settings page — series (existing or new), number and «Початок», saved with the
// story revision; the snapshot state with «Оновити з попередньої книги». Long prose only.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {appInfo} from './app-info.js';
import {statusText,refreshBook} from './series-status.js';
import {confirmDialog} from './dialogs.js';
import {trialState} from './long-prose-trial.js';

const NEW='__new__';
const form=document.querySelector('#story-series-form');
const storyId=document.querySelector('.settings-page')?.dataset.storyId;
// LONG-PROSE-TRIAL-S07: without long prose the form keeps to the trial series: «Без серії» and that series only.
let trialSeries=null,currentSeries=null;

async function load(){
  const [view,items]=await Promise.all([api(`/api/stories/${storyId}`),api('/api/series')]);
  const select=form.elements.series_id;
  select.replaceChildren();
  const none=document.createElement('option');none.value='';uiText(none,'textContent',()=>t('series.none'));select.append(none);
  for(const item of items.filter(item=>!trialSeries||item.id===trialSeries)){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;select.append(option)}
  if(!trialSeries){const fresh=document.createElement('option');fresh.value=NEW;uiText(fresh,'textContent',()=>t('series.new_series'));select.append(fresh)}
  const series=view.series;currentSeries=series?.id||null;
  select.value=series?series.id:'';form.elements.number.value=series?series.number:'';
  form.elements.start.value=series?.start?`${series.start.offset}, ${series.start.anchor}`:'';
  form.elements.bible.checked=Boolean(series?.bible);showBible();
  form.elements.new_title.closest('label').hidden=true;
  form.dataset.revision=view.story.revision;
  const status=form.querySelector('[data-series-status]');uiText(status,'textContent',()=>series?statusText(series.status):'');
  const refresh=form.querySelector('[data-series-refresh]');
  refresh.hidden=!series||!['source_changed','source_finished'].includes(series.status.state);  // never for the bible
  // SERIES-S11: a prequel with a snapshot reviews the facts of later books (series-facts.js).
  form.querySelector('[data-series-facts]').hidden=!series?.status?.prequel||!['fresh','prequel_review'].includes(series.status.state);
  const link=form.querySelector('[data-series-link]');link.hidden=!series;if(series)link.href=`/series/${series.id}`;
}

// SERIES-BIBLE: the world bible has a series but no number and no «Початок», so both fields hide.
function showBible(){
  const bible=form.elements.bible.checked;
  form.elements.number.closest('label').hidden=bible;form.elements.start.closest('label').hidden=bible;
  form.querySelector('#story-series-help').hidden=bible;
}

function install(){
  form.hidden=false;
  form.elements.bible.onchange=showBible;
  form.elements.series_id.onchange=()=>{form.elements.new_title.closest('label').hidden=form.elements.series_id.value!==NEW};
  form.onsubmit=async event=>{
    event.preventDefault();
    try{
      let seriesId=form.elements.series_id.value||null;
      // Leaving the trial series keeps the book's parts but never frees its place.
      if(trialSeries&&currentSeries===trialSeries&&seriesId!==trialSeries&&!await confirmDialog(t('trial.leave_warning')))return;
      if(seriesId===NEW)seriesId=(await api('/api/series',json('POST',{title:form.elements.new_title.value}))).id;
      const bible=Boolean(seriesId)&&form.elements.bible.checked;
      const number=form.elements.number.value&&!bible?Number(form.elements.number.value):null;
      await api(`/api/stories/${storyId}/series`,json('PATCH',{series_id:seriesId,number:seriesId?number:null,bible,
        start_text:seriesId&&!bible?form.elements.start.value:null,expected_revision:Number(form.dataset.revision)}));
      notice(msg('series.saved'));
    }catch(error){notice(error.message,'error')}
    await load().catch(error=>notice(error.message,'error'));
  };
  form.querySelector('[data-series-refresh]').onclick=async()=>{if(await refreshBook(storyId))await load()};
  document.addEventListener('series-changed',()=>load().catch(error=>notice(error.message,'error')));
  load().catch(error=>notice(error.message,'error'));
}

// A book outside any series or inside the trial series gets the form; the trial book (one book) never joins a series.
async function start(){
  const [info,view]=await Promise.all([appInfo(),api(`/api/stories/${storyId}`)]);
  if(info.long_prose!==false){install();return}
  const trial=trialState(info);
  if(trial.state!=='used'||trial.kind!=='series')return;
  const own=view.story.series_id;
  if(own&&own!==trial.id)return;
  trialSeries=trial.id;install();
}
if(form&&storyId)start().catch(()=>{});
