import {t,uiText,uiAttr,diagnostic} from './i18n.js';
// EDITOR-IMPORT (PR 2): the story-menu dialog that reads an editor's DOCX. States: file choice → summary → (choice for
// scenes changed after the export) → result. The summary changes nothing; until it is confirmed or cancelled the server
// keeps the file, so every way out of the dialog without a save sends DELETE.
export const MAX_FILE=20*1024*1024;  // web/routes_editor_import.py: docx_import.MAX_FILE
export const IMPORTED=new Set(['changed','comments_only','over_limit']);
export const statusLabel=status=>t('editor_import.status.'+status);
// The status a scene ends up with: with «Replace all» a scene that needed a choice is compared with the current prose.
export const effectiveStatus=(scene,choice)=>scene.needs_choice&&choice==='replace'&&scene.replace_status?scene.replace_status:scene.status;
// A scene with a proposal opens on its review tab; every other scene on its draft.
export function sceneLink(storyId,sceneId,status){
  const query=new URLSearchParams({scene:sceneId,material:status==='changed'?'review':'draft'});
  return `/stories/${encodeURIComponent(storyId)}?${query}`;
}

export function installEditorImport({state,api,json,notice,document,refresh,selectScene,invokeWorkspaceCommand}){
  const get=id=>document.querySelector('#'+id);
  const button=get('import-edition'),reasonNode=get('import-edition-reason'),dialog=get('editor-import-dialog');
  if(!button||!dialog)return;
  const input=get('editor-import-file'),pick=get('editor-import-pick'),summaryBox=get('editor-import-summary'),tbody=summaryBox.querySelector('tbody');
  const warningsList=get('editor-import-warnings'),choice=get('editor-import-choice'),choiceText=get('editor-import-choice-text');
  const resultBox=get('editor-import-result'),status=get('editor-import-status'),submit=get('editor-import-submit');
  const cancel=get('editor-import-cancel'),cancelLabel=get('editor-import-cancel-label');
  const abort=get('editor-import-abort'),skip=get('editor-import-skip'),replace=get('editor-import-replace');
  // pending: the import_id the server still keeps (neither saved nor cancelled); epoch drops answers of an abandoned step.
  let preview=null,pending=null,epoch=0,busy=false,saving=false,view='pick';
  const base=storyId=>`/api/stories/${storyId}/editor-import`;
  const discard=()=>{
    if(!pending||saving)return;  // a running save reads the file; the server deletes it after a successful apply
    const {storyId,importId}=pending;pending=null;
    api(`${base(storyId)}/${importId}`,{method:'DELETE'}).catch(()=>{});  // the server also sweeps files older than 24 h
  };
  const setStatus=(render,kind='')=>{uiText(status,'textContent',render);status.className=kind};
  const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};
  const importable=()=>(preview?.scenes||[]).filter(scene=>IMPORTED.has(scene.status)).length;

  function sync(){
    pick.hidden=view!=='pick';summaryBox.hidden=view!=='summary';resultBox.hidden=view!=='result';
    const choosing=view==='summary'&&!!preview?.choice_required;
    choice.hidden=!choosing;submit.hidden=view!=='summary'||choosing;cancel.hidden=choosing;
    input.disabled=busy;submit.disabled=busy||importable()===0;abort.disabled=skip.disabled=replace.disabled=busy;cancel.disabled=saving;
    dialog.setAttribute('aria-busy',String(busy));
    uiText(cancelLabel,'textContent',()=>view==='result'?t('editor_import.close'):t('m_8b4c2025378a'));
    uiText(submit,'textContent',()=>t('editor_import.import',{p0:importable()}));
  }
  function show(next){view=next;sync()}
  function reset(){
    epoch++;discard();preview=null;busy=saving=false;input.value='';
    tbody.replaceChildren();warningsList.replaceChildren();choiceText.replaceChildren();resultBox.replaceChildren();
    setStatus(()=>'');show('pick');
  }
  function availability(){
    const reason=state.dirty?'m_a4c2e86ecc1a':state.saving?'m_51204171ac66':'';
    button.disabled=!!reason;uiAttr(button,'title',()=>reason?t(reason):'');
    reasonNode.hidden=!reason;uiText(reasonNode,'textContent',()=>reason?t(reason):'');
  }

  function renderSummary(){
    tbody.replaceChildren();warningsList.replaceChildren();
    for(const scene of preview.scenes){
      const row=document.createElement('tr');
      const title=node('th',null);title.scope='row';title.append(node('span',()=>scene.title));
      if(scene.warnings.length){const list=node('ul',null,'muted');for(const text of scene.warnings)list.append(node('li',()=>diagnostic(text)));title.append(list)}
      const cell=node('td',null);cell.append(node('span',()=>statusLabel(scene.status),'editor-import-status'));
      if(scene.needs_choice&&scene.replace_status){cell.append(document.createElement('br'),node('small',()=>t('editor_import.if_replaced',{p0:statusLabel(scene.replace_status)}),'muted'))}
      row.append(title,cell,node('td',()=>String(scene.edits)),node('td',()=>String(scene.comments+scene.general_comments)));
      tbody.append(row);
    }
    for(const text of preview.warnings)warningsList.append(node('li',()=>diagnostic(text)));
    if(preview.unmatched.length){const headings=preview.unmatched.map(h=>`«${h}»`).join(', ');warningsList.append(node('li',()=>t('editor_import.unmatched',{p0:headings})))}
    const changed=preview.scenes.filter(scene=>scene.needs_choice).map(scene=>`«${scene.title}»`).join(', ');
    uiText(choiceText,'textContent',()=>t('editor_import.choice_intro',{p0:changed}));
    if(!preview.choice_required&&!importable())setStatus(()=>t('editor_import.nothing'),'muted');
    else setStatus(()=>'');
  }

  function renderResult(result,shown,choiceMade){
    resultBox.replaceChildren();
    resultBox.append(node('p',()=>t('editor_import.result',{p0:result.imported.length,p1:result.skipped.length}),'success'));
    const skipped=new Map(result.skipped.map(item=>[item.scene_id,item.status]));
    const list=document.createElement('ul');
    for(const scene of shown.scenes){
      const imported=result.imported.includes(scene.scene_id);
      if(!imported&&!skipped.has(scene.scene_id))continue;
      const draftOnly=result.draft_only.includes(scene.scene_id);
      const final=imported?(draftOnly?'over_limit':effectiveStatus(scene,choiceMade)):skipped.get(scene.scene_id);
      const item=document.createElement('li'),link=node('a',()=>scene.title);
      link.href=sceneLink(state.storyId,scene.scene_id,imported?final:'skipped');
      link.onclick=event=>{
        if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
        event.preventDefault();dialog.close();open(scene.scene_id,imported&&final==='changed'?'review':'draft');
      };
      item.append(link,node('span',()=>' · '+(imported?statusLabel(final):t('editor_import.skipped_as',{p0:statusLabel(final)})),'muted'));
      list.append(item);
    }
    resultBox.append(list);
    if(result.imported.length)resultBox.append(node('p',()=>t('editor_import.where'),'muted'));
    if(result.warnings.length){const warnings=node('ul',null,'muted');for(const text of result.warnings)warnings.append(node('li',()=>diagnostic(text)));resultBox.append(warnings)}
  }

  async function open(sceneId,mode){
    try{
      const scene=(state.view?.scenes||[]).find(item=>item.id===sceneId);if(!scene)return;
      if(state.scene?.id!==sceneId)await selectScene(scene);
      if(state.scene?.id===sceneId)await invokeWorkspaceCommand('show',mode);
    }catch(error){notice(error.message,'error')}
  }

  input.onchange=async()=>{
    const chosen=input.files?.[0];if(!chosen)return;
    epoch++;discard();preview=null;tbody.replaceChildren();show('pick');
    if(chosen.size>MAX_FILE){input.value='';setStatus(()=>t('editor_import.server.too_large',{p0:MAX_FILE/(1024*1024)}),'error');return}
    const mine=epoch,storyId=state.storyId,body=new FormData();body.append('file',chosen,chosen.name);
    busy=true;sync();setStatus(()=>t('editor_import.reading'),'muted');
    try{
      const data=await api(`${base(storyId)}/preview`,{method:'POST',body});
      if(mine!==epoch||!dialog.open){api(`${base(storyId)}/${data.import_id}`,{method:'DELETE'}).catch(()=>{});return}
      pending={storyId,importId:data.import_id};preview=data;busy=false;renderSummary();show('summary');
    }catch(error){if(mine!==epoch)return;input.value='';setStatus(()=>diagnostic(error.message),'error')}
    finally{if(mine===epoch){busy=false;sync()}}
  };

  async function apply(changedScenes){
    if(!preview||busy)return;
    const mine=epoch,shown=preview,storyId=state.storyId;
    busy=saving=true;sync();setStatus(()=>t('editor_import.saving'),'muted');
    try{
      const body={fingerprint:shown.fingerprint};if(changedScenes)body.changed_scenes=changedScenes;
      const result=await api(`${base(storyId)}/${shown.import_id}`,json('POST',body));
      if(pending?.importId===shown.import_id)pending=null;  // saved: the server already removed the file
      if(mine!==epoch){try{await refresh?.()}catch{}return}  // the dialog was closed meanwhile; the scene list still follows
      busy=false;renderResult(result,shown,changedScenes);setStatus(()=>'');show('result');
      try{await refresh?.()}catch{}  // the scene list and statuses follow the new drafts
    }catch(error){
      if(mine!==epoch)return;
      // 409: the story changed after the summary; 404: the kept file is gone. Either way the file is read again.
      if(error.status===409||error.status===404){
        busy=saving=false;discard();preview=null;input.value='';tbody.replaceChildren();show('pick');
        setStatus(()=>t('editor_import.choose_again',{p0:diagnostic(error.message)}),'error');input.focus();
      }else setStatus(()=>diagnostic(error.message),'error');
    }finally{if(mine===epoch){busy=saving=false;sync()}}
  }

  button.onclick=()=>{
    availability();if(button.disabled)return;
    reset();dialog.showModal();button.setAttribute('aria-expanded','true');input.focus();
  };
  // Every way out (Cancel, «Cancel import», Escape, a scene link) resets the dialog; an unconfirmed summary is deleted.
  // While a save runs the dialog stays open: closing would delete the file the save is reading.
  dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault()});
  dialog.addEventListener('close',()=>{reset();button.setAttribute('aria-expanded','false');document.querySelector('#story-menu-toggle')?.focus()});
  cancel.onclick=()=>dialog.close();
  abort.onclick=()=>dialog.close();
  submit.onclick=()=>apply(null);
  skip.onclick=()=>apply('skip');
  replace.onclick=()=>apply('replace');
  document.addEventListener('story-refreshed',availability);document.addEventListener('editor-state-changed',availability);
  availability();sync();
}
