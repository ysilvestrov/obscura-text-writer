import {t,uiText} from './i18n.js';
import {state,textEditor,saveBuffer} from './editor.js';
import {api,json,notice} from './api.js';
const host=document.querySelector('#brief-proposal');
if(host){
  const help=document.createElement('p'),changes=document.createElement('ul'),accept=document.createElement('button');accept.type='button';
  uiText(help,'textContent',()=>t('brief.proposal_help'));uiText(accept,'textContent',()=>t('m_26986720d655'));host.append(help,changes,accept);
  let busy=false;
  const pendingRef=()=>{
    const ref=textEditor.sourceRef();
    return state.mode==='brief'&&state.bufferOrigin==='current'&&ref?.kind==='brief'&&ref.scene_id===state.scene?.id&&ref.id!==state.scene.heads.brief?ref:null;
  };
  function render(){
    const ref=pendingRef(),pending=!!ref,changed=state.pendingBrief!==pending;state.pendingBrief=pending;host.hidden=!pending;
    const active=(state.workspaceRuns||[]).some(run=>['queued','running','pause_requested','cancellation_requested'].includes(run.state));
    accept.disabled=!ref||busy||state.dirty||state.saving||ref.stale||!ref.complete||active;
    uiText(accept,'title',()=>state.dirty?t('m_a4c2e86ecc1a'):ref?.stale?t('m_63721412ce4c'):'');
    changes.replaceChildren();
    if(ref){try{for(const text of JSON.parse(textEditor.read()).proposed_changes||[]){const item=document.createElement('li');item.textContent=text;changes.append(item);}}catch{}}
    if(changed)document.dispatchEvent(new CustomEvent('brief-review-state'));
  }
  accept.onclick=async()=>{
    render();if(accept.disabled)return;
    const ref=pendingRef(),sceneId=state.scene.id,readonly=textEditor.isReadOnly();busy=true;textEditor.readOnly(true);render();
    try{
      await saveBuffer(async snapshot=>{
        const scene=await api(`/api/scenes/${sceneId}/accept-brief`,json('POST',{version_id:ref.id,expected_revision:snapshot.scene.revision}));
        return {scene,version:ref};
      });
      notice(t('brief.accepted'));
    }catch(error){notice(error.message,'error');}
    finally{busy=false;if(state.scene?.id===sceneId&&state.mode==='brief')textEditor.readOnly(readonly);render();}
  };
  for(const event of ['editor-state-changed','scene-selected','story-refreshed','workspace-run-state','workspace-readiness'])document.addEventListener(event,render);
  render();
}
