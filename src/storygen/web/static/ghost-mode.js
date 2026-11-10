// Ghost Mode (#55): rewrite the current AI draft from memory, block by block.
// At any moment the author either reads the AI block (before typing, or while holding Tab / the Peek button) or writes.
import {t,uiText,uiAttr,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
import {confirmDialog} from './dialogs.js';
import {createTextEditor} from './text-editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import * as model from './ghost-session.js';

const entry=document.querySelector('#ghost-entry'),root=document.querySelector('#ghost-mode');
const storage=(()=>{try{return globalThis.localStorage;}catch{return null;}})();

if(entry&&root){
  const el=(tag,className,render)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n;};
  const btn=(render,onclick,className='secondary')=>{const b=el('button',className,render);b.type='button';b.onclick=onclick;return b;};

  // Entry next to the draft.
  const active=()=>state.mode==='draft'&&state.bufferOrigin!=='history'&&!!state.scene?.heads?.draft;
  const headDraft=()=>state.workspaceMaterials?.draft;
  const resumable=()=>!!(state.scene&&model.findSession(storage,state.scene.id));
  const start=btn(()=>t(resumable()?'ghost.resume':'ghost.start'),()=>void open(),'secondary ghost-start');
  const entryStats=el('p','muted ghost-entry-stats');
  entry.append(start,entryStats);
  function syncEntry(){
    entry.hidden=!active();
    if(entry.hidden)return;
    const ref=headDraft();
    start.disabled=state.dirty||state.saving||(ref&&!ref.complete);
    uiAttr(start,'title',()=>state.dirty?t('ghost.save_first'):'');
    uiText(start,'textContent',()=>t(resumable()?'ghost.resume':'ghost.start'));
    entryStats.hidden=!ref?.ghost_rewrite;
    uiText(entryStats,'textContent',()=>model.ghostStatsText(ref?.ghost_rewrite,t));
  }
  for(const event of ['editor-state-changed','scene-selected','story-refreshed','workspace-statistics'])document.addEventListener(event,syncEntry);

  // The full-screen mode.
  root.className='ghost-mode';root.setAttribute('role','dialog');root.setAttribute('aria-modal','true');root.tabIndex=-1;
  const title=el('h2',null,()=>t('ghost.title'));uiAttr(root,'aria-label',()=>t('ghost.title'));
  const progress=el('p','ghost-progress');progress.setAttribute('aria-live','polite');
  const changed=el('p','ghost-warning',()=>t('ghost.draft_changed'));
  const hint=el('p','muted ghost-hint',()=>t('ghost.hint'));
  const aiBox=el('section','ghost-ai');
  const aiLabel=el('h3',null,()=>t('ghost.ai_block'));
  const separatorNote=el('p','ghost-separator',()=>t('ghost.separator'));
  const skippedNote=el('p','ghost-skipped',()=>t('ghost.skipped_note'));
  const authorBox=el('section','ghost-author');
  const authorLabel=el('h3',null,()=>t('ghost.your_text'));
  const aiHosts=el('div','ghost-ai-hosts'),authorHosts=el('div','ghost-author-hosts');
  aiBox.append(aiLabel,aiHosts);authorBox.append(authorLabel,authorHosts);
  const peekButton=btn(()=>t('ghost.peek'),null,'secondary ghost-peek');
  const back=btn(()=>t('ghost.back'),()=>move(-1));
  const next=btn(()=>t('ghost.next'),()=>move(1));
  const skipButton=btn(()=>t('ghost.skip'),()=>toggleSkip());
  const save=btn(()=>t('ghost.save'),()=>void submit(),'ghost-save');
  const cancel=btn(()=>t('ghost.cancel'),()=>void close(true));
  const nav=el('div','actions ghost-nav');nav.append(back,peekButton,skipButton,next);
  const finish=el('div','actions ghost-finish');finish.append(save,cancel);
  const header=el('header','ghost-header');header.append(title,progress);
  root.append(header,changed,hint,aiBox,separatorNote,skippedNote,authorBox,nav,finish);

  let session=null,busy=false,peekSince=0;
  const aiEditors=new Map(),authorEditors=new Map();
  const block=()=>session?.blocks[session.index];

  function editorFor(map,host,index,text,readOnly){
    if(!map.has(index)){
      const area=document.createElement('textarea');area.hidden=true;
      const wrap=el('div','ghost-editor');wrap.dataset.index=String(index);wrap.append(area);host.append(wrap);
      const editor=createTextEditor(area);
      editor.write(text,{material:'draft',content_format:session.format});
      editor.readOnly(readOnly);
      if(!readOnly){
        editor.placeholder(t('ghost.placeholder'));
        editor.onInput(()=>{if(index!==session?.index)return;if(model.input(session,editor.read()))persist();render();});
      }
      map.set(index,{editor,wrap});
    }
    return map.get(index);
  }

  const persist=()=>model.saveSession(storage,session);

  function render(){
    if(!session)return;
    const current=block(),index=session.index,count=session.blocks.length;
    uiText(progress,'textContent',()=>t('ghost.progress',{p0:index+1,p1:count,p2:model.writtenCount(session),p3:model.skippedCount(session)}));
    changed.hidden=state.scene?.heads?.draft===session.draftId;
    const text=current.kind==='text',peeking=current.state==='peek',reading=current.state==='reading',skipped=current.state==='skipped';
    for(const [i,{wrap}] of aiEditors)wrap.hidden=i!==index;
    for(const [i,{wrap}] of authorEditors)wrap.hidden=i!==index;
    separatorNote.hidden=text;skippedNote.hidden=!skipped;
    // The AI block is visible before typing and during a peek; the author's text never at the same time.
    aiBox.hidden=!text||!(reading||peeking);aiBox.setAttribute('aria-hidden',String(aiBox.hidden));
    authorBox.hidden=!text||skipped||peeking;
    if(text){
      editorFor(aiEditors,aiHosts,index,current.source,true);
      const author=editorFor(authorEditors,authorHosts,index,current.text,false);
      author.editor.readOnly(peeking||busy);
    }
    root.classList.toggle('peeking',peeking);
    peekButton.disabled=!text||current.state!=='writing'&&!peeking;
    peekButton.setAttribute('aria-pressed',String(peeking));
    back.disabled=peeking||index===0;next.disabled=peeking||index===count-1;
    skipButton.hidden=!text;skipButton.disabled=peeking;
    uiText(skipButton,'textContent',()=>t(skipped?'ghost.unskip':'ghost.skip'));
    save.disabled=busy||peeking||!model.canSave(session);
    cancel.disabled=busy;
  }

  function focusAuthor(){const current=block();if(current?.kind==='text'&&current.state==='writing'||current?.state==='reading')authorEditors.get(session.index)?.editor.focus();}

  function move(delta){if(!session||!model.go(session,delta))return;persist();render();focusAuthor();}
  function toggleSkip(){if(!session)return;const current=block();if(current.state==='skipped')model.unskip(session);else model.skip(session);persist();render();if(current.state!=='skipped')focusAuthor();}

  function peekOn(){
    if(!session||!model.peekStart(session))return false;
    peekSince=performance.now();root.focus({preventScroll:true});render();return true;
  }
  function peekOff(){
    if(!session||block()?.state!=='peek')return;
    model.peekEnd(session,performance.now()-peekSince);persist();render();focusAuthor();
  }

  root.addEventListener('keydown',event=>{
    if(!session)return;
    const current=block();
    if(current?.state==='peek'){
      // Nothing edits the text while the AI block is visible.
      event.preventDefault();event.stopPropagation();return;
    }
    if(event.key==='Tab'&&!event.ctrlKey&&!event.altKey&&!event.metaKey&&authorHosts.contains(event.target)){
      event.preventDefault();event.stopPropagation();
      if(!event.repeat&&!event.isComposing)peekOn();
      return;
    }
    if(event.key==='Enter'&&(event.ctrlKey||event.metaKey)){event.preventDefault();event.stopPropagation();move(1);return;}
    if(event.key==='Escape'&&authorHosts.contains(event.target)){event.preventDefault();event.stopPropagation();root.focus({preventScroll:true});}
  },true);
  root.addEventListener('keyup',event=>{if(event.key==='Tab')peekOff();},true);
  globalThis.addEventListener?.('blur',peekOff);
  document.addEventListener('visibilitychange',()=>{if(document.hidden)peekOff();});
  peekButton.addEventListener('pointerdown',event=>{event.preventDefault();if(peekOn())try{peekButton.setPointerCapture(event.pointerId);}catch{}});
  for(const type of ['pointerup','pointercancel','pointerleave'])peekButton.addEventListener(type,peekOff);
  peekButton.addEventListener('keydown',event=>{if((event.key===' '||event.key==='Enter')&&!event.repeat){event.preventDefault();peekOn();}});
  peekButton.addEventListener('keyup',event=>{if(event.key===' '||event.key==='Enter')peekOff();});

  // Pasting and dropping into the author's text are blocked; the AI text cannot be copied.
  for(const type of ['paste','drop'])authorHosts.addEventListener(type,event=>{
    event.preventDefault();event.stopPropagation();
    if(session){model.blockPasted(session);persist();}
    notice(t('ghost.paste_blocked'),'error');
  },true);
  for(const type of ['copy','cut','dragstart'])aiHosts.addEventListener(type,event=>{event.preventDefault();event.stopPropagation();},true);

  async function open(){
    if(!active()||state.dirty||state.saving)return;
    const scene=state.scene;
    try{
      const resumeId=model.findSession(storage,scene.id);
      const draftId=resumeId||scene.heads.draft;
      const material=await api('/api/versions/'+draftId);
      if(!material.version.complete||material.version.kind!=='draft')throw new Error(t('ghost.invalid_source'));
      session=(resumeId&&model.loadSession(storage,scene.id,resumeId))||model.createSession({sceneId:scene.id,draftId,format:material.version.content_format,text:material.text});
      if(!session.blocks.some(b=>b.kind==='text'))throw new Error(t('ghost.empty_draft'));
      persist();
      aiEditors.clear();authorEditors.clear();aiHosts.replaceChildren();authorHosts.replaceChildren();
      root.hidden=false;document.body.classList.add('ghost-open');
      render();focusAuthor();
    }catch(error){session=null;notice(diagnostic(error.message),'error');}
  }

  async function close(ask){
    if(!session||busy)return;
    if(ask&&model.hasWork(session)&&!await confirmDialog(t('ghost.cancel_confirm')))return;
    if(ask)model.dropSession(storage,session.sceneId,session.draftId);
    session=null;root.hidden=true;document.body.classList.remove('ghost-open');
    aiHosts.replaceChildren();authorHosts.replaceChildren();aiEditors.clear();authorEditors.clear();
    syncEntry();
  }

  async function submit(){
    if(!session||busy||!model.canSave(session))return;
    const skipped=model.skippedCount(session);
    if(skipped&&!await confirmDialog(t('ghost.skipped_confirm',{p0:skipped})))return;
    busy=true;render();
    const captured=session;
    try{
      const scene=state.view?.scenes?.find(item=>item.id===captured.sceneId)||state.scene;
      const result=await api(`/api/scenes/${captured.sceneId}/ghost-rewrite`,json('POST',{source_draft_id:captured.draftId,text:model.resultText(captured),
        content_format:captured.format,expected_revision:scene.revision,client_stats:model.clientStats(captured)}));
      model.dropSession(storage,captured.sceneId,captured.draftId);
      busy=false;await close(false);
      notice(model.ghostStatsText(result.version.ghost_rewrite,t));
      await refresh();
      if(state.scene?.id===captured.sceneId&&!state.dirty)await invokeWorkspaceCommand('show','draft');
    }catch(error){busy=false;notice(diagnostic(error.message),'error');try{await refresh();}catch{}render();}
  }

  globalThis.addEventListener?.('beforeunload',event=>{if(session&&model.hasWork(session)){persist();event.preventDefault();event.returnValue='';}});
  syncEntry();
}
