import {test,expect} from '../../../frontend/browser-test.mjs';

// R-51 «Знайти персонажів у прозі» on the characters page (CHARACTER-EXTRACT §6): the dialog previews the plan and starts
// the search with its fingerprint; the run row pauses, resumes and stops it; a finished search leaves a proposal whose
// items are chosen one by one, the stale memory is asked with a dry run, and only «Прийняти вибране» writes.
// Neutral pier-lighthouse book.
test.use({locale:'uk-UA'});

async function seed(request,query=''){return (await request.post('/test-character-extract'+query)).json()}
const runsOf=async(request,fixture)=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs.filter(run=>run.request.mode==='character_extract');
async function noHorizontalScroll(page){
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
}

test('?extract=1 opens the preview; «Запустити» starts the search with the fingerprint; the run can be stopped',async({page,request})=>{
  const fixture=await seed(request);
  const posts=[];
  page.on('request',req=>{if(req.method()==='POST'&&/\/api\/runs$/.test(req.url()))posts.push(req.postDataJSON())});
  await page.goto(`/stories/${fixture.story_id}/characters?extract=1`);
  const dialog=page.locator('#character-extract-dialog');
  await expect(dialog).toBeVisible();
  expect(new URL(page.url()).searchParams.has('extract')).toBe(false);
  await expect(dialog.locator('#character-extract-summary')).toHaveText('Буде прочитано сцен: 2, груп: 1; викликів моделі — не більше 4');
  await expect(dialog.locator('#character-extract-cost')).toContainText('Вартість невідома');
  await expect(dialog.locator('#character-extract-pending')).toBeHidden();
  await noHorizontalScroll(page);
  // A group size out of range asks for a valid one; nothing can start meanwhile.
  await dialog.locator('#character-extract-words').fill('900');
  await expect(dialog.locator('#character-extract-status')).toHaveText('Розмір групи — ціле число від 1 000 до 20 000 слів');
  await expect(dialog.locator('#character-extract-submit')).toBeDisabled();
  await dialog.locator('#character-extract-words').fill('2000');
  await expect(dialog.locator('#character-extract-submit')).toBeEnabled();
  await dialog.locator('#character-extract-submit').click();
  await expect(dialog).toBeHidden();
  expect(posts).toHaveLength(1);
  expect(posts[0].request).toMatchObject({story_id:fixture.story_id,mode:'character_extract',group_words:2000});
  expect(posts[0].request.extract_plan_fingerprint).toBeTruthy();
  const row=page.locator('#character-extract-run');
  await expect(row).toBeVisible();
  await expect(page.locator('#character-extract-stop')).toBeVisible();
  // While the search runs, the dialog says so and cannot start a second one.
  await page.locator('#character-extract-open').click();
  await expect(dialog.locator('#character-extract-reason')).toHaveText('Пошук персонажів уже йде');
  await expect(dialog.locator('#character-extract-submit')).toBeDisabled();
  await dialog.locator('#character-extract-cancel').click();
  await page.locator('#character-extract-stop').click();
  await expect(row).toBeHidden();
  const [run]=await runsOf(request,fixture);
  expect(run.state).toBe('cancelled');
  // A cancelled search publishes what it read: here nothing, said as such.
  await expect(page.locator('#character-proposal')).toContainText('Пошук нічого не запропонував');
});

