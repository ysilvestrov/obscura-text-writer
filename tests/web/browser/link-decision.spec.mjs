import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS-S08 in the browser: an unchecked brief and prose of the open scene offer the author's approval.
test.use({locale:'uk-UA'});

test('the author approves the brief and the prose of a scene',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Маяк'}})).json();
  let scene=await(await request.post(`/api/stories/${story.id}/scenes`,{data:{title:'Ранок'}})).json();
  const brief={objective:'Світло на воді',beats:['Маяк'],constraints:[],proposed_changes:[]};
  let saved=await request.post(`/api/scenes/${scene.id}/brief`,{data:{text:JSON.stringify(brief),expected_revision:scene.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  scene=(await saved.json()).scene;
  saved=await request.post(`/api/scenes/${scene.id}/prose`,{data:{text:'Ранок: світло на воді.',expected_revision:scene.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  await page.goto(`/stories/${story.id}?scene=${scene.id}&material=prose`);
  const panel=page.locator('#link-attention');
  await expect(panel).toContainText('Завдання не підтверджено');
  await expect(panel).toContainText('Проза не підтверджена');
  await panel.getByRole('button',{name:'Затвердити завдання'}).click();
  await expect(panel).not.toContainText('Завдання не підтверджено');
  await panel.getByRole('button',{name:'Затвердити відповідність'}).click();
  await expect(panel).not.toContainText('Проза не підтверджена');
  // The scene has no memory yet: only that row stays, with the memory stage as its action.
  await expect(panel.locator('.link-attention-row')).toHaveCount(1);
  await expect(panel).toContainText('У сцени ще немає пам’яті');
  await expect(panel.getByRole('button',{name:'Створити пам’ять'})).toBeVisible();
  const view=await(await request.get(`/api/stories/${story.id}`)).json();
  expect(view.material_status[scene.id].links.brief.source).toBe('author');
  expect(view.material_status[scene.id].links.prose.source).toBe('author');
});

// VALID-LINKS-S11 in the browser: keeping the earlier memory (Z3) clears its note and the next scene may run again.
test('«Залишити попередню пам’ять» unblocks the next scene',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-decision')).json();
  const readiness=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/readiness`,{params:{scene_id:fixture.second_id,operation:'draft'}})).json()).operations.draft;
  const before=await readiness();
  expect(before.ready).toBe(false);
  expect(before.reason).toContain('пам’ять попередньої сцени');
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.first_id}&material=memory`);
  const panel=page.locator('#link-attention');
  await expect(panel).toContainText('Пам’ять не підтверджена: прозу змінено після неї.');
  await expect(panel.getByRole('button',{name:'Створити нову пам’ять'})).toBeVisible();
  await panel.getByRole('button',{name:'Залишити попередню пам’ять'}).click();
  await expect(panel).not.toContainText('Пам’ять не підтверджена');
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect(view.material_status[fixture.first_id].links.memory.source).toBe('author');
  const after=await readiness();
  expect(after.ready,after.reason).toBe(true);
});

// VALID-LINKS-S11: without the previous scene's memory the panel names that scene and opens it to create the memory
// through the usual run preview (cancelled here: nothing runs).
test('«Створити пам’ять» opens the previous scene and asks before the run',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-decision?previous_memory=false')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.second_id}&material=brief`);
  const panel=page.locator('#link-attention');
  await expect(panel).toContainText('Попередня сцена «Ранок» не має пам’яті');
  await panel.getByRole('button',{name:'Створити пам’ять'}).click();
  await expect(page.locator('#scene-title')).toContainText('Ранок');
  const dialog=page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:/Скасувати|Ні/}).click();
  const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  expect(runs).toEqual([]);
  await expect(panel).toContainText('У сцени ще немає пам’яті');
});
