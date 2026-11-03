import {test,expect} from '../../../frontend/browser-test.mjs';

test('successful editor without corrections opens automatically saved prose',async({page,request})=>{
  const f=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${f.story_id}`);
  await page.locator('#mode-tabs [data-mode="draft"]').click();
  const before=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  page.on('dialog',dialog=>dialog.accept());
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.locator('#workspace-primary').click();
  await expect(page.locator('#mode-tabs [data-mode="prose"]')).toHaveAttribute('aria-selected','true');
  await expect(page.locator('.ProseMirror')).toContainText('Лєра побачила зорі.');
  const after=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  expect(after.scene.heads.draft).toBe(before.scene.heads.draft);
  expect(after.scene.heads.prose).not.toBe(before.scene.heads.prose);
  const version=after.versions.find(v=>v.id===after.scene.heads.prose);
  expect(version.content_format).toBe('markdown');
});
