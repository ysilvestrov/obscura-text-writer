/** R20-WORKSPACE-S03: a pinned link to the run controls that now sit under the material. */
const WAITING=new Set(['needs_review','alternative','paused','failed','interrupted']);

/** Shown for run states that wait for the author, or while a review card waits under the editor. */
export function runJumpVisible(runState,reviewWaiting){return WAITING.has(runState)||!!reviewWaiting;}

/** Where the link leads: the first usable run action, otherwise the waiting review card, otherwise the run summary. */
export function jumpTarget(doc){
  const row=doc.querySelector('#workspace-status-row'),review=doc.querySelector('#review-attention');
  const button=[...doc.querySelectorAll('#run-actions button')].find(b=>!b.disabled&&!b.hidden&&!b.closest?.('[hidden]'));
  if(button)return {scroll:row,focus:button};
  if(review&&!review.hidden)return {scroll:review,focus:review};
  return {scroll:row,focus:row?.querySelector?.('.run-summary')||null};
}

export function installRunJump(doc,runState,Observer=globalThis.MutationObserver){
  const link=doc.querySelector('#run-jump'),review=doc.querySelector('#review-attention');
  const update=()=>{if(link)link.hidden=!runJumpVisible(runState(),review&&!review.hidden);};
  // review-session.js reveals the card asynchronously without a workspace render.
  if(review&&Observer)new Observer(update).observe(review,{attributes:true,attributeFilter:['hidden']});
  link?.addEventListener('click',event=>{
    event.preventDefault();
    const target=jumpTarget(doc);
    target.scroll?.scrollIntoView({block:'start',behavior:'smooth'});
    target.focus?.focus({preventScroll:true});
  });
  return update;
}
