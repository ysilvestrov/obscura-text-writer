import {test,expect} from '../../../frontend/browser-test.mjs';

// EDITOR-IMPORT in the browser: the story menu opens the import dialog; the summary lists the scenes with human statuses,
// the choice for a scene changed after the export, the result with scene links and the proposal mark in the review panel.
// Neutral example: three short scenes about a pier lighthouse.
test.use({locale:'uk-UA'});
const SCENE_TITLES=['Ранок','Хвилі','Вечір'];
const DOCX='application/vnd.openxmlformats-officedocument.wordprocessingml.document';

async function seed(request){return (await request.post('/test-editor-import')).json()}
const file=fixture=>({name:'edition.docx',mimeType:DOCX,buffer:Buffer.from(fixture.docx_base64,'base64')});

async function openWorkspace(page,fixture,scene=fixture.scene_ids[0],material='plan'){
  await page.goto(`/stories/${fixture.story_id}?scene=${scene}&material=${material}`);
  // The template's placeholder is already non-empty: wait for the seeded scene title.
  await expect(page.locator('#scene-title')).toHaveText(SCENE_TITLES[fixture.scene_ids.indexOf(scene)]);
}
async function openDialog(page){
  await page.locator('#story-menu-toggle').click();
  const item=page.locator('#import-edition');
  await expect(item).toBeEnabled();
  await item.click();
  const dialog=page.locator('#editor-import-dialog');
  await expect(dialog).toBeVisible();
  return dialog;
}
async function summary(page,fixture){
  const dialog=await openDialog(page);
  await dialog.locator('#editor-import-file').setInputFiles(file(fixture));
  await expect(dialog.locator('#editor-import-summary tbody tr')).toHaveCount(3);
  return dialog;
}

test('the summary, the choice and the result lead to the proposal of scene 1',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  await expect(page.locator('#import-edition')).toHaveText('Імпорт редакції (DOCX)…');
  const dialog=await summary(page,fixture);
  await expect(dialog.locator('#editor-import-title')).toHaveText('Імпорт редакції (DOCX)');
  await expect(dialog.locator('#editor-import-summary tbody .editor-import-status')).toHaveText(['змінено','лише примітки','прозу змінено після експорту']);
  await expect(dialog.locator('#editor-import-summary tbody tr').nth(2)).toContainText('Прозу сцени змінено після експорту.');
  await expect(dialog.locator('#editor-import-choice')).toContainText('Вечір');
  for(const [id,name] of [['abort','Скасувати імпорт'],['skip','Пропустити змінені сцени'],['replace','Замінити все']]){
    await expect(dialog.locator('#editor-import-'+id)).toBeVisible();await expect(dialog.locator('#editor-import-'+id)).toHaveText(name);
  }
  await expect(dialog).toContainText('Ваші пізніші зміни з’являться як правки, які можна відхилити');
  await expect(dialog.locator('#editor-import-submit')).toBeHidden();
  // Review Focus 4: the summary stays inside a phone screen; the choice buttons are reachable.
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
  const width=await page.evaluate(()=>innerWidth),box=await dialog.boundingBox();
  expect(box.x).toBeGreaterThanOrEqual(0);expect(box.x+box.width).toBeLessThanOrEqual(width);
  for(const id of ['abort','skip','replace']){
    const button=dialog.locator('#editor-import-'+id);await button.scrollIntoViewIfNeeded();
    const rect=await button.boundingBox();expect(rect.x).toBeGreaterThanOrEqual(0);expect(rect.x+rect.width).toBeLessThanOrEqual(width);
  }

  await dialog.locator('#editor-import-skip').click();
  const result=dialog.locator('#editor-import-result');
  await expect(result).toContainText('Імпортовано сцен: 2 · пропущено: 1');
  const [first,second,third]=fixture.scene_ids;
  const link=result.locator(`a[href="/stories/${fixture.story_id}?scene=${first}&material=review"]`);
  await expect(link).toHaveText('Ранок');
  await expect(result.locator(`a[href="/stories/${fixture.story_id}?scene=${second}&material=draft"]`)).toHaveText('Хвилі');
  await expect(result.locator(`a[href="/stories/${fixture.story_id}?scene=${third}&material=draft"]`)).toHaveText('Вечір');
  await expect(dialog.locator('#editor-import-cancel')).toHaveText('Закрити');

  // Scene 1 is the open scene: the link still reloads its review panel.
  await link.click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#mode-tabs [data-mode="review"]')).toHaveAttribute('aria-selected','true');
  const panel=page.locator('.copyedit-review').filter({has:page.locator('summary',{hasText:'Правки редактора'})});
  // workspace-route.js already opens the panel in review mode; a click would close it.
  if(!await panel.evaluate(node=>node.open))await panel.locator('summary').click();
  await expect(panel.locator('select option')).toHaveCount(1);
  await expect(panel.locator('select option').first()).toContainText(' · від редактора (DOCX)');
  await expect(panel.locator('[data-editor-import-note]')).toBeVisible();

  // Review Focus 5: reopening after an import shows the empty file choice.
  const again=await openDialog(page);
  await expect(again.locator('#editor-import-summary')).toBeHidden();
  await expect(again.locator('#editor-import-result')).toBeHidden();
  await expect(again.locator('#editor-import-file')).toBeVisible();
  expect(await again.locator('#editor-import-file').evaluate(input=>input.value)).toBe('');
});

