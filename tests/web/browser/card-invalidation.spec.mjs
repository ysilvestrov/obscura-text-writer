import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS rule (г) in the browser: after a card is saved the author decides whether the dependent scenes lose the
// validity of their links; «Ні» changes nothing.
test.use({locale:'uk-UA'});

async function saveChangedCard(page,request){
  const fixture=await(await request.post('/test-card-invalidation')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  await expect(page.locator('#workspace-scene-status')).toContainText('Валідна');
  await page.goto(`/stories/${fixture.story_id}/characters?scene=${fixture.scene_id}`);
  const card=page.locator('.character-editor fieldset').first();
  await expect(card.locator('textarea')).toHaveValue('Доглядачка маяка.');
  await card.locator('textarea').fill('Доглядачка маяка на пагорбі.');
  await page.locator('#characters-save').click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('Змінено картки: Олена. Позначити 1 залежних сцен як неперевірені?');
  return {fixture,dialog};
}

test('«Так» marks the dependent scene unchecked',async({page,request})=>{
  const {fixture,dialog}=await saveChangedCard(page,request);
  await dialog.getByRole('button',{name:'Так'}).click();
  await expect(page.locator('#notice')).toContainText('Залежні сцени позначено як неперевірені.');
  await page.locator('#characters-return').click();
  await expect(page.locator('#workspace-scene-status')).toContainText('Не перевірено');
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect(view.material_status[fixture.scene_id].links.brief.status).toBe('unchecked');
});

test('«Ні» keeps the scene valid',async({page,request})=>{
  const {fixture,dialog}=await saveChangedCard(page,request);
  await dialog.getByRole('button',{name:'Ні'}).click();
  await expect(dialog).toBeHidden();
  await page.locator('#characters-return').click();
  await expect(page.locator('#workspace-scene-status')).toContainText('Валідна');
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect(view.material_status[fixture.scene_id].validity).toBe('valid');
});

test('a location description asks too, and «Так» unchecks the scene',async({page,request})=>{
  const fixture=await(await request.post('/test-card-invalidation')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=memory`);
  await expect(page.locator('#workspace-scene-status')).toContainText('Валідна');
  const hill=page.locator('#memory-view #story-locations .location-row').filter({has:page.locator('strong',{hasText:/^Пагорб$/})});
  await hill.locator('summary').click();
  await hill.locator('textarea').fill('Вітряний пагорб над морем.');
  await hill.getByRole('button',{name:'Зберегти опис'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('Змінено локації: Пагорб. Позначити 1 залежних сцен як неперевірені?');
  await dialog.getByRole('button',{name:'Так'}).click();
  await expect(page.locator('#workspace-scene-status')).toContainText('Не перевірено');
});
