import {api,json,notice} from './api.js';
import {state,refresh} from './editor.js';
const target=document.querySelector('#context-content');
function draw(){
  if(!state.scene)return;
  const old=document.querySelector('#scene-settings');old?.remove();
  const form=document.createElement('form');form.id='scene-settings';form.className='panel';
  form.innerHTML='<h3>Параметри сцени</h3><label>Назва<input name="title" required></label><label>Орієнтир, слів<input name="target_words" type="number" min="1" max="15000" required></label><label>ID персонажів через кому<input name="character_ids"></label><button>Зберегти параметри</button>';
  for(const key of ['title','target_words'])form.elements[key].value=state.scene[key];form.elements.character_ids.value=state.scene.character_ids.join(', ');
  form.onsubmit=async event=>{event.preventDefault();try{if(state.dirty)throw new Error('Спершу збережіть текст');state.scene=await api(`/api/scenes/${state.scene.id}`,json('PATCH',{story_id:state.storyId,expected_revision:state.scene.revision,title:form.elements.title.value,target_words:Number(form.elements.target_words.value),character_ids:form.elements.character_ids.value.split(',').map(s=>s.trim()).filter(Boolean)}));await refresh();notice('Параметри сцени збережено')}catch(e){notice(e.message,'error')}};
  for(const [offset,label]of[[-1,'Перемістити вище'],[1,'Перемістити нижче']]){const b=document.createElement('button');b.type='button';b.className='secondary';b.textContent=label;b.onclick=async()=>{try{if(state.dirty)throw new Error('Спершу збережіть текст');const ids=state.view.scenes.map(s=>s.id),index=ids.indexOf(state.scene.id),next=index+offset;if(next<0||next>=ids.length)return;[ids[index],ids[next]]=[ids[next],ids[index]];await api(`/api/stories/${state.storyId}/scene-order`,json('PUT',{scene_ids:ids,expected_revision:state.view.story.revision}));await refresh();notice('Порядок змінено; перевірте залежні матеріали')}catch(e){notice(e.message,'error')}};form.append(b)}
  target.after(form);
}
document.addEventListener('scene-selected',draw);document.addEventListener('story-refreshed',draw);
