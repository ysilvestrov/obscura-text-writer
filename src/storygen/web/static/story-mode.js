import {t,msg} from './i18n.js';
import {api,json,notice} from './api.js';
// WRITING-MODE: who writes the texts — the chat over MCP or Obscura's models; saves at once, like the language select.
const root=document.querySelector('[data-story-id]'),form=document.querySelector('#story-mode-form');
if(root&&form){
  const id=root.dataset.storyId,select=form.elements.writing_mode;
  let story=null;
  async function load(){story=(await api(`/api/stories/${id}`)).story;select.value=story.writing_mode||'chat';select.disabled=false}
  form.onsubmit=event=>event.preventDefault();
  select.onchange=async()=>{
    if(!story||select.value===story.writing_mode)return;
    const shown=story.writing_mode||'chat';select.disabled=true;
    try{
      // Other settings bump the story revision; take the current one, but only for the mode the author saw.
      const current=(await api(`/api/stories/${id}`)).story;
      if((current.writing_mode||'chat')!==shown)throw new Error(t('conflict.story_changed'));
      story=await api(`/api/stories/${id}/writing-mode`,json('PUT',{writing_mode:select.value,expected_revision:current.revision}));
      document.dispatchEvent(new CustomEvent('story-mode-changed'));
      notice(msg('writing_mode.saved'));
    }catch(error){notice(error.message,'error')}
    await load().catch(error=>notice(error.message,'error'));
  };
  load().catch(error=>notice(error.message,'error'));
}
