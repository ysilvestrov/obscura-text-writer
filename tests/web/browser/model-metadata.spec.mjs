import {test,expect} from '../../../frontend/browser-test.mjs';

const tariff={provider:'venice',model:'synthetic-priced',base_url:'https://api.venice.ai/api/v1',input_per_million:'0.07',output_per_million:'0.4',request_usd:'0',kind:'official',source:'https://api.venice.ai/api/v1/models',fetched_at:'2026-01-01T00:00:00Z',expires_at:'2099-01-01T00:00:00Z'};

test('selected model shows tariff units, caps and unknown without changing other inputs',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:[{id:'synthetic-priced',context_tokens:200000,max_output_tokens:24000,uncensored:true,tariff},{id:'unknown-price',context_tokens:null,max_output_tokens:null,tariff:null}]}}));
  await page.goto(`/stories/${f.story_id}/settings`);await page.locator('[data-settings-role=writer]').click();
  const form=page.locator('form[data-role=writer]'),model=form.locator('[name=model]'),info=form.locator('[data-model-info]').first();
  await form.locator('[name=provider]').selectOption('venice');
  await page.locator('[data-ui-locale=en]').click();
  await form.locator('.discover').click();await model.fill('synthetic-priced');
  await expect(info).toContainText('0.07');await expect(info).toContainText('0.4');await expect(info).toContainText('USD');await expect(info).toContainText('1,000,000');await expect(info).toContainText('24000');
  // The synthetic rows report no privacy level, so the default «Private and above» filter hides them.
  await form.locator('.model-picker-privacy select').first().selectOption('any');
  await expect(form.locator('.model-picker tbody tr[data-model-id="synthetic-priced"]')).toContainText('0.07');
  const max=await form.locator('[name=max_output_tokens]').inputValue();
  await page.locator('[data-ui-locale=uk]').click();await expect(info).toContainText('Вхід');await expect(model).toHaveValue('synthetic-priced');await expect(form.locator('[name=max_output_tokens]')).toHaveValue(max);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await expect(model).toHaveAccessibleName('Model ID');
  await page.evaluate(()=>import('/static/api.js').then(m=>m.dismissNotice()));
  await info.scrollIntoViewIfNeeded();await page.screenshot({path:`docs/images/model-tariff-${test.info().project.name}.png`});
  await model.fill('unknown-price');await expect(info).toContainText('Тариф невідомий');await expect(info).not.toContainText('0.07');
  await form.locator('[name=provider]').selectOption('openrouter');await expect(info).toContainText('Тариф невідомий');
});

test('manual expired tariff is labelled and stale discovery cannot label another provider',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  let release;const gate=new Promise(r=>release=r);
  await page.route('**/api/providers/discover',async route=>{await gate;await route.fulfill({json:{models:[{id:'old-model',context_tokens:200000,max_output_tokens:24000,tariff:{...tariff,model:'old-model',kind:'manual',fetched_at:'2020-01-01T00:00:00Z',expires_at:'2021-01-01T00:00:00Z'}}]}});});
  await page.goto(`/stories/${f.story_id}/settings`);await page.locator('[data-settings-role=planner]').click();
  const form=page.locator('form[data-role=planner]'),info=form.locator('[data-model-info]').first();
  await form.locator('[name=provider]').selectOption('venice');await form.locator('.discover').click();
  await form.locator('[name=provider]').selectOption('openrouter');release();
  await expect(form.locator('.discover')).toBeEnabled();
  await form.locator('[name=model]').fill('old-model');await expect(info).toContainText(/Тариф невідомий|Tariff unknown/);
  await form.locator('[name=provider]').selectOption('venice');await form.locator('.discover').click();
  await expect(info).toContainText(/прострочений|expired/);await expect(info).toContainText(/ручний|manual/i);
});


test('shared classifier connection shows the same tariff without changing its limits',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:[{id:'synthetic-priced',context_tokens:200000,max_output_tokens:24000,tariff}]}}));
  await page.goto(`/stories/${f.story_id}/settings`);await page.locator('[data-settings-role=editor]').click();
  const form=page.locator('form[data-role=editor]'),toggle=form.locator('[name=classification_enabled]');
  await toggle.evaluate(e=>e.closest('details').open=true);await toggle.check();
  const fields=form.locator('.classification-fields'),limit=fields.locator('[name=classification_max_output_tokens]');
  const before=await limit.inputValue();await fields.locator('label:has([name=classification_model]) button').click();
  await fields.locator('[name=classification_model]').fill('synthetic-priced');
  await expect(fields.locator('[data-model-info]')).toContainText('0.07');
  await page.locator('[data-ui-locale=en]').click();await expect(fields.locator('[data-model-info]')).toContainText('Input:');
  await expect(fields.locator('[name=classification_model]')).toHaveAccessibleName('Model');
  await expect(limit).toHaveValue(before);
});
