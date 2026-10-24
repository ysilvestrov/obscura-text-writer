export function installStoryTitle({root,state,api,json}){
  const heading=root.querySelector('#story-title'),edit=root.querySelector('#rename-story');
  const form=root.querySelector('#story-title-form'),input=root.querySelector('#story-title-input');
  const submit=root.querySelector('#story-title-submit'),error=root.querySelector('#story-title-error');
  let editing=false,saving=false,revision=null,original='';
  function display(story){heading.textContent=story.title;document.title=story.title+' — Obscura'}
  function close(){editing=false;form.hidden=true;heading.hidden=false;edit.hidden=false;error.textContent='';edit.focus()}
  edit.addEventListener('click',()=>{
    if(saving||!state.view?.story)return;
    original=state.view.story.title;revision=state.view.story.revision;
    input.value=original;editing=true;heading.hidden=true;edit.hidden=true;form.hidden=false;error.textContent='';input.focus();input.select();
  });
  input.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&!saving){event.preventDefault();close()}
  });
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(saving||!editing)return;
    const title=input.value.trim();
    if(!title||title.length>300){error.textContent='Введіть назву від 1 до 300 символів.';input.focus();return}
    saving=true;input.disabled=true;submit.disabled=true;error.textContent='';
    try{
      const story=await api('/api/stories/'+state.storyId,json('PATCH',{title,expected_revision:revision}));
      state.view.story=story;display(story);close();
    }catch(problem){
      error.textContent=problem.message;
      // Refresh only metadata for a deliberate reopen; preserve the typed title and scene buffer.
      try{const latest=await api('/api/stories/'+state.storyId);state.view.story=latest.story;display(latest.story)}catch{}
    }
    finally{saving=false;input.disabled=false;submit.disabled=false;if(editing)input.focus()}
  });
  document.addEventListener('story-refreshed',()=>{if(!editing&&state.view?.story)display(state.view.story)});
  globalThis.addEventListener?.('beforeunload',event=>{
    if(saving||(editing&&input.value!==original)){event.preventDefault();event.returnValue=''}
  });
}
