// SERIES-S11: the facts of later books in a prequel's settings — the records of its start memory by category, each
// marked «Минуле» (already happened, becomes the prequel's memory) or «Майбутнє» (the writer must not contradict it).
// Saving sends only the changed marks with the revision the author saw and asks first: it stales the first scenes.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {appInfo} from './app-info.js';
import {confirmDialog} from './dialogs.js';

const CATEGORIES=['facts','character_states','open_threads','timeline'];
const form=document.querySelector('#story-series-form');
const dialog=document.querySelector('#series-facts-dialog');
const storyId=document.querySelector('.settings-page')?.dataset.storyId;
let facts=[],chosen={},titles={},revision=null;

function element(tag,className,text){
  const item=document.createElement(tag);if(className)item.className=className;
  if(text!==undefined)uiText(item,'textContent',typeof text==='function'?text:()=>text);return item;
}

const changed=()=>facts.filter(fact=>chosen[fact.key]!==fact.decision);

function updateCounter(){
  const count=changed().length;
  uiText(dialog.querySelector('[data-facts-changed]'),'textContent',()=>t('series.facts.changed',{p0:count}));
  dialog.querySelector('[data-facts-save]').disabled=count===0;
}

function choice(fact,index,value){
  const label=document.createElement('label');label.className='series-fact-choice';
  const input=document.createElement('input');input.type='radio';input.name=`series-fact-${index}`;input.value=value;
  input.checked=chosen[fact.key]===value;
  input.onchange=()=>{chosen[fact.key]=value;updateCounter()};
  label.append(input,element('span','',()=>t(`series.facts.${value}`)));return label;
}

function render(){
  const list=dialog.querySelector('[data-facts-list]');list.replaceChildren();
  if(!facts.length)list.append(element('p','muted',()=>t('series.facts.empty')));
  let index=0;
  for(const category of CATEGORIES){
    const group=facts.filter(fact=>fact.category===category);
    if(!group.length)continue;
    const section=element('section','series-facts-group');
    section.append(element('h3','',()=>t(`series.facts.category.${category}`)));
    for(const fact of group){
      const row=element('div','series-fact');
      const text=element('p','series-fact-text',fact.text);
      const source=titles[fact.story_id];
      if(source)text.append(element('span','muted series-fact-source',()=>' '+t('series.facts.from',{p0:source})));
      const choices=element('div','series-fact-choices');
      choices.append(choice(fact,index,'past'),choice(fact,index,'future'));
      row.append(text,choices);section.append(row);index+=1;
    }
    list.append(section);
  }
  updateCounter();
}

async function open(){
  const [data,view]=await Promise.all([api(`/api/stories/${storyId}/series/facts`),api(`/api/stories/${storyId}`)]);
  const series=view.series?await api(`/api/series/${view.series.id}`):{books:[]};
  facts=data.facts;chosen=Object.fromEntries(facts.map(fact=>[fact.key,fact.decision]));revision=view.story.revision;
  titles=Object.fromEntries(series.books.map(book=>[book.id,book.title]));
  render();dialog.showModal();
}

async function save(){
  const decisions=Object.fromEntries(changed().map(fact=>[fact.key,chosen[fact.key]]));
  if(!Object.keys(decisions).length)return;
  if(!await confirmDialog(t('series.facts.confirm'),{accept:t('series.facts.save'),cancel:t('series.cancel')}))return;
  try{
    await api(`/api/stories/${storyId}/series/decisions`,json('PUT',{decisions,expected_revision:revision,confirm:true}));
    dialog.close();notice(msg('series.facts.saved'));
    document.dispatchEvent(new CustomEvent('series-changed'));
  }catch(error){notice(error.message,'error');if(String(error.status)==='409')await open().catch(()=>{})}
}

function install(){
  const button=form.querySelector('[data-series-facts]');
  button.onclick=()=>open().catch(error=>notice(error.message,'error'));
  dialog.querySelector('[data-facts-close]').onclick=()=>dialog.close();
  dialog.querySelector('[data-facts-all-future]').onclick=()=>{for(const fact of facts)chosen[fact.key]='future';render()};
  dialog.querySelector('[data-facts-save]').onclick=()=>save();
}

if(form&&dialog&&storyId)appInfo().then(info=>{if(info.long_prose!==false)install()});
