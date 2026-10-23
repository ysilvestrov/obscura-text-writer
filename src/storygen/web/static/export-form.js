// This controller has no scene-selection dependency: publication belongs to the story.
export function installExportForm({state,api,json,notice,document}){
  const get=id=>document.querySelector('#'+id);
  const button=get('export-story'),form=get('export-form'),submit=get('export-submit'),status=get('export-status');
  let busy=false;
  button.hidden=false;
  function availability(){
    const reason=state.dirty?'Спершу збережіть ручні правки':state.saving?'Триває збереження':!state.view?.scenes.some(scene=>scene.heads.prose)?'Немає завершеної прози для експорту':'';
    button.disabled=busy||!!reason;submit.disabled=busy||!!reason;button.title=reason;submit.title=reason;
    if(reason){status.textContent=reason;status.className='muted';}
  }
  button.onclick=()=>{form.hidden=!form.hidden;button.setAttribute('aria-expanded',String(!form.hidden));if(!form.hidden)get('export-format').focus();};
  get('export-cancel').onclick=()=>{form.hidden=true;button.setAttribute('aria-expanded','false');button.focus();};
  form.onsubmit=async event=>{
    event.preventDefault();availability();if(submit.disabled)return;
    busy=true;availability();form.setAttribute('aria-busy','true');status.textContent='Створюємо файл…';status.className='muted';
    try{
      const format=get('export-format').value,allow_incomplete=get('export-incomplete').checked;
      const result=await api(`/api/stories/${state.storyId}/export`,json('POST',{format,allow_incomplete}));
      const box=document.createElement('div');
      for(const [url,label]of[[result.download_url,`Завантажити ${format.toUpperCase()}`],[result.manifest_url,'Завантажити manifest']]){
        const link=document.createElement('a');link.href=url;link.textContent=label;link.download='';box.append(link);
      }
      get('publication-links').replaceChildren(box);status.textContent='Файл готовий. Посилання нижче.';status.className='success';
      notice('Файл твору готовий.');
    }catch(error){status.textContent=error.message;status.className='error';notice(error.message,'error');}
    finally{busy=false;form.setAttribute('aria-busy','false');availability();}
  };
  document.addEventListener('story-refreshed',availability);document.addEventListener('editor-state-changed',availability);availability();
}
