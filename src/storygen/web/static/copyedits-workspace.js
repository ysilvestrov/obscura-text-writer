import {api,json,notice} from './api.js';
import {state,refresh,loadBuffer} from './editor.js';
import {mountCopyeditReview} from './copyedits.js';
import {registerWorkspaceCommand} from './workspace-commands.js';

const host=document.querySelector('#copyedit-panel');
if(host){
  const component=mountCopyeditReview({host,state,api,json,notice,onAvailability:value=>{state.reviewAvailability=value;document.dispatchEvent(new CustomEvent('workspace-review-state'))},onQueued:run=>document.dispatchEvent(new CustomEvent('run-enqueued',{detail:run})),onApplied:async(result,captured)=>{
    const version=await api('/api/versions/'+result.version.id);
    if(state.scene?.id===captured.sceneId&&!state.dirty&&!state.saving&&state.bufferEpoch===captured.epoch){
      loadBuffer(result.scene,'prose',version.text);
      document.querySelector('#current-kind').textContent='ПРОЗА';
    }
    await refresh();
  }});
  registerWorkspaceCommand('accept-review',component.accept);
  for(const event of ['scene-selected','story-refreshed'])document.addEventListener(event,()=>component.reload());
  document.addEventListener('editor-state-changed',component.updateAvailability);
  component.reload();
}
