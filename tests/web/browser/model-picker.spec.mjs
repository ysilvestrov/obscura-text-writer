// MODEL-005-S01/S02: catalog badges, filters and JSON Schema mode of the model picker.
import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const tariff=(id,input,output)=>({provider:'venice',model:id,base_url:'https://api.venice.ai/api/v1',input_per_million:input,output_per_million:output,request_usd:'0',kind:'official',source:'https://api.venice.ai/api/v1/models',fetched_at:'2026-01-01T00:00:00Z',expires_at:'2099-01-01T00:00:00Z'});
// Synthetic Venice catalog: TEE without Uncensored, Private+Uncensored+schema, Anonymous+Uncensored, Private+Uncensored without schema.
const models=[
  {id:'syn-tee',name:'Syn TEE',context_tokens:131072,max_output_tokens:8192,tariff:tariff('syn-tee','0.9','3'),uncensored:false,privacy:'private',tee:true,supports_schema:false},
  {id:'syn-private',name:'Syn Private',context_tokens:200000,max_output_tokens:16000,tariff:tariff('syn-private','0.55','2.2'),uncensored:true,privacy:'private',tee:false,supports_schema:true},
  {id:'syn-anon',name:'Syn Anon',context_tokens:65536,max_output_tokens:4096,tariff:tariff('syn-anon','0.1','0.4'),uncensored:true,privacy:'anonymized',tee:false,supports_schema:true},
  {id:'syn-noschema',name:'Syn No Schema',context_tokens:32768,max_output_tokens:4096,tariff:null,uncensored:true,privacy:'private',tee:false,supports_schema:false},
];

async function openWriter(page,request,{provider='venice',catalog=models}={}){
  const f=await(await request.post('/test-fixture')).json();
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:catalog}}));
  await page.goto(`/stories/${f.story_id}/settings`);await page.locator('[data-settings-role=writer]').click();
  const form=page.locator('form[data-role=writer]');
  await form.locator('[name=provider]').selectOption(provider);
  return {form,picker:form.locator('.model-picker').first(),model:form.locator('[name=model]')};
}
const row=(picker,id)=>picker.locator(`tbody tr[data-model-id="${id}"]`);
const rows=picker=>picker.locator('tbody tr[data-model-id]');
async function setMode(form,mode){
  const select=form.locator('[name=response_mode]');await select.evaluate(e=>{const d=e.closest('details');if(d)d.open=true});await select.selectOption(mode);
}