test('an unsaved edit makes the menu item unavailable with a visible reason',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture,fixture.scene_ids[0],'prose');
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await editor.click();await page.keyboard.press('End');await page.keyboard.type(' Нова думка');
  await page.locator('#story-menu-toggle').click();
  const item=page.locator('#import-edition');
  await expect(item).toBeDisabled();
  await expect(item).toHaveAttribute('title','Спершу збережіть ручні правки');
  await expect(page.locator('#import-edition-reason')).toBeVisible();
  await expect(page.locator('#import-edition-reason')).toHaveText('Спершу збережіть ручні правки');
  await expect(page.locator('#editor-import-dialog')).toBeHidden();
  await expect(editor).toContainText('Нова думка');
});

test('cancel after the summary deletes the kept file and reopening shows the empty state',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await summary(page,fixture);
  const deleted=page.waitForRequest(req=>req.method()==='DELETE'&&/\/editor-import\/[0-9a-f]{32}$/.test(req.url()));
  await dialog.locator('#editor-import-abort').click();
  await deleted;
  await expect(dialog).toBeHidden();
  const again=await openDialog(page);
  await expect(again.locator('#editor-import-summary')).toBeHidden();
  await expect(again.locator('#editor-import-choice')).toBeHidden();
  await expect(again.locator('#editor-import-status')).toHaveText('');
  expect(await again.locator('#editor-import-file').evaluate(input=>input.value)).toBe('');
});

test('a story changed after the summary shows the reason and offers the file choice again',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture,fixture.scene_ids[1]);
  const dialog=await summary(page,fixture);
  await request.post(`/test-editor-import-touch/${fixture.scene_ids[0]}`);
  const deleted=page.waitForRequest(req=>req.method()==='DELETE');
  await dialog.locator('#editor-import-replace').click();
  await expect(dialog.locator('#editor-import-status')).toContainText('Твір змінився після зведення; перегляньте його ще раз');
  await expect(dialog.locator('#editor-import-status')).toContainText('Виберіть файл ще раз');
  await deleted;
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('#editor-import-summary')).toBeHidden();
  await expect(dialog.locator('#editor-import-file')).toBeVisible();
  await expect(dialog.locator('#editor-import-file')).toBeFocused();
  // The file can be chosen again: a new summary of the current story.
  await dialog.locator('#editor-import-file').setInputFiles(file(fixture));
  await expect(dialog.locator('#editor-import-summary tbody tr')).toHaveCount(3);
});

test('the English interface shows English statuses and warnings',async({page,request})=>{
  const fixture=await seed(request);
  await openWorkspace(page,fixture);
  const dialog=await summary(page,fixture);
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en')});
  await expect(dialog.locator('#editor-import-title')).toHaveText("Import editor's revision (DOCX)");
  await expect(dialog.locator('#editor-import-summary tbody .editor-import-status')).toHaveText(['changed','comments only','prose changed after export']);
  await expect(dialog.locator('#editor-import-summary tbody tr').nth(2)).toContainText('The scene prose was changed after the export.');
  await expect(dialog.locator('#editor-import-skip')).toHaveText('Skip changed scenes');
  // Review Focus 3: nothing Ukrainian is left except the scene titles of the story itself.
  expect((await dialog.innerText()).replace(/Ранок|Хвилі|Вечір/g,'')).not.toMatch(/[А-Яа-яІіЇїЄєҐґ]/);
  await dialog.locator('#editor-import-skip').click();
  await expect(dialog.locator('#editor-import-result')).toContainText('Imported scenes: 2 · skipped: 1');
  await expect(dialog.locator('#editor-import-result')).toContainText("Edits are on the scene's Editing tab");
  // A link to another scene selects it and opens its draft (the comments-only scene has no proposal).
  await dialog.locator('#editor-import-result a',{hasText:'Хвилі'}).click();
  await expect(dialog).toBeHidden();
  await expect(page.locator('#scene-title')).toContainText('Хвилі');
  await expect(page.locator('#mode-tabs [data-mode="draft"]')).toHaveAttribute('aria-selected','true');
});
