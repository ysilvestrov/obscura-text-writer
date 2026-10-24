import {textStatistics} from './text-statistics.js';
import {createTextEditor} from './text-editor.js';
const labels={plan:'План',brief:'Завдання',draft:'Чернетка',prose:'Проза',memory:'Пам’ять'};
const groups={system:'Системний промпт',plans:'Плани',characters:'Персонажі',memory:'Пам’ять',previous_tail:'Хвіст попередньої прози',brief:'Завдання',draft:'Чернетка / робоча копія',prose:'Проза',other:'Інші вказівки й метадані',response_schema:'Схема відповіді',protocol:'Протокол і резерв оцінки'};
const categories={facts:'Факти',character_states:'Стани персонажів',open_threads:'Сюжетні лінії',timeline:'Хронологія'};

export function installSceneStatistics({state,api,document}){
  const host=document.querySelector('#scene-statistics');if(!host)return;
  const textEditor=createTextEditor(document.querySelector('#editor'));
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
  const compact=node('p'),details=node('details'),summary=node('summary','Статистика сцени й контексту');
  const stage=node('select');stage.setAttribute('aria-label','Етап для оцінки контексту');
  for(const [value,label] of [['brief','Створити завдання'],['draft','Написати'],['edit','Редагувати'],['memory','Оновити пам’ять']]){const option=node('option',label);option.value=value;stage.append(option);}
  stage.value='draft';
  const reload=node('button','Оновити статистику');reload.type='button';reload.className='secondary';
  const controls=node('div');controls.className='actions';controls.append(stage,reload);
  const status=node('p');status.setAttribute('role','status');const body=node('div');
  details.append(summary,controls,status,body);host.append(compact,details);
  let epoch=0;
  function buffer(){
    if(!state.scene){compact.textContent='Оберіть сцену для статистики.';return;}
    if(state.mode==='review'){compact.textContent='Перегляд редакторських змін. Обсяг збережених текстів — у деталях.';return;}
    if(state.memoryTableActive){compact.textContent='Пам’ять показано таблицею. Кількість записів — у деталях статистики.';return;}
    const counts=textStatistics(textEditor.read());
    const origin=state.saving?'Буфер під час збереження':state.bufferOrigin==='history'?'Історична версія':state.dirty?'Незбережений буфер':'Відкритий буфер';
    compact.textContent=`${origin} · ${labels[state.mode]||'матеріал'} · ${counts.words} слів · ${counts.characters} символів із пробілами${['brief','memory','blueprint'].includes(state.mode)?' · JSON':''}`;
  }
  function table(headers,rows){
    const t=node('table'),head=node('thead'),tr=node('tr');for(const h of headers){const th=node('th',h);th.scope='col';tr.append(th);}head.append(tr);t.append(head);
    const b=node('tbody');for(const row of rows){const r=node('tr');for(const value of row)r.append(node('td',value??'—'));b.append(r);}t.append(b);body.append(t);
  }
  function render(data){
    body.replaceChildren();body.append(node('h3','Збережені матеріали'));
    table(['Матеріал','Слів','Символів','Стан'],Object.entries(data.materials).map(([key,m])=>[labels[key],m?.words,m?.characters,!m?'Немає':!m.complete?'Незавершений':m.stale?'Застарілий':m.version_id?'Актуальний':'Без версії']));
    const prose=data.materials.prose;body.append(node('p',`Поточна проза: ${prose?prose.words:'—'} / ${data.target_words} цільових слів. Історія й альтернативи не підсумовуються.`));
    for(const [key,title] of [['previous','Пам’ять попередніх сцен'],['through_scene','Пам’ять після цієї сцени']]){
      const m=data.memory[key];body.append(node('h3',title));
      if(!m?.available){body.append(node('p',m?.reason||'Немає даних'));continue;}
      body.append(node('p',`${m.stale?'Застарілий журнал. ':''}${m.complete===false?'Незавершений журнал. ':''}Подій в історії: ${m.event_count}. ${key==='previous'?'Внесок останньої попередньої сцени':'Внесок поточної сцени'}: ${m.current_scene_events}.`));
      table(['Категорія','Чинних','Подій'],Object.entries(categories).map(([category,label])=>[label,m.active[category],m.events[category]]));
      body.append(node('p',`Додано: ${m.operations.add}; оновлено: ${m.operations.update}; закрито: ${m.operations.retire}.`));
    }
    const c=data.context;body.append(node('h3','Контекст наступного виклику'));
    if(c.available){
      body.append(node('p',`${c.provider} / ${c.model} · оцінка входу: ${c.estimated_input_tokens} / ${c.input_budget} токенів; резерв відповіді: ${c.output_reserve}; вікно: ${c.context_tokens}. Метод: ${c.method}.`));
      table(['Джерело','Символів','Байтів JSON','Розподіл оцінки токенів'],c.parts.map(p=>[groups[p.kind]||p.kind,p.characters,p.request_bytes,p.estimated_tokens]));
      body.append(node('p','Розподіл пропорційний байтам JSON, не фактичній токенізації. Службовий рядок містить резерв оцінки.'));
    }
    if(c.reason)body.append(node('p',c.reason));
    const last=data.last_usage;body.append(node('h3','Останній фактичний виклик цього етапу'));
    if(last){const u=last.usage;body.append(node('p',`${last.created_at} · ${last.model} · ${last.state}. Вхід: ${u.prompt_tokens??u.input_tokens??'невідомо'}; вихід: ${u.completion_tokens??u.output_tokens??'невідомо'}; reasoning: ${u.completion_tokens_details?.reasoning_tokens??'невідомо'}. Профіль міг відрізнятися від поточного.`));}
    else body.append(node('p','Фактичного usage ще немає. Оцінка вище не є виміряним usage.'));
  }
  async function load(){
    const stamp=++epoch,id=state.scene?.id;if(!id||!details.open){body.replaceChildren();return;}
    status.textContent='Завантажуємо збережений стан…';body.replaceChildren();
    try{
      const sourceHead=stage.value==='edit'&&['draft','prose'].includes(state.mode)?state.mode:null;
      const query=new URLSearchParams({stage:stage.value});
      if(sourceHead&&state.scene.heads?.[sourceHead]){query.set('editor_source_head',sourceHead);query.set('editor_source_version_id',state.scene.heads[sourceHead]);}
      const result=await api(`/api/scenes/${id}/statistics?${query}`);
      state.workspaceMaterials=result.materials;if(document.dispatchEvent)document.dispatchEvent(new CustomEvent('workspace-statistics'));
      if(stamp!==epoch||state.scene?.id!==id)return;
      render(result);status.textContent=`Збережений стан сцени · ревізія ${result.scene_revision}. Ручний буфер у ці розрахунки не входить.`;
    }catch(error){if(stamp===epoch&&state.scene?.id===id)status.textContent=error.message;}
  }
  details.addEventListener('toggle',()=>void load());stage.addEventListener('change',()=>void load());reload.addEventListener('click',()=>void load());
  document.addEventListener('editor-state-changed',buffer);
  for(const event of ['scene-selected','story-refreshed'])document.addEventListener(event,()=>{buffer();void load();});
  buffer();return {compact,details,body,load};
}
