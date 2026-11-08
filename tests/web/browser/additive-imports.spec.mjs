import {test,expect} from '../../../frontend/browser-test.mjs';
async function writing(page){
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
}

test('writing target saves, resets, switches language and detects remote target conflict',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}/settings`);await writing(page);
  const target=page.locator('#profile-form [name="target_words"]');
  await expect(target).toHaveValue('7000');
  await target.fill('25000');await page.locator('[data-ui-locale="uk"]').click();
  await expect(target).toHaveValue('25000');
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save')).toBeDisabled();
  await expect.poll(async()=>(await(await request.get(`/api/stories/${f.story_id}/settings`)).json()).story.target_words).toBe(25000);
  await target.fill('26000');await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});await page.locator('#settings-reset').click();await expect(target).toHaveValue('25000');
  await page.evaluate(()=>import('/static/api.js').then(m=>m.dismissNotice()));
  await page.screenshot({path:`docs/images/writing-target-${test.info().project.name}.png`,fullPage:true});
  await target.fill('27000');
  const latest=await(await request.get(`/api/stories/${f.story_id}/settings`)).json();
  await request.put(`/api/stories/${f.story_id}/settings`,{data:{expected_revision:latest.story.revision,target_words:28000}});
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save-status')).toHaveText('Ці налаштування вже змінено. Відкиньте правки або звірте їх перед повторним збереженням.');
  await expect(target).toHaveValue('27000');
  expect((await(await request.get(`/api/stories/${f.story_id}/settings`)).json()).story.target_words).toBe(28000);
});


async function uploadFile(page,kind,name,text){
  await page.locator('.importer').evaluate(e=>e.open=true);
  await page.locator(`#import-sources [name="${kind}"]`).setInputFiles({name,mimeType:'text/plain',buffer:Buffer.from(text)});
  await page.locator('#import-sources button').click();
  await expect(page.locator('#import-sources')).not.toHaveAttribute('aria-busy','true');
}

test('dated import journal, duplicate results and selected material survive additive imports',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await page.locator('[data-ui-locale="en"]').click();
  await uploadFile(page,'characters','people-a.md','## Анна\nПрацює в бібліотеці.');
  await expect(page.locator('#import-results')).toContainText('New character cards: 1');
  expect(await page.locator('#import-sources [name=characters]').evaluate(e=>e.files.length)).toBe(0);
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await uploadFile(page,'characters','people-b.md','## Анна\nНе замінювати.\n## Марія\nЛюбить читати.');
  await expect(page.locator('#import-results')).toContainText('Skipped characters: Анна');
  await expect(page.locator('#import-results a')).toHaveAttribute('href',new RegExp(`/stories/${f.story_id}/characters`));
  await uploadFile(page,'plan','plan-2.md','Сцена 2: День\nОпис дня.');
  await uploadFile(page,'plan','plan-3.md','Сцена 2: Дубль\nПропустити.\nСцена 3: Вечір\nОпис вечора.');
  await expect(page.locator('#import-results')).toContainText('Skipped scene numbers: 2');
  await page.locator('.workspace-context > summary').click();
  await expect(page.locator('.source-record')).toHaveCount(4);
  await expect(page.locator('.source-record time[datetime]')).toHaveCount(4);
  await expect(page.locator('#context-content')).toContainText('Active plan from accepted sections');
  const activeRow=page.locator('.source-record').filter({hasText:'people-b.md'});
  await expect(activeRow.locator('small')).toHaveText('Active source');
  await expect(page.locator('.source-record').filter({hasText:'people-a.md'}).locator('small')).toHaveCount(0);
  await expect(activeRow.locator('time')).toContainText(/(?:GMT|UTC|CET)/);
  await expect(page.locator('#context-content')).toContainText('people-a.md');
  await expect(page.locator('#context-content')).toContainText('plan-3.md');
  await page.locator('[data-ui-locale="uk"]').click();
  await expect(page.locator('#import-results')).toContainText('Пропущені номери сцен: 2');
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  await page.locator('#context-content').screenshot({path:`docs/images/import-journal-${test.info().project.name}.png`});
  await page.locator('#import-results').screenshot({path:`docs/images/import-results-${test.info().project.name}.png`});
});

