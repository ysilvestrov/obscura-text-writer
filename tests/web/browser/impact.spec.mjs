import {test,expect} from '../../../frontend/browser-test.mjs';

test('impact review previews planner calls and clears only verified prose',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await page.locator('#impact-panel summary').click();
  await page.locator('#impact-preview').click();
  await expect(page.locator('#impact-preview-info')).toContainText('synthetic-impact');
  await expect(page.locator('#impact-start')).toBeEnabled();
  await page.locator('#impact-start').click();
  await expect(page.locator('#review-session')).toContainText(/Перегляд завершено|Review complete/);
  const data=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  expect(data.scene.heads.prose).toBe(f.prose_id);
  if(await page.locator('#notice-close').isVisible())await page.locator('#notice-close').click();
  await page.locator('#impact-panel').screenshot({path:`../artifacts/r28-impact/${test.info().project.name}.png`});
  expect(data.versions.find(v=>v.id===f.prose_id).stale).toBe(false);
});

test('specific impact findings preserve unsaved prose and locale switch',async({page,request})=>{
  const f=await(await request.post('/test-impact?changes=true')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
  await page.locator('#impact-panel summary').click();await page.locator('#impact-preview').click();
  await page.locator('#impact-start').click();
  await page.locator('.ProseMirror').fill('Незбережена авторська правка.');
  await expect(page.locator('#review-session')).toContainText(/оберіть рішення|choose a decision/);
  await expect(page.locator('#review-session blockquote')).not.toHaveCount(0);
  await expect(page.locator('.ProseMirror')).toHaveText('Незбережена авторська правка.');
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en');});
  await expect(page.locator('#review-session')).toContainText('choose a decision');
  await expect(page.locator('#review-session .review-concern')).toContainText('Марія');
  await expect(page.locator('#review-session .review-concern details p.muted')).toContainText('План');
  await expect(page.locator('.ProseMirror')).toHaveText('Незбережена авторська правка.');
});

test('old backend does not expose new review actions after a static update',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();
  await page.route(`**/api/stories/${f.story_id}/impact`,async route=>{
    const response=await route.fetch();const data=await response.json();delete data.review_protocols;
    await route.fulfill({response,json:data});
  });
  await page.goto(`/stories/${f.story_id}`);
  await expect(page.locator('#impact-panel')).toHaveAttribute('data-review-protocol','unsupported');
  await expect(page.locator('#impact-panel')).toBeHidden();
});


test('large impact preview shows parts and synthesis before author dispatch',async({page,request})=>{
  const f=await(await request.post('/test-impact?chunked=true')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await page.locator('#impact-panel summary').click();
  await page.locator('#impact-preview').click();
  await expect(page.locator('#impact-preview-info')).toContainText(/Початковий пошук|Initial search/i);
  await expect(page.locator('#impact-start')).toBeEnabled();
  await page.locator('#impact-panel').screenshot({path:`../artifacts/r28b-impact/${test.info().project.name}.png`});
  const before=await(await request.get(`/api/stories/${f.story_id}/runs`)).json();
  expect(before.runs?.length??before.length).toBe(0);
  await page.locator('#impact-start').click();
  await expect(page.locator('#review-session')).toContainText(/Перегляд завершено|Review complete/,{timeout:30000});
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en');});
  await expect(page.locator('#review-session')).toContainText('Review complete');
});


test('slow impact preview is visible immediately and can be cancelled without dispatch',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();let release;let entered;
  const held=new Promise(resolve=>{release=resolve});const started=new Promise(resolve=>{entered=resolve});
  await page.route('**/review/preview',async route=>{entered();await held;try{await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({ready:false,reason:'test'})});}catch{}});
  try{
    await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
    await page.locator('#impact-panel summary').click();await page.locator('#impact-preview').click();await started;
    await expect(page.locator('#impact-preview-info')).toBeVisible();
    await expect(page.locator('#impact-progress')).toContainText(/Підготовка|Preparing/);
    await expect(page.locator('#impact-start')).toBeHidden();
    await expect(page.locator('#impact-cancel-preview')).toBeVisible();
    await page.locator('#impact-panel').screenshot({path:`../artifacts/impact-preview-wait/${test.info().project.name}.png`});
    await page.locator('#impact-cancel-preview').click();
    await expect(page.locator('#impact-preview')).toBeEnabled();
    await expect(page.locator('#impact-preview-panel')).toBeHidden();
    const runs=await(await request.get(`/api/stories/${f.story_id}/runs`)).json();expect(runs.runs).toHaveLength(0);
  }finally{release();await page.unrouteAll({behavior:'wait'});}
});

