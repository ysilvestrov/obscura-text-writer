import {test,expect} from '../../../frontend/browser-test.mjs';

// MANUSCRIPT-IMPORT in the browser: the library opens the import dialog; the preview lists the scenes, a boundary moves in
// the paragraph list, the import ends with the summary that leads to the memory build. Neutral example: a pier lighthouse.
test.use({locale:'uk-UA'});
const DOCX='application/vnd.openxmlformats-officedocument.wordprocessingml.document';
const TITLES=['Пірс (1)','Пірс (2)','Шторм (1)','Шторм (2)'];

async function seed(request){return (await request.post('/test-manuscript-import')).json()}
const docxFile=fixture=>({name:'manuscript.docx',mimeType:DOCX,buffer:Buffer.from(fixture.docx_base64,'base64')});
const mdFile=fixture=>({name:'manuscript.md',mimeType:'text/markdown',buffer:Buffer.from(fixture.md_base64,'base64')});
const sceneTitles=dialog=>dialog.locator('#manuscript-import-scenes .manuscript-import-scene-title');

async function openDialog(page){
  const open=page.locator('#manuscript-import-open');
  await expect(open).toHaveText('Імпорт рукопису (DOCX, Markdown, TXT)…');
  await open.click();
  const dialog=page.locator('#manuscript-import-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#manuscript-import-file')).toBeFocused();
  return dialog;
}
async function preview(page,file){
  const dialog=await openDialog(page);
  const answered=page.waitForResponse(res=>res.request().method()==='POST'&&res.url().endsWith('/api/manuscript-import/preview'));
  await dialog.locator('#manuscript-import-file').setInputFiles(file);
  const data=await (await answered).json();
  await expect(sceneTitles(dialog)).toHaveCount(4);
  return {dialog,data};
}
async function fitsWindow(page,dialog){
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const width=await page.evaluate(()=>innerWidth),box=await dialog.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);
}

