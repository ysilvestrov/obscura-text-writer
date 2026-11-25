import {test,expect} from '../../../frontend/browser-test.mjs';
test.use({locale:'uk-UA'});

// EDIT-SENTENCE-GROUPS-S04: one sentence with two separate edits; the author keeps the name and takes the wording.
const ORIGINAL='Boris скинув важкий робочий жилет на стілець та розстібнув комір комбінезона, що з тихим шелестом відійшов від шкіри.';
const PARTIAL='Boris скинув важкий робочий жилет на стілець і розстебнув комір комбінезона; тканина з тихим шелестом відійшла від шкіри.';

async function openReview(page,f){
  await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=review`);
  const panel=page.locator('.copyedit-review').filter({has:page.locator('summary',{hasText:'Правки редактора'})});
  await expect(panel.locator('select option')).toHaveCount(1);
  if(!await panel.evaluate(e=>e.open))await panel.locator('summary').click();
  return panel;
}

test('split a sentence, accept one part, restore the split from the decision',async({page,request})=>{
  const f=await(await request.post('/test-edit-split')).json();
  const panel=await openReview(page,f);
  const item=panel.locator('.copyedit-item');
  await expect(item).toHaveCount(1);
  const splitButton=panel.getByRole('button',{name:'Прийняти окремо (2)',exact:true});
  await expect(splitButton).toBeVisible();
  // The button sits inside the item's label: clicking it must not toggle the group checkbox.
  const checkedBefore=await item.locator('input[type=checkbox]').isChecked();
  await splitButton.click();

  const block=panel.locator('.copyedit-split');
  await expect(block).toHaveCount(1);
  await expect(block.locator('.copyedit-item')).toHaveCount(2);
  await expect(block.locator('.copyedit-item').nth(0).locator('del')).toHaveText('Boris');
  await expect(block.locator('.copyedit-item').nth(0).locator('ins')).toHaveText('Борис');
  await expect(block.locator('.copyedit-item').nth(1).locator('del')).toHaveCount(1);
  await expect(block.locator('.copyedit-item').nth(1)).not.toContainText('Борис');
  const boxes=block.locator('input[type=checkbox]');
  for(const index of [0,1])expect(await boxes.nth(index).isChecked()).toBe(checkedBefore);
  await panel.screenshot({path:`../artifacts/edit-split/${test.info().project.name}-split.png`});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();

  await boxes.nth(0).uncheck();await boxes.nth(1).check();
  const result=block.locator('[data-split-result]');
  await expect(result).toHaveText('Вийде так: '+PARTIAL);
  await boxes.nth(0).check();
  await expect(result).toContainText('Вийде так: Борис');
  await boxes.nth(0).uncheck();
  await expect(result).toHaveText('Вийде так: '+PARTIAL);

  // «Вийде так» matches the assembled preview the server returns for the same choice.
  const previewRequest=page.waitForRequest(r=>r.url().endsWith('/selection-preview'));
  await panel.getByRole('button',{name:'Переглянути виправлений текст',exact:true}).click();
  expect((await previewRequest).postDataJSON().split_groups).toEqual([0]);
  await expect(panel.locator('.copyedit-selected-text')).toHaveText(PARTIAL);

  // «Разом» returns one checkbox, undetermined for a partial choice; splitting again keeps the choice.
  await block.getByRole('button',{name:'Разом',exact:true}).click();
  await expect(panel.locator('.copyedit-split')).toHaveCount(0);
  const group=panel.locator('.copyedit-item input[type=checkbox]');
  await expect(group).toHaveCount(1);
  expect(await group.evaluate(e=>e.indeterminate)).toBe(true);
  await expect(panel.locator('[data-review-accept]')).toBeDisabled();
  await panel.getByRole('button',{name:'Прийняти окремо (2)',exact:true}).click();
  await expect(panel.locator('.copyedit-split input[type=checkbox]:checked')).toHaveCount(1);
  await panel.getByRole('button',{name:'Переглянути виправлений текст',exact:true}).click();
  await expect(panel.locator('.copyedit-selected-text')).toHaveText(PARTIAL);

  const attemptId=await panel.locator('select').inputValue();
  const applyRequest=page.waitForRequest(r=>r.method()==='POST'&&new URL(r.url()).pathname===`/api/scenes/${f.scene_id}/copyedits/${attemptId}`);
  // The workspace primary button accepts the review; a confirmation dialog, if any, is confirmed.
  await page.addLocatorHandler(page.locator('.app-dialog'),async dialog=>{await dialog.locator('.app-dialog-actions button').last().click()});
  await expect(page.locator('#workspace-primary')).toBeEnabled();
  await page.locator('#workspace-primary').click();
  expect((await applyRequest).postDataJSON()).toMatchObject({selected_indices:[1],split_groups:[0]});
  await expect.poll(async()=>(await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json()).scene.heads.prose||null).not.toBeNull();
  const versions=await(await request.get(`/api/scenes/${f.scene_id}/versions`)).json();
  const prose=await(await request.get(`/api/versions/${versions.scene.heads.prose}`)).json();
  expect(prose.text).toBe(PARTIAL);
  expect(prose.text).not.toBe(ORIGINAL);

  // The last decision opens the group split again after a reload.
  const again=await openReview(page,f);
  await expect(again.locator('.copyedit-split')).toHaveCount(1);
  await expect(again.locator('.copyedit-split input[type=checkbox]:checked')).toHaveCount(1);
  await expect(again.locator('[data-split-result]')).toHaveText('Вийде так: '+PARTIAL);
});

test.describe('english interface',()=>{
  test.use({locale:'en-US'});
  test('english labels for the split view',async({page,request})=>{
    const f=await(await request.post('/test-edit-split')).json();
    await page.goto(`/stories/${f.story_id}?scene=${f.scene_id}&material=review`);
    const panel=page.locator('.copyedit-review').filter({has:page.locator('summary',{hasText:'Editor changes'})});
    await expect(panel.locator('select option')).toHaveCount(1);
    if(!await panel.evaluate(e=>e.open))await panel.locator('summary').click();
    await panel.getByRole('button',{name:'Accept separately (2)',exact:true}).click();
    await expect(panel.getByRole('button',{name:'Together',exact:true})).toBeVisible();
    await expect(panel.locator('[data-split-result]')).toHaveText('Result: '+ORIGINAL);
  });
});
