import {test,expect} from '../../../frontend/browser-test.mjs';

// R-48 «Побудувати пам'ять» in the workspace (spec §5, §5.1): the story menu counts the scenes the build covers; the preview
// names scenes, calls, the cost (unknown without a tariff), the scenes that will not fit and the cast; «Побудувати» fills
// the cast, then starts the run with the plan fingerprint and hands it to the run panel. Neutral pier-lighthouse book.
test.use({locale:'uk-UA'});

async function seed(request,query=''){return (await request.post('/test-memory-build'+query)).json()}
const runsOf=async(request,fixture)=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
async function openWorkspace(page,fixture,material='plan',extra=''){
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_ids[0]}&material=${material}${extra}`);
  await expect(page.locator('#scene-title')).toHaveText('Пірс');
}
async function openDialog(page){
  await page.locator('#story-menu-toggle').click();
  const item=page.locator('#story-menu-build-memory');
  await expect(item).toHaveText('Побудувати пам’ять (сцен: 2)');
  await item.click();
  const dialog=page.locator('#memory-build-dialog');
  await expect(dialog).toBeVisible();
  return dialog;
}
async function noHorizontalScroll(page){
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  const box=await page.locator('#memory-build-dialog').boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x+box.width).toBeLessThanOrEqual(page.viewportSize().width);
}

test('the preview shows scenes, unknown cost and cast; «Побудувати» fills the cast and starts the run with the fingerprint',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-summary')).toContainText('Сцен: 2');
  await expect(dialog.locator('#memory-build-summary')).toContainText('викликів моделі пам’яті: 2');
  await expect(dialog.locator('#memory-build-summary')).toContainText('synthetic-slow');
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  await expect(dialog.locator('#memory-build-cast')).toContainText('Карток персонажів: 1');
  await expect(dialog.locator('#memory-build-cast')).toContainText('Олена');
  await expect(dialog.locator('#memory-build-cast')).toContainText('учасників отримають сцен: 1');
  await expect(dialog.locator('#memory-build-unfit')).toBeHidden();
  await expect(dialog.locator('#memory-build-series')).toBeHidden();
  await noHorizontalScroll(page);
  // Cancelling starts nothing.
  await dialog.locator('#memory-build-cancel').click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#story-menu-toggle')).toBeFocused();
  expect(await runsOf(request,fixture)).toEqual([]);
  // The run request carries the fingerprint of the preview; the cast was written right before it.
  const calls=[];
  page.on('request',req=>{if(req.method()==='POST'&&/\/scene-cast\/infer$|\/api\/runs$/.test(req.url()))calls.push([new URL(req.url()).pathname,req.postDataJSON()])});
  await openDialog(page);
  const preview=(await(await request.get(`/api/stories/${fixture.story_id}/readiness?scene_id=${fixture.scene_ids[0]}&operation=rebuild_memory`)).json()).operations.rebuild_memory;
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog).toBeHidden();
  await expect.poll(()=>calls.length).toBe(2);
  expect(calls[0][0]).toBe(`/api/stories/${fixture.story_id}/scene-cast/infer`);
  expect(Number.isInteger(calls[0][1].expected_revision)).toBe(true);
  const body=calls[1][1];
  expect(body.request.mode).toBe('rebuild_memory');
  expect(body.request.scene_id).toBe(fixture.scene_ids[0]);
  expect(body.request.memory_plan_fingerprint).toBe(preview.plan_fingerprint);
  expect('budget_limit_usd' in body.request).toBe(true);
  const story=(await(await request.get(`/api/stories/${fixture.story_id}`)).json());
  expect(story.scenes[0].character_ids).toEqual(['A']);
  // The run panel takes over: the run is visible and can be cancelled there.
  await expect.poll(async()=>(await runsOf(request,fixture)).at(-1)?.state).toMatch(/queued|running/);
  // While it runs, a second build would be queued and paid twice: the dialog says why «Побудувати» waits.
  await page.locator('#story-menu-toggle').click();
  await page.locator('#story-menu-build-memory').click();
  await expect(dialog.locator('#memory-build-reason')).toHaveText('Спершу дочекайтеся завершення поточного запуску або скасуйте його');
  await expect(dialog.locator('#memory-build-submit')).toBeDisabled();
  await dialog.locator('#memory-build-cancel').click();
  expect((await runsOf(request,fixture)).length).toBe(1);
  const cancel=page.locator('#run-actions').getByRole('button',{name:/Скасувати/});
  await cancel.first().click();
  await expect.poll(async()=>(await runsOf(request,fixture)).at(-1)?.state).toMatch(/cancel/);
});

test('a plan that changed after the preview is refreshed in the dialog, not started',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  // The prose of scene 2 changes in another window: the run answers 409 for the stale fingerprint.
  await request.post(`/test-editor-import-touch/${fixture.scene_ids[1]}`);
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog.locator('#memory-build-status')).toContainText('Перевірте перегляд ще раз');
  await expect(dialog).toBeVisible();
  expect(await runsOf(request,fixture)).toEqual([]);
  await expect(dialog.locator('#memory-build-submit')).toBeEnabled();
  // The refreshed preview reads the revision and the plan again: the next press starts exactly one run with the new plan.
  const fresh=(await(await request.get(`/api/stories/${fixture.story_id}/readiness?scene_id=${fixture.scene_ids[0]}&operation=rebuild_memory`)).json()).operations.rebuild_memory;
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog).toBeHidden();
  await expect.poll(async()=>(await runsOf(request,fixture)).length).toBe(1);
  const run=(await runsOf(request,fixture))[0];
  expect(run.request.memory_plan_fingerprint).toBe(fresh.plan_fingerprint);
  await request.post(`/api/runs/${run.id}/cancel`,{data:{}});
});

test('a run refused after the cast was written can be started again without a false stale preview',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  // The first run request is refused (not 409) after infer has written the cast of scene 1 and bumped the story revision.
  let refused=false;
  await page.route(/\/api\/runs$/,async route=>{
    if(refused||route.request().method()!=='POST')return route.continue();
    refused=true;
    await route.fulfill({status:400,json:{detail:'Тимчасова відмова'}});
  });
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog.locator('#memory-build-status')).toHaveText('Тимчасова відмова');
  await expect(dialog.locator('#memory-build-submit')).toBeEnabled();
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog).toBeHidden();
  await expect.poll(async()=>(await runsOf(request,fixture)).length).toBe(1);
  await request.post(`/api/runs/${(await runsOf(request,fixture))[0].id}/cancel`,{data:{}});
});

for(const close of ['Cancel','Escape'])test(`${close} while the cast is being written stops the build before the run, and nothing else starts meanwhile`,async({page,request})=>{
  const fixture=await seed(request);
  let release,inferSeen=false;
  const held=new Promise(resolve=>{release=resolve});
  await page.route(/\/scene-cast\/infer$/,async route=>{inferSeen=true;await held;await route.continue()});
  const runPosts=[];
  page.on('request',req=>{if(req.method()==='POST'&&/\/api\/runs$/.test(req.url()))runPosts.push(req.url())});
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  await dialog.locator('#memory-build-submit').click();
  await expect.poll(()=>inferSeen).toBe(true);
  if(close==='Escape')await page.keyboard.press('Escape');else await dialog.locator('#memory-build-cancel').click();
  await expect(dialog).toBeHidden();
  // The build is still in flight: the menu cannot open the dialog for a second one.
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-build-memory')).toBeDisabled();
  await page.locator('#story-menu-toggle').click();
  const settled=page.waitForResponse(/\/scene-cast\/infer$/);
  release();
  await settled;
  await expect(page.locator('#notice')).toContainText('Побудову пам’яті скасовано: запуск не розпочато');
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-build-memory')).toBeEnabled();
  expect(runPosts).toEqual([]);
  expect(await runsOf(request,fixture)).toEqual([]);
});

test('a close after the run request was sent leaves the run in the run panel',async({page,request})=>{
  const fixture=await seed(request);
  let release,runSeen=false;
  const held=new Promise(resolve=>{release=resolve});
  await page.route(/\/api\/runs$/,async route=>{if(route.request().method()!=='POST')return route.continue();runSeen=true;await held;await route.continue()});
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  await dialog.locator('#memory-build-submit').click();
  await expect.poll(()=>runSeen).toBe(true);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
  release();
  await expect.poll(async()=>(await runsOf(request,fixture)).length).toBe(1);
  // The run panel follows it and offers its cancellation.
  const cancel=page.locator('#run-actions').getByRole('button',{name:/Скасувати/}).first();
  await expect(cancel).toBeVisible();
  await expect(cancel).toBeEnabled();
  await cancel.click();
  await expect.poll(async()=>(await runsOf(request,fixture)).at(-1)?.state).toMatch(/cancel/);
});

test('closing the dialog during a series refresh re-enables the menu item once the refresh settles',async({page,request})=>{
  const fixture=await seed(request,'?series=true');
  let release,refreshSeen=false;
  const held=new Promise(resolve=>{release=resolve});
  await page.route(/\/series\/refresh$/,async route=>{refreshSeen=true;await held;await route.continue()});
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await dialog.locator('#memory-build-refresh').click();
  await page.locator('dialog[open]').filter({hasText:'Знімок візьметься'}).getByRole('button',{name:'Оновити з попередньої книги'}).click();
  await expect.poll(()=>refreshSeen).toBe(true);
  await dialog.locator('#memory-build-cancel').click();
  await expect(dialog).toBeHidden();
  const settled=page.waitForResponse(/\/series\/refresh$/);
  release();
  await settled;
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-build-memory')).toBeEnabled();
  await page.locator('#story-menu-build-memory').click();
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#memory-build-series')).toBeHidden();  // the refresh took the snapshot
});

test('a known price shows the total; an unknown one shows its reason',async({page,request})=>{
  const fixture=await seed(request);
  let cost={per_call_usd:'0.40',total_usd:'0.75',calls:2,reason:null};
  await page.route(/\/readiness\?.*operation=rebuild_memory/,async route=>{
    const response=await route.fetch(),body=await response.json();
    body.operations.rebuild_memory.cost=cost;
    await route.fulfill({response,json:body});
  });
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість: до 0.75 $ (верхня межа)');
  await dialog.locator('#memory-build-cancel').click();
  cost={per_call_usd:null,total_usd:null,calls:2,reason:'Немає ціни моделі'};
  await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома: Немає ціни моделі');
});

test('a book still being written hides the item; a direct open shows why the build waits',async({page,request})=>{
  // Owner, 25.11.2026 (review I-2): a scene after the target has no prose yet, so the build would be refused — the menu
  // does not offer it. The summary link (?build_memory=1) still opens the dialog with the reason.
  const fixture=await seed(request);
  await request.post(`/api/stories/${fixture.story_id}/scenes`,{data:{title:'Порожня'}});
  expect((await(await request.get(`/api/stories/${fixture.story_id}/memory-build`)).json()).buildable).toBe(false);
  await openWorkspace(page,fixture);
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-build-memory')).toBeHidden();
  await page.locator('#story-menu-toggle').click();
  await openWorkspace(page,fixture,'plan','&build_memory=1');
  const dialog=page.locator('#memory-build-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#memory-build-reason')).toHaveText('Спершу виберіть завершену прозу сцени 3');
  await expect(dialog.locator('#memory-build-submit')).toBeDisabled();
});

for(const shape of ['reason','can_confirm'])test(`previous memory awaiting the author's confirmation blocks the build with a link to the scene (${shape})`,async({page,request})=>{
  // Review M-1: the dialog cannot give that confirmation; the server sends it as the reason of a not-ready preview (a
  // memory stage of one scene offers `can_confirm` instead): either way «Побудувати» stays disabled and links to the scene.
  const fixture=await seed(request);
  await page.route(/\/readiness\?.*operation=rebuild_memory/,async route=>{
    const response=await route.fetch(),body=await response.json();
    Object.assign(body.operations.rebuild_memory,{ready:false,plan_fingerprint:null,reason:'Попередня пам’ять потребує авторського підтвердження'},
                  shape==='can_confirm'?{can_confirm:true}:{});
    await route.fulfill({response,json:body});
  });
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-reason')).toContainText('Попередня пам’ять потребує авторського підтвердження');
  await expect(dialog.locator('#memory-build-submit')).toBeDisabled();
  const link=dialog.locator('#memory-build-approval');
  await expect(link).toHaveText('Відкрити сцену 1');
  await expect(link).toHaveAttribute('href',`/stories/${fixture.story_id}?scene=${fixture.scene_ids[0]}&material=memory`);
  await dialog.locator('#memory-build-submit').click({force:true});
  expect(await runsOf(request,fixture)).toEqual([]);
});

