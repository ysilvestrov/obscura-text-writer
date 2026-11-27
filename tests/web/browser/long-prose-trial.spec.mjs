import {test,expect} from '../../../frontend/browser-test.mjs';

// LONG-PROSE-TRIAL-S07: the store edition offers the one trial in the window and works inside it afterwards.
// Every test starts in the store edition with a free trial and goes back to the full edition.
test.use({locale:'uk-UA'});
const READ_ONLY='Ця книга має частини чи арки; у цій збірці вона доступна лише для читання й експорту';
const view=async(request,id)=>(await request.get(`/api/stories/${id}`)).json();
const store=async(request,extra={})=>expect((await(await request.post('/test-build-edition',{data:{edition:'store',...extra}})).json()).edition).toBe('store');

test.beforeEach(async({request})=>{await request.post('/test-reset-trial')});
test.afterEach(async({request})=>{
  await request.post('/test-build-edition',{data:{edition:'full'}});
  await request.post('/test-reset-trial');
});

async function structure(request,story_id){
  const data=await view(request,story_id);
  const ids=data.scenes.map(scene=>scene.id);
  const parts=[{id:'p1',title:'Дім',arcs:[{id:'a1',title:''}]},{id:'p2',title:'',arcs:[{id:'b1',title:''}]}];
  const scene_arcs=Object.fromEntries(ids.map((id,index)=>[id,index?'b1':'a1']));
  const put=await request.put(`/api/stories/${story_id}/structure`,{data:{expected_revision:data.story.revision,parts,scene_arcs}});
  expect(put.ok(),await put.text()).toBeTruthy();
}

async function structuredBook(request){
  const {story_id,scene_id}=await(await request.post('/test-fixture')).json();
  expect((await request.post(`/api/stories/${story_id}/scenes`,{data:{title:'Друга сцена'}})).ok()).toBeTruthy();
  await structure(request,story_id);
  return {story_id,scene_id};
}

async function openWriting(page){
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
}

async function accept(page,title){
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText(`Увімкнути пробу на «${title}»?`);
  await dialog.getByRole('button',{name:'Підтвердити'}).click();
}

test('flat book offers the trial in settings and gets the structure panel after it',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  const title=(await view(request,story_id)).story.title;
  await store(request);
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  await expect(page.locator('#book-structure')).toHaveCount(0);
  const offer=page.locator('#book-structure-trial').getByRole('button',{name:'Спробувати частини й арки на цій книзі'});
  await offer.click();
  const reloaded=page.waitForEvent('load');
  await accept(page,title);
  await reloaded;  // the page reloads after a successful claim
  await openWriting(page);
  await expect(page.locator('#book-structure').getByRole('button',{name:'Додати частину'})).toBeVisible();
  await expect(page.locator('#book-structure-trial')).toHaveCount(0);
});

test('structured book banner keeps its text and offers the trial',async({page,request})=>{
  const {story_id,scene_id}=await structuredBook(request);
  const title=(await view(request,story_id)).story.title;
  await store(request);
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  await expect(page.locator('#book-readonly')).toHaveText(READ_ONLY);
  await expect(page.locator('#save-text')).toBeDisabled();
  await page.locator('#book-readonly-trial button').click();
  const reloaded=page.waitForEvent('load');
  await accept(page,title);
  await reloaded;  // the page reloads after a successful claim
  await expect(page.locator('#scene-title')).toBeVisible();
  await expect(page.locator('#book-readonly')).toHaveCount(0);
  await expect(page.locator('#book-readonly-trial')).toHaveCount(0);
  await expect(page.locator('#save-text')).not.toBeDisabled();
});

test('used trial shows where it went and the waitlist',async({page,request})=>{
  const first=await(await request.post('/test-fixture')).json();
  const title=(await view(request,first.story_id)).story.title;
  const other=await structuredBook(request);
  await store(request,{waitlist_url:'https://example.test/waitlist'});
  expect((await request.post('/api/long-prose-trial',{data:{story_id:first.story_id,confirm:true}})).ok()).toBeTruthy();
  await page.goto(`/stories/${other.story_id}?scene=${other.scene_id}`);
  await expect(page.locator('#book-readonly')).toHaveText(READ_ONLY);
  const used=page.locator('#book-readonly-trial');
  await expect(used).toContainText(`Пробу використано на «${title}»`);
  await expect(used.locator('a')).toHaveText('Повідомте про платну версію');
  await expect(used.locator('a')).toHaveAttribute('href','https://example.test/waitlist');
  await expect(used.locator('button')).toHaveCount(0);
});

