import {test,expect} from '../../../frontend/browser-test.mjs';

// R-44 book validation in the browser: the story menu counts the invalid scenes, the preview names scenes, calls and
// the auditor, and nothing runs without consent. The run stops on the first discrepancy; its summary leads to the scene,
// and after the author's approval and «Продовжити» the rest of the book is checked and the counter reaches 0.
test.use({locale:'uk-UA'});

test('book validation stops on a discrepancy, leads to the scene and finishes the book after resume',async({page,request})=>{
  const fixture=await(await request.post('/test-book-validation')).json();
  const runs=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.second_id}&material=prose`);
  const toggle=page.locator('#story-menu-toggle'),item=page.locator('#story-menu-validate');
  await toggle.click();
  await expect(item).toHaveText('Валідація книги (2)');
  await expect(item).toBeEnabled();
  // The preview: scenes, calls, the auditor and the caveat; cancelling starts nothing.
  await item.click();
  let dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('Сцен до перевірки: 2.');
  await expect(dialog).toContainText('До 4 викликів Ревізора');
  await expect(dialog).toContainText('synthetic-book-auditor');
  await expect(dialog).toContainText('правки під час перевірки');
  await dialog.getByRole('button',{name:'Скасувати'}).click();
  await expect(dialog).toBeHidden();
  expect(await runs()).toEqual([]);
  await toggle.click();
  await item.click();
  dialog=page.locator('dialog[open]');
  await dialog.getByRole('button',{name:'Почати валідацію'}).click();
  await expect.poll(async()=>(await runs()).at(-1)?.state).toBe('needs_review');
  const run=(await runs()).at(-1);
  expect(run.request.mode).toBe('audit');
  expect(run.request.audit_scope).toBe('story');
  // The stopped run leads to the first scene, where the link panel shows the discrepancy.
  const jump=page.locator('#run-stop-scene');
  await expect(jump).toHaveText('Перейти до сцени 1');
  // Visible progress: the run started from this tab opens expanded, with the focus on its title.
  const status=page.locator('#run-status'),title=status.locator('.run-progress-title');
  await expect(status).toHaveClass(/expanded/);
  await expect(title).toHaveText('Валідація книги: перевірено сцен 1 з 2 · «Ранок»');
  await expect(status.locator('.run-progress-step')).toHaveText('завдання ↔ план');
  await expect(status.locator('.run-progress-counts')).toHaveText(/^Викликів: 1 \/ 4/);
  await expect(status.locator('progress.run-progress-bar')).toHaveAttribute('value','0.25');
  await expect(title).toBeFocused();  // Review Focus 1: survives the redraws of queued → running → needs_review
  const cancel=page.locator('#run-actions').getByRole('button',{name:'Скасувати валідацію'});
  await expect(cancel).toHaveClass(/link-button/);
  await expect(jump).not.toHaveClass(/secondary/);
  // The menu leads to the stopped run and starts nothing.
  await page.locator('#editor').focus();
  await toggle.click();
  await expect(item).toHaveText('Валідацію зупинено: показати');
  await item.click();
  await expect(title).toBeFocused();
  expect((await runs()).length).toBe(1);
  // A page load opens the stopped run (needs_review) but does not move the focus.
  await page.reload();
  await expect(page.locator('#run-status')).toHaveClass(/expanded/);
  await expect(page.locator('#run-status .run-progress-title')).not.toBeFocused();
  await jump.click();
  await expect(page.locator('#scene-title')).toContainText('Ранок');
  const row=page.locator('#link-attention [data-link="brief"]');
  await expect(row).toContainText('Місце дії не збігається з планом');
  await expect(page.locator('#link-attention')).toBeFocused();  // Р7: the stop scene's link panel takes the focus
  await row.getByRole('button',{name:'Затвердити завдання'}).click();
  await expect(row).toHaveCount(0);
  await page.locator('#run-actions').getByRole('button',{name:'Продовжити'}).click();
  dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('Сцен до перевірки: 2.');
  await dialog.getByRole('button',{name:'Підтвердити'}).click();
  await expect.poll(async()=>(await runs()).at(-1)?.state).toBe('completed');
  await expect(jump).toBeHidden();
  // Review Focus 2: the resumed run counts against the extended plan.
  await expect(page.locator('#run-status .run-progress-title')).toHaveText('Валідація книги: перевірено сцен 2 з 2 · «Вечір»');
  await expect(page.locator('#run-status .run-progress-counts')).toHaveText(/^Викликів: \d \/ 4/);
  await expect(page.locator('#run-status .run-progress-title')).toBeFocused();  // Р2: a resume from this tab focuses its row
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect([fixture.first_id,fixture.second_id].map(id=>view.material_status[id].validity)).toEqual(['valid','valid']);
  await toggle.click();
  await expect(item).toHaveText('Книга валідна');
  await expect(item).toBeDisabled();
});

test('a plan that changed after the preview starts nothing and offers the preview again',async({page,request})=>{
  const fixture=await(await request.post('/test-book-validation')).json();
  const runs=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.second_id}&material=prose`);
  await page.locator('#story-menu-toggle').click();
  await page.locator('#story-menu-validate').click();
  let dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('Сцен до перевірки: 2.');
  // While the dialog is open the first scene's prose changes: the consented plan is stale.
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  const first=view.scenes.find(scene=>scene.id===fixture.first_id);
  const saved=await request.post(`/api/scenes/${first.id}/prose`,{data:{text:'Олена запалила старий маяк.',expected_revision:first.revision}});
  expect(saved.ok(),await saved.text()).toBeTruthy();
  await dialog.getByRole('button',{name:'Почати валідацію'}).click();
  dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('План перевірки змінився. Перегляньте його ще раз');
  expect(await runs()).toEqual([]);
  await dialog.getByRole('button',{name:'Переглянути знову'}).click();
  dialog=page.locator('dialog[open]');
  await expect(dialog).toContainText('Сцен до перевірки: 2.');
  await dialog.getByRole('button',{name:'Скасувати'}).click();
  await expect(dialog).toBeHidden();
  expect(await runs()).toEqual([]);
});

