import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML} from './i18n.js';
const commands=new Map();
export function registerWorkspaceCommand(name,handler){commands.set(name,handler)}
export async function invokeWorkspaceCommand(name,payload){
  const handler=commands.get(name);
  if(!handler)throw new Error(t("m_78a192c6eb97"));
  return handler(payload);
}
