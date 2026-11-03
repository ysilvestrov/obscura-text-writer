import {test,expect} from '../../../frontend/browser-test.mjs';
async function selectSecond(page){
  if(test.info().project.name==='mobile'){
    const option=await page.locator('#scene-select-mobile option').nth(1).getAttribute('value');await page.locator('#scene-select-mobile').selectOption(option);
  }else await page.locator('#scene-list .scene-item').nth(1).click();
}

test('reload restores scene and material separately for each story',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  const second=await(await request.post(`/api/stories/${fixture.story_id}/scenes`,{data:{title:'Друга сцена',beats:'Прогулянка.'}})).json();
  await page.goto(`/stories/${fixture.story_id}`);await expect(page.locator('#scene-list .scene-item')).toHaveCount(2);
  await selectSecond(page);await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
  await page.reload();
  await expect(page.locator('#scene-title')).toHaveText('Друга сцена');
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
  const other=await(await request.post('/test-fixture')).json();await page.goto(`/stories/${other.story_id}`);
  await expect(page.locator('#mode-tabs [data-mode="plan"]')).toHaveAttribute('aria-selected','true');
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  await page.goto(`/stories/${fixture.story_id}`);
  await expect(page.locator('#scene-title')).toHaveText('Друга сцена');
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
  // A direct link intentionally overrides the browser's remembered position.
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await selectSecond(page);await page.locator('#mode-tabs [data-mode="memory"]').click();await page.reload();
  await expect(page.locator('#scene-title')).toHaveText('Друга сцена');
  await expect(page.locator('#mode-tabs [data-mode="memory"]')).toHaveAttribute('aria-selected','true');
});


test('deleted scene falls back to first available outline',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  const second=await(await request.post(`/api/stories/${fixture.story_id}/scenes`,{data:{title:'Тимчасова сцена'}})).json();
  await page.goto(`/stories/${fixture.story_id}`);await expect(page.locator('#scene-list .scene-item')).toHaveCount(2);
  await selectSecond(page);await page.locator('#mode-tabs [data-mode="memory"]').click();
  const deleted=await request.post(`/api/scenes/${second.id}/trash`,{data:{story_id:fixture.story_id,expected_revision:second.revision}});expect(deleted.ok()).toBeTruthy();
  await page.reload();await expect(page.locator('#scene-title')).toHaveText('Зорі над парком');
  await expect(page.locator('#mode-tabs [data-mode="plan"]')).toHaveAttribute('aria-selected','true');
});

test('restricted storage still restores the current URL',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.addInitScript(()=>Object.defineProperty(window,'localStorage',{get(){throw new DOMException('blocked','SecurityError');}}));
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await page.locator('#mode-tabs [data-mode="draft"]').click();await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');await page.reload();
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
});

test('history viewing does not replace the remembered current material',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);await page.locator('#mode-tabs [data-mode="draft"]').click();
  const refs=await(await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  await page.locator('#workspace-history summary').click();await page.locator('#history-version').selectOption(refs.scene.heads.prose);
  await page.getByRole('button',{name:/Переглянути версію|View version/,exact:true}).click();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','false');await page.reload();
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
  const saved=await page.evaluate(id=>JSON.parse(localStorage.getItem('obscura.workspace.v1.'+id)),fixture.story_id);
  expect(Object.keys(saved).sort()).toEqual(['material','scene_id']);
});
