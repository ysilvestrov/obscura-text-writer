import {test,expect} from '../../../frontend/browser-test.mjs';

// VALID-LINKS in the browser: «Перевірити сцену» runs the auditor only after the preview and the author's consent; its
// discrepancies appear in the link panel as hints with quotes, and the author's approval clears the row.
test.use({locale:'uk-UA'});

test('a valid scene offers no check',async({page,request})=>{
  const fixture=await(await request.post('/test-card-invalidation')).json();
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  await expect(page.locator('#workspace-scene-status')).toContainText('Валідна');
  await expect(page.locator('#audit-scene')).toBeHidden();
});

test('the auditor checks the scene after consent and the author approves its discrepancy',async({page,request})=>{
  const fixture=await(await request.post('/test-scene-audit')).json();
  const runs=async()=>(await(await request.get(`/api/stories/${fixture.story_id}/runs`)).json()).runs;
  await page.goto(`/stories/${fixture.story_id}?scene=${fixture.scene_id}&material=prose`);
  const button=page.locator('#audit-scene');
  await expect(button).toBeVisible();
  await expect(button).toHaveText('Перевірити сцену');
  // The preview names the links and the auditor's model; cancelling it starts nothing.
  await button.click();
  let dialog=page.getByRole('dialog');
  await expect(dialog).toContainText('Зв’язки до перевірки: завдання, проза');
  await expect(dialog).toContainText('synthetic-auditor');
  await dialog.getByRole('button',{name:'Скасувати'}).click();
  await expect(dialog).toBeHidden();
  expect(await runs()).toEqual([]);
  await button.click();
  dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Підтвердити'}).click();
  // The run stops on the brief: the panel shows both discrepancies with their quotes as hints to check.
  const panel=page.locator('#link-attention');
  const row=panel.locator('[data-link="brief"]');
  await expect(row).toContainText('Ревізор вважає');
  await expect(row).toContainText('35%');
  await expect(row).toContainText('пояснення моделі можуть бути неточними');
  await expect(row.locator('.link-discrepancy')).toHaveCount(2);
  await expect(row).toContainText('Місце дії не збігається з планом');
  await expect(row.locator('blockquote').first()).toHaveText('Світло на воді');
  await expect.poll(async()=>(await runs()).at(-1)?.state).toBe('needs_review');
  const run=(await(await request.get(`/api/runs/${(await runs()).at(-1).id}`)).json()).run;
  expect(run.request.mode).toBe('audit');
  expect(run.checkpoint.link).toBe('brief');
  await row.getByRole('button',{name:'Затвердити завдання'}).click();
  await expect(panel.locator('[data-link="brief"]')).toHaveCount(0);
  const view=await(await request.get(`/api/stories/${fixture.story_id}`)).json();
  expect(view.material_status[fixture.scene_id].links.brief.source).toBe('author');
});

// MODEL-001: an auditor without saved settings runs on the editor's model; saving its form keeps a row of its own, with
// the stage prompts of audit_brief and audit_memory beside the main one.
test('the auditor settings borrow the editor until saved',async({page,request})=>{
  const fixture=await(await request.post('/test-memory-decision')).json();
  const url=`/api/stories/${fixture.story_id}/settings`;
  await page.goto(`/stories/${fixture.story_id}/settings`);
  await page.locator('[data-settings-role="auditor"]').click();
  const form=page.locator('form[data-role="auditor"]');
  await expect(form.locator('[data-auditor-derived]')).toHaveText('Поки Ревізора не збережено, він бере модель редактора.');
  await expect(form.locator('[name="model"]')).toHaveValue('synthetic-editor');
  await expect(form.locator('[name="stage_audit_brief"]')).toHaveCount(1);
  await expect(form.locator('[name="stage_audit_memory"]')).toHaveCount(1);
  await form.locator('summary',{hasText:'Промпти та їхні призначення'}).click();
  await form.locator('[name="stage_audit_brief"]').fill('Перевір завдання сцени й відповідай JSON.');
  const saved=page.waitForResponse(r=>r.url().endsWith(url)&&r.request().method()==='PUT');
  await page.locator('#settings-save').click();
  expect((await saved).ok()).toBe(true);
  const data=await(await request.get(url)).json();
  expect(data.roles.auditor.derived).toBeUndefined();
  expect(data.roles.auditor.provider.model).toBe('synthetic-editor');
  expect(data.stage_prompts.auditor.audit_brief).toBe('Перевір завдання сцени й відповідай JSON.');
  await expect(form.locator('[data-auditor-derived]')).toHaveCount(0);
});
