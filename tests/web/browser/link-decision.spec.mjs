import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS-S08/S15 in the browser: the «Узгодженість сцени» panel offers «Я перевірив сам» for an unchecked brief and prose.
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
  const panel=page.locator('#scene-consistency');
  const briefRow=panel.locator('li[data-link="brief"]'),proseRow=panel.locator('li[data-link="prose"]'),memoryRow=panel.locator('li[data-link="memory"]');
  await expect(panel.locator('#scene-consistency-title')).toHaveText('Узгодженість сцени');
  await expect(briefRow).toHaveAttribute('data-state','pending');
  await expect(briefRow.locator('.consistency-status')).toHaveText('не перевірено');
  await expect(proseRow).toHaveAttribute('data-state','pending');
  await briefRow.getByRole('button',{name:'Я перевірив сам'}).click();
  await expect(panel).toBeFocused();  // Review Focus 4: the focus waits on the panel while the row redraws
  await expect(briefRow).toHaveAttribute('data-state','ok');
  await expect(briefRow.locator('.consistency-status')).toHaveText('узгоджено · ви');
  await proseRow.getByRole('button',{name:'Я перевірив сам'}).click();
  await expect(proseRow).toHaveAttribute('data-state','ok');
  await expect(panel).toBeFocused();
  // The scene has no memory yet, so it is not valid: the memory row stays, with the memory stage as its action.
  await expect(panel.locator('.consistency-badge')).toHaveText('1 з 3 не перевірено');
  await expect(memoryRow).toContainText('У сцени ще немає пам’яті');
  await expect(memoryRow.getByRole('button',{name:'Створити пам’ять'})).toHaveClass(/link-button/);
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
  const panel=page.locator('#scene-consistency');
  await expect(panel.locator('li[data-link="memory"]')).toContainText('Пам’ять не підтверджена: прозу змінено після неї.');
  await expect(panel.getByRole('button',{name:'Створити нову пам’ять'})).toBeVisible();
  await panel.getByRole('button',{name:'Залишити попередню пам’ять'}).click();
  await expect(panel).not.toContainText('Пам’ять не підтверджена');
  await expect(panel).toBeFocused();
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
  const panel=page.locator('#scene-consistency');
  await expect(panel.locator('li[data-link="brief"]')).toContainText('Попередня сцена «Ранок» не має пам’яті');
  await panel.getByRole('button',{name:'Створити пам’ять'}).click();
  await expect(page.locator('#scene-title')).toContainText('Ранок');
  const dialog=page.getByRole('dialog');
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button',{name:/Скасувати|Ні/}).click();
  const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  expect(runs).toEqual([]);
  await expect(panel).toContainText('У сцени ще немає пам’яті');
});
