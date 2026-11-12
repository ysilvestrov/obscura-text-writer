// Model catalog picker: pure logic for badges, filters and selectability, plus the DOM mount.
import {t,uiText,uiAttr,getLocale} from './i18n.js';
import {modelMetadataLabel} from './model-catalog.js';
export const PRIVACY_RANK={unknown:-1,anonymized:0,private:1,tee:2};
const MIN_RANK={any:-1,private:1,tee:2};

export function privacyLevel(model){
  if(model.tee)return 'tee';
  return Object.hasOwn(PRIVACY_RANK,model.privacy)?model.privacy:'unknown';
}

export function modelBadges(model){
  const kinds=[];
  if(model.uncensored===true)kinds.push('uncensored');
  kinds.push(privacyLevel(model));
  if(model.supports_schema===true)kinds.push('schema');
  return kinds.map(kind=>({kind,key:`models.badge_${kind}`}));
}

export const providerReportsPrivacy=provider=>provider==='venice';
export const schemaLocked=responseMode=>responseMode==='json_schema';

export function filterModels(models,{query='',uncensoredOnly=false,minPrivacy='any',schemaOnly=false}={},provider){
  const needle=String(query||'').trim().toLowerCase();
  const minRank=providerReportsPrivacy(provider)?(MIN_RANK[minPrivacy]??-1):-1;
  return models.filter(model=>{
    if(needle&&!`${model.id||''}`.toLowerCase().includes(needle)&&!`${model.name||''}`.toLowerCase().includes(needle))return false;
    if(uncensoredOnly&&model.uncensored!==true)return false;
    if(schemaOnly&&model.supports_schema!==true)return false;
    return PRIVACY_RANK[privacyLevel(model)]>=minRank;
  });
}

export function selectable(model,{provider,responseMode}={}){
  if(model===null||model===undefined)return {ok:true,reason:null};
  // Only an explicit "no" blocks; unknown support (local, rows without the field) stays selectable with a hint.
  if(schemaLocked(responseMode)&&model.supports_schema===false)return {ok:false,reason:'schema_required'};
  return {ok:true,reason:null};
}

// A value above a cap the catalog reports would fail at call time; unknown caps never block.
export function limitsProblem(model,values={}){
  if(!model)return null;
  for(const [name,key] of [['context_tokens','models.context_exceeded'],['max_output_tokens','models.output_exceeded']]){
    const cap=model[name],value=values[name];
    if(Number.isInteger(cap)&&cap>0&&Number.isFinite(value)&&value>cap)return {key,params:{p0:value,p1:cap}};
  }
  return null;
}
// validate() yields a message key or {key,params}; callers show it through this.
export const pickerMessage=problem=>!problem?'':typeof problem==='string'?t(problem):t(problem.key,problem.params);

export const schemaUnknown=(model,{responseMode}={})=>Boolean(model)&&schemaLocked(responseMode)&&(model.supports_schema===null||model.supports_schema===undefined);

export function formatPrice(usd){
  if(usd===null||usd===undefined||usd==='')return '—';
  const value=Number(usd);
  if(!Number.isFinite(value))return '—';
  // A tiny positive rate is not free: never round it down to "0".
  if(value>0&&value<0.01)return '<0.01';
  const digits=value<10?2:1;
  return String(Number(value.toFixed(digits)));
}

// Catalog picker mounted next to a real model input; manual IDs keep working and form code reads the input.
const formatContext=n=>Number.isInteger(n)&&n>0?(n>=1e6?`${Number((n/1e6).toFixed(1))}M`:`${Math.round(n/1000)}K`):'—';
const rate=(model,side)=>{const raw=model.tariff?.[`${side}_per_million`],value=Number(raw);return raw===null||raw===undefined||raw===''||!Number.isFinite(value)?null:value};
const SORT_KEYS={name:m=>String(m.name||m.id).toLowerCase(),context:m=>Number.isInteger(m.context_tokens)?m.context_tokens:null,input:m=>rate(m,'input'),output:m=>rate(m,'output')};
const COLUMNS=[['name','models.col_model'],[null,'models.col_badges'],['context','models.col_context'],['input','models.col_input'],['output','models.col_output']];
let pickerCount=0;
function el(tag,props={},...children){const node=document.createElement(tag);for(const[k,v]of Object.entries(props))if(k in node&&!k.includes('-'))node[k]=v;else node.setAttribute(k,v);node.append(...children);return node}
const badgeList=model=>el('span',{className:'model-badges'},...modelBadges(model).map(b=>el('span',{className:`model-badge model-badge-${b.kind}`},t(b.key))));

