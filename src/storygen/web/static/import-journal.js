import {t,getLocale,uiText} from './i18n.js';
export function importDate(value){
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T/.test(value))return null;
  const date=new Date(value);return Number.isFinite(date.getTime())?date:null;
}
export function formatImportTime(value,locale,timeZone){
  const date=importDate(value);if(!date)return null;
  return new Intl.DateTimeFormat(locale,{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',timeZoneName:'short',...(timeZone?{timeZone}:{})}).format(date);
}
export function renderImportJournal(host,files=[],active={}){
  host.replaceChildren();const title=document.createElement('h3');uiText(title,'textContent',()=>t('imports.journal'));host.append(title);
  if(active.source_plan&&!files.some(f=>f.kind==='source_plan'&&f.version_id===active.source_plan)){
    const combined=document.createElement('p');combined.className='muted';uiText(combined,'textContent',()=>t('imports.combined'));host.append(combined);
  }
  if(!files.length){const empty=document.createElement('p');uiText(empty,'textContent',()=>t('imports.empty'));host.append(empty);return;}
  const list=document.createElement('ul');list.className='source-journal';
  for(const file of files){
    const row=document.createElement('li');row.className='source-record';
    const name=document.createElement('strong');name.textContent=file.name||'';row.append(name);
    const kind=document.createElement('span');uiText(kind,'textContent',()=>t(file.kind==='source_plan'?'imports.plan':'characters.nav'));row.append(kind);
    const time=document.createElement('time');const date=importDate(file.created_at);
    if(date)time.dateTime=date.toISOString();
    uiText(time,'textContent',()=>formatImportTime(file.created_at,getLocale())||t('imports.time_unknown'));row.append(time);
    const counts=document.createElement('span');counts.className='source-counts';
    uiText(counts,'textContent',()=>Number.isInteger(file.created_scene_count)&&file.created_scene_count>=0&&Number.isInteger(file.created_character_count)&&file.created_character_count>=0?t('imports.counts',{p0:file.created_scene_count,p1:file.created_character_count}):t('imports.counts_unknown'));row.append(counts);
    if(active[file.kind]===file.version_id){const badge=document.createElement('small');uiText(badge,'textContent',()=>t('imports.active'));row.append(badge);}
    list.append(row);
  }
  host.append(list);
}
