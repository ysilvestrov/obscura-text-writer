import {t,uiText,uiAttr,diagnostic,getLocale} from './i18n.js';
// MANUSCRIPT-IMPORT (R-48 PR 2, spec §4.4): the library dialog that turns an author's manuscript into a new book.
// Steps: file choice → preview (scenes, boundaries, book fields) → summary. The preview creates nothing; until the import or a
// cancel the server keeps the file, so every way out of the dialog without an import sends DELETE.
export const MAX_FILE=20*1024*1024;  // application/manuscript_import.py: MAX_FILE
export const MAX_SCENES=500;  // application/manuscript_import.py: MAX_SCENES
export const MAX_PARAGRAPHS=2000;  // application/manuscript_import.py: MAX_PARAGRAPHS, one paragraphs request
export const SCENE_TITLE_LIMIT=200,BOOK_TITLE_LIMIT=300;
const IMPORTED=new Set(['prose','front_matter']);  // the paragraphs a scene carries; headings and separators stay out
const AXES=['sexual','violence','themes'];

const byIndex=paragraphs=>paragraphs instanceof Map?paragraphs:new Map((paragraphs||[]).map(p=>[p.index,p]));
// Words of one scene: from its paragraphs when all of them are loaded, otherwise the count it already has.
function wordsOf(scene,known){
  let total=0;
  for(let index=scene.start;index<=scene.end;index++){
    const paragraph=known.get(index);if(!paragraph)return scene.words??0;
    if(IMPORTED.has(paragraph.role))total+=paragraph.words;
  }
  return total;
}
export function sceneWords(scenes,paragraphs){const known=byIndex(paragraphs);return scenes.map(scene=>wordsOf(scene,known))}
// «<title> (n)» with the smallest free n ≥ 2; a « (n)» the title already ends with is stripped first, so «Шторм (1)» gives
// «Шторм (2)» (or the next free number), never «Шторм (1) (2)». The base is cut, never the suffix, to stay within 200 characters.
function nextTitle(title,taken){
  const base=title.replace(/ \(\d+\)$/,'');
  for(let n=2;;n++){
    const suffix=` (${n})`,title=base.slice(0,SCENE_TITLE_LIMIT-suffix.length)+suffix;
    if(!taken.has(title))return title;
  }
}
// Adds a boundary on an allowed paragraph inside a scene or removes the boundary that starts there; the first one stays.
export function toggleBoundary(scenes,index,paragraphs){
  const known=byIndex(paragraphs),list=scenes.map(scene=>({...scene}));
  const at=list.findIndex(scene=>scene.start===index);
  if(at===0)return list;
  if(at>0){
    const previous=list[at-1],removed=list[at];
    const words=wordsOf(previous,known)+wordsOf(removed,known);
    list.splice(at-1,2,{...previous,end:removed.end,words});
    return list;
  }
  if(!known.get(index)?.boundary_allowed)return list;
  const inside=list.findIndex(scene=>scene.start<index&&index<=scene.end);
  if(inside<0)return list;
  const scene=list[inside],taken=new Set(list.map(item=>item.title));
  const first={...scene,end:index-1},second={start:index,end:scene.end,title:nextTitle(scene.title,taken),part_index:scene.part_index??null,proposed:false,warnings:[]};
  first.words=wordsOf(first,known);second.words=wordsOf(second,known);
  list.splice(inside,1,first,second);
  return list;
}
// The front matter joins the first scene (it starts at the first front-matter paragraph) or leaves it again; boundaries
// placed inside the front matter go with it.
export function setFrontMatter(scenes,frontMatter,include,firstProse){
  const list=scenes.map(scene=>({...scene}));
  if(!frontMatter?.length||!list.length)return list;
  if(include){list[0].start=Math.min(list[0].start,frontMatter[0]);return list}
  let next=1;while(next<list.length&&list[next].start<=firstProse)next++;
  const joined=list.slice(0,next);
  const first={...list[0],start:firstProse,end:joined[joined.length-1].end};
  if(joined.length>1)first.words=joined.reduce((sum,scene)=>sum+(scene.words??0),0);
  return [first,...list.slice(next)];
}
// Did the author move a boundary or rename a scene: the first start is left out, the front matter moves it.
const signature=scenes=>JSON.stringify(scenes.map((scene,position)=>[position?scene.start:0,String(scene.title)]));
export function authorEdits(scenes,proposed){return signature(scenes)!==signature(proposed)}
// The detected source ('markers', 'level:N', 'none') as the value the preview request takes ('markers', '1'–'3', 'auto').
export function chapterSourceValue(source){
  if(source==='markers')return 'markers';
  const level=/^level:([123])$/.exec(source||'');
  return level?level[1]:'auto';
}
// The body of POST /api/manuscript-import/{id} (ManuscriptApply, extra fields forbidden). The store edition sends no
// parts, part indices or series: the server refuses them there.
export function applyBody(state){
  const scenes=[...state.scenes].sort((a,b)=>a.start-b.start).map(scene=>{
    const item={start:scene.start,title:String(scene.title).trim()};
    if(state.long_prose&&scene.part_index!==null&&scene.part_index!==undefined)item.part_index=scene.part_index;
    return item;
  });
  if(state.include_front_matter&&state.front_matter?.length&&scenes.length)scenes[0].start=Math.min(scenes[0].start,state.front_matter[0]);
  const used=new Set(scenes.map(scene=>scene.part_index).filter(index=>index!==undefined));
  const body={fingerprint:state.fingerprint,title:String(state.title).trim(),language:state.language,content_rating:state.content_rating??null,
    include_front_matter:!!state.include_front_matter,scenes,
    parts:state.long_prose&&used.size?(state.parts||[]).map(part=>({index:part.index,title:part.title||''})):[]};
  if(state.long_prose&&state.series)body.series={series_id:state.series.series_id,number:state.series.number};
  return body;
}

