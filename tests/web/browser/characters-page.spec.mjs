import {test,expect} from '../../../frontend/browser-test.mjs';

test('characters page saves, previews and returns to the same material',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await page.locator('#workspace-characters').click();
  await expect(page.locator('#characters-page')).toBeVisible();
  await page.locator('#characters-add').click();
  await page.locator('[data-ui-locale="uk"]').click();
  const card=page.locator('.character-editor fieldset').last();
  await card.locator('input').fill('Олена');
  await card.getByRole('button',{name:/Додати відомість|Add detail/}).click();
  await card.locator('textarea').fill('Працює у бібліотеці. '.repeat(35));
  await card.locator('select').first().selectOption('timeless');
  await page.locator('[data-ui-locale="en"]').click();
  await expect(card.locator('input')).toHaveValue('Олена');
  await page.locator('#characters-preview').click();
  await expect(page.locator('#characters-preview-text')).toContainText('No information is available');
  await page.locator('#characters-save').click();
  await expect(page.locator('#characters-status')).toHaveText('Details saved');
  await expect(page.locator('#characters-save')).toBeDisabled();
  const saved=await(await request.get(`/api/stories/${f.story_id}/characters`)).json();
  const view=await(await request.get(`/api/stories/${f.story_id}`)).json();
  const scene=view.scenes.find(s=>s.id===f.scene_id);
  const cast=await request.patch(`/api/scenes/${f.scene_id}`,{data:{story_id:f.story_id,expected_revision:scene.revision,character_ids:[saved.cards.at(-1).id]}});
  expect(cast.ok()).toBeTruthy();
  await page.reload();
  await expect(page.locator('#characters-preview')).toBeEnabled();
  await page.locator('#characters-preview').click();
  await expect(page.locator('#characters-preview-text')).toContainText('Працює у бібліотеці.');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:`docs/images/characters-page-${test.info().project.name}.png`,fullPage:true});
  await page.locator('#characters-return').click();
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
});

test('empty story, dirty navigation and failed save preserve edits',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Персонажі без сцен'}})).json();
  await page.goto(`/stories/${story.id}/characters`);
  await expect(page.locator('#characters-preview')).toBeDisabled();
  await page.locator('#characters-add').click();
  await page.locator('.character-editor input').fill('Марія');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('#characters-return').click();
  await expect(page.locator('#characters-page')).toBeVisible();
  await page.route(`**/api/stories/${story.id}/characters`,async route=>{
    if(route.request().method()==='PUT')await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({detail:'Конфлікт версій'})});else await route.continue();
  });
  await page.locator('#characters-save').click();
  await expect(page.locator('#characters-status')).toContainText('Конфлікт');
  await expect(page.locator('.character-editor input')).toHaveValue('Марія');
  await expect(page.locator('#characters-save')).toBeEnabled();
});


test('unsaved manuscript is protected before opening characters',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}`);
  await expect(page.locator('#editor')).toBeEditable();
  await page.locator('#editor').fill('Незбережений план.');
  page.once('dialog',dialog=>dialog.dismiss());
  await page.locator('#workspace-characters').click();
  await expect(page.locator('#workspace')).toBeVisible();
  await expect(page.locator('#editor')).toHaveValue('Незбережений план.');
});
