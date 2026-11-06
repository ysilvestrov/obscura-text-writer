import {test,expect} from '../../../frontend/browser-test.mjs';

test('draft displays editor and planned calls before starting',async({page,request},testInfo)=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const telemetry=page.locator('#workspace-telemetry');
  await expect(telemetry).toContainText('synthetic-no-changes');
  await expect(telemetry).toContainText('5');
  await expect(telemetry).not.toContainText('⚠');
  await page.locator('#workspace-primary').focus();
  await expect(page.locator('#workspace-telemetry-details')).toBeVisible();
  await page.screenshot({path:testInfo.outputPath('telemetry.png')});
  await page.locator('[data-mode="memory"]').click();
  await expect(telemetry).toBeHidden();
});

test('sidebar retains the planned model after reload',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.locator('#workspace-primary').click();
  await expect(page.locator('#run-status')).toContainText('synthetic-no-changes');
  await page.reload();
  await expect(page.locator('#run-status')).toContainText('synthetic-no-changes');
});

test('keyboard can open telemetry when the primary action is disabled',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  await expect(page.locator('#workspace-telemetry')).toContainText('synthetic-no-changes');
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.evaluate(()=>{document.querySelector('#workspace-primary').disabled=true});
  await page.locator('#workspace-telemetry').focus();
  await expect(page.locator('#workspace-telemetry-details')).toBeVisible();
});