test('a second build refused by the server (409) is said as is and the preview stays',async({page,request})=>{
  // Review I-1: another tab or the chat has queued or started a build; the server refuses this one.
  const fixture=await seed(request);
  await page.route(/\/api\/runs$/,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    const detail='Побудова пам’яті цього твору вже в черзі або виконується: дочекайтеся її чи скасуйте в панелі запусків';
    await route.fulfill({status:409,json:{detail,detail_original:detail}});
  });
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  await dialog.locator('#memory-build-submit').click();
  await expect(dialog.locator('#memory-build-status')).toHaveText('Побудова пам’яті цього твору вже в черзі або виконується: дочекайтеся її чи скасуйте в панелі запусків');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#memory-build-summary')).toContainText('Сцен: 2');
  await expect(dialog.locator('#memory-build-status')).not.toContainText('Перевірте перегляд ще раз');
});

test('an active memory build hidden behind a newer run disables «Побудувати»; a paused one does not',async({page,request})=>{
  // Re-review N-0/N-2: the dialog blocks on the server's states (a paused build does not block) for any memory build of the
  // story, not only the latest run, so infer never writes the casts before a sure 409.
  const fixture=await seed(request);
  let buildState='running';
  const fake=(id,mode,state)=>({id,story_id:fixture.story_id,request_id:id,request:{story_id:fixture.story_id,scene_id:fixture.scene_ids[0],mode},
    state,tasks:[],cursor:0,created_at:'2026-11-25T10:00:00Z'});
  await page.route(/\/api\/stories\/[^/]+\/runs$/,route=>route.fulfill({json:{runs:[fake('build','rebuild_memory',buildState),
    fake('later','prepare','completed')]}}));
  const infer=[];
  page.on('request',req=>{if(req.method()==='POST'&&/\/scene-cast\/infer$/.test(req.url()))infer.push(req.url())});
  await openWorkspace(page,fixture);
  let dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-reason')).toHaveText('Спершу дочекайтеся завершення поточного запуску або скасуйте його');
  await expect(dialog.locator('#memory-build-submit')).toBeDisabled();
  expect(infer).toEqual([]);
  buildState='paused';
  await page.reload();
  await expect(page.locator('#scene-title')).toHaveText('Пірс');
  dialog=await openDialog(page);
  await expect(dialog.locator('#memory-build-cost')).toHaveText('Вартість невідома');
  await expect(dialog.locator('#memory-build-submit')).toBeEnabled();
});