test('a DOCX preview, a new boundary, the import and the summary with the memory build',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog}=await preview(page,docxFile(fixture));
  await expect(dialog.locator('#manuscript-import-title')).toHaveText('Імпорт рукопису');
  for(const [index,title] of TITLES.entries())await expect(sceneTitles(dialog).nth(index)).toHaveValue(title);
  const scenes=dialog.locator('#manuscript-import-scenes > li');
  await expect(scenes.nth(3).locator('.manuscript-import-proposed')).toHaveText('запропоновано');
  await expect(scenes.nth(2).locator('.manuscript-import-proposed')).toHaveCount(0);
  await expect(dialog.locator('#manuscript-import-book-title')).toHaveValue('Маяк на пірсі');
  await expect(dialog.locator('#manuscript-import-front-matter')).toBeVisible();
  await expect(dialog.locator('#manuscript-import-submit')).toHaveText('Імпортувати');
  await expect(dialog.locator('#manuscript-import-submit')).toBeEnabled();

  // Expanding a scene loads its paragraphs; every prose paragraph but the first offers «Межа тут».
  const loaded=page.waitForResponse(res=>/\/api\/manuscript-import\/[0-9a-f]{32}\/paragraphs\?start=8&end=20$/.test(res.url()));
  await scenes.nth(2).locator('summary').click();
  await loaded;
  const paragraphs=scenes.nth(2).locator('.manuscript-import-paragraphs > li');
  await expect(paragraphs).toHaveCount(13);
  // The scene start is a chapter boundary: it can be removed; the first scene of the book cannot.
  await expect(paragraphs.first().locator('button')).toHaveText('Прибрати межу');
  await scenes.nth(0).locator('summary').click();
  await expect(scenes.nth(0).locator('.manuscript-import-paragraphs > li')).toHaveCount(2);
  await expect(scenes.nth(0).locator('.manuscript-import-paragraphs > li').first().locator('button')).toHaveCount(0);
  await fitsWindow(page,dialog);
  const before=await scenes.nth(2).locator('.manuscript-import-words').innerText();
  await paragraphs.nth(6).locator('button',{hasText:'Межа тут'}).click();
  await expect(sceneTitles(dialog)).toHaveCount(5);
  // Focus stays on the moved boundary: now the «Прибрати межу» button of the new scene.
  await expect(dialog.locator('.manuscript-import-boundary[data-index="14"]')).toBeFocused();
  await page.waitForTimeout(100);  // a late re-render of the paragraph list would drop the focus
  await expect(dialog.locator('.manuscript-import-boundary[data-index="14"]')).toBeFocused();
  await expect(sceneTitles(dialog).nth(3)).toHaveValue('Шторм (3)');
  await expect(scenes.nth(2).locator('.manuscript-import-words')).not.toHaveText(before);
  await expect(scenes.nth(3).locator('.manuscript-import-paragraphs > li').first().locator('button')).toHaveText('Прибрати межу');
  await fitsWindow(page,dialog);
  await sceneTitles(dialog).nth(0).fill('Пірс на світанку');

  await dialog.locator('#manuscript-import-submit').click();
  const result=dialog.locator('#manuscript-import-result');
  await expect(result).toBeVisible();
  const build=result.locator('#manuscript-import-build-memory');
  await expect(build).toHaveText('Побудувати пам’ять (сцен: 5)');
  const href=await build.getAttribute('href');
  expect(href).toMatch(/^\/stories\/[0-9a-f]{32}\?build_memory=1$/);
  const storyId=href.split('/')[2].split('?')[0];
  await expect(result.locator(`a[href="/stories/${storyId}"]`)).toContainText('Маяк на пірсі');
  await expect(dialog.locator('#manuscript-import-cancel')).toHaveText('Закрити');
  await fitsWindow(page,dialog);
  const view=await (await request.get(`/api/stories/${storyId}`)).json();
  expect(view.scenes.map(scene=>scene.title)).toEqual(['Пірс на світанку','Пірс (2)','Шторм (1)','Шторм (3)','Шторм (2)']);
  // Nothing is left to delete: closing the summary sends no DELETE.
  const deletes=[];page.on('request',req=>{if(req.method()==='DELETE')deletes.push(req.url())});
  await dialog.locator('#manuscript-import-cancel').click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#manuscript-import-open')).toBeFocused();
  expect(deletes).toHaveLength(0);
});

test('changing the chapter markers parses the file again and resets the author boundaries',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog,data}=await preview(page,docxFile(fixture));
  const scenes=dialog.locator('#manuscript-import-scenes > li');
  await scenes.nth(2).locator('summary').click();
  await scenes.nth(2).locator('.manuscript-import-paragraphs > li').nth(6).locator('button').click();
  await expect(sceneTitles(dialog)).toHaveCount(5);
  await dialog.locator('.manuscript-import-structure summary').click();  // chapters and parts are folded by default
  await expect(dialog.locator('#manuscript-import-detected')).toHaveText('Визначено: маркери глав');
  const again=page.waitForRequest(req=>req.method()==='POST'&&req.url().endsWith('/api/manuscript-import/preview'));
  await dialog.locator('#manuscript-import-chapter-markers').fill('Розділ');
  await dialog.locator('#manuscript-import-chapter-markers').press('Tab');
  const sent=(await again).postData();
  expect(sent).toContain(data.import_id);expect(sent).toContain('Розділ');
  await expect(sceneTitles(dialog)).toHaveCount(3);
  await expect(dialog.locator('#manuscript-import-warnings')).toContainText('ваші межі сцен скинуто');
  await expect(dialog.locator('#manuscript-import-detected')).toHaveText('Визначено: глав не знайдено');
  // The new preview imports with its own fingerprint.
  await dialog.locator('#manuscript-import-submit').click();
  await expect(dialog.locator('#manuscript-import-build-memory')).toHaveText('Побудувати пам’ять (сцен: 3)');
});

