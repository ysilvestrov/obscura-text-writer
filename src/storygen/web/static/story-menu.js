import {uiText} from './i18n.js';
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
  const budget=document.querySelector('#story-menu-budget span');
  document.addEventListener('workspace-budget-updated',event=>uiText(budget,'textContent',()=>menuBudgetText(event.detail)));
}