test.describe('store edition',()=>{
  test.beforeEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'store'}})).json()).edition).toBe('store')});
  test.afterEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'full'}})).json()).edition).toBe('full')});
  test('a series book is read-only: no build item; a plain book keeps it without the series offer',async({page,request})=>{
    // Review M-8: the long-prose guard refuses the writes of a series or structured book in this edition.
    const series=await seed(request,'?series=true');
    await openWorkspace(page,series);
    await page.locator('#story-menu-toggle').click();
    await expect(page.locator('#story-menu-rename')).toBeVisible();
    await expect(page.locator('#story-menu-build-memory')).toBeHidden();
    await page.locator('#story-menu-toggle').click();
    const plain=await seed(request);
    await openWorkspace(page,plain);
    const dialog=await openDialog(page);
    await expect(dialog.locator('#memory-build-series')).toBeHidden();
  });
});

test('scenes that will not fit the memory role are listed with links',async({page,request})=>{
  const fixture=await seed(request,'?narrow=true');
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  const unfit=dialog.locator('#memory-build-unfit');
  await expect(unfit).toBeVisible();
  await expect(unfit.locator('a')).toHaveText(['1. Пірс','2. Шторм']);
  await expect(unfit.locator('a').first()).toHaveAttribute('href',`/stories/${fixture.story_id}?scene=${fixture.scene_ids[0]}&material=prose`);
});

