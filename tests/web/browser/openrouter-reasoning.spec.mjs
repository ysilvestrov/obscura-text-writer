import {test,expect} from '../../../frontend/browser-test.mjs';

// OPENROUTER-REASONING-S04: the saved level shows before the catalog loads; leaving OpenRouter clears it on save.
test('openrouter reasoning shows the saved level and a provider switch clears it',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  const url=`/api/stories/${f.story_id}/settings`;
  const before=await(await request.get(url)).json();
  const put=await request.put(url,{data:{expected_revision:before.story.revision,role:'planner',settings:{...(before.roles.planner||{}),provider:{provider:'openrouter',model:'qwen/qwen3.8-flash',openrouter_reasoning_effort:'low'}}}});
  expect(put.ok(),await put.text()).toBe(true);
  await page.goto(`/stories/${f.story_id}/settings`);
  await page.locator('[data-settings-role="planner"]').click();
  const form=page.locator('form[data-role="planner"]');
  const select=form.locator('[name="openrouter_reasoning_effort"]');
  await expect(form.locator('.openrouter-options')).toBeVisible();
  await expect(select).toHaveValue('low');
  await form.locator('[name="provider"]').selectOption('local');
  await form.locator('[name="model"]').fill('synthetic-local-json');
  await expect(form.locator('.openrouter-options')).toBeHidden();
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  const after=await(await request.get(url)).json();
  expect(after.roles.planner.provider.provider).toBe('local');
  expect(after.roles.planner.provider).not.toHaveProperty('openrouter_reasoning_effort');
});

// OPENROUTER-REASONING-S04: with the catalog loaded, the choices follow the chosen model and the chosen level is saved.
test('openrouter reasoning choices follow the loaded catalog and save',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  const url=`/api/stories/${f.story_id}/settings`;
  const catalog=[
    {id:'z-ai/glm-5.3-flash',name:'GLM',context_tokens:131072,max_output_tokens:8192,privacy:'unknown',reasoning:{mandatory:true,default_enabled:true,efforts:['max','high','low'],default_effort:'max'}},
    {id:'qwen/qwen3.7-plus',name:'Qwen',context_tokens:131072,max_output_tokens:8192,privacy:'unknown',reasoning:{mandatory:false,default_enabled:true,efforts:[],default_effort:null}},
  ];
  await page.route('**/api/providers/discover',route=>route.fulfill({json:{models:catalog}}));
  await page.goto(`/stories/${f.story_id}/settings`);
  await page.locator('[data-settings-role="planner"]').click();
  const form=page.locator('form[data-role="planner"]');
  await form.locator('[name="provider"]').selectOption('openrouter');
  const select=form.locator('[name="openrouter_reasoning_effort"]');
  const values=()=>select.locator('option').evaluateAll(options=>options.map(o=>o.value));
  await expect.poll(values).toEqual(['']);
  await form.locator('.discover').click();
  const picker=form.locator('.model-picker').first();
  await picker.locator('tbody tr[data-model-id="z-ai/glm-5.3-flash"]').click();
  await expect.poll(values).toEqual(['','low','high','max']);
  await picker.locator('tbody tr[data-model-id="qwen/qwen3.7-plus"]').click();
  await expect.poll(values).toEqual(['','none']);
  await select.selectOption('none');
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  const after=await(await request.get(url)).json();
  expect(after.roles.planner.provider.model).toBe('qwen/qwen3.7-plus');
  expect(after.roles.planner.provider.openrouter_reasoning_effort).toBe('none');
});
