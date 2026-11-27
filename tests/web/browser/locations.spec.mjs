import {test,expect} from '../../../frontend/browser-test.mjs';

// MEMORY-LOCATIONS-S07, S12 in the browser: the «Locations» page lists cards, merges a look-alike, splits it back and
// saves a description; the workspace links to it and back, and a location change does not make the next memory-kind
// change a conflict once the author is back.
test.use({locale:'uk-UA'});

async function openPanel(page,request){
  const fixture=await(await request.post('/test-locations')).json();
  await page.goto(`/stories/${fixture.story_id}/locations?scene=${fixture.scene_id}&material=memory`);
  const panel=page.locator('#locations-page #story-locations');
  await expect(panel.locator('.location-row')).toHaveCount(4);
  return {fixture,panel};
}

const row=(panel,path)=>panel.locator('.location-row').filter({has:panel.page().locator('strong',{hasText:new RegExp(`^${path}$`)})});

test('the panel lists cards and merges a suggested look-alike, then splits it back',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  await expect(row(panel,'Квартира Джорджа / вітальня')).toContainText('Сцени: 1. Ранок');
  const hint=panel.locator('.location-suggestion');
  await expect(hint).toHaveCount(1);
  await expect(hint).toContainText('«Квартира Джоржа» схоже на «Квартира Джорджа»');
  await hint.getByRole('button',{name:'Злити'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('текст планів не зміниться');
  await dialog.getByRole('button',{name:'Злити'}).click();
  await expect(page.locator('#notice')).toContainText('Локації злито.');
  await expect(panel.locator('.location-suggestion')).toHaveCount(0);
  const merged=row(panel,'Квартира Джоржа');
  await expect(merged).toContainText('Злито в «Квартира Джорджа»');
  await expect(row(panel,'Квартира Джорджа')).toContainText('Сцени: 2. Вечір');
  await merged.getByRole('button',{name:'Розділити'}).click();
  await expect(page.locator('#notice')).toContainText('Злиття скасовано.');
  await expect(row(panel,'Квартира Джоржа')).not.toContainText('Злито');
});

test('a description is saved and a conflict keeps the typed text',async({page,request})=>{
  const {fixture,panel}=await openPanel(page,request);
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Тісний двір із липою.');
  await expect(yard).toContainText('21 / 2000');
  // Another tab changes the story first.
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const room=data.locations.find(card=>card.path==='Квартира Джорджа / вітальня');
  expect((await request.put(`/api/stories/${fixture.story_id}/locations/${room.id}`,
    {data:{description:'Інша вкладка.',expected_revision:data.story_revision}})).ok()).toBeTruthy();
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Твір уже змінено');
  await expect(row(panel,'двір').locator('textarea')).toHaveValue('Тісний двір із липою.');
  await row(panel,'двір').getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  await expect(row(panel,'двір').locator('summary')).toContainText('Тісний двір із липою.');
});

const pickKind=page=>async value=>{
  const kind=page.locator('button.memory-kind').first();
  await kind.click();await page.locator(`.memory-kind-menu:not([hidden]) [role=menuitemradio][data-kind="${value}"]`).click();
};
const noSideScroll=page=>page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth);

test('the header and the memory tab open the page, which returns to the same scene and material',async({page,request})=>{
  const fixture=await(await request.post('/test-locations')).json();
  const position=`scene=${fixture.scene_id}&material=memory`;
  await page.goto(`/stories/${fixture.story_id}?${position}`);
  await expect(page.locator('#memory-view #story-locations')).toHaveCount(0);
  const line=page.locator('#memory-view > .memory-locations-link');
  await expect(line).toContainText('Локації твору →');
  await expect(page.locator('#memory-view > :last-child')).toHaveClass(/memory-locations-link/);
  await expect(line.locator('a')).toHaveAttribute('href',`/stories/${fixture.story_id}/locations?${position}`);
  expect(await noSideScroll(page)).toBe(true);
  await page.locator('#workspace-locations').click();
  await expect(page).toHaveURL(url=>url.pathname===`/stories/${fixture.story_id}/locations`&&url.search==='?'+position);
  await expect(page.locator('#locations-page h1')).toHaveText('Локації');
  await expect(page.locator('#locations-page .location-row')).toHaveCount(4);
  expect(await noSideScroll(page)).toBe(true);
  await page.locator('#locations-return').click();
  await expect(page).toHaveURL(url=>url.pathname===`/stories/${fixture.story_id}`&&url.search==='?'+position);
  await expect(page.locator('button.memory-kind').first()).toBeVisible();
});

test('a story without locations explains where cards come from',async({page,request})=>{
  const story=await(await request.post('/api/stories',{data:{title:'Порожньо'}})).json();
  await page.goto(`/stories/${story.id}/locations`);
  const section=page.locator('#locations-page #story-locations');
  await expect(section).toContainText('Картки з’являються з рядка «Локація:» у плані сцени');
  await expect(section.getByRole('link',{name:'Персонажі'})).toHaveAttribute('href',`/stories/${story.id}/characters`);
  await expect(page.locator('#locations-return')).toHaveAttribute('href',`/stories/${story.id}`);
});