test('a preview changed elsewhere answers 409: the dialog returns to the file choice',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog,data}=await preview(page,docxFile(fixture));
  // Another tab parses the same file with other markers: the fingerprint of this preview is stale.
  const other=await request.post('/api/manuscript-import/preview',{multipart:{import_id:data.import_id,chapter_markers:'Розділ'}});
  expect(other.ok()).toBeTruthy();
  const deleted=page.waitForRequest(req=>req.method()==='DELETE'&&req.url().endsWith(`/api/manuscript-import/${data.import_id}`));
  await dialog.locator('#manuscript-import-submit').click();
  const status=dialog.locator('#manuscript-import-status');
  await expect(status).toContainText('Перегляд рукопису застарів');
  await expect(status).toContainText('Виберіть файл ще раз');
  await deleted;
  await expect(dialog.locator('#manuscript-import-preview')).toBeHidden();
  await expect(dialog.locator('#manuscript-import-file')).toBeVisible();
  await expect(dialog.locator('#manuscript-import-file')).toBeFocused();
  await dialog.locator('#manuscript-import-file').setInputFiles(docxFile(fixture));
  await expect(sceneTitles(dialog)).toHaveCount(4);
});

test('a kept file that vanished returns to the file choice from the import and from the paragraphs',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  let {dialog,data}=await preview(page,docxFile(fixture));
  expect((await request.delete(`/api/manuscript-import/${data.import_id}`)).status()).toBe(204);  // as the 24-hour sweep would
  await dialog.locator('#manuscript-import-submit').click();
  const status=dialog.locator('#manuscript-import-status');
  await expect(status).toHaveText('Файл перегляду більше не зберігається: минуло 24 години або імпорт скасовано в іншій вкладці. Виберіть файл ще раз.');
  await expect(dialog.locator('#manuscript-import-preview')).toBeHidden();
  await expect(dialog.locator('#manuscript-import-file')).toBeFocused();
  // The same from a scene's paragraphs.
  const again=page.waitForResponse(res=>res.request().method()==='POST'&&res.url().endsWith('/api/manuscript-import/preview'));
  await dialog.locator('#manuscript-import-file').setInputFiles(docxFile(fixture));
  data=await (await again).json();
  await expect(sceneTitles(dialog)).toHaveCount(4);
  await request.delete(`/api/manuscript-import/${data.import_id}`);
  await dialog.locator('#manuscript-import-scenes > li').nth(2).locator('summary').click();
  await expect(status).toContainText('Файл перегляду більше не зберігається');
  await expect(dialog.locator('#manuscript-import-preview')).toBeHidden();
  await expect(dialog.locator('#manuscript-import-file')).toBeFocused();
});

test('closing without saving deletes the kept file and reopening shows the empty choice',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog,data}=await preview(page,docxFile(fixture));
  const deleted=page.waitForRequest(req=>req.method()==='DELETE'&&req.url().endsWith(`/api/manuscript-import/${data.import_id}`));
  await dialog.locator('#manuscript-import-cancel').click();
  await deleted;
  await expect(dialog).toBeHidden();
  const again=await openDialog(page);
  await expect(again.locator('#manuscript-import-preview')).toBeHidden();
  await expect(again.locator('#manuscript-import-status')).toHaveText('');
  expect(await again.locator('#manuscript-import-file').evaluate(input=>input.value)).toBe('');
  // Escape is a way out too.
  const second=page.waitForRequest(req=>req.method()==='DELETE'&&/\/api\/manuscript-import\/[0-9a-f]{32}$/.test(req.url()));
  await again.locator('#manuscript-import-file').setInputFiles(docxFile(fixture));
  await expect(sceneTitles(again)).toHaveCount(4);
  await page.keyboard.press('Escape');
  await second;
  await expect(again).toBeHidden();
});