test('partial and409 results stay visible, pending blocks repeats and invalid dates are unknown',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.route(`**/api/stories/${f.story_id}`,async route=>{
    const response=await route.fetch(),body=await response.json();
    body.source_files=[{id:'synthetic',name:'<img src=x>.md',kind:'source_plan',version_id:'p',created_at:null}];
    await route.fulfill({response,json:body});
  });
  await page.goto(`/stories/${f.story_id}`);await page.locator('[data-ui-locale="en"]').click();
  await page.locator('.workspace-context > summary').click();
  await expect(page.locator('#context-content')).toContainText('Time unknown');
  await expect(page.locator('#context-content img')).toHaveCount(0);
  let release;const gate=new Promise(r=>release=r);let calls=0;
  const files=[{client_index:0,name:'first.md',kind:'source_plan',status:'imported',created_scene_ids:['s'],created_character_cards:0,skipped_character_names:[],skipped_scene_numbers:[],warnings:[],error:null},{client_index:1,name:'second.md',kind:'source_characters',status:'failed',created_scene_ids:[],created_character_cards:0,skipped_character_names:[],skipped_scene_numbers:[],warnings:[],error:'Safe failure <img src=x>'}];
  await page.route(`**/api/stories/${f.story_id}/sources`,async route=>{calls++;await gate;await route.fulfill({json:{partial:true,created_scene_ids:['s'],created_character_cards:0,files}})});
  await page.locator('.importer').evaluate(e=>e.open=true);
  await page.locator('#import-sources [name="plan"]').setInputFiles({name:'first.md',mimeType:'text/plain',buffer:Buffer.from('Plan')});
  await page.locator('#import-sources [name=characters]').setInputFiles({name:'second.md',mimeType:'text/plain',buffer:Buffer.from('Characters')});
  await page.locator('#import-sources button').click();
  await expect(page.locator('#import-sources button')).toBeDisabled();
  await expect(page.locator('#import-sources [name=plan]')).toBeDisabled();
  await expect(page.locator('#import-sources [name=characters]')).toBeDisabled();
  await page.locator('#import-sources').evaluate(f=>f.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true})));
  release();await expect(page.locator('#import-results')).toContainText('Partially imported');
  expect(calls).toBe(1);
  await expect(page.locator('#import-results')).toContainText('Saved and processed');
  await expect(page.locator('#import-results')).toContainText('Not applied');
  await expect(page.locator('#import-results')).toContainText('Successful files are already applied');
  await expect(page.locator('#import-results')).toContainText('Safe failure <img src=x>');
  await expect(page.locator('#import-results img')).toHaveCount(0);
  expect(await page.locator('#import-sources [name=plan]').evaluate(e=>e.files.length)).toBe(0);
  expect(await page.locator('#import-sources [name=characters]').evaluate(e=>e.files[0].name)).toBe('second.md');
  await page.unroute(`**/api/stories/${f.story_id}/sources`);
  await page.route(`**/api/stories/${f.story_id}/sources`,route=>route.fulfill({status:409,json:{partial:false,files:[{...files[1],client_index:0,status:'failed',error:'Матеріали вже змінено; файл не застосовано'}]}}));
  await uploadFile(page,'plan','retry.md','Plan');
  await expect(page.locator('#import-results')).toContainText('Import not applied');
  await expect(page.locator('#import-results')).toContainText('second.md');
  await expect(page.locator('#import-results')).toContainText('Materials have changed; the file was not applied');
  await expect(page.locator('#notice')).toContainText('Materials have changed; the file was not applied');
});


