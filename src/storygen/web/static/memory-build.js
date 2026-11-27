import {t,uiText,diagnostic} from './i18n.js';
import {operationReason} from './run-readiness.js';
import {refreshBook} from './series-status.js';
import {refresh,displaySceneTitle} from './editor.js';
import {sendsText} from './memory-sends.js';
// R-48 «Побудувати пам'ять» (spec §5, §5.1): the story-menu item counts the scenes from the first one without valid memory
// to the end of the book (GET /memory-build). Its dialog reads the rebuild_memory preview of that scene — calls, the upper
// bound on cost, the scenes that will not fit, the cast the build fills — and nothing runs without «Побудувати». The press
// writes the cast (scene-cast/infer, under the story revision read before the preview), then starts the run with the
// preview's plan fingerprint and hands it to the run panel (pause, cancel and resume live there). A 409 for a changed plan
// or cast from either call is a stale preview: the dialog reads it again and asks the author to check it; nothing starts on
// its own. While a run is
// active in the workspace the build waits; the server also refuses a second build while one is queued or running
// (409, shown as is). The item is shown only when every scene the build covers has finished prose (`buildable`, owner
// 25.11.2026); a direct open (?build_memory=1) still shows the refusal. In an edition without long prose a structured or
// series book is read-only: the item and the series offer stay hidden there (the server refuses those writes either way).

// The server's rounded-up total is shown as is; a per-call price is never multiplied out. Unknown → the reason, if any.
export function costText(cost){
  if(cost?.total_usd!=null)return t('memory_build.ui.cost_total',{p0:cost.total_usd});
  return cost?.reason?t('memory_build.ui.cost_unknown_reason',{p0:diagnostic(cost.reason)}):t('memory_build.ui.cost_unknown');
}

// The run states the server's duplicate-build guard blocks on (worker MEMORY_BUILD_ACTIVE; re-review N-0, N-2): a paused
// build does not block. Any such memory build of the story blocks «Побудувати» before infer writes the casts, even when a
// newer run hides it from the run row.
const ACTIVE_RUN=new Set(['queued','running','pause_requested','cancellation_requested']);
const activeBuild=state=>[state.workspaceRun,...(state.workspaceRuns||[])].some(run=>run?.request?.mode==='rebuild_memory'&&ACTIVE_RUN.has(run.state));

