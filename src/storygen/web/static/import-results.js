import {t,uiText,diagnostic} from './i18n.js';
function paragraph(host,render){const p=document.createElement('p');uiText(p,'textContent',render);host.append(p);return p;}
export function showImportPending(host){host.hidden=false;host.replaceChildren();paragraph(host,()=>t('imports.pending'));}
function refreshControl(host,onRefresh,initial){
  const status=paragraph(host,()=>t(initial));
  const button=document.createElement('button');button.type='button';button.className='secondary';
  uiText(button,'textContent',()=>t('imports.refresh_journal'));host.append(button);
  button.onclick=async()=>{button.disabled=true;try{await onRefresh();uiText(status,'textContent',()=>t('imports.journal_updated'));button.remove();}catch{uiText(status,'textContent',()=>t('imports.refresh_failed'));button.disabled=false;}};
}
export function showImportRefreshWarning(host,onRefresh){refreshControl(host,onRefresh,'imports.refresh_failed');}
export function renderImportResults(host,data={},options={}){
  host.hidden=false;host.replaceChildren();
  const files=Array.isArray(data.files)?data.files:[];
  const failed=options.failed||files.some(f=>f.status==='failed');
  const title=document.createElement('h3');uiText(title,'textContent',()=>t(options.uncertain?'imports.unknown':data.partial?'imports.partial':failed?'imports.failure':'imports.success'));host.append(title);
  if(options.uncertain){paragraph(host,()=>t('imports.unknown_help'));refreshControl(host,options.onRefresh,'imports.check_journal');return;}
  const imported=files.filter(f=>f.status==='imported');
  const scenes=data.created_scene_ids?.length??imported.reduce((n,f)=>n+(f.created_scene_ids?.length||0),0);
  const cards=data.created_character_cards??imported.reduce((n,f)=>n+(f.created_character_cards||0),0);
  paragraph(host,()=>t('imports.counts',{p0:scenes,p1:cards}));
  if(cards)paragraph(host,()=>t('imports.temporal'));
  if(data.partial)paragraph(host,()=>t('imports.no_retry'));
  for(const file of files){
    const item=document.createElement('div');item.className='import-file-result';
    const name=document.createElement('strong');name.textContent=file.name;item.append(name);
    paragraph(item,()=>t('imports.status.'+file.status));
    if(file.skipped_character_names?.length){
      paragraph(item,()=>t('imports.skipped_characters',{p0:file.skipped_character_names.join(', ')}));
      const link=document.createElement('a');link.className='import-character-link';link.href=options.charactersHref;uiText(link,'textContent',()=>t('characters.nav'));item.append(link);
    }
    if(file.skipped_scene_numbers?.length)paragraph(item,()=>t('imports.skipped_scenes',{p0:file.skipped_scene_numbers.join(', ')}));
    if(file.status==='failed'){paragraph(item,()=>t('imports.failed_file'));if(typeof file.error==='string')paragraph(item,()=>diagnostic(file.error));}
    if(file.status==='imported'&&!file.created_character_cards&&!file.created_scene_ids?.length&&!file.skipped_character_names?.length&&!file.skipped_scene_numbers?.length)paragraph(item,()=>t('imports.no_changes'));
    for(const warning of file.warnings||[]){
      const mixed=warning.match(/^Ім’я «(.+)» містить латинські й кириличні літери/);
      if(mixed)paragraph(item,()=>t('imports.mixed',{p0:mixed[1]}));
      else if(!/^(Створено нових карток|Наявні картки не перезаписано|Пропущено номери сцен|Дублікати сцен за номером|Сцени без номера|Картки не створено)/.test(warning))paragraph(item,()=>diagnostic(warning));
    }
    host.append(item);
  }
  if(!files.length&&options.error)paragraph(host,()=>diagnostic(options.error.message));
}
