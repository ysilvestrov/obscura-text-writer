import {live,msg,t,uiText} from './i18n.js';
import {api,json,notice} from './api.js';
import {registerSettingsForm,settingsSaved,withSettingsSave} from './settings-workspace.js';
import {appInfo,allowedLevels,limited} from './app-info.js';
const form=document.querySelector('#rating-form'),id=document.querySelector('[data-story-id]').dataset.storyId;
const axes=['sexual','violence','themes'];
let shown=null;
// BUILD-EDITION-001: levels above the build edition limit are not offered; a stored higher level stays visible.
let maxRating={sexual:2,violence:2,themes:2};
function applyLimit(rating){
  for(const axis of axes){
    const allowed=allowedLevels(maxRating[axis],rating?rating[axis]:null);
    for(const option of form.elements[axis].options){
      if(option.value==='')continue;
      const off=!allowed.includes(Number(option.value));option.hidden=off;option.disabled=off;
    }
  }
  let hint=form.querySelector('.rating-edition-hint');
  if(limited(maxRating)&&!hint){
    hint=document.createElement('small');hint.className='rating-edition-hint';
    uiText(hint,'textContent',()=>t('rating.edition.hint',{p0:maxRating.sexual}));
    form.querySelector('fieldset').append(hint);
  }
}
function show(story){
  const rating=story.content_rating;shown=rating?axes.map(axis=>rating[axis]).join(','):'';
  for(const axis of axes){
    const select=form.elements[axis];
    select.value=rating?String(rating[axis]):'';
    select.querySelector('option[value=""]').disabled=Boolean(rating);
  }
  applyLimit(rating);
}
async function load(){
  maxRating=(await appInfo()).max_rating;
  show((await api(`/api/stories/${id}/settings`)).story);
  // Shares the settings dirty registry: leaving with unsaved axes warns like other forms.
  registerSettingsForm('rating',{form,label:live(()=>t('rating.legend')),section:'writing',reset:load});
}
async function save(){
  const values=axes.map(axis=>form.elements[axis].value);
  if(values.includes(''))throw new Error(t('rating.incomplete'));
  const latest=(await api(`/api/stories/${id}/settings`)).story;
  const current=latest.content_rating?axes.map(axis=>latest.content_rating[axis]).join(','):'';
  if(current!==shown)throw new Error(t('rating.changed'));
  const body={content_rating:Object.fromEntries(axes.map((axis,index)=>[axis,Number(values[index])])),expected_revision:latest.revision};
  show(await api(`/api/stories/${id}/content-rating`,json('PUT',body)));
  settingsSaved('rating');
  notice(msg('rating.saved'));
}
document.querySelector('#rating-save').onclick=async()=>{
  try{await withSettingsSave('rating',save)}catch(e){notice(e.message,'error')}
};
load().catch(e=>notice(e.message,'error'));
