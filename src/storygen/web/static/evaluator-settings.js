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
    form.innerHTML='<p class="evaluation-state settings-status" role="status"></p><div class="settings-fields"><label class="checkbox"><input name="enabled" type="checkbox"> Увімкнути оцінювач · зберігається одразу</label><label>Режим роботи<select name="policy"><option value="report">Лише звіт</option><option value="pause_on_failure">Пауза при проблемі</option></select><small class="calibration-state"></small></label></div><p class="settings-notice">Оцінювання не запускається від зміни налаштувань. Candidate-профіль дає попередній звіт, без підтвердження літературної якості.</p><fieldset class="evaluator-normal"><legend>Модель оцінювача</legend><div class="evaluator-connection"></div><div class="settings-fields"><label>Контекст, токенів<input name="context_tokens" type="number" min="1024" step="1" required></label><label>Резерв відповіді, токенів<input name="max_output_tokens" type="number" min="1" step="1" required></label><label>Температура<input name="temperature" type="number" min="0" max="2" step="any"><small>Порожнє поле — типове для провайдера.</small></label><label>Ліміт входу, символів<input name="max_input_chars" type="number" min="1" step="1" required></label></div><details><summary>Параметри Codex CLI</summary><label>Команда Codex<input name="codex_command" required></label><p class="settings-hint">Codex CLI — засіб розробки; модель можна не задавати.</p></details><details><summary>Критерії та пороги</summary><p class="profile-status"></p><button type="button" class="secondary candidate">Створити профіль-кандидат</button><fieldset class="scoring-fields"><legend>Профіль оцінювання</legend><label>Версія профілю<input name="profile_version"></label><table class="evaluator-thresholds"><thead><tr><th>Критерій</th><th>Мінімум 0–4</th></tr></thead><tbody></tbody></table><label>Мінімальна довжина цитати<input name="min_quote_chars" type="number" min="1" step="1" required></label><div class="blocking-levels"></div></fieldset><details><summary>Походження калібрування</summary><pre class="calibration-metadata"></pre></details></details></fieldset><details class="raw-settings"><summary>Технічний JSON · необов’язково</summary><p class="settings-hint">Правки JSON застосовуються явно. До застосування або відкидання звичайні поля й збереження заблоковані.</p><label>Конфігурація JSON<textarea name="evaluator_json" rows="12" spellcheck="false" data-derived="true"></textarea></label><div class="actions"><button type="button" class="secondary raw-apply">Застосувати JSON</button><button type="button" class="secondary raw-discard">Відкинути правки JSON</button></div><p class="raw-error form-error" role="alert"></p></details><p class="form-error evaluator-error" role="alert"></p><button type="submit" class="scope-submit">Зберегти оцінювача</button>';
    const f=form.elements,normal=form.querySelector('.evaluator-normal'),raw=f.evaluator_json,error=form.querySelector('.evaluator-error'),rawError=form.querySelector('.raw-error');
    const connection=mountConnection(form.querySelector('.evaluator-connection'),{value:saved.config,kind:'evaluator',prefix:'eval_',onChange:()=>{if(!updating)fromFields()}});
    const rows=form.querySelector('tbody');
    for(const[id,label]of Object.entries(criterionLabels)){
      const row=document.createElement('tr'),name=document.createElement('td'),cell=document.createElement('td'),input=document.createElement('input');name.textContent=label;input.name='score_'+id;input.type='number';input.min='0';input.max='4';input.step='1';input.setAttribute('aria-label','Мінімум: '+label);cell.append(input);row.append(name,cell);rows.append(row);
    }
    for(const[value,label]of [['minor','Незначні'],['major','Суттєві'],['critical','Критичні']]){
      const l=document.createElement('label');l.className='checkbox';l.innerHTML=`<input type="checkbox" name="blocking_${value}">`;l.append(document.createTextNode(label));form.querySelector('.blocking-levels').append(l);
    }
    function meta(){
      form.querySelector('.evaluation-state').textContent=block?'Збережений оцінювач заблоковано: '+block.failure.message:saved.policy==='off'?'Вимкнено: запити оцінювачу не надсилаються.':'Увімкнено: '+(saved.policy==='report'?'лише звіт.':'пауза при проблемі.');
      const eligible=draft.current.profile.calibrated&&!draft.calibrationLost();
      f.policy.querySelector('[value=pause_on_failure]').disabled=!eligible;
      form.querySelector('.calibration-state').textContent=eligible?'Калібрування підтверджене сервером.':draft.calibrationLost()?'Зміна конфігурації скасує допуск. Оберіть «Лише звіт» або вимкніть оцінювач.':'Попередній профіль. Для паузи потрібне успішне калібрування.';
      form.querySelector('.profile-status').textContent=draft.current.profile.calibrated?'Калібрований профіль: пороги лише для перегляду. Для змін створіть кандидата.':'Профіль-кандидат: пороги не є підтвердженим допуском.';
      form.querySelector('.scoring-fields').disabled=draft.current.profile.calibrated;
      form.querySelector('.candidate').hidden=!draft.current.profile.calibrated;
      form.querySelector('.calibration-metadata').textContent=JSON.stringify({calibrated:draft.current.profile.calibrated,evaluator_fingerprint:draft.current.profile.evaluator_fingerprint,calibration_fingerprint:draft.current.profile.calibration_fingerprint},null,2);
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
        draft.patch({config,context_tokens:Number(f.context_tokens.value),profile,policy:f.enabled.checked?f.policy.value:'off'});raw.value=draft.rawText;error.textContent='';
      }catch(problem){error.textContent=problem.message}
      meta();settingsChanged('evaluator');
    }
    form.addEventListener('input',event=>{if(event.target===raw){draft.setRaw(raw.value);meta();settingsChanged('evaluator')}else if(event.target!==f.enabled)fromFields()});
    form.addEventListener('change',event=>{if(event.target!==f.enabled&&event.target!==raw)fromFields()});
    form.addEventListener('settings-unlocked',()=>{connection.update();meta()});
    form.querySelector('.raw-apply').onclick=()=>{try{draft.applyRaw();write();rawError.textContent='';settingsChanged('evaluator')}catch(problem){rawError.textContent=problem.message}};
    form.querySelector('.raw-discard').onclick=()=>{draft.discardRaw();write();rawError.textContent='';settingsChanged('evaluator')};
    form.querySelector('.candidate').onclick=()=>{if(confirm('Створити профіль-кандидат без допуску калібрування? Для продовження оберіть «Лише звіт» або вимкніть оцінювач.')){try{draft.makeCandidate();write();settingsChanged('evaluator')}catch(problem){error.textContent=problem.message}}};
    f.enabled.onchange=async()=>{
      const enabled=f.enabled.checked,policy=enabled?f.policy.value:'off';
      if(enabled&&!confirm(`Увімкнути збережений оцінювач ${saved.config.provider} / ${saved.config.model||'модель CLI за замовчуванням'}? Незбережена конфігурація не застосовується.${configured?'':' Буде створена стандартна конфігурація Codex CLI.'}`)){f.enabled.checked=saved.policy!=='off';settingsChanged('evaluator');return}
      try{
        await withSettingsSave('evaluator',async()=>{
          const result=await draft.savePolicy(policy,value=>api(base+'/policy',json('PUT',{policy:value})));saved=normalizeEvaluator(result);configured=true;block=result.block;
          f.enabled.checked=result.policy!=='off';if(result.policy!=='off')f.policy.value=result.policy;
          if(!draft.rawPending)raw.value=draft.rawText;meta();settingsRebaseFields('evaluator',['enabled','policy']);
          document.dispatchEvent(new CustomEvent('evaluation-policy-changed'));notice(result.policy==='off'?'Оцінювач вимкнено':'Збережений оцінювач увімкнено');
        });
      }catch(problem){f.enabled.checked=saved.policy!=='off';error.textContent=problem.message;settingsChanged('evaluator')}
    };
    form.onsubmit=async event=>{
      event.preventDefault();fromFields();
      try{
        const payload=draft.read();
        await withSettingsSave('evaluator',async()=>{
          if(configured){const latest=normalizeEvaluator(await api(base));if(settingsSignature(latest)!==settingsSignature(saved))throw new Error('Оцінювача вже змінено. Звірте конфігурацію або відкиньте правки перед збереженням.')}
          await api(base,json('PUT',payload));settingsSaved('evaluator');await load();document.dispatchEvent(new CustomEvent('evaluation-policy-changed'));notice('Оцінювача збережено');
        });
      }catch(problem){error.textContent=problem.message;settingsFormError('evaluator',problem);notice(problem.message,'error')}
    };
    write();host.replaceChildren(form);registerSettingsForm('evaluator',{form,label:'Оцінювач',section:'evaluator',reset:load});
  }
  try{await load()}catch(error){
    host.replaceChildren();const message=document.createElement('p'),retry=document.createElement('button');message.className='form-error';message.textContent='Не вдалося завантажити оцінювача: '+error.message;retry.type='button';retry.textContent='Спробувати завантажити знову';retry.onclick=()=>installEvaluatorSettings(host,storyId);host.append(message,retry);
  }
}
