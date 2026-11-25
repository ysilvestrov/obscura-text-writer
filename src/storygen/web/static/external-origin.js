// MCP-BRIDGE: a version written by an external chat client carries the client's own claim {client, model?}.
// R-48 MANUSCRIPT-IMPORT: prose from the author's manuscript file names that file; given a scene without a plan the label adds
// that the plan is optional — validation checks the prose and the memory (spec §4.4, owner's answer 1).
import {t,uiText} from './i18n.js';
const planless=scene=>!!scene&&!scene.heads?.plan&&!String(scene.beats||'').trim();
export function externalOriginLabel(version,scene=null){
  const manuscript=version?.manuscript_import;
  if(manuscript?.file_name){
    const label=t('manuscript_import.ui.origin',{p0:manuscript.file_name});
    return planless(scene)?label+' · '+t('manuscript_import.ui.plan_optional'):label;
  }
  const origin=version?.external_origin;
  if(!origin?.client)return '';
  return origin.model?t('version.external_client_model',{p0:origin.client,p1:origin.model}):t('version.external_client',{p0:origin.client});
}
// R-48 (spec §4.4): the scene's status row names the manuscript its prose head came from (`prose_origin` of the story view)
// and, without a plan, adds that the plan is optional.
export function sceneOriginLabel(scene){
  const origin=scene?.prose_origin;
  return origin?.kind==='manuscript_import'?externalOriginLabel({manuscript_import:origin},scene):'';
}
// The status row shows the label of the version in the buffer as text; a version without an origin hides it.
export function renderOriginInto(node,version,scene=null){if(!node)return;node.hidden=!externalOriginLabel(version,scene);uiText(node,'textContent',()=>externalOriginLabel(version,scene))}
