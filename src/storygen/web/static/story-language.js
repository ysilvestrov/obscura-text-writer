import {t,msg,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
// STORY-LANGUAGE: the story language is chosen until a model has produced material; the server decides the lock.
const root=document.querySelector('[data-story-id]'),form=document.querySelector('#story-language-form');
if(root&&form){
  const id=root.dataset.storyId,select=form.elements.language,help=form.querySelector('#story-language-help'),button=form.querySelector('button');
  let story=null;
  async function load(){
    const view=await api(`/api/stories/${id}`);story=view.story;
    select.value=story.language||'uk';
    select.disabled=button.disabled=!!view.language_locked;
    uiText(help,'textContent',()=>view.language_locked?t('language.locked'):t('language.help'));
  }
  form.onsubmit=async event=>{
    event.preventDefault();
    try{
      if(!story||select.value===story.language)return;
      story=await api(`/api/stories/${id}/language`,json('PUT',{language:select.value,expected_revision:story.revision}));
      notice(msg('language.saved'));
    }catch(error){notice(error.message,'error')}
    await load().catch(error=>notice(error.message,'error'));
  };
  load().catch(error=>notice(error.message,'error'));
}
