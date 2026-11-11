import {test,expect} from '../../../frontend/browser-test.mjs';

test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();
// The scene panel lives in a collapsed details block on both layouts; opening it is not layout specific.
const openPanel=async page=>{
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  await expect(page.locator('#scene-settings')).toBeVisible();
};
const selectScene=async(page,index)=>{
  if(test.info().project.name==='mobile'){
    const option=await page.locator('#scene-select-mobile option').nth(index).getAttribute('value');await page.locator('#scene-select-mobile').selectOption(option);
  }else await page.locator('#scene-list .scene-item').nth(index).click();
};
const selectedSceneId=page=>page.evaluate(async()=>(await import('/static/editor.js')).state.scene?.id??null);

test('a slow scene settings save does not pull the selection back to its scene',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  const second=await(await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Друга сцена',beats:'Прогулянка.'}})).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(2);
  await openPanel(page);
  let release;const held=new Promise(resolve=>{release=resolve});
  await page.route(`**/api/scenes/${scene_id}`,async route=>{if(route.request().method()==='PATCH')await held;await route.continue()});
  const form=page.locator('#scene-settings');
  await form.locator('input[name="title"]').fill('Перейменована сцена');
  await form.getByRole('button',{name:'Зберегти параметри'}).click();
  await selectScene(page,1);
  await expect.poll(()=>selectedSceneId(page)).toBe(second.id);
  release();
  await expect(page.locator('#notice')).toContainText('Параметри сцени збережено');
  expect(await selectedSceneId(page)).toBe(second.id);
  await expect(form.locator('input[name="title"]')).toHaveValue('Друга сцена');
  expect((await view(request,story_id)).scenes.find(s=>s.id===scene_id).title).toBe('Перейменована сцена');
});
