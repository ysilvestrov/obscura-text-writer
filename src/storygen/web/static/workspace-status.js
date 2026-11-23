import {t} from './i18n.js';
// UI-FEEDBACK: one scene-status vocabulary for the scene list and the status row (#89).
const KEYS={not_started:'m_521bdc3a57e0',no_text:'m_4b3a60e43929',draft:'m_4de0a8f8a92b',prose:'m_79679b4689c4',needs_review:'m_f3522e6a9fcc'};
// materialStatus is the story view's material_status: stale prose ('pending') needs review like a flagged scene.
export function sceneStatusKey(scene,materialStatus={}){
  const heads=scene.heads||{},prose=(materialStatus||{})[scene.id]?.prose;
  if(!heads.prose&&!heads.draft)return heads.brief?'no_text':'not_started';
  if(scene.needs_review||prose==='pending')return 'needs_review';
  return heads.prose?'prose':'draft';
}
export function sceneStatus(scene,materialStatus){const key=sceneStatusKey(scene,materialStatus);return {key,label:t(KEYS[key])}}
// The editor keeps its scene object to protect the loaded buffer; status labels read the refreshed list,
// unless the buffer already holds a newer scene than the list (#105: the brief loader fetches a fresh one).
export function liveScene(scene,scenes){
  if(!scene)return null;
  const listed=(scenes||[]).find(s=>s.id===scene.id);
  return listed&&(listed.revision??0)>=(scene.revision??0)?listed:scene;
}
