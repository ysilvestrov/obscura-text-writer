// #89 WORKSPACE-TOOLS: scene sections of the side panel remember being open in this browser.
// Storage may be missing or throw (private mode); then every section simply starts closed.
export const SECTIONS_KEY='obscura.workspace.sections';
function read(storage){try{const value=JSON.parse(storage?.getItem(SECTIONS_KEY)||'{}');return value&&typeof value==='object'?value:{}}catch{return {}}}
export function restoreSections(sections,storage){const saved=read(storage);for(const section of sections)section.open=saved[section.dataset.section]===true}
export function rememberSection(section,storage){try{const saved=read(storage);saved[section.dataset.section]=!!section.open;storage?.setItem(SECTIONS_KEY,JSON.stringify(saved))}catch{}}
export function installToolSections(root=document){
  let storage=null;try{storage=globalThis.localStorage}catch{}
  const sections=[...root.querySelectorAll('.tool-section[data-section]')];
  restoreSections(sections,storage);
  for(const section of sections)section.addEventListener('toggle',()=>rememberSection(section,storage));
}
if(globalThis.document?.querySelector?.('.tool-section[data-section]'))installToolSections();
