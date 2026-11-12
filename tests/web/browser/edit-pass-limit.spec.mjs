import {test,expect} from '../../../frontend/browser-test.mjs';

// Changing the editor model happens on the settings page; coming back reloads the workspace.
test('editor pass limit survives a reload and stays per story',async({page,request})=>{
  const fixture=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${fixture.story_id}`);
  const input=page.locator('#edit-pass-limit');
  await expect(input).toHaveValue('5');
  await input.evaluate(el=>el.closest('details')?.setAttribute('open',''));
  await input.fill('3');
  await page.goto(`/stories/${fixture.story_id}/settings`);
  await page.goto(`/stories/${fixture.story_id}`);
  await expect(page.locator('#edit-pass-limit')).toHaveValue('3');
  const other=await(await request.post('/test-fixture')).json();
  await page.goto(`/stories/${other.story_id}`);
  await expect(page.locator('#edit-pass-limit')).toHaveValue('5');
});
