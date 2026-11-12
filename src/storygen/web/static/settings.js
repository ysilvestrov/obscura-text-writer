import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,uiInsertHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {registerSettingsForm,settingsSaved,withSettingsSave,settingsChanged,settingsRebaseFields,confirmSettingsReplacement,settingsFormError} from './settings-workspace.js';
import {settingsSignature,expectedPromptContract} from './settings-state.js';
import {mountClassification} from './classification-settings.js';
import {groupRoleFields} from './settings-role-layout.js';
import {mountHorizonControls} from './horizon-controls.js';
import {mountModelPicker,pickerMessage} from './model-picker.js';
import {mountModelPolicy} from './model-policy.js';
import {mountProviderKey} from './provider-key.js';
import {mountWriterVariant} from './writer-variant.js';
const root=document.querySelector('[data-story-id]'),id=root.dataset.storyId;
const names={get planner(){return t("m_38c94c25c4af")},get writer(){return t("m_75515c07207a")},get editor(){return t("m_19e99ed8f039")},get memory(){return t("m_aa1cfb48cc30")}};
const defaults={provider:{provider:'local',base_url:'http://localhost:1235/v1',model:'',timeout:3600,key_env:'OPENROUTER_API_KEY',include_usage:false,response_mode:'prompt_json'},context_tokens:8192,max_output_tokens:2048,max_input_chars:80000,temperature:0.7,prompt_version_id:null,prepare_prompt_version_id:null};
let snapshot,profileBaseline;
const providerNames=['provider','base_url','model','timeout','key_env','response_mode','include_usage','local_disable_thinking','venice_include_system_prompt','venice_disable_thinking','venice_reasoning_effort'];
const roleScope=(data,role)=>({settings:data.roles[role]||null,prompt:data.prompts[role]||'',prepare:role==='planner'?data.prepare_prompt:null,contract:data.prompt_contracts?.[role]||null});
async function checkScope(role,baseline,shared=false){
 const latest=await api(`/api/stories/${id}/settings`);
 if(settingsSignature(role==='writing'?{profile:latest.profile,target_words:latest.story.target_words}:roleScope(latest,role))!==settingsSignature(baseline))throw new Error(t("m_01f8b6c01617"));
 if(shared)for(const other of document.querySelectorAll('form[data-role]'))if(other.dataset.role!==role&&settingsSignature(roleScope(latest,other.dataset.role))!==settingsSignature(other.serverBaseline))throw new Error(t("m_e92bbe8c4cb8"));
 return latest.story.revision;
}
async function load(onlyRole=null){
  snapshot=await api(`/api/stories/${id}/settings`);
  const profileForm=document.querySelector('#profile-form');if(!onlyRole||onlyRole==='writing'){for(const[key,value]of Object.entries(snapshot.profile))profileForm.elements[key].value=value;profileForm.elements.target_words.value=snapshot.story.target_words;profileBaseline=structuredClone({profile:snapshot.profile,target_words:snapshot.story.target_words});registerSettingsForm('writing',{form:profileForm,label:live(()=>(t("m_88f778367baf"))),section:'writing',reset:()=>load('writing')})}
  const target=document.querySelector('#role-settings');if(!onlyRole)target.replaceChildren();
  for(const[role,name]of labelEntries(names)){
    if(onlyRole&&role!==onlyRole)continue;
    const config=snapshot.roles[role]||structuredClone(defaults),form=document.createElement('form');form.className='panel role-form';form.dataset.role=role;form.serverBaseline=structuredClone(roleScope(snapshot,role));
    uiHTML(form,"<h2></h2><label><span data-i18n=\"m_2d385af6d69b\">Провайдер</span><select name=\"provider\"><option value=\"local\" data-i18n=\"m_63156f17fb93\">Локальний API</option><option value=\"openrouter\">OpenRouter</option><option value=\"venice\">Venice · uncensored=true</option></select></label><label>Base URL<input name=\"base_url\" required></label><label><span data-i18n=\"m_4ad7dbb43159\">Змінна середовища з ключем</span><input name=\"key_env\"><small><span data-i18n=\"m_057feec1bfee\">Лише назва змінної, без значення ключа.</span></small></label><label>Model ID<input name=\"model\" required></label><div class=\"model-picker\"></div><button type=\"button\" class=\"secondary discover\"><span data-i18n=\"m_bb570a85efbc\">Отримати список моделей</span></button><label><span data-i18n=\"m_a5e1bed8c89a\">Перевірений контекст, токенів</span><input name=\"context_tokens\" type=\"number\" min=\"512\" required></label><label><span data-i18n=\"m_11de327806c2\">Резерв відповіді, токенів</span><input name=\"max_output_tokens\" type=\"number\" min=\"1\" required></label><label><span data-i18n=\"m_c8f9fea4d67c\">Операційний ліміт входу, символів</span><input name=\"max_input_chars\" type=\"number\" min=\"1\" required></label><label><span data-i18n=\"m_56f7653b8834\">Температура</span><input name=\"temperature\" type=\"number\" min=\"0\" max=\"2\" step=\"any\" required></label><label><span data-i18n=\"m_ae883a01f59f\">Timeout, секунд</span><input name=\"timeout\" type=\"number\" min=\"0.001\" step=\"any\"></label><label><span data-i18n=\"m_fa279e215359\">Структуровані відповіді</span><select name=\"response_mode\"><option value=\"prompt_json\" data-i18n=\"m_ba14990fda9a\">JSON за промптом</option><option value=\"json_schema\" data-i18n=\"m_f879e7ffc740\">JSON Schema (endpoint має підтримувати)</option></select></label><label><input name=\"include_usage\" type=\"checkbox\"> <span data-i18n=\"m_b4ebc128e2fb\">Запитувати usage потоку (якщо підтримується)</span></label><label><span data-i18n=\"m_78196b7df642\">Промпт ролі</span><textarea name=\"prompt_text\" rows=\"4\" placeholder=\"Стандартний промпт, якщо поле порожнє\" data-i18n-attrs='{\"placeholder\":\"m_d97aa9664d44\"}'></textarea></label>",{});
    if(role==='planner')uiInsertHTML(form,'beforeend',"<label><span data-i18n=\"m_d3594f6b0020\">Окремий промпт підготовки структури</span><textarea name=\"prepare_prompt_text\" rows=\"4\" placeholder=\"Стандартний промпт підготовки\" data-i18n-attrs='{\"placeholder\":\"m_ddd756ac7c81\"}'></textarea></label>");
    if(role==='editor')uiInsertHTML(form,'beforeend',"<label><span data-i18n=\"m_1957022cf52c\">Режим редактора</span><select name=\"edit_mode\"><option value=\"prose\" data-i18n=\"m_237991f9d28d\">Повна літературна версія</option><option value=\"patches\" data-i18n=\"m_fb139d04582b\">Точкові мовні правки</option><option value=\"diff\" data-i18n=\"m_44f181c12a60\">Редактура з переглядом змін</option></select></label><p><span data-i18n=\"m_65dbe06c0d53\">Режим перегляду повертає звичайний текст без JSON Schema. Програма виділяє зміни й завжди чекає авторського рішення.</span></p>");
    if(role==='editor')uiInsertHTML(form,'beforeend',"<label><span data-i18n=\"m_9306e22d8bfb\">Застосування точкових правок</span><select name=\"edit_review\"><option value=\"auto\" data-i18n=\"m_a45a12fa5f5a\">Автоматично після перевірки</option><option value=\"review\" data-i18n=\"m_fe373cb07534\">Спочатку перегляд автором</option></select></label><p><span data-i18n=\"m_6bbd41ee0dce\">Перегляд стосується точкових правок. Workflow чекатиме на вибір і явне продовження.</span></p>");
    if(role==='memory')uiInsertHTML(form,'beforeend',"<label><span data-i18n=\"m_839c80ab7eef\">Режим пам’яті</span><select name=\"memory_mode\"><option value=\"evidence_delta\" data-i18n=\"memory.mode.evidence_delta_v4\">Операції пам’яті v4 за доказами</option></select><small class=\"settings-hint\"><span data-i18n=\"memory.mode.schema_hint\">Для моделей, що підтримують схему, оберіть режим відповіді json_schema — він унеможливлює більшість помилок формату.</span></small></label>");
    if(role==='editor'||role==='memory'){const hint=document.createElement('p');uiText(hint,"textContent",()=>(t("m_2a38a1b3e96e")));form.append(hint);}
    const horizonControls=mountHorizonControls(form,role,config);
    uiInsertHTML(form,'beforeend',"<fieldset class=\"venice-options\"><legend>Venice</legend><label><input type=\"checkbox\" name=\"venice_include_system_prompt\"> <span data-i18n=\"m_4195bd21fe9b\">Додавати системний промпт Venice</span></label><label><input type=\"checkbox\" name=\"venice_disable_thinking\"> <span data-i18n=\"m_914397a43529\">Вимкнути thinking (якщо модель підтримує)</span></label><p><span data-i18n=\"m_5e1cfcc38605\">Лише моделі з uncensored=true. Вебпошук вимкнено.</span></p></fieldset>");
    uiInsertHTML(form.querySelector('.venice-options'),'beforeend',"<label>Reasoning effort<select name=\"venice_reasoning_effort\"><option value=\"\" data-i18n=\"m_0d9ad3f0a130\">Типове для моделі</option><option value=\"none\">none</option><option value=\"low\">low</option><option value=\"medium\">medium</option><option value=\"high\">high</option><option value=\"xhigh\">xhigh</option><option value=\"max\">max</option></select></label><p><span data-i18n=\"m_e4d40b1373e8\">Залежить від моделі. Виберіть або effort, або вимкнення thinking.</span></p>");
    for(const key of ['venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=config.provider[key]||false;
    form.elements.venice_reasoning_effort.value=config.provider.venice_reasoning_effort||'';
    const updateEffort=()=>{form.elements.venice_reasoning_effort.disabled=form.elements.venice_disable_thinking.checked;if(form.elements.venice_disable_thinking.checked)form.elements.venice_reasoning_effort.value=''};
    form.elements.venice_disable_thinking.onchange=updateEffort;updateEffort();
    uiInsertHTML(form,'beforeend','<label class="local-options"><input type="checkbox" name="local_disable_thinking"> <span data-i18n="m_d11a85d919fd">Вимкнути thinking</span> (reasoning_effort=none)</label>');
    form.elements.local_disable_thinking.checked=!!config.provider.local_disable_thinking;
    const classification=role==='editor'?mountClassification(form,config.classification):null;
    const vendorVisibility=()=>{form.querySelector('.venice-options').hidden=form.elements.provider.value!=='venice';form.querySelector('.local-options').hidden=form.elements.provider.value!=='local'};
    uiInsertHTML(form,'beforeend',"<label><input type=\"checkbox\" name=\"shared_provider\"> <span data-i18n=\"m_eebf11e6a0f9\">Застосувати цю модель та її підключення до всіх 4 ролей</span></label><p><span data-i18n=\"m_326a237b045f\">Промпти, режими та ліміти інших ролей зберігаються.</span></p>");
    const save=document.createElement('button');save.type='submit';save.className='scope-submit';uiText(save,"textContent",()=>(t("m_32c3e22963bc")));form.append(save);
    uiText(form.querySelector('h2'),"textContent",()=>(name));
    if(role==='editor')form.elements.edit_mode.value=config.edit_mode||'prose';
    if(role==='editor')form.elements.edit_review.value=config.edit_review||'auto';
    if(role==='memory')form.elements.memory_mode.value=config.memory_mode||'evidence_delta';
    for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])form.elements[field].value=config[field];
    for(const field of ['provider','base_url','model','timeout','key_env','response_mode'])form.elements[field].value=config.provider[field];
    form.elements.include_usage.checked=config.provider.include_usage; const stopLabel=document.createElement('label');uiText(stopLabel,"textContent",()=>(t("m_194ab523d2bd")));const stopInput=document.createElement('textarea');stopInput.name='stop_sequences';stopInput.rows=2;stopInput.value=(config.stop_sequences||[]).join('\n');stopLabel.append(stopInput);form.insertBefore(stopLabel,save);
    const originalPrompt=snapshot.prompts[role]||'',originalPrepare=snapshot.prepare_prompt||'';
    form.elements.prompt_text.value=originalPrompt;if(role==='planner')form.elements.prepare_prompt_text.value=originalPrepare;
    const contract=document.createElement('p');contract.dataset.promptMeta='true';contract.className='muted';form.elements.prompt_text.parentElement.after(contract);
    const assignment=document.createElement('label');const assignInput=document.createElement('input');assignInput.type='checkbox';assignInput.name='confirm_prompt_contract';assignment.append(assignInput,caption("m_90e681732477"));contract.after(assignment);
    const reset=document.createElement('button');reset.type='button';reset.dataset.promptMeta='true';reset.className='secondary';uiText(reset,"textContent",()=>(t("m_630a80f8c628")));assignment.after(reset);const upgradeWrap=document.createElement('div');upgradeWrap.dataset.promptMeta='true';upgradeWrap.hidden=true;const upgradeLabel=document.createElement('label'),upgradeInput=document.createElement('input'),upgradeText=document.createElement('span'),upgradeHelp=document.createElement('p');upgradeInput.type='checkbox';upgradeInput.name='upgrade_memory_wire';uiText(upgradeText,'textContent',()=>t('memory.prompt.upgrade_v4'));upgradeLabel.append(upgradeInput,' ',upgradeText);upgradeHelp.className='muted';uiText(upgradeHelp,'textContent',()=>t('memory.prompt.upgrade_v4_help'));upgradeWrap.append(upgradeLabel,upgradeHelp);assignment.after(upgradeWrap);
    reset.onclick=()=>{form.elements.prompt_text.value='';assignInput.checked=false;upgradeInput.checked=false;updateContract();settingsChanged(role)};
    const stage={planner:'brief',writer:'draft',editor:'edit',memory:'memory'}[role];
    function updateContract(){const mode=role==='editor'?form.elements.edit_mode.value:role==='memory'?form.elements.memory_mode.value:role==='planner'?'brief':'prose';const stored=snapshot.prompt_contracts?.[role];const storedOld=role==='memory'&&mode==='evidence_delta'&&!!config.prompt_version_id&&stored?.stage==='memory'&&stored?.mode==='evidence_delta'&&[2,3].includes(stored?.schema_version);upgradeWrap.hidden=!storedOld;if(!storedOld)upgradeInput.checked=false;const expected=expectedPromptContract(stage,mode,stored,config.prompt_version_id,form.elements.prompt_text.value,upgradeInput.checked);const saved=config.prompt_version_id?(stored?`${stored.stage}/${stored.mode}/${stored.schema_version}`:t("m_28a26271f7e7")):t("m_fcedf84d6354");uiText(contract,"textContent",()=>(t("m_6b2c1a90724c",{p0:(expected),p1:(saved)})))}
    for(const field of ['edit_mode','memory_mode'])if(form.elements[field])form.elements[field].onchange=()=>{if(!config.prompt_version_id&&form.elements.prompt_text.value===originalPrompt)form.elements.prompt_text.value='';assignInput.checked=false;upgradeInput.checked=false;updateContract()};
    upgradeInput.onchange=updateContract;
    form.elements.prompt_text.addEventListener('input',updateContract);updateContract();
    if(role==='planner'){const prepareAssignment=document.createElement('label');const input=document.createElement('input');input.type='checkbox';input.name='confirm_prepare_prompt_contract';prepareAssignment.append(input,caption("m_083894cf6717"));form.elements.prepare_prompt_text.parentElement.after(prepareAssignment)}
    form.applyProvider=value=>{config.provider=structuredClone(value);for(const key of ['provider','base_url','model','timeout','key_env','response_mode'])form.elements[key].value=value[key];for(const key of ['include_usage','local_disable_thinking','venice_include_system_prompt','venice_disable_thinking'])form.elements[key].checked=value[key]||false;form.elements.venice_reasoning_effort.value=value.venice_reasoning_effort||'';updateEffort();vendorVisibility();catalog.clear();form.providerKey?.refresh()};
    if(role==='editor'){
      const updateReview=()=>{const manual=form.elements.edit_mode.value==='diff';form.elements.edit_review.disabled=manual;form.elements.edit_review.closest('label').hidden=form.elements.edit_mode.value!=='patches';if(manual)form.elements.edit_review.value='review'};
      const previous=form.elements.edit_mode.onchange;form.elements.edit_mode.onchange=()=>{previous?.();updateReview()};updateReview();
    }
    vendorVisibility();
    form.elements.provider.onchange=()=>{const selected=form.elements.provider.value;form.elements.base_url.value={local:'http://localhost:1235/v1',openrouter:'https://openrouter.ai/api/v1',venice:'https://api.venice.ai/api/v1'}[selected];form.elements.timeout.value=selected==='local'?3600:180;form.elements.key_env.value=selected==='venice'?'VENICE_API_KEY':'OPENROUTER_API_KEY';vendorVisibility()};
    const provider=()=>({...config.provider,provider:form.elements.provider.value,key_env:form.elements.key_env.value||null,local_disable_thinking:form.elements.local_disable_thinking.checked,venice_include_system_prompt:form.elements.venice_include_system_prompt.checked,venice_disable_thinking:form.elements.venice_disable_thinking.checked,venice_reasoning_effort:form.elements.venice_reasoning_effort.value||null,model:form.elements.model.value||'discovery-only',base_url:form.elements.base_url.value,timeout:form.elements.timeout.value===''?null:Number(form.elements.timeout.value),response_mode:form.elements.response_mode.value,include_usage:form.elements.include_usage.checked});
    const catalog=mountModelPicker({host:form.querySelector('.model-picker'),modelInput:form.elements.model,providerInput:form.elements.provider,baseUrlInput:form.elements.base_url,responseModeInput:form.elements.response_mode,limitInputs:{context_tokens:form.elements.context_tokens,max_output_tokens:form.elements.max_output_tokens}});
    // MODEL-003/MODEL-004: consent and refusal mark sit under the chosen model and travel with the picker in the layout.
    const policyHost=document.createElement('div');form.querySelector('.model-picker').append(policyHost);
    mountModelPolicy({host:policyHost,role,modelInput:form.elements.model,providerInput:form.elements.provider,baseUrlInput:form.elements.base_url,picker:catalog});
    form.querySelector('.discover').onclick=async()=>{
      const button=form.querySelector('.discover'),captured=catalog.capture();button.disabled=true;
      try{const result=await api('/api/providers/discover',json('POST',provider()));if(!catalog.setModels(result.models,captured))throw new Error(t('m_b6361b46aced'));notice(t('m_8d511fd9fc01',{p0:result.models.length}));}
      catch(e){notice(e.message,'error')}finally{button.disabled=false}
    };
    form.onsubmit=async event=>{
      event.preventDefault();
      try{
        const blocked=catalog.validate();if(blocked)throw new Error(pickerMessage(blocked));
        const settings={...config,...horizonControls.read(),provider:provider(),stop_sequences:form.elements.stop_sequences.value.split(/\r?\n/).filter(value=>value.length>0)};for(const field of ['context_tokens','max_output_tokens','max_input_chars','temperature'])settings[field]=Number(form.elements[field].value);
        if(role==='editor')settings.edit_mode=form.elements.edit_mode.value;
        if(role==='editor')settings.edit_review=form.elements.edit_review.value;
        if(role==='editor')settings.classification=classification.read();
        if(role==='memory')settings.memory_mode=form.elements.memory_mode.value;
        if(role==='writer')settings.low_rating_variant=variant.read();
        const body={expected_revision:snapshot.story.revision,role,settings};
        body.confirm_prompt_contract=form.elements.confirm_prompt_contract.checked;
        if(upgradeInput.checked&&!upgradeWrap.hidden){body.upgrade_memory_wire=true;body.confirm_prompt_contract=true}
        if(role==='planner')body.confirm_prepare_prompt_contract=form.elements.confirm_prepare_prompt_contract.checked;
        if(form.elements.prompt_text.value!==originalPrompt)body.prompt_text=form.elements.prompt_text.value;
        if(role==='planner'&&form.elements.prepare_prompt_text.value!==originalPrepare)body.prepare_prompt_text=form.elements.prepare_prompt_text.value;
        const shared=form.elements.shared_provider.checked;
        const others=[...target.querySelectorAll('form[data-role]')].filter(other=>other!==form);
        if(shared&&!await confirmSettingsReplacement(others.map(other=>other.dataset.role),providerNames))return;
        await withSettingsSave(role,async()=>{
          body.expected_revision=await checkScope(role,form.serverBaseline,shared);
          if(shared){body.provider=provider();snapshot.story=await api(`/api/stories/${id}/settings/shared-provider`,json('PUT',body));for(const other of others){other.applyProvider(body.provider);settingsRebaseFields(other.dataset.role,providerNames)}}
          else snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',body));
          settingsSaved(role);await load(role);
          if(shared)for(const other of others)other.serverBaseline=structuredClone(roleScope(snapshot,other.dataset.role));
          notice(shared?t("m_34d0e77fcf4b"):t("m_3face1913579"));
        });
      }catch(e){settingsFormError(role,e);notice(e.message,'error')}
    };
    form.addEventListener('settings-reset',()=>{vendorVisibility();updateEffort();horizonControls.update();updateContract()});
    form.addEventListener('settings-unlocked',()=>{vendorVisibility();updateEffort();horizonControls.update()});
    const reserve=groupRoleFields(form,role);
    // SECURITY-002: the key block sits right under the main fields, outside the collapsed details.
    const keyHost=document.createElement('div');form.querySelector(':scope > .settings-fields').after(keyHost);
    form.providerKey=mountProviderKey(keyHost,{nameField:form.elements.key_env,providerField:form.elements.provider,i18n:{t,uiText,diagnostic},request:api});
    // MODEL-001: the optional model for scenes rated 0–1 sits under the main model; the main hint names who writes level 2.
    let variant=null;
    if(role==='writer'){const mainHint=document.createElement('p');mainHint.className='settings-hint';uiText(mainHint,'textContent',()=>t('writer.variant.main_hint'));form.querySelector('h2').after(mainHint);variant=mountWriterVariant(form,config);reserve.after(variant.block)}
    form.providerKey.refresh();for(const type of ['settings-reset','settings-unlocked'])form.addEventListener(type,()=>form.providerKey.refresh());
    horizonControls.update();
    const previous=target.querySelector(`[data-role="${role}"]`);if(previous)previous.replaceWith(form);else target.append(form);registerSettingsForm(role,{form,label:name,section:'models',reset:()=>load(role)});
  }
  document.querySelector('#settings-loading').hidden=true;document.dispatchEvent(new CustomEvent('workspace-settings-loaded'));
}
document.querySelector('#profile-form button').classList.add('scope-submit');
document.querySelector('#profile-form').onsubmit=async event=>{
 event.preventDefault();const form=event.target;
 const profile=Object.fromEntries([...form.elements].filter(e=>e.name&&e.name!=='target_words').map(e=>[e.name,e.value]));const target_words=Number(form.elements.target_words.value);profile.previous_tail_chars=Number(profile.previous_tail_chars);
 try{await withSettingsSave('writing',async()=>{const revision=await checkScope('writing',profileBaseline);snapshot.story=await api(`/api/stories/${id}/settings`,json('PUT',{expected_revision:revision,profile,target_words}));settingsSaved('writing');await load('writing');notice(msg("m_01e9934fcb2b"))})}catch(e){settingsFormError('writing',e);notice(e.message,'error')}
};
load().catch(e=>{uiText(document.querySelector('#settings-loading'),"textContent",()=>(diagnostic(e.message)));notice(e.message,'error')});
// The story language changes default role prompts: rebuild role forms so their baselines match the server (#32).
document.addEventListener('story-language-changed',()=>load().catch(e=>notice(e.message,'error')));

function caption(key){const span=document.createElement('span');uiText(span,'textContent',()=>t(key));return span}
