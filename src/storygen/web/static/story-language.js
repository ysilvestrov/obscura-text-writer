import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {hasUnsavedSettings} from './settings-workspace.js';
// STORY-LANGUAGE: the story language is chosen until a model has produced material; the server decides the lock.
// Settings forms save through the shared toolbar; this one field saves at once, like the memory kind selects.
const root=document.querySelector('[data-story-id]'),form=document.querySelector('#story-language-form');
if(root&&form){
  const id=root.dataset.storyId,select=form.elements.language,help=form.querySelector('#story-language-help');
  let story=null;
  async function load(){
    const view=await api(`/api/stories/${id}`);story=view.story;
    select.value=story.language||'uk';
    select.disabled=!!view.language_locked;
    uiText(help,'textContent',()=>view.language_locked?t('language.locked'):t('language.help_settings'));
  }
  form.onsubmit=event=>event.preventDefault();
  select.onchange=async()=>{
    if(!story||select.value===story.language)return;
    // Default role prompts follow the language: role forms are rebuilt afterwards, so unsaved edits must not exist.
    if(hasUnsavedSettings()){notice(t('language.unsaved_first'),'error');select.value=story.language;return}
    const shown=story.language;select.disabled=true;
    try{
      // Other settings on this page bump the story revision; take the current one, but only for the language the author saw.
      const current=(await api(`/api/stories/${id}`)).story;
      if(current.language!==shown)throw new Error(t('conflict.story_changed'));
      story=await api(`/api/stories/${id}/language`,json('PUT',{language:select.value,expected_revision:current.revision}));
      document.dispatchEvent(new CustomEvent('story-language-changed'));
      notice(msg('language.saved'));
    }catch(error){notice(error.message,'error')}
    await load().catch(error=>notice(error.message,'error'));
  };
  load().catch(error=>notice(error.message,'error'));
}
