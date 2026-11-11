import {api,notice} from './api.js';
import {state,refresh} from './revision-context.js';
// #89: the revision page has no run stream of its own; it polls while a run is active and
// re-dispatches the events impact.js and review-session.js already listen to.
const active=new Set(['queued','running','pause_requested','cancellation_requested']);
let known=new Map(),timer=null;
async function poll(){
  timer=null;
  try{
    await refresh();
    for(const run of state.workspaceRuns){
      if(known.get(run.id)===run.state)continue;known.set(run.id,run.state);
      const detail=(await api(`/api/runs/${run.id}`)).run;
      document.dispatchEvent(new CustomEvent('workspace-run-state',{detail}));
    }
  }catch(error){notice(error.message,'error')}
  if(state.workspaceRuns.some(run=>active.has(run.state)))timer=setTimeout(poll,1500);
}
const schedule=()=>{if(!timer)timer=setTimeout(poll,300)};
document.addEventListener('run-enqueued',schedule);
refresh().then(()=>{for(const run of state.workspaceRuns)known.set(run.id,run.state);if(state.workspaceRuns.some(run=>active.has(run.state)))schedule()}).catch(error=>notice(error.message,'error'));
