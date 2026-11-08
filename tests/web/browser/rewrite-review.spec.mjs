import {test,expect} from '../../../frontend/browser-test.mjs';

test('one saved rewrite, draft-only review, partial apply and cleared notes',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#author-general')).toBeEnabled();
  await expect(page.getByRole('button',{name:/Переписати за коментарями|Rewrite from comments/,exact:true})).toBeDisabled();
  await page.locator('#author-general').fill('Скоротити й зробити виразнішим.');
  const seen=[];await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{seen.push(await dialog.locator('.app-dialog-message').innerText());await dialog.locator('.app-dialog-actions button').last().click();});
  await page.getByRole('button',{name:/Переписати за коментарями|Rewrite from comments/,exact:true}).click();
  const review=page.locator('#assisted-review');
  await expect(review.locator('.copyedit-item')).toHaveCount(2);
  expect(seen.length).toBe(2);
  await review.screenshot({path:`../artifacts/r23-ui/${test.info().project.name}-rewrite.png`});
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','false');
  await expect(review.locator('input[type=checkbox]:checked')).toHaveCount(0);
  await review.locator('input[type=checkbox]').first().check();
  await review.getByRole('button',{name:/Показати вибраний текст|Preview selected text/,exact:true}).click();
  await expect(review.locator('.copyedit-selected-text')).toContainText('сузір’я');
  await review.locator('[data-review-accept]').click();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
  await expect(page.locator('#author-general')).toHaveValue('');
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
  const sources=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(sources.comment_set.general).toBe('');
  const selectAll=review.locator('[data-review-select-all]');
  await expect(review.locator('input:checked')).toHaveCount(1);
  await expect(selectAll).toBeDisabled();
  await selectAll.evaluate(e=>e.onclick());
  await expect(review.locator('input:checked')).toHaveCount(1);
  await expect(review.locator('[data-review-accept]')).toBeDisabled();
});

test('cancel dirty Save keeps notes and makes no rewrite call',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#author-general')).toBeEnabled();
  await page.locator('#author-general').fill('Моя вказівка.');
  await page.getByRole('button',{name:/Переписати за коментарями|Rewrite from comments/,exact:true}).click();
  const dialog=page.locator('.app-dialog');await expect(dialog).toBeVisible();
  await dialog.locator('.app-dialog-actions button').first().click();await expect(dialog).toHaveCount(0);
  await expect(page.locator('#author-general')).toHaveValue('Моя вказівка.');
  const runs=await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json();
  expect(runs.runs).toHaveLength(0);
});


test('reject all preserves comments and creates no duplicate draft',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#author-general')).toBeEnabled();await page.locator('#author-general').fill('Моя вказівка.');
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await page.getByRole('button',{name:/Переписати за коментарями|Rewrite from comments/,exact:true}).click();
  const review=page.locator('#assisted-review');await expect(review.locator('.copyedit-item')).toHaveCount(2);
  const before=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  await review.locator('[data-review-accept]').click();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
  await expect(page.locator('#author-general')).toHaveValue('Моя вказівка.');
  const after=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(after.source_version_id).toBe(before.source_version_id);expect(after.comment_set.id).toBe(before.comment_set.id);
});


test('rewrite never substitutes another tab notes for the locally reviewed set',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();await expect(page.locator('#author-general')).toBeEnabled();
  await page.locator('#author-general').fill('Моя збережена вказівка.');await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toHaveText(/Збережено|Saved/);
  const before=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  const source=await(await request.get(`/api/versions/${before.source_version_id}`)).json();
  const other=await request.post(`/api/scenes/${fixture.scene_id}/draft`,{data:{text:source.text,content_format:source.version.content_format,expected_revision:before.scene.revision,expected_source_version_id:source.version.id,expected_comments_revision:before.expected_comments_revision,comment_set:{general:'Інша вкладка.',comments:[]}}});expect(other.ok()).toBeTruthy();
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await page.getByRole('button',{name:/Переписати за коментарями|Rewrite from comments/,exact:true}).click();
  await expect(page.locator('#notice')).toContainText(/Коментарі змінено|Comments changed/);
  await expect(page.locator('#author-general')).toHaveValue('Моя збережена вказівка.');
  expect((await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs).toHaveLength(0);
});


