import {api,json,notice} from './api.js';

const panel=document.querySelector('#role-profiles');
const storyId=document.querySelector('[data-story-id]').dataset.storyId;
const select=panel.querySelector('#role-profile-select');
const previewButton=panel.querySelector('#role-profile-preview');
const applyButton=panel.querySelector('#role-profile-apply');
const exportButton=panel.querySelector('#role-profile-export');
const summary=panel.querySelector('#role-profile-summary');
const form=panel.querySelector('form');
const file=panel.querySelector('input[type=file]');
const labels={planner:'Планувальник',writer:'Письменник',editor:'Редактор',memory:'Пам’ять'};
let items=[],preview=null,busy=false,dirty=false,selectionEpoch=0;

function selected(){return items.find(item=>`${item.id}:${item.version}`===select.value)}
function controls(){const item=selected();previewButton.disabled=busy||!item;exportButton.disabled=busy||!item;applyButton.disabled=busy||!preview;form.querySelector('button').disabled=busy;file.disabled=busy;select.disabled=busy;form.elements.new_version.disabled=busy||!item}
function reset(){selectionEpoch++;preview=null;summary.replaceChildren();controls()}
select.onchange=()=>{reset();const item=selected();if(item)form.elements.name.value=item.name};
document.addEventListener('input',event=>{if(event.target.closest('form')&&!panel.contains(event.target)){dirty=true;reset()}});

async function load(preferred=null){
  const result=await api('/api/role-profiles');items=result.profiles;select.replaceChildren();
  const empty=document.createElement('option');empty.value='';empty.textContent=items.length?'Оберіть комплект і версію':'Збережених комплектів поки немає';select.append(empty);
  for(const item of items){const option=document.createElement('option');option.value=`${item.id}:${item.version}`;option.textContent=`${item.name} · версія ${item.version}${item.has_evaluator?' · з Evaluator':''}`;select.append(option)}
  if(preferred){select.value=`${preferred.id}:${preferred.version}`;form.elements.name.value=preferred.document.name}
  reset();
}

async function action(work){busy=true;controls();try{await work()}catch(error){notice(error.message,'error')}finally{busy=false;controls()}}
async function revision(){return (await api(`/api/stories/${storyId}/settings`)).story.revision}

previewButton.onclick=()=>action(async()=>{
  const item=selected(),epoch=selectionEpoch;
  preview=null;
  const data=await api(`/api/stories/${storyId}/role-profiles/preview`,json('POST',{profile_id:item.id,version:item.version,expected_revision:await revision()}));
  if(epoch!==selectionEpoch)return;
  preview=data;summary.replaceChildren();
  const title=document.createElement('h3');title.textContent=`${data.name} · версія ${data.version}`;summary.append(title);
  const list=document.createElement('dl');
  for(const [role,config] of Object.entries(data.roles)){
    const name=document.createElement('dt');name.textContent=labels[role];
    const value=document.createElement('dd');value.textContent=`${config.provider.provider} / ${config.provider.model}; контекст ${config.context_tokens}, відповідь ${config.max_output_tokens}; ${data.prompts[role].prompt.text===null?'стандартний':'власний'} промпт`;
    list.append(name,value);
  }
  summary.append(list);
  const evaluator=document.createElement('p');evaluator.textContent=data.evaluator?`Evaluator: ${data.evaluator.config.provider} / ${data.evaluator.config.model||'модель CLI'}; режим ${data.evaluator.policy}.`:'Evaluator цього твору залишиться без змін.';summary.append(evaluator);
  for(const text of data.warnings){const warning=document.createElement('p');warning.textContent=text;summary.append(warning)}
  const details=document.createElement('details'),caption=document.createElement('summary'),raw=document.createElement('pre');caption.textContent='Усі параметри та промпти';raw.textContent=JSON.stringify(data,null,2);details.append(caption,raw);summary.append(details);
});

applyButton.onclick=()=>action(async()=>{
  if(!preview)return;
  const warning=dirty?'Є незбережені зміни форм. Вони будуть втрачені після застосування. ':'Сторінка перезавантажиться; незбережені зміни форм будуть втрачені. ';
  if(!confirm(warning+`Застосувати «${preview.name}», версію ${preview.version}, до цього твору?`))return;
  await api(`/api/stories/${storyId}/role-profiles/apply`,json('POST',{profile_id:preview.id,version:preview.version,expected_revision:preview.expected_revision}));
  location.reload();
});

exportButton.onclick=()=>{const item=selected();if(item)location.href=`/api/role-profiles/${encodeURIComponent(item.id)}/versions/${item.version}/export`};
form.onsubmit=event=>{event.preventDefault();action(async()=>{
  if(dirty&&!confirm('Зберегти комплект із уже збережених налаштувань? Незбережені правки форм до нього не потраплять.'))return;
  const body={name:form.elements.name.value,include_evaluator:form.elements.include_evaluator.checked,expected_revision:await revision()};
  if(form.elements.new_version.checked){const item=selected();if(!item)throw new Error('Оберіть комплект для нової версії');body.profile_id=item.id;body.expected_version=item.version}
  const saved=await api(`/api/stories/${storyId}/role-profiles/capture`,json('POST',body));await load(saved);notice('Комплект збережено; налаштування твору не змінено');
})};
file.onchange=()=>action(async()=>{
  const source=file.files[0];if(!source)return;
  try{
    if(source.size>2*1024*1024)throw new Error('Файл профілю перевищує 2 MiB');
    const saved=await api('/api/role-profiles/import',{method:'POST',headers:{'Content-Type':'application/json'},body:await source.text()});
    await load(saved);notice('Комплект імпортовано. Перегляньте його перед застосуванням');
  }finally{file.value=''}
});
load().catch(error=>notice(error.message,'error'));
