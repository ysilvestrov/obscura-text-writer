import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
export class APIError extends Error{
  constructor(message,status,data){super(message);this.name='APIError';this.status=status;this.data=data;}
}
const inflight=new Map();
let generation=0;
async function load(url,options){let response;try{response=await fetch(url,options)}catch(error){return{failed:error}}let data,bad=false;try{data=await response.json()}catch{bad=true}return{ok:response.ok,status:response.status,data,bad}}
export async function api(url,options){
  options=options||{};
  // fresh: відповідь на подію сервера; не приєднується до GET, надісланого раніше, і новіші GET можуть приєднатися лише до нього.
  const fresh=options.fresh===true;
  if('fresh' in options){const {fresh:_,...rest}=options;options=rest}
  if(fresh)generation++;
  const readOnly=(options.method===undefined||String(options.method).toUpperCase()==='GET')&&options.body===undefined;
  const shareable=readOnly&&!options.signal;
  let result;
  if(shareable){const key=generation+' '+url;let pending=inflight.get(key);if(!pending){pending=load(url,options).finally(()=>{if(inflight.get(key)===pending)inflight.delete(key)});inflight.set(key,pending)}result=await pending}
  else if(!readOnly){generation++;try{result=await load(url,options)}finally{generation++}}
  else result=await load(url,options);
  if(result.failed){if(!shareable)throw result.failed;const error=new Error(result.failed?.message);error.name=result.failed?.name||'Error';throw error}
  const data=result.bad?{get detail(){return t("m_acea534098cb")}}:shareable?structuredClone(result.data):result.data;
  if(!result.ok){const fileError=Array.isArray(data?.files)?data.files.find(file=>file.status==='failed'&&typeof file.error==='string')?.error:null;throw new APIError(typeof data?.detail==='string'?(data.detail_original??data.detail):fileError||t("m_d135f0690e85"),result.status,data);}
  return data}
export function json(method,body){return{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}}
export function dismissNotice(){const box=document.querySelector('#notice');if(!box)return;clearTimeout(box.timer);box.hidden=true;}
export function notice(text,kind='success'){const box=document.querySelector('#notice');const message=box.querySelector?.('.notice-message');if(message)uiText(message,"textContent",()=>(diagnostic(text)));else uiText(box,"textContent",()=>(diagnostic(text)));box.dataset.kind=kind;box.setAttribute('role',kind==='error'?'alert':'status');box.hidden=false;clearTimeout(box.timer);box.timer=setTimeout(dismissNotice,kind==='error'?12000:7000)}
document.querySelector('#notice-close')?.addEventListener('click',dismissNotice);
document.addEventListener?.('scene-selected',dismissNotice);
document.querySelector('#new-story')?.addEventListener('submit',async event=>{event.preventDefault();try{const form=new FormData(event.target);const story=await api('/api/stories',json('POST',{title:form.get('title'),target_words:Number(form.get('target_words')),language:form.get('language')||'uk',writing_mode:form.get('writing_mode')||'obscura'}));location.href='/stories/'+story.id}catch(error){notice(error.message,'error')}});
