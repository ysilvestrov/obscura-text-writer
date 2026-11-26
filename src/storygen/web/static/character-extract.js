import {t,uiText,uiAttr,diagnostic,getLocale} from './i18n.js';
// CHARACTER-EXTRACT (R-51, spec §6): the characters page searches the book's prose for characters. The dialog reads the
// read-only plan (scenes, groups, calls bound, upper bound on cost, skipped scenes) and nothing runs without «Запустити»;
// the run is started with the plan fingerprint of the preview shown, and a 409 for a changed plan reads the preview again.
// The run row follows the book's latest character search (pause, resume and stop are the run's own actions). A finished
// search leaves a proposal: every item has a checkbox, the memory that would go stale is asked from the server with a dry
// run, and only «Прийняти вибране» writes. The server decides every skip; the page shows its reasons as given.

const ACTIVE=new Set(['queued','running','pause_requested','cancellation_requested']);
const RESUMABLE=new Set(['paused','failed','interrupted']);
const POLL_MS=2000;

// The server's rounded-up total is shown as is (as the memory build); a per-call price is never multiplied out.
export function costText(cost){
  if(cost?.total_usd!=null)return t('character_extract.ui.cost_total',{p0:cost.total_usd});
  return cost?.reason?t('character_extract.ui.cost_unknown_reason',{p0:diagnostic(cost.reason)}):t('character_extract.ui.cost_unknown');
}

// The body of the accept request from the selection; names are sent in the proposal's order.
export function acceptBody(proposal,selection,runId,dryRun){
  const cards=proposal.cards.filter(card=>selection.cards.has(card.key)).map(card=>({key:card.key,
    names:card.other_names.map(item=>item.name).filter(name=>selection.names.has(`n:${card.key}:${name}`))}));
  const name_updates=proposal.name_updates.map(update=>({card_id:update.card_id,
    names:update.names.map(item=>item.name).filter(name=>selection.names.has(`u:${update.card_id}:${name}`))})).filter(update=>update.names.length);
  const casts=proposal.casts.map(cast=>cast.scene_id).filter(id=>selection.casts.has(id));
  return {run_id:runId,fingerprint:proposal.fingerprint,cards,name_updates,protagonist:!!proposal.protagonist&&selection.protagonist,casts,dry_run:dryRun};
}

// Everything is chosen except the names the server marks as not suggested (descriptions written in lower case).
export function defaultSelection(proposal){
  const names=new Set();
  for(const card of proposal.cards)for(const item of card.other_names)if(item.suggested)names.add(`n:${card.key}:${item.name}`);
  for(const update of proposal.name_updates)for(const item of update.names)if(item.suggested)names.add(`u:${update.card_id}:${item.name}`);
  return {cards:new Set(proposal.cards.map(card=>card.key)),names,protagonist:!!proposal.protagonist,casts:new Set(proposal.casts.map(cast=>cast.scene_id))};
}

