import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
const target=document.querySelector('#context-content');
function draw(){
  // Without a selected scene (e.g. the last one was trashed) no scene form may stay actionable.
  if(!state.scene){document.querySelector('#scene-rating')?.remove();return}
  const old=document.querySelector('#scene-settings');old?.remove();
  const form=document.createElement('form');form.id='scene-settings';form.className='panel';
  uiHTML(form,"<h3><span data-i18n=\"m_760039854033\">Параметри сцени</span></h3><label><span data-i18n=\"m_382c87f95f48\">Назва</span><input name=\"title\" required></label><label><span data-i18n=\"m_fd9c23636b93\">Орієнтир, слів</span><input name=\"target_words\" type=\"number\" min=\"1\" required aria-describedby=\"scene-target-help\"><small id=\"scene-target-help\" data-i18n=\"word_target.recommendation\">Рекомендовано до 15 000 слів</small></label><div><strong><span data-i18n=\"m_418e80220ec3\">Учасники сцени</span></strong><p id=\"scene-cast\" aria-live=\"polite\"></p><small><span data-i18n=\"m_f778f01a5f94\">Склад визначається рядком «Персонажі:» або «Хто бере участь:» у плані.</span></small></div><button><span data-i18n=\"m_4111b5e5d2dd\">Зберегти параметри</span></button>",{});
  for(const key of ['title','target_words'])form.elements[key].value=state.scene[key];
  const cast=state.view?.scenes.find(scene=>scene.id===state.scene.id)||state.scene;
  const names=cast.character_ids.map(id=>state.view?.character_names?.[id]).filter(name=>typeof name==='string');
  const missing=cast.character_ids.length-names.length;
  uiText(form.querySelector('#scene-cast'),"textContent",()=>(cast.character_ids.length?[names.join(', '),missing?t("m_3da57d38ee30",{p0:(missing)}):''].filter(Boolean).join(' · '):t("m_c47bda0ce0de")));
  form.onsubmit=async event=>{event.preventDefault();try{if(state.dirty)throw new Error(t("m_7b803d601f5d"));const scene=state.scene;const saved=await api(`/api/scenes/${scene.id}`,json('PATCH',{story_id:state.storyId,expected_revision:scene.revision,title:form.elements.title.value,target_words:Number(form.elements.target_words.value)}));
    // A slow response must not switch the selection back if the author has moved to another scene meanwhile.
    if(state.scene?.id===scene.id)state.scene=saved;await refresh();notice(msg("m_3912c755e566"))}catch(e){notice(e.message,'error')}};
  for(const [offset,label]of[[-1,msg("m_fbece07fa4b9")],[1,msg("m_64e67f3cc069")]]){const b=document.createElement('button');b.type='button';b.className='secondary';uiText(b,"textContent",()=>(label));b.onclick=async()=>{try{if(state.dirty)throw new Error(t("m_7b803d601f5d"));const ids=state.view.scenes.map(s=>s.id),index=ids.indexOf(state.scene.id),next=index+offset;if(next<0||next>=ids.length)return;[ids[index],ids[next]]=[ids[next],ids[index]];await api(`/api/stories/${state.storyId}/scene-order`,json('PUT',{scene_ids:ids,expected_revision:state.view.story.revision}));await refresh();notice(msg("m_fdf76ffdf76d"))}catch(e){notice(e.message,'error')}};form.append(b)}
  target.after(form);
  drawRating(form);
}
const axes=['sexual','violence','themes'];
function drawRating(after){
  document.querySelector('#scene-rating')?.remove();
  const storyRating=state.view?.story?.content_rating||null,own=state.scene.content_rating||null;
  const form=document.createElement('form');form.id='scene-rating';form.className='panel';
  const fieldset=document.createElement('fieldset'),legend=document.createElement('legend');
  uiText(legend,'textContent',()=>t('rating.scene.legend'));fieldset.append(legend);
  const radio=(value,render)=>{
    const label=document.createElement('label'),input=document.createElement('input'),span=document.createElement('span');
    input.type='radio';input.name='mode';input.value=value;uiText(span,'textContent',render);label.append(input,span);fieldset.append(label);return input;
  };
  radio('inherit',()=>t('rating.scene.inherit',{p0:storyRating?t('rating.scene.summary',{p0:storyRating.sexual,p1:storyRating.violence,p2:storyRating.themes}):t('rating.level.unset')}));
  radio('own',()=>t('rating.scene.own'));
  for(const axis of axes){
    const label=document.createElement('label'),span=document.createElement('span'),select=document.createElement('select');
    uiText(span,'textContent',()=>t(`rating.axis.${axis}`));select.name=axis;
    for(const level of [0,1,2]){const option=document.createElement('option');option.value=String(level);uiText(option,'textContent',()=>t(`rating.level.${level}`));select.append(option)}
    label.append(span,select);fieldset.append(label);
  }
  const hint=document.createElement('small');uiText(hint,'textContent',()=>t('rating.scene.hint'));fieldset.append(hint);
  const save=document.createElement('button');uiText(save,'textContent',()=>t('rating.scene.save'));
  form.append(fieldset,save);
  const shownRating=own||storyRating;
  for(const axis of axes)form.elements[axis].value=String(shownRating?shownRating[axis]:0);
  form.elements.mode.value=own?'own':'inherit';
  const sync=()=>{for(const axis of axes)form.elements[axis].disabled=form.elements.mode.value==='inherit'};
  sync();form.addEventListener('change',event=>{if(event.target.name==='mode')sync()});
  form.onsubmit=async event=>{
    event.preventDefault();
    try{
      if(state.dirty)throw new Error(t("m_7b803d601f5d"));
      const content_rating=form.elements.mode.value==='inherit'?null:Object.fromEntries(axes.map(axis=>[axis,Number(form.elements[axis].value)]));
      const scene=state.scene;
      const saved=await api(`/api/scenes/${scene.id}/content-rating`,json('PUT',{story_id:state.storyId,content_rating,expected_revision:scene.revision}));
      // A slow response must not switch the selection back if the author has moved to another scene meanwhile.
      if(state.scene?.id===scene.id)state.scene=saved;
      await refresh();notice(msg('rating.scene.saved'));
    }catch(e){notice(e.message,'error')}
  };
  after.after(form);
}
document.addEventListener('scene-selected',draw);document.addEventListener('story-refreshed',draw);