test('a reopened page finds the running search; pause is requested; a paused search offers resume',async({page,request})=>{
  const fixture=await seed(request);
  const preview=await(await request.post(`/api/stories/${fixture.story_id}/character-extract/preview`,{data:{group_words:5000}})).json();
  const created=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,mode:'character_extract',
    group_words:5000,extract_plan_fingerprint:preview.plan_fingerprint}}});
  expect(created.ok()).toBeTruthy();
  const id=(await created.json()).id;
  await page.goto(`/stories/${fixture.story_id}/characters`);
  await expect(page.locator('#character-extract-run')).toBeVisible();
  // The slow model holds the call: the pause is requested and waits for it; the search can still be stopped.
  await page.locator('#character-extract-pause').click();
  await expect(page.locator('#character-extract-pause')).toBeHidden();
  await expect(page.locator('#character-extract-stop')).toBeVisible();
  // A paused search (as the server reports it) says how far it got and offers «Продовжити».
  let resumed=false;
  await page.route(new RegExp(`/api/runs/${id}(/resume)?$`),async route=>{
    const response=await route.fetch(),body=await response.json();
    const run=body.run||body;
    const paused={...run,state:resumed?'running':'paused',checkpoint:{...(run.checkpoint||{}),phase:'reading',pending:[[fixture.scene_ids[0]]],state:{calls:1}}};
    if(route.request().method()==='POST'){resumed=true;return route.fulfill({json:{...paused,state:'running'}})}
    await route.fulfill({json:body.run?{...body,run:paused}:paused});
  });
  await page.reload();
  await expect(page.locator('#character-extract-run-status')).toHaveText('Пошук призупинено: лишилося груп — 1, викликів зроблено — 1');
  await expect(page.locator('#character-extract-resume')).toBeVisible();
  const resume=page.waitForRequest(req=>req.method()==='POST'&&req.url().endsWith(`/api/runs/${id}/resume`));
  await page.locator('#character-extract-resume').click();
  expect((await resume).postDataJSON()).toEqual({repeat_interrupted:false});
  await expect(page.locator('#character-extract-run-status')).toHaveText('Пошук персонажів: лишилося груп — 1, викликів зроблено — 1');
  await page.unroute(new RegExp(`/api/runs/${id}(/resume)?$`));
  await request.post(`/api/runs/${id}/cancel`);
});

test('a search paused before its first group offers resume; stopping it reads the published proposal at once',async({page,request})=>{
  const fixture=await seed(request);
  const preview=await(await request.post(`/api/stories/${fixture.story_id}/character-extract/preview`,{data:{group_words:5000}})).json();
  const created=await request.post('/api/runs',{data:{request_id:crypto.randomUUID(),request:{story_id:fixture.story_id,mode:'character_extract',
    group_words:5000,extract_plan_fingerprint:preview.plan_fingerprint}}});
  const id=(await created.json()).id;
  // A queued run paused before the worker took it has no checkpoint (as the server reports it).
  let cancelled=false;
  const proposal={fingerprint:'f',cards:[],name_updates:[],protagonist:null,casts:[],calls:0,
    skipped_scenes:[{scene_id:fixture.scene_ids[1],reason:'Пошук скасовано до цієї сцени'}]};
  await page.route(new RegExp(`/api/runs/${id}(/cancel)?$`),async route=>{
    if(route.request().method()==='POST'){cancelled=true}
    const response=await route.fetch(),body=await response.json(),run=body.run||body;
    const shown={...run,state:cancelled?'cancelled':'paused',checkpoint:cancelled?{phase:'done',proposal}:null};
    await route.fulfill({json:body.run?{...body,run:shown}:shown});
  });
  await page.route(new RegExp(`/api/stories/${fixture.story_id}/runs$`),async route=>{
    const body=await(await route.fetch()).json();
    await route.fulfill({json:{...body,runs:body.runs.map(run=>run.id===id?{...run,state:cancelled?'cancelled':'paused',checkpoint:null}:run)}});
  });
  await page.route(new RegExp(`/api/stories/${fixture.story_id}/character-proposal$`),async route=>{
    if(!cancelled)return route.fulfill({status:404,json:{detail:'Немає пропозиції'}});
    await route.fulfill({json:{run_id:id,state:'cancelled',proposal}});
  });
  await page.goto(`/stories/${fixture.story_id}/characters`);
  await expect(page.locator('#character-extract-run-status')).toHaveText('Пошук зупинено до початку читання');
  await expect(page.locator('#character-extract-resume')).toBeVisible();
  await expect(page.locator('#character-extract-stop')).toBeVisible();
  // The stop ends the run without an active state between: the proposal is read at once, with the unread scenes.
  await page.locator('#character-extract-stop').click();
  await expect(page.locator('#character-extract-run')).toBeHidden();
  await expect(page.locator('#character-proposal-unread')).toContainText('Ці сцени не прочитано:');
  await expect(page.locator('#character-proposal-unread')).toContainText('2. Шторм');
  await expect(page.locator('#character-proposal')).toContainText('Пошук нічого не запропонував');
  await page.unrouteAll({behavior:'ignoreErrors'});
  await request.post(`/api/runs/${id}/cancel`);
});

