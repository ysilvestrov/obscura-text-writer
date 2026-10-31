import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {textStatistics} from './text-statistics.js';
import {createTextEditor} from './text-editor.js';
const labels={get plan(){return t("m_3146141c9367")},get brief(){return t("m_5a2ec5eaf0a1")},get draft(){return t("m_e9d875d4120b")},get prose(){return t("m_9c685577453c")},get memory(){return t("m_aa1cfb48cc30")}};
const groups={get system(){return t("m_cfd2384225f6")},get plans(){return t("m_3b55c2af5527")},get characters(){return t("m_fda6febf7bc7")},get memory(){return t("m_aa1cfb48cc30")},get previous_tail(){return t("m_cfeb3b7c3dc9")},get brief(){return t("m_5a2ec5eaf0a1")},get draft(){return t("m_50c3770dbdf6")},get prose(){return t("m_9c685577453c")},get other(){return t("m_2ba58492f61e")},get response_schema(){return t("m_477ae4bbd201")},get protocol(){return t("m_bcac9d5b1d6f")}};
const categories={get facts(){return t("m_d7faf80a1479")},get character_states(){return t("m_eda54a73a727")},get open_threads(){return t("m_2d082c022b82")},get timeline(){return t("m_208c38963ff5")}};

export function installSceneStatistics({state,api,document}){
  const host=document.querySelector('#scene-statistics');if(!host)return;
  const textEditor=createTextEditor(document.querySelector('#editor'));
  const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)uiText(n,"textContent",()=>(String(text)));return n;};
  const compact=node('p'),details=node('details'),summary=node('summary',msg("m_7ab2ade83e6e"));
  const stage=node('select');uiAttr(stage,'aria-label',()=>(t("m_e100ff24e7e6")));
  for(const [value,label] of [['brief',msg("m_27e8e3278f1a")],['draft',msg("m_a0503ed62ae7")],['edit',msg("m_c542d0ba7da5")],['memory',msg("m_05c4218abe15")]]){const option=node('option',live(()=>(label)));option.value=value;stage.append(option);}
  stage.value='draft';
  const reload=node('button',msg("m_0d5314e02813"));reload.type='button';reload.className='secondary';
  const controls=node('div');controls.className='actions';controls.append(stage,reload);
  const status=node('p');status.setAttribute('role','status');const body=node('div');
  details.append(summary,controls,status,body);host.append(compact,details);
  let epoch=0;
  function buffer(){
    if(!state.scene){uiText(compact,"textContent",()=>(t("m_9db3e384fef1")));return;}
    if(state.mode==='review'){uiText(compact,"textContent",()=>(t("m_7a2c0faa8dc9")));return;}
    if(state.memoryTableActive){uiText(compact,"textContent",()=>(t("m_13f59587aa98")));return;}
    const counts=textStatistics(textEditor.visibleText());
    const markdown=textEditor.snapshot().content_format==='markdown';
    const sourceCount=markdown?textStatistics(textEditor.read()).characters:null;
    const origin=state.saving?msg("m_e4b34364f6ba"):state.bufferOrigin==='history'?msg("m_f96dd4fff344"):state.dirty?msg("m_168842f7a2a9"):msg("m_e57e6fe92371");
    uiText(compact,"textContent",()=>(t("m_ce18850f712c",{p0:(origin),p1:(labels[state.mode]||t("m_e070440d491b")),p2:(counts.words),p3:(counts.characters),p4:(['brief','memory','blueprint'].includes(state.mode)?' · JSON':markdown?' · '+t('authoring.source_count',{p0:sourceCount}):'')})));
  }
  function table(headers,rows){
    const t=node('table'),head=node('thead'),tr=node('tr');for(const h of headers){const th=node('th',live(()=>(h)));th.scope='col';tr.append(th);}head.append(tr);t.append(head);
    const b=node('tbody');for(const row of rows){const r=node('tr');for(const value of row)r.append(node('td',live(()=>(value??'—'))));b.append(r);}t.append(b);body.append(t);
  }
  function render(data){
    body.replaceChildren();body.append(node('h3',msg("m_36d1ede72ecf")));
    table([msg("m_bb1bd3087adb"),msg("m_6aed0c4d8e9f"),msg("m_43faaa884006"),msg("m_5333d2e9fcf4")],Object.entries(data.materials).map(([key,m])=>[live(()=>labels[key]),m?.words,m?.characters,live(()=>!m?t("m_d382957ff069"):!m.complete?t("m_95b192576ae2"):m.stale?t("m_8f11db75e9e9"):m.version_id?t("m_3a3b72738467"):t("m_f414d7717fc7"))]));
    const prose=data.materials.prose;body.append(node('p',live(()=>(t("m_9e4e840556de",{p0:(prose?prose.words:'—'),p1:(data.target_words)})))));
    for(const [key,title] of [['previous',msg("m_c6cecc869f8a")],['through_scene',msg("m_80a7d9ba02de")]]){
      const m=data.memory[key];body.append(node('h3',live(()=>(title))));
      if(!m?.available){body.append(node('p',live(()=>(diagnostic(m?.reason)||t("m_e3b740479858")))));continue;}
      body.append(node('p',live(()=>(t("m_5e22a3825f49",{p0:(m.stale?t("m_6905317151f0"):''),p1:(m.complete===false?t("m_11cd78e7bb92"):''),p2:(m.event_count),p3:(key==='previous'?t("m_463bcb2e5314"):t("m_2b556fcb30bb")),p4:(m.current_scene_events)})))));
      table([msg("m_7f3e53d4d224"),msg("m_f25c3cd361bf"),msg("m_37a68c627876")],labelEntries(categories).map(([category,label])=>[label,m.active[category],m.events[category]]));
      body.append(node('p',live(()=>(t("m_2980cf4d9cd1",{p0:(m.operations.add),p1:(m.operations.update),p2:(m.operations.retire)})))));
    }
    const c=data.context;body.append(node('h3',msg("m_36a0e97c4ec2")));
    if(c.available){
      body.append(node('p',live(()=>(t("m_ea0ab2a81e6d",{p0:(c.provider),p1:(c.model),p2:(c.estimated_input_tokens),p3:(c.input_budget),p4:(c.output_reserve),p5:(c.context_tokens),p6:(c.method)})))));
      table([msg("m_aca3cc594690"),msg("m_43faaa884006"),msg("m_707d60cdd672"),msg("m_7bed2c0f58d5")],c.parts.map(p=>[live(()=>groups[p.kind]||p.kind),p.characters,p.request_bytes,p.estimated_tokens]));
      body.append(node('p',msg("m_a57ab6439f85")));
    }
    if(c.reason)body.append(node('p',live(()=>(diagnostic(c.reason)))));
    const last=data.last_usage;body.append(node('h3',msg("m_fc489ce88b97")));
    if(last){const u=last.usage;body.append(node('p',live(()=>(t("m_f8b2a0d9451c",{p0:(last.created_at),p1:(last.model),p2:(last.state),p3:(u.prompt_tokens??u.input_tokens??t("m_5f3c207c48c1")),p4:(u.completion_tokens??u.output_tokens??t("m_5f3c207c48c1")),p5:(u.completion_tokens_details?.reasoning_tokens??t("m_5f3c207c48c1"))})))));}
    else body.append(node('p',msg("m_c1ae3e0b3f46")));
  }
  async function load(){
    const stamp=++epoch,id=state.scene?.id;if(!id||!details.open){body.replaceChildren();return;}
    uiText(status,"textContent",()=>(t("m_a307b67d11c5")));body.replaceChildren();
    try{
      const sourceHead=stage.value==='edit'&&['draft','prose'].includes(state.mode)?state.mode:null;
      const query=new URLSearchParams({stage:stage.value});
      if(sourceHead&&state.scene.heads?.[sourceHead]){query.set('editor_source_head',sourceHead);query.set('editor_source_version_id',state.scene.heads[sourceHead]);}
      const result=await api(`/api/scenes/${id}/statistics?${query}`);
      state.workspaceMaterials=result.materials;if(document.dispatchEvent)document.dispatchEvent(new CustomEvent('workspace-statistics'));
      if(stamp!==epoch||state.scene?.id!==id)return;
      render(result);uiText(status,"textContent",()=>(t("m_e639137a54f5",{p0:(result.scene_revision)})));
    }catch(error){if(stamp===epoch&&state.scene?.id===id)uiText(status,"textContent",()=>(diagnostic(error.message)));}
  }
  details.addEventListener('toggle',()=>void load());stage.addEventListener('change',()=>void load());reload.addEventListener('click',()=>void load());
  document.addEventListener('editor-state-changed',buffer);
  for(const event of ['scene-selected','story-refreshed'])document.addEventListener(event,()=>{buffer();void load();});
  buffer();return {compact,details,body,load};
}
