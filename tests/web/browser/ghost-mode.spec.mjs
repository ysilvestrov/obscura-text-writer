import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

async function openDraft(page,storyId){
  await page.goto(`/stories/${storyId}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#ghost-entry')).toBeVisible();
}

const mode=page=>page.locator('#ghost-mode');
const ai=page=>mode(page).locator('.ghost-ai');
const author=page=>mode(page).locator('.ghost-author .ghost-editor:not([hidden]) .ProseMirror');

async function head(request,sceneId){
  const data=await(await request.get(`/api/scenes/${sceneId}/versions`)).json();
  return data.versions.find(v=>v.id===data.scene.heads.draft);
}

test('reading, writing and Tab peek; save creates an author draft',async({page,request})=>{
  const f=await(await request.post('/test-ghost-mode')).json();
  await openDraft(page,f.story_id);
  await page.locator('#ghost-entry .ghost-start').click();
  await expect(mode(page)).toBeVisible();
  await expect(mode(page).locator('.ghost-progress')).toContainText('Блок 1 з 3');
  await expect(ai(page)).toContainText('Над морем повільно сідало сонце');
  // Tab before typing does nothing: the AI block is already visible and nothing is counted.
  await author(page).click();
  await page.keyboard.press('Tab');
  await expect(ai(page)).toBeVisible();
  await expect(author(page)).toBeFocused();
  await page.keyboard.type('Сонце сідало');
  await expect(ai(page)).toBeHidden();
  await page.keyboard.press('Control+A');await page.keyboard.press('Backspace');
  await expect(ai(page)).toBeHidden();
  await page.keyboard.type('Сонце сідало над морем, маяк засвітився.');
  // Hold Tab: the AI block shows, the author's text hides, typing changes nothing.
  await page.keyboard.down('Tab');
  await expect(ai(page)).toBeVisible();
  await expect(mode(page).locator('.ghost-author')).toBeHidden();
  await page.keyboard.type('зайве');
  await page.keyboard.up('Tab');
  await expect(ai(page)).toBeHidden();
  await expect(author(page)).toHaveText('Сонце сідало над морем, маяк засвітився.');
  await expect(author(page)).toBeFocused();
  await page.keyboard.press('Control+Enter');
  await expect(mode(page).locator('.ghost-separator')).toBeVisible();
  await mode(page).getByRole('button',{name:'Далі'}).click();
  await author(page).click();
  await page.keyboard.type('Вона піднялася нагору й подивилася на затоку.');
  await mode(page).evaluate(node=>node.scrollTo(0,0));
  await page.keyboard.down('Tab');
  await mode(page).screenshot({path:`../docs/images/ghost-mode-${test.info().project.name}.png`});
  await page.keyboard.up('Tab');
  await mode(page).getByRole('button',{name:'Зберегти як чернетку'}).click();
  await expect(mode(page)).toBeHidden();
  await expect(page.locator('#notice')).toContainText('блоків 2 з 2');
  const saved=await head(request,f.scene_id);
  expect(saved.id).not.toBe(f.draft_id);
  expect(saved.author_lineage.parent_version_id).toBe(f.draft_id);
  expect(saved.content_format).toBe('markdown');
  expect(saved.ghost_rewrite).toMatchObject({blocks:2,blocks_written:2,blocks_skipped:0,peeks:2,pastes_blocked:0});
  const text=(await(await request.get(`/api/versions/${saved.id}`)).json()).text;
  expect(text).toBe('Сонце сідало над морем, маяк засвітився.\n\n***\n\nВона піднялася нагору й подивилася на затоку.');
  await expect(page.locator('#ghost-entry .ghost-entry-stats')).toContainText('Переписано по пам’яті');
});

test('peek button, blocked paste and copy, explicit skip',async({page,request})=>{
  const f=await(await request.post('/test-ghost-mode')).json();
  await openDraft(page,f.story_id);
  await page.locator('#ghost-entry .ghost-start').click();
  const peek=mode(page).locator('.ghost-peek');
  await expect(peek).toBeDisabled();
  await author(page).click();
  await page.keyboard.type('Вечір.');
  // Pasting and dropping are blocked and counted.
  await author(page).evaluate(node=>{const data=new DataTransfer();data.setData('text/plain','вставлений текст');node.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));});
  await expect(author(page)).toHaveText('Вечір.');
  await expect(page.locator('#notice')).toHaveAttribute('data-kind','error');
  // The peek button works while held.
  const box=await peek.boundingBox();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
  await page.mouse.down();
  await expect(ai(page)).toBeVisible();
  await expect(peek).toHaveAttribute('aria-pressed','true');
  const copied=await ai(page).locator('.ProseMirror').evaluate(node=>{const event=new ClipboardEvent('copy',{bubbles:true,cancelable:true});node.dispatchEvent(event);return event.defaultPrevented;});
  expect(copied).toBe(true);
  await page.mouse.up();
  await expect(ai(page)).toBeHidden();
  await mode(page).getByRole('button',{name:'Далі'}).click();
  await mode(page).getByRole('button',{name:'Далі'}).click();
  const save=mode(page).getByRole('button',{name:'Зберегти як чернетку'});
  await expect(save).toBeDisabled();
  await mode(page).getByRole('button',{name:'Пропустити блок'}).click();
  await expect(mode(page).locator('.ghost-skipped')).toBeVisible();
  await expect(save).toBeEnabled();
  await save.click();
  const dialog=page.locator('.app-dialog');
  await expect(dialog).toContainText('Пропущено блоків: 1');
  await dialog.locator('.app-dialog-actions button').last().click();
  await expect(mode(page)).toBeHidden();
  const saved=await head(request,f.scene_id);
  expect(saved.ghost_rewrite).toMatchObject({blocks:2,blocks_written:1,blocks_skipped:1,peeks:1,pastes_blocked:1});
  expect((await(await request.get(`/api/versions/${saved.id}`)).json()).text).toBe('Вечір.\n\n***');
});

test('an unsaved rewrite survives a reload and cancel discards it',async({page,request})=>{
  const f=await(await request.post('/test-ghost-mode')).json();
  await openDraft(page,f.story_id);
  await page.locator('#ghost-entry .ghost-start').click();
  await author(page).click();
  await page.keyboard.type('Збережений у браузері текст.');
  await page.keyboard.press('Control+Enter');
  page.once('dialog',dialog=>dialog.accept());
  await page.reload();
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(page.locator('#ghost-entry .ghost-start')).toHaveText('Продовжити переписування');
  await page.locator('#ghost-entry .ghost-start').click();
  await expect(mode(page).locator('.ghost-progress')).toContainText('Блок 2 з 3');
  await mode(page).getByRole('button',{name:'Назад'}).click();
  await expect(author(page)).toHaveText('Збережений у браузері текст.');
  await expect(ai(page)).toBeHidden();
  await mode(page).getByRole('button',{name:'Скасувати переписування'}).click();
  const confirm=page.locator('.app-dialog');
  await expect(confirm).toContainText('Вийти з переписування? Написаний текст буде видалено.');
  await confirm.getByRole('button',{name:'Продовжити писати'}).click();
  await expect(author(page)).toHaveText('Збережений у браузері текст.');
  await mode(page).getByRole('button',{name:'Скасувати переписування'}).click();
  await confirm.getByRole('button',{name:'Видалити написане'}).click();
  await expect(mode(page)).toBeHidden();
  await expect(page.locator('#ghost-entry .ghost-start')).toHaveText('Переписати по пам’яті');
  expect((await head(request,f.scene_id)).id).toBe(f.draft_id);
});

const onTop=locator=>locator.evaluate(node=>{const box=node.getBoundingClientRect();const hit=document.elementFromPoint(box.left+box.width/2,box.top+box.height/2);return node.contains(hit);});

test('plain draft with formatting saves Markdown; notices stay above the mode',async({page,request})=>{
  const f=await(await request.post('/test-ghost-mode?format=plain')).json();
  await openDraft(page,f.story_id);
  await page.locator('#ghost-entry .ghost-start').click();
  await author(page).click();
  await page.keyboard.type('Маяк ');
  await page.keyboard.press('Control+B');await page.keyboard.type('світив');await page.keyboard.press('Control+B');
  await author(page).evaluate(node=>{const data=new DataTransfer();data.setData('text/plain','x');node.dispatchEvent(new ClipboardEvent('paste',{clipboardData:data,bubbles:true,cancelable:true}));});
  await expect(page.locator('#notice')).toContainText('Вставка тексту');
  expect(await onTop(page.locator('#notice'))).toBe(true);
  // Space held on the Peek button peeks and releasing it returns to writing.
  await mode(page).locator('.ghost-peek').focus();
  await page.keyboard.down(' ');
  await expect(ai(page)).toBeVisible();
  await page.keyboard.up(' ');
  await expect(ai(page)).toBeHidden();
  await expect(mode(page).locator('.ghost-author')).toBeVisible();
  await mode(page).getByRole('button',{name:'Далі'}).click();
  await mode(page).getByRole('button',{name:'Далі'}).click();
  await mode(page).getByRole('button',{name:'Пропустити блок'}).click();
  await mode(page).getByRole('button',{name:'Зберегти як чернетку'}).click();
  await page.locator('.app-dialog .app-dialog-actions button').last().click();
  await expect(mode(page)).toBeHidden();
  const saved=await head(request,f.scene_id);
  expect(saved.content_format).toBe('markdown');
  expect((await(await request.get(`/api/versions/${saved.id}`)).json()).text).toContain('**світив**');
});

test('a corrupted saved session never leaves the mode stuck',async({page,request})=>{
  const f=await(await request.post('/test-ghost-mode')).json();
  await page.goto(`/stories/${f.story_id}`);
  await page.evaluate(([scene,draft])=>localStorage.setItem(`ghost:${scene}:${draft}`,JSON.stringify({version:1,sceneId:scene,draftId:draft,format:'markdown',index:99,peeks:0,peekMs:0,pastesBlocked:0,blocks:[{kind:'text',source:'x',state:'writing',touched:true,text:'y',format:'markdown'}]})),[f.scene_id,f.draft_id]);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  await page.locator('#ghost-entry .ghost-start').click();
  await expect(mode(page)).toBeVisible();
  await expect(mode(page).locator('.ghost-progress')).toContainText('Блок 1 з 3','the broken session is ignored and a fresh one starts');
  await mode(page).getByRole('button',{name:'Скасувати переписування'}).click();
  await expect(mode(page)).toBeHidden();
});
