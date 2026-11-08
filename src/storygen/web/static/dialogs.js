import {t} from './i18n.js';

let open=false;
function openDialog(message,withInput){
  if(open)return Promise.resolve(withInput?null:false);
  open=true;
  return new Promise(resolve=>{
    const previous=document.activeElement;
    const dialog=document.createElement('dialog');dialog.className='app-dialog';dialog.setAttribute('aria-labelledby','app-dialog-title');dialog.setAttribute('aria-describedby','app-dialog-message');
    const title=document.createElement('h2');title.id='app-dialog-title';title.textContent=t(withInput?'dialog.input_title':'dialog.confirm_title');
    const content=document.createElement('p');content.id='app-dialog-message';content.className='app-dialog-message';content.textContent=String(message);
    const input=withInput?document.createElement('input'):null;if(input){input.type='text';input.setAttribute('aria-label',String(message));}
    const actions=document.createElement('div');actions.className='app-dialog-actions';
    const cancel=document.createElement('button');cancel.type='button';cancel.className='secondary';cancel.textContent=t('dialog.cancel');
    const accept=document.createElement('button');accept.type='button';accept.textContent=t('dialog.confirm');actions.append(cancel,accept);
    dialog.append(title,content);if(input)dialog.append(input);dialog.append(actions);document.body.append(dialog);
    let result=withInput?null:false;
    const finish=value=>{result=value;dialog.close()};
    cancel.onclick=()=>finish(withInput?null:false);
    accept.onclick=()=>finish(withInput?input.value:true);
    input?.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();finish(input.value)}});
    dialog.addEventListener('cancel',event=>{event.preventDefault();finish(withInput?null:false)});
    dialog.addEventListener('close',()=>{dialog.remove();open=false;resolve(result);queueMicrotask(()=>{if(previous?.isConnected&&!previous.disabled)previous.focus()})});
    try{dialog.showModal();(input||cancel).focus()}catch(error){dialog.remove();open=false;resolve(withInput?null:false)}
  });
}
export const confirmDialog=message=>openDialog(message,false);
export const promptDialog=message=>openDialog(message,true);
