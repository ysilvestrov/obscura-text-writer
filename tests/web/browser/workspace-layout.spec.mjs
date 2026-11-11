import {test,expect} from '../../../frontend/browser-test.mjs';

// #89 R20-WORKSPACE: run controls, the scene status and the next-run limit sit in the status row above the editor.
test('status row holds run controls and the next-run limit',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const row=page.locator('.workspace-sticky #workspace-status-row');
  await expect(row.locator('#workspace-scene-status')).not.toBeEmpty();
  // Which run actions are visible for which run state is unchanged (runs.js / run-readiness.js); here only their place.
  await expect(row.locator('#run-actions button',{hasText:/^(Скасувати|Cancel)$/})).toHaveCount(1);
  await expect(row.locator('#run-actions .run-action')).toHaveCount(5); // pause, cancel, continue after acceptance, resume, repeat
  await expect(page.locator('.context-panel #run-actions')).toHaveCount(0);
  await row.locator('#run-options summary').click();
  await expect(row.locator('#run-options #run-budget')).toBeVisible();
  await expect(page.locator('.context-panel .budget-panel')).toHaveCount(0);
});

// #89 WORKSPACE-TOOLS: three icon actions, story actions behind a keyboard-operable disclosure menu.
test('story menu opens from the keyboard and returns focus on Escape',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  for(const id of ['#workspace-characters','#workspace-settings','#add-scene'])await expect(page.locator(id)).toHaveAttribute('aria-label',/.+/);
  const toggle=page.locator('#story-menu-toggle'),menu=page.locator('#story-menu');
  await expect(menu).toBeHidden();
  await toggle.focus();await page.keyboard.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded','true');await expect(menu).toBeVisible();
  await expect(menu.locator('#story-menu-revision')).toHaveAttribute('href',`/stories/${fixture.story_id}/revision`);
  await expect(menu.locator('#story-menu-budget')).toContainText(/Бюджет|Budget/);
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute('aria-expanded','false');
  await toggle.click();await expect(menu).toBeVisible();
  await page.locator('#story-title').click();await expect(menu).toBeHidden();
});

test('book revision page opens from the menu with a pending count',async({page,request})=>{
  const f=await(await request.post('/test-impact?changes=true')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-revision-count')).toHaveText(/^[1-9]\d*$/);
  await expect(page.locator('#story-menu-toggle .menu-dot')).toBeVisible();
  await page.locator('#story-menu-revision').click();
  await expect(page).toHaveURL(new RegExp(`/stories/${f.story_id}/revision$`));
  await expect(page.locator('#impact-preview')).toBeVisible();
  await expect(page.locator('#revision-return')).toHaveAttribute('href',`/stories/${f.story_id}`);
});

// #89 WORKSPACE-TOOLS: the side panel is about the scene only; sections remember being open and never touch the buffer.
test('scene sections reopen after reload and leave unsaved text alone',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const scene=page.locator('.context-panel details[data-section=scene]');
  await expect(scene).not.toHaveAttribute('open','');
  await expect(page.locator('#evaluation-section')).toBeHidden(); // no evaluator configured in the fixture
  await expect(page.locator('#story-menu-evaluate')).toBeHidden();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
  await page.locator('.ProseMirror').fill('Незбережений рядок.');
  await expect(page.locator('#save-text')).toBeEnabled();
  await scene.locator('summary').click();
  await expect(page.locator('#scene-settings')).toBeVisible();
  await expect(page.locator('.ProseMirror')).toHaveText('Незбережений рядок.');
  await expect(page.locator('#save-text')).toBeEnabled();
  await page.locator('#save-text').click();await expect(page.locator('#save-text')).toBeDisabled();
  await page.reload();
  await expect(scene).toHaveAttribute('open','');
});

test('sections work when storage throws',async({page,request})=>{
  await page.addInitScript(()=>{Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError')}})});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const scene=page.locator('.context-panel details[data-section=scene]');
  await expect(scene).not.toHaveAttribute('open','');
  await scene.locator('summary').click();await expect(scene).toHaveAttribute('open','');
  expect(errors.filter(message=>/tool-section|SECTIONS|denied/.test(message))).toEqual([]);
});

// #89 documentation screenshots (neutral synthetic fixture): the workspace with the story menu open, and the book revision page.
test('workspace screenshots for the user guide',async({page,request})=>{
  const f=await(await request.post('/test-impact?changes=true')).json(),name=test.info().project.name;
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('#workspace-scene-status')).not.toBeEmpty();
  await page.locator('#story-menu-toggle').click();await expect(page.locator('#story-menu')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const box=await page.locator('#story-menu').boundingBox(),width=await page.evaluate(()=>innerWidth);
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);  // final review #2: no clipping on either side
  await page.screenshot({path:`docs/images/workspace-menu-${name}.png`});
  await page.locator('#story-menu-revision').click();await expect(page.locator('#impact-preview')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.screenshot({path:`docs/images/workspace-revision-${name}.png`});
});

// #89 final review #4: opening a scene from the revision page keeps the page (and unsaved review choices) alive.
test('opening a scene from book revision keeps the revision page',async({page,request,context})=>{
  const f=await(await request.post('/test-impact?changes=true')).json();
  await page.goto(`/stories/${f.story_id}/revision`);
  await page.evaluate(()=>{window.__kept=true});
  const opened=context.waitForEvent('page');
  await page.evaluate(()=>import('/static/revision-context.js').then(m=>m.selectScene(m.state.view?.scenes?.[0]||{id:'x',heads:{}})));
  const tab=await opened;await tab.waitForLoadState();
  expect(tab.url()).toContain(`/stories/${f.story_id}?scene=`);
  expect(await page.evaluate(()=>window.__kept)).toBe(true);
  await tab.close();
});

// Cross-review #2: "Open material" for a brief report opens the brief even when the scene already has prose.
test('book revision opens the reported material in the workspace',async({page,request})=>{
  const f=await(await request.post('/test-impact?changes=true')).json();
  await page.goto(`/stories/${f.story_id}/revision`);
  const url=await page.evaluate(async()=>{
    const ctx=await import('/static/revision-context.js'),cmd=await import('/static/workspace-commands.js');
    let opened=null;window.open=u=>{opened=u};
    const scene={id:'scene-x',heads:{brief:'b',prose:'p'}};
    await ctx.selectScene(scene);if(ctx.state.scene?.id===scene.id&&!ctx.state.dirty)await cmd.invokeWorkspaceCommand('show','brief');
    await new Promise(r=>setTimeout(r,50));return opened;
  });
  expect(url).toContain('scene=scene-x');expect(url).toContain('material=brief');
});

// Cross-review #1: coming back to the revision page while a run is active resumes polling.
test('book revision resumes polling when the author returns during a run',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}/revision`);
  await page.evaluate(()=>{window.__runEvents=0;document.addEventListener('workspace-run-state',()=>window.__runEvents++)});
  await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,scene_id:fixture.scene_id,mode:'edit_loop'}}});
  await page.evaluate(()=>window.dispatchEvent(new Event('focus')));
  await expect.poll(()=>page.evaluate(()=>window.__runEvents),{timeout:5000}).toBeGreaterThan(0);
});