test('trial book keeps the memory-build menu',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-build')).json();
  await structure(request,fixture.story_id);
  await store(request);
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_ids[0]}&material=plan`);
  await expect(page.locator('#scene-title')).toHaveText('Пірс');
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-rename')).toBeVisible();
  await expect(page.locator('#story-menu-build-memory')).toBeHidden();
  await page.locator('#story-menu-toggle').click();
  expect((await request.post('/api/long-prose-trial',{data:{story_id:fixture.story_id,confirm:true}})).ok()).toBeTruthy();
  await page.reload();
  await expect(page.locator('#scene-title')).toHaveText('Пірс');
  await page.locator('#story-menu-toggle').click();
  await expect(page.locator('#story-menu-build-memory')).toBeVisible();
  await expect(page.locator('#story-menu-build-memory')).toHaveText('Побудувати пам’ять (сцен: 2)');
});

// Series: both projects share one fixture server, so titles carry the project name and a random tail.
const unique=title=>`${title} ${test.info().project.name} ${Math.random().toString(36).slice(2,7)}`;
const SERIES_FULL='Проба серії дозволяє дві книги; третя — у платній версії';
const LEAVE='Книга вийде із серії проби й збереже частини й арки, але місце в серії проби не звільниться.';

test('free trial creates the trial series from the series page',async({page,request})=>{
  await store(request);
  const title=unique('Пробна сага');
  await page.goto('/');
  await page.getByRole('link',{name:'Серії'}).click();
  await expect(page).toHaveURL(/\/series$/);
  await expect(page.locator('.series-trial-hint')).toHaveText('Пробною може стати серія, у якій не більше двох книг.');
  await page.getByLabel('Назва серії').fill(title);
  const reloaded=page.waitForEvent('load');
  await page.getByRole('button',{name:'Створити пробну серію'}).click();
  await accept(page,title);
  await reloaded;
  await expect(page.locator('#series-list .card')).toHaveCount(1);
  await expect(page.locator('#series-list .card a')).toHaveText(title);
  await expect(page.locator('#series-create')).toBeHidden();
});

test('a series from another edition can become the trial series but is not a link',async({page,request})=>{
  const title=unique('Чужа сага');
  const item=await(await request.post('/api/series',{data:{title}})).json();
  for(const book of ['Перша','Друга'])expect((await request.post(`/api/series/${item.id}/books`,{data:{title:book}})).ok()).toBeTruthy();
  await store(request);
  await page.goto('/series');
  const card=page.locator('#series-list .card',{hasText:title});
  await expect(card).toBeVisible();
  await expect(card.locator('a[href]')).toHaveCount(0);
  const reloaded=page.waitForEvent('load');
  await card.getByRole('button',{name:'Зробити пробною серією'}).click();
  await accept(page,title);
  await reloaded;
  await expect(page.locator(`#series-list a[href="/series/${item.id}"]`)).toHaveText(title);
});

test('third book of the trial series is disabled with the paid hint',async({page,request})=>{
  await store(request);
  const item=await(await request.post('/api/series',{data:{title:unique('Повна сага'),trial:true}})).json();
  for(const book of ['Перша','Друга'])expect((await request.post(`/api/series/${item.id}/books`,{data:{title:book}})).ok()).toBeTruthy();
  await page.goto(`/series/${item.id}`);
  await expect(page.locator('#series-books .series-book')).toHaveCount(2);
  await expect(page.locator('#series-new-book')).toBeDisabled();
  await expect(page.locator('#series-new-book')).toHaveAttribute('title',SERIES_FULL);
});

test('leaving the trial series warns that the place stays taken',async({page,request})=>{
  await store(request);
  const item=await(await request.post('/api/series',{data:{title:unique('Сага виходу'),trial:true}})).json();
  const book=await(await request.post(`/api/series/${item.id}/books`,{data:{title:'Перша'}})).json();
  await page.goto(`/stories/${book.id}/settings`);
  await openWriting(page);
  const form=page.locator('#story-series-form');
  await expect(form.locator('select[name="series_id"]')).toHaveValue(item.id);
  await form.locator('select[name="series_id"]').selectOption('');
  await form.getByRole('button',{name:'Зберегти'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText(LEAVE);
  await dialog.getByRole('button',{name:'Скасувати'}).click();
  await expect(dialog).toHaveCount(0);
  expect((await view(request,book.id)).series.id).toBe(item.id);
});

test('book settings offer only the trial series',async({page,request})=>{
  const other=await(await request.post('/api/series',{data:{title:unique('Інша сага')}})).json();
  const {story_id}=await(await request.post('/test-fixture')).json();
  await store(request);
  const item=await(await request.post('/api/series',{data:{title:unique('Сага вибору'),trial:true}})).json();
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  const select=page.locator('#story-series-form select[name="series_id"]');
  await expect(select).toBeVisible();
  expect(await select.locator('option').evaluateAll(items=>items.map(item=>item.value))).toEqual(['',item.id]);
  expect(other.id).not.toBe(item.id);
});

test('the trial book has no series form',async({page,request})=>{
  const {story_id}=await(await request.post('/test-fixture')).json();
  await store(request);
  expect((await request.post('/api/long-prose-trial',{data:{story_id,confirm:true}})).ok()).toBeTruthy();
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  await expect(page.locator('#book-structure')).toBeVisible();
  await expect(page.locator('#story-series-form')).toBeHidden();
});
