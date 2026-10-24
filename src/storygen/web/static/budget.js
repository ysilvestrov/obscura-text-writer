import {registerSettingsForm,settingsSaved,withSettingsSave,settingsDrafts,confirmSettingsReplacement} from './settings-workspace.js';
import {usageText,compactBudgetText} from './workspace-links.js';
import {api,json,notice} from './api.js';
import {usd,lastCallText} from './budget-format.js';
const root=document.querySelector('[data-story-id]');
if(root){
  const id=root.dataset.storyId,base=`/api/stories/${id}/budget`,settings=!!document.querySelector('.settings-page');
  const host=document.createElement('section');host.className='budget-panel'+(settings?' panel':'');
  host.innerHTML='<h2>Бюджет викликів</h2><p class="budget-summary" role="status" aria-live="polite">Завантажуємо облік…</p><p class="budget-last-call" role="status" aria-live="polite"></p><button type="button" class="secondary budget-refresh">Оновити облік</button>';
  (settings?(document.querySelector('#settings-budget-content')||root):document.querySelector('.context-panel')).append(host);
  if(!settings)host.insertAdjacentHTML('beforeend','<label>Ліміт наступного запуску, USD · необов’язково<input id="run-budget" type="number" min="0" step="any" placeholder="Типовий ліміт із налаштувань"></label>');
  let current=null,budgetRevision=null;
  async function load(){
    current=await api(base);
    host.dataset.compactBudget=compactBudgetText(current);
    document.dispatchEvent(new CustomEvent('workspace-budget-updated',{detail:compactBudgetText(current)}));
    host.querySelector('.budget-last-call').textContent=lastCallText(current.last_call);
    let usage=host.querySelector('.budget-usage');if(!usage){usage=document.createElement('p');usage.className='budget-usage muted';host.querySelector('.budget-last-call').after(usage)}usage.textContent=usageText(current.last_call?.usage);
    const status=host.querySelector('.budget-summary');
    status.textContent=current.limit_nanos===null?'Ліміт не задано. Платні API потребують явного бюджету.':
      `Доступно ${usd(current.available_nanos)} із ${usd(current.limit_nanos)}. Підтверджено ${usd(current.actual_nanos)}; розраховано за токенами ${usd(current.estimated_nanos)}; у резерві ${usd(current.reserved_nanos)}; потребує звірки ${usd(current.unresolved_nanos)}.`;
    if(settings&&!host.querySelector('#budget-limit-form').dataset.dirty){
      budgetRevision=current.policy?.revision||0;
      host.querySelector('[name=limit_usd]').value=current.limit_nanos===null?'':String(current.limit_nanos/1e9);
      const value=current.policy?.default_run_limit_nanos;
      host.querySelector('[name=default_run_limit_usd]').value=value==null?'':String(value/1e9);
      registerSettingsForm('budget',{form:host.querySelector('#budget-limit-form'),label:'Ліміти',section:'budget',reset:async()=>{delete host.querySelector('#budget-limit-form').dataset.dirty;await load()}});
    }
  }
  async function perform(button,fn){button.disabled=true;try{await fn()}catch(error){notice(error.message,'error')}finally{button.disabled=false}}
  host.querySelector('.budget-refresh').onclick=e=>perform(e.currentTarget,load);
  if(settings){
    host.insertAdjacentHTML('beforeend','<p class="muted">Облік починається з нових викликів. Старі запуски не отримують вигаданої вартості. Local і Codex мають облік usage без ціни в доларах.</p><form id="budget-limit-form"><label>Загальний ліміт оповідання, USD<input name="limit_usd" type="number" min="0" step="any" required></label><label>Типовий ліміт окремого запуску, USD · необов’язково<input name="default_run_limit_usd" type="number" min="0" step="any"></label><button>Зберегти ліміти</button></form><details><summary>Тариф моделі</summary><form id="budget-price-form"><label>Провайдер<select name="provider"><option value="venice">Venice</option><option value="openrouter">OpenRouter</option></select></label><label>Точний Model ID<input name="model" required></label><button type="button" class="secondary catalog-price">Оновити з каталогу</button><p class="muted">Ручний тариф застосовується до нових викликів цієї моделі в застосунку. Збережені виклики зберігають свій тариф.</p><label>Вхід, USD за мільйон токенів<input name="input_per_million" type="number" min="0" step="any" required></label><label>Вихід, USD за мільйон токенів<input name="output_per_million" type="number" min="0" step="any" required></label><label>За запит, USD<input name="request_usd" type="number" min="0" step="any" value="0" required></label><label>Джерело тарифу<input name="source" required></label><label>Чинний до · ваш місцевий час<input name="expires_at" type="datetime-local" required></label><button>Підтвердити ручний тариф</button><p class="price-result" role="status"></p></form></details><details class="budget-history"><summary>Історія викликів і звірка</summary><button type="button" class="secondary load-calls">Завантажити виклики</button><ul class="budget-calls"></ul></details>');
    const form=host.querySelector('#budget-limit-form');form.oninput=()=>{form.dataset.dirty='true'};
    form.onsubmit=e=>{e.preventDefault();perform(form.querySelector('button'),()=>withSettingsSave('budget',async()=>{
      if(!current)throw new Error('Спершу оновіть облік');
      await api(base,json('PUT',{expected_revision:budgetRevision,limit_usd:form.elements.limit_usd.value,default_run_limit_usd:form.elements.default_run_limit_usd.value||null}));
      delete form.dataset.dirty;settingsSaved('budget');await load();notice('Ліміти збережено.');
    }))};
    const price=host.querySelector('#budget-price-form'),result=price.querySelector('.price-result');registerSettingsForm('budget-price',{form:price,label:'Тариф',section:'budget'});
    price.querySelector('.catalog-price').onclick=e=>perform(e.currentTarget,async()=>{
      if(!price.elements.model.value.trim())throw new Error('Вкажіть точний Model ID');
      const value=await api(base+'/prices',json('POST',{provider:price.elements.provider.value,model:price.elements.model.value,refresh:true}));
      result.textContent=`Каталог: вхід $${value.input_per_million}/M, вихід $${value.output_per_million}/M; чинний до ${new Date(value.expires_at).toLocaleString('uk-UA')}.`;
    });
    price.onsubmit=e=>{e.preventDefault();const body=Object.fromEntries(new FormData(price));body.expires_at=new Date(body.expires_at).toISOString();perform(price.querySelector('button:not([type=button])'),()=>withSettingsSave('budget-price',async()=>{
      await api(base+'/prices',json('POST',body));settingsSaved('budget-price');result.textContent='Ручний тариф підтверджено.';
    }))};
    host.querySelector('.load-calls').onclick=e=>perform(e.currentTarget,async()=>{
      const rows=await api(base+'/calls'),list=host.querySelector('.budget-calls');if(!confirmSettingsReplacement([...settingsDrafts.records.keys()].filter(k=>k.startsWith('reconcile:'))))return;list.replaceChildren();
      if(!rows.length){const li=document.createElement('li');li.textContent='Облік нових викликів ще порожній.';list.append(li)}
      for(const call of rows){
        const li=document.createElement('li'),description=document.createElement('p');
        description.textContent=`${call.provider} · ${call.model} · ${call.state}. ${call.cost_source==='unpriced'?'Без токенної USD-ціни':`Резерв-прогноз ${usd(call.reserved_nanos)}; враховано ${usd(call.counted_nanos)} (${call.cost_source==='provider'?'підтверджено':call.cost_source==='priced_usage_estimate'?'за токенами':'очікує звірки'})`}`;
        li.append(description);
        if(call.reported_diem!=null){const p=document.createElement('p');p.textContent=`Провайдер повідомив DiEM: ${call.reported_diem}.`;li.append(p)}
        if(['unresolved','reserved','sent'].includes(call.state)&&call.cost_source!=='unpriced'){
          const check=document.createElement('form');check.innerHTML='<label>Перевірена сума, USD<input name="amount_usd" type="number" min="0" step="any" required></label><label>Джерело звірки<input name="source" required></label><button>Підтвердити звірку</button>';
          check.onsubmit=event=>{event.preventDefault();const body=Object.fromEntries(new FormData(check));perform(check.querySelector('button'),()=>withSettingsSave('reconcile:'+call.call_id,async()=>{await api(base+`/calls/${encodeURIComponent(call.call_id)}/reconcile`,json('POST',body));settingsSaved('reconcile:'+call.call_id);await load();description.textContent='Виклик звірено.';check.remove()}))};li.append(check);registerSettingsForm('reconcile:'+call.call_id,{form:check,label:'Звірка виклику',section:'budget'});
        }
        list.append(li);
      }
    });
  }
  load().catch(error=>{host.querySelector('.budget-summary').textContent=error.message;notice(error.message,'error')});
  document.addEventListener('story-refreshed',()=>load().catch(()=>{}));
}
