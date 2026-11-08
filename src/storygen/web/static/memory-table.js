import {createTextEditor} from './text-editor.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
export function installMemoryTable({state,api,json,notice,refresh,loadBuffer}){
  const panel=document.querySelector('#memory-view');
  if(!panel)return {active:()=>false,save:async()=>{}};
  const editor=createTextEditor(document.querySelector('#editor')),saveButton=document.querySelector('#save-text');
  const node=(tag,text)=>{const n=document.createElement(tag);if(text)uiText(n,"textContent",()=>(text));return n;};
  const help=node('p',msg("m_0f4d928f4083"));
  const actions=node('div');actions.className='actions';
  const toggle=node('button',msg("m_41ebabe287dc"));toggle.type='button';toggle.className='secondary';
  const reload=node('button',msg("m_75a060c1564b"));reload.type='button';reload.className='secondary';actions.append(toggle,reload);
  const info=node('p');info.setAttribute('role','status');
  const tools=node('div');tools.className='memory-filters';
  const search=node('input');search.type='search';uiText(search,"placeholder",()=>(t("m_7d6c01cf20e1")));uiAttr(search,'aria-label',()=>(t("m_7d6c01cf20e1")));
  const filter=node('select');uiAttr(filter,'aria-label',()=>(t("m_ed9073f821ed")));
  for(const [value,label] of [['',msg("m_2471988b961a")],['facts',msg("m_d7faf80a1479")],['character_states',msg("m_eda54a73a727")],['open_threads',msg("m_2d082c022b82")],['timeline',msg("m_208c38963ff5")]]){const o=node('option',live(()=>(label)));o.value=value;filter.append(o);}
  tools.append(search,filter);
  const wrap=node('div');wrap.className='memory-table-wrap';
  const table=node('table');table.className='memory-table';
  const caption=node('caption',msg("m_80a7d9ba02de"));const head=node('thead'),header=node('tr');
  for(const title of [msg("m_6cf9b3a4b307"),msg("m_461437b0662b"),msg("m_7f3e53d4d224"),msg("m_aca3cc594690")]){const th=node('th',live(()=>(title)));th.scope='col';header.append(th);}
  head.append(header);const body=node('tbody');table.append(caption,head,body);wrap.append(table);
  panel.append(help,actions,info,tools,wrap);
  let key=null,data=null,pending={},advanced=false,loading=false,rawText='',loadedSceneId=null,loadedMemoryId=null;
  const currentKey=()=>`${state.scene?.id}:${state.scene?.heads.memory||''}:${state.bufferEpoch}`;
  const emit=()=>document.dispatchEvent(new CustomEvent('editor-state-changed'));
  const active=()=>state.mode==='memory'&&state.bufferOrigin!=='history'&&!advanced;
  function counts(shown){
    const enabled=data.rows.filter(row=>pending[row.claim_id]??row.forward).length;
    uiText(info,"textContent",()=>[diagnostic(data.reason)||t("m_8305b929daa9",{p0:(enabled),p1:(data.rows.length),p2:(shown)}),...(data.warnings||[]).map(diagnostic)].join(' '));
    if(!data.rows.length&&!data.reason)uiText(info,"textContent",()=>(t("m_48cdfb12cbf3")));
  }
  function controls(){
    const visible=state.mode==='memory'&&state.bufferOrigin!=='history';panel.hidden=!visible;
    state.memoryTableActive=visible&&!advanced;editor.visible(!(visible&&!advanced));
    tools.hidden=advanced;wrap.hidden=advanced;
    uiText(toggle,"textContent",()=>(advanced?t("m_7a516601ed73"):t("m_41ebabe287dc")));
    toggle.disabled=state.saving||loading;reload.disabled=state.saving||loading;
    if(visible&&!advanced)saveButton.disabled=loading||state.saving||!data?.can_save||!state.dirty;
    else if(visible&&advanced)saveButton.disabled=loading||state.saving;
  }
  function draw(){
    body.replaceChildren();if(!data){controls();return;}
    const rows=data.rows.filter(row=>(!filter.value||row.category===filter.value)&&`${row.text} ${row.source_title}`.toLocaleLowerCase('uk').includes(search.value.toLocaleLowerCase('uk')));
    counts(rows.length);
    if(!rows.length&&data.rows.length){const tr=node('tr'),td=node('td',msg("m_2d74a1418749"));td.colSpan=4;tr.append(td);body.append(tr);}
    for(const row of rows){
      const tr=node('tr'),choice=node('td'),content=node('td'),category=node('td',live(()=>(diagnostic(row.category_label)+(row.closed?t("m_d5c9ae2ce4bc"):'')))),source=node('td',live(()=>(row.source_scene?t("m_90d9f38d6edc",{p0:(row.source_scene),p1:(row.source_title)}):row.source_title)));
      const check=node('input');check.type='checkbox';check.checked=pending[row.claim_id]??row.forward;
      uiAttr(check,'aria-label',()=>(t("m_069fcf4281aa",{p0:(row.text)})));check.disabled=state.saving||!data.can_save;
      check.onchange=()=>{
        if(state.saving||!data.can_save)return;
        if(check.checked===row.forward)delete pending[row.claim_id];else pending[row.claim_id]=check.checked;
        state.dirty=Object.keys(pending).length>0;
        uiText(document.querySelector('#save-state'),"textContent",()=>(state.dirty?t("m_9279ff773392"):t("m_6a25073b2b9f")));
        emit();counts(rows.length);controls();
      };
      choice.append(check);content.append(node('p',live(()=>(row.text))));
      const proof=node('details');proof.append(node('summary',msg("m_a09205d5a71e")),node('p',live(()=>(row.quote))));for(const extra of Array.isArray(row.supporting_quotes)?row.supporting_quotes:[])proof.append(node('p',live(()=>(extra))));content.append(proof);
      [choice,content,category,source].forEach((td,i)=>uiAttr(td,'data-label',()=>[msg("m_6cf9b3a4b307"),msg("m_461437b0662b"),msg("m_7f3e53d4d224"),msg("m_aca3cc594690")][i]));
      tr.append(choice,content,category,source);body.append(tr);
    }
    controls();
  }
  async function load(){
    const captured=currentKey();key=captured;loadedSceneId=state.scene.id;loadedMemoryId=state.scene.heads.memory;data=null;pending={};advanced=false;rawText=editor.read();loading=true;uiText(info,"textContent",()=>(t("m_1f3975528ccd")));draw();
    try{
      const result=await api(`/api/scenes/${state.scene.id}/memory-view`);
      if(currentKey()!==captured||state.mode!=='memory')return;
      data=result;
      if(result.memory_id!==(state.scene.heads.memory||null))data={...result,can_save:false,reason:t("m_df25fc889f42")};
      else if(!state.dirty)state.scene=result.scene;
      draw();
    }catch(error){if(currentKey()===captured)uiText(info,"textContent",()=>(diagnostic(error.message)));}
    finally{if(currentKey()===captured){loading=false;controls();}}
  }
  function update(){
    if(state.mode!=='memory'||state.bufferOrigin==='history'){advanced=false;key=null;controls();return;}
    controls();
    const editingSameJson=advanced&&state.scene.id===loadedSceneId&&state.scene.heads.memory===loadedMemoryId;
    if(currentKey()!==key&&!editingSameJson)void load();
  }
  toggle.onclick=()=>{
    if(state.saving||loading)return;
    if(state.dirty&&!confirm(t("m_d02463e81890")))return;
    if(state.dirty){pending={};editor.write(rawText,{material:'memory'});state.dirty=false;}
    advanced=!advanced;emit();draw();
  };
  reload.onclick=async()=>{
    if(state.saving||loading)return;
    if(state.dirty&&!confirm(t("m_4a84469cb5d2")))return;
    const captured=currentKey();loading=true;controls();
    try{
      const latest=await api(`/api/scenes/${state.scene.id}/memory-view`);
      const text=latest.memory_id?(await api(`/api/versions/${latest.memory_id}`)).text:'';
      if(currentKey()===captured){loading=false;loadBuffer(latest.scene,'memory',text);}
    }catch(error){notice(error.message,'error');}
    finally{loading=false;controls();}
  };
  search.oninput=filter.onchange=draw;
  document.addEventListener('editor-state-changed',update);document.addEventListener('story-refreshed',update);
  return {active,save:async()=>{
    if(state.saving||loading||!state.dirty||!data?.can_save)return;
    const captured=currentKey(),snapshot=data,choices={...pending};state.saving=true;emit();draw();
    try{
      const result=await api(`/api/scenes/${snapshot.scene.id}/memory-view`,json('PUT',{expected_revision:snapshot.expected_revision,fingerprint:snapshot.fingerprint,choices}));
      if(currentKey()===captured){data=result;state.scene=result.scene;pending={};state.dirty=false;uiText(document.querySelector('#save-state'),"textContent",()=>(t("m_922c2ebbfd84")));}
      await refresh();notice(msg("m_3fae998ee80e"));
    }catch(error){notice(error.message,'error');}
    finally{state.saving=false;emit();draw();}
  }};
}
