import {test,expect} from '../../../frontend/browser-test.mjs';

// MEMORY-LOCATIONS-S07 in the browser: the «Locations» section lists cards, merges a look-alike, splits it back and
// saves a description; a location change does not make the next memory-kind change a conflict.
test.use({locale:'uk-UA'});

async function openPanel(page,request,material='plan'){
  const fixture=await(await request.post('/test-locations')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=${material}`);
  const section=page.locator('details.tool-section[data-section="locations"]');
  if(!await section.evaluate(node=>node.open))await section.locator(':scope > summary').click();
  const panel=page.locator('#story-locations');
  await expect(panel.locator('.location-row')).toHaveCount(4);
  return {fixture,panel};
}

const row=(panel,path)=>panel.locator('.location-row').filter({has:panel.page().locator('strong',{hasText:new RegExp(`^${path}$`)})});

test('the panel lists cards and merges a suggested look-alike, then splits it back',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  await expect(row(panel,'Квартира Джорджа / вітальня')).toContainText('Сцени: 1. Ранок');
  const hint=panel.locator('.location-suggestion');
  await expect(hint).toHaveCount(1);
  await expect(hint).toContainText('«Квартира Джоржа» схоже на «Квартира Джорджа»');
  await hint.getByRole('button',{name:'Злити'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('текст планів не зміниться');
  await dialog.getByRole('button',{name:'Злити'}).click();
  await expect(page.locator('#notice')).toContainText('Локації злито.');
  await expect(panel.locator('.location-suggestion')).toHaveCount(0);
  const merged=row(panel,'Квартира Джоржа');
  await expect(merged).toContainText('Злито в «Квартира Джорджа»');
  await expect(row(panel,'Квартира Джорджа')).toContainText('Сцени: 2. Вечір');
  await merged.getByRole('button',{name:'Розділити'}).click();
  await expect(page.locator('#notice')).toContainText('Злиття скасовано.');
  await expect(row(panel,'Квартира Джоржа')).not.toContainText('Злито');
});

test('a description is saved and a conflict keeps the typed text',async({page,request})=>{
  const {fixture,panel}=await openPanel(page,request);
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Тісний двір із липою.');
  await expect(yard).toContainText('21 / 2000');
  // Another tab changes the story first.
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const room=data.locations.find(card=>card.path==='Квартира Джорджа / вітальня');
  expect((await request.put(`/api/stories/${fixture.story_id}/locations/${room.id}`,
    {data:{description:'Інша вкладка.',expected_revision:data.story_revision}})).ok()).toBeTruthy();
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Твір уже змінено');
  await expect(row(panel,'двір').locator('textarea')).toHaveValue('Тісний двір із липою.');
  await row(panel,'двір').getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  await expect(row(panel,'двір').locator('summary')).toContainText('Тісний двір із липою.');
});

test('a location change does not turn the next memory-kind change into a conflict',async({page,request})=>{
  const {panel}=await openPanel(page,request,'memory');
  const kind=page.locator('select.memory-kind').first();
  await expect(kind).toBeVisible();
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Тісний двір.');
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  await kind.selectOption('atmosphere');
  await expect(page.locator('#notice')).toContainText('Тип запису збережено');
  await expect(page.locator('.memory-locations').first()).toContainText('Локації: Квартира Джорджа / вітальня');
});
