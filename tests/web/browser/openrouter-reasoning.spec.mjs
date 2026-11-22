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