test('the English interface leaves only the manuscript text in Ukrainian',async({page,request})=>{
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog}=await preview(page,docxFile(fixture));
  await dialog.locator('#manuscript-import-scenes > li').nth(2).locator('summary').click();
  await expect(dialog.locator('.manuscript-import-boundary').first()).toBeVisible();
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en')});
  await expect(dialog.locator('#manuscript-import-title')).toHaveText('Import manuscript');
  await expect(dialog.locator('#manuscript-import-submit')).toHaveText('Import');
  await expect(dialog.locator('.manuscript-import-proposed')).toHaveText('proposed');
  await expect(dialog.locator('.manuscript-import-boundary').nth(1)).toHaveText('Boundary here');
  const text=await dialog.evaluate(node=>{
    const clone=node.cloneNode(true);
    for(const item of clone.querySelectorAll('.manuscript-import-text,#manuscript-import-front-matter-text,input,option,[placeholder]'))item.remove();
    return clone.innerText??clone.textContent;
  });
  expect(text).not.toMatch(/[А-Яа-яІіЇїЄєҐґ]/);
});

test('a boundary the server refuses (400) is explained and the accepted boundaries stay',async({page,request})=>{
  // Review M-10: the server still validates every boundary; its 400 goes through diagnostic() and keeps the preview.
  const fixture=await seed(request);
  await page.goto('/');
  const {dialog}=await preview(page,docxFile(fixture));
  const scenes=dialog.locator('#manuscript-import-scenes > li');
  await scenes.nth(2).locator('summary').click();
  const paragraphs=scenes.nth(2).locator('.manuscript-import-paragraphs > li');
  await expect(paragraphs).toHaveCount(13);
  await paragraphs.nth(6).locator('button',{hasText:'Межа тут'}).click();
  await expect(sceneTitles(dialog)).toHaveCount(5);
  let sent=null;
  await page.route(/\/api\/manuscript-import\/[0-9a-f]{32}$/,async route=>{
    if(route.request().method()!=='POST')return route.continue();
    sent=route.request().postDataJSON();
    await route.fulfill({status:400,json:{detail:'Межа сцени має стояти на початку абзацу тексту рукопису',
                                          detail_original:'Межа сцени має стояти на початку абзацу тексту рукопису'}});
  });
  // The English interface shows the catalogue text of the server's Ukrainian refusal: it went through diagnostic().
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en')});
  await dialog.locator('#manuscript-import-submit').click();
  await expect(dialog.locator('#manuscript-import-status')).toHaveText('A scene boundary must be at the start of a prose paragraph of the manuscript');
  expect(sent.scenes.map(scene=>scene.start)).toContain(14);
  // The preview, the author's boundary and the paragraph list stay for a fix; nothing was created.
  await expect(sceneTitles(dialog)).toHaveCount(5);
  await expect(dialog.locator('.manuscript-import-boundary[data-index="14"]')).toHaveCount(1);
  await expect(dialog.locator('#manuscript-import-submit')).toBeEnabled();
  await expect(dialog.locator('#manuscript-import-result')).toBeHidden();
});

test('a book of a series: the number goes with the import; a taken number keeps the preview',async({page,request})=>{
  const fixture=await seed(request);
  // Series titles are unique on the shared fixture server: one per project run.
  const created=await request.post('/api/series',{data:{title:`Маяки узбережжя ${test.info().project.name} ${Date.now()}`}});
  expect(created.ok(),await created.text()).toBeTruthy();
  const series=await created.json();
  await page.goto('/');
  let {dialog}=await preview(page,docxFile(fixture));
  await expect(dialog.locator('#manuscript-import-series-number')).toBeDisabled();
  await dialog.locator('#manuscript-import-series').selectOption(series.id);
  await dialog.locator('#manuscript-import-series-number').fill('1');
  await expect(dialog.locator('#manuscript-import-series-warning')).toBeHidden();  // the first book has nothing to start from
  await dialog.locator('#manuscript-import-submit').click();
  const href=await dialog.locator('#manuscript-import-build-memory').getAttribute('href');
  const storyId=href.split('/')[2].split('?')[0];
  const settings=await (await request.get(`/api/stories/${storyId}/settings`)).json();
  expect([settings.story.series_id,settings.story.series_number]).toEqual([series.id,1]);
  await dialog.locator('#manuscript-import-cancel').click();
  // The same number again: the server refuses it (400); the preview and its boundaries stay for a fix.
  ({dialog}=await preview(page,docxFile(fixture)));
  await dialog.locator('#manuscript-import-series').selectOption(series.id);
  await dialog.locator('#manuscript-import-series-number').fill('1');
  await dialog.locator('#manuscript-import-submit').click();
  await expect(dialog.locator('#manuscript-import-status')).toContainText('Номер 1 у серії вже зайнятий');
  await expect(sceneTitles(dialog)).toHaveCount(4);
  await dialog.locator('#manuscript-import-series-number').fill('2');
  // §4.2: book 1 has no memory yet, so the preview warns with a link to it before the import.
  const warning=dialog.locator('#manuscript-import-series-warning');
  await expect(warning).toBeVisible();
  await expect(warning).toContainText('Пам’ять попередньої книги серії ще не побудовано');
  await expect(warning.locator(`a[href="/stories/${storyId}"]`)).toHaveText('Маяк на пірсі');
  await dialog.locator('#manuscript-import-submit').click();
  await expect(dialog.locator('#manuscript-import-build-memory')).toBeVisible();
});

