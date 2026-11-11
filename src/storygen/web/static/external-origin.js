// MCP-BRIDGE: a version written by an external chat client carries the client's own claim {client, model?}.
import {t} from './i18n.js';
export function externalOriginLabel(version){
  const origin=version?.external_origin;
  if(!origin?.client)return '';
  return origin.model?t('version.external_client_model',{p0:origin.client,p1:origin.model}):t('version.external_client',{p0:origin.client});
}
