import {confirmDialog} from './dialogs.js';
import {createTextEditor} from './text-editor.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';

function action(label,callback){const button=document.createElement('button');button.type='button';button.className='secondary';uiText(button,"textContent",()=>(label));button.onclick=callback;return button}

export function installSceneTrash(state,refresh,clear){
  const trash=action(live(()=>(t("m_225f1a7f10a9"))),async()=>{
    if(state.dirty||state.saving){notice(msg("m_a4c2e86ecc1a"),'error');return}
    if(!state.scene){notice(msg("m_f0f1417db6de"),'error');return}
    const sceneId=state.scene.id,revision=state.scene.revision;
    if(!await confirmDialog(t("m_5853565cd7c6")))return;
    if(state.dirty||state.saving||state.scene?.id!==sceneId||state.scene.revision!==revision)return;
    trash.disabled=true;state.saving=true;
    const editor=createTextEditor(document.querySelector("#editor")),readOnly=editor.isReadOnly();editor.readOnly(true);
    document.dispatchEvent(new CustomEvent("editor-state-changed"));
    try{
      await api('/api/scenes/'+state.scene.id+'/trash',json('POST',{story_id:state.storyId,expected_revision:state.scene.revision}));
      clear();state.saving=false;await refresh();notice(msg("m_4731b2e61aa6"));
    }catch(error){notice(error.message,'error')}finally{trash.disabled=false;state.saving=false;editor.readOnly(readOnly);document.dispatchEvent(new CustomEvent('editor-state-changed'))}
  });
  (document.querySelector('#workspace-scene-actions')||document.querySelector('.editor-toolbar')).append(trash);
  function availability(){const reason=!state.scene?t("m_f0f1417db6de"):state.saving?t("m_1705600b6470"):state.dirty?t("m_a4c2e86ecc1a"):'';trash.disabled=!!reason;uiText(trash,"title",()=>(diagnostic(reason)))}
  for(const event of ['scene-selected','story-refreshed','editor-state-changed'])document.addEventListener(event,availability);availability();
  const details=document.createElement('details'),summary=document.createElement('summary'),list=document.createElement('div');
  uiText(summary,"textContent",()=>(t("m_62ad9a54bdd0")));details.append(summary,list);document.querySelector('.scene-panel').append(details);
  let epoch=0;
  async function load(){
    const current=++epoch;
    try{
      const result=await api('/api/stories/'+state.storyId+'/trash');if(current!==epoch)return;
      list.replaceChildren();
      for(const scene of result.scenes||[]){
        const row=document.createElement('p'),title=document.createElement('span');uiText(title,"textContent",()=>(scene.title+' '));
        const restore=action(live(()=>(t("m_11b6e5a88fd6"))),async()=>{
          if(state.dirty||state.saving){notice(msg("m_a4c2e86ecc1a"),'error');return}
          restore.disabled=true;
          try{await api('/api/scenes/'+scene.id+'/restore',json('POST',{story_id:state.storyId,expected_revision:scene.revision}));await refresh();notice(msg("m_415e821184f4"))}
          catch(error){notice(error.message,'error')}finally{restore.disabled=false}
        });row.append(title,restore);list.append(row);
      }
      if(!(result.scenes||[]).length){const empty=document.createElement('p');uiText(empty,"textContent",()=>(t("m_f5afb4e831d7")));list.append(empty)}
    }catch(error){notice(error.message,'error')}
  }
  document.addEventListener('story-refreshed',load);
}

export function installLibraryTrash(){
  for(const button of document.querySelectorAll('[data-trash-story]'))button.onclick=async()=>{
    if(button.disabled)return;
    button.disabled=true;
    try{
      const {runs}=await api('/api/stories/'+button.dataset.trashStory+'/runs');
      const closed=new Set(['completed','failed','cancelled']),stopped=new Set(['paused','interrupted','needs_review','alternative']);
      const pending=runs.filter(run=>!closed.has(run.state));
      if(pending.some(run=>!stopped.has(run.state)))throw new Error(t("m_6be0942b3149"));
      const message=pending.length?t("m_3c7a4d78d4f4",{p0:(pending.length)}):t("m_b1e87fa38fde");
      if(!await confirmDialog(message))return;
      for(const run of pending){
        const result=await api('/api/runs/'+run.id+'/cancel',json('POST',{}));
        if(!closed.has(result.state))throw new Error(t("m_6fd8fbdc1385"));
      }
      await api('/api/stories/'+button.dataset.trashStory+'/trash',json('POST',{expected_revision:Number(button.dataset.revision)}));location.reload();
    }catch(error){notice(error.message,'error')}
    finally{button.disabled=false}
  };
  const list=document.querySelector('#story-trash-list');
  async function load(){
    try{
      const result=await api('/api/trash');list.replaceChildren();
      for(const story of result.stories){
        const row=document.createElement('p'),title=document.createElement('span');uiText(title,"textContent",()=>(story.title+' '));
        const restore=action(live(()=>(t("m_11b6e5a88fd6"))),async()=>{
          restore.disabled=true;
          try{await api('/api/stories/'+story.id+'/restore',json('POST',{expected_revision:story.revision}));location.reload()}
          catch(error){notice(error.message,'error');restore.disabled=false}
        });row.append(title,restore);list.append(row);
      }
      if(!result.stories.length)uiText(list,"textContent",()=>(t("m_f5afb4e831d7")));
    }catch(error){notice(error.message,'error')}
  }
  load();
}