test('leaving with a typed description asks first',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Ще не збережено.');
  let asked=null;
  page.once('dialog',dialog=>{asked=dialog.type();void dialog.dismiss();});
  await page.locator('#locations-return').click();
  await expect.poll(()=>asked).toBe('beforeunload');
  await expect(page.locator('#locations-page')).toBeVisible();
  await expect(row(panel,'двір').locator('textarea')).toHaveValue('Ще не збережено.');
});

test('a draft of a card merged away does not keep the page asking',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Не встиг зберегти.');
  await yard.getByRole('button',{name:'Злити в…'}).click();
  await yard.locator('select').selectOption({label:'Квартира Джорджа'});
  await yard.getByRole('button',{name:'Злити'}).click();
  await page.locator('.app-dialog').getByRole('button',{name:'Злити'}).click();
  await expect(page.locator('#notice')).toContainText('Локації злито.');
  let asked=null;
  page.once('dialog',dialog=>{asked=dialog.type();void dialog.dismiss();});
  await page.locator('#locations-return').click();
  await expect(page.locator('#workspace')).toBeVisible();
  expect(asked).toBeNull();
});

test('the page restored from the browser cache reloads the list before the next change',async({page,request})=>{
  const {fixture,panel}=await openPanel(page,request);
  // The workspace (or another tab) moved the story revision while this page waited in the cache.
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const room=data.locations.find(card=>card.path==='Квартира Джорджа / вітальня');
  expect((await request.put(`/api/stories/${fixture.story_id}/locations/${room.id}`,
    {data:{description:'Змінено деінде.',expected_revision:data.story_revision}})).ok()).toBeTruthy();
  const reloaded=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/stories/${fixture.story_id}/locations`);
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
  await reloaded;
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Після повернення.');
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
});

test('a location change does not turn the next memory-kind change into a conflict after the return',async({page,request})=>{
  const fixture=await(await request.post('/test-locations')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=memory`);
  const pick=pickKind(page);
  await expect(page.locator('button.memory-kind').first()).toBeVisible();
  await page.locator('#workspace-locations').click();
  const panel=page.locator('#locations-page #story-locations');
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Тісний двір.');
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  // A merge: the memory row names the target after the return.
  const room=row(panel,'Квартира Джорджа / вітальня');
  await room.getByRole('button',{name:'Злити в…'}).click();
  await room.locator('select').selectOption({label:'двір'});
  await room.getByRole('button',{name:'Злити'}).click();
  await page.locator('.app-dialog').getByRole('button',{name:'Злити'}).click();
  await expect(page.locator('#notice')).toContainText('Локації злито.');
  await page.locator('#locations-return').click();
  await expect(page.locator('.memory-locations').first()).toContainText('Локації: двір');
  await pick('atmosphere');
  await expect(page.locator('#notice')).toContainText('Тип запису збережено');
});

test('a workspace restored from the page cache notices a story change made elsewhere',async({page,request})=>{
  const fixture=await(await request.post('/test-locations')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=memory`);
  const pick=pickKind(page);
  await expect(page.locator('button.memory-kind').first()).toBeVisible();
  // The locations page (another tab, or the page left before «Back») changes the story.
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const yard=data.locations.find(card=>card.path==='двір');
  expect((await request.put(`/api/stories/${fixture.story_id}/locations/${yard.id}`,
    {data:{description:'Двір змінено деінде.',expected_revision:data.story_revision}})).ok()).toBeTruthy();
  const reloaded=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/stories/${fixture.story_id}`);
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
  await reloaded;
  await pick('core');
  await expect(page.locator('#notice')).toContainText('Тип запису збережено');
});