test('more than 500 scenes keep Import disabled with the reason',async({page,request})=>{
  const fixture=await seed(request);
  await page.route('**/api/manuscript-import/preview',async route=>{
    const response=await route.fetch(),data=await response.json();
    data.scenes=Array.from({length:501},(_,index)=>({start:index,end:index,title:`Сцена ${index+1}`,words:10,part_index:null,proposed:false,warnings:[]}));
    await route.fulfill({response,json:data});
  });
  await page.goto('/');
  await openDialog(page);
  const dialog=page.locator('#manuscript-import-dialog');
  await dialog.locator('#manuscript-import-file').setInputFiles(docxFile(fixture));
  await expect(sceneTitles(dialog)).toHaveCount(501);
  await expect(dialog.locator('#manuscript-import-submit')).toBeDisabled();
  await expect(dialog.locator('#manuscript-import-limit')).toBeVisible();
  await expect(dialog.locator('#manuscript-import-limit')).toHaveText('Сцен: 501, а за один імпорт можна до 500. Об’єднайте сцени або розділіть рукопис на кілька файлів.');
});

test('the client rejects a file over 20 MiB before sending',async({page})=>{
  await page.goto('/');
  const dialog=await openDialog(page);
  const sent=[];page.on('request',req=>{if(req.method()==='POST'&&req.url().endsWith('/manuscript-import/preview'))sent.push(req.url())});
  await dialog.locator('#manuscript-import-file').setInputFiles({name:'big.docx',mimeType:DOCX,buffer:Buffer.alloc(20*1024*1024+1)});
  await expect(dialog.locator('#manuscript-import-status')).toHaveText('Файл має бути до 20 MiB');
  expect(sent).toHaveLength(0);
});

test.describe('store edition',()=>{
  test.beforeEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'store'}})).json()).edition).toBe('store')});
  test.afterEach(async({request})=>{expect((await(await request.post('/test-build-edition',{data:{edition:'full'}})).json()).edition).toBe('full')});

  test('a Markdown manuscript imports without the series field',async({page,request})=>{
    const fixture=await seed(request);
    await page.goto('/');
    const {dialog}=await preview(page,mdFile(fixture));
    await expect(dialog.locator('#manuscript-import-series')).toHaveCount(0);
    await expect(dialog.locator('#manuscript-import-series-number')).toHaveCount(0);
    await expect(dialog.locator('#manuscript-import-part-markers')).toHaveCount(0);  // no parts in the store edition
    await dialog.locator('.manuscript-import-structure summary').click();
    await expect(dialog.locator('#manuscript-import-chapter-markers')).toBeVisible();
    await expect(dialog.locator('#manuscript-import-rating-sexual option[value="2"]')).toHaveJSProperty('hidden',true);
    await fitsWindow(page,dialog);
    await dialog.locator('#manuscript-import-submit').click();
    await expect(dialog.locator('#manuscript-import-build-memory')).toHaveText('Побудувати пам’ять (сцен: 4)');
  });
});
