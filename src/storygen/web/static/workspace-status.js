import {t} from './i18n.js';
// UI-FEEDBACK: one scene-status vocabulary for the scene list and the status row (#89).
const KEYS={not_started:'m_521bdc3a57e0',no_text:'m_4b3a60e43929',draft:'m_4de0a8f8a92b',prose:'m_79679b4689c4',needs_review:'m_f3522e6a9fcc',
  impact_pending:'impact.pending',impact_changes:'impact.changes_required',impact_current:'impact.current'};
export function sceneStatusKey(scene,impactStatus={}){
  const heads=scene.heads||{},impact=(impactStatus||{})[scene.id]?.prose;
  if(!heads.prose&&!heads.draft)return heads.brief?'no_text':'not_started';
  if(impact==='changes_required')return 'impact_changes';
  if(impact==='no_impact')return 'impact_current';
  if(scene.needs_review)return impact==='pending'?'impact_pending':'needs_review';
  return heads.prose?'prose':'draft';
}
export function sceneStatus(scene,impactStatus){const key=sceneStatusKey(scene,impactStatus);return {key,label:t(KEYS[key])}}
// #89: the workspace shows a sequential review card only while that session waits for the author (a decision, a resume or a retry), not while it runs.
export function reviewNeedsAuthor(run){return ['needs_review','paused','pause_requested','failed','interrupted','alternative'].includes(run?.state)}
// Materials awaiting an impact decision: brief and prose of one scene count separately, as on the revision page.
const PENDING=['pending','changes_required'];
export function pendingMaterialCount(impactStatus){return Object.values(impactStatus||{}).reduce((n,s)=>n+PENDING.includes(s?.brief)+PENDING.includes(s?.prose),0)}
// The editor keeps its scene object to protect the loaded buffer; status labels read the refreshed list.
export function liveScene(scene,scenes){return scene?(scenes||[]).find(s=>s.id===scene.id)||scene:null}
