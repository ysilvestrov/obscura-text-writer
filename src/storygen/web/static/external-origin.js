// MCP-BRIDGE: a version written by an external chat client carries the client's own claim {client, model?}.
import {t,uiText} from './i18n.js';
export function externalOriginLabel(version){
  const origin=version?.external_origin;
  if(!origin?.client)return '';
  return origin.model?t('version.external_client_model',{p0:origin.client,p1:origin.model}):t('version.external_client',{p0:origin.client});
}
// The status row shows the label of the version in the buffer as text; a version without an origin hides it.
export function renderOriginInto(node,version){if(!node)return;node.hidden=!externalOriginLabel(version);uiText(node,'textContent',()=>externalOriginLabel(version))}
