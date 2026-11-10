import {t,uiText,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {state,selectScene,refresh} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
// #44: the author confirms that the accepted prose rests on the current brief and marks who was introduced.
// The checkboxes are a local draft per scene and prose: reloads, opening the brief and switching scenes keep them.
// The confirmation always targets the prose the editor shows; if the server head moved on, confirming is disabled.
export function briefLinkModel(data,draft){
  const checked=new Set(draft??(data?.cast||[]).filter(item=>item.checked).map(item=>item.id));
  return {
    visible:!!data&&(data.needed||data.source==='link')&&!!data.brief&&(data.cast||[]).length>0,
    confirmed:data?.source==='link',
    rows:(data?.cast||[]).map(item=>({id:item.id,name:item.name,checked:checked.has(item.id)})),
    introduced:[...checked].filter(id=>(data?.cast||[]).some(item=>item.id===id)),
  };
}

const host=document.querySelector('#brief-link');
if(host){
  host.className='brief-link';
  let data=null,key=null,busy=false,open=false,token=0;
  const drafts=new Map();
  const draftKey=()=>state.scene?.heads?.prose?`${state.scene.id}:${state.scene.heads.prose}`:null;
  const getDraft=()=>drafts.get(draftKey())??null;
  const setDraft=value=>{const k=draftKey();if(!k)return;value===null?drafts.delete(k):drafts.set(k,value);};
  const behind=()=>!!data&&data.prose_version_id!==state.scene?.heads?.prose;
  const node=(tag,render,className)=>{const n=document.createElement(tag);if(render)uiText(n,'textContent',render);if(className)n.className=className;return n;};
  const button=(render,onclick,className='secondary')=>{const b=node('button',render,className);b.type='button';b.onclick=onclick;return b;};
  const active=()=>state.mode==='prose'&&state.bufferOrigin!=='history'&&!!state.scene?.heads?.prose;
  const sceneKey=()=>active()?`${state.scene.id}:${state.scene.heads.prose}:${state.scene.heads.brief||''}`:null;

  function render(){
    host.replaceChildren();
    const draft=getDraft(),model=briefLinkModel(data,draft);
    host.hidden=!active()||!model.visible;
    if(host.hidden)return;
    host.append(node('h3',()=>t('brief_link.title')));
    if(model.confirmed&&!open){
      const names=model.rows.filter(row=>row.checked).map(row=>row.name);
      host.append(node('p',()=>names.length?t('brief_link.confirmed_with',{p0:names.join(', ')}):t('brief_link.confirmed_none'),'brief-link-state'));
      const actions=node('div',null,'actions');
      actions.append(button(()=>t('brief_link.change'),()=>{open=true;render();}));
      if(data.next_scene_id)actions.append(button(()=>t('brief_link.next'),goNext));
      host.append(actions);return;
    }
    host.append(node('p',()=>t('brief_link.help',{p0:data.hero_name||''}),'brief-link-help'));
    const brief=node('p',null,'brief-link-brief');
    uiText(brief,'textContent',()=>t('brief_link.brief',{p0:data.brief.objective||'—'})+(data.brief.stale?' '+t('brief_link.stale'):''));
    const openBrief=button(()=>t('brief_link.open_brief'),()=>void invokeWorkspaceCommand('show','brief'));
    host.append(brief,openBrief);
    const list=node('fieldset',null,'brief-link-cast');
    list.append(node('legend',()=>t('brief_link.introduced')));
    for(const row of model.rows){
      const label=document.createElement('label'),box=document.createElement('input');
      box.type='checkbox';box.checked=row.checked;box.disabled=busy;box.value=row.id;
      box.onchange=()=>{const next=new Set(briefLinkModel(data,getDraft()).introduced);box.checked?next.add(row.id):next.delete(row.id);setDraft([...next]);};
      label.append(box,document.createTextNode(' '+row.name));list.append(label);
    }
    host.append(list);
    if(behind())host.append(node('p',()=>t('brief_link.prose_changed'),'brief-link-stale'));
    const actions=node('div',null,'actions');
    const confirm=button(()=>t('brief_link.confirm'),submit,'brief-link-confirm');confirm.disabled=busy||state.saving||behind();
    actions.append(confirm);
    if(data.next_scene_id)actions.append(button(()=>t('brief_link.next'),goNext));
    host.append(actions);
  }

  async function load(force=false){
    const next=sceneKey();
    if(!next){data=null;key=null;render();return;}
    if(next===key&&!force)return render();
    const sameScene=key&&next.split(':')[0]===key.split(':')[0]&&next.split(':')[1]===key.split(':')[1];
    if(!sameScene)open=false;
    key=next;const mine=++token;
    try{
      const result=await api(`/api/scenes/${state.scene.id}/brief-link`);
      if(mine!==token)return;
      data=result;render();
    }catch(error){if(mine===token){data=null;render();notice(diagnostic(error.message),'error');}}
  }

  async function submit(){
    if(busy||behind())return;
    const model=briefLinkModel(data,getDraft()),sceneId=state.scene.id,proseId=state.scene.heads.prose;
    busy=true;render();
    try{
      await api(`/api/scenes/${sceneId}/brief-link`,json('POST',{prose_version_id:proseId,brief_version_id:data.brief.version_id,introduced:model.introduced,expected_revision:data.revision}));
      drafts.delete(`${sceneId}:${proseId}`);open=false;notice(t('brief_link.saved'));
      await refresh();
    }catch(error){notice(diagnostic(error.message),'error');}
    finally{busy=false;if(state.scene?.id===sceneId)await load(true);}
  }

  async function goNext(){
    const scene=state.view?.scenes?.find(item=>item.id===data?.next_scene_id);
    if(!scene)return;
    await selectScene(scene);
    if(state.scene?.id===scene.id&&!state.dirty)await invokeWorkspaceCommand('show','prose');
  }

  for(const event of ['editor-state-changed','scene-selected','story-refreshed'])document.addEventListener(event,()=>void load());
  document.addEventListener?.('ui-locale-changed',render);
  globalThis.addEventListener?.('beforeunload',event=>{if(drafts.size){event.preventDefault();event.returnValue='';}});
  void load();
}