test('the menu never takes the run line from another active run',async({page,request})=>{
  // Final(core) ruling 2: while a stage run streams, «Валідацію зупинено: показати» is disabled with its reason and a
  // `run-reveal` of the stopped validation leaves the active run in the line; once that run ends, the item shows the book run.
  const fixture=await(await request.post('/test-book-validation?slow_planner=true')).json();
  const runs=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  const preview=await(await request.post(`/api/stories/${fixture.story_id}/audit/preview`,{data:{scope:'story'}})).json();
  const book=await(await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:null,mode:'audit',
    stage:null,audit_scope:'story',audit_plan_fingerprint:preview.plan_fingerprint,pause_after:[]}}})).json();
  await expect.poll(async()=>(await runs()).find(run=>run.id===book.id)?.state).toBe('needs_review');
  const stage=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.second_id,
    mode:'stage',stage:'brief',pause_after:[]}}});
  expect(stage.ok(),await stage.text()).toBeTruthy();
  const active=await stage.json();
  try{
    await expect.poll(async()=>(await runs()).find(run=>run.id===active.id)?.state).toBe('running');
    await page.goto(`/stories/${fixture.story_id}?scene=${fixture.second_id}&material=prose`);
    const title=page.locator('#run-status .run-progress-title'),item=page.locator('#story-menu-validate');
    await expect(title).toHaveText('Сцена 1 з 1, етап: завдання');
    await page.locator('#story-menu-toggle').click();
    await expect(item).toHaveText('Валідацію зупинено: показати');
    await expect(item).toBeDisabled();
    await expect(item).toHaveAttribute('title','Рядок запуску зайнятий іншим запуском: дочекайтеся його завершення');
    const stopped=(await runs()).find(run=>run.id===book.id);
    await page.evaluate(run=>document.dispatchEvent(new CustomEvent('run-reveal',{detail:run})),stopped);
    await page.waitForTimeout(500);
    await expect(title).toHaveText('Сцена 1 з 1, етап: завдання');
    await expect(page.locator('#run-stop-scene')).toBeHidden();
  }finally{
    await request.post(`/api/runs/${active.id}/cancel`,{data:{}});
  }
  await expect.poll(async()=>(await runs()).find(run=>run.id===active.id)?.state).toBe('cancelled');
  // The active run is over: the item reveals the stopped validation and starts nothing.
  const item=page.locator('#story-menu-validate');
  if(!await item.isVisible())await page.locator('#story-menu-toggle').click();
  await expect(item).toBeEnabled();
  await expect(item).not.toHaveAttribute('title',/.+/);
  await item.click();
  await expect(page.locator('#run-status .run-progress-title')).toHaveText('Валідація книги: перевірено сцен 1 з 2 · «Ранок»');
  await expect(page.locator('#run-status .run-progress-title')).toBeFocused();
  expect((await runs()).length).toBe(2);
});
