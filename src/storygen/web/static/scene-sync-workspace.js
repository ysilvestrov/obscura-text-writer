// MCP-BRIDGE (#105): on return to the page, notice scene changes made elsewhere (a chat client, another window).
// A clean buffer is replaced by the story-refreshed handler in versions.js; otherwise the author gets a notice.
import {t,uiText} from './i18n.js';
import {api,notice} from './api.js';
import {state,refresh,clearSceneBuffer} from './editor.js';
import {invokeWorkspaceCommand} from './workspace-commands.js';
import {revisionsChanged,externalNotice,cleanBuffer,createSceneSync,ghostOpen} from './scene-sync.js';

const box=document.querySelector('#external-change'),text=box?.querySelector('span'),button=box?.querySelector('button');
const saveButton=document.querySelector('#save-text');
const MATERIALS=['plan','brief','draft','review','prose','memory'];
let lastKind=null;

async function check(){
  if(!state.view||!state.storyId)return;
  const {scenes}=await api(`/api/stories/${encodeURIComponent(state.storyId)}/scene-revisions`,{fresh:true});
  const result=revisionsChanged(state.view.scenes,scenes,state.scene);
  if(!result.changed)return;
  if(result.currentChanged||result.currentGone)state.externalChange=true;
  if(result.currentGone&&cleanBuffer(state,ghostOpen()))clearSceneBuffer();
  await refresh({fresh:true});
}

const sync=createSceneSync({check,busy:()=>state.saving||(state.refreshing||0)>0});
const trigger=()=>{void sync.trigger()};
const settle=()=>{void sync.settle()};
document.addEventListener('visibilitychange',()=>{if(!document.hidden)trigger()});
globalThis.addEventListener?.('focus',trigger);
document.addEventListener('workspace-sync-settle',settle);
document.addEventListener('editor-state-changed',settle);

function render(){
  if(!box)return;
  let kind=externalNotice(state);
  // A clean buffer is being reloaded by the story-refreshed handler; announcing the change first would only flash.
  if(kind==='changed'&&cleanBuffer(state,ghostOpen())&&MATERIALS.includes(state.mode))kind=null;
  box.hidden=!kind;box.dataset.kind=kind||'';
  uiText(text,'textContent',()=>kind==='gone'?t('sync.trashed'):kind?t('sync.changed'):'');
  button.hidden=kind!=='changed';
  uiText(button,'textContent',()=>t('sync.open_newer'));
  if(kind==='gone'){saveButton.disabled=true;uiText(saveButton,'title',()=>t('sync.trashed'))}
  else{uiText(saveButton,'title',()=>'');if(lastKind==='gone')saveButton.disabled=state.saving||['history','blueprint','review'].includes(state.mode)}
  lastKind=kind;
}
// Blueprint and history buffers are not materials of their own: the newer version opens in the plan.
button?.addEventListener('click',()=>{invokeWorkspaceCommand('show',MATERIALS.includes(state.mode)?state.mode:'plan').catch(error=>notice(error.message,'error'))});
for(const event of ['editor-state-changed','story-refreshed','scene-selected'])document.addEventListener(event,render);
render();
