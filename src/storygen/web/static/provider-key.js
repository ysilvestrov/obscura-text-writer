// SECURITY-002: the key goes to the server and never comes back; this block only shows where a key comes from.
const NAME=/^[A-Z][A-Z0-9_]{2,63}$/;
const CLOUD=new Set(['openrouter','venice']);
export const validKeyName=name=>NAME.test(name);
export const needsKey=provider=>CLOUD.has(provider);
// i18n key of the status line for a state returned by /api/provider-keys/{name}.
export function keyStatusKey(state){
  if(state.source==='env')return state.stored?'keys.status.env_and_store':'keys.status.env';
  if(state.source==='store')return 'keys.status.store';
  return state.store_available?'keys.status.none':'keys.status.unavailable';
}
export function mountProviderKey(host,{nameField,providerField,i18n,request}){
  const {t,uiText,diagnostic}=i18n;
  const block=document.createElement('div'),status=document.createElement('p'),label=document.createElement('label'),caption=document.createElement('span');
  const input=document.createElement('input'),hint=document.createElement('small'),actions=document.createElement('div');
  const save=document.createElement('button'),remove=document.createElement('button');
  block.className='provider-key';status.className='settings-hint provider-key-status';status.setAttribute('role','status');
  // new-password: browsers ignore autocomplete=off on password fields and would offer to save or fill the key.
  input.type='password';input.autocomplete='new-password';input.spellcheck=false;input.className='provider-key-input';
  uiText(caption,'textContent',()=>t('keys.field.label'));uiText(hint,'textContent',()=>t('keys.field.hint'));
  label.append(caption,input,hint);
  save.type='button';remove.type='button';remove.className='secondary';actions.className='actions';
  uiText(save,'textContent',()=>t('keys.save'));uiText(remove,'textContent',()=>t('keys.delete'));
  actions.append(save,remove);block.append(status,label,actions);host.append(block);
  // Typing a key or pressing these buttons is not a change of the settings form around it.
  for(const type of ['input','change'])block.addEventListener(type,event=>event.stopPropagation());
  let current=0,state=null,pending=false;
  const url=()=>'/api/provider-keys/'+encodeURIComponent(nameField.value);
  const say=render=>uiText(status,'textContent',render);
  function draw(){
    // While a write is on its way nothing may start another one: the older request could land last.
    const usable=state!==null&&!pending;
    save.disabled=!usable||!state.store_available||!input.value.trim();
    remove.disabled=!usable||!state.stored||!state.store_available;
    input.disabled=!usable||!state.store_available;
  }
  function show(next,note){
    state=next;
    say(()=>(note?t(note)+' ':'')+t(keyStatusKey(next)));
    draw();
  }
  async function refresh(){
    const ticket=++current;
    block.hidden=!needsKey(providerField.value);
    if(block.hidden)return;
    state=null;draw();
    if(!validKeyName(nameField.value)){say(()=>t('keys.name_hint'));return}
    try{
      const next=await request(url());
      if(ticket===current)show(next);
    }catch(error){if(ticket===current)say(()=>diagnostic(error.message))}
  }
  async function send(method,body,note){
    if(pending)return;
    const ticket=++current;pending=true;draw();
    try{
      const next=await request(url(),{method,...(body?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});
      if(ticket===current)show(next,note);
    }catch(error){if(ticket===current){say(()=>diagnostic(error.message));draw()}}
    finally{pending=false;input.value='';draw()}
  }
  input.addEventListener('input',draw);
  // Enter in the key field saves the key; it must never submit the settings form around the block.
  input.addEventListener('keydown',event=>{if(event.key!=='Enter')return;event.preventDefault();event.stopPropagation();if(!save.disabled)save.click()});
  save.onclick=()=>send('PUT',{value:input.value},'keys.saved');
  remove.onclick=()=>send('DELETE',null,'keys.deleted');
  let timer=null;
  nameField.addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(refresh,300)});
  providerField.addEventListener('change',()=>setTimeout(refresh,0));
  return {block,refresh};
}
