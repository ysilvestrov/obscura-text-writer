import {test,expect} from '../../../frontend/browser-test.mjs';
const activate=locator=>test.info().project.name==='mobile'?locator.tap():locator.click();

async function selectWord(editor,offset=0,end=4){
  await editor.evaluate((element,{offset,end})=>{
    element.focus();const text=document.createTreeWalker(element.querySelector('strong'),NodeFilter.SHOW_TEXT).nextNode();
    window.getSelection().setBaseAndExtent(text,offset,text,end);
    document.dispatchEvent(new Event('selectionchange'));
  },{offset,end});
}

test('fragment popover, general comment, atomic Save, reload and undo',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await expect(editor).toHaveAttribute('contenteditable','true');
  await selectWord(editor);
  await activate(page.getByRole('button',{name:/Коментувати|Comment selection/,exact:true}));
  const popup=page.locator('#author-comment-popover');
  await expect(popup).toBeVisible();
  await popup.locator('textarea').fill('Зробити опис емоційнішим.');
  await popup.getByRole('button',{name:/Зберегти коментар|Save comment/,exact:true}).click();
  await expect(editor.locator('.author-comment')).toHaveText('зорі');
  await page.locator('#author-general').fill('Скоротити вступ.');
  await page.locator('#workspace-material').screenshot({path:`../artifacts/r23-ui/${test.info().project.name}-comments.png`});
  const before=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(before.comment_set).toBeNull();
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText(/Збережено|Saved/);
  const saved=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(saved.comment_set.general).toBe('Скоротити вступ.');
  expect(saved.comment_set.comments[0].anchor.display_quote).toBe('зорі');
  await page.reload();await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(editor.locator('.author-comment')).toHaveText('зорі');
  await expect(page.locator('#author-general')).toHaveValue('Скоротити вступ.');
  await selectWord(editor,1,1);await page.keyboard.type('!');
  await expect(page.locator('#author-comments')).toContainText(/Потребує прив’язки|Needs reattachment/);
  await page.getByRole('button',{name:/Скасувати правку|Undo/,exact:true}).click();
  await expect(editor.locator('.author-comment-pending')).toHaveCount(0);
  await expect(page.locator('#save-state')).toContainText(/Збережена версія|Saved version/);
  await page.getByRole('button',{name:/Повторити правку|Redo/,exact:true}).click();
  await expect(page.locator('#author-comments')).toContainText(/Потребує прив’язки|Needs reattachment/);
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toContainText(/Збережено|Saved/);
  const pending=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(pending.comment_set.comments[0].anchor.state).toBe('needs_review');
  expect(pending.comment_set.comments[0].anchor.origin.version_id).toBe(saved.source_version_id);
});

test('highlight reopens editable popover; overlapping ranges are blocked',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await expect(editor).toHaveAttribute('contenteditable','true');
  await selectWord(editor);
  const comment=page.getByRole('button',{name:/Коментувати|Comment selection/,exact:true});
  await activate(comment);
  const popup=page.locator('#author-comment-popover');
  await popup.locator('textarea').fill('Перша вказівка.');
  await popup.getByRole('button',{name:/Зберегти коментар|Save comment/,exact:true}).click();
  await selectWord(editor,1,3);
  await expect(comment).toBeDisabled();
  await activate(editor.locator('.author-comment'));
  await expect(popup).toBeVisible();
  await page.screenshot({path:`../artifacts/r23-ui/${test.info().project.name}-popover.png`});
  await expect(popup.locator('textarea')).toHaveValue('Перша вказівка.');
  await popup.locator('textarea').fill('Уточнена вказівка.');
  await page.keyboard.press('Escape');
  await expect(popup).toBeHidden();
  await activate(editor.locator('.author-comment'));
  await expect(popup).toBeVisible();
  await expect(popup.locator('textarea')).toHaveValue('Перша вказівка.');
  await popup.getByRole('button',{name:/Видалити коментар|Delete comment/,exact:true}).click();
  await expect(editor.locator('.author-comment')).toHaveCount(0);
});

test('unsaved origin proof, reattachment and locale preserve author input',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const editor=page.locator('.rich-text-surface .ProseMirror');
  await expect(editor).toHaveAttribute('contenteditable','true');
  await editor.click();await page.keyboard.press('Control+Home');await page.keyboard.type('X');
  await selectWord(editor);
  await activate(page.getByRole('button',{name:/Коментувати|Comment selection/,exact:true}));
  const popup=page.locator('#author-comment-popover');
  await popup.locator('textarea').fill('Не втратити цю вказівку.');
  await activate(page.locator('[data-ui-locale="uk"]'));
  await expect(popup).toBeVisible();
  await expect(popup.locator('textarea')).toHaveValue('Не втратити цю вказівку.');
  await popup.getByRole('button',{name:'Зберегти коментар',exact:true}).click();
  await selectWord(editor,1,1);await page.keyboard.type('!');
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toHaveText('Збережено');
  const pending=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(pending.comment_set.comments[0].anchor.origin.version_id).toBeNull();
  expect(pending.comment_set.comments[0].anchor.origin.relative_path).toContain('/c/');
  await page.reload();await page.locator('#mode-tabs [data-mode="draft"]').click();
  await expect(editor).toHaveAttribute('contenteditable','true');
  await selectWord(editor,0,5);
  await page.getByRole('button',{name:'Прив’язати до виділення',exact:true}).click();
  await page.locator('#save-text').click();
  await expect(page.locator('#save-state')).toHaveText('Збережено');
  const fixed=await(await request.get(`/api/scenes/${fixture.scene_id}/comments`)).json();
  expect(fixed.source_version_id).toBe(pending.source_version_id);
  expect(fixed.comment_set.comments[0].anchor.state).toBe('valid');
  expect(fixed.comment_set.comments[0].anchor.source_quote).toBe('з!орі');
});

test('notes conflict preserves working input and unlocks the editor',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const general=page.locator('#author-general');await expect(general).toBeEnabled();
  await general.fill('Моя незбережена вказівка.');
  const versions=await(await request.get(`/api/scenes/${fixture.scene_id}/versions`)).json();
  const ref=await(await request.get(`/api/versions/${versions.scene.heads.draft}`)).json();
  const other=await request.post(`/api/scenes/${fixture.scene_id}/draft`,{data:{
    text:ref.text,content_format:ref.version.content_format,expected_revision:versions.scene.revision,
    expected_source_version_id:ref.version.id,expected_comments_revision:0,comment_set:{general:'Інша вкладка.',comments:[]}
  }});
  expect(other.ok()).toBeTruthy();
  await page.locator('#save-text').click();
  await expect(page.locator('#notice')).toContainText(/Коментарі змінено|Comments changed/);
  await expect(general).toHaveValue('Моя незбережена вказівка.');
  await expect(general).toBeEnabled();
  await expect(page.locator('.ProseMirror')).toHaveAttribute('contenteditable','true');
});
