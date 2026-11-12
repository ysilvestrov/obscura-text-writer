import {confirmDialog} from './dialogs.js';
import {pickerMessage} from './model-picker.js';
import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,diagnostic} from './i18n.js';
import {api,json,notice} from './api.js';
import {mountConnection} from './settings-connection.js';
import {EvaluatorDraft,normalizeEvaluator,criterionLabels} from './evaluator-form-state.js';
import {settingsSignature} from './settings-state.js';
import {registerSettingsForm,withSettingsSave,settingsSaved,settingsChanged,settingsRebaseFields,settingsFormError} from './settings-workspace.js';

export async function installEvaluatorSettings(host,storyId){
  const base=`/api/stories/${storyId}/evaluator`;
  async function load(){
    let data,configured=true;
    try{data=await api(base)}catch(error){
      if(!/оцінювач не налаштовано/i.test(error.message))throw error;
      configured=false;data={config:{provider:'codex_cli',model:null,max_input_chars:100000},context_tokens:128000,policy:'off'};
    }
    let saved=normalizeEvaluator(data),draft=new EvaluatorDraft(data),block=data.block,updating=false;
    const form=document.createElement('form');form.id='evaluator-form';form.className='panel';
    uiHTML(form,"<p class=\"evaluation-state settings-status\" role=\"status\"></p><div class=\"settings-fields\"><label class=\"checkbox\"><input name=\"enabled\" type=\"checkbox\"> <span data-i18n=\"m_75a03055faba\">Увімкнути оцінювач · зберігається одразу</span></label><label><span data-i18n=\"m_dd9021de319d\">Режим роботи</span><select name=\"policy\"><option value=\"report\" data-i18n=\"m_2d6e318dc6c7\">Лише звіт</option><option value=\"pause_on_failure\" data-i18n=\"m_721c39fbca1b\">Пауза при проблемі</option></select><small class=\"calibration-state\"></small></label></div><p class=\"settings-notice\"><span data-i18n=\"m_708f7a788fd9\">Оцінювання не запускається від зміни налаштувань. Candidate-профіль дає попередній звіт, без підтвердження літературної якості.</span></p><fieldset class=\"evaluator-normal\"><legend><span data-i18n=\"m_100be6d3fc62\">Модель оцінювача</span></legend><div class=\"evaluator-connection\"></div><div class=\"settings-fields\"><label><span data-i18n=\"m_526a85b7766b\">Контекст, токенів</span><input name=\"context_tokens\" type=\"number\" min=\"1024\" step=\"1\" required></label><label><span data-i18n=\"m_11de327806c2\">Резерв відповіді, токенів</span><input name=\"max_output_tokens\" type=\"number\" min=\"1\" step=\"1\" required></label><label><span data-i18n=\"m_56f7653b8834\">Температура</span><input name=\"temperature\" type=\"number\" min=\"0\" max=\"2\" step=\"any\"><small><span data-i18n=\"m_09649a1e4889\">Порожнє поле — типове для провайдера.</span></small></label><label><span data-i18n=\"m_a1adc1cec8e7\">Ліміт входу, символів</span><input name=\"max_input_chars\" type=\"number\" min=\"1\" step=\"1\" required></label></div><details><summary><span data-i18n=\"m_c75a55f7ee4d\">Параметри Codex CLI</span></summary><label><span data-i18n=\"m_d48468e1e5a7\">Команда Codex</span><input name=\"codex_command\" required></label><p class=\"settings-hint\"><span data-i18n=\"m_60eacb3f36d4\">Codex CLI — засіб розробки; модель можна не задавати.</span></p></details><details><summary><span data-i18n=\"m_aa279d15c1a7\">Критерії та пороги</span></summary><p class=\"profile-status\"></p><button type=\"button\" class=\"secondary candidate\"><span data-i18n=\"m_26dbda2c80bd\">Створити профіль-кандидат</span></button><fieldset class=\"scoring-fields\"><legend><span data-i18n=\"m_c1e4bd7ede4c\">Профіль оцінювання</span></legend><label><span data-i18n=\"m_919b5269a2c8\">Версія профілю</span><input name=\"profile_version\"></label><table class=\"evaluator-thresholds\"><thead><tr><th><span data-i18n=\"m_aa71ce873e61\">Критерій</span></th><th><span data-i18n=\"m_3f47ad13a926\">Мінімум 0–4</span></th></tr></thead><tbody></tbody></table><label><span data-i18n=\"m_8a9306d0a034\">Мінімальна довжина цитати</span><input name=\"min_quote_chars\" type=\"number\" min=\"1\" step=\"1\" required></label><div class=\"blocking-levels\"></div></fieldset><details><summary><span data-i18n=\"m_9e6601f2f3e5\">Походження калібрування</span></summary><pre class=\"calibration-metadata\"></pre></details></details></fieldset><details class=\"raw-settings\"><summary><span data-i18n=\"m_1f1987b3c0f4\">Технічний JSON · необов’язково</span></summary><p class=\"settings-hint\"><span data-i18n=\"m_a24250aeef56\">Правки JSON застосовуються явно. До застосування або відкидання звичайні поля й збереження заблоковані.</span></p><label><span data-i18n=\"m_abd2bf068fb5\">Конфігурація JSON</span><textarea name=\"evaluator_json\" rows=\"12\" spellcheck=\"false\" data-derived=\"true\"></textarea></label><div class=\"actions\"><button type=\"button\" class=\"secondary raw-apply\"><span data-i18n=\"m_cf9792634402\">Застосувати JSON</span></button><button type=\"button\" class=\"secondary raw-discard\"><span data-i18n=\"m_09011f0a3405\">Відкинути правки JSON</span></button></div><p class=\"raw-error form-error\" role=\"alert\"></p></details><p class=\"form-error evaluator-error\" role=\"alert\"></p><button type=\"submit\" class=\"scope-submit\"><span data-i18n=\"m_b92a405d3ebb\">Зберегти оцінювача</span></button>",{});
    const f=form.elements,normal=form.querySelector('.evaluator-normal'),raw=f.evaluator_json,error=form.querySelector('.evaluator-error'),rawError=form.querySelector('.raw-error');
    const connection=mountConnection(form.querySelector('.evaluator-connection'),{value:saved.config,kind:'evaluator',prefix:'eval_',onChange:()=>{if(!updating)fromFields()}});
    connection.picker.bindLimits({context_tokens:f.context_tokens,max_output_tokens:f.max_output_tokens});
    const rows=form.querySelector('.evaluator-thresholds tbody');
    for(const[id,label]of labelEntries(criterionLabels)){
      const row=document.createElement('tr'),name=document.createElement('td'),cell=document.createElement('td'),input=document.createElement('input');uiText(name,"textContent",()=>(label));input.name='score_'+id;input.type='number';input.min='0';input.max='4';input.step='1';uiAttr(input,'aria-label',()=>(t("m_2bda29f1fce4")+label));cell.append(input);row.append(name,cell);rows.append(row);
    }
    for(const[value,label]of [['minor',msg("m_cea352394285")],['major',msg("m_2335825a0608")],['critical',msg("m_a09dd05bf8c5")]]){
      const l=document.createElement('label');l.className='checkbox';uiHTML(l,`<input type="checkbox" name="blocking_${value}">`,{p0:(value)});const caption=document.createElement('span');uiText(caption,'textContent',()=>label);l.append(caption);form.querySelector('.blocking-levels').append(l);
    }
    function meta(){
      uiText(form.querySelector('.evaluation-state'),"textContent",()=>(block?t("m_d53e5d32a657")+diagnostic(block.failure.message):saved.policy==='off'?t("m_a305f6eb6fb1"):t("m_75ca469b05a8")+(saved.policy==='report'?t("m_14833a5f715e"):t("m_76cac4bc1edd"))));
      const eligible=draft.current.profile.calibrated&&!draft.calibrationLost();
      f.policy.querySelector('[value=pause_on_failure]').disabled=!eligible;
      uiText(form.querySelector('.calibration-state'),"textContent",()=>(eligible?t("m_5a78a49bdba1"):draft.calibrationLost()?t("m_0f52a29b7504"):t("m_5e3b3dea465d")));
      uiText(form.querySelector('.profile-status'),"textContent",()=>(draft.current.profile.calibrated?t("m_6b05a2f83e4b"):t("m_1b7ca7d50566")));
      form.querySelector('.scoring-fields').disabled=draft.current.profile.calibrated;
      form.querySelector('.candidate').hidden=!draft.current.profile.calibrated;
      uiText(form.querySelector('.calibration-metadata'),"textContent",()=>(JSON.stringify({calibrated:draft.current.profile.calibrated,evaluator_fingerprint:draft.current.profile.evaluator_fingerprint,calibration_fingerprint:draft.current.profile.calibration_fingerprint},null,2)));
      normal.disabled=draft.rawPending;form.dataset.rawPending=String(draft.rawPending);
      f.policy.disabled=draft.rawPending;
      form.dataset.saveBlocked=String(draft.rawPending||draft.current.policy==='pause_on_failure'&&!eligible);
      form.querySelector('.raw-apply').disabled=!draft.rawPending;form.querySelector('.raw-discard').disabled=!draft.rawPending;
    }
    function write(){
      updating=true;const s=draft.current;connection.write(s.config);
      f.enabled.checked=s.policy!=='off';f.policy.value=s.policy==='off'?'report':s.policy;
      f.context_tokens.value=s.context_tokens;for(const key of ['max_output_tokens','max_input_chars','temperature','codex_command'])f[key].value=s.config[key]??'';
      f.profile_version.value=s.profile.version;f.min_quote_chars.value=s.profile.min_quote_chars;
      for(const id of Object.keys(criterionLabels))f['score_'+id].value=s.profile.minimum_scores[id]??'';
      for(const severity of ['minor','major','critical'])f['blocking_'+severity].checked=s.profile.blocking_severities.includes(severity);
      raw.value=draft.rawText;updating=false;meta();
    }
    function fromFields(){
      if(updating||draft.rawPending)return;
      try{
        const config={...connection.read(),max_output_tokens:Number(f.max_output_tokens.value),max_input_chars:Number(f.max_input_chars.value),temperature:f.temperature.value===''?null:Number(f.temperature.value),codex_command:f.codex_command.value};
        const profile={...draft.current.profile,version:f.profile_version.value,min_quote_chars:Number(f.min_quote_chars.value),minimum_scores:Object.fromEntries(Object.keys(criterionLabels).filter(id=>f['score_'+id].value!=='').map(id=>[id,Number(f['score_'+id].value)])),blocking_severities:(()=>{const selected=['minor','major','critical'].filter(k=>f['blocking_'+k].checked);return settingsSignature([...new Set(draft.current.profile.blocking_severities)].sort())===settingsSignature([...selected].sort())?draft.current.profile.blocking_severities:selected})()};
        draft.patch({config,context_tokens:Number(f.context_tokens.value),profile,policy:f.enabled.checked?f.policy.value:'off'});raw.value=draft.rawText;uiText(error,"textContent",()=>(''));
      }catch(problem){uiText(error,"textContent",()=>(diagnostic(problem.message)))}
      meta();settingsChanged('evaluator');
    }
    form.addEventListener('input',event=>{if(event.target===raw){draft.setRaw(raw.value);meta();settingsChanged('evaluator')}else if(event.target!==f.enabled)fromFields()});
    form.addEventListener('change',event=>{if(event.target!==f.enabled&&event.target!==raw)fromFields()});
    form.addEventListener('settings-unlocked',()=>{connection.update();meta()});
    form.querySelector('.raw-apply').onclick=()=>{try{draft.applyRaw();write();uiText(rawError,"textContent",()=>(''));settingsChanged('evaluator')}catch(problem){uiText(rawError,"textContent",()=>(diagnostic(problem.message)))}};
    form.querySelector('.raw-discard').onclick=()=>{draft.discardRaw();write();uiText(rawError,"textContent",()=>(''));settingsChanged('evaluator')};
    form.querySelector('.candidate').onclick=async()=>{if(await confirmDialog(t("m_be93656b233e"))){try{draft.makeCandidate();write();settingsChanged('evaluator')}catch(problem){uiText(error,"textContent",()=>(diagnostic(problem.message)))}}};
    f.enabled.onchange=async()=>{
      const enabled=f.enabled.checked,policy=enabled?f.policy.value:'off';
      if(enabled&&!await confirmDialog(t("m_5f7d10cf524a",{p0:(saved.config.provider),p1:(saved.config.model||t("m_c2a15f0686c0")),p2:(configured?'':t("m_32ad2eb54918"))}))){f.enabled.checked=saved.policy!=='off';settingsChanged('evaluator');return}
      try{
        await withSettingsSave('evaluator',async()=>{
          const result=await draft.savePolicy(policy,value=>api(base+'/policy',json('PUT',{policy:value})));saved=normalizeEvaluator(result);configured=true;block=result.block;
          f.enabled.checked=result.policy!=='off';if(result.policy!=='off')f.policy.value=result.policy;
          if(!draft.rawPending)raw.value=draft.rawText;meta();settingsRebaseFields('evaluator',['enabled','policy']);
          document.dispatchEvent(new CustomEvent('evaluation-policy-changed'));notice(result.policy==='off'?t("m_aa4eb4e4596f"):t("m_857c0ba39928"));
        });
      }catch(problem){f.enabled.checked=saved.policy!=='off';uiText(error,"textContent",()=>(diagnostic(problem.message)));settingsChanged('evaluator')}
    };
    form.onsubmit=async event=>{
      event.preventDefault();fromFields();
      try{
        const blocked=connection.validate();if(blocked)throw new Error(pickerMessage(blocked));
        const payload=draft.read();
        await withSettingsSave('evaluator',async()=>{
          if(configured){const latest=normalizeEvaluator(await api(base));if(settingsSignature(latest)!==settingsSignature(saved))throw new Error(t("m_89114026ce6a"))}
          await api(base,json('PUT',payload));settingsSaved('evaluator');await load();document.dispatchEvent(new CustomEvent('evaluation-policy-changed'));notice(msg("m_cf4bb91e1be3"));
        });
      }catch(problem){uiText(error,"textContent",()=>(diagnostic(problem.message)));settingsFormError('evaluator',problem);notice(problem.message,'error')}
    };
    write();host.replaceChildren(form);registerSettingsForm('evaluator',{form,label:live(()=>(t("m_04c7075b6943"))),section:'evaluator',reset:load});
  }
  try{await load()}catch(error){
    host.replaceChildren();const message=document.createElement('p'),retry=document.createElement('button');message.className='form-error';uiText(message,"textContent",()=>(t("m_fc62f37ea979")+diagnostic(error.message)));retry.type='button';uiText(retry,"textContent",()=>(t("m_9d423dc847c8")));retry.onclick=()=>installEvaluatorSettings(host,storyId);host.append(message,retry);
  }
}
