// BOOK-STRUCTURE-S06: the «Book structure» panel on the story settings page. Edits stay in a buffer until «Save»
// sends the whole structure in one PUT with the story revision; «Dissolve» is a DELETE after confirmation.
import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {appInfo} from './app-info.js';
import {confirmDialog} from './dialogs.js';
import {addArc,addPart,arcTitle,createBuffer,move,partTitle,payload,remove,rename,setProtagonist} from './book-structure.js';

const page=document.querySelector('.settings-page');
const storyId=page?.dataset.storyId;
const label=(key,n)=>t(key,{p0:n});
let view=null,buffer=null;

function button(key,action,secondary=true){
  const item=document.createElement('button');item.type='button';if(secondary)item.className='secondary';
  uiText(item,'textContent',()=>t(key));item.onclick=action;return item;
}

function apply(result){
  if(result){notice(msg(result),'error');return}
  render();
}

function row(kind,p,a,item,number){
  const line=document.createElement('div');line.className='book-structure-row book-structure-row-'+kind;
  const input=document.createElement('input');input.value=item.title;input.maxLength=200;
  input.placeholder=kind==='part'?partTitle({title:''},number,label):arcTitle({title:''},number,label);
  input.setAttribute('aria-label',input.placeholder);
  input.oninput=()=>rename(buffer,p,a,input.value);
  line.append(input);
  if(kind==='arc')line.append(protagonistField(p,a,item,input.placeholder));
  line.append(button('book.panel.up',()=>apply(move(buffer,p,a,-1))),button('book.panel.down',()=>apply(move(buffer,p,a,1))),
    button('book.panel.delete',()=>apply(remove(buffer,p,a))));
  // STORY-TIME: with a flashback in the book, an arc without a known start sees no flashbacks of other arcs.
  if(kind==='arc'&&(view.book_structure.arc_start_unknown||[]).includes(item.id)){
    const hint=document.createElement('small');hint.className='book-structure-arc-hint muted';
    uiText(hint,'textContent',()=>t('book.arc_start_unknown'));line.append(hint);
  }
  return line;
}

// BOOK-LINEAGE-S04: «Герой книги» or a card; a protagonist whose card is gone stays as an option, so a save keeps it.
function protagonistField(p,a,arc,name){
  const select=document.createElement('select');select.className='book-structure-protagonist';
  select.setAttribute('aria-label',t('book.panel.protagonist',{p0:arc.title||name}));
  const names=view.character_names||{};
  const option=(value,text)=>{const item=document.createElement('option');item.value=value;item.textContent=text;select.append(item)};
  option('',t('book.panel.protagonist_auto'));
  for(const [id,text] of Object.entries(names).sort((x,y)=>x[1].localeCompare(y[1])))option(id,text);
  if(arc.protagonist_id&&!(arc.protagonist_id in names))option(arc.protagonist_id,arc.protagonist_id);
  select.value=arc.protagonist_id||'';
  select.onchange=()=>setProtagonist(buffer,p,a,select.value);
  return select;
}

function render(){
  const panel=document.querySelector('#book-structure');if(!panel)return;
  const list=panel.querySelector('.book-structure-list');list.replaceChildren();
  buffer.parts.forEach((part,p)=>{
    const box=document.createElement('div');box.className='book-structure-part';
    box.append(row('part',p,null,part,p+1));
    part.arcs.forEach((arc,a)=>box.append(row('arc',p,a,arc,a+1)));
    box.append(button('book.panel.add_arc',()=>apply(addArc(buffer,p))));
    list.append(box);
  });
}

async function load(){
  view=await api('/api/stories/'+storyId);
  buffer=createBuffer(view.book_structure,view.scenes);
  render();
  const dissolve=document.querySelector('#book-structure-dissolve');if(dissolve)dissolve.hidden=!view.book_structure.explicit;
}

async function save(){
  try{
    await api(`/api/stories/${storyId}/structure`,json('PUT',payload(buffer,view.story.revision)));
    notice(msg('book.panel.saved'));await load();
  }catch(e){notice(e.message,'error')}  // the buffer stays as the author left it
}

async function dissolve(){
  if(!await confirmDialog(t('book.panel.dissolve_confirm')))return;
  try{
    await api(`/api/stories/${storyId}/structure`,json('DELETE',{expected_revision:view.story.revision}));
    notice(msg('book.panel.dissolved'));await load();
  }catch(e){notice(e.message,'error')}
}

function mount(){
  const host=document.querySelector('[data-settings-section="writing"]');if(!host||!storyId)return;
  const panel=document.createElement('section');panel.id='book-structure';panel.className='panel';
  const title=document.createElement('h2');uiText(title,'textContent',()=>t('book.panel.title'));
  const help=document.createElement('p');help.className='muted';uiText(help,'textContent',()=>t('book.panel.help'));
  const list=document.createElement('div');list.className='book-structure-list';
  const actions=document.createElement('div');actions.className='actions';
  const dissolveButton=button('book.panel.dissolve',dissolve);dissolveButton.id='book-structure-dissolve';
  actions.append(button('book.panel.add_part',()=>apply(addPart(buffer))),button('book.panel.save',save,false),dissolveButton);
  panel.append(title,help,list,actions);host.append(panel);
  load().catch(e=>notice(e.message,'error'));
}

// An edition without long prose shows no panel at all.
appInfo().then(info=>{if(info.long_prose!==false)mount()});
