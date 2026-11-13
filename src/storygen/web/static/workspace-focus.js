/** R20-WORKSPACE-S05: spread the editor over the app window (not the browser Fullscreen API). */
import {t,uiAttr} from './i18n.js';

function openPopover(doc){try{return !!doc.querySelector(':popover-open')}catch{return false}}
const shown=node=>!!node&&!node.hidden&&node.getClientRects?.().length>0;

export function installWorkspaceFocus(doc,textEditor){
  const root=doc.querySelector('#workspace'),button=doc.querySelector('#workspace-focus');
  if(!root||!button)return null;
  const icon=button.querySelector('.icon'),material=doc.querySelector('#workspace-material');
  const label=()=>t(root.classList.contains('focus-mode')?'workspace.focus_exit':'workspace.focus_enter');
  uiAttr(button,'aria-label',label);uiAttr(button,'title',label);
  function focusMaterial(){
    // Memory and review tabs hide the text editor: focus the material panel they scroll in instead.
    if(shown(material?.querySelector('.rich-text-surface'))||shown(material?.querySelector('textarea#editor')))textEditor.focus();
    else material?.focus({preventScroll:true});
  }
  function set(on){
    root.classList.toggle('focus-mode',on);
    button.setAttribute('aria-pressed',String(on));
    icon?.classList.toggle('icon-maximize',!on);icon?.classList.toggle('icon-minimize',on);
    uiAttr(button,'aria-label',label);uiAttr(button,'title',label);
    focusMaterial();
  }
  button.addEventListener('click',()=>set(!root.classList.contains('focus-mode')));
  // Capture phase: ProseMirror's base keymap binds Escape to selectParentNode and always prevents it.
  // Dialogs, an open comment popover and Ghost mode keep their own Escape.
  doc.addEventListener('keydown',event=>{
    if(event.key!=='Escape'||!root.classList.contains('focus-mode'))return;
    if(doc.querySelector('dialog[open]')||openPopover(doc)||event.target?.closest?.('#ghost-mode'))return;
    event.preventDefault();event.stopPropagation();set(false);
  },true);
  return {set,active:()=>root.classList.contains('focus-mode')};
}
