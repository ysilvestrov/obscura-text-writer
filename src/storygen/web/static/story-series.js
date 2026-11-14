// SERIES: the series line under a book's title — series, number and the snapshot warning, linked to the series screen.
import {t,uiText} from './i18n.js';
import {api} from './api.js';
import {statusText} from './series-status.js';

const root=document.querySelector('#workspace[data-story-id]');
const line=document.querySelector('#story-series');

async function show(){
  const series=(await api(`/api/stories/${root.dataset.storyId}`)).series;
  if(!series){line.hidden=true;return}
  const link=document.createElement('a');link.href=`/series/${series.id}`;
  uiText(link,'textContent',()=>t('series.header',{p0:series.title,p1:series.number}));
  const state=document.createElement('span');state.className='series-header-status';
  const warn=series.status.prequel||['source_changed','source_finished','no_summary'].includes(series.status.state);
  uiText(state,'textContent',()=>warn?' · '+statusText(series.status):'');
  line.replaceChildren(link,state);line.hidden=false;
}

if(root&&line)show().catch(()=>{line.hidden=true});
