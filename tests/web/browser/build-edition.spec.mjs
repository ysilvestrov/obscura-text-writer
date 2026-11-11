import {test,expect} from '../../../frontend/browser-test.mjs';

// BUILD-EDITION-001-S06/S07: the fixture server is switched to the store edition for each test and back afterwards.
test.use({locale:'uk-UA'});
test.beforeEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'store'}})).json()).edition).toBe('store')});
test.afterEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'full'}})).json()).edition).toBe('full')});

const openWriting=async page=>{
  if(test.info().project.name==='mobile')await page.locator('#settings-section-mobile').selectOption('writing');
  else await page.locator('[data-settings-nav="writing"]').click();
};
const offered=select=>select.locator('option').evaluateAll(options=>options.filter(o=>!o.hidden&&!o.disabled&&o.value!=='').map(o=>o.value));

test('story rating form offers only the levels of the store edition',async({page,request})=>{
  const {story_id}=await(await request.post('/test-unrated')).json();
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  const form=page.locator('#rating-form');
  await expect(form.locator('.rating-edition-hint')).toHaveText('У цьому виданні Obscura найвищий рівень сексуального змісту — 1.');
  expect(await offered(form.locator('select[name="sexual"]'))).toEqual(['0','1']);
  expect(await offered(form.locator('select[name="violence"]'))).toEqual(['0','1','2']);
  expect(await offered(form.locator('select[name="themes"]'))).toEqual(['0','1','2']);
});

test('a stored level above the limit stays visible and can only be lowered',async({page,request})=>{
  const {story_id}=await(await request.post('/test-unrated')).json();
  await request.post(`/test-force-story-rating/${story_id}`,{data:{sexual:2,violence:0,themes:0}});
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  const form=page.locator('#rating-form'),sexual=form.locator('select[name="sexual"]');
  await expect(sexual).toHaveValue('2');
  expect(await offered(sexual)).toEqual(['0','1','2']);
  await sexual.selectOption('1');
  await form.locator('#rating-save').click();
  await expect(page.locator('#notice')).toContainText('Рейтинг збережено');
  await expect(sexual).toHaveValue('1');
  expect(await offered(sexual)).toEqual(['0','1']);
});

test('scene rating panel follows the limit and late app info keeps unsaved scene settings',async({page,request})=>{
  const {story_id,scene_id}=await(await request.post('/test-unrated')).json();
  const story=await(await request.get(`/api/stories/${story_id}/settings`)).json();
  await request.put(`/api/stories/${story_id}/content-rating`,{data:{content_rating:{sexual:0,violence:0,themes:0},expected_revision:story.story.revision}});
  // App info answers after the author has started typing: the scene settings form must not be rebuilt.
  let release;const held=new Promise(resolve=>{release=resolve});
  await page.route('**/api/app-info',async route=>{await held;await route.continue()});
  await page.goto(`/stories/${story_id}?scene=${scene_id}`);
  // The scene panel lives in a collapsed details block on both layouts.
  await page.locator('.tool-section[data-section=scene]').evaluate(details=>{details.open=true});
  const title=page.locator('#scene-settings input[name="title"]');
  await expect(title).toBeVisible();
  await title.fill('Назва, яку ще не збережено');
  const panel=page.locator('#scene-rating');
  await panel.locator('input[name="mode"][value="own"]').check();
  await panel.locator('select[name="violence"]').selectOption('2');
  release();
  await expect(panel.locator('.rating-edition-hint')).toHaveText('У цьому виданні Obscura найвищий рівень сексуального змісту — 1.');
  await expect(title).toHaveValue('Назва, яку ще не збережено');
  await expect(panel.locator('input[name="mode"][value="own"]')).toBeChecked();
  await expect(panel.locator('select[name="violence"]')).toHaveValue('2');
  await expect(panel.locator('select[name="violence"]')).toBeEnabled();
  expect(await offered(panel.locator('select[name="sexual"]'))).toEqual(['0','1']);
});

test('header shows the links of the edition and translates them',async({page})=>{
  await page.goto('/');
  const links=page.locator('.app-links .app-link');
  await expect(links).toHaveText(['Подякувати авторові','Поскаржитися на результат']);
  await expect(links.nth(1)).toHaveAttribute('href','https://example.test/report');
  await expect(links.nth(1)).toHaveAttribute('target','_blank');
  await expect(links.nth(1)).toHaveAttribute('rel','noopener noreferrer');
  await page.locator('[data-ui-locale="en"]').click();
  await expect(links).toHaveText(['Support the author','Report a result']);
});

test('rating forms offer every level when app info is unavailable',async({page,request})=>{
  const {story_id}=await(await request.post('/test-unrated')).json();
  await page.route('**/api/app-info',route=>route.abort());
  await page.goto(`/stories/${story_id}/settings`);
  await openWriting(page);
  const form=page.locator('#rating-form');
  await form.locator('select[name="sexual"]').selectOption('2');
  expect(await offered(form.locator('select[name="sexual"]'))).toEqual(['0','1','2']);
  await expect(form.locator('.rating-edition-hint')).toHaveCount(0);
  // The server still holds the limit.
  await form.locator('select[name="violence"]').selectOption('0');
  await form.locator('select[name="themes"]').selectOption('0');
  await form.locator('#rating-save').click();
  await expect(page.locator('#notice')).toContainText('найвищий дозволений — 1');
});
