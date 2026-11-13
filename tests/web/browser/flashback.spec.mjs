import {test,expect} from '../../../frontend/browser-test.mjs';

// STORY-TIME-S07 in the browser: the «Спогад» checkbox, the scene list mark and the structure panel hint (neutral book).
test.use({locale:'uk-UA'});
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();
const openPanel=async page=>{
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  await expect(page.locator('#scene-settings')).toBeVisible();
};
const selectScene=async(page,index)=>{
  if(test.info().project.name==='mobile'){
    const option=await page.locator('#scene-select-mobile option').nth(index).getAttribute('value');await page.locator('#scene-select-mobile').selectOption(option);
  }else await page.locator('#scene-list .scene-item').nth(index).click();
};

test('the flashback checkbox is saved and marks the scene in the list',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await openPanel(page);
  const form=page.locator('#scene-settings');
  const box=form.getByRole('checkbox',{name:'Спогад'});
  await expect(box).not.toBeChecked();await expect(box).toBeEnabled();
  await box.check();
  await form.getByRole('button',{name:'Зберегти параметри'}).click();
  await expect(page.locator('#notice')).toContainText('Параметри сцени збережено');
  expect((await view(request,story_id)).scenes.find(s=>s.id===scene_id).flashback).toBe(true);
  if(test.info().project.name!=='mobile')await expect(page.locator('#scene-list .scene-item').first()).toContainText('спогад');
});

test('a flashback mark in «Початок:» checks and locks the checkbox',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  const marked=await(await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Давнина',beats:'Початок: Рік -2 (спогад)\nПрогулянка.'}})).json();
  await page.goto(`/stories/${story_id}`);
  await expect(page.locator('#scene-list .scene-item')).toHaveCount(2);
  await selectScene(page,1);
  await openPanel(page);
  await expect(page.locator('#scene-settings input[name="title"]')).toHaveValue('Давнина');
  const box=page.locator('#scene-settings').getByRole('checkbox',{name:'Спогад'});
  await expect(box).toBeChecked();await expect(box).toBeDisabled();
  await expect(page.locator('#scene-flashback-help')).toContainText('позначкою в рядку «Початок:»');
});

test('the structure panel hints at an arc with an unknown start',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  const second=await(await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Давнина',beats:'Початок: Рік -2 (спогад)'}})).json();
  const data=await view(request,story_id);
  const parts=[{id:'p1',title:'Дім',arcs:[{id:'a1',title:'Ранок'},{id:'a2',title:'Вечір'}]}];
  const put=await request.put(`/api/stories/${story_id}/structure`,{data:{expected_revision:data.story.revision,parts,scene_arcs:{[scene_id]:'a1',[second.id]:'a2'}}});
  expect(put.ok(),await put.text()).toBeTruthy();
  await page.goto(`/stories/${story_id}/settings`);
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
  await expect(page.locator('#book-structure .book-structure-arc-hint')).toHaveCount(2);
  await expect(page.locator('#book-structure .book-structure-arc-hint').first()).toContainText('Початок арки невідомий');
});
