// SERIES-S07: the series list and the series screen (variant B): release order on the left, the chronology axis by
// «Початок» on the right, books off the axis below it. Every write sends the revision the author saw.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {confirmDialog,promptDialog} from './dialogs.js';
import {statusText,refreshBook} from './series-status.js';
import {appInfo} from './app-info.js';
import {claimTrial,trialState} from './long-prose-trial.js';

const page=document.querySelector('.series-page');
const seriesId=page?.dataset.seriesId;
let view=null,info=null;
// LONG-PROSE-TRIAL-S07: without long prose the pages offer the one trial and keep to its series; the server decides.
const store=()=>info?.long_prose===false;
const trial=()=>trialState(info);
const trialDeps=()=>({api,json,confirmDialog,notice,location});

function element(tag,className,text){
  const item=document.createElement(tag);if(className)item.className=className;
  if(text!==undefined)uiText(item,'textContent',typeof text==='function'?text:()=>text);return item;
}

// A series of another edition opens nowhere here: its row is no link. While the trial is free, a series of at most two
// books (the bible aside) offers to become the trial series; once the trial is on a series, only that series is listed.
async function loadList(){
  const list=page.querySelector('#series-list');list.replaceChildren();
  let items=await api('/api/series');
  const state=trial(),open=item=>!store()||state.kind==='series'&&state.id===item.id;
  if(store()&&state.state==='used')items=items.filter(item=>item.id===state.id);
  if(!items.length){list.append(element('p','muted',()=>t('series.empty')));return}
  for(const item of items){
    const card=element('article','card');
    if(open(item)){const link=document.createElement('a');link.href=`/series/${item.id}`;link.append(element('h2','',item.title));card.append(link)}
    else card.append(element('h2','',item.title));
    list.append(card);
    if(store()&&state.state==='available')offerSeries(card,item).catch(()=>{});
  }
}

async function offerSeries(card,item){
  const data=await api(`/api/series/${item.id}`);
  if(data.books.filter(book=>!book.bible).length>2)return;
  const offer=element('button','secondary',()=>t('trial.offer_series'));offer.type='button';
  offer.onclick=()=>claimTrial(trialDeps(),{series_id:item.id},item.title);
  card.append(offer);
}

// SERIES-S11: a book whose start memory merged two or more books (after a prequel) lists its sources and the conflicts
// the automatic merge settled, by book titles; a title missing from the series falls back to the plain ID.
function sourcesBlock(book,titles){
  const sources=book.status.sources||[];if(sources.length<2)return [];
  const name=id=>`«${titles[id]||id}»`;
  const blocks=[element('p','series-sources muted',()=>t('series.sources',{p0:sources.map(name).join(', ')}))];
  const resolved=book.status.resolved||[];
  if(resolved.length){
    const details=element('details','series-resolved');
    details.append(element('summary','',()=>t('series.resolved_summary',{p0:resolved.length})));
    const list=element('ul','');
    for(const item of resolved)for(const dropped of item.dropped)
      list.append(element('li','',()=>t('series.resolved_item',{p0:dropped.text,p1:name(dropped.story_id),p2:name(item.kept_story_id)})));
    details.append(list);blocks.push(details);
  }
  return blocks;
}

function bookCard(book){
  const card=element('article','card series-book');card.dataset.bookId=book.id;
  card.append(element('h3','',()=>book.bible?book.title:t('series.book_heading',{p0:book.number,p1:book.title})));
  if(book.trashed)card.append(element('p','series-trashed',()=>t('series.trashed')));
  card.append(element('p','series-status',()=>statusText(book.status)));
  card.append(...sourcesBlock(book,Object.fromEntries(view.books.map(item=>[item.id,item.title]))));
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
  // SERIES-BIBLE: the world bible stands apart, above the books, and is off the axis.
  const bible=view.books.find(book=>book.bible);
  page.querySelector('#series-bible').hidden=!bible;
  page.querySelector('[data-series-bible-card]').replaceChildren(...(bible?[bookCard(bible)]:[]));
  page.querySelector('#series-new-bible').hidden=Boolean(bible);
  page.querySelector('#series-books').replaceChildren(...view.books.filter(book=>!book.bible).map(bookCard));
  const byId=Object.fromEntries(view.books.map(book=>[book.id,book]));
  // The origin is the book without «Початок»; every other book on the axis shows its offset from the anchor.
  const mark=book=>book.start?book.start.offset:t('series.origin');
  page.querySelector('#series-axis').replaceChildren(...view.placed.map(id=>element('li','',()=>t('series.axis_item',{p0:mark(byId[id]),p1:byId[id].number,p2:byId[id].title}))));
  page.querySelector('#series-outside').replaceChildren(...view.outside.map(id=>element('li','',()=>t('series.book_heading',{p0:byId[id].number,p1:byId[id].title}))));
  // The trial series holds two books: a third is the paid version's (the server refuses it as well).
  const full=store()&&trial().kind==='series'&&trial().id===seriesId&&view.books.filter(book=>!book.bible).length>=2;
  const newBook=page.querySelector('#series-new-book');newBook.disabled=full;
  uiText(newBook,'title',()=>full?t('trial.refusal.series_full'):'');
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
  page.querySelector('#series-new-bible').onclick=async()=>{
    const title=await promptDialog(t('series.new_bible_prompt'));if(!title||!title.trim())return;
    try{const story=await api(`/api/series/${seriesId}/bible`,json('POST',{title:title.trim()}));location.href=`/stories/${story.id}`}
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
  const form=page.querySelector('#series-create'),state=trial();
  const asTrial=store()&&state.state==='available';
  if(store()&&state.state==='used')form.hidden=true;
  if(asTrial){
    const hint=element('p','muted series-trial-hint',()=>t('trial.series_list_hint'));form.before(hint);
    const label=form.querySelector('button span')||form.querySelector('button');label.dataset.i18n='trial.create_series';
    uiText(label,'textContent',()=>t('trial.create_series'));
  }
  form.onsubmit=async event=>{
    event.preventDefault();
    const title=event.target.elements.title.value;
    if(asTrial&&!await confirmDialog(t('trial.confirm',{p0:title})))return;
    try{
      const item=await api('/api/series',json('POST',{title,...(asTrial?{trial:true}:{})}));
      if(asTrial)location.reload();else location.href=`/series/${item.id}`;
    }catch(error){notice(error.message,'error')}
  };
  loadList().catch(error=>notice(error.message,'error'));
}

if(page)appInfo().then(value=>{info=value;(seriesId?installScreen:installIndex)()});