export function installMemoryBuild({api,json,notice,document,state}){
  const item=document.querySelector('#story-menu-build-memory'),dialog=document.querySelector('#memory-build-dialog');
  if(!item||!dialog||!state.storyId)return;
  const part=name=>dialog.querySelector('#memory-build-'+name);
  const summary=part('summary'),sends=part('sends'),cost=part('cost'),unfit=part('unfit'),cast=part('cast'),series=part('series'),seriesButton=part('refresh'),
    reasonNode=part('reason'),seriesWarning=part('series-warning'),status=part('status'),submit=part('submit'),cancel=part('cancel');
  const storyPath=()=>`/api/stories/${encodeURIComponent(state.storyId)}`;
  let target={scene_id:null,count:0,buildable:false},plan=null,failure='',loading=false,busy=false,epoch=0,keepFocus=false,pending=null;
  // LONG-PROSE-TRIAL-S07: the book answers for itself (its trial included), not the build.
  const longProse=()=>state.view?.long_prose!==false;
  const readOnly=()=>!longProse()&&(state.view?.book_structure?.kind==='structured'||!!state.view?.story?.series_id);
  // The previous memory awaits the author's confirmation in the scene: this dialog cannot give it, so the build is blocked
  // with the reason and a link to the scene (review M-1), whether the preview says so with `can_confirm` or as its reason.
  const needsApproval=preview=>!!preview&&(preview.can_confirm||!!preview.reason&&diagnostic(preview.reason)===t('memory.needs_approval'));
  // Why «Побудувати» is unavailable: a failed preview, an active run, then the preview's own readiness (dirty buffer included).
  const blocked=()=>(failure==='memory_build.ui.nothing'?t(failure):failure)||(!plan?'':ACTIVE_RUN.has(state.workspaceRun?.state)||activeBuild(state)?t('memory_build.ui.run_active'):
    plan.preview.can_confirm?(plan.preview.reason||t('memory.needs_approval')):operationReason(state,plan.preview));

  function renderMenu(){
    item.hidden=!target.count||!target.buildable||readOnly();
    uiText(item,'textContent',()=>t('manuscript_import.ui.build_memory',{p0:target.count}));
  }
  // The count is asked on every workspace refresh; one request at a time, and one more if a refresh came meanwhile.
  let counting=null,again=false;
  function count(){
    if(counting){again=true;return counting}
    counting=(async()=>{
      try{do{again=false;target=await api(`${storyPath()}/memory-build`)}while(again)}
      catch{/* the item keeps its last count; the dialog reads the target again */}
      finally{counting=null}
      renderMenu();
    })();
    return counting;
  }

  const element=(tag,className='')=>{const node=document.createElement(tag);if(className)node.className=className;return node};
  const sceneOf=id=>state.view?.scenes?.find(scene=>scene.id===id);
  function setStatus(render){if(render)uiText(status,'textContent',render);else status.textContent=''}
  function sync(){
    const reason=blocked();
    submit.disabled=busy||loading||!plan||!!reason;
    seriesButton.disabled=busy||loading;
    item.disabled=busy;  // a build still in flight (even with the dialog closed) must settle before another can start
    dialog.setAttribute('aria-busy',String(busy||loading));
    reasonNode.hidden=!reason;
    if(!reason){reasonNode.textContent='';return}
    const text=element('span');
    uiText(text,'textContent',()=>diagnostic(blocked()));
    reasonNode.replaceChildren(text);
    if(plan&&needsApproval(plan.preview)&&diagnostic(reason)===t('memory.needs_approval')){
      const link=element('a'),scene=sceneOf(plan.scene_id);
      link.id='memory-build-approval';
      link.href=`/stories/${encodeURIComponent(state.storyId)}?scene=${encodeURIComponent(plan.scene_id)}&material=memory`;
      uiText(link,'textContent',()=>t('memory_build.ui.open_scene',{p0:scene?scene.position+1:'—'}));
      reasonNode.append(document.createTextNode(' '),link);
    }
  }
  function clear(){
    summary.textContent='';sends.textContent='';sends.hidden=true;cost.textContent='';cost.hidden=true;cast.replaceChildren();
    unfit.hidden=true;unfit.querySelector('ul').replaceChildren();series.hidden=true;seriesWarning.hidden=true;
  }
  function renderCast(entry){
    cast.replaceChildren();
    if(!entry)return;
    if(entry.cards){
      const line=element('p');
      uiText(line,'textContent',()=>t('memory_build.ui.cast',{p0:entry.cards,p1:entry.protagonist||t('memory_build.ui.no_hero'),p2:entry.scenes_to_fill}));
      cast.append(line);
    }
    if(!entry.warning)return;
    // §5.1: without cards the memory has no hero state; the run is not blocked, the author is led to the cards.
    const warning=element('p','warning'),text=element('span'),characters=element('a'),importer=element('button','link-button');
    uiText(text,'textContent',()=>diagnostic(entry.warning)+' ');
    characters.href=`/stories/${encodeURIComponent(state.storyId)}/characters`;
    uiText(characters,'textContent',()=>t('characters.nav'));
    importer.type='button';
    uiText(importer,'textContent',()=>t('memory_build.ui.import_characters'));
    importer.onclick=()=>{
      keepFocus=true;dialog.close();
      const details=document.querySelector('.importer');if(details){details.dataset.userOpened='true';details.open=true}
      document.querySelector('#import-sources input[name="characters"]')?.focus();
    };
    // R-51 (CHARACTER-EXTRACT §6): the same warning leads to the character search in the prose.
    const extract=element('a');extract.id='memory-build-extract';
    extract.href=`/stories/${encodeURIComponent(state.storyId)}/characters?extract=1`;
    uiText(extract,'textContent',()=>t('memory_build.ui.find_characters'));
    warning.append(text,characters,document.createTextNode(' · '),importer,document.createTextNode(' · '),extract);
    cast.append(warning);
  }
  function render(){
    clear();
    if(!plan)return;
    const preview=plan.preview,scene=sceneOf(plan.scene_id),memory=preview.roles?.memory;
    const number=scene?scene.position+1:'—';
    uiText(summary,'textContent',()=>t('memory_build.ui.summary',{p0:plan.count,p1:number,p2:preview.calls})+
      (memory?' · '+t('memory_build.ui.model',{p0:`${memory.provider} / ${memory.model}`}):''));
    // R-49 (MANUSCRIPT-IMPORT-S16): what the memory model receives; for a model on this computer, only where Obscura sends it.
    if(preview.sends&&memory){sends.hidden=false;uiText(sends,'textContent',()=>sendsText(preview.sends,`${memory.provider} / ${memory.model}`))}
    if(preview.cost){cost.hidden=false;uiText(cost,'textContent',()=>costText(preview.cost))}
    const list=unfit.querySelector('ul');
    for(const id of preview.unfit_scenes||[]){
      const row=element('li'),link=element('a'),known=sceneOf(id);
      link.href=`/stories/${encodeURIComponent(state.storyId)}?scene=${encodeURIComponent(id)}&material=prose`;
      link.textContent=known?`${known.position+1}. ${displaySceneTitle(known.title)}`:id;  // author text, never localized
      row.append(link);list.append(row);
    }
    unfit.hidden=!list.children.length;
    renderCast(preview.cast);
    // §5: a series book without a start snapshot first offers the refresh from the previous book; the build stays secondary.
    // An offer, never a gate (a failed refresh must not block the author): the build then warns what its memory lacks.
    const offer=!!preview.series_refresh&&longProse();  // no series in an edition without long prose
    series.hidden=seriesWarning.hidden=!offer;
    submit.classList.toggle('secondary',offer);
  }

  // The revision is read before the preview, so a change in between is refused by the cast write (409), never applied.
  async function load(message=null){
    const ask=++epoch;
    plan=null;failure='';loading=true;clear();
    setStatus(message||(()=>t('memory_build.ui.loading')));sync();
    try{
      target=await api(`${storyPath()}/memory-build`);renderMenu();
      if(ask!==epoch)return;
      if(!target.scene_id){failure='memory_build.ui.nothing';return}
      const revision=(await api(storyPath())).story.revision;
      const preview=(await api(`${storyPath()}/readiness?scene_id=${encodeURIComponent(target.scene_id)}&operation=rebuild_memory`)).operations.rebuild_memory;
      if(ask!==epoch)return;
      plan={scene_id:target.scene_id,count:target.count,revision,preview};
      render();
    }catch(error){if(ask===epoch)failure=error.message}
    finally{if(ask===epoch){loading=false;if(!message)setStatus(null);sync()}}
  }
  async function refreshWorkspace(){try{await refresh()}catch(error){notice(error.message,'error')}}

  async function build(){
    if(busy||loading||!plan)return;
    const current=plan;
    if(blocked()){sync();return}
    busy=true;setStatus(null);sync();
    // Closing the dialog (Cancel, Escape, the character import) aborts the sequence before the run request; `busy` stays set
    // until every pending request has settled, so neither a reopened dialog nor the menu can start a second build meanwhile.
    const build={aborted:false};pending=build;
    let inferred=false;
    try{
      // The cast write bumps the story revision: a retry after a refused run must not be refused as a stale preview.
      const written=await api(`${storyPath()}/scene-cast/infer`,json('POST',{expected_revision:current.revision}));
      inferred=true;
      if(Number.isInteger(written?.story?.revision))current.revision=written.story.revision;
      if(build.aborted){await refreshWorkspace();notice(t('memory_build.ui.cancelled'));return}
      const request={story_id:state.storyId,scene_id:current.scene_id,mode:'rebuild_memory',stage:null,
        pause_after:document.querySelector('#pause-each')?.checked?['brief','draft','edit','memory']:[],
        memory_plan_fingerprint:current.preview.plan_fingerprint,budget_limit_usd:document.querySelector('#run-budget')?.value||null};
      const run=await api('/api/runs',json('POST',{request_id:crypto.randomUUID(),request}));
      // A run requested before the close exists: it goes to the run panel, where it can be cancelled. `busy` stays set until
      // the workspace refresh settles (finally), so the menu item is not re-armed in between.
      pending=null;
      if(dialog.open)dialog.close();
      document.dispatchEvent(new CustomEvent('run-reveal',{detail:run}));
      await refreshWorkspace();
    }catch(error){
      pending=null;
      if(build.aborted){if(inferred)await refreshWorkspace();if(error.status!==409)notice(error.message,'error');return}
      const stale=[t('memory_build.server.plan_changed'),t('memory_build.server.cast_conflict')].includes(diagnostic(error.message));
      if(error.status===409&&!stale){
        // Another build is already queued or running (or another refusal): said as is; the preview is kept.
        if(inferred)await refreshWorkspace();
        setStatus(()=>diagnostic(error.message));sync();
        return;
      }
      if(error.status===409){
        // A stale preview (the plan or the story changed): read it again; the author decides after checking it.
        await refreshWorkspace();
        if(dialog.open)await load(()=>t('memory_build.ui.stale'));
        return;
      }
      // Scene casts may already be written: the workspace shows the new scene revisions.
      if(inferred)await refreshWorkspace();
      setStatus(()=>diagnostic(error.message));sync();
    }finally{
      if(pending===build)pending=null;
      busy=false;sync();
    }
  }

  // The dialog may be closed while the refresh runs: `busy` and the menu item are restored in finally either way.
  async function refreshSeries(){
    if(busy||loading)return;
    busy=true;sync();
    try{
      if(!await refreshBook(state.storyId))return;
      await refreshWorkspace();
      if(dialog.open)await load();
    }finally{busy=false;sync()}
  }

  function open(){
    if(dialog.open||busy)return;
    setStatus(null);dialog.showModal();item.setAttribute('aria-expanded','true');
    void load();
  }
  item.addEventListener('click',open);
  submit.onclick=()=>void build();
  seriesButton.onclick=()=>void refreshSeries().catch(error=>notice(error.message,'error'));
  cancel.onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>{
    // `busy` is not reset here: the build or the series refresh still in flight resets it when its requests settle.
    if(pending)pending.aborted=true;
    epoch++;plan=null;loading=false;clear();sync();item.setAttribute('aria-expanded','false');
    // The character import keeps the focus on its file field; every other exit returns it to the menu button.
    const toggle=document.querySelector('#story-menu-toggle');
    if(keepFocus)keepFocus=false;else if(toggle&&!document.querySelector('dialog[open]'))toggle.focus();
  });

  // ?build_memory=1 (the manuscript import summary) opens the dialog once the workspace has loaded; the parameter is removed
  // at once, so a reload or a later address rewrite does not open it again.
  const location=globalThis.location,history=globalThis.history;
  let openOnLoad=false;
  try{
    const url=new URL(location.href);
    if(url.searchParams.has('build_memory')){openOnLoad=true;url.searchParams.delete('build_memory');history.replaceState(history.state,'',url.href)}
  }catch{/* a restricted browser keeps the address; the dialog still opens */}
  function loaded(){
    void count();
    if(openOnLoad){openOnLoad=false;open()}
  }
  document.addEventListener('story-refreshed',loaded);
  for(const name of ['workspace-run-state','workspace-run-pending'])document.addEventListener(name,()=>{if(dialog.open)sync()});
  if(state.view)loaded();
  renderMenu();
}
