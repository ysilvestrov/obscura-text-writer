/** R20-WORKSPACE-S03: a pinned link to the run controls that now sit under the material. */
const WAITING=new Set(['needs_review','alternative','paused','failed','interrupted']);

/** Shown for run states that wait for the author. */
export function runJumpVisible(runState){return WAITING.has(runState);}

/** Where the link leads: the first usable run action, otherwise the run summary. */
export function jumpTarget(doc){
  const row=doc.querySelector('#workspace-status-row');
  const button=[...doc.querySelectorAll('#run-actions button')].find(b=>!b.disabled&&!b.hidden&&!b.closest?.('[hidden]'));
  if(button)return {scroll:row,focus:button};
  return {scroll:row,focus:row?.querySelector?.('.run-summary')||null};
}

export function installRunJump(doc,runState){
  const link=doc.querySelector('#run-jump');
  const update=()=>{if(link)link.hidden=!runJumpVisible(runState());};
  link?.addEventListener('click',event=>{
    event.preventDefault();
    const target=jumpTarget(doc);
    target.scroll?.scrollIntoView({block:'start',behavior:'smooth'});
    target.focus?.focus({preventScroll:true});
  });
  return update;
}