export function installCharacterExtract({storyId,api,json,notice,onAccepted,isDirty,document=globalThis.document}){
  const section=document.querySelector('#character-extract'),dialog=document.querySelector('#character-extract-dialog');
  if(!section||!dialog||!storyId)return null;
  const $=id=>document.querySelector('#character-extract-'+id);
  const openButton=$('open'),words=$('words'),summary=$('summary'),cost=$('cost'),skipped=$('skipped'),pending=$('pending'),
    reasonNode=$('reason'),status=$('status'),submit=$('submit'),cancel=$('cancel');
  const runRow=$('run'),runStatus=$('run-status'),pauseButton=$('pause'),resumeButton=$('resume'),stopButton=$('stop');
  const proposalNode=document.querySelector('#character-proposal');
  const storyPath=`/api/stories/${encodeURIComponent(storyId)}`;
  const element=(tag,className='')=>{const node=document.createElement(tag);if(className)node.className=className;return node};
  const say=(node,render)=>{if(render)uiText(node,'textContent',render);else node.textContent=''};
  let scenes=new Map(),cards=new Map(),plan=null,previewEpoch=0,loading=false,starting=false,run=null,pollTimer=null,runEpoch=0;
  let pollFailed=false,proposal=null,selection=null,dryEpoch=0,dryReady=false,accepting=false,acceptedSummary=null;
  const sceneLabel=id=>{const scene=scenes.get(id);return scene?`${scene.position+1}. ${scene.title}`:id};  // author text, never localized
  const runActive=()=>!!run&&ACTIVE.has(run.state);

  async function readContext(){
    const [view,material]=await Promise.all([api(storyPath),api(`${storyPath}/characters`)]);
    scenes=new Map((view.scenes||[]).filter(scene=>!scene.trashed_at).map(scene=>[scene.id,scene]));
    cards=new Map((material.cards||[]).map(card=>[card.id,card.name]));
    // §6: the action is offered once some scene has finished prose; the preview says what it will read and skip.
    section.hidden=![...scenes.values()].some(scene=>scene.heads?.prose);
  }

  // ---- the dialog ----
  function syncDialog(){
    const reason=plan&&!plan.ready?diagnostic(plan.reason||''):runActive()?t('character_extract.ui.run_active'):'';
    submit.disabled=loading||starting||!plan||!!reason;
    reasonNode.hidden=!reason;
    if(reason)uiText(reasonNode,'textContent',()=>plan&&!plan.ready?diagnostic(plan.reason||''):t('character_extract.ui.run_active'));
    dialog.setAttribute('aria-busy',String(loading||starting));
  }
  function clearPreview(){
    say(summary,null);say(cost,null);skipped.hidden=true;skipped.querySelector('ul').replaceChildren();pending.hidden=true;
  }
  function renderPreview(){
    clearPreview();
    if(!plan)return;
    const current=plan;
    uiText(summary,'textContent',()=>t('character_extract.ui.summary',{p0:current.scenes_count,p1:current.groups.length,p2:current.calls_bound}));
    if(current.groups.length)uiText(cost,'textContent',()=>costText(current.cost));
    const list=skipped.querySelector('ul');
    for(const item of current.skipped||[]){
      const row=element('li'),label=element('span'),why=element('span','muted');
      label.textContent=sceneLabel(item.scene_id);
      uiText(why,'textContent',()=>' — '+diagnostic(item.reason));
      row.append(label,why);list.append(row);
    }
    skipped.hidden=!list.children.length;
    pending.hidden=!current.pending_proposal;
  }
  function groupWords(){
    const value=Number(words.value);
    return Number.isInteger(value)&&value>=1000&&value<=20000?value:null;
  }
  async function loadPreview(message=null){
    const ask=++previewEpoch,size=groupWords();
    plan=null;clearPreview();
    if(size===null){loading=false;say(status,()=>t('character_extract.ui.words_range'));syncDialog();return}
    loading=true;say(status,message||(()=>t('character_extract.ui.loading')));syncDialog();
    try{
      const result=await api(`${storyPath}/character-extract/preview`,json('POST',{group_words:size}));
      if(ask!==previewEpoch)return;
      plan={...result,group_words:size};renderPreview();
      if(!message)say(status,null);
    }catch(error){if(ask===previewEpoch)say(status,()=>diagnostic(error.message))}
    finally{if(ask===previewEpoch){loading=false;syncDialog()}}
  }
  let wordsTimer=null;
  words.addEventListener('input',()=>{
    clearTimeout(wordsTimer);previewEpoch++;plan=null;clearPreview();loading=true;syncDialog();
    wordsTimer=setTimeout(()=>void loadPreview(),300);
  });
  async function start(){
    if(!plan||submit.disabled)return;
    const current=plan;starting=true;say(status,null);syncDialog();
    try{
      const created=await api('/api/runs',json('POST',{request_id:crypto.randomUUID(),request:{story_id:storyId,
        mode:'character_extract',group_words:current.group_words,extract_plan_fingerprint:current.plan_fingerprint}}));
      dialog.close();
      proposal=null;acceptedSummary=null;renderProposal();
      track(created);
    }catch(error){
      if(error.status===409&&diagnostic(error.message)===t('character_extract.server.plan_changed')){
        // The plan changed after the preview: read it again; the author starts after checking it.
        starting=false;await loadPreview(()=>t('character_extract.ui.stale'));return;
      }
      say(status,()=>diagnostic(error.message));
    }finally{starting=false;syncDialog()}
  }
  function open(){
    if(dialog.open)return;
    say(status,null);dialog.showModal();openButton.setAttribute('aria-expanded','true');
    void loadPreview();
  }
  openButton.addEventListener('click',open);
  submit.addEventListener('click',()=>void start());
  cancel.addEventListener('click',()=>dialog.close());
  dialog.addEventListener('close',()=>{previewEpoch++;plan=null;loading=false;clearPreview();syncDialog();openButton.setAttribute('aria-expanded','false');openButton.focus()});

  // ---- the run row ----
  function renderRun(){
    clearTimeout(pollTimer);
    if(!run){runRow.hidden=true;return}
    const checkpoint=run.checkpoint||{},reading=checkpoint.phase==='reading',resumable=RESUMABLE.has(run.state)&&checkpoint.phase!=='done';
    const calls=(checkpoint.state||checkpoint.proposal||{}).calls??0,left=Array.isArray(checkpoint.pending)?checkpoint.pending.length:null;
    const current=run;
    let render=null;
    const failed=()=>t('character_extract.ui.failed',{p0:current.error?diagnostic(current.error):t('character_extract.ui.no_reason')});
    if(current.state==='queued')render=()=>t('character_extract.ui.queued');
    else if(current.state==='pause_requested')render=()=>t('character_extract.ui.pausing');
    else if(current.state==='cancellation_requested')render=()=>t('character_extract.ui.cancelling');
    else if(ACTIVE.has(current.state))render=()=>left===null?t('character_extract.ui.starting'):t('character_extract.ui.progress',{p0:left,p1:calls});
    else if(resumable&&current.state!=='paused')render=failed;  // failed or interrupted: the reason, and «Продовжити»
    else if(resumable)render=()=>reading?t('character_extract.ui.paused',{p0:left??0,p1:calls}):t('character_extract.ui.stopped_before_start');
    else if(current.state==='failed')render=failed;
    runRow.hidden=!render;
    say(runStatus,render);
    pauseButton.hidden=!['queued','running'].includes(current.state);
    resumeButton.hidden=!resumable;
    stopButton.hidden=!(ACTIVE.has(current.state)&&current.state!=='cancellation_requested'||resumable);
    syncDialog();
    if(ACTIVE.has(current.state))pollTimer=setTimeout(()=>void poll(),POLL_MS);
  }
  async function poll(){
    if(!run)return;
    const ask=runEpoch,id=run.id;
    try{
      const data=await api(`/api/runs/${encodeURIComponent(id)}`,{fresh:true});
      if(ask!==runEpoch)return;
      const wasActive=runActive();pollFailed=false;
      run=data.run;renderRun();
      if(wasActive&&!runActive())await loadProposal();
    }catch(error){if(ask===runEpoch){if(!pollFailed)notice(error.message,'error');pollFailed=true;pollTimer=setTimeout(()=>void poll(),POLL_MS*3)}}
  }
  function track(created){runEpoch++;run=created;renderRun();void poll()}
  async function findRun(){
    const {runs}=await api(`${storyPath}/runs`);
    const latest=(runs||[]).filter(item=>item.request?.mode==='character_extract').sort((a,b)=>String(b.created_at).localeCompare(String(a.created_at)))[0];
    const ask=++runEpoch;run=null;renderRun();
    if(!latest)return;
    const data=await api(`/api/runs/${encodeURIComponent(latest.id)}`,{fresh:true});
    if(ask!==runEpoch)return;  // a search started meanwhile is the one to follow
    run=data.run;renderRun();
  }
  async function action(path,body){
    if(!run)return;
    for(const button of [pauseButton,resumeButton,stopButton])button.disabled=true;
    try{
      run=await api(`/api/runs/${encodeURIComponent(run.id)}/${path}`,json('POST',body||{}));runEpoch++;renderRun();
      if(runActive())void poll();else await loadProposal();
    }
    catch(error){notice(error.message,'error')}
    finally{for(const button of [pauseButton,resumeButton,stopButton])button.disabled=false}
  }
  pauseButton.addEventListener('click',()=>void action('pause'));
  resumeButton.addEventListener('click',()=>void action('resume',{repeat_interrupted:false}));
  stopButton.addEventListener('click',()=>void action('cancel'));

  // ---- the proposal ----
  const refName=(ref,from=proposal)=>(from?.cards||[]).find(card=>card.key===ref)?.name||cards.get(ref)||ref;
  function checkbox(checked,label,onchange){
    const wrap=element('label','character-proposal-check'),input=element('input');
    input.type='checkbox';input.checked=checked;input.addEventListener('change',()=>{onchange(input.checked);void dryRun()});
    wrap.append(input,label);return wrap;
  }
  function text(value,className=''){const node=element('span',className);node.textContent=value;return node}  // author text
  function group(titleKey,items,setAll){
    const box=element('section','character-proposal-group'),head=element('div','character-proposal-head'),title=element('h3');
    uiText(title,'textContent',()=>t(titleKey,{p0:items.length}));
    const all=element('button','link-button'),none=element('button','link-button');all.type=none.type='button';
    const name=titleKey.split('.').pop();all.id=`character-proposal-all-${name}`;none.id=`character-proposal-none-${name}`;
    uiText(all,'textContent',()=>t('character_extract.ui.select_all'));uiText(none,'textContent',()=>t('character_extract.ui.select_none'));
    uiAttr(all,'aria-label',()=>t('character_extract.ui.select_all_in',{p0:t(titleKey,{p0:items.length})}));
    uiAttr(none,'aria-label',()=>t('character_extract.ui.select_none_in',{p0:t(titleKey,{p0:items.length})}));
    const choose=(on,id)=>{setAll(on);renderProposal();document.getElementById(id)?.focus();void dryRun()};
    all.onclick=()=>choose(true,all.id);none.onclick=()=>choose(false,none.id);
    head.append(title,all,none);box.append(head);
    const list=element('ul');for(const item of items){const row=element('li');row.append(item);list.append(row)}box.append(list);
    return box;
  }
  function namesRow(prefix,owner,names){
    const row=element('div','character-proposal-names');
    for(const item of names){
      const key=`${prefix}:${owner}:${item.name}`;
      row.append(checkbox(selection.names.has(key),text(item.name),on=>{if(on)selection.names.add(key);else selection.names.delete(key)}));
    }
    return row;
  }
  function renderProposal(){
    proposalNode.replaceChildren();
    if(acceptedSummary)proposalNode.append(acceptedSummary);
    if(!proposal){proposalNode.hidden=!acceptedSummary;return}
    proposalNode.hidden=false;
    const heading=element('h3');
    uiText(heading,'textContent',()=>proposal.partial?t('character_extract.ui.proposal_partial'):t('character_extract.ui.proposal'));
    proposalNode.append(heading);
    const empty=!proposal.cards.length&&!proposal.name_updates.length&&!proposal.protagonist&&!proposal.casts.length;
    const unread=proposal.skipped_scenes||[];
    if(unread.length){
      const box=element('div','character-proposal-unread'),label=element('p'),list=element('ul');box.id='character-proposal-unread';
      uiText(label,'textContent',()=>t('character_extract.ui.unread'));
      for(const item of unread){const row=element('li'),why=element('span','muted');row.append(text(sceneLabel(item.scene_id)));uiText(why,'textContent',()=>' — '+diagnostic(item.reason));row.append(why);list.append(row)}
      box.append(label,list);proposalNode.append(box);
    }
    if(empty){const line=element('p');uiText(line,'textContent',()=>t('character_extract.ui.nothing_found'));proposalNode.append(line);return}
    if(proposal.cards.length)proposalNode.append(group('character_extract.ui.new_cards',proposal.cards.map(card=>{
      const body=element('div','character-proposal-card'),title=checkbox(selection.cards.has(card.key),text(card.name,'character-proposal-name'),
        on=>{if(on)selection.cards.add(card.key);else selection.cards.delete(card.key)});
      body.append(title);
      if(card.other_names.length){const label=element('small','muted');uiText(label,'textContent',()=>t('character_extract.ui.other_names'));body.append(label,namesRow('n',card.key,card.other_names))}
      const quotes=element('ul','character-proposal-quotes');
      for(const quote of card.quotes){const row=element('li'),where=element('small','muted');const words=element('span');uiText(words,'textContent',()=>getLocale()==='en'?`“${quote.quote}”`:`«${quote.quote}»`);row.append(words);where.textContent=' — '+sceneLabel(quote.scene_id);row.append(where);quotes.append(row)}
      body.append(quotes);
      return body;
    }),on=>{selection.cards=new Set(on?proposal.cards.map(card=>card.key):[])}));
    if(proposal.name_updates.length)proposalNode.append(group('character_extract.ui.new_names',proposal.name_updates.map(update=>{
      const body=element('div','character-proposal-card');body.append(text(cards.get(update.card_id)||update.card_id,'character-proposal-name'),namesRow('u',update.card_id,update.names));
      return body;
    }),on=>{for(const update of proposal.name_updates)for(const item of update.names){const key=`u:${update.card_id}:${item.name}`;if(on)selection.names.add(key);else selection.names.delete(key)}}));
    if(proposal.protagonist){
      const label=element('span'),name=refName(proposal.protagonist.ref);
      uiText(label,'textContent',()=>t('character_extract.ui.protagonist_item',{p0:name}));
      proposalNode.append(group('character_extract.ui.protagonist',[checkbox(selection.protagonist,label,on=>{selection.protagonist=on})],on=>{selection.protagonist=on}));
    }
    if(proposal.casts.length)proposalNode.append(group('character_extract.ui.casts',proposal.casts.map(cast=>{
      const label=element('span'),scene=text(sceneLabel(cast.scene_id),'character-proposal-name'),who=cast.participants.map(refName).join(', ');
      const mode=element('small','muted');uiText(mode,'textContent',()=>' '+t(cast.mode==='set'?'character_extract.ui.cast_set':'character_extract.ui.cast_add',{p0:who}));
      label.append(scene,mode);
      return checkbox(selection.casts.has(cast.scene_id),label,on=>{if(on)selection.casts.add(cast.scene_id);else selection.casts.delete(cast.scene_id)});
    }),on=>{selection.casts=new Set(on?proposal.casts.map(cast=>cast.scene_id):[])}));
    const stale=element('p','character-proposal-stale');stale.id='character-proposal-stale';stale.setAttribute('role','status');
    const actions=element('div','actions'),accept=element('button');accept.type='button';accept.id='character-proposal-accept';
    uiText(accept,'textContent',()=>t('character_extract.ui.accept'));
    const blocked=element('small','muted');blocked.id='character-proposal-blocked';
    accept.onclick=()=>void acceptSelected();
    actions.append(accept,blocked);proposalNode.append(stale,actions);
    syncAccept();
  }
  function syncAccept(){
    const accept=document.querySelector('#character-proposal-accept'),blocked=document.querySelector('#character-proposal-blocked');
    if(!accept)return;
    const dirty=isDirty();
    accept.disabled=accepting||dirty||!dryReady;
    say(blocked,dirty?()=>t('character_extract.ui.unsaved_cards'):null);
    for(const control of proposalNode.querySelectorAll('input[type=checkbox],.character-proposal-head button'))control.disabled=accepting;
  }
  async function dryRun(){
    if(!proposal)return;
    const ask=++dryEpoch,stale=document.querySelector('#character-proposal-stale');
    if(!stale)return;
    say(stale,()=>t('character_extract.ui.checking'));dryReady=false;syncAccept();
    try{
      const result=await api(`${storyPath}/character-proposal/accept`,json('POST',acceptBody(proposal,selection,proposal.run_id,true)));
      const line=document.querySelector('#character-proposal-stale');
      if(ask!==dryEpoch||!line)return;
      const count=result.stale_memory_scenes.length;
      say(line,()=>count?t('character_extract.ui.stale_memory',{p0:count}):t('character_extract.ui.no_stale_memory'));
      dryReady=true;syncAccept();
    }catch(error){
      const line=document.querySelector('#character-proposal-stale');
      if(ask!==dryEpoch||!line)return;
      if(error.status===409){notice(error.message,'warning');await loadProposal();return}
      say(line,()=>diagnostic(error.message));
    }
  }
  function itemLabel(item,from){
    if(item.kind==='card'||item.kind==='quote')return refName(item.key,from)+(item.scene_id?` (${sceneLabel(item.scene_id)})`:'');
    if(item.kind==='name')return `${item.key?refName(item.key,from):cards.get(item.card_id)||item.card_id}: ${item.name}`;
    if(item.kind==='name_update')return cards.get(item.card_id)||item.card_id;
    if(item.kind==='protagonist')return refName(item.ref,from);
    if(item.kind==='cast')return sceneLabel(item.scene_id);
    return item.kind;
  }
  async function acceptSelected(){
    if(!proposal||accepting||isDirty())return;
    accepting=true;dryEpoch++;syncAccept();
    const current=proposal;
    try{
      const result=await api(`${storyPath}/character-proposal/accept`,json('POST',acceptBody(current,selection,current.run_id,false)));
      // Names of the accepted cards are read from the proposal before it is dropped.
      const labels=result.skipped.map(entry=>({label:itemLabel(entry.item,current),reason:entry.reason}));
      const box=element('div','character-proposal-result'),line=element('p');box.id='character-proposal-result';box.setAttribute('role','status');
      const applied=result.applied.length,skippedCount=labels.length;
      uiText(line,'textContent',()=>t('character_extract.ui.accepted',{p0:applied,p1:skippedCount}));box.append(line);
      if(labels.length){const list=element('ul');for(const entry of labels){const row=element('li'),why=element('span','muted');row.append(text(entry.label));uiText(why,'textContent',()=>' — '+diagnostic(entry.reason));row.append(why);list.append(row)}box.append(list)}
      const count=result.stale_memory_scenes.length;
      if(count){const stale=element('p','warning');uiText(stale,'textContent',()=>t('character_extract.ui.stale_memory_done',{p0:count}));box.append(stale)}
      acceptedSummary=box;proposal=null;selection=null;renderProposal();
      await onAccepted?.();
      await readContext().catch(()=>{});
    }catch(error){
      notice(error.message,'error');
      if(error.status===409)await loadProposal();
    }finally{accepting=false;syncAccept()}
  }
  async function loadProposal(){
    let found=null;
    try{found=await api(`${storyPath}/character-proposal`,{fresh:true})}
    catch(error){if(error.status!==404)notice(error.message,'error')}
    try{await readContext()}catch{/* names fall back to IDs */}
    dryEpoch++;proposal=found?{...found.proposal,run_id:found.run_id}:null;
    selection=proposal?defaultSelection(proposal):null;
    renderProposal();
    if(proposal)void dryRun();
  }

  // ?extract=1 (the memory build's link) opens the dialog once; the parameter is removed at once.
  let openOnLoad=false;
  try{
    const url=new URL(globalThis.location.href);
    if(url.searchParams.has('extract')){openOnLoad=true;url.searchParams.delete('extract');globalThis.history.replaceState(globalThis.history.state,'',url.href)}
  }catch{/* a restricted browser keeps the address; the dialog still opens */}

  async function init(){
    try{await readContext()}catch(error){notice(error.message,'error')}
    try{await findRun()}catch(error){notice(error.message,'error')}
    await loadProposal();
    if(openOnLoad&&!section.hidden)open();
  }
  void init();
  return {syncAccept};
}
