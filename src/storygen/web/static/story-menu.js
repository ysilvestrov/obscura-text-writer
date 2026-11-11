import {t,uiText} from './i18n.js';
import {state} from './editor.js';
import {menuBudgetText} from './budget-format.js';
// #89 WORKSPACE-TOOLS: story actions behind a disclosure menu (button + list; Escape returns focus).
const toggle=document.querySelector('#story-menu-toggle'),menu=document.querySelector('#story-menu');
if(toggle&&menu){
  const setOpen=open=>{menu.hidden=!open;toggle.setAttribute('aria-expanded',String(open))};
  toggle.addEventListener('click',()=>setOpen(menu.hidden));
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!menu.hidden){setOpen(false);toggle.focus()}});
  document.addEventListener('click',event=>{if(!menu.hidden&&!menu.contains(event.target)&&!toggle.contains(event.target))setOpen(false)});
  menu.addEventListener('click',event=>{if(event.target.closest('a,button'))setOpen(false)});
  document.querySelector('#story-menu-rename')?.addEventListener('click',()=>document.querySelector('#rename-story')?.click());
  // Materials waiting for review: the same count the revision page shows (scenes whose brief or prose awaits a decision).
  const count=document.querySelector('#story-menu-revision-count'),dot=toggle.querySelector('.menu-dot');
  const pending=()=>Object.values(state.view?.impact_status||{}).filter(s=>['pending','changes_required'].includes(s.prose)||['pending','changes_required'].includes(s.brief)).length;
  function drawPending(){const n=pending();count.hidden=dot.hidden=!n;uiText(count,'textContent',()=>n?String(n):'');uiText(count,'title',()=>t('workspace.revision_pending',{p0:n}))}
  document.addEventListener('story-refreshed',drawPending);drawPending();
  const budget=document.querySelector('#story-menu-budget span');
  document.addEventListener('workspace-budget-updated',event=>uiText(budget,'textContent',()=>menuBudgetText(event.detail)));
}
