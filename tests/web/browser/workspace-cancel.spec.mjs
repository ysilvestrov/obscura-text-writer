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
  const other=await context.newPage();await other.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await page.waitForTimeout(5500);await primary.click();release();
  await expect.poll(()=>cancelled).toBe(1);await other.close();
});
