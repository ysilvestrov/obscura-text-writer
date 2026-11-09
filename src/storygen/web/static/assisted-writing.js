import {t,uiText,diagnostic} from './i18n.js';
import {state,textEditor,getAuthorComments,saveCurrentMaterial,loadBuffer,refresh} from './editor.js';
import {api,json,notice} from './api.js';
import {mountChangeReview} from './change-review.js';

const host=document.querySelector('#assisted-writing'),reviewHost=document.querySelector('#assisted-review');
if(host&&reviewHost){
  const button=document.createElement('button');button.type='button';uiText(button,'textContent',()=>t('rewrite.start'));
  const wrap=document.createElement('span');wrap.className='workspace-primary-wrap';
  const telemetry=document.createElement('small');telemetry.className='rewrite-telemetry';telemetry.tabIndex=0;
  const details=document.createElement('div');details.id='rewrite-telemetry-details';details.className='workspace-telemetry-details';details.setAttribute('role','tooltip');
  const hint=document.createElement('p');hint.className='muted';uiText(hint,'textContent',()=>t('rewrite.hint'));
  button.setAttribute('aria-describedby','rewrite-telemetry-details');wrap.append(button,telemetry,details);host.append(wrap,hint);
  const noteHistory=document.createElement('details'),noteTitle=document.createElement('summary'),noteText=document.createElement('pre');
  uiText(noteTitle,'textContent',()=>t('rewrite.instructions'));noteHistory.append(noteTitle,noteText);reviewHost.append(noteHistory);
  let busy=false,current=null,writer=null,rewriteWarnings=[],settingsEpoch=0;
  async function loadWriter(){const epoch=++settingsEpoch;writer=null;sync();try{const settings=await api(`/api/stories/${state.storyId}/settings`);if(epoch===settingsEpoch)writer=settings.roles?.writer?.provider||null;}catch{}if(epoch===settingsEpoch)sync();}
  const active=()=>state.mode==='draft'&&state.bufferOrigin!=='history'&&!!state.scene;
  function sync(){
    host.hidden=reviewHost.hidden=!active();
    const warnings=rewriteWarnings;
    const model=writer?.provider&&writer?.model?`${writer.provider} / ${writer.model}`:'';
    uiText(telemetry,'textContent',()=>model?t('workspace.telemetry',{p0:model,p1:1})+(warnings.length?' ⚠':''):t('workspace.telemetry_unknown'));
    uiText(details,'textContent',()=>[t('workspace.model',{p0:model||t('workspace.unknown')}),t('rewrite.hint'),...(warnings.length?[t('workspace.warnings',{p0:warnings.map(diagnostic).join('; ')})]:[])].join('\n'));
    const pending=active()&&!state.dirty&&!!current?.can_apply&&!!current?.has_changes&&!current?.decisions?.length;
    getAuthorComments()?.lock(busy||pending);
    let inputReady=false;
    try{const notes=getAuthorComments()?.capture()?.comment_set;inputReady=!!textEditor.read().trim()&&!!notes&&(!!notes.general.trim()||!!notes.comments.length)&&notes.comments.every(c=>c.anchor.state==='valid');}catch{}
    button.disabled=!inputReady||busy||state.saving||pending||!active()||(state.workspaceRuns||[]).some(r=>['queued','running','pause_requested','cancellation_requested'].includes(r.state));
    const changed=state.assistedReview!==pending;state.assistedReview=pending;
    if(changed)document.dispatchEvent(new CustomEvent('editor-state-changed'));
  }
  const component=mountChangeReview({host:reviewHost,state,api,json,notice,adapter:{kind:'rewrite',extraBody:data=>({expected_comments_revision:data.expected_comments_revision}),
    panel:panel=>{panel.open=true;},onReview:data=>{
      current=data;noteText.textContent=data?.comments?[data.comments.general,...data.comments.comments.map(c=>c.anchor.display_quote+' — '+c.instruction)].filter(Boolean).join('\n\n'):'';
      noteHistory.hidden=!data;sync();
    }},onApplied:async(result,captured)=>{
      current=null;sync();
      if(result.version&&state.scene?.id===captured.sceneId&&!state.dirty&&!state.saving&&state.bufferEpoch===captured.epoch){
        const version=await api('/api/versions/'+result.version.id);
        if(state.scene?.id===captured.sceneId&&!state.dirty&&!state.saving&&state.bufferEpoch===captured.epoch)loadBuffer(result.scene,'draft',version.text,'current',version.version);
      }
      await refresh();
    }});
  function assertCaptured(captured){
    if(!active()||state.scene.id!==captured.sceneId||state.bufferEpoch!==captured.epoch||state.dirty||state.saving)throw new Error(t('rewrite.input_changed'));
  }
  button.onclick=async()=>{
    if(busy||state.saving||!active())return;
    const captured={sceneId:state.scene.id,epoch:state.bufferEpoch};
    busy=true;sync();
    try{
      if(state.dirty)await saveCurrentMaterial();
      assertCaptured(captured);
      // Capture also blocks an unfinished popover before any network preflight.
      const local=getAuthorComments().capture();
      const notes=await api(`/api/scenes/${captured.sceneId}/comments`);assertCaptured(captured);
      if(notes.expected_comments_revision!==local.expected_comments_revision||notes.source_version_id!==local.expected_source_version_id)throw new Error(t('rewrite.diagnostic.2'));
      if(!notes.comment_set||!notes.comment_fingerprint||notes.source_version_id!==textEditor.identity().version_id)throw new Error(t('rewrite.save_first'));
      const inputs={source_version_id:notes.source_version_id,comment_set_id:notes.comment_set.id,comment_fingerprint:notes.comment_fingerprint};
      const preflight=await api(`/api/scenes/${captured.sceneId}/rewrites/preflight`,json('POST',inputs));assertCaptured(captured);
      if(!preflight.ready)throw new Error(diagnostic(preflight.reason));
      writer=preflight.roles?.writer||writer;rewriteWarnings=preflight.warnings||[];sync();
      assertCaptured(captured);
      const run=await api('/api/runs',json('POST',{request_id:crypto.randomUUID(),request:{story_id:state.storyId,scene_id:captured.sceneId,mode:'rewrite',...inputs}}));
      document.dispatchEvent(new CustomEvent('run-enqueued',{detail:run}));
    }catch(error){notice(error.message,'error');}
    finally{busy=false;sync();}
  };
  for(const event of ['scene-selected','story-refreshed'])document.addEventListener(event,()=>{current=null;rewriteWarnings=[];sync();void component.reload();});
  document.addEventListener('editor-state-changed',()=>{sync();component.updateAvailability();});
  document.addEventListener('workspace-run-state',sync);
  document.addEventListener('workspace-readiness',sync);
  document.addEventListener('story-refreshed',()=>void loadWriter());
  sync();void loadWriter();void component.reload();
}
