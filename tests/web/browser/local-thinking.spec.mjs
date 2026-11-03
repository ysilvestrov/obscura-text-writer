import {test,expect} from '../../../frontend/browser-test.mjs';

test('local thinking control saves only the selected role and survives locale switch',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  const url=`/api/stories/${f.story_id}/settings`;
  const before=await(await request.get(url)).json();
  await page.goto(`/stories/${f.story_id}/settings`);
  await page.locator('[data-settings-role="planner"]').click();
  const form=page.locator('form[data-role="planner"]');
  await expect(form.locator('[name="model"]')).toBeVisible();
  await form.locator('[name="model"]').fill('synthetic-local-json');
  const flag=form.locator('[name="local_disable_thinking"]');
  await flag.evaluate(el=>{el.closest('details').open=true});
  await flag.check();
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en')});
  await expect(flag).toBeChecked();
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  await expect(page.locator('#settings-save')).toBeDisabled();
  const after=await(await request.get(url)).json();
  expect(after.roles.planner.provider.local_disable_thinking).toBe(true);
  expect(after.roles.writer).toEqual(before.roles.writer);
  await page.reload();
  await page.locator('[data-settings-role="planner"]').click();
  await expect(form.locator('[name="local_disable_thinking"]')).toBeChecked();
});
