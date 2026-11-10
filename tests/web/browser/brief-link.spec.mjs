import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

async function openProse(page,storyId){
  await page.goto(`/stories/${storyId}`);
  await page.locator('#mode-tabs [data-mode="prose"]').click();
}

test('author confirms the brief with introductions and moves to the next scene',async({page,request})=>{
  const f=await(await request.post('/test-brief-link')).json();
  await openProse(page,f.story_id);
  const panel=page.locator('#brief-link');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('Ранок у парку: нейтральне завдання');
  await expect(panel.locator('input[type=checkbox]')).toHaveCount(2);
  await panel.locator('input[value="nina"]').check();
  await panel.evaluate(node=>node.scrollIntoView({block:'end'}));
  await panel.screenshot({path:`../docs/images/brief-link-${test.info().project.name}.png`});
  await panel.locator('.brief-link-confirm').click();
  await expect(panel).toContainText('Ніна');
  await expect(panel.locator('.brief-link-confirm')).toHaveCount(0);
  const state=await(await request.get(`/api/scenes/${f.scene_ids[0]}/brief-link`)).json();
  expect(state.source).toBe('link');expect(state.link.introduced).toEqual(['nina']);
  await panel.getByRole('button',{name:/Наступна непідтверджена сцена|Next unconfirmed scene/}).click();
  await expect(panel).toContainText('Кав’ярня: нейтральне завдання');
});

test('conflict keeps the ticked introductions and saves nothing',async({page,request})=>{
  const f=await(await request.post('/test-brief-link')).json();
  await openProse(page,f.story_id);
  const panel=page.locator('#brief-link');
  await panel.locator('input[value="marko"]').check();
  const versions=await(await request.get(`/api/scenes/${f.scene_ids[0]}/versions`)).json();
  const changed=await request.patch(`/api/scenes/${f.scene_ids[0]}`,{data:{story_id:f.story_id,expected_revision:versions.scene.revision,title:'Ранок у парку'+' '}});
  expect(changed.ok()).toBeTruthy();
  await panel.locator('.brief-link-confirm').click();
  await expect(page.locator('#notice')).toHaveAttribute('data-kind','error');
  await expect(panel.locator('input[value="marko"]')).toBeChecked();
  const state=await(await request.get(`/api/scenes/${f.scene_ids[0]}/brief-link`)).json();
  expect(state.source).toBe('fallback');
});

test('opening the brief and switching scenes keep the ticked introductions',async({page,request})=>{
  const f=await(await request.post('/test-brief-link')).json();
  await openProse(page,f.story_id);
  const panel=page.locator('#brief-link');
  await panel.locator('input[value="marko"]').check();
  await panel.getByRole('button',{name:/Відкрити завдання/}).click();
  await expect(panel).toBeHidden();
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  await expect(panel.locator('input[value="marko"]')).toBeChecked();
  await panel.getByRole('button',{name:/Наступна непідтверджена сцена/}).click();
  await expect(panel).toContainText('Кав’ярня: нейтральне завдання');
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(f.scene_ids[0]);
  else await page.locator('#scene-list .scene-item').first().click();
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  await expect(panel.locator('input[value="marko"]')).toBeChecked();
});

test('prose replaced elsewhere cannot be confirmed from the stale editor',async({page,request})=>{
  const f=await(await request.post('/test-brief-link')).json();
  await openProse(page,f.story_id);
  const panel=page.locator('#brief-link');
  await panel.locator('input[value="nina"]').check();
  const versions=await(await request.get(`/api/scenes/${f.scene_ids[0]}/versions`)).json();
  const saved=await request.post(`/api/scenes/${f.scene_ids[0]}/prose`,{data:{expected_revision:versions.scene.revision,text:'Інша проза.'}});
  expect(saved.ok()).toBeTruthy();
  const newProse=(await saved.json()).version.id;
  await panel.locator('.brief-link-confirm').click();
  await expect(page.locator('#notice')).toHaveAttribute('data-kind','error');
  await expect(panel.locator('.brief-link-stale')).toBeVisible();
  await expect(panel.locator('.brief-link-confirm')).toBeDisabled();
  const state=await(await request.get(`/api/scenes/${f.scene_ids[0]}/brief-link`)).json();
  expect(state.prose_version_id).toBe(newProse);expect(state.link).toBeNull();
});
