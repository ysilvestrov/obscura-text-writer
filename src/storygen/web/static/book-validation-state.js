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

// The full book run the scene panel resumes. `current` (the run line) may be the short list entry of the same run
// (no checkpoint), so the cached full run is kept while the run is the same and in the same state. A cached run stays
// only while the story's list still holds it in that state as its latest book validation (not resumed or replaced elsewhere).
export function panelBookRun(cached,runs,current){
  if(cached&&current&&current.id===cached.id&&current.state===cached.state)return cached;
  if(isBookRun(current))return current;
  if(isBookRun(cached)&&(runs||[]).some(run=>run.id===cached.id&&run.state===cached.state)&&latestBookRun(runs,null)?.id===cached.id)return cached;
  return null;
}

// While a different run is active (the run line follows it), revealing the book run would close that run's stream:
// the menu item is then disabled and `run-reveal` is a no-op (Final(core) ruling 2). The same run reveals itself.
export function revealBlocked(current,run){
  return !!current&&current.id!==run?.id&&BOOK_ACTIVE.has(current.state);
}

// The label key and state of the item: a running or stopped validation shows its run (`show`, never a new run) unless
// a different run is active; otherwise unknown before the view loads, «Книга валідна» and inactive at 0.
export function bookMenuState(count,bookRun=null,current=null){
  const key=BOOK_ACTIVE.has(bookRun?.state)?'book_validation.menu_running':BOOK_STOPPED.has(bookRun?.state)?'book_validation.menu_stopped':null;
  if(key)return revealBlocked(current,bookRun)?{key,params:{},disabled:true,show:true,reason:'book_validation.other_run_active'}:{key,params:{},disabled:false,show:true};
  if(!Number.isInteger(count))return {key:'book_validation.menu',params:{},disabled:true};
  if(count===0)return {key:'book_validation.valid',params:{},disabled:true};
  return {key:'book_validation.menu_count',params:{p0:count},disabled:false};
}