export function installManuscriptImport({api,json,notice,document,appInfo}){
  const get=id=>document.querySelector('#'+id);
  const button=get('manuscript-import-open'),dialog=get('manuscript-import-dialog');
  if(!button||!dialog)return;
  const input=get('manuscript-import-file'),pick=get('manuscript-import-pick'),previewBox=get('manuscript-import-preview');
  const resultBox=get('manuscript-import-result'),status=get('manuscript-import-status'),submit=get('manuscript-import-submit');
  const cancel=get('manuscript-import-cancel'),cancelLabel=get('manuscript-import-cancel-label');
  const fileName=get('manuscript-import-file-name'),bookTitle=get('manuscript-import-book-title'),language=get('manuscript-import-language');
  const chapterMarkers=get('manuscript-import-chapter-markers'),partMarkers=get('manuscript-import-part-markers');
  const chapterSource=get('manuscript-import-chapter-source'),detected=get('manuscript-import-detected');
  const frontRow=get('manuscript-import-front-matter-row'),front=get('manuscript-import-front-matter'),frontText=get('manuscript-import-front-matter-text');
  const partRow=get('manuscript-import-part-markers-row'),seriesWarning=get('manuscript-import-series-warning');
  const seriesRow=get('manuscript-import-series-row'),series=get('manuscript-import-series'),seriesNumber=get('manuscript-import-series-number');
  const list=get('manuscript-import-scenes'),warningsList=get('manuscript-import-warnings'),limit=get('manuscript-import-limit');
  const ratings=Object.fromEntries(AXES.map(axis=>[axis,get('manuscript-import-rating-'+axis)]));
  // pending: the import_id the server still keeps; epoch drops answers of an abandoned step; saving: an import reads the file.
  let preview=null,pending=null,epoch=0,busy=false,saving=false,view='pick',scenes=[],firstProse=0,longProse=true,reset=false;
  const paragraphs=new Map(),expanded=new Set();
  const discard=()=>{
    if(!pending||saving)return;  // a running import reads the file; the server deletes it after a successful import
    const importId=pending;pending=null;
    api(`/api/manuscript-import/${importId}`,{method:'DELETE'}).catch(()=>{});  // the server also sweeps files older than 24 h
  };
  const setStatus=(render,kind='')=>{uiText(status,'textContent',render);status.className=kind};
  const node=(tag,render,className)=>{const n=document.createElement(tag);if(className)n.className=className;if(render)uiText(n,'textContent',render);return n};
  const blankTitle=()=>!bookTitle.value.trim()||scenes.some(scene=>!String(scene.title).trim());

  function sync(){
    pick.hidden=view!=='pick';previewBox.hidden=view!=='preview';resultBox.hidden=view!=='result';submit.hidden=view!=='preview';
    const tooMany=scenes.length>MAX_SCENES;
    limit.hidden=!(view==='preview'&&tooMany);
    uiText(limit,'textContent',()=>tooMany?t('manuscript_import.ui.too_many',{p0:scenes.length,p1:MAX_SCENES}):'');
    submit.disabled=busy||!scenes.length||tooMany||blankTitle();
    uiAttr(submit,'title',()=>tooMany?t('manuscript_import.ui.too_many',{p0:scenes.length,p1:MAX_SCENES}):blankTitle()?t('manuscript_import.ui.blank_title'):'');
    input.disabled=busy;cancel.disabled=saving;
    for(const field of [bookTitle,language,chapterMarkers,partMarkers,chapterSource,front,series,...Object.values(ratings)])if(field)field.disabled=busy;
    if(seriesNumber)seriesNumber.disabled=busy||!series.value;
    dialog.setAttribute('aria-busy',String(busy));
    uiText(cancelLabel,'textContent',()=>view==='result'?t('manuscript_import.ui.close'):t('m_8b4c2025378a'));
  }
  function show(next){view=next;sync()}
  function clearPreview(){
    preview=null;scenes=[];paragraphs.clear();expanded.clear();reset=false;
    list.replaceChildren();warningsList.replaceChildren();limit.hidden=true;
  }
  function restart(){
    epoch++;discard();clearPreview();busy=saving=false;input.value='';resultBox.replaceChildren();
    chapterMarkers.value='';if(partMarkers)partMarkers.value='';chapterSource.value='auto';front.checked=false;bookTitle.value='';
    language.value=getLocale()==='en'?'en':'uk';for(const select of Object.values(ratings))select.value='';
    if(series){series.value='';seriesNumber.value='';readinessAsk++;seriesWarning.hidden=true;seriesWarning.replaceChildren()}
    setStatus(()=>'');show('pick');
  }

  async function edition(){
    let info;try{info=await appInfo()}catch{info={}}
    longProse=info.long_prose!==false;
    if(seriesRow&&!longProse)seriesRow.hidden=true;
    if(partRow&&!longProse)partRow.hidden=true;  // no parts in this edition: their markers would only feed warnings
    const max=info.max_rating||{sexual:2,violence:2,themes:2};
    for(const axis of AXES)for(const option of ratings[axis].options){if(option.value==='')continue;const off=Number(option.value)>max[axis];option.hidden=off;option.disabled=off}
    if(series&&longProse){
      try{
        const items=await api('/api/series');
        series.replaceChildren(series.options[0]);
        for(const item of items){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;series.append(option)}
      }catch{seriesRow.hidden=true}
    }
  }

  // --- Rendering ---
  function renderWarnings(){
    warningsList.replaceChildren();
    if(reset)warningsList.append(node('li',()=>t('manuscript_import.ui.reset')));
    for(const text of preview.warnings)warningsList.append(node('li',()=>diagnostic(text)));
    for(const item of preview.dropped)warningsList.append(node('li',()=>t(item.reason==='toc'?'manuscript_import.ui.dropped_toc':'manuscript_import.ui.dropped_part',{p0:item.text})));
  }
  function partTitle(index){
    const part=(preview.parts||[]).find(item=>item.index===index);
    return part?.title||t('manuscript_import.ui.part_untitled',{p0:index+1});
  }
  function renderParagraphs(box,scene,position){
    box.replaceChildren();
    if(missing(scene).length){box.append(node('p',()=>t('manuscript_import.ui.loading'),'muted'));return}
    const items=document.createElement('ol');items.className='manuscript-import-paragraphs';
    for(let index=scene.start;index<=scene.end;index++){
      const paragraph=paragraphs.get(index);if(!paragraph)continue;
      const item=document.createElement('li');item.dataset.index=String(index);item.className='manuscript-import-paragraph role-'+paragraph.role;
      item.append(node('span',null,'manuscript-import-text'));item.firstChild.textContent=paragraph.text_head||'·';
      const start=index===scene.start;
      if((start&&position>0)||(!start&&paragraph.boundary_allowed)){
        const toggle=node('button',()=>t(start?'manuscript_import.ui.boundary_remove':'manuscript_import.ui.boundary_add'),'secondary manuscript-import-boundary');
        toggle.type='button';toggle.dataset.index=String(index);toggle.disabled=busy;toggle.onclick=()=>moveBoundary(index);
        item.append(toggle);
      }
      items.append(item);
    }
    box.append(items);
  }
  function renderScenes(){
    list.replaceChildren();
    const counts=sceneWords(scenes,paragraphs);
    scenes.forEach((scene,position)=>{
      const item=document.createElement('li');item.className='manuscript-import-scene';item.dataset.start=String(scene.start);
      const head=document.createElement('div');head.className='manuscript-import-scene-head';
      const title=document.createElement('input');title.className='manuscript-import-scene-title';title.maxLength=SCENE_TITLE_LIMIT;title.required=true;
      title.value=scene.title;title.disabled=busy;uiAttr(title,'aria-label',()=>t('manuscript_import.ui.scene_title',{p0:position+1}));
      title.oninput=()=>{scene.title=title.value;sync()};
      const meta=document.createElement('p');meta.className='muted manuscript-import-meta';
      meta.append(node('span',()=>t('manuscript_import.ui.words',{p0:counts[position]}),'manuscript-import-words'));
      if(longProse&&scene.part_index!==null&&scene.part_index!==undefined)meta.append(' · ',node('span',()=>t('manuscript_import.ui.part',{p0:partTitle(scene.part_index)}),'manuscript-import-part'));
      if(scene.proposed)meta.append(' · ',node('span',()=>t('manuscript_import.ui.proposed'),'manuscript-import-proposed'));
      head.append(title,meta);item.append(head);
      if(scene.warnings?.length){const notes=node('ul',null,'muted');for(const text of scene.warnings)notes.append(node('li',()=>diagnostic(text)));item.append(notes)}
      const details=document.createElement('details');details.open=expanded.has(scene.start);
      details.append(node('summary',()=>t('manuscript_import.ui.paragraphs')));
      const box=document.createElement('div');details.append(box);
      if(details.open)renderParagraphs(box,scene,position);
      details.ontoggle=()=>{
        if(!details.open){expanded.delete(scene.start);return}
        expanded.add(scene.start);
        if(box.childElementCount&&!missing(scene).length)return;  // already shown: a re-render would drop the focus
        renderParagraphs(box,scene,position);
        ensureParagraphs(scene).then(()=>{if(box.isConnected)renderParagraphs(box,scene,position)});
      };
      item.append(details);list.append(item);
    });
    sync();
  }
  function renderPreview(){
    fileName.textContent=preview.file_name;
    const source=chapterSourceValue(preview.chapter_source),none=preview.chapter_source==='none';
    uiText(detected,'textContent',()=>t('manuscript_import.ui.detected',{p0:t(none?'manuscript_import.ui.source_none':source==='markers'?'manuscript_import.ui.source_markers':'manuscript_import.ui.source_level_'+source)}));
    const hasFront=(preview.front_matter||[]).length>0;
    frontRow.hidden=!hasFront;frontText.hidden=!hasFront;
    if(!hasFront)front.checked=false;
    renderWarnings();renderScenes();
  }

  // --- Paragraphs and boundaries ---
  function missing(scene){const out=[];for(let index=scene.start;index<=scene.end;index++)if(!paragraphs.has(index))out.push(index);return out}
  // Lazy: a scene's paragraphs are read when it is expanded, at most MAX_PARAGRAPHS per request.
  async function ensureParagraphs(scene){
    const wanted=missing(scene);
    if(!wanted.length||!preview)return;
    const mine=epoch,importId=preview.import_id,last=wanted[wanted.length-1];
    try{
      for(let start=wanted[0];start<=last;start+=MAX_PARAGRAPHS){
        const items=await api(`/api/manuscript-import/${importId}/paragraphs?start=${start}&end=${Math.min(last,start+MAX_PARAGRAPHS-1)}`);
        if(mine!==epoch)return;
        for(const item of items)paragraphs.set(item.index,item);
      }
    }catch(error){if(mine===epoch)fail(error)}
  }
  function moveBoundary(index){
    const before=scenes.length;
    scenes=toggleBoundary(scenes,index,paragraphs);
    if(scenes.length===before)return;
    // The scenes on both sides of the boundary stay open; focus returns to the same paragraph's button.
    const owner=scenes.find(scene=>scene.start<=index&&index<=scene.end);
    if(scenes.length>before)expanded.add(index);
    else{expanded.delete(index);if(owner)expanded.add(owner.start)}
    renderScenes();
    (list.querySelector(`.manuscript-import-boundary[data-index="${index}"]`)||list.querySelector(`[data-start="${owner?.start}"] .manuscript-import-scene-title`))?.focus();
  }
  function fillFrontText(){
    const ids=preview?.front_matter||[];
    if(!ids.length){frontText.textContent='';return}
    const loaded=ids.map(index=>paragraphs.get(index)?.text_head).filter(Boolean);
    frontText.textContent=loaded.length?loaded.join(' · '):'';
  }
  async function loadFront(){
    const ids=preview?.front_matter||[];if(!ids.length)return;
    const mine=epoch;
    try{
      const items=await api(`/api/manuscript-import/${preview.import_id}/paragraphs?start=${ids[0]}&end=${ids[ids.length-1]}`);
      if(mine!==epoch)return;
      for(const item of items)paragraphs.set(item.index,item);fillFrontText();
    }catch{}
  }

  // --- Requests ---
  function settingsForm(){
    const body=new FormData();
    if(chapterMarkers.value.trim())body.append('chapter_markers',chapterMarkers.value);
    if(partMarkers?.value.trim())body.append('part_markers',partMarkers.value);
    body.append('chapter_source',chapterSource.value||'auto');
    body.append('language',getLocale()==='en'?'en':'uk');  // the Prologue title follows the interface language (spec §3.3)
    return body;
  }
  function accept(data,{again}){
    const hadEdits=again&&preview&&authorEdits(scenes,preview.scenes);
    const keepTitle=again?bookTitle.value:null;
    clearPreview();
    preview=data;pending=data.import_id;reset=!!hadEdits;
    scenes=data.scenes.map(scene=>({...scene,warnings:[...(scene.warnings||[])]}));
    firstProse=scenes[0]?.start??0;
    if(front.checked)scenes=setFrontMatter(scenes,data.front_matter,true,firstProse);
    bookTitle.value=(keepTitle??data.title_suggestion??'').slice(0,BOOK_TITLE_LIMIT);
    renderPreview();loadFront();
  }
  input.onchange=async()=>{
    const chosen=input.files?.[0];if(!chosen)return;
    epoch++;discard();clearPreview();show('pick');
    if(chosen.size>MAX_FILE){input.value='';setStatus(()=>t('manuscript_import.server.too_large',{p0:MAX_FILE/(1024*1024)}),'error');return}
    const mine=epoch,body=settingsForm();body.append('file',chosen,chosen.name);
    busy=true;sync();setStatus(()=>t('manuscript_import.ui.reading'),'muted');
    try{
      const data=await api('/api/manuscript-import/preview',{method:'POST',body});
      if(mine!==epoch||!dialog.open){api(`/api/manuscript-import/${data.import_id}`,{method:'DELETE'}).catch(()=>{});return}
      busy=false;accept(data,{again:false});setStatus(()=>'');show('preview');bookTitle.focus();
    }catch(error){if(mine!==epoch)return;input.value='';setStatus(()=>diagnostic(error.message),'error')}
    finally{if(mine===epoch){busy=false;sync()}}
  };
  // New markers or another chapter source parse the kept file again: a new fingerprint, and the author's boundaries reset.
  async function reparse(){
    if(!preview||busy)return;
    const mine=++epoch,body=settingsForm();body.append('import_id',preview.import_id);
    busy=true;renderScenes();setStatus(()=>t('manuscript_import.ui.reparsing'),'muted');
    try{
      const data=await api('/api/manuscript-import/preview',{method:'POST',body});
      if(mine!==epoch)return;
      busy=false;accept(data,{again:true});setStatus(()=>'');
    }catch(error){if(mine!==epoch)return;busy=false;fail(error)}
    finally{if(mine===epoch){busy=false;if(preview)renderScenes();else sync()}}
  }
  // 409 (an older preview, or the import already runs) and a missing kept file: the file is chosen again. Every other
  // refusal (a taken series number, a bad title) keeps the preview and the author's boundaries for a fix.
  // A 404 from the import or the paragraphs means the kept file is gone (24 hours passed, a cancel in another tab); the
  // server's 404 text is generic, so the status code decides and the dialog says it in its own words.
  function fail(error){
    if(error.status===409||error.status===404){
      const gone=error.status===404;
      busy=saving=false;discard();clearPreview();input.value='';show('pick');
      setStatus(()=>gone?t('manuscript_import.ui.vanished'):t('manuscript_import.ui.choose_again',{p0:diagnostic(error.message)}),'error');input.focus();
    }else setStatus(()=>diagnostic(error.message),'error');
  }
  function rating(){
    const values=AXES.map(axis=>ratings[axis].value);
    if(values.every(value=>value===''))return null;
    if(values.includes(''))throw new Error(t('rating.incomplete'));
    return Object.fromEntries(AXES.map((axis,index)=>[axis,Number(values[index])]));
  }
  function seriesChoice(){
    if(!series||!longProse||!series.value)return null;
    const number=Number(seriesNumber.value);
    if(!Number.isInteger(number)||number<1)throw new Error(t('manuscript_import.ui.series_number_required'));
    return {series_id:series.value,number};
  }
  async function apply(){
    if(!preview||busy||submit.disabled)return;
    let body;
    try{
      body=applyBody({fingerprint:preview.fingerprint,title:bookTitle.value,language:language.value,content_rating:rating(),scenes,parts:preview.parts,
        include_front_matter:front.checked&&(preview.front_matter||[]).length>0,front_matter:preview.front_matter,series:seriesChoice(),long_prose:longProse});
    }catch(error){setStatus(()=>error.message,'error');return}
    const mine=epoch,shown=preview;
    busy=saving=true;renderScenes();setStatus(()=>t('manuscript_import.ui.saving'),'muted');
    try{
      const result=await api(`/api/manuscript-import/${shown.import_id}`,json('POST',body));
      if(pending===shown.import_id)pending=null;  // imported: the server already removed the file
      if(mine!==epoch)return;
      busy=saving=false;renderResult(result,body.title);setStatus(()=>'');show('result');
      resultBox.querySelector('a')?.focus();
    }catch(error){
      if(mine!==epoch)return;
      saving=false;fail(error);
    }finally{if(mine===epoch){busy=saving=false;if(view==='preview')renderScenes();else sync()}}
  }
  function renderResult(result,title){
    resultBox.replaceChildren();
    const count=result.scene_ids.length,storyUrl=`/stories/${encodeURIComponent(result.story_id)}`;
    const done=node('p',null,'success');
    const link=document.createElement('a');link.href=storyUrl;link.textContent=title;
    done.append(node('span',()=>t('manuscript_import.ui.result',{p0:count})+' '),link);
    resultBox.append(done);
    if(result.warnings?.length){const notes=node('ul',null,'muted');for(const text of result.warnings)notes.append(node('li',()=>diagnostic(text)));resultBox.append(notes)}
    resultBox.append(node('p',()=>t('manuscript_import.ui.build_memory_hint'),'muted'));
    const build=node('a',()=>t('manuscript_import.ui.build_memory',{p0:count}),'button');
    build.id='manuscript-import-build-memory';build.href=`${storyUrl}?build_memory=1`;
    const actions=document.createElement('p');actions.append(build);resultBox.append(actions);
  }

  bookTitle.oninput=()=>sync();
  chapterMarkers.onchange=chapterSource.onchange=()=>reparse();
  if(partMarkers)partMarkers.onchange=()=>reparse();
  front.onchange=()=>{scenes=setFrontMatter(scenes,preview?.front_matter,front.checked,firstProse);renderScenes()};
  // §4.2: a series book whose previous book has no memory yet starts without a snapshot; the preview says so with a link.
  let readinessAsk=0;
  async function readiness(){
    const ask=++readinessAsk,number=Number(seriesNumber.value);
    seriesWarning.hidden=true;seriesWarning.replaceChildren();
    if(!series.value||!Number.isInteger(number)||number<1)return;
    try{
      const data=await api(`/api/series/${encodeURIComponent(series.value)}/start-readiness?number=${number}`);
      if(ask!==readinessAsk||data.state!=='no_summary'||!data.source_story_id)return;
      const link=document.createElement('a');link.href=`/stories/${encodeURIComponent(data.source_story_id)}`;link.textContent=data.source_title||'';
      seriesWarning.append(node('span',()=>t('manuscript_import.ui.series_no_memory')+' '),link);seriesWarning.hidden=false;
    }catch{}  // a missing answer only loses the hint: the import still warns after the book exists
  }
  if(series){
    series.onchange=()=>{if(!series.value)seriesNumber.value='';sync();readiness()};
    seriesNumber.oninput=()=>readiness();
  }
  button.onclick=()=>{
    restart();dialog.showModal();button.setAttribute('aria-expanded','true');input.focus();
  };
  // Every way out (Cancel, Escape, the summary links) resets the dialog; a preview that was not imported is deleted.
  // While an import runs the dialog stays open: closing would delete the file the import is reading.
  dialog.addEventListener('cancel',event=>{if(saving)event.preventDefault()});
  dialog.addEventListener('close',()=>{restart();button.setAttribute('aria-expanded','false');button.focus()});
  cancel.onclick=()=>dialog.close();
  submit.onclick=()=>apply();
  edition().catch(error=>notice(error.message,'error'));
  sync();
}
