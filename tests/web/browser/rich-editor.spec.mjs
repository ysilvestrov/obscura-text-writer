import {test, expect} from '../../../frontend/browser-test.mjs';

test('draft/prose visual editing, exact no-op, undo and locale without losing work', async ({page, request}) => {
  const fixture = await (await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const editor = page.locator('.rich-text-surface .ProseMirror');
  await expect(editor.locator('strong')).toHaveText('зорі');
  await expect(editor.locator('em')).toHaveText('тихим');
  await expect(page.locator('#scene-statistics')).toContainText(/Markdown (?:source: \d+ characters|джерело: \d+ символів)/);
  await page.screenshot({path: `../artifacts/r22-ui/${test.info().project.name}.png`, fullPage: true});
  const before = await (await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText(/Збережено|Saved/);
  const after = await (await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  expect(after.scene.heads.draft).toBe(before.scene.heads.draft);
  await editor.click();
  await page.keyboard.press('Control+End');
  await page.getByRole('button', {name: /Жирний|Bold/, exact: true}).click();
  await page.keyboard.type(' Нове');
  await expect(editor.locator('strong').last()).toHaveText('Нове');
  await page.getByRole('button', {name: /Скасувати правку|Undo/, exact: true}).click();
  await expect(editor).not.toContainText('Нове');
  await page.getByRole('button', {name: /Повторити правку|Redo/, exact: true}).click();
  await expect(editor).toContainText('Нове');
  const text = await editor.textContent();
  await editor.evaluate(element => {
    const text = element.querySelector('strong').firstChild;
    const selection = window.getSelection();selection.setBaseAndExtent(text, 0, text, 2);
  });
  const selectionBefore = await editor.evaluate(() => window.getSelection().toString());
  // The switch only changes product labels, not the editor or the undo stack.
  await page.locator('[data-ui-locale="en"]').click();
  await expect(editor).toHaveText(text);
  expect(await editor.evaluate(() => window.getSelection().toString())).toBe(selectionBefore);
  await expect(page.locator('#save-state')).toContainText('Unsaved');
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText('Saved');
  const savedScene = await (await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  const saved = await (await request.get(`/api/versions/${savedScene.scene.heads.draft}`)).json();
  expect(saved.version.content_format).toBe('markdown');
  expect(saved.text).toMatch(/\*\*(?:&#x20;)?Нове\*\*/);
  // Saving marks a baseline without discarding the undo history.
  await page.getByRole('button', {name: 'Undo', exact: true}).click();
  await expect(editor).not.toContainText('Нове');
  page.once('dialog', dialog => dialog.accept());
  await page.locator('#mode-tabs [data-mode="plan"]').click();
  await expect(page.locator('#editor')).toBeVisible();
  await expect(page.locator('.rich-text-surface')).toBeHidden();
});

test('legacy plain, safe paste, singleton and read-only history', async ({page, request}) => {
  const fixture = await (await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  const editor = page.locator('.rich-text-surface .ProseMirror');
  await expect(editor).toHaveText('Літеральні *зірочки* та &amp;.');
  await expect(editor.locator('em')).toHaveCount(0);
  await editor.click();await page.keyboard.press('Control+End');
  await editor.evaluate(element => {
    const transfer = new DataTransfer();
    transfer.setData('text/plain', ' <img src="https://example.org/private.png">');
    transfer.setData('text/html', '<img src="https://example.org/private.png" onerror="alert(1)">');
    element.dispatchEvent(new ClipboardEvent('paste', {clipboardData: transfer, bubbles: true, cancelable: true}));
  });
  await expect(editor.locator('img')).toHaveCount(0);
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText(/Збережено|Saved/);
  await page.reload();
  await page.locator('#mode-tabs [data-mode="prose"]').click();
  await expect(editor).toContainText('Літеральні *зірочки* та &amp;.');
  await expect(editor.locator('em,img')).toHaveCount(0);
  await expect(page.locator('.rich-text-surface')).toHaveCount(1);
  await page.locator('#workspace-history summary').click();
  const refs = await (await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  await page.locator('#history-version').selectOption(refs.scene.heads.prose);
  await page.getByRole('button', {name: /Переглянути версію|View version/, exact: true}).click();
  await expect(editor).toHaveAttribute('contenteditable', 'false');
  const old = await editor.textContent();
  await editor.click();await page.keyboard.press('Control+b');await page.keyboard.press('Control+z');
  await expect(editor).toHaveText(old);
  await expect(page.getByRole('button', {name: /Жирний|Bold/, exact: true})).toBeDisabled();
});

test('plain multiline paste preserves paragraphs and can be saved',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await editor.click();await page.keyboard.press('Control+a');
  await editor.evaluate(element=>{
    const transfer=new DataTransfer();transfer.setData('text/plain','Один.\n\nДва.');
    element.dispatchEvent(new ClipboardEvent('paste',{clipboardData:transfer,bubbles:true,cancelable:true}));
  });
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText(/Збережено|Saved/);
  await expect(editor.locator('p')).toHaveCount(2);
});


test('long draft scrolls internally while formatting toolbar stays in place',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  const versions=await(await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  const text=Array.from({length:100},(_,i)=>`Абзац ${i+1}. `+'Нейтральний опис ранкової прогулянки парком. '.repeat(5)).join('\n\n');
  const saved=await request.post(`/api/scenes/${fixture.scene_id}/draft`,{data:{text,content_format:'markdown',expected_revision:versions.scene.revision}});
  expect(saved.ok()).toBeTruthy();
  await page.goto(`/stories/${fixture.story_id}`);await page.locator('#mode-tabs [data-mode="draft"]').click();
  const surface=page.locator('.rich-text-surface'),editor=surface.locator('.ProseMirror'),toolbar=surface.locator('.rich-text-toolbar');
  await expect(editor).toHaveAttribute('contenteditable','true');
  const size=await editor.evaluate(el=>({client:el.clientHeight,scroll:el.scrollHeight,viewport:innerHeight}));
  expect(size.client).toBeLessThan(size.viewport*.65);expect(size.scroll).toBeGreaterThan(size.client*2);
  await surface.scrollIntoViewIfNeeded();
  const before=await toolbar.boundingBox();const pageScroll=await page.evaluate(()=>scrollY);
  await editor.evaluate(el=>{el.scrollTop=el.scrollHeight;});
  expect(await editor.evaluate(el=>el.scrollTop)).toBeGreaterThan(0);
  expect((await toolbar.boundingBox()).y).toBeCloseTo(before.y,0);
  expect(await page.evaluate(()=>scrollY)).toBe(pageScroll);
  await expect(toolbar.getByRole('button',{name:/Жирний|Bold/,exact:true})).toBeInViewport();
});