test('the proposal is chosen item by item; the dry run says what goes stale; «Прийняти вибране» writes the choice',async({page,request})=>{
  const fixture=await seed(request,'?proposal=true');
  await page.goto(`/stories/${fixture.story_id}/characters`);
  const proposal=page.locator('#character-proposal');
  await expect(proposal).toBeVisible();
  // Every item is chosen except the names the server marks as not suggested.
  await expect(proposal.getByRole('checkbox',{name:'Марко',exact:true})).toBeChecked();
  await expect(proposal.getByRole('checkbox',{name:'Марк',exact:true})).toBeChecked();
  await expect(proposal.getByRole('checkbox',{name:'сторож'})).not.toBeChecked();
  await expect(proposal.getByRole('checkbox',{name:'Оленка'})).toBeChecked();
  await expect(proposal.getByRole('checkbox',{name:'Позначити «Олена» головним героєм'})).toBeChecked();
  await expect(proposal).toContainText('«Марко махнув їй з човна» — 1. Пірс');
  await expect(page.locator('#character-proposal-stale')).toHaveText('Пам\'ять жодної сцени не застаріє');
  await noHorizontalScroll(page);
  const none=proposal.getByRole('button',{name:/^Зняти все: Нові імена/});
  await none.click();
  await expect(proposal.getByRole('checkbox',{name:'Оленка'})).not.toBeChecked();
  await expect(proposal.getByRole('button',{name:/^Зняти все: Нові імена/})).toBeFocused();
  await proposal.getByRole('button',{name:/^Вибрати все: Нові імена/}).click();
  await expect(proposal.getByRole('checkbox',{name:'Оленка'})).toBeChecked();
  await page.locator('#character-extract').screenshot({path:`docs/images/character-proposal-${test.info().project.name}.png`});
  // Unsaved card edits hold the acceptance back.
  await page.locator('#characters-add').click();
  await expect(page.locator('#character-proposal-accept')).toBeDisabled();
  await expect(page.locator('#character-proposal-blocked')).toHaveText('Спершу збережіть або скасуйте правки карток');
  page.once('dialog',dialog=>dialog.accept());
  await page.reload();
  await expect(page.locator('#character-proposal-accept')).toBeEnabled();
  // Leaving the new card out: its scene in a cast is skipped by the server with the reason.
  const dry=page.waitForResponse(res=>/character-proposal\/accept$/.test(res.url())&&res.request().postDataJSON().dry_run===true&&res.request().postDataJSON().cards.length===0);
  await proposal.getByRole('checkbox',{name:'Марко',exact:true}).uncheck();
  await dry;
  await page.locator('#character-proposal-accept').click();
  const result=page.locator('#character-proposal-result');
  await expect(result).toContainText('Прийнято пунктів: 3, пропущено: 1');
  await expect(result).toContainText('2. Шторм — немає кого додати до складу');
  await expect(page.locator('#character-proposal-accept')).toHaveCount(0);
  const cards=(await(await request.get(`/api/stories/${fixture.story_id}/characters`)).json()).cards;
  expect(cards.map(card=>card.name)).toEqual(['Олена']);
  expect(cards[0].entries.map(entry=>entry.text)).toEqual(expect.arrayContaining(['Інше ім\'я: Оленка','Головний герой']));
  expect((await request.get(`/api/stories/${fixture.story_id}/character-proposal`)).status()).toBe(404);
  // The card editor shows the written entries with the model's origin.
  await expect.poll(()=>page.locator('.character-editor fieldset textarea').evaluateAll(nodes=>nodes.map(node=>node.value))).toContain('Головний герой');
});

test('a proposal superseded meanwhile is refused (409) and nothing is written',async({page,request})=>{
  const fixture=await seed(request,'?proposal=true');
  await page.goto(`/stories/${fixture.story_id}/characters`);
  await expect(page.locator('#character-proposal-accept')).toBeEnabled();
  await page.route(/character-proposal\/accept$/,async route=>{
    if(route.request().postDataJSON().dry_run)return route.continue();
    await route.fulfill({status:409,json:{detail:'Є новіша пропозиція',detail_original:'Є новіша пропозиція'}});
  });
  await page.locator('#character-proposal-accept').click();
  await expect(page.locator('#notice')).toContainText('Є новіша пропозиція');
  await expect(page.locator('#character-proposal-accept')).toBeEnabled();
  const cards=(await(await request.get(`/api/stories/${fixture.story_id}/characters`)).json()).cards;
  expect(cards.map(card=>card.name)).toEqual(['Олена']);
  expect(cards[0].entries).toHaveLength(0);
});
