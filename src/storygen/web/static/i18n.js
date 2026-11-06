import catalogs from './i18n.json' with {type:'json'};
const supported=new Set(['uk','en']);
export function chooseLocale(preference,languages=''){
  if(supported.has(preference))return preference;
  const candidates=String(languages).split(',').map((part,index)=>{const [tag,...rest]=part.trim().toLowerCase().split(';'),q=rest.find(p=>p.trim().startsWith('q='));return {lang:tag.split('-')[0],quality:q===undefined?1:Number(q.trim().slice(2)),index}}).filter(p=>supported.has(p.lang)&&p.quality>0&&p.quality<=1).sort((a,b)=>b.quality-a.quality||a.index-b.index);
  return candidates[0]?.lang||'uk';
}
function preference(){try{return globalThis.document?.cookie?.split(';').map(p=>p.trim()).find(p=>p.startsWith('obscura_locale='))?.slice(15)}catch{return null}}
let locale=globalThis.document?.documentElement?chooseLocale(preference(),globalThis.document.documentElement.lang||globalThis.navigator?.languages?.join(',')||''):'uk';
const bindings=new Set(),byElement=new WeakMap();
let tracking=null;
const depend=()=>{if(tracking)tracking.localized=true};
export const getLocale=()=>{depend();return locale};
class LiveLabel{constructor(render){this.render=render}toString(){return String(this.render())}[Symbol.toPrimitive](){return this.toString()}}
export const msg=(key,params={})=>new LiveLabel(()=>t(key,params));
export const live=render=>new LiveLabel(render);
export const labelEntries=object=>Object.keys(object).map(key=>[key,new LiveLabel(()=>object[key])]);
export function t(key,params={}){depend();const value=catalogs[locale]?.[key]??catalogs.uk[key]??key;return value.replace(/{(p\d+)}/g,(whole,name)=>Object.hasOwn(params,name)?String(params[name]):whole)}
const exactDiagnostics=new Map(),diagnosticPatterns=[];
const escapePattern=text=>text.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
for(const key of Object.keys(catalogs.uk))for(const value of [catalogs.uk[key],catalogs.en[key]]){
  const names=[...value.matchAll(/{(p\d+)}/g)].map(match=>match[1]);
  if(!names.length){exactDiagnostics.set(value,key);continue}
  const parts=value.split(/{p\d+}/g),weight=parts.join('').length;
  if(weight>=8)diagnosticPatterns.push({pattern:new RegExp('^'+parts.map(escapePattern).join('([\\s\\S]*?)')+'$'),key,names,weight});
}
diagnosticPatterns.sort((a,b)=>b.weight-a.weight);
export function diagnostic(text){
  if(typeof text!=='string')return text;
  const http=text.length<=6000&&text.match(/^HTTP (\d{3}): ([\s\S]+) (?:Автоматичного повтору немає|No automatic retry)\.$/);
  if(http)return t('generation.http_failure',{p0:http[1],p1:diagnostic(http[2])});
  if(exactDiagnostics.has(text))return t(exactDiagnostics.get(text));
  if(text.length<=6000)for(const entry of diagnosticPatterns){const match=entry.pattern.exec(text);if(match)return t(entry.key,Object.fromEntries(entry.names.map((name,index)=>[name,match[index+1]])))}
  for(const[uk,en]of [['Некоректні дані: ','Invalid data: '],['Помилка редактора: ','Editor error: '],['Помилка планувальника: ','Planner error: ']])for(const prefix of [uk,en])if(text.startsWith(prefix))return (getLocale()==='en'?en:uk)+diagnostic(text.slice(prefix.length));
  return text;
}
function remember(element,property,render,attribute=false){
  let entries=byElement.get(element);if(!entries){entries=new Map();byElement.set(element,entries)}
  const key=(attribute?'attr:':'')+property;let entry=entries.get(key);
  const previous=tracking,reads={localized:false};tracking=reads;let value;
  try{value=String(render())}finally{tracking=previous}
  // Raw manuscript, partial streams and clearing writes never participate in localization.
  if(reads.localized){if(!entry){entry={element:new WeakRef(element),property,attribute,render};entries.set(key,entry);bindings.add(entry)}else entry.render=render}
  else if(entry){bindings.delete(entry);entries.delete(key);entry=null}
  if(attribute){if(element.getAttribute?.(property)!==value)element.setAttribute(property,value)}else if(element[property]!==value)element[property]=value;
  if(entry&&!attribute&&property==='textContent')entry.textNode=element.firstChild?.nodeType===3?element.firstChild:null;
  return value;
}
export const uiText=(element,property,render)=>remember(element,property,render);
export const uiAttr=(element,property,render)=>remember(element,property,render,true);
export function bindMarked(root,params={}){
  if(!root?.querySelectorAll)return;
  const elements=[...(root.matches?.('[data-i18n],[data-i18n-attrs],[data-i18n-title-prefix]')?[root]:[]),...root.querySelectorAll('[data-i18n],[data-i18n-attrs],[data-i18n-title-prefix]')];
  for(const el of elements){if(el.dataset.i18nTitlePrefix)uiText(el,'textContent',()=>t(el.dataset.i18nTitlePrefix)+' '+el.dataset.uiTitleAuthor+' — Obscura');if(el.dataset.i18n)uiText(el,'textContent',()=>t(el.dataset.i18n,params));if(el.dataset.i18nAttrs)for(const[property,key]of Object.entries(JSON.parse(el.dataset.i18nAttrs)))uiAttr(el,property,()=>t(key))}
}
export function uiHTML(element,markup,params={}){element.innerHTML=markup;bindMarked(element,params);return markup}
export function uiInsertHTML(element,position,markup,params={}){element.insertAdjacentHTML(position,markup);bindMarked(element,params)}
export function setLocale(next){
  if(!supported.has(next))throw new Error('Unsupported UI locale');locale=next;
  const doc=globalThis.document;
  if(doc?.documentElement){doc.documentElement.lang=next;doc.cookie='obscura_locale='+next+'; Path=/; Max-Age=31536000; SameSite=Strict'}
  for(const entry of bindings){const el=entry.element.deref();if(!el){bindings.delete(entry);continue}if(el.isConnected===false)continue;const value=entry.render();if(entry.attribute){if(el.getAttribute?.(entry.property)!==String(value))el.setAttribute(entry.property,value)}else if(entry.property==='textContent'&&entry.textNode?.parentNode===el){if(entry.textNode.nodeValue!==String(value))entry.textNode.nodeValue=String(value)}else if(entry.property==='textContent'&&el.childNodes?.length){continue}else if(el[entry.property]!==String(value))el[entry.property]=String(value)}
  if(typeof doc?.dispatchEvent==='function'&&typeof CustomEvent!=='undefined')doc.dispatchEvent(new CustomEvent('ui-locale-changed',{detail:{locale:next}}));
  for(const button of doc?.querySelectorAll?.('[data-ui-locale]')||[])button.setAttribute('aria-pressed',String(button.dataset.uiLocale===next));
}
export const formatNumber=value=>new Intl.NumberFormat(locale==='en'?'en-US':'uk-UA').format(value);
export const formatDate=value=>new Intl.DateTimeFormat(locale==='en'?'en-GB':'uk-UA',{dateStyle:'medium',timeStyle:'short'}).format(new Date(value));
if(globalThis.document?.documentElement){
  bindMarked(document);
  for(const button of document.querySelectorAll('[data-ui-locale]')){button.setAttribute('aria-pressed',String(button.dataset.uiLocale===locale));button.addEventListener('click',()=>setLocale(button.dataset.uiLocale))}
}
