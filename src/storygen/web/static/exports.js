import {api,json,notice} from './api.js';
import {state} from './editor.js';
const button=document.querySelector('#export-story');button.hidden=false;
button.onclick=async()=>{try{const format=prompt('Формат експорту: md або txt','md');if(!format)return;const allow_incomplete=confirm('Дозволити неповний експорт із явними позначками відсутніх/застарілих сцен? Скасувати — вимагати повний твір.');const result=await api(`/api/stories/${state.storyId}/export`,json('POST',{format,allow_incomplete}));const box=document.createElement('div');for(const [url,label]of[[result.download_url,'Завантажити твір'],[result.manifest_url,'Завантажити manifest']]){const link=document.createElement('a');link.href=url;link.textContent=label;link.download='';link.style.marginRight='1rem';box.append(link)}document.querySelector('#version-panel').prepend(box);notice('Експорт створено зі знімка вибраних версій')}catch(e){notice(e.message,'error')}};

function exportAvailability(){const reason=state.dirty?'Спершу збережіть ручні правки':!state.view?.scenes.some(s=>s.heads.prose)?'Немає завершеної прози для експорту':'';button.disabled=!!reason;button.title=reason}
document.addEventListener('story-refreshed',exportAvailability);document.addEventListener('editor-state-changed',exportAvailability);exportAvailability();
