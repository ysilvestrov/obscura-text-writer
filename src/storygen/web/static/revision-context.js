import {api} from './api.js';
// #89: on the book revision page this module stands in for editor.js (import map), so impact.js and
// review-session.js run unchanged. There is no editor here: nothing is dirty, and opening a scene goes to the workspace.
const root=document.querySelector('[data-story-id]');
export const state={storyId:root?.dataset.storyId,scene:null,view:null,mode:null,dirty:false,saving:false,bufferEpoch:0,workspaceRuns:[],workspaceRun:null};
export async function refresh(){
  const [view,runs]=await Promise.all([api(`/api/stories/${state.storyId}`),api(`/api/stories/${state.storyId}/runs`)]);
  state.view=view;state.workspaceRuns=runs.runs;state.workspaceRun=runs.runs.at(-1)||null;
  document.dispatchEvent(new CustomEvent('story-refreshed'));
  return view;
}
export function sceneUrl(scene){
  const material=scene.heads?.prose?'prose':'brief';
  return `/stories/${encodeURIComponent(state.storyId)}?`+new URLSearchParams({scene:scene.id,material});
}
export async function selectScene(scene){location.assign(sceneUrl(scene))}
