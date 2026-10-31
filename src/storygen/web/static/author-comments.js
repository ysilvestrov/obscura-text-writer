import {t,uiText,uiAttr,diagnostic} from './i18n.js';
import {notePayload,notesFingerprint,instructionLimit} from './comment-state.js';
import {state,textEditor,registerAuthorComments} from './editor.js';
import {api,notice} from './api.js';

export function mountAuthorComments({host,state,editor,api,notice,document}){
  const node=(tag,key)=>{const element=document.createElement(tag);if(key)uiText(element,'textContent',()=>t(key));return element;};
  const label=node('label','comments.general');label.htmlFor='author-general';
  const general=node('textarea');general.id='author-general';general.rows=3;uiAttr(general,'placeholder',()=>t('comments.general_placeholder'));
  const help=node('p','comments.save_help');help.className='muted';
  const status=node('p');status.setAttribute('role','status');
  const details=node('details'),summary=node('summary','comments.fragments'),list=node('div');details.append(summary,list);
  host.append(label,general,help,status,details);
  const popup=node('section');popup.id='author-comment-popover';popup.setAttribute('popover','manual');popup.setAttribute('role','dialog');popup.setAttribute('aria-labelledby','author-comment-title');
  const title=node('h3','comments.fragment');title.id='author-comment-title';
  const quote=node('blockquote');const inputLabel=node('label','comments.instruction');inputLabel.htmlFor='author-comment-input';
  const input=node('textarea');input.id='author-comment-input';input.rows=4;
  const error=node('p');error.setAttribute('role','alert');
  const actions=node('div');actions.className='actions';
  const save=node('button','comments.save'),cancel=node('button','comments.cancel'),remove=node('button','comments.delete');
  for(const button of [save,cancel,remove])button.type='button';cancel.className=remove.className='secondary';
  actions.append(save,cancel,remove);popup.append(title,quote,inputLabel,input,error,actions,node('p','comments.save_help'));document.body.append(popup);
  let context=null,loading=false,ready=false,locked=false,epoch=0,revision=0,baseline='',lastWorking='',instructions=new Map(),mutating=false;
  let popupId=null,candidate=null,popupChanged=false,popupOriginal='';
  const active=()=>state.mode==='draft'&&state.bufferOrigin!=='history'&&!!state.scene;
  const key=()=>state.scene?.id+':'+(editor.identity().version_id||'-');
  const capturePayload=()=>notePayload(general.value,instructions,editor.captureComments());
  function dirty(){return ready&&(editor.isDirty()||notesFingerprint(capturePayload())!==baseline||popupChanged);}
  function changed(){
    if(mutating||!active()||!ready)return;
    const fingerprint=notesFingerprint(capturePayload())+(popupChanged?'\n'+input.value:'');
    if(fingerprint!==lastWorking)state.bufferEpoch++;
    lastWorking=fingerprint;state.dirty=dirty();
    uiText(document.querySelector('#save-state'),'textContent',()=>t(state.dirty?'m_ee929a68273c':'m_4fc1598084c2'));
    document.dispatchEvent(new CustomEvent('editor-state-changed'));render();
  }
  function close(){if(popup.matches(':popover-open'))popup.hidePopover();popupChanged=false;popupId=null;candidate=null;editor.focus();}
  function controls(){
    host.hidden=!active();general.disabled=loading||locked||!ready;
    for(const button of [save,remove])button.disabled=locked||loading;
    if(active()&&(loading||locked))document.querySelector('#save-text').disabled=true;
  }
  function render(){
    controls();list.replaceChildren();if(!active()||!ready)return;
    const payload=capturePayload();details.hidden=!payload.comments.length;
    const pending=payload.comments.filter(comment=>comment.anchor.state==='needs_review').length;
    uiText(status,'textContent',()=>pending?t('comments.pending_count',{p0:pending}):state.dirty?t('comments.unsaved'):t('comments.saved'));
    if(pending)details.open=true;
    for(const comment of payload.comments){
      const row=node('div');row.className='author-comment-row';
      const excerpt=node('p');excerpt.textContent=comment.anchor.display_quote;
      const instruction=node('p');instruction.textContent=comment.instruction;
      const edit=node('button','comments.edit');edit.type='button';edit.className='secondary';edit.disabled=locked;edit.onclick=()=>open(comment.id);
      row.append(excerpt,instruction,edit);
      if(comment.anchor.state==='needs_review'){
        row.append(node('p','comments.needs_reattachment'));
        const attach=node('button','comments.reattach');attach.type='button';attach.className='secondary';attach.disabled=locked||!editor.canComment().allowed;
        attach.onclick=()=>{
          try{const value=editor.prepareComment(comment.id);mutating=true;editor.upsertComment(value);mutating=false;changed();}
          catch(reason){mutating=false;notice(diagnostic(reason.message),'error');}
        };row.append(attach);
      }
      list.append(row);
    }
  }
  function open(id=null){
    if(!ready||loading||locked||!active())return;
    if(id&&!instructions.has(id))return;
    try{
      popupId=id||crypto.randomUUID();candidate=id?null:editor.prepareComment(popupId);
      if(id)editor.selectComment(id);
      quote.textContent=id?editor.commentQuote(id):candidate.origin.anchor.display_quote;
      input.value=id?instructions.get(id)||'':'';popupOriginal=input.value;popupChanged=false;
      error.textContent='';remove.hidden=!id;
      const selection=window.getSelection();popup.anchorRect=selection?.rangeCount?selection.getRangeAt(0).getBoundingClientRect():host.getBoundingClientRect();
      popup.showPopover();positionPopup();input.focus();
    }catch(reason){notice(diagnostic(reason.message),'error');}
  }
  popup.addEventListener('toggle',event=>{if(event.newState==='closed'){popupChanged=false;popupId=null;candidate=null;changed();}});
  document.addEventListener('pointerdown',event=>{
    if(popup.matches(':popover-open')&&!popup.contains(event.target)&&!event.target.closest?.('[data-ui-locale]')){close();changed();}
  },true);
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&popup.matches(':popover-open')){event.preventDefault();close();changed();}
  },true);
  function positionPopup(){
    if(!popup.matches(':popover-open'))return;
    const width=window.visualViewport?.width||window.innerWidth,height=window.visualViewport?.height||window.innerHeight;
    popup.style.maxHeight=Math.max(160,height-32)+'px';
    const rect=popup.anchorRect,box=popup.getBoundingClientRect();
    popup.style.left=Math.max(16,Math.min(rect.left,width-box.width-16))+'px';
    const below=rect.bottom+8;
    popup.style.top=Math.max(16,Math.min(below+box.height<=height-16?below:rect.top-box.height-8,height-box.height-16))+'px';
  }
  window.visualViewport?.addEventListener('resize',positionPopup);
  window.addEventListener('resize',positionPopup);
  input.oninput=()=>{popupChanged=input.value!==popupOriginal;changed();};
  save.onclick=()=>{
    if(!popupId||locked)return;
    if(!input.value.trim()||[...input.value].length>8000){uiText(error,'textContent',()=>t('comments.limit_instruction'));return;}
    const old=instructions.get(popupId);
    try{
      mutating=true;instructions.set(popupId,input.value);
      if(candidate)editor.upsertComment(candidate);
      const issue=instructionLimit(capturePayload());if(issue)throw new Error(t(issue));
      mutating=false;close();changed();
    }catch(reason){
      if(old===undefined){instructions.delete(popupId);if(candidate)editor.removeComment(popupId);}else instructions.set(popupId,old);
      mutating=false;error.textContent=diagnostic(reason.message);
    }
  };
  cancel.onclick=()=>{close();changed();};
  remove.onclick=()=>{if(!popupId||locked)return;mutating=true;instructions.delete(popupId);editor.removeComment(popupId);mutating=false;close();changed();};
  general.oninput=changed;
  // ProseMirror handleClick runs during mouseup; open after native light-dismiss.
  editor.setCommentHandlers({onCreate:()=>open(),onClick:id=>setTimeout(()=>open(id),0),onChange:()=>{if(!mutating)changed();}});
  editor.onTransaction(()=>{if(ready&&!loading&&!locked)render();});
  async function load(){
    const captured=key(),requestEpoch=++epoch;context=captured;loading=true;ready=false;instructions=new Map();general.value='';
    close();
    editor.readOnly(true);controls();uiText(status,'textContent',()=>t('comments.loading'));
    try{
      const data=await api(`/api/scenes/${state.scene.id}/comments`);
      if(requestEpoch!==epoch||!active()||captured!==key())return;
      if(data.source_version_id!==editor.identity().version_id&&!(data.source_version_id===null&&!editor.identity().version_id))throw new Error(t('comments.source_changed'));
      revision=data.expected_comments_revision;general.value=data.comment_set?.general||'';
      instructions=new Map((data.comment_set?.comments||[]).map(comment=>[comment.id,comment.instruction]));
      editor.setComments(data.comment_set,{mismatch:!data.source_matches_current});
      baseline=notesFingerprint(capturePayload());lastWorking=baseline;ready=true;
    }catch(reason){if(requestEpoch===epoch&&active()&&captured===key())status.textContent=diagnostic(reason.message);}
    finally{if(requestEpoch===epoch&&active()&&captured===key()){loading=false;editor.readOnly(locked);if(ready){document.querySelector('#save-text').disabled=false;render();document.dispatchEvent(new CustomEvent('editor-state-changed'));}else controls();}}
  }
  function sync(){
    if(!active()){if(context!==null){epoch++;context=null;ready=false;loading=false;close();}controls();return;}
    if(context!==key()){void load();return;}
    controls();
  }
  for(const event of ['editor-state-changed','scene-selected','story-refreshed'])document.addEventListener(event,sync);
  const controller={
    capture(){
      if(!active()||!ready||loading||context!==key())throw new Error(t('comments.wait_loading'));
      if(popup.matches(':popover-open')&&popupChanged)throw new Error(t('comments.finish_popup'));
      const payload=capturePayload(),issue=instructionLimit(payload);if(issue)throw new Error(t(issue));
      return {comment_set:payload,expected_comments_revision:revision,expected_source_version_id:editor.identity().version_id};
    },
    isDirty:()=>ready&&notesFingerprint(capturePayload())!==baseline,
    lock(value){locked=Boolean(value);if(active())editor.readOnly(locked||loading||!ready);controls();},
    saved(result){
      revision=result.comment_set?.revision||0;general.value=result.comment_set?.general||'';
      instructions=new Map((result.comment_set?.comments||[]).map(comment=>[comment.id,comment.instruction]));
      editor.setComments(result.comment_set);context=key();baseline=notesFingerprint(capturePayload());lastWorking=baseline;ready=true;render();
    },
  };
  sync();return controller;
}

const host=document.querySelector('#author-comments');
if(host)registerAuthorComments(mountAuthorComments({host,state,editor:textEditor,api,notice,document}));
