import {test,expect} from '../../../frontend/browser-test.mjs';

test('stop fences a pending enqueue before its response arrives',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  let release,posted;const gate=new Promise(resolve=>release=resolve),sent=new Promise(resolve=>posted=resolve);let cancelled=0;
  await page.route('**/api/runs',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    posted();await gate;await route.continue();
  });
  await page.route('**/api/runs/cancel-request',async route=>{cancelled++;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();await sent;
  await expect(primary).toContainText(/Зупинити|Stop/);await primary.click();
  await expect.poll(()=>cancelled).toBe(1);release();
});

test('stop reconciles a lost enqueue response and cancels the existing run',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  let release,posted;const gate=new Promise(resolve=>release=resolve),sent=new Promise(resolve=>posted=resolve);let cancelled=0,posts=0;
  await page.route('**/api/runs',async route=>{
    if(route.request().method()!=='POST')return route.continue();
    posts++;await route.fetch();posted();await gate;await route.abort();
  });
  await page.route('**/api/runs/cancel-request',async route=>{cancelled++;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();await sent;await primary.click();release();
  await expect.poll(()=>cancelled).toBe(1);expect(posts).toBe(1);
});

test('a 500 response after enqueue retains the stop request',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();let release,posted,cancelled=0;
  const gate=new Promise(resolve=>release=resolve),sent=new Promise(resolve=>posted=resolve);
  await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();await route.fetch();posted();await gate;await route.fulfill({status:500,json:{detail:'synthetic'}})});
  await page.route('**/api/runs/cancel-request',async route=>{cancelled++;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();await sent;await primary.click();release();
  await expect.poll(()=>cancelled).toBe(1);
});

test('a 500 after enqueue without Stop recovers the run without a second POST',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-slow')).json();let posts=0;
  await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();posts++;await route.fetch();await route.fulfill({status:500,json:{detail:'synthetic'}})});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();
  await expect(page.locator('#run-status')).toContainText('synthetic-slow');expect(posts).toBe(1);
  const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;expect(runs).toHaveLength(1);await primary.click();
});

test('unknown enqueue is not shown as cancelled and Stop fences it',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();await route.fulfill({status:500,json:{detail:'synthetic'}})});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();
  await expect(page.locator('#notice')).toContainText(/невідом|unknown/i);await expect(page.locator('#run-status')).not.toContainText(/скасован|cancelled/i);
  await expect(primary).toContainText(/Зупинити|Stop/);await primary.click();
  await expect.poll(async()=>{const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;return runs.length===1&&runs[0].state==='cancelled'}).toBe(true);
});

test('active primary action can be stopped after reload',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-slow')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();
  await expect(primary).toContainText(/Зупинити|Stop/);await expect(page.locator('#run-status')).toContainText(/Генер|Generating|Queued|Черга/i);await page.reload();
  await expect(primary).toContainText(/Зупинити|Stop/);await expect(primary).toBeEnabled();await primary.click();
  await expect(page.locator('#run-status')).toContainText(/Скас|Cancel/i);
});

test('another tab cannot clear a pending stop request',async({page,context,request})=>{
  const fixture=await(await request.post('/test-editor-slow')).json();let release,posted,cancelled=0;
  const gate=new Promise(resolve=>release=resolve),sent=new Promise(resolve=>posted=resolve);
  await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();await route.fetch();posted();await gate;await route.abort()});
  await page.route('**/api/runs/cancel-request',async route=>{cancelled++;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();await sent;
  const other=await context.newPage();await other.clock.install();await other.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await other.clock.fastForward(5500);await primary.click();release();
  await expect.poll(()=>cancelled).toBe(1);await other.close();
});

test('stop during reconciliation is not lost',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-slow')).json();let release,listing,posted=false,cancelled=0;
  const gate=new Promise(resolve=>release=resolve),waiting=new Promise(resolve=>listing=resolve);
  await page.route('**/api/runs',async route=>{if(route.request().method()!=='POST')return route.continue();await route.fetch();posted=true;await route.fulfill({status:500,json:{detail:'synthetic'}})});
  await page.route('**/api/stories/*/runs',async route=>{if(posted){posted=false;listing();await gate}await route.continue()});
  await page.route('**/api/runs/cancel-request',async route=>{cancelled++;await route.continue()});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();await primary.click();await waiting;await primary.click();release();
  await expect.poll(()=>cancelled).toBe(1);
  await expect.poll(async()=>{const runs=(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;return runs.at(-1)?.state}).toMatch(/cancelled|cancellation_requested/);
});

test('stopping readiness restores controls without a settings error',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();let started;const waiting=new Promise(resolve=>started=resolve);let block=false;
  await page.route('**/api/stories/*/readiness*',async route=>{if(block){block=false;started();await new Promise(resolve=>setTimeout(resolve,3000))}try{await route.continue()}catch{}});
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const primary=page.locator('#workspace-primary');await expect(primary).toBeEnabled();block=true;await primary.click();await waiting;await primary.click();
  await expect(primary).toBeEnabled();await expect(primary).not.toContainText(/Зупинити|Stop/);
  await expect(page.locator('#workspace-error-settings')).toBeHidden();
});
