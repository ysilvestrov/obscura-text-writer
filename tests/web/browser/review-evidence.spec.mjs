import {test,expect} from '../../../frontend/browser-test.mjs';

test('evidence review shows exact quotes, author priority and locale after reload',async({page,request})=>{
  const f=await(await request.post('/test-impact?changes=true&evidence=true')).json();
  await page.goto(`/stories/${f.story_id}/revision`);
  await page.locator('#review-contract-version').selectOption('4');
  await page.locator('#impact-preview').click();await expect(page.locator('#impact-start')).toBeEnabled();
  await page.locator('#impact-start').click();
  const panel=page.locator('#review-session');
  await expect(panel).toContainText(/Конфлікт передумов|Premise conflict/);
  await expect(panel.locator('[data-priority-choice]')).toHaveCount(2);
  await page.reload();
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en');});
  await expect(panel).toContainText('Premise conflict');
  await expect(panel.locator('blockquote')).toHaveCount(2);
  await panel.screenshot({path:`../artifacts/review-evidence/${test.info().project.name}.png`});
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await panel.locator('[data-priority-choice]').first().click();
  await expect(panel).toContainText('Author priorities changed');
  const policies=await(await request.get(`/api/stories/${f.story_id}/review/priorities/${f.scene_id}`)).json();
  expect(policies.authority_revisions.prose).toBe(1);
  expect(policies.priorities).toHaveLength(1);
});
