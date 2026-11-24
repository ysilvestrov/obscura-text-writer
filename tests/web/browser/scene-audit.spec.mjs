import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS-S15 in the browser: «Перевірити Ревізором» in the «Узгодженість сцени» panel names the calls of the
// scene's preview and runs the auditor only after the preview dialog and the author's consent; its discrepancies appear
// in their row as hints with quotes, and the author's «Розбіжності немає» clears the row.
test.use({locale:'uk-UA'});

const scenePreview=async(request,storyId,sceneId)=>
  (await(await request.post(`/api/stories/${storyId}/audit/preview`,{data:{scope:'scene',scene_id:sceneId}})).json());

test('a valid scene offers no check',async({page,request})=>{
  const fixture=await(await request.post('/test-card-invalidation')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  await expect(page.locator('#workspace-scene-status')).toContainText('Валідна');
  await expect(page.locator('#audit-scene')).toHaveCount(0);
  await expect(page.locator('#scene-consistency')).toHaveText('Сцена узгоджена ✓');
  await expect(page.locator('#scene-consistency-primary')).toHaveCount(0);
  // M5: the label of the panel exists in the valid view too.
  await expect(page.locator('#scene-consistency-title')).toHaveText('Сцена узгоджена ✓');
});

test('the auditor checks the scene after consent and the author decides its discrepancy',async({page,request})=>{
  const fixture=await(await request.post('/test-scene-audit')).json();
  const runs=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  const before=await scenePreview(request,fixture.story_id,fixture.scene_id);
  expect(before.calls).toBe(2);
  // Review Focus 4: a preview that arrives while «Я перевірив сам» has the focus leaves the focus there.
  let release;const held=new Promise(resolve=>{release=resolve});
  await page.route('**/audit/preview',async route=>{await held;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  const panel=page.locator('#scene-consistency'),button=page.locator('#scene-consistency-primary'),cost=panel.locator('.consistency-cost');
  const brief=panel.locator('li[data-link="brief"]');
  const approve=brief.getByRole('button',{name:'Я перевірив сам'});
  await expect(button).toHaveText('Перевірити Ревізором');
  await expect(button).toBeDisabled();  // no preview yet
  await approve.focus();
  await page.waitForTimeout(500);
  release();
  // A local auditor has no price: the calls only.
  await expect(cost).toHaveText(`Викликів: ${before.calls}`);
  await expect(approve).toBeFocused();
  await page.unroute('**/audit/preview');
  await expect(button).toBeEnabled();
  await expect(button).not.toHaveClass(/secondary/);
  await expect(button).toHaveAttribute('aria-describedby','scene-consistency-reason');
  // The main button keeps the focus across a refresh of the story.
  await button.focus();
  await page.evaluate(()=>document.dispatchEvent(new CustomEvent('story-refreshed')));
  await expect(button).toBeFocused();
  // The preview names the links and the auditor's model; cancelling it starts nothing.
  await button.click();
  let dialog=page.getByRole('dialog');
  await expect(dialog).toContainText('Зв’язки до перевірки: завдання, проза');
  await expect(dialog).toContainText('synthetic-auditor');
  await dialog.getByRole('button',{name:'Скасувати'}).click();
  await expect(dialog).toBeHidden();
  expect(await runs()).toEqual([]);
  // Review Focus 3: the author's own check of the brief leaves one call for the auditor.
  await approve.click();
  await expect(panel).toBeFocused();
  await expect(brief).toHaveAttribute('data-state','ok');
  await expect(cost).toHaveText(`Викликів: ${before.calls-1}`);
  await button.click();
  dialog=page.getByRole('dialog');
  await expect(dialog).toContainText('Зв’язки до перевірки: проза');
  await dialog.getByRole('button',{name:'Підтвердити'}).click();
  // The run stops on the prose: its row shows both discrepancies with their quotes as hints to check.
  const row=panel.locator('li[data-link="prose"]');
  await expect(row).toHaveAttribute('data-state','discrepancy');
  await expect(row.locator('.consistency-status')).toHaveText('Ревізор: можлива розбіжність (упевненість у відповідності — 35%)');
  await expect(row.locator('.link-audit-summary')).toHaveText('Завдання може розходитися з планом');
  await expect(row).toContainText('Пояснення моделі бувають неточні');
  await expect(row.locator('.link-discrepancy')).toHaveCount(2);
  await expect(row).toContainText('Місце дії не збігається з планом');
  await expect(row.locator('blockquote').first()).toHaveText('Світло на воді');
  await expect.poll(async()=>(await runs()).at(-1)?.state).toBe('needs_review');
  // Visible run progress replaces the plan line: the scene check names its scene, the calls against the plan and the
  // auditor's model; it has no input material, so no «Невідомо».
  const progress=page.locator('#run-status .run-progress');
  await expect(progress.locator('.run-progress-title')).toHaveText(/^Перевірка сцени «.+»$/);
  await expect(progress.locator('.run-progress-counts')).toHaveText(/^Викликів: \d+ \/ \d+/);
  await expect(progress.locator('.run-progress-model')).toHaveText(/^\S+ \/ synthetic-auditor$/);
  await expect(progress).not.toContainText('Невідомо');
  const run=(await(await request.get(`/api/runs/${(await runs()).at(-1).id}`)).json()).run;
  expect(run.request.mode).toBe('audit');
  expect(run.checkpoint.link).toBe('prose');
  // R-44: the run carries the plan the author consented to.
  expect(run.request.audit_plan_fingerprint).toMatch(/^[a-f0-9]{64}$/);
  await row.getByRole('button',{name:'Розбіжності немає'}).click();
  await expect(row).toHaveAttribute('data-state','ok');
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect(view.material_status[fixture.scene_id].links.prose.source).toBe('author');
});

test('the main action is disabled with its reason',async({page,request})=>{
  // Brief approved by the author, then the auditor's discrepancy on the prose: nothing is left for the auditor.
  const fixture=await(await request.post('/test-scene-audit')).json();
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  const decided=await request.post(`/api/scenes/${fixture.scene_id}/links/brief/decision`,
    {data:{action:'approve',fingerprint:view.material_status[fixture.scene_id].links.brief.fingerprint}});
  expect(decided.ok(),await decided.text()).toBeTruthy();
  const plan=await scenePreview(request,fixture.story_id,fixture.scene_id);
  const started=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.scene_id,
    mode:'audit',stage:null,audit_scope:'scene',audit_plan_fingerprint:plan.plan_fingerprint,pause_after:[]}}});
  expect(started.ok(),await started.text()).toBeTruthy();
  const runId=(await started.json()).id;
  await expect.poll(async()=>(await(await request.get(`/api/runs/${runId}`)).json()).run.state).toBe('needs_review');
  expect((await scenePreview(request,fixture.story_id,fixture.scene_id)).calls).toBe(0);
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  const button=page.locator('#scene-consistency-primary'),reason=page.locator('#scene-consistency-reason');
  await expect(page.locator('#scene-consistency li[data-link="prose"]')).toHaveAttribute('data-state','discrepancy');
  await expect(reason).toHaveText('Ревізору нема що перевіряти: вирішіть зв’язки вручну');
  await expect(button).toBeDisabled();
  // I1: typing updates the main action in place; the rows are not rebuilt and the panel is not a live region.
  await expect(page.locator('#scene-consistency')).not.toHaveAttribute('aria-live',/.*/);
  const rowNode=await page.locator('#scene-consistency li[data-link="prose"]').elementHandle();
  // An unsaved edit wins: the reason names it.
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await expect(editor).toHaveAttribute('contenteditable','true');
  await editor.click();await page.keyboard.press('Control+End');await page.keyboard.type(' Човен.');
  await expect(reason).toHaveText('Спершу збережіть ручні правки');
  await expect(button).toBeDisabled();
  await page.keyboard.type(' Ще.');
  expect(await rowNode.evaluate(node=>node.isConnected)).toBe(true);
});

