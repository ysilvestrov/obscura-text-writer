import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
// This controller has no scene-selection dependency: publication belongs to the story.
export function installExportForm({state,api,json,notice,document}){
  const get=id=>document.querySelector('#'+id);
  const button=get('export-story'),form=get('export-form'),submit=get('export-submit'),status=get('export-status');
  let busy=false;
  button.hidden=false;
  function availability(){
    const reason=state.dirty?t("m_a4c2e86ecc1a"):state.saving?t("m_51204171ac66"):!state.view?.scenes.some(scene=>scene.heads.prose)?t("m_1b19cb3ea4ae"):'';
    button.disabled=busy||!!reason;submit.disabled=busy||!!reason;uiText(button,"title",()=>(diagnostic(reason)));uiText(submit,"title",()=>(diagnostic(reason)));
    if(reason){uiText(status,"textContent",()=>(diagnostic(reason)));status.className='muted';}
  }
  // #89: in the workspace the form lives in a dialog opened from the story menu.
  const dialog=form.closest?.('dialog');
  if(dialog)dialog.addEventListener('close',()=>{button.setAttribute('aria-expanded','false');document.querySelector('#story-menu-toggle')?.focus()});
  button.onclick=()=>{if(dialog){form.hidden=false;dialog.showModal();button.setAttribute('aria-expanded','true');get('export-format').focus();return}form.hidden=!form.hidden;button.setAttribute('aria-expanded',String(!form.hidden));if(!form.hidden)get('export-format').focus();};
  get('export-cancel').onclick=()=>{if(dialog){dialog.close();return}form.hidden=true;button.setAttribute('aria-expanded','false');button.focus();};
  form.onsubmit=async event=>{
    event.preventDefault();availability();if(submit.disabled)return;
    busy=true;availability();form.setAttribute('aria-busy','true');uiText(status,"textContent",()=>(t("m_74a8c1872ac9")));status.className='muted';
    try{
      const format=get('export-format').value,allow_incomplete=get('export-incomplete').checked;
      const result=await api(`/api/stories/${state.storyId}/export`,json('POST',{format,allow_incomplete}));
      const box=document.createElement('div');
      for(const [url,label]of[[result.download_url,t("m_c5cec41d8b00",{p0:(format.toUpperCase())})],[result.manifest_url,msg("m_d328f5580f1f")]]){
        const link=document.createElement('a');link.href=url;uiText(link,"textContent",()=>(label));link.download='';box.append(link);
      }
      get('publication-links').replaceChildren(box);uiText(status,"textContent",()=>(t("m_5b3186a61583")));status.className='success';
      notice(msg("m_28616225540c"));
    }catch(error){uiText(status,"textContent",()=>(diagnostic(error.message)));status.className='error';notice(error.message,'error');}
    finally{busy=false;form.setAttribute('aria-busy','false');availability();}
  };
  document.addEventListener('story-refreshed',availability);document.addEventListener('editor-state-changed',availability);availability();
}
