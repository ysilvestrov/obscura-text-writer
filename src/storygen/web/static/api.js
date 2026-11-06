import {t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
export class APIError extends Error{
  constructor(message,status,data){super(message);this.name='APIError';this.status=status;this.data=data;}
}
export async function api(url,options={}){const response=await fetch(url,options);let data;try{data=await response.json()}catch{data={get detail(){return t("m_acea534098cb")}}}if(!response.ok)throw new APIError(typeof data?.detail==='string'?(data.detail_original??data.detail):t("m_d135f0690e85"),response.status,data);return data}
export function json(method,body){return{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}}
export function dismissNotice(){const box=document.querySelector('#notice');if(!box)return;clearTimeout(box.timer);box.hidden=true;}
export function notice(text,kind='success'){const box=document.querySelector('#notice');const message=box.querySelector?.('.notice-message');if(message)uiText(message,"textContent",()=>(diagnostic(text)));else uiText(box,"textContent",()=>(diagnostic(text)));box.dataset.kind=kind;box.setAttribute('role',kind==='error'?'alert':'status');box.hidden=false;clearTimeout(box.timer);box.timer=setTimeout(dismissNotice,kind==='error'?12000:7000)}
document.querySelector('#notice-close')?.addEventListener('click',dismissNotice);
document.addEventListener?.('scene-selected',dismissNotice);
document.querySelector('#new-story')?.addEventListener('submit',async event=>{event.preventDefault();try{const form=new FormData(event.target);const story=await api('/api/stories',json('POST',{title:form.get('title'),target_words:Number(form.get('target_words'))}));location.href='/stories/'+story.id}catch(error){notice(error.message,'error')}});
