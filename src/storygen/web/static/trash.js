import {api,json,notice} from './api.js';

function action(label,callback){const button=document.createElement('button');button.type='button';button.className='secondary';button.textContent=label;button.onclick=callback;return button}

export function installSceneTrash(state,refresh,clear){
  const trash=action('У кошик',async()=>{
    if(state.dirty||state.saving){notice('Спершу збережіть ручні правки','error');return}
    if(!state.scene){notice('Оберіть сцену','error');return}
    if(!confirm('Перемістити сцену в кошик? Її можна відновити. Наступні сцени потребуватимуть перегляду.'))return;
    trash.disabled=true;state.saving=true;
    const editor=document.querySelector("#editor"),readOnly=editor.readOnly;editor.readOnly=true;
    document.dispatchEvent(new CustomEvent("editor-state-changed"));
    try{
      await api('/api/scenes/'+state.scene.id+'/trash',json('POST',{story_id:state.storyId,expected_revision:state.scene.revision}));
      clear();state.saving=false;await refresh();notice('Сцену переміщено в кошик');
    }catch(error){notice(error.message,'error')}finally{trash.disabled=false;state.saving=false;editor.readOnly=readOnly;document.dispatchEvent(new CustomEvent('editor-state-changed'))}
  });
  document.querySelector('.editor-toolbar').append(trash);
  function availability(){const reason=!state.scene?'Оберіть сцену':state.saving?'Дочекайтеся завершення операції':state.dirty?'Спершу збережіть ручні правки':'';trash.disabled=!!reason;trash.title=reason}
  for(const event of ['scene-selected','story-refreshed','editor-state-changed'])document.addEventListener(event,availability);availability();
  const details=document.createElement('details'),summary=document.createElement('summary'),list=document.createElement('div');
  summary.textContent='Кошик сцен';details.append(summary,list);document.querySelector('.scene-panel').append(details);
  let epoch=0;
  async function load(){
    const current=++epoch;
    try{
      const result=await api('/api/stories/'+state.storyId+'/trash');if(current!==epoch)return;
      list.replaceChildren();
      for(const scene of result.scenes||[]){
        const row=document.createElement('p'),title=document.createElement('span');title.textContent=scene.title+' ';
        const restore=action('Відновити',async()=>{
          if(state.dirty||state.saving){notice('Спершу збережіть ручні правки','error');return}
          restore.disabled=true;
          try{await api('/api/scenes/'+scene.id+'/restore',json('POST',{story_id:state.storyId,expected_revision:scene.revision}));await refresh();notice('Сцену відновлено. Перегляньте контекст наступних сцен')}
          catch(error){notice(error.message,'error')}finally{restore.disabled=false}
        });row.append(title,restore);list.append(row);
      }
      if(!(result.scenes||[]).length){const empty=document.createElement('p');empty.textContent='Кошик порожній';list.append(empty)}
    }catch(error){notice(error.message,'error')}
  }
  document.addEventListener('story-refreshed',load);
}

export function installLibraryTrash(){
  for(const button of document.querySelectorAll('[data-trash-story]'))button.onclick=async()=>{
    if(!confirm('Перемістити твір у кошик? Усі версії залишаться доступними після відновлення.'))return;
    button.disabled=true;
    try{await api('/api/stories/'+button.dataset.trashStory+'/trash',json('POST',{expected_revision:Number(button.dataset.revision)}));location.reload()}
    catch(error){notice(error.message,'error');button.disabled=false}
  };
  const list=document.querySelector('#story-trash-list');
  async function load(){
    try{
      const result=await api('/api/trash');list.replaceChildren();
      for(const story of result.stories){
        const row=document.createElement('p'),title=document.createElement('span');title.textContent=story.title+' ';
        const restore=action('Відновити',async()=>{
          restore.disabled=true;
          try{await api('/api/stories/'+story.id+'/restore',json('POST',{expected_revision:story.revision}));location.reload()}
          catch(error){notice(error.message,'error');restore.disabled=false}
        });row.append(title,restore);list.append(row);
      }
      if(!result.stories.length)list.textContent='Кошик порожній';
    }catch(error){notice(error.message,'error')}
  }
  load();
}
