import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

// R-49 (WRITING-MODE-S09): a «Пишу сам» story offers no prose run in the workspace; memory and the brief stay.
const PROSE_RUNS=['Написати','Редагувати','Уся сцена','Пройти решту'];

async function controls(page){
  await page.locator('.workspace-extra summary').click();
  return page.locator('#generation-controls');
}

test('the author mode hides prose runs and the primary action leads to the prose',async({page,request})=>{
  const f=await(await request.post('/test-author-mode')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=plan`);
  await expect(page.locator('#workspace-primary')).toHaveText('Писати прозу');
  const panel=await controls(page);
  for(const label of PROSE_RUNS)await expect(panel.getByRole('button',{name:label,exact:true})).toBeHidden();
  await expect(panel.getByRole('button',{name:'Створити завдання',exact:true})).toBeVisible();
  await expect(panel.getByRole('button',{name:'Оновити пам’ять',exact:true})).toBeVisible();
  await page.locator('#workspace-primary').click();
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
});

test('the draft tab offers taking the draft as prose, not editing it',async({page,request})=>{
  const f=await(await request.post('/test-author-mode')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=draft`);
  await expect(page.locator('#workspace-primary')).toHaveText('Взяти як прозу');
  await expect(page.locator('#workspace-use-draft')).toBeHidden();
  await expect(page.locator('#assisted-writing')).toBeHidden();
});

test('a mode switch in another window redraws the actions on return',async({page,request})=>{
  const f=await(await request.post('/test-author-mode?mode=obscura')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=plan`);
  const panel=await controls(page);
  await expect(panel.getByRole('button',{name:'Уся сцена',exact:true})).toBeVisible();
  const story=(await(await request.get(`/api/stories/${f.story_id}`)).json()).story;
  expect((await request.put(`/api/stories/${f.story_id}/writing-mode`,{data:{writing_mode:'author',expected_revision:story.revision}})).ok()).toBe(true);
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await expect(panel.getByRole('button',{name:'Уся сцена',exact:true})).toBeHidden();
  await expect(page.locator('#workspace-primary')).toHaveText('Писати прозу');
});