test('a failed preview is read again on the next refresh',async({page,request})=>{
  // M3: an error of the preview request is not kept as a permanent reason.
  const fixture=await(await request.post('/test-scene-audit')).json();
  let fail=true;
  await page.route('**/audit/preview',async route=>{
    if(fail){await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({detail:'Тимчасова помилка'})});return}
    await route.continue();
  });
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  const button=page.locator('#scene-consistency-primary'),reason=page.locator('#scene-consistency-reason');
  await expect(reason).toBeVisible();
  await expect(button).toBeDisabled();
  fail=false;
  await page.evaluate(()=>document.dispatchEvent(new CustomEvent('story-refreshed')));
  await expect(page.locator('#scene-consistency .consistency-cost')).toHaveText("Викликів: 2");
  await expect(button).toBeEnabled();
  await expect(reason).toBeHidden();
});

test('a late preview of another scene is dropped',async({page,request})=>{
  // Review Focus 2: the first scene's preview answers after the author opened the second scene.
  const fixture=await(await request.post('/test-book-validation')).json();
  // The second scene's brief is the author's, so its preview counts fewer calls than the first scene's.
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  const decided=await request.post(`/api/scenes/${fixture.second_id}/links/brief/decision`,
    {data:{action:'approve',fingerprint:view.material_status[fixture.second_id].links.brief.fingerprint}});
  expect(decided.ok(),await decided.text()).toBeTruthy();
  const own=await scenePreview(request,fixture.story_id,fixture.second_id);
  expect(own.calls).not.toBe((await scenePreview(request,fixture.story_id,fixture.first_id)).calls);
  let first=true;
  await page.route('**/audit/preview',async route=>{
    const body=route.request().postDataJSON();
    if(first&&body.scene_id===fixture.first_id){first=false;await new Promise(resolve=>setTimeout(resolve,1500))}
    await route.continue();
  });
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.first_id}&material=prose`);
  await expect(page.locator('#scene-consistency-primary')).toBeVisible();
  if(test.info().project.name==='mobile')await page.locator('#scene-select-mobile').selectOption(fixture.second_id);
  else await page.locator('#scene-list .scene-item').nth(1).click();
  await expect(page.locator('#scene-title')).toContainText('Вечір');
  await page.waitForTimeout(2000);
  await expect(page.locator('#scene-consistency .consistency-cost')).toHaveText(`Викликів: ${own.calls}`);
});

// MODEL-001: an auditor without saved settings runs on the editor's model; saving its form keeps a row of its own, with
// the stage prompts of audit_brief and audit_memory beside the main one.
test('the auditor settings borrow the editor until saved',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-decision')).json();
  const url=`/api/stories/${fixture.story_id}/settings`;
  await page.goto(`/stories/${fixture.story_id}/settings`);
  await page.locator('[data-settings-role="auditor"]').click();
  const form=page.locator('form[data-role="auditor"]');
  await expect(form.locator('[data-auditor-derived]')).toHaveText('Поки Ревізора не збережено, він бере модель редактора.');
  await expect(form.locator('[name="model"]')).toHaveValue('synthetic-editor');
  await expect(form.locator('[name="stage_audit_brief"]')).toHaveCount(1);
  await expect(form.locator('[name="stage_audit_memory"]')).toHaveCount(1);
  await form.locator('summary',{hasText:'Промпти та їхні призначення'}).click();
  await form.locator('[name="stage_audit_brief"]').fill('Перевір завдання сцени й відповідай JSON.');
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  const data=await(await request.get(url)).json();
  expect(data.roles.auditor.derived).toBeUndefined();
  expect(data.roles.auditor.provider.model).toBe('synthetic-editor');
  expect(data.stage_prompts.auditor.audit_brief).toBe('Перевір завдання сцени й відповідай JSON.');
  await expect(form.locator('[data-auditor-derived]')).toHaveCount(0);
});

// MODEL-001: the derived auditor follows the editor, so saving the editor refreshes the auditor form; saving the auditor
// afterwards meets no conflict.
test('the derived auditor form follows a saved editor',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-decision')).json();
  const url=`/api/stories/${fixture.story_id}/settings`;
  await page.goto(`/stories/${fixture.story_id}/settings`);
  await page.locator('[data-settings-role="editor"]').click();
  await page.locator('form[data-role="editor"] [name="model"]').fill('synthetic-editor-2');
  let saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  await page.locator('[data-settings-role="auditor"]').click();
  const form=page.locator('form[data-role="auditor"]');
  await expect(form.locator('[name="model"]')).toHaveValue('synthetic-editor-2');
  await expect(form.locator('[data-auditor-derived]')).toHaveCount(1);
  await form.locator('[name="temperature"]').fill('0.3');
  saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  const data=await(await request.get(url)).json();
  expect(data.roles.auditor.derived).toBeUndefined();
  expect(data.roles.auditor.provider.model).toBe('synthetic-editor-2');
  expect(data.roles.auditor.temperature).toBe(0.3);
});
