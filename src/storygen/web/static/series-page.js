// SERIES-S07: the series list and the series screen (variant B): release order on the left, the chronology axis by
// «Початок» on the right, books off the axis below it. Every write sends the revision the author saw.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {confirmDialog,promptDialog} from './dialogs.js';
import {statusText,refreshBook} from './series-status.js';

const page=document.querySelector('.series-page');
const seriesId=page?.dataset.seriesId;
let view=null;

function element(tag,className,text){
  const item=document.createElement(tag);if(className)item.className=className;
  if(text!==undefined)uiText(item,'textContent',typeof text==='function'?text:()=>text);return item;
}

async function loadList(){
  const list=page.querySelector('#series-list');list.replaceChildren();
  const items=await api('/api/series');
  if(!items.length){list.append(element('p','muted',()=>t('series.empty')));return}
  for(const item of items){
    const card=element('article','card');const link=document.createElement('a');link.href=`/series/${item.id}`;
    link.append(element('h2','',item.title));card.append(link);list.append(card);
  }
}

function bookCard(book){
  const card=element('article','card series-book');card.dataset.bookId=book.id;
  card.append(element('h3','',()=>t('series.book_heading',{p0:book.number,p1:book.title})));
  if(book.trashed)card.append(element('p','series-trashed',()=>t('series.trashed')));
  card.append(element('p','series-status',()=>statusText(book.status)));
  const actions=element('div','actions');
  const open=document.createElement('a');open.className='button secondary';open.href=`/stories/${book.id}`;
  uiText(open,'textContent',()=>t('series.open'));actions.append(open);
  if(!book.trashed&&['source_changed','source_finished'].includes(book.status.state)){
    const refresh=element('button','',()=>t('series.refresh'));refresh.type='button';
    refresh.onclick=async()=>{if(await refreshBook(book.id))await loadSeries()};actions.append(refresh);
  }
  card.append(actions);return card;
}

function renderSeries(){
  uiText(page.querySelector('#series-title'),'textContent',()=>view.series.title);
  page.querySelector('#series-rename').elements.title.value=view.series.title;
  page.querySelector('#series-books').replaceChildren(...view.books.map(bookCard));
  const byId=Object.fromEntries(view.books.map(book=>[book.id,book]));
  page.querySelector('#series-axis').replaceChildren(...view.placed.map(id=>element('li','',()=>t('series.axis_item',{p0:byId[id].start.offset,p1:byId[id].number,p2:byId[id].title}))));
  page.querySelector('#series-outside').replaceChildren(...view.outside.map(id=>element('li','',()=>t('series.book_heading',{p0:byId[id].number,p1:byId[id].title}))));
  const remove=page.querySelector('#series-delete');remove.disabled=view.books.length>0;
  uiText(remove,'title',()=>view.books.length?t('series.delete_blocked'):'');
}

async function loadSeries(){view=await api(`/api/series/${seriesId}`);renderSeries()}

function installScreen(){
  page.querySelector('#series-rename').onsubmit=async event=>{
    event.preventDefault();
    try{await api(`/api/series/${seriesId}`,json('PATCH',{title:event.target.elements.title.value,expected_revision:view.series.revision}));notice(msg('series.saved'))}
    catch(error){notice(error.message,'error')}
    await loadSeries().catch(error=>notice(error.message,'error'));
  };
  page.querySelector('#series-new-book').onclick=async()=>{
    const title=await promptDialog(t('series.new_book_prompt'));if(!title||!title.trim())return;
    try{const story=await api(`/api/series/${seriesId}/books`,json('POST',{title:title.trim()}));location.href=`/stories/${story.id}`}
    catch(error){notice(error.message,'error')}
  };
  page.querySelector('#series-delete').onclick=async()=>{
    if(!await confirmDialog(t('series.delete_confirm')))return;
    try{await api(`/api/series/${seriesId}?expected_revision=${view.series.revision}`,{method:'DELETE'});location.href='/series'}
    catch(error){notice(error.message,'error')}
  };
  loadSeries().catch(error=>notice(error.message,'error'));
}

function installIndex(){
  page.querySelector('#series-create').onsubmit=async event=>{
    event.preventDefault();
    try{const item=await api('/api/series',json('POST',{title:event.target.elements.title.value}));location.href=`/series/${item.id}`}
    catch(error){notice(error.message,'error')}
  };
  loadList().catch(error=>notice(error.message,'error'));
}

if(page)(seriesId?installScreen:installIndex)();