test('a story change noticed on return leaves unsaved scene text alone',async({page,request})=>{
  const fixture=await(await request.post('/test-locations')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=plan`);
  const editor=page.locator('#editor');
  await expect(editor).toBeVisible();
  await editor.focus();await page.keyboard.press('Control+End');await page.keyboard.type(' Незбережена правка плану.');
  await expect(page.locator('#save-text')).toBeEnabled();
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const yard=data.locations.find(card=>card.path==='двір');
  expect((await request.put(`/api/stories/${fixture.story_id}/locations/${yard.id}`,
    {data:{description:'Змінено деінде.',expected_revision:data.story_revision}})).ok()).toBeTruthy();
  const reloaded=page.waitForResponse(response=>new URL(response.url()).pathname===`/api/stories/${fixture.story_id}`);
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
  await reloaded;
  await page.waitForTimeout(300);
  await expect(editor).toHaveValue(/Незбережена правка плану\.$/);
  await expect(page.locator('#save-text')).toBeEnabled();
});

test('a slow reload after a return does not undo a save made meanwhile',async({page,request})=>{
  const {panel}=await openPanel(page,request);
  // The restoration GET reads the list before the save, but its answer arrives after it.
  let release;const held=new Promise(resolve=>{release=resolve});
  let holding=true;
  await page.route(url=>url.pathname.endsWith('/locations'),async route=>{
    if(!holding||route.request().method()!=='GET')return route.continue();
    holding=false;const response=await route.fetch();await held;await route.fulfill({response});
  });
  await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Збережено під час перечитування.');
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  release();
  await page.waitForTimeout(500);
  await expect(row(panel,'двір').locator('summary')).toContainText('Збережено під час перечитування.');
  await row(panel,'двір').locator('summary').click();
  await row(panel,'двір').locator('textarea').fill('Друга правка.');
  await row(panel,'двір').getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Опис збережено.');
  await expect(row(panel,'двір').locator('summary')).toContainText('Друга правка.');
});

test('a draft of a card merged elsewhere is dropped when the refused save reloads the list',async({page,request})=>{
  const {fixture,panel}=await openPanel(page,request);
  const yard=row(panel,'двір');
  await yard.locator('summary').click();
  await yard.locator('textarea').fill('Набрано до злиття.');
  const data=await(await request.get(`/api/stories/${fixture.story_id}/locations`)).json();
  const card=path=>data.locations.find(item=>item.path===path);
  expect((await request.post(`/api/stories/${fixture.story_id}/locations/${card('двір').id}/merge`,
    {data:{into:card('Квартира Джорджа').id,expected_revision:data.story_revision}})).ok()).toBeTruthy();
  await yard.getByRole('button',{name:'Зберегти опис'}).click();
  await expect(page.locator('#notice')).toContainText('Твір уже змінено');
  await expect(row(panel,'двір')).toContainText('Злито в «Квартира Джорджа»');
  let asked=null;
  page.once('dialog',dialog=>{asked=dialog.type();void dialog.dismiss();});
  await page.locator('#locations-return').click();
  await expect(page.locator('#workspace')).toBeVisible();
  expect(asked).toBeNull();
});

test('a place a prose search gave a scene is removed from it; a plan place has no such button',async({page,request})=>{
  // MEMORY-LOCATIONS-S08: «двір» is named by the plan of «Вечір» and was given to «Ніч» by a search.
  const fixture=await(await request.post('/test-locations?model=true')).json();
  await page.goto(`/stories/${fixture.story_id}/locations`);
  const panel=page.locator('#locations-page #story-locations');
  const yard=row(panel,'двір');
  await expect(yard).toContainText('Сцени: 2. Вечір, 3. Ніч');
  await expect(panel.getByRole('button',{name:/^Прибрати з/})).toHaveCount(1);
  await yard.getByRole('button',{name:'Прибрати з «3. Ніч»'}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('Прибрати «двір» зі сцени «3. Ніч»?');
  await dialog.getByRole('button',{name:'Прибрати'}).click();
  await expect(page.locator('#notice')).toContainText('Місце прибрано зі сцени.');
  await expect(row(panel,'двір')).toContainText('Сцени: 2. Вечір');
  await expect(row(panel,'двір')).not.toContainText('Ніч');
  await expect(panel.getByRole('button',{name:/^Прибрати з/})).toHaveCount(0);
});

test('a name the parse cut is glued into one card and unglued back',async({page,request})=>{
  // MEMORY-LOCATIONS-S11: «Кава» names «Бар, в якому пахне кавою»; the comma cut it into «Бар» and «в якому пахне кавою».
  const fixture=await(await request.post('/test-locations?glue=true')).json();
  await page.goto(`/stories/${fixture.story_id}/locations`);
  const panel=page.locator('#locations-page #story-locations');
  await expect(row(panel,'Бар')).toContainText('Сцени: 3. Кава');
  await row(panel,'Бар').getByRole('button',{name:'Склеїти з…'}).click();
  const select=row(panel,'Бар').getByRole('combobox',{name:'Яку назву склеїти з «Бар»'});
  await expect(select.locator('option')).toHaveText(['Бар, в якому пахне кавою']);
  await row(panel,'Бар').getByRole('button',{name:'Склеїти',exact:true}).click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('Склеїти «Бар, в якому пахне кавою» в одну назву? Сцен: 1. План не зміниться');
  await dialog.getByRole('button',{name:'Склеїти'}).click();
  await expect(page.locator('#notice')).toContainText('Назву склеєно.');
  await expect(row(panel,'Бар, в якому пахне кавою')).toContainText('Сцени: 3. Кава');
  await expect(row(panel,'Бар')).toContainText('Жодна сцена не називає її прямо');
  const glued=panel.locator('.location-glues');
  await expect(glued).toContainText('Склеєні назви');
  await expect(glued).toContainText('Бар, в якому пахне кавою');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth)).toBe(true);
  await glued.getByRole('button',{name:'Розклеїти'}).click();
  await expect(dialog).toContainText('Ваші злиття лишаться');
  await dialog.getByRole('button',{name:'Розклеїти'}).click();
  await expect(page.locator('#notice')).toContainText('Назву розклеєно.');
  await expect(row(panel,'Бар')).toContainText('Сцени: 3. Кава');
  await expect(panel.locator('.location-glues')).toHaveCount(0);
});
