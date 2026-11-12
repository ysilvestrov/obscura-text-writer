import {test,expect} from '../../../frontend/browser-test.mjs';

// MEMORY-SUMMARY-S07 in the browser: blocks in the memory panel, editing with a conflict that keeps the text, saving.
test.use({locale:'uk-UA'});

async function openPanel(page,request){
  const fixture=await(await request.post('/test-timeline-summaries')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=memory`);
  const panel=page.locator('#timeline-summaries');
  await expect(panel.locator('.timeline-summary-row')).toHaveCount(2);
  return {fixture,panel};
}

test('the memory panel lists summary blocks',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  const first=panel.locator('.timeline-summary-row').first(),second=panel.locator('.timeline-summary-row').nth(1);
  await expect(first).toContainText('Сцени 1–10');
  await expect(first).toContainText('актуальний');
  await expect(first).toContainText('Анна приїхала до міста.');
  await expect(first.getByRole('button',{name:'Перебудувати'})).toBeVisible();
  await expect(second).toContainText('Сцени 11–20');
  await expect(second).toContainText('немає підсумку');
  await expect(second.getByRole('button',{name:'Створити підсумок'})).toBeVisible();
  await expect(second.getByRole('button',{name:'Редагувати'})).toHaveCount(0);
});

test('a correction is saved and replaces the text',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  const first=panel.locator('.timeline-summary-row').first();
  await first.getByRole('button',{name:'Редагувати'}).click();
  await first.locator('textarea').fill('Анна приїхала до міста навесні.');
  await first.getByRole('button',{name:'Зберегти підсумок'}).click();
  await expect(page.locator('#notice')).toContainText('Підсумок збережено.');
  await expect(first.locator('textarea')).toHaveCount(0);
  await expect(first).toContainText('Анна приїхала до міста навесні.');
});

test('editing keeps the typed text when another tab changed the summary',async({page,request})=>{
  const {fixture,panel}=await openPanel(page,request);
  const first=panel.locator('.timeline-summary-row').first();
  await first.getByRole('button',{name:'Редагувати'}).click();
  await first.locator('textarea').fill('Анна приїхала до міста й оселилася біля річки.');
  // Another tab changes the head first.
  const data=await(await request.get(`/api/stories/${fixture.story_id}/timeline-summaries`)).json();
  const block=data.blocks[0];
  expect((await request.put(`/api/stories/${fixture.story_id}/timeline-summaries/${block.key}`,
    {data:{text:'Інша вкладка.',expected_version_id:block.version_id,expected_revision:data.story_revision}})).ok()).toBeTruthy();
  await first.getByRole('button',{name:'Зберегти підсумок'}).click();
  await expect(page.locator('#notice')).toContainText('Підсумок уже змінено');
  await expect(first.locator('textarea')).toHaveValue('Анна приїхала до міста й оселилася біля річки.');
});
