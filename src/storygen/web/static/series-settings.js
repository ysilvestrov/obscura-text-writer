// SERIES: the series of a book on its settings page — series (existing or new), number and «Початок», saved with the
// story revision; the snapshot state with «Оновити з попередньої книги». Long prose only.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {appInfo} from './app-info.js';
import {statusText,refreshBook} from './series-status.js';

const NEW='__new__';
const form=document.querySelector('#story-series-form');
const storyId=document.querySelector('.settings-page')?.dataset.storyId;

async function load(){
  const [view,items]=await Promise.all([api(`/api/stories/${storyId}`),api('/api/series')]);
  const select=form.elements.series_id;
  select.replaceChildren();
  const none=document.createElement('option');none.value='';uiText(none,'textContent',()=>t('series.none'));select.append(none);
  for(const item of items){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;select.append(option)}
  const fresh=document.createElement('option');fresh.value=NEW;uiText(fresh,'textContent',()=>t('series.new_series'));select.append(fresh);
  const series=view.series;
  select.value=series?series.id:'';form.elements.number.value=series?series.number:'';
  form.elements.start.value=series?.start?`${series.start.offset}, ${series.start.anchor}`:'';
  form.elements.new_title.closest('label').hidden=true;
  form.dataset.revision=view.story.revision;
  const status=form.querySelector('[data-series-status]');uiText(status,'textContent',()=>series?statusText(series.status):'');
  const refresh=form.querySelector('[data-series-refresh]');
  refresh.hidden=!series||!['source_changed','source_finished'].includes(series.status.state);
  const link=form.querySelector('[data-series-link]');link.hidden=!series;if(series)link.href=`/series/${series.id}`;
}

function install(){
  form.hidden=false;
  form.elements.series_id.onchange=()=>{form.elements.new_title.closest('label').hidden=form.elements.series_id.value!==NEW};
  form.onsubmit=async event=>{
    event.preventDefault();
    try{
      let seriesId=form.elements.series_id.value||null;
      if(seriesId===NEW)seriesId=(await api('/api/series',json('POST',{title:form.elements.new_title.value}))).id;
      const number=form.elements.number.value?Number(form.elements.number.value):null;
      await api(`/api/stories/${storyId}/series`,json('PATCH',{series_id:seriesId,number:seriesId?number:null,
        start_text:seriesId?form.elements.start.value:null,expected_revision:Number(form.dataset.revision)}));
      notice(msg('series.saved'));
    }catch(error){notice(error.message,'error')}
    await load().catch(error=>notice(error.message,'error'));
  };
  form.querySelector('[data-series-refresh]').onclick=async()=>{if(await refreshBook(storyId))await load()};
  load().catch(error=>notice(error.message,'error'));
}

if(form&&storyId)appInfo().then(info=>{if(info.long_prose!==false)install()});
