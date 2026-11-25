import {t,uiText,diagnostic} from './i18n.js';
import {operationReason} from './run-readiness.js';
import {refreshBook} from './series-status.js';
import {refresh,displaySceneTitle} from './editor.js';
// R-48 «Побудувати пам'ять» (spec §5, §5.1): the story-menu item counts the scenes from the first one without valid memory
// to the end of the book (GET /memory-build). Its dialog reads the rebuild_memory preview of that scene — calls, the upper
// bound on cost, the scenes that will not fit, the cast the build fills — and nothing runs without «Побудувати». The press
// writes the cast (scene-cast/infer, under the story revision read before the preview), then starts the run with the
// preview's plan fingerprint and hands it to the run panel (pause, cancel and resume live there). A 409 from either call is
// a stale preview: the dialog reads it again and asks the author to check it; nothing starts on its own. While a run is
// active in the workspace the build waits (a second build would be queued and paid twice).

// The server's rounded-up total is shown as is; a per-call price is never multiplied out. Unknown → the reason, if any.
export function costText(cost){
  if(cost?.total_usd!=null)return t('memory_build.ui.cost_total',{p0:cost.total_usd});
  return cost?.reason?t('memory_build.ui.cost_unknown_reason',{p0:diagnostic(cost.reason)}):t('memory_build.ui.cost_unknown');
}

const ACTIVE_RUN=new Set(['queued','running','pause_requested','cancellation_requested']);

export function installMemoryBuild({api,json,notice,document,state}){
  const item=document.querySelector('#story-menu-build-memory'),dialog=document.querySelector('#memory-build-dialog');
  if(!item||!dialog||!state.storyId)return;
  const part=name=>dialog.querySelector('#memory-build-'+name);
  const summary=part('summary'),cost=part('cost'),unfit=part('unfit'),cast=part('cast'),series=part('series'),seriesButton=part('refresh'),
    reasonNode=part('reason'),seriesWarning=part('series-warning'),status=part('status'),submit=part('submit'),cancel=part('cancel');
  const storyPath=()=>`/api/stories/${encodeURIComponent(state.storyId)}`;
  let target={scene_id:null,count:0},plan=null,failure='',loading=false,busy=false,epoch=0,keepFocus=false;
  // Why «Побудувати» is unavailable: a failed preview, an active run, then the preview's own readiness (dirty buffer included).
  const blocked=()=>(failure==='memory_build.ui.nothing'?t(failure):failure)||(!plan?'':ACTIVE_RUN.has(state.workspaceRun?.state)?t('memory_build.ui.run_active'):operationReason(state,plan.preview));

  function renderMenu(){
    item.hidden=!target.count;
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
    dialog.setAttribute('aria-busy',String(busy||loading));
    reasonNode.hidden=!reason;
    if(reason)uiText(reasonNode,'textContent',()=>diagnostic(blocked()));else reasonNode.textContent='';
  }
  function clear(){
    summary.textContent='';cost.textContent='';cost.hidden=true;cast.replaceChildren();
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
    warning.append(text,characters,document.createTextNode(' · '),importer);
    cast.append(warning);
  }
  function render(){
    clear();
    if(!plan)return;
    const preview=plan.preview,scene=sceneOf(plan.scene_id),memory=preview.roles?.memory;
    const number=scene?scene.position+1:'—';
    uiText(summary,'textContent',()=>t('memory_build.ui.summary',{p0:plan.count,p1:number,p2:preview.calls})+
      (memory?' · '+t('memory_build.ui.model',{p0:`${memory.provider} / ${memory.model}`}):''));
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
    series.hidden=seriesWarning.hidden=!preview.series_refresh;
    submit.classList.toggle('secondary',!!preview.series_refresh);
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
    let inferred=false;
    try{
      // The cast write bumps the story revision: a retry after a refused run must not be refused as a stale preview.
      const written=await api(`${storyPath()}/scene-cast/infer`,json('POST',{expected_revision:current.revision}));
      inferred=true;
      if(Number.isInteger(written?.story?.revision))current.revision=written.story.revision;
      const request={story_id:state.storyId,scene_id:current.scene_id,mode:'rebuild_memory',stage:null,
        pause_after:document.querySelector('#pause-each')?.checked?['brief','draft','edit','memory']:[],
        memory_plan_fingerprint:current.preview.plan_fingerprint,budget_limit_usd:document.querySelector('#run-budget')?.value||null};
      const run=await api('/api/runs',json('POST',{request_id:crypto.randomUUID(),request}));
      busy=false;
      dialog.close();
      document.dispatchEvent(new CustomEvent('run-reveal',{detail:run}));
      await refreshWorkspace();
    }catch(error){
      busy=false;
      if(error.status===409){
        // A stale preview (the plan or the story changed): read it again; the author decides after checking it.
        await refreshWorkspace();
        if(dialog.open)await load(()=>t('memory_build.ui.stale'));
        return;
      }
      // Scene casts may already be written: the workspace shows the new scene revisions.
      if(inferred)await refreshWorkspace();
      setStatus(()=>diagnostic(error.message));sync();
    }
  }

  async function refreshSeries(){
    if(busy||loading)return;
    busy=true;sync();
    let changed=false;
    try{changed=await refreshBook(state.storyId)}finally{busy=false}
    if(!changed){sync();return}
    await refreshWorkspace();
    if(dialog.open)await load();
  }

  function open(){
    if(dialog.open)return;
    setStatus(null);dialog.showModal();item.setAttribute('aria-expanded','true');
    void load();
  }
  item.addEventListener('click',open);
  submit.onclick=()=>void build();
  seriesButton.onclick=()=>void refreshSeries().catch(error=>notice(error.message,'error'));
  cancel.onclick=()=>dialog.close();
  // While the cast is written or the run starts the dialog stays open: its answer decides what the author sees next.
  dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault()});
  dialog.addEventListener('close',()=>{
    epoch++;plan=null;loading=false;busy=false;clear();item.setAttribute('aria-expanded','false');
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