test('impact preview timeout unlocks controls and reports a specific cause',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();let release;let entered;
  const held=new Promise(resolve=>{release=resolve});const started=new Promise(resolve=>{entered=resolve});
  await page.route('**/review/preview',async route=>{entered();await held;try{await route.abort();}catch{}});
  try{
    await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
    await page.locator('#impact-panel summary').click();await page.clock.install();
    await page.locator('#impact-preview').click();await started;await page.clock.fastForward(121000);
    await expect(page.locator('#impact-preview')).toBeEnabled();
    await expect(page.locator('#notice')).toContainText(/120/);
    await expect(page.locator('#impact-preview-panel')).toBeHidden();
    const runs=await(await request.get(`/api/stories/${f.story_id}/runs`)).json();expect(runs.runs).toHaveLength(0);
  }finally{release();await page.unrouteAll({behavior:'wait'});}
});


test('failed impact preview unlocks retry and does not retain stale start action',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();let calls=0;
  await page.route('**/review/preview',async route=>{if(++calls===1)await route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Synthetic preflight failure'})});else await route.continue();});
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await page.locator('#impact-panel summary').click();await page.locator('#impact-preview').click();
  await expect(page.locator('#notice')).toContainText('Synthetic preflight failure');
  await expect(page.locator('#impact-preview')).toBeEnabled();
  await expect(page.locator('#impact-preview-panel')).toBeHidden();
  await page.locator('#impact-preview').click();await expect(page.locator('#impact-start')).toBeVisible();
  await expect(page.locator('#impact-start')).toBeEnabled();
  const runs=await(await request.get(`/api/stories/${f.story_id}/runs`)).json();expect(runs.runs).toHaveLength(0);
});


test('restored failed run keeps retry visible while checking and when settings block it',async({page,request})=>{
  const f=await(await request.post('/test-impact')).json();
  const run={id:'restore-failed-run',story_id:f.story_id,state:'failed',error:'Synthetic saved failure',created_at:new Date().toISOString(),cursor:0,tasks:[{stage:'impact_part',phase:'check',scene_id:f.scene_id}],request:{mode:'impact',stage:null},impact:{protocol:2}};
  let release;const held=new Promise(resolve=>{release=resolve});let modelCalls=0;
  await page.route(`**/api/stories/${f.story_id}/runs`,route=>route.fulfill({json:{runs:[run]}}));
  await page.route('**/api/runs/restore-failed-run',route=>route.fulfill({json:{run,attempts:[],partial:''}}));
  await page.route('**/api/runs/restore-failed-run/readiness',async route=>{await held;try{await route.fulfill({json:{ready:false,reason:'Налаштування планувальника змінилися; потрібен новий запуск'}});}catch{}});
  await page.route('**/api/runs/restore-failed-run/resume',route=>{modelCalls++;return route.abort();});
  try{
    await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
    const retry=page.locator('#run-actions button').filter({hasText:/Повторити перерваний етап|Repeat interrupted stage/});
    await expect(page.locator('#run-status')).toContainText('Synthetic saved failure');
    await expect(retry).toBeVisible();await expect(retry).toBeDisabled();
    release();
    await expect(retry).toHaveAttribute('title',/Налаштування планувальника/);
    await expect(retry).toBeVisible();await expect(retry).toBeDisabled();
    await page.getByRole('link',{name:/^Налаштування$|^Settings$/}).click();
    await page.locator('#settings-return').click();
    await expect(retry).toBeVisible();await expect(retry).toBeDisabled();
    expect(modelCalls).toBe(0);
  }finally{release();await page.unrouteAll({behavior:'wait'});}
});
