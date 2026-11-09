import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
test('author sets the story rating in settings and generation is unblocked',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-unrated')).json();
  const blocked=async()=>(await request.get(`/api/stories/${story_id}/readiness?operation=brief&scene_id=${scene_id}`)).text();
  expect(await blocked()).toContain('рейтинг');
  await page.goto(`/stories/${story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  const form=page.locator('#rating-form');
  await expect(form.locator('select[name="sexual"]')).toHaveValue('');
  await expect(form.locator('select[name="sexual"] option').nth(2)).toHaveText('1 — доросле без графічних подробиць');
  await form.locator('#rating-save').click();
  await expect(page.locator('#notice')).toContainText('Оберіть рівень');
  await form.locator('select[name="sexual"]').selectOption('1');
  await form.locator('select[name="violence"]').selectOption('0');
  await form.locator('select[name="themes"]').selectOption('2');
  await form.locator('#rating-save').click();
  await expect(page.locator('#notice')).toContainText('Рейтинг збережено');
  await expect(form.locator('select[name="sexual"] option[value=""]')).toHaveJSProperty('disabled',true);
  expect(await blocked()).not.toContain('Задайте віковий рейтинг');
  await page.reload();
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  await expect(form.locator('select[name="sexual"]')).toHaveValue('1');
  await expect(form.locator('select[name="themes"]')).toHaveValue('2');
});
