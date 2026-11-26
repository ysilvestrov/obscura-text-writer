// BRIEF-FORM: the writer's brief as a form. The editor buffer (JSON text) stays the source of truth: the form reads it and writes every edit back.
import {t,uiText,uiAttr} from './i18n.js';
import {parseBrief,stripPlannerNumbers,serializeBrief,canSaveBrief,moveItem,insertBefore,removeItem} from './brief-form.js';

export function installBriefEditor({state,textEditor}){
  const panel=document.querySelector('#brief-form');
  if(!panel)return {active:()=>false,beforeSave:()=>{}};
  const saveButton=document.querySelector('#save-text');
  const node=(tag,className)=>{const n=document.createElement(tag);if(className)n.className=className;return n;};
  const actions=node('div','actions brief-form-actions');
  const toggle=node('button','secondary');toggle.type='button';toggle.id='brief-advanced';actions.append(toggle);
  const problem=node('p','brief-form-problem');problem.setAttribute('role','alert');problem.hidden=true;
  const body=node('div','brief-form-body');
  panel.append(actions,problem,body);

  let model=null,lastText=null,advanced=false,viewKey='',brokenMessage='';
  const readOnly=()=>state.bufferOrigin==='history'||textEditor.isReadOnly()||!!state.saving;
  const visible=()=>state.mode==='brief'&&!!state.scene;
  const active=()=>visible()&&!advanced&&!!model;

  function write(){
    // Every form edit goes into the buffer, so "unsaved", CAS and the unsaved-text guard work as for the JSON text.
    const text=serializeBrief(model);lastText=text;textEditor.replaceText(text);
  }
  // Every field is as tall as its text: no inner scrollbar, rows is only the empty minimum.
  function fit(area){
    const page=document.scrollingElement,top=page?.scrollTop;
    area.style.height='auto';area.style.height=`${area.scrollHeight+area.offsetHeight-area.clientHeight}px`;
    if(page&&page.scrollTop!==top)page.scrollTop=top;
  }
  const fitAll=()=>{if(!body.hidden)body.querySelectorAll('textarea').forEach(fit);};
  // Width changes rewrap the text; a hidden form has no width, so showing it fits the fields too.
  let fittedWidth=-1;
  if(typeof ResizeObserver==='function')new ResizeObserver(()=>{const width=body.clientWidth;if(width!==fittedWidth){fittedWidth=width;fitAll();}}).observe(body);
  function field(value,label,onChange,rows=2){
    const area=node('textarea');area.value=value;area.rows=rows;area.readOnly=readOnly();uiAttr(area,'aria-label',()=>label());
    area.oninput=()=>{fit(area);if(readOnly())return;onChange(area.value);write();controls();};
    return area;
  }
  function iconButton(key,text,onClick,disabled){
    const button=node('button','secondary brief-item-button');button.type='button';button.textContent=text;button.disabled=disabled;
    uiAttr(button,'aria-label',()=>t(key));uiAttr(button,'title',()=>t(key));button.onclick=onClick;return button;
  }
  function list(key,numbered,labelKey,addKey){
    const section=node('section','brief-form-list');section.dataset.list=key;
    const heading=node('h3');uiText(heading,'textContent',()=>t(labelKey));section.append(heading);
    const items=node(numbered?'ol':'ul','brief-items');section.append(items);
    const lock=readOnly();
    model[key].forEach((value,index)=>{
      const item=node('li','brief-item');
      if(numbered){const number=node('span','brief-item-number');number.textContent=`${index+1}.`;number.setAttribute('aria-hidden','true');item.append(number);}
      const area=field(value,()=>numbered?t('brief_form.beat_label',{p0:index+1}):t(labelKey),text=>{model[key][index]=text;});
      area.dataset.index=String(index);item.append(area);
      if(!lock){
        const tools=node('div','brief-item-tools');
        const change=(next,focus)=>{model[key]=next;write();render(key,focus);};
        tools.append(
          iconButton('brief_form.move_up','↑',()=>change(moveItem(model[key],index,-1),index-1),index===0),
          iconButton('brief_form.move_down','↓',()=>change(moveItem(model[key],index,1),index+1),index===model[key].length-1),
          iconButton('brief_form.insert_before','+',()=>change(insertBefore(model[key],index),index),false),
          iconButton('brief_form.remove','×',()=>change(removeItem(model[key],index),Math.min(index,model[key].length-2)),false));
        item.append(tools);
      }
      items.append(item);
    });
    if(!lock){
      const add=node('button','secondary');add.type='button';add.dataset.add=key;uiText(add,'textContent',()=>t(addKey));
      add.onclick=()=>{model[key]=[...model[key],''];write();render(key,model[key].length-1);};
      section.append(add);
    }
    return section;
  }
  function render(focusList=null,focusIndex=null){
    body.replaceChildren();if(!model)return;
    const objective=node('section','brief-form-objective');const label=node('h3');uiText(label,'textContent',()=>t('brief_form.objective'));
    objective.append(label,field(model.objective,()=>t('brief_form.objective'),text=>{model.objective=text;},2));
    body.append(objective,
      list('beats',true,'brief_form.beats','brief_form.add_beat'),
      list('constraints',false,'brief_form.constraints','brief_form.add_constraint'),
      list('proposed_changes',false,'brief_form.proposed_changes','brief_form.add_change'));
    if(focusList!==null&&focusIndex>=0)body.querySelector(`[data-list="${focusList}"] textarea[data-index="${focusIndex}"]`)?.focus();
    controls();fitAll();
  }
  function fromBuffer(){
    const text=textEditor.read(),parsed=parseBrief(text);lastText=text;
    if(!parsed.ok){model=null;advanced=true;brokenMessage=parsed.error;return;}
    const shown=stripPlannerNumbers(parsed.model.beats);
    // Planner numbers are only hidden; the buffer keeps them until the author edits the form.
    model={...parsed.model,beats:shown.beats};brokenMessage='';
  }
  function controls(){
    const show=visible();panel.hidden=!show;
    const formShown=show&&!advanced&&!!model;
    state.briefFormActive=formShown;textEditor.visible(!formShown&&state.mode!=='review'&&!state.memoryTableActive);
    body.hidden=!formShown;
    uiText(toggle,'textContent',()=>advanced?t('brief_form.simple'):t('brief_form.advanced'));
    toggle.disabled=!!state.saving;
    problem.hidden=!(show&&advanced&&brokenMessage);
    uiText(problem,'textContent',()=>t('brief_form.broken',{p0:brokenMessage}));
    if(formShown&&state.bufferOrigin!=='history'&&!state.saving){
      const blocked=!canSaveBrief(model);
      if(blocked)saveButton.disabled=true;
      else if(saveButton.dataset.briefBlocked)saveButton.disabled=false;
      if(blocked)saveButton.dataset.briefBlocked='1';else delete saveButton.dataset.briefBlocked;
      uiAttr(saveButton,'title',()=>blocked?t('brief_form.need_beat'):'');
    }else if(saveButton.dataset.briefBlocked){
      // Leaving the form (advanced JSON, another tab) gives Save back the state the workspace would give it.
      delete saveButton.dataset.briefBlocked;uiAttr(saveButton,'title',()=>'');
      saveButton.disabled=!!state.saving||state.bufferOrigin==='history'||['history','blueprint','review'].includes(state.mode);
    }
  }
  function update(){
    if(!visible()){advanced=false;model=null;viewKey='';lastText=null;brokenMessage='';controls();return;}
    const key=`${state.scene.id}:${state.bufferOrigin}:${state.bufferOrigin==='history'?textEditor.identity().version_id||'':''}`;
    // A scene, tab or version switch opens the form again; the unsaved text itself is guarded by the buffer.
    if(key!==viewKey){viewKey=key;advanced=false;fromBuffer();render();return;}
    if(!advanced&&textEditor.read()!==lastText){fromBuffer();render();return;}
    if(!advanced&&model&&body.querySelector('textarea')?.readOnly!==readOnly()){render();return;}
    controls();
  }
  toggle.onclick=()=>{
    if(state.saving)return;
    if(!advanced){advanced=true;brokenMessage='';controls();textEditor.focus();return;}
    const parsed=parseBrief(textEditor.read());
    if(!parsed.ok){brokenMessage=parsed.error;controls();return;}
    advanced=false;fromBuffer();render();
  };
  for(const event of ['editor-state-changed','story-refreshed','scene-selected'])document.addEventListener(event,update);
  return {
    active,
    /** A brief without a beat is not sent. The buffer is left alone: changing it here would move the buffer epoch
     *  that "Save and run" checks after the save. Empty items are dropped from the request by briefForSave. */
    beforeSave(){
      if(!active()||state.bufferOrigin==='history')return;
      if(!canSaveBrief(model))throw new Error(t('brief_form.need_beat'));
    },
  };
}