test('select all rewrite changes is local and still requires matching assembled preview',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}`);await page.locator('#mode-tabs [data-mode="draft"]').click();
  await page.locator('[data-ui-locale="en"]').click();
  await page.locator('#author-general').fill('Make both sentences vivid.');
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await page.getByRole('button',{name:'Rewrite from comments',exact:true}).click();
  const review=page.locator('#assisted-review'),all=review.locator('[data-review-select-all]');
  await expect(review.locator('.copyedit-item')).toHaveCount(2);
  await expect(review.locator('input:checked')).toHaveCount(0);
  const before=(await(await request.get(`/api/scenes/${f.scene_id}/comments`)).json());
  let mutations=0;page.on('request',r=>{if(r.method()==='POST'||r.method()==='PUT'||r.method()==='PATCH')mutations++;});
  await expect(all).toHaveText('Select all changes');
  await all.click();
  await expect(review.locator('input:checked')).toHaveCount(2);
  await expect(all).toBeDisabled();await expect(review.locator('[data-review-accept]')).toBeDisabled();
  expect(mutations).toBe(0);
  const after=(await(await request.get(`/api/scenes/${f.scene_id}/comments`)).json());
  expect(after).toEqual(before);
  await page.locator('[data-ui-locale="uk"]').click();
  await expect(review.getByRole('button',{name:'Обрати всі зміни',exact:true})).toBeDisabled();
  await expect(review.locator('input:checked')).toHaveCount(2);
  await review.getByRole('button',{name:'Переглянути вибраний текст',exact:true}).click();
  await expect(review.locator('[data-review-accept]')).toBeEnabled();
  await review.locator('input[type=checkbox]').first().uncheck();
  await expect(review.locator('[data-review-accept]')).toBeDisabled();
  await review.getByRole('button',{name:'Обрати всі зміни',exact:true}).click();
  await expect(review.locator('[data-review-accept]')).toBeDisabled();
  await review.getByRole('button',{name:'Переглянути вибраний текст',exact:true}).click();
  await page.evaluate(()=>import('/static/api.js').then(m=>m.dismissNotice()));
  await all.evaluate(e=>e.scrollIntoView({block:'center'}));
  await page.screenshot({path:`docs/images/rewrite-select-all-${test.info().project.name}.png`});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await review.locator('[data-review-accept]').click();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
  await expect(page.locator('.ProseMirror')).toContainText('сузір’я');
  await expect(page.locator('.ProseMirror')).toContainText('Вечір був');
  await expect(page.locator('#author-general')).toHaveValue('');
  await expect(review.locator('[data-review-select-all]')).toBeDisabled();
});


test('select all invalidates an in-flight subset preview and is blocked during apply',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=draft`);
  await expect(page.locator('#author-general')).toBeEnabled();
  await page.locator('#author-general').fill('Update both sentences.');
  await page.locator('[data-ui-locale=en]').click();await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await page.getByRole('button',{name:'Rewrite from comments',exact:true}).click();
  const review=page.locator('#assisted-review'),all=review.locator('[data-review-select-all]'),apply=review.locator('[data-review-accept]');
  await expect(review.locator('.copyedit-item')).toHaveCount(2);
  await review.locator('input[type=checkbox]').first().check();
  let release;const gate=new Promise(r=>release=r);let requested=false;
  await page.route('**/rewrites/*/selection-preview',async route=>{requested=true;const response=await route.fetch();await gate;await route.fulfill({response});});
  await review.getByRole('button',{name:'Preview selected text',exact:true}).click();
  await expect.poll(()=>requested).toBe(true);await all.click();
  const late=page.waitForResponse(r=>r.url().endsWith('/selection-preview'));release();
  await (await late).finished();
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  await expect(review.locator('.copyedit-selected-text')).toHaveText('Selection changed. Click “Preview selected text”.');
  await expect(review.getByRole('button',{name:'Preview selected text',exact:true})).toBeEnabled();
  await expect(apply).toBeDisabled();
  await page.unroute('**/rewrites/*/selection-preview');
  await review.getByRole('button',{name:'Preview selected text',exact:true}).click();await expect(apply).toBeEnabled();
  let finish;const applying=new Promise(r=>finish=r);
  await page.route('**/rewrites/*/apply',async route=>{await applying;await route.continue();});
  await apply.click();await expect(all).toBeDisabled();
  await expect(review.locator('input[type=checkbox]').first()).toBeDisabled();
  finish();await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
});
