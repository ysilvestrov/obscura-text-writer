import {confirmDialog} from './dialogs.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {returnLink} from './workspace-links.js';
import {CharacterBuffer} from './characters-state.js';

const host=document.querySelector('#characters-page');
if(host){
  const buffer=new CharacterBuffer(),panel=document.querySelector('#characters-editor');
  const storyId=host.dataset.storyId,initialScene=new URLSearchParams(location.search).get('scene');
  document.querySelector('#characters-return').href=returnLink(storyId,location.search);
  const help=document.createElement('p');uiText(help,"textContent",()=>(t("m_e80514b7871e")));panel.append(help);
  const form=document.createElement('form'),list=document.createElement('div'),status=document.createElement('p');status.setAttribute('role','status');status.id='characters-status';
  const tools=document.createElement('div');tools.className='actions characters-tools';
  const button=(text,fn)=>{const b=document.createElement('button');b.type='button';b.className='secondary';uiText(b,"textContent",()=>(text));b.onclick=fn;return b};
  const save=document.createElement('button');save.type='submit';save.id='characters-save';uiText(save,"textContent",()=>(t("m_62a3e0c3c375")));
  const add=button(live(()=>(t("m_02e19be588cb"))),()=>{buffer.cards.push({id:null,schema_version:2,name:'',entries:[]});changed();render()});
  const reload=button(live(()=>(t("m_ca97d079f3b6"))),()=>load(true));add.id='characters-add';tools.append(save,add,reload);form.append(tools,status,list);panel.append(form);
  const source=document.createElement('details'),sourceTitle=document.createElement('summary'),sourceText=document.createElement('pre');uiText(sourceTitle,"textContent",()=>(t("m_f617494aaf91")));sourceText.className='character-preview';source.append(sourceTitle,sourceText);panel.append(source);
  const previewLabel=document.createElement('label');uiText(previewLabel,"textContent",()=>(t("m_8f752c2d0363")));
  const previewScene=document.createElement('select');previewLabel.append(previewScene);
  const preview=button(live(()=>(t("m_9476f44d3175"))),showPreview),previewInfo=document.createElement('p'),previewText=document.createElement('pre');preview.id='characters-preview';previewText.id='characters-preview-text';previewText.className='character-preview';previewInfo.setAttribute('role','status');panel.append(previewLabel,preview,previewInfo,previewText);
  let metadata=null,previewBusy=false;
  const url=()=>`/api/stories/${storyId}/characters`;
  function update(){
    save.disabled=buffer.saving||!buffer.dirty||buffer.revision===null;add.disabled=buffer.saving||buffer.revision===null;
    reload.disabled=buffer.saving;preview.disabled=buffer.saving||previewBusy||!previewScene.value||buffer.revision===null;
    list.querySelectorAll('fieldset').forEach(field=>field.disabled=buffer.saving);

  }
  function changed(){buffer.changed();uiText(status,"textContent",()=>(t("m_525315c068da")));uiText(previewInfo,"textContent",()=>(t("m_e2ea033c762a")));uiText(previewText,"textContent",()=>(''));update()}
  function field(label,value,oninput,tag='input'){
    const wrapper=document.createElement('label');uiText(wrapper,"textContent",()=>(label));
    const input=document.createElement(tag);input.value=value||'';input.required=true;
    if(tag==='textarea')input.rows=12;
    input.oninput=()=>{oninput(input.value);changed()};wrapper.append(input);return wrapper;
  }
  function render(){
    list.replaceChildren();
    if(!buffer.cards.length){const p=document.createElement('p');uiText(p,"textContent",()=>(t("m_4827b478b0a5")));list.append(p)}
    buffer.cards.forEach((card,cardIndex)=>{
      const group=document.createElement('fieldset'),legend=document.createElement('legend');uiText(legend,"textContent",()=>(card.name||t("m_8e41ae9d25b5")));group.append(legend);
      group.append(field(msg("m_889b99ca3698"),card.name,value=>{card.name=value;uiText(legend,"textContent",()=>(value||t("m_8e41ae9d25b5")))}));
      if(card.id){const id=document.createElement('small');uiText(id,"textContent",()=>(t("m_acfcb2b6cf7c")+card.id));group.append(id)}
      card.entries.forEach((entry,index)=>{
        const row=document.createElement('div');row.className='character-entry';
        row.append(field(msg("m_4c3c54c0c1d0"),entry.text,value=>{entry.text=value;split.disabled=entry.text.split(/\n\s*\n/).filter(s=>s.trim()).length<2},'textarea'));
        const availability=document.createElement('label');uiText(availability,"textContent",()=>(t("m_954be4c83b36")));const mode=document.createElement('select');
        for(const [value,text]of labelEntries({get unclassified(){return t("m_311580500a99")},get timeless(){return t("m_ecd363f9ec0c")},get from_scene(){return t("m_6a2b794f389a")}})){const opt=document.createElement('option');opt.value=value;uiText(opt,"textContent",()=>(text));mode.append(opt)}
        mode.value=entry.availability;availability.append(mode);row.append(availability);
        const sceneLabel=document.createElement('label');uiText(sceneLabel,"textContent",()=>(t("m_45d0c9504e2b")));const sceneSelect=document.createElement('select');
        const empty=document.createElement('option');empty.value='';uiText(empty,"textContent",()=>(t("m_f0f1417db6de")));sceneSelect.append(empty);
        for(const scene of metadata?.scenes||[]){const opt=document.createElement('option');opt.value=scene.id;uiText(opt,"textContent",()=>(`${scene.position+1}. ${scene.title}`));sceneSelect.append(opt)}
        sceneSelect.value=entry.available_from_scene_id||'';sceneLabel.append(sceneSelect);row.append(sceneLabel);
        const scopeVisibility=()=>{sceneLabel.hidden=mode.value!=='from_scene';sceneSelect.disabled=sceneLabel.hidden;sceneSelect.required=!sceneLabel.hidden};scopeVisibility();
        mode.onchange=()=>{entry.availability=mode.value;entry.available_from_scene_id=mode.value==='from_scene'?(sceneSelect.value||null):null;scopeVisibility();changed()};
        sceneSelect.onchange=()=>{entry.available_from_scene_id=sceneSelect.value||null;changed()};
        const originLabel=document.createElement('label');uiText(originLabel,"textContent",()=>(t("m_ad3ce05697e9")));const origin=document.createElement('select');
        for(const [value,text]of labelEntries({get author(){return t("m_7ac9375dd3a8")},get imported(){return t("m_444226b67869")}})){const opt=document.createElement('option');opt.value=value;uiText(opt,"textContent",()=>(text));opt.disabled=value==='imported'&&!entry.sources?.length;origin.append(opt)}
        origin.value=entry.origin;origin.onchange=()=>{entry.origin=origin.value;changed()};originLabel.append(origin);row.append(originLabel);
        const evidence=document.createElement('small');uiText(evidence,"textContent",()=>(entry.sources?.length?t("m_5ad645c41ab8",{p0:(entry.sources.length)}):t("m_d79944f68a86")));row.append(evidence);
        const actions=document.createElement('div');actions.className='actions';
        const split=button(live(()=>(t("m_71b6d4a1ed6a"))),()=>{const parts=entry.text.split(/\n\s*\n/).map(s=>s.trim()).filter(Boolean);if(parts.length<2)return;card.entries.splice(index,1,...parts.map((text,i)=>({...structuredClone(entry),id:i===0?entry.id:null,text})));changed();render()});
        split.disabled=entry.text.split(/\n\s*\n/).filter(s=>s.trim()).length<2;
        actions.append(split,button(live(()=>(t("m_17a658079b91"))),()=>{card.entries.splice(index,1);changed();render()}));row.append(actions);group.append(row);
      });
      const actions=document.createElement('div');actions.className='actions';
      actions.append(button(live(()=>(t("m_7102b4a4f32a"))),()=>{card.entries.push({id:null,text:'',availability:'unclassified',available_from_scene_id:null,origin:'author',sources:[]});changed();render()}),button(live(()=>(t("m_1c58214eee32"))),()=>{buffer.cards.splice(cardIndex,1);changed();render()}));group.append(actions);list.append(group);
    });update();
  }
  async function load(force=false){
    if(buffer.saving)return;
    if(buffer.dirty&&!force)return;
    const before=buffer.epoch;
    if(buffer.dirty&&force&&!await confirmDialog(t("m_283c542f3d8f")))return;
    if(buffer.saving||buffer.epoch!==before)return;
    const epoch=buffer.epoch,token=buffer.beginLoad();
    try{
      const data=await api(url());
      if(force&&epoch===buffer.epoch)buffer.dirty=false;
      if(!buffer.loaded(data,token))return;
      metadata=data;uiText(status,"textContent",()=>(data.warnings.join(' ')||t("m_32af7a849848")));source.hidden=!data.source;uiText(sourceText,"textContent",()=>(data.source?.text||''));
      const selected=previewScene.value;previewScene.replaceChildren();
      for(const scene of data.scenes){const opt=document.createElement('option');opt.value=scene.id;uiText(opt,"textContent",()=>(`${scene.position+1}. ${scene.title}`));previewScene.append(opt)}
      if(data.scenes.some(s=>s.id===selected))previewScene.value=selected;else if(data.scenes.some(s=>s.id===initialScene))previewScene.value=initialScene;
      render();
    }catch(error){uiText(status,"textContent",()=>(diagnostic(error.message)));notice(error.message,'error');update()}
  }
  form.onsubmit=async event=>{
    event.preventDefault();if(!form.reportValidity()||buffer.saving)return;
    const snapshot=buffer.beginSave();update();
    try{
      const data=await api(url(),json('PUT',{cards:snapshot.cards,expected_revision:snapshot.expected_revision}));
      if(buffer.saved(data,snapshot)){metadata=data;source.hidden=!data.source;uiText(sourceText,"textContent",()=>(data.source?.text||''));uiText(status,"textContent",()=>(t("m_962885cd6c4c")));render();notice(msg("m_e83504ed5d8a"))}
      else{uiText(status,"textContent",()=>(t("m_8542f3691e5d")));notice(status.textContent,'warning')}

    }catch(error){buffer.failed();uiText(status,"textContent",()=>(diagnostic(error.message)));notice(error.message,'error')}
    finally{update()}
  };
  async function showPreview(){
    if(!form.reportValidity())return;
    const request=buffer.previewRequest(previewScene.value);previewBusy=true;uiText(previewInfo,"textContent",()=>(t("m_f1623b0f5ef2")));update();
    try{
      const result=await api(url()+'/preview',json('POST',{cards:structuredClone(buffer.cards),scene_id:request.scene_id}));
      if(!buffer.previewCurrent(request,previewScene.value))return;
      uiText(previewText,"textContent",()=>(result.text||t("m_9eac07c93f30")));
      uiText(previewInfo,"textContent",()=>(t("m_e2b07cc2445c",{p0:(result.excluded_count)})+result.warnings.join(' ')));
    }catch(error){if(buffer.previewCurrent(request,previewScene.value)){uiText(previewInfo,"textContent",()=>(diagnostic(error.message)));notice(error.message,'error')}}
    finally{previewBusy=false;update()}
  }
  previewScene.onchange=()=>{buffer.previewToken++;uiText(previewText,"textContent",()=>(''));uiText(previewInfo,"textContent",()=>(t("m_733e7d9098f5")))};
  globalThis.addEventListener('beforeunload',event=>{if(buffer.dirty||buffer.saving){event.preventDefault();event.returnValue=''}});
  load();
}
