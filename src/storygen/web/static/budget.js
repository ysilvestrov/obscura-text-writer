import {live,t,msg,labelEntries,getLocale,uiText,uiAttr,uiHTML,uiInsertHTML,diagnostic} from './i18n.js';
import {registerSettingsForm,settingsSaved,withSettingsSave,settingsDrafts,confirmSettingsReplacement} from './settings-workspace.js';
import {usageText,compactBudgetText} from './workspace-links.js';
import {api,json,notice} from './api.js';
import {usd,lastCallText} from './budget-format.js';
const root=document.querySelector('[data-story-id]');
if(root){
  const id=root.dataset.storyId,base=`/api/stories/${id}/budget`,settings=!!document.querySelector('.settings-page');
  const host=document.createElement('section');host.className='budget-panel'+(settings?' panel':'');
  uiHTML(host,"<h2><span data-i18n=\"m_c5f278a41270\">Бюджет викликів</span></h2><p class=\"budget-summary\" role=\"status\" aria-live=\"polite\"><span data-i18n=\"m_e297ebd8c120\">Завантажуємо облік…</span></p><p class=\"budget-last-call\" role=\"status\" aria-live=\"polite\"></p><button type=\"button\" class=\"secondary budget-refresh\"><span data-i18n=\"m_1a4e00ab27b0\">Оновити облік</span></button>",{});
  (settings?(document.querySelector('#settings-budget-content')||root):document.querySelector('.context-panel')).append(host);
  if(!settings)uiInsertHTML(host,'beforeend',"<label><span data-i18n=\"m_48b9ac065b9f\">Ліміт наступного запуску, USD · необов’язково</span><input id=\"run-budget\" type=\"number\" min=\"0\" step=\"any\" placeholder=\"Типовий ліміт із налаштувань\" data-i18n-attrs='{\"placeholder\":\"m_c107f418a0e7\"}'></label>");
  let current=null,budgetRevision=null;
  async function load(){
    current=await api(base);
    host.budgetData=current;
    document.dispatchEvent(new CustomEvent('workspace-budget-updated',{detail:current}));
    uiText(host.querySelector('.budget-last-call'),"textContent",()=>(lastCallText(current.last_call)));
    let usage=host.querySelector('.budget-usage');if(!usage){usage=document.createElement('p');usage.className='budget-usage muted';host.querySelector('.budget-last-call').after(usage)}uiText(usage,"textContent",()=>(usageText(current.last_call?.usage)));
    const status=host.querySelector('.budget-summary');
    uiText(status,"textContent",()=>(current.limit_nanos===null?t("m_094095cf4c03"):
      t("m_31411a418b08",{p0:(usd(current.available_nanos)),p1:(usd(current.limit_nanos)),p2:(usd(current.actual_nanos)),p3:(usd(current.estimated_nanos)),p4:(usd(current.reserved_nanos)),p5:(usd(current.unresolved_nanos))})));
    if(settings&&!host.querySelector('#budget-limit-form').dataset.dirty){
      budgetRevision=current.policy?.revision||0;
      host.querySelector('[name=limit_usd]').value=current.limit_nanos===null?'':String(current.limit_nanos/1e9);
      const value=current.policy?.default_run_limit_nanos;
      host.querySelector('[name=default_run_limit_usd]').value=value==null?'':String(value/1e9);
      registerSettingsForm('budget',{form:host.querySelector('#budget-limit-form'),label:live(()=>(t("m_aef7c84659de"))),section:'budget',reset:async()=>{delete host.querySelector('#budget-limit-form').dataset.dirty;await load()}});
    }
  }
  async function perform(button,fn){button.disabled=true;try{await fn()}catch(error){notice(error.message,'error')}finally{button.disabled=false}}
  host.querySelector('.budget-refresh').onclick=e=>perform(e.currentTarget,load);
  if(settings){
    uiInsertHTML(host,'beforeend',"<p class=\"muted\"><span data-i18n=\"m_44cfc9f1900b\">Облік починається з нових викликів. Старі запуски не отримують вигаданої вартості. Local і Codex мають облік usage без ціни в доларах.</span></p><form id=\"budget-limit-form\"><label><span data-i18n=\"m_0c62c2c2489f\">Загальний ліміт оповідання, USD</span><input name=\"limit_usd\" type=\"number\" min=\"0\" step=\"any\" required></label><label><span data-i18n=\"m_ff1b78dde206\">Типовий ліміт окремого запуску, USD · необов’язково</span><input name=\"default_run_limit_usd\" type=\"number\" min=\"0\" step=\"any\"></label><button><span data-i18n=\"m_13a39075fe4d\">Зберегти ліміти</span></button></form><details><summary><span data-i18n=\"m_745c440381bd\">Тариф моделі</span></summary><form id=\"budget-price-form\"><label><span data-i18n=\"m_2d385af6d69b\">Провайдер</span><select name=\"provider\"><option value=\"venice\">Venice</option><option value=\"openrouter\">OpenRouter</option></select></label><label><span data-i18n=\"m_50b63297de21\">Точний Model ID</span><input name=\"model\" required></label><button type=\"button\" class=\"secondary catalog-price\"><span data-i18n=\"m_e6ef86c500b9\">Оновити з каталогу</span></button><p class=\"muted\"><span data-i18n=\"m_bf00d667a538\">Ручний тариф застосовується до нових викликів цієї моделі в застосунку. Збережені виклики зберігають свій тариф.</span></p><label><span data-i18n=\"m_25343141dc8f\">Вхід, USD за мільйон токенів</span><input name=\"input_per_million\" type=\"number\" min=\"0\" step=\"any\" required></label><label><span data-i18n=\"m_a77c84932d50\">Вихід, USD за мільйон токенів</span><input name=\"output_per_million\" type=\"number\" min=\"0\" step=\"any\" required></label><label><span data-i18n=\"m_950b72466867\">За запит, USD</span><input name=\"request_usd\" type=\"number\" min=\"0\" step=\"any\" value=\"0\" required></label><label><span data-i18n=\"m_cffed2da218f\">Джерело тарифу</span><input name=\"source\" required></label><label><span data-i18n=\"m_61e2b206d9d0\">Чинний до · ваш місцевий час</span><input name=\"expires_at\" type=\"datetime-local\" required></label><button><span data-i18n=\"m_8f0ad1148591\">Підтвердити ручний тариф</span></button><p class=\"price-result\" role=\"status\"></p></form></details><details class=\"budget-history\"><summary><span data-i18n=\"m_6eafdc6fc51f\">Історія викликів і звірка</span></summary><button type=\"button\" class=\"secondary load-calls\"><span data-i18n=\"m_655ea9ab140e\">Завантажити виклики</span></button><ul class=\"budget-calls\"></ul></details>");
    const form=host.querySelector('#budget-limit-form');form.oninput=()=>{form.dataset.dirty='true'};
    form.onsubmit=e=>{e.preventDefault();perform(form.querySelector('button'),()=>withSettingsSave('budget',async()=>{
      if(!current)throw new Error(t("m_6c53963408a7"));
      await api(base,json('PUT',{expected_revision:budgetRevision,limit_usd:form.elements.limit_usd.value,default_run_limit_usd:form.elements.default_run_limit_usd.value||null}));
      delete form.dataset.dirty;settingsSaved('budget');await load();notice(msg("m_bfac6b0cd279"));
    }))};
    const price=host.querySelector('#budget-price-form'),result=price.querySelector('.price-result');registerSettingsForm('budget-price',{form:price,label:live(()=>(t("m_587c1dcd0074"))),section:'budget'});
    price.querySelector('.catalog-price').onclick=e=>perform(e.currentTarget,async()=>{
      if(!price.elements.model.value.trim())throw new Error(t("m_17485a937e4b"));
      const value=await api(base+'/prices',json('POST',{provider:price.elements.provider.value,model:price.elements.model.value,refresh:true}));
      uiText(result,"textContent",()=>(t("m_3381b1bf1acc",{p0:(value.input_per_million),p1:(value.output_per_million),p2:(new Date(value.expires_at).toLocaleString(getLocale()==='en'?'en-US':'uk-UA'))})));
    });
    price.onsubmit=e=>{e.preventDefault();const body=Object.fromEntries(new FormData(price));body.expires_at=new Date(body.expires_at).toISOString();perform(price.querySelector('button:not([type=button])'),()=>withSettingsSave('budget-price',async()=>{
      await api(base+'/prices',json('POST',body));settingsSaved('budget-price');uiText(result,"textContent",()=>(t("m_2c5388568c5b")));
    }))};
    host.querySelector('.load-calls').onclick=e=>perform(e.currentTarget,async()=>{
      const rows=await api(base+'/calls'),list=host.querySelector('.budget-calls');if(!await confirmSettingsReplacement([...settingsDrafts.records.keys()].filter(k=>k.startsWith('reconcile:'))))return;list.replaceChildren();
      if(!rows.length){const li=document.createElement('li');uiText(li,"textContent",()=>(t("m_1c7467cc1e7d")));list.append(li)}
      for(const call of rows){
        const li=document.createElement('li'),description=document.createElement('p');
        uiText(description,"textContent",()=>(`${call.provider} · ${call.model} · ${call.state}. ${call.cost_source==='unpriced'?t("m_db266dd16857"):t("m_3760bebc41c9",{p0:(usd(call.reserved_nanos)),p1:(usd(call.counted_nanos)),p2:(call.cost_source==='provider'?t("m_a96608cdcb80"):call.cost_source==='priced_usage_estimate'?t("m_dba4780d37e9"):t("m_bbf190f1819f"))})}`));
        li.append(description);
        if(call.reported_diem!=null){const p=document.createElement('p');uiText(p,"textContent",()=>(t("m_54556a3c67e1",{p0:(call.reported_diem)})));li.append(p)}
        if(['unresolved','reserved','sent'].includes(call.state)&&call.cost_source!=='unpriced'){
          const check=document.createElement('form');uiHTML(check,"<label><span data-i18n=\"m_269c13d7970d\">Перевірена сума, USD</span><input name=\"amount_usd\" type=\"number\" min=\"0\" step=\"any\" required></label><label><span data-i18n=\"m_15f67f2e62e1\">Джерело звірки</span><input name=\"source\" required></label><button><span data-i18n=\"m_94ebd570daa7\">Підтвердити звірку</span></button>",{});
          check.onsubmit=event=>{event.preventDefault();const body=Object.fromEntries(new FormData(check));perform(check.querySelector('button'),()=>withSettingsSave('reconcile:'+call.call_id,async()=>{await api(base+`/calls/${encodeURIComponent(call.call_id)}/reconcile`,json('POST',body));settingsSaved('reconcile:'+call.call_id);await load();uiText(description,"textContent",()=>(t("m_3db2c315c966")));check.remove()}))};li.append(check);registerSettingsForm('reconcile:'+call.call_id,{form:check,label:live(()=>(t("m_66f77a99f662"))),section:'budget'});
        }
        list.append(li);
      }
    });
  }
  load().catch(error=>{uiText(host.querySelector('.budget-summary'),"textContent",()=>(diagnostic(error.message)));notice(error.message,'error')});
  document.addEventListener('story-refreshed',()=>load().catch(()=>{}));
}