test('writing errors and dirty exit preserve target and leave scene targets unchanged',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${f.story_id}/settings`);await writing(page);
  const target=page.locator('#profile-form [name="target_words"]');await target.fill('25000');
  await expect(target).not.toHaveAttribute('max');
  await page.route(`**/api/stories/${f.story_id}/settings`,async route=>{
    if(route.request().method()==='PUT')return route.fulfill({status:409,json:{detail:'Synthetic conflict'}});
    return route.continue();
  });
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save-status')).toContainText('Synthetic conflict');
  await expect(target).toHaveValue('25000');await expect(page.locator('#settings-save')).toBeEnabled();
  await page.unroute(`**/api/stories/${f.story_id}/settings`);
  await page.route(`**/api/stories/${f.story_id}/settings`,async route=>{
    if(route.request().method()==='PUT')return route.abort('failed');
    return route.continue();
  });
  await page.locator('#settings-save').click();await expect(page.locator('#settings-save-status')).toContainText('fetch');
  await expect(target).toHaveValue('25000');await expect(page.locator('#settings-save')).toBeEnabled();
  page.once('dialog',d=>d.dismiss());await page.locator('#settings-return').click();
  await expect(target).toHaveValue('25000');
  const view=await(await request.get(`/api/stories/${f.story_id}`)).json();
  expect(view.scenes[0].target_words).toBe(1000);expect(view.story.target_words).toBe(7000);
});


test('confirmed import stays confirmed when refreshing the journal fails',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();let posted=false;
  await page.route(`**/api/stories/${f.story_id}/sources`,async route=>{const response=await route.fetch();posted=true;await route.fulfill({response});});
  await page.route(`**/api/stories/${f.story_id}`,async route=>{if(posted)return route.abort('failed');return route.continue();});
  await page.goto(`/stories/${f.story_id}`);await page.locator('[data-ui-locale="en"]').click();
  await uploadFile(page,'plan','confirmed.md','Сцена 2: День\nОпис');
  await expect(page.locator('#import-results')).toContainText('Import complete');
  await expect(page.locator('#import-results')).toContainText('New scenes: 1');
  await expect(page.locator('#import-results')).toContainText('Could not refresh');
  await page.unroute(`**/api/stories/${f.story_id}`);
  await page.locator('#import-results button').click();
  await expect(page.locator('#import-results')).toContainText('Journal updated');
  await expect(page.locator('.source-record')).toHaveCount(1);
});

test('lost POST response is unknown and never automatically retries an unnumbered scene',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();let posts=0;
  await page.route(`**/api/stories/${f.story_id}/sources`,async route=>{posts++;const response=await route.fetch();expect(response.ok()).toBeTruthy();await route.abort('failed');});
  await page.goto(`/stories/${f.story_id}`);await page.locator('[data-ui-locale="en"]').click();
  await uploadFile(page,'plan','unknown.md','## Інтерлюдія\nОпис');
  await expect(page.locator('#import-results')).toContainText('Outcome unknown');
  await expect(page.locator('#import-results')).not.toContainText('New scenes: 0');
  expect(await page.locator('#import-sources [name="plan"]').evaluate(e=>e.files.length)).toBe(0);
  await expect(page.locator('#import-sources button')).toBeDisabled();
  await page.locator('#import-results button').click();
  await expect(page.locator('#import-results')).toContainText('Journal updated');
  await expect(page.locator('.source-record')).toHaveCount(1);
  expect(posts).toBe(1);
  expect((await(await request.get(`/api/stories/${f.story_id}`)).json()).scenes).toHaveLength(2);
});


test('first filtered plan does not claim multiple files were combined',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  const created=await request.post(`/api/stories/${f.story_id}/scenes`,{data:{title:'Сцена 2: Існуюча',beats:'Сцена 2: Існуюча\nНаявний опис.',author_scene_number:2}});
  expect(created.ok()).toBeTruthy();
  await page.goto(`/stories/${f.story_id}`);await page.locator('[data-ui-locale="en"]').click();
  await uploadFile(page,'plan','single-plan.md','Сцена 2: Дубль\nПропустити.\nСцена 3: Нова\nНовий опис.');
  await page.locator('.workspace-context > summary').click();
  await expect(page.locator('.source-record')).toHaveCount(1);
  await expect(page.locator('#context-content')).toContainText('Active plan from accepted sections');
  await expect(page.locator('#context-content')).not.toContainText('Combined');
  await expect(page.locator('#import-results')).toContainText('Skipped scene numbers: 2');
});


test('journal retains actual import counts after reload and marks old counts unknown',async({page,request})=>{
  const f=await(await request.post('/test-fixture')).json();
  await request.post(`/api/stories/${f.story_id}/sources`,{multipart:{characters:{name:'first-people.md',mimeType:'text/plain',buffer:Buffer.from('## Анна\nПрацює в бібліотеці.')}}});
  await request.post(`/api/stories/${f.story_id}/sources`,{multipart:{characters:{name:'duplicate-people.md',mimeType:'text/plain',buffer:Buffer.from('## Анна\nДубль.')}}});
  await request.post(`/api/stories/${f.story_id}/sources`,{multipart:{plan:{name:'new-scene.md',mimeType:'text/plain',buffer:Buffer.from('Сцена 2: День\nНова подія.')}}});
  await page.goto(`/stories/${f.story_id}`);await page.locator('[data-ui-locale=en]').click();
  await page.locator('.workspace-context > summary').click();
  const first=page.locator('.source-record').filter({hasText:'first-people.md'}),zero=page.locator('.source-record').filter({hasText:'duplicate-people.md'}),plan=page.locator('.source-record').filter({hasText:'new-scene.md'});
  await expect(first).toContainText('New scenes: 0. New character cards: 1.');
  await expect(zero).toContainText('New scenes: 0. New character cards: 0.');
  await expect(plan).toContainText('New scenes: 1. New character cards: 0.');
  await page.reload();await page.locator('.workspace-context > summary').click();
  await expect(first).toContainText('New scenes: 0. New character cards: 1.');
  await page.locator('[data-ui-locale=uk]').click();await expect(first).toContainText('Нові сцени: 0. Нові картки персонажів: 1.');
  await page.locator('#context-content').screenshot({path:`docs/images/import-journal-counts-${test.info().project.name}.png`});
  await page.route(`**/api/stories/${f.story_id}`,async route=>{const response=await route.fetch(),body=await response.json();for(const file of body.source_files){delete file.created_scene_count;delete file.created_character_count;}await route.fulfill({response,json:body});});
  await page.evaluate(()=>import('/static/editor.js').then(m=>m.refresh()));
  await expect(first).toContainText('Кількість для цього імпорту невідома');
  await expect(first).not.toContainText('Нові сцени: 0');
});