export function mountModelPicker({host,modelInput,providerInput,baseUrlInput,responseModeInput=null,limitInputs={}}){
  const uid=`model-picker-${++pickerCount}`;host.classList.add('model-picker');
  const caption=modelInput.parentElement.firstChild;
  uiAttr(modelInput,'aria-label',()=>{getLocale();return caption?.textContent||t('m_f1f1eed62cda')});
  const code=el('code'),badges=el('span'),info=el('small',{className:'settings-hint',id:`${uid}-info`,'data-model-info':'true'});
  const toggle=el('button',{type:'button',className:'secondary','aria-controls':`${uid}-panel`,'aria-expanded':'false'});
  const blocked=el('p',{className:'model-picker-blocked',role:'status','data-model-blocked':'true'});
  const schemaHint=el('small',{className:'settings-hint','data-schema-unknown':'true',hidden:true});
  const query=el('input',{type:'search'}),uncensored=el('input',{type:'checkbox'}),schema=el('input',{type:'checkbox'});
  const privacy=el('select',{'aria-describedby':`${uid}-privacy`},...['any','private','tee'].map(value=>el('option',{value})));privacy.value='private';
  const privacyNote=el('small',{className:'settings-hint',id:`${uid}-privacy`,'data-privacy-note':'true'});
  const textSpan=key=>{const span=el('span');uiText(span,'textContent',()=>t(key));return span};
  const heads=COLUMNS.map(([key,label])=>{
    const th=el('th',{scope:'col',className:key&&key!=='name'?'num':''});th.dataset.sort=key||'';
    if(!key){th.append(textSpan(label));return th}
    const sort=el('button',{type:'button',className:'model-picker-sort'},textSpan(label));sort.onclick=()=>{direction=sortKey===key?-direction:1;sortKey=key;render()};th.append(sort);return th;
  });
  const tbody=el('tbody'),foot=el('p',{className:'model-picker-foot'});
  const panel=el('div',{className:'model-picker-panel',id:`${uid}-panel`,hidden:true},
    el('div',{className:'model-picker-filters'},query,el('label',{className:'checkbox'},uncensored,' ',textSpan('models.filter_uncensored')),
      el('label',{className:'model-picker-privacy'},textSpan('models.filter_privacy'),privacy),el('label',{className:'checkbox'},schema,' ',textSpan('models.filter_schema')),privacyNote),
    el('div',{className:'model-picker-list'},el('table',{},el('thead',{},el('tr',{},...heads)),tbody)),foot);
  host.replaceChildren(el('div',{className:'model-picker-chosen','data-model-chosen':'true'},code,badges,info,toggle),blocked,schemaHint,panel);
  uiText(toggle,'textContent',()=>t('models.change'));uiAttr(query,'placeholder',()=>t('models.search'));uiAttr(query,'aria-label',()=>t('models.search'));
  uiText(privacyNote,'textContent',()=>t('models.privacy_not_reported'));
  for(const option of privacy.options)uiText(option,'textContent',()=>t(`models.privacy_${option.value}`));
  modelInput.setAttribute('aria-describedby',[modelInput.getAttribute('aria-describedby'),info.id].filter(Boolean).join(' '));
  let catalog=new Map(),binding=null,sortKey='input',direction=1,userSchema=false,message=null;
  const identity=()=>JSON.stringify([providerInput.value,baseUrlInput.value.replace(/\/$/,'')]);
  const context=()=>({provider:providerInput.value,responseMode:responseModeInput?.value});
  const bound=()=>binding!==null&&binding===identity();
  const current=()=>bound()?catalog.get(modelInput.value)??null:null;
  let limits={};
  const limitValues=()=>Object.fromEntries(Object.entries(limits).filter(([,input])=>input).map(([name,input])=>[name,input.value===''?NaN:Number(input.value)]));
  function validate(){const check=selectable(current(),context());return check.ok?limitsProblem(current(),limitValues()):`models.blocked_${check.reason}`}
  // Known caps also become the inputs' max, so the number field itself shows the bound.
  function syncLimitBounds(){const model=current();for(const [name,input] of Object.entries(limits)){if(!input)continue;const cap=model?.[name];if(Number.isInteger(cap)&&cap>0)input.max=String(cap);else input.removeAttribute('max')}}
  // Limit fields may be built after the picker (classifier, evaluator); they are bound when they exist.
  function bindLimits(map){limits={...map};for(const input of Object.values(limits))input?.addEventListener('input',()=>{message=null;renderChosen()});renderChosen()}
  function choose(model){
    // While a settings save is running the form controls are disabled; the list must not change the model either.
    if(modelInput.disabled)return;
    const check=selectable(model,context());
    if(!check.ok){message=`models.blocked_${check.reason}`;render();return}
    modelInput.value=model.id;for(const type of ['input','change'])modelInput.dispatchEvent(new Event(type,{bubbles:true}));
  }
  function renderChosen(){
    const model=current();code.textContent=modelInput.value||'—';badges.replaceChildren(...(model?[badgeList(model)]:[]));
    uiText(info,'textContent',()=>bound()&&!model&&modelInput.value?t('models.not_in_catalog'):modelMetadataLabel(model));
    syncLimitBounds();const key=message||validate();uiText(blocked,'textContent',()=>pickerMessage(key));blocked.hidden=!key;
    const unknown=!key&&schemaUnknown(model,context());uiText(schemaHint,'textContent',()=>unknown?t('models.schema_unknown'):'');schemaHint.hidden=!unknown;
  }
  function row(model){
    const check=selectable(model,context()),tr=el('tr',{role:'button',tabIndex:0,'data-model-id':model.id,'aria-pressed':String(model.id===modelInput.value)});
    if(!check.ok){tr.setAttribute('aria-disabled','true');tr.title=t(`models.blocked_${check.reason}`)}
    else if(schemaUnknown(model,context()))tr.title=t('models.schema_unknown');
    tr.append(el('td',{},el('span',{},model.name||model.id),el('small',{className:'model-picker-id'},model.id)),el('td',{},badgeList(model)),
      el('td',{className:'num'},formatContext(model.context_tokens)),el('td',{className:'num'},formatPrice(rate(model,'input'))),el('td',{className:'num'},formatPrice(rate(model,'output'))));
    tr.onclick=()=>choose(model);tr.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose(model)}};
    return tr;
  }
  function render(){
    const locked=schemaLocked(responseModeInput?.value),reports=providerReportsPrivacy(providerInput.value);
    schema.checked=locked||userSchema;schema.disabled=locked;privacy.disabled=!reports;privacyNote.hidden=reports;
    const all=bound()?[...catalog.values()]:[],read=SORT_KEYS[sortKey];
    // In JSON Schema mode the filter is locked on, but non-schema rows stay visible as blocked instead of hidden.
    const shown=filterModels(all,{query:query.value,uncensoredOnly:uncensored.checked,minPrivacy:privacy.value,schemaOnly:!locked&&userSchema},providerInput.value)
      .sort((a,b)=>{const x=read(a),y=read(b);if(x===y)return 0;if(x===null)return 1;if(y===null)return -1;return (x>y?1:-1)*direction});
    for(const th of heads)if(th.dataset.sort)th.setAttribute('aria-sort',th.dataset.sort===sortKey?(direction>0?'ascending':'descending'):'none');
    const empty=text=>el('tr',{},el('td',{colSpan:5,className:'settings-hint'},text));
    // Rows are rebuilt on every render; keep keyboard focus on the same model row.
    const focused=tbody.contains(document.activeElement)?document.activeElement.closest('tr[data-model-id]')?.dataset.modelId:null;
    tbody.replaceChildren(...(!all.length?[empty(t('models.catalog_empty'))]:shown.length?shown.map(row):[empty(t('models.no_match'))]));
    if(focused)[...tbody.rows].find(tr=>tr.dataset.modelId===focused)?.focus();
    foot.hidden=!all.length;foot.textContent=t('models.shown',{p0:shown.length,p1:all.length});
    toggle.setAttribute('aria-expanded',String(!panel.hidden));renderChosen();
  }
  // The catalog can change without an input event on the model field; dependants (consent block) re-read selected().
  const catalogChanged=()=>modelInput.dispatchEvent(new CustomEvent('model-catalog-changed'));
  function clear(){catalog=new Map();binding=null;message=null;render();catalogChanged()}
  toggle.onclick=()=>{panel.hidden=!panel.hidden;render()};
  schema.addEventListener('change',()=>{if(!schemaLocked(responseModeInput?.value))userSchema=schema.checked;render()});
  for(const control of [query,uncensored,privacy])control.addEventListener('input',render);
  for(const type of ['input','change'])modelInput.addEventListener(type,()=>{message=null;render()});
  providerInput.addEventListener('change',clear);baseUrlInput.addEventListener('input',clear);baseUrlInput.addEventListener('change',clear);
  responseModeInput?.addEventListener('change',()=>{message=null;render()});
  modelInput.form?.addEventListener('settings-reset',()=>{message=null;render()});
  // Forms are rebuilt on reload; a picker that was shown and then detached stops listening for locale changes.
  let attached=false;const onLocale=()=>{if(host.isConnected){attached=true;render()}else if(attached)document.removeEventListener('ui-locale-changed',onLocale)};document.addEventListener('ui-locale-changed',onLocale);
  render();bindLimits(limitInputs);
  return {capture:identity,bindLimits,clear,validate,update:render,selected:current,loaded:bound,open(){panel.hidden=false;render();toggle.focus()},setModels(models,captured){
    if(captured!==identity())return false;
    catalog=new Map(models.map(model=>[model.id,model]));binding=captured;message=null;panel.hidden=false;render();catalogChanged();return true;
  }};
}
