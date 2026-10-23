import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
const target=document.querySelector('#context-content');
function draw(){
  if(!state.scene)return;
  const old=document.querySelector('#scene-settings');old?.remove();
  const form=document.createElement('form');form.id='scene-settings';form.className='panel';
  form.innerHTML='<h3>Параметри сцени</h3><label>Назва<input name="title" required></label><label>Орієнтир, слів<input name="target_words" type="number" min="1" max="15000" required></label><div><strong>Учасники сцени</strong><p id="scene-cast" aria-live="polite"></p><small>Склад визначається рядком «Персонажі:» або «Хто бере участь:» у плані.</small></div><button>Зберегти параметри</button>';
  for(const key of ['title','target_words'])form.elements[key].value=state.scene[key];
  const cast=state.view?.scenes.find(scene=>scene.id===state.scene.id)||state.scene;
  const names=cast.character_ids.map(id=>state.view?.character_names?.[id]).filter(name=>typeof name==='string');
  const missing=cast.character_ids.length-names.length;
  form.querySelector('#scene-cast').textContent=cast.character_ids.length?[names.join(', '),missing?`Картки не знайдено: ${missing}`:''].filter(Boolean).join(' · '):'Учасників не вказано.';
  form.onsubmit=async event=>{event.preventDefault();try{if(state.dirty)throw new Error('Спершу збережіть текст');state.scene=await api(`/api/scenes/${state.scene.id}`,json('PATCH',{story_id:state.storyId,expected_revision:state.scene.revision,title:form.elements.title.value,target_words:Number(form.elements.target_words.value)}));await refresh();notice('Параметри сцени збережено')}catch(e){notice(e.message,'error')}};
  for(const [offset,label]of[[-1,'Перемістити вище'],[1,'Перемістити нижче']]){const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=label;b.onclick=async()=>{try{if(state.dirty)throw new Error('Спершу збережіть текст');const ids=state.view.scenes.map(s=>s.id),index=ids.indexOf(state.scene.id),next=index+offset;if(next<0||next>=ids.length)return;[ids[index],ids[next]]=[ids[next],ids[index]];await api(`/api/stories/${state.storyId}/scene-order`,json('PUT',{scene_ids:ids,expected_revision:state.view.story.revision}));await refresh();notice('Порядок змінено; перевірте залежні матеріали')}catch(e){notice(e.message,'error')}};form.append(b)}
  target.after(form);
}
document.addEventListener('scene-selected',draw);document.addEventListener('story-refreshed',draw);