test('catalog shows badges and the default privacy filter hides anonymous models',async({page,request})=>{
  const {form,picker}=await openWriter(page,request);
  await form.locator('.discover').click();
  await expect(rows(picker)).toHaveCount(3);await expect(row(picker,'syn-anon')).toHaveCount(0);
  await expect(picker.locator('.model-picker-foot')).toContainText('Показано 3 з 4');
  await picker.getByLabel('Приватність').selectOption('any');
  await expect(rows(picker)).toHaveCount(4);await expect(row(picker,'syn-anon')).toContainText('Anonymous');
  const priv=row(picker,'syn-private');
  for(const text of ['Uncensored','Private','JSON Schema','0.55','2.2','200K'])await expect(priv).toContainText(text);
  await expect(row(picker,'syn-tee')).toContainText('TEE');
  await picker.getByLabel('Лише Uncensored').check();await expect(row(picker,'syn-tee')).toHaveCount(0);
  await picker.getByRole('searchbox').fill('no schema');await expect(rows(picker)).toHaveCount(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('json schema mode locks the filter and blocks a non-schema model',async({page,request})=>{
  const {form,picker,model}=await openWriter(page,request);
  await setMode(form,'json_schema');await form.locator('.discover').click();
  const schema=picker.getByLabel('JSON Schema',{exact:true});
  await expect(schema).toBeChecked();await expect(schema).toBeDisabled();
  await expect(row(picker,'syn-noschema')).toHaveAttribute('aria-disabled','true');
  await expect(row(picker,'syn-private')).not.toHaveAttribute('aria-disabled','true');
  // A blocked model typed by hand is not sent to the server.
  let puts=0;page.on('request',r=>{if(r.method()==='PUT'&&r.url().includes('/settings'))puts++});
  await model.fill('syn-noschema');await page.locator('#settings-save').click();
  await expect(page.locator('#notice')).toContainText('Модель не підтримує JSON Schema');expect(puts).toBe(0);
  await setMode(form,'prompt_json');
  await expect(schema).toBeEnabled();await expect(schema).not.toBeChecked();
  await expect(row(picker,'syn-noschema')).not.toHaveAttribute('aria-disabled','true');
  await row(picker,'syn-private').click();await expect(model).toHaveValue('syn-private');
  await row(picker,'syn-noschema').click();await expect(model).toHaveValue('syn-noschema');
});

test('venice model without uncensored is selectable',async({page,request})=>{
  // MODEL-003: it is chosen like any other model; consent is asked under the chosen model.
  const {form,picker,model}=await openWriter(page,request);
  await form.locator('.discover').click();
  const tee=row(picker,'syn-tee');
  await expect(tee).toBeVisible();await expect(tee).not.toHaveAttribute('aria-disabled','true');
  await tee.click();await expect(model).toHaveValue('syn-tee');
  await expect(picker.locator('[data-model-blocked]')).toBeHidden();
});

test('manual id outside the catalog is kept and marked',async({page,request})=>{
  const {form,picker,model}=await openWriter(page,request);
  await form.locator('.discover').click();
  await model.fill('custom-model');
  await expect(picker.locator('[data-model-chosen]')).toContainText('custom-model');
  await expect(picker.locator('[data-model-info]')).toHaveText('Немає в каталозі.');
  await page.locator('#settings-save').click();
  await expect(page.locator('#notice')).toContainText('Роль збережено');
  await expect(form.locator('[name=model]')).toHaveValue('custom-model');
});

test('changing provider clears the loaded list',async({page,request})=>{
  const {form,picker}=await openWriter(page,request);
  await form.locator('.discover').click();await expect(rows(picker)).toHaveCount(3);
  const privacy=picker.getByLabel('Приватність');await expect(privacy).toBeEnabled();
  await form.locator('[name=provider]').selectOption('openrouter');
  await expect(rows(picker)).toHaveCount(0);
  await expect(privacy).toBeDisabled();
  await expect(picker.locator('[data-privacy-note]')).toHaveText('Цей провайдер не повідомляє рівень приватності.');
});

test('rows are selectable from the keyboard',async({page,request})=>{
  const {form,picker,model}=await openWriter(page,request);
  await form.locator('.discover').click();
  const priv=row(picker,'syn-private');await expect(priv).toHaveAttribute('role','button');await expect(priv).toHaveAttribute('tabindex','0');
  await priv.focus();await page.keyboard.press('Enter');
  await expect(model).toHaveValue('syn-private');await expect(priv).toHaveAttribute('aria-pressed','true');
  const focusedId=()=>page.evaluate(()=>document.activeElement?.dataset?.modelId??null);
  expect(await focusedId()).toBe('syn-private');
  // Enter on a blocked row shows the reason and keeps focus on that row.
  await setMode(form,'json_schema');
  await row(picker,'syn-noschema').focus();await page.keyboard.press('Enter');
  await expect(picker.locator('[data-model-blocked]')).toContainText('JSON Schema');await expect(model).toHaveValue('syn-private');
  expect(await focusedId()).toBe('syn-noschema');
  await expect(picker.locator('[data-model-chosen] .model-badge')).toHaveText(['Uncensored','Private','JSON Schema']);
  await page.locator('[data-ui-locale=en]').click();
  await expect(picker.locator('.model-picker-foot')).toContainText('Showing 3 of 4');
});

test('json schema mode keeps a local model with unknown support selectable and saveable',async({page,request})=>{
  // The local provider never reports JSON Schema support: unknown is not "no".
  const local=[{id:'syn-local',name:'Syn Local',context_tokens:8192,max_output_tokens:2048,tariff:null,uncensored:null,privacy:'unknown',tee:false,supports_schema:null}];
  const {form,picker,model}=await openWriter(page,request,{provider:'local',catalog:local});
  await setMode(form,'json_schema');await form.locator('.discover').click();
  const item=row(picker,'syn-local');
  await expect(item).toBeVisible();await expect(item).not.toHaveAttribute('aria-disabled','true');
  await item.click();await expect(model).toHaveValue('syn-local');
  await expect(picker.locator('[data-model-blocked]')).toBeHidden();
  await expect(picker.locator('[data-schema-unknown]')).toHaveText('Підтримка JSON Schema невідома: перевірте модель самостійно.');
  await page.locator('#settings-save').click();
  await expect(page.locator('#notice')).toContainText('Роль збережено');
  await expect(form.locator('[name=model]')).toHaveValue('syn-local');
});

test('sort buttons reorder rows and update aria-sort',async({page,request})=>{
  const {form,picker}=await openWriter(page,request);
  await form.locator('.discover').click();
  const ids=()=>rows(picker).evaluateAll(trs=>trs.map(tr=>tr.dataset.modelId));
  const head=key=>picker.locator(`th[data-sort="${key}"]`);
  // Default: input price ascending, rows without a price last.
  await expect(head('input')).toHaveAttribute('aria-sort','ascending');await expect(head('name')).toHaveAttribute('aria-sort','none');
  expect(await ids()).toEqual(['syn-private','syn-tee','syn-noschema']);
  await head('name').getByRole('button').click();
  await expect(head('name')).toHaveAttribute('aria-sort','ascending');await expect(head('input')).toHaveAttribute('aria-sort','none');
  expect(await ids()).toEqual(['syn-noschema','syn-private','syn-tee']);
  await head('name').getByRole('button').click();
  await expect(head('name')).toHaveAttribute('aria-sort','descending');
  expect(await ids()).toEqual(['syn-tee','syn-private','syn-noschema']);
});

test('rows do not change the model while the form is save-locked',async({page,request})=>{
  const {form,picker,model}=await openWriter(page,request);
  await form.locator('.discover').click();
  const before=await model.inputValue();
  // withSettingsSave disables every form control while a save runs; simulate that lock.
  await model.evaluate(e=>{e.disabled=true});
  await row(picker,'syn-private').click();await expect(model).toHaveValue(before);
  await row(picker,'syn-private').focus();await page.keyboard.press('Enter');await expect(model).toHaveValue(before);
  await model.evaluate(e=>{e.disabled=false});
  await row(picker,'syn-private').click();await expect(model).toHaveValue('syn-private');
});

// MODEL-005-S03: limits above what the catalog reports for the chosen model cannot be saved.
test('limits above the chosen model caps block the save until fixed',async({page,request})=>{
  const {form,picker}=await openWriter(page,request);
  await form.locator('.discover').click();await row(picker,'syn-private').click();
  const output=form.locator('[name=max_output_tokens]');
  await output.evaluate(e=>{const d=e.closest('details');if(d)d.open=true});
  await expect(output).toHaveAttribute('max','16000');
  await output.fill('20000');
  await expect(picker.locator('[data-model-blocked]')).toHaveText('Вихідний ліміт 20000 перевищує ліміт вибраної моделі 16000 токенів. Змініть налаштування; автоматичного повтору немає.');
  let puts=0;page.on('request',r=>{if(r.method()==='PUT'&&/\/api\/stories\/[^/]+\/settings$/.test(r.url()))puts++});
  await page.locator('#settings-save').click();
  expect(await output.evaluate(e=>e.validity.rangeOverflow)).toBe(true);
  await page.waitForTimeout(300);expect(puts).toBe(0);
  await output.fill('4096');await expect(picker.locator('[data-model-blocked]')).toBeHidden();
  const put=page.waitForResponse(r=>r.request().method()==='PUT'&&/\/api\/stories\/[^/]+\/settings$/.test(r.url()));
  await page.locator('#settings-save').click();expect((await put).ok()).toBeTruthy();
});
