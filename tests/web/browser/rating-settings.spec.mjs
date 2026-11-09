import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
// Navigation differs by layout, as in the other settings specs; every assertion below runs on both projects.
const openWriting=async page=>{
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
};
test('author sets the story rating in settings and generation is unblocked',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-unrated')).json();
  const brief=async()=>(await(await request.get(`/api/stories/${story_id}/readiness?operation=brief&scene_id=${scene_id}`)).json()).operations.brief;
  expect(await brief()).toMatchObject({ready:false,reason:expect.stringContaining('Задайте віковий рейтинг')});
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
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
  // The rating block is lifted; sexual content 1 now reaches the minors guard, and this scene has no cast.
  expect(await brief()).toMatchObject({ready:false,reason:expect.stringContaining('склад сцени порожній')});
  await page.reload();
  await openWriting(page);
  await expect(form.locator('select[name="sexual"]')).toHaveValue('1');
  await expect(form.locator('select[name="themes"]')).toHaveValue('2');
  const leaveBlocked=()=>page.evaluate(()=>{const event=new Event('beforeunload',{cancelable:true});dispatchEvent(event);return event.defaultPrevented});
  expect(await leaveBlocked()).toBe(false);
  await form.locator('select[name="sexual"]').selectOption('0');
  expect(await leaveBlocked()).toBe(true);
  // textContent assertion: the desktop nav is hidden on mobile but still carries the unsaved marker.
  await expect(page.locator('[data-settings-nav="writing"]')).toContainText('незбережено');
  await form.locator('#rating-save').click();
  await expect(page.locator('#notice')).toContainText('Рейтинг збережено');
  expect(await leaveBlocked()).toBe(false);
  expect(await brief()).toMatchObject({ready:true,reason:null});
});

test('each rating axis explains itself in a help tip',async({page,request})=>{
  const {story_id}=await(await request.post('/test-unrated')).json();
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  const form=page.locator('#rating-form');
  const expected={sexual:['Сексуальний зміст','вік від 18 років'],violence:['Насильство','бійки, поранення'],themes:['Жорсткі теми','самогубство']};
  for(const [axis,[name,phrase]] of Object.entries(expected)){
    // The axis name still labels its select, not the help button next to it.
    await expect(form.getByLabel(name,{exact:true})).toHaveAttribute('name',axis);
    const tip=form.locator(`#rating-help-${axis}`);
    await expect(tip).toBeHidden();
    await form.locator(`button[aria-describedby="rating-help-${axis}"]`).focus();
    await expect(tip).toBeVisible();
    await expect(tip).toContainText(phrase);
    await expect(tip).toContainText(/0 — .+1 — .+2 — /);
    await expect(form.locator(`select[name="${axis}"]`)).toHaveAttribute('aria-describedby',new RegExp(`rating-help-${axis}`));
  }
  await expect(form.locator('#rating-help-themes')).toContainText('«насильство» — що показано з тілом');
});
