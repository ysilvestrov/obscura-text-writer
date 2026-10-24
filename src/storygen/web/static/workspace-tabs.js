export function revealStageTab(button){
  const parent=button.parentElement;if(!parent)return;
  const item=button.getBoundingClientRect(),box=parent.getBoundingClientRect();
  if(item.left<box.left)parent.scrollLeft-=box.left-item.left;
  else if(item.right>box.right)parent.scrollLeft+=item.right-box.right;
}
export function activateStageTab(button,active){
  const was=button.getAttribute?.('aria-selected')==='true';
  button.setAttribute('aria-selected',String(active));
  button.setAttribute('tabindex',active?'0':'-1');
  button.setAttribute('aria-controls','workspace-material');
  if(active&&!was)revealStageTab(button);
}
export function setStageTabStops(buttons,preferredMode){
  const entry=buttons.find(button=>button.dataset.mode===preferredMode)||buttons[0];
  for(const button of buttons)button.setAttribute('tabindex',button===entry?'0':'-1');
}
