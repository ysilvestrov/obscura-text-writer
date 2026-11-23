import {stoppedAuditScene} from './run-summary.js';
// R-44 book validation, design §12: pure rules of the story menu item; book-validation.js renders them.
const PENDING=new Set(['unchecked','discrepancy','unavailable']);

// The menu counts the scenes the run would visit: those with any link in unchecked, discrepancy or unavailable
// (server: audit_run.book_pending and the preview's `invalid_scenes`), whatever the scene's validity, so a brief-only
// (`incomplete`) scene with an unchecked brief link counts. An item without `links` counts as 0.
export function invalidSceneCount(materialStatus){
  return Object.values(materialStatus||{}).filter(item=>Object.values(item?.links||{}).some(link=>PENDING.has(link?.status))).length;
}

const isBookRun=run=>run?.request?.mode==='audit'&&run.request.audit_scope==='story';
const BOOK_ACTIVE=new Set(['queued','running','pause_requested','cancellation_requested']);
const BOOK_STOPPED=new Set(['paused','needs_review']);

// The latest book validation among the story's runs: the current run replaces its own (fuller) entry in the list,
// and a book validation the list does not hold yet is returned itself.
export function latestBookRun(runs,current){
  const list=(runs||[]).map(run=>current&&run.id===current.id?current:run);
  if(isBookRun(current)&&!list.some(run=>run.id===current.id))list.push(current);
  return list.filter(isBookRun).at(-1)||null;
}

// A stopped book validation keeps «Продовжити» in the run row unless the scene of its stop is missing (the summary then has no link to lead to).
export function bookResumeInRow(run,scenes){
  return !(isBookRun(run)&&run.state==='needs_review'&&stoppedAuditScene(run,scenes));
}

// The label key and state of the item: a running validation disables it, a stopped one shows its run; otherwise unknown before
// the view loads, «Книга валідна» and inactive at 0.
export function bookMenuState(count,bookRun=null){
  if(BOOK_ACTIVE.has(bookRun?.state))return {key:'book_validation.menu_running',params:{},disabled:true};
  if(BOOK_STOPPED.has(bookRun?.state))return {key:'book_validation.menu_stopped',params:{},disabled:false,show:true};
  if(!Number.isInteger(count))return {key:'book_validation.menu',params:{},disabled:true};
  if(count===0)return {key:'book_validation.valid',params:{},disabled:true};
  return {key:'book_validation.menu_count',params:{p0:count},disabled:false};
}
