import {test,expect} from '../../../frontend/browser-test.mjs';

// R20-WORKSPACE-S03: run controls, the scene status and the next-run limit sit in the status row under the material.
test('status row holds run controls and the next-run limit',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const row=page.locator('#workspace-material ~ #workspace-status-row');
  await expect(page.locator('.workspace-sticky #workspace-status-row')).toHaveCount(0);
  await expect(row.locator('#workspace-scene-status')).not.toBeEmpty();
  // Which run actions are visible for which run state is unchanged (runs.js / run-readiness.js); here only their place.
  await expect(row.locator('#run-actions button',{hasText:/^(Скасувати|Cancel)$/})).toHaveCount(1);
  await expect(row.locator('#run-actions .run-action')).toHaveCount(5); // pause, cancel, continue after acceptance, resume, repeat
  await expect(page.locator('.context-panel #run-actions')).toHaveCount(0);
  await row.locator('#run-options summary').click();
  await expect(row.locator('#run-options #run-budget')).toBeVisible();
  await expect(page.locator('.context-panel .budget-panel')).toHaveCount(0);
});

// R20-WORKSPACE-S03: a run waiting for the author keeps the pinned area small and offers a jump to its controls.
test('waiting run shows a decision link and the pinned area stays small',async({page,request})=>{
  await page.setViewportSize({width:1280,height:800});
  const f=await(await request.post('/test-book')).json();
  const run={id:'layout-failed-run',story_id:f.story_id,state:'failed',error:'Synthetic saved failure',created_at:new Date().toISOString(),cursor:0,tasks:[{stage:'draft',scene_id:f.scene_id}],request:{mode:'stage',stage:'draft',scene_id:f.scene_id}};
  await page.route(`**/api/stories/${f.story_id}/runs`,route=>route.fulfill({json:{runs:[run]}}));
  await page.route('**/api/runs/layout-failed-run',route=>route.fulfill({json:{run,attempts:[],partial:''}}));
  await page.route('**/api/runs/layout-failed-run/readiness',route=>route.fulfill({json:{ready:true}}));
  try{
    await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
    await expect(page.locator('#run-status')).toContainText('Synthetic saved failure');
    const jump=page.locator('.workspace-sticky #run-jump');
    await expect(jump).toBeVisible();await expect(jump).toHaveText(/Потрібне рішення|Decision needed/);
    const sticky=await page.locator('.workspace-sticky').boundingBox();
    expect(sticky.height).toBeLessThanOrEqual(800/3);
    await jump.click();
    await expect(page.locator('#workspace-status-row')).toBeInViewport();
    expect(await page.evaluate(()=>!!document.activeElement?.matches('#workspace-status-row #run-actions button:enabled'))).toBe(true);
  }finally{await page.unrouteAll({behavior:'wait'});}
});

// R20-WORKSPACE-S05: full screen spreads the editor over the window and Escape restores the page.
test('full screen mode spreads the editor and exits on Escape',async({page,request})=>{
  await page.setViewportSize({width:1280,height:800});
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const toggle=page.locator('#workspace-focus');
  await expect(toggle).toHaveAttribute('aria-pressed','false');
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-pressed','true');
  await expect(toggle).toHaveAttribute('aria-label',/Згорнути|Exit full screen/);
  // Notices (save errors) stay above the fixed editor panel.
  await page.evaluate(()=>{const n=document.querySelector('#notice');n.textContent='Synthetic notice';n.hidden=false;n.className='error'});
  const notice=await page.locator('#notice').boundingBox();
  expect(await page.evaluate(([x,y])=>document.elementFromPoint(x,y)?.closest('#notice')!==null,[notice.x+notice.width/2,notice.y+notice.height/2])).toBe(true);
  for(const hidden of ['.scene-panel','.context-panel','.storybar','#mode-tabs','#workspace-status-row','#workspace-primary','.topbar'])await expect(page.locator(hidden).first()).toBeHidden();
  await expect(page.locator('#save-text')).toBeVisible();
  const box=await page.locator('.ProseMirror').boundingBox();
  expect(box.height).toBeGreaterThanOrEqual(800*0.8);
  await expect(page.locator('.ProseMirror')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(toggle).toHaveAttribute('aria-pressed','false');
  await expect(page.locator('.scene-panel')).toBeVisible();await expect(page.locator('#mode-tabs')).toBeVisible();
  // Plain materials (plan, brief) use the textarea and spread the same way.
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=plan`);
  await toggle.click();
  const area=await page.locator('textarea#editor').boundingBox();
  expect(area.height).toBeGreaterThanOrEqual(800*0.8);
  await toggle.click();await expect(page.locator('.scene-panel')).toBeVisible();
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
  await expect(menu.locator('#story-menu-revision')).toHaveCount(0);
  await expect(menu.locator('#story-menu-budget')).toContainText(/Бюджет|Budget/);
  await page.keyboard.press('Escape');
  await expect(menu).toBeHidden();await expect(toggle).toBeFocused();await expect(toggle).toHaveAttribute('aria-expanded','false');
  await toggle.click();await expect(menu).toBeVisible();
  await page.locator('#story-title').click();await expect(menu).toBeHidden();
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

// #89 documentation screenshots (neutral synthetic fixture): the workspace with the story menu open.
test('workspace screenshots for the user guide',async({page,request})=>{
  const f=await(await request.post('/test-book')).json(),name=test.info().project.name;
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('#workspace-scene-status')).not.toBeEmpty();
  await page.locator('#story-menu-toggle').click();await expect(page.locator('#story-menu')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const box=await page.locator('#story-menu').boundingBox(),width=await page.evaluate(()=>innerWidth);
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);  // final review #2: no clipping on either side
  await page.screenshot({path:`docs/images/workspace-menu-${name}.png`});
});