test('the imported scene names its manuscript next to its status and says the plan is optional',async({page,request})=>{
  const fixture=await seed(request);
  // The default plan tab: the status row names the manuscript of the prose head (spec §4.4).
  await openWorkspace(page,fixture);
  const origin=page.locator('#workspace-scene-origin');
  await expect(origin).toBeVisible();
  await expect(origin).toHaveText('Імпортовано з рукопису: mayak.docx · План необов’язковий: валідація перевіряє прозу й пам’ять');
  await expect(page.locator('#workspace-scene-status')).toBeVisible();
  // The prose buffer still names the version's origin, as the version history does.
  await openWorkspace(page,fixture,'prose');
  await expect(page.locator('#workspace-origin')).toHaveText('Імпортовано з рукопису: mayak.docx');
  await expect(page.locator('#version-panel')).toContainText('Імпортовано з рукопису: mayak.docx');
});

test('a series book with an empty start snapshot offers «Оновити з попередньої книги» before the build',async({page,request})=>{
  const fixture=await seed(request,'?series=true');
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  const series=dialog.locator('#memory-build-series');
  await expect(series).toBeVisible();
  // An offer, not a gate: «Побудувати» stays available and says what its memory will lack.
  await expect(dialog.locator('#memory-build-series-warning')).toHaveText('Поки книгу не оновлено з попередньої, пам’ять не враховуватиме попередню книгу.');
  await expect(dialog.locator('#memory-build-submit')).toBeEnabled();
  const refresh=dialog.locator('#memory-build-refresh');
  await expect(refresh).toHaveText('Оновити з попередньої книги');
  // The refresh comes first in the dialog's order of actions.
  const order=await dialog.evaluate(node=>{const all=[...node.querySelectorAll('button')];return [all.indexOf(node.querySelector('#memory-build-refresh')),all.indexOf(node.querySelector('#memory-build-submit'))]});
  expect(order[0]).toBeLessThan(order[1]);
  await expect(dialog.locator('#memory-build-cast')).toContainText('Немає карток персонажів');
  await expect(dialog.locator('#memory-build-cast a').first()).toHaveAttribute('href',`/stories/${fixture.story_id}/characters`);
  // R-51: the same warning leads to the character and place search in the prose, which opens its dialog on arrival.
  await expect(dialog.locator('#memory-build-extract')).toHaveText('Знайти персонажів і місця у прозі…');
  await expect(dialog.locator('#memory-build-extract')).toHaveAttribute('href',`/stories/${fixture.story_id}/characters?extract=1`);
  // The character import leads to the workspace importer with the focus on its file field.
  await dialog.locator('#memory-build-cast').getByRole('button',{name:'Імпорт персонажів з Markdown'}).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#import-sources input[name="characters"]')).toBeFocused();
  await page.locator('#story-menu-toggle').click();
  await page.locator('#story-menu-build-memory').click();
  await expect(refresh).toBeEnabled();
  await refresh.click();
  await page.locator('dialog[open]').filter({hasText:'Знімок візьметься'}).getByRole('button',{name:'Оновити з попередньої книги'}).click();
  await expect(series).toBeHidden();
  await expect(dialog.locator('#memory-build-series-warning')).toBeHidden();
  await expect(dialog).toBeVisible();
  const story=(await(await request.get(`/api/stories/${fixture.story_id}`)).json()).story;
  expect(story.series_start_version_id).toBeTruthy();
});

test('?build_memory=1 opens the dialog once after the page loads',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture,'plan','&build_memory=1');
  const dialog=page.locator('#memory-build-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#memory-build-summary')).toContainText('Сцен: 2');
  expect(new URL(page.url()).searchParams.has('build_memory')).toBe(false);
  await noHorizontalScroll(page);
  await dialog.locator('#memory-build-cancel').click();
  await page.reload();
  await expect(page.locator('#scene-title')).toHaveText('Пірс');
  await expect(dialog).toBeHidden();
});

test('the preview says what the memory model receives and where the text goes',async({page,request})=>{
  // R-49 (MEMORY-BUILD): categories from the request sections; the fixture's model is local, so no privacy promise either.
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await openDialog(page);
  const sends=dialog.locator('#memory-build-sends');
  await expect(sends).toContainText('отримає: прозу 2 сцен');
  await expect(sends).toContainText('пам’ять попередніх сцен');
  await expect(sends).toContainText('лише на адресу на цьому комп’ютері');
  await expect(sends).not.toContainText('не залишає');
});
