import {test,expect} from '../../../frontend/browser-test.mjs';

// #89 R20-WORKSPACE: run controls, the scene status and the next-run limit sit in the status row above the editor.
test('status row holds run controls and the next-run limit',async({page,request})=>{
  const fixture=await(await request.post('/test-editor-no-changes')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=draft`);
  const row=page.locator('.workspace-sticky #workspace-status-row');
  await expect(row.locator('#workspace-scene-status')).not.toBeEmpty();
  // Which run actions are visible for which run state is unchanged (runs.js / run-readiness.js); here only their place.
  await expect(row.locator('#run-actions button',{hasText:/^(Скасувати|Cancel)$/})).toHaveCount(1);
  await expect(row.locator('#run-actions .run-action')).toHaveCount(5); // pause, cancel, continue after acceptance, resume, repeat
  await expect(page.locator('.context-panel #run-actions')).toHaveCount(0);
  await row.locator('#run-options summary').click();
  await expect(row.locator('#run-options #run-budget')).toBeVisible();
  await expect(page.locator('.context-panel .budget-panel')).toHaveCount(0);
});
