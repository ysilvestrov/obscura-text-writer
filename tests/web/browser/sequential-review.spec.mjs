import {test,expect} from '../../../frontend/browser-test.mjs';

test('legacy current-consistency mode is explicit in preview and restored author report',async({page,request})=>{
  await start(page,request,'&legacy=true');
  await expect(page.locator('#review-session')).toContainText(/Без історичного порівняння|No historical comparison/);
  await page.reload();
  await expect(page.locator('#review-session')).toContainText(/Поточні передумови|Current premises/);
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en');});
  await expect(page.locator('#review-session')).toContainText('No historical comparison');
  await page.locator('#review-session').getByRole('button',{name:'Dismiss all and continue'}).click();
  await expect(page.locator('#review-session')).toContainText('Review complete');
});

async function start(page,request,query=''){
  const f=await(await request.post('/test-impact?changes=true'+query)).json();
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=prose`);
  await page.locator('#impact-panel summary').click();
  await page.locator('#impact-preview').click();await expect(page.locator('#impact-start')).toBeEnabled();
  if(query.includes('legacy=true'))await expect(page.locator('#impact-targets')).toContainText(/Поточні передумови|Current premises/);
  await page.locator('#impact-start').click();
  await expect(page.locator('#review-session [data-decision]')).toHaveCount(1);
  return f;
}

test('dismiss all continues without a clean confirmation or another search',async({page,request})=>{
  const f=await start(page,request);
  await page.locator('#review-session').getByRole('button',{name:/Відхилити всі|Dismiss all/}).click();
  await expect(page.locator('#review-session')).toContainText(/Перегляд завершено|Review complete/);
  const runs=(await(await request.get(`/api/stories/${f.story_id}/runs`)).json()).runs;
  const data=await(await request.get(`/api/runs/${runs.at(-1).id}`)).json();
  expect(data.attempts.filter(a=>a.stage==='review_part')).toHaveLength(3);
});

test('memory failure preserves acceptance and reload needs an explicit retry',async({page,request})=>{
  const f=await start(page,request,'&memory_fail=true');
  await expect(page.locator('#run-status')).toContainText(/Потрібне рішення автора|Author decision required/);
  await page.evaluate(async()=>{
    const {state}=await import('/static/editor.js');
    state.workspaceRuns=state.workspaceRuns.map(run=>run.id===state.workspaceRun.id?{...run,state:'running'}:run);
    document.dispatchEvent(new CustomEvent('editor-state-changed'));
  });
  await expect(page.locator('#review-session').getByRole('button',{name:/Відхилити всі|Dismiss all/})).toBeEnabled();
  await page.locator('#review-session').getByRole('button',{name:/Відхилити всі|Dismiss all/}).click();
  await expect(page.locator('#review-session')).toContainText('Memory checkpoint unavailable');
  const runs=(await(await request.get(`/api/stories/${f.story_id}/runs`)).json()).runs;
  const url=`/api/runs/${runs.at(-1).id}`;
  const before=await(await request.get(url)).json();
  await page.reload();await expect(page.locator('#review-session')).toContainText('Memory checkpoint unavailable');
  expect((await(await request.get(url)).json()).attempts).toHaveLength(before.attempts.length);
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await page.locator('#review-session').getByRole('button',{name:/Відновити перегляд|Resume review/}).click();
  await expect(page.locator('#review-session')).toContainText(/Перегляд завершено|Review complete/);
  const after=await(await request.get(url)).json();
  expect(after.attempts.filter(a=>a.stage==='review_part')).toHaveLength(3);
  expect(after.attempts.filter(a=>a.stage==='memory')).toHaveLength(3);
});

test('author repairs survive reload and settings return with protected text',async({page,request})=>{
  const f=await start(page,request);
  await page.locator('#review-session [data-decision]').selectOption('fix');
  await page.locator('#review-session').getByRole('button',{name:/Застосувати рішення|Apply decisions/}).click();
  await expect(page.locator('#review-session')).toContainText(/Внесіть обрані|Make your selected/);
  await page.reload();await expect(page.locator('#review-session')).toContainText(/Внесіть обрані|Make your selected/);
  await page.getByRole('link',{name:/^Налаштування$|^Settings$/}).click();await page.locator('#settings-return').click();
  await expect(page.locator('#review-session')).toContainText(/Внесіть обрані|Make your selected/);
  await page.evaluate(async()=>{const i=await import('/static/i18n.js');i.setLocale('en');});
  await expect(page.locator('#review-session')).toContainText('Finish corrections');
  await page.locator('.ProseMirror').fill('Марія передала лист сестрі.');
  const finish=page.locator('#review-session').getByRole('button',{name:'Finish corrections and continue'});
  await expect(finish).toBeDisabled();
  await expect(page.locator('#review-session')).toContainText('Save your open edits first');
  await page.locator('#save-text').click();await expect(finish).toBeEnabled();
  await page.locator('#review-session').screenshot({path:`../artifacts/sequential-review/${test.info().project.name}.png`});
  await finish.click();await expect(page.locator('#review-session')).toContainText('Review complete');
  const data=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  expect(data.scene.heads.prose).not.toBe(f.prose_id);
});
